from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
MANIFESTS = ROOT / "data" / "manifests"
SEAL = MANIFESTS / "phase8a_test_seal.json"


def read_csv(name: str) -> list[dict[str, str]]:
    with (MANIFESTS / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless(SEAL.is_file(), "official Phase 8A artifacts not generated yet")
class Phase8AArtifactTests(unittest.TestCase):
    def test_exact_subject_and_case_accounting_without_leakage(self) -> None:
        subjects = read_csv("phase8a_subject_split_manifest.csv")
        cases = read_csv("phase8a_case_split_manifest.csv")
        self.assertEqual(len(subjects), 2415)
        self.assertEqual(len({row["subjectid"] for row in subjects}), 2415)
        self.assertEqual(Counter(row["assigned_split"] for row in subjects), {"train": 1932, "test": 483})
        self.assertEqual(len(cases), 2460)
        self.assertEqual(len({row["caseid"] for row in cases}), 2460)
        parent = {row["subjectid"]: row["assigned_split"] for row in subjects}
        self.assertEqual(sum(row["assigned_split"] != parent[row["subjectid"]] for row in cases), 0)
        self.assertEqual({row["subjectid"] for row in subjects if row["assigned_split"] == "train"} &
                         {row["subjectid"] for row in subjects if row["assigned_split"] == "test"}, set())

    def test_strata_hamilton_and_rank_fields_are_complete(self) -> None:
        strata = read_csv("phase8a_stratum_allocation.csv")
        subjects = read_csv("phase8a_subject_split_manifest.csv")
        self.assertEqual(len(strata), 24)
        self.assertEqual(sum(int(row["stratum_subject_count"]) for row in strata), 2415)
        self.assertEqual(sum(int(row["final_test_quota"]) for row in strata), 483)
        self.assertTrue(all(row["split_seed"] == "20260720" for row in subjects))
        self.assertTrue(all(row["allocation_method"] == "hamilton_stratified_sha256_rank_v1" for row in subjects))
        self.assertEqual({row["assigned_split"] for row in subjects}, {"train", "test"})

    def test_id_manifests_are_exact_public_membership(self) -> None:
        subjects = read_csv("phase8a_subject_split_manifest.csv")
        cases = read_csv("phase8a_case_split_manifest.csv")
        for split in ("train", "test"):
            subject_ids = {row["subjectid"] for row in read_csv(f"phase8a_{split}_subject_ids.csv")}
            case_ids = {row["caseid"] for row in read_csv(f"phase8a_{split}_case_ids.csv")}
            self.assertEqual(subject_ids, {row["subjectid"] for row in subjects if row["assigned_split"] == split})
            self.assertEqual(case_ids, {row["caseid"] for row in cases if row["assigned_split"] == split})

    def test_test_seal_hashes_and_false_flags_recompute(self) -> None:
        from vitaldb_state_selection.cohort.split_guard import seal_payload_sha256
        from vitaldb_state_selection.cohort.subject_split import sorted_identifier_sha256

        seal = json.loads(SEAL.read_text(encoding="utf-8"))
        self.assertEqual(seal_payload_sha256(seal), seal["seal_payload_sha256"])
        hashes = {
            "sha256_full_subject_split_manifest": sha256(MANIFESTS / "phase8a_subject_split_manifest.csv"),
            "sha256_full_case_split_manifest": sha256(MANIFESTS / "phase8a_case_split_manifest.csv"),
            "sha256_stratum_allocation": sha256(MANIFESTS / "phase8a_stratum_allocation.csv"),
            "sha256_metadata_balance_table": sha256(MANIFESTS / "phase8a_metadata_balance_table.csv"),
            "sha256_sorted_train_subject_ids": sorted_identifier_sha256(read_csv("phase8a_train_subject_ids.csv"), "subjectid"),
            "sha256_sorted_test_subject_ids": sorted_identifier_sha256(read_csv("phase8a_test_subject_ids.csv"), "subjectid"),
            "sha256_sorted_train_case_ids": sorted_identifier_sha256(read_csv("phase8a_train_case_ids.csv"), "caseid"),
            "sha256_sorted_test_case_ids": sorted_identifier_sha256(read_csv("phase8a_test_case_ids.csv"), "caseid"),
        }
        for field, value in hashes.items():
            self.assertEqual(seal[field], value)
        self.assertEqual(seal["split_generation_count"], 1)
        self.assertTrue(seal["membership_public"])
        self.assertEqual(seal["seal_purpose"], "integrity_not_secrecy")
        for field in (
            "test_raw_accessed", "test_template_created", "test_outcome_accessed",
            "ppo_tuned_on_test", "ppo_trained", "alternate_seed_search_performed",
            "balance_optimized_seed_selection",
        ):
            self.assertFalse(seal[field])

    def test_balance_roles_formulas_and_publication_gate(self) -> None:
        rows = read_csv("phase8a_metadata_balance_table.csv")
        summary = json.loads((MANIFESTS / "phase8a_metadata_balance_summary.json").read_text(encoding="utf-8"))
        continuous = [row for row in rows if row["analysis_level"] == "subject_primary_continuous"]
        self.assertEqual({row["variable"] for row in continuous}, {
            "subject_age_median", "subject_height_median_cm", "subject_weight_median_kg", "subject_case_count"
        })
        self.assertTrue(all(row["quantile_method"] == "linear_interpolation_position_n_minus_1" for row in continuous))
        self.assertEqual(summary["sample_sd_ddof"], 1)
        self.assertTrue(summary["membership_fixed_before_balance"])
        self.assertTrue(summary["publication_gate_passed"])
        self.assertLessEqual(summary["maximum_absolute_primary_continuous_smd"], 0.20)
        self.assertEqual(summary["signal_derived_variable_count"], 0)
        forbidden = {"bis", "sqi", "propofol", "remifentanil", "cp", "ce", "reward", "outcome"}
        self.assertFalse(any(any(token in row["variable"].lower() for token in forbidden) for row in rows))
        secondary = [row for row in rows if row["analysis_level"] == "case_secondary_categorical"]
        self.assertTrue(secondary)
        self.assertTrue(all(row["allocation_role"] == "secondary_descriptive_warning_only" for row in secondary))

    def test_source_snapshot_records_strict_boundary(self) -> None:
        snapshot = json.loads((MANIFESTS / "phase8a_source_snapshot.json").read_text(encoding="utf-8"))
        self.assertEqual(snapshot["starting_local_head"], "22448d447d7e07941a3dc2139cb2eae0d76bd511")
        self.assertEqual(snapshot["starting_remote_tracking_main"], snapshot["starting_local_head"])
        self.assertTrue(snapshot["source_worktree_clean"])
        self.assertTrue(snapshot["source_index_clean"])
        self.assertTrue(snapshot["previous_phase_artifacts_unchanged"])
        self.assertTrue(snapshot["legacy_state_unchanged"])
        self.assertEqual(snapshot["raw_signal_file_open_count"], 0)
        self.assertEqual(snapshot["api_request_count"], 0)
        self.assertEqual(snapshot["outcome_access_count"], 0)
        for field in (
            "observation_template_created", "preprocessing_array_created", "normalization_fitted",
            "simulator_real_subject_run", "ppo_training_run", "ppo_evaluation_run",
            "checkpoint_created", "alternate_seed_search_performed", "dependency_change",
        ):
            self.assertFalse(snapshot[field])

    def test_artifact_inventory_is_stable_complete_and_self_excluded(self) -> None:
        inventory = json.loads((MANIFESTS / "phase8a_artifact_checksums.json").read_text(encoding="utf-8"))
        self.assertTrue(inventory["self_excluded"])
        paths = [entry["relative_path"] for entry in inventory["artifacts"]]
        self.assertEqual(paths, sorted(paths))
        self.assertNotIn("data/manifests/phase8a_artifact_checksums.json", paths)
        self.assertNotIn("PHASE_STATUS.md", paths)
        self.assertIn("data/manifests/phase8a_test_seal.json", paths)
        for entry in inventory["artifacts"]:
            path = ROOT / entry["relative_path"]
            self.assertEqual(path.stat().st_size, entry["bytes"])
            self.assertEqual(sha256(path), entry["sha256"])

    def test_prior_phase_checksum_inventories_still_match(self) -> None:
        for name in (
            "protocol_v1_2_artifact_checksums.json", "subject_linkage_artifact_checksums.json",
            "phase7f_artifact_checksums.json", "phase7g_artifact_checksums.json", "phase7h_artifact_checksums.json",
        ):
            inventory = json.loads((MANIFESTS / name).read_text(encoding="utf-8"))
            entries = inventory.get("artifacts") if isinstance(inventory, dict) else None
            if entries is None:
                entries = [{"relative_path": key, "sha256": value} for key, value in inventory.items()]
            for entry in entries:
                self.assertEqual(sha256(ROOT / entry["relative_path"]), entry["sha256"], entry["relative_path"])

    def test_verify_only_is_byte_identical_and_generation_is_refused(self) -> None:
        before = {path: sha256(path) for path in MANIFESTS.glob("phase8a_*")}
        result = subprocess.run(
            [sys.executable, "scripts/run_phase8a_subject_split.py", "--verify-only"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        after = {path: sha256(path) for path in MANIFESTS.glob("phase8a_*")}
        self.assertEqual(before, after)
        refused = subprocess.run(
            [sys.executable, "scripts/run_phase8a_subject_split.py"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("generation refused", refused.stderr)

    def test_phase8a_source_boundary_has_no_network_raw_or_rl_import(self) -> None:
        for relative in (
            "src/vitaldb_state_selection/cohort/subject_split.py",
            "src/vitaldb_state_selection/cohort/split_guard.py",
            "scripts/run_phase8a_subject_split.py",
        ):
            tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
            modules = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules.add(node.module)
            forbidden_external = {"requests", "vitaldb", "gymnasium", "stable_baselines3"}
            forbidden_internal_segments = (".pkpd", ".anesthesia", ".rl_integration")
            self.assertFalse(
                any(
                    module.split(".")[0] in forbidden_external
                    or any(segment in module for segment in forbidden_internal_segments)
                    for module in modules
                ),
                relative,
            )

    def test_no_dependency_raw_model_or_checkpoint_change(self) -> None:
        self.assertEqual(
            sha256(ROOT / "pyproject.toml"),
            "0e403ab599452d41b32938e2a558a69af326e398229f8657d2a6fa24efbc9ff8",
        )
        tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
        forbidden = [path for path in tracked if path.startswith(("data/raw/", "data/modeling/", "checkpoints/"))]
        forbidden += [path for path in tracked if path.startswith("outputs/") and path != "outputs/.gitkeep"]
        self.assertEqual(forbidden, [])
        self.assertEqual(
            subprocess.check_output(["git", "check-ignore", ".venv-phase7h"], cwd=ROOT, text=True).strip(),
            ".venv-phase7h",
        )


if __name__ == "__main__":
    unittest.main()
