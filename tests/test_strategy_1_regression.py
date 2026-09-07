import hashlib
import json
import unittest

from backtest.engine import run_signal_analysis
from backtest.statistics import calculate_backtest_statistics
from data.frozen_market_data import FrozenMarketDataStore
from strategies.registry import get_strategy


SNAPSHOT = "btcusdt_4h_2026_08"
SIGNAL_FINGERPRINT = "58e9115110b5af35219e5db78d029a415c34ffd431014b57da5eeb552c07e11e"
TRADE_FINGERPRINT = "8abc94dab21364b0db6c74e8c8d036fd6d1a7411ec97a0ee80631c670f93445d"


def _fingerprint(payload):
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


class Strategy1RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.strategy = get_strategy("strategy_1")
        cls.candles = FrozenMarketDataStore().load(SNAPSHOT)
        cls.prepared = cls.strategy.prepare_candles(cls.candles)
        cls.signals = cls.strategy.historical_signals(cls.prepared)
        cls.results = run_signal_analysis(cls.prepared, cls.signals)

    def test_signal_sequence_is_frozen(self):
        payload = [
            (
                str(signal["open_time"]), signal["signal"],
                signal["previous_color"], signal["current_color"],
                round(float(signal["sqzmom"]), 10),
            )
            for signal in self.signals
        ]
        self.assertEqual(len(payload), 176)
        self.assertEqual(payload[0][:2], ("2025-09-04 00:00:00+00:00", "SHORT"))
        self.assertEqual(payload[-1][:2], ("2026-08-28 12:00:00+00:00", "SHORT"))
        self.assertEqual(_fingerprint(payload), SIGNAL_FINGERPRINT)

    def test_trade_sequence_and_execution_prices_are_frozen(self):
        payload = []
        for _, trade in self.results.iterrows():
            payload.append((
                str(trade["entry_signal_time"]), str(trade["entry_time"]),
                str(trade.get("exit_signal_time")), str(trade.get("exit_time")),
                trade["signal"], trade["result"],
                None if trade["result"] == "OPEN" else round(float(trade["pnl_neto"]), 10),
                round(float(trade["entry_price"]), 10),
                None if trade["result"] == "OPEN" else round(float(trade["exit_price"]), 10),
            ))
        self.assertEqual(len(payload), 101)
        self.assertEqual(_fingerprint(payload), TRADE_FINGERPRINT)

    def test_fundamental_baseline_metrics_are_frozen(self):
        stats = calculate_backtest_statistics(self.results)
        expected = {
            "total_trades": 100,
            "win_rate": 51.0,
            "total_pnl": -25.09928072148069,
            "compounded_return": -30.0154016163695,
            "profit_factor": 0.8303556086609178,
            "long_pnl": -24.183932654295543,
            "short_pnl": -0.9153480671851426,
        }
        self.assertEqual(stats["total_trades"], expected["total_trades"])
        for key in expected.keys() - {"total_trades"}:
            self.assertAlmostEqual(stats[key], expected[key], places=10, msg=key)

    def test_registry_rejects_unknown_strategy(self):
        with self.assertRaisesRegex(ValueError, "Unknown strategy"):
            get_strategy("strategy_2")


if __name__ == "__main__":
    unittest.main()
