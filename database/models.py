from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint, Column, DateTime, Integer, Numeric, String, UniqueConstraint
)

from database.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (
        CheckConstraint("side IN ('LONG', 'SHORT')", name="ck_trades_side"),
        CheckConstraint(
            "status IN ('PENDING', 'OPEN', 'CLOSED', 'CANCELLED', 'FAILED')",
            name="ck_trades_status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(32), nullable=False, index=True)
    side = Column(String(8), nullable=False)
    signal_timestamp = Column(DateTime(timezone=True), nullable=False)
    signal_origin = Column(String(128), nullable=False)
    client_order_id = Column(String(64), nullable=False, unique=True, index=True)
    binance_order_id = Column(String(64), nullable=True)
    stop_loss_client_order_id = Column(String(64), nullable=True)
    requested_qty = Column(Numeric(28, 12), nullable=False)
    executed_qty = Column(Numeric(28, 12), nullable=False, default=0)
    expected_price = Column(Numeric(28, 12), nullable=False)
    avg_executed_price = Column(Numeric(28, 12), nullable=True)
    avg_exit_price = Column(Numeric(28, 12), nullable=True)
    initial_stop_price = Column(Numeric(28, 12), nullable=False)
    current_stop_price = Column(Numeric(28, 12), nullable=False)
    risk_amount_usdt = Column(Numeric(28, 12), nullable=False)
    commission_paid = Column(Numeric(28, 12), nullable=False, default=0)
    exit_commission = Column(Numeric(28, 12), nullable=False, default=0)
    status = Column(String(16), nullable=False, default="PENDING", index=True)
    close_reason = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    last_reconciled_at = Column(DateTime(timezone=True), nullable=True)


class ProcessedCycle(Base):
    __tablename__ = "processed_cycles"
    __table_args__ = (
        UniqueConstraint(
            "symbol", "timeframe", "candle_timestamp",
            name="uq_processed_cycle_market_candle",
        ),
    )

    id = Column(Integer, primary_key=True)
    symbol = Column(String(32), nullable=False)
    timeframe = Column(String(16), nullable=False)
    candle_timestamp = Column(DateTime(timezone=True), nullable=False)
    signal = Column(String(16), nullable=False)
    decision = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class RuntimeState(Base):
    __tablename__ = "runtime_state"

    key = Column(String(64), primary_key=True)
    value = Column(String(512), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
