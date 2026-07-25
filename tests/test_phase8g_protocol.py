from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Phase8GProtocolTests(unittest.TestCase):
    def test_required_public_artifacts_exist(self) -> None:
        required = (
            "docs/phase8g_multiseed_robustness_protocol.md",
            "docs/phase8g_parallel_training_runbook.md",
            "docs/phase8g_training_infrastructure_report.md",
            "data/manifests/phase8g_multiseed_config.json",
            "data/manifests/phase8g_seed_definition.json",
            "data/manifests/phase8g_shard_definition.json",
            "data/manifests/phase8g_source_snapshot.json",
            "data/manifests/phase8g_artifact_checksums.json",
            "scripts/build_phase8g_artifact_checksums.py",
            "scripts/run_phase8g_multiseed_training.py",
        )
        missing = [path for path in required if not (ROOT / path).is_file()]
        self.assertEqual(missing, [])

    def test_seed_shard_and_config_manifests_are_prespecified(self) -> None:
        seeds = json.loads(
            (ROOT / "data/manifests/phase8g_seed_definition.json").read_text(
                encoding="utf-8"
            )
        )
        config = json.loads(
            (ROOT / "data/manifests/phase8g_multiseed_config.json").read_text(
                encoding="utf-8"
            )
        )
        shards = json.loads(
            (ROOT / "data/manifests/phase8g_shard_definition.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(seeds["extension_seeds"], [43, 44])
        self.assertEqual(seeds["prespecified_date"], "2026-07-25")
        self.assertEqual(config["total_timesteps_per_condition"], 1_000_000)
        self.assertEqual(config["checkpoint_interval_timesteps"], 100_000)
        self.assertEqual(
            config["phase8d_final_ppo_config_sha256"],
            "b5d79a2fb8be3b5337c7cb807936247c630b86f108f2a92cc6f645023f789b3e",
        )
        self.assertEqual(shards["assignments"]["A"]["conditions"], ["P0S0", "P1S0"])
        self.assertEqual(shards["assignments"]["B"]["conditions"], ["P0S1", "P1S1"])
        self.assertTrue(shards["sequential_within_shard"])

    def test_source_snapshot_preserves_seed42_baseline(self) -> None:
        snapshot = json.loads(
            (ROOT / "data/manifests/phase8g_source_snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            snapshot["figure_package_baseline_sha"],
            "edede7b8f1a7b7726b505a5784399ddc96133aa9",
        )
        self.assertEqual(
            snapshot["phase8d_training_implementation_sha"],
            "b782b5e4a9d418f6b907a87d046c4e9789a3e5f0",
        )
        self.assertEqual(set(snapshot["seed42_output_baseline"]), {"P0S0", "P1S0", "P0S1", "P1S1"})
        self.assertTrue(all(row["manifest_mismatch_count"] == 0 for row in snapshot["seed42_output_baseline"].values()))


if __name__ == "__main__":
    unittest.main()
