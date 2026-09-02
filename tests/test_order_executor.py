import unittest
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN, ROUND_UP

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config import Settings
from database.database import Base
from database.trade_service import TradeService
from exchange.binance_client import BinanceFuturesClient
from exchange.exceptions import BinanceOrderRejectedError, BinanceTradingDisabledError
from execution.order_executor import EntryIntent, ExitIntent, OrderExecutor
from execution.safety import KillSwitch
from positions.manager import PositionManager
from positions.reconciliation import ReconciliationResult


def settings(dry_run=False, enabled=True):
    return Settings(
        binance_env="testnet", binance_testnet_api_key="key",
        binance_testnet_api_secret="secret", trading_enabled=enabled,
        dry_run=dry_run, risk_per_trade_pct=1,
        max_notional_usdt=100, atr_multiplier=1.5,
        breakeven_r_multiple=1.5,
    )


def service():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TradeService(sessionmaker(bind=engine, expire_on_commit=False))


class FakeReconciler:
    def __init__(self, action="NO_EXPOSURE", blocked=False):
        self.action = action
        self.blocked = blocked

    def reconcile(self, symbol):
        return ReconciliationResult(symbol, True, self.blocked, self.action)


class FakeBinanceAdapter:
    def __init__(self, fail_stop=False):
        self.fail_stop = fail_stop
        self.orders = []
        self.cancelled = []

    def get_position_mode(self):
        return "ONE_WAY"

    def get_open_positions(self, _symbol):
        return []

    def get_open_orders(self, _symbol):
        return []

    def get_usdt_balance(self):
        return 1000

    def normalize_quantity(self, _symbol, quantity):
        return (Decimal(quantity) / Decimal("0.001")).to_integral_value(
            rounding=ROUND_DOWN
        ) * Decimal("0.001")

    def normalize_price(self, _symbol, price, rounding="down"):
        mode = ROUND_DOWN if rounding == "down" else ROUND_UP
        return (Decimal(price) / Decimal("0.1")).to_integral_value(
            rounding=mode
        ) * Decimal("0.1")

    def validate_min_notional(self, _symbol, quantity, price):
        return Decimal(quantity) * Decimal(price) >= 5

    def create_order(self, symbol, side, order_type, quantity, client_order_id=None, **params):
        call = {
            "symbol": symbol, "side": side, "type": order_type,
            "quantity": quantity, "client_order_id": client_order_id, **params,
        }
        self.orders.append(call)
        if order_type == "STOP_MARKET" and self.fail_stop:
            raise BinanceOrderRejectedError("stop rejected")
        if order_type == "STOP_MARKET":
            return {"clientAlgoId": client_order_id, "algoStatus": "NEW"}
        price = "101" if len(self.orders) == 1 else "102"
        return {
            "status": "FILLED", "orderId": str(len(self.orders)),
            "executedQty": str(quantity), "avgPrice": price,
        }

    def get_order(self, *_args, **_kwargs):
        raise AssertionError("filled responses should not require lookup")

    def cancel_order(self, symbol, client_order_id, conditional=False):
        self.cancelled.append((symbol, client_order_id, conditional))
        return {"status": "CANCELED"}


def intent():
    return EntryIntent(
        symbol="BTCUSDT", side="LONG",
        signal_timestamp=datetime.now(timezone.utc),
        signal_origin="SQZMOM_REVERSAL", expected_price=Decimal("100"),
        atr_value=Decimal("2"), equity_usdt=Decimal("1000"),
    )


