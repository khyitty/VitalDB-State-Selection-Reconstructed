"""Pure dual-drug deterministic simulator assembled from the scientific core."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math

from .bis import deterministic_bis
from .dynamics import _CompartmentState, _exact_zoh_transition
from .errors import PKPDValidationError
from .parameters import DrugParameters, minto_remifentanil_parameters, schnider_propofol_parameters
from .profiles import PatientProfile
from .registry import MintoF12Variant, PARAMETER_REGISTRY_ID


@dataclass(frozen=True, slots=True)
class _DualDrugState:
    """Immutable simulator state for both independent PK/PD systems."""

    elapsed_seconds: float = 0.0
    propofol: _CompartmentState = _CompartmentState()
    remifentanil: _CompartmentState = _CompartmentState()

    def __post_init__(self) -> None:
        if not math.isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0:
            raise PKPDValidationError("elapsed_seconds must be finite and nonnegative")


@dataclass(frozen=True, slots=True)
class SimulationTransition:
    """One exact transition and the immutable simulator to use for continuation."""

    duration_seconds: float
    elapsed_seconds: float
    propofol_a1_mg: float
    propofol_a2_mg: float
    propofol_a3_mg: float
    propofol_cp_mg_per_l: float
    propofol_ce_mg_per_l: float
    remifentanil_a1_microgram: float
    remifentanil_a2_microgram: float
    remifentanil_a3_microgram: float
    remifentanil_cp_microgram_per_l: float
    remifentanil_ce_microgram_per_l: float
    deterministic_bis_index: float
    profile_id: str
    parameter_registry_id: str
    propofol_parameter_id: str
    remifentanil_parameter_id: str
    next_simulator: "DualDrugSimulator"


@dataclass(frozen=True, slots=True)
class DualDrugSimulator:
    """Immutable paper-grounded Stage I simulator; ``advance`` never mutates self."""

    profile: PatientProfile
    propofol_parameters: DrugParameters
    remifentanil_parameters: DrugParameters
    _state: _DualDrugState = _DualDrugState()

    @classmethod
    def from_profile(
        cls,
        profile: PatientProfile,
        *,
        minto_f12_variant: MintoF12Variant = MintoF12Variant.PRIMARY_MINTO_0_0301,
    ) -> "DualDrugSimulator":
        return cls(
            profile=profile,
            propofol_parameters=schnider_propofol_parameters(profile),
            remifentanil_parameters=minto_remifentanil_parameters(
                profile, f12_variant=minto_f12_variant
            ),
        )

    def advance(
        self,
        duration_seconds: float,
        propofol_rate_mg_per_min: float,
        remifentanil_rate_microgram_per_min: float,
    ) -> SimulationTransition:
        """Apply two constant, explicitly unit-labeled infusions for one duration."""

        propofol = _exact_zoh_transition(
            self._state.propofol,
            self.propofol_parameters,
            duration_seconds=duration_seconds,
            infusion_rate_per_minute=propofol_rate_mg_per_min,
        )
        remifentanil = _exact_zoh_transition(
            self._state.remifentanil,
            self.remifentanil_parameters,
            duration_seconds=duration_seconds,
            infusion_rate_per_minute=remifentanil_rate_microgram_per_min,
        )
        elapsed = self._state.elapsed_seconds + float(duration_seconds)
        next_state = _DualDrugState(elapsed, propofol, remifentanil)
        next_simulator = replace(self, _state=next_state)
        propofol_cp = propofol.plasma_concentration(self.propofol_parameters)
        remifentanil_cp = remifentanil.plasma_concentration(self.remifentanil_parameters)
        return SimulationTransition(
            duration_seconds=float(duration_seconds),
            elapsed_seconds=elapsed,
            propofol_a1_mg=propofol.a1_amount,
            propofol_a2_mg=propofol.a2_amount,
            propofol_a3_mg=propofol.a3_amount,
            propofol_cp_mg_per_l=propofol_cp,
            propofol_ce_mg_per_l=propofol.ce_concentration,
            remifentanil_a1_microgram=remifentanil.a1_amount,
            remifentanil_a2_microgram=remifentanil.a2_amount,
            remifentanil_a3_microgram=remifentanil.a3_amount,
            remifentanil_cp_microgram_per_l=remifentanil_cp,
            remifentanil_ce_microgram_per_l=remifentanil.ce_concentration,
            deterministic_bis_index=deterministic_bis(
                propofol.ce_concentration, remifentanil.ce_concentration
            ),
            profile_id=self.profile.identifier,
            parameter_registry_id=PARAMETER_REGISTRY_ID,
            propofol_parameter_id=self.propofol_parameters.variant_id,
            remifentanil_parameter_id=self.remifentanil_parameters.variant_id,
            next_simulator=next_simulator,
        )


def diagnostic_trajectory(
    simulator: DualDrugSimulator,
    *,
    duration_seconds: int,
    propofol_rate_mg_per_min: float,
    remifentanil_rate_microgram_per_min: float,
) -> tuple[SimulationTransition, ...]:
    """Return exact one-second diagnostic snapshots without changing the input."""

    if isinstance(duration_seconds, bool) or not isinstance(duration_seconds, int) or duration_seconds <= 0:
        raise PKPDValidationError("diagnostic duration_seconds must be a positive integer")
    current = simulator
    snapshots: list[SimulationTransition] = []
    for _ in range(duration_seconds):
        step = current.advance(
            1.0,
            propofol_rate_mg_per_min,
            remifentanil_rate_microgram_per_min,
        )
        snapshots.append(step)
        current = step.next_simulator
    return tuple(snapshots)
