import unittest

from ai_decision.budget import AIBudgetExceededError, RunBudget
from ai_decision.runs import AIRunConfigurationMismatchError, AIRunIdentity, AIRunManager
from ai_decision.service import AIDecisionUnavailableError, DecisionService
from ai_decision.store import DecisionStore


def identity(model="gpt-5.6-terra"):
    return AIRunIdentity("strategy_2_v1", "bundle", "hash", "openai", model, "low",
                         "entry-v1", "exit-v1", "1.0.0", "live")


class FakeClient:
    def __init__(self):
        self.calls = 0

    def structured_response(self, **kwargs):
        self.calls += 1
        return ({"decision": "REJECT", "side": "LONG", "confidence": .5,
                 "reason_codes": [], "summary": "no"},
                {"response_id": "response-1", "usage": {"input_tokens": 10, "output_tokens": 5}})


class TimeoutClient:
    def __init__(self):
        self.calls = 0

    def structured_response(self, **kwargs):
        self.calls += 1
        raise TimeoutError()


class AIRunSafetyTests(unittest.TestCase):
    def setUp(self):
        self.store = DecisionStore(":memory:")

    def test_resume_rejects_semantic_configuration_change(self):
        manager = AIRunManager(self.store, identity(), "run-1")
        manager.start()
        manager.interrupt()
        with self.assertRaises(AIRunConfigurationMismatchError):
            AIRunManager(self.store, identity("gpt-5.6-sol"), "run-1").start()

    def test_entry_collection_and_full_backtest_are_distinct_runs(self):
        manager = AIRunManager(self.store, identity(), "run-1")
        manager.start()
        manager.interrupt()
        collection = AIRunIdentity(
            "strategy_2_v1", "bundle", "hash", "openai", "gpt-5.6-terra", "low",
            "entry-v1", "exit-v1", "1.0.0", "live", "entry_collection",
        )
        with self.assertRaises(AIRunConfigurationMismatchError):
            AIRunManager(self.store, collection, "run-1").start()

    def test_checkpoint_and_interrupted_state_are_persisted(self):
        manager = AIRunManager(self.store, identity(), "run-1")
        manager.start()
        manager.checkpoint("2026-01-01T00:00:00+00:00")
        manager.interrupt({"error_type": "KeyboardInterrupt"})
        row = manager.record()
        self.assertEqual(row["status"], "INTERRUPTED")
        self.assertEqual(row["last_processed_event"], "2026-01-01T00:00:00+00:00")

    def test_budget_stops_before_call_limit_is_exceeded(self):
        manager = AIRunManager(self.store, identity(), "run-1")
        manager.start()
        budget = RunBudget(manager, max_cost_usd=10, max_live_calls=1, max_output_tokens=10,
                           input_cost_per_million=2, output_cost_per_million=12)
        budget.authorize(10)
        with self.assertRaises(AIBudgetExceededError):
            budget.authorize(10)
        self.assertEqual(manager.counters()["live_calls"], 1)

    def test_budget_stops_before_cost_limit_is_exceeded(self):
        manager = AIRunManager(self.store, identity(), "run-1")
        manager.start()
        budget = RunBudget(manager, max_cost_usd=.00001, max_live_calls=10, max_output_tokens=10,
                           input_cost_per_million=2, output_cost_per_million=12)
        with self.assertRaises(AIBudgetExceededError):
            budget.authorize(10)
        self.assertEqual(manager.counters()["live_calls"], 0)

    def test_resume_uses_cache_without_new_live_call(self):
        manager = AIRunManager(self.store, identity(), "run-1")
        manager.start()
        budget = RunBudget(manager, max_cost_usd=1, max_live_calls=10, max_output_tokens=50,
                           input_cost_per_million=2, output_cost_per_million=12)
        client = FakeClient()
        service = DecisionService(client, self.store, model="gpt-5.6-terra", mode="live",
                                  budget=budget, run_manager=manager, max_output_tokens=50)
        payload = {"candidate": {"side": "LONG"}, "market_context": {"close": 1}}
        service.review_entry(payload)
        manager.interrupt()
        resumed = AIRunManager(self.store, identity(), "run-1")
        resumed.start()
        resumed_budget = RunBudget(resumed, max_cost_usd=1, max_live_calls=10, max_output_tokens=50,
                                   input_cost_per_million=2, output_cost_per_million=12)
        DecisionService(client, self.store, model="gpt-5.6-terra", mode="live",
                        budget=resumed_budget, run_manager=resumed,
                        max_output_tokens=50).review_entry(payload)
        self.assertEqual(client.calls, 1)
        self.assertEqual(resumed.counters()["cache_hits"], 1)

    def test_replay_miss_never_calls_client(self):
        client = FakeClient()
        service = DecisionService(client, self.store, model="test", mode="replay")
        with self.assertRaises(AIDecisionUnavailableError):
            service.review_entry({"candidate": {"side": "LONG"}})
        self.assertEqual(client.calls, 0)

    def test_unknown_response_window_blocks_duplicate_after_resume(self):
        client = TimeoutClient()
        payload = {"candidate": {"side": "LONG"}}
        first = DecisionService(client, self.store, model="test", mode="live")
        with self.assertRaises(AIDecisionUnavailableError):
            first.review_entry(payload)
        second = DecisionService(client, self.store, model="test", mode="live")
        with self.assertRaisesRegex(AIDecisionUnavailableError, "unresolved prior request"):
            second.review_entry(payload)
        self.assertEqual(client.calls, 1)
