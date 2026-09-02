import unittest

import pandas as pd

from strategies.candles import add_heikin_ashi


class HeikinAshiTests(unittest.TestCase):
    def test_calculation_preserves_real_prices(self):
        candles = pd.DataFrame({
            "open": [10.0, 12.0],
            "high": [14.0, 15.0],
            "low": [8.0, 11.0],
            "close": [12.0, 14.0],
        })

        result = add_heikin_ashi(candles)

        self.assertEqual(result["open"].tolist(), [10.0, 12.0])
        self.assertEqual(result["ha_close"].tolist(), [11.0, 13.0])
        self.assertEqual(result["ha_open"].tolist(), [11.0, 11.0])
        self.assertEqual(result["ha_high"].tolist(), [14.0, 15.0])
        self.assertEqual(result["ha_low"].tolist(), [8.0, 11.0])


if __name__ == "__main__":
    unittest.main()
