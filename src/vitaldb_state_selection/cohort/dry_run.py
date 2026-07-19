"""Fixed-seed 25-case engineering metadata sample construction."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence

from .clinical_metadata import demographics_available, parse_clinical_row
from .guards import CohortGuardError, normalize_caseid
from .track_inventory import AliasRegistry, index_track_rows


DRY_RUN_SEED = 20260719
DRY_RUN_SAMPLE_SIZE = 25
REQUIRED_CONCEPTS = ("bis", "propofol_rate", "remifentanil_rate")


def build_dry_run_metadata_records(
    sample_caseids: Sequence[int],
    clinical_rows: Iterable[Mapping[str, object]],
    track_rows: Iterable[Mapping[str, object]],
    *,
    registry: AliasRegistry,
    source_version: str,
) -> tuple[list[dict[str, object]], dict[int, dict[str, list[dict[str, str]]]]]:
    normalized = [normalize_caseid(value) for value in sample_caseids]
    if len(normalized) != DRY_RUN_SAMPLE_SIZE or len(set(normalized)) != DRY_RUN_SAMPLE_SIZE:
        raise CohortGuardError("dry run requires exactly 25 unique caseids")
    selected = set(normalized)
    clinical_by_case: dict[int, list[Mapping[str, object]]] = defaultdict(list)
    for row in clinical_rows:
        caseid = normalize_caseid(row.get("caseid"))
        if caseid in selected:
            clinical_by_case[caseid].append(row)
    selected_track_rows = [
        row for row in track_rows if normalize_caseid(row.get("caseid")) in selected
    ]
    tracks_by_case = index_track_rows(selected_track_rows, registry)
    records: list[dict[str, object]] = []
    for caseid in sorted(normalized):
        rows = clinical_by_case.get(caseid, [])
        record: dict[str, object] = {
            "caseid": caseid,
            "sample_seed": DRY_RUN_SEED,
            "sample_size": DRY_RUN_SAMPLE_SIZE,
            "sampling_method": "fixed_seed_random_without_replacement",
            "scientific_result": False,
            "source_version": source_version,
            "metadata_status": "complete",
            "clinical_metadata_available": len(rows) == 1,
            "required_demographics_available": False,
            "exact_track_counts": {
                concept: len(tracks_by_case.get(caseid, {}).get(concept, []))
                for concept in REQUIRED_CONCEPTS
            },
            "drug_rate_unit_status": {
                "propofol_rate": registry.unit_status["propofol_rate"],
                "remifentanil_rate": registry.unit_status["remifentanil_rate"],
            },
            "metadata_failure_type": None,
            "metadata_failure_message": None,
            "signal_status": "not_requested",
            "signal_attempt_count": 0,
            "signal_bytes": 0,
            "signal_checksums": {},
            "signal_failure_type": None,
            "signal_failure_message": None,
        }
        try:
            if not rows:
                raise CohortGuardError("clinical metadata missing")
            if len(rows) > 1:
                raise CohortGuardError("duplicate clinical rows")
            parsed = parse_clinical_row(rows[0])
            record["required_demographics_available"] = all(
                demographics_available(parsed).values()
            )
        except CohortGuardError as exc:
            record["metadata_status"] = "failed"
            record["metadata_failure_type"] = type(exc).__name__
            record["metadata_failure_message"] = str(exc)
        records.append(record)
    return records, tracks_by_case


def apply_signal_results(
    metadata_records: Sequence[dict[str, object]],
    download_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    by_case = {int(row["caseid"]): row for row in download_rows}
    if set(by_case) != {int(record["caseid"]) for record in metadata_records}:
        raise CohortGuardError("signal result caseids do not match dry-run sample")
    updated: list[dict[str, object]] = []
    for source in metadata_records:
        record = dict(source)
        download = by_case[int(record["caseid"])]
        status = str(download["status"])
        record["signal_status"] = "complete" if status == "complete" else "failed"
        record["signal_attempt_count"] = int(download["attempt_count"])
        record["signal_bytes"] = int(download["bytes_downloaded"])
        record["signal_checksums"] = dict(download["checksums"])
        record["signal_failure_type"] = download["failure_type"]
        record["signal_failure_message"] = download["failure_message"]
        updated.append(record)
    return updated
