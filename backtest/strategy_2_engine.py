"""Event-driven Strategy 2 backtest with mandatory cached/live AI decisions."""

from dataclasses import asdict, dataclass

from ai_decision.service import AIDecisionUnavailableError


@dataclass(frozen=True)
class Strategy2Trade:
    side: str
    entry_time: str
    entry_price: float
    exit_time: str
    exit_price: float
    pnl_pct: float
    mfe_pct: float
    mae_pct: float
    bars_4h: int


@dataclass(frozen=True)
class Strategy2BacktestResult:
    trades: list[Strategy2Trade]
    decisions: list[dict]
    open_position: dict | None

    def as_dict(self):
        return {"trades": [asdict(item) for item in self.trades],
                "decisions": self.decisions, "open_position": self.open_position}


class Strategy2Backtester:
    """Strategy 2 is never tested as automatic approval: every action uses AI."""

    def __init__(self, strategy, decision_service, commission_rate=0.0004, slippage_rate=0.0005):
        self.strategy, self.ai = strategy, decision_service
        self.commission_rate, self.slippage_rate = commission_rate, slippage_rate

    @staticmethod
    def _next_open(frame, at):
        rows = frame.loc[frame.open_time >= at]
        return None if rows.empty else rows.iloc[0]

    @staticmethod
    def _path(side, entry_price, candles):
        if candles.empty:
            return 0.0, 0.0
        if side == "LONG":
            return ((candles.high.max() / entry_price - 1) * 100,
                    (candles.low.min() / entry_price - 1) * 100)
        return ((entry_price / candles.low.min() - 1) * 100,
                (entry_price / candles.high.max() - 1) * 100)

    def run(self, raw_market_data):
        market = self.strategy.prepare_market_data(raw_market_data)
        hourly = market.full_frame(self.strategy.config.confirmation_timeframe)
        management = market.full_frame(self.strategy.config.management_timeframe)
        trades, audit, position = [], [], None
        for event_time in market.event_times():
            view = market.view_at(event_time)
            if position is None:
                candidate = self.strategy.evaluate(view)
                if candidate is None:
                    continue
                request = {"strategy_version": self.strategy.config.version,
                           "candidate": {"id": candidate.candidate_id, "side": candidate.side,
                                         "setup_time": candidate.setup_time.isoformat(),
                                         "confirmation_time": candidate.confirmation_time.isoformat()},
                           "market_context": candidate.context}
                try:
                    decision = self.ai.review_entry(request)
                except AIDecisionUnavailableError as error:
                    audit.append({"time": event_time.isoformat(), "type": "ENTRY",
                                  "status": "ERROR_FAIL_CLOSED", "detail": str(error)})
                    self.strategy.resolve_candidate(False)
                    raise AIDecisionUnavailableError(
                        "Strategy 2 backtest cannot continue without its required ENTRY decision"
                    ) from error
                audit.append({"time": event_time.isoformat(), "type": "ENTRY", "status": "OK",
                              **decision.as_dict()})
                self.strategy.resolve_candidate(decision.decision == "APPROVE")
                if decision.decision != "APPROVE":
                    continue
                bar = self._next_open(hourly, event_time)
                if bar is None:
                    audit.append({"time": event_time.isoformat(), "type": "ENTRY", "status": "NO_NEXT_BAR"})
                    self.strategy.reset()
                    continue
                price = float(bar.open) * (1 + self.slippage_rate if candidate.side == "LONG"
                                           else 1 - self.slippage_rate)
                self.strategy.mark_entry(bar.open_time, price)
                position = {"side": candidate.side, "entry_time": bar.open_time, "entry_price": price}
                continue

            visible = hourly.loc[(hourly.open_time >= position["entry_time"]) &
                                 (hourly.close_time < event_time)]
            current = view.latest(self.strategy.config.management_timeframe)
            if current is None:
                continue
            side, entry = position["side"], position["entry_price"]
            current_price = float(current.close)
            pnl = ((current_price / entry - 1) if side == "LONG" else (entry / current_price - 1)) * 100
            mfe, mae = self._path(side, entry, visible)
            request = self.strategy.management_payload(view, current_price, pnl, mfe, mae)
            if request is None:
                continue
            try:
                decision = self.ai.review_exit(request)
            except AIDecisionUnavailableError as error:
                audit.append({"time": event_time.isoformat(), "type": "EXIT",
                              "status": "ERROR_POSITION_REMAINS_PROTECTED", "detail": str(error)})
                continue
            audit.append({"time": event_time.isoformat(), "type": "EXIT", "status": "OK",
                          **decision.as_dict()})
            if decision.decision != "EXIT":
                continue
            bar = self._next_open(management, event_time)
            if bar is None:
                continue
            exit_price = float(bar.open) * (1 - self.slippage_rate if side == "LONG"
                                            else 1 + self.slippage_rate)
            gross = ((exit_price / entry - 1) if side == "LONG" else (entry / exit_price - 1)) * 100
            trades.append(Strategy2Trade(side, position["entry_time"].isoformat(), entry,
                                         bar.open_time.isoformat(), exit_price,
                                         gross - 2 * self.commission_rate * 100,
                                         float(mfe), float(mae), self.strategy.state.bars_since_entry))
            self.strategy.reset()
            position = None
        return Strategy2BacktestResult(trades, audit, position)
