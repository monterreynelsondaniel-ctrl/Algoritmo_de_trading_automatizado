import unittest

import numpy as np
import pandas as pd

from research.strategy_diagnostics import _prior_impulse, entry_features


class StrategyDiagnosticsTests(unittest.TestCase):
    def test_prior_impulse_excludes_reversal_bar(self):
        bars, amplitude = _prior_impulse(pd.Series([1.0, 2.0, 3.0, 2.5]), "SHORT")
        self.assertEqual(bars, 2)
        self.assertEqual(amplitude, 2.0)

    def test_entry_features_do_not_read_future_rows(self):
        count = 80
        close = pd.Series(np.linspace(100, 120, count))
        frame = pd.DataFrame({
            "open": close, "high": close + 1, "low": close - 1, "close": close,
            "atr": np.full(count, 2.0), "sqzmom": np.r_[np.linspace(-4, 4, count - 2), 3.0, 2.0],
            "sqz_on": np.zeros(count, dtype=bool), "sqz_off": np.ones(count, dtype=bool),
            "no_sqz": np.zeros(count, dtype=bool),
        })
        position = 60
        expected = entry_features(frame, position, "SHORT")
        changed = frame.copy()
        changed.loc[position + 1:, ["open", "high", "low", "close", "atr", "sqzmom"]] = 999999
        actual = entry_features(changed, position, "SHORT")
        for key in expected:
            if isinstance(expected[key], float) and np.isnan(expected[key]):
                self.assertTrue(np.isnan(actual[key]))
            else:
                self.assertEqual(expected[key], actual[key], key)


if __name__ == "__main__":
    unittest.main()
