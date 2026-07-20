import math
import unittest
from pathlib import Path

import numpy as np

from vitaldb_state_selection.anesthesia import (
    AnesthesiaEnvironmentCore, BISEvent, BISObservationProcessor, BISReason,
    ConstantRemifentanilSchedule, EnvironmentConfig, FOUR_CONDITION_CONFIGS,
    PiecewiseConstantRemifentanilSchedule, PreprocessingID, SQIEvent, StateID,
    SyntheticObservationTemplate, apply_propofol_action, latent_bis_reward,
)
from vitaldb_state_selection.pkpd import DualDrugSimulator, PatientProfile, Sex


PROFILE = PatientProfile(age_years=45, sex=Sex.FEMALE, height_cm=165, weight_kg=60)


def template(*, bis=(10.0, 20.0, 30.0), sqi=((10.0, 80.0), (20.0, 80.0), (30.0, 80.0)), horizon=100.0):
    return SyntheticObservationTemplate(
        "synthetic-test", horizon,
        tuple(BISEvent(float(t)) for t in bis),
        tuple(SQIEvent(float(t), float(v)) for t, v in sqi),
    )


def environment(preprocessing=PreprocessingID.P0, state=StateID.S0, *, tmpl=None, schedule=None, horizon=100.0):
    return AnesthesiaEnvironmentCore(
        profile=PROFILE,
        config=EnvironmentConfig(preprocessing, state, episode_horizon_seconds=horizon),
        observation_template=tmpl or template(horizon=horizon),
        remifentanil_schedule=schedule,
    )


