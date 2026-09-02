import unittest
from decimal import Decimal
from types import SimpleNamespace

from config import Settings
from positions.manager import PositionManager, RiskValidationError


class MockBinanceClient:
    def __init__(self, positions=None, orders=None):
        self.positions = positions or []
        self.orders = orders or []

    def get_open_positions(self, _symbol):
        return self.positions

    def get_open_orders(self, _symbol):
        return self.orders

    def normalize_quantity(self, _symbol, quantity):
        return (Decimal(quantity) / Decimal("0.001")).to_integral_value(
            rounding="ROUND_DOWN"
        ) * Decimal("0.001")

    def normalize_price(self, _symbol, price, rounding="down"):
        mode = "ROUND_DOWN" if rounding == "down" else "ROUND_UP"
        return (Decimal(price) / Decimal("0.1")).to_integral_value(
            rounding=mode
        ) * Decimal("0.1")

    def validate_min_notional(self, _symbol, quantity, price):
        return Decimal(quantity) * Decimal(price) >= Decimal("5")


class MockTradeService:
    def __init__(self, active=None):
        self.active = active
        self.reconciled = []

    def get_active_trade(self, _symbol):
        return self.active

    def mark_reconciled(self, client_order_id):
        self.reconciled.append(client_order_id)


def risk_settings(**changes):
    values = {
        "risk_per_trade_pct": 1.0,
        "max_notional_usdt": 100.0,
        "atr_multiplier": 1.5,
        "breakeven_r_multiple": 1.5,
    }
    values.update(changes)
    return Settings(**values)


class PositionManagerTests(unittest.TestCase):
    def test_position_size_is_capped_by_max_notional(self):
        manager = PositionManager(
            MockBinanceClient(), MockTradeService(), risk_settings()
        )
        # Risk sizing gives 1 BTC, but max notional caps it to 0.01 BTC.
        quantity = manager.calculate_position_size(1000, 10000, 9990, "BTCUSDT")
        self.assertEqual(quantity, Decimal("0.010"))
        self.assertEqual(
            manager.calculate_position_size(1000, 10000, 10010, "BTCUSDT"),
            Decimal("0.010"),
        )

    def test_initial_stops_and_breakeven_are_side_aware(self):
        manager = PositionManager(
            MockBinanceClient(), MockTradeService(), risk_settings()
        )
        self.assertEqual(
            manager.calculate_initial_stop("100.05", "2", "LONG", "BTCUSDT"),
            Decimal("97.0"),
        )
        self.assertEqual(
            manager.calculate_initial_stop("100.05", "2", "SHORT", "BTCUSDT"),
            Decimal("103.1"),
        )
        self.assertTrue(manager.should_move_to_breakeven("LONG", 100, 104.5, 97))
        self.assertFalse(manager.should_move_to_breakeven("LONG", 100, 104.49, 97))
        self.assertTrue(manager.should_move_to_breakeven("SHORT", 100, 95.5, 103))
        self.assertEqual(
            manager.get_breakeven_stop_price("SHORT", "100.01", "BTCUSDT"),
            Decimal("100.1"),
        )

    def test_exchange_position_blocks_opening(self):
        manager = PositionManager(
            MockBinanceClient(positions=[{"positionAmt": "1"}]),
            MockTradeService(), risk_settings(),
        )
        self.assertFalse(manager.can_open_position("BTCUSDT"))

    def test_local_exchange_mismatch_fails_closed(self):
        local = SimpleNamespace(client_order_id="local-1")
        service = MockTradeService(active=local)
        manager = PositionManager(MockBinanceClient(), service, risk_settings())
        self.assertFalse(manager.can_open_position("BTCUSDT"))
        self.assertEqual(service.reconciled, ["local-1"])

    def test_zero_stop_distance_is_rejected(self):
        manager = PositionManager(
            MockBinanceClient(), MockTradeService(), risk_settings()
        )
        with self.assertRaises(RiskValidationError):
            manager.calculate_position_size(1000, 100, 100, "BTCUSDT")


if __name__ == "__main__":
    unittest.main()
