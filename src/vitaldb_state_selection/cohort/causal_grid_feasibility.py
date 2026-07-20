"""Bounded-memory, outcome-blind Phase 6C causal-grid feasibility helpers."""

from __future__ import annotations

import bisect
import csv
import gzip
import math
import random
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .guards import CohortGuardError
from .primary_signal_quality import distribution


EXPECTED_CASE_COUNT = 2470
EXPECTED_SOURCE_RAW_COUNT = 9880
PHASE6C_SEED = 20260720
GRID_INTERVAL_SECONDS = 10.0
HISTORY_OFFSETS_SECONDS = (-50.0, -40.0, -30.0, -20.0, -10.0, 0.0)
TARGET_OFFSET_SECONDS = 30.0
SQI_RULES = ("sqi_not_required", "sqi_ge_20", "sqi_ge_50", "sqi_ge_80")
BIS_STALENESS_CAPS = (10, 20, 30)
DRUG_HOLD_CAPS = (30, 60, 120, 300, 600)
MINIMUM_WINDOW_COUNTS = (30, 60, 120, 300, 600)
TRACK_NAMES = (
    "BIS/BIS",
    "BIS/SQI",
    "Orchestra/PPF20_RATE",
    "Orchestra/RFTN20_RATE",
)


@dataclass(frozen=True)
class ObservationIndex:
    """Chronological lookup index derived without changing the stored raw row order."""

    track_name: str
    timestamps: tuple[float, ...]
    values: tuple[float, ...]
    duplicated_timestamp: tuple[bool, ...]
    original_row_count: int
    finite_row_count: int
    duplicate_timestamp_count: int
    zero_interval_count: int
    negative_interval_count: int


def candidate_id(sqi_rule: str, bis_cap: int, drug_cap: int) -> str:
    if sqi_rule not in SQI_RULES:
        raise CohortGuardError(f"unknown SQI rule: {sqi_rule}")
    if bis_cap not in BIS_STALENESS_CAPS or drug_cap not in DRUG_HOLD_CAPS:
        raise CohortGuardError("candidate cap is outside the Phase 6C matrix")
    return f"{sqi_rule}__bis{bis_cap}s__drug{drug_cap}s"


def all_candidate_ids() -> tuple[str, ...]:
    return tuple(
        candidate_id(sqi_rule, bis_cap, drug_cap)
        for sqi_rule in SQI_RULES
        for bis_cap in BIS_STALENESS_CAPS
        for drug_cap in DRUG_HOLD_CAPS
    )


def _text_stream(path: Path):
    with path.open("rb") as probe:
        magic = probe.read(2)
    if magic == b"\x1f\x8b":
        return gzip.open(path, mode="rt", encoding="utf-8-sig", newline="")
    return path.open(mode="rt", encoding="utf-8-sig", newline="")


def parse_observation_index(
    path: Path,
    *,
    expected_track_name: str,
    anesthesia_start: float,
    anesthesia_end: float,
) -> ObservationIndex:
    """Read in original order and retain the last finite row at each timestamp.

    The sorted tuple is a read-only event-time lookup index. Raw rows are never
    rewritten, reordered, deduplicated, averaged, or otherwise transformed.
    """

    if expected_track_name not in TRACK_NAMES:
        raise CohortGuardError(f"track outside Phase 6C allowlist: {expected_track_name}")
    last_finite: dict[float, float] = {}
    occurrence_count: Counter[float] = Counter()
    original_row_count = finite_row_count = 0
    zero_intervals = negative_intervals = 0
    previous_timestamp: float | None = None
    with _text_stream(path) as stream:
        reader = csv.reader(stream)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError("raw track has no header") from exc
        if len(header) < 2 or header[0].strip() != "Time":
            raise ValueError(f"unexpected raw header: {header!r}")
        if header[1].strip() != expected_track_name:
            raise ValueError(
                f"expected {expected_track_name!r}, got {header[1].strip()!r}"
            )
        for row_number, row in enumerate(reader, start=2):
            if not row:
                continue
            if len(row) < 2:
                raise ValueError(f"row {row_number} has fewer than two columns")
            original_row_count += 1
            try:
                timestamp = float(row[0])
            except ValueError as exc:
                raise ValueError(f"invalid timestamp at row {row_number}") from exc
            if not math.isfinite(timestamp):
                raise ValueError(f"non-finite timestamp at row {row_number}")
            if previous_timestamp is not None:
                interval = timestamp - previous_timestamp
                zero_intervals += interval == 0
                negative_intervals += interval < 0
            previous_timestamp = timestamp
            if timestamp < anesthesia_start or timestamp > anesthesia_end:
                continue
            occurrence_count[timestamp] += 1
            text = row[1].strip()
            if not text:
                continue
            try:
                value = float(text)
            except ValueError as exc:
                raise ValueError(f"invalid numeric value at row {row_number}") from exc
            if math.isfinite(value):
                finite_row_count += 1
                last_finite[timestamp] = value

    timestamps = tuple(sorted(last_finite))
    return ObservationIndex(
        track_name=expected_track_name,
        timestamps=timestamps,
        values=tuple(last_finite[timestamp] for timestamp in timestamps),
        duplicated_timestamp=tuple(occurrence_count[timestamp] > 1 for timestamp in timestamps),
        original_row_count=original_row_count,
        finite_row_count=finite_row_count,
        duplicate_timestamp_count=sum(count - 1 for count in occurrence_count.values()),
        zero_interval_count=zero_intervals,
        negative_interval_count=negative_intervals,
    )


