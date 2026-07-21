from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
PRIVATE = ROOT / "data/processed/phase8c_train_runtime_inputs_v1"
SCALERS = ROOT / "data/manifests/phase8c_scaler_registry.json"
SMOKE = ROOT / "data/manifests/phase8c_smoke_summary.json"

try:
    from vitaldb_state_selection.anesthesia import ConditionID
    from vitaldb_state_selection.cohort.train_runtime_inputs import TrainRuntimeInputStore, load_scaler_registry
    from vitaldb_state_selection.rl_integration.train_runtime import make_train_runtime_environment
    OPTIONAL_AVAILABLE = True
except ImportError:
    OPTIONAL_AVAILABLE = False


@unittest.skipUnless(OPTIONAL_AVAILABLE and PRIVATE.is_dir() and SCALERS.is_file(), "isolated Phase 8C runtime required")
class Phase8CRLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.store = TrainRuntimeInputStore(PRIVATE, ROOT)
        cls.scalers = load_scaler_registry(SCALERS)
        cls.caseid = cls.store.rows[len(cls.store.rows) // 2]["caseid"]

    def test_four_conditions_reset_step_shapes_and_determinism(self) -> None:
        latent_by_state = {}
        for condition in ConditionID:
            scaler = self.scalers["S0" if condition.value.endswith("S0") else "S1"]
            environment = make_train_runtime_environment(store=self.store, caseid=self.caseid, condition_id=condition, scaler=scaler)
            first, _ = environment.reset(seed=42)
            second, _ = environment.reset(seed=42)
            np.testing.assert_array_equal(first, second)
            observation, reward, terminated, truncated, info = environment.step(np.asarray([1.0], dtype=np.float32))
            self.assertEqual(observation.shape, (34 if condition.value.endswith("S0") else 42,))
            self.assertTrue(np.isfinite(observation).all())
            self.assertTrue(np.isfinite(reward))
            self.assertFalse(terminated)
            self.assertFalse(truncated)
            self.assertFalse(info["action_was_clipped"])
            latent_by_state[condition.value] = info["latent_true_bis"]
            environment.close()
        self.assertEqual(latent_by_state["P0S0"], latent_by_state["P1S0"])
        self.assertEqual(latent_by_state["P0S1"], latent_by_state["P1S1"])

    @unittest.skipUnless(SMOKE.is_file(), "official Phase 8C smoke not generated")
    def test_four_condition_smoke_is_bounded_correctness_only(self) -> None:
        payload = json.loads(SMOKE.read_text(encoding="utf-8"))
        self.assertEqual(payload["seed"], 42)
        self.assertTrue(payload["single_seed_only"])
        self.assertEqual(payload["timestep_budget_per_condition"], 128)
        self.assertEqual(len(payload["results"]), 4)
        self.assertTrue(all(row["status"] == "passed" and row["total_timesteps"] == 128 for row in payload["results"]))
        self.assertTrue(all(row["model_persisted"] is False and row["checkpoint_created"] is False for row in payload["results"]))
        self.assertFalse(payload["performance_ranking_computed"])
        self.assertEqual(payload["test_access_count"], 0)


if __name__ == "__main__":
    unittest.main()
