"""Deterministic, outcome-blind subject allocation for Phase 8A.

This module accepts only the versioned Phase 7A clinical-metadata fields listed
in ``SOURCE_COLUMNS_USED``.  It has no network, raw-signal, PK/PD, environment,
or reinforcement-learning dependency.
"""

from __future__ import annotations

import hashlib
import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from fractions import Fraction


STARTING_COMMIT = "22448d447d7e07941a3dc2139cb2eae0d76bd511"
SOURCE_COHORT_PROTOCOL_VERSION = "1.2"
STUDY_PROTOCOL_VERSION = "1.3.2"
SPLIT_MANIFEST_VERSION = "phase8a-v1"
SPLIT_SEED = 20260720
ALLOCATION_METHOD = "hamilton_stratified_sha256_rank_v1"
EXPECTED_CASE_COUNT = 2460
EXPECTED_SUBJECT_COUNT = 2415
TRAIN_SUBJECT_TARGET = 1932
TEST_SUBJECT_TARGET = 483
TEST_FRACTION = Fraction(1, 5)
SOURCE_FINAL_COHORT_SHA256 = (
    "517683c574b642584ecaf6e0c7c8a2c1ec461e4eb2252277f0427c4c55065468"
)
SOURCE_SUBJECT_LINKAGE_FILE_SHA256 = (
    "cd42aa0caa9dd5151585e779af07110f4025688fbae00a81a29db527cf1ba2ad"
)

SOURCE_COLUMNS_USED = frozenset(
    {
        "caseid",
        "subjectid",
        "subject_case_count",
        "sex_group",
        "age",
        "height_cm",
        "weight_kg",
        "age_group",
        "bmi_group",
        "asa_group",
        "emergency_group",
        "operation_type_group",
    }
)
ALLOCATION_COLUMNS = frozenset(
    {
        "caseid",
        "subjectid",
        "subject_case_count",
        "sex_group",
        "age",
        "height_cm",
        "weight_kg",
    }
)
SECONDARY_REPORTING_COLUMNS = frozenset(
    {
        "age_group",
        "bmi_group",
        "asa_group",
        "emergency_group",
        "operation_type_group",
    }
)

SEX_ORDER = ("male", "female")
AGE_GROUP_ORDER = ("18_to_lt_40", "40_to_lt_60", "60_to_lt_75", "ge_75")
CASE_COUNT_BAND_ORDER = ("one_case", "two_cases", "three_or_more_cases")
SPLIT_ORDER = {"train": 0, "test": 1}
QUANTILE_METHOD = "linear_interpolation_position_n_minus_1"


class SubjectSplitError(RuntimeError):
    """Raised when a Phase 8A scientific or integrity invariant fails."""


def _exact_identifier(value: object, field: str) -> tuple[str, int]:
    text = "" if value is None else str(value).strip()
    if not text or not text.isdecimal():
        raise SubjectSplitError(f"{field} must be a nonempty decimal integer string")
    numeric = int(text)
    if numeric < 0:
        raise SubjectSplitError(f"{field} must be nonnegative")
    return text, numeric


def _finite_positive(value: object, field: str, *, minimum: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise SubjectSplitError(f"{field} must be numeric") from error
    if not math.isfinite(number) or number <= minimum:
        raise SubjectSplitError(f"{field} must be finite and greater than {minimum}")
    return number


def subject_age_group(age: float) -> str:
    if not math.isfinite(age) or age < 18:
        raise SubjectSplitError("subject age must be finite and at least 18")
    if age < 40:
        return "18_to_lt_40"
    if age < 60:
        return "40_to_lt_60"
    if age < 75:
        return "60_to_lt_75"
    return "ge_75"


def subject_case_count_band(case_count: int) -> str:
    if case_count == 1:
        return "one_case"
    if case_count == 2:
        return "two_cases"
    if case_count >= 3:
        return "three_or_more_cases"
    raise SubjectSplitError("subject case count must be positive")


def canonical_strata() -> tuple[str, ...]:
    return tuple(
        f"{sex}|{age}|{band}"
        for sex in SEX_ORDER
        for age in AGE_GROUP_ORDER
        for band in CASE_COUNT_BAND_ORDER
    )


def allocation_rank_sha256(subjectid: str, stratum_key: str) -> str:
    exact, _ = _exact_identifier(subjectid, "subjectid")
    if stratum_key not in canonical_strata():
        raise SubjectSplitError(f"unknown stratum key: {stratum_key}")
    payload = f"{SPLIT_SEED}\0{stratum_key}\0{exact}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def empirical_quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered or not all(math.isfinite(value) for value in ordered):
        raise SubjectSplitError("quantile input must be nonempty and finite")
    if not 0 <= probability <= 1:
        raise SubjectSplitError("quantile probability must be in [0, 1]")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] + weight * (ordered[upper] - ordered[lower])


