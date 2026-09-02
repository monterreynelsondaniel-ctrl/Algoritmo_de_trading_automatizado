class BinanceExchangeError(Exception):
    """Base error for the exchange adapter."""


class BinanceConnectionError(BinanceExchangeError):
    """Temporary network, timeout, or Binance 5xx failure."""


class BinanceRateLimitError(BinanceExchangeError):
    """Binance rejected a request due to rate limits."""


class BinanceOrderRejectedError(BinanceExchangeError):
    """Binance rejected an order or mutation request."""


class BinanceUnknownOrderStateError(BinanceExchangeError):
    """An order submission timed out and its final state is unknown."""


class BinanceTradingDisabledError(BinanceExchangeError):
    """A mutation was blocked by the local safety configuration."""
