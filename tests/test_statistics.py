import unittest

import pandas as pd

from backtest.statistics import calculate_monthly_statistics


class MonthlyCriterionTests(unittest.TestCase):
    def test_monthly_70_30_criterion(self):
        results = pd.DataFrame({
            "exit_time": pd.to_datetime([
                "2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04",
                "2026-02-01", "2026-02-02",
            ], utc=True),
            "result": ["WIN", "WIN", "WIN", "LOSS", "WIN", "LOSS"],
            "pnl_pct": [1.0, 1.0, 1.0, -1.0, 1.0, -1.0],
        })

        monthly = calculate_monthly_statistics(results)

        self.assertEqual(monthly.loc[0, "win_rate"], 75.0)
        self.assertTrue(bool(monthly.loc[0, "meets_70_30"]))
        self.assertFalse(bool(monthly.loc[1, "meets_70_30"]))


if __name__ == "__main__":
    unittest.main()
