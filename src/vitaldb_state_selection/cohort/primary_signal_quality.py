"""Outcome-blind, bounded-memory Phase 6B primary-signal characterization."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import random
import statistics
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from .guards import CohortGuardError, normalize_caseid


EXPECTED_CASE_COUNT = 2470
EXPECTED_TRACK_ROW_COUNT = 9880
PHASE6B_SEED = 20260720
TRACK_NAMES = (
    "BIS/BIS",
    "BIS/SQI",
    "Orchestra/PPF20_RATE",
    "Orchestra/RFTN20_RATE",
)
PRIMARY_SIGNAL_NAMES = (
    "BIS/BIS",
    "Orchestra/PPF20_RATE",
    "Orchestra/RFTN20_RATE",
)
DRUG_TRACK_NAMES = (
    "Orchestra/PPF20_RATE",
    "Orchestra/RFTN20_RATE",
)
FIXED_RUN_BOUNDARIES = (30.0, 60.0, 120.0, 300.0)
GAP_THRESHOLDS = (10.0, 30.0, 60.0, 120.0, 300.0, 600.0)
QUANTILES = (
    ("q01", 0.01), ("q05", 0.05), ("q25", 0.25), ("median", 0.50),
    ("q75", 0.75), ("q95", 0.95), ("q99", 0.99),
)


class QualityParseError(ValueError):
    """A source row cannot be parsed without modifying the raw artifact."""


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def nearest_rank(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return float(ordered[max(1, math.ceil(probability * len(ordered))) - 1])


def distribution(values: Sequence[float | int | None]) -> dict[str, object]:
    numeric = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    result: dict[str, object] = {
        "available_count": len(numeric), "missing_count": len(values) - len(numeric),
        "minimum": min(numeric) if numeric else None,
    }
    for label, probability in QUANTILES:
        result[label] = nearest_rank(numeric, probability)
    result["maximum"] = max(numeric) if numeric else None
    result["method"] = "nearest_rank_observed_values"
    return result


def _text_stream(path: Path):
    with path.open("rb") as probe:
        magic = probe.read(2)
    if magic == b"\x1f\x8b":
        return gzip.open(path, mode="rt", encoding="utf-8-sig", newline="")
    return path.open(mode="rt", encoding="utf-8-sig", newline="")


def _run_metrics(
    observations: Sequence[tuple[float, float | None]],
    predicate: Callable[[float], bool],
    boundary_seconds: float | None,
) -> dict[str, object]:
    run_count = 0
    longest = 0.0
    total = 0.0
    current = 0.0
    previous_timestamp: float | None = None
    previous_matches = False
    for timestamp, value in observations:
        matches = value is not None and predicate(value)
        contiguous = False
        interval = None
        if previous_timestamp is not None:
            interval = timestamp - previous_timestamp
            contiguous = (
                boundary_seconds is not None
                and interval > 0
                and interval <= boundary_seconds
            )
        if matches and previous_matches and contiguous and interval is not None:
            current += interval
            total += interval
            longest = max(longest, current)
        elif matches:
            run_count += 1
            current = 0.0
        else:
            current = 0.0
        previous_timestamp = timestamp
        previous_matches = matches
    return {"run_count": run_count, "longest_seconds": longest, "total_seconds": total}


def characterize_track(
    path: Path, *, expected_track_name: str, anesthesia_start: float, anesthesia_end: float,
    retain_finite_timestamps: bool = False,
) -> dict[str, object]:
    if expected_track_name not in TRACK_NAMES:
        raise CohortGuardError(f"track outside Phase 6B allowlist: {expected_track_name}")
    if anesthesia_end <= anesthesia_start:
        raise CohortGuardError("Phase 6B received an invalid anesthesia window")

    total_rows = finite_count = nonfinite_count = missing_count = 0
    rows_before = rows_inside = rows_after = 0
    first_timestamp: float | None = None
    last_timestamp: float | None = None
    inside_first: float | None = None
    inside_last: float | None = None
    all_timestamps: list[float] = []
    window_observations: list[tuple[float, float | None]] = []
    window_values: list[float] = []
    window_finite_timestamps: set[float] = set()
    window_range_timestamps: dict[str, list[float]] = {
        "finite": [], "range_0_100": [], "range_10_100": []
    }
    value_change_count = 0
    previous_window_value: float | None = None
    previous_window_was_finite = False
    longest_constant_samples = 0
    current_constant_samples = 0
    current_constant_value: float | None = None

    with _text_stream(path) as stream:
        reader = csv.reader(stream)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise QualityParseError("raw track has no header") from exc
        if len(header) < 2 or header[0].strip() != "Time":
            raise QualityParseError(f"unexpected header: {header!r}")
        if header[1].strip() != expected_track_name:
            raise QualityParseError(
                f"expected {expected_track_name!r}, got {header[1].strip()!r}"
            )
        for row_number, row in enumerate(reader, start=2):
            if not row:
                continue
            if len(row) < 2:
                raise QualityParseError(f"row {row_number} has fewer than two columns")
            total_rows += 1
            try:
                timestamp = float(row[0])
            except ValueError as exc:
                raise QualityParseError(f"invalid timestamp at row {row_number}") from exc
            if not math.isfinite(timestamp):
                raise QualityParseError(f"non-finite timestamp at row {row_number}")
            if first_timestamp is None:
                first_timestamp = timestamp
            last_timestamp = timestamp
            all_timestamps.append(timestamp)

            raw_value = row[1].strip()
            value: float | None = None
            if raw_value == "":
                missing_count += 1
            else:
                try:
                    parsed = float(raw_value)
                except ValueError as exc:
                    raise QualityParseError(f"invalid numeric value at row {row_number}") from exc
                if math.isfinite(parsed):
                    value = parsed
                    finite_count += 1
                else:
                    nonfinite_count += 1

            if timestamp < anesthesia_start:
                rows_before += 1
                continue
            if timestamp > anesthesia_end:
                rows_after += 1
                continue
            rows_inside += 1
            if inside_first is None:
                inside_first = timestamp
            inside_last = timestamp
            window_observations.append((timestamp, value))
            if value is None:
                previous_window_was_finite = False
                current_constant_samples = 0
                current_constant_value = None
                continue
            window_values.append(value)
            window_finite_timestamps.add(timestamp)
            window_range_timestamps["finite"].append(timestamp)
            if 0 <= value <= 100:
                window_range_timestamps["range_0_100"].append(timestamp)
            if 10 <= value <= 100:
                window_range_timestamps["range_10_100"].append(timestamp)
            if previous_window_was_finite and value != previous_window_value:
                value_change_count += 1
            if current_constant_value is not None and value == current_constant_value:
                current_constant_samples += 1
            else:
                current_constant_value = value
                current_constant_samples = 1
            longest_constant_samples = max(longest_constant_samples, current_constant_samples)
            previous_window_value = value
            previous_window_was_finite = True

    def interval_fields(timestamps: Sequence[float], prefix: str) -> dict[str, object]:
        duplicates = len(timestamps) - len(set(timestamps))
        intervals = [current - previous for previous, current in zip(timestamps, timestamps[1:])]
        positive = [value for value in intervals if value > 0]
        fields: dict[str, object] = {
            f"{prefix}duplicate_timestamp_count": duplicates,
            f"{prefix}zero_interval_count": sum(value == 0 for value in intervals),
            f"{prefix}negative_interval_count": sum(value < 0 for value in intervals),
            f"{prefix}strictly_positive_interval_count": len(positive),
            f"{prefix}positive_interval_minimum": min(positive) if positive else None,
            f"{prefix}positive_interval_q05": nearest_rank(positive, 0.05),
            f"{prefix}positive_interval_q25": nearest_rank(positive, 0.25),
            f"{prefix}positive_interval_median": statistics.median(positive) if positive else None,
            f"{prefix}positive_interval_q75": nearest_rank(positive, 0.75),
            f"{prefix}positive_interval_q95": nearest_rank(positive, 0.95),
            f"{prefix}positive_interval_maximum": max(positive) if positive else None,
            f"{prefix}longest_strictly_positive_gap": max(positive) if positive else None,
        }
        for threshold in GAP_THRESHOLDS:
            fields[f"{prefix}gap_gt_{int(threshold)}s_count"] = sum(value > threshold for value in positive)
        return fields

    anesthesia_duration = anesthesia_end - anesthesia_start
    observed_span = (
        max(0.0, inside_last - inside_first)
        if inside_first is not None and inside_last is not None else None
    )
    result: dict[str, object] = {
        "parsing_status": "complete", "total_row_count": total_rows,
        "finite_value_count": finite_count, "nonfinite_value_count": nonfinite_count,
        "missing_value_count": missing_count, "empty_status": total_rows == 0,
        "original_first_timestamp": first_timestamp, "original_last_timestamp": last_timestamp,
        "anesthesia_start": anesthesia_start, "anesthesia_end": anesthesia_end,
        "anesthesia_duration_seconds": anesthesia_duration,
        "rows_before_anesthesia_window": rows_before,
        "rows_inside_anesthesia_window": rows_inside,
        "rows_after_anesthesia_window": rows_after,
        "first_timestamp_inside_window": inside_first,
        "last_timestamp_inside_window": inside_last,
        "observed_span_inside_window_seconds": observed_span,
        "observed_span_to_anesthesia_duration_ratio": (
            observed_span / anesthesia_duration if observed_span is not None else None
        ),
        "window_finite_count": len(window_values),
        "window_minimum": min(window_values) if window_values else None,
        "window_maximum": max(window_values) if window_values else None,
        "window_unique_value_count": len(set(window_values)),
        "window_value_change_count": value_change_count,
        "window_longest_constant_value_run_samples": longest_constant_samples,
        "processing_resampling": False, "processing_interpolation": False,
        "processing_smoothing": False, "processing_clipping": False,
        "processing_forward_fill": False, "processing_backward_fill": False,
        "processing_timestamp_sorting": False, "processing_duplicate_deletion": False,
    }
    for label, probability in QUANTILES:
        result[f"window_{label}"] = nearest_rank(window_values, probability)
    result.update(interval_fields(all_timestamps, "raw_"))
    result.update(interval_fields([timestamp for timestamp, _ in window_observations], "window_"))

    if expected_track_name == "BIS/BIS":
        finite = len(window_values)
        result.update({
            "bis_equal_zero_count": sum(value == 0 for value in window_values),
            "bis_negative_count": sum(value < 0 for value in window_values),
            "bis_0_lt_10_count": sum(0 <= value < 10 for value in window_values),
            "bis_10_100_count": sum(10 <= value <= 100 for value in window_values),
            "bis_gt_100_count": sum(value > 100 for value in window_values),
            "bis_0_100_count": sum(0 <= value <= 100 for value in window_values),
            "bis_0_100_fraction_of_finite": (
                sum(0 <= value <= 100 for value in window_values) / finite if finite else None
            ),
            "bis_10_100_fraction_of_finite": (
                sum(10 <= value <= 100 for value in window_values) / finite if finite else None
            ),
        })
        for name, timestamps in window_range_timestamps.items():
            result[f"bis_{name}_first_timestamp"] = timestamps[0] if timestamps else None
            result[f"bis_{name}_last_timestamp"] = timestamps[-1] if timestamps else None

    if expected_track_name == "BIS/SQI":
        finite = len(window_values)
        result.update({
            "sqi_negative_count": sum(value < 0 for value in window_values),
            "sqi_gt_100_count": sum(value > 100 for value in window_values),
        })
        for threshold in (20, 50, 80):
            count = sum(value >= threshold for value in window_values)
            result[f"sqi_ge_{threshold}_count"] = count
            result[f"sqi_ge_{threshold}_fraction_of_finite"] = count / finite if finite else None

    if expected_track_name in DRUG_TRACK_NAMES:
        finite = len(window_values)
        positive_count = sum(value > 0 for value in window_values)
        zero_count = sum(value == 0 for value in window_values)
        negative_count = sum(value < 0 for value in window_values)
        finite_observations = [(timestamp, value) for timestamp, value in window_observations if value is not None]
        positive_timestamps = [timestamp for timestamp, value in finite_observations if value > 0]
        finite_timestamps = [timestamp for timestamp, _ in finite_observations]
        positive_intervals = [
            current[0] - previous[0]
            for previous, current in zip(window_observations, window_observations[1:])
            if current[0] - previous[0] > 0
        ]
        median_interval = statistics.median(positive_intervals) if positive_intervals else None
        phase5d_boundary = median_interval * 3.0 if median_interval is not None else None
        result.update({
            "drug_negative_count": negative_count, "drug_zero_count": zero_count,
            "drug_positive_count": positive_count,
            "drug_positive_fraction_of_finite": positive_count / finite if finite else None,
            "drug_first_finite_timestamp": finite_timestamps[0] if finite_timestamps else None,
            "drug_last_finite_timestamp": finite_timestamps[-1] if finite_timestamps else None,
            "drug_first_positive_timestamp": positive_timestamps[0] if positive_timestamps else None,
            "drug_last_positive_timestamp": positive_timestamps[-1] if positive_timestamps else None,
            "drug_phase5d_median_positive_interval_seconds": median_interval,
            "drug_phase5d_gap_boundary_seconds": phase5d_boundary,
        })
        for label, boundary in (("phase5d_3x_median", phase5d_boundary),) + tuple(
            (f"fixed_{int(value)}s", value) for value in FIXED_RUN_BOUNDARIES
        ):
            positive = _run_metrics(window_observations, lambda value: value > 0, boundary)
            zero = _run_metrics(window_observations, lambda value: value == 0, boundary)
            for key, value in positive.items():
                result[f"drug_positive_{label}_{key}"] = value
            for key, value in zero.items():
                result[f"drug_zero_{label}_{key}"] = value

    if retain_finite_timestamps:
        result["_window_finite_timestamps"] = window_finite_timestamps
    return result


def build_case_record(
    caseid: int, anesthesia_start: float, anesthesia_end: float,
    track_rows: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    if set(track_rows) != set(TRACK_NAMES):
        raise CohortGuardError(f"case {caseid} does not have exactly four quality rows")
    bis = track_rows["BIS/BIS"]
    sqi = track_rows["BIS/SQI"]
    prop = track_rows["Orchestra/PPF20_RATE"]
    remi = track_rows["Orchestra/RFTN20_RATE"]
    primary = [bis, prop, remi]
    firsts = [row.get("first_timestamp_inside_window") for row in primary]
    lasts = [row.get("last_timestamp_inside_window") for row in primary]
    if all(value is not None for value in firsts + lasts):
        common_start = max(float(value) for value in firsts)
        common_end = min(float(value) for value in lasts)
        common_duration = max(0.0, common_end - common_start)
        limiting = sorted(
            name for name, row in zip(PRIMARY_SIGNAL_NAMES, primary)
            if row.get("first_timestamp_inside_window") == common_start
            or row.get("last_timestamp_inside_window") == common_end
        )
    else:
        common_start = common_end = None
        common_duration = None
        limiting = [
            name for name, row in zip(PRIMARY_SIGNAL_NAMES, primary)
            if row.get("first_timestamp_inside_window") is None
            or row.get("last_timestamp_inside_window") is None
        ]
    anesthesia_duration = anesthesia_end - anesthesia_start
    bis_times = set(bis.get("_window_finite_timestamps", set()))
    sqi_times = set(sqi.get("_window_finite_timestamps", set()))
    overlap = len(bis_times & sqi_times)
    bis_count = int(bis["window_finite_count"])
    sqi_count = int(sqi["window_finite_count"])
    record: dict[str, object] = {
        "caseid": caseid, "anesthesia_start": anesthesia_start,
        "anesthesia_end": anesthesia_end, "anesthesia_duration_seconds": anesthesia_duration,
        "common_observed_span_start": common_start,
        "common_observed_span_end": common_end,
        "common_observed_span_duration_seconds": common_duration,
        "common_observed_span_to_anesthesia_duration_ratio": (
            common_duration / anesthesia_duration if common_duration is not None else None
        ),
        "common_observed_span_limiting_primary_tracks": limiting,
        "common_span_is_continuous_coverage": False,
        "bis_window_finite_count": bis_count,
        "bis_0_100_fraction_of_finite": bis.get("bis_0_100_fraction_of_finite"),
        "bis_10_100_fraction_of_finite": bis.get("bis_10_100_fraction_of_finite"),
        "sqi_window_finite_count": sqi_count,
        "sqi_ge_20_fraction_of_finite": sqi.get("sqi_ge_20_fraction_of_finite"),
        "sqi_ge_50_fraction_of_finite": sqi.get("sqi_ge_50_fraction_of_finite"),
        "sqi_ge_80_fraction_of_finite": sqi.get("sqi_ge_80_fraction_of_finite"),
        "bis_sqi_exact_timestamp_overlap_count": overlap,
        "bis_sqi_overlap_fraction_of_bis_finite_unique_timestamps": (
            overlap / len(bis_times) if bis_times else None
        ),
        "bis_sqi_overlap_fraction_of_sqi_finite_unique_timestamps": (
            overlap / len(sqi_times) if sqi_times else None
        ),
        "propofol_finite_record_present": int(prop["window_finite_count"]) > 0,
        "propofol_positive_record_count": int(prop.get("drug_positive_count", 0)),
        "propofol_positive_record_present": int(prop.get("drug_positive_count", 0)) > 0,
        "remifentanil_finite_record_present": int(remi["window_finite_count"]) > 0,
        "remifentanil_positive_record_count": int(remi.get("drug_positive_count", 0)),
        "remifentanil_positive_record_present": int(remi.get("drug_positive_count", 0)) > 0,
        "negative_drug_rate_present": (
            int(prop.get("drug_negative_count", 0)) > 0 or int(remi.get("drug_negative_count", 0)) > 0
        ),
        "any_duplicate_timestamp": any(int(row["raw_duplicate_timestamp_count"]) > 0 for row in track_rows.values()),
        "any_negative_timestamp_interval": any(int(row["raw_negative_interval_count"]) > 0 for row in track_rows.values()),
        "quality_threshold_selected": False, "final_eligibility": "pending_human_review",
        "cohort_frozen": False, "split_assigned": False,
    }
    record["both_drugs_positive_record_present"] = (
        record["propofol_positive_record_present"] and record["remifentanil_positive_record_present"]
    )
    record["propofol_only_positive"] = (
        record["propofol_positive_record_present"] and not record["remifentanil_positive_record_present"]
    )
    record["remifentanil_only_positive"] = (
        record["remifentanil_positive_record_present"] and not record["propofol_positive_record_present"]
    )
    record["both_drugs_zero_or_nonpositive"] = not (
        record["propofol_positive_record_present"] or record["remifentanil_positive_record_present"]
    )
    return record


def scenario_results(record: Mapping[str, object]) -> dict[str, dict[str, object]]:
    def ge(value: object, threshold: float) -> bool:
        return value is not None and float(value) >= threshold

    definitions = {
        "permissive": (
            ("anesthesia_duration_lt_20m", ge(record["anesthesia_duration_seconds"], 20 * 60)),
            ("common_span_lt_10m", ge(record["common_observed_span_duration_seconds"], 10 * 60)),
            ("bis_0_100_fraction_lt_80pct", ge(record["bis_0_100_fraction_of_finite"], 0.80)),
            ("propofol_positive_count_lt_1", int(record["propofol_positive_record_count"]) >= 1),
            ("remifentanil_positive_count_lt_1", int(record["remifentanil_positive_record_count"]) >= 1),
            ("negative_drug_rate_present", not bool(record["negative_drug_rate_present"])),
        ),
        "moderate": (
            ("anesthesia_duration_lt_30m", ge(record["anesthesia_duration_seconds"], 30 * 60)),
            ("common_span_lt_20m", ge(record["common_observed_span_duration_seconds"], 20 * 60)),
            ("bis_10_100_fraction_lt_80pct", ge(record["bis_10_100_fraction_of_finite"], 0.80)),
            ("sqi_ge_50_fraction_lt_50pct", ge(record["sqi_ge_50_fraction_of_finite"], 0.50)),
            ("propofol_positive_count_lt_3", int(record["propofol_positive_record_count"]) >= 3),
            ("remifentanil_positive_count_lt_3", int(record["remifentanil_positive_record_count"]) >= 3),
            ("negative_drug_rate_present", not bool(record["negative_drug_rate_present"])),
        ),
        "strict": (
            ("anesthesia_duration_lt_60m", ge(record["anesthesia_duration_seconds"], 60 * 60)),
            ("common_span_lt_30m", ge(record["common_observed_span_duration_seconds"], 30 * 60)),
            ("bis_10_100_fraction_lt_90pct", ge(record["bis_10_100_fraction_of_finite"], 0.90)),
            ("sqi_ge_50_fraction_lt_80pct", ge(record["sqi_ge_50_fraction_of_finite"], 0.80)),
            ("propofol_positive_count_lt_3", int(record["propofol_positive_record_count"]) >= 3),
            ("remifentanil_positive_count_lt_3", int(record["remifentanil_positive_record_count"]) >= 3),
            ("negative_drug_rate_present", not bool(record["negative_drug_rate_present"])),
        ),
    }
    return {
        name: {
            "passes": all(passed for _, passed in criteria),
            "failure_reasons": [reason for reason, passed in criteria if not passed],
        }
        for name, criteria in definitions.items()
    }


def fixed_boundary_samples(
    case_records: Sequence[Mapping[str, object]],
    track_rows_by_case: Mapping[int, Mapping[str, Mapping[str, object]]],
    *, seed: int = PHASE6B_SEED, maximum: int = 5,
) -> list[dict[str, object]]:
    categories: dict[str, list[int]] = {name: [] for name in (
        "bis_no_finite", "bis_10_100_fraction_70_80pct", "bis_10_100_fraction_80_90pct",
        "sqi_ge_50_fraction_40_50pct", "propofol_no_positive", "remifentanil_no_positive",
        "negative_drug_rate", "common_span_10_20m", "common_span_20_30m",
        "longest_gap_30_60s", "longest_gap_60_120s",
        "duplicate_or_negative_timestamp_interval",
    )}
    for record in case_records:
        caseid = int(record["caseid"])
        bis_fraction = record.get("bis_10_100_fraction_of_finite")
        sqi_fraction = record.get("sqi_ge_50_fraction_of_finite")
        common = record.get("common_observed_span_duration_seconds")
        tracks = track_rows_by_case[caseid]
        primary_gaps = [tracks[name].get("window_longest_strictly_positive_gap") for name in PRIMARY_SIGNAL_NAMES]
        numeric_gaps = [float(value) for value in primary_gaps if value is not None]
        longest_gap = max(numeric_gaps) if numeric_gaps else None
        if int(record["bis_window_finite_count"]) == 0: categories["bis_no_finite"].append(caseid)
        if bis_fraction is not None and 0.70 <= float(bis_fraction) < 0.80: categories["bis_10_100_fraction_70_80pct"].append(caseid)
        if bis_fraction is not None and 0.80 <= float(bis_fraction) < 0.90: categories["bis_10_100_fraction_80_90pct"].append(caseid)
        if sqi_fraction is not None and 0.40 <= float(sqi_fraction) < 0.50: categories["sqi_ge_50_fraction_40_50pct"].append(caseid)
        if not record["propofol_positive_record_present"]: categories["propofol_no_positive"].append(caseid)
        if not record["remifentanil_positive_record_present"]: categories["remifentanil_no_positive"].append(caseid)
        if record["negative_drug_rate_present"]: categories["negative_drug_rate"].append(caseid)
        if common is not None and 10 * 60 <= float(common) < 20 * 60: categories["common_span_10_20m"].append(caseid)
        if common is not None and 20 * 60 <= float(common) < 30 * 60: categories["common_span_20_30m"].append(caseid)
        if longest_gap is not None and 30 < longest_gap <= 60: categories["longest_gap_30_60s"].append(caseid)
        if longest_gap is not None and 60 < longest_gap <= 120: categories["longest_gap_60_120s"].append(caseid)
        if record["any_duplicate_timestamp"] or record["any_negative_timestamp_interval"]:
            categories["duplicate_or_negative_timestamp_interval"].append(caseid)
    rng = random.Random(seed)
    rows: list[dict[str, object]] = []
    for category in sorted(categories):
        members = sorted(set(categories[category]))
        selected = sorted(rng.sample(members, min(maximum, len(members))))
        for caseid in selected:
            rows.append({"category": category, "caseid": caseid, "category_case_count": len(members),
                         "seed": seed, "automatic_inclusion_or_exclusion": False})
    return rows


def marginal_sensitivity(
    case_records: Sequence[Mapping[str, object]],
    track_rows_by_case: Mapping[int, Mapping[str, Mapping[str, object]]],
) -> list[dict[str, object]]:
    if len(case_records) != EXPECTED_CASE_COUNT:
        raise CohortGuardError("marginal sensitivity requires exactly 2,470 cases")
    rows: list[dict[str, object]] = []

    def add(category: str, metric: str, threshold: str, values: Sequence[bool | None], note: str) -> None:
        passed = sum(value is True for value in values)
        missing = sum(value is None for value in values)
        rows.append({
            "category": category, "metric": metric, "threshold": threshold,
            "pass_count": passed, "fail_count": len(values) - passed,
            "missing_measure_count": missing, "total_case_count": len(values),
            "pass_fraction": passed / len(values), "selected_for_protocol": False,
            "notes": note,
        })

    for minutes in (10, 20, 30, 60, 120):
        add("anesthesia_window_duration", "anesthesia_duration_seconds", f">={minutes}min",
            [float(record["anesthesia_duration_seconds"]) >= minutes * 60 for record in case_records],
            "metadata window duration only")
    for minutes in (10, 20, 30, 60):
        add("common_observed_span_duration", "common_observed_span_duration_seconds", f">={minutes}min",
            [None if record["common_observed_span_duration_seconds"] is None else
             float(record["common_observed_span_duration_seconds"]) >= minutes * 60 for record in case_records],
            "overlap of primary-track first/last finite timestamp ranges; not continuous coverage")
    for threshold in (0.50, 0.70, 0.80, 0.90, 0.95):
        add("common_observed_span_ratio", "common_observed_span_to_anesthesia_duration_ratio", f">={threshold:.0%}",
            [None if record["common_observed_span_to_anesthesia_duration_ratio"] is None else
             float(record["common_observed_span_to_anesthesia_duration_ratio"]) >= threshold for record in case_records],
            "descriptive span ratio; not a finalized coverage definition")
    for metric in ("bis_0_100_fraction_of_finite", "bis_10_100_fraction_of_finite"):
        for threshold in (0.50, 0.70, 0.80, 0.90, 0.95):
            add("bis_descriptive_range_fraction", metric, f">={threshold:.0%}",
                [None if record[metric] is None else float(record[metric]) >= threshold for record in case_records],
                "denominator is finite BIS observations inside anesthesia window; no finite observations fail and are counted missing")
    for metric in ("sqi_ge_20_fraction_of_finite", "sqi_ge_50_fraction_of_finite", "sqi_ge_80_fraction_of_finite"):
        for threshold in (0.50, 0.70, 0.80, 0.90, 0.95):
            add("sqi_descriptive_fraction", metric, f">={threshold:.0%}",
                [None if record[metric] is None else float(record[metric]) >= threshold for record in case_records],
                "denominator is finite SQI observations inside anesthesia window; SQI remains QC-only")
    for track_name in PRIMARY_SIGNAL_NAMES:
        for seconds in (30, 60, 120, 300, 600):
            values: list[bool | None] = []
            for record in case_records:
                gap = track_rows_by_case[int(record["caseid"])][track_name].get(
                    "window_longest_strictly_positive_gap"
                )
                values.append(None if gap is None else float(gap) <= seconds)
            add("timestamp_gap", f"{track_name} longest strictly positive gap", f"<={seconds}s", values,
                "irregular or event-style cadence may not equal missingness")
    for drug, prefix in (("propofol", "propofol"), ("remifentanil", "remifentanil")):
        for count in (1, 3):
            add("drug_evidence", f"{drug}_positive_record_count", f">={count}",
                [int(record[f"{prefix}_positive_record_count"]) >= count for record in case_records],
                "positive recorded samples only; not dose or exposure reconstruction")
    for count in (1, 3):
        add("drug_evidence", "both_drugs_positive_record_count", f"each>={count}",
            [int(record["propofol_positive_record_count"]) >= count and
             int(record["remifentanil_positive_record_count"]) >= count for record in case_records],
            "both exact rate tracks independently meet recorded-positive count")
    return rows


def scenario_tables(
    case_records: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    scenarios = ("permissive", "moderate", "strict")
    by_case: dict[int, dict[str, dict[str, object]]] = {}
    for record in case_records:
        results = scenario_results(record)
        by_case[int(record["caseid"])] = results
        if isinstance(record, dict):
            for name in scenarios:
                record[f"scenario_{name}_passes"] = results[name]["passes"]
                record[f"scenario_{name}_failure_reasons"] = results[name]["failure_reasons"]
    summary_rows: list[dict[str, object]] = []
    for name in scenarios:
        results = [by_case[int(record["caseid"])][name] for record in case_records]
        reason_counts = Counter(
            reason for result in results for reason in result["failure_reasons"]
        )
        combination_counts = Counter(
            "|".join(result["failure_reasons"]) if result["failure_reasons"] else "PASS"
            for result in results
        )
        passed = sum(bool(result["passes"]) for result in results)
        summary_rows.append({
            "scenario": name, "pass_count": passed,
            "fail_count": len(results) - passed, "total_case_count": len(results),
            "pass_fraction": passed / len(results),
            "individual_failure_reason_counts": dict(sorted(reason_counts.items())),
            "overlapping_failure_reason_combination_counts": dict(sorted(combination_counts.items())),
            "recommended": False, "selected": False,
        })
    disagreement: list[dict[str, object]] = []
    for left in scenarios:
        for right in scenarios:
            count = sum(
                bool(by_case[int(record["caseid"])][left]["passes"])
                != bool(by_case[int(record["caseid"])][right]["passes"])
                for record in case_records
            )
            disagreement.append({
                "scenario_left": left, "scenario_right": right,
                "disagreement_count": count,
                "disagreement_fraction": count / len(case_records),
            })
    return summary_rows, disagreement
