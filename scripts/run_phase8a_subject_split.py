"""Create or verify the single official Phase 8A public subject split and seal."""

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
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.split_guard import (  # noqa: E402
    SplitGuard,
    seal_payload_sha256,
)
from vitaldb_state_selection.cohort.subject_split import (  # noqa: E402
    ALLOCATION_METHOD,
    EXPECTED_CASE_COUNT,
    EXPECTED_SUBJECT_COUNT,
    SOURCE_COHORT_PROTOCOL_VERSION,
    SOURCE_COLUMNS_USED,
    SOURCE_FINAL_COHORT_SHA256,
    SOURCE_SUBJECT_LINKAGE_FILE_SHA256,
    SPLIT_MANIFEST_VERSION,
    SPLIT_SEED,
    STARTING_COMMIT,
    STUDY_PROTOCOL_VERSION,
    TEST_SUBJECT_TARGET,
    TRAIN_SUBJECT_TARGET,
    allocate_subjects,
    build_case_split_rows,
    build_metadata_balance,
    build_subject_rows,
    identifier_rows,
    sorted_identifier_sha256,
)


MANIFESTS = ROOT / "data" / "manifests"
LEGACY_ROOT = ROOT.parent / "VitalDB-Feature-Selection"
SOURCE_CASE_MANIFEST = MANIFESTS / "subject_linkage_case_manifest.csv"
EXPECTED_LEGACY_HEAD = "9501b16a5c4db27f06fa0d0b252a3a75f633967f"
EXPECTED_LEGACY_TREE = "60917f0b61ec1e6a195b9a648faa6466406aeda1"
EXPECTED_LEGACY_STATUS = ["?? debug.log"]

SUBJECT_FIELDS = (
    "subjectid", "assigned_split", "sex_group", "subject_age_median",
    "age_minimum", "age_maximum", "age_range", "subject_age_group",
    "subject_age_group_distinct_count", "subject_age_group_span_warning",
    "subject_height_median_cm", "height_minimum_cm", "height_maximum_cm",
    "height_range_cm", "subject_weight_median_kg", "weight_minimum_kg",
    "weight_maximum_kg", "weight_range_kg", "subject_case_count",
    "subject_case_count_band", "stratum_key", "stratum_subject_count",
    "stratum_test_quota", "allocation_rank_sha256", "within_stratum_rank",
    "split_seed", "allocation_method", "source_cohort_protocol_version",
    "study_protocol_version", "split_manifest_version",
)
CASE_FIELDS = (
    "caseid", "subjectid", "assigned_split", "source_final_cohort_checksum",
    "source_subject_linkage_checksum", "source_cohort_protocol_version",
    "study_protocol_version", "split_manifest_version",
)

OUTPUT_PATHS = (
    MANIFESTS / "phase8a_split_human_decisions.json",
    MANIFESTS / "phase8a_stratum_allocation.csv",
    MANIFESTS / "phase8a_subject_split_manifest.csv",
    MANIFESTS / "phase8a_case_split_manifest.csv",
    MANIFESTS / "phase8a_train_subject_ids.csv",
    MANIFESTS / "phase8a_test_subject_ids.csv",
    MANIFESTS / "phase8a_train_case_ids.csv",
    MANIFESTS / "phase8a_test_case_ids.csv",
    MANIFESTS / "phase8a_metadata_balance_table.csv",
    MANIFESTS / "phase8a_metadata_balance_summary.json",
    MANIFESTS / "phase8a_test_seal.json",
    MANIFESTS / "phase8a_source_snapshot.json",
    ROOT / "docs" / "phase8a_split_decision_record.md",
    ROOT / "docs" / "phase8a_report.md",
)

