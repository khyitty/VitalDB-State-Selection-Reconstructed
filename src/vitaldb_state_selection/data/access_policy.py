"""Fail-closed data-access policy for sealed confirmatory workflows."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path


class TestAccessDenied(RuntimeError):
    """Raised when a request would use sealed test data without authorization."""


TRAIN_ONLY_OPERATIONS = {
    "feature_selection", "scaler_fit", "imputer_fit", "normalization_fit", "pk_calibration_fit",
}
TRAIN_VALIDATION_OPERATIONS = {"early_stopping", "hyperparameter_selection"}
PROHIBITED_TEST_SUMMARIES = {"test_summary", "bis_distribution", "target_summary"}


def _authorization_enabled(manifest: Mapping[str, object] | None) -> bool:
    return bool(manifest and manifest.get("test_evaluation_authorized") is True)


def load_authorization(path: Path | None) -> Mapping[str, object] | None:
    if path is None or not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TestAccessDenied("authorization manifest must be a JSON object")
    return value


def authorize_access(
    operation: str,
    requested_splits: Iterable[str],
    *,
    authorization_manifest: Mapping[str, object] | None = None,
) -> None:
    splits = set(requested_splits)
    unknown = splits - {"train", "validation", "test"}
    if unknown:
        raise ValueError(f"unknown split names: {sorted(unknown)}")
    if operation in PROHIBITED_TEST_SUMMARIES and "test" in splits:
        raise TestAccessDenied(f"{operation} is prohibited for sealed test data")
    if operation in TRAIN_ONLY_OPERATIONS and splits - {"train"}:
        raise TestAccessDenied(f"{operation} is train-only")
    if operation in TRAIN_VALIDATION_OPERATIONS and "test" in splits:
        raise TestAccessDenied(f"{operation} may use validation but not test")
    if "test" in splits and not _authorization_enabled(authorization_manifest):
        raise TestAccessDenied("test evaluation is not authorized by a versioned manifest")


def assert_disjoint_split_ids(
    train_ids: Iterable[int], validation_ids: Iterable[int], test_ids: Iterable[int],
) -> None:
    train, validation, test = set(train_ids), set(validation_ids), set(test_ids)
    if train & validation or train & test or validation & test:
        raise TestAccessDenied("split ID overlap detected")