def build_grid(
    anesthesia_start: float,
    anesthesia_end: float,
    common_start: float | None,
    common_end: float | None,
) -> tuple[float, ...]:
    """Return the anesthesia-start-anchored 10-second grid in the common span."""

    if common_start is None or common_end is None or common_end < common_start:
        return ()
    lower = max(anesthesia_start, common_start)
    upper = min(anesthesia_end, common_end)
    if upper < lower:
        return ()
    first_step = math.ceil(((lower - anesthesia_start) / GRID_INTERVAL_SECONDS) - 1e-12)
    last_step = math.floor(((upper - anesthesia_start) / GRID_INTERVAL_SECONDS) + 1e-12)
    if last_step < first_step:
        return ()
    return tuple(anesthesia_start + step * GRID_INTERVAL_SECONDS for step in range(first_step, last_step + 1))


def _latest_position(timestamps: Sequence[float], grid_time: float) -> int:
    return bisect.bisect_right(timestamps, grid_time) - 1


def align_bis(
    bis_index: ObservationIndex,
    sqi_index: ObservationIndex,
    grid: Sequence[float],
    *,
    sqi_rule: str,
    staleness_cap: int,
) -> tuple[int, ...]:
    """Encode unavailable=0, usable=1, usable-from-duplicate=2."""

    threshold = {
        "sqi_not_required": None,
        "sqi_ge_20": 20.0,
        "sqi_ge_50": 50.0,
        "sqi_ge_80": 80.0,
    }.get(sqi_rule)
    if sqi_rule not in SQI_RULES or staleness_cap not in BIS_STALENESS_CAPS:
        raise CohortGuardError("invalid BIS alignment candidate")
    sqi_at = {
        timestamp: (value, duplicate)
        for timestamp, value, duplicate in zip(
            sqi_index.timestamps, sqi_index.values, sqi_index.duplicated_timestamp
        )
    }
    candidate_times: list[float] = []
    candidate_duplicates: list[bool] = []
    for timestamp, value, duplicate in zip(
        bis_index.timestamps, bis_index.values, bis_index.duplicated_timestamp
    ):
        if not 0 <= value <= 100:
            continue
        matched_duplicate = False
        if threshold is not None:
            matched = sqi_at.get(timestamp)
            if matched is None or matched[0] < threshold:
                continue
            matched_duplicate = matched[1]
        candidate_times.append(timestamp)
        candidate_duplicates.append(duplicate or matched_duplicate)
    aligned: list[int] = []
    for grid_time in grid:
        position = _latest_position(candidate_times, grid_time)
        if position < 0 or grid_time - candidate_times[position] > staleness_cap + 1e-9:
            aligned.append(0)
        else:
            aligned.append(2 if candidate_duplicates[position] else 1)
    return tuple(aligned)


def align_drug(
    index: ObservationIndex,
    grid: Sequence[float],
    *,
    hold_cap: int,
) -> tuple[tuple[int, ...], Counter[str]]:
    """Return alignment states and descriptive reasons without dose conversion.

    State 0 is unavailable, 1 is usable zero, 2 is usable positive, 3/4 are
    duplicate-derived zero/positive. The most recent finite negative observation
    makes the grid point unavailable; the implementation never falls back to an
    older nonnegative observation.
    """

    if hold_cap not in DRUG_HOLD_CAPS:
        raise CohortGuardError("invalid drug hold candidate")
    states: list[int] = []
    reasons: Counter[str] = Counter()
    for grid_time in grid:
        position = _latest_position(index.timestamps, grid_time)
        if position < 0:
            states.append(0)
            reasons["unavailable_no_prior_finite_observation"] += 1
            continue
        value = index.values[position]
        age = grid_time - index.timestamps[position]
        if value < 0:
            states.append(0)
            reasons["unavailable_latest_finite_negative"] += 1
        elif age > hold_cap + 1e-9:
            states.append(0)
            reasons["unavailable_hold_cap_exceeded"] += 1
        else:
            duplicate = index.duplicated_timestamp[position]
            states.append((4 if duplicate else 2) if value > 0 else (3 if duplicate else 1))
            reasons["usable_positive" if value > 0 else "usable_zero"] += 1
            if duplicate:
                reasons["duplicate_timestamp_observation_used"] += 1
    return tuple(states), reasons


