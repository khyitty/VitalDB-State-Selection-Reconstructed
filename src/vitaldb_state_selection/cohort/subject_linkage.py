"""Outcome-blind subject-linkage helpers for the Phase 7A feasibility audit.

The functions in this module consume clinical metadata only. They do not assign
train/validation/test membership and never read a raw signal or outcome.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence

from .guards import CohortGuardError


PHASE = "7A_subject_linkage_and_patient_level_split_feasibility_audit"
PROTOCOL_VERSION = "1.2"
SOURCE_PHASE6D_FOLLOWUP = "449ea6db82697327746919388d5e04597834a230"
SOURCE_ELIGIBLE_COUNT = 2460
SOURCE_ELIGIBLE_IDS_SHA256 = "f2c140ccf150648c2d4f46029849f325742e58eaf16ecb30efa05299384fb9bd"
SOURCE_FINAL_COHORT_SHA256 = "517683c574b642584ecaf6e0c7c8a2c1ec461e4eb2252277f0427c4c55065468"
EXPECTED_SUBJECT_COUNT = 2415
EXPECTED_CLUSTER_SIZE_COUNTS = {1: 2378, 2: 35, 3: 1, 9: 1}
SPLIT_PROPORTIONS = {"train": 0.70, "validation": 0.15, "test": 0.15}
SUBJECTID_DOCUMENTED_MEANING = "Subject ID; Deidentified hospital ID of patient"


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _finite(value: object) -> float | None:
    text = _text(value)
    if not text:
        return None
    try:
        result = float(text)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def sorted_caseid_checksum(caseids: Sequence[int]) -> str:
    normalized = sorted(int(value) for value in caseids)
    if len(normalized) != len(set(normalized)):
        raise CohortGuardError("duplicate case ID in checksum input")
    return hashlib.sha256(("\n".join(map(str, normalized)) + "\n").encode()).hexdigest()


def subject_linkage_checksum(rows: Sequence[Mapping[str, object]]) -> str:
    pairs = sorted((int(row["caseid"]), _text(row["subjectid"])) for row in rows)
    if len(pairs) != len({caseid for caseid, _ in pairs}):
        raise CohortGuardError("duplicate case ID in subject linkage")
    payload = "".join(f"{caseid}\t{subjectid}\n" for caseid, subjectid in pairs)
    return hashlib.sha256(payload.encode()).hexdigest()


def empirical_quantile(values: Sequence[float], probability: float) -> float | None:
    finite = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not finite:
        return None
    if not 0 <= probability <= 1:
        raise ValueError("quantile probability must be in [0, 1]")
    position = (len(finite) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return finite[lower]
    fraction = position - lower
    return finite[lower] + fraction * (finite[upper] - finite[lower])


def sex_group(value: object) -> str:
    normalized = _text(value).upper()
    if normalized == "M":
        return "male"
    if normalized == "F":
        return "female"
    return "missing_or_other"


def age_group(value: object) -> str:
    age = _finite(value)
    if age is None or age < 18:
        return "missing_or_invalid"
    if age < 40:
        return "18_to_lt_40"
    if age < 60:
        return "40_to_lt_60"
    if age < 75:
        return "60_to_lt_75"
    return "ge_75"


def calculate_bmi(height_cm: object, weight_kg: object) -> float | None:
    height = _finite(height_cm)
    weight = _finite(weight_kg)
    if height is None or weight is None or height <= 0 or weight <= 0:
        return None
    return weight / ((height / 100.0) ** 2)


def bmi_group(value: float | None) -> str:
    if value is None or not math.isfinite(value) or value <= 0:
        return "missing_or_invalid"
    if value < 18.5:
        return "lt_18_5"
    if value < 25:
        return "18_5_to_lt_25"
    if value < 30:
        return "25_to_lt_30"
    return "ge_30"


def asa_group(value: object) -> str:
    numeric = _finite(value)
    if numeric == 1:
        return "ASA_1"
    if numeric == 2:
        return "ASA_2"
    if numeric == 3:
        return "ASA_3"
    if numeric is not None and numeric >= 4:
        return "ASA_4_or_higher"
    return "missing_or_other"


def emergency_group(value: object) -> str:
    normalized = _text(value).lower()
    if normalized in {"0", "false", "n", "no"}:
        return "non_emergency"
    if normalized in {"1", "true", "y", "yes"}:
        return "emergency"
    return "missing_or_other"


def operation_type_group(value: object) -> str:
    return _text(value) or "missing_or_other"


def _index_metadata(rows: Sequence[Mapping[str, object]]) -> dict[int, Mapping[str, object]]:
    result: dict[int, Mapping[str, object]] = {}
    for row in rows:
        caseid = int(row["caseid"])
        if caseid in result:
            raise CohortGuardError(f"duplicate clinical metadata case ID: {caseid}")
        result[caseid] = row
    return result


def build_subject_linkage_case_manifest(
    eligible_caseids: Sequence[int],
    metadata_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Create a complete linkage manifest without assigning any split."""

    caseids = [int(caseid) for caseid in eligible_caseids]
    if len(caseids) != SOURCE_ELIGIBLE_COUNT or len(set(caseids)) != SOURCE_ELIGIBLE_COUNT:
        raise CohortGuardError("eligible cohort must contain exactly 2,460 unique case IDs")
    if sorted_caseid_checksum(caseids) != SOURCE_ELIGIBLE_IDS_SHA256:
        raise CohortGuardError("eligible case-ID checksum mismatch")
    indexed = _index_metadata(metadata_rows)
    if set(caseids) - set(indexed):
        raise CohortGuardError("eligible case missing from clinical metadata snapshot")

    subjects: Counter[str] = Counter()
    for caseid in caseids:
        subjectid = _text(indexed[caseid].get("subjectid"))
        if not subjectid:
            raise CohortGuardError(f"missing or unparsable subjectid for case {caseid}")
        subjects[subjectid] += 1
    if len(subjects) != EXPECTED_SUBJECT_COUNT:
        raise CohortGuardError("subject count does not match the pinned Phase 7A source")
    if dict(sorted(Counter(subjects.values()).items())) != EXPECTED_CLUSTER_SIZE_COUNTS:
        raise CohortGuardError("subject cluster-size distribution mismatch")

    result: list[dict[str, object]] = []
    for caseid in sorted(caseids):
        source = indexed[caseid]
        subjectid = _text(source["subjectid"])
        calculated_bmi = calculate_bmi(source.get("height"), source.get("weight"))
        result.append({
            "caseid": caseid,
            "subjectid": subjectid,
            "subject_case_count": subjects[subjectid],
            "repeated_subject": subjects[subjectid] > 1,
            "source_final_cohort_checksum": SOURCE_FINAL_COHORT_SHA256,
            "subjectid_source_field": "subjectid",
            "subjectid_documented_meaning": SUBJECTID_DOCUMENTED_MEANING,
            "split_created": False,
            "assigned_split": "",
            "sex_source_value": _text(source.get("sex")),
            "sex_group": sex_group(source.get("sex")),
            "age": _finite(source.get("age")),
            "age_group": age_group(source.get("age")),
            "height_cm": _finite(source.get("height")),
            "weight_kg": _finite(source.get("weight")),
            "bmi_calculated": calculated_bmi,
            "bmi_group": bmi_group(calculated_bmi),
            "asa_source_value": _text(source.get("asa")),
            "asa_group": asa_group(source.get("asa")),
            "emergency_source_value": _text(source.get("emergency_status")),
            "emergency_group": emergency_group(source.get("emergency_status")),
            "operation_type_source_value": _text(source.get("operation_type")),
            "operation_type_group": operation_type_group(source.get("operation_type")),
            "outcome_used_for_audit": False,
            "raw_signal_read_for_audit": False,
        })
    return result


