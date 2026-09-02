import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.database import Base
from database.trade_service import TradeService
from positions.reconciliation import PositionReconciler


class ReconciliationClient:
    def __init__(self, positions=None, orders=None, history=None, fills=None):
        self.positions = positions or []
        self.orders = orders or []
        self.history = history or []
        self.fills = fills or []

    def get_open_positions(self, _symbol):
        return self.positions

    def get_open_orders(self, _symbol):
        return self.orders

    def get_recent_orders(self, _symbol):
        return self.history

    def get_account_trades(self, _symbol):
        return self.fills


def service():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TradeService(sessionmaker(bind=engine, expire_on_commit=False))


class ReconciliationTests(unittest.TestCase):
    def _open_trade(self, trades):
        now = datetime.now(timezone.utc)
        trades.create_trade_record(
            symbol="BTCUSDT", side="LONG", signal_timestamp=now,
            signal_origin="TEST", client_order_id="entry-1",
            requested_qty="0.01", expected_price="100",
            initial_stop_price="95", risk_amount_usdt="0.05",
            stop_loss_client_order_id="stop-1",
        )
        return trades.update_trade_execution("entry-1", "11", "0.01", "100", "0.01")

    def test_stop_fill_closes_missing_exchange_position_locally(self):
        trades = service()
        trade = self._open_trade(trades)
        fill_time = int(trade.created_at.replace(tzinfo=timezone.utc).timestamp() * 1000) + 1
        client = ReconciliationClient(
            history=[{"clientAlgoId": "stop-1", "algoStatus": "FINISHED"}],
            fills=[{
                "side": "SELL", "orderId": "12", "time": fill_time,
                "price": "95", "qty": "0.01", "commission": "0.001",
            }],
        )
        result = PositionReconciler(client, trades).reconcile("BTCUSDT")

        closed = trades.get_by_client_order_id("entry-1")
        self.assertEqual(result.action, "CLOSED_LOCAL_RECORD")
        self.assertEqual(closed.status, "CLOSED")
        self.assertEqual(closed.close_reason, "STOP_LOSS")
        self.assertIsNotNone(closed.last_reconciled_at)

    def test_unproven_close_is_classified_external(self):
        trades = service()
        self._open_trade(trades)
        result = PositionReconciler(
            ReconciliationClient(), trades
        ).reconcile("BTCUSDT")
        closed = trades.get_by_client_order_id("entry-1")
        self.assertEqual(result.details, "EXTERNAL_CLOSE")
        self.assertEqual(closed.close_reason, "EXTERNAL_CLOSE")

    def test_exchange_position_without_local_record_blocks(self):
        result = PositionReconciler(
            ReconciliationClient(positions=[{"positionAmt": "0.01"}]),
            service(),
        ).reconcile("BTCUSDT")
        self.assertTrue(result.blocked)
        self.assertEqual(result.action, "MANUAL_REVIEW")


if __name__ == "__main__":
    unittest.main()
