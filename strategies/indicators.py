import numpy as np
import pandas as pd


def wilder_rma(series, length=14):
    """Wilder RMA with an SMA seed, without reading future observations."""
    source = pd.Series(series, copy=False, dtype="float64")
    result = pd.Series(np.nan, index=source.index, dtype="float64")
    if length <= 0:
        raise ValueError("length must be positive")
    valid = source.dropna()
    if len(valid) < length:
        return result
    seed_position = source.index.get_loc(valid.index[length - 1])
    seed = source.iloc[:seed_position + 1].dropna().iloc[-length:].mean()
    result.iloc[seed_position] = seed
    previous = seed
    for position in range(seed_position + 1, len(source)):
        current = source.iloc[position]
        if pd.isna(current):
            continue
        previous = (previous * (length - 1) + current) / length
        result.iloc[position] = previous
    return result


def calculate_ema(df, length, source_column="close", output_column=None):
    if length <= 0:
        raise ValueError("length must be positive")
    output_column = output_column or f"ema_{length}"
    df[output_column] = df[source_column].ewm(
        span=length, adjust=False, min_periods=length
    ).mean()
    return df


def calculate_disparity(df, length=20, source_column="close", output_column=None):
    """Percentage distance from a configurable simple moving average."""
    if length <= 0:
        raise ValueError("length must be positive")
    output_column = output_column or f"disparity_{length}"
    average = df[source_column].rolling(length).mean()
    df[output_column] = (df[source_column] / average - 1.0) * 100.0
    return df


