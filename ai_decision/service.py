"""Caching, bounded retries and fail-closed validation around AI calls."""

import hashlib
import json
import time

from ai_decision.budget import (
    AIBudgetExceededError, conservative_token_upper_bound, estimate_tokens,
)
from ai_decision.entry_reviews import get_entry_review_contract

from ai_decision.prompts import EXIT_PROMPT_VERSION, EXIT_SYSTEM_PROMPT
from ai_decision.schemas import EXIT_SCHEMA, SCHEMA_VERSION, ExitDecision
from ai_decision.store import PendingAIRequestError


class AIDecisionUnavailableError(RuntimeError):
    pass


class AIRequestStateUnknownError(AIDecisionUnavailableError):
    pass


class DecisionService:
    def __init__(self, client, store, *, model, provider="openai", reasoning_effort="low", mode="replay",
                 max_attempts=2, sleep=time.sleep, budget=None, run_manager=None,
                 max_output_tokens=300, entry_review_version="v1"):
        if mode not in {"live", "replay"}:
            raise ValueError("AI mode must be 'live' or 'replay'")
        self.client, self.store, self.model, self.provider = client, store, model, provider
        self.reasoning_effort, self.mode = reasoning_effort, mode
        self.max_attempts, self.sleep = max_attempts, sleep
        self.budget, self.run_manager = budget, run_manager
        self.max_output_tokens = int(max_output_tokens)
        self.entry_review = get_entry_review_contract(entry_review_version)

    @property
    def entry_prompt_version(self):
        return self.entry_review.prompt_version

    @property
    def entry_schema_version(self):
        return self.entry_review.schema_version

    def _key(self, kind, payload, prompt_version, schema_version):
        envelope = {"kind": kind, "payload": payload, "provider": self.provider, "model": self.model,
                    "reasoning": self.reasoning_effort, "prompt": prompt_version,
                    "schema": schema_version}
        return hashlib.sha256(json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def cache_key(self, kind, payload):
        versions = {
            "ENTRY": (self.entry_prompt_version, self.entry_schema_version),
            "EXIT": (EXIT_PROMPT_VERSION, SCHEMA_VERSION),
        }
        return self._key(kind, payload, *versions[kind])

    @staticmethod
    def estimated_input_tokens(prompt, payload, schema):
        values = DecisionService._serialized_request_parts(prompt, payload, schema)
        return estimate_tokens(*values)

    @staticmethod
    def input_token_upper_bound(prompt, payload, schema):
        values = DecisionService._serialized_request_parts(prompt, payload, schema)
        return conservative_token_upper_bound(*values)

    @staticmethod
    def _serialized_request_parts(prompt, payload, schema):
        return (prompt,
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                json.dumps(schema, sort_keys=True, separators=(",", ":")))

    @staticmethod
    def _retryable(error):
        code = getattr(error, "code", None)
        body = getattr(error, "body", None)
        if isinstance(body, dict):
            code = code or body.get("code") or body.get("error", {}).get("code")
        if code in {"insufficient_quota", "billing_hard_limit_reached"}:
            return False
        status = getattr(error, "status_code", None)
        return isinstance(error, (TimeoutError, ConnectionError)) or status == 429 or (
            isinstance(status, int) and status >= 500
        )

    def _review(self, kind, payload, prompt, prompt_version, schema_version, schema, parser):
        key = self._key(kind, payload, prompt_version, schema_version)
        cached = self.store.get(key)
        if cached:
            response, metadata = cached
            decision = parser(response)
            self.store.audit(key, "cache", "OK", {**metadata, "cache_hit": True})
            if self.budget:
                self.budget.cache_hit()
            return decision
        if self.mode == "replay":
            self.store.audit(key, "replay", "MISS", {})
            raise AIDecisionUnavailableError(f"Missing cached {kind} decision: {key}")
        if self.client is None:
            raise AIDecisionUnavailableError("Live AI mode requires a configured client")
        last_error = None
        input_tokens = self.input_token_upper_bound(prompt, payload, schema)
        for attempt in range(1, self.max_attempts + 1):
            try:
                if self.budget:
                    self.budget.authorize(input_tokens)
                self.store.mark_pending(
                    key, getattr(self.run_manager, "run_id", None), kind, attempt,
                    {"provider": self.provider, "model": self.model},
                )
                response, response_metadata = self.client.structured_response(
                    model=self.model, system_prompt=prompt, payload=payload,
                    schema=schema, reasoning_effort=self.reasoning_effort,
                    max_output_tokens=self.max_output_tokens,
                )
                decision = parser(response)
                provider_metadata = response_metadata if isinstance(response_metadata, dict) else {
                    "response_id": response_metadata
                }
                metadata = {**provider_metadata, "attempt": attempt, "provider": self.provider,
                            "model": self.model, "prompt_version": prompt_version,
                            "schema_version": schema_version}
                self.store.persist_decision(key, kind, payload, decision.as_dict(), metadata)
                if self.budget:
                    self.budget.reconcile_usage(input_tokens, provider_metadata.get("usage"))
                return decision
            except Exception as error:
                last_error = error
                if isinstance(error, PendingAIRequestError):
                    self.store.audit(key, "live", "BLOCKED_PENDING", {})
                    raise AIDecisionUnavailableError(
                        f"{kind} has an unresolved prior request; refusing a duplicate call"
                    ) from error
                if isinstance(error, (TimeoutError, ConnectionError)):
                    self.store.mark_pending_unknown(key, {"error_type": type(error).__name__})
                    self.store.audit(key, "live", "UNKNOWN", {"error_type": type(error).__name__})
                    raise AIRequestStateUnknownError(
                        f"{kind} response state is unknown; manual resolution is required before retry"
                    ) from error
                self.store.mark_pending_failed(key, {"error_type": type(error).__name__})
                if isinstance(error, AIBudgetExceededError):
                    self.store.audit(key, "live", "BUDGET_STOP", {"error_type": type(error).__name__})
                    raise AIDecisionUnavailableError(f"{kind} stopped by local AI budget") from error
                if not self._retryable(error) or attempt == self.max_attempts:
                    break
                retry_after = getattr(error, "retry_after", None)
                self.sleep(float(retry_after) if retry_after else 2 ** (attempt - 1))
        self.store.audit(key, "live", "ERROR", {"error_type": type(last_error).__name__})
        raise AIDecisionUnavailableError(f"{kind} decision unavailable") from last_error

    def review_entry(self, payload):
        side = payload["candidate"]["side"]
        contract = self.entry_review
        return self._review(
            "ENTRY", payload, contract.system_prompt, contract.prompt_version,
            contract.schema_version, contract.schema,
            lambda value: contract.parse(value, side),
        )

    def review_exit(self, payload):
        return self._review("EXIT", payload, EXIT_SYSTEM_PROMPT, EXIT_PROMPT_VERSION,
                            SCHEMA_VERSION, EXIT_SCHEMA, ExitDecision.parse)
