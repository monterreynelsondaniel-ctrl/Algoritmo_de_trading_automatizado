"""Pre-outcome descriptive audit of cached Strategy 2 ENTRY reviews."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3

import pandas as pd

from ai_decision.prompts import ENTRY_PROMPT_VERSION
from ai_decision.schemas import EntryDecision, SCHEMA_VERSION
from ai_decision.service import DecisionService


DEFAULT_RUN_ID = "7c6f4b7f-b7fd-457a-8d43-b6b289d94558"
DEFAULT_BUNDLE = "btcusdt_1d_4h_1h_2026_08"
EXPECTED_BUNDLE_HASH = "a3176515d0c61ddb9ea210dca710f014957ee1ef80d813b75826da3d1977b840"
EXPECTED_SEQUENCE_FINGERPRINT = "437f242e6f96d8c441359321d10c48e317f8281cb5be86a39501843db808285a"
EXPECTED_INPUT_FINGERPRINT = "6115bd906cf50d587e72310ac0985e186d59381c6ac15c87464ed1902c282ccd"
FORBIDDEN_OUTCOME_NAMES = {
    "pnl", "return", "returns", "mfe", "mae", "win", "loss", "winner", "loser",
    "exit_price", "trade_result", "future", "future_outcome",
}
CONTEXTS = {"trend_1d": "d1", "setup_4h": "h4", "confirmation_1h": "h1"}


class EntryAuditError(RuntimeError):
    pass


def _canonical_hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _contains_forbidden_key(value):
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN_OUTCOME_NAMES or normalized.startswith("future_"):
                return True
            if _contains_forbidden_key(item):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def assert_pre_outcome_columns(columns):
    forbidden = [column for column in columns if (
        column.lower() in FORBIDDEN_OUTCOME_NAMES or column.lower().startswith("future_")
    )]
    if forbidden:
        raise EntryAuditError(f"Forbidden outcome columns: {sorted(forbidden)}")


def _read_run(connection, run_id):
    row = connection.execute("SELECT * FROM ai_runs WHERE run_id=?", (run_id,)).fetchone()
    if row is None:
        raise EntryAuditError(f"AI run not found: {run_id}")
    run = dict(row)
    identity = json.loads(run["identity_json"])
    expected = {
        "run_type": "entry_collection", "ai_mode": "live",
        "bundle_name": DEFAULT_BUNDLE, "bundle_hash": EXPECTED_BUNDLE_HASH,
        "strategy_version": "strategy_2_v1", "provider": "openai",
        "model": "gpt-5.6-terra", "reasoning_effort": "low",
        "entry_prompt_version": ENTRY_PROMPT_VERSION, "schema_version": SCHEMA_VERSION,
    }
    mismatches = {key: (identity.get(key), value) for key, value in expected.items()
                  if identity.get(key) != value}
    if run["status"] != "COMPLETED" or mismatches:
        raise EntryAuditError(f"Run identity/status mismatch: {mismatches or run['status']}")
    return run, identity


def _derive_visible_features(record, prefix, values, side):
    for name, value in values.items():
        record[f"{prefix}_{name}"] = value
    close, ema10, ema55 = values.get("close"), values.get("ema_10"), values.get("ema_55")
    plus_di, minus_di = values.get("plus_di"), values.get("minus_di")
    if close is not None and ema10:
        record[f"{prefix}_close_vs_ema10_pct"] = (close / ema10 - 1) * 100
    if close is not None and ema55:
        record[f"{prefix}_close_vs_ema55_pct"] = (close / ema55 - 1) * 100
    if ema10 is not None and ema55:
        record[f"{prefix}_ema10_vs_ema55_pct"] = (ema10 / ema55 - 1) * 100
        record[f"{prefix}_ema_direction"] = "BULLISH" if ema10 > ema55 else "BEARISH"
    if plus_di is not None and minus_di is not None:
        record[f"{prefix}_dmi_spread"] = plus_di - minus_di
        direction = "BULLISH" if plus_di > minus_di else "BEARISH"
        record[f"{prefix}_dmi_direction"] = direction
        record[f"{prefix}_dmi_aligned"] = direction == side.replace("LONG", "BULLISH").replace(
            "SHORT", "BEARISH"
        )


def _feature_comparison(frame):
    excluded = {"candidate_index", "confidence", "input_tokens", "output_tokens", "total_tokens"}
    numeric = [column for column in frame.select_dtypes(include="number").columns
               if column not in excluded]
    comparisons = {
        "approve_vs_reject": (frame.decision == "APPROVE", frame.decision == "REJECT",
                              "APPROVE", "REJECT"),
        "short_approve_vs_short_reject": (
            (frame.side == "SHORT") & (frame.decision == "APPROVE"),
            (frame.side == "SHORT") & (frame.decision == "REJECT"),
            "SHORT_APPROVE", "SHORT_REJECT",
        ),
        "long_reject_vs_short_reject": (
            (frame.side == "LONG") & (frame.decision == "REJECT"),
            (frame.side == "SHORT") & (frame.decision == "REJECT"),
            "LONG_REJECT", "SHORT_REJECT",
        ),
    }
    rows = []
    for comparison, (left_mask, right_mask, left_name, right_name) in comparisons.items():
        for feature in numeric:
            left = frame.loc[left_mask, feature].dropna()
            right = frame.loc[right_mask, feature].dropna()
            rows.append({
                "comparison": comparison, "feature": feature,
                "left_group": left_name, "right_group": right_name,
                "left_n": len(left), "left_mean": left.mean(),
                "left_median": left.median(), "left_p25": left.quantile(.25),
                "left_p75": left.quantile(.75), "left_min": left.min(), "left_max": left.max(),
                "right_n": len(right), "right_mean": right.mean(),
                "right_median": right.median(), "right_p25": right.quantile(.25),
                "right_p75": right.quantile(.75), "right_min": right.min(),
                "right_max": right.max(), "mean_difference": left.mean() - right.mean(),
                "relative_mean_difference": None if right.mean() == 0 else (
                    left.mean() / right.mean() - 1
                ),
            })
    return pd.DataFrame(rows)


def _categorical_summary(frame):
    columns = [
        "month", "quarter", "hour_utc", "weekday_utc",
        "d1_ema_direction", "d1_dmi_direction", "d1_dmi_aligned",
        "h4_ema_direction", "h4_dmi_direction", "h4_dmi_aligned",
        "h1_ema_direction", "h1_dmi_direction", "h1_dmi_aligned",
    ]
    rows = []
    for group_name, selected in {
        "APPROVE": frame.loc[frame.decision == "APPROVE"],
        "REJECT": frame.loc[frame.decision == "REJECT"],
        "LONG_REJECT": frame.loc[(frame.side == "LONG") & (frame.decision == "REJECT")],
        "SHORT_REJECT": frame.loc[(frame.side == "SHORT") & (frame.decision == "REJECT")],
        "SHORT_APPROVE": frame.loc[(frame.side == "SHORT") & (frame.decision == "APPROVE")],
    }.items():
        for column in columns:
            for value, count in selected[column].value_counts(dropna=False).items():
                rows.append({"group": group_name, "feature": column, "value": value,
                             "count": count, "group_candidates": len(selected),
                             "share": count / len(selected) if len(selected) else None})
    return pd.DataFrame(rows)


def _reason_summary(frame):
    rows = []
    dimensions = {
        "decision": ("APPROVE", "REJECT"),
        "side": ("LONG", "SHORT"),
        "side_decision": tuple(sorted((frame.side + "_" + frame.decision).unique())),
    }
    for dimension, groups in dimensions.items():
        for group in groups:
            if dimension == "decision":
                selected = frame.loc[frame.decision == group]
            elif dimension == "side":
                selected = frame.loc[frame.side == group]
            else:
                selected = frame.loc[(frame.side + "_" + frame.decision) == group]
            counts = Counter(code for codes in selected.reason_codes for code in codes)
            for reason, count in counts.most_common():
                rows.append({"dimension": dimension, "group": group, "reason_code": reason,
                             "count": count, "group_candidates": len(selected),
                             "candidate_share": count / len(selected) if len(selected) else None})
    return pd.DataFrame(rows)


def _group_stats(frame, column):
    output = {}
    for group, selected in frame.groupby(column):
        values = selected.confidence
        output[str(group)] = {
            "n": len(selected), "mean": values.mean(), "median": values.median(),
            "p25": values.quantile(.25), "p75": values.quantile(.75),
            "min": values.min(), "max": values.max(),
        }
    return output


def run_audit(run_id=DEFAULT_RUN_ID, database_path="database/ai_decisions.db",
              collection_dir="research/output/strategy_2_entry_collection",
              output_dir="research/output/strategy_2_entry_audit"):
    collection_path = Path(collection_dir) / f"entry_collection_{run_id}.json"
    collection = json.loads(collection_path.read_text(encoding="utf-8"))
    if collection.get("sequence_fingerprint") != EXPECTED_SEQUENCE_FINGERPRINT:
        raise EntryAuditError("Candidate sequence fingerprint mismatch")
    if collection.get("input_fingerprint") != EXPECTED_INPUT_FINGERPRINT:
        raise EntryAuditError("AI input sequence fingerprint mismatch")
    records = collection["records"]
    sequence = [{"candidate_id": row["candidate_id"],
                 "evaluation_time": row["evaluation_time"], "side": row["side"]}
                for row in records]
    inputs = [{**candidate, "input_hash": row["input_hash"]}
              for candidate, row in zip(sequence, records)]
    if _canonical_hash(sequence) != EXPECTED_SEQUENCE_FINGERPRINT:
        raise EntryAuditError("Recomputed candidate fingerprint mismatch")
    if _canonical_hash(inputs) != EXPECTED_INPUT_FINGERPRINT:
        raise EntryAuditError("Recomputed input fingerprint mismatch")

    uri = f"file:{Path(database_path).resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    run, identity = _read_run(connection, run_id)
    cache_rows = connection.execute(
        "SELECT * FROM ai_decision_cache WHERE decision_type='ENTRY'"
    ).fetchall()
    cache = {row["cache_key"]: row for row in cache_rows}
    service = DecisionService(None, None, model=identity["model"], provider=identity["provider"],
                              reasoning_effort=identity["reasoning_effort"], mode="replay")
    audit_rows = []
    schema_errors = []
    for source in records:
        key = source["input_hash"]
        cached = cache.get(key)
        if cached is None:
            raise EntryAuditError(f"Missing cached decision for {source['candidate_id']}")
        request = json.loads(cached["request_json"])
        response = json.loads(cached["response_json"])
        metadata = json.loads(cached["metadata_json"])
        if _contains_forbidden_key(request):
            raise EntryAuditError(f"Outcome-like key found in request {source['candidate_id']}")
        if service.cache_key("ENTRY", request) != key:
            raise EntryAuditError(f"Cache key mismatch for {source['candidate_id']}")
        try:
            decision = EntryDecision.parse(response, request["candidate"]["side"])
        except Exception as error:
            schema_errors.append({"candidate_id": source["candidate_id"],
                                  "error_type": type(error).__name__})
            continue
        evaluation = pd.Timestamp(source["evaluation_time"])
        setup = pd.Timestamp(request["candidate"]["setup_time"])
        confirmation = pd.Timestamp(request["candidate"]["confirmation_time"])
        as_of = pd.Timestamp(request["market_context"]["as_of"])
        if not (setup <= confirmation <= evaluation and as_of == evaluation):
            raise EntryAuditError(f"Temporal causality mismatch for {source['candidate_id']}")
        usage = metadata.get("usage") or {}
        record = {
            "candidate_index": source["candidate_index"],
            "candidate_id": source["candidate_id"], "input_hash": key,
            "evaluation_time": evaluation.isoformat(), "side": request["candidate"]["side"],
            "setup_time": setup.isoformat(), "confirmation_time": confirmation.isoformat(),
            "confirmation_delay_hours": (confirmation - setup).total_seconds() / 3600,
            "month": evaluation.strftime("%Y-%m"),
            "quarter": f"{evaluation.year}-Q{evaluation.quarter}",
            "hour_utc": evaluation.hour, "weekday_utc": evaluation.day_name(),
            "decision": decision.decision, "confidence": decision.confidence,
            "reason_codes": decision.reason_codes, "summary": decision.summary,
            "provider": metadata.get("provider"), "model": metadata.get("model"),
            "reasoning_effort": identity["reasoning_effort"],
            "prompt_version": metadata.get("prompt_version"),
            "schema_version": metadata.get("schema_version"),
            "response_id": metadata.get("response_id"),
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }
        for context_name, prefix in CONTEXTS.items():
            _derive_visible_features(record, prefix, request["market_context"][context_name],
                                     record["side"])
        audit_rows.append(record)
    connection.close()
    if schema_errors or len(audit_rows) != len(records):
        raise EntryAuditError(f"Schema/join errors: {schema_errors}")
    frame = pd.DataFrame(audit_rows).sort_values("candidate_index").reset_index(drop=True)
    assert_pre_outcome_columns(frame.columns)
    if frame.candidate_id.duplicated().any() or frame.input_hash.duplicated().any():
        raise EntryAuditError("Duplicate candidate ID or input hash")

    feature_comparison = _feature_comparison(frame)
    reason_summary = _reason_summary(frame)
    categorical_summary = _categorical_summary(frame)
    approved = frame.loc[frame.decision == "APPROVE"].copy()
    lexical_conflicts = frame.loc[
        ((frame.decision == "APPROVE") & frame.summary.str.contains(r"\breject\b", case=False))
        | ((frame.decision == "REJECT") & frame.summary.str.contains(r"\bapprove\b", case=False))
    ]
    summary = {
        "run": {key: run[key] for key in (
            "run_id", "status", "started_at", "completed_at", "live_calls", "cache_hits",
            "input_tokens", "output_tokens", "actual_cost_usd",
        )},
        "identity": identity,
        "candidate_sequence_fingerprint": EXPECTED_SEQUENCE_FINGERPRINT,
        "ai_input_sequence_fingerprint": EXPECTED_INPUT_FINGERPRINT,
        "counts": {
            "total": len(frame), "long": int((frame.side == "LONG").sum()),
            "short": int((frame.side == "SHORT").sum()),
            "approve": int((frame.decision == "APPROVE").sum()),
            "reject": int((frame.decision == "REJECT").sum()),
            "long_approve": int(((frame.side == "LONG") & (frame.decision == "APPROVE")).sum()),
            "long_reject": int(((frame.side == "LONG") & (frame.decision == "REJECT")).sum()),
            "short_approve": int(((frame.side == "SHORT") & (frame.decision == "APPROVE")).sum()),
            "short_reject": int(((frame.side == "SHORT") & (frame.decision == "REJECT")).sum()),
        },
        "approval_rates": {
            "overall": float((frame.decision == "APPROVE").mean()),
            "long": float((frame.loc[frame.side == "LONG", "decision"] == "APPROVE").mean()),
            "short": float((frame.loc[frame.side == "SHORT", "decision"] == "APPROVE").mean()),
        },
        "confidence_by_decision": _group_stats(frame, "decision"),
        "confidence_by_side": _group_stats(frame, "side"),
        "monthly_decisions": frame.groupby(["month", "decision"]).size().unstack(fill_value=0).to_dict(
            orient="index"
        ),
        "schema_consistency": {
            "schema_errors": schema_errors, "missing_fields": 0, "side_mismatches": 0,
            "duplicate_candidate_ids": 0, "duplicate_input_hashes": 0,
            "lexical_summary_conflicts": lexical_conflicts.candidate_id.tolist(),
        },
        "reason_code_vocabulary": {
            "unique_codes": len(set(code for codes in frame.reason_codes for code in codes)),
            "total_assignments": sum(len(codes) for codes in frame.reason_codes),
            "singleton_codes": sum(count == 1 for count in Counter(
                code for codes in frame.reason_codes for code in codes
            ).values()),
        },
        "pre_outcome_validation": {
            "forbidden_columns": [], "future_payload_keys": 0,
            "temporal_causality_errors": 0,
        },
        "fields_not_sent_to_ai": [
            "sqzmom_color_current", "sqzmom_color_previous", "sqzmom_slope",
            "setup_quality", "market_location", "technical_space", "risk_flags",
        ],
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    csv_frame = frame.copy()
    csv_frame["reason_codes"] = csv_frame.reason_codes.map(json.dumps)
    csv_frame.to_csv(output / "candidate_audit.csv", index=False)
    csv_frame.loc[csv_frame.decision == "APPROVE"].to_csv(
        output / "approved_candidates.csv", index=False
    )
    reason_summary.to_csv(output / "reason_code_summary.csv", index=False)
    feature_comparison.to_csv(output / "feature_comparison.csv", index=False)
    categorical_summary.to_csv(output / "categorical_summary.csv", index=False)
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    return frame, summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--database", default="database/ai_decisions.db")
    parser.add_argument("--collection-dir", default="research/output/strategy_2_entry_collection")
    parser.add_argument("--output-dir", default="research/output/strategy_2_entry_audit")
    args = parser.parse_args()
    _, summary = run_audit(args.run_id, args.database, args.collection_dir, args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
