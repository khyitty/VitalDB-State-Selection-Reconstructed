from __future__ import annotations

import unittest

from vitaldb_state_selection.cohort.protocol_v1_3_2 import (
    IMPLEMENTATION_AUTHORITY,
    IMPLEMENTATION_STAGES,
    PHASE7E_ALLOWED_OUTPUTS,
    PRESERVED_DESIGN,
    PROHIBITED_EXECUTION,
    PROTOCOL_VERSION,
    SOURCE_PRIORITY,
    validate_amendment,
)


class ProtocolV132Tests(unittest.TestCase):
    def test_version_and_primary_path(self) -> None:
        self.assertEqual(PROTOCOL_VERSION, "1.3.2")
        self.assertEqual(
            IMPLEMENTATION_AUTHORITY["primary_path"],
            "paper_grounded_independent_reconstruction",
        )
        self.assertFalse(IMPLEMENTATION_AUTHORITY["lab_code_expected"])
        self.assertFalse(IMPLEMENTATION_AUTHORITY["laboratory_authoritative_implementation"])
        self.assertEqual(IMPLEMENTATION_AUTHORITY["path_a_lab_code_reuse"], "retired_unavailable")

    def test_source_priority_and_legacy_boundary(self) -> None:
        self.assertEqual(SOURCE_PRIORITY[0], "yun_2023_primary_paper")
        self.assertIn("directly_cited_schnider_minto_bouillon_ppo_gae_primary_sources", SOURCE_PRIORITY)
        self.assertEqual(IMPLEMENTATION_AUTHORITY["legacy_role"], "read_only_equation_cross_check_only")
        self.assertEqual(IMPLEMENTATION_AUTHORITY["undisclosed_value_policy"], "human_decision_required")

    def test_design_and_cohort_are_preserved(self) -> None:
        self.assertEqual(PRESERVED_DESIGN["factorial_design"], "P0_P1_by_S0_S1")
        self.assertEqual((PRESERVED_DESIGN["frozen_case_count"], PRESERVED_DESIGN["frozen_subject_count"]), (2460, 2415))
        self.assertFalse(PRESERVED_DESIGN["cohort_refrozen_in_phase7e"])
        self.assertFalse(PRESERVED_DESIGN["prediction_in_confirmatory_scope"])

    def test_six_stages_are_ordered(self) -> None:
        self.assertEqual(len(IMPLEMENTATION_STAGES), 6)
        self.assertTrue(IMPLEMENTATION_STAGES[0].startswith("Stage_I_"))
        self.assertTrue(IMPLEMENTATION_STAGES[-1].startswith("Stage_VI_"))
        self.assertIn("Stage_V_subject_level_split_and_observation_template", IMPLEMENTATION_STAGES)

    def test_phase7e_outputs_are_specification_only(self) -> None:
        self.assertEqual(
            set(PHASE7E_ALLOWED_OUTPUTS),
            {
                "protocol_amendment",
                "source_evidence_table",
                "missing_constant_register",
                "implementation_sequence",
                "scientific_validation_plan",
                "tests",
                "phase_status",
            },
        )
        self.assertTrue(all(value is False for value in PROHIBITED_EXECUTION.values()))

    def test_validate_amendment(self) -> None:
        validate_amendment()


if __name__ == "__main__":
    unittest.main()
