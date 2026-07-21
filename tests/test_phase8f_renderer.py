from __future__ import annotations

import copy
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.publication.phase8f_renderer import (  # noqa: E402
    CONDITIONS,
    CONTRASTS,
    METRIC_FORMAT,
    METRICS,
    Phase8FRenderError,
    load_aggregate,
    render_payloads,
    validate_aggregate,
    write_outputs,
)

SCHEMA = json.loads((ROOT / "schemas/phase8f_aggregate_results.schema.json").read_text(encoding="utf-8"))


def synthetic_aggregate() -> dict[str, object]:
    conditions = []
    for condition_index, condition in enumerate(CONDITIONS):
        metrics = []
        for metric_index, metric_name in enumerate(METRICS):
            center = float(condition_index + metric_index + 10)
            metrics.append({
                "metric_name": metric_name,
                "unit": METRIC_FORMAT[metric_name][0],
                "subject_count": 483,
                "mean": center,
                "sd": 1.25,
                "median": center,
                "q1": center - 1,
                "q3": center + 1,
                "minimum": center - 2,
                "maximum": center + 2,
            })
        conditions.append({
            "condition_id": condition,
            "seed": 42,
            "final_timestep": 1_000_000,
            "final_model_sha256": f"{condition_index + 1:064x}",
            "case_count": 490,
            "subject_count": 483,
            "failed_case_count": 0,
            "metrics": metrics,
        })
    contrasts = []
    for metric_index, metric_name in enumerate(METRICS):
        for contrast_index, contrast_id in enumerate(CONTRASTS):
            difference = float(metric_index + contrast_index) / 10
            contrasts.append({
                "metric_name": metric_name,
                "unit": METRIC_FORMAT[metric_name][0],
                "contrast_id": contrast_id,
                "subject_count": 483,
                "mean_difference": difference,
                "median_difference": difference,
                "bootstrap_ci_95": [difference - 0.2, difference + 0.2],
                "paired_sign_flip_permutation_p": 0.02,
                "holm_adjusted_p": 0.1,
                "cohens_dz": 0.05,
            })
    return {
        "schema_version": "phase8e-final-evaluation-aggregate-v1",
        "data_origin": "synthetic_fixture",
        "training_implementation_sha": "b782b5e4a9d418f6b907a87d046c4e9789a3e5f0",
        "evaluation_seed": 42,
        "test_case_count": 490,
        "test_subject_count": 483,
        "condition_order": list(CONDITIONS),
        "case_accounting": {
            "attempted_per_condition": 490,
            "completed_per_condition": 490,
            "failed_per_condition": 0,
            "silent_exclusion_count": 0,
            "failed_case_handling": "explicit_private_failure_rows_retained",
            "public_case_level_row_count": 0,
            "public_event_level_row_count": 0,
        },
        "conditions": conditions,
        "contrasts": contrasts,
        "results_interpreted": False,
        "best_condition_selected": False,
    }


