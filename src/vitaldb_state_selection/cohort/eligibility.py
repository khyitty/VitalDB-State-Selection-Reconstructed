"""Full-range, outcome-blind metadata-stage eligibility accounting."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

import yaml

from .clinical_metadata import (
    demographics_available,
    parse_clinical_row,
    time_range_is_valid,
)
from .guards import (
    CohortGuardError,
    assert_manifest_complete,
    assert_production_options,
    assert_source_ids_within_range,
    expected_caseids,
    normalize_caseid,
)
from .track_inventory import AliasRegistry, availability, index_track_rows


TRACK_COLUMNS = {
    "bis": "bis_track_available",
    "bis_sqi": "bis_sqi_track_available",
    "propofol_rate": "propofol_rate_track_available",
    "propofol_volume": "propofol_volume_track_available",
    "remifentanil_rate": "remifentanil_rate_track_available",
    "remifentanil_volume": "remifentanil_volume_track_available",
    "device_propofol_cp": "device_propofol_cp_available",
    "device_propofol_ce": "device_propofol_ce_available",
    "device_remifentanil_cp": "device_remifentanil_cp_available",
    "device_remifentanil_ce": "device_remifentanil_ce_available",
    "volatile_agent": "volatile_agent_track_available",
}

PRIMARY_CONCEPTS = ("bis", "propofol_rate", "remifentanil_rate")


def load_audit_config(path: Path) -> dict:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert_production_options(
        production_mode=bool(config.get("production_mode")),
        case_limit=None,
        first_n=False,
    )
    if config.get("allow_case_limit") is not False or config.get("allow_first_n") is not False:
        raise CohortGuardError("production configuration must explicitly disable case limits")
    thresholds = dict(config.get("quality_thresholds", {}))
    if thresholds.pop("status", None) != "pending_human_review":
        raise CohortGuardError("quality thresholds must remain pending human review")
    if any(value is not None for value in thresholds.values()):
        raise CohortGuardError("quality threshold values must remain null")
    return config


def _empty_record(
    caseid: int, *, timestamp: str, source_version: str
) -> dict[str, object]:
    record: dict[str, object] = {
        "caseid": caseid,
        "source_query_timestamp": timestamp,
        "source_version": source_version,
        "clinical_metadata_available": False,
        "track_inventory_available": False,
        "age": None,
        "age_available": False,
        "sex": None,
        "sex_available": False,
        "height": None,
        "height_available": False,
        "weight": None,
        "weight_available": False,
        "bmi": None,
        "asa": None,
        "subjectid": None,
        "anesthesia_type": None,
        "operation_type": None,
        "emergency_status": None,
        "anesthesia_start": None,
        "anesthesia_end": None,
        "operation_start": None,
        "operation_end": None,
        "legacy_98_case": None,
        "adult_candidate": False,
        "tiva_candidate": None,
        "volatile_exposure_possible": None,
        "candidate_at_metadata_stage": False,
        "metadata_exclusion_flags": [],
        "audit_status": "complete",
        "failure_type": None,
        "failure_message": None,
    }
    record.update({column: None for column in TRACK_COLUMNS.values()})
    return record


def build_eligibility_records(
    clinical_rows: Iterable[Mapping[str, object]],
    track_rows: Iterable[Mapping[str, object]],
    *,
    config: Mapping[str, object],
    registry: AliasRegistry,
    source_version: str,
    query_timestamp: str | None = None,
    clinical_query_available: bool = True,
    track_query_available: bool = True,
    source_failures: Sequence[str] = (),
    legacy_caseids: set[int] | None = None,
) -> list[dict[str, object]]:
    case_range = config["expected_case_range"]
    start = int(case_range["start"])
    end = int(case_range["end"])
    assert_production_options(
        production_mode=bool(config["production_mode"]), case_limit=None, first_n=False
    )
    clinical_materialized = list(clinical_rows)
    track_materialized = list(track_rows)
    assert_source_ids_within_range(
        (row.get("caseid") for row in clinical_materialized), start=start, end=end
    )
    assert_source_ids_within_range(
        (row.get("caseid") for row in track_materialized), start=start, end=end
    )
    clinical_by_case: dict[int, list[Mapping[str, object]]] = defaultdict(list)
    for row in clinical_materialized:
        clinical_by_case[normalize_caseid(row.get("caseid"))].append(row)
    tracks_by_case = index_track_rows(track_materialized, registry)
    timestamp = query_timestamp or datetime.now(UTC).isoformat()
    records: list[dict[str, object]] = []

    for caseid in expected_caseids(start, end):
        record = _empty_record(caseid, timestamp=timestamp, source_version=source_version)
        flags: list[str] = []
        failures: list[str] = list(source_failures)
        rows = clinical_by_case.get(caseid, [])
        record["clinical_metadata_available"] = len(rows) == 1
        record["track_inventory_available"] = bool(track_query_available)

        if not clinical_query_available:
            failures.append("clinical_query_unavailable")
        elif not rows:
            failures.append("clinical_metadata_missing")
        elif len(rows) > 1:
            failures.append("duplicate_clinical_rows")
        else:
            try:
                parsed = parse_clinical_row(rows[0])
            except CohortGuardError as exc:
                failures.append(f"clinical_parse_error:{exc}")
            else:
                for field in (
                    "age",
                    "sex",
                    "height",
                    "weight",
                    "bmi",
                    "asa",
                    "subjectid",
                    "anesthesia_type",
                    "operation_type",
                    "emergency_status",
                    "anesthesia_start",
                    "anesthesia_end",
                    "operation_start",
                    "operation_end",
                ):
                    record[field] = parsed[field]
                record.update(demographics_available(parsed))
                record["adult_candidate"] = (
                    parsed["age"] is not None and float(parsed["age"]) >= 18
                )
                for availability_flag in (
                    "age_available",
                    "sex_available",
                    "height_available",
                    "weight_available",
                ):
                    if not record[availability_flag]:
                        flags.append(availability_flag.replace("_available", "_missing"))
                if not record["adult_candidate"]:
                    flags.append("adult_criterion_not_met")
                if not time_range_is_valid(parsed):
                    flags.append("time_range_invalid_or_missing")

        if not track_query_available:
            failures.append("track_inventory_query_unavailable")
        case_tracks = tracks_by_case.get(caseid, {}) if track_query_available else {}
        track_availability = availability(case_tracks, registry)
        for concept, column in TRACK_COLUMNS.items():
            record[column] = track_availability.get(concept)
        for concept in PRIMARY_CONCEPTS:
            if record[TRACK_COLUMNS[concept]] is not True:
                flags.append(f"{concept}_track_missing")
            if len(case_tracks.get(concept, [])) > 1:
                flags.append(f"{concept}_track_ambiguous")

        if legacy_caseids is None:
            record["legacy_98_case"] = None
            flags.append("legacy_overlap_not_evaluated")
        else:
            record["legacy_98_case"] = caseid in legacy_caseids
            if record["legacy_98_case"]:
                flags.append("legacy_98_case")

        # These decisions intentionally remain unresolved until human review.
        record["tiva_candidate"] = None
        record["volatile_exposure_possible"] = None
        flags.extend(("tiva_classification_pending", "volatile_alias_review_pending"))
        record["candidate_at_metadata_stage"] = False
        record["metadata_exclusion_flags"] = sorted(set(flags))

        if failures:
            record["audit_status"] = "failed"
            record["failure_type"] = failures[0].split(":", 1)[0]
            record["failure_message"] = " | ".join(failures)
        records.append(record)

    assert_manifest_complete([record["caseid"] for record in records], start=start, end=end)
    return records


def summarize_records(records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    assert_manifest_complete([record["caseid"] for record in records])
    return {
        "record_count": len(records),
        "audit_complete_count": sum(record["audit_status"] == "complete" for record in records),
        "audit_failed_count": sum(record["audit_status"] == "failed" for record in records),
        "metadata_candidate_count": sum(
            record["candidate_at_metadata_stage"] is True for record in records
        ),
        "thresholds_finalized": False,
        "scientific_result": False,
    }