def _rolling_all_available(states: Sequence[int], width: int = 6) -> tuple[bool, ...]:
    missing = 0
    result = [False] * len(states)
    for index, state in enumerate(states):
        missing += state == 0
        if index >= width:
            missing -= states[index - width] == 0
        if index >= width - 1:
            result[index] = missing == 0
    return tuple(result)


def _rolling_any_duplicate(
    states: Sequence[int], duplicate_states: frozenset[int], width: int = 6,
) -> tuple[bool, ...]:
    duplicates = 0
    result = [False] * len(states)
    for index, state in enumerate(states):
        duplicates += state in duplicate_states
        if index >= width:
            duplicates -= states[index - width] in duplicate_states
        if index >= width - 1:
            result[index] = duplicates > 0
    return tuple(result)


def audit_case(
    *,
    caseid: int,
    anesthesia_start: float,
    anesthesia_end: float,
    common_start: float | None,
    common_end: float | None,
    indexes: Mapping[str, ObservationIndex],
) -> tuple[list[dict[str, object]], dict[tuple[str, int], Counter[str]]]:
    """Compute 60 count-only candidate rows for one case and releaseable arrays."""

    if set(indexes) != set(TRACK_NAMES):
        raise CohortGuardError(f"case {caseid} lacks the four exact Phase 6C tracks")
    grid = build_grid(anesthesia_start, anesthesia_end, common_start, common_end)
    endpoint_indices = range(5, max(5, len(grid) - 3))
    bis_states: dict[tuple[str, int], tuple[int, ...]] = {}
    bis_history: dict[tuple[str, int], tuple[bool, ...]] = {}
    bis_duplicate: dict[tuple[str, int], tuple[bool, ...]] = {}
    for sqi_rule in SQI_RULES:
        for cap in BIS_STALENESS_CAPS:
            key = (sqi_rule, cap)
            states = align_bis(
                indexes["BIS/BIS"], indexes["BIS/SQI"], grid,
                sqi_rule=sqi_rule, staleness_cap=cap,
            )
            bis_states[key] = states
            bis_history[key] = _rolling_all_available(states)
            bis_duplicate[key] = _rolling_any_duplicate(states, frozenset({2}))

    drug_states: dict[tuple[str, int], tuple[int, ...]] = {}
    drug_history: dict[tuple[str, int], tuple[bool, ...]] = {}
    drug_duplicate: dict[tuple[str, int], tuple[bool, ...]] = {}
    rate_summaries: dict[tuple[str, int], Counter[str]] = {}
    for track_name in ("Orchestra/PPF20_RATE", "Orchestra/RFTN20_RATE"):
        for cap in DRUG_HOLD_CAPS:
            key = (track_name, cap)
            states, counts = align_drug(indexes[track_name], grid, hold_cap=cap)
            drug_states[key] = states
            drug_history[key] = _rolling_all_available(states)
            drug_duplicate[key] = _rolling_any_duplicate(states, frozenset({3, 4}))
            counts["total_grid_points"] = len(grid)
            counts["usable_grid_points"] = sum(state > 0 for state in states)
            counts["unavailable_grid_points"] = sum(state == 0 for state in states)
            rate_summaries[key] = counts

    candidate_rows: list[dict[str, object]] = []
    for sqi_rule in SQI_RULES:
        for bis_cap in BIS_STALENESS_CAPS:
            bis_key = (sqi_rule, bis_cap)
            for drug_cap in DRUG_HOLD_CAPS:
                prop_key = ("Orchestra/PPF20_RATE", drug_cap)
                remi_key = ("Orchestra/RFTN20_RATE", drug_cap)
                failures: Counter[str] = Counter()
                overlapping: Counter[str] = Counter()
                history_count = target_count = window_count = duplicate_count = 0
                for endpoint in endpoint_indices:
                    bis_ok = bis_history[bis_key][endpoint]
                    prop_ok = drug_history[prop_key][endpoint]
                    remi_ok = drug_history[remi_key][endpoint]
                    target_position = endpoint + 3
                    target_ok = bis_states[bis_key][target_position] > 0
                    history_ok = bis_ok and prop_ok and remi_ok
                    history_count += history_ok
                    target_count += target_ok
                    window_count += history_ok and target_ok
                    reasons: list[str] = []
                    if not bis_ok:
                        reasons.append("history_bis_unavailable")
                    if not prop_ok:
                        reasons.append("history_propofol_unavailable")
                    if not remi_ok:
                        reasons.append("history_remifentanil_unavailable")
                    if not target_ok:
                        reasons.append("target_bis_unavailable")
                    for reason in reasons:
                        failures[reason] += 1
                    overlapping["|".join(reasons) if reasons else "PASS"] += 1
                    if (
                        bis_duplicate[bis_key][endpoint]
                        or drug_duplicate[prop_key][endpoint]
                        or drug_duplicate[remi_key][endpoint]
                        or (target_ok and bis_states[bis_key][target_position] == 2)
                    ):
                        duplicate_count += 1
                candidate_rows.append({
                    "caseid": caseid,
                    "candidate_id": candidate_id(sqi_rule, bis_cap, drug_cap),
                    "sqi_rule": sqi_rule,
                    "bis_staleness_cap_seconds": bis_cap,
                    "drug_hold_cap_seconds": drug_cap,
                    "grid_anchor": "anesthesia_start",
                    "grid_interval_seconds": int(GRID_INTERVAL_SECONDS),
                    "total_common_span_grid_points": len(grid),
                    "total_candidate_grid_points": len(endpoint_indices),
                    "usable_history_endpoints": history_count,
                    "usable_target_points": target_count,
                    "total_usable_windows": window_count,
                    "zero_window_case": window_count == 0,
                    "failure_history_bis_unavailable": failures["history_bis_unavailable"],
                    "failure_history_propofol_unavailable": failures["history_propofol_unavailable"],
                    "failure_history_remifentanil_unavailable": failures["history_remifentanil_unavailable"],
                    "failure_target_bis_unavailable": failures["target_bis_unavailable"],
                    "overlapping_failure_reason_counts": dict(sorted(overlapping.items())),
                    "duplicate_timestamp_affected_endpoint_count": duplicate_count,
                    "any_duplicate_timestamp_affected_endpoint": duplicate_count > 0,
                    "raw_zero_interval_warning": any(i.zero_interval_count > 0 for i in indexes.values()),
                    "raw_negative_interval_warning": any(i.negative_interval_count > 0 for i in indexes.values()),
                    "future_timestamp_use_count": 0,
                    "cross_case_connection_count": 0,
                    "modeling_array_saved": False,
                    "selected": False,
                })
    if len(candidate_rows) != 60:
        raise CohortGuardError("Phase 6C case accounting did not produce 60 candidates")
    return candidate_rows, rate_summaries


