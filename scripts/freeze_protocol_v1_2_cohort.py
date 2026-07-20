"""Freeze the human-approved Protocol v1.2 cohort from Phase 6C artifacts only."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.protocol_v1_2 import (  # noqa: E402
    APPROVAL_DATE,
    EXPECTED_ELIGIBLE_CASES,
    EXPECTED_ELIGIBLE_IDS_SHA256,
    EXPECTED_INELIGIBLE_CASES,
    EXPECTED_INELIGIBLE_IDS_SHA256,
    EXPECTED_SOURCE_CASES,
    MINIMUM_USABLE_WINDOWS,
    PHASE6C_PUBLICATION_FOLLOWUP,
    PHASE6C_SOURCE_COMMIT,
    PROTOCOL_VERSION,
    SELECTED_CANDIDATE_ID,
    SELECTED_PARAMETERS,
    build_final_cohort_manifest,
    build_sensitivity_reference,
    cohort_summary,
)


MANIFESTS = ROOT / "data" / "manifests"
RAW_ROOT = ROOT / "data" / "raw" / "phase6a_primary_signals"
LEGACY_ROOT = ROOT.parent / "VitalDB-Feature-Selection"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze Protocol v1.2 final eligible cohort")
    parser.add_argument(
        "--verify-only", action="store_true",
        help="validate already-created Phase 6D artifacts without regenerating them",
    )
    return parser.parse_args()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def csv_value(value: object) -> object:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (list, tuple, dict, set)):
        normalized = sorted(value) if isinstance(value, set) else value
        return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=isinstance(value, dict))
    return value


def csv_bytes(rows: list[dict[str, object]]) -> bytes:
    if not rows:
        raise RuntimeError("refusing to serialize empty CSV")
    fields = list(rows[0]) + sorted({field for row in rows for field in row} - set(rows[0]))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: csv_value(row.get(field)) for field in fields})
    return stream.getvalue().encode()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def raw_tree_state() -> dict[str, object]:
    files = sorted(path for path in RAW_ROOT.rglob("*") if path.is_file())
    entries = [f"{path.relative_to(RAW_ROOT).as_posix()}\t{path.stat().st_size}" for path in files]
    return {
        "file_count": len(files),
        "total_bytes": sum(path.stat().st_size for path in files),
        "relative_path_and_size_fingerprint_sha256": hashlib.sha256(("\n".join(entries) + "\n").encode()).hexdigest(),
        "partial_file_count": sum(path.suffix == ".part" for path in files),
    }


def legacy_state() -> dict[str, object]:
    safe = LEGACY_ROOT.resolve().as_posix()

    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-c", f"safe.directory={safe}", "-C", str(LEGACY_ROOT), *args],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()

    return {
        "head": git("rev-parse", "HEAD"),
        "tree": git("rev-parse", "HEAD^{tree}"),
        "status_short": git("status", "--short").splitlines(),
    }


def load_selected_candidate(path: Path) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    with gzip.open(path, mode="rt", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["candidate_id"] == SELECTED_CANDIDATE_ID:
                selected.append(row)
    return selected


def verify_phase6c_lineage() -> None:
    current_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if current_commit != PHASE6C_PUBLICATION_FOLLOWUP:
        raise RuntimeError(f"Phase 6D must start at verified Phase 6C follow-up, got {current_commit}")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", PHASE6C_SOURCE_COMMIT, current_commit], cwd=ROOT,
        check=False,
    )
    if ancestor.returncode != 0:
        raise RuntimeError("Phase 6C source commit is not an ancestor of the current baseline")


def render_protocol(sensitivity_rows: list[dict[str, object]]) -> str:
    counts = {
        (str(row["dimension"]), str(row["alternative"])): int(row["eligible_case_count"])
        for row in sensitivity_rows
    }
    return f"""# Protocol v1.2 Decision Record

Status: human-approved and frozen on {APPROVAL_DATE}.

## Provenance

### Fact

- Source Phase 6C commit: `{PHASE6C_SOURCE_COMMIT}`.
- Verified Phase 6C publication follow-up: `{PHASE6C_PUBLICATION_FOLLOWUP}`.
- The decision used only outcome-blind Phase 6B/6C feasibility artifacts. No test outcome, target distribution, model result, prediction metric, or control result was inspected.
- Source accounting is 2,470 cases. The selected rule retains 2,460 and excludes 10.

### Human decision

