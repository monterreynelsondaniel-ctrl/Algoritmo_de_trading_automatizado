import pandas as pd

from exchange.market_data import get_candles
from exchange.market_data import transform_candles


# ==========================================================
# SETTINGS
# ==========================================================

FETCH_SYMBOL = "BTCUSDT"

# TradingView syminfo.ticker
DISPLAY_SYMBOL = "BTCUSDT.P"

API_TIMEFRAME = "4h"
PINE_TIMEFRAME = "240"

LIMIT = 2200

TARGET_TIME_MS = 1779552000000

MAX_PINE_LOOKBACK = 1000


# ==========================================================
# HEIKIN ASHI
# ==========================================================

def calculate_heikin_ashi(candles):

    df = candles.copy()

    # Make sure OHLC columns are numeric floats
    for column in ["open", "high", "low", "close"]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        ).astype(float)

    # ------------------------------------------------------
    # HA CLOSE
    #
    # (open + high + low + close) / 4
    # ------------------------------------------------------

    df["ha_close"] = (
        df["open"]
        + df["high"]
        + df["low"]
        + df["close"]
    ) / 4.0

    # ------------------------------------------------------
    # HA OPEN
    #
    # First candle:
    # (open + close) / 2
    #
    # Following candles:
    # (previous HA open + previous HA close) / 2
    # ------------------------------------------------------

    ha_open = [0.0] * len(df)

    ha_open[0] = (
        df["open"].iloc[0]
        + df["close"].iloc[0]
    ) / 2.0

    for i in range(1, len(df)):

        ha_open[i] = (
            ha_open[i - 1]
            + df["ha_close"].iloc[i - 1]
        ) / 2.0

    df["ha_open"] = ha_open

    # ------------------------------------------------------
    # HA HIGH
    # ------------------------------------------------------

    df["ha_high"] = df[
        [
            "high",
            "ha_open",
            "ha_close"
        ]
    ].max(axis=1)

    # ------------------------------------------------------
    # HA LOW
    # ------------------------------------------------------

    df["ha_low"] = df[
        [
            "low",
            "ha_open",
            "ha_close"
        ]
    ].min(axis=1)

    return df


# ==========================================================
# FORMAT HELPERS
# ==========================================================

def format_time(timestamp):

    return timestamp.strftime(
        "%Y-%m-%d %H:%M"
    )


def pine_number(value):

    if pd.isna(value):
        return "NaN"

    value = float(value)

    if value.is_integer():
        return str(int(value))

    return str(value)


# ==========================================================
# MAIN
# ==========================================================

def main():

    # ======================================================
    # GET NORMAL MARKET DATA
    # ======================================================

    candles = get_candles(
        symbol=FETCH_SYMBOL,
        timeframe=API_TIMEFRAME,
        limit=LIMIT
    )

    candles = transform_candles(candles)

    # ======================================================
    # NORMALIZE TIMESTAMP
    # ======================================================

    candles["open_time"] = pd.to_datetime(
        candles["open_time"],
        utc=True
    )

    candles = (
        candles
        .sort_values("open_time")
        .reset_index(drop=True)
    )

    # ======================================================
    # CONVERT NORMAL CANDLES -> HEIKIN ASHI
    # ======================================================

    candles = calculate_heikin_ashi(
        candles
    )

    # ======================================================
    # TARGET
    # ======================================================

    target_time = pd.to_datetime(
        TARGET_TIME_MS,
        unit="ms",
        utc=True
    )

    # ======================================================
    # REPRODUCE:
    #
    # for i = 0 to 1000
    #     if time[i] == targetTime
    # ======================================================

    target_bar = None

    last_position = len(candles) - 1

    max_search = min(
        MAX_PINE_LOOKBACK,
        last_position
    )

    for i in range(max_search + 1):

        dataframe_position = (
            last_position - i
        )

        candle_time = (
            candles["open_time"]
            .iloc[dataframe_position]
        )

        candle_time_ms = (
            candle_time.value
            // 1_000_000
        )

        if candle_time_ms == TARGET_TIME_MS:

            target_bar = i
            break

    # ======================================================
    # OUTPUT
    # ======================================================

    output = ""

    output += "TIMESTAMP_DEBUG\n"

    output += (
        "Symbol="
        + DISPLAY_SYMBOL
        + "\n"
    )

    output += (
        "Timeframe="
        + PINE_TIMEFRAME
        + "\n"
    )

    output += (
        "Target timestamp="
        + str(TARGET_TIME_MS)
        + "\n"
    )

    output += (
        "Target="
        + format_time(target_time)
        + "\n"
    )

    output += (
        "Target Bar Index="
        + (
            "No encontrada"
            if target_bar is None
            else str(target_bar)
        )
        + "\n"
    )

    # ======================================================
    # TARGET BAR
    # ======================================================

    if target_bar is not None:

        target_position = (
            last_position
            - target_bar
        )

        target = candles.iloc[
            target_position
        ]

        output += "\nTARGET BAR DETAILS\n"

        output += (
            "Index: "
            + str(target_bar)
            + "\n"
        )

        output += (
            "Time: "
            + format_time(
                target["open_time"]
            )
            + "\n"
        )

        # IMPORTANT:
        # Pine is reading HA candles,
        # therefore use ha_* rather than normal OHLC.

        output += (
            "Open: "
            + pine_number(
                target["ha_open"]
            )
            + "\n"
        )

        output += (
            "High: "
            + pine_number(
                target["ha_high"]
            )
            + "\n"
        )

        output += (
            "Low: "
            + pine_number(
                target["ha_low"]
            )
            + "\n"
        )

        output += (
            "Close: "
            + pine_number(
                target["ha_close"]
            )
            + "\n"
        )

        # ==================================================
        # SURROUNDING BARS
        # ==================================================

        output += "\nSURROUNDING BARS\n"

        output += (
            "Index|Time|Open|Close\n"
        )

        for offset in range(-2, 3):

            pine_index = (
                target_bar
                + offset
            )

            dataframe_position = (
                last_position
                - pine_index
            )

            row = candles.iloc[
                dataframe_position
            ]

            output += (
                str(pine_index)
                + "|"
                + format_time(
                    row["open_time"]
                )
                + "|"
                + pine_number(
                    row["ha_open"]
                )
                + "|"
                + pine_number(
                    row["ha_close"]
                )
                + "\n"
            )

    output += "\nEND_TIMESTAMP_DEBUG"

    print(output)


if __name__ == "__main__":
    main()