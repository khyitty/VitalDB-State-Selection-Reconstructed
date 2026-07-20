"""Declarative Protocol v1.3.2 paper-grounded reconstruction amendment.

This module specifies authority, scope, and stage gates only. It does not
implement PK/PD dynamics, an RL environment, a split, or PPO training.
"""

from __future__ import annotations

from .guards import CohortGuardError


PROTOCOL_VERSION = "1.3.2"
AMENDS_VERSION = "1.3.1"
PHASE = "7E_paper_grounded_reconstruction_specification"

IMPLEMENTATION_AUTHORITY = {
    "primary_path": "paper_grounded_independent_reconstruction",
    "primary_paper": "Yun_et_al_2023_10.1016_j.compbiomed.2023.106739",
    "lab_code_expected": False,
    "laboratory_authoritative_implementation": False,
    "path_a_lab_code_reuse": "retired_unavailable",
    "legacy_role": "read_only_equation_cross_check_only",
    "undisclosed_value_policy": "human_decision_required",
}

PRESERVED_DESIGN = {
    "factorial_design": "P0_P1_by_S0_S1",
    "frozen_case_count": 2460,
    "frozen_subject_count": 2415,
    "cohort_refrozen_in_phase7e": False,
    "prediction_in_confirmatory_scope": False,
}

SOURCE_PRIORITY = (
    "yun_2023_primary_paper",
    "directly_cited_schnider_minto_bouillon_ppo_gae_primary_sources",
    "yun_2024_auxiliary_interpretation",
    "legacy_repository_read_only_reference",
    "human_decision_for_undisclosed_values",
)

IMPLEMENTATION_STAGES = (
    "Stage_I_paper_faithful_pkpd_simulator_reconstruction",
    "Stage_II_gymnasium_anesthesia_environment_reconstruction",
    "Stage_III_sb3_ppo_integration_or_paper_style_wrapper",
    "Stage_IV_synthetic_scientific_validation",
    "Stage_V_subject_level_split_and_observation_template",
    "Stage_VI_four_policy_training_and_evaluation",
)

PHASE7E_ALLOWED_OUTPUTS = (
    "protocol_amendment",
    "source_evidence_table",
    "missing_constant_register",
    "implementation_sequence",
    "scientific_validation_plan",
    "tests",
    "phase_status",
)

PROHIBITED_EXECUTION = {
    "simulator_implementation": False,
    "environment_implementation": False,
    "ppo_implementation": False,
    "dependency_installation": False,
    "subject_split": False,
    "test_seal": False,
    "observation_template_extraction": False,
    "raw_signal_access": False,
    "modeling_array": False,
    "ppo_training": False,
    "ppo_evaluation": False,
    "legacy_artifact_reuse": False,
    "prediction": False,
}


def validate_amendment() -> None:
    """Reject drift from the human-directed Phase 7E specification boundary."""

    if PROTOCOL_VERSION != "1.3.2" or AMENDS_VERSION != "1.3.1":
        raise CohortGuardError("Protocol v1.3.2 version lineage drift")
    if IMPLEMENTATION_AUTHORITY["primary_path"] != "paper_grounded_independent_reconstruction":
        raise CohortGuardError("paper-grounded reconstruction must remain primary")
    if IMPLEMENTATION_AUTHORITY["lab_code_expected"]:
        raise CohortGuardError("laboratory code is unavailable and cannot be assumed")
    if IMPLEMENTATION_AUTHORITY["path_a_lab_code_reuse"] != "retired_unavailable":
        raise CohortGuardError("Path A lab-code reuse must remain retired")
    if PRESERVED_DESIGN["factorial_design"] != "P0_P1_by_S0_S1":
        raise CohortGuardError("the approved 2x2 design must remain unchanged")
    if (PRESERVED_DESIGN["frozen_case_count"], PRESERVED_DESIGN["frozen_subject_count"]) != (2460, 2415):
        raise CohortGuardError("frozen cohort accounting drift")
    if len(IMPLEMENTATION_STAGES) != 6:
        raise CohortGuardError("the six-stage reconstruction sequence is incomplete")
    if any(PROHIBITED_EXECUTION.values()):
        raise CohortGuardError("Phase 7E is specification-only")
