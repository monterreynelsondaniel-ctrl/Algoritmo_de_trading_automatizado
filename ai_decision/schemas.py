"""Strict, versioned schemas. AI output is untrusted until validated here."""

from dataclasses import asdict, dataclass
from typing import Any


SCHEMA_VERSION = "1.0.0"


class DecisionSchemaError(ValueError):
    pass


def _strict_object(name, properties, required):
    return {
        "type": "json_schema",
        "name": name,
        "strict": True,
        "schema": {
            "type": "object", "properties": properties,
            "required": required, "additionalProperties": False,
        },
    }


ENTRY_SCHEMA = _strict_object("strategy_2_entry_decision", {
    "decision": {"type": "string", "enum": ["APPROVE", "REJECT"]},
    "side": {"type": "string", "enum": ["LONG", "SHORT"]},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "reason_codes": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
    "summary": {"type": "string", "maxLength": 500},
}, ["decision", "side", "confidence", "reason_codes", "summary"])

EXIT_SCHEMA = _strict_object("strategy_2_exit_decision", {
    "decision": {"type": "string", "enum": ["HOLD", "EXIT"]},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "reason_codes": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
    "summary": {"type": "string", "maxLength": 500},
}, ["decision", "confidence", "reason_codes", "summary"])


def _validate_common(payload: Any, schema, expected_keys):
    if not isinstance(payload, dict) or set(payload) != set(expected_keys):
        raise DecisionSchemaError("AI response has unexpected or missing fields")
    decision = payload["decision"]
    allowed = schema["schema"]["properties"]["decision"]["enum"]
    if decision not in allowed:
        raise DecisionSchemaError("Invalid AI decision")
    confidence = payload["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise DecisionSchemaError("confidence must be a number between 0 and 1")
    if not isinstance(payload["reason_codes"], list) or not all(
        isinstance(value, str) for value in payload["reason_codes"]
    ) or len(payload["reason_codes"]) > 8:
        raise DecisionSchemaError("reason_codes must be strings")
    if not isinstance(payload["summary"], str) or len(payload["summary"]) > 500:
        raise DecisionSchemaError("summary must be a string")


@dataclass(frozen=True)
class EntryDecision:
    decision: str
    side: str
    confidence: float
    reason_codes: list[str]
    summary: str

    @classmethod
    def parse(cls, payload, expected_side):
        keys = ("decision", "side", "confidence", "reason_codes", "summary")
        _validate_common(payload, ENTRY_SCHEMA, keys)
        if payload["side"] not in {"LONG", "SHORT"} or payload["side"] != expected_side:
            raise DecisionSchemaError("AI side does not match deterministic candidate")
        return cls(**payload)

    def as_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class ExitDecision:
    decision: str
    confidence: float
    reason_codes: list[str]
    summary: str

    @classmethod
    def parse(cls, payload):
        keys = ("decision", "confidence", "reason_codes", "summary")
        _validate_common(payload, EXIT_SCHEMA, keys)
        return cls(**payload)

    def as_dict(self):
        return asdict(self)
