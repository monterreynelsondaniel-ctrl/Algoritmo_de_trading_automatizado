"""Deterministic 1D/4H/1H candidate pipeline; AI is outside this module."""

import hashlib

import pandas as pd

from exchange.multi_timeframe import MultiTimeframeMarketData
from strategies.candles import add_heikin_ashi
from strategies.indicators import (
    calculate_atr, calculate_bollinger_bands, calculate_disparity,
    calculate_dmi_adx, calculate_ema, calculate_keltner_channels,
    calculate_squeeze_state, calculate_sqzmom, calculate_sqzmom_color,
)
from strategies.strategy_2.config import Strategy2Config
from strategies.strategy_2.models import EntryCandidate, Strategy2Phase, Strategy2State
from strategies.strategy_2.rules import daily_trend, sqzmom_reversal


def _prepare_sqzmom(raw):
    frame = add_heikin_ashi(raw.copy())
    frame = calculate_bollinger_bands(frame, close_column="ha_close")
    frame = calculate_keltner_channels(frame, high_column="ha_high", low_column="ha_low",
                                       close_column="ha_close")
    frame = calculate_squeeze_state(frame)
    frame = calculate_sqzmom(frame, high_column="ha_high", low_column="ha_low",
                             close_column="ha_close")
    return calculate_sqzmom_color(frame)


class Strategy2:
    name = "strategy_2"
    signal_origin = "STRATEGY_2_MTF_SQZMOM"

    def __init__(self, config=None):
        self.config = config or Strategy2Config()
        self.config.validate()
        self.state = Strategy2State()

    def prepare_market_data(self, market_data):
        missing = set(self.config.required_timeframes) - set(market_data.timeframes)
        if missing:
            raise ValueError(f"Strategy 2 missing timeframes: {sorted(missing)}")
        frames = {}
        for timeframe in market_data.timeframes:
            raw = market_data.full_frame(timeframe)
            frame = _prepare_sqzmom(raw) if timeframe in {
                self.config.setup_timeframe, self.config.confirmation_timeframe,
            } else raw.copy()
            calculate_ema(frame, 10)
            calculate_ema(frame, 55)
            calculate_atr(frame, self.config.atr_length, output_column="market_atr")
            calculate_dmi_adx(frame, self.config.adx_length)
            calculate_disparity(frame, self.config.disparity_length)
            frames[timeframe] = frame
        return MultiTimeframeMarketData(market_data.symbol, frames)

    @staticmethod
    def _numeric_context(row):
        names = ("open", "high", "low", "close", "volume", "ema_10", "ema_55",
                 "market_atr", "plus_di", "minus_di", "adx", "disparity_20", "sqzmom")
        return {name: (None if name not in row or pd.isna(row[name]) else float(row[name]))
                for name in names}

    def evaluate(self, view):
        if self.state.phase == Strategy2Phase.POSITION_OPEN:
            return None
        setup_frame = view.frame(self.config.setup_timeframe)
        trend_frame = view.frame(self.config.trend_timeframe)
        if not setup_frame.empty:
            setup_time = setup_frame.close_time.iloc[-1]
            if setup_time != self.state.last_setup_candle:
                self.state.last_setup_candle = setup_time
                if self.state.phase == Strategy2Phase.WAITING_FOR_SETUP:
                    reversal = sqzmom_reversal(setup_frame)
                    trend = daily_trend(trend_frame)
                    if reversal and reversal == trend:
                        self.state.phase = Strategy2Phase.WAITING_FOR_CONFIRMATION
                        self.state.side, self.state.setup_time = reversal, setup_time
                elif self.state.phase == Strategy2Phase.WAITING_FOR_CONFIRMATION:
                    self.state.setup_bars_waited += 1
                    expiry = self.config.setup_expiration_bars
                    if expiry is not None and self.state.setup_bars_waited >= expiry:
                        last_seen = self.state.last_setup_candle
                        self.reset()
                        self.state.last_setup_candle = last_seen

        if self.state.phase != Strategy2Phase.WAITING_FOR_CONFIRMATION:
            return None
        confirmation = view.frame(self.config.confirmation_timeframe)
        if confirmation.empty:
            return None
        confirmation_time = confirmation.close_time.iloc[-1]
        if confirmation_time == self.state.last_confirmation_candle:
            return None
        self.state.last_confirmation_candle = confirmation_time
        if confirmation_time <= self.state.setup_time:
            return None
        if sqzmom_reversal(confirmation) != self.state.side:
            return None
        identity = f"{view.symbol}|{self.state.side}|{self.state.setup_time.isoformat()}|{confirmation_time.isoformat()}"
        context = {
            "symbol": view.symbol, "as_of": view.as_of.isoformat(),
            "trend_1d": self._numeric_context(trend_frame.iloc[-1]),
            "setup_4h": self._numeric_context(setup_frame.iloc[-1]),
            "confirmation_1h": self._numeric_context(confirmation.iloc[-1]),
        }
        candidate = EntryCandidate(hashlib.sha256(identity.encode()).hexdigest(), self.state.side,
                                   self.state.setup_time, confirmation_time, context)
        self.state.candidate, self.state.phase = candidate, Strategy2Phase.CANDIDATE
        return candidate

    def resolve_candidate(self, approved):
        if self.state.phase != Strategy2Phase.CANDIDATE:
            raise RuntimeError("No Strategy 2 candidate is awaiting resolution")
        candidate = self.state.candidate
        if approved:
            self.state.phase = Strategy2Phase.POSITION_OPEN
            self.state.side = candidate.side
            self.state.entry_context = candidate.context
        else:
            self.reset()

    def mark_entry(self, timestamp, price):
        if self.state.phase != Strategy2Phase.POSITION_OPEN:
            raise RuntimeError("Entry requires an approved Strategy 2 candidate")
        self.state.entry_time, self.state.entry_price = pd.Timestamp(timestamp), float(price)

    def management_payload(self, view, current_price, unrealized_pnl_pct, mfe_pct, mae_pct):
        frame = view.frame(self.config.management_timeframe)
        if frame.empty:
            return None
        candle_time = frame.close_time.iloc[-1]
        if candle_time == self.state.last_management_candle or self.state.entry_time is None:
            return None
        if candle_time <= self.state.entry_time:
            return None
        self.state.last_management_candle = candle_time
        self.state.bars_since_entry += 1
        return {
            "strategy_version": self.config.version,
            "position": {"side": self.state.side, "entry_time": self.state.entry_time.isoformat(),
                         "entry_price": self.state.entry_price},
            "entry_context": self.state.entry_context,
            "current_context_4h": self._numeric_context(frame.iloc[-1]),
            "path": {"current_price": float(current_price), "unrealized_pnl_pct": float(unrealized_pnl_pct),
                     "mfe_pct": float(mfe_pct), "mae_pct": float(mae_pct),
                     "bars_since_entry": self.state.bars_since_entry},
        }

    def technical_invalidation(self, view):
        """No v1 stop formula is authorized; execution/risk must not invent one."""
        return None

    def reset(self):
        self.state = Strategy2State()