def _range_fields(values: Sequence[float], prefix: str, suffix: str = "") -> dict[str, float]:
    low, high = min(values), max(values)
    return {
        f"{prefix}_minimum{suffix}": low,
        f"{prefix}_maximum{suffix}": high,
        f"{prefix}_range{suffix}": high - low,
    }


def build_subject_rows(
    case_rows: Sequence[Mapping[str, object]],
    *,
    enforce_production_counts: bool = True,
) -> list[dict[str, object]]:
    """Collapse allowed Phase 7A case metadata to the pinned subject table."""

    if not case_rows:
        raise SubjectSplitError("source case manifest is empty")
    missing = SOURCE_COLUMNS_USED - set(case_rows[0])
    if missing:
        raise SubjectSplitError(f"source manifest lacks required columns: {sorted(missing)}")

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    seen_caseids: set[str] = set()
    for source in case_rows:
        caseid, caseid_numeric = _exact_identifier(source.get("caseid"), "caseid")
        subjectid, subjectid_numeric = _exact_identifier(source.get("subjectid"), "subjectid")
        if caseid in seen_caseids:
            raise SubjectSplitError(f"duplicate caseid: {caseid}")
        seen_caseids.add(caseid)
        sex = str(source.get("sex_group", "")).strip()
        if sex not in SEX_ORDER:
            raise SubjectSplitError(f"invalid sex_group for subject {subjectid}: {sex!r}")
        grouped[subjectid].append(
            {
                "caseid": caseid,
                "caseid_numeric": caseid_numeric,
                "subjectid": subjectid,
                "subjectid_numeric": subjectid_numeric,
                "subject_case_count": int(str(source.get("subject_case_count", "")).strip()),
                "sex_group": sex,
                "age": _finite_positive(source.get("age"), "age", minimum=17.999999999),
                "height_cm": _finite_positive(source.get("height_cm"), "height_cm"),
                "weight_kg": _finite_positive(source.get("weight_kg"), "weight_kg"),
                "age_group": str(source.get("age_group", "")).strip(),
            }
        )

    if enforce_production_counts:
        if len(case_rows) != EXPECTED_CASE_COUNT or len(grouped) != EXPECTED_SUBJECT_COUNT:
            raise SubjectSplitError("production source must contain 2,460 cases and 2,415 subjects")

    subjects: list[dict[str, object]] = []
    for subjectid, rows in grouped.items():
        declared_counts = {int(row["subject_case_count"]) for row in rows}
        if declared_counts != {len(rows)}:
            raise SubjectSplitError(f"subject_case_count mismatch for subject {subjectid}")
        sexes = {str(row["sex_group"]) for row in rows}
        if len(sexes) != 1:
            raise SubjectSplitError(f"sex_group inconsistency for subject {subjectid}")
        ages = [float(row["age"]) for row in rows]
        heights = [float(row["height_cm"]) for row in rows]
        weights = [float(row["weight_kg"]) for row in rows]
        age_median = float(statistics.median(ages))
        age_groups = {str(row["age_group"]) for row in rows}
        band = subject_case_count_band(len(rows))
        age_group = subject_age_group(age_median)
        sex = next(iter(sexes))
        stratum = f"{sex}|{age_group}|{band}"
        subjects.append(
            {
                "subjectid": subjectid,
                "subjectid_numeric_sort_key": int(rows[0]["subjectid_numeric"]),
                "sex_group": sex,
                "subject_age_median": age_median,
                **_range_fields(ages, "age"),
                "subject_age_group": age_group,
                "subject_age_group_distinct_count": len(age_groups),
                "subject_age_group_span_warning": len(age_groups) > 1,
                "subject_height_median_cm": float(statistics.median(heights)),
                **_range_fields(heights, "height", "_cm"),
                "subject_weight_median_kg": float(statistics.median(weights)),
                **_range_fields(weights, "weight", "_kg"),
                "subject_case_count": len(rows),
                "subject_case_count_band": band,
                "stratum_key": stratum,
            }
        )

    actual_clusters = Counter(int(row["subject_case_count"]) for row in subjects)
    if enforce_production_counts and actual_clusters != Counter({1: 2378, 2: 35, 3: 1, 9: 1}):
        raise SubjectSplitError("production subject cluster distribution mismatch")
    return subjects


