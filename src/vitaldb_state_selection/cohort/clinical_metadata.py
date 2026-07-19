"""Outcome-blind parsing of VitalDB clinical metadata rows."""

from __future__ import annotations

import math
from collections.abc import Mapping

from .guards import CohortGuardError, normalize_caseid


MISSING_TEXT = {"", "na", "n/a", "nan", "none", "null"}

SOURCE_FIELDS: dict[str, tuple[str, ...]] = {
    "caseid": ("caseid",),
    "subjectid": ("subjectid",),
    "age": ("age",),
    "sex": ("sex",),
    "height": ("height",),
    "weight": ("weight",),
    "bmi": ("bmi",),
    "asa": ("asa",),
    "anesthesia_type": ("anetype", "ane_type", "anesthesia_type"),
    "operation_type": ("optype", "operation_type"),
    "emergency_status": ("emop", "emergency_status"),
    "anesthesia_start": ("anestart", "ane_start", "anesthesia_start"),
    "anesthesia_end": ("aneend", "ane_end", "anesthesia_end"),
    "operation_start": ("opstart", "op_start", "operation_start"),
    "operation_end": ("opend", "op_end", "operation_end"),
}

NUMERIC_FIELDS = {
    "age",
    "height",
    "weight",
    "bmi",
    "anesthesia_start",
    "anesthesia_end",
    "operation_start",
    "operation_end",
}


def _first_present(row: Mapping[str, object], names: tuple[str, ...]) -> object | None:
    for name in names:
        if name in row:
            return row[name]
    return None


def _missing(value: object | None) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and value.strip().lower() in MISSING_TEXT


def _number(value: object | None, field: str) -> float | None:
    if _missing(value):
        return None
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise CohortGuardError(f"invalid numeric {field}: {value!r}") from exc
    if not math.isfinite(result):
        raise CohortGuardError(f"non-finite numeric {field}: {value!r}")
    return result


def _text(value: object | None) -> str | None:
    if _missing(value):
        return None
    return str(value).strip()


def parse_clinical_row(row: Mapping[str, object]) -> dict[str, object | None]:
    parsed: dict[str, object | None] = {}
    parsed["caseid"] = normalize_caseid(_first_present(row, SOURCE_FIELDS["caseid"]))
    for field, names in SOURCE_FIELDS.items():
        if field == "caseid":
            continue
        raw = _first_present(row, names)
        parsed[field] = _number(raw, field) if field in NUMERIC_FIELDS else _text(raw)
    return parsed


def demographics_available(parsed: Mapping[str, object | None]) -> dict[str, bool]:
    return {
        "age_available": parsed.get("age") is not None,
        "sex_available": parsed.get("sex") is not None,
        "height_available": parsed.get("height") is not None,
        "weight_available": parsed.get("weight") is not None,
    }


def time_range_is_valid(parsed: Mapping[str, object | None]) -> bool:
    starts_ends = (
        (parsed.get("anesthesia_start"), parsed.get("anesthesia_end")),
        (parsed.get("operation_start"), parsed.get("operation_end")),
    )
    for start, end in starts_ends:
        if start is None or end is None:
            return False
        # VitalDB case-event times may be relative and therefore negative.
        # Phase 5A checks only presence and ordering, not an assumed zero origin.
        if float(end) <= float(start):
            return False
    return True
