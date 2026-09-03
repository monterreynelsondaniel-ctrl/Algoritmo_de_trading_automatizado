import unittest

import pandas as pd

from research.atr_contraction_experiment import apply_fixed_filter, evaluate


class AtrContractionExperimentTests(unittest.TestCase):
    def test_filter_uses_fixed_semantic_threshold(self):
        trades = pd.DataFrame({"atr_expansion": [0.99, 1.0, 1.01]})
        self.assertEqual(list(apply_fixed_filter(trades).index), [0, 1])

    def test_audit_preserves_all_baseline_trades(self):
        trades = pd.DataFrame({
            "entry_signal_time": ["a", "b"], "entry_time": ["c", "d"],
            "signal": ["LONG", "SHORT"], "atr_expansion": [.9, 1.1],
            "pnl_bruto": [1.0, -1.0], "pnl_neto": [.8, -1.2],
            "result": ["WIN", "LOSS"], "duration_hours": [48, 48],
            "max_favorable_pct": [1.2, .1], "max_adverse_pct": [-.2, -1.5],
        })
        comparisons, audit = evaluate(trades)
        self.assertEqual(len(audit), 2)
        self.assertEqual(audit.entry_allowed.tolist(), [True, False])
        self.assertEqual(comparisons.iloc[0].candidate_trades, 1)


if __name__ == "__main__":
    unittest.main()
