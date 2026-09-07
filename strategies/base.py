"""Minimal contract consumed by shared runners and backtests."""

from typing import Protocol

import pandas as pd


class Strategy(Protocol):
    name: str
    signal_origin: str

    def prepare_candles(self, candles: pd.DataFrame) -> pd.DataFrame:
        """Add the shared transformations and indicators required by a strategy."""

    def generate_signal(self, candles: pd.DataFrame) -> dict:
        """Return the current signal using closed, prepared candles."""

    def historical_signals(self, candles: pd.DataFrame) -> list[dict]:
        """Return historical signals using closed, prepared candles."""
