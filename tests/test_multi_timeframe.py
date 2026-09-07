import tempfile
import unittest
from pathlib import Path

import pandas as pd

from data.frozen_market_data import FrozenMarketDataStore
from exchange.multi_timeframe import MultiTimeframeMarketData


def candles(frequency, periods=3):
    opened = pd.date_range("2026-01-01", periods=periods, freq=frequency, tz="UTC")
    delta = pd.Timedelta(frequency)
    return pd.DataFrame({"open_time": opened, "open": range(1, periods + 1),
                         "high": range(2, periods + 2), "low": range(periods),
                         "close": range(1, periods + 1), "volume": 1.0,
                         "close_time": opened + delta - pd.Timedelta(milliseconds=1)})


class MultiTimeframeTests(unittest.TestCase):
    def test_view_never_exposes_unclosed_candle(self):
        frame = candles("1h")
        market = MultiTimeframeMarketData("BTCUSDT", {"1h": frame})
        exactly_at_close = market.view_at(frame.close_time.iloc[1])
        just_after_close = market.view_at(frame.close_time.iloc[1] + pd.Timedelta(milliseconds=1))
        self.assertEqual(len(exactly_at_close.frame("1h")), 1)
        self.assertEqual(len(just_after_close.frame("1h")), 2)

    def test_bundle_reuses_snapshots_and_validates_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            store = FrozenMarketDataStore(directory)
            store.save("one", candles("1h"), {"symbol": "BTCUSDT", "timeframe": "1h"})
            store.save("four", candles("4h"), {"symbol": "BTCUSDT", "timeframe": "4h"})
            store.save_bundle("bundle", "BTCUSDT", {"1h": "one", "4h": "four"})
            loaded = store.load_bundle("bundle")
            self.assertEqual(loaded.timeframes, ("1h", "4h"))
            self.assertEqual(len(loaded.full_frame("4h")), 3)
