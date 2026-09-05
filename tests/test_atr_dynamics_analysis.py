import unittest

import numpy as np
import pandas as pd

from research.atr_dynamics_analysis import add_atr_dynamics, calculate_real_atr


class AtrDynamicsAnalysisTests(unittest.TestCase):
    def setUp(self):
        count = 40
        times = pd.date_range("2026-01-01", periods=count, freq="4h", tz="UTC")
        close = pd.Series(np.linspace(100, 120, count))
        self.candles = pd.DataFrame({
            "open_time": times, "high": close + np.linspace(1, 3, count),
            "low": close - np.linspace(1, 3, count), "close": close,
        })
        self.trades = pd.DataFrame({
            "entry_signal_time": [times[30]], "signal": ["LONG"],
            "pnl_neto": [1.0], "max_adverse_pct": [-.5],
        })

    def test_changes_use_signal_and_past_atr_only(self):
        original = add_atr_dynamics(self.trades, self.candles)
        changed = self.candles.copy()
        changed.loc[31:, ["high", "low", "close"]] = 999999
        actual = add_atr_dynamics(self.trades, changed)
        for window in (1, 2, 3):
            self.assertEqual(original[f"atr_change_{window}"].iloc[0],
                             actual[f"atr_change_{window}"].iloc[0])

    def test_real_atr_is_wilder_smoothed_and_available(self):
        atr = calculate_real_atr(self.candles)
        self.assertTrue(atr.iloc[:13].isna().all())
        self.assertGreater(atr.iloc[-1], 0)


if __name__ == "__main__":
    unittest.main()
