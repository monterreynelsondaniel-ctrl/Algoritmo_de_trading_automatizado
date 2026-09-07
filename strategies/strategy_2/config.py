from dataclasses import dataclass


@dataclass(frozen=True)
class Strategy2Config:
    version: str = "strategy_2_v1"
    trend_timeframe: str = "1d"
    setup_timeframe: str = "4h"
    confirmation_timeframe: str = "1h"
    management_timeframe: str = "4h"
    fast_ema: int = 10
    slow_ema: int = 55
    sqzmom_length: int = 20
    atr_length: int = 14
    adx_length: int = 14
    disparity_length: int = 20
    setup_expiration_bars: int | None = None
    capital_allocation: float = 1.0

    @property
    def required_timeframes(self):
        return tuple(dict.fromkeys((self.trend_timeframe, self.setup_timeframe,
                                    self.confirmation_timeframe, self.management_timeframe)))

    def validate(self):
        if any(value <= 0 for value in (self.fast_ema, self.slow_ema, self.sqzmom_length,
                                         self.atr_length, self.adx_length, self.disparity_length)):
            raise ValueError("Indicator lengths must be positive")
        if not 0 < self.capital_allocation <= 1:
            raise ValueError("capital_allocation must be in (0, 1]")
        if self.setup_expiration_bars is not None and self.setup_expiration_bars <= 0:
            raise ValueError("setup_expiration_bars must be positive or None")
