"""Schnider propofol and Minto remifentanil parameter equations."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .errors import PKPDValidationError
from .profiles import PatientProfile, james_lean_body_mass_kg
from .registry import F12_BY_VARIANT, F_PRIMARY_VALUES, H_VALUES, MintoF12Variant, PARAMETER_REGISTRY_ID


@dataclass(frozen=True, slots=True)
class DrugParameters:
    """Three-compartment and effect-site parameters with explicit units."""

    drug: str
    v1_l: float
    v2_l: float
    v3_l: float
    cl1_l_per_min: float
    cl2_l_per_min: float
    cl3_l_per_min: float
    ke0_per_min: float
    amount_unit: str
    infusion_rate_unit: str
    concentration_unit: str
    parameter_registry_id: str
    variant_id: str

    def __post_init__(self) -> None:
        values = (
            self.v1_l,
            self.v2_l,
            self.v3_l,
            self.cl1_l_per_min,
            self.cl2_l_per_min,
            self.cl3_l_per_min,
            self.ke0_per_min,
        )
        if not all(math.isfinite(value) for value in values):
            raise PKPDValidationError(f"{self.drug} parameters must be finite")
        if min(self.v1_l, self.v2_l, self.v3_l) <= 0:
            raise PKPDValidationError(f"{self.drug} compartment volumes must be positive")
        if min(self.cl1_l_per_min, self.cl2_l_per_min, self.cl3_l_per_min) < 0:
            raise PKPDValidationError(f"{self.drug} clearances must be nonnegative")
        if self.ke0_per_min <= 0:
            raise PKPDValidationError(f"{self.drug} ke0 must be positive")

    @property
    def micro_rate_constants_per_min(self) -> dict[str, float]:
        return {
            "k10": self.cl1_l_per_min / self.v1_l,
            "k12": self.cl2_l_per_min / self.v1_l,
            "k13": self.cl3_l_per_min / self.v1_l,
            "k21": self.cl2_l_per_min / self.v2_l,
            "k31": self.cl3_l_per_min / self.v3_l,
        }


def schnider_propofol_parameters(profile: PatientProfile) -> DrugParameters:
    """Calculate the published Schnider covariate model in L and L/min."""

    h = H_VALUES
    lbm = james_lean_body_mass_kg(profile)
    return DrugParameters(
        drug="propofol",
        v1_l=h["h1"],
        v2_l=h["h2"] - h["h3"] * (profile.age_years - h["h4"]),
        v3_l=h["h5"],
        cl1_l_per_min=(
            h["h6"]
            + h["h7"] * (profile.weight_kg - h["h8"])
            - h["h9"] * (lbm - h["h10"])
            + h["h11"] * (profile.height_cm - h["h12"])
        ),
        cl2_l_per_min=h["h13"] - h["h14"] * (profile.age_years - h["h15"]),
        cl3_l_per_min=h["h16"],
        ke0_per_min=h["h17"],
        amount_unit="mg",
        infusion_rate_unit="mg/min",
        concentration_unit="mg/L",
        parameter_registry_id=PARAMETER_REGISTRY_ID,
        variant_id="schnider_primary",
    )


def minto_remifentanil_parameters(
    profile: PatientProfile,
    *,
    f12_variant: MintoF12Variant = MintoF12Variant.PRIMARY_MINTO_0_0301,
) -> DrugParameters:
    """Calculate Minto parameters using approved f18=55 and closed f12 variants."""

    if not isinstance(f12_variant, MintoF12Variant):
        raise PKPDValidationError("f12_variant must be an explicit MintoF12Variant")
    f = F_PRIMARY_VALUES
    f12 = F12_BY_VARIANT[f12_variant]
    lbm = james_lean_body_mass_kg(profile)
    age_delta = profile.age_years - f["f17"]
    lbm_delta = lbm - f["f18"]
    return DrugParameters(
        drug="remifentanil",
        v1_l=f["f1"] - f["f2"] * age_delta + f["f3"] * lbm_delta,
        v2_l=f["f4"] - f["f5"] * age_delta + f["f6"] * lbm_delta,
        v3_l=f["f7"],
        cl1_l_per_min=f["f8"] - f["f9"] * age_delta + f["f10"] * lbm_delta,
        cl2_l_per_min=f["f11"] - f12 * age_delta,
        cl3_l_per_min=f["f13"] - f["f14"] * age_delta,
        ke0_per_min=f["f15"] - f["f16"] * age_delta,
        amount_unit="microgram",
        infusion_rate_unit="microgram/min",
        concentration_unit="microgram/L",
        parameter_registry_id=PARAMETER_REGISTRY_ID,
        variant_id=f12_variant.value,
    )
