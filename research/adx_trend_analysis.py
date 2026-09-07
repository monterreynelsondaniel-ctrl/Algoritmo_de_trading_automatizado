"""Exploratory DMI/ADX context analysis for the frozen SQZMOM baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from backtest.run import execute_backtest
from backtest.statistics import calculate_backtest_statistics
from data.frozen_market_data import FrozenMarketDataStore
from strategies.indicators import calculate_dmi_adx as add_dmi_adx
from strategies.indicators import wilder_rma


ADX_LENGTH = 14
BANDS = ("LOW", "MID", "HIGH")


def calculate_dmi_adx(candles: pd.DataFrame, length: int = ADX_LENGTH) -> pd.DataFrame:
    """Compatibility wrapper around the shared mathematical implementation."""
    enriched = add_dmi_adx(candles.copy(), length)
    return enriched[["dmi_atr", "plus_di", "minus_di", "dx", "adx"]]


def classify_alignment(side: str, plus_di: float, minus_di: float) -> str:
    if np.isclose(plus_di, minus_di, rtol=0, atol=1e-12):
        return "NEUTRAL"
    bullish = plus_di > minus_di
    return "ALIGNED" if ((side == "LONG" and bullish) or (side == "SHORT" and not bullish)) else "COUNTER"


def enrich_trades(trades: pd.DataFrame, candles: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    enriched = trades.copy()
    dmi = calculate_dmi_adx(candles)
    candle_times = pd.to_datetime(candles.open_time, utc=True)
    signal_times = pd.to_datetime(enriched.entry_signal_time, utc=True)
    position_by_time = pd.Series(np.arange(len(candles)), index=candle_times)
    positions = position_by_time.reindex(signal_times).astype(int).to_numpy()
    for column in ("plus_di", "minus_di", "dx", "adx"):
        enriched[column] = dmi[column].iloc[positions].to_numpy()
    previous_adx = dmi.adx.iloc[positions - 1].to_numpy()
    enriched["adx_change_1"] = enriched.adx.to_numpy() / previous_adx - 1
    enriched["adx_direction"] = np.select(
        [enriched.adx_change_1 > 0, enriched.adx_change_1 < 0],
        ["RISING", "FALLING"], default="UNCHANGED",
    )
    enriched["alignment"] = [
        classify_alignment(side, plus, minus)
        for side, plus, minus in zip(enriched.signal, enriched.plus_di, enriched.minus_di)
    ]
    # Global equal-frequency bands keep the same descriptive ADX scale for both sides.
    ranked = enriched.adx.rank(method="first")
    if len(enriched) >= 3:
        enriched["adx_band"] = pd.qcut(ranked, 3, labels=BANDS).astype(str)
    else:
        enriched["adx_band"] = "UNAVAILABLE"
    quantiles = enriched.adx.quantile([1 / 3, 2 / 3]).to_dict()
    enriched["trend_adx_group"] = enriched.alignment + "_" + enriched.adx_band
    enriched["trend_adx_direction"] = enriched.alignment + "_" + enriched.adx_direction
    enriched["large_loss_3"] = enriched.pnl_neto < -3
    enriched["large_loss_5"] = enriched.pnl_neto < -5
    enriched["large_win_3"] = enriched.pnl_neto > 3
    enriched["large_win_5"] = enriched.pnl_neto > 5
    return enriched, {"lower_upper_bound": quantiles[1 / 3], "middle_upper_bound": quantiles[2 / 3]}


def metrics(group: pd.DataFrame) -> dict:
    pnl = group.pnl_neto.astype(float)
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    return {
        "n": len(group), "win_rate": (pnl > 0).mean() * 100,
        "expectancy": pnl.mean(), "profit_factor": wins.sum() / abs(losses.sum()) if len(losses) else np.inf,
        "average_pnl": pnl.mean(), "median_pnl": pnl.median(),
        "average_win": wins.mean(), "average_loss": losses.mean(),
        "payoff_ratio": wins.mean() / abs(losses.mean()) if len(losses) else np.inf,
        "mean_mfe": group.max_favorable_pct.mean(), "mean_mae": group.max_adverse_pct.mean(),
        "loss_lt_3_rate": (pnl < -3).mean() * 100, "loss_lt_5_rate": (pnl < -5).mean() * 100,
        "best_trade": pnl.max(), "worst_trade": pnl.min(), "mean_duration_hours": group.duration_hours.mean(),
    }


def grouped_metrics(trades: pd.DataFrame) -> pd.DataFrame:
    rows = []
    dimensions = ("alignment", "adx_band", "trend_adx_group", "trend_adx_direction")
    for side in ("ALL", "LONG", "SHORT"):
        scoped = trades if side == "ALL" else trades[trades.signal == side]
        for dimension in dimensions:
            for value, group in scoped.groupby(dimension, sort=True):
                rows.append({"side": side, "dimension": dimension, "group": value, **metrics(group)})
    return pd.DataFrame(rows)


def _contrast(sample: pd.DataFrame, label: str, mask_a: pd.Series, mask_b: pd.Series) -> dict:
    a, b = sample[mask_a], sample[mask_b]
    ma, mb = metrics(a), metrics(b)
    return {
        "comparison": label, "group_a_n": ma["n"], "group_b_n": mb["n"],
        "expectancy_a_minus_b": ma["expectancy"] - mb["expectancy"],
        "mae_a_minus_b": ma["mean_mae"] - mb["mean_mae"],
        "loss3_rate_a_minus_b": ma["loss_lt_3_rate"] - mb["loss_lt_3_rate"],
        "profit_factor_a": ma["profit_factor"], "profit_factor_b": mb["profit_factor"],
    }


def outlier_robustness(trades: pd.DataFrame) -> pd.DataFrame:
    rows = []
    variants = (("ALL_TRADES", 0, False), ("REMOVE_WORST_1", 1, False),
                ("REMOVE_WORST_2", 2, False), ("REMOVE_BEST_AND_WORST", 1, True))
    for side in ("ALL", "LONG", "SHORT"):
        original = trades if side == "ALL" else trades[trades.signal == side]
        for variant, remove_worst, remove_best in variants:
            sample = original.sort_values("pnl_neto").iloc[remove_worst:]
            if remove_best:
                sample = sample.iloc[:-1]
            comparisons = [
                _contrast(sample, "COUNTER_MINUS_ALIGNED", sample.alignment == "COUNTER", sample.alignment == "ALIGNED"),
                _contrast(sample, "COUNTER_HIGH_MINUS_OTHERS",
                          (sample.alignment == "COUNTER") & (sample.adx_band == "HIGH"),
                          ~((sample.alignment == "COUNTER") & (sample.adx_band == "HIGH"))),
                _contrast(sample, "COUNTER_RISING_MINUS_OTHERS",
                          (sample.alignment == "COUNTER") & (sample.adx_direction == "RISING"),
                          ~((sample.alignment == "COUNTER") & (sample.adx_direction == "RISING"))),
            ]
            rows.extend({"side": side, "variant": variant, **comparison} for comparison in comparisons)
    return pd.DataFrame(rows)


def temporal_stability(trades: pd.DataFrame) -> pd.DataFrame:
    rows = []
    midpoint = len(trades) // 2
    for period, period_data in (("FIRST_HALF", trades.iloc[:midpoint]), ("SECOND_HALF", trades.iloc[midpoint:])):
        for side in ("ALL", "LONG", "SHORT"):
            sample = period_data if side == "ALL" else period_data[period_data.signal == side]
            comparisons = [
                _contrast(sample, "COUNTER_MINUS_ALIGNED", sample.alignment == "COUNTER", sample.alignment == "ALIGNED"),
                _contrast(sample, "COUNTER_HIGH_MINUS_OTHERS",
                          (sample.alignment == "COUNTER") & (sample.adx_band == "HIGH"),
                          ~((sample.alignment == "COUNTER") & (sample.adx_band == "HIGH"))),
                _contrast(sample, "COUNTER_RISING_MINUS_OTHERS",
                          (sample.alignment == "COUNTER") & (sample.adx_direction == "RISING"),
                          ~((sample.alignment == "COUNTER") & (sample.adx_direction == "RISING"))),
            ]
            rows.extend({"period": period, "side": side, **comparison} for comparison in comparisons)
    return pd.DataFrame(rows)


def event_summary(trades: pd.DataFrame) -> pd.DataFrame:
    rows = []
    definitions = {"LOSS_LT_3": trades.pnl_neto < -3, "LOSS_LT_5": trades.pnl_neto < -5,
                   "WIN_GT_3": trades.pnl_neto > 3, "WIN_GT_5": trades.pnl_neto > 5}
    groups = {
        "ALIGNED": trades.alignment == "ALIGNED", "COUNTER": trades.alignment == "COUNTER",
        "COUNTER_HIGH": (trades.alignment == "COUNTER") & (trades.adx_band == "HIGH"),
        "COUNTER_RISING": (trades.alignment == "COUNTER") & (trades.adx_direction == "RISING"),
        "ADX_LOW": trades.adx_band == "LOW", "ADX_MID": trades.adx_band == "MID",
        "ADX_HIGH": trades.adx_band == "HIGH", "ADX_RISING": trades.adx_direction == "RISING",
        "ADX_FALLING": trades.adx_direction == "FALLING",
    }
    for event, event_mask in definitions.items():
        total_events = int(event_mask.sum())
        for group, group_mask in groups.items():
            overlap = int((event_mask & group_mask).sum())
            rows.append({"event": event, "event_n": total_events, "group": group,
                         "group_base_n": int(group_mask.sum()),
                         "group_base_rate": group_mask.mean() * 100,
                         "event_share_in_group": overlap / total_events * 100 if total_events else 0,
                         "event_rate_within_group": overlap / group_mask.sum() * 100 if group_mask.sum() else 0})
    return pd.DataFrame(rows)


def run(snapshot: str, diagnostics_dir: Path, output_dir: Path) -> dict:
    candles = FrozenMarketDataStore().load(snapshot)
    results = execute_backtest(candles)
    stats = calculate_backtest_statistics(results)
    trades = pd.read_csv(diagnostics_dir / "trade_features.csv", index_col=0)
    enriched, boundaries = enrich_trades(trades, candles)
    grouped = grouped_metrics(enriched)
    outliers = outlier_robustness(enriched)
    temporal = temporal_stability(enriched)
    events = event_summary(enriched)
    output_dir.mkdir(parents=True, exist_ok=True)
    enriched.to_csv(output_dir / "trade_audit.csv", index=True)
    grouped.to_csv(output_dir / "grouped_metrics.csv", index=False)
    outliers.to_csv(output_dir / "outlier_robustness.csv", index=False)
    temporal.to_csv(output_dir / "temporal_stability.csv", index=False)
    events.to_csv(output_dir / "event_concentration.csv", index=False)
    report = {
        "experiment": "003_dmi_adx_trend_strength", "classification": "EXPLORATORY_IN_SAMPLE",
        "snapshot": snapshot, "strategy_modified": False, "adx_length": ADX_LENGTH,
        "adx_band_boundaries_descriptive_only": boundaries,
        "neutral_alignment_count": int((enriched.alignment == "NEUTRAL").sum()),
        "unchanged_adx_count": int((enriched.adx_direction == "UNCHANGED").sum()),
        "methodological_conclusion": (
            "C: general hypothesis rejected; SHORT DMI alignment retained for future research"
        ),
        "next_experiment_not_implemented": (
            "On a non-overlapping snapshot, allow new SHORT entries only when minus_di > plus_di; "
            "keep all exits unchanged and do not combine with ADX strength or ATR"
        ),
        "baseline": {key: stats[key] for key in (
            "total_trades", "win_rate", "total_pnl", "compounded_return", "profit_factor",
            "long_pnl", "short_pnl")},
    }
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Exploratory DMI/ADX trend analysis")
    parser.add_argument("--snapshot", default="btcusdt_4h_2026_08")
    parser.add_argument("--diagnostics-dir", type=Path,
                        default=Path("research/output/btcusdt_4h_2026_08"))
    parser.add_argument("--output-dir", type=Path,
                        default=Path("research/output/adx_trend_analysis"))
    args = parser.parse_args()
    print(json.dumps(run(args.snapshot, args.diagnostics_dir, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
