from exchange.market_data import get_candles
from exchange.market_data import transform_candles

from strategies.candles import add_heikin_ashi
from strategies.indicators import calculate_indicators
from strategies.signals import detect_sqzmom_reversal


def main():
    candles = get_candles(symbol="BTCUSDT", timeframe="4h", limit=150)
    candles = add_heikin_ashi(transform_candles(candles))
    candles = calculate_indicators(candles)

    print("\n=== SQZMOM REVERSALS ===\n")
    for i in range(1, len(candles)):
        historical_df = candles.iloc[:i + 1]
        reversal = detect_sqzmom_reversal(historical_df)
        if reversal:
            timestamp = historical_df["open_time"].iloc[-1]
            previous = historical_df["sqzmom"].iloc[-2]
            current = historical_df["sqzmom"].iloc[-1]
            print(
                timestamp, "|", reversal,
                "| previous:", round(previous, 2),
                "| current:", round(current, 2)
            )


if __name__ == "__main__":
    main()
