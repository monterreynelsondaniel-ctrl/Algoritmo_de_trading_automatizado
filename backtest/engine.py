import pandas as pd


def _slipped_price(reference_price, order_side, slippage_rate):
    multiplier = 1 + slippage_rate if order_side == "BUY" else 1 - slippage_rate
    return reference_price * multiplier


def _signal_details(df, index, signal):
    """Capture the exact synthetic candle that confirmed a signal."""
    row = df.loc[index]
    return {
        "signal_time": signal["open_time"],
        "signal_sqzmom": row.get("sqzmom"),
        "signal_previous_color": signal.get("previous_color"),
        "signal_current_color": signal.get("current_color"),
        "signal_ha_open": row.get("ha_open"),
        "signal_ha_high": row.get("ha_high"),
        "signal_ha_low": row.get("ha_low"),
        "signal_ha_close": row.get("ha_close"),
    }


def run_signal_analysis(
    df,
    signals,
    timeframe_hours=4,
    commission_rate=0.0004,
    slippage_rate=0.0005,
    funding_rate=0.0001,
    funding_interval_hours=8,
):
    """
    Backtest complete movements using opposite SQZMOM signals
    as exit signals.

    Rules:

    LONG:
        LONG signal  -> open LONG
        SHORT signal -> close LONG and open SHORT

    SHORT:
        SHORT signal -> open SHORT
        LONG signal  -> close SHORT and open LONG

    Same-direction signals while a position is open are ignored.

    No stop loss, take profit, leverage, confidence,
    or additional market filters yet.
    """

    if any(rate < 0 for rate in (commission_rate, slippage_rate, funding_rate)):
        raise ValueError("commission, slippage, and funding rates cannot be negative")
    if timeframe_hours <= 0 or funding_interval_hours <= 0:
        raise ValueError("time intervals must be positive")

    results = []

    position = None

    for signal in signals:

        signal_time = signal["open_time"]
        signal_type = signal["signal"]

        # Find the candle where the signal was confirmed at close.
        signal_index = df.index[
            df["open_time"] == signal_time
        ]

        if len(signal_index) == 0:
            continue

        signal_index = signal_index[0]

        # A confirmed close can only be acted on at the next market open.
        execution_position = df.index.get_loc(signal_index) + 1
        if execution_position >= len(df):
            continue

        index = df.index[execution_position]
        execution_time = df.loc[index, "open_time"]
        reference_price = df.loc[index, "open"]
        entry_order_side = "BUY" if signal_type == "LONG" else "SELL"
        entry_execution_price = _slipped_price(
            reference_price, entry_order_side, slippage_rate
        )
        signal_details = _signal_details(df, signal_index, signal)

        # --------------------------------
        # NO OPEN POSITION
        # --------------------------------

        if position is None:

            position = {
                "signal": signal_type,
                "signal_time": signal_time,
                "entry_time": execution_time,
                "entry_index": index,
                "entry_position": execution_position,
                "entry_reference_price": reference_price,
                "entry_price": entry_execution_price,
                "entry_signal_details": signal_details,
            }

            continue

        # --------------------------------
        # SAME DIRECTION
        # --------------------------------

        if position["signal"] == signal_type:

            # Ignore repeated signal
            continue

        # --------------------------------
        # OPPOSITE SIGNAL
        # CLOSE CURRENT POSITION
        # --------------------------------

        exit_order_side = "SELL" if position["signal"] == "LONG" else "BUY"
        exit_price = _slipped_price(reference_price, exit_order_side, slippage_rate)

        entry_price = position["entry_price"]
        entry_reference_price = position["entry_reference_price"]

        if position["signal"] == "LONG":
            gross_pnl_pct = (
                (reference_price - entry_reference_price) / entry_reference_price
            ) * 100
            pnl_after_slippage_pct = (
                (exit_price - entry_price)
                / entry_price
            ) * 100

        else:  # SHORT
            gross_pnl_pct = (
                (entry_reference_price - reference_price) / entry_reference_price
            ) * 100
            pnl_after_slippage_pct = (
                (entry_price - exit_price)
                / entry_price
            ) * 100

        commission_pct = (
            (entry_price * commission_rate + exit_price * commission_rate)
            / entry_price
        ) * 100

        # --------------------------------
        # MFE / MAE
        # --------------------------------

        entry_index = position["entry_index"]
        entry_position = position["entry_position"]

        # The exit happens at the candle open, so its later high/low cannot be
        # counted as favorable or adverse movement for the closed trade.
        trade_data = df.iloc[entry_position:execution_position]

        max_price = trade_data["high"].max()
        min_price = trade_data["low"].min()

        if position["signal"] == "LONG":

            max_favorable_pct = (
                (max_price - entry_price)
                / entry_price
            ) * 100

            max_adverse_pct = (
                (min_price - entry_price)
                / entry_price
            ) * 100

        else:  # SHORT

            max_favorable_pct = (
                (entry_price - min_price)
                / entry_price
            ) * 100

            max_adverse_pct = (
                (entry_price - max_price)
                / entry_price
            ) * 100

        # --------------------------------
        # DURATION
        # --------------------------------

        duration_candles = execution_position - entry_position

        duration_hours = duration_candles * timeframe_hours
        funding_cycles = int(duration_hours // funding_interval_hours)
        funding_cost_pct = funding_cycles * funding_rate * 100
        slippage_cost_pct = gross_pnl_pct - pnl_after_slippage_pct
        total_fees_pct = commission_pct + funding_cost_pct
        net_pnl_pct = pnl_after_slippage_pct - total_fees_pct

        # --------------------------------
        # RESULT
        # --------------------------------

        results.append({
            "entry_signal_time": position["signal_time"],
            "entry_signal_sqzmom": position["entry_signal_details"]["signal_sqzmom"],
            "entry_signal_previous_color": position["entry_signal_details"]["signal_previous_color"],
            "entry_signal_current_color": position["entry_signal_details"]["signal_current_color"],
            "entry_signal_ha_open": position["entry_signal_details"]["signal_ha_open"],
            "entry_signal_ha_high": position["entry_signal_details"]["signal_ha_high"],
            "entry_signal_ha_low": position["entry_signal_details"]["signal_ha_low"],
            "entry_signal_ha_close": position["entry_signal_details"]["signal_ha_close"],
            "entry_time": position["entry_time"],
            "exit_signal_time": signal_time,
            "exit_signal_sqzmom": signal_details["signal_sqzmom"],
            "exit_signal_previous_color": signal_details["signal_previous_color"],
            "exit_signal_current_color": signal_details["signal_current_color"],
            "exit_signal_ha_open": signal_details["signal_ha_open"],
            "exit_signal_ha_high": signal_details["signal_ha_high"],
            "exit_signal_ha_low": signal_details["signal_ha_low"],
            "exit_signal_ha_close": signal_details["signal_ha_close"],
            "exit_time": execution_time,
            "signal": position["signal"],
            "entry_reference_price": entry_reference_price,
            "entry_price": entry_price,
            "exit_reference_price": reference_price,
            "exit_price": exit_price,
            "pnl_bruto": gross_pnl_pct,
            "commission_pct": commission_pct,
            "funding_cycles": funding_cycles,
            "funding_cost_pct": funding_cost_pct,
            "total_fees": total_fees_pct,
            "slippage_cost": slippage_cost_pct,
            "pnl_neto": net_pnl_pct,
            "pnl_pct": net_pnl_pct,
            "max_favorable_pct": max_favorable_pct,
            "max_adverse_pct": max_adverse_pct,
            "duration_candles": duration_candles,
            "duration_hours": duration_hours,
            "result": (
                "WIN"
                if net_pnl_pct > 0
                else "LOSS"
                if net_pnl_pct < 0
                else "BREAKEVEN"
            )
        })

        # --------------------------------
        # REVERSE POSITION
        # --------------------------------

        position = {
            "signal": signal_type,
            "signal_time": signal_time,
            "entry_time": execution_time,
            "entry_index": index,
            "entry_position": execution_position,
            "entry_reference_price": reference_price,
            "entry_price": entry_execution_price,
            "entry_signal_details": signal_details,
        }

    # --------------------------------
    # OPEN POSITION AT END OF DATA
    # --------------------------------

    if position is not None:

        results.append({
            "entry_signal_time": position["signal_time"],
            "entry_signal_sqzmom": position["entry_signal_details"]["signal_sqzmom"],
            "entry_signal_previous_color": position["entry_signal_details"]["signal_previous_color"],
            "entry_signal_current_color": position["entry_signal_details"]["signal_current_color"],
            "entry_signal_ha_open": position["entry_signal_details"]["signal_ha_open"],
            "entry_signal_ha_high": position["entry_signal_details"]["signal_ha_high"],
            "entry_signal_ha_low": position["entry_signal_details"]["signal_ha_low"],
            "entry_signal_ha_close": position["entry_signal_details"]["signal_ha_close"],
            "entry_time": position["entry_time"],
            "exit_signal_time": None,
            "exit_time": None,
            "signal": position["signal"],
            "entry_reference_price": position["entry_reference_price"],
            "entry_price": position["entry_price"],
            "exit_reference_price": None,
            "exit_price": None,
            "pnl_bruto": None,
            "commission_pct": None,
            "funding_cycles": None,
            "funding_cost_pct": None,
            "total_fees": None,
            "slippage_cost": None,
            "pnl_neto": None,
            "pnl_pct": None,
            "max_favorable_pct": None,
            "max_adverse_pct": None,
            "duration_candles": None,
            "duration_hours": None,
            "result": "OPEN"
        })

    return pd.DataFrame(results)
