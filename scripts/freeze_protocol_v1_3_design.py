"""Create Phase 7B protocol artifacts from versioned summaries only."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.protocol_v1_3 import (  # noqa: E402
    CONDITIONS,
    EXPECTED_CASES,
    EXPECTED_ELIGIBLE_IDS_SHA256,
    EXPECTED_FINAL_COHORT_SHA256,
    EXPECTED_PHASE6C_CASES,
    EXPECTED_SUBJECT_LINKAGE_SHA256,
    EXPECTED_SUBJECTS,
    EXPECTED_TEST_SUBJECTS,
    EXPECTED_TRAIN_SUBJECTS,
    FINAL_SEEDS,
    P0,
    P0_ID,
    P1,
    P1_ID,
    PROHIBITED_EXECUTION,
    PROTOCOL_VERSION,
    S0_DYNAMIC_FEATURES,
    S1_ADDITIONAL_FEATURES,
    SMOKE_SEED,
    SOURCE_BASELINE_COMMIT,
    STATIC_FEATURES,
    validate_design,
    validate_upstream,
)

MANIFESTS = ROOT / "data" / "manifests"
LEGACY = ROOT.parent / "VitalDB-Feature-Selection"
LEGACY_ALLOWLIST = (
    "src/rl_env/config.py",
    "src/rl_env/environment.py",
    "src/rl_env/history.py",
    "src/rl_env/observation.py",
    "src/rl_env/reward.py",
    "src/rl_env/state_adapters.py",
    "src/rl_env/state_manifests.py",
    "src/rl_training/config.py",
    "src/rl_training/environment_factory.py",
    "src/rl_training/feature_extractors.py",
    "src/pkpd/simulator.py",
    "src/pkpd/reconstruction.py",
    "src/pkpd/parameters.py",
    "src/pkpd/units.py",
    "src/pkpd/demographics.py",
    "src/pkpd/bis_response.py",
    "src/pkpd/compartment.py",
    "src/pkpd/schedules.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def csv_bytes(rows: list[dict[str, object]]) -> bytes:
    fields = list(rows[0])
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def git_legacy(*args: str) -> str:
    safe = LEGACY.resolve().as_posix()
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={safe}", "-C", str(LEGACY), *args],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def legacy_state() -> dict[str, object]:
    return {
        "head": git_legacy("rev-parse", "HEAD"),
        "tree": git_legacy("rev-parse", "HEAD^{tree}"),
        "status_short": git_legacy("status", "--short").splitlines(),
    }


def legacy_blob(path: str) -> str:
    return git_legacy("rev-parse", f"HEAD:{path}")


def legacy_text(path: str) -> str:
    return git_legacy("show", f"HEAD:{path}")


def verify_legacy_interfaces() -> dict[str, object]:
    simulator = legacy_text("src/pkpd/simulator.py")
    environment = legacy_text("src/rl_env/environment.py")
    history = legacy_text("src/rl_env/history.py")
    observation = legacy_text("src/rl_env/observation.py")
    if "observed_bis" not in simulator or "SQI" in simulator or "sqi" in simulator:
        raise RuntimeError("legacy simulator observation audit changed")
    if "post_bis=state.observed_bis" not in environment:
        raise RuntimeError("legacy reward input contract changed")
    if "history_mask" not in observation or "HistoryBuffer" not in history:
        raise RuntimeError("legacy fixed-shape history contract changed")
    return {
        "allowlisted_source_blob_ids": {path: legacy_blob(path) for path in LEGACY_ALLOWLIST},
        "rejected_config_read_count": 0,
        "checkpoint_read_count": 0,
        "result_read_count": 0,
    }


def candidate_case_connection() -> dict[str, object]:
    path = MANIFESTS / "causal_grid_feasibility_case_candidate_manifest.csv.gz"
    counts = {P0_ID: 0, P1_ID: 0}
    caseids = {P0_ID: set(), P1_ID: set()}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            candidate_id = row["candidate_id"]
            if candidate_id in counts:
                counts[candidate_id] += 1
                caseids[candidate_id].add(int(row["caseid"]))
    final_rows = read_csv(MANIFESTS / "final_eligible_cohort_manifest.csv")
    eligible = {int(row["caseid"]) for row in final_rows if row["final_eligible"].lower() == "true"}
    excluded = {int(row["caseid"]) for row in final_rows if row["final_eligible"].lower() == "false"}
    for candidate_id in counts:
        if counts[candidate_id] != EXPECTED_PHASE6C_CASES or len(caseids[candidate_id]) != EXPECTED_PHASE6C_CASES:
            raise RuntimeError(f"incomplete Phase 6C rows for {candidate_id}")
        if not eligible <= caseids[candidate_id] or not excluded <= caseids[candidate_id]:
            raise RuntimeError(f"Phase 6C candidate universe mismatch for {candidate_id}")
    return {
        "p0_case_candidate_rows": counts[P0_ID],
        "p1_case_candidate_rows": counts[P1_ID],
        "p0_frozen_case_link_count": len(eligible & caseids[P0_ID]),
        "p1_frozen_case_link_count": len(eligible & caseids[P1_ID]),
        "source_excluded_case_count": len(excluded),
        "source_excluded_cases_authorized_for_protocol_v1_3": 0,
    }


def main() -> int:
    validate_design()
    current_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if current_commit != SOURCE_BASELINE_COMMIT:
        raise RuntimeError(
            f"Phase 7B must start at verified Phase 7A follow-up, got {current_commit}"
        )
    legacy_before = legacy_state()
    legacy_audit = verify_legacy_interfaces()

    candidate_summaries = read_csv(MANIFESTS / "causal_grid_candidate_summary.csv")
    final_cohort = read_csv(MANIFESTS / "final_eligible_cohort_manifest.csv")
    subject_summary = read_json(MANIFESTS / "subject_linkage_summary.json")
    upstream = validate_upstream(candidate_summaries, final_cohort, subject_summary)
    connection = candidate_case_connection()

    final_cohort_hash = sha256(MANIFESTS / "final_eligible_cohort_manifest.csv")
    if final_cohort_hash != EXPECTED_FINAL_COHORT_SHA256:
        raise RuntimeError("Protocol v1.2 final cohort checksum changed")
    if subject_summary["source_eligible_ids_sha256"] != EXPECTED_ELIGIBLE_IDS_SHA256:
        raise RuntimeError("eligible case-ID checksum changed")

    preprocessing_comparison = [
        {"component": "frozen cohort", "P0": "same 2460 cases", "P1": "same 2460 cases", "relationship": "common"},
        {"component": "anesthesia window and grid", "P0": "10s; anesthesia start", "P1": "10s; anesthesia start", "relationship": "common"},
        {"component": "history", "P0": "-50,-40,-30,-20,-10,0s", "P1": "-50,-40,-30,-20,-10,0s", "relationship": "common"},
        {"component": "causal alignment", "P0": "no future/interpolation/bfill", "P1": "no future/interpolation/bfill", "relationship": "common"},
        {"component": "missing-data representation framework", "P0": "must be identical; unresolved", "P1": "must be identical; unresolved", "relationship": "common_pending_human_review"},
        {"component": "SQI quality gating", "P0": "none", "P1": "exact timestamp SQI >= 50", "relationship": "bundle_difference"},
        {"component": "BIS staleness cap", "P0": "30 seconds", "P1": "20 seconds", "relationship": "bundle_difference"},
        {"component": "drug-rate hold cap", "P0": "120 seconds", "P1": "60 seconds", "relationship": "bundle_difference"},
    ]

    missing_audit = {
        "status": "undefined_and_requires_human_decision",
        "same_encoding_required_for_p0_and_p1": True,
        "bis_zero_is_valid_not_missing": True,
        "drug_rate_zero_is_valid_not_missing": True,
        "binary_availability_mask_candidate": "pending_human_review",
        "observation_age_channel_candidate": "pending_human_review",
        "sentinel_or_placeholder": "undefined",
        "stale_beyond_cap_usable": False,
        "pipeline_specific_episode_deletion_allowed": False,
        "different_evaluation_horizons_allowed": False,
        "reward_bis_source": "latent_true_simulator_bis_preferred_pending_environment_contract",
        "current_legacy_history_mask_role": "reset_padding_only_not_observation_missingness",
        "implementation_authorized": False,
    }

    simulator_audit = {
        "overall_status": "requires_new_implementation",
        "implementation_ready": False,
        "ppo_execution_authorized": False,
        "questions": [
            {"id": 1, "question": "perfect BIS at every simulator time", "finding": "yes; observed BIS is generated each advance"},
            {"id": 2, "question": "simulator generates SQI", "finding": "no"},
            {"id": 3, "question": "simulator generates BIS missingness", "finding": "no"},
            {"id": 4, "question": "simulator generates delayed observations", "finding": "no"},
            {"id": 5, "question": "simulator generates drug-rate observation staleness", "finding": "no"},
            {"id": 6, "question": "VitalDB timestamp/SQI/missingness replay layer exists", "finding": "no"},
            {"id": 7, "question": "controller observation and latent reward state separable", "finding": "not by a quality layer; refactor required"},
            {"id": 8, "question": "P0 and P1 can share one latent trajectory with distinct observation views", "finding": "not currently; new replay/corruption layer required"},
        ],
        "required_component": "observation_corruption_or_replay_layer",
        "claim_boundary": "preprocessing effect is not implemented and Protocol v1.3 is not implementation-ready",
    }

    s0 = {
        "state_id": "S0",
        "name": "observable_history_state",
        "static_features": list(STATIC_FEATURES),
        "dynamic_features": list(S0_DYNAMIC_FEATURES),
        "history_relative_seconds": [-50, -40, -30, -20, -10, 0],
        "bmi_included": False,
        "sqi_numeric_value_included": False,
        "common_missingness_channels": "pending_human_review_and_must_match_S1",
        "implementation_status": "requires_new_implementation",
    }
    s1 = {
        "state_id": "S1",
        "name": "pharmacology_enriched_state",
        "strict_superset_of": "S0",
        "inherited_static_features": list(STATIC_FEATURES),
        "inherited_dynamic_features": list(S0_DYNAMIC_FEATURES),
        "additional_features": list(S1_ADDITIONAL_FEATURES),
        "sqi_numeric_value_included": False,
        "common_missingness_channels": "pending_human_review_and_must_match_S0",
        "values_calculated_in_phase7b": False,
        "implementation_status": "reusable_after_refactor_with_primary_source_revalidation",
    }

    s1_rows: list[dict[str, object]] = []
    feature_specs = (
        ("propofol_recent_dose_60s", "dose in preceding 60 seconds", "mg", "simulator history", "Schnider propofol model context"),
        ("remifentanil_recent_dose_60s", "dose in preceding 60 seconds", "microgram", "simulator history", "Minto remifentanil model context"),
        ("propofol_cumulative_dose_since_anesthesia_start", "dose since episode/anesthesia start", "mg", "simulator compartment state", "Schnider propofol model context"),
        ("remifentanil_cumulative_dose_since_anesthesia_start", "dose since episode/anesthesia start", "microgram", "simulator compartment state", "Minto remifentanil model context"),
        ("propofol_cp", "central plasma concentration", "mg/L", "simulator exposes cp", "Schnider; primary-source revalidation required"),
        ("propofol_ce", "effect-site concentration", "mg/L", "simulator exposes ce", "Schnider; primary-source revalidation required"),
        ("remifentanil_cp", "central plasma concentration", "microgram/L", "simulator exposes cp", "Minto; primary-source revalidation required"),
        ("remifentanil_ce", "effect-site concentration", "microgram/L", "simulator exposes ce", "Minto; primary-source revalidation required"),
    )
    for feature, definition, unit, exposure, source in feature_specs:
        s1_rows.append({
            "feature": feature,
            "exact_definition": definition,
            "unit": unit,
            "causal_availability": "yes within simulator; real-case mapping not implemented",
            "parameter_source": source,
            "pkpd_model_name": "Schnider" if feature.startswith("propofol") else "Minto",
            "patient_inputs": "age,sex,height,weight for PK features; none newly fitted",
            "simulator_exposure": exposure,
            "raw_signal_download_required": False,
            "possible_without_test_leakage": True,
            "depends_on_train_fitted_statistics": False,
            "status": "reusable after refactor",
            "phase7b_value_calculation": False,
        })

    policies = {
        "conditions": list(CONDITIONS),
        "trained_separately_from_scratch": True,
        "pretrained_checkpoint_reuse": False,
        "same_train_subjects": True,
        "same_test_subjects": True,
        "same_underlying_latent_trajectory_for_p0_p1": True,
        "same_evaluation_horizon": True,
        "pipeline_specific_episode_deletion_allowed": False,
        "every_test_subject_evaluated_under_all_four": True,
        "only_allowed_difference": "preprocessing pipeline and state representation; first input size may follow state dimension",
        "component_ablation_defined": False,
    }
    invariance = {
        "status": "equality_constraints_frozen_exact_values_pending_human_review",
        "common_fields": [
            "PPO implementation", "simulator", "reward", "target BIS", "action space",
            "action bounds", "actor hidden layers", "critic hidden layers", "activation",
            "optimizer", "learning rate", "discount factor", "GAE", "PPO clipping",
            "entropy coefficient", "value-loss coefficient", "rollout length",
            "minibatch size", "update epochs", "total environment steps",
            "patient sampling", "evaluation horizon", "termination", "seed set",
        ],
        "only_input_layer_size_may_differ": True,
        "architecture_exact_values": "pending_human_review",
        "training_budget_exact_value": "pending_human_review",
        "reward_exact_profile": "pending_human_review; latent true BIS preferred",
        "action_bounds_exact_values": "pending_human_review",
        "ppo_execution_authorized": False,
    }
    split = {
        "unit": "subjectid",
        "unique_subject_count": EXPECTED_SUBJECTS,
        "target_train_fraction": 0.8,
        "target_test_fraction": 0.2,
        "target_train_subject_count": EXPECTED_TRAIN_SUBJECTS,
        "target_test_subject_count": EXPECTED_TEST_SUBJECTS,
        "validation_split": False,
        "subject_cluster_integrity_required": True,
        "same_membership_for_all_conditions": True,
        "all_four_policies_per_test_subject": True,
        "split_created": False,
        "train_subject_ids_created": False,
        "test_subject_ids_created": False,
        "test_seal_created": False,
        "allocation_algorithm_and_balance_objective": "pending_human_review",
    }
    seeds = {
        "engineering_smoke_seed": SMOKE_SEED,
        "final_ppo_seeds": list(FINAL_SEEDS),
        "same_final_seeds_for_all_conditions": True,
        "best_seed_only_reporting_prohibited": True,
        "ppo_run_in_phase7b": False,
    }
    outcomes = {
        "primary": "subject_level_mean_absolute_BIS_target_error_mean_abs_BIS_minus_50",
        "secondary": [
            "percentage_time_BIS_40_60", "percentage_time_BIS_below_40",
            "percentage_time_BIS_above_60", "time_to_first_BIS_40_60",
            "cumulative_propofol_dose", "mean_absolute_action_change",
            "maximum_absolute_action_change", "safety_termination_rate", "episode_failure_rate",
        ],
        "preferred_bis_source": "latent_true_simulator_BIS",
        "reward_is_scientific_outcome": False,
        "calculated_in_phase7b": False,
    }
    stats = {
        "design": "repeated_measures_all_four_conditions_per_test_subject",
        "fixed_effects": ["preprocessing", "state", "preprocessing_by_state_interaction"],
        "random_or_blocking_effects": ["subjectid", "PPO_seed"],
        "subject_level_aggregation": True,
        "paired_comparisons": True,
        "effect_sizes": True,
        "confidence_interval_percent": 95,
        "summaries": ["mean_SD", "median_IQR"],
        "paired_bootstrap_unit": "subjectid",
        "secondary_outcome_multiplicity": "Holm",
        "episode_level_pseudoreplication": False,
        "component_effect_claims_allowed": False,
        "statistical_test_run_in_phase7b": False,
    }

    deprecation_rows = [
        {"item": item, "protocol_v1_3_status": "outside_confirmatory_scope", "retention": "historical_or_exploratory_code_and_docs_retained", "used_for_state_selection": False}
        for item in (
            "future BIS prediction", "persistence prediction baseline", "Elastic Net future-BIS prediction",
            "stability selection", "GRU prediction", "Attention-GRU prediction",
            "attention-weight feature ranking", "prediction MAE/RMSE state selection",
            "prediction-informed PPO state choice",
        )
    ]
    implementation_rows = [
        {"component": "Phase 6C exact candidate schemas and causal alignment audit", "location": "current cohort/causal_grid_feasibility.py and versioned artifacts", "classification": "already implemented and reusable", "notes": "schema and feasibility evidence only; not a PPO observation layer"},
        {"component": "current PPO actor critic and trainer", "location": "current rl package placeholder", "classification": "requires new implementation", "notes": "no executable current implementation"},
        {"component": "current anesthesia environment and simulator", "location": "current rl/pkpd package placeholders", "classification": "requires new implementation", "notes": "no executable current implementation"},
        {"component": "legacy simulator equations and interface", "location": "legacy src/pkpd allowlist", "classification": "reusable after refactor", "notes": "primary-source and unit revalidation required"},
        {"component": "legacy environment reward and action interfaces", "location": "legacy src/rl_env allowlist", "classification": "reusable after refactor", "notes": "common contract only; no result reuse"},
        {"component": "legacy state adapter schema", "location": "legacy src/rl_env/state_adapters.py", "classification": "reusable after refactor", "notes": "does not implement P0/P1 quality views"},
        {"component": "observation-quality replay/corruption layer", "location": "absent", "classification": "requires new implementation", "notes": "required before PPO"},
        {"component": "missing-observation fixed-shape encoding", "location": "undefined", "classification": "undefined and requires human decision", "notes": "mask/age/sentinel choice not approved"},
        {"component": "PPO architecture budget reward and action bound values", "location": "Protocol v1.3 invariance constraints", "classification": "undefined and requires human decision", "notes": "must be frozen before implementation"},
        {"component": "legacy PPO configs checkpoints splits scalers selected features metrics results", "location": "legacy rejected artifacts", "classification": "prohibited legacy artifact", "notes": "not read or migrated"},
    ]

    artifacts: dict[Path, bytes] = {}
    artifacts[MANIFESTS / "protocol_v1_3_p0_preprocessing.json"] = json_bytes(P0)
    artifacts[MANIFESTS / "protocol_v1_3_p1_preprocessing.json"] = json_bytes(P1)
    artifacts[MANIFESTS / "protocol_v1_3_preprocessing_comparison.csv"] = csv_bytes(preprocessing_comparison)
    artifacts[MANIFESTS / "protocol_v1_3_missing_observation_audit.json"] = json_bytes(missing_audit)
    artifacts[MANIFESTS / "protocol_v1_3_simulator_observation_feasibility.json"] = json_bytes(simulator_audit)
    artifacts[MANIFESTS / "protocol_v1_3_s0_state_schema.json"] = json_bytes(s0)
    artifacts[MANIFESTS / "protocol_v1_3_s1_state_schema.json"] = json_bytes(s1)
    artifacts[MANIFESTS / "protocol_v1_3_s1_feature_feasibility.csv"] = csv_bytes(s1_rows)
    artifacts[MANIFESTS / "protocol_v1_3_four_policy_spec.json"] = json_bytes(policies)
    artifacts[MANIFESTS / "protocol_v1_3_ppo_invariance_spec.json"] = json_bytes(invariance)
    artifacts[MANIFESTS / "protocol_v1_3_planned_subject_split.json"] = json_bytes(split)
    artifacts[MANIFESTS / "protocol_v1_3_seed_protocol.json"] = json_bytes(seeds)
    artifacts[MANIFESTS / "protocol_v1_3_control_outcomes.json"] = json_bytes(outcomes)
    artifacts[MANIFESTS / "protocol_v1_3_statistical_analysis_plan.json"] = json_bytes(stats)
    artifacts[MANIFESTS / "protocol_v1_3_prediction_scope_deprecation.csv"] = csv_bytes(deprecation_rows)
    artifacts[MANIFESTS / "protocol_v1_3_implementation_audit.csv"] = csv_bytes(implementation_rows)

    docs = {
        ROOT / "docs" / "protocol_v1_3_scope_revision_decision_record.md": """# Protocol v1.3 Scope-Revision Decision Record\n\nStatus: design frozen; implementation is not ready and PPO is not authorized.\n\n## Decision\n\nThe confirmatory question is now control-focused: how temporal signal preprocessing and state representation affect PPO-based propofol infusion control. Future BIS prediction and prediction-driven state selection are historical or exploratory and outside the Protocol v1.3 confirmatory analysis. Existing code and documents are retained but cannot determine the confirmatory state.\n\n## Unchanged cohort\n\nProtocol v1.2 remains frozen at 2,460 cases and 2,415 subjects. Its case-ID and cohort checksums, legacy-98 exclusion, volatile exclusion, invalid-window exclusion, and minimum-120-window rule are unchanged. The ten Phase 6D exclusions cannot re-enter through P0.\n\n## Boundary\n\nThis phase creates no split, test seal, modeling array, dose, Cp/Ce value, policy, checkpoint, prediction, control result, or statistical result.\n""",
        ROOT / "docs" / "control_focused_research_question.md": """# Control-Focused Research Question\n\n## Primary question\n\nHow do temporal signal preprocessing and state representation affect PPO-based propofol infusion control?\n\n## Confirmatory aim\n\nThe study compares target tracking near BIS 50, time in BIS 40–60, time below 40 and above 60, action smoothness, and stable closed-loop control. It does not ask which model best predicts future BIS.\n""",
        ROOT / "docs" / "control_focused_2x2_factorial_design.md": """# Control-Focused 2×2 Factorial Design\n\nThe four confirmatory conditions are P0S0, P1S0, P0S1, and P1S1. Each future policy must be trained independently from scratch and evaluated on the same test subjects. Preprocessing and state are the only intended factors; simulator, reward, action, PPO framework, capacity, budget, seeds, and evaluation must be invariant.\n\nP0 is the Phase 6C `sqi_not_required__bis30s__drug120s` bundle. P1 is `sqi_ge_50__bis20s__drug60s`. The design estimates bundle-level preprocessing effects only; it defines no SQI-only, BIS-staleness-only, or drug-hold-only ablation.\n\nS0 contains age, sex, height, weight and six 10-second samples each of BIS, propofol rate, and remifentanil rate. S1 is a strict conceptual superset adding recent and cumulative doses plus propofol/remifentanil Cp and Ce. SQI is quality control only and is absent from both states.\n""",
    }

    for path, payload in docs.items():
        artifacts[path] = payload.encode()

    legacy_after = legacy_state()
    if legacy_after != legacy_before:
        raise RuntimeError("legacy repository changed during read-only audit")
    tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    raw_tracked = [path for path in tracked if path.startswith("data/raw/")]
    if raw_tracked:
        raise RuntimeError("raw data is tracked by Git")

    source_snapshot = {
        "phase": "7B_protocol_v1_3_control_focused_design",
        "protocol_version": PROTOCOL_VERSION,
        "source_baseline_commit": SOURCE_BASELINE_COMMIT,
        "input_artifact_sha256": {
            name: sha256(MANIFESTS / name)
            for name in (
                "causal_grid_candidate_summary.csv",
                "causal_grid_feasibility_case_candidate_manifest.csv.gz",
                "final_eligible_cohort_manifest.csv",
                "final_eligible_caseids.csv",
                "subject_linkage_summary.json",
                "subject_linkage_case_manifest.csv",
            )
        },
        "expected_final_cohort_sha256": EXPECTED_FINAL_COHORT_SHA256,
        "expected_eligible_ids_sha256": EXPECTED_ELIGIBLE_IDS_SHA256,
        "expected_subject_linkage_sha256": EXPECTED_SUBJECT_LINKAGE_SHA256,
        "upstream_validation": upstream,
        "phase6c_connection": connection,
        "legacy_state_before": legacy_before,
        "legacy_state_after": legacy_after,
        "legacy_state_unchanged": True,
        "legacy_interface_audit": legacy_audit,
        "raw_signal_file_open_count": 0,
        "raw_git_tracked_count": 0,
        "outcome_access_count": 0,
        "execution_flags": PROHIBITED_EXECUTION,
    }
    artifacts[MANIFESTS / "protocol_v1_3_source_snapshot.json"] = json_bytes(source_snapshot)

    report = f"""# Phase 7B Control-Focused Design Report\n\n## Outcome\n\nProtocol v1.3 freezes a control-focused 2×2 design with P0/P1 preprocessing and S0/S1 state representation. The frozen Protocol v1.2 cohort remains {EXPECTED_CASES:,} cases across {EXPECTED_SUBJECTS:,} subjects. P0 and P1 each have {EXPECTED_PHASE6C_CASES:,} source-case rows in Phase 6C and each links to all {EXPECTED_CASES:,} frozen cases; none of the ten excluded cases is authorized to re-enter.\n\n## Feasibility finding\n\nThe inspected legacy simulator supplies an observed BIS at every simulator advance but has no SQI, BIS missingness, delayed-observation, or drug-rate-staleness layer. Its history mask represents episode-start padding, not signal availability. A new observation replay/corruption layer is therefore required before P0/P1 can produce meaningfully different controller views of one latent trajectory. Fixed-shape missing encoding is unresolved and requires human approval. Protocol v1.3 is not implementation-ready and PPO execution remains prohibited.\n\n## State and policy boundary\n\nS0 is the observable-history state; S1 is its strict conceptual superset with eight pharmacology candidates. Legacy dose and Cp/Ce interfaces are reference-only and require refactor plus primary-source revalidation. No value was calculated. Four future policies are named PPO_P0S0, PPO_P1S0, PPO_P0S1, and PPO_P1S1. Exact architecture, budget, reward profile, action bounds, and missing encoding remain pending human review but must be identical across conditions when frozen.\n\n## Planned design\n\nThe future split unit is subjectid with target counts {EXPECTED_TRAIN_SUBJECTS:,} train and {EXPECTED_TEST_SUBJECTS:,} test subjects and no formal validation split. No membership or seal was created. Smoke seed 42 and final seeds 7, 42, and 84 are predeclared; no PPO was run. Outcomes and repeated-measures statistics are specifications only.\n\n## Execution boundary\n\nNo raw signal, API, outcome, split, test seal, modeling array, normalization, imputation, dose, Cp/Ce, prediction, feature selection, PPO, checkpoint, evaluation, control metric, or statistical test was executed. Legacy checkpoints, configs, splits, scalers, selected features, metrics, and results were not read.\n"""
    artifacts[ROOT / "docs" / "phase7b_control_design_report.md"] = report.encode()

    for path, payload in artifacts.items():
        atomic_write(path, payload)

    checksum_rows = []
    for path in sorted(artifacts, key=lambda item: item.relative_to(ROOT).as_posix()):
        checksum_rows.append({
            "relative_path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        })
    checksum_path = MANIFESTS / "protocol_v1_3_artifact_checksums.json"
    atomic_write(checksum_path, json_bytes({"artifacts": checksum_rows, "self_excluded": True}))
    print(f"wrote {len(artifacts) + 1} Phase 7B artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
