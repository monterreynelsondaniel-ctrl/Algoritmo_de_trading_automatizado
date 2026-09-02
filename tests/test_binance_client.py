import io
import logging
import unittest
from decimal import Decimal

from config import Settings
from exchange.binance_client import BinanceFuturesClient
from exchange.exceptions import BinanceUnknownOrderStateError
from logs.logger import SensitiveDataFilter, UTCFormatter


EXCHANGE_INFO = {
    "symbols": [{
        "symbol": "BTCUSDT",
        "filters": [
            {"filterType": "LOT_SIZE", "stepSize": "0.001"},
            {"filterType": "PRICE_FILTER", "tickSize": "0.10"},
            {"filterType": "MIN_NOTIONAL", "notional": "5"},
        ],
    }]
}


def enabled_settings(dry_run=False):
    return Settings(
        binance_env="testnet",
        binance_testnet_api_key="key",
        binance_testnet_api_secret="secret",
        trading_enabled=True,
        dry_run=dry_run,
    )


class MockClient:
    def __init__(self):
        self.exchange_info_calls = 0
        self.create_calls = []
        self.lookup_calls = []

    def futures_exchange_info(self):
        self.exchange_info_calls += 1
        return EXCHANGE_INFO


class BinanceClientTests(unittest.TestCase):
    def test_normalization_uses_decimal_and_caches_filters(self):
        mock = MockClient()
        client = BinanceFuturesClient(mock_client=mock)

        self.assertEqual(client.normalize_quantity("BTCUSDT", 0.1239), Decimal("0.123"))
        self.assertEqual(client.normalize_price("BTCUSDT", 123.199), Decimal("123.10"))
        self.assertEqual(client.normalize_price("BTCUSDT", 123.101, "up"), Decimal("123.20"))
        self.assertEqual(mock.exchange_info_calls, 1)

    def test_min_notional_validation(self):
        client = BinanceFuturesClient(mock_client=MockClient())
        self.assertTrue(client.validate_min_notional("BTCUSDT", "0.001", "5000"))
        self.assertFalse(client.validate_min_notional("BTCUSDT", "0.001", "4999"))

    def test_read_retries_with_exponential_backoff(self):
        mock = MockClient()
        attempts = []
        delays = []

        def mark_price(**_):
            attempts.append(1)
            if len(attempts) < 3:
                raise TimeoutError("temporary")
            return {"markPrice": "50000.5"}

        mock.futures_mark_price = mark_price
        client = BinanceFuturesClient(mock_client=mock, sleep=delays.append)

        self.assertEqual(client.get_mark_price("BTCUSDT"), 50000.5)
        self.assertEqual(len(attempts), 3)
        self.assertEqual(delays, [1, 2])

    def test_create_order_timeout_queries_same_client_id_without_resending(self):
        mock = MockClient()

        def create(**params):
            mock.create_calls.append(params)
            raise TimeoutError("unknown execution")

        def lookup(**params):
            mock.lookup_calls.append(params)
            return {"status": "FILLED", "clientOrderId": params["origClientOrderId"]}

        mock.futures_create_order = create
        mock.futures_get_order = lookup
        client = BinanceFuturesClient(config=enabled_settings(), mock_client=mock)

        result = client.create_order("BTCUSDT", "BUY", "MARKET", Decimal("0.001"), client_order_id="fixed-id")

        self.assertEqual(result["status"], "FILLED")
        self.assertEqual(len(mock.create_calls), 1)
        self.assertEqual(mock.create_calls[0]["newClientOrderId"], "fixed-id")
        self.assertEqual(mock.lookup_calls[0]["origClientOrderId"], "fixed-id")

    def test_create_order_unknown_lookup_never_resends(self):
        mock = MockClient()

        def create(**params):
            mock.create_calls.append(params)
            raise TimeoutError("unknown execution")

        def lookup(**params):
            mock.lookup_calls.append(params)
            raise RuntimeError("not found")

        mock.futures_create_order = create
        mock.futures_get_order = lookup
        client = BinanceFuturesClient(config=enabled_settings(), mock_client=mock, max_attempts=1)

        with self.assertRaises(BinanceUnknownOrderStateError):
            client.create_order("BTCUSDT", "BUY", "MARKET", "0.001")
        self.assertEqual(len(mock.create_calls), 1)

    def test_dry_run_does_not_call_exchange(self):
        mock = MockClient()
        client = BinanceFuturesClient(config=enabled_settings(dry_run=True), mock_client=mock)
        result = client.create_order("BTCUSDT", "BUY", "MARKET", "0.001")
        self.assertTrue(result["dryRun"])
        self.assertEqual(mock.create_calls, [])

    def test_conditional_order_uses_algo_client_id_and_reduce_only(self):
        mock = MockClient()
        calls = []

        def create_algo(**params):
            calls.append(params)
            return {"clientAlgoId": params["clientAlgoId"], "algoStatus": "NEW"}

        mock.futures_create_algo_order = create_algo
        client = BinanceFuturesClient(config=enabled_settings(), mock_client=mock)
        result = client.create_order(
            "BTCUSDT", "SELL", "STOP_MARKET", "0.001",
            client_order_id="stop-fixed", stopPrice="50000", reduceOnly=True,
        )

        self.assertEqual(result["clientAlgoId"], "stop-fixed")
        self.assertEqual(calls[0]["clientAlgoId"], "stop-fixed")
        self.assertEqual(calls[0]["triggerPrice"], "50000")
        self.assertTrue(calls[0]["reduceOnly"])
        self.assertNotIn("newClientOrderId", calls[0])


class LoggerSanitizationTests(unittest.TestCase):
    def test_nested_credentials_and_plain_strings_are_redacted(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(SensitiveDataFilter())
        handler.setFormatter(UTCFormatter("%(asctime)s | %(message)s"))
        logger = logging.getLogger("sanitization-test")
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.INFO)

        logger.info({
            "API_KEY": "visible-key",
            "nested": {"signature": "visible-signature"},
            "header": "Authorization: Bearer visible-token",
        })
        output = stream.getvalue()

        self.assertNotIn("visible-key", output)
        self.assertNotIn("visible-signature", output)
        self.assertNotIn("visible-token", output)
        self.assertIn("***REDACTED***", output)
        self.assertIn("UTC", output)

        stream.seek(0)
        stream.truncate(0)
        logger.info('{"api_secret":"raw-secret","value":1}')
        self.assertNotIn("raw-secret", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
