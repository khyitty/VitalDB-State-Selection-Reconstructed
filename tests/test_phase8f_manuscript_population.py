from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tests.test_phase8f_renderer import synthetic_aggregate  # noqa: E402
from vitaldb_state_selection.publication.manuscript_population import (  # noqa: E402
    ManuscriptPopulationError,
    TOKEN_PATTERN,
    populate_manuscript,
    token_values,
)


class Phase8FManuscriptPopulationTests(unittest.TestCase):
    def test_all_37_occurrences_have_deterministic_sources(self) -> None:
        aggregate = synthetic_aggregate()
        template = "\n".join([*token_values(aggregate), "[CONCLUSION_PENDING]"])
        populated, report = populate_manuscript(template, aggregate)
        self.assertEqual(report["placeholder_occurrences_replaced"], 37)
        self.assertEqual(report["placeholder_occurrences_remaining"], 0)
        self.assertEqual(TOKEN_PATTERN.findall(populated), [])
        self.assertIn("without selecting a best condition", populated)
        self.assertNotIn("significantly improved", populated.lower())
        self.assertNotIn("superior condition", populated.lower())

    def test_unknown_or_missing_token_is_rejected(self) -> None:
        aggregate = synthetic_aggregate()
        template = "\n".join([*token_values(aggregate), "[CONCLUSION_PENDING]"])
        with self.assertRaises(ManuscriptPopulationError):
            populate_manuscript(template.replace("{{FINAL_COMPLETED_CASES_PER_CONDITION}}", "{{UNKNOWN_RESULT}}"), aggregate)

    def test_published_manuscript_values_match_the_frozen_aggregate(self) -> None:
        aggregate_path = ROOT / "paper/generated/phase8e_aggregate_results.json"
        aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
        manuscript = (ROOT / "paper/manuscript.md").read_text(encoding="utf-8")
        report = json.loads((ROOT / "paper/generated/manuscript_token_map.json").read_text(encoding="utf-8"))
        self.assertEqual(
            report["source_aggregate_sha256"],
            hashlib.sha256(aggregate_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(report["placeholder_occurrences_replaced"], 37)
        self.assertEqual(report["placeholder_occurrences_remaining"], 0)
        self.assertFalse(report["results_interpreted"])
        self.assertFalse(report["best_condition_selected"])
        self.assertEqual(TOKEN_PATTERN.findall(manuscript), [])
        for value in token_values(aggregate).values():
            self.assertIn(value, manuscript)


if __name__ == "__main__":
    unittest.main()
