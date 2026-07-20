import importlib.util
import unittest


RL_AVAILABLE = importlib.util.find_spec("gymnasium") is not None and importlib.util.find_spec("stable_baselines3") is not None


@unittest.skipUnless(RL_AVAILABLE, "Phase 7H optional RL dependencies are not installed")
class Phase7HSmokeTests(unittest.TestCase):
    def test_one_bounded_smoke_per_condition(self):
        from vitaldb_state_selection.rl_integration.smoke import run_condition_smoke

        rows = [run_condition_smoke(condition) for condition in ("P0S0", "P1S0", "P0S1", "P1S1")]
        self.assertEqual(len(rows), 4)
        for row in rows:
            self.assertEqual(row["status"], "passed")
            self.assertEqual(row["seed"], 42)
            self.assertEqual(row["device"], "cpu")
            self.assertEqual(row["total_timesteps"], 128)
            self.assertEqual(row["action_shape"], [1])
            self.assertIn(row["observation_shape"], ([34], [42]))
            self.assertEqual(row["environment_core_clip_count"], 0)
            self.assertFalse(row["checkpoint_created"])
            self.assertFalse(row["performance_metrics_recorded"])

    def test_p0s0_repeat_is_deterministic(self):
        from vitaldb_state_selection.rl_integration.smoke import run_condition_smoke

        first = run_condition_smoke("P0S0")
        second = run_condition_smoke("P0S0")
        self.assertEqual(first["initial_observation_sha256"], second["initial_observation_sha256"])
        self.assertEqual(first["first_deterministic_action_sha256"], second["first_deterministic_action_sha256"])
        self.assertEqual(first["model_parameter_sha256"], second["model_parameter_sha256"])
        self.assertEqual(first["total_timesteps"], second["total_timesteps"])


if __name__ == "__main__":
    unittest.main()
