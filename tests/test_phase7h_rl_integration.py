import importlib.util
import math
from pathlib import Path
import subprocess
import sys
import unittest
import warnings

import numpy as np


RL_AVAILABLE = importlib.util.find_spec("gymnasium") is not None and importlib.util.find_spec("stable_baselines3") is not None


@unittest.skipUnless(RL_AVAILABLE, "Phase 7H optional RL dependencies are not installed")
class Phase7HRLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vitaldb_state_selection.anesthesia import BISEvent, SQIEvent, SyntheticObservationTemplate
        from vitaldb_state_selection.pkpd import PatientProfile, Sex

        cls.profile = PatientProfile(45, Sex.FEMALE, 165, 60)
        cls.template = SyntheticObservationTemplate(
            "phase7h-test-template", 100,
            tuple(BISEvent(float(t)) for t in (0, 7, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)),
            tuple(SQIEvent(float(t), 80.0 if t != 20 else 40.0) for t in (0, 7, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)),
        )

    def make_env(self, condition, horizon=30):
        from vitaldb_state_selection.anesthesia import PiecewiseConstantRemifentanilSchedule
        from vitaldb_state_selection.rl_integration.factory import make_gymnasium_environment

        return make_gymnasium_environment(
            condition_id=condition,
            patient_profile=self.profile,
            observation_template=self.template,
            remifentanil_schedule=PiecewiseConstantRemifentanilSchedule(((0, 0), (4, 2), (17, 1))),
            seed=42,
            episode_horizon_seconds=horizon,
        )

    def test_all_four_reset_step_spaces_and_full_episode(self):
        for condition, dimension in (("P0S0", 34), ("P1S0", 34), ("P0S1", 42), ("P1S1", 42)):
            env = self.make_env(condition)
            observation, info = env.reset(seed=42)
            self.assertEqual(observation.shape, (dimension,))
            self.assertEqual(observation.dtype, np.float32)
            self.assertTrue(np.isfinite(observation).all())
            self.assertEqual(env.observation_space.shape, (dimension,))
            self.assertEqual(env.action_space.shape, (1,))
            np.testing.assert_array_equal(env.action_space.low, np.asarray([0.0], dtype=np.float32))
            np.testing.assert_array_equal(env.action_space.high, np.asarray([27.7], dtype=np.float32))
            steps = 0
            truncated = False
            while not truncated:
                observation, reward, terminated, truncated, info = env.step(np.asarray([1.0], dtype=np.float32))
                steps += 1
                self.assertIsInstance(reward, float)
                self.assertIsInstance(terminated, bool)
                self.assertIsInstance(truncated, bool)
                self.assertIsInstance(info, dict)
                self.assertFalse(terminated)
                self.assertFalse(info["action_was_clipped"])
            self.assertEqual(steps, 3)
            env.close()

    def test_gymnasium_and_sb3_checkers_all_four(self):
        from gymnasium.utils.env_checker import check_env as gym_check_env
        from stable_baselines3.common.env_checker import check_env as sb3_check_env

        captured = []
        for condition in ("P0S0", "P1S0", "P0S1", "P1S1"):
            env = self.make_env(condition)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                gym_check_env(env, skip_render_check=True)
                sb3_check_env(env, warn=True)
            captured.extend(str(item.message) for item in caught)
            env.close()
        unexpected = [message for message in captured if "symmetric and normalized" not in message]
        self.assertEqual(unexpected, [])

    def test_dummy_vec_env_and_model_initialization_all_four(self):
        from stable_baselines3.common.vec_env import DummyVecEnv
        from vitaldb_state_selection.rl_integration.config import PPO_INTEGRATION_SMOKE_V1, make_ppo_model

        for condition in ("P0S0", "P1S0", "P0S1", "P1S1"):
            vector = DummyVecEnv([lambda condition=condition: self.make_env(condition)])
            model = make_ppo_model(vector, PPO_INTEGRATION_SMOKE_V1)
            self.assertEqual(model.num_timesteps, 0)
            self.assertEqual(str(model.device), "cpu")
            self.assertTrue(all(group["weight_decay"] == 0.001 for group in model.policy.optimizer.param_groups))
            vector.close()

    def test_adapter_matches_direct_core_without_duplicate_clipping(self):
        from vitaldb_state_selection.anesthesia import AnesthesiaEnvironmentCore, EnvironmentConfig, PreprocessingID, StateID

        adapted = self.make_env("P0S1")
        direct = AnesthesiaEnvironmentCore(
            profile=self.profile,
            config=EnvironmentConfig(PreprocessingID.P0, StateID.S1, episode_horizon_seconds=30),
            observation_template=self.template,
            remifentanil_schedule=adapted.core.schedule,
        )
        adapted_observation, _ = adapted.reset(seed=42)
        direct_observation, _ = direct.reset(seed=42)
        np.testing.assert_array_equal(adapted_observation, direct_observation.astype(np.float32))
        for action in (0.0, 2.5, 27.7):
            adapted_result = adapted.step(np.asarray([action], dtype=np.float32))
            direct_result = direct.step(action)
            np.testing.assert_array_equal(adapted_result[0], direct_result[0].astype(np.float32))
            self.assertEqual(adapted_result[1], direct_result[1])
            self.assertEqual(adapted_result[4]["latent_true_bis"], direct_result[4]["latent_true_bis"])
            self.assertFalse(adapted_result[4]["action_was_clipped"])

    def test_candidate_and_smoke_configurations_are_exact_and_separate(self):
        from vitaldb_state_selection.rl_integration.config import PAPER_ORIENTED_PPO_CANDIDATE_V1 as candidate
        from vitaldb_state_selection.rl_integration.config import PPO_INTEGRATION_SMOKE_V1 as smoke

        common = {
            "gamma": 0.99, "gae_lambda": 0.95, "clip_range": 0.2, "vf_coef": 0.1,
            "ent_coef": 0.0, "max_grad_norm": 0.5, "learning_rate": 0.001,
            "optimizer_weight_decay": 0.001, "actor_hidden_layers": (128,),
            "critic_hidden_layers": (128,), "activation": "Tanh", "device": "cpu",
        }
        for key, value in common.items():
            self.assertEqual(getattr(candidate, key), value)
            self.assertEqual(getattr(smoke, key), value)
        self.assertEqual((candidate.n_steps, candidate.batch_size, candidate.n_epochs), (2048, 64, 10))
        self.assertIsNone(candidate.total_timesteps)
        self.assertIsNone(candidate.seed)
        self.assertEqual((smoke.n_steps, smoke.batch_size, smoke.n_epochs, smoke.total_timesteps, smoke.seed), (64, 32, 1, 128, 42))
        self.assertNotEqual(candidate.configuration_id, smoke.configuration_id)

    def test_no_recurrent_attention_prediction_or_custom_ppo(self):
        root = Path("src/vitaldb_state_selection/rl_integration")
        source = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
        for forbidden in ("LstmPolicy", "RecurrentPPO", "MultiheadAttention", "prediction_head", "class PPO("):
            self.assertNotIn(forbidden, source)

    def test_resolved_lock_exactly_matches_isolated_environment(self):
        completed = subprocess.run(
            [sys.executable, "-m", "pip", "freeze", "--all"],
            check=True,
            capture_output=True,
            text=True,
        )
        actual = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        expected = [line.strip() for line in Path("requirements/phase7h_rl_lock.txt").read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
