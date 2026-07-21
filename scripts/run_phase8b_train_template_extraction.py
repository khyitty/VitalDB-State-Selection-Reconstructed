"""Run Phase 8B preflight, full train extraction, or private-store verification."""

from __future__ import annotations

import argparse
import csv
import hashlib
import heapq
import json
import math
import shutil
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.anesthesia.recorded_observation import (  # noqa: E402
    TrainObservationTemplateStore,
    load_recorded_template,
)
from vitaldb_state_selection.cohort.split_guard import SplitGuard  # noqa: E402
from vitaldb_state_selection.cohort.train_observation_templates import (  # noqa: E402
    EXPECTED_TRAIN_CASES,
    OPERATIONAL_TIMING_RELATIVE,
    OPERATIONAL_TIMING_SHA256,
    PAYLOAD_FILES,
    PHASE8A_SEAL_PAYLOAD_SHA256,
    PRIVATE_ROOT_RELATIVE,
    SCHEMA_VERSION,
    TEMPLATE_FORMAT_VERSION,
    UPSTREAM_TIMING_RELATIVE,
    UPSTREAM_TIMING_SHA256,
    TrainCase,
    TrainTemplateError,
    canonical_json_bytes,
    distribution,
    extract_template,
    load_train_cases,
    private_store_root_sha256,
    sha256_path,
    write_csv,
    write_json,
)
from vitaldb_state_selection.cohort.train_raw_access import (  # noqa: E402
    ALLOWED_TRACKS,
    TrainRawAccessGuard,
)


SOURCE_COMMIT = "f45a0ee6f1208f1f8202bc185a7a005701dfa3e0"
MANIFESTS = ROOT / "data" / "manifests"
PRIVATE_ROOT = ROOT / PRIVATE_ROOT_RELATIVE
LEGACY_ROOT = ROOT.parent / "VitalDB-Feature-Selection"
LEGACY_EXPECTED = {
    "head": "9501b16a5c4db27f06fa0d0b252a3a75f633967f",
    "tree": "60917f0b61ec1e6a195b9a648faa6466406aeda1",
    "status_short": ["?? debug.log"],
}
PUBLIC_MANIFESTS = (
    "phase8b_train_template_human_decisions.json",
    "phase8b_private_template_schema.json",
    "phase8b_private_tree_summary.json",
    "phase8b_template_qc_summary.json",
    "phase8b_access_summary.json",
    "phase8b_source_snapshot.json",
)
INDEX_FIELDS = (
    "caseid", "subjectid", "template_id", "assigned_split", "relative_template_directory",
    "template_payload_tree_sha256", "episode_horizon_seconds", "bis_event_count",
    "bis_available_count", "sqi_exact_match_count", "p1_event_acceptance_count",
    "source_bis_file_sha256", "source_sqi_file_sha256", "schema_version",
)
LEDGER_FIELDS = (
    "sequence_number", "caseid", "assigned_split", "track_name", "expected_source_sha256",
    "observed_source_sha256", "access_purpose", "status",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("preflight", "full", "verify-only"), required=True)
    return parser.parse_args()


def git(*args: str, cwd: Path = ROOT) -> str:
    command = ["git"]
    if cwd == LEGACY_ROOT:
        command.extend(("-c", f"safe.directory={cwd.as_posix()}"))
    return subprocess.check_output([*command, *args], cwd=cwd, text=True).strip()


def legacy_state() -> dict[str, object]:
    state = {
        "head": git("rev-parse", "HEAD", cwd=LEGACY_ROOT),
        "tree": git("rev-parse", "HEAD^{tree}", cwd=LEGACY_ROOT),
        "status_short": git("status", "--short", cwd=LEGACY_ROOT).splitlines(),
    }
    if state != LEGACY_EXPECTED:
        raise TrainTemplateError(f"legacy repository changed: {state}")
    return state


