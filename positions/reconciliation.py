import logging
from dataclasses import dataclass
from datetime import timezone
from decimal import Decimal
from typing import Optional

from logs.logger import get_logger, log_event


def _decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value or "0"))


@dataclass(frozen=True)
class ReconciliationResult:
    symbol: str
    consistent: bool
    blocked: bool
    action: str
    details: str = ""


class PositionReconciler:
    """Compare exchange truth with local lifecycle records and fail closed."""

    def __init__(self, binance_client, trade_service, logger=None):
        self.binance_client = binance_client
        self.trade_service = trade_service
        self.logger = logger or get_logger()

    def reconcile(self, symbol: str) -> ReconciliationResult:
        symbol = symbol.upper()
        positions = self.binance_client.get_open_positions(symbol)
        open_orders = self.binance_client.get_open_orders(symbol)
        local = self.trade_service.get_active_trade(symbol)

        if positions and local is None:
            self._log_mismatch(symbol, "Exchange exposure exists without local trade")
            return ReconciliationResult(
                symbol, False, True, "MANUAL_REVIEW",
                "Exchange position has no local lifecycle record",
            )

        if positions and local is not None:
            exchange_side = "LONG" if _decimal(positions[0].get("positionAmt")) > 0 else "SHORT"
            if exchange_side != local.side:
                self._log_mismatch(symbol, "Local and exchange sides differ")
                return ReconciliationResult(
                    symbol, False, True, "MANUAL_REVIEW", "Position side mismatch"
                )
            self.trade_service.mark_reconciled(local.client_order_id)
            return ReconciliationResult(symbol, True, True, "ACTIVE_POSITION")

        if local is not None and local.status == "OPEN":
            reason, exit_price, commission = self._resolve_external_close(local)
            self.trade_service.close_trade_record(
                local.client_order_id, reason, exit_price, commission
            )
            self.trade_service.mark_reconciled(local.client_order_id)
            log_event(
                self.logger, logging.WARNING, "local_trade_reconciled_closed",
                symbol=symbol, client_order_id=local.client_order_id,
                close_reason=reason,
            )
            return ReconciliationResult(symbol, True, False, "CLOSED_LOCAL_RECORD", reason)

        if local is not None or open_orders:
            self._log_mismatch(symbol, "Pending local trade or orphan exchange order")
            if local is not None:
                self.trade_service.mark_reconciled(local.client_order_id)
            return ReconciliationResult(
                symbol, False, True, "MANUAL_REVIEW",
                "Pending state requires explicit resolution",
            )

        return ReconciliationResult(symbol, True, False, "NO_EXPOSURE")

    def _resolve_external_close(self, trade):
        orders = self.binance_client.get_recent_orders(trade.symbol)
        fills = self.binance_client.get_account_trades(trade.symbol)
        matching_stop = next(
            (
                order for order in orders
                if trade.stop_loss_client_order_id
                and self._client_id(order) == trade.stop_loss_client_order_id
                and self._order_finished(order)
            ),
            None,
        )
        exit_fills = self._exit_fills(trade, fills)
        exit_price, commission = self._fill_totals(exit_fills)
        reason = "STOP_LOSS" if matching_stop is not None and exit_fills else "EXTERNAL_CLOSE"
        return reason, exit_price, commission

    @staticmethod
    def _client_id(order) -> Optional[str]:
        return order.get("clientAlgoId") or order.get("clientOrderId")

    @staticmethod
    def _order_finished(order) -> bool:
        status = order.get("algoStatus") or order.get("status")
        return status in {"FILLED", "FINISHED", "TRIGGERED"}

    @staticmethod
    def _exit_fills(trade, fills):
        expected_side = "SELL" if trade.side == "LONG" else "BUY"
        created = trade.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        created_ms = int(created.timestamp() * 1000)
        return [
            fill for fill in fills
            if fill.get("side") == expected_side
            and int(fill.get("time", 0)) >= created_ms
            and str(fill.get("orderId")) != str(trade.binance_order_id)
        ]

    @staticmethod
    def _fill_totals(fills):
        total_quantity = sum((_decimal(fill.get("qty")) for fill in fills), Decimal("0"))
        commission = sum((_decimal(fill.get("commission")) for fill in fills), Decimal("0"))
        if total_quantity <= 0:
            return None, commission
        total_value = sum(
            (_decimal(fill.get("price")) * _decimal(fill.get("qty")) for fill in fills),
            Decimal("0"),
        )
        return total_value / total_quantity, commission

    def _log_mismatch(self, symbol: str, details: str) -> None:
        log_event(
            self.logger, logging.ERROR, "reconciliation_mismatch",
            symbol=symbol, details=details,
        )
