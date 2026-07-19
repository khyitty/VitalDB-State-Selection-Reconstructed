from __future__ import annotations

import csv
import json
import subprocess
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "migration_provenance.csv"
SNAPSHOT = ROOT / "docs" / "legacy_source_snapshot.json"
PHASE2_SUBJECT = "Inventory legacy migration candidates"
PHASE2_ALLOWED_FILES = {
    "PHASE_STATUS.md",
    "docs/compliance_matrix.csv",
    "docs/legacy_source_snapshot.json",
    "docs/migration_inventory_summary.md",
    "docs/migration_provenance.csv",
    "tests/test_governance.py",
    "tests/test_migration_inventory.py",
}


def read_inventory() -> list[dict[str, str]]:
    with INVENTORY.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


class MigrationInventoryTests(unittest.TestCase):
    def test_inventory_has_exact_snapshot_coverage(self) -> None:
        rows = read_inventory()
        snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), snapshot["tracked_file_count"])
        source_paths = [row["source_path"] for row in rows]
        self.assertEqual(len(source_paths), len(set(source_paths)))
        self.assertEqual(source_paths, sorted(source_paths))
        self.assertEqual({row["source_commit_sha"] for row in rows}, {snapshot["source_commit_sha"]})
        self.assertEqual({row["source_repository"] for row in rows}, {snapshot["source_repository"]})

    def test_every_row_has_complete_allowed_classification(self) -> None:
        rows = read_inventory()
        required_columns = {
            "target_path", "source_repository", "source_path", "source_commit_sha",
            "migration_type", "scientific_dependency", "required_tests",
            "audit_status", "migration_date", "notes",
        }
        self.assertEqual(set(rows[0]), required_columns)
        for row in rows:
            self.assertTrue(all(row[column].strip() for column in required_columns))
            self.assertIn(row["migration_type"], {"copy", "refactor", "rewrite", "reject"})
            self.assertIn(row["scientific_dependency"], {"yes", "no", "mixed"})
            self.assertIn(row["audit_status"], {"pending", "rejected"})
            if row["migration_type"] == "reject":
                self.assertEqual(row["target_path"], "NOT_MIGRATED")
                self.assertEqual(row["audit_status"], "rejected")
            else:
                self.assertEqual(row["audit_status"], "pending")

    def test_data_dependent_artifacts_and_legacy_oracles_are_rejected(self) -> None:
        rows = read_inventory()
        for row in rows:
            path = row["source_path"]
            if row["scientific_dependency"] == "yes":
                self.assertEqual(row["migration_type"], "reject", path)
            if path.startswith(("data/", "outputs/", "notebooks/", "configs/")):
                self.assertEqual(row["migration_type"], "reject", path)
        by_path = {row["source_path"]: row for row in rows}
        self.assertEqual(by_path["main.py"]["migration_type"], "rewrite")
        self.assertEqual(by_path["explore_vitaldb_sample.py"]["migration_type"], "rewrite")

    def test_no_source_code_is_approved_for_verbatim_copy(self) -> None:
        rows = read_inventory()
        python_rows = [row for row in rows if row["source_path"].endswith(".py")]
        self.assertTrue(python_rows)
        self.assertNotIn("copy", {row["migration_type"] for row in python_rows})
        counts = Counter(row["migration_type"] for row in rows)
        self.assertEqual(counts["copy"], 0)
        self.assertGreater(counts["reject"], 0)
        self.assertGreater(counts["rewrite"], 0)
        self.assertGreater(counts["refactor"], 0)

    def test_phase2_commit_contains_inventory_only(self) -> None:
        log = subprocess.run(
            ["git", "log", "--format=%H%x09%s"], cwd=ROOT,
            text=True, capture_output=True, check=True,
        ).stdout.splitlines()
        phase_commit = next(
            (line.split("\t", 1)[0] for line in log if line.endswith("\t" + PHASE2_SUBJECT)),
            None,
        )
        if phase_commit:
            changed = set(subprocess.run(
                ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", phase_commit],
                cwd=ROOT, text=True, capture_output=True, check=True,
            ).stdout.splitlines())
        else:
            changed = set(subprocess.run(
                ["git", "diff", "--name-only", "HEAD"], cwd=ROOT,
                text=True, capture_output=True, check=True,
            ).stdout.splitlines())
            changed.update(subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT,
                text=True, capture_output=True, check=True,
            ).stdout.splitlines())
        self.assertTrue(changed)
        self.assertLessEqual(changed, PHASE2_ALLOWED_FILES)
        self.assertFalse(any(path.startswith(("src/", "scripts/", "data/", "outputs/")) for path in changed))


if __name__ == "__main__":
    unittest.main()