SOURCE_ARTIFACT_PATHS = (
    "data/manifests/protocol_v1_2_cohort_freeze.json",
    "data/manifests/protocol_v1_2_artifact_checksums.json",
    "data/manifests/subject_linkage_case_manifest.csv",
    "data/manifests/subject_level_cluster_summary.csv",
    "data/manifests/within_subject_metadata_consistency.csv",
    "data/manifests/subject_linkage_summary.json",
    "data/manifests/subject_linkage_source_snapshot.json",
    "data/manifests/subject_linkage_artifact_checksums.json",
    "data/manifests/protocol_v1_3_planned_subject_split.json",
    "data/manifests/phase7f_artifact_checksums.json",
    "data/manifests/phase7g_artifact_checksums.json",
    "data/manifests/phase7h_artifact_checksums.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 8A subject split and integrity seal")
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True, stderr=subprocess.DEVNULL
    ).strip()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def csv_value(value: object) -> object:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return ""
    return value


def csv_bytes(rows: list[dict[str, object]], fields: tuple[str, ...] | None = None) -> bytes:
    if not rows:
        raise RuntimeError("refusing to serialize empty CSV")
    fieldnames = list(fields or tuple(rows[0]))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: csv_value(row.get(field)) for field in fieldnames})
    return stream.getvalue().encode("utf-8")


def read_source_case_rows() -> list[dict[str, str]]:
    if sha256_path(SOURCE_CASE_MANIFEST) != SOURCE_SUBJECT_LINKAGE_FILE_SHA256:
        raise RuntimeError("Phase 7A subject-linkage source checksum mismatch")
    with SOURCE_CASE_MANIFEST.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or not SOURCE_COLUMNS_USED.issubset(reader.fieldnames):
            raise RuntimeError("subject-linkage source does not satisfy the explicit column allowlist")
        return [{column: row[column] for column in SOURCE_COLUMNS_USED} for row in reader]


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


def verify_inventory(path: Path) -> int:
    inventory = json.loads(path.read_text(encoding="utf-8"))
    entries = inventory.get("artifacts") if isinstance(inventory, dict) else None
    if entries is None:
        entries = [{"relative_path": relative, "sha256": expected} for relative, expected in inventory.items()]
    for entry in entries:
        artifact = ROOT / entry["relative_path"]
        if not artifact.is_file() or sha256_path(artifact) != entry["sha256"]:
            raise RuntimeError(f"source artifact checksum mismatch: {entry['relative_path']}")
        if "bytes" in entry and artifact.stat().st_size != int(entry["bytes"]):
            raise RuntimeError(f"source artifact byte-count mismatch: {entry['relative_path']}")
    return len(entries)


def legacy_state() -> dict[str, object]:
    safe = LEGACY_ROOT.resolve().as_posix()
    command = ["git", "-c", f"safe.directory={safe}", "-C", str(LEGACY_ROOT)]
    legacy_commit = subprocess.check_output([*command, "rev-parse", "HEAD"], text=True).strip()
    tree = subprocess.check_output([*command, "rev-parse", "HEAD^{tree}"], text=True).strip()
    status = subprocess.check_output([*command, "status", "--short"], text=True).splitlines()
    state = {"head": legacy_commit, "tree": tree, "status_short": status}
    if state != {
        "head": EXPECTED_LEGACY_HEAD,
        "tree": EXPECTED_LEGACY_TREE,
        "status_short": EXPECTED_LEGACY_STATUS,
    }:
        raise RuntimeError("legacy repository state differs from the approved read-only baseline")
    return state


