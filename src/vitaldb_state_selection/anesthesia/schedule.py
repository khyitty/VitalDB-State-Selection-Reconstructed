"""Synthetic deterministic remifentanil schedules with exact ZOH semantics."""

from __future__ import annotations

from dataclasses import dataclass
import bisect
import math


def _rate(value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError("remifentanil rate must be finite and nonnegative")
    return value


@dataclass(frozen=True, slots=True)
class ConstantRemifentanilSchedule:
    rate: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "rate", _rate(self.rate))

    def rate_microgram_per_min(self, time_seconds: float) -> float:
        if not math.isfinite(float(time_seconds)) or float(time_seconds) < 0:
            raise ValueError("time must be finite and nonnegative")
        return self.rate

    def change_times(self, start_seconds: float, end_seconds: float) -> tuple[float, ...]:
        return ()


@dataclass(frozen=True, slots=True)
class PiecewiseConstantRemifentanilSchedule:
    """Right-continuous knots: a knot's rate applies on [knot, next knot)."""

    knots: tuple[tuple[float, float], ...]

    def __post_init__(self) -> None:
        normalized = tuple((float(t), _rate(r)) for t, r in self.knots)
        if not normalized or normalized[0][0] != 0.0:
            raise ValueError("piecewise schedule must start at time zero")
        times = tuple(t for t, _ in normalized)
        if any(not math.isfinite(t) or t < 0 for t in times) or tuple(sorted(times)) != times:
            raise ValueError("schedule timestamps must be finite, nonnegative, and sorted")
        if len(set(times)) != len(times):
            raise ValueError("schedule timestamps must be unique")
        object.__setattr__(self, "knots", normalized)

    def rate_microgram_per_min(self, time_seconds: float) -> float:
        time = float(time_seconds)
        if not math.isfinite(time) or time < 0:
            raise ValueError("time must be finite and nonnegative")
        times = tuple(t for t, _ in self.knots)
        return self.knots[bisect.bisect_right(times, time) - 1][1]

    def change_times(self, start_seconds: float, end_seconds: float) -> tuple[float, ...]:
        return tuple(t for t, _ in self.knots if start_seconds < t < end_seconds)
