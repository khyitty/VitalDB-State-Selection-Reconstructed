from __future__ import annotations

import ast
import csv
import json
import re
import subprocess
import tomllib
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]


def read_yaml(relative: str) -> dict:
    return yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))


class GovernanceTests(unittest.TestCase):
    def test_protocol_documents_have_expected_topology(self) -> None:
        expected = {
            "docs/research_reset_protocol_v1.md": ("# 1. Research Reset Protocol v1", "1", 18),
            "docs/repository_migration_plan.md": ("# 2. 새 Repository Migration Plan", "2", 7),
            "docs/eligibility_audit_plan.md": ("# 3. 전체 VitalDB Eligibility Audit 실행 계획", "3", 15),
        }
        for relative, (title, prefix, count) in expected.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertEqual(text.splitlines()[0], title)
            section_numbers = re.findall(rf"^## ({prefix}\.\d+)(?:\s|$)", text, re.MULTILINE)
            self.assertEqual(
                section_numbers,
                [f"{prefix}.{number}" for number in range(1, count + 1)],
            )

    def test_repository_skeleton_and_warning_documents_exist(self) -> None:
        required = {
            ".gitignore",
            "README.md",
            "PHASE_STATUS.md",
            "pyproject.toml",
            "configs/eligibility_audit.yaml",
            "configs/track_aliases.yaml",
            "docs/claim_boundary.md",
            "docs/legacy_98case_statement.md",
            "docs/migration_provenance.csv",
            "schemas/eligibility_manifest.schema.json",
            "schemas/download_manifest.schema.json",
            "schemas/signal_quality_manifest.schema.json",
            "src/vitaldb_state_selection/cohort/__init__.py",
            "src/vitaldb_state_selection/data/__init__.py",
        }
        missing = sorted(path for path in required if not (ROOT / path).is_file())
        self.assertEqual(missing, [])
        warning = (ROOT / "docs/legacy_98case_statement.md").read_text(encoding="utf-8")
        self.assertIn("non-random", warning)
        self.assertIn("not confirmatory", warning)
        self.assertIn("rather than an exact reproduction", warning)

    def test_readme_scope_is_phase_limited(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        normalized = " ".join(text.split())
        for required in (
            "repository governance and provenance",
            "fixed-seed random 25-case engineering dry runs",
            "Phase 5A full 1–6388 `/cases` metadata and `/trks` inventory audit",
            "Phase 5B outcome-blind eligibility decision-support audit",
            "Phase 5C outcome-blind characterization of seven exact volatile tracks",
            "full signal download",
            "final quality thresholds",
            "PPO training",
            "Dry-run output is engineering evidence only. It is not a scientific result",
        ):
            self.assertIn(required, normalized)

    def test_audit_config_has_full_range_and_no_decided_thresholds(self) -> None:
        config = read_yaml("configs/eligibility_audit.yaml")
        self.assertEqual(config["expected_case_range"], {"start": 1, "end": 6388})
        self.assertTrue(config["production_mode"])
        self.assertFalse(config["allow_case_limit"])
        self.assertFalse(config["allow_first_n"])
        self.assertTrue(config["exclude_legacy_98"])
        thresholds = dict(config["quality_thresholds"])
        self.assertEqual(thresholds.pop("status"), "pending_human_review")
        self.assertTrue(thresholds)
        self.assertTrue(all(value is None for value in thresholds.values()))

    def test_only_explicit_protocol_aliases_are_active(self) -> None:
        config = read_yaml("configs/track_aliases.yaml")
        self.assertEqual(config["review_policy"], "human_approval_required")
        expected = {
            "bis": ["BIS/BIS"],
            "propofol_rate": ["Orchestra/PPF20_RATE"],
            "remifentanil_rate": ["Orchestra/RFTN20_RATE"],
        }
        self.assertEqual(set(config["aliases"]), set(expected))
        for concept, names in expected.items():
            self.assertEqual(config["aliases"][concept]["status"], "protocol_validated")
            self.assertEqual(config["aliases"][concept]["unit_status"], "validated")
            self.assertEqual(config["aliases"][concept]["names"], names)
        self.assertFalse(set(expected) & set(config["pending_concepts"]))
        sqi = config["qc_only_exact_tracks"]["bis_sqi"]
        self.assertEqual(sqi["names"], ["BIS/SQI"])
        self.assertFalse(sqi["prediction_feature_allowed"])
        self.assertFalse(sqi["ppo_state_allowed"])
        rftn50 = config["unused_exact_tracks"]["remifentanil_50_rate"]
        self.assertFalse(rftn50["merged_with_rftn20"])
        self.assertFalse(rftn50["used_in_phase6a"])

    def test_json_schemas_are_valid_and_reject_invalid_identity(self) -> None:
        schemas = {}
        for path in sorted((ROOT / "schemas").glob("*.json")):
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            schemas[path.name] = schema
        self.assertEqual(
            set(schemas),
            {
                "download_manifest.schema.json",
                "engineering_dry_run.schema.json",
                "eligibility_manifest.schema.json",
                "signal_quality_manifest.schema.json",
            },
        )
        eligibility = schemas["eligibility_manifest.schema.json"]
        validator = Draft202012Validator(eligibility)
        minimal = {}
        for name, spec in eligibility["properties"].items():
            value_types = spec.get("type", "string")
            value_types = {value_types} if isinstance(value_types, str) else set(value_types)
            if "null" in value_types:
                minimal[name] = None
            elif "boolean" in value_types:
                minimal[name] = False
            elif "integer" in value_types:
                minimal[name] = 1
            elif "number" in value_types:
                minimal[name] = 1.0
            elif "array" in value_types:
                minimal[name] = []
            elif "object" in value_types:
                minimal[name] = {}
            elif "enum" in spec:
                minimal[name] = spec["enum"][0]
            else:
                minimal[name] = "synthetic"
        minimal.update(
            caseid=1,
            audit_status="failed",
            failure_type="synthetic",
            failure_message="expected test record",
        )
        validator.validate(minimal)
        self.assertTrue(list(validator.iter_errors({**minimal, "caseid": 0})))
        self.assertTrue(list(validator.iter_errors({**minimal, "unknown": True})))

    def test_pyproject_declares_runtime_contract(self) -> None:
        with (ROOT / "pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream)["project"]
        self.assertEqual(project["name"], "vitaldb-state-selection")
        self.assertEqual(project["requires-python"], ">=3.11")
        dependencies = {item.split(">=")[0] for item in project["dependencies"]}
        self.assertEqual(dependencies, {"jsonschema", "PyYAML", "requests"})

    def test_gitignore_blocks_research_artifacts_but_not_manifests(self) -> None:
        candidates = [
            "data/raw/cases/1/bis.parquet",
            "data/processed/model.csv",
            "data/modeling/train.npz",
            "outputs/run/metrics.json",
            "checkpoints/model.pt",
            "data/manifests/example.csv",
        ]
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "-z", "--stdin"],
            cwd=ROOT,
            input=("\0".join(candidates) + "\0").encode("utf-8"),
            capture_output=True,
            check=False,
        )
        self.assertIn(result.returncode, (0, 1), result.stderr.decode(errors="replace"))
        ignored = {
            item.decode("utf-8") for item in result.stdout.split(b"\0") if item
        }
        self.assertEqual(ignored, set(candidates[:-1]))

    def test_git_index_contains_no_data_dependent_artifacts(self) -> None:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        tracked = {
            item.decode("utf-8") for item in result.stdout.split(b"\0") if item
        }
        forbidden_extensions = {".ckpt", ".npy", ".npz", ".onnx", ".parquet", ".pt", ".pth"}
        forbidden = {
            path
            for path in tracked
            if (
                (path.startswith("data/") and not path.startswith("data/manifests/"))
                or (path.startswith("outputs/") and path != "outputs/.gitkeep")
                or Path(path).suffix.lower() in forbidden_extensions
            )
        }
        self.assertEqual(forbidden, set())

    def test_blocked_research_packages_have_no_executable_implementation(self) -> None:
        blocked = ("pkpd", "prediction", "selection", "rl")
        for package in blocked:
            files = list((ROOT / "src" / "vitaldb_state_selection" / package).glob("*.py"))
            self.assertEqual([path.name for path in files], ["__init__.py"])
            tree = ast.parse(files[0].read_text(encoding="utf-8"))
            executable = [
                node
                for node in tree.body
                if not (
                    isinstance(node, ast.Expr)
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                )
            ]
            self.assertEqual(executable, [])

    def test_migration_provenance_contract_is_exact(self) -> None:
        with (ROOT / "docs/migration_provenance.csv").open(
            encoding="utf-8", newline=""
        ) as stream:
            rows = [row for row in csv.reader(stream) if row]
        self.assertEqual(
            rows[0],
            [
                "target_path",
                "source_repository",
                "source_path",
                "source_commit_sha",
                "migration_type",
                "scientific_dependency",
                "required_tests",
                "audit_status",
                "migration_date",
                "notes",
            ],
        )

    def test_compliance_matrix_does_not_overclaim_pending_requirements(self) -> None:
        with (ROOT / "docs/compliance_matrix.csv").open(
            encoding="utf-8", newline=""
        ) as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(
            list(rows[0]),
            [
                "requirement",
                "implemented file",
                "relevant line or section",
                "automated test",
                "status",
                "notes",
            ],
        )
        self.assertEqual(len({row["requirement"] for row in rows}), len(rows))
        allowed_statuses = {"implemented", "blocked_by_protocol", "pending"}
        self.assertTrue(rows)
        for row in rows:
            self.assertIn(row["status"], allowed_statuses)
            if row["status"] != "pending":
                paths = [item.strip() for item in row["implemented file"].split(";")]
                self.assertTrue(all((ROOT / path).exists() for path in paths))
                self.assertRegex(
                    row["automated test"],
                    r"^[A-Za-z][A-Za-z0-9_]*\.test_[A-Za-z0-9_]+$",
                )
                qualified_tests = set()
                for test_path in (ROOT / "tests").glob("test_*.py"):
                    tree = ast.parse(test_path.read_text(encoding="utf-8"))
                    for node in tree.body:
                        if isinstance(node, ast.ClassDef):
                            qualified_tests.update(
                                f"{node.name}.{item.name}"
                                for item in node.body
                                if isinstance(item, ast.FunctionDef)
                                and item.name.startswith("test_")
                            )
                self.assertIn(row["automated test"], qualified_tests)
        pending = {row["requirement"] for row in rows if row["status"] == "pending"}
        self.assertIn("Final signal-quality thresholds are chosen by human review", pending)
        self.assertNotIn("All 6388 production cases receive exactly one manifest row", pending)
        self.assertNotIn("Random 25-case signal dry run completes with checksums", pending)

    def test_phase_status_has_gate_and_failure_record_contract(self) -> None:
        text = (ROOT / "PHASE_STATUS.md").read_text(encoding="utf-8")
        self.assertIn("## Failure record template", text)
        for field in (
            "failed_gate",
            "failure_reason",
            "commands",
            "generated_files",
            "remaining_work",
            "local_commit_sha",
            "push_error",
        ):
            self.assertIn(f"- `{field}`:", text)


if __name__ == "__main__":
    unittest.main()
