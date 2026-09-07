def sqzmom_reversal(frame):
    if len(frame) < 2:
        return None
    previous, current = frame.sqzmom_color.iloc[-2], frame.sqzmom_color.iloc[-1]
    if previous == "dark_red" and current == "light_red":
        return "LONG"
    if previous == "dark_green" and current == "light_green":
        return "SHORT"
    return None


def daily_trend(frame):
    if frame.empty:
        return None
    row = frame.iloc[-1]
    if row[["ema_10", "ema_55"]].isna().any():
        return None
    if row.ema_10 > row.ema_55:
        return "LONG"
    if row.ema_10 < row.ema_55:
        return "SHORT"
    return None
