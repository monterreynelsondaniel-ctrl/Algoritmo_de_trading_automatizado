import tempfile
import unittest
from pathlib import Path

from research.strategy_2_entry_ai_audit import (
    DEFAULT_RUN_ID, EXPECTED_INPUT_FINGERPRINT, EXPECTED_SEQUENCE_FINGERPRINT,
    EntryAuditError, assert_pre_outcome_columns, run_audit,
)


ARTIFACTS_PRESENT = (
    Path("database/ai_decisions.db").exists()
    and Path(f"research/output/strategy_2_entry_collection/entry_collection_{DEFAULT_RUN_ID}.json").exists()
)


class Strategy2EntryAIAuditTests(unittest.TestCase):
    def test_outcome_columns_are_rejected(self):
        for column in ("pnl", "return", "mfe", "mae", "win", "loss", "exit_price", "future_close"):
            with self.subTest(column=column), self.assertRaises(EntryAuditError):
                assert_pre_outcome_columns(["candidate_id", column])

    @unittest.skipUnless(ARTIFACTS_PRESENT, "Local AI cache and collector dataset are required")
    def test_live_entry_cache_join_and_outputs_are_reproducible(self):
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first, first_summary = run_audit(output_dir=first_dir)
            second, second_summary = run_audit(output_dir=second_dir)
            self.assertEqual(first_summary["counts"], {
                "total": 81, "long": 18, "short": 63, "approve": 8, "reject": 73,
                "long_approve": 0, "long_reject": 18,
                "short_approve": 8, "short_reject": 55,
            })
            self.assertEqual(first_summary["candidate_sequence_fingerprint"],
                             EXPECTED_SEQUENCE_FINGERPRINT)
            self.assertEqual(first_summary["ai_input_sequence_fingerprint"],
                             EXPECTED_INPUT_FINGERPRINT)
            self.assertEqual(first.candidate_id.tolist(), second.candidate_id.tolist())
            self.assertEqual(first.input_hash.tolist(), second.input_hash.tolist())
            self.assertEqual(first_summary["pre_outcome_validation"]["forbidden_columns"], [])
            self.assertEqual(first_summary["schema_consistency"]["schema_errors"], [])
            expected = {"candidate_audit.csv", "approved_candidates.csv",
                        "reason_code_summary.csv", "feature_comparison.csv",
                        "categorical_summary.csv", "summary.json"}
            self.assertEqual({path.name for path in Path(first_dir).iterdir()}, expected)
