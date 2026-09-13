"""Shared causal enumeration of independent Strategy 2 ENTRY candidates."""

from dataclasses import dataclass

from backtest.strategy_2_engine import build_entry_request
from strategies.strategy_2 import Strategy2


@dataclass(frozen=True)
class EntryCandidateEnvelope:
    index: int
    evaluation_time: object
    candidate: object
    payload: dict


def enumerate_flat_entry_candidates(raw_market_data, strategy=None,
                                    entry_prompt_version=None):
    """Return every potential ENTRY candidate while remaining portfolio-flat.

    This is research/census semantics, not a simulated APPROVE or REJECT. After
    each candidate, the already-seen setup and confirmation candles are retained
    so the same closed bars cannot be rediscovered on the next event.
    """
    strategy = strategy or Strategy2()
    entry_prompt_version = entry_prompt_version or "strategy2-entry-v1"
    market = strategy.prepare_market_data(raw_market_data)
    candidates = []
    for event_time in market.event_times():
        candidate = strategy.evaluate(market.view_at(event_time))
        if candidate is None:
            continue
        candidates.append(EntryCandidateEnvelope(
            index=len(candidates) + 1,
            evaluation_time=event_time,
            candidate=candidate,
            payload=build_entry_request(strategy, candidate, entry_prompt_version),
        ))
        last_setup = strategy.state.last_setup_candle
        last_confirmation = strategy.state.last_confirmation_candle
        strategy.reset()
        strategy.state.last_setup_candle = last_setup
        strategy.state.last_confirmation_candle = last_confirmation
    return market, candidates
