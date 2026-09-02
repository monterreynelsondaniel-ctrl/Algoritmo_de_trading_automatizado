import argparse

import pandas as pd

from backtest.engine import run_signal_analysis
from backtest.statistics import (
    calculate_backtest_statistics,
    calculate_monthly_statistics,
    print_backtest_statistics,
)
from data.frozen_market_data import FrozenMarketDataStore
from exchange.market_data import get_candles
from strategies.candles import add_heikin_ashi
from strategies.indicators import calculate_indicators
from strategies.signals import detect_historical_reversals


def prepare_candles(candles):
    return calculate_indicators(add_heikin_ashi(candles))


def execute_backtest(candles, timeframe_hours=4, **engine_options):
    prepared = prepare_candles(candles)
    signals = detect_historical_reversals(prepared)
    return run_signal_analysis(
        prepared, signals, timeframe_hours=timeframe_hours, **engine_options
    )


def print_trade_details(results):
    """Print signal candles and next-candle executions in UTC."""
    print("\n=== TRADE DETAILS (UTC) ===\n")
    if results.empty:
        print("No trades available.")
        return

    def timestamp(value):
        if value is None or pd.isna(value):
            return "OPEN"
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M")

    for number, (_, trade) in enumerate(results.iterrows(), start=1):
        exit_price = (
            "OPEN" if pd.isna(trade.get("exit_price"))
            else f"{trade['exit_price']:.2f}"
        )
        pnl = (
            "OPEN" if pd.isna(trade.get("pnl_pct"))
            else f"{trade['pnl_pct']:+.2f}%"
        )
        sqzmom = trade.get("entry_signal_sqzmom")
        sqzmom_text = "N/A" if pd.isna(sqzmom) else f"{sqzmom:.2f}"
        print(
            f"#{number:03d} {trade['signal']:<5} {trade['result']:<4} | "
            f"signal entrada {timestamp(trade['entry_signal_time'])} "
            f"({trade.get('entry_signal_previous_color')} -> "
            f"{trade.get('entry_signal_current_color')}, SQZMOM={sqzmom_text})"
        )
        print(
            f"      entrada real {timestamp(trade['entry_time'])} "
            f"@ {trade['entry_price']:.2f} | "
            f"signal salida {timestamp(trade.get('exit_signal_time'))} | "
            f"salida real {timestamp(trade.get('exit_time'))} @ {exit_price} | "
            f"P&L {pnl}"
        )


def main():
    parser = argparse.ArgumentParser(description="Reproducible SQZMOM backtest")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--snapshot", help="Name of a frozen dataset")
    source.add_argument("--download", action="store_true", help="Fetch Binance REST data")
    parser.add_argument("--save-as", help="Freeze downloaded candles under this name")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--timeframe", default="4h")
    parser.add_argument("--timeframe-hours", type=float, default=4)
    parser.add_argument("--limit", type=int, default=2200)
    parser.add_argument("--commission-rate", type=float, default=0.0004)
    parser.add_argument("--slippage-rate", type=float, default=0.0005)
    parser.add_argument("--funding-rate", type=float, default=0.0001)
    parser.add_argument("--funding-interval-hours", type=float, default=8)
    parser.add_argument(
        "--summary-only", action="store_true",
        help="Hide individual entry and exit candles",
    )
    parser.add_argument(
        "--trades-csv", help="Optional path for the complete trade audit CSV"
    )
    args = parser.parse_args()

    store = FrozenMarketDataStore()
    if args.snapshot:
        candles = store.load(args.snapshot)
    else:
        candles = get_candles(args.symbol, args.timeframe, args.limit)
        if args.save_as:
            store.save(args.save_as, candles, metadata={
                "source": "binance_futures_rest",
                "symbol": args.symbol,
                "timeframe": args.timeframe,
                "closed_candles_only": True,
            })

    results = execute_backtest(
        candles,
        args.timeframe_hours,
        commission_rate=args.commission_rate,
        slippage_rate=args.slippage_rate,
        funding_rate=args.funding_rate,
        funding_interval_hours=args.funding_interval_hours,
    )
    print(
        "\nCost assumptions: "
        f"commission={args.commission_rate:.4%} per side, "
        f"slippage={args.slippage_rate:.4%} per execution, "
        f"funding={args.funding_rate:.4%} every "
        f"{args.funding_interval_hours:g}h (fixed estimate)"
    )
    print_backtest_statistics(calculate_backtest_statistics(results))

    if not args.summary_only:
        print_trade_details(results)

    if args.trades_csv:
        results.to_csv(args.trades_csv, index=False)
        print(f"\nTrade audit saved to: {args.trades_csv}")

    monthly = calculate_monthly_statistics(results)
    print("\n=== MONTHLY 70/30 CRITERION ===\n")
    if monthly.empty:
        print("No completed trades available.")
    else:
        print(monthly.to_string(index=False, formatters={
            "win_rate": "{:.2f}%".format,
            "pnl_pct": "{:.2f}%".format,
        }))


if __name__ == "__main__":
    main()
