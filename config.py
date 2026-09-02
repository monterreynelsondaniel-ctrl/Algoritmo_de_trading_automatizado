import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    """Raised when environment configuration is invalid."""


def _boolean(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be a boolean")


@dataclass(frozen=True)
class Settings:
    binance_env: str = "testnet"
    binance_testnet_api_key: str = ""
    binance_testnet_api_secret: str = ""
    binance_live_api_key: str = ""
    binance_live_api_secret: str = ""
    trading_enabled: bool = False
    dry_run: bool = True
    symbol: str = "BTCUSDT"
    timeframe: str = "4h"
    leverage: int = 1
    risk_per_trade_pct: float = 0.5
    max_notional_usdt: float = 100.0
    atr_multiplier: float = 1.5
    breakeven_r_multiple: float = 1.5
    dry_run_equity_usdt: float = 1000.0
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None, env_file: Optional[str] = ".env") -> "Settings":
        if env_file:
            load_dotenv(Path(env_file), override=False)
        values = os.environ if env is None else env
        settings = cls(
            binance_env=values.get("BINANCE_ENV", "testnet").strip().lower(),
            binance_testnet_api_key=values.get("BINANCE_TESTNET_API_KEY", "").strip(),
            binance_testnet_api_secret=values.get("BINANCE_TESTNET_API_SECRET", "").strip(),
            binance_live_api_key=values.get("BINANCE_LIVE_API_KEY", "").strip(),
            binance_live_api_secret=values.get("BINANCE_LIVE_API_SECRET", "").strip(),
            trading_enabled=_boolean(values.get("TRADING_ENABLED", "false"), "TRADING_ENABLED"),
            dry_run=_boolean(values.get("DRY_RUN", "true"), "DRY_RUN"),
            symbol=values.get("SYMBOL", "BTCUSDT").strip().upper(),
            timeframe=values.get("TIMEFRAME", "4h").strip(),
            leverage=int(values.get("LEVERAGE", "1")),
            risk_per_trade_pct=float(values.get("RISK_PER_TRADE_PCT", "0.5")),
            max_notional_usdt=float(values.get("MAX_NOTIONAL_USDT", "100.0")),
            atr_multiplier=float(values.get("ATR_MULTIPLIER", "1.5")),
            breakeven_r_multiple=float(values.get("BREAKEVEN_R_MULTIPLE", "1.5")),
            dry_run_equity_usdt=float(values.get("DRY_RUN_EQUITY_USDT", "1000.0")),
            log_level=values.get("LOG_LEVEL", "INFO").strip().upper(),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.binance_env not in {"testnet", "live"}:
            raise ConfigurationError("BINANCE_ENV must be 'testnet' or 'live'")
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigurationError("LOG_LEVEL is invalid")
        if not self.symbol or not self.timeframe:
            raise ConfigurationError("SYMBOL and TIMEFRAME cannot be empty")
        if self.leverage < 1:
            raise ConfigurationError("LEVERAGE must be at least 1")
        if not 0 < self.risk_per_trade_pct <= 100:
            raise ConfigurationError("RISK_PER_TRADE_PCT must be between 0 and 100")
        if self.max_notional_usdt <= 0:
            raise ConfigurationError("MAX_NOTIONAL_USDT must be greater than zero")
        if self.atr_multiplier <= 0 or self.breakeven_r_multiple <= 0:
            raise ConfigurationError("ATR and breakeven multipliers must be positive")
        if self.dry_run_equity_usdt <= 0:
            raise ConfigurationError("DRY_RUN_EQUITY_USDT must be positive")

    @property
    def api_key(self) -> str:
        return self.binance_testnet_api_key if self.binance_env == "testnet" else self.binance_live_api_key

    @property
    def api_secret(self) -> str:
        return self.binance_testnet_api_secret if self.binance_env == "testnet" else self.binance_live_api_secret

    def has_credentials(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def can_send_orders(self) -> bool:
        return self.trading_enabled and not self.dry_run and self.has_credentials()

    def is_live_ready(self) -> bool:
        return self.binance_env == "live" and self.can_send_orders()


settings = Settings.from_env()

# Backward-compatible constants for the existing strategy modules.
SYMBOL = settings.symbol
TIMEFRAME = settings.timeframe
LEVERAGE = settings.leverage
RISK_PER_TRADE_PCT = settings.risk_per_trade_pct
MAX_NOTIONAL_USDT = settings.max_notional_usdt
ATR_MULTIPLIER = settings.atr_multiplier
BREAKEVEN_R_MULTIPLE = settings.breakeven_r_multiple
MAX_OPEN_POSITIONS = 1
MIN_CONFIDENCE = 70
AGGRESSIVE_CONFIDENCE = 85
USE_STOP_LOSS = False
