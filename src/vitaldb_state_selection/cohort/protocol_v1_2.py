"""Human-approved Protocol v1.2 cohort-freeze helpers.

This module consumes Phase 6C count artifacts only. It never reads raw signals,
builds modeling arrays, assigns a split, or evaluates an outcome/model.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence

from .guards import CohortGuardError


PROTOCOL_VERSION = "1.2"
APPROVAL_DATE = "2026-07-20"
PHASE6C_SOURCE_COMMIT = "b8f010dcc67497f77e26cee53094819f2f5d6cd9"
PHASE6C_PUBLICATION_FOLLOWUP = "624e5eaf9f5919ae94fa4d344478af85563ee622"
SELECTED_CANDIDATE_ID = "sqi_ge_50__bis20s__drug60s"
MINIMUM_USABLE_WINDOWS = 120
EXPECTED_SOURCE_CASES = 2470
EXPECTED_ELIGIBLE_CASES = 2460
EXPECTED_INELIGIBLE_CASES = 10
EXPECTED_ELIGIBLE_IDS_SHA256 = "f2c140ccf150648c2d4f46029849f325742e58eaf16ecb30efa05299384fb9bd"
EXPECTED_INELIGIBLE_IDS_SHA256 = "6d2f5186c4fed0234dd8bde3f8756f978140de62d91eb880532eeab3432c5907"

SELECTED_PARAMETERS = {
    "grid_interval_seconds": 10,
    "grid_anchor": "each_case_anesthesia_start",
    "history_relative_seconds": [-50, -40, -30, -20, -10, 0],
    "target_relative_seconds": 30,
    "bis_admissible_range_inclusive": [0, 100],
    "bis_0_10_admissible": True,
    "bis_staleness_cap_seconds": 20,
    "sqi_exact_timestamp_threshold": 50,
    "sqi_role": "qc_only_not_prediction_feature_not_ppo_state",
    "drug_rate_hold_cap_seconds": 60,
    "drug_rate_require_finite_nonnegative": True,
    "minimum_usable_prediction_windows": MINIMUM_USABLE_WINDOWS,
}


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    raise CohortGuardError(f"expected explicit boolean, got {value!r}")


def sorted_caseid_checksum(caseids: Sequence[int]) -> str:
    normalized = sorted(int(caseid) for caseid in caseids)
    if len(normalized) != len(set(normalized)):
        raise CohortGuardError("duplicate case ID in checksum input")
    payload = ("\n".join(str(caseid) for caseid in normalized) + "\n").encode()
    return hashlib.sha256(payload).hexdigest()


def _index_unique(rows: Sequence[Mapping[str, object]], name: str) -> dict[int, Mapping[str, object]]:
    indexed: dict[int, Mapping[str, object]] = {}
    for row in rows:
        caseid = int(row["caseid"])
        if caseid in indexed:
            raise CohortGuardError(f"duplicate {name} case ID: {caseid}")
        indexed[caseid] = row
    return indexed


def build_final_cohort_manifest(
    candidate_rows: Sequence[Mapping[str, object]],
    pre_quality_rows: Sequence[Mapping[str, object]],
    demographic_rows: Sequence[Mapping[str, object]],
    quality_rows: Sequence[Mapping[str, object]],
    *,
    case_candidate_sha256: str,
) -> list[dict[str, object]]:
    """Freeze one human-selected candidate without consulting any outcome."""

    if len(candidate_rows) != EXPECTED_SOURCE_CASES:
        raise CohortGuardError("selected candidate must contain exactly 2,470 rows")
    if any(row["candidate_id"] != SELECTED_CANDIDATE_ID for row in candidate_rows):
        raise CohortGuardError("candidate row does not match Protocol v1.2 selection")
    if len({int(row["caseid"]) for row in candidate_rows}) != EXPECTED_SOURCE_CASES:
        raise CohortGuardError("selected candidate contains duplicate case IDs")
    for row in candidate_rows:
        if (
            row["sqi_rule"] != "sqi_ge_50"
            or int(row["bis_staleness_cap_seconds"]) != 20
            or int(row["drug_hold_cap_seconds"]) != 60
        ):
            raise CohortGuardError("selected candidate parameter columns do not match its ID")
        if int(row["future_timestamp_use_count"]) != 0:
            raise CohortGuardError("future timestamp use detected in selected source row")
        if int(row["cross_case_connection_count"]) != 0:
            raise CohortGuardError("cross-case connection detected in selected source row")

    pre = _index_unique(pre_quality_rows, "pre-quality")
    demographics = _index_unique(demographic_rows, "demographic")
    quality = _index_unique(quality_rows, "quality")
    source_ids = {int(row["caseid"]) for row in candidate_rows}
    if not source_ids <= set(pre) or source_ids != set(demographics) or source_ids != set(quality):
        raise CohortGuardError("Phase 6A/6B/6C case accounting does not align")

    result: list[dict[str, object]] = []
    for candidate in sorted(candidate_rows, key=lambda row: int(row["caseid"])):
        caseid = int(candidate["caseid"])
        pre_row = pre[caseid]
        demo = demographics[caseid]
        quality_row = quality[caseid]
        source_included = parse_bool(pre_row["included_for_primary_signal_acquisition"])
        legacy_overlap = parse_bool(pre_row["legacy_98_overlap"])
        volatile_excluded = parse_bool(pre_row["volatile_positive_run_ge_10s"])
        invalid_window = parse_bool(pre_row["invalid_anesthesia_window"])
        if not source_included or legacy_overlap or volatile_excluded or invalid_window:
            raise CohortGuardError(f"case {caseid} violates inherited Phase 6A exclusions")

        windows = int(candidate["total_usable_windows"])
        eligible = windows >= MINIMUM_USABLE_WINDOWS
        candidate_points = int(candidate["total_candidate_grid_points"])
        failure_bis_history = int(candidate["failure_history_bis_unavailable"])
        failure_bis_target = int(candidate["failure_target_bis_unavailable"])
        failure_propofol = int(candidate["failure_history_propofol_unavailable"])
        failure_remifentanil = int(candidate["failure_history_remifentanil_unavailable"])
        result.append({
            "caseid": caseid,
            "source_pre_quality_inclusion": source_included,
            "selected_candidate_id": SELECTED_CANDIDATE_ID,
            "selected_candidate_usable_window_count": windows,
            "passes_minimum_120_windows": eligible,
            "final_eligible": eligible,
            "exclusion_reason": "eligible" if eligible else "ineligible_fewer_than_120_usable_windows",
            "all_four_demographics_present": parse_bool(demo["all_four_demographics_present"]),
            "schnider_minto_basic_input_feasible": parse_bool(demo["schnider_minto_basic_numeric_inputs_present"]),
            "duplicate_timestamp_affected": parse_bool(candidate["any_duplicate_timestamp_affected_endpoint"]),
            "negative_rate_warning": parse_bool(quality_row["negative_drug_rate_present"]),
            "contributing_bis_sqi_history_unavailable": (not eligible and failure_bis_history > 0),
            "contributing_no_candidate_grid_points": (not eligible and candidate_points == 0),
            "contributing_no_usable_bis_sqi_history": (
                not eligible and candidate_points > 0 and failure_bis_history == candidate_points
            ),
            "contributing_bis_target_unavailable": (not eligible and failure_bis_target > 0),
            "contributing_no_usable_bis_target": (
                not eligible and candidate_points > 0 and failure_bis_target == candidate_points
            ),
            "contributing_propofol_unavailable": (not eligible and failure_propofol > 0),
            "contributing_remifentanil_unavailable": (not eligible and failure_remifentanil > 0),
            "contributing_zero_usable_windows": (not eligible and windows == 0),
            "contributing_fewer_than_120_windows": not eligible,
            "legacy_98_overlap": legacy_overlap,
            "volatile_excluded_overlap": volatile_excluded,
            "invalid_anesthesia_window_overlap": invalid_window,
            "source_phase6c_commit": PHASE6C_SOURCE_COMMIT,
            "source_case_candidate_sha256": case_candidate_sha256,
            "protocol_version": PROTOCOL_VERSION,
            "cohort_frozen": True,
            "split_created": False,
            "modeling_arrays_created": False,
            "outcome_or_model_used_for_eligibility": False,
        })

    eligible_ids = [int(row["caseid"]) for row in result if row["final_eligible"]]
    ineligible_ids = [int(row["caseid"]) for row in result if not row["final_eligible"]]
    if len(result) != EXPECTED_SOURCE_CASES:
        raise CohortGuardError("final cohort manifest lost source cases")
    if len(eligible_ids) != EXPECTED_ELIGIBLE_CASES or len(ineligible_ids) != EXPECTED_INELIGIBLE_CASES:
        raise CohortGuardError("expected 2,460/10 accounting mismatch; cohort must not freeze")
    if sorted_caseid_checksum(eligible_ids) != EXPECTED_ELIGIBLE_IDS_SHA256:
        raise CohortGuardError("final eligible ID checksum mismatch; cohort must not freeze")
    if sorted_caseid_checksum(ineligible_ids) != EXPECTED_INELIGIBLE_IDS_SHA256:
        raise CohortGuardError("final ineligible ID checksum mismatch; cohort must not freeze")
    return result


def build_sensitivity_reference(
    minimum_window_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    lookup: dict[tuple[str, int], int] = {}
    for row in minimum_window_rows:
        key = (str(row["candidate_id"]), int(row["minimum_usable_windows"]))
        if key in lookup:
            raise CohortGuardError(f"duplicate Phase 6C sensitivity row: {key}")
        lookup[key] = int(row["pass_case_count"])
    definitions = (
        ("sqi_rule", "sqi_not_required", "sqi_not_required__bis20s__drug60s", 120),
        ("sqi_rule", "sqi_ge_20", "sqi_ge_20__bis20s__drug60s", 120),
        ("sqi_rule", "sqi_ge_80", "sqi_ge_80__bis20s__drug60s", 120),
        ("bis_staleness", "10_seconds", "sqi_ge_50__bis10s__drug60s", 120),
        ("bis_staleness", "30_seconds", "sqi_ge_50__bis30s__drug60s", 120),
        ("drug_hold", "30_seconds", "sqi_ge_50__bis20s__drug30s", 120),
        ("drug_hold", "120_seconds", "sqi_ge_50__bis20s__drug120s", 120),
        ("drug_hold", "300_seconds", "sqi_ge_50__bis20s__drug300s", 120),
        ("drug_hold", "600_seconds", "sqi_ge_50__bis20s__drug600s", 120),
        ("minimum_windows", "30", SELECTED_CANDIDATE_ID, 30),
        ("minimum_windows", "60", SELECTED_CANDIDATE_ID, 60),
        ("minimum_windows", "300", SELECTED_CANDIDATE_ID, 300),
        ("minimum_windows", "600", SELECTED_CANDIDATE_ID, 600),
    )
    result: list[dict[str, object]] = []
    for dimension, alternative, identifier, threshold in definitions:
        key = (identifier, threshold)
        if key not in lookup:
            raise CohortGuardError(f"missing Phase 6C sensitivity row: {key}")
        result.append({
            "dimension": dimension,
            "alternative": alternative,
            "candidate_id": identifier,
            "minimum_usable_windows": threshold,
            "eligible_case_count": lookup[key],
            "source": "Phase_6C_minimum_window_sensitivity",
            "robustness_reference_only": True,
            "final_cohort": False,
            "selected": False,
        })
    return result


def cohort_summary(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    eligible = [row for row in rows if bool(row["final_eligible"])]
    excluded = [row for row in rows if not bool(row["final_eligible"])]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "selected_candidate_id": SELECTED_CANDIDATE_ID,
        "minimum_usable_windows": MINIMUM_USABLE_WINDOWS,
        "source_case_count": len(rows),
        "eligible_case_count": len(eligible),
        "excluded_case_count": len(excluded),
        "exclusion_reason_counts": dict(sorted(Counter(str(row["exclusion_reason"]) for row in rows).items())),
        "all_four_demographics_present_count": sum(bool(row["all_four_demographics_present"]) for row in rows),
        "schnider_minto_basic_input_feasible_count": sum(bool(row["schnider_minto_basic_input_feasible"]) for row in rows),
        "duplicate_timestamp_affected_case_count": sum(bool(row["duplicate_timestamp_affected"]) for row in rows),
        "negative_rate_warning_case_count": sum(bool(row["negative_rate_warning"]) for row in rows),
        "legacy_overlap_count": sum(bool(row["legacy_98_overlap"]) for row in rows),
        "volatile_excluded_overlap_count": sum(bool(row["volatile_excluded_overlap"]) for row in rows),
        "invalid_anesthesia_window_overlap_count": sum(bool(row["invalid_anesthesia_window_overlap"]) for row in rows),
        "eligible_ids_sha256": sorted_caseid_checksum([int(row["caseid"]) for row in eligible]),
        "ineligible_ids_sha256": sorted_caseid_checksum([int(row["caseid"]) for row in excluded]),
        "primary_final_cohort_count": 1,
        "cohort_frozen": True,
        "split_created": False,
        "modeling_arrays_created": False,
        "outcome_or_model_used": False,
    }


def sensitivity_counts_json(rows: Sequence[Mapping[str, object]]) -> str:
    return json.dumps(
        {f"{row['dimension']}:{row['alternative']}": row["eligible_case_count"] for row in rows},
        sort_keys=True,
    )
