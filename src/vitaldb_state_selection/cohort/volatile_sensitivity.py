"""Outcome-blind Phase 5D volatile-exposure rule sensitivity calculations."""

from __future__ import annotations

import csv
import gzip
import io
import math
import random
import statistics
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass

from .guards import CohortGuardError
from .volatile_characterization import ALLOWED_TRACK_NAMES, SPEC_BY_NAME


EXPECTED_UNIVERSE_COUNT = 3219
PHASE5D_SEED = 20260720
CONTINUITY_GAP_MULTIPLIER = 3.0
DURATION_THRESHOLDS_SECONDS = (10.0, 30.0, 60.0, 300.0)
POSITIVE_PROPORTION_THRESHOLDS = (0.001, 0.01, 0.05, 0.10)

AGENT_SPECIFIC_TRACKS = frozenset(
    name
    for name in ALLOWED_TRACK_NAMES
    if SPEC_BY_NAME[name].device_group == "primus_agent_specific"
)
GAS2_TRACKS = frozenset(
    name for name in ALLOWED_TRACK_NAMES if SPEC_BY_NAME[name].device_group == "solar_gas2"
)
MAC_TRACKS = frozenset(
    name for name in ALLOWED_TRACK_NAMES if SPEC_BY_NAME[name].device_group == "primus_mac"
)
SUPPORT_TRACKS = GAS2_TRACKS | MAC_TRACKS

DEFINITION_ORDER = (
    "A_any_allowed_positive_once",
    "B_any_agent_specific_positive_once",
    "C_agent_specific_or_support_positive_once",
    "D_longest_positive_run_ge_10s",
    "E_longest_positive_run_ge_30s",
    "F_longest_positive_run_ge_60s",
    "G_longest_positive_run_ge_300s",
    "H_positive_proportion_ge_0_1pct",
    "H_positive_proportion_ge_1pct",
    "H_positive_proportion_ge_5pct",
    "H_positive_proportion_ge_10pct",
    "I_agent_specific_and_support_positive",
    "J_agent_specific_only_positive",
    "K_support_only_positive",
)

DEFINITION_DESCRIPTIONS = {
    "A_any_allowed_positive_once": "any allowed track value > 0 at least once in the anesthesia window",
    "B_any_agent_specific_positive_once": "any agent-specific track value > 0 at least once in the anesthesia window",
    "C_agent_specific_or_support_positive_once": "agent-specific or GAS2/MAC value > 0 at least once in the anesthesia window",
    "D_longest_positive_run_ge_10s": "maximum within-track continuous positive duration >= 10 seconds",
    "E_longest_positive_run_ge_30s": "maximum within-track continuous positive duration >= 30 seconds",
    "F_longest_positive_run_ge_60s": "maximum within-track continuous positive duration >= 60 seconds",
    "G_longest_positive_run_ge_300s": "maximum within-track continuous positive duration >= 300 seconds",
    "H_positive_proportion_ge_0_1pct": "maximum within-track positive proportion >= 0.1%",
    "H_positive_proportion_ge_1pct": "maximum within-track positive proportion >= 1%",
    "H_positive_proportion_ge_5pct": "maximum within-track positive proportion >= 5%",
    "H_positive_proportion_ge_10pct": "maximum within-track positive proportion >= 10%",
    "I_agent_specific_and_support_positive": "agent-specific and GAS2/MAC support are both positive",
    "J_agent_specific_only_positive": "agent-specific evidence is positive and GAS2/MAC support is not",
    "K_support_only_positive": "GAS2/MAC support is positive and agent-specific evidence is not",
}


class SensitivityParseError(ValueError):
    """A Phase 5C raw signal cannot be parsed without changing source semantics."""


@dataclass(frozen=True)
class TrackWindowEvidence:
    caseid: int
    track_name: str
    device_group: str
    track_present: bool
    positive_observed_anywhere: bool
    positive_observed_in_anesthesia_window: bool
    anesthesia_window_sample_count: int
    anesthesia_window_finite_value_count: int
    anesthesia_window_positive_count: int
    positive_proportion: float | None
    median_positive_timestamp_interval_seconds: float | None
    continuity_gap_boundary_seconds: float | None
    positive_run_count: int
    longest_positive_run_seconds: float
    total_positive_continuous_duration_seconds: float
    duplicate_timestamp_count: int
    zero_interval_count: int
    negative_interval_count: int
    long_gap_interval_count: int
    nonfinite_value_count: int
    warning_flags: tuple[str, ...]


def _decode_payload(payload: bytes) -> str:
    decoded = gzip.decompress(payload) if payload.startswith(b"\x1f\x8b") else payload
    try:
        return decoded.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SensitivityParseError(f"UTF-8 decode failed: {exc}") from exc


