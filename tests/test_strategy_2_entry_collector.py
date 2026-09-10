import json
import tempfile
import unittest
from types import SimpleNamespace

import pandas as pd

from ai_decision.budget import RunBudget
from ai_decision.runs import AIRunIdentity, AIRunManager
from ai_decision.service import DecisionService
from ai_decision.store import DecisionStore
from backtest.strategy_2_candidates import enumerate_flat_entry_candidates
from backtest.strategy_2_engine import build_entry_request
from backtest.strategy_2_entry_collector import Strategy2EntryCollector
from data.frozen_market_data import FrozenMarketDataStore


class FakeMarket:
    def __init__(self, count=2):
        self.events = [pd.Timestamp(f"2026-01-01 0{index}:00", tz="UTC")
                       for index in range(1, count + 1)]

    def event_times(self):
        return self.events

    def view_at(self, timestamp):
        return timestamp


class FlatCandidateStrategy:
    def __init__(self):
        self.config = SimpleNamespace(version="strategy_2_v1")
        self.state = SimpleNamespace(last_setup_candle=None, last_confirmation_candle=None)

    def prepare_market_data(self, market):
        return market

    def evaluate(self, timestamp):
        side = "LONG" if timestamp.hour % 2 else "SHORT"
        setup = timestamp - pd.Timedelta(hours=1)
        self.state.last_setup_candle = setup
        self.state.last_confirmation_candle = timestamp
        return SimpleNamespace(
            candidate_id=f"candidate-{timestamp.hour}", side=side,
            setup_time=setup, confirmation_time=timestamp,
            context={"symbol": "BTCUSDT", "as_of": timestamp.isoformat()},
        )

    def reset(self):
        self.state = SimpleNamespace(last_setup_candle=None, last_confirmation_candle=None)


class FakeEntryClient:
    def __init__(self, decision="APPROVE"):
        self.decision, self.calls = decision, 0

    def structured_response(self, **kwargs):
        self.calls += 1
        return ({"decision": self.decision, "side": kwargs["payload"]["candidate"]["side"],
                 "confidence": .75, "reason_codes": ["TEST"], "summary": "test"},
                {"response_id": f"response-{self.calls}",
                 "usage": {"input_tokens": 10, "output_tokens": 5}})


def identity(mode="replay"):
    return AIRunIdentity(
        "strategy_2_v1", "bundle", "hash", "openai", "test-model", "low",
        "strategy2-entry-v1", "strategy2-exit-v1", "1.0.0", mode,
        "entry_collection",
    )


def service_and_run(store, mode, client=None, run_id="collector-run", max_calls=20):
    manager = AIRunManager(store, identity(mode), run_id)
    manager.start()
    budget = RunBudget(manager, max_cost_usd=10, max_live_calls=max_calls,
                       max_output_tokens=50, input_cost_per_million=2,
                       output_cost_per_million=12)
    service = DecisionService(client, store, model="test-model", mode=mode,
                              budget=budget, run_manager=manager, max_output_tokens=50)
    service.review_exit = lambda payload: (_ for _ in ()).throw(
        AssertionError("ENTRY collection invoked EXIT review")
    )
    return service, manager


