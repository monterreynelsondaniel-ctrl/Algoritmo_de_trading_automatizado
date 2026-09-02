import logging
import time
import uuid
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from typing import Callable, Dict, Literal, Optional

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout as RequestsTimeout

from config import Settings, settings as default_settings
from exchange.exceptions import (
    BinanceConnectionError,
    BinanceExchangeError,
    BinanceOrderRejectedError,
    BinanceRateLimitError,
    BinanceTradingDisabledError,
    BinanceUnknownOrderStateError,
)
from logs.logger import get_logger, log_event


TESTNET_FUTURES_URL = "https://testnet.binancefuture.com/fapi"
RATE_LIMIT_CODES = {-1003, -1015}
ORDER_NOT_FOUND_CODE = -2013
UNKNOWN_SUBMISSION_CODES = {-1006, -1007}
CONDITIONAL_ORDER_TYPES = {
    "STOP", "STOP_MARKET", "TAKE_PROFIT", "TAKE_PROFIT_MARKET",
    "TRAILING_STOP_MARKET",
}


def _decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise ValueError("Exchange step must be greater than zero")
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def _api_string(value: Decimal) -> str:
    return format(value, "f")


class BinanceFuturesClient:
    """Isolated, fail-closed adapter for Binance USD-M Futures REST."""

    def __init__(
        self,
        config: Settings = default_settings,
        mock_client=None,
        sleep: Callable[[float], None] = time.sleep,
        logger=None,
        max_attempts: int = 3,
    ):
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.settings = config
        self.sleep = sleep
        self.max_attempts = max_attempts
        self.logger = logger or get_logger(level=config.log_level)
        self._exchange_info_cache: Dict[str, dict] = {}

        if mock_client is not None:
            self.client = mock_client
        else:
            self.client = Client(
                config.api_key or None,
                config.api_secret or None,
                testnet=config.binance_env == "testnet",
                ping=False,
            )
            if config.binance_env == "testnet":
                self.client.FUTURES_URL = TESTNET_FUTURES_URL

    def _translate_error(self, error: Exception, mutation: bool = False) -> BinanceExchangeError:
        if isinstance(error, BinanceExchangeError):
            return error
        if isinstance(error, BinanceAPIException):
            status = getattr(error, "status_code", None)
            code = getattr(error, "code", None)
            message = getattr(error, "message", str(error))
            if status in {418, 429} or code in RATE_LIMIT_CODES:
                return BinanceRateLimitError(message)
            if status is not None and status >= 500:
                return BinanceConnectionError(message)
            if mutation:
                return BinanceOrderRejectedError(message)
            return BinanceExchangeError(message)
        if isinstance(error, (TimeoutError, RequestsTimeout, RequestsConnectionError, BinanceRequestException)):
            return BinanceConnectionError(str(error))
        return BinanceExchangeError(str(error))

    def _read(self, operation: str, callback: Callable[[], object]):
        for attempt in range(1, self.max_attempts + 1):
            try:
                return callback()
            except Exception as raw_error:
                error = self._translate_error(raw_error)
                retryable = isinstance(error, (BinanceConnectionError, BinanceRateLimitError))
                if not retryable or attempt == self.max_attempts:
                    log_event(self.logger, logging.ERROR, "binance_read_failed", operation=operation, attempt=attempt, error=str(error))
                    raise error from raw_error
                delay = 2 ** (attempt - 1)
                log_event(self.logger, logging.WARNING, "binance_read_retry", operation=operation, attempt=attempt, delay_seconds=delay, error=str(error))
                self.sleep(delay)

    def _mutation_allowed(self) -> None:
        if not self.settings.can_send_orders():
            raise BinanceTradingDisabledError(
                "Mutation blocked: require TRADING_ENABLED=true, DRY_RUN=false and credentials"
            )

    def get_usdt_balance(self) -> float:
        balances = self._read("get_usdt_balance", self.client.futures_account_balance)
        for asset in balances:
            if asset.get("asset") == "USDT":
                return float(asset.get("availableBalance", asset.get("balance", 0)))
        return 0.0

    def get_mark_price(self, symbol: str) -> float:
        data = self._read(
            "get_mark_price",
            lambda: self.client.futures_mark_price(symbol=symbol.upper()),
        )
        return float(data["markPrice"])

    def get_position_mode(self) -> str:
        data = self._read(
            "get_position_mode", self.client.futures_get_position_mode
        )
        return "HEDGE" if data.get("dualSidePosition") else "ONE_WAY"

    def get_open_positions(self, symbol: str) -> list:
        positions = self._read(
            "get_open_positions",
            lambda: self.client.futures_position_information(symbol=symbol.upper()),
        )
        return [item for item in positions if _decimal(item.get("positionAmt", "0")) != 0]

    def get_open_orders(self, symbol: str) -> list:
        regular = self._read(
            "get_open_orders",
            lambda: self.client.futures_get_open_orders(symbol=symbol.upper()),
        )
        algo_method = getattr(self.client, "futures_get_open_algo_orders", None)
        if algo_method is None:
            return regular
        algo = self._read(
            "get_open_algo_orders",
            lambda: algo_method(symbol=symbol.upper()),
        )
        return regular + algo

    def get_order(self, symbol: str, client_order_id: str, conditional=False) -> dict:
        if conditional:
            return self._read(
                "get_algo_order",
                lambda: self.client.futures_get_algo_order(
                    symbol=symbol.upper(), clientAlgoId=client_order_id
                ),
            )
        return self._read(
            "get_order",
            lambda: self.client.futures_get_order(
                symbol=symbol.upper(), origClientOrderId=client_order_id
            ),
        )

    def get_recent_orders(self, symbol: str, limit: int = 100) -> list:
        regular = self._read(
            "get_recent_orders",
            lambda: self.client.futures_get_all_orders(
                symbol=symbol.upper(), limit=limit
            ),
        )
        algo_method = getattr(self.client, "futures_get_all_algo_orders", None)
        if algo_method is None:
            return regular
        conditional = self._read(
            "get_recent_algo_orders",
            lambda: algo_method(symbol=symbol.upper(), limit=limit),
        )
        return regular + conditional

    def get_account_trades(self, symbol: str, limit: int = 100) -> list:
        return self._read(
            "get_account_trades",
            lambda: self.client.futures_account_trades(
                symbol=symbol.upper(), limit=limit
            ),
        )

    def get_exchange_info(self, symbol: str) -> dict:
        symbol = symbol.upper()
        if symbol in self._exchange_info_cache:
            return self._exchange_info_cache[symbol]

        response = self._read("get_exchange_info", self.client.futures_exchange_info)
        raw_symbol = next(
            (item for item in response.get("symbols", []) if item.get("symbol") == symbol),
            None,
        )
        if raw_symbol is None:
            raise BinanceExchangeError(f"Symbol not found in exchangeInfo: {symbol}")

        filters = {item["filterType"]: item for item in raw_symbol.get("filters", [])}
        try:
            parsed = {
                "symbol": symbol,
                "stepSize": _decimal(filters["LOT_SIZE"]["stepSize"]),
                "tickSize": _decimal(filters["PRICE_FILTER"]["tickSize"]),
                "minNotional": _decimal(filters["MIN_NOTIONAL"].get("notional", filters["MIN_NOTIONAL"].get("minNotional"))),
            }
        except (KeyError, TypeError, ValueError) as error:
            raise BinanceExchangeError(f"Incomplete exchange filters for {symbol}") from error

        self._exchange_info_cache[symbol] = parsed
        return parsed

    def normalize_quantity(self, symbol: str, quantity) -> Decimal:
        step = self.get_exchange_info(symbol)["stepSize"]
        return _floor_to_step(_decimal(quantity), step)

    def normalize_price(
        self,
        symbol: str,
        price,
        rounding: Literal["down", "up"] = "down",
    ) -> Decimal:
        tick = self.get_exchange_info(symbol)["tickSize"]
        if rounding not in {"down", "up"}:
            raise ValueError("rounding must be 'down' or 'up'")
        mode = ROUND_DOWN if rounding == "down" else ROUND_UP
        value = _decimal(price)
        return (value / tick).to_integral_value(rounding=mode) * tick

    def validate_min_notional(self, symbol: str, quantity, price) -> bool:
        minimum = self.get_exchange_info(symbol)["minNotional"]
        return _decimal(quantity) * _decimal(price) >= minimum

    def set_leverage(self, symbol: str, leverage: int):
        if leverage < 1:
            raise ValueError("leverage must be at least 1")
        if self.settings.dry_run:
            return {"dryRun": True, "symbol": symbol.upper(), "leverage": leverage}
        self._mutation_allowed()
        try:
            return self.client.futures_change_leverage(symbol=symbol.upper(), leverage=leverage)
        except Exception as raw_error:
            raise self._translate_error(raw_error, mutation=True) from raw_error

    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity,
        client_order_id: Optional[str] = None,
        **params,
    ) -> dict:
        order_id = client_order_id or f"tb-{uuid.uuid4().hex}"
        normalized_type = order_type.upper()
        conditional = normalized_type in CONDITIONAL_ORDER_TYPES
        payload = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": normalized_type,
            "quantity": _api_string(_decimal(quantity)),
            **params,
        }
        if conditional:
            payload["clientAlgoId"] = order_id
            payload["algoType"] = "CONDITIONAL"
            if "stopPrice" in payload and "triggerPrice" not in payload:
                payload["triggerPrice"] = payload.pop("stopPrice")
        else:
            payload["newClientOrderId"] = order_id
        if self.settings.dry_run:
            return {"dryRun": True, "status": "SIMULATED", **payload}
        self._mutation_allowed()

        try:
            if conditional:
                return self.client.futures_create_algo_order(**payload)
            return self.client.futures_create_order(**payload)
        except Exception as raw_error:
            translated = self._translate_error(raw_error, mutation=True)
            uncertain = isinstance(raw_error, (TimeoutError, RequestsTimeout, RequestsConnectionError, BinanceRequestException))
            uncertain = uncertain or isinstance(translated, BinanceConnectionError)
            uncertain = uncertain or (
                isinstance(raw_error, BinanceAPIException)
                and getattr(raw_error, "code", None) in UNKNOWN_SUBMISSION_CODES
            )
            if not uncertain:
                raise translated from raw_error

            log_event(self.logger, logging.WARNING, "order_submission_uncertain", symbol=symbol, client_order_id=order_id, error=str(translated))
            try:
                return self._read(
                    "get_order_after_timeout",
                    lambda: (
                        self.client.futures_get_algo_order(
                            symbol=symbol.upper(), clientAlgoId=order_id
                        )
                        if conditional
                        else self.client.futures_get_order(
                            symbol=symbol.upper(), origClientOrderId=order_id
                        )
                    ),
                )
            except Exception as lookup_error:
                raise BinanceUnknownOrderStateError(
                    f"Order state is unknown for clientOrderId={order_id}"
                ) from lookup_error

    def cancel_order(
        self, symbol: str, client_order_id: str, conditional=False
    ) -> dict:
        if self.settings.dry_run:
            return {
                "dryRun": True, "status": "CANCELED", "symbol": symbol.upper(),
                "clientOrderId": client_order_id,
            }
        self._mutation_allowed()
        try:
            if conditional:
                return self.client.futures_cancel_algo_order(
                    symbol=symbol.upper(), clientAlgoId=client_order_id
                )
            return self.client.futures_cancel_order(
                symbol=symbol.upper(), origClientOrderId=client_order_id
            )
        except Exception as raw_error:
            raise self._translate_error(raw_error, mutation=True) from raw_error


# Compatibility alias for concise imports.
BinanceClient = BinanceFuturesClient
