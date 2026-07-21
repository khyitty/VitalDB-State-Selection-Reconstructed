"""Build or verify sealed-test Phase 8E private input stores."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.anesthesia.recorded_observation import TrainObservationTemplateStore  # noqa: E402
from vitaldb_state_selection.cohort.test_observation_templates import (  # noqa: E402
    EXPECTED_TEST_CASES,
    PRIVATE_ROOT_RELATIVE as TEMPLATE_RELATIVE,
    TestObservationTemplateStore,
    TestRawAccessGuard,
    atomic_csv,
    atomic_json,
    extract_template,
    load_test_cases,
    private_root_sha256,
    sha256_path,
)
from vitaldb_state_selection.cohort.test_runtime_inputs import (  # noqa: E402
    PHASE8C_EXPECTED_ROOT_SHA256,
    PRIVATE_ROOT_RELATIVE as RUNTIME_RELATIVE,
    TestRemifentanilAccessGuard,
    TestRuntimeInputStore,
    extract_bundle,
    load_test_patient_records,
    verify_train_scalers,
)
from vitaldb_state_selection.cohort.train_observation_templates import PRIVATE_ROOT_RELATIVE as TRAIN_TEMPLATE_RELATIVE  # noqa: E402
from vitaldb_state_selection.cohort.train_runtime_inputs import (  # noqa: E402
    PHASE8B_EXPECTED_ROOT_SHA256,
    PRIVATE_ROOT_RELATIVE as TRAIN_RUNTIME_RELATIVE,
    TrainRuntimeInputStore,
)
from vitaldb_state_selection.rl_integration.final_evaluation import verify_final_model  # noqa: E402


STARTING_SHA = "eb11dedfb644f41ac587d29156a2ec0dea007001"
TRAINING_SHA = "b782b5e4a9d418f6b907a87d046c4e9789a3e5f0"
SHARD_A_ROOT = ROOT / "data/processed/phase8d_final_training_v1"
TEMPLATE_ROOT = ROOT / TEMPLATE_RELATIVE
RUNTIME_ROOT = ROOT / RUNTIME_RELATIVE
SUMMARY_PATH = ROOT / "data/manifests/phase8e_test_input_summary.json"
SOURCE_PATH = ROOT / "data/manifests/phase8e_source_snapshot.json"
LEGACY_ROOT = ROOT.parent / "VitalDB-Feature-Selection"
LEGACY_COMMIT = "9501b16a5c4db27f06fa0d0b252a3a75f633967f"
LEGACY_TREE = "60917f0b61ec1e6a195b9a648faa6466406aeda1"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


def _legacy_state() -> dict[str, object]:
    prefix = ["git", "-c", f"safe.directory={LEGACY_ROOT.as_posix()}", "-C", str(LEGACY_ROOT)]
    commit = subprocess.check_output([*prefix, "rev-parse", "HEAD"], text=True, encoding="utf-8").strip()
    tree = subprocess.check_output([*prefix, "rev-parse", "HEAD^{tree}"], text=True, encoding="utf-8").strip()
    status = subprocess.check_output([*prefix, "status", "--short"], text=True, encoding="utf-8").splitlines()
    if commit != LEGACY_COMMIT or tree != LEGACY_TREE or status != ["?? debug.log"]:
        raise RuntimeError("legacy repository read-only state mismatch")
    return {
        "commit_sha": commit,
        "pre_existing_untracked_entries": ["debug.log"],
        "tree_sha": tree,
    }


def _train_roots() -> tuple[str, str]:
    template = TrainObservationTemplateStore(ROOT / TRAIN_TEMPLATE_RELATIVE, ROOT).verify_all()
    runtime = TrainRuntimeInputStore(ROOT / TRAIN_RUNTIME_RELATIVE, ROOT).verify_all()
    if template != PHASE8B_EXPECTED_ROOT_SHA256 or runtime != PHASE8C_EXPECTED_ROOT_SHA256:
        raise RuntimeError("Phase 8B/8C train private root mismatch")
    return template, runtime


def _shard_a() -> dict[str, object]:
    records = [verify_final_model(SHARD_A_ROOT, condition, expected_training_sha=TRAINING_SHA) for condition in ("P0S0", "P1S0")]
    return {
        "episode_execution_count": 0,
        "models_loaded": False,
        "partial_directory_count": sum(1 for path in SHARD_A_ROOT.rglob("*") if ".partial" in path.name),
        "records": [
            {
                "condition_id": row.condition_id,
                "final_model_sha256": row.final_model_sha256,
                "output_root_sha256": json.loads((row.directory / "OUTPUT_COMPLETE.json").read_text(encoding="utf-8"))["output_root_sha256"],
                "timestep": 1_000_000,
            }
            for row in records
        ],
        "test_access_count": 0,
    }


def _clean_partials(root: Path) -> int:
    paths = [path for path in root.rglob("*") if ".partial" in path.name or path.suffix == ".tmp"] if root.exists() else []
    for path in sorted(paths, key=lambda item: len(item.parts), reverse=True):
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    return len(paths)


def build() -> None:
    started = time.perf_counter()
    if git("rev-parse", "HEAD") != STARTING_SHA:
        raise RuntimeError("Phase 8E starting HEAD mismatch")
    legacy_before = _legacy_state()
    train_before = _train_roots()
    shard_a = _shard_a()
    cases = load_test_cases(ROOT)
    records = load_test_patient_records(ROOT)
    by_case = {case.caseid: case for case in cases}
    by_record = {record.caseid: record for record in records}
    if len(cases) != EXPECTED_TEST_CASES or set(by_case) != set(by_record):
        raise RuntimeError("test timing/patient accounting mismatch")

    removed_partials = _clean_partials(TEMPLATE_ROOT) + _clean_partials(RUNTIME_ROOT)
    template_access = TestRawAccessGuard(ROOT)
    extracted_templates: dict[str, dict[str, object]] = {}
    for case in cases:
        extracted_templates[case.caseid] = extract_template(case, access=template_access, template_root=TEMPLATE_ROOT / "templates")
    template_rows = [
        {
            "caseid": case.caseid,
            "relative_template_directory": f"templates/{extracted_templates[case.caseid]['template_id']}",
            "subjectid": case.subjectid,
            "template_id": extracted_templates[case.caseid]["template_id"],
            "template_payload_tree_sha256": extracted_templates[case.caseid]["fingerprint"],
        }
        for case in cases
    ]
    atomic_csv(
        TEMPLATE_ROOT / "private_index.csv",
        ("caseid", "relative_template_directory", "subjectid", "template_id", "template_payload_tree_sha256"),
        template_rows,
    )
    template_ledger = template_access.ledger_rows()
    if len(template_ledger) != EXPECTED_TEST_CASES * 2:
        raise RuntimeError("test BIS/SQI logical access accounting mismatch")
    atomic_csv(
        TEMPLATE_ROOT / "access_ledger.csv",
        ("sequence_number", "caseid", "assigned_split", "track_name", "expected_source_sha256", "observed_source_sha256", "access_purpose", "status"),
        template_ledger,
    )
    template_root = private_root_sha256([
        {"template_id": row["template_id"], "template_payload_tree_sha256": row["template_payload_tree_sha256"]}
        for row in template_rows
    ])
    atomic_json(TEMPLATE_ROOT / "STORE_COMPLETE.json", {
        "access_ledger_sha256": sha256_path(TEMPLATE_ROOT / "access_ledger.csv"),
        "complete": True,
        "private_index_sha256": sha256_path(TEMPLATE_ROOT / "private_index.csv"),
        "private_template_root_sha256": template_root,
        "test_template_count": EXPECTED_TEST_CASES,
        "train_template_count": 0,
    })
    if TestObservationTemplateStore(TEMPLATE_ROOT, ROOT).verify_all() != template_root:
        raise RuntimeError("test template store verify-only mismatch")

    scalers, scaler_sha = verify_train_scalers(ROOT)
    template_index = {row["caseid"]: row for row in template_rows}
    remi_access = TestRemifentanilAccessGuard(ROOT)
    extracted_bundles: dict[str, dict[str, object]] = {}
    for record in records:
        case = by_case[record.caseid]
        extracted_bundles[record.caseid] = extract_bundle(
            record,
            anesthesia_start=case.anesthesia_start,
            anesthesia_end=case.anesthesia_end,
            template_root=TEMPLATE_ROOT,
            template_index_row=template_index[record.caseid],
            access=remi_access,
            bundle_root=RUNTIME_ROOT / "bundles",
            scaler_sha256=scaler_sha,
        )
    bundle_rows = [
        {
            "bundle_id": extracted_bundles[record.caseid]["bundle_id"],
            "bundle_payload_tree_sha256": extracted_bundles[record.caseid]["fingerprint"],
            "caseid": record.caseid,
            "relative_bundle_directory": f"bundles/{extracted_bundles[record.caseid]['bundle_id']}",
            "subjectid": record.subjectid,
        }
        for record in records
    ]
    atomic_csv(
        RUNTIME_ROOT / "private_index.csv",
        ("bundle_id", "bundle_payload_tree_sha256", "caseid", "relative_bundle_directory", "subjectid"),
        bundle_rows,
    )
    remi_ledger = remi_access.ledger_rows()
    if len(remi_ledger) != EXPECTED_TEST_CASES:
        raise RuntimeError("test remifentanil logical access accounting mismatch")
    atomic_csv(
        RUNTIME_ROOT / "access_ledger.csv",
        ("sequence_number", "caseid", "assigned_split", "track_name", "expected_source_sha256", "observed_source_sha256", "access_purpose", "status"),
        remi_ledger,
    )
    lines = "".join(
        f"{row['bundle_id']}\t{row['bundle_payload_tree_sha256']}\n"
        for row in sorted(bundle_rows, key=lambda item: item["bundle_id"])
    )
    runtime_root = hashlib.sha256(lines.encode("utf-8")).hexdigest()
    atomic_json(RUNTIME_ROOT / "STORE_COMPLETE.json", {
        "access_ledger_sha256": sha256_path(RUNTIME_ROOT / "access_ledger.csv"),
        "complete": True,
        "private_index_sha256": sha256_path(RUNTIME_ROOT / "private_index.csv"),
        "private_runtime_root_sha256": runtime_root,
        "test_bundle_count": EXPECTED_TEST_CASES,
        "train_bundle_count": 0,
        "train_scaler_registry_sha256": scaler_sha,
    })
    store = TestRuntimeInputStore(RUNTIME_ROOT, ROOT)
    if store.verify_all() != runtime_root:
        raise RuntimeError("test runtime store verify-only mismatch")

    # Apply, but never fit, the frozen train scalers to every test initial state.
    from vitaldb_state_selection.rl_integration.train_runtime import make_train_runtime_environment

    finite_checks = 0
    case_order = [row["caseid"] for row in store.rows]
    for condition in ("P0S0", "P1S0", "P0S1", "P1S1"):
        scaler = scalers["S0" if condition.endswith("S0") else "S1"]
        for caseid in case_order:
            environment = make_train_runtime_environment(store=store, caseid=caseid, condition_id=condition, scaler=scaler, seed=42)
            observation, _ = environment.reset(seed=42)
            environment.close()
            if not np.isfinite(observation).all():
                raise RuntimeError("train scaler produced non-finite test observation")
            finite_checks += 1
    if finite_checks != EXPECTED_TEST_CASES * 4:
        raise RuntimeError("test scaler-application accounting mismatch")

    partial_count = sum(
        1 for root in (TEMPLATE_ROOT, RUNTIME_ROOT) for path in root.rglob("*")
        if ".partial" in path.name or path.suffix == ".tmp"
    )
    if partial_count:
        raise RuntimeError("partial test private paths remain")
    train_after = _train_roots()
    if train_before != train_after:
        raise RuntimeError("Phase 8B/8C train roots changed")
    legacy_after = _legacy_state()
    if legacy_before != legacy_after:
        raise RuntimeError("legacy repository changed during Phase 8E")
    case_order_sha = hashlib.sha256("".join(f"{caseid}\n" for caseid in case_order).encode("ascii")).hexdigest()
    summary = {
        "actual_model_episode_count": 0,
        "approved_fallback_used": False,
        "case_order_sha256": case_order_sha,
        "condition_comparison_performed": False,
        "missing_required_profile_count": 0,
        "invalid_profile_count": 0,
        "partial_directory_count": partial_count,
        "phase8b_train_root_after": train_after[0],
        "phase8b_train_root_before": train_before[0],
        "phase8c_train_root_after": train_after[1],
        "phase8c_train_root_before": train_before[1],
        "private_test_runtime_root_sha256": runtime_root,
        "private_test_template_root_sha256": template_root,
        "public_event_level_value_count": 0,
        "runtime_seconds": time.perf_counter() - started,
        "shard_a_read_only_verification": shard_a,
        "test_bis_logical_access_count": sum(row["track_name"] == "BIS/BIS" for row in template_ledger),
        "test_case_count": EXPECTED_TEST_CASES,
        "test_remifentanil_logical_access_count": len(remi_ledger),
        "test_runtime_bundle_count": len(bundle_rows),
        "test_scaler_application_count": finite_checks,
        "test_sqi_logical_access_count": sum(row["track_name"] == "BIS/SQI" for row in template_ledger),
        "test_template_count": len(template_rows),
        "train_case_access_count_during_test_extraction": 0,
        "train_scaler_fit_count_during_test_phase": 0,
        "train_scaler_registry_sha256": scaler_sha,
    }
    atomic_json(SUMMARY_PATH, summary)
    atomic_json(SOURCE_PATH, {
        "actual_condition_comparison_performed": False,
        "actual_model_episode_count": 0,
        "legacy_repository_after": legacy_after,
        "legacy_repository_before": legacy_before,
        "phase": "Phase 8E",
        "phase8a_test_seal_sha256": sha256_path(ROOT / "data/manifests/phase8a_test_seal.json"),
        "phase8b_train_root_sha256": train_after[0],
        "phase8c_train_root_sha256": train_after[1],
        "phase8d_training_implementation_sha": TRAINING_SHA,
        "shard_a_output_roots": {row["condition_id"]: row["output_root_sha256"] for row in shard_a["records"]},
        "shard_a_policy_models_loaded": False,
        "shard_a_test_episode_count": 0,
        "shard_b_accessed": False,
        "shard_b_state": "pending_external_completion",
        "starting_sha": STARTING_SHA,
        "train_scaler_registry_sha256": scaler_sha,
    })
    print(json.dumps(summary, indent=2, sort_keys=True))


def verify_only() -> None:
    _legacy_state()
    train_before = _train_roots()
    shard_a = _shard_a()
    template_complete = json.loads((TEMPLATE_ROOT / "STORE_COMPLETE.json").read_text(encoding="utf-8"))
    runtime_complete = json.loads((RUNTIME_ROOT / "STORE_COMPLETE.json").read_text(encoding="utf-8"))
    template_root = TestObservationTemplateStore(TEMPLATE_ROOT, ROOT).verify_all()
    runtime_root = TestRuntimeInputStore(RUNTIME_ROOT, ROOT).verify_all()
    if template_root != template_complete.get("private_template_root_sha256"):
        raise RuntimeError("test template root mismatch")
    if runtime_root != runtime_complete.get("private_runtime_root_sha256"):
        raise RuntimeError("test runtime root mismatch")
    if template_complete.get("test_template_count") != EXPECTED_TEST_CASES or runtime_complete.get("test_bundle_count") != EXPECTED_TEST_CASES:
        raise RuntimeError("test private-store accounting mismatch")
    train_after = _train_roots()
    if train_before != train_after:
        raise RuntimeError("train private root changed during verify-only")
    partials = sum(1 for root in (TEMPLATE_ROOT, RUNTIME_ROOT) for path in root.rglob("*") if ".partial" in path.name or path.suffix == ".tmp")
    if partials:
        raise RuntimeError("partial private paths remain")
    print(json.dumps({
        "episode_execution_count": 0,
        "partial_count": 0,
        "shard_a_models_loaded": shard_a["models_loaded"],
        "test_runtime_root": runtime_root,
        "test_template_root": template_root,
    }, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("build", "verify-only"), required=True)
    args = parser.parse_args()
    if args.stage == "build":
        build()
    else:
        verify_only()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
