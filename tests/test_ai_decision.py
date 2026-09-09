import tempfile
import unittest

from ai_decision.schemas import DecisionSchemaError
from ai_decision.service import (
    AIDecisionUnavailableError, AIRequestStateUnknownError, DecisionService,
)
from ai_decision.store import DecisionStore


class FakeClient:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), 0

    def structured_response(self, **kwargs):
        self.calls += 1
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value, f"response-{self.calls}"


def entry_payload():
    return {"candidate": {"side": "LONG"}, "market_context": {"close": 100.0}}


class AIDecisionTests(unittest.TestCase):
    def test_live_decision_is_cached_and_replayed_without_second_call(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DecisionStore(f"{directory}/cache.db")
            client = FakeClient([{"decision": "APPROVE", "side": "LONG", "confidence": .7,
                                  "reason_codes": ["ALIGNED"], "summary": "ok"}])
            live = DecisionService(client, store, model="test-model", mode="live")
            self.assertEqual(live.review_entry(entry_payload()).decision, "APPROVE")
            replay = DecisionService(None, store, model="test-model", mode="replay")
            self.assertEqual(replay.review_entry(entry_payload()).decision, "APPROVE")
            self.assertEqual(client.calls, 1)

    def test_replay_cache_miss_fails_explicitly(self):
        service = DecisionService(None, DecisionStore(":memory:"), model="test", mode="replay")
        with self.assertRaises(AIDecisionUnavailableError):
            service.review_entry(entry_payload())

    def test_invalid_or_wrong_side_output_is_rejected(self):
        client = FakeClient([{"decision": "APPROVE", "side": "SHORT", "confidence": .7,
                              "reason_codes": [], "summary": "bad"}])
        service = DecisionService(client, DecisionStore(":memory:"), model="test", mode="live")
        with self.assertRaises(AIDecisionUnavailableError) as raised:
            service.review_entry(entry_payload())
        self.assertIsInstance(raised.exception.__cause__, DecisionSchemaError)

    def test_timeout_is_not_retried_when_response_state_is_unknown(self):
        client = FakeClient([TimeoutError(), {"decision": "REJECT", "side": "LONG",
                                              "confidence": .5, "reason_codes": [], "summary": "no"}])
        service = DecisionService(client, DecisionStore(":memory:"), model="test", mode="live",
                                  max_attempts=2, sleep=lambda _: None)
        with self.assertRaises(AIRequestStateUnknownError):
            service.review_entry(entry_payload())
        self.assertEqual(client.calls, 1)

    def test_reasoning_effort_is_part_of_cache_identity(self):
        store = DecisionStore(":memory:")
        low = DecisionService(None, store, model="test", mode="replay", reasoning_effort="low")
        medium = DecisionService(None, store, model="test", mode="replay", reasoning_effort="medium")
        self.assertNotEqual(low.cache_key("ENTRY", entry_payload()),
                            medium.cache_key("ENTRY", entry_payload()))

    def test_refusal_like_invalid_output_is_not_retried(self):
        client = FakeClient([ValueError("refusal")])
        service = DecisionService(client, DecisionStore(":memory:"), model="test", mode="live",
                                  max_attempts=3, sleep=lambda _: None)
        with self.assertRaises(AIDecisionUnavailableError):
            service.review_entry(entry_payload())
        self.assertEqual(client.calls, 1)
