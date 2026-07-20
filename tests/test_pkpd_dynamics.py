from __future__ import annotations

import unittest

import numpy as np
from scipy.integrate import solve_ivp

from vitaldb_state_selection.pkpd import (
    PKPDValidationError,
    PatientProfile,
    Sex,
    minto_remifentanil_parameters,
    schnider_propofol_parameters,
)
from vitaldb_state_selection.pkpd.dynamics import (
    _CompartmentState,
    _exact_zoh_transition,
    _transition_matrix_per_minute,
)


PROFILE = PatientProfile(age_years=40, sex=Sex.MALE, height_cm=170, weight_kg=70)


def assert_state_close(test: unittest.TestCase, left: _CompartmentState, right: _CompartmentState, tol: float) -> None:
    np.testing.assert_allclose(left.as_tuple(), right.as_tuple(), rtol=tol, atol=tol)


class PKPDDynamicsTests(unittest.TestCase):
    def test_zero_state_and_input_remain_zero(self) -> None:
        for parameters in (schnider_propofol_parameters(PROFILE), minto_remifentanil_parameters(PROFILE)):
            result = _exact_zoh_transition(
                _CompartmentState(), parameters, duration_seconds=600, infusion_rate_per_minute=0
            )
            self.assertEqual(result, _CompartmentState())

    def test_exact_semigroup_for_two_fives_and_ten_ones(self) -> None:
        for parameters, rate in (
            (schnider_propofol_parameters(PROFILE), 8.0),
            (minto_remifentanil_parameters(PROFILE), 6.0),
        ):
            initial = _CompartmentState()
            ten = _exact_zoh_transition(initial, parameters, duration_seconds=10, infusion_rate_per_minute=rate)
            five = _exact_zoh_transition(initial, parameters, duration_seconds=5, infusion_rate_per_minute=rate)
            two_fives = _exact_zoh_transition(five, parameters, duration_seconds=5, infusion_rate_per_minute=rate)
            one = initial
            for _ in range(10):
                one = _exact_zoh_transition(one, parameters, duration_seconds=1, infusion_rate_per_minute=rate)
            assert_state_close(self, ten, two_fives, 2e-13)
            assert_state_close(self, ten, one, 2e-13)

    def test_exact_transition_matches_high_accuracy_solve_ivp(self) -> None:
        profiles = (
            PROFILE,
            PatientProfile(age_years=40, sex=Sex.FEMALE, height_cm=160, weight_kg=60),
            PatientProfile(age_years=75, sex=Sex.MALE, height_cm=175, weight_kg=72),
        )
        for profile in profiles:
            for parameters, rate in (
                (schnider_propofol_parameters(profile), 8.0),
                (minto_remifentanil_parameters(profile), 6.0),
            ):
                matrix = _transition_matrix_per_minute(parameters)
                forcing = np.array([rate, 0.0, 0.0, 0.0])
                solution = solve_ivp(
                    lambda _t, y: matrix @ y + forcing,
                    (0.0, 10.0 / 60.0),
                    np.zeros(4),
                    method="DOP853",
                    rtol=1e-12,
                    atol=1e-14,
                )
                self.assertTrue(solution.success)
                exact = _exact_zoh_transition(
                    _CompartmentState(), parameters, duration_seconds=10, infusion_rate_per_minute=rate
                )
                np.testing.assert_allclose(exact.as_tuple(), solution.y[:, -1], rtol=2e-11, atol=2e-12)

    def test_validation_rejects_bad_duration_rate_and_state(self) -> None:
        parameters = schnider_propofol_parameters(PROFILE)
        for duration in (0, -1, float("nan")):
            with self.assertRaises(PKPDValidationError):
                _exact_zoh_transition(
                    _CompartmentState(), parameters, duration_seconds=duration, infusion_rate_per_minute=0
                )
        for rate in (-1, float("inf")):
            with self.assertRaises(PKPDValidationError):
                _exact_zoh_transition(
                    _CompartmentState(), parameters, duration_seconds=10, infusion_rate_per_minute=rate
                )
        with self.assertRaises(PKPDValidationError):
            _CompartmentState(a1_amount=-1e-5)

    def test_units_and_deliberate_thousand_fold_remifentanil_error(self) -> None:
        parameters = minto_remifentanil_parameters(PROFILE)
        correct = _exact_zoh_transition(
            _CompartmentState(), parameters, duration_seconds=10, infusion_rate_per_minute=6.0
        )
        mistaken_mg_numeric = _exact_zoh_transition(
            _CompartmentState(), parameters, duration_seconds=10, infusion_rate_per_minute=0.006
        )
        ratios = np.array(correct.as_tuple()) / np.array(mistaken_mg_numeric.as_tuple())
        np.testing.assert_allclose(ratios, np.full(4, 1000.0), rtol=2e-12, atol=2e-9)
        self.assertEqual(parameters.amount_unit, "microgram")
        self.assertEqual(parameters.infusion_rate_unit, "microgram/min")


if __name__ == "__main__":
    unittest.main()
