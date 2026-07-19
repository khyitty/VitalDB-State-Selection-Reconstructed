"""Phase 5A source hygiene, inventory summaries, and outcome-blind reporting."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .guards import CohortGuardError, assert_manifest_complete, normalize_caseid
from .track_inventory import AliasRegistry


EXPECTED_ACTIVE_ALIASES = {
    "bis": ("BIS/BIS",),
    "propofol_rate": ("Orchestra/PPF20_RATE",),
    "remifentanil_rate": ("Orchestra/RFTN20_RATE",),
}
PENDING_DECISIONS = (
    "tiva_classification",
    "volatile_exposure",
    "propofol_rate_unit",
    "remifentanil_rate_unit",
    "legacy_98_overlap",
    "final_eligibility",
    "signal_quality_thresholds",
)


@dataclass(frozen=True)
class PreparedSourceRows:
    rows: list[dict[str, object]]
    events: list[dict[str, object]]
    case_failures: dict[int, tuple[str, ...]]


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_phase5a_boundaries(
    config: Mapping[str, object], registry: AliasRegistry
) -> None:
    case_range = config.get("expected_case_range")
    if case_range != {"start": 1, "end": 6388}:
        raise CohortGuardError("Phase 5A requires the exact case range 1..6388")
    if registry.active != EXPECTED_ACTIVE_ALIASES:
        raise CohortGuardError("Phase 5A permits exactly three approved track names")
    if any(
        registry.unit_status.get(concept) != "pending_human_review"
        for concept in EXPECTED_ACTIVE_ALIASES
    ):
        raise CohortGuardError("drug-rate and BIS units must remain pending human review")


def _source_event(
    *,
    source: str,
    row_index: int,
    failure_type: str,
    failure_message: str,
    caseid: int | None,
) -> dict[str, object]:
    return {
        "scope": "source_row",
        "source": source,
        "row_index": row_index,
        "caseid": caseid,
        "failure_type": failure_type,
        "failure_message": failure_message,
        "retryable": False,
    }


def prepare_source_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    source: str,
    start: int = 1,
    end: int = 6388,
) -> PreparedSourceRows:
    """Preserve malformed source-row evidence while isolating valid rows for parsing."""

    if source not in {"cases", "tracks"}:
        raise ValueError(f"unsupported source: {source}")
    prepared: list[dict[str, object]] = []
    events: list[dict[str, object]] = []
    case_failures: dict[int, list[str]] = defaultdict(list)
    seen_tracks: Counter[tuple[int, str, str]] = Counter()

    for row_index, source_row in enumerate(rows, start=1):
        row = dict(source_row)
        try:
            caseid = normalize_caseid(row.get("caseid"))
        except CohortGuardError as exc:
            events.append(
                _source_event(
                    source=source,
                    row_index=row_index,
                    failure_type="invalid_caseid",
                    failure_message=str(exc),
                    caseid=None,
                )
            )
            continue
        if caseid < start or caseid > end:
            events.append(
                _source_event(
                    source=source,
                    row_index=row_index,
                    failure_type="out_of_range_caseid",
                    failure_message=f"caseid {caseid} outside {start}..{end}",
                    caseid=caseid,
                )
            )
            continue
        row["caseid"] = caseid

        if source == "tracks":
            name = str(row.get("tname", "")).strip()
            tid = str(row.get("tid", "")).strip()
            missing = [field for field, value in (("tname", name), ("tid", tid)) if not value]
            if missing:
                message = f"track row missing required fields: {missing}"
                events.append(
                    _source_event(
                        source=source,
                        row_index=row_index,
                        failure_type="track_parse_error",
                        failure_message=message,
                        caseid=caseid,
                    )
                )
                case_failures[caseid].append(f"track_parse_error:{message}")
                continue
            row["tname"] = name
            row["tid"] = tid
            key = (caseid, name, tid)
            seen_tracks[key] += 1
            if seen_tracks[key] > 1:
                message = f"duplicate track row for tname={name!r}, tid={tid!r}"
                events.append(
                    _source_event(
                        source=source,
                        row_index=row_index,
                        failure_type="duplicate_track_row",
                        failure_message=message,
                        caseid=caseid,
                    )
                )
                case_failures[caseid].append(f"duplicate_track_row:{message}")
        prepared.append(row)

    return PreparedSourceRows(
        rows=prepared,
        events=events,
        case_failures={
            caseid: tuple(messages) for caseid, messages in sorted(case_failures.items())
        },
    )


def merge_case_failures(
    *failure_maps: Mapping[int, Sequence[str]],
) -> dict[int, tuple[str, ...]]:
    merged: dict[int, list[str]] = defaultdict(list)
    for failure_map in failure_maps:
        for caseid, messages in failure_map.items():
            merged[int(caseid)].extend(str(message) for message in messages)
    return {caseid: tuple(messages) for caseid, messages in sorted(merged.items())}


def build_unapproved_alias_candidates(
    track_rows: Iterable[Mapping[str, object]], registry: AliasRegistry
) -> list[dict[str, object]]:
    counts: Counter[str] = Counter()
    cases: dict[str, set[int]] = defaultdict(set)
    tids: dict[str, set[str]] = defaultdict(set)
    for row in track_rows:
        name = str(row.get("tname", "")).strip()
        if registry.concept_for(name) is not None:
            continue
        caseid = normalize_caseid(row.get("caseid"))
        counts[name] += 1
        cases[name].add(caseid)
        tids[name].add(str(row.get("tid", "")).strip())
    return [
        {
            "track_name": name,
            "row_count": counts[name],
            "case_count": len(cases[name]),
            "distinct_tid_count": len(tids[name]),
            "review_status": "pending_human_review",
            "auto_approved": False,
        }
        for name in sorted(counts, key=lambda item: (-counts[item], item))
    ]


def summarize_full_metadata_audit(
    records: Sequence[Mapping[str, object]],
    *,
    track_rows: Sequence[Mapping[str, object]],
    source_events: Sequence[Mapping[str, object]],
    candidates: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    assert_manifest_complete([record["caseid"] for record in records])
    combinations: Counter[str] = Counter()
    for record in records:
        values = []
        for concept in ("bis", "propofol_rate", "remifentanil_rate"):
            value = record[f"{concept}_track_available"]
            encoded = "unknown" if value is None else str(int(bool(value)))
            values.append(f"{concept}={encoded}")
        combinations["|".join(values)] += 1
    failure_types = Counter(
        str(record["failure_type"])
        for record in records
        if record["audit_status"] == "failed"
    )
    source_failure_types = Counter(str(event["failure_type"]) for event in source_events)
    caseids = [int(record["caseid"]) for record in records]
    caseid_fingerprint = hashlib.sha256(
        ",".join(str(caseid) for caseid in caseids).encode("ascii")
    ).hexdigest()
    return {
        "phase": "5A_full_metadata_and_track_inventory",
        "scientific_result": False,
        "record_count": len(records),
        "caseid_min": min(caseids),
        "caseid_max": max(caseids),
        "caseid_fingerprint_sha256": caseid_fingerprint,
        "duplicate_manifest_case_count": len(caseids) - len(set(caseids)),
        "missing_manifest_case_count": 6388 - len(set(caseids)),
        "audit_complete_count": sum(row["audit_status"] == "complete" for row in records),
        "audit_failed_count": sum(row["audit_status"] == "failed" for row in records),
        "audit_failure_type_counts": dict(sorted(failure_types.items())),
        "source_row_failure_type_counts": dict(sorted(source_failure_types.items())),
        "clinical_metadata_available_count": sum(
            row["clinical_metadata_available"] is True for row in records
        ),
        "clinical_metadata_missing_count": sum(
            row["clinical_metadata_available"] is False for row in records
        ),
        "track_inventory_available_count": sum(
            row["track_inventory_available"] is True for row in records
        ),
        "track_inventory_missing_count": sum(
            row["track_inventory_available"] is False for row in records
        ),
        "metadata_missing_counts": {
            field: sum(row[field] is None for row in records)
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
            )
        },
        "exact_track_available_counts": {
            concept: sum(row[f"{concept}_track_available"] is True for row in records)
            for concept in ("bis", "propofol_rate", "remifentanil_rate")
        },
        "exact_track_combination_counts": dict(sorted(combinations.items())),
        "source_track_row_count": len(track_rows),
        "source_unique_track_name_count": len(
            {str(row.get("tname", "")).strip() for row in track_rows}
        ),
        "unapproved_track_name_count": len(candidates),
        "unapproved_track_row_count": sum(int(row["row_count"]) for row in candidates),
        "active_exact_aliases": {
            concept: list(names) for concept, names in EXPECTED_ACTIVE_ALIASES.items()
        },
        "pending_decisions": list(PENDING_DECISIONS),
        "legacy_overlap_evaluated": False,
        "metadata_candidate_count": 0,
        "quality_thresholds_finalized": False,
        "cohort_frozen": False,
        "split_created": False,
        "raw_signal_downloaded": False,
        "prediction_run": False,
        "feature_selection_run": False,
        "cpce_reconstruction_run": False,
        "ppo_run": False,
    }


def render_outcome_blind_report(
    summary: Mapping[str, object],
    source_snapshot: Mapping[str, object],
    candidates: Sequence[Mapping[str, object]],
) -> str:
    endpoints = source_snapshot["endpoints"]
    lines = [
        "# Phase 5A Full Metadata and Track Inventory Audit",
        "",
        "## Interpretation boundary",
        "",
        "This is an outcome-blind source and metadata inventory, not an eligibility",
        "decision or scientific result. Only the VitalDB `/cases` and `/trks` endpoints",
        "were queried. No raw time-series signal was downloaded.",
        "",
        "Legacy 98-case IDs were not read, extracted, copied, or compared. Legacy overlap,",
        "TIVA classification, volatile exposure, drug-rate units, quality thresholds, and",
        "final eligibility remain pending human review.",
        "",
        "## Source snapshots",
        "",
        "| Endpoint | Status | Rows | Bytes | SHA-256 |",
        "|---|---:|---:|---:|---|",
    ]
    for endpoint in ("cases", "tracks"):
        item = endpoints[endpoint]
        lines.append(
            f"| `/{endpoint if endpoint == 'cases' else 'trks'}` | {item['status']} | "
            f"{item.get('row_count', 0)} | {item.get('byte_count', 0)} | "
            f"`{item.get('sha256', 'unavailable')}` |"
        )
    lines.extend(
        [
            "",
            "## Complete case accounting",
            "",
            "| Measure | Count |",
            "|---|---:|",
            f"| Manifest rows | {summary['record_count']} |",
            f"| Duplicate manifest case IDs | {summary['duplicate_manifest_case_count']} |",
            f"| Missing manifest case IDs | {summary['missing_manifest_case_count']} |",
            f"| Audit-complete rows | {summary['audit_complete_count']} |",
            f"| Explicit failed rows | {summary['audit_failed_count']} |",
            f"| Clinical metadata unavailable | {summary['clinical_metadata_missing_count']} |",
            f"| Track inventory unavailable | {summary['track_inventory_missing_count']} |",
            "",
            "## Metadata missingness",
            "",
            "| Field | Missing cases |",
            "|---|---:|",
        ]
    )
    for field, count in summary["metadata_missing_counts"].items():
        lines.append(f"| {field} | {count} |")
    lines.extend(
        [
            "",
            "## Approved exact-track combinations",
            "",
            "Only `BIS/BIS`, `Orchestra/PPF20_RATE`, and `Orchestra/RFTN20_RATE`",
            "were resolved. No other name was assigned a concept.",
            "",
            "| Exact availability combination | Cases |",
            "|---|---:|",
        ]
    )
    for combination, count in summary["exact_track_combination_counts"].items():
        lines.append(f"| `{combination}` | {count} |")
    lines.extend(
        [
            "",
            "## API and parsing failures",
            "",
            "| Failure type | Count |",
            "|---|---:|",
        ]
    )
    combined_failures = Counter(summary["audit_failure_type_counts"])
    combined_failures.update(summary["source_row_failure_type_counts"])
    combined_failures.update(summary.get("api_failure_type_counts", {}))
    if combined_failures:
        for failure_type, count in sorted(combined_failures.items()):
            lines.append(f"| `{failure_type}` | {count} |")
    else:
        lines.append("| none observed | 0 |")
    lines.extend(
        [
            "",
            "## Unapproved alias candidate report",
            "",
            f"The inventory contains {summary['unapproved_track_name_count']} unapproved",
            "track names. Every item below remains `pending_human_review`; frequency does",
            "not imply semantic equivalence or unit validity.",
            "",
            "| Track name | Rows | Cases | Distinct TIDs | Status |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for item in candidates:
        safe_name = str(item["track_name"]).replace("|", "\\|")
        lines.append(
            f"| `{safe_name}` | {item['row_count']} | {item['case_count']} | "
            f"{item['distinct_tid_count']} | pending human review |"
        )
    lines.extend(
        [
            "",
            "## Prohibited downstream work",
            "",
            "No full signal download, threshold finalization, cohort freeze, split,",
            "prediction, feature selection, Cp/Ce reconstruction, or PPO execution was",
            "performed. Phase 5A stops at metadata and track inventory.",
            "",
        ]
    )
    return "\n".join(lines)
