import unittest

import numpy as np
import pandas as pd

from research.adx_trend_analysis import (
    calculate_dmi_adx,
    classify_alignment,
    enrich_trades,
    wilder_rma,
)


class AdxTrendAnalysisTests(unittest.TestCase):
    def test_wilder_rma_uses_sma_seed_then_recursive_update(self):
        values = pd.Series([1.0, 2.0, 3.0, 6.0])
        result = wilder_rma(values, 3)
        self.assertTrue(result.iloc[:2].isna().all())
        self.assertAlmostEqual(result.iloc[2], 2.0)
        self.assertAlmostEqual(result.iloc[3], 10 / 3)

    def test_dmi_adx_on_monotonic_market(self):
        count = 50
        close = pd.Series(np.arange(100.0, 100.0 + count))
        candles = pd.DataFrame({"high": close + 1, "low": close - 1, "close": close})
        result = calculate_dmi_adx(candles)
        self.assertAlmostEqual(result.plus_di.iloc[-1], 50)
        self.assertEqual(result.minus_di.iloc[-1], 0)
        self.assertAlmostEqual(result.dx.iloc[-1], 100)
        self.assertAlmostEqual(result.adx.iloc[-1], 100)
        self.assertEqual(result.adx.first_valid_index(), 27)

    def test_alignment_is_side_aware(self):
        self.assertEqual(classify_alignment("LONG", 30, 10), "ALIGNED")
        self.assertEqual(classify_alignment("SHORT", 30, 10), "COUNTER")
        self.assertEqual(classify_alignment("SHORT", 10, 30), "ALIGNED")
        self.assertEqual(classify_alignment("LONG", 20, 20), "NEUTRAL")

    def test_entry_classification_does_not_read_future(self):
        count = 80
        times = pd.date_range("2026-01-01", periods=count, freq="4h", tz="UTC")
        close = pd.Series(100 + np.sin(np.arange(count) / 3) * 5 + np.arange(count) / 10)
        candles = pd.DataFrame({"open_time": times, "high": close + 2,
                                "low": close - 2, "close": close})
        trades = pd.DataFrame({"entry_signal_time": [times[60]], "signal": ["LONG"],
                               "pnl_neto": [1.0], "max_favorable_pct": [2.0],
                               "max_adverse_pct": [-1.0], "duration_hours": [48]})
        expected, _ = enrich_trades(trades, candles)
        changed = candles.copy()
        changed.loc[61:, ["high", "low", "close"]] = 999999
        actual, _ = enrich_trades(trades, changed)
        for column in ("plus_di", "minus_di", "dx", "adx", "adx_change_1", "alignment"):
            self.assertEqual(expected[column].iloc[0], actual[column].iloc[0])

    def test_adx_bands_are_reproducible_and_balanced(self):
        count = 130
        times = pd.date_range("2026-01-01", periods=count, freq="4h", tz="UTC")
        close = pd.Series(100 + np.sin(np.arange(count) / 4) * 5 + np.arange(count) / 20)
        candles = pd.DataFrame({"open_time": times, "high": close + 2,
                                "low": close - 2, "close": close})
        selected = list(range(40, 130))
        trades = pd.DataFrame({"entry_signal_time": times[selected],
                               "signal": ["LONG", "SHORT"] * 45,
                               "pnl_neto": np.ones(90), "max_favorable_pct": np.ones(90),
                               "max_adverse_pct": -np.ones(90), "duration_hours": np.ones(90)})
        first, _ = enrich_trades(trades, candles)
        second, _ = enrich_trades(trades, candles)
        self.assertEqual(first.adx_band.tolist(), second.adx_band.tolist())
        self.assertEqual(first.adx_band.value_counts().to_dict(), {"LOW": 30, "MID": 30, "HIGH": 30})


if __name__ == "__main__":
    unittest.main()