def verify_source_gate() -> dict[str, object]:
    if git_output(ROOT, "rev-parse", "HEAD") != STARTING_COMMIT:
        raise RuntimeError("Phase 8A starting HEAD mismatch")
    if git_output(ROOT, "rev-parse", "refs/remotes/origin/main") != STARTING_COMMIT:
        raise RuntimeError("Phase 8A starting remote-tracking ref mismatch")

    freeze = json.loads((MANIFESTS / "protocol_v1_2_cohort_freeze.json").read_text(encoding="utf-8"))
    linkage = json.loads((MANIFESTS / "subject_linkage_summary.json").read_text(encoding="utf-8"))
    planned = json.loads((MANIFESTS / "protocol_v1_3_planned_subject_split.json").read_text(encoding="utf-8"))
    if not (
        freeze.get("cohort_frozen") is True
        and freeze.get("protocol_version") == SOURCE_COHORT_PROTOCOL_VERSION
        and freeze.get("eligible_case_count") == EXPECTED_CASE_COUNT
        and freeze.get("full_cohort_manifest_sha256") == SOURCE_FINAL_COHORT_SHA256
    ):
        raise RuntimeError("Protocol v1.2 frozen cohort gate failed")
    expected_linkage = {
        "total_case_count": EXPECTED_CASE_COUNT,
        "unique_subject_count": EXPECTED_SUBJECT_COUNT,
        "subjectid_missing_count": 0,
        "subjectid_parsing_failure_count": 0,
        "caseid_duplicate_count": 0,
        "case_to_subject_ambiguity_count": 0,
        "ineligible_overlap_count": 0,
        "assigned_split_nonblank_count": 0,
        "split_created": False,
        "test_seal_created": False,
    }
    if any(linkage.get(key) != value for key, value in expected_linkage.items()):
        raise RuntimeError("Phase 7A linkage/accounting gate failed")
    if not (
        planned.get("split_created") is False
        and planned.get("test_seal_created") is False
        and planned.get("target_train_subject_count") == TRAIN_SUBJECT_TARGET
        and planned.get("target_test_subject_count") == TEST_SUBJECT_TARGET
        and planned.get("validation_split") is False
    ):
        raise RuntimeError("Protocol v1.3 planned split gate failed")

    inventory_counts = {
        "protocol_v1_2_artifact_checksums.json": verify_inventory(MANIFESTS / "protocol_v1_2_artifact_checksums.json"),
        "subject_linkage_artifact_checksums.json": verify_inventory(MANIFESTS / "subject_linkage_artifact_checksums.json"),
        "phase7f_artifact_checksums.json": verify_inventory(MANIFESTS / "phase7f_artifact_checksums.json"),
        "phase7g_artifact_checksums.json": verify_inventory(MANIFESTS / "phase7g_artifact_checksums.json"),
        "phase7h_artifact_checksums.json": verify_inventory(MANIFESTS / "phase7h_artifact_checksums.json"),
    }
    tracked = git_output(ROOT, "ls-files").splitlines()
    forbidden = [
        path for path in tracked
        if path.startswith(("data/raw/", "data/modeling/", "checkpoints/"))
        or (path.startswith("outputs/") and path != "outputs/.gitkeep")
        or Path(path).suffix.lower() in {".npy", ".npz", ".pt", ".pth", ".ckpt", ".parquet"}
    ]
    if forbidden:
        raise RuntimeError(f"raw/model/checkpoint paths are tracked: {forbidden}")
    if git_output(ROOT, "check-ignore", ".venv-phase7h") != ".venv-phase7h":
        raise RuntimeError(".venv-phase7h is not ignored")
    return {"inventory_counts": inventory_counts, "legacy_state": legacy_state()}


def decision_artifact() -> dict[str, object]:
    return {
        "phase": "Phase 8A",
        "source_cohort_protocol_version": SOURCE_COHORT_PROTOCOL_VERSION,
        "study_protocol_version": STUDY_PROTOCOL_VERSION,
        "source_remote_commit": STARTING_COMMIT,
        "split_manifest_version": SPLIT_MANIFEST_VERSION,
        "split_unit": "subjectid",
        "train_fraction": 0.80,
        "train_subject_count": TRAIN_SUBJECT_TARGET,
        "test_fraction": 0.20,
        "test_subject_count": TEST_SUBJECT_TARGET,
        "validation_split": False,
        "split_seed": SPLIT_SEED,
        "allocation_method": ALLOCATION_METHOD,
        "strata": "sex_group|repository_defined_subject_age_group|subject_case_count_band",
        "subject_metadata_aggregation": "deterministic_median_with_minimum_maximum_and_range_retained",
        "alternate_seed_search": "prohibited",
        "outcome_use": False,
        "raw_signal_use": False,
        "all_four_conditions_use_same_membership": True,
        "test_membership_publication": "deidentified_public_metadata",
        "seal_purpose": "integrity_not_secrecy",
        "membership_change_requirement": "new_human_approved_protocol_amendment",
    }


