import hashlib
import json
import tempfile
import unittest

from ai_decision.entry_reviews import ENTRY_REVIEW_V1, ENTRY_REVIEW_V2
from ai_decision.schemas import DecisionSchemaError
from ai_decision.service import DecisionService
from ai_decision.store import DecisionStore
from backtest.strategy_2_candidates import enumerate_flat_entry_candidates
from backtest.strategy_2_engine import assert_entry_request_pre_outcome
from backtest.strategy_2_entry_collector import Strategy2EntryCollector
from data.frozen_market_data import FrozenMarketDataStore


BUNDLE = "btcusdt_1d_4h_1h_2026_08"
CANDIDATE_FINGERPRINT = "437f242e6f96d8c441359321d10c48e317f8281cb5be86a39501843db808285a"
V1_INPUT_FINGERPRINT = "6115bd906cf50d587e72310ac0985e186d59381c6ac15c87464ed1902c282ccd"
V2_INPUT_FINGERPRINT = "521c0adecf70ffcbdfbde21dda75abb93d09802fa9f5da28d4147c5cb8bd67c2"
FORBIDDEN = {
    "pnl", "future_return", "trade_result", "winner", "loser",
    "mfe_after_entry", "mae_after_entry", "future_high", "future_low",
    "exit_price", "exit_time",
}


def fingerprints(envelopes, service):
    sequence = [{"candidate_id": item.candidate.candidate_id,
                 "evaluation_time": item.evaluation_time.isoformat(),
                 "side": item.candidate.side} for item in envelopes]
    candidate = hashlib.sha256(
        json.dumps(sequence, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    inputs = [{**row, "input_hash": service.cache_key("ENTRY", item.payload)}
              for row, item in zip(sequence, envelopes)]
    input_sequence = hashlib.sha256(
        json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return candidate, input_sequence


def payload_keys(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key.lower()
            yield from payload_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from payload_keys(nested)


class FakeV2Client:
    def __init__(self):
        self.calls = 0

    def structured_response(self, **kwargs):
        self.calls += 1
        return ({"decision": "APPROVE",
                 "side": kwargs["payload"]["candidate"]["side"],
                 "confidence": .8,
                 "reason_codes": ["MOMENTUM_REVERSAL_CLEAR"],
                 "summary": "Causal reversal semantics are explicit."},
                {"usage": {"input_tokens": 10, "output_tokens": 5}})


class NoRunManager:
    run_id = "v2-test"

    def __init__(self):
        self.values = {"live_calls": 0, "cache_hits": 0, "input_tokens": 0,
                       "output_tokens": 0, "estimated_cost_usd": 0.0,
                       "actual_cost_usd": 0.0}

    def counters(self):
        return dict(self.values)

    def checkpoint(self, _):
        pass


class Strategy2EntryV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.market = FrozenMarketDataStore().load_bundle(BUNDLE)
        _, cls.v1 = enumerate_flat_entry_candidates(
            cls.market, entry_prompt_version=ENTRY_REVIEW_V1.prompt_version,
        )
        _, cls.v2 = enumerate_flat_entry_candidates(
            cls.market, entry_prompt_version=ENTRY_REVIEW_V2.prompt_version,
        )

    def test_candidate_sequence_is_unchanged_but_inputs_are_versioned(self):
        store = DecisionStore(":memory:")
        v1_service = DecisionService(None, store, model="gpt-5.6-terra", mode="replay")
        v2_service = DecisionService(None, store, model="gpt-5.6-terra", mode="replay",
                                     entry_review_version="v2")
        self.assertEqual(len(self.v1), 81)
        self.assertEqual(sum(item.candidate.side == "LONG" for item in self.v2), 18)
        self.assertEqual(sum(item.candidate.side == "SHORT" for item in self.v2), 63)
        self.assertEqual(fingerprints(self.v1, v1_service),
                         (CANDIDATE_FINGERPRINT, V1_INPUT_FINGERPRINT))
        self.assertEqual(fingerprints(self.v2, v2_service),
                         (CANDIDATE_FINGERPRINT, V2_INPUT_FINGERPRINT))
        self.assertNotEqual(v1_service.cache_key("ENTRY", self.v1[0].payload),
                            v2_service.cache_key("ENTRY", self.v2[0].payload))

    def test_v2_semantics_match_existing_reversal_rules_without_future_fields(self):
        expected = {
            "LONG": ("dark_red -> light_red", "recovering toward zero"),
            "SHORT": ("dark_green -> light_green", "weakening"),
        }
        for envelope in self.v2:
            payload = envelope.payload
            side = envelope.candidate.side
            self.assertTrue(FORBIDDEN.isdisjoint(payload_keys(payload)))
            self.assertEqual(payload["candidate"]["candidate_side"], side)
            self.assertEqual(payload["candidate"]["setup_direction"], side)
            self.assertEqual(payload["candidate"]["confirmation_direction"], side)
            for timeframe in ("setup_4h", "confirmation_1h"):
                semantics = payload["strategy_semantics"][timeframe]
                self.assertEqual(semantics["direction"], side)
                self.assertEqual(semantics["transition"], expected[side][0])
                self.assertIn(expected[side][1], semantics["transition_interpretation"])
            self.assertLessEqual(envelope.candidate.setup_time, envelope.evaluation_time)
            self.assertLessEqual(envelope.candidate.confirmation_time, envelope.evaluation_time)

    def test_v2_schema_rejects_free_form_reason_codes(self):
        valid = {"decision": "REJECT", "side": "LONG", "confidence": .8,
                 "reason_codes": ["TREND_CONFLICT"], "summary": "Conflict."}
        self.assertEqual(ENTRY_REVIEW_V2.parse(valid, "LONG").decision, "REJECT")
        invalid = {**valid, "reason_codes": ["FREE_FORM_REASON"]}
        with self.assertRaises(DecisionSchemaError):
            ENTRY_REVIEW_V2.parse(invalid, "LONG")

    def test_runtime_guard_rejects_outcome_fields(self):
        with self.assertRaisesRegex(ValueError, "Forbidden future/outcome"):
            assert_entry_request_pre_outcome({"context": {"future_return": 1.0}})

    def test_v2_collector_approvals_remain_flat_and_never_review_exit(self):
        store = DecisionStore(":memory:")
        client = FakeV2Client()
        manager = NoRunManager()
        service = DecisionService(client, store, model="gpt-5.6-terra", mode="live",
                                  run_manager=manager, entry_review_version="v2")
        service.review_exit = lambda _: self.fail("V2 collector invoked EXIT review")
        with tempfile.TemporaryDirectory() as directory:
            result = Strategy2EntryCollector(
                None, service, store, manager, directory,
            ).run(self.market)
        summary = result.summary()
        self.assertEqual(summary["approve"], 81)
        self.assertEqual(client.calls, 81)
        self.assertEqual((summary["positions_opened"], summary["trades"],
                          summary["exit_reviews"]), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