class ActionRewardTests(unittest.TestCase):
    def test_action_bounds_and_conversion(self):
        for raw, expected, clipped in ((0, 0, False), (27.7, 27.7, False), (-1, 0, True), (30, 27.7, True)):
            result = apply_propofol_action(raw)
            self.assertEqual(result.applied_action_mg_per_10s, expected)
            self.assertEqual(result.action_was_clipped, clipped)
            self.assertEqual(result.propofol_rate_mg_per_min, expected * 6)

    def test_nonfinite_action_raises(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.assertRaises(ValueError):
                apply_propofol_action(value)

    def test_reward_formula_positive_and_monotone(self):
        self.assertEqual(latent_bis_reward(target_bis=50, latent_next_bis=50), 1.0)
        self.assertAlmostEqual(latent_bis_reward(target_bis=50, latent_next_bis=60), 1 / 11)
        self.assertGreater(latent_bis_reward(target_bis=50, latent_next_bis=51), latent_bis_reward(target_bis=50, latent_next_bis=60))


class ObservationProcessorTests(unittest.TestCase):
    def test_p0_ignores_sqi_but_p1_requires_exact_sqi(self):
        tmpl = template(bis=(10,), sqi=((9.999, 100),))
        p0 = BISObservationProcessor(PreprocessingID.P0, tmpl)
        p1 = BISObservationProcessor(PreprocessingID.P1, tmpl)
        event = tmpl.bis_events[0]
        self.assertEqual(p0.ingest(event, 50), BISReason.AVAILABLE)
        self.assertEqual(p1.ingest(event, 50), BISReason.SQI_MISSING)
        self.assertEqual(p0.query(10).mask, 1)
        self.assertEqual(p1.query(10).mask, 0)

    def test_p1_threshold_is_inclusive(self):
        for sqi, expected in ((49.999, BISReason.SQI_LOW), (50.0, BISReason.AVAILABLE)):
            tmpl = template(bis=(10,), sqi=((10, sqi),))
            processor = BISObservationProcessor(PreprocessingID.P1, tmpl)
            self.assertEqual(processor.ingest(tmpl.bis_events[0], 40), expected)

    def test_staleness_caps_and_age_clip(self):
        tmpl = template(bis=(0,), sqi=((0, 100),))
        p0 = BISObservationProcessor(PreprocessingID.P0, tmpl)
        p1 = BISObservationProcessor(PreprocessingID.P1, tmpl)
        for processor in (p0, p1):
            processor.ingest(tmpl.bis_events[0], 50)
        self.assertEqual(p0.query(30).mask, 1)
        self.assertEqual(p0.query(30.001).reason, BISReason.STALE)
        self.assertEqual(p1.query(20).mask, 1)
        self.assertEqual(p1.query(20.001).mask, 0)
        self.assertEqual(p1.query(100).age_seconds, 30)

    def test_genuine_zero_and_explicit_missing_are_distinct(self):
        tmpl = SyntheticObservationTemplate("x", 100, (BISEvent(0), BISEvent(10, False)), ())
        processor = BISObservationProcessor(PreprocessingID.P0, tmpl)
        processor.ingest(tmpl.bis_events[0], 0)
        self.assertEqual(processor.query(0).value, 0)
        self.assertEqual(processor.query(0).mask, 1)
        processor.ingest(tmpl.bis_events[1], 40)
        self.assertEqual(processor.query(10).reason, BISReason.AVAILABLE)
        self.assertEqual(processor.query(10).value, 0)

    def test_no_future_event_access(self):
        tmpl = template(bis=(10,), sqi=((10, 100),))
        processor = BISObservationProcessor(PreprocessingID.P0, tmpl)
        self.assertEqual(processor.query(9.999).reason, BISReason.NO_PRIOR)

    def test_unordered_template_sorted(self):
        tmpl = SyntheticObservationTemplate("x", 30, (BISEvent(20), BISEvent(10)), (SQIEvent(20, 80), SQIEvent(10, 80)))
        self.assertEqual([e.timestamp_seconds for e in tmpl.bis_events], [10, 20])

    def test_rejection_reason_codes(self):
        cases = (
            (PreprocessingID.P0, template(bis=(10,), sqi=()), float("nan"), BISReason.NONFINITE),
            (PreprocessingID.P0, template(bis=(10,), sqi=()), 101.0, BISReason.OUT_OF_RANGE),
            (PreprocessingID.P1, template(bis=(10,), sqi=()), 50.0, BISReason.SQI_MISSING),
            (PreprocessingID.P1, template(bis=(10,), sqi=((10, 49),)), 50.0, BISReason.SQI_LOW),
        )
        for pipeline, tmpl, value, expected in cases:
            processor = BISObservationProcessor(pipeline, tmpl)
            self.assertEqual(processor.ingest(tmpl.bis_events[0], value), expected)
            self.assertEqual(processor.query(10).reason, expected)
            self.assertEqual(processor.audit_events[-1].reason, expected)


class EnvironmentTests(unittest.TestCase):
    def test_reset_shapes_determinism_and_zero_prehistory(self):
        for state, size in ((StateID.S0, 34), (StateID.S1, 42)):
            env = environment(state=state)
            first, info1 = env.reset(seed=7)
            second, info2 = env.reset(seed=7)
            np.testing.assert_array_equal(first, second)
            self.assertEqual(first.shape, (size,))
            self.assertTrue(np.isfinite(first).all())
            self.assertEqual(info1["target_bis"], 50)
            self.assertEqual(info1["visible_current_bis_mask"], 0)
            self.assertEqual(info1["visible_current_bis_age_seconds"], 30)
            self.assertEqual(info1["latent_true_bis"], info2["latent_true_bis"])
            self.assertTrue(np.all(first[22:34] == 0))
            if state is StateID.S1:
                self.assertTrue(np.all(first[34:42] == 0))

    def test_step_info_and_clipping_counter(self):
        env = environment()
        env.reset()
        _, _, terminated, truncated, info = env.step(30)
        self.assertFalse(terminated)
        self.assertFalse(truncated)
        self.assertEqual(info["raw_action_mg_per_10s"], 30)
        self.assertEqual(info["applied_action_mg_per_10s"], 27.7)
        self.assertTrue(info["action_was_clipped"])
        self.assertEqual(info["action_saturation_count"], 1)
        _, _, _, _, info = env.step(1)
        self.assertEqual(info["action_saturation_count"], 1)

    def test_event_after_endpoint_is_not_visible_early(self):
        tmpl = template(bis=(10.001,), sqi=((10.001, 100),))
        env = environment(tmpl=tmpl)
        env.reset()
        _, _, _, _, first = env.step(0)
        self.assertEqual(first["visible_current_bis_reason"], BISReason.NO_PRIOR.value)
        _, _, _, _, second = env.step(0)
        self.assertEqual(second["visible_current_bis_mask"], 1)

    def test_horizon_truncates_without_bis_safety_termination(self):
        env = environment(horizon=10, tmpl=template(horizon=10, bis=(10,), sqi=((10, 100),)))
        env.reset()
        _, _, terminated, truncated, _ = env.step(0)
        self.assertFalse(terminated)
        self.assertTrue(truncated)
        with self.assertRaises(RuntimeError):
            env.step(0)

    def test_piecewise_schedule_exact_endpoint(self):
        schedule = PiecewiseConstantRemifentanilSchedule(((0, 0), (4, 6)))
        tmpl = template(bis=(3, 8), sqi=((3, 100), (8, 100)))
        env = environment(tmpl=tmpl, schedule=schedule)
        env.reset()
        _, _, _, _, info = env.step(2)
        direct = DualDrugSimulator.from_profile(PROFILE)
        first = direct.advance(4, 12, 0)
        second = first.next_simulator.advance(6, 12, 6)
        self.assertAlmostEqual(info["latent_true_bis"], second.deterministic_bis_index, places=12)
        self.assertAlmostEqual(info["remifentanil_cp_microgram_per_l"], second.remifentanil_cp_microgram_per_l, places=12)

    def test_s1_prefix_recent_cumulative_and_concentrations(self):
        tmpl = template(bis=(), sqi=(), horizon=100)
        schedule = ConstantRemifentanilSchedule(6)
        s0 = environment(state=StateID.S0, tmpl=tmpl, schedule=schedule)
        s1 = environment(state=StateID.S1, tmpl=tmpl, schedule=schedule)
        for _ in range(7):
            o0, *_ = s0.step(2)
            o1, _, _, _, info = s1.step(2)
            np.testing.assert_array_equal(o0, o1[:34])
        self.assertAlmostEqual(o1[34], 12.0)
        self.assertAlmostEqual(o1[35], 6.0)
        self.assertAlmostEqual(o1[36], 14.0)
        self.assertAlmostEqual(o1[37], 7.0)
        self.assertAlmostEqual(o1[38], info["propofol_cp_mg_per_l"])
        self.assertAlmostEqual(o1[41], info["remifentanil_ce_microgram_per_l"])

    def test_four_condition_latent_reward_action_invariance(self):
        tmpl = template(bis=(10, 20, 30), sqi=((10, 20), (20, 20), (30, 20)))
        envs = {
            name: AnesthesiaEnvironmentCore(
                profile=PROFILE,
                config=EnvironmentConfig(config.preprocessing_id, config.state_id, episode_horizon_seconds=100),
                observation_template=tmpl,
                remifentanil_schedule=PiecewiseConstantRemifentanilSchedule(((0, 1), (15, 3))),
            ) for name, config in FOUR_CONDITION_CONFIGS.items()
        }
        for env in envs.values():
            env.reset(seed=11)
        for action in (1, 2, 30):
            results = {name: env.step(action) for name, env in envs.items()}
            latent = {round(result[4]["latent_true_bis"], 13) for result in results.values()}
            rewards = {round(result[1], 13) for result in results.values()}
            applied = {result[4]["applied_action_mg_per_10s"] for result in results.values()}
            self.assertEqual(len(latent), 1)
            self.assertEqual(len(rewards), 1)
            self.assertEqual(len(applied), 1)
            np.testing.assert_array_equal(results["P0S0"][0], results["P0S1"][0][:34])
            np.testing.assert_array_equal(results["P1S0"][0], results["P1S1"][0][:34])
        self.assertNotEqual(results["P0S0"][4]["visible_current_bis_mask"], results["P1S0"][4]["visible_current_bis_mask"])

    def test_forbidden_rl_imports_absent(self):
        source = "\n".join(path.read_text(encoding="utf-8") for path in Path("src/vitaldb_state_selection/anesthesia").glob("*.py"))
        for forbidden in ("import gymnasium", "import gym", "stable_baselines3", "import torch"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