- Selected candidate: `{SELECTED_CANDIDATE_ID}`.
- Grid: 10 seconds, anchored at each case anesthesia start.
- History: `t-50, t-40, t-30, t-20, t-10, t`; target: `t+30`.
- Every history and target stays inside the same case, anesthesia window, and inherited common observed span.
- Final eligibility requires at least 120 usable prediction endpoints under the selected candidate.

### Interpretation

The 120 endpoints are a count of usable 10-second prediction endpoints. They are not described as 20 continuous minutes. This record freezes preprocessing eligibility only; it does not authorize a split, modeling array, model, dose, Cp/Ce, feature selection, or PPO.

## Selected BIS and SQI rule

### Fact

- Finite BIS in the inclusive numerical range 0–100 is admissible. BIS below 0 or above 100 is unavailable and values are not clipped.
- SQI is joined only at the exact BIS raw timestamp. Usable BIS requires SQI >=50.
- At a requested history or target time, the most recent usable BIS at or before that time is allowed only when staleness is <=20 seconds.

### Human decision

BIS 0–10 remains admissible because Phase 6B/6C supplied no outcome-blind evidence that these in-range values are automatically erroneous. The Phase 6B BIS 10–100 fractions are not used for exclusion. SQI 50 was selected as the QC threshold; SQI 80, which retains {counts[("sqi_rule", "sqi_ge_80")]} cases at the 120-endpoint rule, remains a stricter sensitivity reference rather than the primary rule.

### Interpretation

SQI is QC-only and is prohibited from the prediction feature universe and PPO state. There is no case-level SQI-fraction threshold, nearest SQI match, SQI interpolation, or future BIS/SQI use.

## Selected drug-rate rule

### Fact

- Propofol and remifentanil are aligned independently using the most recent finite, nonnegative observation at or before each grid time.
- The hold cap is <=60 seconds. Zero is valid; negative rate is unavailable and remains a warning.
- The period before the first observation is not filled with zero. There is no future use, interpolation, backward fill, unlimited hold, unit conversion, dose, or Cp/Ce calculation.

### Human decision

The 60-second cap was selected to limit the temporal age of carried rate observations. The 120-, 300-, and 600-second candidates each retain {counts[("drug_hold", "120_seconds")]}, {counts[("drug_hold", "300_seconds")]}, and {counts[("drug_hold", "600_seconds")]} cases at the same 120-endpoint rule, but their longer stale holds are preserved only as sensitivity analyses.

### Interpretation

Equal case counts do not make longer holds equivalent. This is a temporal-fidelity decision made without model performance.

## Duplicate timestamps

### Human decision

For duplicated raw timestamps, the derived lookup uses the last finite value in original payload order. Raw rows are not deleted, averaged, sorted in place, or modified. Duplicate-derived grid use remains flagged.

## Minimum-window decision

### Fact

For the selected candidate, thresholds 30, 60, 120, 300, and 600 retain {counts[("minimum_windows", "30")]}, {counts[("minimum_windows", "60")]}, 2,460, {counts[("minimum_windows", "300")]}, and {counts[("minimum_windows", "600")]} cases, respectively.

### Human decision

The minimum is 120 usable prediction endpoints. The 300 and 600 thresholds were not selected because they would impose substantially longer endpoint-count requirements and exclude additional cases without an outcome-blind necessity established by Phase 6B/6C.

### Interpretation

All unselected SQI, BIS-staleness, drug-hold, and minimum-window alternatives remain machine-readable robustness references. They are not additional frozen cohorts.

## Explicitly unused case-level rules

Phase 6B permissive/moderate/strict scenarios, BIS 10–100 fraction, case-level SQI fraction, common-span ratio, anesthesia-duration 60/120-minute thresholds, longest raw timestamp gap, minimum 300/600 windows, and clinical-plausibility demographic cutoffs do not control final eligibility.

## Freeze boundary

There is exactly one primary final cohort. No train/validation/test split, stratification, test sealing, normalization, imputation fit, modeling array, persistence baseline, prediction, Elastic Net, GRU, Attention-GRU, feature selection, Cp/Ce reconstruction, dose calculation, or PPO is authorized or performed in Phase 6D.
"""


def render_report(summary: dict[str, object]) -> str:
    return f"""# Phase 6D Final Cohort Freeze Report

## Frozen decision

- Protocol: `{PROTOCOL_VERSION}`.
- Selected candidate: `{SELECTED_CANDIDATE_ID}`.
- Minimum usable prediction endpoints: `{MINIMUM_USABLE_WINDOWS}`.
- Source cases: `{summary['source_case_count']}`.
- Final eligible: `{summary['eligible_case_count']}`.
- Final excluded: `{summary['excluded_case_count']}`.
- Sorted eligible-ID SHA-256: `{summary['eligible_ids_sha256']}`.

