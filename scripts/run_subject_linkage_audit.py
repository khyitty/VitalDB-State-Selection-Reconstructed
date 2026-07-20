"""Run Phase 7A subject linkage and patient-level split feasibility audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.subject_linkage import (  # noqa: E402
    EXPECTED_CLUSTER_SIZE_COUNTS,
    EXPECTED_SUBJECT_COUNT,
    PHASE,
    PROTOCOL_VERSION,
    SOURCE_ELIGIBLE_COUNT,
    SOURCE_ELIGIBLE_IDS_SHA256,
    SOURCE_FINAL_COHORT_SHA256,
    SOURCE_PHASE6D_FOLLOWUP,
    SUBJECTID_DOCUMENTED_MEANING,
    build_subject_cluster_rows,
    build_subject_linkage_case_manifest,
    count_only_split_feasibility,
    repeated_subject_distribution,
    sorted_caseid_checksum,
    subject_accounting,
    subject_linkage_checksum,
)


MANIFESTS = ROOT / "data" / "manifests"
RAW_ROOT = ROOT / "data" / "raw" / "phase6a_primary_signals"
LEGACY_ROOT = ROOT.parent / "VitalDB-Feature-Selection"
REPORT = ROOT / "docs" / "phase7a_subject_linkage_audit_report.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 7A subject-linkage feasibility audit")
    parser.add_argument("--verify-only", action="store_true")
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
    if value is None:
        return ""
    return value


def csv_bytes(rows: list[dict[str, object]]) -> bytes:
    if not rows:
        raise RuntimeError("refusing to serialize empty CSV")
    fields = list(rows[0])
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
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def git_output(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def legacy_state() -> dict[str, object]:
    safe = LEGACY_ROOT.resolve().as_posix()

    def legacy_git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-c", f"safe.directory={safe}", "-C", str(LEGACY_ROOT), *args],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()

    return {
        "head": legacy_git("rev-parse", "HEAD"),
        "tree": legacy_git("rev-parse", "HEAD^{tree}"),
        "status_short": legacy_git("status", "--short").splitlines(),
    }


def raw_tree_state() -> dict[str, object]:
    files = sorted(path for path in RAW_ROOT.rglob("*") if path.is_file())
    entries = [f"{path.relative_to(RAW_ROOT).as_posix()}\t{path.stat().st_size}" for path in files]
    return {
        "file_count": len(files),
        "total_bytes": sum(path.stat().st_size for path in files),
        "partial_file_count": sum(path.suffix in {".part", ".partial", ".tmp"} for path in files),
        "relative_path_and_size_fingerprint_sha256": hashlib.sha256(
            ("\n".join(entries) + "\n").encode()
        ).hexdigest(),
    }


def verify_source() -> dict[str, object]:
    current = git_output(ROOT, "rev-parse", "HEAD")
    remote_tracking = git_output(ROOT, "rev-parse", "refs/remotes/origin/main")
    if current != SOURCE_PHASE6D_FOLLOWUP or remote_tracking != SOURCE_PHASE6D_FOLLOWUP:
        raise RuntimeError("Phase 7A must start at the verified Phase 6D follow-up")
    freeze = json.loads((MANIFESTS / "protocol_v1_2_cohort_freeze.json").read_text(encoding="utf-8"))
    if freeze["protocol_version"] != PROTOCOL_VERSION or freeze["cohort_frozen"] is not True:
        raise RuntimeError("Protocol v1.2 cohort is not frozen")
    if freeze["eligible_case_count"] != SOURCE_ELIGIBLE_COUNT:
        raise RuntimeError("source eligible count mismatch")
    if freeze["sorted_eligible_case_ids_sha256"] != SOURCE_ELIGIBLE_IDS_SHA256:
        raise RuntimeError("source eligible checksum mismatch")
    if freeze["full_cohort_manifest_sha256"] != SOURCE_FINAL_COHORT_SHA256:
        raise RuntimeError("source final cohort manifest checksum mismatch")
    phase6d_inventory = json.loads(
        (MANIFESTS / "protocol_v1_2_artifact_checksums.json").read_text(encoding="utf-8")
    )
    for relative, expected in phase6d_inventory.items():
        if sha256_path(ROOT / relative) != expected:
            raise RuntimeError(f"Phase 6D artifact checksum mismatch: {relative}")
    return freeze


def balance_variable_definitions() -> dict[str, object]:
    return {
        "schema_version": 1,
        "purpose": "future_patient_level_marginal_balance_inventory_not_allocation",
        "subject_allocation_rule": (
            "Every subject must move with the sum of all case-level marginal contribution vectors; "
            "do not collapse a subject to one operation type or mean ASA."
        ),
        "variables": {
            "sex": {
                "source_field": "sex", "groups": ["male", "female", "missing_or_other"],
                "mapping": {"M": "male", "F": "female", "other_or_missing": "missing_or_other"},
            },
            "age_group": {
                "source_field": "age",
                "groups": ["18_to_lt_40", "40_to_lt_60", "60_to_lt_75", "ge_75", "missing_or_invalid"],
            },
            "bmi_group": {
                "source_fields": ["height", "weight"],
                "formula": "weight_kg / (height_cm / 100) ** 2",
                "groups": ["lt_18_5", "18_5_to_lt_25", "25_to_lt_30", "ge_30", "missing_or_invalid"],
                "eligibility_role": False,
                "model_feature_role": False,
            },
            "asa_group": {
                "source_field": "asa",
                "groups": ["ASA_1", "ASA_2", "ASA_3", "ASA_4_or_higher", "missing_or_other"],
            },
            "emergency_group": {
                "source_field": "emergency_status",
                "groups": ["non_emergency", "emergency", "missing_or_other"],
            },
            "operation_type_group": {
                "source_field": "operation_type",
                "rule": "exact source category; blank only becomes missing_or_other; no semantic regrouping",
            },
        },
    }


def alternative_rows() -> list[dict[str, object]]:
    return [
        {
            "alternative": "A_case_count_prioritized",
            "subject_groups_indivisible": True,
            "primary_objective": "minimize deviation from 70/15/15 case counts",
            "secondary_reporting": "subject-count ratios",
            "metadata_marginal_balance_future_objective": False,
            "advantage": "closest control of case counts",
            "limitation": "subject-count ratios and metadata marginals may deviate",
            "selected": False, "allocation_executed": False,
        },
        {
            "alternative": "B_subject_count_prioritized",
            "subject_groups_indivisible": True,
            "primary_objective": "minimize deviation from 70/15/15 subject counts",
            "secondary_reporting": "case-count ratios",
            "metadata_marginal_balance_future_objective": False,
            "advantage": "closest control of subject counts",
            "limitation": "case counts may deviate because clusters are indivisible",
            "selected": False, "allocation_executed": False,
        },
        {
            "alternative": "C_joint_case_subject_balance",
            "subject_groups_indivisible": True,
            "primary_objective": "joint case-count and subject-count deviation",
            "secondary_reporting": "both ratios and future case-level marginal contributions",
            "metadata_marginal_balance_future_objective": True,
            "advantage": "can trade off both count scales and metadata marginals",
            "limitation": "requires predeclared weights and tie-breaking before allocation",
            "selected": False, "allocation_executed": False,
        },
    ]


def render_report(
    accounting: dict[str, object],
    distribution: list[dict[str, object]],
    consistency_rows: list[dict[str, object]],
    feasibility: dict[str, object],
    linkage_sha256: str,
) -> str:
    size_rows = "\n".join(
        f"| {row['cluster_size']} | {row['subject_count']} | {row['case_count']} |"
        for row in distribution
    )
    sex_warnings = sum(bool(row["sex_inconsistency_warning"]) for row in consistency_rows)
    return f"""# Phase 7A Subject Linkage and Patient-Level Split Feasibility Audit

