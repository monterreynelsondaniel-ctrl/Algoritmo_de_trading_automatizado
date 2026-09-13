from dataclasses import dataclass, field
from enum import Enum

import pandas as pd


class Strategy2Phase(str, Enum):
    WAITING_FOR_SETUP = "WAITING_FOR_SETUP"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
    CANDIDATE = "CANDIDATE"
    POSITION_OPEN = "POSITION_OPEN"


@dataclass(frozen=True)
class EntryCandidate:
    candidate_id: str
    side: str
    setup_time: pd.Timestamp
    confirmation_time: pd.Timestamp
    context: dict
    semantic_context: dict = field(default_factory=dict)


@dataclass
class Strategy2State:
    phase: Strategy2Phase = Strategy2Phase.WAITING_FOR_SETUP
    side: str | None = None
    setup_time: pd.Timestamp | None = None
    candidate: EntryCandidate | None = None
    last_setup_candle: pd.Timestamp | None = None
    last_confirmation_candle: pd.Timestamp | None = None
    last_management_candle: pd.Timestamp | None = None
    entry_time: pd.Timestamp | None = None
    entry_price: float | None = None
    bars_since_entry: int = 0
    setup_bars_waited: int = 0
    entry_context: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TechnicalInvalidation:
    """Contract reserved for a future explicit strategy stop; no rule exists yet."""
    price: float
    reason_code: str