## Inherited exclusions

Legacy overlap, Phase 6A volatile exclusion, and invalid-anesthesia-window overlap are all zero in the 2,470-case source and frozen eligible cohort. Demographic and warning fields are preserved but do not add an unapproved clinical cutoff.

## Interpretation boundary

This is a human-approved preprocessing and cohort-freeze record based only on outcome-blind Phase 6B/6C feasibility. Alternative counts are robustness references, not additional final cohorts. The minimum is an endpoint count, not a continuous-duration claim.

## Prohibited work

No raw signal was read or downloaded. No API request, split, stratification, test sealing, modeling array, normalization, imputation fit, unit conversion, dose, Cp/Ce, persistence baseline, prediction, metric, Elastic Net, GRU, Attention-GRU, feature selection, target inspection, or PPO execution occurred.
"""


def verify_existing() -> dict[str, object]:
    inventory_path = MANIFESTS / "protocol_v1_2_artifact_checksums.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    for relative, expected in inventory.items():
        if sha256_path(ROOT / relative) != expected:
            raise RuntimeError(f"Phase 6D artifact checksum mismatch: {relative}")
    freeze = json.loads((MANIFESTS / "protocol_v1_2_cohort_freeze.json").read_text(encoding="utf-8"))
    if freeze["eligible_case_count"] != EXPECTED_ELIGIBLE_CASES:
        raise RuntimeError("existing Phase 6D eligible count mismatch")
    return freeze


def main() -> int:
    args = parse_args()
    if args.verify_only:
        print(json.dumps(verify_existing(), sort_keys=True))
        return 0

    verify_phase6c_lineage()
    raw_before = raw_tree_state()
    legacy_before = legacy_state()
    if raw_before["partial_file_count"] != 0:
        raise RuntimeError("raw partial file exists before Phase 6D")

    source_paths = (
        ROOT / "docs" / "protocol_v1_1_decision_record.md",
        MANIFESTS / "pre_quality_acquisition_cohort.csv",
        MANIFESTS / "primary_signal_download_manifest.csv",
        MANIFESTS / "primary_signal_checksum_manifest.csv",
        MANIFESTS / "primary_signal_quality_case_manifest.csv",
        MANIFESTS / "primary_signal_quality_track_manifest.csv",
        MANIFESTS / "primary_signal_quality_summary.json",
        MANIFESTS / "causal_grid_feasibility_case_candidate_manifest.csv.gz",
        MANIFESTS / "causal_grid_candidate_summary.csv",
        MANIFESTS / "causal_grid_minimum_window_sensitivity.csv",
        MANIFESTS / "causal_grid_demographics_pk_input_feasibility.csv",
        MANIFESTS / "causal_grid_feasibility_source_snapshot.json",
        MANIFESTS / "causal_grid_feasibility_artifact_checksums.json",
    )
    input_checksums = {path.relative_to(ROOT).as_posix(): sha256_path(path) for path in source_paths}
    phase6c_inventory = json.loads((MANIFESTS / "causal_grid_feasibility_artifact_checksums.json").read_text(encoding="utf-8"))
    for relative, expected in phase6c_inventory.items():
        if sha256_path(ROOT / relative) != expected:
            raise RuntimeError(f"Phase 6C source artifact checksum mismatch: {relative}")

    candidate_path = MANIFESTS / "causal_grid_feasibility_case_candidate_manifest.csv.gz"
    candidate_rows = load_selected_candidate(candidate_path)
    pre_quality = read_csv(MANIFESTS / "pre_quality_acquisition_cohort.csv")
    downloads = read_csv(MANIFESTS / "primary_signal_download_manifest.csv")
    raw_checksums = read_csv(MANIFESTS / "primary_signal_checksum_manifest.csv")
    quality_rows = read_csv(MANIFESTS / "primary_signal_quality_case_manifest.csv")
    quality_tracks = read_csv(MANIFESTS / "primary_signal_quality_track_manifest.csv")
    quality_summary = json.loads((MANIFESTS / "primary_signal_quality_summary.json").read_text(encoding="utf-8"))
    demographics = read_csv(MANIFESTS / "causal_grid_demographics_pk_input_feasibility.csv")
    candidate_summary = read_csv(MANIFESTS / "causal_grid_candidate_summary.csv")
    minimum_rows = read_csv(MANIFESTS / "causal_grid_minimum_window_sensitivity.csv")
    if len(downloads) != 9880 or len(raw_checksums) != 9880 or len(quality_tracks) != 9880:
        raise RuntimeError("Phase 6A/6B 9,880-row accounting mismatch")
    if quality_summary["case_count"] != EXPECTED_SOURCE_CASES:
        raise RuntimeError("Phase 6B summary case accounting mismatch")
    selected_summary = [row for row in candidate_summary if row["candidate_id"] == SELECTED_CANDIDATE_ID]
    selected_minimum = [
        row for row in minimum_rows
        if row["candidate_id"] == SELECTED_CANDIDATE_ID
        and int(row["minimum_usable_windows"]) == MINIMUM_USABLE_WINDOWS
    ]
    if len(selected_summary) != 1 or int(selected_summary[0]["case_count"]) != EXPECTED_SOURCE_CASES:
        raise RuntimeError("selected Phase 6C candidate aggregate mismatch")
    if len(selected_minimum) != 1 or int(selected_minimum[0]["pass_case_count"]) != EXPECTED_ELIGIBLE_CASES:
        raise RuntimeError("selected Phase 6C 120-window count mismatch; cohort must not freeze")

    manifest_rows = build_final_cohort_manifest(
        candidate_rows, pre_quality, demographics, quality_rows,
        case_candidate_sha256=input_checksums["data/manifests/causal_grid_feasibility_case_candidate_manifest.csv.gz"],
    )
    sensitivity_rows = build_sensitivity_reference(minimum_rows)
    summary = cohort_summary(manifest_rows)
    eligible_rows = [
        {
            "caseid": row["caseid"], "protocol_version": PROTOCOL_VERSION,
            "selected_candidate_id": SELECTED_CANDIDATE_ID,
            "minimum_usable_windows": MINIMUM_USABLE_WINDOWS,
            "final_eligible": True,
        }
        for row in manifest_rows if row["final_eligible"]
    ]
    ineligible_rows = [
        {
            "caseid": row["caseid"],
            "selected_candidate_usable_window_count": row["selected_candidate_usable_window_count"],
            "exclusion_reason": row["exclusion_reason"],
            "contributing_bis_sqi_history_unavailable": row["contributing_bis_sqi_history_unavailable"],
            "contributing_no_candidate_grid_points": row["contributing_no_candidate_grid_points"],
            "contributing_no_usable_bis_sqi_history": row["contributing_no_usable_bis_sqi_history"],
            "contributing_bis_target_unavailable": row["contributing_bis_target_unavailable"],
            "contributing_no_usable_bis_target": row["contributing_no_usable_bis_target"],
            "contributing_propofol_unavailable": row["contributing_propofol_unavailable"],
            "contributing_remifentanil_unavailable": row["contributing_remifentanil_unavailable"],
            "contributing_zero_usable_windows": row["contributing_zero_usable_windows"],
            "contributing_fewer_than_120_windows": row["contributing_fewer_than_120_windows"],
        }
        for row in manifest_rows if not row["final_eligible"]
    ]
    if len(eligible_rows) != EXPECTED_ELIGIBLE_CASES or len(ineligible_rows) != EXPECTED_INELIGIBLE_CASES:
        raise RuntimeError("final 2,460/10 accounting mismatch; refusing to write freeze artifacts")

    manifest_payload = csv_bytes(manifest_rows)
    eligible_payload = csv_bytes(eligible_rows)
    ineligible_payload = csv_bytes(ineligible_rows)
    sensitivity_payload = csv_bytes(sensitivity_rows)
    manifest_sha256 = hashlib.sha256(manifest_payload).hexdigest()
    created_at = datetime.now(UTC).isoformat()
    freeze = {
        "protocol_version": PROTOCOL_VERSION,
        "source_commit_sha": PHASE6C_SOURCE_COMMIT,
        "selected_candidate_id": SELECTED_CANDIDATE_ID,
        "selected_preprocessing_parameters": SELECTED_PARAMETERS,
        "minimum_usable_window_count": MINIMUM_USABLE_WINDOWS,
        "source_case_count": EXPECTED_SOURCE_CASES,
        "eligible_case_count": EXPECTED_ELIGIBLE_CASES,
        "excluded_case_count": EXPECTED_INELIGIBLE_CASES,
        "sorted_eligible_case_ids_sha256": EXPECTED_ELIGIBLE_IDS_SHA256,
        "sorted_ineligible_case_ids_sha256": EXPECTED_INELIGIBLE_IDS_SHA256,
        "full_cohort_manifest_sha256": manifest_sha256,
        "created_timestamp": created_at,
        "cohort_frozen": True,
        "split_created": False,
        "modeling_arrays_created": False,
        "outcome_or_model_used": False,
    }
    summary.update({
        "source_phase6c_commit": PHASE6C_SOURCE_COMMIT,
        "source_phase6c_publication_followup": PHASE6C_PUBLICATION_FOLLOWUP,
        "selected_preprocessing_parameters": SELECTED_PARAMETERS,
        "sensitivity_reference_count": len(sensitivity_rows),
        "created_timestamp": created_at,
        "final_cohort_manifest_sha256": manifest_sha256,
        "execution_flags": {
            "api_requests": 0, "raw_signal_reads": 0, "new_raw_files": 0,
            "split": False, "stratification": False, "test_sealing": False,
            "modeling_arrays": False, "normalization": False, "imputation_fit": False,
            "unit_conversion": False, "dose": False, "recent_dose": False,
            "cumulative_dose": False, "schnider_minto_parameters": False,
            "cpce": False, "persistence": False, "prediction": False,
            "elastic_net": False, "gru": False, "attention_gru": False,
            "feature_selection": False, "ppo": False,
            "target_distribution_inspection": False, "prediction_metrics": False,
        },
    })

    raw_after = raw_tree_state()
    legacy_after = legacy_state()
    if raw_before != raw_after:
        raise RuntimeError("raw tree changed during Phase 6D")
    if legacy_before != legacy_after:
        raise RuntimeError("legacy repository state changed during Phase 6D")
    source_snapshot = {
        "schema_version": 1,
        "phase": "6D_protocol_v1_2_final_preprocessing_decision_and_cohort_freeze",
        "recorded_at": created_at,
        "phase6c_source_commit": PHASE6C_SOURCE_COMMIT,
        "phase6c_publication_followup": PHASE6C_PUBLICATION_FOLLOWUP,
        "input_artifact_sha256": input_checksums,
        "phase6c_checksum_inventory_verified": True,
        "phase6c_remote_sha_verified_before_phase6d": True,
        "source_case_count": EXPECTED_SOURCE_CASES,
        "selected_candidate_id": SELECTED_CANDIDATE_ID,
        "raw_tree_before": raw_before,
        "raw_tree_after": raw_after,
        "raw_tree_unchanged": True,
        "raw_signal_file_open_count": 0,
        "new_raw_file_count": 0,
        "api_request_count": 0,
        "legacy_state_before": legacy_before,
        "legacy_state_after": legacy_after,
        "legacy_state_unchanged": True,
        "legacy_case_ids_accessed": False,
        "sqi_in_prediction_feature_universe": False,
        "bis_0_10_admissible": True,
        "first_n_sampling": False,
        "cohort_regeneration_from_model_result": False,
        "cohort_frozen": True,
        "prohibited_execution": summary["execution_flags"],
    }
    protocol_text = render_protocol(sensitivity_rows)
    report_text = render_report(summary)

    outputs: dict[Path, bytes] = {
        MANIFESTS / "final_eligible_cohort_manifest.csv": manifest_payload,
        MANIFESTS / "final_eligible_caseids.csv": eligible_payload,
        MANIFESTS / "final_ineligible_caseids.csv": ineligible_payload,
        MANIFESTS / "protocol_v1_2_sensitivity_reference.csv": sensitivity_payload,
        MANIFESTS / "final_cohort_accounting_summary.json": json_bytes(summary),
        MANIFESTS / "protocol_v1_2_cohort_freeze.json": json_bytes(freeze),
        MANIFESTS / "protocol_v1_2_source_snapshot.json": json_bytes(source_snapshot),
        ROOT / "docs" / "protocol_v1_2_decision_record.md": (protocol_text.rstrip() + "\n").encode(),
        ROOT / "docs" / "final_cohort_freeze_report.md": (report_text.rstrip() + "\n").encode(),
    }
    for path, payload in outputs.items():
        atomic_bytes(path, payload)
    atomic_bytes(MANIFESTS / "protocol_v1_2_artifact_checksums.json", json_bytes({
        path.relative_to(ROOT).as_posix(): hashlib.sha256(payload).hexdigest()
        for path, payload in outputs.items()
    }))
    print(json.dumps({
        "source_cases": EXPECTED_SOURCE_CASES,
        "eligible": EXPECTED_ELIGIBLE_CASES,
        "ineligible": EXPECTED_INELIGIBLE_CASES,
        "selected_candidate": SELECTED_CANDIDATE_ID,
        "eligible_ids_sha256": EXPECTED_ELIGIBLE_IDS_SHA256,
        "manifest_sha256": manifest_sha256,
        "sensitivity_references": len(sensitivity_rows),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