def aggregate_candidates(
    rows_by_candidate: Mapping[str, Sequence[Mapping[str, object]]],
) -> list[dict[str, object]]:
    if set(rows_by_candidate) != set(all_candidate_ids()):
        raise CohortGuardError("aggregate requires all 60 candidate IDs")
    rows: list[dict[str, object]] = []
    for identifier in all_candidate_ids():
        records = rows_by_candidate[identifier]
        if len(records) != EXPECTED_CASE_COUNT:
            raise CohortGuardError(f"{identifier} does not account for 2,470 cases")
        windows = [int(record["total_usable_windows"]) for record in records]
        failures: Counter[str] = Counter()
        overlaps: Counter[str] = Counter()
        for record in records:
            for field, reason in (
                ("failure_history_bis_unavailable", "history_bis_unavailable"),
                ("failure_history_propofol_unavailable", "history_propofol_unavailable"),
                ("failure_history_remifentanil_unavailable", "history_remifentanil_unavailable"),
                ("failure_target_bis_unavailable", "target_bis_unavailable"),
            ):
                failures[reason] += int(record[field])
            overlaps.update(record["overlapping_failure_reason_counts"])
        first = records[0]
        rows.append({
            "candidate_id": identifier,
            "sqi_rule": first["sqi_rule"],
            "bis_staleness_cap_seconds": first["bis_staleness_cap_seconds"],
            "drug_hold_cap_seconds": first["drug_hold_cap_seconds"],
            "case_count": len(records),
            "total_candidate_grid_points": sum(int(r["total_candidate_grid_points"]) for r in records),
            "usable_history_endpoints": sum(int(r["usable_history_endpoints"]) for r in records),
            "usable_target_points": sum(int(r["usable_target_points"]) for r in records),
            "total_usable_windows": sum(windows),
            "usable_case_count": sum(value > 0 for value in windows),
            "zero_window_cases": sum(value == 0 for value in windows),
            "patient_window_count_distribution": distribution(windows),
            "failure_reason_counts": dict(sorted(failures.items())),
            "overlapping_failure_reason_counts": dict(sorted(overlaps.items())),
            "selected": False,
            "recommended": False,
        })
    return rows


