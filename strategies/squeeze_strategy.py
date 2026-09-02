def detect_squeeze_movement(df):
    """
    Detect the current squeeze state.
    """

    if len(df) < 1:
        return "UNKNOWN"

    current = df.iloc[-1]

    if current["sqz_on"]:
        return "SQUEEZE_ON"

    if current["sqz_off"]:
        return "SQUEEZE_OFF"

    return "NO_SQUEEZE"


def detect_squeeze_transition(df):
    """
    Detect changes in the squeeze state.
    """

    if len(df) < 2:
        return "NO_CHANGE"

    previous = df.iloc[-2]
    current = df.iloc[-1]

    if not previous["sqz_on"] and current["sqz_on"]:
        return "SQUEEZE_STARTED"

    if previous["sqz_on"] and current["sqz_off"]:
        return "SQUEEZE_RELEASED"

    if previous["sqz_on"] and current["sqz_on"]:
        return "SQUEEZE_CONTINUING"

    return "NO_CHANGE"


def detect_momentum_movement(df):
    """
    Detect the direction of SQZMOM momentum.
    """

    if len(df) < 2:
        return "FLAT"

    current = df["sqzmom"].iloc[-1]
    previous = df["sqzmom"].iloc[-2]

    if current > previous:
        return "ACCELERATING"

    if current < previous:
        return "DECELERATING"

    return "FLAT"