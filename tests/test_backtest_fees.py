import unittest

import pandas as pd

from backtest.engine import run_signal_analysis


def candles_and_signals(entry_reference, exit_reference, first_signal, second_signal):
    times = pd.date_range("2026-01-01", periods=4, freq="4h", tz="UTC")
    candles = pd.DataFrame({
        "open_time": times,
        "open": [entry_reference, entry_reference, exit_reference, exit_reference],
        "high": [entry_reference + 1] * 2 + [exit_reference + 1] * 2,
        "low": [entry_reference - 1] * 2 + [exit_reference - 1] * 2,
        "close": [entry_reference] * 2 + [exit_reference] * 2,
    })
    signals = [
        {"open_time": times[0], "signal": first_signal},
        {"open_time": times[2], "signal": second_signal},
    ]
    return candles, signals


class BacktestFeesTests(unittest.TestCase):
    def test_long_net_pnl_includes_adverse_slippage_and_both_commissions(self):
        candles, signals = candles_and_signals(100, 110, "LONG", "SHORT")
        trade = run_signal_analysis(
            candles, signals, commission_rate=0.001,
            slippage_rate=0.001, funding_rate=0,
        ).iloc[0]

        expected_entry = 100 * 1.001
        expected_exit = 110 * 0.999
        after_slippage = (expected_exit - expected_entry) / expected_entry * 100
        commission = (
            expected_entry * 0.001 + expected_exit * 0.001
        ) / expected_entry * 100

        self.assertAlmostEqual(trade["pnl_bruto"], 10.0)
        self.assertAlmostEqual(trade["pnl_neto"], after_slippage - commission)
        self.assertAlmostEqual(trade["pnl_pct"], trade["pnl_neto"])

    def test_short_net_pnl_includes_adverse_slippage_and_funding(self):
        candles, signals = candles_and_signals(100, 90, "SHORT", "LONG")
        trade = run_signal_analysis(
            candles, signals, commission_rate=0.001,
            slippage_rate=0.001, funding_rate=0.0001,
            funding_interval_hours=8,
        ).iloc[0]

        expected_entry = 100 * 0.999
        expected_exit = 90 * 1.001
        after_slippage = (expected_entry - expected_exit) / expected_entry * 100
        commission = (
            expected_entry * 0.001 + expected_exit * 0.001
        ) / expected_entry * 100

        self.assertEqual(trade["funding_cycles"], 1)
        self.assertAlmostEqual(
            trade["pnl_neto"], after_slippage - commission - 0.01
        )


if __name__ == "__main__":
    unittest.main()