## Boundary

This is an outcome-blind metadata-only linkage and count-feasibility audit. It
creates no train/validation/test membership, provisional split, ID list, test
seal, raw read, modeling array, preprocessing fit, or downstream analysis.

`subjectid` is used only because the official VitalDB parameter definition is
“{SUBJECTID_DOCUMENTED_MEANING}”. No re-identification or external linkage was
attempted. Subject IDs are retained only in versioned manifests and are not
listed in this report.

## Source verification

- Frozen eligible cases: {accounting['total_case_count']}.
- Eligible case-ID checksum: `{SOURCE_ELIGIBLE_IDS_SHA256}`.
- Subject-linkage checksum: `{linkage_sha256}`.
- Missing or unparsable subject IDs: 0.
- Duplicate or ambiguous case-to-subject mappings: 0.
- Ineligible-case overlap: 0.

## Subject-level accounting

- Unique subjects: {accounting['unique_subject_count']}.
- Repeated subjects: {accounting['repeated_subject_count']}.
- Cases belonging to repeated subjects: {accounting['repeated_subject_case_count']}
  ({accounting['repeated_subject_case_proportion']:.6%} of cases).
- Largest subject cluster: {accounting['largest_subject_cluster_case_count']} cases.

| Cluster size | Subjects | Cases |
|---:|---:|---:|
{size_rows}