class Phase8FRendererTests(unittest.TestCase):
    def assert_invalid(self, mutate) -> None:
        payload = synthetic_aggregate()
        mutate(payload)
        with self.assertRaises(Phase8FRenderError):
            validate_aggregate(payload, SCHEMA)

    def test_valid_synthetic_fixture_and_all_formats_are_deterministic(self) -> None:
        payload = synthetic_aggregate()
        validate_aggregate(payload, SCHEMA)
        first = render_payloads(payload)
        second = render_payloads(copy.deepcopy(payload))
        self.assertEqual(first, second)
        self.assertEqual(len(first), 7)
        self.assertIn(b"\\begin{tabular}", first["condition_metrics.tex"])
        self.assertEqual(first["condition_metrics.csv"].count(b"\n"), 45)
        self.assertEqual(first["paired_contrasts.csv"].count(b"\n"), 56)
        summary = json.loads(first["publication_summary.json"])
        self.assertEqual(len(summary["condition_metrics"]), 44)
        self.assertEqual(len(summary["paired_contrasts"]), 55)

    def test_missing_condition_is_rejected(self) -> None:
        self.assert_invalid(lambda value: value["conditions"].pop())

    def test_wrong_seed_timestep_and_test_count_are_rejected(self) -> None:
        for key, value in (("seed", 7), ("final_timestep", 900_000), ("case_count", 489)):
            with self.subTest(key=key):
                self.assert_invalid(lambda payload, key=key, value=value: payload["conditions"][0].__setitem__(key, value))
        self.assert_invalid(lambda value: value.__setitem__("test_case_count", 489))

    def test_missing_metric_is_rejected(self) -> None:
        self.assert_invalid(lambda value: value["conditions"][0]["metrics"].pop())

    def test_invalid_contrast_is_rejected(self) -> None:
        self.assert_invalid(lambda value: value["contrasts"][0].__setitem__("contrast_id", "best_minus_worst"))

    def test_duplicate_contrast_is_rejected(self) -> None:
        self.assert_invalid(lambda value: value["contrasts"].__setitem__(1, copy.deepcopy(value["contrasts"][0])))

    def test_nonfinite_value_is_rejected(self) -> None:
        self.assert_invalid(lambda value: value["conditions"][0]["metrics"][0].__setitem__("mean", math.nan))

    def test_incomplete_or_silently_excluded_cases_are_rejected(self) -> None:
        self.assert_invalid(lambda value: value["case_accounting"].__setitem__("failed_per_condition", 1))
        self.assert_invalid(lambda value: value["case_accounting"].__setitem__("silent_exclusion_count", 1))

    def test_event_case_and_private_path_leakage_is_rejected(self) -> None:
        for key, value in (("timestamp", 1), ("caseid", 2), ("note", "data/processed/private-results.json")):
            with self.subTest(key=key):
                self.assert_invalid(lambda payload, key=key, value=value: payload.__setitem__(key, value))

    def test_duplicate_json_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"schema_version":"a","schema_version":"b"}', encoding="utf-8")
            with self.assertRaises(Phase8FRenderError):
                load_aggregate(path)

    def test_overwrite_is_refused_unless_explicit(self) -> None:
        outputs = render_payloads(synthetic_aggregate())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            write_outputs(output, outputs, overwrite=False)
            with self.assertRaises(Phase8FRenderError):
                write_outputs(output, outputs, overwrite=False)
            write_outputs(output, outputs, overwrite=True)
            self.assertEqual((output / "publication_summary.json").read_bytes(), outputs["publication_summary.json"])

    def test_verify_only_cli_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "aggregate.json"
            output = root / "does-not-exist"
            source.write_text(json.dumps(synthetic_aggregate(), allow_nan=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/render_phase8f_paper_tables.py"), "--input", str(source), "--output-dir", str(output), "--verify-only"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(output.exists())
            self.assertEqual(json.loads(result.stdout)["writes_performed"], 0)


class Phase8FArtifactTests(unittest.TestCase):
    def test_source_snapshot_checksums_and_execution_boundaries(self) -> None:
        snapshot = json.loads((ROOT / "data/manifests/phase8f_source_snapshot.json").read_text(encoding="utf-8"))
        self.assertEqual(snapshot["starting_commit_sha"], "2346b964c6c8a0bc1f66953b80c65aae8d4ca800")
        self.assertEqual(snapshot["local_head_at_start"], snapshot["starting_commit_sha"])
        self.assertEqual(snapshot["remote_tracking_main_at_start"], snapshot["starting_commit_sha"])
        self.assertEqual(snapshot["actual_remote_main_at_start"], snapshot["starting_commit_sha"])
        self.assertTrue(snapshot["worktree_and_index_clean_at_start"])
        for row in snapshot["source_files"]:
            path = ROOT / row["relative_path"]
            self.assertEqual(path.stat().st_size, row["bytes"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row["sha256"])
        boundaries = snapshot["execution_boundaries"]
        self.assertEqual(boundaries["actual_model_load_count"], 0)
        self.assertEqual(boundaries["actual_test_episode_count"], 0)
        self.assertFalse(boundaries["actual_condition_comparison"])
        self.assertEqual(boundaries["shard_b_access_count"], 0)
        self.assertFalse(boundaries["full_test_suite_run"])

    def test_manuscript_is_result_pending_and_has_required_sections(self) -> None:
        manuscript = (ROOT / "paper/manuscript.md").read_text(encoding="utf-8")
        for heading in ("## Abstract", "## Introduction", "## Methods", "## Results", "## Discussion", "### Limitations", "## Conclusion"):
            self.assertIn(heading, manuscript)
        self.assertIn("[RESULTS_PENDING]", manuscript)
        self.assertGreaterEqual(manuscript.count("[CONCLUSION_PENDING]"), 2)
        self.assertRegex(manuscript, r"\{\{P0S0_[A-Z0-9_]+\}\}")
        self.assertNotIn("significantly improved", manuscript.lower())
        self.assertNotIn("superior condition", manuscript.lower())
        self.assertTrue((ROOT / "paper/discussion_scenarios.md").is_file())
        self.assertTrue((ROOT / "paper/figures_tables_plan.md").is_file())
        self.assertTrue((ROOT / "paper/references.bib").is_file())

    def test_finalization_runbook_uses_existing_interfaces_and_declares_aggregate_gap(self) -> None:
        runbook = (ROOT / "docs/phase8f_finalization_runbook.md").read_text(encoding="utf-8")
        self.assertIn("scripts\\run_phase8d_final_training.py --shard B", runbook)
        self.assertIn("scripts\\run_phase8e_final_evaluation.py", runbook)
        self.assertIn("--verify-only", runbook)
        self.assertIn("--execute --output-root data/processed/phase8e_evaluation_outputs_v1", runbook)
        self.assertIn("does **not** expose a command that creates the Phase 8F aggregate JSON", runbook)
        self.assertIn("Do not invent or imply an existing aggregate-freeze CLI", runbook)

    def test_synthetic_validation_is_public_aggregate_only(self) -> None:
        validation = json.loads((ROOT / "data/manifests/phase8f_synthetic_validation.json").read_text(encoding="utf-8"))
        self.assertTrue(validation["fixture_only"])
        self.assertFalse(validation["actual_phase8e_aggregate_used"])
        self.assertEqual(validation["actual_model_load_count"], 0)
        self.assertEqual(validation["actual_test_episode_count"], 0)
        self.assertFalse(validation["actual_condition_comparison"])
        self.assertEqual(validation["shard_b_access_count"], 0)
        self.assertEqual(validation["public_case_level_row_count"], 0)
        self.assertEqual(validation["public_event_level_row_count"], 0)


if __name__ == "__main__":
    unittest.main()
