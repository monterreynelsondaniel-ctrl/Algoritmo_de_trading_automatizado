"""Exploratory diagnostics for the frozen SQZMOM baseline.

Entry features are built exclusively from candles available at the signal close.
Trade path and outcome columns use later candles and are labelled as outcomes.
Nothing in this module changes strategy or backtest execution rules.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from backtest.run import execute_backtest, prepare_candles
from data.frozen_market_data import FrozenMarketDataStore


HORIZONS = (1, 2, 3, 6, 12, 18)
FEATURE_COLUMNS = (
    "sqzmom_abs_pct_price", "sqzmom_delta_pct_price",
    "sqzmom_accel_pct_price", "sqzmom_slope3_pct_price",
    "sqzmom_slope6_pct_price", "reversal_retracement",
    "prior_impulse_bars", "prior_impulse_amplitude_pct_price",
    "return_3", "return_6", "return_12", "return_24",
    "distance_sma20", "distance_sma50", "sma20_slope5",
    "range_position20", "range_position50", "atr_pct",
    "realized_vol12", "realized_vol24", "range_pct",
    "atr_expansion", "bars_since_release", "squeeze_on_last6",
)


def _slope(values: pd.Series, length: int) -> float:
    clean = values.iloc[-length:].dropna()
    if len(clean) != length:
        return np.nan
    return float(np.polyfit(np.arange(length), clean.to_numpy(), 1)[0])


def _prior_impulse(momentum: pd.Series, side: str) -> tuple[int, float]:
    """Count the monotonic impulse ending one bar before the reversal."""
    values = momentum.dropna().to_numpy()
    if len(values) < 3:
        return 0, np.nan
    count = 0
    for cursor in range(len(values) - 2, 0, -1):
        delta = values[cursor] - values[cursor - 1]
        continues = delta > 0 if side == "SHORT" else delta < 0
        if not continues:
            break
        count += 1
    start = max(0, len(values) - 2 - count)
    return count, float(abs(values[-2] - values[start]))


def _squeeze_state(row: pd.Series) -> str:
    if bool(row["sqz_on"]):
        return "ON"
    if bool(row["sqz_off"]):
        return "OFF"
    return "NONE"


def entry_features(prepared: pd.DataFrame, signal_position: int, side: str) -> dict:
    """Return point-in-time features, using rows <= ``signal_position`` only."""
    history = prepared.iloc[: signal_position + 1]
    row = history.iloc[-1]
    mom = history["sqzmom"]
    close = float(row["close"])
    current, previous = float(mom.iloc[-1]), float(mom.iloc[-2])
    prior_delta = float(mom.iloc[-2] - mom.iloc[-3])
    delta = current - previous
    window = mom.iloc[-20:]
    recent_extreme = float(window.max() if side == "SHORT" else window.min())
    denominator = abs(recent_extreme)
    retracement = (
        (recent_extreme - current) / denominator if side == "SHORT"
        else (current - recent_extreme) / denominator
    ) if denominator else np.nan
    impulse_bars, impulse_amplitude = _prior_impulse(mom, side)

    real_close = history["close"]
    sma20 = real_close.rolling(20).mean()
    sma50 = real_close.rolling(50).mean()
    high20, low20 = history["high"].rolling(20).max(), history["low"].rolling(20).min()
    high50, low50 = history["high"].rolling(50).max(), history["low"].rolling(50).min()
    returns = real_close.pct_change()
    tr = pd.concat([
        history["high"] - history["low"],
        (history["high"] - real_close.shift()).abs(),
        (history["low"] - real_close.shift()).abs(),
    ], axis=1).max(axis=1)
    real_atr = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()

    previous_sqz_on = history["sqz_on"].shift(1, fill_value=False).astype(bool)
    releases = previous_sqz_on & history["sqz_off"].astype(bool)
    release_positions = np.flatnonzero(releases.to_numpy())
    bars_since_release = (
        signal_position - int(release_positions[-1]) if len(release_positions) else np.nan
    )
    trend_score = (float(sma20.iloc[-1]) - float(sma50.iloc[-1])) / close
    regime = "UP" if trend_score > 0 and sma20.iloc[-1] > sma20.iloc[-6] else (
        "DOWN" if trend_score < 0 and sma20.iloc[-1] < sma20.iloc[-6] else "RANGE"
    )

    def range_position(high: float, low: float) -> float:
        return (close - low) / (high - low) if high > low else np.nan

    features = {
        "sqzmom": current,
        "sqzmom_abs_pct_price": abs(current) / close * 100,
        "sqzmom_delta": delta,
        "sqzmom_delta_pct_price": delta / close * 100,
        "sqzmom_acceleration": delta - prior_delta,
        "sqzmom_accel_pct_price": (delta - prior_delta) / close * 100,
        "sqzmom_slope3_pct_price": _slope(mom, 3) / close * 100,
        "sqzmom_slope6_pct_price": _slope(mom, 6) / close * 100,
        "sqzmom_recent_extreme": recent_extreme,
        "reversal_retracement": retracement,
        "prior_impulse_bars": impulse_bars,
        "prior_impulse_amplitude_pct_price": impulse_amplitude / close * 100,
        "return_3": close / float(real_close.iloc[-4]) - 1,
        "return_6": close / float(real_close.iloc[-7]) - 1,
        "return_12": close / float(real_close.iloc[-13]) - 1,
        "return_24": close / float(real_close.iloc[-25]) - 1,
        "distance_sma20": close / float(sma20.iloc[-1]) - 1,
        "distance_sma50": close / float(sma50.iloc[-1]) - 1,
        "sma20_slope5": float(sma20.iloc[-1] / sma20.iloc[-6] - 1),
        "range_position20": range_position(float(high20.iloc[-1]), float(low20.iloc[-1])),
        "range_position50": range_position(float(high50.iloc[-1]), float(low50.iloc[-1])),
        "atr_pct": float(real_atr.iloc[-1]) / close * 100,
        "ha_atr_pct": float(row["atr"]) / close * 100,
        "range_pct": float(row["high"] - row["low"]) / close * 100,
        "realized_vol12": float(returns.iloc[-12:].std(ddof=1) * np.sqrt(12) * 100),
        "realized_vol24": float(returns.iloc[-24:].std(ddof=1) * np.sqrt(24) * 100),
        "atr_expansion": float(real_atr.iloc[-1] / real_atr.iloc[-20:].mean()),
        "squeeze_state": _squeeze_state(row),
        "previous_squeeze_state": _squeeze_state(history.iloc[-2]),
        "bars_since_release": bars_since_release,
        "squeeze_on_last6": int(history["sqz_on"].iloc[-6:].sum()),
        "trend_regime": regime,
        "with_trend": (side == "LONG" and regime == "UP") or (side == "SHORT" and regime == "DOWN"),
    }
    return features


def build_trade_dataset(prepared: pd.DataFrame, results: pd.DataFrame) -> pd.DataFrame:
    completed = results[results["result"].isin(["WIN", "LOSS"])].copy().reset_index(drop=True)
    time_to_position = {timestamp: pos for pos, timestamp in enumerate(prepared["open_time"])}
    feature_rows = []
    for trade_id, trade in completed.iterrows():
        signal_pos = time_to_position[pd.Timestamp(trade["entry_signal_time"])]
        entry_pos = time_to_position[pd.Timestamp(trade["entry_time"])]
        exit_pos = time_to_position[pd.Timestamp(trade["exit_time"])]
        row = entry_features(prepared, signal_pos, trade["signal"])
        row["trade_id"] = trade_id + 1
        row["exit_month"] = pd.Timestamp(trade["exit_time"]).strftime("%Y-%m")
        row["entry_month"] = pd.Timestamp(trade["entry_time"]).strftime("%Y-%m")

        path = prepared.iloc[entry_pos:exit_pos]
        directional_close = (path["close"] / trade["entry_price"] - 1) * 100
        if trade["signal"] == "SHORT":
            directional_close *= -1
        for horizon in HORIZONS:
            row[f"outcome_return_{horizon}bar"] = (
                float(directional_close.iloc[horizon - 1]) if len(path) >= horizon else np.nan
            )
        row["outcome_mfe_to_net_giveback"] = trade["max_favorable_pct"] - trade["pnl_neto"]
        feature_rows.append(row)

    features = pd.DataFrame(feature_rows).set_index("trade_id")
    completed.index = np.arange(1, len(completed) + 1)
    completed.index.name = "trade_id"
    return completed.join(features)


def performance_summary(trades: pd.DataFrame) -> dict:
    pnl = trades["pnl_neto"].astype(float)
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    gross_profit, gross_loss = wins.sum(), abs(losses.sum())
    return {
        "trades": int(len(trades)), "wins": int((pnl > 0).sum()),
        "losses": int((pnl < 0).sum()), "win_rate": float((pnl > 0).mean() * 100),
        "expectancy": float(pnl.mean()), "sum_net": float(pnl.sum()),
        "sum_gross": float(trades["pnl_bruto"].sum()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else None,
        "mean": float(pnl.mean()), "median": float(pnl.median()),
        "std": float(pnl.std(ddof=1)), "skew": float(pnl.skew()),
        "p05": float(pnl.quantile(.05)), "p25": float(pnl.quantile(.25)),
        "p75": float(pnl.quantile(.75)), "p95": float(pnl.quantile(.95)),
        "best": float(pnl.max()), "worst": float(pnl.min()),
        "avg_win": float(wins.mean()), "avg_loss": float(losses.mean()),
        "payoff_ratio": float(wins.mean() / abs(losses.mean())) if len(losses) else None,
        "mfe_mean": float(trades["max_favorable_pct"].mean()),
        "mae_mean": float(trades["max_adverse_pct"].mean()),
        "duration_mean_h": float(trades["duration_hours"].mean()),
        "duration_median_h": float(trades["duration_hours"].median()),
    }


def feature_comparison(trades: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scope, scoped in [("ALL", trades), ("LONG", trades[trades.signal == "LONG"]),
                          ("SHORT", trades[trades.signal == "SHORT"])]:
        for feature in FEATURE_COLUMNS:
            winners = scoped.loc[scoped.pnl_neto > 0, feature].dropna().astype(float)
            losers = scoped.loc[scoped.pnl_neto < 0, feature].dropna().astype(float)
            if min(len(winners), len(losers)) < 2:
                continue
            pooled = np.sqrt((winners.var(ddof=1) + losers.var(ddof=1)) / 2)
            effect = (winners.mean() - losers.mean()) / pooled if pooled else 0.0
            pairs = (winners.to_numpy()[:, None] > losers.to_numpy()).mean()
            ties = (winners.to_numpy()[:, None] == losers.to_numpy()).mean()
            auc = pairs + .5 * ties
            midpoint = len(scoped) // 2
            half_diffs = []
            for half in (scoped.iloc[:midpoint], scoped.iloc[midpoint:]):
                half_diffs.append(half.loc[half.pnl_neto > 0, feature].mean() -
                                  half.loc[half.pnl_neto < 0, feature].mean())
            rows.append({
                "scope": scope, "feature": feature,
                "winner_mean": winners.mean(), "loser_mean": losers.mean(),
                "standardized_difference": effect, "winner_higher_auc": auc,
                "first_half_difference": half_diffs[0], "second_half_difference": half_diffs[1],
                "direction_stable_halves": bool(np.sign(half_diffs[0]) == np.sign(half_diffs[1])),
            })
    return pd.DataFrame(rows)


def grouped_summary(trades: pd.DataFrame, column: str) -> pd.DataFrame:
    rows = []
    for value, group in trades.groupby(column, observed=True, sort=True):
        row = {column: str(value), **performance_summary(group)}
        rows.append(row)
    return pd.DataFrame(rows)


def fragility(trades: pd.DataFrame) -> pd.DataFrame:
    pnl = trades["pnl_neto"].sort_values()
    cases = {"all": pnl, "without_best_1": pnl.iloc[:-1], "without_worst_1": pnl.iloc[1:],
             "without_best_3": pnl.iloc[:-3], "without_worst_3": pnl.iloc[3:],
             "without_best_5": pnl.iloc[:-5], "without_worst_5": pnl.iloc[5:]}
    return pd.DataFrame([{"case": name, "trades": len(values), "sum_net": values.sum(),
                          "mean_net": values.mean()} for name, values in cases.items()])


def run(snapshot: str, output_dir: Path) -> dict:
    candles = FrozenMarketDataStore().load(snapshot)
    prepared = prepare_candles(candles)
    results = execute_backtest(candles)
    trades = build_trade_dataset(prepared, results)
    output_dir.mkdir(parents=True, exist_ok=True)

    trades["duration_bucket"] = pd.cut(
        trades.duration_hours, [-np.inf, 24, 48, 72, 120, np.inf],
        labels=["<24h", "24-48h", "48-72h", "3-5d", ">5d"], right=False,
    )
    median_vol = trades.atr_pct.median()
    trades["volatility_regime"] = np.where(trades.atr_pct >= median_vol, "HIGH", "LOW")

    summaries = {
        "ALL": performance_summary(trades),
        "LONG": performance_summary(trades[trades.signal == "LONG"]),
        "SHORT": performance_summary(trades[trades.signal == "SHORT"]),
    }
    threshold_rows = []
    for label, mask in {
        "loss_lt_-3": trades.pnl_neto < -3, "loss_lt_-5": trades.pnl_neto < -5,
        "loss_lt_-10": trades.pnl_neto < -10, "win_gt_3": trades.pnl_neto > 3,
        "win_gt_5": trades.pnl_neto > 5, "win_gt_10": trades.pnl_neto > 10,
    }.items():
        group = trades[mask]
        threshold_rows.append({"group": label, **performance_summary(group)} if len(group)
                              else {"group": label, "trades": 0})

    trajectory = []
    for side in ("ALL", "LONG", "SHORT"):
        scoped = trades if side == "ALL" else trades[trades.signal == side]
        for outcome in ("ALL", "WIN", "LOSS"):
            sample = scoped if outcome == "ALL" else scoped[scoped.result == outcome]
            for horizon in HORIZONS:
                values = sample[f"outcome_return_{horizon}bar"].dropna()
                trajectory.append({"side": side, "outcome": outcome, "bars": horizon,
                                   "hours": horizon * 4, "n": len(values),
                                   "mean": values.mean(), "median": values.median(),
                                   "positive_pct": (values > 0).mean() * 100})

    frames = {
        "trade_features.csv": trades,
        "feature_comparison.csv": feature_comparison(trades),
        "threshold_groups.csv": pd.DataFrame(threshold_rows),
        "trajectory.csv": pd.DataFrame(trajectory),
        "duration_buckets.csv": grouped_summary(trades, "duration_bucket"),
        "trend_regimes.csv": grouped_summary(trades, "trend_regime"),
        "volatility_regimes.csv": grouped_summary(trades, "volatility_regime"),
        "squeeze_states.csv": grouped_summary(trades, "squeeze_state"),
        "monthly.csv": grouped_summary(trades, "exit_month"),
        "monthly_side.csv": grouped_summary(trades, "exit_month").iloc[0:0],
        "fragility.csv": fragility(trades),
    }
    monthly_side = []
    for (month, side), group in trades.groupby(["exit_month", "signal"]):
        monthly_side.append({"exit_month": month, "signal": side, **performance_summary(group)})
    frames["monthly_side.csv"] = pd.DataFrame(monthly_side)
    for filename, frame in frames.items():
        frame.to_csv(output_dir / filename, index=True if filename == "trade_features.csv" else False)

    report = {
        "snapshot": snapshot, "candles": len(candles),
        "first_candle": str(candles.open_time.iloc[0]), "last_candle": str(candles.open_time.iloc[-1]),
        "closed_trades": len(trades), "open_trades_excluded": int((results.result == "OPEN").sum()),
        "costs": {"commission_rate_each_side": .0004, "slippage_rate_each_execution": .0005,
                  "fixed_funding_rate_each_8h": .0001},
        "performance": summaries, "median_entry_atr_pct_for_regime": median_vol,
    }
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen-baseline strategy diagnostics")
    parser.add_argument("--snapshot", default="btcusdt_4h_2026_08")
    parser.add_argument("--output-dir", type=Path, default=Path("research/output/btcusdt_4h_2026_08"))
    args = parser.parse_args()
    report = run(args.snapshot, args.output_dir)
    print(json.dumps(report, indent=2))
    print(f"Artifacts written to {args.output_dir}")


if __name__ == "__main__":
    main()
