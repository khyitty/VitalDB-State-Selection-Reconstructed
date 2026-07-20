from __future__ import annotations

from dataclasses import asdict, fields
import inspect
import math
import unittest

import numpy as np

from vitaldb_state_selection.pkpd import (
    DualDrugSimulator,
    MintoF12Variant,
    PatientProfile,
    Sex,
    SimulationTransition,
    deterministic_bis,
    diagnostic_trajectory,
)
from vitaldb_state_selection.pkpd.registry import BIS_PARAMETERS


PROFILE = PatientProfile(age_years=40, sex=Sex.MALE, height_cm=170, weight_kg=70)


class PKPDCoreTests(unittest.TestCase):
    def test_public_transition_fields_and_advance_arguments_encode_units(self) -> None:
        field_names = {field.name for field in fields(SimulationTransition)}
        self.assertTrue(
            {
                "duration_seconds",
                "elapsed_seconds",
                "propofol_a1_mg",
                "propofol_a2_mg",
                "propofol_a3_mg",
                "propofol_cp_mg_per_l",
                "propofol_ce_mg_per_l",
                "remifentanil_a1_microgram",
                "remifentanil_a2_microgram",
                "remifentanil_a3_microgram",
                "remifentanil_cp_microgram_per_l",
                "remifentanil_ce_microgram_per_l",
                "deterministic_bis_index",
            }
            <= field_names
        )
        self.assertNotIn("propofol", field_names)
        self.assertNotIn("remifentanil", field_names)
        self.assertEqual(
            list(inspect.signature(DualDrugSimulator.advance).parameters),
            [
                "self",
                "duration_seconds",
                "propofol_rate_mg_per_min",
                "remifentanil_rate_microgram_per_min",
            ],
        )

    def test_zero_reset_zero_input_and_baseline_bis(self) -> None:
        simulator = DualDrugSimulator.from_profile(PROFILE)
        step = simulator.advance(10, 0, 0)
        self.assertEqual(step.elapsed_seconds, 10)
        self.assertEqual(
            (step.propofol_a1_mg, step.propofol_a2_mg, step.propofol_a3_mg, step.propofol_ce_mg_per_l),
            (0, 0, 0, 0),
        )
        self.assertEqual(
            (step.remifentanil_a1_microgram, step.remifentanil_a2_microgram,
             step.remifentanil_a3_microgram, step.remifentanil_ce_microgram_per_l),
            (0, 0, 0, 0),
        )
        self.assertEqual(step.deterministic_bis_index, 98.0)
        self.assertEqual(simulator._state.elapsed_seconds, 0.0)

    def test_advance_is_immutable_and_deterministic(self) -> None:
        simulator = DualDrugSimulator.from_profile(PROFILE)
        profile_before = asdict(PROFILE)
        first = simulator.advance(10, 8, 6)
        second = simulator.advance(10, 8, 6)
        self.assertEqual(first, second)
        self.assertEqual(asdict(PROFILE), profile_before)
        self.assertEqual(simulator._state.elapsed_seconds, 0.0)
        self.assertEqual(first.profile_id, PROFILE.identifier)

    def test_no_future_input_access_and_drugs_are_independent_before_bis(self) -> None:
        simulator = DualDrugSimulator.from_profile(PROFILE)
        common = simulator.advance(10, 8, 6)
        future_a = common.next_simulator.advance(10, 0, 0)
        future_b = common.next_simulator.advance(10, 20, 30)
        self.assertEqual(common, simulator.advance(10, 8, 6))
        self.assertNotEqual(future_a.propofol_a1_mg, future_b.propofol_a1_mg)
        self.assertNotEqual(future_a.remifentanil_a1_microgram, future_b.remifentanil_a1_microgram)
        prop_only_a = simulator.advance(10, 8, 0)
        prop_only_b = simulator.advance(10, 8, 100)
        self.assertEqual(
            (prop_only_a.propofol_a1_mg, prop_only_a.propofol_a2_mg, prop_only_a.propofol_a3_mg, prop_only_a.propofol_ce_mg_per_l),
            (prop_only_b.propofol_a1_mg, prop_only_b.propofol_a2_mg, prop_only_b.propofol_a3_mg, prop_only_b.propofol_ce_mg_per_l),
        )
        remi_only_a = simulator.advance(10, 0, 6)
        remi_only_b = simulator.advance(10, 100, 6)
        self.assertEqual(
            (remi_only_a.remifentanil_a1_microgram, remi_only_a.remifentanil_a2_microgram,
             remi_only_a.remifentanil_a3_microgram, remi_only_a.remifentanil_ce_microgram_per_l),
            (remi_only_b.remifentanil_a1_microgram, remi_only_b.remifentanil_a2_microgram,
             remi_only_b.remifentanil_a3_microgram, remi_only_b.remifentanil_ce_microgram_per_l),
        )

    def test_ten_second_advance_matches_one_second_diagnostics(self) -> None:
        simulator = DualDrugSimulator.from_profile(PROFILE)
        direct = simulator.advance(10, 8, 6)
        trajectory = diagnostic_trajectory(
            simulator,
            duration_seconds=10,
            propofol_rate_mg_per_min=8,
            remifentanil_rate_microgram_per_min=6,
        )
        self.assertEqual([row.elapsed_seconds for row in trajectory], list(range(1, 11)))
        np.testing.assert_allclose(
            (direct.propofol_a1_mg, direct.propofol_a2_mg, direct.propofol_a3_mg, direct.propofol_ce_mg_per_l),
            (trajectory[-1].propofol_a1_mg, trajectory[-1].propofol_a2_mg,
             trajectory[-1].propofol_a3_mg, trajectory[-1].propofol_ce_mg_per_l),
            rtol=2e-13, atol=2e-13,
        )
        np.testing.assert_allclose(
            (direct.remifentanil_a1_microgram, direct.remifentanil_a2_microgram,
             direct.remifentanil_a3_microgram, direct.remifentanil_ce_microgram_per_l),
            (trajectory[-1].remifentanil_a1_microgram, trajectory[-1].remifentanil_a2_microgram,
             trajectory[-1].remifentanil_a3_microgram, trajectory[-1].remifentanil_ce_microgram_per_l),
            rtol=2e-13, atol=2e-13,
        )

    def test_bis_is_finite_deterministic_monotone_and_unclipped(self) -> None:
        propofol_grid = (0.0, 0.5, 1.0, 2.0, 4.47, 10.0, 50.0)
        remifentanil_grid = (0.0, 1.0, 5.0, 10.0, 19.3, 40.0, 100.0)
        for remi in remifentanil_grid:
            values = [deterministic_bis(prop, remi) for prop in propofol_grid]
            self.assertTrue(all(math.isfinite(value) for value in values))
            self.assertTrue(all(left >= right for left, right in zip(values, values[1:])))
        for prop in propofol_grid:
            values = [deterministic_bis(prop, remi) for remi in remifentanil_grid]
            self.assertTrue(all(left >= right for left, right in zip(values, values[1:])))
        self.assertFalse(BIS_PARAMETERS["gaussian_noise_enabled"])
        self.assertFalse(BIS_PARAMETERS["effect_site_random_drop_enabled"])
        self.assertFalse(BIS_PARAMETERS["output_clipping_enabled"])
        self.assertLess(deterministic_bis(1000, 1000), 1.0)

    def test_f12_sensitivity_is_explicit_and_not_default(self) -> None:
        primary = DualDrugSimulator.from_profile(PROFILE)
        sensitivity = DualDrugSimulator.from_profile(
            PROFILE, minto_f12_variant=MintoF12Variant.SENSITIVITY_YUN_0_030
        )
        self.assertEqual(primary.remifentanil_parameters.variant_id, "primary_minto_0.0301")
        self.assertEqual(sensitivity.remifentanil_parameters.variant_id, "sensitivity_yun_0.030")
        self.assertNotEqual(
            primary.remifentanil_parameters.cl2_l_per_min,
            DualDrugSimulator.from_profile(
                PatientProfile(age_years=75, sex=Sex.MALE, height_cm=175, weight_kg=72)
            ).remifentanil_parameters.cl2_l_per_min,
        )


if __name__ == "__main__":
    unittest.main()