def analyze_track_payload(
    payload: bytes,
    *,
    caseid: int,
    track_name: str,
    anesthesia_start: float,
    anesthesia_end: float,
    gap_multiplier: float = CONTINUITY_GAP_MULTIPLIER,
) -> TrackWindowEvidence:
    """Analyze one exact track without sorting, deleting, averaging, or resampling rows."""
    if track_name not in SPEC_BY_NAME:
        raise CohortGuardError(f"track is outside the Phase 5C allowlist: {track_name}")
    if gap_multiplier <= 0:
        raise ValueError("gap_multiplier must be positive")
    anesthesia_window_valid = anesthesia_end >= anesthesia_start

    reader = csv.reader(io.StringIO(_decode_payload(payload)))
    try:
        header = next(reader)
    except StopIteration as exc:
        raise SensitivityParseError("track payload has no header") from exc
    if len(header) < 2 or header[0].strip() != "Time":
        raise SensitivityParseError(f"unexpected track header: {header!r}")
    if header[1].strip() != track_name:
        raise SensitivityParseError(
            f"value-column mismatch: expected {track_name!r}, got {header[1].strip()!r}"
        )

    observations: list[tuple[float, float | None]] = []
    nonfinite_value_count = 0
    for row_number, row in enumerate(reader, start=2):
        if not row:
            continue
        if len(row) < 2:
            raise SensitivityParseError(f"row {row_number} has fewer than two columns")
        try:
            timestamp = float(row[0])
        except ValueError as exc:
            raise SensitivityParseError(
                f"row {row_number} has invalid timestamp {row[0]!r}"
            ) from exc
        if not math.isfinite(timestamp):
            raise SensitivityParseError(f"row {row_number} has non-finite timestamp")
        raw_value = row[1].strip()
        if raw_value == "":
            observations.append((timestamp, None))
            continue
        try:
            value = float(raw_value)
        except ValueError as exc:
            raise SensitivityParseError(
                f"row {row_number} has invalid value {raw_value!r}"
            ) from exc
        if not math.isfinite(value):
            nonfinite_value_count += 1
            observations.append((timestamp, None))
            continue
        observations.append((timestamp, value))

    positive_anywhere = any(value is not None and value > 0 for _, value in observations)
    window = (
        [
            (timestamp, value)
            for timestamp, value in observations
            if anesthesia_start <= timestamp <= anesthesia_end
        ]
        if anesthesia_window_valid
        else []
    )
    finite_values = [value for _, value in window if value is not None]
    positive_count = sum(value > 0 for value in finite_values)
    positive_proportion = positive_count / len(finite_values) if finite_values else None

    positive_intervals = [
        current[0] - previous[0]
        for previous, current in zip(window, window[1:])
        if current[0] - previous[0] > 0
    ]
    median_interval = statistics.median(positive_intervals) if positive_intervals else None
    gap_boundary = median_interval * gap_multiplier if median_interval is not None else None

    seen_timestamps: set[float] = set()
    duplicate_timestamp_count = 0
    for timestamp, _ in window:
        if timestamp in seen_timestamps:
            duplicate_timestamp_count += 1
        seen_timestamps.add(timestamp)

    zero_interval_count = 0
    negative_interval_count = 0
    long_gap_interval_count = 0
    run_count = 0
    current_duration = 0.0
    longest_duration = 0.0
    total_duration = 0.0
    previous_timestamp: float | None = None
    previous_positive = False
    for timestamp, value in window:
        current_positive = value is not None and value > 0
        contiguous = False
        if previous_timestamp is not None:
            interval = timestamp - previous_timestamp
            if interval == 0:
                zero_interval_count += 1
            elif interval < 0:
                negative_interval_count += 1
            elif gap_boundary is not None and interval > gap_boundary:
                long_gap_interval_count += 1
            else:
                contiguous = gap_boundary is not None

            if current_positive and previous_positive and contiguous:
                current_duration += interval
                total_duration += interval
                longest_duration = max(longest_duration, current_duration)
            elif current_positive:
                run_count += 1
                current_duration = 0.0
            else:
                current_duration = 0.0
        elif current_positive:
            run_count += 1

        previous_timestamp = timestamp
        previous_positive = current_positive

    flags: set[str] = set()
    if duplicate_timestamp_count:
        flags.add("duplicate_timestamp")
    if zero_interval_count:
        flags.add("zero_interval")
    if negative_interval_count:
        flags.add("negative_interval")
    if long_gap_interval_count:
        flags.add("long_gap")
    if nonfinite_value_count:
        flags.add("nonfinite_value")
    if positive_count and gap_boundary is None:
        flags.add("continuity_boundary_unavailable")
    if not anesthesia_window_valid:
        flags.add("inverted_anesthesia_window")

    return TrackWindowEvidence(
        caseid=caseid,
        track_name=track_name,
        device_group=SPEC_BY_NAME[track_name].device_group,
        track_present=True,
        positive_observed_anywhere=positive_anywhere,
        positive_observed_in_anesthesia_window=positive_count > 0,
        anesthesia_window_sample_count=len(window),
        anesthesia_window_finite_value_count=len(finite_values),
        anesthesia_window_positive_count=positive_count,
        positive_proportion=positive_proportion,
        median_positive_timestamp_interval_seconds=median_interval,
        continuity_gap_boundary_seconds=gap_boundary,
        positive_run_count=run_count,
        longest_positive_run_seconds=longest_duration,
        total_positive_continuous_duration_seconds=total_duration,
        duplicate_timestamp_count=duplicate_timestamp_count,
        zero_interval_count=zero_interval_count,
        negative_interval_count=negative_interval_count,
        long_gap_interval_count=long_gap_interval_count,
        nonfinite_value_count=nonfinite_value_count,
        warning_flags=tuple(sorted(flags)),
    )


