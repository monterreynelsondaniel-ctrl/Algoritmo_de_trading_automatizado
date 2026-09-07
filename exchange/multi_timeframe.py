"""Causal, strategy-agnostic access to synchronized candle timeframes."""

from dataclasses import dataclass
from typing import Mapping

import pandas as pd

from exchange.market_data import REQUIRED_CANDLE_COLUMNS


def _normalize(candles: pd.DataFrame) -> pd.DataFrame:
    missing = set(REQUIRED_CANDLE_COLUMNS) - set(candles.columns)
    if missing:
        raise ValueError(f"Missing candle columns: {sorted(missing)}")
    result = candles.copy()
    for column in ("open_time", "close_time"):
        result[column] = pd.to_datetime(result[column], utc=True)
    if result["open_time"].duplicated().any():
        raise ValueError("Candle open_time values must be unique")
    return result.sort_values("open_time").reset_index(drop=True)


@dataclass(frozen=True)
class MarketDataView:
    symbol: str
    as_of: pd.Timestamp
    candles: Mapping[str, pd.DataFrame]

    def frame(self, timeframe: str) -> pd.DataFrame:
        try:
            return self.candles[timeframe].copy()
        except KeyError as error:
            raise KeyError(f"Unknown timeframe: {timeframe}") from error

    def latest(self, timeframe: str):
        frame = self.frame(timeframe)
        return None if frame.empty else frame.iloc[-1]


class MultiTimeframeMarketData:
    """Immutable frames exposed only after their real close timestamp."""

    def __init__(self, symbol: str, candles: Mapping[str, pd.DataFrame]):
        if not symbol or not candles:
            raise ValueError("symbol and at least one timeframe are required")
        self.symbol = symbol.upper()
        self._candles = {name: _normalize(frame) for name, frame in candles.items()}

    @property
    def timeframes(self) -> tuple[str, ...]:
        return tuple(self._candles)

    def full_frame(self, timeframe: str) -> pd.DataFrame:
        try:
            return self._candles[timeframe].copy()
        except KeyError as error:
            raise KeyError(f"Unknown timeframe: {timeframe}") from error

    def view_at(self, as_of) -> MarketDataView:
        timestamp = pd.Timestamp(as_of)
        timestamp = timestamp.tz_localize("UTC") if timestamp.tz is None else timestamp.tz_convert("UTC")
        visible = {
            timeframe: frame.loc[frame["close_time"] < timestamp].copy()
            for timeframe, frame in self._candles.items()
        }
        return MarketDataView(self.symbol, timestamp, visible)

    def event_times(self) -> list[pd.Timestamp]:
        values = set()
        for frame in self._candles.values():
            values.update(frame["close_time"] + pd.Timedelta(milliseconds=1))
        return sorted(values)