def _range_summary(rows: Sequence[Mapping[str, object]], field: str) -> dict[str, float | None]:
    values = [float(value) for row in rows if (value := row.get(field)) is not None]
    if not values:
        return {"minimum": None, "maximum": None, "range": None}
    low, high = min(values), max(values)
    return {"minimum": low, "maximum": high, "range": high - low}


def build_subject_cluster_rows(
    linkage_rows: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in linkage_rows:
        grouped[_text(row["subjectid"])].append(row)
    clusters: list[dict[str, object]] = []
    consistency: list[dict[str, object]] = []
    for subjectid in sorted(grouped):
        rows = grouped[subjectid]
        sex_values = sorted({_text(row["sex_source_value"]) for row in rows})
        ages = _range_summary(rows, "age")
        heights = _range_summary(rows, "height_cm")
        weights = _range_summary(rows, "weight_kg")
        bmis = _range_summary(rows, "bmi_calculated")
        clusters.append({
            "subjectid": subjectid,
            "subject_case_count": len(rows),
            "repeated_subject": len(rows) > 1,
            "split_created": False,
            "assigned_split": "",
        })
        consistency.append({
            "subjectid": subjectid,
            "subject_case_count": len(rows),
            "sex_exact_source_distinct_count": len(sex_values),
            "sex_exact_source_consistent": len(sex_values) == 1,
            "sex_source_values_json": json.dumps(sex_values, separators=(",", ":")),
            "sex_inconsistency_warning": len(sex_values) > 1,
            "age_minimum": ages["minimum"], "age_maximum": ages["maximum"], "age_range": ages["range"],
            "height_minimum": heights["minimum"], "height_maximum": heights["maximum"], "height_range": heights["range"],
            "weight_minimum": weights["minimum"], "weight_maximum": weights["maximum"], "weight_range": weights["range"],
            "bmi_minimum": bmis["minimum"], "bmi_maximum": bmis["maximum"], "bmi_range": bmis["range"],
            "distinct_asa_count": len({_text(row["asa_source_value"]) for row in rows}),
            "distinct_operation_type_count": len({_text(row["operation_type_source_value"]) for row in rows}),
            "emergency_case_count": sum(row["emergency_group"] == "emergency" for row in rows),
            "non_emergency_case_count": sum(row["emergency_group"] == "non_emergency" for row in rows),
            "missing_or_other_emergency_case_count": sum(row["emergency_group"] == "missing_or_other" for row in rows),
            "linkage_changed_from_metadata_variation": False,
        })
    return clusters, consistency


def repeated_subject_distribution(cluster_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    counts = Counter(int(row["subject_case_count"]) for row in cluster_rows)
    total_subjects = len(cluster_rows)
    total_cases = sum(size * count for size, count in counts.items())
    return [{
        "cluster_size": size,
        "subject_count": counts[size],
        "case_count": size * counts[size],
        "subject_proportion": counts[size] / total_subjects,
        "case_proportion": (size * counts[size]) / total_cases,
    } for size in sorted(counts)]


def subject_accounting(cluster_rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    sizes = [int(row["subject_case_count"]) for row in cluster_rows]
    repeated_cases = sum(size for size in sizes if size > 1)
    return {
        "total_case_count": sum(sizes),
        "unique_subject_count": len(sizes),
        "cases_per_subject": {
            "minimum": min(sizes),
            "q01": empirical_quantile(sizes, 0.01),
            "q05": empirical_quantile(sizes, 0.05),
            "q25": empirical_quantile(sizes, 0.25),
            "median": empirical_quantile(sizes, 0.50),
            "q75": empirical_quantile(sizes, 0.75),
            "q95": empirical_quantile(sizes, 0.95),
            "q99": empirical_quantile(sizes, 0.99),
            "maximum": max(sizes),
            "quantile_method": "linear_interpolation_position_n_minus_1",
        },
        "subjects_with_exactly_1_case": sum(size == 1 for size in sizes),
        "subjects_with_exactly_2_cases": sum(size == 2 for size in sizes),
        "subjects_with_exactly_3_cases": sum(size == 3 for size in sizes),
        "subjects_with_4_or_more_cases": sum(size >= 4 for size in sizes),
        "repeated_subject_count": sum(size > 1 for size in sizes),
        "repeated_subject_case_count": repeated_cases,
        "repeated_subject_case_proportion": repeated_cases / sum(sizes),
        "largest_subject_cluster_case_count": max(sizes),
    }

def nearest_integer_targets(total: int) -> dict[str, int]:
    order = ("train", "validation", "test")
    ideals = {name: total * SPLIT_PROPORTIONS[name] for name in order}
    targets = {name: math.floor(ideals[name]) for name in order}
    remainder = total - sum(targets.values())
    ranked = sorted(order, key=lambda name: (-(ideals[name] - targets[name]), order.index(name)))
    for name in ranked[:remainder]:
        targets[name] += 1
    return targets


def count_only_split_feasibility(cluster_rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Evaluate arithmetic feasibility from cluster sizes without assigning a subject."""

    sizes = [int(row["subject_case_count"]) for row in cluster_rows]
    total_cases, total_subjects = sum(sizes), len(sizes)
    case_targets = nearest_integer_targets(total_cases)
    subject_targets = nearest_integer_targets(total_subjects)
    singleton_count = sum(size == 1 for size in sizes)
    non_singleton_cases = sum(size for size in sizes if size > 1)

    # A count-only sufficient condition for exact case targets: all non-singleton
    # clusters fit inside the largest case target and the remaining targets can be
    # filled with singleton clusters. No subject ID or membership is retained.
    largest_target = max(case_targets.values())
    exact_case_targets_feasible = (
        non_singleton_cases <= largest_target
        and singleton_count == total_cases - non_singleton_cases
        and singleton_count >= total_cases - largest_target
    )

    required_extra = {name: case_targets[name] - subject_targets[name] for name in SPLIT_PROPORTIONS}
    extras = [size - 1 for size in sizes if size > 1]
    reachable = {(0, 0)}
    total_extra = sum(extras)
    for extra in extras:
        next_reachable: set[tuple[int, int]] = set()
        for train_extra, validation_extra in reachable:
            next_reachable.add((train_extra + extra, validation_extra))
            next_reachable.add((train_extra, validation_extra + extra))
            next_reachable.add((train_extra, validation_extra))
        reachable = next_reachable

    minimum_l1: int | None = None
    exact_joint = False
    for train_extra, validation_extra in reachable:
        test_extra = total_extra - train_extra - validation_extra
        deviations = {
            "train": subject_targets["train"] + train_extra - case_targets["train"],
            "validation": subject_targets["validation"] + validation_extra - case_targets["validation"],
            "test": subject_targets["test"] + test_extra - case_targets["test"],
        }
        score = sum(abs(value) for value in deviations.values())
        minimum_l1 = score if minimum_l1 is None else min(minimum_l1, score)
        if all(value == 0 for value in deviations.values()):
            exact_joint = True

    return {
        "target_proportions": SPLIT_PROPORTIONS,
        "case_count_targets": {
            name: {
                "ideal_fractional": total_cases * proportion,
                "nearest_integer": case_targets[name],
            } for name, proportion in SPLIT_PROPORTIONS.items()
        },
        "subject_count_targets": {
            name: {
                "ideal_fractional": total_subjects * proportion,
                "nearest_integer": subject_targets[name],
            } for name, proportion in SPLIT_PROPORTIONS.items()
        },
        "indivisible_subject_cluster_present": any(size > 1 for size in sizes),
        "exact_case_targets_arithmetically_feasible": exact_case_targets_feasible,
        "exact_joint_nearest_case_and_subject_targets_arithmetically_feasible": exact_joint,
        "minimum_total_absolute_case_count_deviation_under_nearest_subject_targets": minimum_l1,
        "largest_cluster_case_count": max(sizes),
        "largest_cluster_share_of_targets": {
            name: max(sizes) / case_targets[name] for name in SPLIT_PROPORTIONS
        },
        "analysis_type": "cluster_size_histogram_only_no_subject_membership_allocation",
        "split_created": False,
        "assigned_split_count": 0,
    }
