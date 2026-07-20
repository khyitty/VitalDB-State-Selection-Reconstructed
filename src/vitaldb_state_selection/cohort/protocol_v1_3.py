"""Protocol v1.3 control-design contracts without split or model execution.

The Phase 7B contract is deliberately declarative.  It defines the two-by-two
comparison and validates versioned upstream artifacts, but it cannot create a
split, a modeling array, a PK/PD value, a dose, or a PPO policy.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .guards import CohortGuardError


PROTOCOL_VERSION = "1.3"
SOURCE_PROTOCOL_VERSION = "1.2"
SOURCE_BASELINE_COMMIT = "f18794da91d622b22db07b25c63bc6826e5c75a4"
EXPECTED_CASES = 2460
EXPECTED_SUBJECTS = 2415
EXPECTED_TRAIN_SUBJECTS = 1932
EXPECTED_TEST_SUBJECTS = 483
EXPECTED_PHASE6C_CASES = 2470
EXPECTED_EXCLUDED_CASES = 10
EXPECTED_ELIGIBLE_IDS_SHA256 = (
    "f2c140ccf150648c2d4f46029849f325742e58eaf16ecb30efa05299384fb9bd"
)
EXPECTED_FINAL_COHORT_SHA256 = (
    "517683c574b642584ecaf6e0c7c8a2c1ec461e4eb2252277f0427c4c55065468"
)
EXPECTED_SUBJECT_LINKAGE_SHA256 = (
    "102ccc60d9f03a8bfe858e5862366ef0b49f80cef3dcc027dae94afface464f7"
)

P0_ID = "sqi_not_required__bis30s__drug120s"
P1_ID = "sqi_ge_50__bis20s__drug60s"
HISTORY_SECONDS = (-50, -40, -30, -20, -10, 0)

COMMON_PREPROCESSING = {
    "grid_interval_seconds": 10,
    "grid_anchor": "each_case_anesthesia_start",
    "history_relative_seconds": list(HISTORY_SECONDS),
    "bis_range_inclusive": [0, 100],
    "bis_0_10_admissible": True,
    "causal_lookup_only": True,
    "source_timestamp_must_be_lte_requested_time": True,
    "future_observation_allowed": False,
    "interpolation_allowed": False,
    "backward_fill_allowed": False,
    "pre_observation_zero_assumption_allowed": False,
    "drug_rate_requires_finite_nonnegative": True,
    "zero_bis_is_missing": False,
    "zero_drug_rate_is_missing": False,
    "duplicate_timestamp_rule": "phase6c_last_finite_in_original_row_order",
    "sqi_in_ppo_state": False,
}

P0 = {
    **COMMON_PREPROCESSING,
    "pipeline_id": "P0",
    "candidate_id": P0_ID,
    "name": "permissive_causal_preprocessing",
    "sqi_rule": "not_required",
    "sqi_exact_timestamp_threshold": None,
    "bis_staleness_cap_seconds": 30,
    "propofol_rate_hold_cap_seconds": 120,
    "remifentanil_rate_hold_cap_seconds": 120,
}

P1 = {
    **COMMON_PREPROCESSING,
    "pipeline_id": "P1",
    "candidate_id": P1_ID,
    "name": "quality_aware_causal_preprocessing",
    "sqi_rule": "exact_timestamp_gte_50",
    "sqi_exact_timestamp_threshold": 50,
    "sqi_nearest_matching_allowed": False,
    "sqi_interpolation_allowed": False,
    "bis_staleness_cap_seconds": 20,
    "propofol_rate_hold_cap_seconds": 60,
    "remifentanil_rate_hold_cap_seconds": 60,
}

STATIC_FEATURES = ("age", "sex", "height", "weight")
S0_DYNAMIC_FEATURES = (
    "bis_history_6x10s",
    "propofol_infusion_rate_history_6x10s",
    "remifentanil_infusion_rate_history_6x10s",
)
S1_ADDITIONAL_FEATURES = (
    "propofol_recent_dose_60s",
    "remifentanil_recent_dose_60s",
    "propofol_cumulative_dose_since_anesthesia_start",
    "remifentanil_cumulative_dose_since_anesthesia_start",
    "propofol_cp",
    "propofol_ce",
    "remifentanil_cp",
    "remifentanil_ce",
)

CONDITIONS = (
    {"condition_id": "P0S0", "policy_id": "PPO_P0S0", "preprocessing": "P0", "state": "S0"},
    {"condition_id": "P1S0", "policy_id": "PPO_P1S0", "preprocessing": "P1", "state": "S0"},
    {"condition_id": "P0S1", "policy_id": "PPO_P0S1", "preprocessing": "P0", "state": "S1"},
    {"condition_id": "P1S1", "policy_id": "PPO_P1S1", "preprocessing": "P1", "state": "S1"},
)

SMOKE_SEED = 42
FINAL_SEEDS = (7, 42, 84)

PROHIBITED_EXECUTION = {
    "actual_split": False,
    "train_test_id_lists": False,
    "test_seal": False,
    "modeling_arrays": False,
    "raw_signal_read": False,
    "normalization_fit": False,
    "imputation_fit": False,
    "real_case_recent_or_cumulative_dose": False,
    "real_case_cpce": False,
    "ppo_training": False,
    "ppo_evaluation": False,
    "ppo_checkpoint": False,
    "control_metric_calculation": False,
    "statistical_test": False,
    "future_bis_prediction": False,
    "elastic_net": False,
    "stability_selection": False,
    "gru": False,
    "attention_gru": False,
    "feature_ranking": False,
    "preprocessing_component_ablation": False,
    "api_requests": 0,
    "new_raw_files": 0,
}


def validate_upstream(
    candidate_summaries: Sequence[Mapping[str, object]],
    final_cohort: Sequence[Mapping[str, object]],
    subject_summary: Mapping[str, object],
) -> dict[str, object]:
    """Validate the frozen cohort and exact Phase 6C candidate connection."""

    by_id = {str(row["candidate_id"]): row for row in candidate_summaries}
    if len(by_id) != len(candidate_summaries):
        raise CohortGuardError("duplicate candidate summary ID")
    for candidate_id in (P0_ID, P1_ID):
        if candidate_id not in by_id:
            raise CohortGuardError(f"missing exact Phase 6C candidate: {candidate_id}")
        if int(by_id[candidate_id]["case_count"]) != EXPECTED_PHASE6C_CASES:
            raise CohortGuardError(f"{candidate_id} does not account for 2,470 cases")
        if int(by_id[candidate_id]["future_timestamp_use_count"]) != 0:
            raise CohortGuardError(f"future timestamp use in {candidate_id}")
        if int(by_id[candidate_id]["cross_case_connection_count"]) != 0:
            raise CohortGuardError(f"cross-case connection in {candidate_id}")

    if len(final_cohort) != EXPECTED_PHASE6C_CASES:
        raise CohortGuardError("Protocol v1.2 source accounting changed")
    caseids = [int(row["caseid"]) for row in final_cohort]
    if len(set(caseids)) != EXPECTED_PHASE6C_CASES:
        raise CohortGuardError("duplicate case in final cohort manifest")
    eligible = [row for row in final_cohort if str(row["final_eligible"]).lower() == "true"]
    excluded = [row for row in final_cohort if str(row["final_eligible"]).lower() == "false"]
    if (len(eligible), len(excluded)) != (EXPECTED_CASES, EXPECTED_EXCLUDED_CASES):
        raise CohortGuardError("frozen 2,460/10 case accounting changed")
    for field in (
        "legacy_98_overlap",
        "volatile_excluded_overlap",
        "invalid_anesthesia_window_overlap",
    ):
        if any(str(row[field]).lower() == "true" for row in eligible):
            raise CohortGuardError(f"frozen eligible cohort contains {field}")

    if int(subject_summary["total_case_count"]) != EXPECTED_CASES:
        raise CohortGuardError("subject-linkage case count changed")
    if int(subject_summary["unique_subject_count"]) != EXPECTED_SUBJECTS:
        raise CohortGuardError("subject-linkage subject count changed")
    if str(subject_summary["subject_linkage_sha256"]) != EXPECTED_SUBJECT_LINKAGE_SHA256:
        raise CohortGuardError("subject-linkage checksum changed")
    if bool(subject_summary["split_created"]) or bool(subject_summary["test_seal_created"]):
        raise CohortGuardError("Phase 7B must start before split or test sealing")

    return {
        "phase6c_source_case_count": EXPECTED_PHASE6C_CASES,
        "frozen_case_count": len(eligible),
        "frozen_excluded_case_count": len(excluded),
        "frozen_subject_count": EXPECTED_SUBJECTS,
        "p0_candidate_exists": True,
        "p1_candidate_exists": True,
        "p0_source_case_count": int(by_id[P0_ID]["case_count"]),
        "p1_source_case_count": int(by_id[P1_ID]["case_count"]),
        "p0_usable_source_case_count": int(by_id[P0_ID]["usable_case_count"]),
        "p1_usable_source_case_count": int(by_id[P1_ID]["usable_case_count"]),
        "excluded_cases_reintroduced": 0,
        "cohort_changed": False,
        "subject_linkage_changed": False,
    }


def validate_design() -> None:
    """Reject accidental drift in the explicitly approved design."""

    if P0["bis_staleness_cap_seconds"] != 30 or P1["bis_staleness_cap_seconds"] != 20:
        raise CohortGuardError("BIS staleness contract drift")
    if P0["propofol_rate_hold_cap_seconds"] != 120 or P1["propofol_rate_hold_cap_seconds"] != 60:
        raise CohortGuardError("drug hold contract drift")
    if P0["sqi_rule"] != "not_required" or P1["sqi_rule"] != "exact_timestamp_gte_50":
        raise CohortGuardError("SQI contract drift")
    if len({row["condition_id"] for row in CONDITIONS}) != 4:
        raise CohortGuardError("four unique conditions are required")
    if len({row["policy_id"] for row in CONDITIONS}) != 4:
        raise CohortGuardError("four unique policy IDs are required")
    if set(STATIC_FEATURES + S0_DYNAMIC_FEATURES) & set(S1_ADDITIONAL_FEATURES):
        raise CohortGuardError("S1 additions must be distinct from S0")
    if EXPECTED_TRAIN_SUBJECTS + EXPECTED_TEST_SUBJECTS != EXPECTED_SUBJECTS:
        raise CohortGuardError("planned subject split count mismatch")
    if PROHIBITED_EXECUTION["preprocessing_component_ablation"]:
        raise CohortGuardError("component ablation is outside Protocol v1.3")
