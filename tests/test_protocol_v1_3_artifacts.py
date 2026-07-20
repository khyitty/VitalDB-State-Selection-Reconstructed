from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "data" / "manifests"


def read_json(name: str) -> dict:
    return json.loads((MANIFESTS / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (MANIFESTS / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ProtocolV13ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = read_json("protocol_v1_3_source_snapshot.json")
        cls.p0 = read_json("protocol_v1_3_p0_preprocessing.json")
        cls.p1 = read_json("protocol_v1_3_p1_preprocessing.json")
        cls.s0 = read_json("protocol_v1_3_s0_state_schema.json")
        cls.s1 = read_json("protocol_v1_3_s1_state_schema.json")
        cls.missing = read_json("protocol_v1_3_missing_observation_audit.json")
        cls.simulator = read_json("protocol_v1_3_simulator_observation_feasibility.json")
        cls.policies = read_json("protocol_v1_3_four_policy_spec.json")
        cls.invariance = read_json("protocol_v1_3_ppo_invariance_spec.json")
        cls.split = read_json("protocol_v1_3_planned_subject_split.json")

    def test_protocol_v1_2_cohort_and_subject_checksums_are_unchanged(self) -> None:
        self.assertEqual(self.source["expected_final_cohort_sha256"], "517683c574b642584ecaf6e0c7c8a2c1ec461e4eb2252277f0427c4c55065468")
        self.assertEqual(self.source["expected_eligible_ids_sha256"], "f2c140ccf150648c2d4f46029849f325742e58eaf16ecb30efa05299384fb9bd")
        self.assertEqual(self.source["expected_subject_linkage_sha256"], "102ccc60d9f03a8bfe858e5862366ef0b49f80cef3dcc027dae94afface464f7")
        self.assertEqual(sha256(MANIFESTS / "final_eligible_cohort_manifest.csv"), self.source["expected_final_cohort_sha256"])
        upstream = self.source["upstream_validation"]
        self.assertEqual(upstream["frozen_case_count"], 2460)
        self.assertEqual(upstream["frozen_subject_count"], 2415)
        self.assertFalse(upstream["cohort_changed"])
        self.assertFalse(upstream["subject_linkage_changed"])

    def test_phase6c_p0_p1_connection_is_complete_without_reinclusion(self) -> None:
        connection = self.source["phase6c_connection"]
        self.assertEqual(connection["p0_case_candidate_rows"], 2470)
        self.assertEqual(connection["p1_case_candidate_rows"], 2470)
        self.assertEqual(connection["p0_frozen_case_link_count"], 2460)
        self.assertEqual(connection["p1_frozen_case_link_count"], 2460)
        self.assertEqual(connection["source_excluded_case_count"], 10)
        self.assertEqual(connection["source_excluded_cases_authorized_for_protocol_v1_3"], 0)
        self.assertEqual(self.source["upstream_validation"]["excluded_cases_reintroduced"], 0)

    def test_inherited_legacy_volatile_and_invalid_exclusions_remain_zero(self) -> None:
        rows = read_csv("final_eligible_cohort_manifest.csv")
        eligible = [row for row in rows if row["final_eligible"] == "true"]
        self.assertEqual(len(eligible), 2460)
        for field in ("legacy_98_overlap", "volatile_excluded_overlap", "invalid_anesthesia_window_overlap"):
            self.assertEqual(sum(row[field] == "true" for row in eligible), 0, field)

    def test_exact_preprocessing_schemas_and_bundle_only_comparison(self) -> None:
        self.assertEqual(self.p0["candidate_id"], "sqi_not_required__bis30s__drug120s")
        self.assertEqual(self.p1["candidate_id"], "sqi_ge_50__bis20s__drug60s")
        self.assertEqual((self.p0["bis_staleness_cap_seconds"], self.p1["bis_staleness_cap_seconds"]), (30, 20))
        self.assertEqual((self.p0["propofol_rate_hold_cap_seconds"], self.p1["propofol_rate_hold_cap_seconds"]), (120, 60))
        comparison = read_csv("protocol_v1_3_preprocessing_comparison.csv")
        differences = [row for row in comparison if row["relationship"] == "bundle_difference"]
        self.assertEqual({row["component"] for row in differences}, {"SQI quality gating", "BIS staleness cap", "drug-rate hold cap"})
        self.assertFalse(self.policies["component_ablation_defined"])

    def test_s0_is_strict_subset_of_s1_and_sqi_is_absent(self) -> None:
        s0 = set(self.s0["static_features"] + self.s0["dynamic_features"])
        s1 = set(self.s1["inherited_static_features"] + self.s1["inherited_dynamic_features"] + self.s1["additional_features"])
        self.assertLess(s0, s1)
        self.assertEqual(len(self.s1["additional_features"]), 8)
        self.assertFalse(self.s0["sqi_numeric_value_included"])
        self.assertFalse(self.s1["sqi_numeric_value_included"])
        self.assertNotIn("bmi", s1)
        self.assertTrue(all("sqi" not in feature.lower() for feature in s1))
        feasibility = read_csv("protocol_v1_3_s1_feature_feasibility.csv")
        self.assertEqual(len(feasibility), 8)
        self.assertTrue(all(row["phase7b_value_calculation"] == "False" for row in feasibility))
        self.assertTrue(all(row["status"] == "reusable after refactor" for row in feasibility))

    def test_missing_encoding_is_not_overclaimed_and_simulator_is_not_ready(self) -> None:
        self.assertEqual(self.missing["status"], "undefined_and_requires_human_decision")
        self.assertFalse(self.missing["implementation_authorized"])
        self.assertTrue(self.missing["same_encoding_required_for_p0_and_p1"])
        self.assertTrue(self.missing["bis_zero_is_valid_not_missing"])
        self.assertTrue(self.missing["drug_rate_zero_is_valid_not_missing"])
        self.assertEqual(self.simulator["overall_status"], "requires_new_implementation")
        self.assertFalse(self.simulator["implementation_ready"])
        self.assertFalse(self.simulator["ppo_execution_authorized"])
        self.assertEqual(len(self.simulator["questions"]), 8)
        self.assertIn("not implementation-ready", self.simulator["claim_boundary"])

    def test_four_policies_and_ppo_invariance_are_complete_but_unimplemented(self) -> None:
        self.assertEqual({row["policy_id"] for row in self.policies["conditions"]}, {"PPO_P0S0", "PPO_P1S0", "PPO_P0S1", "PPO_P1S1"})
        self.assertTrue(self.policies["trained_separately_from_scratch"])
        self.assertFalse(self.policies["pretrained_checkpoint_reuse"])
        self.assertTrue(self.policies["same_underlying_latent_trajectory_for_p0_p1"])
        self.assertTrue(self.policies["same_evaluation_horizon"])
        self.assertFalse(self.policies["pipeline_specific_episode_deletion_allowed"])
        self.assertTrue(self.policies["every_test_subject_evaluated_under_all_four"])
        self.assertTrue(self.invariance["only_input_layer_size_may_differ"])
        self.assertEqual(self.invariance["architecture_exact_values"], "pending_human_review")
        self.assertFalse(self.invariance["ppo_execution_authorized"])

    def test_planned_split_and_seed_protocol_create_no_membership_or_seal(self) -> None:
        self.assertEqual(self.split["unit"], "subjectid")
        self.assertEqual((self.split["target_train_subject_count"], self.split["target_test_subject_count"]), (1932, 483))
        self.assertFalse(self.split["validation_split"])
        for field in ("split_created", "train_subject_ids_created", "test_subject_ids_created", "test_seal_created"):
            self.assertFalse(self.split[field], field)
        self.assertEqual(self.split["allocation_algorithm_and_balance_objective"], "pending_human_review")
        seeds = read_json("protocol_v1_3_seed_protocol.json")
        self.assertEqual(seeds["engineering_smoke_seed"], 42)
        self.assertEqual(seeds["final_ppo_seeds"], [7, 42, 84])
        self.assertFalse(seeds["ppo_run_in_phase7b"])

    def test_outcomes_and_statistics_are_plans_not_results(self) -> None:
        outcomes = read_json("protocol_v1_3_control_outcomes.json")
        stats = read_json("protocol_v1_3_statistical_analysis_plan.json")
        self.assertIn("subject_level_mean_absolute_BIS_target_error", outcomes["primary"])
        self.assertEqual(len(outcomes["secondary"]), 9)
        self.assertFalse(outcomes["reward_is_scientific_outcome"])
        self.assertFalse(outcomes["calculated_in_phase7b"])
        self.assertEqual(stats["fixed_effects"], ["preprocessing", "state", "preprocessing_by_state_interaction"])
        self.assertEqual(stats["paired_bootstrap_unit"], "subjectid")
        self.assertEqual(stats["secondary_outcome_multiplicity"], "Holm")
        self.assertFalse(stats["episode_level_pseudoreplication"])
        self.assertFalse(stats["statistical_test_run_in_phase7b"])

    def test_prediction_scope_is_deprecated_and_implementation_audit_is_explicit(self) -> None:
        deprecation = read_csv("protocol_v1_3_prediction_scope_deprecation.csv")
        self.assertEqual(len(deprecation), 9)
        self.assertTrue(all(row["protocol_v1_3_status"] == "outside_confirmatory_scope" for row in deprecation))
        self.assertTrue(all(row["used_for_state_selection"] == "False" for row in deprecation))
        audit = read_csv("protocol_v1_3_implementation_audit.csv")
        categories = {row["classification"] for row in audit}
        self.assertEqual(categories, {"already implemented and reusable", "reusable after refactor", "requires new implementation", "undefined and requires human decision", "prohibited legacy artifact"})

    def test_source_snapshot_proves_no_raw_outcome_split_or_model_execution(self) -> None:
        self.assertEqual(self.source["raw_signal_file_open_count"], 0)
        self.assertEqual(self.source["raw_git_tracked_count"], 0)
        self.assertEqual(self.source["outcome_access_count"], 0)
        for name, value in self.source["execution_flags"].items():
            self.assertIn(value, (False, 0), name)
        self.assertTrue(self.source["legacy_state_unchanged"])
        self.assertEqual(self.source["legacy_state_before"], self.source["legacy_state_after"])
        legacy = self.source["legacy_interface_audit"]
        self.assertEqual(legacy["rejected_config_read_count"], 0)
        self.assertEqual(legacy["checkpoint_read_count"], 0)
        self.assertEqual(legacy["result_read_count"], 0)
        self.assertEqual(subprocess.check_output(["git", "ls-files", "data/raw"], cwd=ROOT, text=True).splitlines(), [])

    def test_no_split_ids_model_arrays_checkpoints_or_phase7c_artifacts_exist(self) -> None:
        new_paths = [path.relative_to(ROOT).as_posix() for path in ROOT.rglob("protocol_v1_3*")]
        forbidden_tokens = ("train_ids", "test_ids", "test_seal", "modeling_array", "checkpoint", "phase7c")
        self.assertEqual([path for path in new_paths if any(token in path.lower() for token in forbidden_tokens)], [])

    def test_artifact_checksums_and_report_claim_boundary(self) -> None:
        inventory = read_json("protocol_v1_3_artifact_checksums.json")
        self.assertTrue(inventory["self_excluded"])
        self.assertEqual(len(inventory["artifacts"]), 21)
        for row in inventory["artifacts"]:
            path = ROOT / row["relative_path"]
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.stat().st_size, row["bytes"], path)
            self.assertEqual(sha256(path), row["sha256"], path)
        report = (ROOT / "docs" / "phase7b_control_design_report.md").read_text(encoding="utf-8")
        self.assertIn("not implementation-ready", report)
        self.assertIn("No raw signal, API, outcome, split", report)
        self.assertIn("none of the ten excluded cases is authorized to re-enter", report)

    def test_production_entrypoint_is_artifact_only_and_has_no_model_capability(self) -> None:
        code = (ROOT / "scripts" / "freeze_protocol_v1_3_design.py").read_text(encoding="utf-8")
        for prohibited in (
            "import requests", "VitalDBOpenAPI", "data / \"raw\"", "numpy", "pandas",
            "sklearn", "torch", "stable_baselines", "model.fit", "env.step",
        ):
            self.assertNotIn(prohibited, code)


if __name__ == "__main__":
    unittest.main()
