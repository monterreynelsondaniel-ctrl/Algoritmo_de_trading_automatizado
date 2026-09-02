def detect_sqzmom_reversal(df):

    if len(df) < 2:
        return None

    previous_color = df["sqzmom_color"].iloc[-2]
    current_color = df["sqzmom_color"].iloc[-1]

    # LONG
    if (
        previous_color == "dark_red"
        and current_color == "light_red"
    ):
        return "LONG"

    # SHORT
    if (
        previous_color == "dark_green"
        and current_color == "light_green"
    ):
        return "SHORT"

    return None


def generate_signal(df):

    signal = detect_sqzmom_reversal(df)

    return {
        "signal": signal if signal else "NONE"
    }


def detect_historical_reversals(df):

    signals = []

    for i in range(1, len(df)):

        previous_color = df["sqzmom_color"].iloc[i - 1]
        current_color = df["sqzmom_color"].iloc[i]

        signal = None

        # -------------------------------
        # LONG
        # -------------------------------

        if (
            previous_color == "dark_red"
            and current_color == "light_red"
        ):
            signal = "LONG"

        # -------------------------------
        # SHORT
        # -------------------------------

        elif (
            previous_color == "dark_green"
            and current_color == "light_green"
        ):
            signal = "SHORT"

        # -------------------------------
        # SAVE SIGNAL
        # -------------------------------

        if signal:

            signals.append({
                "open_time": df["open_time"].iloc[i],
                "signal": signal,
                "previous_color": previous_color,
                "current_color": current_color,
                "sqzmom": df["sqzmom"].iloc[i],
                "signal_price": df["close"].iloc[i]
            })

    return signals
