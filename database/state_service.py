from datetime import datetime, timezone

from sqlalchemy import select

from database.database import SessionLocal, session_scope
from database.models import ProcessedCycle, RuntimeState


class StateService:
    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    def is_cycle_processed(
        self, symbol: str, timeframe: str, candle_timestamp: datetime
    ) -> bool:
        with session_scope(self.session_factory) as session:
            statement = select(ProcessedCycle.id).where(
                ProcessedCycle.symbol == symbol.upper(),
                ProcessedCycle.timeframe == timeframe,
                ProcessedCycle.candle_timestamp == candle_timestamp,
            )
            return session.execute(statement).scalar_one_or_none() is not None

    def record_cycle(
        self, symbol: str, timeframe: str, candle_timestamp: datetime,
        signal: str, decision: str,
    ) -> None:
        if candle_timestamp.tzinfo is None or candle_timestamp.utcoffset() is None:
            raise ValueError("candle_timestamp must be timezone-aware")
        with session_scope(self.session_factory) as session:
            session.add(ProcessedCycle(
                symbol=symbol.upper(), timeframe=timeframe,
                candle_timestamp=candle_timestamp.astimezone(timezone.utc),
                signal=signal, decision=decision,
            ))

    def get_value(self, key: str, default=None):
        with session_scope(self.session_factory) as session:
            state = session.get(RuntimeState, key)
            return state.value if state else default

    def set_value(self, key: str, value: str) -> None:
        with session_scope(self.session_factory) as session:
            state = session.get(RuntimeState, key)
            if state is None:
                session.add(RuntimeState(key=key, value=str(value)))
            else:
                state.value = str(value)
                state.updated_at = datetime.now(timezone.utc)


state_service = StateService()
