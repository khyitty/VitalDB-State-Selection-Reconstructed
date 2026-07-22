"""Fail-closed aggregation of private Phase 8E rows into public-safe results."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np

from vitaldb_state_selection.publication.phase8f_renderer import (
    CONDITIONS,
    CONTRASTS,
    METRIC_FORMAT,
    METRICS,
)
from vitaldb_state_selection.statistics.paired_evaluation import paired_metric_summary


EXPECTED_CASES = 490
EXPECTED_SUBJECTS = 483
EXPECTED_ROWS = EXPECTED_CASES * len(CONDITIONS)
TRAINING_IMPLEMENTATION_SHA = "b782b5e4a9d418f6b907a87d046c4e9789a3e5f0"
FINAL_TIMESTEP = 1_000_000
SEED = 42
BOOTSTRAP_REPLICATES = 2_000
PERMUTATION_REPLICATES = 2_000
MODEL_SHA256 = {
    "P0S0": "f783ba214b9dc7e511ff4af7d38a641bd3924861cf562fad670b4b840ff77f3f",
    "P1S0": "c73bd394af2e5bf801c890bf9d98e1bf5876660b775c3c611ab7c8cdf0a93b83",
    "P0S1": "644371f5d74164fbe04b5f85f2301c4e2b0babf193e1667e623d3a209ce67947",
    "P1S1": "f79172fa014f23507ab2b33eb2a4cd9f2f1615e321165ce8a448ea5d3e0ab662",
}


class FinalResultsError(RuntimeError):
    """Raised before public output when private result integrity is incomplete."""


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def verify_model_files(models_root: Path | str) -> dict[str, str]:
    root = Path(models_root)
    observed: dict[str, str] = {}
    for condition in CONDITIONS:
        directory = root / condition / "seed_42"
        marker_path = directory / "OUTPUT_COMPLETE.json"
        model_path = directory / "final_model.zip"
        if not marker_path.is_file() or not model_path.is_file():
            raise FinalResultsError(f"missing final model or completion marker: {condition}")
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        expected_marker = {
            "completed": True,
            "condition_id": condition,
            "git_implementation_sha": TRAINING_IMPLEMENTATION_SHA,
            "seed": SEED,
            "timestep": FINAL_TIMESTEP,
            "total_timestep_budget": FINAL_TIMESTEP,
            "test_access_count": 0,
            "final_model_sha256": MODEL_SHA256[condition],
        }
        if any(marker.get(key) != value for key, value in expected_marker.items()):
            raise FinalResultsError(f"final model completion metadata mismatch: {condition}")
        model_sha = hashlib.sha256(model_path.read_bytes()).hexdigest()
        if model_sha != MODEL_SHA256[condition]:
            raise FinalResultsError(f"final model checksum mismatch after evaluation: {condition}")
        observed[condition] = model_sha
    return observed


def read_private_rows(path: Path | str) -> tuple[list[dict[str, object]], str]:
    source = Path(path)
    payload = source.read_bytes()
    rows: list[dict[str, object]] = []
    try:
        text = payload.decode("utf-8")
        reader = csv.DictReader(text.splitlines())
        required = ("caseid", "subjectid", "condition_id", *METRICS, "episode_completed", "episode_failure_reason")
        if tuple(reader.fieldnames or ()) != required:
            raise FinalResultsError("private result header differs from the frozen Phase 8E contract")
        for source_row in reader:
            row: dict[str, object] = {
                "caseid": str(source_row["caseid"]).strip(),
                "subjectid": str(source_row["subjectid"]).strip(),
                "condition_id": str(source_row["condition_id"]).strip(),
                "episode_completed": str(source_row["episode_completed"]).strip().lower() == "true",
                "episode_failure_reason": str(source_row["episode_failure_reason"]),
            }
            for metric in METRICS:
                value = float(source_row[metric])
                if not math.isfinite(value):
                    raise FinalResultsError(f"non-finite private metric: {metric}")
                row[metric] = value
            rows.append(row)
    except (UnicodeDecodeError, csv.Error, ValueError, TypeError) as error:
        raise FinalResultsError(f"private result parsing failed: {error}") from error
    return rows, sha256_bytes(payload)


def validate_private_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    expected_cases: int = EXPECTED_CASES,
    expected_subjects: int = EXPECTED_SUBJECTS,
) -> dict[str, object]:
    if len(rows) != expected_cases * len(CONDITIONS):
        raise FinalResultsError("private case-condition row accounting mismatch")
    pairs: set[tuple[str, str]] = set()
    subjects_by_case: dict[str, set[str]] = {}
    cases_by_condition = {condition: set() for condition in CONDITIONS}
    failed_by_condition = {condition: 0 for condition in CONDITIONS}
    for row in rows:
        caseid = str(row.get("caseid", "")).strip()
        subjectid = str(row.get("subjectid", "")).strip()
        condition = str(row.get("condition_id", "")).strip()
        if not caseid or not subjectid or condition not in CONDITIONS:
            raise FinalResultsError("missing identifier or unknown condition in private results")
        pair = (caseid, condition)
        if pair in pairs:
            raise FinalResultsError("duplicate case-condition row")
        pairs.add(pair)
        subjects_by_case.setdefault(caseid, set()).add(subjectid)
        cases_by_condition[condition].add(caseid)
        completed = row.get("episode_completed") is True
        failure = str(row.get("episode_failure_reason", "")).strip()
        if not completed or failure:
            failed_by_condition[condition] += 1
        for metric in METRICS:
            value = float(row[metric])
            if not math.isfinite(value):
                raise FinalResultsError(f"non-finite private metric: {metric}")
    caseids = set(subjects_by_case)
    if len(caseids) != expected_cases or any(cases != caseids for cases in cases_by_condition.values()):
        raise FinalResultsError("condition case sets are not the same complete sealed-test set")
    if any(len(subjects) != 1 for subjects in subjects_by_case.values()):
        raise FinalResultsError("case-to-subject mapping differs across conditions")
    subjectids = {next(iter(subjects)) for subjects in subjects_by_case.values()}
    if len(subjectids) != expected_subjects:
        raise FinalResultsError("private subject accounting mismatch")
    if any(failed_by_condition.values()):
        raise FinalResultsError(f"failed final-evaluation episode present: {failed_by_condition}")
    return {
        "case_count": len(caseids),
        "subject_count": len(subjectids),
        "case_condition_row_count": len(rows),
        "failed_by_condition": failed_by_condition,
    }


def _subject_condition_values(
    rows: Sequence[Mapping[str, object]], condition: str, metric: str
) -> np.ndarray:
    by_subject: dict[str, list[float]] = {}
    for row in rows:
        if row["condition_id"] == condition:
            by_subject.setdefault(str(row["subjectid"]), []).append(float(row[metric]))
    return np.asarray(
        [float(np.mean(by_subject[subject])) for subject in sorted(by_subject, key=lambda value: (int(value), value))],
        dtype=np.float64,
    )


def build_aggregate(
    rows: Sequence[Mapping[str, object]],
    *,
    expected_cases: int = EXPECTED_CASES,
    expected_subjects: int = EXPECTED_SUBJECTS,
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES,
    permutation_replicates: int = PERMUTATION_REPLICATES,
) -> tuple[dict[str, object], dict[str, object]]:
    accounting = validate_private_rows(rows, expected_cases=expected_cases, expected_subjects=expected_subjects)
    condition_rows: list[dict[str, object]] = []
    for condition in CONDITIONS:
        metrics: list[dict[str, object]] = []
        for metric in METRICS:
            values = _subject_condition_values(rows, condition, metric)
            if values.size != expected_subjects or not np.isfinite(values).all():
                raise FinalResultsError("subject-level condition summary is incomplete")
            metrics.append({
                "metric_name": metric,
                "unit": METRIC_FORMAT[metric][0],
                "subject_count": expected_subjects,
                "mean": float(values.mean()),
                "sd": float(values.std(ddof=1)),
                "median": float(np.median(values)),
                "q1": float(np.quantile(values, 0.25)),
                "q3": float(np.quantile(values, 0.75)),
                "minimum": float(values.min()),
                "maximum": float(values.max()),
            })
        condition_rows.append({
            "condition_id": condition,
            "seed": SEED,
            "final_timestep": FINAL_TIMESTEP,
            "final_model_sha256": MODEL_SHA256[condition],
            "case_count": expected_cases,
            "subject_count": expected_subjects,
            "failed_case_count": 0,
            "metrics": metrics,
        })
    contrasts: list[dict[str, object]] = []
    for metric in METRICS:
        summary = paired_metric_summary(
            rows,
            metric,
            seed=SEED,
            bootstrap_replicates=bootstrap_replicates,
            permutation_replicates=permutation_replicates,
        )
        if summary["case_count"] != expected_cases or summary["subject_count"] != expected_subjects:
            raise FinalResultsError("paired subject aggregation accounting mismatch")
        for contrast in CONTRASTS:
            result = summary["contrasts"][contrast]
            dz = result["cohens_dz"]
            if dz is None or not math.isfinite(float(dz)):
                raise FinalResultsError("Cohen's dz is undefined or non-finite")
            contrasts.append({
                "metric_name": metric,
                "unit": METRIC_FORMAT[metric][0],
                "contrast_id": contrast,
                "subject_count": expected_subjects,
                "mean_difference": float(result["mean_difference"]),
                "median_difference": float(result["median_difference"]),
                "bootstrap_ci_95": [float(value) for value in result["bootstrap_ci_95"]],
                "paired_sign_flip_permutation_p": float(result["paired_sign_flip_permutation_p"]),
                "holm_adjusted_p": float(result["holm_adjusted_p"]),
                "cohens_dz": float(dz),
            })
    aggregate = {
        "schema_version": "phase8e-final-evaluation-aggregate-v1",
        "data_origin": "sealed_test_evaluation",
        "training_implementation_sha": TRAINING_IMPLEMENTATION_SHA,
        "evaluation_seed": SEED,
        "test_case_count": expected_cases,
        "test_subject_count": expected_subjects,
        "condition_order": list(CONDITIONS),
        "case_accounting": {
            "attempted_per_condition": expected_cases,
            "completed_per_condition": expected_cases,
            "failed_per_condition": 0,
            "silent_exclusion_count": 0,
            "failed_case_handling": "explicit_private_failure_rows_retained",
            "public_case_level_row_count": 0,
            "public_event_level_row_count": 0,
        },
        "conditions": condition_rows,
        "contrasts": contrasts,
        "results_interpreted": False,
        "best_condition_selected": False,
    }
    statistics = {
        "schema_version": "phase8e-final-statistics-v1",
        "case_level_rows_consumed": accounting["case_condition_row_count"],
        "case_count": expected_cases,
        "subject_count": expected_subjects,
        "condition_order": list(CONDITIONS),
        "metric_order": list(METRICS),
        "contrast_order": list(CONTRASTS),
        "subject_aggregation": "mean_of_case_level_metric_within_subject_before_inference",
        "bootstrap_unit": "subjectid_after_case_level_metrics",
        "bootstrap_replicates": bootstrap_replicates,
        "permutation_test": "paired_sign_flip_two_sided",
        "permutation_replicates": permutation_replicates,
        "random_seed": SEED,
        "holm_scope": "five_frozen_contrasts_within_each_metric",
        "condition_metric_row_count": len(CONDITIONS) * len(METRICS),
        "contrast_row_count": len(contrasts),
        "results_interpreted": False,
        "best_condition_selected": False,
        "contrasts": contrasts,
    }
    return aggregate, statistics
