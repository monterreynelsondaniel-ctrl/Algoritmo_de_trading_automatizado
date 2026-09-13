"""Offline workload, token and cost preview for Strategy 2 AI runs."""

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

import pandas as pd

from ai_decision.entry_reviews import ENTRY_REVIEW_V1, ENTRY_REVIEW_V2, get_entry_review_contract
from ai_decision.prompts import EXIT_SYSTEM_PROMPT
from ai_decision.schemas import EXIT_SCHEMA
from ai_decision.service import DecisionService
from ai_decision.budget import token_cost
from backtest.strategy_2_candidates import enumerate_flat_entry_candidates
from data.frozen_market_data import FrozenMarketDataStore
from strategies.strategy_2 import Strategy2


@dataclass(frozen=True)
class PreflightReport:
    bundle: str
    bundle_hash: str
    strategy_version: str
    model: str
    reasoning_effort: str
    entry_prompt_version: str
    entry_schema_version: str
    deterministic_candidates: int
    candidates_long: int
    candidates_short: int
    entry_cache_hits: int
    entry_live_calls: int
    exit_reviews_minimum: int
    exit_reviews_reasonable: int
    exit_reviews_upper_bound: int
    entry_input_tokens: int
    entry_input_tokens_upper: int
    entry_output_tokens_expected: int
    exit_input_tokens: int
    exit_input_tokens_upper: int
    exit_output_tokens_expected: int
    cost_per_entry_usd: float
    cost_per_exit_usd: float
    reserved_cost_per_entry_usd: float
    reserved_cost_per_exit_usd: float
    entry_first_run_cost_usd: float
    entry_first_run_reserved_upper_usd: float
    reasonable_total_cost_usd: float
    conservative_upper_bound_usd: float
    cache_entries: int
    first_candidate_hash: str | None
    candidate_sequence_fingerprint: str
    v1_input_sequence_fingerprint: str
    v2_input_sequence_fingerprint: str
    entry_budget_limit_usd: float
    entry_call_limit: int
    budget_covers_reserved_entry_run: bool
    call_limit_covers_entry_run: bool

    def as_dict(self):
        return asdict(self)


