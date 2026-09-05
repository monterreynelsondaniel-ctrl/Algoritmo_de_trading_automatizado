"""Descriptive ATR dynamics study with fixed 1, 2 and 3 candle windows.

This module does not filter trades. ATR changes are known at signal close;
performance, MAE and large-loss labels are subsequent outcomes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from data.frozen_market_data import FrozenMarketDataStore


WINDOWS = (1, 2, 3)


def calculate_real_atr(candles: pd.DataFrame, length: int = 14) -> pd.Series:
    previous_close = candles["close"].shift(1)
    true_range = pd.concat([
        candles["high"] - candles["low"],
        (candles["high"] - previous_close).abs(),
        (candles["low"] - previous_close).abs(),
    ], axis=1).max(axis=1)
    return true_range.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()


def add_atr_dynamics(trades: pd.DataFrame, candles: pd.DataFrame) -> pd.DataFrame:
    """Attach point-in-time ATR changes at each trade's signal timestamp."""
    enriched = trades.copy()
    atr = calculate_real_atr(candles)
    by_time = pd.Series(atr.to_numpy(), index=pd.to_datetime(candles.open_time, utc=True))
    signal_times = pd.to_datetime(enriched.entry_signal_time, utc=True)
    current = by_time.reindex(signal_times).to_numpy()
    positions = pd.Series(np.arange(len(candles)), index=pd.to_datetime(candles.open_time, utc=True))
    signal_positions = positions.reindex(signal_times).astype(int).to_numpy()
    for window in WINDOWS:
        previous = atr.iloc[signal_positions - window].to_numpy()
        change = current / previous - 1
        enriched[f"atr_change_{window}"] = change
        enriched[f"atr_direction_{window}"] = np.select(
            [change > 0, change < 0], ["EXPANDING", "CONTRACTING"], default="UNCHANGED"
        )
        # Equal-frequency bands describe monotonicity; they are not candidate cutoffs.
        if len(enriched) >= 3:
            # Ranking makes ties deterministic and prevents duplicate qcut edges.
            ranked = enriched[f"atr_change_{window}"].rank(method="first")
            enriched[f"atr_rank_band_{window}"] = pd.qcut(
                ranked, 3, labels=["LOWER_THIRD", "MIDDLE_THIRD", "UPPER_THIRD"]
            ).astype(str)
        else:
            enriched[f"atr_rank_band_{window}"] = "UNAVAILABLE"
    return enriched


def _metrics(group: pd.DataFrame) -> dict:
    pnl = group.pnl_neto.astype(float)
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    return {
        "trades": len(group),
        "expectancy": pnl.mean(),
        "profit_factor": wins.sum() / abs(losses.sum()) if len(losses) else np.inf,
        "mean_mae": group.max_adverse_pct.mean(),
        "large_loss_rate": (pnl < -3).mean() * 100,
        "large_loss_count": int((pnl < -3).sum()),
        "worst_trade": pnl.min(),
        "median_pnl": pnl.median(),
    }


def summarize_groups(trades: pd.DataFrame, grouping: str) -> pd.DataFrame:
    rows = []
    for side in ("ALL", "LONG", "SHORT"):
        scoped = trades if side == "ALL" else trades[trades.signal == side]
        for value, group in scoped.groupby(grouping, sort=True):
            rows.append({"side": side, "grouping": grouping, "group": value, **_metrics(group)})
    return pd.DataFrame(rows)


def robustness(trades: pd.DataFrame) -> pd.DataFrame:
    """Compare expansion vs contraction after excluding zero, one or two worst trades."""
    rows = []
    midpoint = len(trades) // 2
    scopes = [("ALL", trades), ("LONG", trades[trades.signal == "LONG"]),
              ("SHORT", trades[trades.signal == "SHORT"]),
              ("FIRST_HALF", trades.iloc[:midpoint]), ("SECOND_HALF", trades.iloc[midpoint:])]
    for window in WINDOWS:
        direction = f"atr_direction_{window}"
        for scope, original in scopes:
            for removed in (0, 1, 2):
                sample = original.sort_values("pnl_neto").iloc[removed:]
                expanding = sample[sample[direction] == "EXPANDING"]
                contracting = sample[sample[direction] == "CONTRACTING"]
                if not len(expanding) or not len(contracting):
                    continue
                exp, con = _metrics(expanding), _metrics(contracting)
                rows.append({
                    "window": window, "scope": scope, "worst_trades_removed": removed,
                    "expanding_n": exp["trades"], "contracting_n": con["trades"],
                    "expectancy_difference_exp_minus_con": exp["expectancy"] - con["expectancy"],
                    "mae_difference_exp_minus_con": exp["mean_mae"] - con["mean_mae"],
                    "large_loss_rate_difference": exp["large_loss_rate"] - con["large_loss_rate"],
                    "expanding_profit_factor": exp["profit_factor"],
                    "contracting_profit_factor": con["profit_factor"],
                })
    return pd.DataFrame(rows)


def run(snapshot: str, diagnostics_dir: Path, output_dir: Path) -> dict:
    trades = pd.read_csv(diagnostics_dir / "trade_features.csv", index_col=0)
    candles = FrozenMarketDataStore().load(snapshot)
    enriched = add_atr_dynamics(trades, candles)
    summaries = []
    for window in WINDOWS:
        summaries.append(summarize_groups(enriched, f"atr_direction_{window}"))
        summaries.append(summarize_groups(enriched, f"atr_rank_band_{window}"))
    grouped = pd.concat(summaries, ignore_index=True)
    robust = robustness(enriched)
    output_dir.mkdir(parents=True, exist_ok=True)
    enriched.to_csv(output_dir / "trade_audit.csv", index=True)
    grouped.to_csv(output_dir / "grouped_metrics.csv", index=False)
    robust.to_csv(output_dir / "outlier_robustness.csv", index=False)

    core = robust[(robust.scope.isin(["LONG", "SHORT"])) & (robust.worst_trades_removed == 0)]
    robust_all = robust[(robust.scope == "ALL") & (robust.worst_trades_removed.isin([0, 1, 2]))]
    report = {
        "snapshot": snapshot,
        "windows": list(WINDOWS),
        "strategy_modified": False,
        "threshold_optimization": False,
        "development_only": True,
        "directional_checks": {
            "worse_expectancy_in_every_side_window": bool((core.expectancy_difference_exp_minus_con < 0).all()),
            "worse_mae_in_every_side_window": bool((core.mae_difference_exp_minus_con < 0).all()),
            "higher_large_loss_rate_in_every_side_window": bool((core.large_loss_rate_difference > 0).all()),
            "expectancy_effect_survives_removing_two_worst": bool(
                (robust_all.expectancy_difference_exp_minus_con < 0).all()
            ),
        },
    }
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Descriptive pre-signal ATR dynamics analysis")
    parser.add_argument("--snapshot", default="btcusdt_4h_2026_08")
    parser.add_argument("--diagnostics-dir", type=Path,
                        default=Path("research/output/btcusdt_4h_2026_08"))
    parser.add_argument("--output-dir", type=Path,
                        default=Path("research/output/atr_dynamics_analysis"))
    args = parser.parse_args()
    print(json.dumps(run(args.snapshot, args.diagnostics_dir, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
