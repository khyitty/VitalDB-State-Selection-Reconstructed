"""Deterministic combined propofol-remifentanil BIS response."""

from __future__ import annotations

import math

from .errors import PKPDValidationError
from .registry import BIS_PARAMETERS


def deterministic_bis(
    propofol_ce_mg_per_l: float,
    remifentanil_ce_microgram_per_l: float,
) -> float:
    """Evaluate the Yun/Bouillon response without noise, drop, or clipping."""

    values = (float(propofol_ce_mg_per_l), float(remifentanil_ce_microgram_per_l))
    if not all(math.isfinite(value) and value >= 0 for value in values):
        raise PKPDValidationError("effect-site concentrations must be finite and nonnegative")
    scaled = (
        1.0
        + values[0] / BIS_PARAMETERS["propofol_ce50_mg_per_l"]
        + values[1] / BIS_PARAMETERS["remifentanil_ce50_microgram_per_l"]
    )
    result = BIS_PARAMETERS["baseline"] * scaled ** (-BIS_PARAMETERS["hill_exponent"])
    if not math.isfinite(result):
        raise PKPDValidationError("BIS response is nonfinite")
    return result
