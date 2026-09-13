import tempfile
import unittest
from pathlib import Path

import pandas as pd

from research.strategy_2_entry_v2_audit import (
    V1_RUN_ID, V2_RUN_ID, assert_pre_outcome, run_comparison,
)


ARTIFACTS = (
    Path("database/ai_decisions.db"),
    Path(f"research/output/strategy_2_entry_collection/entry_collection_{V1_RUN_ID}.json"),
    Path(f"research/output/strategy_2_entry_collection/entry_collection_{V2_RUN_ID}.json"),
)


class Strategy2EntryV2AuditTests(unittest.TestCase):
    def test_outcome_columns_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Forbidden outcome columns"):
            assert_pre_outcome(pd.DataFrame(columns=["candidate_id", "future_return"]))

    @unittest.skipUnless(all(path.exists() for path in ARTIFACTS),
                         "Local V1/V2 AI artifacts are not available")
    def test_v1_v2_join_and_outputs_are_pre_outcome_and_reproducible(self):
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first, summary = run_comparison(output_dir=first_dir)
            second, repeated = run_comparison(output_dir=second_dir)
            self.assertEqual(summary, repeated)
            self.assertEqual(first.to_dict("records"), second.to_dict("records"))
            self.assertEqual(summary["counts"], {
                "candidates": 81, "long": 18, "short": 63,
                "v1_approve": 8, "v2_approve": 33,
                "reject_to_approve": 25, "approve_to_approve": 8,
                "approve_to_reject": 0, "long_v2_approve": 7,
                "short_v2_approve": 26,
            })
            self.assertEqual(summary["reason_code_stability"]["v2_unique"], 14)
            self.assertEqual(summary["reason_code_stability"]["v2_singletons"], 0)
            self.assertEqual(summary["reason_code_stability"]["v2_outside_enum"], [])
            self.assertEqual(summary["pre_outcome_validation"]["outcomes_loaded"], 0)
            for name in ("candidate_comparison.csv", "newly_approved_candidates.csv",
                         "transition_summary.csv", "reason_code_comparison.csv", "summary.json"):
                self.assertTrue((Path(first_dir) / name).exists())


if __name__ == "__main__":
    unittest.main()
