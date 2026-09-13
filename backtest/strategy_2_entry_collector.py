"""ENTRY-only AI decision collection; never simulates positions or outcomes."""

import csv
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re

from ai_decision.budget import AIBudgetExceededError
from ai_decision.service import AIDecisionUnavailableError, AIRequestStateUnknownError
from backtest.strategy_2_candidates import enumerate_flat_entry_candidates


COLLECTION_COLUMNS = (
    "candidate_index", "candidate_id", "evaluation_time", "side", "setup_time",
    "confirmation_time", "ai_status", "confidence", "reason_codes", "summary",
    "provider", "model", "reasoning_effort", "prompt_version", "schema_version",
    "cache_hit", "live_call", "input_hash", "run_id",
)


@dataclass(frozen=True)
class EntryCollectionResult:
    records: list[dict]
    run_id: str
    sequence_fingerprint: str
    input_fingerprint: str
    output_csv: str
    output_json: str
    completed: bool
    stop_reason: str | None
    live_calls: int
    cache_hits: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    actual_cost_usd: float

    def summary(self):
        counts = {status: 0 for status in ("APPROVE", "REJECT", "MISSING", "UNKNOWN", "ERROR")}
        for record in self.records:
            counts[record["ai_status"]] += 1
        decided = counts["APPROVE"] + counts["REJECT"]
        return {
            "total_candidates": len(self.records),
            "long": sum(record["side"] == "LONG" for record in self.records),
            "short": sum(record["side"] == "SHORT" for record in self.records),
            **{status.lower(): value for status, value in counts.items()},
            "approval_rate": None if not decided else counts["APPROVE"] / decided,
            "cache_hits": self.cache_hits,
            "live_calls": self.live_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "actual_cost_usd": self.actual_cost_usd,
            "positions_opened": 0,
            "trades": 0,
            "exit_reviews": 0,
            "run_id": self.run_id,
            "completed": self.completed,
            "stop_reason": self.stop_reason,
            "sequence_fingerprint": self.sequence_fingerprint,
            "input_fingerprint": self.input_fingerprint,
            "output_csv": self.output_csv,
            "output_json": self.output_json,
        }


def _caused_by(error, error_type):
    current = error
    while current is not None:
        if isinstance(current, error_type):
            return True
        current = current.__cause__
    return False


def _safe_run_id(run_id):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", run_id):
        raise ValueError("run_id contains characters unsafe for an output filename")
    return run_id


class Strategy2EntryCollector:
    """Consumes only ``review_entry`` over independent, portfolio-flat candidates."""

    def __init__(self, strategy, decision_service, store, run_manager,
                 output_dir="research/output/strategy_2_entry_collection", progress=None):
        self.strategy = strategy
        self.ai = decision_service
        self.store = store
        self.run_manager = run_manager
        self.output_dir = Path(output_dir)
        self.progress = progress

    def _base_record(self, envelope, input_hash):
        candidate = envelope.candidate
        return {
            "candidate_index": envelope.index,
            "candidate_id": candidate.candidate_id,
            "evaluation_time": envelope.evaluation_time.isoformat(),
            "side": candidate.side,
            "setup_time": candidate.setup_time.isoformat(),
            "confirmation_time": candidate.confirmation_time.isoformat(),
            "ai_status": "MISSING", "confidence": None, "reason_codes": [], "summary": None,
            "provider": self.ai.provider, "model": self.ai.model,
            "reasoning_effort": self.ai.reasoning_effort,
            "prompt_version": self.ai.entry_prompt_version,
            "schema_version": self.ai.entry_schema_version,
            "cache_hit": False, "live_call": False, "input_hash": input_hash,
            "run_id": self.run_manager.run_id,
        }

    def _write(self, records, sequence_fingerprint, input_fingerprint):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        run_id = _safe_run_id(self.run_manager.run_id)
        csv_path = self.output_dir / f"entry_collection_{run_id}.csv"
        json_path = self.output_dir / f"entry_collection_{run_id}.json"
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLLECTION_COLUMNS)
            writer.writeheader()
            for record in records:
                row = dict(record)
                row["reason_codes"] = json.dumps(row["reason_codes"], separators=(",", ":"))
                writer.writerow(row)
        json_path.write_text(json.dumps({
            "run_id": self.run_manager.run_id,
            "sequence_fingerprint": sequence_fingerprint,
            "input_fingerprint": input_fingerprint,
            "records": records,
        }, indent=2, sort_keys=True), encoding="utf-8")
        return str(csv_path), str(json_path)

    def run(self, raw_market_data):
        _, candidates = enumerate_flat_entry_candidates(
            raw_market_data, self.strategy, self.ai.entry_prompt_version,
        )
        keyed = [(item, self.ai.cache_key("ENTRY", item.payload)) for item in candidates]
        sequence = [{"candidate_id": item.candidate.candidate_id,
                     "evaluation_time": item.evaluation_time.isoformat(),
                     "side": item.candidate.side} for item, _ in keyed]
        fingerprint = hashlib.sha256(
            json.dumps(sequence, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        inputs = [{**candidate, "input_hash": key}
                  for candidate, (_, key) in zip(sequence, keyed)]
        input_fingerprint = hashlib.sha256(
            json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        records = []
        completed, stop_reason = True, None
        for position, (envelope, input_hash) in enumerate(keyed):
            base = self._base_record(envelope, input_hash)
            cached_before = self.store.get(input_hash) is not None
            pending = self.store.pending_status(input_hash)
            calls_before = self.run_manager.counters()["live_calls"]
            if pending in {"PENDING", "UNKNOWN"} and not cached_before:
                base["ai_status"] = "UNKNOWN"
            else:
                try:
                    decision = self.ai.review_entry(envelope.payload)
                    decision_data = decision.as_dict()
                    decision_data.pop("decision", None)
                    decision_data.pop("side", None)
                    base.update(decision_data)
                    base["ai_status"] = decision.decision
                    base["cache_hit"] = cached_before
                except AIRequestStateUnknownError:
                    base["ai_status"] = "UNKNOWN"
                except AIDecisionUnavailableError as error:
                    if self.ai.mode == "replay" and not cached_before:
                        base["ai_status"] = "MISSING"
                    else:
                        base["ai_status"] = "ERROR"
                    if _caused_by(error, AIBudgetExceededError):
                        completed, stop_reason = False, "AI_BUDGET_LIMIT"
            base["live_call"] = self.run_manager.counters()["live_calls"] > calls_before
            records.append(base)
            self.run_manager.checkpoint(envelope.evaluation_time)
            if self.progress:
                self.progress(base, len(candidates), self.run_manager.counters())
            if stop_reason:
                for remaining, remaining_hash in keyed[position + 1:]:
                    records.append(self._base_record(remaining, remaining_hash))
                break
        counters = self.run_manager.counters()
        csv_path, json_path = self._write(records, fingerprint, input_fingerprint)
        return EntryCollectionResult(
            records, self.run_manager.run_id, fingerprint, input_fingerprint,
            csv_path, json_path,
            completed, stop_reason, **counters,
        )
