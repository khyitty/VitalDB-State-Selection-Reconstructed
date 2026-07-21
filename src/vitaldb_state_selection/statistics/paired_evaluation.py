"""Paired 2x2 evaluation summaries for synthetic validation and later Phase 8E use."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import numpy as np


CONTRAST_WEIGHTS = {
    "P1S0_minus_P0S0": {"P0S0": -1.0, "P1S0": 1.0, "P0S1": 0.0, "P1S1": 0.0},
    "P1S1_minus_P0S1": {"P0S0": 0.0, "P1S0": 0.0, "P0S1": -1.0, "P1S1": 1.0},
    "P0S1_minus_P0S0": {"P0S0": -1.0, "P1S0": 0.0, "P0S1": 1.0, "P1S1": 0.0},
    "P1S1_minus_P1S0": {"P0S0": 0.0, "P1S0": -1.0, "P0S1": 0.0, "P1S1": 1.0},
    "interaction": {"P0S0": 1.0, "P1S0": -1.0, "P0S1": -1.0, "P1S1": 1.0},
}


class PairedEvaluationError(RuntimeError):
    pass


def paired_differences(rows: Sequence[Mapping[str, object]], metric: str, contrast: str) -> np.ndarray:
    if contrast not in CONTRAST_WEIGHTS:
        raise PairedEvaluationError(f"unknown contrast: {contrast}")
    by_case: dict[str, dict[str, float]] = {}
    for row in rows:
        caseid, condition = str(row["caseid"]), str(row["condition_id"])
        value = float(row[metric])
        if not math.isfinite(value):
            raise PairedEvaluationError("non-finite paired metric")
        if condition in by_case.setdefault(caseid, {}):
            raise PairedEvaluationError("duplicate case/condition row")
        by_case[caseid][condition] = value
    required = set(CONTRAST_WEIGHTS[contrast])
    if not by_case or any(set(values) != required for values in by_case.values()):
        raise PairedEvaluationError("paired case accounting is incomplete")
    return np.asarray([
        sum(CONTRAST_WEIGHTS[contrast][condition] * values[condition] for condition in required)
        for _, values in sorted(by_case.items(), key=lambda item: (int(item[0]), item[0]))
    ], dtype=np.float64)


def paired_subject_differences(
    rows: Sequence[Mapping[str, object]],
    metric: str,
    contrast: str,
) -> np.ndarray:
    """Aggregate complete case-level contrasts within subject before inference."""

    case_values = paired_differences(rows, metric, contrast)
    caseids = sorted({str(row["caseid"]) for row in rows}, key=lambda value: (int(value), value))
    subjects_by_case: dict[str, set[str]] = {caseid: set() for caseid in caseids}
    for row in rows:
        subjectid = str(row.get("subjectid", "")).strip()
        if not subjectid:
            raise PairedEvaluationError("subjectid is required for subject-level inference")
        subjects_by_case[str(row["caseid"])].add(subjectid)
    if any(len(subjects) != 1 for subjects in subjects_by_case.values()):
        raise PairedEvaluationError("case-to-subject mapping differs across conditions")
    by_subject: dict[str, list[float]] = {}
    for caseid, value in zip(caseids, case_values, strict=True):
        subjectid = next(iter(subjects_by_case[caseid]))
        by_subject.setdefault(subjectid, []).append(float(value))
    return np.asarray([
        float(np.mean(by_subject[subjectid]))
        for subjectid in sorted(by_subject, key=lambda value: (int(value), value))
    ], dtype=np.float64)


def holm_adjust(p_values: Mapping[str, float]) -> dict[str, float]:
    """Return multiplicity-adjusted p-values using Holm's step-down method."""

    if not p_values:
        raise PairedEvaluationError("Holm adjustment requires at least one p-value")
    ordered: list[tuple[str, float]] = []
    for name, raw in p_values.items():
        value = float(raw)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise PairedEvaluationError("p-values must be finite and within [0, 1]")
        ordered.append((str(name), value))
    ordered.sort(key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    running = 0.0
    total = len(ordered)
    for rank, (name, value) in enumerate(ordered):
        running = max(running, min(1.0, (total - rank) * value))
        adjusted[name] = running
    return {name: adjusted[name] for name in p_values}


def paired_summary(
    differences: Sequence[float],
    *,
    seed: int = 42,
    bootstrap_replicates: int = 2000,
    permutation_replicates: int = 2000,
) -> dict[str, object]:
    values = np.asarray(differences, dtype=np.float64)
    if values.ndim != 1 or values.size < 2 or not np.isfinite(values).all():
        raise PairedEvaluationError("paired differences must be finite and contain at least two values")
    generator = np.random.Generator(np.random.PCG64(seed))
    bootstrap = np.empty(bootstrap_replicates, dtype=np.float64)
    for index in range(bootstrap_replicates):
        bootstrap[index] = generator.choice(values, size=values.size, replace=True).mean()
    observed = abs(float(values.mean()))
    exceed = 0
    for _ in range(permutation_replicates):
        signs = generator.choice(np.asarray([-1.0, 1.0]), size=values.size)
        exceed += abs(float((values * signs).mean())) >= observed
    sample_sd = float(values.std(ddof=1))
    return {
        "bootstrap_ci_95": [float(np.quantile(bootstrap, 0.025)), float(np.quantile(bootstrap, 0.975))],
        "case_count": int(values.size),
        "cohens_dz": None if sample_sd <= 1e-12 else float(values.mean() / sample_sd),
        "mean_difference": float(values.mean()),
        "median_difference": float(np.median(values)),
        "paired_sign_flip_permutation_p": float((exceed + 1) / (permutation_replicates + 1)),
        "seed": seed,
    }


def paired_metric_summary(
    rows: Sequence[Mapping[str, object]],
    metric: str,
    *,
    seed: int = 42,
    bootstrap_replicates: int = 2000,
    permutation_replicates: int = 2000,
) -> dict[str, object]:
    """Summarize every frozen contrast at the subject analysis unit."""

    summaries: dict[str, dict[str, object]] = {}
    raw_p: dict[str, float] = {}
    for contrast in CONTRAST_WEIGHTS:
        differences = paired_subject_differences(rows, metric, contrast)
        summary = paired_summary(
            differences,
            seed=seed,
            bootstrap_replicates=bootstrap_replicates,
            permutation_replicates=permutation_replicates,
        )
        summaries[contrast] = summary
        raw_p[contrast] = float(summary["paired_sign_flip_permutation_p"])
    adjusted = holm_adjust(raw_p)
    for contrast, value in adjusted.items():
        summaries[contrast]["holm_adjusted_p"] = value
    return {
        "case_count": len({str(row["caseid"]) for row in rows}),
        "contrasts": summaries,
        "metric": metric,
        "subject_count": len({str(row["subjectid"]) for row in rows}),
    }
