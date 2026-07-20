"""Declarative Protocol v1.3.1 online-observation amendment.

This module defines contracts only. It cannot create a split, read a raw signal,
construct a modeling array, implement an observation adapter, or execute PPO.
"""

from __future__ import annotations

from .guards import CohortGuardError


PROTOCOL_VERSION = "1.3.1"
AMENDS_VERSION = "1.3"
EXPECTED_CASES = 2460
EXPECTED_SUBJECTS = 2415
EXPECTED_FINAL_COHORT_SHA256 = (
    "517683c574b642584ecaf6e0c7c8a2c1ec461e4eb2252277f0427c4c55065468"
)
EXPECTED_ELIGIBLE_IDS_SHA256 = (
    "f2c140ccf150648c2d4f46029849f325742e58eaf16ecb30efa05299384fb9bd"
)
EXPECTED_SUBJECT_LINKAGE_SHA256 = (
    "102ccc60d9f03a8bfe858e5862366ef0b49f80cef3dcc027dae94afface464f7"
)
HISTORY_RELATIVE_SECONDS = (-50, -40, -30, -20, -10, 0)


COMMON_ONLINE = {
    "grid_interval_seconds": 10,
    "history_relative_seconds": list(HISTORY_RELATIVE_SECONDS),
    "bis_range_inclusive": [0, 100],
    "bis_0_10_admissible": True,
    "causal_lookup_only": True,
    "future_observation_allowed": False,
    "interpolation_allowed": False,
    "backward_fill_allowed": False,
    "propofol_history_source": "applied_internal_commanded_action",
    "remifentanil_history_source": "applied_internal_exogenous_schedule",
    "drug_histories_identical_across_pipelines": True,
    "drug_staleness_contrast": False,
    "drug_artificial_missingness": False,
    "drug_availability_mask_in_state": False,
    "drug_observation_age_in_state": False,
}

P0_ONLINE = {
    **COMMON_ONLINE,
    "pipeline_id": "P0_online_bis_permissive_v1",
    "sqi_rule": "not_required",
    "sqi_exact_timestamp_threshold": None,
    "bis_staleness_cap_seconds": 30,
}

P1_ONLINE = {
    **COMMON_ONLINE,
    "pipeline_id": "P1_online_bis_quality_v1",
    "sqi_rule": "exact_timestamp_gte_50",
    "sqi_exact_timestamp_threshold": 50,
    "sqi_nearest_matching_allowed": False,
    "sqi_interpolation_allowed": False,
    "bis_staleness_cap_seconds": 20,
}

MISSING_ENCODING = {
    "selection": "Option_B_minimal",
    "status": "human_approved_structure",
    "applies_to": "BIS_history_only",
    "channels_per_history_point": [
        "bis_value",
        "bis_availability_mask",
        "bis_observation_age_seconds",
    ],
    "unavailable_value_placeholder": 0,
    "unavailable_mask": 0,
    "available_bis_zero_value": 0,
    "available_bis_zero_mask": 1,
    "age_nonnegative": True,
    "age_unit": "seconds",
    "age_clip_rule": "fixed_predeclared_maximum_not_fit_from_data",
    "age_clip_maximum_seconds": None,
    "age_clip_maximum_status": "pending_human_numeric_value_before_implementation",
    "no_prior_age_rule": "use_same_fixed_capped_age",
    "no_prior_state_channel": False,
    "detailed_reason_codes_audit_only": True,
    "same_for_p0_and_p1": True,
    "implemented_in_phase7d": False,
}

S0_SCHEMA = {
    "state_id": "S0",
    "static_conceptual_fields": ["age", "sex", "height", "weight"],
    "bis_history": {
        "points": 6,
        "channels": ["value", "availability_mask", "observation_age_seconds"],
        "conceptual_dimension": 18,
    },
    "drug_histories": {
        "propofol_commanded_rate_points": 6,
        "remifentanil_environment_rate_points": 6,
        "conceptual_dimension": 12,
        "mask_or_age_channels": False,
    },
    "sqi_numeric_value_included": False,
    "conceptual_dimension": 34,
    "physical_tensor_dimension": "pending_sex_encoding_contract",
    "implemented_in_phase7d": False,
}

