"""Caching, bounded retries and fail-closed validation around AI calls."""

import hashlib
import json
import time

from ai_decision.prompts import (
    ENTRY_PROMPT_VERSION, ENTRY_SYSTEM_PROMPT, EXIT_PROMPT_VERSION, EXIT_SYSTEM_PROMPT,
)
from ai_decision.schemas import ENTRY_SCHEMA, EXIT_SCHEMA, SCHEMA_VERSION, EntryDecision, ExitDecision


class AIDecisionUnavailableError(RuntimeError):
    pass


class DecisionService:
    def __init__(self, client, store, *, model, provider="openai", reasoning_effort="low", mode="replay",
                 max_attempts=2, sleep=time.sleep):
        if mode not in {"live", "replay"}:
            raise ValueError("AI mode must be 'live' or 'replay'")
        self.client, self.store, self.model, self.provider = client, store, model, provider
        self.reasoning_effort, self.mode = reasoning_effort, mode
        self.max_attempts, self.sleep = max_attempts, sleep

    def _key(self, kind, payload, prompt_version):
        envelope = {"kind": kind, "payload": payload, "provider": self.provider, "model": self.model,
                    "reasoning": self.reasoning_effort, "prompt": prompt_version,
                    "schema": SCHEMA_VERSION}
        return hashlib.sha256(json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

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

    def _review(self, kind, payload, prompt, prompt_version, schema, parser):
        key = self._key(kind, payload, prompt_version)
        cached = self.store.get(key)
        if cached:
            response, metadata = cached
            decision = parser(response)
            self.store.audit(key, "cache", "OK", {**metadata, "cache_hit": True})
            return decision
        if self.mode == "replay":
            self.store.audit(key, "replay", "MISS", {})
            raise AIDecisionUnavailableError(f"Missing cached {kind} decision: {key}")
        if self.client is None:
            raise AIDecisionUnavailableError("Live AI mode requires a configured client")
        last_error = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response, response_metadata = self.client.structured_response(
                    model=self.model, system_prompt=prompt, payload=payload,
                    schema=schema, reasoning_effort=self.reasoning_effort,
                )
                decision = parser(response)
                provider_metadata = response_metadata if isinstance(response_metadata, dict) else {
                    "response_id": response_metadata
                }
                metadata = {**provider_metadata, "attempt": attempt, "provider": self.provider,
                            "model": self.model, "prompt_version": prompt_version,
                            "schema_version": SCHEMA_VERSION}
                self.store.put(key, kind, payload, decision.as_dict(), metadata)
                self.store.audit(key, "live", "OK", {**metadata, "cache_hit": False})
                return decision
            except Exception as error:
                last_error = error
                if not self._retryable(error) or attempt == self.max_attempts:
                    break
                retry_after = getattr(error, "retry_after", None)
                self.sleep(float(retry_after) if retry_after else 2 ** (attempt - 1))
        self.store.audit(key, "live", "ERROR", {"error_type": type(last_error).__name__})
        raise AIDecisionUnavailableError(f"{kind} decision unavailable") from last_error

    def review_entry(self, payload):
        side = payload["candidate"]["side"]
        return self._review("ENTRY", payload, ENTRY_SYSTEM_PROMPT, ENTRY_PROMPT_VERSION,
                            ENTRY_SCHEMA, lambda value: EntryDecision.parse(value, side))

    def review_exit(self, payload):
        return self._review("EXIT", payload, EXIT_SYSTEM_PROMPT, EXIT_PROMPT_VERSION,
                            EXIT_SCHEMA, ExitDecision.parse)
