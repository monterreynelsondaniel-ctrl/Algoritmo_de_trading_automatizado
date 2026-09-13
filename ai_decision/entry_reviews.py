"""Versioned ENTRY review contracts; historical V1 remains immutable."""

from dataclasses import dataclass

from ai_decision.prompts import (
    ENTRY_PROMPT_VERSION_V1, ENTRY_PROMPT_VERSION_V2,
    ENTRY_SYSTEM_PROMPT_V1, ENTRY_SYSTEM_PROMPT_V2,
)
from ai_decision.schemas import (
    ENTRY_REASON_CODES_V2, ENTRY_SCHEMA_V1, ENTRY_SCHEMA_V2,
    SCHEMA_VERSION_V1, SCHEMA_VERSION_V2, EntryDecision,
)


@dataclass(frozen=True)
class EntryReviewContract:
    name: str
    prompt_version: str
    system_prompt: str
    schema_version: str
    schema: dict
    controlled_reason_codes: tuple[str, ...] | None = None

    def parse(self, payload, expected_side):
        return EntryDecision.parse(
            payload, expected_side, self.schema, self.controlled_reason_codes,
        )


ENTRY_REVIEW_V1 = EntryReviewContract(
    "v1", ENTRY_PROMPT_VERSION_V1, ENTRY_SYSTEM_PROMPT_V1,
    SCHEMA_VERSION_V1, ENTRY_SCHEMA_V1,
)
ENTRY_REVIEW_V2 = EntryReviewContract(
    "v2", ENTRY_PROMPT_VERSION_V2, ENTRY_SYSTEM_PROMPT_V2,
    SCHEMA_VERSION_V2, ENTRY_SCHEMA_V2, ENTRY_REASON_CODES_V2,
)

ENTRY_REVIEW_CONTRACTS = {
    ENTRY_REVIEW_V1.name: ENTRY_REVIEW_V1,
    ENTRY_REVIEW_V2.name: ENTRY_REVIEW_V2,
    ENTRY_REVIEW_V1.prompt_version: ENTRY_REVIEW_V1,
    ENTRY_REVIEW_V2.prompt_version: ENTRY_REVIEW_V2,
}


def get_entry_review_contract(version="v1"):
    try:
        return ENTRY_REVIEW_CONTRACTS[version]
    except KeyError as error:
        raise ValueError(f"Unknown Strategy 2 ENTRY review version: {version}") from error