def decision_record() -> str:
    return """# Phase 8A Split Decision Record

## Authority and lineage

This human-approved decision uses the frozen Protocol v1.2 cohort while the
current reconstruction study protocol remains v1.3.2. The split artifact has
its own version, `phase8a-v1`; neither prior protocol artifact is modified.

## Fixed allocation

- Unit: exact public VitalDB `subjectid`.
- Targets: 1,932 train and 483 test subjects; no validation split.
- Strata: sex × repository-defined subject age group × subject case-count band.
- Quotas: exact 1/5 Hamilton largest remainder with canonical stratum tie order.
- Rank: SHA-256 of `20260720\\0{stratum_key}\\0{exact_subjectid}`.
- All cases follow their parent subject and all four P0/P1 × S0/S1 conditions
  use the same membership.

No alternate seed, balance optimization, outcome, signal, observation template,
normalization, simulator run, PPO run, or checkpoint is permitted. Membership
changes require a new human-approved protocol amendment. The public test seal is
an integrity mechanism, not secrecy.
"""


def report_text(summary: dict[str, object], subject_counts: Counter[str], case_counts: Counter[str], seal_hash: str) -> str:
    return f"""# Phase 8A Outcome-Blind Subject Split Report

## Result

- Subjects: {sum(subject_counts.values())} total; {subject_counts['train']} train;
  {subject_counts['test']} test.
- Cases: {sum(case_counts.values())} total; {case_counts['train']} train;
  {case_counts['test']} test.
- Subject overlap: 0; case overlap: 0; case-to-parent split mismatch: 0.
- Allocation: `{ALLOCATION_METHOD}`, seed `{SPLIT_SEED}`.
- Maximum absolute primary continuous SMD:
  `{summary['maximum_absolute_primary_continuous_smd']}`.
- Balance warnings: {summary['balance_warning_count_total']}.
- Test seal payload SHA-256: `{seal_hash}`.

Membership was fixed before balance calculation. Warnings did not trigger a
retry, alternate seed, changed strata, or changed membership. Secondary
case-level metadata is descriptive only.

## Boundary

No raw signal, outcome, observation template, preprocessing array, scaler,
real-subject simulator, PPO training/evaluation, model, or checkpoint was read or
created. Phase 8B and later work did not begin.
"""


