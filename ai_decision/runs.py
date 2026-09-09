"""Small local run identity and checkpoint layer for resumable AI research."""

from dataclasses import asdict, dataclass
import hashlib
import json
import uuid


class AIRunConfigurationMismatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class AIRunIdentity:
    strategy_version: str
    bundle_name: str
    bundle_hash: str
    provider: str
    model: str
    reasoning_effort: str
    entry_prompt_version: str
    exit_prompt_version: str
    schema_version: str
    ai_mode: str

    def canonical_json(self):
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def fingerprint(self):
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


class AIRunManager:
    def __init__(self, store, identity, run_id=None):
        self.store, self.identity = store, identity
        self.run_id = run_id or str(uuid.uuid4())

    def start(self):
        current = self.store.get_run(self.run_id)
        if current is None:
            self.store.create_run(self.run_id, self.identity.canonical_json(), self.identity.fingerprint())
        elif current["identity_hash"] != self.identity.fingerprint():
            raise AIRunConfigurationMismatchError(
                "Cannot resume: strategy, bundle, model, reasoning, prompts, schema, or mode changed"
            )
        elif current["status"] == "COMPLETED":
            raise RuntimeError("Completed AI runs cannot be resumed; start a new run")
        self.store.update_run(self.run_id, status="RUNNING")
        return self.store.get_run(self.run_id)

    def checkpoint(self, event_time):
        value = event_time.isoformat() if hasattr(event_time, "isoformat") else str(event_time)
        self.store.update_run(self.run_id, last_event=value)

    def increment(self, **values):
        self.store.update_run(self.run_id, **values)

    def counters(self):
        row = self.store.get_run(self.run_id)
        return {name: row[name] for name in (
            "live_calls", "cache_hits", "input_tokens", "output_tokens",
            "estimated_cost_usd", "actual_cost_usd"
        )}

    def complete(self):
        self.store.update_run(self.run_id, status="COMPLETED")

    def interrupt(self, detail=None):
        self.store.update_run(self.run_id, status="INTERRUPTED", detail=detail or {})

    def fail(self, detail=None):
        self.store.update_run(self.run_id, status="FAILED", detail=detail or {})

    def record(self):
        return self.store.get_run(self.run_id)
