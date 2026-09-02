import unittest

import pandas as pd

from backtest.engine import run_signal_analysis


class BacktestExecutionTests(unittest.TestCase):
    def test_signals_execute_at_next_real_open(self):
        times = pd.date_range("2026-01-01", periods=4, freq="4h", tz="UTC")
        candles = pd.DataFrame({
            "open_time": times,
            "open": [100.0, 101.0, 104.0, 106.0],
            "high": [102.0, 105.0, 107.0, 108.0],
            "low": [99.0, 100.0, 103.0, 105.0],
            "close": [101.0, 104.0, 106.0, 107.0],
        })
        signals = [
            {"open_time": times[0], "signal": "LONG"},
            {"open_time": times[2], "signal": "SHORT"},
        ]

        results = run_signal_analysis(
            candles, signals,
            commission_rate=0, slippage_rate=0, funding_rate=0,
        )
        closed = results.iloc[0]

        self.assertEqual(closed["entry_time"], times[1])
        self.assertEqual(closed["entry_price"], 101.0)
        self.assertEqual(closed["exit_time"], times[3])
        self.assertEqual(closed["exit_price"], 106.0)
        self.assertAlmostEqual(closed["pnl_pct"], 4.950495, places=5)

    def test_signal_on_last_candle_is_not_executed(self):
        times = pd.date_range("2026-01-01", periods=2, freq="4h", tz="UTC")
        candles = pd.DataFrame({
            "open_time": times, "open": [1.0, 2.0], "high": [2.0, 3.0],
            "low": [0.5, 1.5], "close": [1.5, 2.5]
        })
        results = run_signal_analysis(
            candles, [{"open_time": times[-1], "signal": "LONG"}]
        )
        self.assertTrue(results.empty)


if __name__ == "__main__":
    unittest.main()
