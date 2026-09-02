import pandas as pd


REQUIRED_OHLC_COLUMNS = ("open", "high", "low", "close")


def add_heikin_ashi(candles):
    """Add Heikin Ashi columns without replacing executable market prices."""
    if candles.empty:
        return candles.copy()

    missing = set(REQUIRED_OHLC_COLUMNS) - set(candles.columns)
    if missing:
        raise ValueError(f"Missing OHLC columns: {sorted(missing)}")

    df = candles.copy()
    for column in REQUIRED_OHLC_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="raise").astype(float)

    df["ha_close"] = df[list(REQUIRED_OHLC_COLUMNS)].mean(axis=1)

    ha_open = [0.0] * len(df)
    ha_open[0] = (df["open"].iloc[0] + df["close"].iloc[0]) / 2.0
    for i in range(1, len(df)):
        ha_open[i] = (ha_open[i - 1] + df["ha_close"].iloc[i - 1]) / 2.0

    df["ha_open"] = ha_open
    df["ha_high"] = df[["high", "ha_open", "ha_close"]].max(axis=1)
    df["ha_low"] = df[["low", "ha_open", "ha_close"]].min(axis=1)
    return df
