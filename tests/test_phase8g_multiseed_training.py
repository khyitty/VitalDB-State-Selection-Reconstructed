from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
PRIVATE = ROOT / "data/processed/phase8c_train_runtime_inputs_v1"

try:
    extension = importlib.import_module(
        "vitaldb_state_selection.rl_integration.multiseed_training"
    )
    from vitaldb_state_selection.cohort.train_runtime_inputs import (
        TrainRuntimeInputStore,
        load_scaler_registry,
    )

    EXTENSION_AVAILABLE = True
except ImportError:
    extension = None
    EXTENSION_AVAILABLE = False


class Phase8GModuleAvailabilityTests(unittest.TestCase):
    def test_phase8g_module_exists(self) -> None:
        self.assertTrue(EXTENSION_AVAILABLE, "Phase 8G module is not implemented")


@unittest.skipUnless(EXTENSION_AVAILABLE and PRIVATE.is_dir(), "Phase 8G isolated runtime required")
class Phase8GMultiseedTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.store = TrainRuntimeInputStore(PRIVATE, ROOT)
        cls.caseids = tuple(row["caseid"] for row in cls.store.rows)
        cls.scalers = load_scaler_registry(
            ROOT / "data/manifests/phase8c_scaler_registry.json"
        )

    def test_only_prespecified_seeds_and_budget_are_accepted(self) -> None:
        self.assertEqual(extension.ALLOWED_SEEDS, (43, 44))
        for seed in extension.ALLOWED_SEEDS:
            config = extension.multiseed_configuration(seed)
            self.assertEqual(config.seed, seed)
            self.assertEqual(config.total_timesteps, 1_000_000)
        for seed in (42, 45, -1):
            with self.assertRaises(extension.MultiSeedTrainingError):
                extension.multiseed_configuration(seed)

    def test_phase8d_config_and_runner_remain_seed_42_only(self) -> None:
        from vitaldb_state_selection.rl_integration.final_training import (
            final_config_sha256,
        )

        self.assertEqual(
            final_config_sha256(),
            "b5d79a2fb8be3b5337c7cb807936247c630b86f108f2a92cc6f645023f789b3e",
        )
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/run_phase8d_final_training.py"),
                "--condition",
                "P0S0",
                "--seed",
                "43",
                "--expected-git-sha",
                "0" * 40,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rejects every seed except 42", result.stderr)

    def test_same_seed_sequences_match_and_different_seeds_differ(self) -> None:
        by_seed = {}
        for seed in extension.ALLOWED_SEEDS:
            rows = []
            for _ in range(4):
                sequence = extension.MultiSeedTrainCaseSequence(
                    self.caseids, seed=seed
                )
                rows.append([sequence.next_caseid() for _ in range(256)])
            self.assertTrue(all(row == rows[0] for row in rows[1:]))
            by_seed[seed] = rows[0]
        self.assertNotEqual(by_seed[43], by_seed[44])
        self.assertNotEqual(
            extension.episode_sequence_sha256(self.caseids, seed=43, count=1000),
            extension.episode_sequence_sha256(self.caseids, seed=44, count=1000),
        )

    def test_state_dimensions_action_bounds_and_no_leakage_are_preserved(self) -> None:
        for seed in extension.ALLOWED_SEEDS:
            for condition in ("P0S0", "P1S0", "P0S1", "P1S1"):
                state = "S0" if condition.endswith("S0") else "S1"
                sequence = extension.MultiSeedTrainCaseSequence(
                    self.caseids, seed=seed
                )
                environment = extension.MultiSeedSequentialTrainRuntimeEnv(
                    store=self.store,
                    condition_id=condition,
                    scaler=self.scalers[state],
                    sequence=sequence,
                    seed=seed,
                )
                observation, info = environment.reset(seed=seed)
                self.assertEqual(observation.shape, (34 if state == "S0" else 42,))
                np.testing.assert_array_equal(
                    environment.action_space.low, np.asarray([0.0], dtype=np.float32)
                )
                np.testing.assert_array_equal(
                    environment.action_space.high,
                    np.asarray([27.7], dtype=np.float32),
                )
                self.assertEqual(info["phase8g_test_access_count"], 0)
                _, reward, _, _, step_info = environment.step(
                    np.asarray([1.0], dtype=np.float32)
                )
                self.assertTrue(np.isfinite(reward))
                self.assertEqual(
                    step_info["phase8g_future_remifentanil_leakage_count"], 0
                )
                environment.close()

    def test_output_paths_and_partial_directories_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            self.assertEqual(
                extension.condition_output_directory(output, "P0S0", 43),
                output / "P0S0" / "seed_43",
            )
            for seed in (42, 45):
                with self.assertRaises(extension.MultiSeedTrainingError):
                    extension.condition_output_directory(output, "P0S0", seed)
            partial = output / "P0S0" / "seed_43" / ".checkpoint.partial"
            partial.mkdir(parents=True)
            manager = extension.make_checkpoint_manager(
                condition_directory=partial.parent,
                condition_id="P0S0",
                implementation_sha="a" * 40,
                config_sha256="b" * 64,
                state_schema_sha256=self.scalers["S0"].schema_sha256,
                train_universe_sha256_value=extension.train_universe_sha256(
                    self.caseids
                ),
                seed=43,
            )
            with self.assertRaises(extension.MultiSeedTrainingError):
                manager.assert_no_partials()
            self.assertTrue(partial.is_dir())

    def test_resume_rejects_wrong_seed_condition_config_and_implementation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            metadata = {
                "condition_id": "P0S0",
                "seed": 43,
                "config_sha256": "a" * 64,
                "git_implementation_sha": "b" * 40,
                "state_schema_sha256": self.scalers["S0"].schema_sha256,
                "phase8c_private_root_sha256": extension.PHASE8C_EXPECTED_ROOT_SHA256,
                "train_universe_sha256": extension.train_universe_sha256(
                    self.caseids
                ),
                "total_timestep_budget": 1_000_000,
            }
            path = root / "metadata.json"
            path.write_text(json.dumps(metadata), encoding="utf-8")
            extension.validate_resume_metadata(path, expected=metadata)
            for key, value in (
                ("seed", 44),
                ("condition_id", "P1S0"),
                ("config_sha256", "c" * 64),
                ("git_implementation_sha", "d" * 40),
            ):
                wrong = dict(metadata)
                wrong[key] = value
                with self.assertRaises(extension.MultiSeedTrainingError):
                    extension.validate_resume_metadata(path, expected=wrong)

    def test_progress_jsonl_appends_monitorable_seed_condition_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            extension.append_progress(
                directory,
                {
                    "condition_id": "P0S0",
                    "event": "checkpoint",
                    "seed": 43,
                    "test_access_count": 0,
                    "timestep": 100_000,
                },
            )
            extension.append_progress(
                directory,
                {
                    "condition_id": "P0S0",
                    "event": "checkpoint",
                    "seed": 43,
                    "test_access_count": 0,
                    "timestep": 200_000,
                },
            )
            rows = [
                json.loads(line)
                for line in (directory / "progress.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual([row["timestep"] for row in rows], [100_000, 200_000])
            self.assertTrue(all(row["seed"] == 43 for row in rows))


if __name__ == "__main__":
    unittest.main()
