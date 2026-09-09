import pandas as pd

from binance.client import Client


CANDLE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_asset_volume", "number_of_trades", "taker_buy_base",
    "taker_buy_quote", "ignore"
]

REQUIRED_CANDLE_COLUMNS = (
    "open_time", "open", "high", "low", "close", "volume", "close_time"
)


def _timestamp_ms(value):
    if value is None:
        return None
    timestamp = pd.Timestamp(value)
    timestamp = timestamp.tz_localize("UTC") if timestamp.tz is None else timestamp.tz_convert("UTC")
    return int(timestamp.timestamp() * 1000)


def get_candles(
    symbol, timeframe, limit, client=None, closed_only=True,
    start_time=None, end_time=None,
):
    """Fetch chronological futures candles from Binance's REST API."""

    if limit <= 0:
        raise ValueError("limit must be greater than zero")

    api_client = client or Client()

    all_candles = []

    max_per_request = 1500

    remaining = limit

    start_ms = _timestamp_ms(start_time)
    requested_end_ms = _timestamp_ms(end_time)
    if start_ms is not None and requested_end_ms is not None and start_ms > requested_end_ms:
        raise ValueError("start_time must not be after end_time")
    cursor_end_time = requested_end_ms

    while remaining > 0:

        batch_size = min(remaining, max_per_request)

        params = {
            "symbol": symbol,
            "interval": timeframe,
            "limit": batch_size
        }

        if cursor_end_time is not None:
            params["endTime"] = cursor_end_time

        candles = api_client.futures_klines(**params)

        if not candles:
            break

        all_candles = candles + all_candles

        remaining -= len(candles)

        # Move backwards in time
        cursor_end_time = candles[0][0] - 1

        # If Binance returned fewer candles than requested,
        # there may be no more historical data available.
        if len(candles) < batch_size:
            break

    df = pd.DataFrame(
        all_candles,
        columns=CANDLE_COLUMNS
    )

    # Remove possible duplicates
    df = df.drop_duplicates(subset="open_time")

    # Make sure candles are chronological
    df = df.sort_values("open_time").reset_index(drop=True)

    df = transform_candles(df)

    if start_ms is not None:
        start_timestamp = pd.to_datetime(start_ms, unit="ms", utc=True)
        df = df[df["open_time"] >= start_timestamp]
    if requested_end_ms is not None:
        end_timestamp = pd.to_datetime(requested_end_ms, unit="ms", utc=True)
        df = df[df["close_time"] <= end_timestamp]

    if closed_only and not df.empty:
        now = pd.Timestamp.now(tz="UTC")
        df = df[df["close_time"] < now].reset_index(drop=True)

    return df.reset_index(drop=True)


def transform_candles(df):

    numeric_columns = [
        
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time"
    ]

    for column in numeric_columns:

        df[column] = df[column].astype(float)

    for column in ("open_time", "close_time"):
        if pd.api.types.is_numeric_dtype(df[column]):
            df[column] = pd.to_datetime(df[column], unit="ms", utc=True)
        else:
            df[column] = pd.to_datetime(df[column], utc=True)

    return df
