import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from config import Settings, settings as default_settings
from exchange.exceptions import (
    BinanceExchangeError,
    BinanceOrderRejectedError,
    BinanceTradingDisabledError,
    BinanceUnknownOrderStateError,
)
from execution.safety import KillSwitch
from logs.logger import get_logger, log_event


def _decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value or "0"))


@dataclass(frozen=True)
class EntryIntent:
    symbol: str
    side: str
    signal_timestamp: datetime
    signal_origin: str
    expected_price: Decimal
    atr_value: Decimal
    equity_usdt: Optional[Decimal] = None


@dataclass(frozen=True)
class ExitIntent:
    symbol: str
    close_reason: str = "SIGNAL_EXIT"
    expected_price: Optional[Decimal] = None


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    status: str
    symbol: str
    side: Optional[str] = None
    client_order_id: Optional[str] = None
    stop_order_id: Optional[str] = None
    quantity: Optional[Decimal] = None
    avg_price: Optional[Decimal] = None
    message: str = ""


class OrderExecutor:
    """The only application boundary authorized to create trading mutations."""

    def __init__(
        self, binance_client, position_manager, trade_service, reconciler,
        config: Settings = default_settings, kill_switch=None, logger=None,
        sleep=time.sleep, fill_attempts: int = 3,
    ):
        if fill_attempts < 1:
            raise ValueError("fill_attempts must be at least 1")
        self.binance_client = binance_client
        self.position_manager = position_manager
        self.trade_service = trade_service
        self.reconciler = reconciler
        self.settings = config
        self.kill_switch = kill_switch or KillSwitch()
        self.logger = logger or get_logger(level=config.log_level)
        self.sleep = sleep
        self.fill_attempts = fill_attempts

    def execute_entry(self, intent: EntryIntent) -> ExecutionResult:
        side = intent.side.upper()
        symbol = intent.symbol.upper()
        if side not in {"LONG", "SHORT"}:
            raise ValueError("entry side must be LONG or SHORT")
        self._ensure_execution_allowed()

        if not self._can_open(symbol):
            return ExecutionResult(False, "BLOCKED", symbol, side, message="Existing or uncertain exposure")

        equity = (
            _decimal(intent.equity_usdt)
            if intent.equity_usdt is not None
            else _decimal(self.binance_client.get_usdt_balance())
        )
        expected = _decimal(intent.expected_price)
        initial_stop = self.position_manager.calculate_initial_stop(
            expected, intent.atr_value, side, symbol
        )
        quantity = self.position_manager.calculate_position_size(
            equity, expected, initial_stop, symbol
        )
        risk_amount = self.position_manager.calculate_risk_amount(
            quantity, expected, initial_stop
        )
        client_order_id = self._id("en")

        self.trade_service.create_trade_record(
            symbol=symbol, side=side,
            signal_timestamp=intent.signal_timestamp,
            signal_origin=intent.signal_origin,
            client_order_id=client_order_id,
            requested_qty=quantity, expected_price=expected,
            initial_stop_price=initial_stop, risk_amount_usdt=risk_amount,
        )

        order_side = "BUY" if side == "LONG" else "SELL"
        try:
            response = self.binance_client.create_order(
                symbol, order_side, "MARKET", quantity,
                client_order_id=client_order_id,
                newOrderRespType="RESULT",
            )
            filled = self._confirmed_fill(
                symbol, client_order_id, response, expected, quantity
            )
            exact_stop = self.position_manager.calculate_initial_stop(
                filled["avg_price"], intent.atr_value, side, symbol
            )
            self.trade_service.update_trade_execution(
                client_order_id, filled["order_id"], filled["quantity"],
                filled["avg_price"], filled["commission"],
            )
        except BinanceOrderRejectedError:
            self.trade_service.mark_trade_failed(client_order_id)
            raise
        except BinanceUnknownOrderStateError:
            # Keep PENDING: reconciliation must resolve an uncertain submission.
            raise

        stop_id = self._id("sl")
        try:
            stop_response = self._place_stop(
                symbol, side, filled["quantity"], exact_stop, stop_id
            )
            confirmed_stop_id = (
                stop_response.get("clientAlgoId")
                or stop_response.get("clientOrderId")
                or stop_id
            )
            self.trade_service.update_stop_loss(
                client_order_id, exact_stop, confirmed_stop_id,
                update_initial=True,
            )
            return ExecutionResult(
                True, "OPEN_PROTECTED", symbol, side, client_order_id,
                confirmed_stop_id, filled["quantity"], filled["avg_price"],
            )
        except Exception as stop_error:
            return self._handle_unprotected_position(
                symbol, side, client_order_id, filled, stop_error
            )

    def execute_exit(self, intent: ExitIntent) -> ExecutionResult:
        symbol = intent.symbol.upper()
        self._ensure_execution_allowed()
        if not self.settings.dry_run:
            self._ensure_one_way_mode()
            reconciliation = self.reconciler.reconcile(symbol)
            if reconciliation.blocked and reconciliation.action != "ACTIVE_POSITION":
                return ExecutionResult(False, "BLOCKED", symbol, message=reconciliation.details)

        trade = self.trade_service.get_active_trade(symbol)
        if trade is None or trade.status != "OPEN":
            return ExecutionResult(False, "NO_OPEN_POSITION", symbol)

        side = "SELL" if trade.side == "LONG" else "BUY"
        exit_id = self._id("ex")
        response = self.binance_client.create_order(
            symbol, side, "MARKET", trade.executed_qty,
            client_order_id=exit_id, reduceOnly=True,
            newOrderRespType="RESULT",
        )
        fallback = intent.expected_price or trade.avg_executed_price
        filled = self._confirmed_fill(
            symbol, exit_id, response, fallback, trade.executed_qty
        )
        self.trade_service.close_trade_record(
            trade.client_order_id, intent.close_reason,
            filled["avg_price"], filled["commission"],
        )
        if trade.stop_loss_client_order_id:
            try:
                self.binance_client.cancel_order(
                    symbol, trade.stop_loss_client_order_id, conditional=True
                )
            except BinanceExchangeError as error:
                log_event(
                    self.logger, logging.WARNING, "orphan_stop_cancel_failed",
                    symbol=symbol, client_order_id=trade.client_order_id,
                    error=str(error),
                )
        return ExecutionResult(
            True, "CLOSED", symbol, trade.side, exit_id,
            quantity=filled["quantity"], avg_price=filled["avg_price"],
        )

    def move_stop_to_breakeven(
        self, symbol: str, current_price: Optional[Decimal] = None
    ) -> ExecutionResult:
        self._ensure_execution_allowed()
        symbol = symbol.upper()
        if not self.settings.dry_run:
            self._ensure_one_way_mode()
            reconciliation = self.reconciler.reconcile(symbol)
            if reconciliation.blocked and reconciliation.action != "ACTIVE_POSITION":
                return ExecutionResult(
                    False, "BLOCKED", symbol, message=reconciliation.details
                )
        trade = self.trade_service.get_active_trade(symbol)
        if trade is None or trade.status != "OPEN":
            return ExecutionResult(False, "NO_OPEN_POSITION", symbol)
        market_price = (
            _decimal(current_price)
            if current_price is not None
            else _decimal(self.binance_client.get_mark_price(symbol))
        )
        if not self.position_manager.should_move_to_breakeven(
            trade.side, trade.avg_executed_price, market_price,
            trade.initial_stop_price,
        ):
            return ExecutionResult(
                False, "BREAKEVEN_NOT_TRIGGERED", symbol, trade.side,
                trade.client_order_id,
            )
        new_stop = self.position_manager.get_breakeven_stop_price(
            trade.side, trade.avg_executed_price, trade.symbol
        )
        new_stop_id = self._id("be")
        self._place_stop(
            trade.symbol, trade.side, trade.executed_qty, new_stop, new_stop_id
        )
        old_stop_id = trade.stop_loss_client_order_id
        self.trade_service.update_stop_loss(
            trade.client_order_id, new_stop, new_stop_id
        )
        if old_stop_id:
            self.binance_client.cancel_order(
                trade.symbol, old_stop_id, conditional=True
            )
        return ExecutionResult(
            True, "BREAKEVEN_PROTECTED", trade.symbol, trade.side,
            trade.client_order_id, new_stop_id, trade.executed_qty,
            trade.avg_executed_price,
        )

    def _can_open(self, symbol: str) -> bool:
        if self.settings.dry_run:
            return self.trade_service.get_active_trade(symbol) is None
        self._ensure_one_way_mode()
        reconciliation = self.reconciler.reconcile(symbol)
        return not reconciliation.blocked and self.position_manager.can_open_position(symbol)

    def _ensure_execution_allowed(self) -> None:
        if self.kill_switch.active:
            raise BinanceTradingDisabledError("Runtime kill switch is active")
        if not self.settings.dry_run and not self.settings.can_send_orders():
            raise BinanceTradingDisabledError("Trading mutation is disabled")

    def _ensure_one_way_mode(self) -> None:
        if self.binance_client.get_position_mode() != "ONE_WAY":
            raise BinanceTradingDisabledError(
                "One-way position mode is required for reduceOnly orders"
            )

    def _place_stop(self, symbol, position_side, quantity, stop_price, stop_id):
        order_side = "SELL" if position_side == "LONG" else "BUY"
        return self.binance_client.create_order(
            symbol, order_side, "STOP_MARKET", quantity,
            client_order_id=stop_id, reduceOnly=True,
            stopPrice=str(stop_price), workingType="MARK_PRICE",
        )

    def _confirmed_fill(self, symbol, client_order_id, response, fallback_price, fallback_qty):
        if response.get("dryRun"):
            return {
                "order_id": response.get("orderId", client_order_id),
                "quantity": _decimal(fallback_qty),
                "avg_price": _decimal(fallback_price),
                "commission": Decimal("0"),
            }
        current = response
        for attempt in range(1, self.fill_attempts + 1):
            if _decimal(current.get("executedQty")) > 0 and _decimal(current.get("avgPrice")) > 0:
                break
            current = self.binance_client.get_order(symbol, client_order_id)
            if _decimal(current.get("executedQty")) > 0 and _decimal(current.get("avgPrice")) > 0:
                break
            if attempt < self.fill_attempts:
                self.sleep(0.5 * attempt)
        quantity = _decimal(current.get("executedQty"))
        avg_price = _decimal(current.get("avgPrice"))
        if quantity <= 0 or avg_price <= 0:
            raise BinanceExchangeError("Market order fill could not be confirmed")
        commission = sum(
            (_decimal(fill.get("commission")) for fill in current.get("fills", [])),
            Decimal("0"),
        )
        return {
            "order_id": str(current.get("orderId", "")),
            "quantity": quantity,
            "avg_price": avg_price,
            "commission": commission,
        }

    def _handle_unprotected_position(self, symbol, side, client_order_id, filled, error):
        reason = f"Stop placement failed after entry: {error}"
        self.kill_switch.activate(reason)
        log_event(
            self.logger, logging.CRITICAL, "unprotected_position",
            symbol=symbol, side=side, client_order_id=client_order_id,
            error=str(error),
        )
        close_side = "SELL" if side == "LONG" else "BUY"
        try:
            close_id = self._id("ks")
            response = self.binance_client.create_order(
                symbol, close_side, "MARKET", filled["quantity"],
                client_order_id=close_id, reduceOnly=True,
                newOrderRespType="RESULT",
            )
            emergency_fill = self._confirmed_fill(
                symbol, close_id, response, filled["avg_price"], filled["quantity"]
            )
            self.trade_service.close_trade_record(
                client_order_id, "EMERGENCY_KILL",
                emergency_fill["avg_price"], emergency_fill["commission"],
            )
            return ExecutionResult(
                False, "EMERGENCY_CLOSED", symbol, side, client_order_id,
                quantity=filled["quantity"], avg_price=filled["avg_price"],
                message=reason,
            )
        except Exception as close_error:
            log_event(
                self.logger, logging.CRITICAL, "emergency_close_failed",
                symbol=symbol, client_order_id=client_order_id,
                error=str(close_error),
            )
            return ExecutionResult(
                False, "UNPROTECTED_KILL_SWITCH", symbol, side,
                client_order_id, quantity=filled["quantity"],
                avg_price=filled["avg_price"], message=str(close_error),
            )

    @staticmethod
    def _id(prefix: str) -> str:
        return f"tb-{prefix}-{uuid.uuid4().hex[:24]}"
