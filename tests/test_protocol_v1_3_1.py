from __future__ import annotations

import unittest

from vitaldb_state_selection.cohort.protocol_v1_3_1 import (
    EXPECTED_CASES,
    EXPECTED_SUBJECTS,
    MISSING_ENCODING,
    OBSERVATION_TEMPLATE_CONTRACT,
    P0_ONLINE,
    P1_ONLINE,
    PROHIBITED_EXECUTION,
    S0_SCHEMA,
    S1_SCHEMA,
    validate_amendment,
)


class ProtocolV131Tests(unittest.TestCase):
    def test_declarative_amendment_validates(self) -> None:
        validate_amendment()
        self.assertEqual((EXPECTED_CASES, EXPECTED_SUBJECTS), (2460, 2415))

    def test_online_bis_bundle_is_exact(self) -> None:
        self.assertEqual(P0_ONLINE["pipeline_id"], "P0_online_bis_permissive_v1")
        self.assertEqual(P1_ONLINE["pipeline_id"], "P1_online_bis_quality_v1")
        self.assertEqual(P0_ONLINE["sqi_rule"], "not_required")
        self.assertEqual(P1_ONLINE["sqi_rule"], "exact_timestamp_gte_50")
        self.assertEqual(P1_ONLINE["sqi_exact_timestamp_threshold"], 50)
        self.assertEqual(
            (P0_ONLINE["bis_staleness_cap_seconds"], P1_ONLINE["bis_staleness_cap_seconds"]),
            (30, 20),
        )

    def test_drug_histories_are_identical_internal_values(self) -> None:
        invariant_keys = (
            "propofol_history_source",
            "remifentanil_history_source",
            "drug_histories_identical_across_pipelines",
            "drug_staleness_contrast",
            "drug_artificial_missingness",
            "drug_availability_mask_in_state",
            "drug_observation_age_in_state",
        )
        for key in invariant_keys:
            self.assertEqual(P0_ONLINE[key], P1_ONLINE[key], key)
        self.assertFalse(P0_ONLINE["drug_staleness_contrast"])
        self.assertFalse(P0_ONLINE["drug_artificial_missingness"])
        self.assertFalse(P0_ONLINE["drug_availability_mask_in_state"])
        self.assertFalse(P0_ONLINE["drug_observation_age_in_state"])

    def test_option_b_minimal_distinguishes_zero_from_missing(self) -> None:
        self.assertEqual(MISSING_ENCODING["selection"], "Option_B_minimal")
        self.assertEqual(MISSING_ENCODING["applies_to"], "BIS_history_only")
        self.assertEqual(MISSING_ENCODING["unavailable_value_placeholder"], 0)
        self.assertEqual(MISSING_ENCODING["unavailable_mask"], 0)
        self.assertEqual(MISSING_ENCODING["available_bis_zero_value"], 0)
        self.assertEqual(MISSING_ENCODING["available_bis_zero_mask"], 1)
        self.assertFalse(MISSING_ENCODING["no_prior_state_channel"])
        self.assertIsNone(MISSING_ENCODING["age_clip_maximum_seconds"])
        self.assertEqual(
            MISSING_ENCODING["age_clip_maximum_status"],
            "pending_human_numeric_value_before_implementation",
        )

    def test_s0_s1_conceptual_dimensions_are_frozen_without_sqi(self) -> None:
        self.assertEqual(S0_SCHEMA["conceptual_dimension"], 34)
        self.assertEqual(S1_SCHEMA["conceptual_dimension"], 42)
        self.assertEqual(S1_SCHEMA["strict_superset_of"], "S0")
        self.assertEqual(len(S1_SCHEMA["additional_features"]), 8)
        self.assertFalse(S0_SCHEMA["sqi_numeric_value_included"])
        self.assertFalse(S1_SCHEMA["sqi_numeric_value_included"])
        self.assertFalse(S0_SCHEMA["implemented_in_phase7d"])
        self.assertFalse(S1_SCHEMA["implemented_in_phase7d"])

    def test_future_template_is_timing_only_and_not_extracted(self) -> None:
        self.assertIn(
            "raw_observed_bis_values", OBSERVATION_TEMPLATE_CONTRACT["excluded_fields"]
        )
        self.assertIn(
            "bis_observation_timestamps", OBSERVATION_TEMPLATE_CONTRACT["included_fields"]
        )
        self.assertTrue(OBSERVATION_TEMPLATE_CONTRACT["same_template_for_p0_and_p1"])
        self.assertEqual(OBSERVATION_TEMPLATE_CONTRACT["reward_bis_source"], "latent_true_bis")
        self.assertFalse(OBSERVATION_TEMPLATE_CONTRACT["template_extracted_in_phase7d"])

    def test_phase7d_execution_flags_are_all_inactive(self) -> None:
        self.assertTrue(PROHIBITED_EXECUTION)
        self.assertTrue(all(value is False for value in PROHIBITED_EXECUTION.values()))


if __name__ == "__main__":
    unittest.main()
