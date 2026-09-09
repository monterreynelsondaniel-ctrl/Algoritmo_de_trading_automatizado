import os
from dataclasses import dataclass, field
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
    openai_api_key: str = field(default="", repr=False)
    ai_provider: str = "openai"
    openai_model: str = "gpt-5.6-terra"
    openai_reasoning_effort: str = "low"
    ai_decision_mode: str = "replay"
    ai_cache_path: str = "database/ai_decisions.db"
    ai_max_attempts: int = 2
    openai_timeout_seconds: float = 30.0
    ai_max_run_cost_usd: float = 2.5
    ai_max_live_calls_per_run: int = 100
    ai_max_output_tokens_per_call: int = 2000
    ai_input_cost_per_million_usd: float = 2.0
    ai_output_cost_per_million_usd: float = 12.0

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
            openai_api_key=values.get("OPENAI_API_KEY", "").strip(),
            ai_provider=values.get("AI_PROVIDER", "openai").strip().lower(),
            openai_model=values.get("OPENAI_MODEL", "gpt-5.6-terra").strip(),
            openai_reasoning_effort=values.get("OPENAI_REASONING_EFFORT", "low").strip().lower(),
            ai_decision_mode=values.get("AI_DECISION_MODE", "replay").strip().lower(),
            ai_cache_path=values.get("AI_CACHE_PATH", "database/ai_decisions.db").strip(),
            ai_max_attempts=int(values.get("AI_MAX_ATTEMPTS", "2")),
            openai_timeout_seconds=float(values.get("OPENAI_TIMEOUT_SECONDS", "30")),
            ai_max_run_cost_usd=float(values.get("AI_MAX_RUN_COST_USD", "2.5")),
            ai_max_live_calls_per_run=int(values.get("AI_MAX_LIVE_CALLS_PER_RUN", "100")),
            ai_max_output_tokens_per_call=int(values.get("AI_MAX_OUTPUT_TOKENS_PER_CALL", "2000")),
            ai_input_cost_per_million_usd=float(
                values.get("AI_INPUT_COST_PER_MILLION_USD", "2.0")
            ),
            ai_output_cost_per_million_usd=float(
                values.get("AI_OUTPUT_COST_PER_MILLION_USD", "12.0")
            ),
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
        if self.ai_decision_mode not in {"replay", "live"}:
            raise ConfigurationError("AI_DECISION_MODE must be 'replay' or 'live'")
        if self.ai_provider != "openai":
            raise ConfigurationError("Only AI_PROVIDER=openai is currently supported")
        if not self.openai_model or self.openai_reasoning_effort not in {
            "none", "minimal", "low", "medium", "high", "xhigh", "max"
        }:
            raise ConfigurationError("OpenAI model/reasoning configuration is invalid")
        if self.ai_max_attempts < 1 or not self.ai_cache_path or self.openai_timeout_seconds <= 0:
            raise ConfigurationError("AI_MAX_ATTEMPTS and AI_CACHE_PATH are invalid")
        if self.ai_max_run_cost_usd <= 0 or self.ai_max_live_calls_per_run < 1:
            raise ConfigurationError("AI run cost and call limits must be positive")
        if self.ai_max_output_tokens_per_call < 1:
            raise ConfigurationError("AI_MAX_OUTPUT_TOKENS_PER_CALL must be positive")
        if self.ai_input_cost_per_million_usd < 0 or self.ai_output_cost_per_million_usd < 0:
            raise ConfigurationError("AI token prices cannot be negative")

    def ai_live_ready(self) -> bool:
        return self.ai_decision_mode == "live" and bool(self.openai_api_key)

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
