"""Physical action contract; no normalized or policy-facing wrapper is present."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class ActionApplication:
    raw_action_mg_per_10s: float
    applied_action_mg_per_10s: float
    action_was_clipped: bool
    propofol_rate_mg_per_min: float


def apply_propofol_action(action: float, *, minimum: float = 0.0, maximum: float = 27.7) -> ActionApplication:
    if isinstance(action, bool):
        raise ValueError("action must be a finite real scalar")
    try:
        raw = float(action)
    except (TypeError, ValueError) as exc:
        raise ValueError("action must be a finite real scalar") from exc
    if not math.isfinite(raw):
        raise ValueError("action must be a finite real scalar")
    applied = min(max(raw, minimum), maximum)
    return ActionApplication(raw, applied, applied != raw, applied * 6.0)