The cases-per-subject distribution and quantiles are machine-readable in the
summary JSON. Exact subject IDs appear only in the linkage and subject-level
manifests.

## Within-subject consistency

Exact-source sex inconsistency warnings: {sex_warnings}. Warnings are preserved
without correcting linkage. Age, height, weight, BMI, ASA, emergency status, and
operation type are described as potentially time-varying case metadata and do
not invalidate linkage.

## Count-only feasibility

- Nearest case targets: train {feasibility['case_count_targets']['train']['nearest_integer']},
  validation {feasibility['case_count_targets']['validation']['nearest_integer']},
  test {feasibility['case_count_targets']['test']['nearest_integer']}.
- Nearest subject targets: train {feasibility['subject_count_targets']['train']['nearest_integer']},
  validation {feasibility['subject_count_targets']['validation']['nearest_integer']},
  test {feasibility['subject_count_targets']['test']['nearest_integer']}.
- Exact nearest case targets are arithmetically feasible from the cluster-size
  histogram: {str(feasibility['exact_case_targets_arithmetically_feasible']).lower()}.
- Exact joint nearest case and subject targets are arithmetically feasible:
  {str(feasibility['exact_joint_nearest_case_and_subject_targets_arithmetically_feasible']).lower()}.
- Minimum total absolute case-count deviation under nearest subject targets:
  {feasibility['minimum_total_absolute_case_count_deviation_under_nearest_subject_targets']}.

These are count-only facts. No subject or case was assigned to a split. The three
future objective alternatives remain unselected.

## Future metadata inventory

Future subject-level allocation must move every subject with the sum of all its
case-level sex, age-group, BMI-group, ASA-group, emergency-group, and exact
operation-type marginal contributions. A subject must not be collapsed to one
operation type or mean ASA.

## Stop boundary

