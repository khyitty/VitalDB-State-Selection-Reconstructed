"""Fixed-order S0/S1 observation construction."""

from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np

from vitaldb_state_selection.pkpd import PatientProfile, Sex, SimulationTransition

from .config import StateID
from .observation import BISObservationProcessor, VisibleBIS


OFFSETS = (-50.0, -40.0, -30.0, -20.0, -10.0, 0.0)
S0_FIELDS = (
    "age_years", "sex_binary", "height_cm", "weight_kg",
    *(name for offset in OFFSETS for name in (
        f"bis_value_t{int(offset):+d}", f"bis_mask_t{int(offset):+d}", f"bis_age_seconds_t{int(offset):+d}")),
    *(f"propofol_dose_mg_t{int(offset):+d}" for offset in OFFSETS),
    *(f"remifentanil_rate_microgram_per_min_t{int(offset):+d}" for offset in OFFSETS),
)
S1_EXTRA_FIELDS = (
    "propofol_recent_dose_60s_mg", "remifentanil_recent_dose_60s_microgram",
    "propofol_cumulative_dose_mg", "remifentanil_cumulative_dose_microgram",
    "propofol_cp_mg_per_l", "propofol_ce_mg_per_l",
    "remifentanil_cp_microgram_per_l", "remifentanil_ce_microgram_per_l",
)
S1_FIELDS = S0_FIELDS + S1_EXTRA_FIELDS


@dataclass(frozen=True, slots=True)
class CompletedDrugInterval:
    end_seconds: float
    propofol_dose_mg: float
    remifentanil_rate_microgram_per_min: float
    remifentanil_dose_microgram: float


@dataclass(frozen=True, slots=True)
class BuiltState:
    vector: np.ndarray
    current_visible_bis: VisibleBIS
    field_names: tuple[str, ...]


def _sex_binary(profile: PatientProfile) -> float:
    if profile.sex is Sex.FEMALE:
        return 0.0
    if profile.sex is Sex.MALE:
        return 1.0
    raise ValueError("unsupported sex category")


def _six_completed(records: tuple[CompletedDrugInterval, ...]) -> tuple[CompletedDrugInterval | None, ...]:
    values: list[CompletedDrugInterval | None] = [None] * max(0, 6 - len(records))
    values.extend(records[-6:])
    return tuple(values)


def build_state(
    *, state_id: StateID, profile: PatientProfile, elapsed_seconds: float,
    bis_processor: BISObservationProcessor, intervals: tuple[CompletedDrugInterval, ...],
    transition: SimulationTransition | None,
) -> BuiltState:
    visible = tuple(bis_processor.query(elapsed_seconds + offset) for offset in OFFSETS)
    values: list[float] = [profile.age_years, _sex_binary(profile), profile.height_cm, profile.weight_kg]
    for point in visible:
        values.extend((point.value, point.mask, point.age_seconds))
    completed = _six_completed(intervals)
    values.extend(0.0 if item is None else item.propofol_dose_mg for item in completed)
    values.extend(0.0 if item is None else item.remifentanil_rate_microgram_per_min for item in completed)
    fields = S0_FIELDS
    if state_id is StateID.S1:
        recent = tuple(item for item in intervals if elapsed_seconds - 60.0 < item.end_seconds <= elapsed_seconds)
        prop_recent = sum(item.propofol_dose_mg for item in recent)
        remi_recent = sum(item.remifentanil_dose_microgram for item in recent)
        prop_cumulative = sum(item.propofol_dose_mg for item in intervals)
        remi_cumulative = sum(item.remifentanil_dose_microgram for item in intervals)
        if transition is None:
            concentrations = (0.0, 0.0, 0.0, 0.0)
        else:
            concentrations = (
                transition.propofol_cp_mg_per_l, transition.propofol_ce_mg_per_l,
                transition.remifentanil_cp_microgram_per_l,
                transition.remifentanil_ce_microgram_per_l,
            )
        values.extend((prop_recent, remi_recent, prop_cumulative, remi_cumulative, *concentrations))
        fields = S1_FIELDS
    vector = np.asarray(values, dtype=np.float64)
    if vector.ndim != 1 or len(vector) != len(fields) or not np.isfinite(vector).all():
        raise RuntimeError("state vector invariant violated")
    return BuiltState(vector, visible[-1], fields)