class OrderExecutorTests(unittest.TestCase):
    def _executor(self, adapter, config, trade_service=None, reconciler=None, kill=None):
        trades = trade_service or service()
        manager = PositionManager(adapter, trades, config)
        return OrderExecutor(
            adapter, manager, trades,
            reconciler or FakeReconciler(), config, kill_switch=kill,
        ), trades

    def test_trading_disabled_blocks_non_dry_run(self):
        executor, _ = self._executor(FakeBinanceAdapter(), settings(enabled=False))
        with self.assertRaises(BinanceTradingDisabledError):
            executor.execute_entry(intent())

    def test_dry_run_never_calls_raw_sdk_mutations(self):
        class RawClient:
            mutation_calls = 0

            def futures_exchange_info(self):
                return {"symbols": [{"symbol": "BTCUSDT", "filters": [
                    {"filterType": "LOT_SIZE", "stepSize": "0.001"},
                    {"filterType": "PRICE_FILTER", "tickSize": "0.1"},
                    {"filterType": "MIN_NOTIONAL", "notional": "5"},
                ]}]}

            def futures_create_order(self, **_):
                self.mutation_calls += 1

        raw = RawClient()
        config = settings(dry_run=True, enabled=False)
        adapter = BinanceFuturesClient(config=config, mock_client=raw)
        executor, trades = self._executor(adapter, config)
        result = executor.execute_entry(intent())

        self.assertTrue(result.success)
        self.assertEqual(result.status, "OPEN_PROTECTED")
        self.assertEqual(raw.mutation_calls, 0)
        self.assertEqual(trades.get_active_trade("BTCUSDT").status, "OPEN")

    def test_entry_is_filled_then_protected_with_reduce_only_stop(self):
        adapter = FakeBinanceAdapter()
        executor, trades = self._executor(adapter, settings())
        result = executor.execute_entry(intent())

        self.assertEqual(result.status, "OPEN_PROTECTED")
        self.assertEqual([order["type"] for order in adapter.orders], ["MARKET", "STOP_MARKET"])
        stop = adapter.orders[1]
        self.assertTrue(stop["reduceOnly"])
        self.assertEqual(stop["stopPrice"], "98.0")
        trade = trades.get_active_trade("BTCUSDT")
        self.assertEqual(trade.avg_executed_price, Decimal("101.000000000000"))
        self.assertEqual(trade.current_stop_price, Decimal("98.000000000000"))

    def test_stop_failure_activates_kill_switch_and_emergency_reduce_only_close(self):
        adapter = FakeBinanceAdapter(fail_stop=True)
        kill = KillSwitch()
        executor, trades = self._executor(adapter, settings(), kill=kill)
        result = executor.execute_entry(intent())

        self.assertEqual(result.status, "EMERGENCY_CLOSED")
        self.assertTrue(kill.active)
        self.assertTrue(adapter.orders[-1]["reduceOnly"])
        self.assertEqual(trades.get_by_client_order_id(result.client_order_id).status, "CLOSED")
        with self.assertRaises(BinanceTradingDisabledError):
            executor.execute_entry(intent())

    def test_every_explicit_exit_is_reduce_only(self):
        adapter = FakeBinanceAdapter()
        trades = service()
        executor, _ = self._executor(adapter, settings(), trades)
        entry_result = executor.execute_entry(intent())
        executor.reconciler = FakeReconciler("ACTIVE_POSITION", blocked=True)
        result = executor.execute_exit(ExitIntent("BTCUSDT", expected_price=Decimal("102")))

        self.assertEqual(result.status, "CLOSED")
        exits = [order for order in adapter.orders if order["type"] == "MARKET"][1:]
        self.assertTrue(exits)
        self.assertTrue(all(order.get("reduceOnly") is True for order in exits))
        self.assertIn(("BTCUSDT", entry_result.stop_order_id, True), adapter.cancelled)

    def test_breakeven_places_new_protection_before_canceling_old_stop(self):
        adapter = FakeBinanceAdapter()
        trades = service()
        executor, _ = self._executor(adapter, settings(), trades)
        entry_result = executor.execute_entry(intent())
        executor.reconciler = FakeReconciler("ACTIVE_POSITION", blocked=True)

        result = executor.move_stop_to_breakeven(
            "BTCUSDT", current_price=Decimal("105.5")
        )

        self.assertEqual(result.status, "BREAKEVEN_PROTECTED")
        new_stop = adapter.orders[-1]
        self.assertEqual(new_stop["type"], "STOP_MARKET")
        self.assertTrue(new_stop["reduceOnly"])
        self.assertEqual(new_stop["stopPrice"], "101.0")
        self.assertIn(("BTCUSDT", entry_result.stop_order_id, True), adapter.cancelled)


if __name__ == "__main__":
    unittest.main()