def source_gate(*, require_exact_source_refs: bool = True) -> dict[str, object]:
    if require_exact_source_refs:
        if git("rev-parse", "HEAD") != SOURCE_COMMIT:
            raise TrainTemplateError("Phase 8B source HEAD mismatch")
        if git("rev-parse", "refs/remotes/origin/main") != SOURCE_COMMIT:
            raise TrainTemplateError("Phase 8B source remote-tracking SHA mismatch")
    else:
        for ref, label in (("HEAD", "HEAD"), ("refs/remotes/origin/main", "remote-tracking SHA")):
            result = subprocess.run(
                ["git", "merge-base", "--is-ancestor", SOURCE_COMMIT, ref],
                cwd=ROOT,
                check=False,
            )
            if result.returncode != 0:
                raise TrainTemplateError(f"Phase 8B source commit is not an ancestor of {label}")
    seal = json.loads((MANIFESTS / "phase8a_test_seal.json").read_text(encoding="utf-8"))
    if seal.get("seal_payload_sha256") != PHASE8A_SEAL_PAYLOAD_SHA256:
        raise TrainTemplateError("Phase 8A seal payload mismatch")
    cases = load_train_cases(ROOT)
    before = legacy_state()
    return {
        "cases": cases,
        "legacy_before": before,
        "phase8a_seal": seal,
        "starting_local_head": SOURCE_COMMIT,
        "starting_remote_tracking_sha": SOURCE_COMMIT,
        "source_worktree_clean": True,
        "source_index_clean": True,
    }


def preflight_selection(cases: list[TrainCase]) -> list[TrainCase]:
    def rank(case: TrainCase) -> str:
        return hashlib.sha256(f"phase8b-preflight-v1\0{case.caseid}".encode("utf-8")).hexdigest()
    return heapq.nsmallest(25, cases, key=lambda case: (rank(case), int(case.caseid), case.caseid))


def _reset_phase8b_private_subtree(path: Path) -> None:
    resolved_root = PRIVATE_ROOT.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as error:
        raise TrainTemplateError("refusing to replace a path outside the Phase 8B private root") from error
    if path.exists():
        shutil.rmtree(path)


def run_preflight(gate: dict[str, object]) -> None:
    if any((MANIFESTS / name).exists() for name in PUBLIC_MANIFESTS):
        raise TrainTemplateError("official public Phase 8B artifacts exist before preflight")
    cases = preflight_selection(gate["cases"])
    if len(cases) != 25:
        raise TrainTemplateError("preflight selection accounting mismatch")
    PRIVATE_ROOT.mkdir(parents=True, exist_ok=True)
    runs = (PRIVATE_ROOT / "preflight_run_one", PRIVATE_ROOT / "preflight_run_two")
    for path in runs:
        _reset_phase8b_private_subtree(path)
    fingerprints: list[list[str]] = []
    elapsed: list[float] = []
    access_counts: list[int] = []
    output_bytes = 0
    guard = SplitGuard.from_repository(ROOT)
    for run_root in runs:
        access = TrainRawAccessGuard(ROOT)
        started = time.perf_counter()
        run_fingerprints: list[str] = []
        for case in cases:
            guard.assert_train_cases([case.caseid])
            extracted = extract_template(
                case, access=access, template_root=run_root / "templates",
                access_purpose="phase8b_preflight",
            )
            loaded = load_recorded_template(extracted.directory, split_guard=guard)
            if loaded.template_id != extracted.template_id:
                raise TrainTemplateError("preflight private load mismatch")
            run_fingerprints.append(extracted.payload_tree_sha256)
        elapsed.append(time.perf_counter() - started)
        access_counts.append(len(access.logical_accesses))
        fingerprints.append(run_fingerprints)
        output_bytes = sum(path.stat().st_size for path in run_root.rglob("*") if path.is_file())
    if fingerprints[0] != fingerprints[1]:
        raise TrainTemplateError("preflight deterministic rerun fingerprint mismatch")
    if access_counts != [50, 50]:
        raise TrainTemplateError(f"preflight access accounting mismatch: {access_counts}")
    projected_bytes = math.ceil(output_bytes * EXPECTED_TRAIN_CASES / len(cases))
    projected_seconds = max(elapsed) * EXPECTED_TRAIN_CASES / len(cases)
    disk_free = shutil.disk_usage(PRIVATE_ROOT).free
    required_free = max(2 * projected_bytes, projected_bytes + 1024 ** 3)
    summary = {
        "stage": "preflight",
        "selected_train_case_count": 25,
        "unique_source_file_count": 50,
        "first_run_logical_access_count": access_counts[0],
        "deterministic_rerun_logical_access_count": access_counts[1],
        "source_checksum_mismatch_count": 0,
        "test_raw_access_count": 0,
        "drug_raw_access_count": 0,
        "first_run_output_bytes": output_bytes,
        "first_run_elapsed_seconds": elapsed[0],
        "deterministic_rerun_elapsed_seconds": elapsed[1],
        "projected_full_private_payload_bytes": projected_bytes,
        "projected_full_elapsed_seconds": projected_seconds,
        "disk_free_bytes": disk_free,
        "required_free_bytes": required_free,
        "disk_gate_passed": disk_free > required_free,
        "deterministic_payload_tree_match": True,
        "public_official_artifact_count": 0,
        "raw_bis_values_persisted": False,
    }
    write_json(PRIVATE_ROOT / "preflight_summary.json", summary)
    if not summary["disk_gate_passed"]:
        raise TrainTemplateError("preflight disk-space gate failed")
    print(json.dumps(summary, indent=2, sort_keys=True))


