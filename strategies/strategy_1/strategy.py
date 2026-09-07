"""Encapsulation of the historical SQZMOM strategy."""

import pandas as pd

from strategies.candles import add_heikin_ashi
from strategies.indicators import calculate_indicators
from strategies.strategy_1.signals import detect_historical_reversals, generate_signal


class Strategy1:
    """Frozen Strategy 1 behavior: HA SQZMOM reversal on four-hour candles."""

    name = "strategy_1"
    signal_origin = "SQZMOM_REVERSAL_HEIKIN_ASHI"

    def prepare_candles(self, candles: pd.DataFrame) -> pd.DataFrame:
        return calculate_indicators(add_heikin_ashi(candles))

    def generate_signal(self, candles: pd.DataFrame) -> dict:
        return generate_signal(candles)

    def historical_signals(self, candles: pd.DataFrame) -> list[dict]:
        return detect_historical_reversals(candles)