def calculate_dmi_adx(df, length=14, prefix=""):
    """Standard causal DMI/ADX on real OHLC using Wilder smoothing."""
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=df.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=df.index,
    )
    plus_dm.iloc[0] = np.nan
    minus_dm.iloc[0] = np.nan
    true_range = calculate_true_range(df)
    true_range.iloc[0] = np.nan
    atr = wilder_rma(true_range, length)
    plus_di = 100.0 * wilder_rma(plus_dm, length) / atr
    minus_di = 100.0 * wilder_rma(minus_dm, length) / atr
    denominator = (plus_di + minus_di).replace(0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / denominator
    df[f"{prefix}plus_di"] = plus_di
    df[f"{prefix}minus_di"] = minus_di
    df[f"{prefix}dmi_atr"] = atr
    df[f"{prefix}dx"] = dx
    df[f"{prefix}adx"] = wilder_rma(dx, length)
    return df


def linreg(series, length):
    """
    Reproduction of TradingView's linreg(source, length, 0)
    for the Lazy Bear SQZMOM indicator.
    """

    values = []

    x = np.arange(length)

    for i in range(len(series)):

        if i < length - 1:
            values.append(np.nan)
            continue

        y = series.iloc[i - length + 1:i + 1]

        slope, intercept = np.polyfit(
            x,
            y,
            1
        )

        result = (
            slope * (length - 1)
            + intercept
        )

        values.append(result)

    return pd.Series(
        values,
        index=series.index
    )


def calculate_bollinger_bands(
    df,
    length=20,
    mult=2.0,
    close_column="close"
):
    """
    Calculate Bollinger Bands using the same
    parameters as the Lazy Bear TradingView script.
    """

    basis = (
        df[close_column]
        .rolling(length)
        .mean()
    )

    dev = (
        mult
        * df[close_column].rolling(length).std(ddof=0)
    )

    df["bb_basis"] = basis
    df["upper_bb"] = basis + dev
    df["lower_bb"] = basis - dev

    return df


def calculate_true_range(df, high_column="high", low_column="low", close_column="close"):
    """
    Calculate True Range.

    TradingView's TR:
        max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close)
        )
    """

    previous_close = df[close_column].shift(1)

    high_low = (
        df[high_column] - df[low_column]
    )

    high_previous_close = (
        df[high_column] - previous_close
    ).abs()

    low_previous_close = (
        df[low_column] - previous_close
    ).abs()

    true_range = pd.concat(
        [
            high_low,
            high_previous_close,
            low_previous_close
        ],
        axis=1
    ).max(axis=1)

    return true_range


def calculate_atr(
    df, length=14, high_column="high", low_column="low", close_column="close",
    output_column="atr",
):
    """TradingView-style ATR using Wilder's RMA on the selected candle source."""
    true_range = calculate_true_range(
        df, high_column=high_column, low_column=low_column,
        close_column=close_column,
    )
    df[output_column] = true_range.ewm(
        alpha=1 / length, adjust=False, min_periods=length
    ).mean()
    return df


def calculate_keltner_channels(
    df,
    length=20,
    mult=1.5,
    use_true_range=True,
    high_column="high",
    low_column="low",
    close_column="close"
):
    """
    Calculate Keltner Channels using the
    Lazy Bear TradingView parameters.
    """

    basis = (
        df[close_column]
        .rolling(length)
        .mean()
    )

    if use_true_range:
        price_range = calculate_true_range(
            df, high_column, low_column, close_column
        )

    else:
        price_range = (
            df[high_column] - df[low_column]
        )

    range_ma = (
        price_range
        .rolling(length)
        .mean()
    )

    df["kc_basis"] = basis

    df["upper_kc"] = (
        basis
        + range_ma * mult
    )

    df["lower_kc"] = (
        basis
        - range_ma * mult
    )

    return df


def calculate_squeeze_state(df):
    """
    Calculate Squeeze ON, Squeeze OFF and NO SQUEEZE.
    """

    df["sqz_on"] = (
        (df["lower_bb"] > df["lower_kc"]) &
        (df["upper_bb"] < df["upper_kc"])
    )

    df["sqz_off"] = (
        (df["lower_bb"] < df["lower_kc"]) &
        (df["upper_bb"] > df["upper_kc"])
    )

    df["no_sqz"] = (
        ~df["sqz_on"] &
        ~df["sqz_off"]
    )

    return df


def calculate_sqzmom(
    df,
    length=20,
    high_column="high",
    low_column="low",
    close_column="close"
):
    """
    Calculate the Lazy Bear SQZMOM momentum value.
    """

    highest = (
        df[high_column]
        .rolling(length)
        .max()
    )

    lowest = (
        df[low_column]
        .rolling(length)
        .min()
    )

    sma_close = (
        df[close_column]
        .rolling(length)
        .mean()
    )

    midpoint = (
        highest + lowest
    ) / 2

    average = (
        midpoint + sma_close
    ) / 2

    series = (
        df[close_column] - average
    )

    df["sqzmom"] = linreg(
        series,
        length
    )

    return df


def calculate_sqzmom_color(df):
    """
    Project SQZMOM color definitions.

    Dark green:
        val > 0 AND val > previous
        Positive momentum increasing.

    Light green:
        val > 0 AND val <= previous
        Positive momentum decreasing.

    Dark red:
        val < 0 AND val < previous
        Negative momentum becoming more negative.

    Light red:
        val < 0 AND val >= previous
        Negative momentum recovering toward zero.
    """

    current = df["sqzmom"]
    previous = current.shift(1)

    conditions = [

        # DARK GREEN
        (
            (current > 0)
            &
            (current > previous)
        ),

        # LIGHT GREEN
        (
            (current > 0)
            &
            (current <= previous)
        ),

        # DARK RED
        (
            (current < 0)
            &
            (current < previous)
        ),

        # LIGHT RED
        (
            (current < 0)
            &
            (current >= previous)
        )
    ]

    colors = [
        "dark_green",
        "light_green",
        "dark_red",
        "light_red"
    ]

    df["sqzmom_color"] = np.select(
        conditions,
        colors,
        default="neutral"
    )

    return df




def calculate_indicators(df, price_source="heikin_ashi"):
    """
    Calculate the complete Lazy Bear SQZMOM indicator.
    """

    if price_source == "heikin_ashi":
        columns = ("ha_high", "ha_low", "ha_close")
    elif price_source == "market":
        columns = ("high", "low", "close")
    else:
        raise ValueError("price_source must be 'heikin_ashi' or 'market'")

    missing = set(columns) - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns for {price_source}: {sorted(missing)}")

    high_column, low_column, close_column = columns

    df = calculate_atr(
        df, high_column=high_column, low_column=low_column,
        close_column=close_column,
    )

    df = calculate_bollinger_bands(df, close_column=close_column)

    df = calculate_keltner_channels(
        df,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
    )

    df = calculate_squeeze_state(df)

    df = calculate_sqzmom(
        df,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
    )

    df = calculate_sqzmom_color(df)

    return df
