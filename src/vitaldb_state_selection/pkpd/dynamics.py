"""Amount-state dynamics and exact zero-order-hold transitions."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy.linalg import expm

from .errors import PKPDValidationError
from .parameters import DrugParameters


NEGATIVE_NUMERICAL_TOLERANCE = 1e-10


@dataclass(frozen=True, slots=True)
class _CompartmentState:
    """A1/A2/A3 amounts and Ce concentration for one drug."""

    a1_amount: float = 0.0
    a2_amount: float = 0.0
    a3_amount: float = 0.0
    ce_concentration: float = 0.0

    def __post_init__(self) -> None:
        values = self.as_tuple()
        if not all(math.isfinite(value) for value in values):
            raise PKPDValidationError("compartment state must be finite")
        if min(values) < -NEGATIVE_NUMERICAL_TOLERANCE:
            raise PKPDValidationError("compartment state cannot be negative")

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.a1_amount, self.a2_amount, self.a3_amount, self.ce_concentration)

    def plasma_concentration(self, parameters: DrugParameters) -> float:
        return self.a1_amount / parameters.v1_l


def _transition_matrix_per_minute(parameters: DrugParameters) -> np.ndarray:
    """Return the four-state amount/Ce system matrix on a minute basis."""

    k = parameters.micro_rate_constants_per_min
    return np.array(
        [
            [-(k["k10"] + k["k12"] + k["k13"]), k["k21"], k["k31"], 0.0],
            [k["k12"], -k["k21"], 0.0, 0.0],
            [k["k13"], 0.0, -k["k31"], 0.0],
            [parameters.ke0_per_min / parameters.v1_l, 0.0, 0.0, -parameters.ke0_per_min],
        ],
        dtype=float,
    )


def _finite_nonnegative(name: str, value: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise PKPDValidationError(f"{name} must be finite and nonnegative") from exc
    if not math.isfinite(numeric) or numeric < 0:
        raise PKPDValidationError(f"{name} must be finite and nonnegative")
    return numeric


def _exact_zoh_transition(
    state: _CompartmentState,
    parameters: DrugParameters,
    *,
    duration_seconds: float,
    infusion_rate_per_minute: float,
) -> _CompartmentState:
    """Advance one drug exactly for a constant infusion using an augmented expm.

    Published volumes, clearances, and ke0 are minute-based. The requested
    duration is explicitly converted from seconds to minutes before applying the
    exact matrix exponential. No Euler substep is used.
    """

    duration = _finite_nonnegative("duration_seconds", duration_seconds)
    if duration <= 0:
        raise PKPDValidationError("duration_seconds must be positive")
    rate = _finite_nonnegative("infusion_rate_per_minute", infusion_rate_per_minute)

    augmented = np.zeros((5, 5), dtype=float)
    augmented[:4, :4] = _transition_matrix_per_minute(parameters)
    augmented[0, 4] = rate
    initial = np.array((*state.as_tuple(), 1.0), dtype=float)
    result = expm(augmented * (duration / 60.0)) @ initial
    values = result[:4]
    if not np.all(np.isfinite(values)):
        raise PKPDValidationError("exact transition produced a nonfinite state")
    if float(np.min(values)) < -NEGATIVE_NUMERICAL_TOLERANCE:
        raise PKPDValidationError("exact transition produced a negative state")
    values[np.abs(values) <= NEGATIVE_NUMERICAL_TOLERANCE] = 0.0
    return _CompartmentState(*(float(value) for value in values))
