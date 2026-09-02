import unittest
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.database import Base
from database.trade_service import TradeService


class TradeServiceTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.service = TradeService(sessionmaker(bind=engine, expire_on_commit=False))

    def test_complete_trade_lifecycle(self):
        trade = self.service.create_trade_record(
            symbol="BTCUSDT", side="LONG",
            signal_timestamp=datetime.now(timezone.utc),
            signal_origin="SQZMOM_REVERSAL", client_order_id="entry-1",
            requested_qty="0.001", expected_price="50000",
            initial_stop_price="49000", risk_amount_usdt="1",
        )
        self.assertEqual(trade.status, "PENDING")

        trade = self.service.update_trade_execution(
            "entry-1", "123", "0.001", "50001", "0.02"
        )
        self.assertEqual(trade.status, "OPEN")
        self.assertEqual(trade.avg_executed_price, Decimal("50001.000000000000"))

        trade = self.service.update_stop_loss("entry-1", "50001", "stop-1")
        self.assertEqual(trade.stop_loss_client_order_id, "stop-1")

        active = self.service.get_active_trade("BTCUSDT")
        self.assertEqual(active.client_order_id, "entry-1")

        trade = self.service.close_trade_record(
            "entry-1", "SIGNAL_EXIT", "51000", "0.02"
        )
        self.assertEqual(trade.status, "CLOSED")
        self.assertIsNone(self.service.get_active_trade("BTCUSDT"))


if __name__ == "__main__":
    unittest.main()
