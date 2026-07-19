from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.decision_support import (  # noqa: E402
    RATE_DOCUMENTATION,
    RELEVANT_TRACK_SPECS,
    build_relevant_track_presence,
)


class EligibilityDecisionSupportTests(unittest.TestCase):
    def test_review_scope_is_the_explicit_narrow_track_set(self) -> None:
        names = {spec.track_name for spec in RELEVANT_TRACK_SPECS}
        self.assertEqual(len(names), 21)
        self.assertIn("BIS/SQI", names)
        self.assertIn("Orchestra/RFTN50_RATE", names)
        self.assertIn("Solar8000/GAS2_EXPIRED", names)
        self.assertIn("Primus/MAC", names)
        self.assertNotIn("Solar8000/HR", names)
        self.assertNotIn("BIS/EMG", names)

    def test_presence_accounts_for_every_case_without_classifying_unknown_names(self) -> None:
        rows = [
            {"caseid": 1, "tname": "BIS/SQI", "tid": "a"},
            {"caseid": 1, "tname": "BIS/SQI", "tid": "b"},
            {"caseid": 2, "tname": "Primus/EXP_SEVO", "tid": "c"},
            {"caseid": 3, "tname": "Solar8000/HR", "tid": "d"},
        ]
        presence, inventory = build_relevant_track_presence(
            list(range(1, 6389)), rows
        )
        self.assertEqual(len(presence), 6388)
        self.assertEqual([row["caseid"] for row in presence], list(range(1, 6389)))
        self.assertTrue(presence[0]["bis_sqi_present"])
        self.assertFalse(presence[0]["volatile_candidate_track_present"])
        self.assertTrue(presence[1]["volatile_candidate_track_present"])
        self.assertFalse(presence[2]["volatile_candidate_track_present"])
        by_name = {row["track_name"]: row for row in inventory}
        self.assertEqual(by_name["BIS/SQI"]["row_count"], 2)
        self.assertEqual(by_name["BIS/SQI"]["case_count"], 1)
        self.assertNotIn("Solar8000/HR", by_name)
        self.assertTrue(all(row["auto_approved"] is False for row in inventory))
        self.assertTrue(
            all(row["review_status"] == "pending_human_review" for row in inventory)
        )

    def test_rate_documentation_is_evidence_not_automatic_approval_or_merge(self) -> None:
        by_name = {row["track_name"]: row for row in RATE_DOCUMENTATION}
        self.assertEqual(by_name["Orchestra/PPF20_RATE"]["documented_unit"], "mL/hr")
        self.assertEqual(by_name["Orchestra/RFTN20_RATE"]["documented_unit"], "mL/hr")
        self.assertEqual(by_name["Orchestra/RFTN50_RATE"]["documented_unit"], "mL/hr")
        self.assertIn("20 mcg/mL", by_name["Orchestra/RFTN20_RATE"]["documented_meaning"])
        self.assertIn("50 mcg/mL", by_name["Orchestra/RFTN50_RATE"]["documented_meaning"])
        self.assertTrue(
            all(
                row["review_status"] == "source_documented_pending_human_review"
                for row in RATE_DOCUMENTATION
            )
        )


if __name__ == "__main__":
    unittest.main()
