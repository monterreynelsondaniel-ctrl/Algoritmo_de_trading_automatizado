import logging
import os
import tempfile
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings
from database.database import Base
from database.trade_service import TradeService
from exchange.binance_client import BinanceFuturesClient
from execution.order_executor import EntryIntent, ExitIntent, OrderExecutor
from execution.safety import KillSwitch
from logs.logger import get_logger
from positions.manager import PositionManager
from positions.reconciliation import PositionReconciler


RUN_INTEGRATION = os.getenv("RUN_BINANCE_INTEGRATION") == "1"


@unittest.skipUnless(
    RUN_INTEGRATION,
    "Set RUN_BINANCE_INTEGRATION=1 explicitly to use Binance Futures Testnet",
)
class BinanceFuturesIntegrationTests(unittest.TestCase):
    def test_protected_entry_and_cleanup(self):
        self.assertEqual(settings.binance_env, "testnet")
        self.assertTrue(settings.has_credentials())
        self.assertTrue(settings.trading_enabled)
        self.assertFalse(settings.dry_run)

        configured_notional = Decimal(
            os.getenv("INTEGRATION_TEST_NOTIONAL_USDT", "10")
        )
        hard_cap = Decimal(
            os.getenv("INTEGRATION_TEST_HARD_CAP_USDT", "150")
        )
        self.assertGreater(configured_notional, 0)
        self.assertGreater(hard_cap, 0)

        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine(f"sqlite:///{directory}/integration.db")
            Base.metadata.create_all(engine)
            trades = TradeService(sessionmaker(bind=engine, expire_on_commit=False))
            logger = get_logger(
                name=f"integration-{uuid.uuid4().hex}",
                log_file=f"{directory}/integration.log",
            )
            client = BinanceFuturesClient(config=settings, logger=logger)

            # This test owns an account only when it starts completely neutral.
            self.assertEqual(client.get_position_mode(), "ONE_WAY")
            self.assertFalse(client.get_open_positions(settings.symbol))
            self.assertFalse(client.get_open_orders(settings.symbol))

            mark_price = Decimal(str(client.get_mark_price(settings.symbol)))
            filters = client.get_exchange_info(settings.symbol)
            minimum_executable = max(
                filters["minNotional"], filters["stepSize"] * mark_price
            )
            effective_notional = max(configured_notional, minimum_executable) * Decimal("1.02")
            if effective_notional > hard_cap:
                self.skipTest(
                    f"Minimum executable notional {effective_notional} exceeds hard cap {hard_cap}"
                )
            balance = Decimal(str(client.get_usdt_balance()))
            self.assertLess(effective_notional, balance)

            integration_settings = replace(
                settings, max_notional_usdt=float(effective_notional)
            )
            client.set_leverage(settings.symbol, 1)
            manager = PositionManager(client, trades, integration_settings, logger)
            reconciler = PositionReconciler(client, trades, logger)
            kill_switch = KillSwitch()
            executor = OrderExecutor(
                client, manager, trades, reconciler, integration_settings,
                kill_switch=kill_switch, logger=logger,
            )

            result = None
            cleanup_errors = []
            try:
                atr = mark_price * Decimal("0.02") / Decimal(str(settings.atr_multiplier))
                result = executor.execute_entry(EntryIntent(
                    symbol=settings.symbol, side="LONG",
                    signal_timestamp=datetime.now(timezone.utc),
                    signal_origin="INTEGRATION_TEST",
                    expected_price=mark_price, atr_value=atr,
                    equity_usdt=balance,
                ))
                self.assertTrue(result.success)
                self.assertEqual(result.status, "OPEN_PROTECTED")
                self.assertTrue(any(
                    (order.get("clientAlgoId") or order.get("clientOrderId"))
                    == result.stop_order_id
                    for order in client.get_open_orders(settings.symbol)
                ))

                closed = executor.execute_exit(ExitIntent(
                    settings.symbol, "SIGNAL_EXIT", mark_price
                ))
                self.assertTrue(closed.success)
                self.assertEqual(
                    trades.get_by_client_order_id(result.client_order_id).status,
                    "CLOSED",
                )
            finally:
                # Only touch the order created by this test; never cancel account-wide orders.
                if result and result.stop_order_id:
                    try:
                        client.cancel_order(
                            settings.symbol, result.stop_order_id, conditional=True
                        )
                    except Exception as error:
                        cleanup_errors.append(f"stop cleanup: {error}")

                for position in client.get_open_positions(settings.symbol):
                    amount = Decimal(position["positionAmt"])
                    side = "SELL" if amount > 0 else "BUY"
                    try:
                        client.create_order(
                            settings.symbol, side, "MARKET", abs(amount),
                            client_order_id=f"tb-it-clean-{uuid.uuid4().hex[:16]}",
                            reduceOnly=True, newOrderRespType="RESULT",
                        )
                    except Exception as error:
                        cleanup_errors.append(f"position cleanup: {error}")

                remaining = client.get_open_positions(settings.symbol)
                self.assertFalse(
                    remaining,
                    f"TESTNET NOT NEUTRAL; inspect account immediately: {cleanup_errors}",
                )
                if result:
                    remaining_test_orders = [
                        order for order in client.get_open_orders(settings.symbol)
                        if (order.get("clientAlgoId") or order.get("clientOrderId"))
                        == result.stop_order_id
                    ]
                    self.assertFalse(
                        remaining_test_orders,
                        f"Test stop still open; inspect account: {cleanup_errors}",
                    )
                log_text = Path(f"{directory}/integration.log").read_text(
                    encoding="utf-8"
                )
                self.assertNotIn(settings.api_key, log_text)
                self.assertNotIn(settings.api_secret, log_text)
