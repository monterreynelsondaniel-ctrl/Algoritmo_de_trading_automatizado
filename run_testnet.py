import argparse
import logging
import math
import time
from dataclasses import dataclass
from decimal import Decimal

from config import Settings, settings
from data.frozen_market_data import FrozenMarketDataStore
from database.database import create_schema
from database.state_service import StateService, state_service
from database.trade_service import TradeService, trade_service
from exchange.binance_client import BinanceFuturesClient
from exchange.market_data import get_candles
from execution.order_executor import EntryIntent, ExitIntent, OrderExecutor
from execution.process_lock import single_runner_lock
from execution.safety import KillSwitch
from logs.logger import get_logger, log_event
from positions.manager import PositionManager
from positions.reconciliation import PositionReconciler
from strategies.registry import available_strategies, get_strategy


@dataclass(frozen=True)
class CycleResult:
    candle_timestamp: object
    signal: str
    decision: str


class PollingRunner:
    def __init__(
        self, candle_provider, executor: OrderExecutor,
        reconciler: PositionReconciler, trades: TradeService,
        states: StateService, config: Settings = settings, logger=None,
        strategy=None,
    ):
        self.candle_provider = candle_provider
        self.executor = executor
        self.reconciler = reconciler
        self.trades = trades
        self.states = states
        self.settings = config
        self.logger = logger or get_logger(level=config.log_level)
        self.strategy = strategy or get_strategy()

    def run_once(self) -> CycleResult:
        candles = self.strategy.prepare_candles(self.candle_provider())
        if len(candles) < 2:
            raise RuntimeError("At least two closed candles are required")

        latest = candles.iloc[-1]
        candle_time = latest["open_time"]
        signal = self.strategy.generate_signal(candles)["signal"]
        symbol = self.settings.symbol

        if not self.settings.dry_run:
            reconciliation = self.reconciler.reconcile(symbol)
            if reconciliation.blocked and reconciliation.action != "ACTIVE_POSITION":
                return self._finish(candle_time, signal, "BLOCKED_RECONCILIATION")

        active = self.trades.get_active_trade(symbol)
        self._manage_breakeven(active, latest)

        if self.states.is_cycle_processed(
            symbol, self.settings.timeframe, candle_time
        ):
            self._log_cycle(candle_time, signal, "DUPLICATE_CANDLE")
            return CycleResult(candle_time, signal, "DUPLICATE_CANDLE")

        if active and active.status == "OPEN":
            if signal in {"LONG", "SHORT"} and signal != active.side:
                result = self.executor.execute_exit(ExitIntent(
                    symbol=symbol, close_reason="SIGNAL_EXIT",
                    expected_price=Decimal(str(latest["close"])),
                ))
                decision = result.status
            else:
                decision = "HOLD_POSITION"
            return self._finish(candle_time, signal, decision)

        if signal in {"LONG", "SHORT"}:
            atr = float(latest["atr"])
            if not math.isfinite(atr) or atr <= 0:
                return self._finish(candle_time, signal, "INVALID_ATR")
            expected_price = (
                Decimal(str(latest["close"]))
                if self.settings.dry_run
                else Decimal(str(self.executor.binance_client.get_mark_price(symbol)))
            )
            equity = (
                Decimal(str(self.settings.dry_run_equity_usdt))
                if self.settings.dry_run else None
            )
            result = self.executor.execute_entry(EntryIntent(
                symbol=symbol, side=signal, signal_timestamp=candle_time,
                signal_origin=self.strategy.signal_origin,
                expected_price=expected_price,
                atr_value=Decimal(str(atr)), equity_usdt=equity,
            ))
            return self._finish(candle_time, signal, result.status)

        return self._finish(candle_time, signal, "NO_SIGNAL")

    def run_forever(self, poll_interval_seconds=60):
        if poll_interval_seconds <= 0:
            raise ValueError("poll interval must be positive")
        while True:
            try:
                self.run_once()
            except KeyboardInterrupt:
                log_event(self.logger, logging.INFO, "runner_stopped_by_user")
                return
            except Exception as error:
                log_event(
                    self.logger, logging.ERROR, "runner_cycle_failed",
                    error=str(error),
                )
            time.sleep(poll_interval_seconds)

    def _manage_breakeven(self, trade, latest) -> None:
        if trade is None or trade.status != "OPEN":
            return
        entry = Decimal(str(trade.avg_executed_price))
        current_stop = Decimal(str(trade.current_stop_price))
        already_moved = (
            current_stop >= entry if trade.side == "LONG" else current_stop <= entry
        )
        if already_moved:
            return
        current_price = (
            Decimal(str(latest["close"]))
            if self.settings.dry_run
            else Decimal(str(self.executor.binance_client.get_mark_price(trade.symbol)))
        )
        result = self.executor.move_stop_to_breakeven(
            trade.symbol, current_price=current_price
        )
        if result.status == "BREAKEVEN_PROTECTED":
            log_event(
                self.logger, logging.INFO, "breakeven_stop_moved",
                symbol=trade.symbol, client_order_id=trade.client_order_id,
            )

    def _finish(self, candle_time, signal, decision) -> CycleResult:
        self.states.record_cycle(
            self.settings.symbol, self.settings.timeframe,
            candle_time, signal, decision,
        )
        self._log_cycle(candle_time, signal, decision)
        return CycleResult(candle_time, signal, decision)

    def _log_cycle(self, candle_time, signal, decision) -> None:
        log_event(
            self.logger, logging.INFO, "polling_cycle",
            symbol=self.settings.symbol, timeframe=self.settings.timeframe,
            candle_timestamp=candle_time, signal=signal, decision=decision,
            dry_run=self.settings.dry_run,
        )


def build_runner(config: Settings, candle_provider, strategy=None):
    create_schema()
    client = BinanceFuturesClient(config=config)
    trades = trade_service
    states = state_service
    kill_switch = KillSwitch(states)
    reconciler = PositionReconciler(client, trades)
    manager = PositionManager(client, trades, config)
    executor = OrderExecutor(
        client, manager, trades, reconciler, config, kill_switch=kill_switch
    )
    return PollingRunner(
        candle_provider, executor, reconciler, trades, states, config,
        strategy=strategy,
    )


def main():
    parser = argparse.ArgumentParser(description="Binance Futures polling runner")
    parser.add_argument("--once", action="store_true", help="Run one polling cycle")
    parser.add_argument("--poll-seconds", type=float, default=60)
    parser.add_argument("--snapshot", help="Offline snapshot name; implies --once")
    parser.add_argument(
        "--strategy", choices=available_strategies(), default="strategy_1",
        help="Strategy implementation to run",
    )
    args = parser.parse_args()

    if args.snapshot:
        store = FrozenMarketDataStore()
        provider = lambda: store.load(args.snapshot)
    else:
        provider = lambda: get_candles(
            settings.symbol, settings.timeframe, limit=200, closed_only=True
        )

    with single_runner_lock():
        runner = build_runner(settings, provider, strategy=get_strategy(args.strategy))
        if args.once or args.snapshot:
            result = runner.run_once()
            print(
                f"{result.candle_timestamp} | signal={result.signal} | "
                f"decision={result.decision}"
            )
        else:
            runner.run_forever(args.poll_seconds)


if __name__ == "__main__":
    main()