def build_outputs(created_timestamp: str) -> tuple[dict[Path, bytes], dict[str, object]]:
    gate = verify_source_gate()
    case_source_rows = read_source_case_rows()
    subject_source_rows = build_subject_rows(case_source_rows)
    subject_rows, stratum_rows = allocate_subjects(subject_source_rows)
    case_rows = build_case_split_rows(case_source_rows, subject_rows)
    train_subject_ids = identifier_rows(subject_rows, "subjectid", "train")
    test_subject_ids = identifier_rows(subject_rows, "subjectid", "test")
    train_case_ids = identifier_rows(case_rows, "caseid", "train")
    test_case_ids = identifier_rows(case_rows, "caseid", "test")
    balance_rows, balance_summary = build_metadata_balance(subject_rows, case_source_rows, case_rows)

    subject_payload = csv_bytes(subject_rows, SUBJECT_FIELDS)
    case_payload = csv_bytes(case_rows, CASE_FIELDS)
    stratum_payload = csv_bytes(stratum_rows)
    balance_payload = csv_bytes(balance_rows)
    id_payloads = {
        "train_subject": csv_bytes(train_subject_ids, ("subjectid",)),
        "test_subject": csv_bytes(test_subject_ids, ("subjectid",)),
        "train_case": csv_bytes(train_case_ids, ("caseid",)),
        "test_case": csv_bytes(test_case_ids, ("caseid",)),
    }
    subject_counts = Counter(str(row["assigned_split"]) for row in subject_rows)
    case_counts = Counter(str(row["assigned_split"]) for row in case_rows)

    seal: dict[str, object] = {
        "seal_version": "phase8a-test-seal-v1",
        "phase": "Phase 8A",
        "source_cohort_protocol_version": SOURCE_COHORT_PROTOCOL_VERSION,
        "study_protocol_version": STUDY_PROTOCOL_VERSION,
        "split_manifest_version": SPLIT_MANIFEST_VERSION,
        "source_remote_commit_sha": STARTING_COMMIT,
        "split_seed": SPLIT_SEED,
        "allocation_method": ALLOCATION_METHOD,
        "train_subject_count": subject_counts["train"],
        "test_subject_count": subject_counts["test"],
        "train_case_count": case_counts["train"],
        "test_case_count": case_counts["test"],
        "sha256_sorted_train_subject_ids": sorted_identifier_sha256(train_subject_ids, "subjectid"),
        "sha256_sorted_test_subject_ids": sorted_identifier_sha256(test_subject_ids, "subjectid"),
        "sha256_sorted_train_case_ids": sorted_identifier_sha256(train_case_ids, "caseid"),
        "sha256_sorted_test_case_ids": sorted_identifier_sha256(test_case_ids, "caseid"),
        "sha256_full_subject_split_manifest": hashlib.sha256(subject_payload).hexdigest(),
        "sha256_full_case_split_manifest": hashlib.sha256(case_payload).hexdigest(),
        "sha256_stratum_allocation": hashlib.sha256(stratum_payload).hexdigest(),
        "sha256_metadata_balance_table": hashlib.sha256(balance_payload).hexdigest(),
        "source_subject_linkage_sha256": SOURCE_SUBJECT_LINKAGE_FILE_SHA256,
        "source_frozen_cohort_sha256": SOURCE_FINAL_COHORT_SHA256,
        "creation_timestamp_utc": created_timestamp,
        "split_generation_count": 1,
        "same_membership_for_all_four_conditions": True,
        "membership_public": True,
        "seal_purpose": "integrity_not_secrecy",
        "test_raw_accessed": False,
        "test_template_created": False,
        "test_outcome_accessed": False,
        "ppo_tuned_on_test": False,
        "ppo_trained": False,
        "alternate_seed_search_performed": False,
        "balance_optimized_seed_selection": False,
        "regeneration_requires_human_approved_protocol_amendment": True,
    }
    seal["seal_payload_sha256"] = seal_payload_sha256(seal)

    source_hashes = {relative: sha256_path(ROOT / relative) for relative in SOURCE_ARTIFACT_PATHS}
    source_snapshot = {
        "phase": "Phase 8A",
        "created_timestamp_utc": created_timestamp,
        "starting_local_head": STARTING_COMMIT,
        "starting_remote_tracking_main": STARTING_COMMIT,
        "source_commit_verified": True,
        "source_worktree_clean": True,
        "source_index_clean": True,
        "source_artifact_sha256": source_hashes,
        "protocol_v1_2_cohort_freeze_verified": True,
        "phase7a_subject_linkage_verified": True,
        "protocol_v1_3_planned_split_verified": True,
        "phase7f_checksum_inventory_verified": True,
        "phase7g_checksum_inventory_verified": True,
        "phase7h_checksum_inventory_verified": True,
        "source_inventory_entry_counts": gate["inventory_counts"],
        "case_count": EXPECTED_CASE_COUNT,
        "subject_count": EXPECTED_SUBJECT_COUNT,
        "train_subject_target": TRAIN_SUBJECT_TARGET,
        "test_subject_target": TEST_SUBJECT_TARGET,
        "assigned_split_count_before_phase8a": 0,
        "existing_test_seal_before_phase8a": False,
        "raw_signal_file_open_count": 0,
        "api_request_count": 0,
        "outcome_access_count": 0,
        "observation_template_created": False,
        "preprocessing_array_created": False,
        "normalization_fitted": False,
        "simulator_real_subject_run": False,
        "ppo_training_run": False,
        "ppo_evaluation_run": False,
        "checkpoint_created": False,
        "alternate_seed_search_performed": False,
        "dependency_change": False,
        "raw_model_checkpoint_git_tracking_count": 0,
        "legacy_state_before": gate["legacy_state"],
        "legacy_state_after": gate["legacy_state"],
        "legacy_state_unchanged": True,
        "previous_phase_artifacts_unchanged": True,
    }

    outputs = {
        MANIFESTS / "phase8a_split_human_decisions.json": json_bytes(decision_artifact()),
        MANIFESTS / "phase8a_stratum_allocation.csv": stratum_payload,
        MANIFESTS / "phase8a_subject_split_manifest.csv": subject_payload,
        MANIFESTS / "phase8a_case_split_manifest.csv": case_payload,
        MANIFESTS / "phase8a_train_subject_ids.csv": id_payloads["train_subject"],
        MANIFESTS / "phase8a_test_subject_ids.csv": id_payloads["test_subject"],
        MANIFESTS / "phase8a_train_case_ids.csv": id_payloads["train_case"],
        MANIFESTS / "phase8a_test_case_ids.csv": id_payloads["test_case"],
        MANIFESTS / "phase8a_metadata_balance_table.csv": balance_payload,
        MANIFESTS / "phase8a_metadata_balance_summary.json": json_bytes(balance_summary),
        MANIFESTS / "phase8a_test_seal.json": json_bytes(seal),
        MANIFESTS / "phase8a_source_snapshot.json": json_bytes(source_snapshot),
        ROOT / "docs" / "phase8a_split_decision_record.md": decision_record().encode("utf-8"),
        ROOT / "docs" / "phase8a_report.md": report_text(
            balance_summary, subject_counts, case_counts, str(seal["seal_payload_sha256"])
        ).encode("utf-8"),
    }
    result = {
        "subjects": dict(subject_counts),
        "cases": dict(case_counts),
        "maximum_absolute_primary_smd": balance_summary["maximum_absolute_primary_continuous_smd"],
        "balance_warnings": balance_summary["balance_warning_count_total"],
        "subject_manifest_sha256": seal["sha256_full_subject_split_manifest"],
        "case_manifest_sha256": seal["sha256_full_case_split_manifest"],
        "seal_payload_sha256": seal["seal_payload_sha256"],
    }
    return outputs, result


def verify_existing() -> dict[str, object]:
    seal_path = MANIFESTS / "phase8a_test_seal.json"
    if not seal_path.is_file():
        raise RuntimeError("official Phase 8A seal does not exist")
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    expected, result = build_outputs(str(seal["creation_timestamp_utc"]))
    for path, payload in expected.items():
        if not path.is_file() or path.read_bytes() != payload:
            raise RuntimeError(f"Phase 8A artifact is not byte-identical: {path.relative_to(ROOT)}")
    inventory = MANIFESTS / "phase8a_artifact_checksums.json"
    if inventory.exists():
        SplitGuard.from_repository(ROOT)
    return result


def main() -> int:
    args = parse_args()
    if args.verify_only:
        print(json.dumps(verify_existing(), sort_keys=True))
        return 0
    existing = [path.relative_to(ROOT).as_posix() for path in OUTPUT_PATHS if path.exists()]
    if existing or (MANIFESTS / "phase8a_artifact_checksums.json").exists():
        raise RuntimeError(f"official Phase 8A artifact already exists; generation refused: {existing}")
    created_timestamp = datetime.now(UTC).isoformat()
    outputs, result = build_outputs(created_timestamp)
    for path, payload in outputs.items():
        atomic_bytes(path, payload)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
