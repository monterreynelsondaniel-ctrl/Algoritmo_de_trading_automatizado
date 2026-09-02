import pandas as pd
import numpy as np


def calculate_backtest_statistics(results):
    """
    Calculate performance statistics from completed backtest trades.

    Args:
        results: DataFrame returned by the backtest engine.

    Returns:
        dict containing overall, LONG, and SHORT statistics.
    """

    if results.empty:
        return {}

    # Only completed trades
    completed = results[
        results["result"].isin(["WIN", "LOSS"])
    ].copy()

    if completed.empty:
        return {}

    # --------------------------------
    # Overall statistics
    # --------------------------------

    total_trades = len(completed)

    wins = completed[
        completed["result"] == "WIN"
    ]

    losses = completed[
        completed["result"] == "LOSS"
    ]

    win_count = len(wins)
    loss_count = len(losses)

    win_rate = (
        win_count / total_trades
    ) * 100

    total_pnl = completed["pnl_pct"].sum()

    total_gross_pnl = (
        completed["pnl_bruto"].sum()
        if "pnl_bruto" in completed else total_pnl
    )
    total_fees = (
        completed["total_fees"].sum()
        if "total_fees" in completed else 0.0
    )
    total_slippage = (
        completed["slippage_cost"].sum()
        if "slippage_cost" in completed else 0.0
    )

    compounded_return = ((1 + completed["pnl_pct"] / 100).prod() - 1) * 100
    gross_profit = completed.loc[completed["pnl_pct"] > 0, "pnl_pct"].sum()
    gross_loss = abs(completed.loc[completed["pnl_pct"] < 0, "pnl_pct"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss else float("inf")

    returns = completed["pnl_pct"] / 100
    equity_curve = (1 + returns).cumprod()
    drawdown = equity_curve / equity_curve.cummax() - 1
    max_drawdown = abs(drawdown.min()) * 100
    sharpe_ratio = (
        np.sqrt(len(returns)) * returns.mean() / returns.std(ddof=1)
        if len(returns) > 1 and returns.std(ddof=1) > 0
        else 0.0
    )

    average_pnl = completed["pnl_pct"].mean()

    best_trade = completed["pnl_pct"].max()

    worst_trade = completed["pnl_pct"].min()

    average_favorable = (
        completed["max_favorable_pct"].mean()
    )

    average_adverse = (
        completed["max_adverse_pct"].mean()
    )

    average_duration = (
        completed["duration_hours"].mean()
    )

    # --------------------------------
    # LONG statistics
    # --------------------------------

    long_trades = completed[
        completed["signal"] == "LONG"
    ]

    long_wins = long_trades[
        long_trades["result"] == "WIN"
    ]

    long_win_rate = (
        len(long_wins) / len(long_trades) * 100
        if len(long_trades) > 0
        else 0
    )

    long_pnl = (
        long_trades["pnl_pct"].sum()
        if len(long_trades) > 0
        else 0
    )

    # --------------------------------
    # SHORT statistics
    # --------------------------------

    short_trades = completed[
        completed["signal"] == "SHORT"
    ]

    short_wins = short_trades[
        short_trades["result"] == "WIN"
    ]

    short_win_rate = (
        len(short_wins) / len(short_trades) * 100
        if len(short_trades) > 0
        else 0
    )

    short_pnl = (
        short_trades["pnl_pct"].sum()
        if len(short_trades) > 0
        else 0
    )

    # --------------------------------
    # Return statistics
    # --------------------------------

    return {
        "total_trades": total_trades,

        "wins": win_count,
        "losses": loss_count,
        "win_rate": win_rate,

        "total_pnl": total_pnl,
        "total_gross_pnl": total_gross_pnl,
        "total_fees": total_fees,
        "total_slippage": total_slippage,
        "compounded_return": compounded_return,
        "profit_factor": profit_factor,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe_ratio,
        "average_pnl": average_pnl,

        "best_trade": best_trade,
        "worst_trade": worst_trade,

        "average_favorable": average_favorable,
        "average_adverse": average_adverse,

        "average_duration_hours": average_duration,

        "long_trades": len(long_trades),
        "long_win_rate": long_win_rate,
        "long_pnl": long_pnl,

        "short_trades": len(short_trades),
        "short_win_rate": short_win_rate,
        "short_pnl": short_pnl
    }


def calculate_monthly_statistics(results, target_win_rate=70.0):
    """Evaluate the initial 70/30 criterion by trade exit month (UTC)."""
    if results.empty:
        return pd.DataFrame()

    completed = results[
        results["result"].isin(["WIN", "LOSS", "BREAKEVEN"])
    ].copy()
    if completed.empty:
        return pd.DataFrame()

    completed["exit_time"] = pd.to_datetime(completed["exit_time"], utc=True)
    completed["month"] = completed["exit_time"].dt.strftime("%Y-%m")

    rows = []
    for month, trades in completed.groupby("month", sort=True):
        wins = int((trades["result"] == "WIN").sum())
        losses = int((trades["result"] == "LOSS").sum())
        breakeven = int((trades["result"] == "BREAKEVEN").sum())
        win_rate = wins / len(trades) * 100
        rows.append({
            "month": month,
            "trades": len(trades),
            "wins": wins,
            "losses": losses,
            "breakeven": breakeven,
            "win_rate": win_rate,
            "pnl_pct": trades["pnl_pct"].sum(),
            "meets_70_30": win_rate >= target_win_rate,
        })

    return pd.DataFrame(rows)


def print_backtest_statistics(statistics):
    """
    Print a readable backtest performance report.
    """

    if not statistics:
        print("\nNo completed trades available.")
        return

    print("\n=== BACKTEST STATISTICS ===\n")

    print(
        f"Total trades: "
        f"{statistics['total_trades']}"
    )

    print(
        f"Wins: "
        f"{statistics['wins']}"
    )

    print(
        f"Losses: "
        f"{statistics['losses']}"
    )

    print(
        f"Win rate: "
        f"{statistics['win_rate']:.2f}%"
    )

    print(
        f"Total P&L: "
        f"{statistics['total_pnl']:.2f}%"
    )

    print(
        f"Gross P&L: "
        f"{statistics['total_gross_pnl']:.2f}%"
    )

    print(
        f"Fees + funding: "
        f"{statistics['total_fees']:.2f}%"
    )

    print(
        f"Estimated slippage cost: "
        f"{statistics['total_slippage']:.2f}%"
    )

    print(
        f"Compounded return: "
        f"{statistics['compounded_return']:.2f}%"
    )

    print(
        f"Profit factor: "
        f"{statistics['profit_factor']:.2f}"
    )

    print(
        f"Max drawdown: "
        f"{statistics['max_drawdown']:.2f}%"
    )

    print(
        f"Per-trade Sharpe: "
        f"{statistics['sharpe_ratio']:.2f}"
    )

    print(
        f"Average P&L: "
        f"{statistics['average_pnl']:.2f}%"
    )

    print(
        f"Best trade: "
        f"{statistics['best_trade']:.2f}%"
    )

    print(
        f"Worst trade: "
        f"{statistics['worst_trade']:.2f}%"
    )

    print(
        f"Average favorable movement: "
        f"{statistics['average_favorable']:.2f}%"
    )

    print(
        f"Average adverse movement: "
        f"{statistics['average_adverse']:.2f}%"
    )

    print(
        f"Average duration: "
        f"{statistics['average_duration_hours']:.2f} hours"
    )

    print("\n--- LONG ---")

    print(
        f"Trades: "
        f"{statistics['long_trades']}"
    )

    print(
        f"Win rate: "
        f"{statistics['long_win_rate']:.2f}%"
    )

    print(
        f"Total P&L: "
        f"{statistics['long_pnl']:.2f}%"
    )

    print("\n--- SHORT ---")

    print(
        f"Trades: "
        f"{statistics['short_trades']}"
    )

    print(
        f"Win rate: "
        f"{statistics['short_win_rate']:.2f}%"
    )

    print(
        f"Total P&L: "
        f"{statistics['short_pnl']:.2f}%"
    )
