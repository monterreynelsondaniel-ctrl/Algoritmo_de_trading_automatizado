import unittest

import pandas as pd

from exchange.multi_timeframe import MarketDataView
from strategies.strategy_2 import Strategy2


def frame(times, colors=None, ema_fast=110, ema_slow=100):
    count = len(times)
    result = pd.DataFrame({"open_time": times, "close_time": times,
                           "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
                           "volume": 1.0, "ema_10": ema_fast, "ema_55": ema_slow})
    if colors:
        result["sqzmom_color"] = colors
        result["sqzmom"] = 1.0
    return result


class Strategy2Tests(unittest.TestCase):
    def test_confirmation_must_be_after_aligned_setup(self):
        strategy = Strategy2()
        setup_times = pd.to_datetime(["2026-01-01 00:00", "2026-01-01 04:00"], utc=True)
        same = pd.to_datetime(["2026-01-01 03:00", "2026-01-01 04:00"], utc=True)
        later = pd.to_datetime(["2026-01-01 04:00", "2026-01-01 05:00"], utc=True)
        daily = frame(pd.to_datetime(["2025-12-31"], utc=True))
        setup = frame(setup_times, ["dark_red", "light_red"])
        first = MarketDataView("BTCUSDT", pd.Timestamp("2026-01-01 04:00", tz="UTC"),
                               {"1d": daily, "4h": setup, "1h": frame(same, ["dark_red", "light_red"])})
        self.assertIsNone(strategy.evaluate(first))
        second = MarketDataView("BTCUSDT", pd.Timestamp("2026-01-01 05:00", tz="UTC"),
                                {"1d": daily, "4h": setup, "1h": frame(later, ["dark_red", "light_red"])})
        candidate = strategy.evaluate(second)
        self.assertEqual(candidate.side, "LONG")
        self.assertGreater(candidate.confirmation_time, candidate.setup_time)

    def test_countertrend_setup_does_not_create_candidate(self):
        strategy = Strategy2()
        times = pd.to_datetime(["2026-01-01 00:00", "2026-01-01 04:00"], utc=True)
        daily = frame(pd.to_datetime(["2025-12-31"], utc=True), ema_fast=90, ema_slow=100)
        view = MarketDataView("BTCUSDT", pd.Timestamp("2026-01-01 05:00", tz="UTC"), {
            "1d": daily, "4h": frame(times, ["dark_red", "light_red"]),
            "1h": frame(times + pd.Timedelta(hours=1), ["dark_red", "light_red"]),
        })
        self.assertIsNone(strategy.evaluate(view))
