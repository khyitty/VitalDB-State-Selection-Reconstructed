from __future__ import annotations

import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.protocol_v1_3 import (
    CONDITIONS,
    EXPECTED_CASES,
    EXPECTED_SUBJECTS,
    EXPECTED_TEST_SUBJECTS,
    EXPECTED_TRAIN_SUBJECTS,
    FINAL_SEEDS,
    P0,
    P0_ID,
    P1,
    P1_ID,
    PROHIBITED_EXECUTION,
    S0_DYNAMIC_FEATURES,
    S1_ADDITIONAL_FEATURES,
    SMOKE_SEED,
    STATIC_FEATURES,
    validate_design,
)


class ProtocolV13Tests(unittest.TestCase):
    def test_design_contract_validates(self) -> None:
        validate_design()

    def test_p0_and_p1_exact_candidate_contracts(self) -> None:
        self.assertEqual(P0["candidate_id"], P0_ID)
        self.assertEqual(P1["candidate_id"], P1_ID)
        self.assertEqual(P0_ID, "sqi_not_required__bis30s__drug120s")
        self.assertEqual(P1_ID, "sqi_ge_50__bis20s__drug60s")
        self.assertEqual(P0["bis_staleness_cap_seconds"], 30)
        self.assertEqual(P1["bis_staleness_cap_seconds"], 20)
        self.assertEqual(P0["propofol_rate_hold_cap_seconds"], 120)
        self.assertEqual(P1["propofol_rate_hold_cap_seconds"], 60)
        self.assertEqual(P0["remifentanil_rate_hold_cap_seconds"], 120)
        self.assertEqual(P1["remifentanil_rate_hold_cap_seconds"], 60)

    def test_sqi_roles_are_exact_and_never_ppo_state(self) -> None:
        self.assertEqual(P0["sqi_rule"], "not_required")
        self.assertIsNone(P0["sqi_exact_timestamp_threshold"])
        self.assertEqual(P1["sqi_rule"], "exact_timestamp_gte_50")
        self.assertEqual(P1["sqi_exact_timestamp_threshold"], 50)
        self.assertFalse(P1["sqi_nearest_matching_allowed"])
        self.assertFalse(P1["sqi_interpolation_allowed"])
        self.assertFalse(P0["sqi_in_ppo_state"])
        self.assertFalse(P1["sqi_in_ppo_state"])

    def test_common_causal_rules_preserve_zero_and_prohibit_future_use(self) -> None:
        for pipeline in (P0, P1):
            self.assertEqual(pipeline["history_relative_seconds"], [-50, -40, -30, -20, -10, 0])
            self.assertEqual(pipeline["bis_range_inclusive"], [0, 100])
            self.assertTrue(pipeline["bis_0_10_admissible"])
            self.assertFalse(pipeline["zero_bis_is_missing"])
            self.assertFalse(pipeline["zero_drug_rate_is_missing"])
            self.assertFalse(pipeline["future_observation_allowed"])
            self.assertFalse(pipeline["interpolation_allowed"])
            self.assertFalse(pipeline["backward_fill_allowed"])
            self.assertFalse(pipeline["pre_observation_zero_assumption_allowed"])

    def test_s0_is_conceptual_strict_subset_of_s1_without_bmi_or_sqi(self) -> None:
        s0 = set(STATIC_FEATURES + S0_DYNAMIC_FEATURES)
        s1 = s0 | set(S1_ADDITIONAL_FEATURES)
        self.assertLess(s0, s1)
        self.assertNotIn("bmi", s1)
        self.assertTrue(all("sqi" not in feature.lower() for feature in s1))

    def test_four_policy_conditions_are_unique_without_ablation(self) -> None:
        self.assertEqual({row["condition_id"] for row in CONDITIONS}, {"P0S0", "P1S0", "P0S1", "P1S1"})
        self.assertEqual({row["policy_id"] for row in CONDITIONS}, {"PPO_P0S0", "PPO_P1S0", "PPO_P0S1", "PPO_P1S1"})
        self.assertFalse(PROHIBITED_EXECUTION["preprocessing_component_ablation"])

    def test_planned_counts_and_seeds_are_predeclared_only(self) -> None:
        self.assertEqual((EXPECTED_CASES, EXPECTED_SUBJECTS), (2460, 2415))
        self.assertEqual((EXPECTED_TRAIN_SUBJECTS, EXPECTED_TEST_SUBJECTS), (1932, 483))
        self.assertEqual(EXPECTED_TRAIN_SUBJECTS + EXPECTED_TEST_SUBJECTS, EXPECTED_SUBJECTS)
        self.assertEqual(SMOKE_SEED, 42)
        self.assertEqual(FINAL_SEEDS, (7, 42, 84))

    def test_phase7b_execution_flags_are_all_inactive(self) -> None:
        for name, value in PROHIBITED_EXECUTION.items():
            if isinstance(value, bool):
                self.assertFalse(value, name)
            else:
                self.assertEqual(value, 0, name)


if __name__ == "__main__":
    unittest.main()
