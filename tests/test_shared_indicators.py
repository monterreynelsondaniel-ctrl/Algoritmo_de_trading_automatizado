import unittest

import numpy as np
import pandas as pd

from strategies.indicators import calculate_dmi_adx, calculate_disparity, calculate_ema, wilder_rma


class SharedIndicatorTests(unittest.TestCase):
    def test_wilder_rma_sma_seed_and_recursive_value(self):
        result = wilder_rma(pd.Series([1.0, 2.0, 3.0, 4.0]), 3)
        self.assertTrue(np.isnan(result.iloc[1]))
        self.assertEqual(result.iloc[2], 2.0)
        self.assertAlmostEqual(result.iloc[3], 8 / 3)

    def test_ema_disparity_and_dmi_are_causal(self):
        size = 45
        original = pd.DataFrame({"high": np.arange(size) + 2.0, "low": np.arange(size),
                                 "close": np.arange(size) + 1.0})
        changed = original.copy()
        changed.loc[40:, ["high", "low", "close"]] *= 10
        for frame in (original, changed):
            calculate_ema(frame, 10)
            calculate_disparity(frame, 10)
            calculate_dmi_adx(frame, 14)
        for column in ("ema_10", "disparity_10", "plus_di", "minus_di", "adx"):
            pd.testing.assert_series_equal(original[column].iloc[:40], changed[column].iloc[:40])
