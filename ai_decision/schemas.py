"""Strict, versioned schemas. AI output is untrusted until validated here."""

from dataclasses import asdict, dataclass
from typing import Any


SCHEMA_VERSION_V1 = "1.0.0"
SCHEMA_VERSION_V2 = "1.1.0"
SCHEMA_VERSION = SCHEMA_VERSION_V1


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


ENTRY_SCHEMA_V1 = _strict_object("strategy_2_entry_decision", {
    "decision": {"type": "string", "enum": ["APPROVE", "REJECT"]},
    "side": {"type": "string", "enum": ["LONG", "SHORT"]},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "reason_codes": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
    "summary": {"type": "string", "maxLength": 500},
}, ["decision", "side", "confidence", "reason_codes", "summary"])
ENTRY_SCHEMA = ENTRY_SCHEMA_V1

ENTRY_REASON_CODES_V2 = (
    "TREND_ALIGNED", "TREND_CONFLICT",
    "SETUP_CONFIRMED", "SETUP_WEAK",
    "CONFIRMATION_STRONG", "CONFIRMATION_WEAK",
    "DMI_ALIGNED", "DMI_CONFLICT",
    "ADX_STRONG", "ADX_WEAK",
    "EMA_ALIGNED", "EMA_CONFLICT",
    "MOMENTUM_REVERSAL_CLEAR", "MOMENTUM_REVERSAL_WEAK",
)

ENTRY_SCHEMA_V2 = _strict_object("strategy_2_entry_decision_v2", {
    "decision": {"type": "string", "enum": ["APPROVE", "REJECT"]},
    "side": {"type": "string", "enum": ["LONG", "SHORT"]},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "reason_codes": {
        "type": "array",
        "items": {"type": "string", "enum": list(ENTRY_REASON_CODES_V2)},
        "maxItems": 8,
    },
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
    def parse(cls, payload, expected_side, schema=ENTRY_SCHEMA,
              allowed_reason_codes=None):
        keys = ("decision", "side", "confidence", "reason_codes", "summary")
        _validate_common(payload, schema, keys)
        if payload["side"] not in {"LONG", "SHORT"} or payload["side"] != expected_side:
            raise DecisionSchemaError("AI side does not match deterministic candidate")
        if allowed_reason_codes is not None and not set(payload["reason_codes"]).issubset(
                set(allowed_reason_codes)):
            raise DecisionSchemaError("AI reason_codes are outside the controlled vocabulary")
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