def hamilton_test_quotas(stratum_counts: Mapping[str, int], test_target: int) -> dict[str, int]:
    order = canonical_strata()
    if set(stratum_counts) != set(order):
        raise SubjectSplitError("stratum count map must contain every canonical stratum")
    raw = {key: Fraction(int(stratum_counts[key]), 1) * TEST_FRACTION for key in order}
    quotas = {key: math.floor(raw[key]) for key in order}
    remaining = test_target - sum(quotas.values())
    if remaining < 0 or remaining > len(order):
        raise SubjectSplitError("invalid Hamilton remainder-slot count")
    ranked = sorted(order, key=lambda key: (-(raw[key] - quotas[key]), order.index(key)))
    for key in ranked[:remaining]:
        quotas[key] += 1
    if sum(quotas.values()) != test_target:
        raise SubjectSplitError("Hamilton quotas do not sum to the target")
    if any(quotas[key] > int(stratum_counts[key]) for key in order):
        raise SubjectSplitError("Hamilton quota exceeds stratum size")
    return quotas


def allocate_subjects(
    subject_rows: Sequence[Mapping[str, object]],
    *,
    train_target: int = TRAIN_SUBJECT_TARGET,
    test_target: int = TEST_SUBJECT_TARGET,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Allocate subjects once using Hamilton quotas and pinned SHA-256 ranks."""

    if len(subject_rows) != train_target + test_target:
        raise SubjectSplitError("subject count does not equal train plus test targets")
    subjectids = [str(row["subjectid"]) for row in subject_rows]
    if len(subjectids) != len(set(subjectids)):
        raise SubjectSplitError("duplicate subject in allocation input")

    grouped: dict[str, list[dict[str, object]]] = {key: [] for key in canonical_strata()}
    for source in subject_rows:
        row = dict(source)
        key = str(row["stratum_key"])
        if key not in grouped:
            raise SubjectSplitError(f"noncanonical stratum: {key}")
        exact, numeric = _exact_identifier(row["subjectid"], "subjectid")
        row["subjectid"] = exact
        row["subjectid_numeric_sort_key"] = numeric
        row["allocation_rank_sha256"] = allocation_rank_sha256(exact, key)
        grouped[key].append(row)

    counts = {key: len(grouped[key]) for key in canonical_strata()}
    quotas = hamilton_test_quotas(counts, test_target)
    allocation_rows: list[dict[str, object]] = []
    stratum_rows: list[dict[str, object]] = []
    for order_index, key in enumerate(canonical_strata(), start=1):
        ordered = sorted(
            grouped[key],
            key=lambda row: (
                str(row["allocation_rank_sha256"]),
                int(row["subjectid_numeric_sort_key"]),
                str(row["subjectid"]),
            ),
        )
        quota = quotas[key]
        raw = Fraction(counts[key], 1) * TEST_FRACTION
        stratum_rows.append(
            {
                "canonical_stratum_order": order_index,
                "stratum_key": key,
                "stratum_subject_count": counts[key],
                "raw_test_quota_numerator": raw.numerator,
                "raw_test_quota_denominator": raw.denominator,
                "floor_test_quota": math.floor(raw),
                "fractional_remainder_numerator": (raw - math.floor(raw)).numerator,
                "fractional_remainder_denominator": (raw - math.floor(raw)).denominator,
                "final_test_quota": quota,
                "final_train_count": counts[key] - quota,
            }
        )
        for rank, row in enumerate(ordered, start=1):
            row.update(
                {
                    "assigned_split": "test" if rank <= quota else "train",
                    "stratum_subject_count": counts[key],
                    "stratum_test_quota": quota,
                    "within_stratum_rank": rank,
                    "split_seed": SPLIT_SEED,
                    "allocation_method": ALLOCATION_METHOD,
                    "source_cohort_protocol_version": SOURCE_COHORT_PROTOCOL_VERSION,
                    "study_protocol_version": STUDY_PROTOCOL_VERSION,
                    "split_manifest_version": SPLIT_MANIFEST_VERSION,
                }
            )
            row.pop("subjectid_numeric_sort_key", None)
            allocation_rows.append(row)

    counts_by_split = Counter(str(row["assigned_split"]) for row in allocation_rows)
    if counts_by_split != Counter({"train": train_target, "test": test_target}):
        raise SubjectSplitError("exact train/test subject targets were not met")
    allocation_rows.sort(
        key=lambda row: (
            SPLIT_ORDER[str(row["assigned_split"])],
            int(str(row["subjectid"])),
            str(row["subjectid"]),
        )
    )
    return allocation_rows, stratum_rows


def build_case_split_rows(
    case_rows: Sequence[Mapping[str, object]],
    subject_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    assignment = {str(row["subjectid"]): str(row["assigned_split"]) for row in subject_rows}
    if len(assignment) != len(subject_rows):
        raise SubjectSplitError("duplicate subject in subject split manifest")
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for source in case_rows:
        caseid, case_numeric = _exact_identifier(source.get("caseid"), "caseid")
        subjectid, subject_numeric = _exact_identifier(source.get("subjectid"), "subjectid")
        if caseid in seen:
            raise SubjectSplitError(f"duplicate caseid: {caseid}")
        seen.add(caseid)
        if subjectid not in assignment:
            raise SubjectSplitError(f"case has unknown parent subject: {caseid}")
        result.append(
            {
                "caseid": caseid,
                "subjectid": subjectid,
                "assigned_split": assignment[subjectid],
                "source_final_cohort_checksum": SOURCE_FINAL_COHORT_SHA256,
                "source_subject_linkage_checksum": SOURCE_SUBJECT_LINKAGE_FILE_SHA256,
                "source_cohort_protocol_version": SOURCE_COHORT_PROTOCOL_VERSION,
                "study_protocol_version": STUDY_PROTOCOL_VERSION,
                "split_manifest_version": SPLIT_MANIFEST_VERSION,
                "_case_numeric": case_numeric,
                "_subject_numeric": subject_numeric,
            }
        )
    if len(result) != EXPECTED_CASE_COUNT:
        raise SubjectSplitError("case split manifest must contain exactly 2,460 cases")
    result.sort(
        key=lambda row: (
            SPLIT_ORDER[str(row["assigned_split"])],
            int(row["_subject_numeric"]),
            int(row["_case_numeric"]),
            str(row["caseid"]),
        )
    )
    for row in result:
        row.pop("_case_numeric")
        row.pop("_subject_numeric")
    return result


def identifier_rows(
    rows: Sequence[Mapping[str, object]], field: str, assigned_split: str
) -> list[dict[str, str]]:
    values = {
        _exact_identifier(row[field], field)
        for row in rows
        if str(row["assigned_split"]) == assigned_split
    }
    return [{field: exact} for exact, _ in sorted(values, key=lambda item: (item[1], item[0]))]


def _sample_sd(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.stdev(values)


def standardized_mean_difference(train: Sequence[float], test: Sequence[float]) -> float:
    if not train or not test:
        raise SubjectSplitError("SMD groups must be nonempty")
    train_mean, test_mean = statistics.mean(train), statistics.mean(test)
    train_var = statistics.variance(train) if len(train) > 1 else 0.0
    test_var = statistics.variance(test) if len(test) > 1 else 0.0
    pooled = math.sqrt((train_var + test_var) / 2)
    if pooled == 0:
        if train_mean == test_mean:
            return 0.0
        raise SubjectSplitError("zero pooled variance with unequal means")
    return (train_mean - test_mean) / pooled


def _continuous_balance_row(
    subject_rows: Sequence[Mapping[str, object]], variable: str
) -> dict[str, object]:
    train = [float(row[variable]) for row in subject_rows if row["assigned_split"] == "train"]
    test = [float(row[variable]) for row in subject_rows if row["assigned_split"] == "test"]
    smd = standardized_mean_difference(train, test)
    absolute = abs(smd)
    interpretation = "acceptable" if absolute <= 0.10 else "warning" if absolute <= 0.20 else "hard_fail"
    return {
        "analysis_level": "subject_primary_continuous",
        "variable": variable,
        "level": "",
        "train_n": len(train),
        "test_n": len(test),
        "train_count": "",
        "test_count": "",
        "train_proportion": "",
        "test_proportion": "",
        "signed_proportion_difference": "",
        "absolute_proportion_difference": "",
        "train_mean": statistics.mean(train),
        "train_sample_sd_ddof1": _sample_sd(train),
        "test_mean": statistics.mean(test),
        "test_sample_sd_ddof1": _sample_sd(test),
        "train_median": empirical_quantile(train, 0.5),
        "train_q1": empirical_quantile(train, 0.25),
        "train_q3": empirical_quantile(train, 0.75),
        "test_median": empirical_quantile(test, 0.5),
        "test_q1": empirical_quantile(test, 0.25),
        "test_q3": empirical_quantile(test, 0.75),
        "standardized_mean_difference": smd,
        "absolute_smd": absolute,
        "interpretation": interpretation,
        "allocation_role": "primary_predeclared_stratum_or_balance_only_no_retry",
        "quantile_method": QUANTILE_METHOD,
    }


def _categorical_balance_rows(
    rows: Sequence[Mapping[str, object]],
    variable: str,
    *,
    analysis_level: str,
    level_order: Sequence[str] | None = None,
) -> list[dict[str, object]]:
    train = [str(row[variable]) for row in rows if row["assigned_split"] == "train"]
    test = [str(row[variable]) for row in rows if row["assigned_split"] == "test"]
    observed = set(train) | set(test)
    levels = list(level_order or sorted(observed))
    if set(levels) != observed:
        raise SubjectSplitError(f"categorical level order mismatch for {variable}")
    result: list[dict[str, object]] = []
    for level in levels:
        train_count, test_count = train.count(level), test.count(level)
        train_prop, test_prop = train_count / len(train), test_count / len(test)
        difference = train_prop - test_prop
        result.append(
            {
                "analysis_level": analysis_level,
                "variable": variable,
                "level": level,
                "train_n": len(train),
                "test_n": len(test),
                "train_count": train_count,
                "test_count": test_count,
                "train_proportion": train_prop,
                "test_proportion": test_prop,
                "signed_proportion_difference": difference,
                "absolute_proportion_difference": abs(difference),
                "train_mean": "",
                "train_sample_sd_ddof1": "",
                "test_mean": "",
                "test_sample_sd_ddof1": "",
                "train_median": "",
                "train_q1": "",
                "train_q3": "",
                "test_median": "",
                "test_q1": "",
                "test_q3": "",
                "standardized_mean_difference": "",
                "absolute_smd": "",
                "interpretation": "acceptable" if abs(difference) <= 0.05 else "warning",
                "allocation_role": (
                    "primary_predeclared_stratum_no_retry"
                    if analysis_level == "subject_primary_categorical"
                    else "secondary_descriptive_warning_only"
                ),
                "quantile_method": "",
            }
        )
    return result


def build_metadata_balance(
    subject_rows: Sequence[Mapping[str, object]],
    case_source_rows: Sequence[Mapping[str, object]],
    case_split_rows: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    balance: list[dict[str, object]] = []
    for variable in (
        "subject_age_median",
        "subject_height_median_cm",
        "subject_weight_median_kg",
        "subject_case_count",
    ):
        balance.append(_continuous_balance_row(subject_rows, variable))
    balance.extend(
        _categorical_balance_rows(
            subject_rows, "sex_group", analysis_level="subject_primary_categorical", level_order=SEX_ORDER
        )
    )
    balance.extend(
        _categorical_balance_rows(
            subject_rows,
            "subject_age_group",
            analysis_level="subject_primary_categorical",
            level_order=AGE_GROUP_ORDER,
        )
    )
    balance.extend(
        _categorical_balance_rows(
            subject_rows,
            "subject_case_count_band",
            analysis_level="subject_primary_categorical",
            level_order=CASE_COUNT_BAND_ORDER,
        )
    )

    split_by_case = {str(row["caseid"]): str(row["assigned_split"]) for row in case_split_rows}
    case_reporting: list[dict[str, object]] = []
    for source in case_source_rows:
        caseid = str(source["caseid"])
        case_reporting.append(
            {
                "assigned_split": split_by_case[caseid],
                **{column: str(source[column]) for column in SECONDARY_REPORTING_COLUMNS},
            }
        )
    for variable in ("age_group", "bmi_group", "asa_group", "emergency_group", "operation_type_group"):
        balance.extend(
            _categorical_balance_rows(
                case_reporting,
                variable,
                analysis_level="case_secondary_categorical",
            )
        )

    continuous = [row for row in balance if row["analysis_level"] == "subject_primary_continuous"]
    categorical = [row for row in balance if row["analysis_level"] == "subject_primary_categorical"]
    secondary = [row for row in balance if row["analysis_level"] == "case_secondary_categorical"]
    maximum_smd = max(float(row["absolute_smd"]) for row in continuous)
    summary = {
        "phase": "Phase 8A",
        "split_manifest_version": SPLIT_MANIFEST_VERSION,
        "membership_fixed_before_balance": True,
        "alternate_seed_search_performed": False,
        "balance_optimized_seed_selection": False,
        "quantile_method": QUANTILE_METHOD,
        "sample_sd_ddof": 1,
        "maximum_absolute_primary_continuous_smd": maximum_smd,
        "primary_continuous_warning_count": sum(row["interpretation"] == "warning" for row in continuous),
        "primary_continuous_hard_failure_count": sum(row["interpretation"] == "hard_fail" for row in continuous),
        "primary_categorical_warning_count": sum(row["interpretation"] == "warning" for row in categorical),
        "secondary_categorical_warning_count": sum(row["interpretation"] == "warning" for row in secondary),
        "balance_warning_count_total": sum(row["interpretation"] == "warning" for row in balance),
        "publication_gate_passed": maximum_smd <= 0.20,
        "signal_derived_variable_count": 0,
        "outcome_variable_count": 0,
    }
    if maximum_smd > 0.20:
        raise SubjectSplitError("primary continuous balance gate exceeded absolute SMD 0.20")
    return balance, summary


def sorted_identifier_sha256(rows: Sequence[Mapping[str, object]], field: str) -> str:
    identifiers = [_exact_identifier(row[field], field) for row in rows]
    if len(identifiers) != len(set(exact for exact, _ in identifiers)):
        raise SubjectSplitError(f"duplicate {field} in ID hash input")
    payload = "".join(f"{exact}\n" for exact, _ in sorted(identifiers, key=lambda item: (item[1], item[0])))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
