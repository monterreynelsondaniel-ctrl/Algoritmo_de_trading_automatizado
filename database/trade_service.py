from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select

from database.database import SessionLocal, session_scope
from database.models import Trade


ACTIVE_STATUSES = ("PENDING", "OPEN")
VALID_CLOSE_REASONS = {
    "STOP_LOSS", "TAKE_PROFIT", "SIGNAL_EXIT", "EMERGENCY_KILL",
    "EXTERNAL_CLOSE",
}


def _decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


class TradeNotFoundError(LookupError):
    pass


class TradeService:
    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    def create_trade_record(
        self, *, symbol: str, side: str, signal_timestamp: datetime,
        signal_origin: str, client_order_id: str, requested_qty,
        expected_price, initial_stop_price, risk_amount_usdt,
        stop_loss_client_order_id: Optional[str] = None,
    ) -> Trade:
        if side not in {"LONG", "SHORT"}:
            raise ValueError("side must be LONG or SHORT")
        if signal_timestamp.tzinfo is None or signal_timestamp.utcoffset() is None:
            raise ValueError("signal_timestamp must be timezone-aware UTC")
        signal_timestamp = signal_timestamp.astimezone(timezone.utc)
        numeric_values = {
            "requested_qty": _decimal(requested_qty),
            "expected_price": _decimal(expected_price),
            "initial_stop_price": _decimal(initial_stop_price),
            "risk_amount_usdt": _decimal(risk_amount_usdt),
        }
        if any(value <= 0 for value in numeric_values.values()):
            raise ValueError("trade quantities, prices, and risk must be positive")
        trade = Trade(
            symbol=symbol.upper(), side=side, signal_timestamp=signal_timestamp,
            signal_origin=signal_origin, client_order_id=client_order_id,
            stop_loss_client_order_id=stop_loss_client_order_id,
            requested_qty=numeric_values["requested_qty"], executed_qty=Decimal("0"),
            expected_price=numeric_values["expected_price"],
            initial_stop_price=numeric_values["initial_stop_price"],
            current_stop_price=numeric_values["initial_stop_price"],
            risk_amount_usdt=numeric_values["risk_amount_usdt"],
            commission_paid=Decimal("0"), exit_commission=Decimal("0"),
            status="PENDING",
        )
        with session_scope(self.session_factory) as session:
            session.add(trade)
            session.flush()
            trade_id = trade.id
        return self.get_by_id(trade_id)

    def update_trade_execution(
        self, client_order_id: str, binance_order_id: str,
        executed_qty, avg_price, commission,
    ) -> Trade:
        with session_scope(self.session_factory) as session:
            trade = self._require(session, client_order_id)
            trade.binance_order_id = str(binance_order_id)
            trade.executed_qty = _decimal(executed_qty)
            trade.avg_executed_price = _decimal(avg_price)
            trade.commission_paid = _decimal(commission)
            trade.status = "OPEN"
            trade.updated_at = datetime.now(timezone.utc)
            trade_id = trade.id
        return self.get_by_id(trade_id)

    def update_stop_loss(
        self, client_order_id: str, new_stop_price,
        stop_loss_client_order_id: Optional[str] = None,
        update_initial: bool = False,
    ) -> Trade:
        with session_scope(self.session_factory) as session:
            trade = self._require(session, client_order_id)
            trade.current_stop_price = _decimal(new_stop_price)
            if update_initial:
                trade.initial_stop_price = _decimal(new_stop_price)
            if stop_loss_client_order_id is not None:
                trade.stop_loss_client_order_id = stop_loss_client_order_id
            trade.updated_at = datetime.now(timezone.utc)
            trade_id = trade.id
        return self.get_by_id(trade_id)

    def close_trade_record(
        self, client_order_id: str, close_reason: str,
        avg_exit_price=None, exit_commission=0,
    ) -> Trade:
        if close_reason not in VALID_CLOSE_REASONS:
            raise ValueError("invalid close_reason")
        now = datetime.now(timezone.utc)
        with session_scope(self.session_factory) as session:
            trade = self._require(session, client_order_id)
            trade.avg_exit_price = (
                _decimal(avg_exit_price) if avg_exit_price is not None else None
            )
            trade.exit_commission = _decimal(exit_commission)
            trade.close_reason = close_reason
            trade.status = "CLOSED"
            trade.closed_at = now
            trade.updated_at = now
            trade_id = trade.id
        return self.get_by_id(trade_id)

    def mark_trade_failed(self, client_order_id: str) -> Trade:
        with session_scope(self.session_factory) as session:
            trade = self._require(session, client_order_id)
            trade.status = "FAILED"
            trade.updated_at = datetime.now(timezone.utc)
            trade_id = trade.id
        return self.get_by_id(trade_id)

    def get_active_trade(self, symbol: str) -> Optional[Trade]:
        with session_scope(self.session_factory) as session:
            statement = select(Trade).where(
                Trade.symbol == symbol.upper(), Trade.status.in_(ACTIVE_STATUSES)
            ).order_by(Trade.created_at.desc())
            trade = session.execute(statement).scalars().first()
            if trade:
                session.expunge(trade)
            return trade

    def mark_reconciled(self, client_order_id: str) -> Trade:
        with session_scope(self.session_factory) as session:
            trade = self._require(session, client_order_id)
            trade.last_reconciled_at = datetime.now(timezone.utc)
            trade.updated_at = trade.last_reconciled_at
            trade_id = trade.id
        return self.get_by_id(trade_id)

    def get_by_id(self, trade_id: int) -> Trade:
        with session_scope(self.session_factory) as session:
            trade = session.get(Trade, trade_id)
            if trade is None:
                raise TradeNotFoundError(f"Trade id not found: {trade_id}")
            session.expunge(trade)
            return trade

    def get_by_client_order_id(self, client_order_id: str) -> Trade:
        with session_scope(self.session_factory) as session:
            trade = self._require(session, client_order_id)
            session.expunge(trade)
            return trade

    @staticmethod
    def _require(session, client_order_id: str) -> Trade:
        trade = session.execute(
            select(Trade).where(Trade.client_order_id == client_order_id)
        ).scalar_one_or_none()
        if trade is None:
            raise TradeNotFoundError(f"Trade not found: {client_order_id}")
        return trade


trade_service = TradeService()
create_trade_record = trade_service.create_trade_record
update_trade_execution = trade_service.update_trade_execution
update_stop_loss = trade_service.update_stop_loss
close_trade_record = trade_service.close_trade_record
get_active_trade = trade_service.get_active_trade
mark_trade_failed = trade_service.mark_trade_failed