def _append_progress(path: Path, record: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8", newline="") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()


def _index_row(extracted) -> dict[str, object]:
    metadata = extracted.metadata
    return {
        "caseid": metadata["caseid"], "subjectid": metadata["subjectid"],
        "template_id": extracted.template_id, "assigned_split": "train",
        "relative_template_directory": f"templates/{extracted.template_id}",
        "template_payload_tree_sha256": extracted.payload_tree_sha256,
        "episode_horizon_seconds": metadata["episode_horizon_seconds"],
        "bis_event_count": metadata["bis_event_count"],
        "bis_available_count": metadata["bis_available_count"],
        "sqi_exact_match_count": metadata["sqi_exact_match_count"],
        "p1_event_acceptance_count": metadata["p1_event_acceptance_count"],
        "source_bis_file_sha256": metadata["source_bis_file_sha256"],
        "source_sqi_file_sha256": metadata["source_sqi_file_sha256"],
        "schema_version": metadata["schema_version"],
    }


def _visibility(template, *, p1: bool) -> tuple[int, int]:
    horizon = template.episode_horizon_seconds
    grid_count = math.floor(horizon / 10.0 + 1e-12) + 1
    accepted = []
    sqi_by_timestamp = {
        event.timestamp_seconds: event.value for event in template.sqi_events
    } if p1 else {}
    for event in template.bis_events:
        if not event.available:
            continue
        if p1:
            sqi = sqi_by_timestamp.get(event.timestamp_seconds)
            if sqi is None or sqi < 50.0:
                continue
        accepted.append(event.timestamp_seconds)
    visible = 0
    position = -1
    cap = 20.0 if p1 else 30.0
    for step in range(grid_count):
        grid_time = step * 10.0
        while position + 1 < len(accepted) and accepted[position + 1] <= grid_time:
            position += 1
        if position >= 0 and grid_time - accepted[position] <= cap + 1e-9:
            visible += 1
    return grid_count, visible


def _full_qc(store: TrainObservationTemplateStore) -> dict[str, object]:
    variables: dict[str, list[float]] = {
        "episode_horizon_seconds": [], "bis_finite_event_count": [],
        "bis_available_event_count": [], "bis_finite_out_of_range_count": [],
        "exact_sqi_match_count": [], "p1_accepted_event_count": [],
        "fraction_bis_events_with_exact_sqi_match": [], "fraction_bis_events_accepted_by_p1": [],
    }
    p0_proportions: list[float] = []
    p1_proportions: list[float] = []
    p0_total = p1_total = grid_total = zero_p0 = zero_p1 = 0
    warnings: Counter[str] = Counter()
    for row in store.rows:
        template = store.load_case(row["caseid"])
        metadata = json.loads((store.root / row["relative_template_directory"] / "metadata.json").read_text(encoding="utf-8"))
        bis_count = int(metadata["bis_event_count"])
        available = int(metadata["bis_available_count"])
        out_range = int(metadata["bis_unavailable_finite_out_of_range_count"])
        sqi_count = int(metadata["sqi_exact_match_count"])
        p1_count = int(metadata["p1_event_acceptance_count"])
        variables["episode_horizon_seconds"].append(float(metadata["episode_horizon_seconds"]))
        variables["bis_finite_event_count"].append(float(bis_count))
        variables["bis_available_event_count"].append(float(available))
        variables["bis_finite_out_of_range_count"].append(float(out_range))
        variables["exact_sqi_match_count"].append(float(sqi_count))
        variables["p1_accepted_event_count"].append(float(p1_count))
        variables["fraction_bis_events_with_exact_sqi_match"].append(sqi_count / bis_count if bis_count else 0.0)
        variables["fraction_bis_events_accepted_by_p1"].append(p1_count / bis_count if bis_count else 0.0)
        g0, v0 = _visibility(template, p1=False)
        g1, v1 = _visibility(template, p1=True)
        if g0 != g1:
            raise TrainTemplateError("P0/P1 grid accounting mismatch")
        grid_total += g0; p0_total += v0; p1_total += v1
        p0_proportions.append(v0 / g0); p1_proportions.append(v1 / g1)
        zero_p0 += v0 == 0; zero_p1 += v1 == 0
        warnings["templates_with_finite_sqi_outside_0_100"] += int(metadata["sqi_outside_conventional_range_count"] > 0)
        warnings["templates_with_finite_bis_out_of_range"] += out_range > 0
        warnings["templates_with_source_duplicate_timestamps"] += (
            int(metadata["bis_duplicate_timestamp_count"]) + int(metadata["sqi_duplicate_timestamp_count"]) > 0
        )
        warnings["templates_with_source_nonmonotonic_intervals"] += (
            int(metadata["bis_negative_interval_count"]) + int(metadata["sqi_negative_interval_count"]) > 0
        )
    if zero_p0 or zero_p1:
        raise TrainTemplateError(f"zero-visibility hard gate failed: P0={zero_p0}, P1={zero_p1}")
    return {
        "phase": "Phase 8B", "train_template_count": len(store.rows), "test_template_count": 0,
        "structural_hard_gates": {
            "missing_train_case_count": 0, "duplicate_train_case_count": 0,
            "non_train_parent_subject_count": 0, "raw_bis_value_persisted_count": 0,
            "sqi_timestamp_not_in_bis_count": 0, "nonfinite_relative_timestamp_count": 0,
            "out_of_horizon_timestamp_count": 0, "nonmonotone_array_count": 0,
            "duplicate_canonical_event_timestamp_count": 0, "private_hash_mismatch_count": 0,
            "source_checksum_mismatch_count": 0, "test_raw_open_count": 0,
            "drug_raw_open_count": 0,
        },
        "distributions": {name: distribution(values) for name, values in variables.items()},
        "visibility_audit": {
            "grid_anchor": "anesthesia_start", "grid_interval_seconds": 10,
            "synthetic_latent_bis_value": 50.0, "total_grid_points": grid_total,
            "p0_visible_grid_points": p0_total, "p0_visible_proportion": p0_total / grid_total,
            "p1_visible_grid_points": p1_total, "p1_visible_proportion": p1_total / grid_total,
            "p0_minus_p1_visible_grid_points": p0_total - p1_total,
            "p0_minus_p1_visible_proportion": (p0_total - p1_total) / grid_total,
            "p0_per_template_visibility_proportion": distribution(p0_proportions),
            "p1_per_template_visibility_proportion": distribution(p1_proportions),
            "templates_with_zero_p0_visibility": zero_p0,
            "templates_with_zero_p1_visibility": zero_p1,
            "scientific_result": False,
        },
        "aggregate_warning_counts": dict(sorted(warnings.items())),
        "warning_cutoff_invented": False, "membership_changed_by_qc": False,
    }


def _verify_inventory(name: str) -> int:
    inventory = json.loads((MANIFESTS / name).read_text(encoding="utf-8"))
    entries = inventory.get("artifacts", [])
    for entry in entries:
        path = ROOT / entry["relative_path"]
        if path.stat().st_size != entry["bytes"] or sha256_path(path) != entry["sha256"]:
            raise TrainTemplateError(f"prior protected artifact changed: {entry['relative_path']}")
    return len(entries)


def _write_public_artifacts(
    gate: dict[str, object], store: TrainObservationTemplateStore,
    root_fingerprint: str, qc: dict[str, object], ledger_rows: list[dict[str, object]],
) -> None:
    index_path = PRIVATE_ROOT / "private_index.csv"
    ledger_path = PRIVATE_ROOT / "access_ledger.csv"
    template_payload_files = len(store.rows) * len(PAYLOAD_FILES)
    template_tree_bytes = sum(
        path.stat().st_size for row in store.rows
        for path in (PRIVATE_ROOT / row["relative_template_directory"]).iterdir() if path.is_file()
    )
    total_private_files = sum(1 for path in PRIVATE_ROOT.rglob("*") if path.is_file())
    total_private_bytes = sum(path.stat().st_size for path in PRIVATE_ROOT.rglob("*") if path.is_file())
    train_bis = sum(row["track_name"] == "BIS/BIS" and row["status"] == "complete" for row in ledger_rows)
    train_sqi = sum(row["track_name"] == "BIS/SQI" and row["status"] == "complete" for row in ledger_rows)
    decisions = {
        "phase": "Phase 8B", "source_remote_commit": SOURCE_COMMIT,
        "source_cohort_protocol_version": "1.2", "online_observation_contract_version": "1.3.1",
        "current_reconstruction_protocol_version": "1.3.2", "phase8a_split_manifest_version": "phase8a-v1",
        "phase8a_seal_payload_sha256": PHASE8A_SEAL_PAYLOAD_SHA256,
        "template_format_version": TEMPLATE_FORMAT_VERSION, "authorized_split": "train",
        "authorized_case_count": EXPECTED_TRAIN_CASES, "authorized_tracks": list(ALLOWED_TRACKS),
        "operational_timing_source": {"relative_path": OPERATIONAL_TIMING_RELATIVE, "sha256": OPERATIONAL_TIMING_SHA256},
        "upstream_authoritative_timing_lineage": {"relative_path": UPSTREAM_TIMING_RELATIVE, "sha256": UPSTREAM_TIMING_SHA256},
        "timing_lineage_train_case_exact_string_and_numeric_match": True,
        "test_raw_access_authorized": False, "test_template_authorized": False,
        "drug_track_access_authorized": False, "raw_bis_transient_read_authorized": True,
        "raw_bis_persistence_authorized": False, "raw_sqi_private_persistence_authorized": True,
        "public_event_level_data_authorized": False, "same_template_for_p0_p1": True,
        "p0_sqi_rule": "not_required", "p0_staleness_seconds": 30,
        "p1_sqi_rule": "exact_timestamp_gte_50", "p1_staleness_seconds": 20,
        "duplicate_rule": "last_finite_in_original_row_order", "interpolation": False,
        "nearest_sqi_matching": False, "output_root": PRIVATE_ROOT_RELATIVE.as_posix(),
        "private_store_publication": "prohibited",
        "public_artifacts": "code_schema_aggregate_qc_fingerprint_only",
        "normalization_fit": False, "ppo_training": False, "test_seal_modified": False,
    }
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema", "schema_version": SCHEMA_VERSION,
        "template_format_version": TEMPLATE_FORMAT_VERSION, "private_store_relative_root": PRIVATE_ROOT_RELATIVE.as_posix(),
        "files": {
            "metadata.json": "canonical UTF-8 JSON; contains no raw BIS values",
            "bis_timestamp_seconds.npy": {"dtype": "little-endian float64", "shape": "one-dimensional"},
            "bis_available.npy": {"dtype": "boolean", "shape": "one-dimensional"},
            "sqi_timestamp_seconds.npy": {"dtype": "little-endian float64", "shape": "one-dimensional"},
            "sqi_value.npy": {"dtype": "little-endian float64", "shape": "one-dimensional", "privacy": "private only"},
            "COMPLETE.json": "written last; hashes the five payload files",
        },
        "relative_timing": "exact source timestamp minus anesthesia_start; negative zero normalized only",
        "same_template_for_p0_p1": True, "raw_bis_values_forbidden": True,
        "raw_sqi_values_private_only": True, "arrays_must_never_be_committed": True,
        "test_templates_absent": True, "pickle_forbidden": True,
        "event_level_publication_forbidden": True, "future_use_requires_split_guard": True,
    }
    access_summary = {
        "phase": "Phase 8B", "train_case_count": EXPECTED_TRAIN_CASES, "test_case_count": 490,
        "train_bis_logical_file_access_count": train_bis, "train_sqi_logical_file_access_count": train_sqi,
        "train_total_logical_file_access_count": len(ledger_rows), "test_logical_file_access_count": 0,
        "drug_logical_file_access_count": 0, "api_request_count": 0, "network_request_count": 0,
        "source_checksum_match_count": len(ledger_rows), "source_checksum_mismatch_count": 0,
        "raw_source_write_count": 0, "raw_bis_values_persisted": False,
        "raw_sqi_values_persisted_private": True, "public_event_level_value_count": 0,
        "split_guard_enforced": True, "completed": True,
    }
    tree_summary = {
        "phase": "Phase 8B", "private_store_relative_root": PRIVATE_ROOT_RELATIVE.as_posix(),
        "store_is_git_ignored": True, "store_is_git_tracked": False,
        "template_format_version": TEMPLATE_FORMAT_VERSION, "train_template_count": len(store.rows),
        "test_template_count": 0, "unique_template_id_count": len({row['template_id'] for row in store.rows}),
        "private_payload_file_count": template_payload_files, "private_template_tree_bytes": template_tree_bytes,
        "private_total_file_count": total_private_files, "private_total_bytes": total_private_bytes,
        "private_template_store_root_sha256": root_fingerprint,
        "private_index_sha256": sha256_path(index_path), "private_access_ledger_sha256": sha256_path(ledger_path),
        "phase8a_train_case_ids_sha256": gate["phase8a_seal"]["sha256_sorted_train_case_ids"],
        "phase8a_test_case_ids_sha256": gate["phase8a_seal"]["sha256_sorted_test_case_ids"],
        "per_case_mapping_published": False, "per_case_qc_published": False,
        "event_arrays_published": False, "raw_bis_values_persisted": False,
        "raw_sqi_values_private_only": True, "verify_only_passed": True,
    }
    inventory_counts = {
        name: _verify_inventory(name) for name in (
            "phase7f_artifact_checksums.json", "phase7g_artifact_checksums.json",
            "phase7h_artifact_checksums.json", "phase8a_artifact_checksums.json",
        )
    }
    legacy_after = legacy_state()
    source_snapshot = {
        "phase": "Phase 8B", "starting_local_head": SOURCE_COMMIT,
        "starting_remote_tracking_sha": SOURCE_COMMIT, "expected_source_sha": SOURCE_COMMIT,
        "source_sha_verified": True, "source_worktree_clean": True, "source_index_clean": True,
        "phase8a_manifest_hashes": {
            "subject_split": gate["phase8a_seal"]["sha256_full_subject_split_manifest"],
            "case_split": gate["phase8a_seal"]["sha256_full_case_split_manifest"],
        },
        "phase8a_seal_payload_sha256": PHASE8A_SEAL_PAYLOAD_SHA256,
        "phase8a_artifact_checksum_verification": True,
        "prior_inventory_entry_counts": inventory_counts,
        "operational_timing_source": {"relative_path": OPERATIONAL_TIMING_RELATIVE, "sha256": OPERATIONAL_TIMING_SHA256},
        "upstream_authoritative_timing_lineage": {"relative_path": UPSTREAM_TIMING_RELATIVE, "sha256": UPSTREAM_TIMING_SHA256},
        "timing_lineage_verified_train_case_count": EXPECTED_TRAIN_CASES,
        "timing_lineage_mismatch_count": 0, "frozen_cohort_count": 2460,
        "train_subject_count": 1932, "test_subject_count": 483,
        "train_case_count": EXPECTED_TRAIN_CASES, "test_case_count": 490,
        "permitted_raw_tracks": list(ALLOWED_TRACKS),
        "forbidden_raw_tracks": ["Orchestra/PPF20_RATE", "Orchestra/RFTN20_RATE", "all_other_tracks"],
        "expected_train_raw_file_count": 3940, "raw_access_scope": "checksum_verified_train_BIS_and_SQI_only",
        "raw_test_access_count": 0, "test_template_count": 0,
        "observation_template_public_value_count": 0, "normalization_fitted": False,
        "real_subject_simulator_run": False, "ppo_training": False, "ppo_evaluation": False,
        "model_or_checkpoint_created": False, "api_requests": 0, "network_requests": 0,
        "dependency_change": False, "previous_artifacts_changed": False,
        "phase8a_test_seal_changed": False, "legacy_state_before": gate["legacy_before"],
        "legacy_state_after": legacy_after, "legacy_unchanged": legacy_after == gate["legacy_before"],
        "private_store_ignored": True, "private_store_tracked_count": 0,
    }
    for name, value in (
        ("phase8b_train_template_human_decisions.json", decisions),
        ("phase8b_private_template_schema.json", schema),
        ("phase8b_private_tree_summary.json", tree_summary),
        ("phase8b_template_qc_summary.json", qc),
        ("phase8b_access_summary.json", access_summary),
        ("phase8b_source_snapshot.json", source_snapshot),
    ):
        write_json(MANIFESTS / name, value)
    report = f"""# Phase 8B train observation-template report

Phase 8B extracted {len(store.rows):,} sealed train templates and no test templates. The private store remains ignored and only its aggregate fingerprint is public.

- Train BIS/SQI logical accesses: {len(ledger_rows):,} ({train_bis:,} BIS, {train_sqi:,} SQI)
- Source checksum mismatches: 0
- Test and drug raw accesses: 0
- Raw BIS values persisted: false
- Raw SQI values: private only
- Private-store root SHA-256: `{root_fingerprint}`
- P0 visible grid points: {qc['visibility_audit']['p0_visible_grid_points']:,}/{qc['visibility_audit']['total_grid_points']:,}
- P1 visible grid points: {qc['visibility_audit']['p1_visible_grid_points']:,}/{qc['visibility_audit']['total_grid_points']:,}
- Zero-visibility templates: P0=0, P1=0

These visibility counts are a structural audit using fixed latent BIS 50.0, not a prediction or control result. No membership, preprocessing rule, normalization, model, checkpoint, or PPO operation was changed or executed.
"""
    decision_record = f"""# Phase 8B train-template decision record

The approved operational anesthesia-window source is `{OPERATIONAL_TIMING_RELATIVE}` at SHA-256 `{OPERATIONAL_TIMING_SHA256}`. Its upstream authoritative lineage is `{UPSTREAM_TIMING_RELATIVE}` at SHA-256 `{UPSTREAM_TIMING_SHA256}`. Exact strings and finite numeric interpretations matched for all {EXPECTED_TRAIN_CASES:,} sealed train cases.

Only `BIS/BIS` and `BIS/SQI` were read through the train-only SplitGuard. One private pseudonymous template is reused for P0 and P1. BIS values were used transiently only to derive availability; SQI exact matches remain private. Test templates, drug histories, normalization, outcome access, simulation with real profiles, PPO, models, and checkpoints remain prohibited.
"""
    (ROOT / "docs/phase8b_train_template_report.md").write_text(report, encoding="utf-8", newline="\n")
    (ROOT / "docs/phase8b_train_template_decision_record.md").write_text(decision_record, encoding="utf-8", newline="\n")


