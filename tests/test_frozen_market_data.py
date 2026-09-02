import tempfile
import unittest

import pandas as pd

from data.frozen_market_data import FrozenMarketDataStore


class FrozenMarketDataTests(unittest.TestCase):
    def test_snapshot_round_trip_and_no_accidental_overwrite(self):
        candles = pd.DataFrame({
            "open_time": pd.to_datetime(["2026-01-01"], utc=True),
            "open": [1.0], "high": [2.0], "low": [0.5], "close": [1.5],
            "volume": [10.0],
            "close_time": pd.to_datetime(["2026-01-01 03:59:59"], utc=True),
        })
        with tempfile.TemporaryDirectory() as directory:
            store = FrozenMarketDataStore(directory)
            store.save("sample", candles, {"symbol": "BTCUSDT"})
            loaded = store.load("sample")

            self.assertEqual(len(loaded), 1)
            self.assertEqual(store.metadata("sample")["symbol"], "BTCUSDT")
            with self.assertRaises(FileExistsError):
                store.save("sample", candles)


if __name__ == "__main__":
    unittest.main()