def absent_track_evidence(caseid: int, track_name: str) -> TrackWindowEvidence:
    if track_name not in SPEC_BY_NAME:
        raise CohortGuardError(f"track is outside the Phase 5C allowlist: {track_name}")
    return TrackWindowEvidence(
        caseid=caseid,
        track_name=track_name,
        device_group=SPEC_BY_NAME[track_name].device_group,
        track_present=False,
        positive_observed_anywhere=False,
        positive_observed_in_anesthesia_window=False,
        anesthesia_window_sample_count=0,
        anesthesia_window_finite_value_count=0,
        anesthesia_window_positive_count=0,
        positive_proportion=None,
        median_positive_timestamp_interval_seconds=None,
        continuity_gap_boundary_seconds=None,
        positive_run_count=0,
        longest_positive_run_seconds=0.0,
        total_positive_continuous_duration_seconds=0.0,
        duplicate_timestamp_count=0,
        zero_interval_count=0,
        negative_interval_count=0,
        long_gap_interval_count=0,
        nonfinite_value_count=0,
        warning_flags=(),
    )


def _maximum_metric(
    evidence: Sequence[TrackWindowEvidence],
    field: str,
    allowed_names: frozenset[str] | set[str] | None = None,
) -> float:
    selected = [item for item in evidence if allowed_names is None or item.track_name in allowed_names]
    values = [getattr(item, field) for item in selected]
    numeric = [float(value) for value in values if value is not None]
    return max(numeric, default=0.0)


def build_case_record(
    case_source: Mapping[str, object],
    evidence: Sequence[TrackWindowEvidence],
) -> dict[str, object]:
    caseid = int(case_source["caseid"])
    if len(evidence) != len(ALLOWED_TRACK_NAMES):
        raise CohortGuardError(f"case {caseid} does not have seven Phase 5D evidence rows")
    if {item.track_name for item in evidence} != set(ALLOWED_TRACK_NAMES):
        raise CohortGuardError(f"case {caseid} has an invalid Phase 5D track set")

    positive_names = {
        item.track_name for item in evidence if item.positive_observed_in_anesthesia_window
    }
    agent_positive = bool(positive_names & AGENT_SPECIFIC_TRACKS)
    gas2_positive = bool(positive_names & GAS2_TRACKS)
    mac_positive = bool(positive_names & MAC_TRACKS)
    support_positive = gas2_positive or mac_positive
    any_positive = agent_positive or support_positive
    longest = _maximum_metric(evidence, "longest_positive_run_seconds")
    max_proportion = _maximum_metric(evidence, "positive_proportion")

    definitions = {
        "A_any_allowed_positive_once": any_positive,
        "B_any_agent_specific_positive_once": agent_positive,
        "C_agent_specific_or_support_positive_once": agent_positive or support_positive,
        "D_longest_positive_run_ge_10s": longest >= 10.0,
        "E_longest_positive_run_ge_30s": longest >= 30.0,
        "F_longest_positive_run_ge_60s": longest >= 60.0,
        "G_longest_positive_run_ge_300s": longest >= 300.0,
        "H_positive_proportion_ge_0_1pct": max_proportion >= 0.001,
        "H_positive_proportion_ge_1pct": max_proportion >= 0.01,
        "H_positive_proportion_ge_5pct": max_proportion >= 0.05,
        "H_positive_proportion_ge_10pct": max_proportion >= 0.10,
        "I_agent_specific_and_support_positive": agent_positive and support_positive,
        "J_agent_specific_only_positive": agent_positive and not support_positive,
        "K_support_only_positive": support_positive and not agent_positive,
    }
    if tuple(definitions) != DEFINITION_ORDER:
        raise AssertionError("definition order drifted")

    return {
        "caseid": caseid,
        "anesthesia_window_valid": float(case_source["anesthesia_end"])
        >= float(case_source["anesthesia_start"]),
        "analysis_universe_frozen": False,
        "legacy_overlap": "pending_not_evaluated",
        "volatile_exposure_decision": "pending_human_review",
        "tiva_decision": "pending_human_review",
        "any_allowed_positive_anywhere": any(
            item.positive_observed_anywhere for item in evidence
        ),
        "any_allowed_positive_in_anesthesia_window": any_positive,
        "agent_specific_positive": agent_positive,
        "gas2_positive": gas2_positive,
        "mac_positive": mac_positive,
        "support_positive": support_positive,
        "max_allowed_longest_positive_run_seconds": longest,
        "max_agent_longest_positive_run_seconds": _maximum_metric(
            evidence, "longest_positive_run_seconds", set(AGENT_SPECIFIC_TRACKS)
        ),
        "max_support_longest_positive_run_seconds": _maximum_metric(
            evidence, "longest_positive_run_seconds", set(SUPPORT_TRACKS)
        ),
        "max_allowed_track_positive_proportion": max_proportion,
        "max_agent_track_positive_proportion": _maximum_metric(
            evidence, "positive_proportion", set(AGENT_SPECIFIC_TRACKS)
        ),
        "max_support_track_positive_proportion": _maximum_metric(
            evidence, "positive_proportion", set(SUPPORT_TRACKS)
        ),
        "duplicate_timestamp_count": sum(item.duplicate_timestamp_count for item in evidence),
        "zero_interval_count": sum(item.zero_interval_count for item in evidence),
        "negative_interval_count": sum(item.negative_interval_count for item in evidence),
        "long_gap_interval_count": sum(item.long_gap_interval_count for item in evidence),
        "warning_track_count": sum(bool(item.warning_flags) for item in evidence),
        "definitions": definitions,
    }


