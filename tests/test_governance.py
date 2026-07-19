from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class GovernanceTests(unittest.TestCase):
    def test_protocol_documents_and_warnings_exist(self) -> None:
        required = [
            ROOT / "docs" / "research_reset_protocol_v1.md",
            ROOT / "docs" / "repository_migration_plan.md",
            ROOT / "docs" / "eligibility_audit_plan.md",
            ROOT / "docs" / "legacy_98case_statement.md",
            ROOT / "docs" / "claim_boundary.md",
        ]
        self.assertTrue(all(path.is_file() for path in required))
        warning = (ROOT / "docs" / "legacy_98case_statement.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("non-random", warning)
        self.assertIn("not confirmatory", warning)
        self.assertIn("rather than an exact reproduction", warning)

    def test_quality_thresholds_are_not_decided(self) -> None:
        config = yaml.safe_load(
            (ROOT / "configs" / "eligibility_audit.yaml").read_text(
                encoding="utf-8"
            )
        )
        thresholds = config["quality_thresholds"]
        self.assertEqual(thresholds.pop("status"), "pending_human_review")
        self.assertTrue(thresholds)
        self.assertTrue(all(value is None for value in thresholds.values()))

    def test_only_protocol_validated_track_aliases_are_active(self) -> None:
        config = yaml.safe_load(
            (ROOT / "configs" / "track_aliases.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(config["review_policy"], "human_approval_required")
        for item in config["aliases"].values():
            self.assertEqual(item["status"], "protocol_validated")
            self.assertEqual(len(item["names"]), 1)

    def test_json_schemas_and_pyproject_parse(self) -> None:
        for path in sorted((ROOT / "schemas").glob("*.json")):
            self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)
        with (ROOT / "pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream)
        self.assertEqual(project["project"]["name"], "vitaldb-state-selection")

    def test_data_and_output_directories_contain_no_artifacts(self) -> None:
        allowed = {".gitkeep"}
        for relative in ("data", "outputs"):
            root = ROOT / relative
            if root.exists():
                unexpected = [
                    path
                    for path in root.rglob("*")
                    if path.is_file() and path.name not in allowed
                ]
                self.assertEqual(unexpected, [])


if __name__ == "__main__":
    unittest.main()
