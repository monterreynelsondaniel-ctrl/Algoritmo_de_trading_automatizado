"""Single pre-registered ATR-contraction experiment over the frozen baseline.

The hypothesis and cutoff were selected in the preceding exploratory study.
Consequently, results on this snapshot are development evidence, not a genuine
out-of-sample validation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from research.strategy_diagnostics import performance_summary, run as run_diagnostics


EXPERIMENT_ID = "atr14_not_above_20bar_mean"
FIXED_THRESHOLD = 1.0


def apply_fixed_filter(trades: pd.DataFrame) -> pd.DataFrame:
    """Allow entry only when point-in-time ATR expansion is <= 1.0."""
    return trades.loc[trades["atr_expansion"] <= FIXED_THRESHOLD].copy()


def comparison_row(label: str, baseline: pd.DataFrame, candidate: pd.DataFrame) -> dict:
    base = performance_summary(baseline)
    test = performance_summary(candidate) if len(candidate) else {}
    positive_pool = baseline.loc[baseline.pnl_neto > 0, "pnl_neto"].sum()
    retained_positive = candidate.loc[candidate.pnl_neto > 0, "pnl_neto"].sum()
    return {
        "scope": label,
        "baseline_trades": base["trades"],
        "candidate_trades": test.get("trades", 0),
        "trade_retention_pct": len(candidate) / len(baseline) * 100 if len(baseline) else 0,
        "baseline_win_rate": base["win_rate"],
        "candidate_win_rate": test.get("win_rate"),
        "baseline_expectancy": base["expectancy"],
        "candidate_expectancy": test.get("expectancy"),
        "baseline_profit_factor": base["profit_factor"],
        "candidate_profit_factor": test.get("profit_factor"),
        "baseline_sum_net": base["sum_net"],
        "candidate_sum_net": test.get("sum_net"),
        "baseline_avg_loss": base["avg_loss"],
        "candidate_avg_loss": test.get("avg_loss"),
        "positive_pnl_retention_pct": retained_positive / positive_pool * 100 if positive_pool else 0,
    }


def evaluate(trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    candidate = apply_fixed_filter(trades)
    midpoint = len(trades) // 2
    scopes = [
        ("ALL", trades),
        ("LONG", trades[trades.signal == "LONG"]),
        ("SHORT", trades[trades.signal == "SHORT"]),
        ("FIRST_HALF", trades.iloc[:midpoint]),
        ("SECOND_HALF", trades.iloc[midpoint:]),
    ]
    comparisons = pd.DataFrame([
        comparison_row(label, baseline, apply_fixed_filter(baseline))
        for label, baseline in scopes
    ])
    audit = trades[[
        "entry_signal_time", "entry_time", "signal", "atr_expansion",
        "pnl_bruto", "pnl_neto", "result", "duration_hours",
    ]].copy()
    audit["entry_allowed"] = audit.atr_expansion <= FIXED_THRESHOLD
    audit["experiment_id"] = EXPERIMENT_ID
    return comparisons, audit


def run(snapshot: str, diagnostics_dir: Path, output_dir: Path) -> dict:
    trade_path = diagnostics_dir / "trade_features.csv"
    if not trade_path.exists():
        run_diagnostics(snapshot, diagnostics_dir)
    trades = pd.read_csv(trade_path, index_col=0)
    comparisons, audit = evaluate(trades)
    output_dir.mkdir(parents=True, exist_ok=True)
    comparisons.to_csv(output_dir / "comparison.csv", index=False)
    audit.to_csv(output_dir / "entry_audit.csv", index=True)

    overall = comparisons.iloc[0].to_dict()
    acceptance = {
        "expectancy_improved": bool(overall["candidate_expectancy"] > overall["baseline_expectancy"]),
        "profit_factor_improved": bool(overall["candidate_profit_factor"] > overall["baseline_profit_factor"]),
        "average_loss_improved": bool(overall["candidate_avg_loss"] > overall["baseline_avg_loss"]),
        "trade_retention_at_least_70_pct": bool(overall["trade_retention_pct"] >= 70),
        "positive_pnl_retention_at_least_70_pct": bool(overall["positive_pnl_retention_pct"] >= 70),
        "out_of_sample_validated": False,
    }
    acceptance["development_criteria_passed"] = all(
        value for key, value in acceptance.items() if key != "out_of_sample_validated"
    )
    report = {
        "experiment_id": EXPERIMENT_ID,
        "snapshot": snapshot,
        "rule": "allow entry when ATR(14) / mean(ATR(14), 20) <= 1.0",
        "threshold_scanned": False,
        "baseline_rules_modified": False,
        "development_only": True,
        "overall": overall,
        "acceptance": acceptance,
    }
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-registered ATR contraction experiment")
    parser.add_argument("--snapshot", default="btcusdt_4h_2026_08")
    parser.add_argument("--diagnostics-dir", type=Path,
                        default=Path("research/output/btcusdt_4h_2026_08"))
    parser.add_argument("--output-dir", type=Path,
                        default=Path("research/output/atr_contraction_experiment"))
    args = parser.parse_args()
    report = run(args.snapshot, args.diagnostics_dir, args.output_dir)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
