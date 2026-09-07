import unittest
from types import SimpleNamespace

import pandas as pd

from ai_decision.service import AIDecisionUnavailableError, DecisionService
from ai_decision.store import DecisionStore
from backtest.strategy_2_engine import Strategy2Backtester


class FakeMarket:
    def event_times(self):
        return [pd.Timestamp("2026-01-01 01:00", tz="UTC")]

    def view_at(self, timestamp):
        return object()

    def full_frame(self, timeframe):
        return pd.DataFrame(columns=["open_time", "close_time", "open", "high", "low", "close"])


class CandidateStrategy:
    def __init__(self):
        self.config = SimpleNamespace(confirmation_timeframe="1h", management_timeframe="4h",
                                      version="strategy_2_v1")
        self.resolved = None

    def prepare_market_data(self, market):
        return market

    def evaluate(self, view):
        stamp = pd.Timestamp("2026-01-01", tz="UTC")
        return SimpleNamespace(candidate_id="candidate", side="LONG", setup_time=stamp,
                               confirmation_time=stamp, context={})

    def resolve_candidate(self, approved):
        self.resolved = approved


class Strategy2BacktestTests(unittest.TestCase):
    def test_required_ai_cache_miss_aborts_instead_of_auto_approving(self):
        strategy = CandidateStrategy()
        ai = DecisionService(None, DecisionStore(":memory:"), model="test", mode="replay")
        with self.assertRaisesRegex(AIDecisionUnavailableError, "cannot continue"):
            Strategy2Backtester(strategy, ai).run(FakeMarket())
        self.assertFalse(strategy.resolved)