S1_ADDITIONAL = (
    "propofol_recent_dose_60s",
    "remifentanil_recent_dose_60s",
    "cumulative_propofol_dose",
    "cumulative_remifentanil_dose",
    "propofol_cp",
    "propofol_ce",
    "remifentanil_cp",
    "remifentanil_ce",
)

S1_SCHEMA = {
    "state_id": "S1",
    "strict_superset_of": "S0",
    "inherits_s0_conceptual_dimension": 34,
    "additional_features": list(S1_ADDITIONAL),
    "additional_conceptual_dimension": 8,
    "conceptual_dimension": 42,
    "sqi_numeric_value_included": False,
    "implemented_in_phase7d": False,
    "real_values_calculated_in_phase7d": False,
}

OBSERVATION_TEMPLATE_CONTRACT = {
    "status": "future_contract_frozen_no_extraction",
    "included_fields": [
        "bis_observation_timestamps",
        "bis_sqi_exact_timestamps",
        "bis_sqi_values",
        "anesthesia_relative_timing",
        "pseudonymous_template_key",
        "source_split_label_after_split_creation",
    ],
    "excluded_fields": [
        "raw_observed_bis_values",
        "future_bis_target",
        "real_propofol_outcome",
        "model_prediction",
        "ppo_result",
    ],
    "same_template_for_p0_and_p1": True,
    "same_latent_trajectory_for_p0_and_p1": True,
    "same_disturbances_for_p0_and_p1": True,
    "reward_bis_source": "latent_true_bis",
    "scientific_outcome_bis_source": "latent_true_bis",
    "train_template_scope": "future_train_subject_templates_only",
    "test_template_scope": "future_test_subject_templates_only",
    "template_extracted_in_phase7d": False,
}

PROHIBITED_EXECUTION = {
    "actual_split": False,
    "subject_id_allocation": False,
    "test_seal": False,
    "raw_vitaldb_read": False,
    "observation_template_extraction": False,
    "raw_bis_value_use": False,
    "modeling_array": False,
    "normalization_fit": False,
    "real_dose_or_cpce": False,
    "simulator_implementation": False,
    "environment_implementation": False,
    "ppo_implementation": False,
    "dependency_installation": False,
    "ppo_execution": False,
    "checkpoint": False,
    "component_ablation": False,
    "phase7e_work": False,
}


def validate_amendment() -> None:
    """Reject drift in the human-approved declarative amendment."""

    if P0_ONLINE["pipeline_id"] != "P0_online_bis_permissive_v1":
        raise CohortGuardError("P0-online identifier drift")
    if P1_ONLINE["pipeline_id"] != "P1_online_bis_quality_v1":
        raise CohortGuardError("P1-online identifier drift")
    if (P0_ONLINE["bis_staleness_cap_seconds"], P1_ONLINE["bis_staleness_cap_seconds"]) != (30, 20):
        raise CohortGuardError("BIS freshness contrast drift")
    if not P0_ONLINE["drug_histories_identical_across_pipelines"]:
        raise CohortGuardError("online drug histories must be invariant")
    if P0_ONLINE["drug_staleness_contrast"] or P1_ONLINE["drug_staleness_contrast"]:
        raise CohortGuardError("retrospective drug hold cannot enter online protocol")
    if MISSING_ENCODING["selection"] != "Option_B_minimal":
        raise CohortGuardError("missing encoding selection drift")
    if MISSING_ENCODING["age_clip_maximum_seconds"] is not None:
        raise CohortGuardError("numeric age cap was not approved in Phase 7D")
    if S0_SCHEMA["conceptual_dimension"] != 34 or S1_SCHEMA["conceptual_dimension"] != 42:
        raise CohortGuardError("state conceptual dimension drift")
    if len(S1_ADDITIONAL) != 8 or not set(S0_SCHEMA["static_conceptual_fields"]):
        raise CohortGuardError("S1 superset contract drift")
    if any(PROHIBITED_EXECUTION.values()):
        raise CohortGuardError("Phase 7D cannot authorize execution")
