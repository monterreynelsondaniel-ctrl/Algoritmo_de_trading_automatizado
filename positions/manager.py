import logging
from decimal import Decimal

from config import Settings, settings as default_settings
from database.trade_service import TradeService, trade_service as default_trade_service
from logs.logger import get_logger, log_event


def _decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


class RiskValidationError(ValueError):
    """A proposed position violates a risk or exchange constraint."""


class PositionManager:
    def __init__(
        self,
        binance_client,
        trade_service: TradeService = default_trade_service,
        config: Settings = default_settings,
        logger=None,
    ):
        self.binance_client = binance_client
        self.trade_service = trade_service
        self.settings = config
        self.logger = logger or get_logger(level=config.log_level)

    def can_open_position(self, symbol: str) -> bool:
        """Fail closed when Binance or local state reports exposure."""
        symbol = symbol.upper()
        positions = self.binance_client.get_open_positions(symbol)
        orders = self.binance_client.get_open_orders(symbol)
        local_trade = self.trade_service.get_active_trade(symbol)

        if positions or orders:
            if local_trade:
                self.trade_service.mark_reconciled(local_trade.client_order_id)
            else:
                log_event(
                    self.logger, logging.ERROR, "exchange_local_position_mismatch",
                    symbol=symbol, exchange_positions=len(positions),
                    exchange_orders=len(orders), local_trade=False,
                )
            return False

        if local_trade:
            self.trade_service.mark_reconciled(local_trade.client_order_id)
            log_event(
                self.logger, logging.ERROR, "local_exchange_position_mismatch",
                symbol=symbol, client_order_id=local_trade.client_order_id,
            )
            return False

        return True

    def calculate_position_size(
        self, equity_usdt, entry_price, stop_price, symbol: str
    ) -> Decimal:
        equity = _decimal(equity_usdt)
        entry = _decimal(entry_price)
        stop = _decimal(stop_price)
        if equity <= 0 or entry <= 0:
            raise RiskValidationError("equity and entry price must be positive")

        stop_distance = abs(entry - stop)
        if stop_distance <= 0:
            raise RiskValidationError("stop distance must be greater than zero")

        risk_fraction = _decimal(self.settings.risk_per_trade_pct) / Decimal("100")
        risk_amount = equity * risk_fraction
        raw_quantity = risk_amount / stop_distance

        max_notional = _decimal(self.settings.max_notional_usdt)
        if raw_quantity * entry > max_notional:
            raw_quantity = max_notional / entry

        quantity = self.binance_client.normalize_quantity(symbol, raw_quantity)
        if quantity <= 0:
            raise RiskValidationError("normalized quantity is zero")
        if not self.binance_client.validate_min_notional(symbol, quantity, entry):
            raise RiskValidationError("position does not meet MIN_NOTIONAL")
        return quantity

    def calculate_risk_amount(self, quantity, entry_price, stop_price) -> Decimal:
        return _decimal(quantity) * abs(_decimal(entry_price) - _decimal(stop_price))

    def calculate_initial_stop(
        self, entry_price, atr_value, side: str, symbol: str
    ) -> Decimal:
        entry = _decimal(entry_price)
        atr = _decimal(atr_value)
        side = side.upper()
        if entry <= 0 or atr <= 0:
            raise RiskValidationError("entry price and ATR must be positive")
        distance = atr * _decimal(self.settings.atr_multiplier)
        if side == "LONG":
            stop = entry - distance
            rounding = "down"
        elif side == "SHORT":
            stop = entry + distance
            rounding = "up"
        else:
            raise RiskValidationError("side must be LONG or SHORT")
        if stop <= 0:
            raise RiskValidationError("calculated stop must be positive")
        return self.binance_client.normalize_price(symbol, stop, rounding)

    def should_move_to_breakeven(
        self, side: str, entry_price, current_price, initial_stop
    ) -> bool:
        entry = _decimal(entry_price)
        current = _decimal(current_price)
        initial_risk = abs(entry - _decimal(initial_stop))
        if initial_risk <= 0:
            raise RiskValidationError("initial risk must be greater than zero")
        trigger_distance = initial_risk * _decimal(self.settings.breakeven_r_multiple)
        side = side.upper()
        if side == "LONG":
            return current >= entry + trigger_distance
        if side == "SHORT":
            return current <= entry - trigger_distance
        raise RiskValidationError("side must be LONG or SHORT")

    def get_breakeven_stop_price(
        self, side: str, entry_price, symbol: str
    ) -> Decimal:
        side = side.upper()
        if side not in {"LONG", "SHORT"}:
            raise RiskValidationError("side must be LONG or SHORT")
        rounding = "down" if side == "LONG" else "up"
        return self.binance_client.normalize_price(symbol, entry_price, rounding)
