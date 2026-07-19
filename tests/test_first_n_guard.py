from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.guards import (  # noqa: E402
    CohortGuardError,
    assert_manifest_complete,
    assert_production_options,
    fixed_seed_random_sample,
)
from vitaldb_state_selection.provenance.source_guard import scan_source  # noqa: E402


class FirstNGuardTests(unittest.TestCase):
    def test_production_case_limit_is_rejected(self) -> None:
        with self.assertRaises(CohortGuardError):
            assert_production_options(production_mode=True, case_limit=100)
        with self.assertRaises(CohortGuardError):
            assert_production_options(production_mode=True, first_n=True)

    def test_manifest_duplicate_and_missing_ids_are_rejected(self) -> None:
        with self.assertRaisesRegex(CohortGuardError, "duplicate"):
            assert_manifest_complete([1, 1], start=1, end=2)
        with self.assertRaisesRegex(CohortGuardError, "coverage mismatch"):
            assert_manifest_complete([1], start=1, end=2)

    def test_ast_guard_detects_case_prefix_slice_and_banned_identifier(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.py"
            path.write_text("N_CASES = 100\nselected = caseids[:N_CASES]\n", encoding="utf-8")
            violations = scan_source(path)
        self.assertGreaterEqual(len(violations), 2)

    def test_fixed_seed_sample_is_reproducible_and_not_first_25(self) -> None:
        caseids = list(range(1, 6389))
        first = fixed_seed_random_sample(caseids, seed=20260719)
        second = fixed_seed_random_sample(caseids, seed=20260719)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 25)
        self.assertNotEqual(first, caseids[:25])

    def test_production_source_guard_script_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/verify_no_first_n_limit.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("first-N guard passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
