from __future__ import annotations

import csv
import hashlib
import json
import re
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


class ProtocolV132ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evidence = read_csv("protocol_v1_3_2_reconstruction_evidence.csv")
        cls.missing = read_csv("protocol_v1_3_2_missing_constants.csv")
        cls.sequence = read_json("protocol_v1_3_2_implementation_sequence.json")
        cls.validation = read_json("protocol_v1_3_2_scientific_validation_plan.json")
        cls.registry = read_json("protocol_v1_3_2_source_registry.json")
        cls.source = read_json("protocol_v1_3_2_source_snapshot.json")

    def test_evidence_schema_ids_and_closed_classifications(self) -> None:
        required = {
            "evidence_id",
            "domain",
            "item",
            "value_or_equation",
            "unit",
            "classification",
            "source_id",
            "source_location",
            "conflict_or_gap",
            "implementation_status",
            "notes",
        }
        self.assertEqual(set(self.evidence[0]), required)
        ids = [row["evidence_id"] for row in self.evidence]
        self.assertEqual(len(ids), len(set(ids)))
        allowed = {
            "explicit_in_primary_paper",
            "explicit_in_cited_primary_source",
            "derivable_without_new_assumption",
            "missing",
            "conflicting",
            "requires_human_decision",
        }
        self.assertTrue(all(row["classification"] in allowed for row in self.evidence))
        self.assertTrue(all(row["source_location"] and row["source_id"] for row in self.evidence))

    def test_all_h_and_f_constants_are_exactly_once(self) -> None:
        h_rows = [row for row in self.evidence if row["evidence_id"].startswith("CONST-H")]
        f_rows = [row for row in self.evidence if row["evidence_id"].startswith("CONST-F")]
        self.assertEqual([row["item"] for row in h_rows], [f"h{i}" for i in range(1, 18)])
        self.assertEqual([row["item"] for row in f_rows], [f"f{i}" for i in range(1, 19)])
        values = {row["item"]: row["value_or_equation"] for row in h_rows + f_rows}
        self.assertEqual(values["h1"], "4.27")
        self.assertEqual(values["h17"], "0.456")
        self.assertEqual(values["f1"], "5.1")
        self.assertIn("0.0301", values["f12"])
        self.assertEqual(values["f18"], "55")

    def test_required_pkpd_environment_and_ppo_items_are_present(self) -> None:
        items = {row["item"] for row in self.evidence}
        required = {
            "three_compartment_mass_balance",
            "lean_body_mass_male",
            "lean_body_mass_female",
            "plasma_concentration",
            "effect_site_equation",
            "bis_interaction",
            "gaussian_bis_noise",
            "numerical_integration_interval",
            "target_bis",
            "safe_bis_range",
            "state_variables",
            "action_definition",
            "action_range",
            "action_interval",
            "remifentanil_history_sampling",
            "episode_initialization",
            "transition_order",
            "reward_equation",
            "termination_condition",
            "evaluation_horizon",
            "policy_distribution",
            "ppo_clipped_loss",
            "value_loss",
            "gae_equation",
            "l2_term",
            "loss_coefficients",
            "network_architecture",
            "learning_rate",
            "optimizer",
            "training_epochs_or_budget",
            "gamma",
            "gae_lambda",
            "clip_epsilon",
            "batch_size",
            "rollout_length",
        }
        self.assertEqual(required - items, set())

    def test_conflicts_and_missing_values_are_not_overclaimed(self) -> None:
        by_item = {row["item"]: row for row in self.evidence}
        for item in ("lean_body_mass_male", "minto_Cl1", "minto_Cl2", "infusion_units", "action_range"):
            self.assertEqual(by_item[item]["classification"], "conflicting", item)
        for item in ("gaussian_bis_noise", "numerical_integration_interval", "episode_initialization", "termination_condition", "gamma", "gae_lambda", "batch_size", "rollout_length"):
            self.assertEqual(by_item[item]["classification"], "missing", item)
            self.assertEqual(by_item[item]["implementation_status"], "recommended_pending_human_approval", item)

    def test_missing_constant_register_has_all_required_decision_fields(self) -> None:
        self.assertGreaterEqual(len(self.missing), 30)
        required = {
            "constant_id",
            "domain",
            "constant_or_rule",
            "paper_disclosure",
            "sb3_or_gymnasium_standard_default",
            "legacy_candidate_read_only",
            "recommended_study_value",
            "sensitivity_risk",
            "status",
            "approval_note",
        }
        self.assertEqual(set(self.missing[0]), required)
        self.assertTrue(all(row["status"] == "recommended_pending_human_approval" for row in self.missing))
        for row in self.missing:
            self.assertTrue(all(row[field] for field in required), row["constant_id"])
        constants = {row["constant_or_rule"] for row in self.missing}
        self.assertIn("reward alpha", constants)
        self.assertIn("SB3 dependency version", constants)
        self.assertIn("BIS observation-age clip maximum", constants)
        self.assertIn("sex tensor encoding", constants)

    def test_source_registry_uses_primary_sources_and_correct_dois(self) -> None:
        sources = {row["source_id"]: row for row in self.registry["sources"]}
        self.assertEqual(sources["yun_2023"]["priority"], 1)
        self.assertEqual(sources["yun_2023"]["doi"], "10.1016/j.compbiomed.2023.106739")
        self.assertEqual(sources["yun_2024"]["doi"], "10.1109/TNNLS.2022.3190379")
        for source_id in ("schnider_1998", "minto_1997", "bouillon_2004", "ppo_2017", "gae_2015"):
            self.assertEqual(sources[source_id]["priority"], 2)
        self.assertEqual(self.registry["legacy_repository_role"], "read_only_reference_only")
        self.assertFalse(self.registry["laboratory_code_available"])
        self.assertEqual(self.registry["source_pdf_copies_added_to_repository"], 0)

    def test_protocol_lineage_cohort_and_upstream_artifacts_are_unchanged(self) -> None:
        self.assertEqual(self.source["source_remote_main_at_start"], "99e32a8a74472ebb07620d280b215f89b21cfe12")
        self.assertEqual((self.source["frozen_case_count"], self.source["frozen_subject_count"]), (2460, 2415))
        for relative_path, expected in self.source["input_artifact_sha256"].items():
            self.assertEqual(sha256(ROOT / relative_path), expected, relative_path)
        self.assertFalse(self.source["old_protocol_v1_3_1_artifacts_modified"])
        self.assertFalse(self.source["dependency_files_changed"])

    def test_sequence_has_six_ordered_unexecuted_gated_stages(self) -> None:
        stages = self.sequence["stages"]
        self.assertEqual([row["stage"] for row in stages], ["I", "II", "III", "IV", "V", "VI"])
        self.assertTrue(all(not row["executed_in_phase7e"] for row in stages))
        self.assertTrue(all(row["entry_gate"] and row["exit_gate"] for row in stages))
        self.assertIn("prefer validated library PPO for the standard clipped algorithm", stages[2]["scope"])
        self.assertIn("subject-level allocation", stages[4]["scope"])

    def test_validation_plan_is_synthetic_planning_only(self) -> None:
        self.assertEqual(self.validation["status"], "planned_not_executed")
        self.assertEqual(self.validation["validation_scope"], "synthetic_and_analytical_only")
        self.assertFalse(self.validation["executed_in_phase7e"])
        groups = {row["group"] for row in self.validation["validation_groups"]}
        self.assertEqual(
            groups,
            {
                "parameter_and_unit_registry",
                "three_compartment_dynamics",
                "effect_site_and_bis",
                "conflict_sensitivity",
                "environment_contract",
                "ppo_integration",
            },
        )

    def test_no_implementation_dependency_split_raw_or_ppo_execution(self) -> None:
        self.assertTrue(all(value is False for value in self.source["execution_flags"].values()))
        self.assertEqual(subprocess.check_output(["git", "ls-files", "data/raw"], cwd=ROOT, text=True).splitlines(), [])
        prohibited_files = (
            ROOT / "src" / "vitaldb_state_selection" / "pkpd" / "simulator.py",
            ROOT / "src" / "vitaldb_state_selection" / "rl" / "environment.py",
            ROOT / "src" / "vitaldb_state_selection" / "rl" / "ppo.py",
        )
        self.assertTrue(all(not path.exists() for path in prohibited_files))
        self.assertEqual(sha256(ROOT / "pyproject.toml"), self.source["input_artifact_sha256"]["pyproject.toml"])

    def test_reports_retire_path_a_without_modifying_v131(self) -> None:
        amendment = (ROOT / "docs" / "protocol_v1_3_2_amendment_decision_record.md").read_text(encoding="utf-8")
        report = (ROOT / "docs" / "phase7e_paper_grounded_reconstruction_specification.md").read_text(encoding="utf-8")
        self.assertIn("paper-grounded independent reconstruction", amendment)
        self.assertIn("Path A", amendment)
        self.assertIn("retired", amendment)
        self.assertIn("2,460 cases and 2,415 subjects", amendment)
        self.assertIn("not an implementation or reproduction claim", report)
        self.assertNotRegex(amendment + report, r"[A-Za-z]:\\Users\\|/home/")

    def test_artifact_checksum_manifest(self) -> None:
        inventory = read_json("protocol_v1_3_2_artifact_checksums.json")
        self.assertTrue(inventory["self_excluded"])
        paths = [row["relative_path"] for row in inventory["artifacts"]]
        self.assertEqual(len(paths), len(set(paths)))
        for row in inventory["artifacts"]:
            path = ROOT / row["relative_path"]
            self.assertEqual(path.stat().st_size, row["bytes"], path)
            self.assertEqual(sha256(path), row["sha256"], path)

    def test_legacy_snapshot_is_unchanged_and_no_artifact_reused(self) -> None:
        self.assertTrue(self.source["legacy_state_unchanged"])
        self.assertEqual(self.source["legacy_state_before"], self.source["legacy_state_after"])
        self.assertEqual(self.source["legacy_artifacts_reused"], [])


if __name__ == "__main__":
    unittest.main()
