"""Validated, outcome-independent patient covariates for PK parameterization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import math

from .errors import PKPDValidationError


class Sex(str, Enum):
    """Biological model category used by the published James LBM equations.

    This is not the future PPO tensor encoding governed by MC-032.
    """

    MALE = "male"
    FEMALE = "female"


def _finite_number(name: str, value: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise PKPDValidationError(f"{name} must be a finite real number") from exc
    if not math.isfinite(numeric):
        raise PKPDValidationError(f"{name} must be a finite real number")
    return numeric


@dataclass(frozen=True, slots=True)
class PatientProfile:
    """Four covariates required by the Schnider and Minto equations."""

    age_years: float
    sex: Sex
    height_cm: float
    weight_kg: float

    def __post_init__(self) -> None:
        age = _finite_number("age_years", self.age_years)
        height = _finite_number("height_cm", self.height_cm)
        weight = _finite_number("weight_kg", self.weight_kg)
        if not isinstance(self.sex, Sex):
            raise PKPDValidationError("sex must be an explicit Sex enum value")
        if age <= 0:
            raise PKPDValidationError("age_years must be positive")
        if height <= 0:
            raise PKPDValidationError("height_cm must be positive")
        if weight <= 0:
            raise PKPDValidationError("weight_kg must be positive")
        object.__setattr__(self, "age_years", age)
        object.__setattr__(self, "height_cm", height)
        object.__setattr__(self, "weight_kg", weight)

    @property
    def identifier(self) -> str:
        payload = (
            f"age={self.age_years:.12g}|sex={self.sex.value}|"
            f"height_cm={self.height_cm:.12g}|weight_kg={self.weight_kg:.12g}"
        )
        return "profile-" + hashlib.sha256(payload.encode("ascii")).hexdigest()[:16]


def james_lean_body_mass_kg(profile: PatientProfile) -> float:
    """Return James lean body mass with the approved squared term (MC-001)."""

    ratio_squared = (profile.weight_kg / profile.height_cm) ** 2
    if profile.sex is Sex.MALE:
        value = 1.1 * profile.weight_kg - 128.0 * ratio_squared
    elif profile.sex is Sex.FEMALE:
        value = 1.07 * profile.weight_kg - 148.0 * ratio_squared
    else:  # pragma: no cover - enum and profile validation make this unreachable.
        raise PKPDValidationError("unsupported sex category")
    if not math.isfinite(value) or value <= 0:
        raise PKPDValidationError("James lean body mass is nonpositive for this profile")
    return value
