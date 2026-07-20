from __future__ import annotations

import ast
import csv
import hashlib
import json
import subprocess
import unittest
from pathlib import Path

from vitaldb_state_selection.pkpd.registry import (
    BIS_PARAMETERS,
    F12_BY_VARIANT,
    F_PRIMARY_VALUES,
    H_VALUES,
    MintoF12Variant,
    PARAMETER_REGISTRY_ID,
    UNIT_CONTRACT,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "data" / "manifests"
PKPD = ROOT / "src" / "vitaldb_state_selection" / "pkpd"


def read_json(name: str) -> dict:
    return json.loads((MANIFESTS / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Phase7FArtifactTests(unittest.TestCase):
    def test_mc001_to_mc009_are_approved_and_mc010_to_mc034_remain_pending(self) -> None:
        decisions = read_json("phase7f_stage_i_human_decisions.json")
        approved = decisions["approved_decisions"]
        self.assertEqual([row["constant_id"] for row in approved], [f"MC-{i:03d}" for i in range(1, 10)])
        self.assertTrue(all(row["status"] == "approved_for_stage_i" for row in approved))
        self.assertEqual(decisions["still_pending_ids"], [f"MC-{i:03d}" for i in range(10, 35)])
        self.assertTrue(decisions["approval_does_not_extend_to_environment_or_ppo"])
        with (MANIFESTS / "protocol_v1_3_2_missing_constants.csv").open(encoding="utf-8", newline="") as stream:
            original = list(csv.DictReader(stream))
        pending = {row["constant_id"]: row["status"] for row in original}
        self.assertTrue(all(pending[f"MC-{i:03d}"] == "recommended_pending_human_approval" for i in range(10, 35)))

    def test_constant_and_unit_registries_match_implementation(self) -> None:
        constants = read_json("phase7f_pkpd_constant_registry.json")
        units = read_json("phase7f_pkpd_unit_contract.json")
        self.assertEqual(constants["registry_id"], PARAMETER_REGISTRY_ID)
        self.assertEqual(constants["propofol_schnider_h"], dict(H_VALUES))
        self.assertEqual(constants["remifentanil_minto_f_primary"], dict(F_PRIMARY_VALUES))
        self.assertEqual(constants["named_sensitivity_variants"]["sensitivity_yun_0.030"]["f12"],
                         F12_BY_VARIANT[MintoF12Variant.SENSITIVITY_YUN_0_030])
        self.assertEqual(constants["bis_response"]["baseline"], BIS_PARAMETERS["baseline"])
        self.assertFalse(constants["bis_response"]["noise_enabled"])
        self.assertEqual(units["propofol"]["infusion_rate"], UNIT_CONTRACT["propofol_infusion_rate"])
        self.assertEqual(units["remifentanil"]["infusion_rate"], UNIT_CONTRACT["remifentanil_infusion_rate"])
        self.assertIn("remifentanil_rate_microgram_per_min", units["public_advance_signature"])

    def test_equation_provenance_is_complete_and_legacy_free(self) -> None:
        with (MANIFESTS / "phase7f_pkpd_equation_provenance.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual([row["equation_id"] for row in rows], [f"EQ-{i:03d}" for i in range(1, 10)])
        self.assertTrue(all(row["primary_source"] and row["phase7e_evidence_id"] for row in rows))
        self.assertTrue(all(row["implementation_file"].startswith("src/vitaldb_state_selection/pkpd/") for row in rows))
        self.assertTrue(all("legacy" not in row["implementation_file"].lower() for row in rows))

    def test_synthetic_profiles_are_fixed_and_have_no_subject_identifiers(self) -> None:
        payload = read_json("phase7f_synthetic_profiles.json")
        self.assertEqual(len(payload["profiles"]), 3)
        self.assertTrue(all(row["synthetic"] is True for row in payload["profiles"]))
        self.assertEqual({row["sex"] for row in payload["profiles"]}, {"male", "female"})
        text = json.dumps(payload).lower()
        self.assertNotIn("caseid", text)
        self.assertNotIn("subjectid", text)

    def test_validation_summary_passes_prespecified_numerical_gates(self) -> None:
        summary = read_json("phase7f_pkpd_validation_summary.json")
        results = summary["results"]
        tolerances = summary["tolerances"]
        self.assertEqual(summary["profile_count"], 3)
        self.assertLessEqual(results["maximum_semigroup_absolute_error"], tolerances["semigroup_max_abs"])
        self.assertLessEqual(results["maximum_solve_ivp_absolute_error"], tolerances["solve_ivp_max_abs"])
        self.assertEqual(results["bis_monotonic_grid_violations"], 0)
        self.assertAlmostEqual(results["remifentanil_unit_regression_observed_ratio"], 1000.0, places=10)
        self.assertTrue(results["all_values_finite"])
        self.assertTrue(all(value is False for value in summary["execution_flags"].values()))

    def test_f12_sensitivity_is_closed_nondefault_and_numerical_only(self) -> None:
        config = read_json("phase7f_f12_sensitivity_config.json")
        self.assertEqual(config["primary"]["f12"], 0.0301)
        self.assertTrue(config["primary"]["default"])
        self.assertEqual(config["sensitivity_only"]["f12"], 0.030)
        self.assertFalse(config["sensitivity_only"]["default"])
        self.assertEqual(config["sensitivity_only"]["permitted_use"], "numerical_difference_report_only")
        self.assertFalse(config["other_variants_allowed"])

    def test_source_lineage_cohort_dependency_and_legacy_state_are_unchanged(self) -> None:
        source = read_json("phase7f_source_snapshot.json")
        self.assertEqual(source["source_remote_main_at_start"], "ba76c51f3a007581764c0f9b28b15a0bc31b9fe1")
        self.assertEqual((source["frozen_case_count"], source["frozen_subject_count"]), (2460, 2415))
        self.assertEqual(source["confirmatory_design"], "P0_P1_by_S0_S1")
        self.assertFalse(source["dependency_installed_or_modified"])
        for relative_path, expected in source["input_artifact_sha256"].items():
            self.assertEqual(sha256(ROOT / relative_path), expected, relative_path)
        self.assertEqual(source["legacy_state_before"], source["legacy_state_after"])
        legacy = ROOT.parent / "VitalDB-Feature-Selection"
        head = subprocess.check_output(
            ["git", "-c", "safe.directory=*", "rev-parse", "HEAD"], cwd=legacy, text=True
        ).strip()
        tree = subprocess.check_output(
            ["git", "-c", "safe.directory=*", "rev-parse", "HEAD^{tree}"], cwd=legacy, text=True
        ).strip()
        status = subprocess.check_output(
            ["git", "-c", "safe.directory=*", "status", "--short"], cwd=legacy, text=True
        ).splitlines()
        self.assertEqual({"head": head, "tree": tree, "status": status}, source["legacy_state_after"])

    def test_no_downstream_import_data_access_or_forbidden_artifact(self) -> None:
        banned_modules = {"gymnasium", "stable_baselines3", "vitaldb"}
        imported = set()
        for path in PKPD.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
        self.assertEqual(imported & banned_modules, set())
        source = read_json("phase7f_source_snapshot.json")
        self.assertTrue(all(value is False for value in source["execution_flags"].values()))
        tracked_raw = subprocess.check_output(
            ["git", "ls-files", "data/raw"], cwd=ROOT, text=True
        ).splitlines()
        self.assertEqual(tracked_raw, [])
        self.assertFalse((PKPD / "simulator.py").exists())
        self.assertFalse((ROOT / "src" / "vitaldb_state_selection" / "rl" / "environment.py").exists())
        self.assertFalse((ROOT / "src" / "vitaldb_state_selection" / "rl" / "ppo.py").exists())

    def test_reports_use_research_only_claim_boundary(self) -> None:
        report = (ROOT / "docs" / "phase7f_pkpd_scientific_validation_report.md").read_text(encoding="utf-8")
        phase = (ROOT / "docs" / "phase7f_report.md").read_text(encoding="utf-8")
        decision = (ROOT / "docs" / "phase7f_stage_i_decision_record.md").read_text(encoding="utf-8")
        combined = report + phase + decision
        self.assertIn("paper-grounded deterministic PK/PD reconstruction", combined)
        self.assertIn("synthetic numerical validation", combined)
        self.assertIn("MC-010 through MC-034 remain", combined)
        self.assertNotRegex(combined, r"[A-Za-z]:\\Users\\|/home/")

    def test_artifact_checksum_manifest(self) -> None:
        inventory = read_json("phase7f_artifact_checksums.json")
        self.assertTrue(inventory["self_excluded"])
        paths = [row["relative_path"] for row in inventory["artifacts"]]
        self.assertEqual(len(paths), len(set(paths)))
        for row in inventory["artifacts"]:
            path = ROOT / row["relative_path"]
            self.assertEqual(path.stat().st_size, row["bytes"], path)
            self.assertEqual(sha256(path), row["sha256"], path)


if __name__ == "__main__":
    unittest.main()