Phase 7B patient-level allocation is not authorized. No outcome, BIS, SQI, drug
rate, raw signal, API, normalization, imputation, dose, Cp/Ce, persistence,
prediction, feature selection, model, test seal, or PPO operation occurred.
"""


def verify_existing() -> dict[str, object]:
    inventory = json.loads(
        (MANIFESTS / "subject_linkage_artifact_checksums.json").read_text(encoding="utf-8")
    )
    for relative, expected in inventory.items():
        if sha256_path(ROOT / relative) != expected:
            raise RuntimeError(f"Phase 7A artifact checksum mismatch: {relative}")
    summary = json.loads((MANIFESTS / "subject_linkage_summary.json").read_text(encoding="utf-8"))
    if summary["total_case_count"] != SOURCE_ELIGIBLE_COUNT:
        raise RuntimeError("Phase 7A case count mismatch")
    if summary["unique_subject_count"] != EXPECTED_SUBJECT_COUNT:
        raise RuntimeError("Phase 7A subject count mismatch")
    if summary["split_created"] is not False:
        raise RuntimeError("Phase 7A must not contain a split")
    return summary


def main() -> int:
    args = parse_args()
    if args.verify_only:
        print(json.dumps(verify_existing(), sort_keys=True))
        return 0

    freeze = verify_source()
    raw_before = raw_tree_state()
    legacy_before = legacy_state()
    if raw_before["partial_file_count"] != 0:
        raise RuntimeError("raw partial file exists before Phase 7A")

    source_paths = (
        ROOT / "docs" / "protocol_v1_2_decision_record.md",
        MANIFESTS / "protocol_v1_2_cohort_freeze.json",
        MANIFESTS / "final_eligible_cohort_manifest.csv",
        MANIFESTS / "final_eligible_caseids.csv",
        MANIFESTS / "final_ineligible_caseids.csv",
        MANIFESTS / "all_case_eligibility_manifest.csv",
        MANIFESTS / "metadata_audit_source_snapshot.json",
        MANIFESTS / "metadata_audit_artifact_checksums.json",
        MANIFESTS / "eligibility_decision_support_source_snapshot.json",
        MANIFESTS / "protocol_v1_2_artifact_checksums.json",
        MANIFESTS / "protocol_v1_2_source_snapshot.json",
    )
    source_checksums = {path.relative_to(ROOT).as_posix(): sha256_path(path) for path in source_paths}
    if source_checksums["data/manifests/final_eligible_cohort_manifest.csv"] != SOURCE_FINAL_COHORT_SHA256:
        raise RuntimeError("final cohort manifest checksum mismatch")

    eligible_rows = read_csv(MANIFESTS / "final_eligible_caseids.csv")
    eligible_caseids = [int(row["caseid"]) for row in eligible_rows]
    if sorted_caseid_checksum(eligible_caseids) != SOURCE_ELIGIBLE_IDS_SHA256:
        raise RuntimeError("eligible ID checksum mismatch")
    final_manifest = read_csv(MANIFESTS / "final_eligible_cohort_manifest.csv")
    final_ineligible = {int(row["caseid"]) for row in final_manifest if row["final_eligible"] == "false"}
    if len(final_ineligible) != 10 or final_ineligible & set(eligible_caseids):
        raise RuntimeError("final ineligible cases entered Phase 7A universe")
    for row in final_manifest:
        if row["legacy_98_overlap"] != "false" or row["volatile_excluded_overlap"] != "false":
            raise RuntimeError("inherited legacy or volatile exclusion mismatch")
        if row["invalid_anesthesia_window_overlap"] != "false":
            raise RuntimeError("inherited invalid-window exclusion mismatch")

    metadata = read_csv(MANIFESTS / "all_case_eligibility_manifest.csv")
    if not metadata or "subjectid" not in metadata[0]:
        raise RuntimeError("versioned metadata snapshot lacks subjectid")
    linkage_rows = build_subject_linkage_case_manifest(eligible_caseids, metadata)
    clusters, consistency = build_subject_cluster_rows(linkage_rows)
    distribution = repeated_subject_distribution(clusters)
    accounting = subject_accounting(clusters)
    feasibility = count_only_split_feasibility(clusters)
    linkage_sha256 = subject_linkage_checksum(linkage_rows)
    sex_warning_count = sum(bool(row["sex_inconsistency_warning"]) for row in consistency)
    created_at = datetime.now(UTC).isoformat()
    accounting.update({
        "schema_version": 1,
        "phase": PHASE,
        "protocol_version": PROTOCOL_VERSION,
        "source_phase6d_followup": SOURCE_PHASE6D_FOLLOWUP,
        "source_eligible_ids_sha256": SOURCE_ELIGIBLE_IDS_SHA256,
        "source_final_cohort_sha256": SOURCE_FINAL_COHORT_SHA256,
        "subject_linkage_sha256": linkage_sha256,
        "cluster_size_subject_counts": {str(key): value for key, value in EXPECTED_CLUSTER_SIZE_COUNTS.items()},
        "subjectid_missing_count": 0,
        "subjectid_parsing_failure_count": 0,
        "caseid_duplicate_count": 0,
        "case_to_subject_ambiguity_count": 0,
        "ineligible_overlap_count": 0,
        "sex_inconsistency_warning_subject_count": sex_warning_count,
        "split_created": False,
        "assigned_split_nonblank_count": 0,
        "test_seal_created": False,
        "outcome_access_count": 0,
        "raw_signal_access_count": 0,
        "api_request_count": 0,
        "new_raw_file_count": 0,
        "modeling_array_count": 0,
        "created_timestamp": created_at,
    })
    feasibility.update({
        "schema_version": 1,
        "phase": PHASE,
        "source_case_count": SOURCE_ELIGIBLE_COUNT,
        "source_subject_count": EXPECTED_SUBJECT_COUNT,
        "metadata_balance_used": False,
        "outcome_used": False,
        "raw_signal_used": False,
        "allocation_executed": False,
        "alternative_selected": False,
        "created_timestamp": created_at,
    })
    definitions = balance_variable_definitions()
    definitions["created_timestamp"] = created_at
    alternatives = alternative_rows()
    report = render_report(accounting, distribution, consistency, feasibility, linkage_sha256)

    raw_after = raw_tree_state()
    legacy_after = legacy_state()
    if raw_before != raw_after:
        raise RuntimeError("raw tree changed during Phase 7A")
    if legacy_before != legacy_after:
        raise RuntimeError("legacy repository changed during Phase 7A")
    tracked_raw = git_output(ROOT, "ls-files", "--", "data/raw").splitlines()
    if tracked_raw:
        raise RuntimeError("raw data entered Git tracking")
    source_snapshot = {
        "schema_version": 1,
        "phase": PHASE,
        "created_timestamp": created_at,
        "source_phase6d_followup": SOURCE_PHASE6D_FOLLOWUP,
        "phase6d_remote_sha_verified_before_phase7a": True,
        "source_artifact_sha256": source_checksums,
        "protocol_version": freeze["protocol_version"],
        "cohort_frozen": freeze["cohort_frozen"],
        "source_eligible_count": SOURCE_ELIGIBLE_COUNT,
        "source_eligible_ids_sha256": SOURCE_ELIGIBLE_IDS_SHA256,
        "subjectid_source_field": "subjectid",
        "subjectid_documented_meaning": SUBJECTID_DOCUMENTED_MEANING,
        "raw_tree_before": raw_before,
        "raw_tree_after": raw_after,
        "raw_tree_unchanged": True,
        "legacy_state_before": legacy_before,
        "legacy_state_after": legacy_after,
        "legacy_state_unchanged": True,
        "raw_signal_file_open_count": 0,
        "api_request_count": 0,
        "new_raw_file_count": 0,
        "outcome_access_count": 0,
        "split_created": False,
        "provisional_split_created": False,
        "split_id_list_created": False,
        "test_seal_created": False,
        "modeling_arrays_created": False,
        "preprocessing_statistics_fitted": False,
        "raw_git_tracking_count": 0,
        "first_n_sampling": False,
    }

    outputs: dict[Path, bytes] = {
        MANIFESTS / "subject_linkage_case_manifest.csv": csv_bytes(linkage_rows),
        MANIFESTS / "subject_level_cluster_summary.csv": csv_bytes(clusters),
        MANIFESTS / "repeated_subject_distribution.csv": csv_bytes(distribution),
        MANIFESTS / "within_subject_metadata_consistency.csv": csv_bytes(consistency),
        MANIFESTS / "subject_linkage_summary.json": json_bytes(accounting),
        MANIFESTS / "patient_level_split_feasibility_summary.json": json_bytes(feasibility),
        MANIFESTS / "alternative_split_objective_comparison.csv": csv_bytes(alternatives),
        MANIFESTS / "patient_level_balance_variable_definitions.json": json_bytes(definitions),
        MANIFESTS / "subject_linkage_source_snapshot.json": json_bytes(source_snapshot),
        REPORT: (report.rstrip() + "\n").encode(),
    }
    for path, payload in outputs.items():
        atomic_bytes(path, payload)
    inventory = {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(payload).hexdigest()
        for path, payload in outputs.items()
    }
    atomic_bytes(MANIFESTS / "subject_linkage_artifact_checksums.json", json_bytes(inventory))
    print(json.dumps({
        "cases": accounting["total_case_count"],
        "subjects": accounting["unique_subject_count"],
        "repeated_subject_cases": accounting["repeated_subject_case_count"],
        "largest_cluster": accounting["largest_subject_cluster_case_count"],
        "sex_warnings": sex_warning_count,
        "exact_joint_count_feasible": feasibility[
            "exact_joint_nearest_case_and_subject_targets_arithmetically_feasible"
        ],
        "split_created": False,
        "subject_linkage_sha256": linkage_sha256,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
