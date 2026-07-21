from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
PRIVATE = ROOT / "data/processed/phase8c_train_runtime_inputs_v1"
CONFIG = ROOT / "data/manifests/phase8d_final_ppo_config.json"

try:
    from vitaldb_state_selection.cohort.train_runtime_inputs import TrainRuntimeInputStore, load_scaler_registry
    from vitaldb_state_selection.rl_integration.final_training import (
        CANONICAL_PPO_SEED,
        CHECKPOINT_INTERVAL,
        FINAL_TOTAL_TIMESTEPS,
        PHASE8C_EXPECTED_ROOT_SHA256,
        CheckpointManager,
        DeterministicTrainCaseSequence,
        FinalTrainingCallback,
        FinalTrainingError,
        SequentialTrainRuntimeEnv,
        episode_sequence_sha256,
        final_config_sha256,
        train_universe_sha256,
    )
    OPTIONAL_AVAILABLE = True
except ImportError:
    OPTIONAL_AVAILABLE = False


@unittest.skipUnless(OPTIONAL_AVAILABLE and PRIVATE.is_dir() and CONFIG.is_file(), "isolated Phase 8D runtime required")
class Phase8DFinalTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.store = TrainRuntimeInputStore(PRIVATE, ROOT)
        cls.caseids = tuple(row["caseid"] for row in cls.store.rows)
        cls.scalers = load_scaler_registry(ROOT / "data/manifests/phase8c_scaler_registry.json")

    def test_same_deterministic_sequence_for_every_condition(self) -> None:
        sequences = []
        for _ in range(4):
            sequence = DeterministicTrainCaseSequence(self.caseids)
            sequences.append([sequence.next_caseid() for _ in range(100)])
        self.assertTrue(all(row == sequences[0] for row in sequences[1:]))
        self.assertEqual(episode_sequence_sha256(self.caseids, count=1000), episode_sequence_sha256(self.caseids, count=1000))

    def test_test_case_is_refused_before_runtime_bundle_load(self) -> None:
        test_case = next(caseid for caseid, split in self.store.split_guard.case_split.items() if split == "test")
        with self.assertRaises(Exception):
            self.store.load_case(test_case)

    def test_four_conditions_have_only_the_frozen_input_dimension_difference(self) -> None:
        for condition in ("P0S0", "P1S0", "P0S1", "P1S1"):
            state = "S0" if condition.endswith("S0") else "S1"
            sequence = DeterministicTrainCaseSequence(self.caseids)
            environment = SequentialTrainRuntimeEnv(
                store=self.store,
                condition_id=condition,
                scaler=self.scalers[state],
                sequence=sequence,
            )
            observation, info = environment.reset(seed=42)
            self.assertEqual(observation.shape, (34 if state == "S0" else 42,))
            self.assertTrue(np.isfinite(observation).all())
            self.assertEqual(info["phase8d_test_access_count"], 0)
            _, reward, _, _, step_info = environment.step(np.asarray([1.0], dtype=np.float32))
            self.assertTrue(np.isfinite(reward))
            self.assertEqual(step_info["phase8d_future_remifentanil_leakage_count"], 0)
            environment.close()

    def _manager(self, directory: Path, **overrides) -> CheckpointManager:
        values = {
            "condition_directory": directory,
            "condition_id": "P0S0",
            "implementation_sha": "a" * 40,
            "config_sha256": final_config_sha256(),
            "state_schema_sha256": self.scalers["S0"].schema_sha256,
            "runtime_root_sha256": PHASE8C_EXPECTED_ROOT_SHA256,
            "train_universe_sha256_value": train_universe_sha256(self.caseids),
            "seed": CANONICAL_PPO_SEED,
            "total_timesteps": FINAL_TOTAL_TIMESTEPS,
        }
        values.update(overrides)
        return CheckpointManager(**values)

    def test_checkpoint_atomicity_corruption_and_mismatch_refusal(self) -> None:
        class FakeModel:
            num_timesteps = CHECKPOINT_INTERVAL

            @staticmethod
            def save(path: str) -> None:
                Path(path + ".zip").write_bytes(b"model-with-optimizer")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "condition"
            manager = self._manager(root)
            sequence = DeterministicTrainCaseSequence(self.caseids)
            manager.save(FakeModel(), sequence)  # type: ignore[arg-type]
            checkpoint = root / "checkpoint_0000100000"
            self.assertTrue((checkpoint / "COMPLETE.json").is_file())
            self.assertFalse(any(path.name.endswith(".partial") for path in root.iterdir()))
            self.assertEqual(manager.latest()[0], CHECKPOINT_INTERVAL)  # type: ignore[index]
            wrong_seed = self._manager(root, seed=7)
            with self.assertRaises(FinalTrainingError):
                wrong_seed.latest()
            wrong_condition = self._manager(root, condition_id="P1S0")
            with self.assertRaises(FinalTrainingError):
                wrong_condition.latest()
            wrong_config = self._manager(root, config_sha256="b" * 64)
            with self.assertRaises(FinalTrainingError):
                wrong_config.latest()
            (checkpoint / "model.zip").write_bytes(b"corrupt")
            with self.assertRaises(FinalTrainingError):
                manager.latest()

    def test_seed_budget_and_exact_final_stop_are_not_configurable(self) -> None:
        self.assertEqual(CANONICAL_PPO_SEED, 42)
        self.assertEqual(FINAL_TOTAL_TIMESTEPS, 1_000_000)
        self.assertEqual(CHECKPOINT_INTERVAL, 100_000)
        with tempfile.TemporaryDirectory() as temporary:
            callback = FinalTrainingCallback(self._manager(Path(temporary) / "phase8d-test"), target_timestep=1_000_000)
            self.assertEqual(callback.target_timestep, 1_000_000)
        source = (ROOT / "scripts/run_phase8d_final_training.py").read_text(encoding="utf-8")
        self.assertIn("args.seed != CANONICAL_PPO_SEED", source)
        self.assertIn("args.total_timesteps != FINAL_TOTAL_TIMESTEPS", source)
        self.assertNotIn("early_stop", source)
        self.assertNotIn("best_checkpoint", source)


if __name__ == "__main__":
    unittest.main()
