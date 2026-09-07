"""Signal rules specific to Strategy 1.

SQZMOM calculation and color assignment remain shared indicators. Only the
interpretation of color transitions as LONG/SHORT belongs here.
"""


def detect_sqzmom_reversal(df):
    if len(df) < 2:
        return None

    previous_color = df["sqzmom_color"].iloc[-2]
    current_color = df["sqzmom_color"].iloc[-1]

    if previous_color == "dark_red" and current_color == "light_red":
        return "LONG"
    if previous_color == "dark_green" and current_color == "light_green":
        return "SHORT"
    return None


def generate_signal(df):
    signal = detect_sqzmom_reversal(df)
    return {"signal": signal if signal else "NONE"}


def detect_historical_reversals(df):
    signals = []
    for position in range(1, len(df)):
        previous_color = df["sqzmom_color"].iloc[position - 1]
        current_color = df["sqzmom_color"].iloc[position]

        signal = None
        if previous_color == "dark_red" and current_color == "light_red":
            signal = "LONG"
        elif previous_color == "dark_green" and current_color == "light_green":
            signal = "SHORT"

        if signal:
            signals.append({
                "open_time": df["open_time"].iloc[position],
                "signal": signal,
                "previous_color": previous_color,
                "current_color": current_color,
                "sqzmom": df["sqzmom"].iloc[position],
                "signal_price": df["close"].iloc[position],
            })
    return signals
