import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config import Settings
from database.database import Base
from database.state_service import StateService
from database.trade_service import TradeService
from execution.order_executor import ExecutionResult
from execution.safety import KillSwitch
from positions.reconciliation import ReconciliationResult
from run_testnet import PollingRunner


def services():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return TradeService(factory), StateService(factory)


def candles():
    times = pd.date_range("2026-01-01", periods=60, freq="4h", tz="UTC")
    close = pd.Series([100 + index * 0.2 for index in range(60)])
    return pd.DataFrame({
        "open_time": times, "open": close - 0.1, "high": close + 1,
        "low": close - 1, "close": close, "volume": 10,
    })


class FakeExecutor:
    def __init__(self):
        self.entries = []
        self.exits = []
        self.binance_client = None

    def execute_entry(self, intent):
        self.entries.append(intent)
        return ExecutionResult(True, "OPEN_PROTECTED", intent.symbol, intent.side)

    def execute_exit(self, intent):
        self.exits.append(intent)
        return ExecutionResult(True, "CLOSED", intent.symbol)


class FakeReconciler:
    def reconcile(self, symbol):
        return ReconciliationResult(symbol, True, False, "NO_EXPOSURE")


class RunnerTests(unittest.TestCase):
    def test_dry_run_processes_each_closed_candle_only_once(self):
        trades, states = services()
        executor = FakeExecutor()
        config = Settings(dry_run=True, trading_enabled=False)
        runner = PollingRunner(
            candles, executor, FakeReconciler(), trades, states, config
        )

        with patch("run_testnet.generate_signal", return_value={"signal": "LONG"}):
            first = runner.run_once()
            second = runner.run_once()

        self.assertEqual(first.decision, "OPEN_PROTECTED")
        self.assertEqual(second.decision, "DUPLICATE_CANDLE")
        self.assertEqual(len(executor.entries), 1)
        self.assertEqual(executor.entries[0].equity_usdt, Decimal("1000.0"))

    def test_kill_switch_survives_new_runtime_instance(self):
        _, states = services()
        first = KillSwitch(states)
        first.activate("manual audit required")

        restored = KillSwitch(states)
        self.assertTrue(restored.active)
        self.assertEqual(restored.snapshot().reason, "manual audit required")


if __name__ == "__main__":
    unittest.main()
