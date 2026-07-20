from __future__ import annotations

import math
import unittest

from vitaldb_state_selection.pkpd import (
    MintoF12Variant,
    PKPDValidationError,
    PatientProfile,
    Sex,
    james_lean_body_mass_kg,
    minto_remifentanil_parameters,
    schnider_propofol_parameters,
)
from vitaldb_state_selection.pkpd.registry import F12_BY_VARIANT, F_PRIMARY_VALUES, H_VALUES, UNIT_CONTRACT


MALE = PatientProfile(age_years=40, sex=Sex.MALE, height_cm=170, weight_kg=70)
FEMALE = PatientProfile(age_years=40, sex=Sex.FEMALE, height_cm=160, weight_kg=60)
OLDER = PatientProfile(age_years=75, sex=Sex.MALE, height_cm=175, weight_kg=72)


class PKPDParameterTests(unittest.TestCase):
    def test_profile_requires_finite_positive_covariates_and_explicit_enum(self) -> None:
        for field, value in (("age_years", 0), ("height_cm", 0), ("weight_kg", -1)):
            kwargs = dict(age_years=40, sex=Sex.MALE, height_cm=170, weight_kg=70)
            kwargs[field] = value
            with self.assertRaises(PKPDValidationError):
                PatientProfile(**kwargs)
        with self.assertRaises(PKPDValidationError):
            PatientProfile(age_years=40, sex="unknown", height_cm=170, weight_kg=70)  # type: ignore[arg-type]
        with self.assertRaises(PKPDValidationError):
            PatientProfile(age_years=math.nan, sex=Sex.MALE, height_cm=170, weight_kg=70)

    def test_james_lbm_uses_approved_squared_term(self) -> None:
        expected_male = 1.1 * 70 - 128 * (70 / 170) ** 2
        expected_female = 1.07 * 60 - 148 * (60 / 160) ** 2
        self.assertAlmostEqual(james_lean_body_mass_kg(MALE), expected_male, places=14)
        self.assertAlmostEqual(james_lean_body_mass_kg(FEMALE), expected_female, places=14)
        nonsquared_print = 1.1 * 70 - 128 * (70 / 170)
        self.assertNotAlmostEqual(james_lean_body_mass_kg(MALE), nonsquared_print)

    def test_h_and_f_registries_are_complete_and_versioned(self) -> None:
        self.assertEqual(list(H_VALUES), [f"h{i}" for i in range(1, 18)])
        self.assertEqual(list(F_PRIMARY_VALUES), [f"f{i}" for i in range(1, 19)])
        self.assertEqual(F_PRIMARY_VALUES["f18"], 55.0)
        self.assertEqual(F_PRIMARY_VALUES["f12"], 0.0301)
        self.assertEqual(F12_BY_VARIANT[MintoF12Variant.SENSITIVITY_YUN_0_030], 0.030)

    def test_schnider_equations_match_explicit_formula(self) -> None:
        p = schnider_propofol_parameters(MALE)
        h = H_VALUES
        lbm = james_lean_body_mass_kg(MALE)
        self.assertEqual(p.v1_l, 4.27)
        self.assertAlmostEqual(p.v2_l, h["h2"] - h["h3"] * (40 - h["h4"]))
        self.assertEqual(p.v3_l, 238.0)
        self.assertAlmostEqual(
            p.cl1_l_per_min,
            h["h6"] + h["h7"] * (70 - h["h8"]) - h["h9"] * (lbm - h["h10"])
            + h["h11"] * (170 - h["h12"]),
        )
        self.assertAlmostEqual(p.cl2_l_per_min, h["h13"] - h["h14"] * (40 - h["h15"]))
        self.assertEqual(p.cl3_l_per_min, h["h16"])
        self.assertEqual(p.ke0_per_min, h["h17"])

    def test_minto_uses_f18_and_closed_f12_variants(self) -> None:
        primary = minto_remifentanil_parameters(MALE)
        sensitivity = minto_remifentanil_parameters(
            MALE, f12_variant=MintoF12Variant.SENSITIVITY_YUN_0_030
        )
        f = F_PRIMARY_VALUES
        lbm_delta = james_lean_body_mass_kg(MALE) - 55.0
        self.assertAlmostEqual(primary.cl1_l_per_min, f["f8"] + f["f10"] * lbm_delta)
        self.assertAlmostEqual(primary.cl2_l_per_min, f["f11"])
        self.assertAlmostEqual(primary.cl3_l_per_min, f["f13"])
        self.assertAlmostEqual(primary.ke0_per_min, f["f15"])
        self.assertEqual(primary.variant_id, MintoF12Variant.PRIMARY_MINTO_0_0301.value)
        self.assertEqual(sensitivity.variant_id, MintoF12Variant.SENSITIVITY_YUN_0_030.value)
        with self.assertRaises(PKPDValidationError):
            minto_remifentanil_parameters(MALE, f12_variant="0.031")  # type: ignore[arg-type]

    def test_parameters_are_finite_physiologically_signed_and_deterministic(self) -> None:
        for profile in (MALE, FEMALE, OLDER):
            for function in (schnider_propofol_parameters, minto_remifentanil_parameters):
                first = function(profile)
                second = function(profile)
                self.assertEqual(first, second)
                self.assertTrue(all(math.isfinite(value) for value in (
                    first.v1_l, first.v2_l, first.v3_l, first.cl1_l_per_min,
                    first.cl2_l_per_min, first.cl3_l_per_min, first.ke0_per_min,
                )))
                self.assertGreater(min(first.v1_l, first.v2_l, first.v3_l), 0)
                self.assertGreaterEqual(min(first.cl1_l_per_min, first.cl2_l_per_min, first.cl3_l_per_min), 0)
                self.assertGreater(first.ke0_per_min, 0)

    def test_drug_unit_contracts_are_distinct(self) -> None:
        propofol = schnider_propofol_parameters(MALE)
        remifentanil = minto_remifentanil_parameters(MALE)
        self.assertEqual((propofol.amount_unit, propofol.infusion_rate_unit, propofol.concentration_unit),
                         ("mg", "mg/min", "mg/L"))
        self.assertEqual((remifentanil.amount_unit, remifentanil.infusion_rate_unit, remifentanil.concentration_unit),
                         ("microgram", "microgram/min", "microgram/L"))
        self.assertEqual(UNIT_CONTRACT["transition_input_time"], "second")


if __name__ == "__main__":
    unittest.main()
