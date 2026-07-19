"""Runtime guards that prevent partial production cohort accounting."""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable, Sequence


class CohortGuardError(ValueError):
    """Raised when a cohort accounting invariant is violated."""


def expected_caseids(start: int = 1, end: int = 6388) -> tuple[int, ...]:
    if start < 1 or end < start:
        raise CohortGuardError(f"invalid expected case range: {start}..{end}")
    return tuple(range(start, end + 1))


def normalize_caseid(value: object) -> int:
    if isinstance(value, bool):
        raise CohortGuardError("boolean is not a valid caseid")
    try:
        normalized = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise CohortGuardError(f"invalid caseid: {value!r}") from exc
    return normalized


def assert_source_ids_within_range(
    caseids: Iterable[object], *, start: int = 1, end: int = 6388
) -> list[int]:
    normalized = [normalize_caseid(value) for value in caseids]
    unexpected = sorted(set(normalized) - set(expected_caseids(start, end)))
    if unexpected:
        raise CohortGuardError(f"source contains out-of-range caseids: {unexpected[:10]}")
    return normalized


def assert_manifest_complete(
    caseids: Sequence[object], *, start: int = 1, end: int = 6388
) -> None:
    normalized = [normalize_caseid(value) for value in caseids]
    duplicates = sorted(caseid for caseid, count in Counter(normalized).items() if count > 1)
    if duplicates:
        raise CohortGuardError(f"duplicate manifest caseids: {duplicates[:10]}")
    expected = set(expected_caseids(start, end))
    actual = set(normalized)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise CohortGuardError(
            f"manifest coverage mismatch: missing={missing[:10]}, extra={extra[:10]}"
        )


def assert_production_options(
    *, production_mode: bool, case_limit: int | None = None, first_n: bool = False
) -> None:
    if production_mode and case_limit is not None:
        raise CohortGuardError("production audit forbids a case limit")
    if production_mode and first_n:
        raise CohortGuardError("production audit forbids first-N selection")


def fixed_seed_random_sample(
    caseids: Sequence[object], *, seed: int, sample_size: int = 25
) -> list[int]:
    if sample_size < 1 or sample_size > 25:
        raise CohortGuardError("engineering dry-run sample size must be between 1 and 25")
    normalized = [normalize_caseid(value) for value in caseids]
    if len(normalized) != len(set(normalized)):
        raise CohortGuardError("cannot sample from duplicate caseids")
    ordered = sorted(normalized)
    if len(ordered) < sample_size:
        raise CohortGuardError(
            f"need at least {sample_size} cases for dry run; found {len(ordered)}"
        )
    return sorted(random.Random(seed).sample(ordered, sample_size))