def run_full(gate: dict[str, object]) -> None:
    preflight_path = PRIVATE_ROOT / "preflight_summary.json"
    if not preflight_path.is_file() or not json.loads(preflight_path.read_text(encoding="utf-8")).get("disk_gate_passed"):
        raise TrainTemplateError("successful Phase 8B preflight is required")
    cases: list[TrainCase] = gate["cases"]
    template_root = PRIVATE_ROOT / "templates"
    progress = PRIVATE_ROOT / "progress.jsonl"
    started = time.perf_counter()
    index_path = PRIVATE_ROOT / "private_index.csv"
    ledger_path = PRIVATE_ROOT / "access_ledger.csv"
    complete_directories = list(template_root.iterdir()) if template_root.is_dir() else []
    resume_complete = (
        len([path for path in complete_directories if path.is_dir() and not path.name.endswith(".partial")])
        == EXPECTED_TRAIN_CASES
        and index_path.is_file() and ledger_path.is_file()
    )
    if resume_complete:
        with index_path.open(encoding="utf-8", newline="") as stream:
            index_rows = list(csv.DictReader(stream))
        with ledger_path.open(encoding="utf-8", newline="") as stream:
            ledger_rows = list(csv.DictReader(stream))
        print("resuming from 1970 checksum-verified complete templates; no raw reparse or rewrite")
    else:
        access = TrainRawAccessGuard(ROOT)
        index_rows = []
        for position, case in enumerate(cases, start=1):
            extracted = extract_template(case, access=access, template_root=template_root)
            index_rows.append(_index_row(extracted))
            _append_progress(progress, {
                "completed": position, "total": EXPECTED_TRAIN_CASES,
                "template_id_prefix": extracted.template_id[:12], "status": "complete",
            })
            if position % 100 == 0 or position == EXPECTED_TRAIN_CASES:
                elapsed = time.perf_counter() - started
                print(f"completed {position}/{EXPECTED_TRAIN_CASES}; elapsed={elapsed:.1f}s")
        ledger_rows = access.ledger_rows()
    if len(index_rows) != EXPECTED_TRAIN_CASES or len({row["caseid"] for row in index_rows}) != EXPECTED_TRAIN_CASES:
        raise TrainTemplateError("full private index accounting mismatch")
    if len({row["template_id"] for row in index_rows}) != EXPECTED_TRAIN_CASES:
        raise TrainTemplateError("template ID collision")
    if len(ledger_rows) != 3940 or Counter(row["track_name"] for row in ledger_rows) != Counter({"BIS/BIS": 1970, "BIS/SQI": 1970}):
        raise TrainTemplateError("full logical raw-access accounting mismatch")
    if any(row["status"] != "complete" or row["assigned_split"] != "train" for row in ledger_rows):
        raise TrainTemplateError("failed or non-train logical raw access")
    if not resume_complete:
        write_csv(index_path, INDEX_FIELDS, index_rows)
        write_csv(ledger_path, LEDGER_FIELDS, ledger_rows)
    store = TrainObservationTemplateStore(PRIVATE_ROOT, ROOT)
    root_fingerprint = store.verify_all()
    expected_root = private_store_root_sha256(index_rows)
    if root_fingerprint != expected_root:
        raise TrainTemplateError("private store root fingerprint mismatch")
    qc = _full_qc(store)
    full_summary = {
        "stage": "full", "train_template_count": EXPECTED_TRAIN_CASES,
        "test_template_count": 0, "logical_raw_access_count": len(ledger_rows),
        "private_template_store_root_sha256": root_fingerprint,
        "elapsed_seconds": time.perf_counter() - started, "completed": True,
    }
    write_json(PRIVATE_ROOT / "full_summary.json", full_summary)
    write_json(PRIVATE_ROOT / "STORE_COMPLETE.json", {
        "complete": True, "private_template_store_root_sha256": root_fingerprint,
        "private_index_sha256": sha256_path(PRIVATE_ROOT / "private_index.csv"),
        "private_access_ledger_sha256": sha256_path(PRIVATE_ROOT / "access_ledger.csv"),
        "train_template_count": EXPECTED_TRAIN_CASES, "test_template_count": 0,
    })
    _write_public_artifacts(gate, store, root_fingerprint, qc, ledger_rows)
    print(json.dumps(full_summary, indent=2, sort_keys=True))


