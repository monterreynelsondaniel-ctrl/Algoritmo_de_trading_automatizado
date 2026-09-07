"""Compatibility imports for the historical Strategy 1 signal API.

New application code should select Strategy 1 through ``strategies.registry``.
This module remains temporarily to avoid breaking existing scripts and imports.
"""

from strategies.strategy_1.signals import (
    detect_historical_reversals,
    detect_sqzmom_reversal,
    generate_signal,
)

__all__ = [
    "detect_historical_reversals",
    "detect_sqzmom_reversal",
    "generate_signal",
]
