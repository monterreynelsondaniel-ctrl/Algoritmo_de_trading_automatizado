import unittest

from exchange.market_data import get_candles


class FakeHistoricalClient:
    def __init__(self):
        self.calls = []

    def futures_klines(self, **params):
        self.calls.append(params)
        rows = []
        for opened in (0, 3_600_000, 7_200_000):
            rows.append([opened, "1", "2", ".5", "1.5", "10", opened + 3_599_999,
                         "0", 0, "0", "0", "0"])
        return rows


class HistoricalMarketDataRangeTests(unittest.TestCase):
    def test_historical_end_is_sent_and_range_is_filtered(self):
        client = FakeHistoricalClient()
        candles = get_candles(
            "BTCUSDT", "1h", 3, client=client, closed_only=False,
            start_time="1970-01-01 01:00:00+00:00",
            end_time="1970-01-01 02:59:59.999+00:00",
        )
        self.assertEqual(client.calls[0]["endTime"], 10_799_999)
        self.assertEqual(len(candles), 2)
        self.assertEqual(candles.open_time.iloc[0].hour, 1)

    def test_invalid_historical_range_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "start_time"):
            get_candles("BTCUSDT", "1h", 1, client=FakeHistoricalClient(),
                        start_time="2026-01-02", end_time="2026-01-01")
