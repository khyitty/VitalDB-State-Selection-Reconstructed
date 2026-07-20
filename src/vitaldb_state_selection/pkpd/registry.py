"""Versioned constants, units, and provenance for Phase 7F Stage I."""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType


PARAMETER_REGISTRY_ID = "phase7f-pkpd-v1"

H_VALUES = MappingProxyType(
    {
        "h1": 4.27,
        "h2": 18.9,
        "h3": 0.391,
        "h4": 53.0,
        "h5": 238.0,
        "h6": 1.89,
        "h7": 0.0456,
        "h8": 77.0,
        "h9": 0.0681,
        "h10": 59.0,
        "h11": 0.0264,
        "h12": 177.0,
        "h13": 1.29,
        "h14": 0.024,
        "h15": 53.0,
        "h16": 0.836,
        "h17": 0.456,
    }
)

F_PRIMARY_VALUES = MappingProxyType(
    {
        "f1": 5.1,
        "f2": 0.0201,
        "f3": 0.072,
        "f4": 9.82,
        "f5": 0.0811,
        "f6": 0.108,
        "f7": 5.42,
        "f8": 2.6,
        "f9": 0.0162,
        "f10": 0.0191,
        "f11": 2.05,
        "f12": 0.0301,
        "f13": 0.076,
        "f14": 0.00113,
        "f15": 0.595,
        "f16": 0.007,
        "f17": 40.0,
        "f18": 55.0,
    }
)


class MintoF12Variant(str, Enum):
    """Closed f12 configurations; arbitrary numeric variants are prohibited."""

    PRIMARY_MINTO_0_0301 = "primary_minto_0.0301"
    SENSITIVITY_YUN_0_030 = "sensitivity_yun_0.030"


F12_BY_VARIANT = MappingProxyType(
    {
        MintoF12Variant.PRIMARY_MINTO_0_0301: 0.0301,
        MintoF12Variant.SENSITIVITY_YUN_0_030: 0.030,
    }
)

UNIT_CONTRACT = MappingProxyType(
    {
        "time_parameter_basis": "minute",
        "transition_input_time": "second",
        "propofol_amount": "mg",
        "propofol_infusion_rate": "mg/min",
        "propofol_cp": "mg/L",
        "propofol_ce": "mg/L",
        "remifentanil_amount": "microgram",
        "remifentanil_infusion_rate": "microgram/min",
        "remifentanil_cp": "microgram/L",
        "remifentanil_ce": "microgram/L",
        "volume": "L",
        "clearance": "L/min",
        "rate_constant": "1/min",
        "bis": "index",
    }
)

BIS_PARAMETERS = MappingProxyType(
    {
        "baseline": 98.0,
        "propofol_ce50_mg_per_l": 4.47,
        "remifentanil_ce50_microgram_per_l": 19.3,
        "hill_exponent": 1.43,
        "gaussian_noise_enabled": False,
        "effect_site_random_drop_enabled": False,
        "output_clipping_enabled": False,
    }
)