def fixed_boundary_samples(
    case_candidate_rows: Mapping[int, Sequence[Mapping[str, object]]],
    demographics: Mapping[int, Mapping[str, object]],
    phase6b_cases: Mapping[int, Mapping[str, object]],
    *,
    seed: int = PHASE6C_SEED,
    maximum: int = 5,
) -> list[dict[str, object]]:
    categories: dict[str, list[int]] = {name: [] for name in (
        "no_usable_window_under_all_60_combinations",
        "usable_only_with_sqi_not_required",
        "usable_with_sqi_ge_20_but_not_sqi_ge_50",
        "usable_with_sqi_ge_50_but_not_sqi_ge_80",
        "usable_only_with_bis_staleness_30s",
        "usable_only_with_drug_hold_ge_300s",
        "phase6b_moderate_fail_but_at_least_120_usable_windows",
        "phase6b_strict_fail_but_at_least_120_usable_windows",
        "duplicate_timestamp_affected_grid",
        "missing_demographic_input",
        "unresolved_sex_encoding",
        "nonpositive_height_or_weight",
    )}
    for caseid, rows in case_candidate_rows.items():
        usable = [row for row in rows if int(row["total_usable_windows"]) > 0]
        by_sqi = {rule: any(row["sqi_rule"] == rule for row in usable) for rule in SQI_RULES}
        if not usable:
            categories["no_usable_window_under_all_60_combinations"].append(caseid)
        if by_sqi["sqi_not_required"] and not any(by_sqi[rule] for rule in SQI_RULES[1:]):
            categories["usable_only_with_sqi_not_required"].append(caseid)
        if by_sqi["sqi_ge_20"] and not by_sqi["sqi_ge_50"] and not by_sqi["sqi_ge_80"]:
            categories["usable_with_sqi_ge_20_but_not_sqi_ge_50"].append(caseid)
        if by_sqi["sqi_ge_50"] and not by_sqi["sqi_ge_80"]:
            categories["usable_with_sqi_ge_50_but_not_sqi_ge_80"].append(caseid)
        if usable and all(int(row["bis_staleness_cap_seconds"]) == 30 for row in usable):
            categories["usable_only_with_bis_staleness_30s"].append(caseid)
        if usable and all(int(row["drug_hold_cap_seconds"]) >= 300 for row in usable):
            categories["usable_only_with_drug_hold_ge_300s"].append(caseid)
        maximum_windows = max((int(row["total_usable_windows"]) for row in rows), default=0)
        source = phase6b_cases[caseid]
        if source["scenario_moderate_passes"] == "false" and maximum_windows >= 120:
            categories["phase6b_moderate_fail_but_at_least_120_usable_windows"].append(caseid)
        if source["scenario_strict_passes"] == "false" and maximum_windows >= 120:
            categories["phase6b_strict_fail_but_at_least_120_usable_windows"].append(caseid)
        if any(str(row["any_duplicate_timestamp_affected_endpoint"]).lower() == "true" or row["any_duplicate_timestamp_affected_endpoint"] is True for row in rows):
            categories["duplicate_timestamp_affected_grid"].append(caseid)
        demo = demographics[caseid]
        if not bool(demo["all_four_demographics_present"]):
            categories["missing_demographic_input"].append(caseid)
        if not bool(demo["sex_encoding_resolvable"]):
            categories["unresolved_sex_encoding"].append(caseid)
        if not bool(demo["height_positive"]) or not bool(demo["weight_positive"]):
            categories["nonpositive_height_or_weight"].append(caseid)
    rng = random.Random(seed)
    result: list[dict[str, object]] = []
    for category in sorted(categories):
        members = sorted(set(categories[category]))
        selected = sorted(rng.sample(members, min(maximum, len(members))))
        for caseid in selected:
            result.append({
                "category": category,
                "caseid": caseid,
                "category_case_count": len(members),
                "seed": seed,
                "automatic_inclusion_or_exclusion": False,
            })
    return result