class Strategy2EntryCollectorTests(unittest.TestCase):
    def collect(self, store, mode="replay", client=None, run_id="collector-run",
                count=2, max_calls=20):
        service, manager = service_and_run(store, mode, client, run_id, max_calls)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        result = Strategy2EntryCollector(
            FlatCandidateStrategy(), service, store, manager, temporary.name
        ).run(FakeMarket(count))
        return result, service, manager

    def test_replay_empty_cache_completes_with_missing_records(self):
        result, _, _ = self.collect(DecisionStore(":memory:"))
        summary = result.summary()
        self.assertEqual(summary["missing"], 2)
        self.assertEqual(summary["live_calls"], 0)
        self.assertEqual(summary["positions_opened"], 0)
        self.assertEqual(summary["trades"], 0)
        self.assertEqual(summary["exit_reviews"], 0)

    def test_cached_approvals_and_rejections_never_open_positions_or_call_exit(self):
        store = DecisionStore(":memory:")
        probe = DecisionService(None, store, model="test-model", mode="replay")
        _, envelopes = enumerate_flat_entry_candidates(FakeMarket(), FlatCandidateStrategy())
        for index, envelope in enumerate(envelopes):
            decision = "APPROVE" if index == 0 else "REJECT"
            store.put(probe.cache_key("ENTRY", envelope.payload), "ENTRY", envelope.payload,
                      {"decision": decision, "side": envelope.candidate.side, "confidence": .7,
                       "reason_codes": [], "summary": "cached"}, {})
        result, _, _ = self.collect(store)
        summary = result.summary()
        self.assertEqual((summary["approve"], summary["reject"], summary["cache_hits"]), (1, 1, 2))
        self.assertEqual((summary["positions_opened"], summary["trades"], summary["exit_reviews"]),
                         (0, 0, 0))

    def test_live_fake_client_obeys_max_calls_and_can_resume_from_cache(self):
        store = DecisionStore(":memory:")
        first_client = FakeEntryClient("APPROVE")
        first, _, first_manager = self.collect(
            store, "live", first_client, run_id="resume-run", max_calls=1
        )
        self.assertFalse(first.completed)
        self.assertEqual(first_client.calls, 1)
        first_manager.interrupt({"reason": first.stop_reason})
        second_client = FakeEntryClient("REJECT")
        second, _, _ = self.collect(
            store, "live", second_client, run_id="resume-run", max_calls=3
        )
        self.assertTrue(second.completed)
        self.assertEqual(second_client.calls, 1)
        self.assertTrue(second.records[0]["cache_hit"])
        self.assertEqual(second.records[0]["ai_status"], "APPROVE")
        self.assertEqual(second.records[1]["ai_status"], "REJECT")

    def test_unknown_candidate_blocks_duplicate_live_call(self):
        store = DecisionStore(":memory:")
        service, manager = service_and_run(store, "live", FakeEntryClient())
        _, envelopes = enumerate_flat_entry_candidates(FakeMarket(1), FlatCandidateStrategy())
        key = service.cache_key("ENTRY", envelopes[0].payload)
        store.mark_pending(key, manager.run_id, "ENTRY", 1)
        store.mark_pending_unknown(key)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        result = Strategy2EntryCollector(
            FlatCandidateStrategy(), service, store, manager, temporary.name
        ).run(FakeMarket(1))
        self.assertEqual(result.records[0]["ai_status"], "UNKNOWN")
        self.assertEqual(service.client.calls, 0)

    def test_dataset_is_pre_outcome_and_payload_hash_matches_full_backtest(self):
        store = DecisionStore(":memory:")
        result, service, _ = self.collect(store, count=1)
        record = result.records[0]
        forbidden = {"pnl", "mfe", "mae", "trade_result", "future_outcome"}
        self.assertTrue(forbidden.isdisjoint(record))
        _, envelopes = enumerate_flat_entry_candidates(FakeMarket(1), FlatCandidateStrategy())
        full_payload = build_entry_request(FlatCandidateStrategy(), envelopes[0].candidate)
        self.assertEqual(envelopes[0].payload, full_payload)
        self.assertEqual(record["input_hash"], service.cache_key("ENTRY", full_payload))
        with open(result.output_json, encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(payload["records"][0]["candidate_id"], record["candidate_id"])

    def test_candidate_order_ids_and_hashes_are_deterministic(self):
        market = FakeMarket(2)
        _, first = enumerate_flat_entry_candidates(market, FlatCandidateStrategy())
        _, second = enumerate_flat_entry_candidates(market, FlatCandidateStrategy())
        first_values = [(item.candidate.candidate_id, item.evaluation_time, item.payload) for item in first]
        second_values = [(item.candidate.candidate_id, item.evaluation_time, item.payload) for item in second]
        self.assertEqual(first_values, second_values)
        self.assertEqual([item.evaluation_time for item in first], sorted(item.evaluation_time for item in first))

    def test_frozen_bundle_census_is_reproducible(self):
        market = FrozenMarketDataStore().load_bundle("btcusdt_1d_4h_1h_2026_08")
        _, first = enumerate_flat_entry_candidates(market)
        _, second = enumerate_flat_entry_candidates(market)
        self.assertEqual(len(first), 81)
        self.assertEqual(sum(item.candidate.side == "LONG" for item in first), 18)
        self.assertEqual(sum(item.candidate.side == "SHORT" for item in first), 63)
        self.assertEqual(
            [(item.candidate.candidate_id, item.evaluation_time) for item in first],
            [(item.candidate.candidate_id, item.evaluation_time) for item in second],
        )