def _nearest_rank(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    rank = max(1, math.ceil(probability * len(ordered)))
    return ordered[rank - 1]


def metric_distribution(values: Sequence[float]) -> dict[str, object]:
    numeric = [float(value) for value in values]
    return {
        "count": len(numeric),
        "minimum": min(numeric) if numeric else None,
        "q01": _nearest_rank(numeric, 0.01),
        "q05": _nearest_rank(numeric, 0.05),
        "q25": _nearest_rank(numeric, 0.25),
        "q50": _nearest_rank(numeric, 0.50),
        "q75": _nearest_rank(numeric, 0.75),
        "q95": _nearest_rank(numeric, 0.95),
        "q99": _nearest_rank(numeric, 0.99),
        "maximum": max(numeric) if numeric else None,
        "quantile_method": "nearest_rank_across_supplied_case_level_metrics",
    }


def duration_histogram(values: Sequence[float]) -> list[dict[str, object]]:
    specifications = (
        ("zero", lambda value: value == 0.0, 0.0, 0.0),
        ("positive_under_10s", lambda value: 0.0 < value < 10.0, 0.0, 10.0),
        ("10_to_under_30s", lambda value: 10.0 <= value < 30.0, 10.0, 30.0),
        ("30_to_under_60s", lambda value: 30.0 <= value < 60.0, 30.0, 60.0),
        ("60_to_under_300s", lambda value: 60.0 <= value < 300.0, 60.0, 300.0),
        ("300_to_under_600s", lambda value: 300.0 <= value < 600.0, 300.0, 600.0),
        ("600_to_under_1800s", lambda value: 600.0 <= value < 1800.0, 600.0, 1800.0),
        ("1800_to_under_3600s", lambda value: 1800.0 <= value < 3600.0, 1800.0, 3600.0),
        ("3600s_or_more", lambda value: value >= 3600.0, 3600.0, None),
    )
    rows = [
        {
            "label": label,
            "lower_bound": lower,
            "upper_bound": upper,
            "count": sum(predicate(float(value)) for value in values),
        }
        for label, predicate, lower, upper in specifications
    ]
    if sum(int(row["count"]) for row in rows) != len(values):
        raise AssertionError("duration histogram does not account for every case")
    return rows


def proportion_histogram(values: Sequence[float]) -> list[dict[str, object]]:
    specifications = (
        ("zero", lambda value: value == 0.0, 0.0, 0.0),
        ("positive_under_0_1pct", lambda value: 0.0 < value < 0.001, 0.0, 0.001),
        ("0_1_to_under_1pct", lambda value: 0.001 <= value < 0.01, 0.001, 0.01),
        ("1_to_under_5pct", lambda value: 0.01 <= value < 0.05, 0.01, 0.05),
        ("5_to_under_10pct", lambda value: 0.05 <= value < 0.10, 0.05, 0.10),
        ("10_to_under_25pct", lambda value: 0.10 <= value < 0.25, 0.10, 0.25),
        ("25_to_under_50pct", lambda value: 0.25 <= value < 0.50, 0.25, 0.50),
        ("50_to_under_75pct", lambda value: 0.50 <= value < 0.75, 0.50, 0.75),
        ("75_to_100pct", lambda value: 0.75 <= value <= 1.0, 0.75, 1.0),
    )
    rows = [
        {
            "label": label,
            "lower_bound": lower,
            "upper_bound": upper,
            "count": sum(predicate(float(value)) for value in values),
        }
        for label, predicate, lower, upper in specifications
    ]
    if sum(int(row["count"]) for row in rows) != len(values):
        raise AssertionError("proportion histogram does not account for every case")
    return rows


def definition_summaries(case_records: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name in DEFINITION_ORDER:
        excluded = sum(bool(row["definitions"][name]) for row in case_records)
        rows.append(
            {
                "definition": name,
                "description": DEFINITION_DESCRIPTIONS[name],
                "excluded_case_count": excluded,
                "retained_case_count": EXPECTED_UNIVERSE_COUNT - excluded,
                "excluded_fraction": excluded / EXPECTED_UNIVERSE_COUNT,
                "retained_fraction": (EXPECTED_UNIVERSE_COUNT - excluded)
                / EXPECTED_UNIVERSE_COUNT,
                "selected": False,
            }
        )
    return rows


def disagreement_matrix(case_records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    matrix: dict[str, dict[str, int]] = {}
    for left in DEFINITION_ORDER:
        matrix[left] = {}
        for right in DEFINITION_ORDER:
            matrix[left][right] = sum(
                bool(row["definitions"][left]) != bool(row["definitions"][right])
                for row in case_records
            )
    return {"definition_order": list(DEFINITION_ORDER), "counts": matrix}


def _fixed_sample(
    members: Sequence[int],
    *,
    seed: int,
    size: int = 5,
) -> list[int]:
    unique = sorted(set(int(value) for value in members))
    rng = random.Random(seed)
    return sorted(rng.sample(unique, min(size, len(unique))))


def boundary_samples(
    case_records: Sequence[Mapping[str, object]],
    *,
    seed: int = PHASE5D_SEED,
) -> tuple[dict[str, int], dict[str, list[int]]]:
    categories = {
        "any_positive_but_under_10s": [
            int(row["caseid"])
            for row in case_records
            if row["any_allowed_positive_in_anesthesia_window"]
            and float(row["max_allowed_longest_positive_run_seconds"]) < 10.0
        ],
        "10_to_under_30s": [
            int(row["caseid"])
            for row in case_records
            if 10.0 <= float(row["max_allowed_longest_positive_run_seconds"]) < 30.0
        ],
        "30_to_under_60s": [
            int(row["caseid"])
            for row in case_records
            if 30.0 <= float(row["max_allowed_longest_positive_run_seconds"]) < 60.0
        ],
        "60_to_under_300s": [
            int(row["caseid"])
            for row in case_records
            if 60.0 <= float(row["max_allowed_longest_positive_run_seconds"]) < 300.0
        ],
        "agent_negative_support_positive": [
            int(row["caseid"])
            for row in case_records
            if not row["agent_specific_positive"] and row["support_positive"]
        ],
        "agent_positive_support_negative": [
            int(row["caseid"])
            for row in case_records
            if row["agent_specific_positive"] and not row["support_positive"]
        ],
        "positive_only_outside_anesthesia_window": [
            int(row["caseid"])
            for row in case_records
            if row["any_allowed_positive_anywhere"]
            and not row["any_allowed_positive_in_anesthesia_window"]
        ],
        "duplicate_timestamp_or_abnormal_gap_warning": [
            int(row["caseid"])
            for row in case_records
            if int(row["duplicate_timestamp_count"]) > 0
            or int(row["zero_interval_count"]) > 0
            or int(row["negative_interval_count"]) > 0
            or int(row["long_gap_interval_count"]) > 0
        ],
        "invalid_anesthesia_window": [
            int(row["caseid"])
            for row in case_records
            if not row["anesthesia_window_valid"]
        ],
    }
    counts = {name: len(members) for name, members in sorted(categories.items())}
    samples = {
        name: _fixed_sample(members, seed=seed + offset)
        for offset, (name, members) in enumerate(sorted(categories.items()))
    }
    return counts, samples


def combination_results(case_records: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    groups: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in case_records:
        key = "|".join(
            (
                f"agent_specific_positive={str(bool(row['agent_specific_positive'])).lower()}",
                f"gas2_positive={str(bool(row['gas2_positive'])).lower()}",
                f"mac_positive={str(bool(row['mac_positive'])).lower()}",
            )
        )
        groups[key].append(row)
    return [
        {
            "combination": combination,
            "case_count": len(members),
            "definition_excluded_counts": {
                name: sum(bool(row["definitions"][name]) for row in members)
                for name in DEFINITION_ORDER
            },
        }
        for combination, members in sorted(groups.items())
    ]


def candidate_protocols(
    definition_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    by_name = {str(row["definition"]): row for row in definition_rows}
    candidates = (
        ("conservative", "A_any_allowed_positive_once"),
        ("duration-based", "F_longest_positive_run_ge_60s"),
        ("corroborated", "I_agent_specific_and_support_positive"),
    )
    return [
        {
            "candidate_name": candidate,
            "exact_rule": definition,
            "exact_rule_description": DEFINITION_DESCRIPTIONS[definition],
            "expected_excluded_case_count": int(by_name[definition]["excluded_case_count"]),
            "expected_retained_case_count": int(by_name[definition]["retained_case_count"]),
            "selected": False,
            "recommended": False,
        }
        for candidate, definition in candidates
    ]


def build_sensitivity_summary(
    case_records: Sequence[Mapping[str, object]],
    track_evidence: Sequence[TrackWindowEvidence],
    *,
    source_integrity: Mapping[str, object],
) -> dict[str, object]:
    caseids = [int(row["caseid"]) for row in case_records]
    if len(caseids) != EXPECTED_UNIVERSE_COUNT or len(caseids) != len(set(caseids)):
        raise CohortGuardError("Phase 5D requires exactly 3,219 unique case records")
    if len(track_evidence) != EXPECTED_UNIVERSE_COUNT * len(ALLOWED_TRACK_NAMES):
        raise CohortGuardError("Phase 5D requires a complete 3,219 by 7 evidence matrix")
    definition_rows = definition_summaries(case_records)
    durations = [float(row["max_allowed_longest_positive_run_seconds"]) for row in case_records]
    proportions = [float(row["max_allowed_track_positive_proportion"]) for row in case_records]
    boundary_counts, manual_samples = boundary_samples(case_records)
    warning_counts = Counter(
        flag for item in track_evidence for flag in item.warning_flags
    )
    continuity_by_track: dict[str, object] = {}
    for name in ALLOWED_TRACK_NAMES:
        present = [item for item in track_evidence if item.track_name == name and item.track_present]
        cadence_values = [
            float(item.median_positive_timestamp_interval_seconds)
            for item in present
            if item.median_positive_timestamp_interval_seconds is not None
        ]
        boundary_values = [
            float(item.continuity_gap_boundary_seconds)
            for item in present
            if item.continuity_gap_boundary_seconds is not None
        ]
        continuity_by_track[name] = {
            "present_track_count": len(present),
            "boundary_available_count": len(boundary_values),
            "boundary_unavailable_count": len(present) - len(boundary_values),
            "median_timestamp_interval_seconds_distribution": metric_distribution(
                cadence_values
            ),
            "continuity_gap_boundary_seconds_distribution": metric_distribution(
                boundary_values
            ),
        }
    return {
        "phase": "5D_volatile_exposure_rule_sensitivity_audit",
        "scientific_result": False,
        "decision_support_only": True,
        "selected_exposure_definition": None,
        "selected_protocol_candidate": None,
        "analysis_universe": {
            "definition": "exact primary tracks + age >= 18 + anesthesia_type exact General",
            "case_count": len(caseids),
            "duplicate_case_count": len(caseids) - len(set(caseids)),
            "missing_case_count": EXPECTED_UNIVERSE_COUNT - len(set(caseids)),
            "cohort_frozen": False,
        },
        "allowed_exact_tracks": [
            {
                "track_name": name,
                "device_group": SPEC_BY_NAME[name].device_group,
                "official_description": SPEC_BY_NAME[name].official_description,
                "official_unit": SPEC_BY_NAME[name].official_unit,
                "approval_status": "pending_human_review",
            }
            for name in ALLOWED_TRACK_NAMES
        ],
        "continuity_method": {
            "row_order": "original_payload_order",
            "timestamps": "original_no_sorting",
            "duplicate_timestamps": "retained_not_averaged_and_break_continuity",
            "zero_or_negative_interval": "flagged_and_breaks_continuity",
            "cadence_estimator": "median_of_strictly_positive_consecutive_timestamp_differences_within_anesthesia_window",
            "long_gap_boundary": "case_track_cadence_seconds_times_3",
            "gap_multiplier": CONTINUITY_GAP_MULTIPLIER,
            "long_gap_handling": "flagged_and_not_added_to_positive_duration",
            "single_positive_sample_duration_seconds": 0.0,
            "cross_track_runs_combined": False,
            "final_signal_quality_threshold": False,
        },
        "positive_proportion_method": {
            "track_level_denominator": "finite_samples_within_anesthesia_window",
            "case_level_metric": "maximum_track_level_positive_proportion_across_allowed_exact_tracks",
            "tracks_pooled": False,
        },
        "continuity_boundary_distributions_by_track": continuity_by_track,
        "definition_summaries": definition_rows,
        "pairwise_disagreement_matrix": disagreement_matrix(case_records),
        "duration_distribution_seconds": {
            "summary": metric_distribution(durations),
            "histogram_bins": duration_histogram(durations),
        },
        "positive_proportion_distribution": {
            "summary": metric_distribution(proportions),
            "histogram_bins": proportion_histogram(proportions),
        },
        "agent_specific_gas2_mac_combination_results": combination_results(case_records),
        "boundary_category_counts": boundary_counts,
        "manual_review_fixed_seed": PHASE5D_SEED,
        "manual_review_boundary_samples": manual_samples,
        "protocol_candidates": candidate_protocols(definition_rows),
        "warning_flag_track_counts": dict(sorted(warning_counts.items())),
        "source_integrity": dict(source_integrity),
        "case_records": list(case_records),
        "pending_decisions": [
            "volatile_exposure_rule",
            "tiva_classification",
            "final_alias_approval",
            "final_unit_approval",
            "signal_quality_thresholds",
            "legacy_98_overlap",
            "final_eligibility",
        ],
        "execution_flags": {
            "new_api_requests": False,
            "new_raw_files_created": False,
            "legacy_98_ids_accessed": False,
            "bis_signal_read": False,
            "drug_signal_read": False,
            "cp_ce_vol_signal_read": False,
            "cohort_frozen": False,
            "split_created": False,
            "prediction_dataset_built": False,
            "prediction_run": False,
            "feature_selection_run": False,
            "cpce_reconstruction_run": False,
            "ppo_run": False,
            "signal_quality_threshold_finalized": False,
            "alias_or_unit_approved": False,
        },
    }


def track_evidence_records(
    evidence: Sequence[TrackWindowEvidence],
) -> list[dict[str, object]]:
    return [asdict(item) for item in evidence]


def _display_fraction(value: object) -> str:
    return f"{100.0 * float(value):.2f}%"


def render_sensitivity_report(summary: Mapping[str, object]) -> str:
    universe = summary["analysis_universe"]
    method = summary["continuity_method"]
    lines = [
        "# Phase 5D Volatile Exposure Rule Sensitivity Audit",
        "",
        "## Interpretation boundary",
        "",
        "This is outcome-blind decision support over the unfrozen Phase 5C universe.",
        "No volatile-exposure rule, TIVA decision, signal-quality threshold, protocol",
        "candidate, or cohort was selected. Track presence alone is not exposure.",
        "",
        "## Source and accounting",
        "",
        "| Measure | Result |",
        "|---|---:|",
        f"| Cases | {universe['case_count']} |",
        f"| Duplicate cases | {universe['duplicate_case_count']} |",
        f"| Missing cases | {universe['missing_case_count']} |",
        f"| Phase 5C raw signals checksum-verified | {summary['source_integrity']['raw_signal_checksum_verified_count']} |",
        f"| New API requests | {summary['execution_flags']['new_api_requests']} |",
        f"| New raw files created | {summary['execution_flags']['new_raw_files_created']} |",
        "",
        "## Continuity and gap handling",
        "",
        "Rows and duplicate timestamps are retained in original payload order. For each",
        "case×track, the engineering continuity boundary is three times the median of",
        "strictly positive consecutive timestamp differences inside the anesthesia window.",
        "A zero/negative interval or an interval above that boundary is flagged and breaks",
        "the run; its gap is not added to duration. A single positive sample has duration 0.",
        "Runs are never joined across tracks. This engineering boundary is not a finalized",
        "signal-quality threshold.",
        "",
        f"- gap multiplier: `{method['gap_multiplier']}`",
        f"- cadence estimator: `{method['cadence_estimator']}`",
        f"- duplicate handling: `{method['duplicate_timestamps']}`",
        "",
        "### Observed continuity-boundary distributions",
        "",
        "The boundary is case×track-specific. Values below are across present tracks",
        "with an estimable positive timestamp interval.",
        "",
        "| Exact track | Available / present | Boundary q05 (s) | q50 (s) | q95 (s) |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, item in summary["continuity_boundary_distributions_by_track"].items():
        distribution = item["continuity_gap_boundary_seconds_distribution"]
        lines.append(
            f"| `{name}` | {item['boundary_available_count']} / {item['present_track_count']} | "
            f"{distribution['q05']:.6g} | {distribution['q50']:.6g} | "
            f"{distribution['q95']:.6g} |"
        )
    lines.extend(
        [
            "",
            "### Timestamp and gap warning flags",
            "",
            "| Track-level warning | Track rows |",
            "|---|---:|",
        ]
    )
    for flag, count in summary["warning_flag_track_counts"].items():
        lines.append(f"| `{flag}` | {count} |")
    lines.extend(
        [
            "",
        "## Exposure-definition sensitivity — none selected",
        "",
        "| Definition | Excluded | Retained | Excluded fraction |",
        "|---|---:|---:|---:|",
        ]
    )
    for row in summary["definition_summaries"]:
        lines.append(
            f"| `{row['definition']}` | {row['excluded_case_count']} | "
            f"{row['retained_case_count']} | {_display_fraction(row['excluded_fraction'])} |"
        )

    lines.extend(
        [
            "",
            "Definitions A and C are logically identical because the seven allowed tracks",
            "are exhausted by agent-specific, GAS2, and MAC groups; their disagreement is 0.",
            "",
            "## Pairwise disagreement matrix",
            "",
        ]
    )
    order = summary["pairwise_disagreement_matrix"]["definition_order"]
    matrix = summary["pairwise_disagreement_matrix"]["counts"]
    lines.append("| Definition | " + " | ".join(order) + " |")
    lines.append("|---|" + "---:|" * len(order))
    for left in order:
        lines.append(
            f"| `{left}` | " + " | ".join(str(matrix[left][right]) for right in order) + " |"
        )

    lines.extend(
        [
            "",
            "## Duration and positive-proportion distributions",
            "",
            "The proportion metric is the maximum within-track positive fraction per case;",
            "tracks with different sampling rates are not pooled.",
            "",
            "| Metric | Minimum | q25 | q50 | q75 | q95 | Maximum |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label, key in (
        ("Longest continuous positive duration (s)", "duration_distribution_seconds"),
        ("Maximum within-track positive proportion", "positive_proportion_distribution"),
    ):
        stats = summary[key]["summary"]
        lines.append(
            f"| {label} | {stats['minimum']:.6g} | {stats['q25']:.6g} | "
            f"{stats['q50']:.6g} | {stats['q75']:.6g} | {stats['q95']:.6g} | "
            f"{stats['maximum']:.6g} |"
        )
    for label, key in (
        ("Duration histogram", "duration_distribution_seconds"),
        ("Positive-proportion histogram", "positive_proportion_distribution"),
    ):
        lines.extend(["", f"### {label}", "", "| Bin | Cases |", "|---|---:|"])
        for row in summary[key]["histogram_bins"]:
            lines.append(f"| `{row['label']}` | {row['count']} |")

    lines.extend(
        [
            "",
            "## Agent-specific / GAS2 / MAC combinations",
            "",
            "| Positive-recording combination | Cases |",
            "|---|---:|",
        ]
    )
    for row in summary["agent_specific_gas2_mac_combination_results"]:
        lines.append(f"| `{row['combination'].replace('|', '; ')}` | {row['case_count']} |")

    lines.extend(
        [
            "",
            f"## Fixed-seed boundary review samples (seed {summary['manual_review_fixed_seed']})",
            "",
            "No sampled case is automatically included or excluded.",
            "",
            "| Boundary category | All cases | Sample case IDs |",
            "|---|---:|---|",
        ]
    )
    for category, count in summary["boundary_category_counts"].items():
        members = summary["manual_review_boundary_samples"][category]
        shown = ", ".join(str(value) for value in members) or "none"
        lines.append(f"| `{category}` | {count} | {shown} |")

    lines.extend(
        [
            "",
            "## Named protocol candidates — comparison only",
            "",
            "| Candidate | Exact rule | Expected excluded | Expected retained |",
            "|---|---|---:|---:|",
        ]
    )
    for row in summary["protocol_candidates"]:
        lines.append(
            f"| `{row['candidate_name']}` | `{row['exact_rule']}` | "
            f"{row['expected_excluded_case_count']} | {row['expected_retained_case_count']} |"
        )
    lines.extend(
        [
            "",
            "None is recommended or selected. Official documentary descriptions and units",
            "remain evidence only; alias and unit approval remain `pending_human_review`.",
            "",
            "## Work deliberately not performed",
            "",
            "No API request or raw download occurred. Legacy 98 IDs, BIS, propofol,",
            "remifentanil, CP, CE, VOL, prediction outcomes, and BIS values were not read.",
            "No final rule, TIVA classification, cohort freeze, threshold, split, prediction",
            "dataset, prediction, feature selection, Cp/Ce reconstruction, or PPO was run.",
            "Phase 5D stops here.",
            "",
        ]
    )
    return "\n".join(lines)
