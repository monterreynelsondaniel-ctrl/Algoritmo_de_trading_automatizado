"""Strictly pre-outcome comparison of Strategy 2 ENTRY V1 and V2 reviews."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import tempfile

import pandas as pd

from ai_decision.entry_reviews import ENTRY_REVIEW_V2
from ai_decision.service import DecisionService
from research.strategy_2_entry_ai_audit import (
    EntryAuditError, EXPECTED_BUNDLE_HASH, EXPECTED_SEQUENCE_FINGERPRINT,
    EXPECTED_INPUT_FINGERPRINT, _contains_forbidden_key, run_audit,
)


V1_RUN_ID = "7c6f4b7f-b7fd-457a-8d43-b6b289d94558"
V2_RUN_ID = "f0432b91-9104-4c8c-8e74-0064fa354a41"
V2_INPUT_FINGERPRINT = "521c0adecf70ffcbdfbde21dda75abb93d09802fa9f5da28d4147c5cb8bd67c2"
FORBIDDEN_COLUMNS = {
    "pnl", "return", "returns", "mfe", "mae", "win", "loss", "winner", "loser",
    "exit_price", "exit_time", "trade_result", "future_outcome",
}


def assert_pre_outcome(frame):
    forbidden = [column for column in frame.columns if (
        column.lower() in FORBIDDEN_COLUMNS or column.lower().startswith("future_")
    )]
    if forbidden:
        raise EntryAuditError(f"Forbidden outcome columns: {sorted(forbidden)}")


def _read_v2(database_path, collection_path):
    collection = json.loads(Path(collection_path).read_text(encoding="utf-8"))
    if collection["sequence_fingerprint"] != EXPECTED_SEQUENCE_FINGERPRINT:
        raise EntryAuditError("V2 candidate fingerprint mismatch")
    if collection["input_fingerprint"] != V2_INPUT_FINGERPRINT:
        raise EntryAuditError("V2 input fingerprint mismatch")
    uri = f"file:{Path(database_path).resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    run = connection.execute("SELECT * FROM ai_runs WHERE run_id=?", (V2_RUN_ID,)).fetchone()
    if run is None or run["status"] != "COMPLETED":
        raise EntryAuditError("Completed V2 live run not found")
    identity = json.loads(run["identity_json"])
    expected = {
        "run_type": "entry_collection", "ai_mode": "live",
        "bundle_hash": EXPECTED_BUNDLE_HASH, "strategy_version": "strategy_2_v1",
        "provider": "openai", "model": "gpt-5.6-terra", "reasoning_effort": "low",
        "entry_prompt_version": "strategy2-entry-v2", "schema_version": "1.1.0",
    }
    mismatches = {key: (identity.get(key), value) for key, value in expected.items()
                  if identity.get(key) != value}
    if mismatches:
        raise EntryAuditError(f"V2 run identity mismatch: {mismatches}")
    cache = {row["cache_key"]: row for row in connection.execute(
        "SELECT * FROM ai_decision_cache WHERE decision_type='ENTRY'"
    )}
    service = DecisionService(
        None, None, model=identity["model"], provider=identity["provider"],
        reasoning_effort=identity["reasoning_effort"], mode="replay",
        entry_review_version="v2",
    )
    records = []
    for source in collection["records"]:
        cached = cache.get(source["input_hash"])
        if cached is None:
            raise EntryAuditError(f"Missing V2 cache row: {source['candidate_id']}")
        request = json.loads(cached["request_json"])
        response = json.loads(cached["response_json"])
        metadata = json.loads(cached["metadata_json"])
        if _contains_forbidden_key(request):
            raise EntryAuditError(f"Outcome-like V2 input: {source['candidate_id']}")
        if service.cache_key("ENTRY", request) != source["input_hash"]:
            raise EntryAuditError(f"V2 cache identity mismatch: {source['candidate_id']}")
        decision = ENTRY_REVIEW_V2.parse(response, source["side"])
        evaluation = pd.Timestamp(source["evaluation_time"])
        setup = pd.Timestamp(request["candidate"]["setup_time"])
        confirmation = pd.Timestamp(request["candidate"]["confirmation_time"])
        as_of = pd.Timestamp(request["market_context"]["as_of"])
        if not (setup <= confirmation <= evaluation and as_of == evaluation):
            raise EntryAuditError(f"V2 causality mismatch: {source['candidate_id']}")
        records.append({
            "candidate_index": source["candidate_index"],
            "candidate_id": source["candidate_id"],
            "evaluation_time": evaluation.isoformat(), "side": source["side"],
            "v2_input_hash": source["input_hash"], "v2_decision": decision.decision,
            "v2_confidence": decision.confidence, "v2_reason_codes": decision.reason_codes,
            "v2_summary": decision.summary,
            "setup_transition": request["strategy_semantics"]["setup_4h"]["transition"],
            "confirmation_transition": request["strategy_semantics"]["confirmation_1h"]["transition"],
            "prompt_version": metadata.get("prompt_version"),
            "schema_version": metadata.get("schema_version"),
        })
    connection.close()
    frame = pd.DataFrame(records).sort_values("candidate_index").reset_index(drop=True)
    assert_pre_outcome(frame)
    if len(frame) != 81 or frame.candidate_id.duplicated().any():
        raise EntryAuditError("V2 audit does not contain 81 unique candidates")
    return frame, dict(run), identity


def _reason_rows(frame):
    rows = []
    groups = {
        "V1_ALL": frame,
        "V2_ALL": frame,
        "V1_REJECT_TO_V2_APPROVE": frame.loc[frame.transition == "REJECT_TO_APPROVE"],
        "V2_RETAINED_APPROVE": frame.loc[frame.transition == "APPROVE_TO_APPROVE"],
        "V2_LONG_APPROVE": frame.loc[(frame.side == "LONG") & (frame.v2_decision == "APPROVE")],
        "V2_SHORT_APPROVE": frame.loc[(frame.side == "SHORT") & (frame.v2_decision == "APPROVE")],
    }
    for group, selected in groups.items():
        version = "v1" if group.startswith("V1_") else "v2"
        column = f"{version}_reason_codes"
        counts = Counter(code for codes in selected[column] for code in codes)
        for code, count in counts.most_common():
            rows.append({"group": group, "reason_code": code, "count": count,
                         "candidates": len(selected),
                         "candidate_share": count / len(selected) if len(selected) else None})
    return pd.DataFrame(rows)


def run_comparison(database_path="database/ai_decisions.db",
                   collection_dir="research/output/strategy_2_entry_collection",
                   output_dir="research/output/strategy_2_entry_v2_audit"):
    with tempfile.TemporaryDirectory() as temporary:
        v1, v1_summary = run_audit(
            V1_RUN_ID, database_path, collection_dir, temporary,
        )
    v2_path = Path(collection_dir) / f"entry_collection_{V2_RUN_ID}.json"
    v2, v2_run, v2_identity = _read_v2(database_path, v2_path)
    v1_selected = v1[[
        "candidate_index", "candidate_id", "evaluation_time", "side", "input_hash",
        "decision", "confidence", "reason_codes", "summary",
    ]].rename(columns={
        "input_hash": "v1_input_hash", "decision": "v1_decision",
        "confidence": "v1_confidence", "reason_codes": "v1_reason_codes",
        "summary": "v1_summary",
    })
    frame = v1_selected.merge(
        v2, on=["candidate_index", "candidate_id", "evaluation_time", "side"],
        validate="one_to_one",
    )
    frame["transition"] = frame.v1_decision + "_TO_" + frame.v2_decision
    assert_pre_outcome(frame)
    transitions = frame.groupby(["side", "transition"]).size().reset_index(name="count")
    reason_summary = _reason_rows(frame)
    all_v1_codes = Counter(code for codes in frame.v1_reason_codes for code in codes)
    all_v2_codes = Counter(code for codes in frame.v2_reason_codes for code in codes)
    opposite_pairs = (
        ("TREND_ALIGNED", "TREND_CONFLICT"),
        ("SETUP_CONFIRMED", "SETUP_WEAK"),
        ("CONFIRMATION_STRONG", "CONFIRMATION_WEAK"),
        ("DMI_ALIGNED", "DMI_CONFLICT"),
        ("ADX_STRONG", "ADX_WEAK"),
        ("EMA_ALIGNED", "EMA_CONFLICT"),
        ("MOMENTUM_REVERSAL_CLEAR", "MOMENTUM_REVERSAL_WEAK"),
    )
    contradictions = [{
        "candidate_index": int(row.candidate_index), "candidate_id": row.candidate_id,
        "side": row.side, "decision": row.v2_decision, "pair": [left, right],
    } for left, right in opposite_pairs for _, row in frame.iterrows()
      if left in row.v2_reason_codes and right in row.v2_reason_codes]
    shifted = frame.loc[frame.transition == "REJECT_TO_APPROVE"]
    retained = frame.loc[frame.transition == "APPROVE_TO_APPROVE"]
    summary = {
        "identity": {
            "v1_run_id": V1_RUN_ID, "v2_run_id": V2_RUN_ID,
            "v2_status": v2_run["status"], "v2_model": v2_identity["model"],
            "v2_reasoning": v2_identity["reasoning_effort"],
            "v2_prompt": v2_identity["entry_prompt_version"],
            "v2_schema": v2_identity["schema_version"],
        },
        "fingerprints": {
            "bundle": EXPECTED_BUNDLE_HASH,
            "candidate_sequence": EXPECTED_SEQUENCE_FINGERPRINT,
            "v1_input_sequence": EXPECTED_INPUT_FINGERPRINT,
            "v2_input_sequence": V2_INPUT_FINGERPRINT,
        },
        "counts": {
            "candidates": len(frame), "long": int((frame.side == "LONG").sum()),
            "short": int((frame.side == "SHORT").sum()),
            "v1_approve": int((frame.v1_decision == "APPROVE").sum()),
            "v2_approve": int((frame.v2_decision == "APPROVE").sum()),
            "reject_to_approve": len(shifted),
            "approve_to_approve": len(retained),
            "approve_to_reject": int((frame.transition == "APPROVE_TO_REJECT").sum()),
            "long_v2_approve": int(((frame.side == "LONG") &
                                    (frame.v2_decision == "APPROVE")).sum()),
            "short_v2_approve": int(((frame.side == "SHORT") &
                                     (frame.v2_decision == "APPROVE")).sum()),
        },
        "approval_rates": {
            "v1_total": float((frame.v1_decision == "APPROVE").mean()),
            "v2_total": float((frame.v2_decision == "APPROVE").mean()),
            "v2_long": float((frame.loc[frame.side == "LONG", "v2_decision"] == "APPROVE").mean()),
            "v2_short": float((frame.loc[frame.side == "SHORT", "v2_decision"] == "APPROVE").mean()),
        },
        "reason_code_stability": {
            "v1_unique": len(all_v1_codes), "v1_singletons": sum(v == 1 for v in all_v1_codes.values()),
            "v2_unique": len(all_v2_codes), "v2_singletons": sum(v == 1 for v in all_v2_codes.values()),
            "v2_outside_enum": sorted(set(all_v2_codes) - set(ENTRY_REVIEW_V2.controlled_reason_codes)),
            "opposite_pair_assignments": contradictions,
        },
        "v1_schema_consistency": v1_summary["schema_consistency"],
        "pre_outcome_validation": {
            "forbidden_columns": [], "future_payload_keys": 0,
            "outcomes_loaded": 0,
        },
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    serializable = frame.copy()
    for column in ("v1_reason_codes", "v2_reason_codes"):
        serializable[column] = serializable[column].map(json.dumps)
    serializable.to_csv(output / "candidate_comparison.csv", index=False)
    serializable.loc[serializable.transition == "REJECT_TO_APPROVE"].to_csv(
        output / "newly_approved_candidates.csv", index=False,
    )
    transitions.to_csv(output / "transition_summary.csv", index=False)
    reason_summary.to_csv(output / "reason_code_comparison.csv", index=False)
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8",
    )
    return frame, summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default="database/ai_decisions.db")
    parser.add_argument("--collection-dir", default="research/output/strategy_2_entry_collection")
    parser.add_argument("--output-dir", default="research/output/strategy_2_entry_v2_audit")
    args = parser.parse_args()
    _, summary = run_comparison(args.database, args.collection_dir, args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
