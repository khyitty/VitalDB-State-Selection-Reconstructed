"""Paper-grounded deterministic PK/PD scientific core.

This package is research-only. It contains no environment, policy, reward,
patient-data adapter, or clinical dosing recommendation.
"""

from .bis import deterministic_bis
from .core import DualDrugSimulator, SimulationTransition, diagnostic_trajectory
from .errors import PKPDValidationError
from .parameters import DrugParameters, minto_remifentanil_parameters, schnider_propofol_parameters
from .profiles import PatientProfile, Sex, james_lean_body_mass_kg
from .registry import MintoF12Variant, PARAMETER_REGISTRY_ID

__all__ = [
    "DrugParameters",
    "DualDrugSimulator",
    "MintoF12Variant",
    "PARAMETER_REGISTRY_ID",
    "PKPDValidationError",
    "PatientProfile",
    "Sex",
    "SimulationTransition",
    "deterministic_bis",
    "diagnostic_trajectory",
    "james_lean_body_mass_kg",
    "minto_remifentanil_parameters",
    "schnider_propofol_parameters",
]
