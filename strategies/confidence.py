def calculate_signal_confidence(df, reversal):
    """
    Calculate confidence for an early SQZMOM reversal.

    Returns:
        tuple:
            confidence: int (0-100)
            reasons: list[str]
    """

    confidence = 0
    reasons = []

    # --------------------------------
    # No reversal
    # --------------------------------

    if reversal is None:
        return 0, ["No SQZMOM reversal detected"]

    current = df["sqzmom"].iloc[-1]
    previous = df["sqzmom"].iloc[-2]

    # --------------------------------
    # 1. Early reversal detected
    # --------------------------------

    confidence += 30
    reasons.append("Early SQZMOM reversal detected")

    # --------------------------------
    # 2. Momentum is turning
    # --------------------------------

    if reversal == "LONG":

        if current > previous:
            confidence += 25
            reasons.append("Bullish momentum turn")

    elif reversal == "SHORT":

        if current < previous:
            confidence += 25
            reasons.append("Bearish momentum turn")

    # --------------------------------
    # 3. Reversal before zero
    # --------------------------------

    if reversal == "LONG" and current < 0:

        confidence += 20
        reasons.append("Bullish reversal before zero")

    elif reversal == "SHORT" and current > 0:

        confidence += 20
        reasons.append("Bearish reversal before zero")

    # --------------------------------
    # 4. Momentum movement
    # --------------------------------

    movement = abs(current - previous)

    if movement > 0:

        confidence += 25
        reasons.append("Momentum moving")

    # --------------------------------
    # Final score
    # --------------------------------

    confidence = min(confidence, 100)

    return confidence, reasons