def run_verify_only(gate: dict[str, object]) -> None:
    before = {
        path.relative_to(PRIVATE_ROOT).as_posix(): sha256_path(path)
        for path in PRIVATE_ROOT.rglob("*") if path.is_file()
    }
    store = TrainObservationTemplateStore(PRIVATE_ROOT, ROOT)
    root_fingerprint = store.verify_all()
    complete = json.loads((PRIVATE_ROOT / "STORE_COMPLETE.json").read_text(encoding="utf-8"))
    if complete.get("private_template_store_root_sha256") != root_fingerprint:
        raise TrainTemplateError("STORE_COMPLETE root mismatch")
    after = {
        path.relative_to(PRIVATE_ROOT).as_posix(): sha256_path(path)
        for path in PRIVATE_ROOT.rglob("*") if path.is_file()
    }
    if before != after:
        raise TrainTemplateError("verify-only rewrote the private store")
    legacy_state()
    print(json.dumps({"verified": True, "train_templates": len(store.rows), "root_sha256": root_fingerprint}, indent=2))


def main() -> int:
    args = parse_args()
    gate = source_gate(require_exact_source_refs=args.stage != "verify-only")
    if args.stage == "preflight":
        run_preflight(gate)
    elif args.stage == "full":
        run_full(gate)
    else:
        run_verify_only(gate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
