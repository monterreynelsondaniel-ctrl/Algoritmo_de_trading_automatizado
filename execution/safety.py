from dataclasses import dataclass
from threading import Lock
from typing import Optional


@dataclass(frozen=True)
class KillSwitchState:
    active: bool
    reason: Optional[str]


class KillSwitch:
    """One-way runtime latch; only an explicit human action may reset it."""

    def __init__(self, state_store=None):
        self._state_store = state_store
        persisted_reason = (
            state_store.get_value("kill_switch_reason") if state_store else None
        )
        self._active = (
            state_store.get_value("kill_switch_active", "false") == "true"
            if state_store else False
        )
        self._reason = persisted_reason
        self._lock = Lock()

    def activate(self, reason: str) -> None:
        with self._lock:
            self._active = True
            self._reason = reason
            if self._state_store:
                self._state_store.set_value("kill_switch_reason", reason)
                self._state_store.set_value("kill_switch_active", "true")

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    def snapshot(self) -> KillSwitchState:
        with self._lock:
            return KillSwitchState(self._active, self._reason)

    def reset(self) -> None:
        """Explicit human-operated reset after the underlying issue is audited."""
        with self._lock:
            self._active = False
            self._reason = None
            if self._state_store:
                self._state_store.set_value("kill_switch_active", "false")
                self._state_store.set_value("kill_switch_reason", "")