def bundle_fingerprint(bundle_name, root="data/snapshots"):
    root = Path(root)
    manifest = json.loads((root / f"{bundle_name}.bundle.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256()
    digest.update(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode())
    for snapshot in sorted(manifest["snapshots"].values()):
        for suffix in (".csv", ".json"):
            digest.update((root / f"{snapshot}{suffix}").read_bytes())
    return digest.hexdigest()


def _representative_exit_payload(entry):
    context = entry["market_context"]
    return {
        "strategy_version": entry["strategy_version"],
        "position": {"side": entry["candidate"]["side"],
                     "entry_time": entry["candidate"]["confirmation_time"],
                     "entry_price": context["confirmation_1h"].get("close")},
        "entry_context": context,
        "current_context_4h": context["setup_4h"],
        "path": {"current_price": context["setup_4h"].get("close"),
                 "unrealized_pnl_pct": 0.0, "mfe_pct": 0.0, "mae_pct": 0.0,
                 "bars_since_entry": 1},
    }


def _sequence_fingerprints(envelopes, service):
    sequence = [{"candidate_id": item.candidate.candidate_id,
                 "evaluation_time": item.evaluation_time.isoformat(),
                 "side": item.candidate.side} for item in envelopes]
    candidate_fingerprint = hashlib.sha256(
        json.dumps(sequence, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    inputs = [{**candidate, "input_hash": service.cache_key("ENTRY", item.payload)}
              for candidate, item in zip(sequence, envelopes)]
    input_fingerprint = hashlib.sha256(
        json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return candidate_fingerprint, input_fingerprint


def create_preflight_report(bundle_name, store, settings, entry_review_version="v1"):
    market = FrozenMarketDataStore().load_bundle(bundle_name)
    contract = get_entry_review_contract(entry_review_version)
    prepared, envelopes = enumerate_flat_entry_candidates(
        market, entry_prompt_version=contract.prompt_version,
    )
    candidates = [item.payload for item in envelopes]
    if not candidates:
        raise RuntimeError("Strategy 2 produced no deterministic candidates")
    service = DecisionService(None, store, model=settings.openai_model,
                              provider=settings.ai_provider,
                              reasoning_effort=settings.openai_reasoning_effort, mode="replay",
                              entry_review_version=entry_review_version)
    _, v1_envelopes = enumerate_flat_entry_candidates(
        market, entry_prompt_version=ENTRY_REVIEW_V1.prompt_version,
    )
    _, v2_envelopes = enumerate_flat_entry_candidates(
        market, entry_prompt_version=ENTRY_REVIEW_V2.prompt_version,
    )
    v1_service = DecisionService(
        None, store, model=settings.openai_model, provider=settings.ai_provider,
        reasoning_effort=settings.openai_reasoning_effort, mode="replay",
        entry_review_version="v1",
    )
    v2_service = DecisionService(
        None, store, model=settings.openai_model, provider=settings.ai_provider,
        reasoning_effort=settings.openai_reasoning_effort, mode="replay",
        entry_review_version="v2",
    )
    candidate_fingerprint, _ = _sequence_fingerprints(envelopes, service)
    _, v1_input_fingerprint = _sequence_fingerprints(v1_envelopes, v1_service)
    _, v2_input_fingerprint = _sequence_fingerprints(v2_envelopes, v2_service)
    cached = sum(store.get(service.cache_key("ENTRY", payload)) is not None for payload in candidates)
    entry_tokens = max(service.estimated_input_tokens(contract.system_prompt, payload, contract.schema)
                       for payload in candidates)
    entry_tokens_upper = max(
        service.input_token_upper_bound(contract.system_prompt, payload, contract.schema)
        for payload in candidates
    )
    exit_payload = _representative_exit_payload(candidates[0])
    exit_tokens = service.estimated_input_tokens(EXIT_SYSTEM_PROMPT, exit_payload, EXIT_SCHEMA)
    exit_tokens_upper = service.input_token_upper_bound(EXIT_SYSTEM_PROMPT, exit_payload, EXIT_SCHEMA)
    output_limit = settings.ai_max_output_tokens_per_call
    expected_output = min(300, output_limit)
    entry_cost = token_cost(entry_tokens, expected_output,
                            settings.ai_input_cost_per_million_usd,
                            settings.ai_output_cost_per_million_usd)
    exit_cost = token_cost(exit_tokens, expected_output,
                           settings.ai_input_cost_per_million_usd,
                           settings.ai_output_cost_per_million_usd)
    reserved_entry_cost = token_cost(entry_tokens_upper, output_limit,
                                     settings.ai_input_cost_per_million_usd,
                                     settings.ai_output_cost_per_million_usd)
    reserved_exit_cost = token_cost(exit_tokens_upper, output_limit,
                                    settings.ai_input_cost_per_million_usd,
                                    settings.ai_output_cost_per_million_usd)
    frame_4h = prepared.full_frame(Strategy2().config.management_timeframe)
    manifest = json.loads(
        Path(f"data/snapshots/{bundle_name}.bundle.json").read_text(encoding="utf-8")
    )
    evaluation_start = manifest.get("evaluation_start")
    evaluation_end = manifest.get("evaluation_end")
    event_times = frame_4h["close_time"] + pd.Timedelta(milliseconds=1)
    eligible = event_times
    if evaluation_start:
        eligible = eligible.loc[eligible >= pd.Timestamp(evaluation_start)]
    if evaluation_end:
        eligible = eligible.loc[eligible <= pd.Timestamp(evaluation_end)]
    upper_exit = len(eligible)
    reasonable_exit = min(upper_exit, len(candidates) * 10)
    live_entries = len(candidates) - cached
    return PreflightReport(
        bundle=bundle_name, bundle_hash=bundle_fingerprint(bundle_name),
        strategy_version=Strategy2().config.version, model=settings.openai_model,
        reasoning_effort=settings.openai_reasoning_effort,
        entry_prompt_version=contract.prompt_version,
        entry_schema_version=contract.schema_version,
        deterministic_candidates=len(candidates),
        candidates_long=sum(p["candidate"]["side"] == "LONG" for p in candidates),
        candidates_short=sum(p["candidate"]["side"] == "SHORT" for p in candidates),
        entry_cache_hits=cached, entry_live_calls=live_entries,
        exit_reviews_minimum=0, exit_reviews_reasonable=reasonable_exit,
        exit_reviews_upper_bound=upper_exit,
        entry_input_tokens=entry_tokens, entry_input_tokens_upper=entry_tokens_upper,
        entry_output_tokens_expected=expected_output,
        exit_input_tokens=exit_tokens, exit_input_tokens_upper=exit_tokens_upper,
        exit_output_tokens_expected=expected_output,
        cost_per_entry_usd=entry_cost, cost_per_exit_usd=exit_cost,
        reserved_cost_per_entry_usd=reserved_entry_cost,
        reserved_cost_per_exit_usd=reserved_exit_cost,
        entry_first_run_cost_usd=live_entries * entry_cost,
        entry_first_run_reserved_upper_usd=live_entries * reserved_entry_cost,
        reasonable_total_cost_usd=live_entries * entry_cost + reasonable_exit * exit_cost,
        conservative_upper_bound_usd=(live_entries * reserved_entry_cost
                                      + upper_exit * reserved_exit_cost),
        cache_entries=store.count(),
        first_candidate_hash=service.cache_key("ENTRY", candidates[0]),
        candidate_sequence_fingerprint=candidate_fingerprint,
        v1_input_sequence_fingerprint=v1_input_fingerprint,
        v2_input_sequence_fingerprint=v2_input_fingerprint,
        entry_budget_limit_usd=settings.ai_max_run_cost_usd,
        entry_call_limit=settings.ai_max_live_calls_per_run,
        budget_covers_reserved_entry_run=(
            live_entries * reserved_entry_cost <= settings.ai_max_run_cost_usd
        ),
        call_limit_covers_entry_run=(
            live_entries <= settings.ai_max_live_calls_per_run
        ),
    )
