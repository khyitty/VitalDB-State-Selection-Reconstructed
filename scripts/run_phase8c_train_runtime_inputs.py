"""Build, verify, and smoke-test ignored Phase 8C train runtime inputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.anesthesia import ConditionID, S0_FIELDS, S1_FIELDS  # noqa: E402
from vitaldb_state_selection.anesthesia.recorded_observation import TrainObservationTemplateStore  # noqa: E402
from vitaldb_state_selection.cohort.train_observation_templates import (  # noqa: E402
    PRIVATE_ROOT_RELATIVE as PHASE8B_PRIVATE_ROOT_RELATIVE,
    load_train_cases,
)
from vitaldb_state_selection.cohort.train_runtime_inputs import (  # noqa: E402
    EXPECTED_TEST_CASES,
    EXPECTED_TRAIN_CASES,
    PHASE8B_EXPECTED_ROOT_SHA256,
    PRIVATE_ROOT_RELATIVE,
    REMIFENTANIL_TRACK,
    RUNTIME_FORMAT_VERSION,
    ExtractedRuntimeBundle,
    StateScaler,
    TrainRemifentanilAccessGuard,
    TrainRuntimeInputError,
    TrainRuntimeInputStore,
    atomic_bytes,
    atomic_json,
    bundle_id_for_case,
    extract_runtime_bundle,
    load_scaler_registry,
    load_train_patient_records,
    make_scaler_fields,
    sha256_path,
    state_schema_sha256,
    verify_complete_bundle,
)
from vitaldb_state_selection.pkpd import DualDrugSimulator  # noqa: E402


MANIFESTS = ROOT / "data/manifests"
PRIVATE_ROOT = ROOT / PRIVATE_ROOT_RELATIVE
PHASE8B_ROOT = ROOT / PHASE8B_PRIVATE_ROOT_RELATIVE
SCALER_PATH = MANIFESTS / "phase8c_scaler_registry.json"
SUMMARY_PATH = MANIFESTS / "phase8c_runtime_input_summary.json"
SMOKE_PATH = MANIFESTS / "phase8c_smoke_summary.json"
STARTING_SHA = "a7821b43b608180f52e471c4bd8247d60336d8ef"
SEED = 42
CONDITIONS = tuple(condition.value for condition in ConditionID)


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _phase8b_root() -> str:
    complete = _json(PHASE8B_ROOT / "STORE_COMPLETE.json")
    if (
        complete.get("complete") is not True
        or complete.get("train_template_count") != EXPECTED_TRAIN_CASES
        or complete.get("test_template_count") != 0
        or complete.get("private_template_store_root_sha256") != PHASE8B_EXPECTED_ROOT_SHA256
        or sha256_path(PHASE8B_ROOT / "private_index.csv") != complete.get("private_index_sha256")
        or sha256_path(PHASE8B_ROOT / "access_ledger.csv") != complete.get("private_access_ledger_sha256")
    ):
        raise TrainRuntimeInputError("Phase 8B private store integrity gate failed")
    return PHASE8B_EXPECTED_ROOT_SHA256


def _atomic_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    atomic_bytes(path, stream.getvalue().encode("utf-8"))


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "minimum": None, "q1": None, "median": None, "q3": None, "maximum": None, "mean": None}
    ordered = np.asarray(sorted(values), dtype=np.float64)
    return {
        "count": int(ordered.size),
        "minimum": float(ordered[0]),
        "q1": float(np.quantile(ordered, 0.25)),
        "median": float(np.quantile(ordered, 0.5)),
        "q3": float(np.quantile(ordered, 0.75)),
        "maximum": float(ordered[-1]),
        "mean": float(ordered.mean()),
    }


def _preflight_records(records, cases):
    by_case = {case.caseid: case for case in cases}
    eligible = [record for record in records if record.caseid in by_case]
    ordered = sorted(eligible, key=lambda row: (row.profile.age_years, float(by_case[row.caseid].anesthesia_end - by_case[row.caseid].anesthesia_start), int(row.caseid)))
    candidates = (ordered[0], ordered[len(ordered) // 2], ordered[-1])
    selected = []
    subjects = set()
    for candidate in candidates + tuple(ordered):
        if candidate.subjectid not in subjects:
            selected.append(candidate)
            subjects.add(candidate.subjectid)
        if len(selected) == 3:
            break
    if len(selected) != 3:
        raise TrainRuntimeInputError("could not select three distinct train subjects")
    return selected


def _phase8b_index() -> dict[str, dict[str, str]]:
    with (PHASE8B_ROOT / "private_index.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != EXPECTED_TRAIN_CASES:
        raise TrainRuntimeInputError("Phase 8B private index accounting mismatch")
    return {row["caseid"]: row for row in rows}


def _build_one(record, case, index_row, access) -> ExtractedRuntimeBundle:
    return extract_runtime_bundle(
        record,
        anesthesia_start=case.anesthesia_start,
        anesthesia_end=case.anesthesia_end,
        phase8b_template_root=PHASE8B_ROOT,
        phase8b_index_row=index_row,
        access=access,
        bundle_root=PRIVATE_ROOT / "bundles",
    )


def _bundle_index_row(record, extracted: ExtractedRuntimeBundle) -> dict[str, object]:
    return {
        "bundle_id": extracted.bundle_id,
        "bundle_payload_tree_sha256": extracted.fingerprint,
        "caseid": record.caseid,
        "relative_bundle_directory": f"bundles/{extracted.bundle_id}",
        "subjectid": record.subjectid,
    }


@dataclass
class RunningStatistic:
    count: int = 0
    mean: float = 0.0
    m2: float = 0.0

    def add(self, value: float) -> None:
        value = float(value)
        if not math.isfinite(value):
            raise TrainRuntimeInputError("non-finite scaler source value")
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        self.m2 += delta * (value - self.mean)

    def triple(self) -> tuple[int, float, float]:
        sample_sd = math.sqrt(self.m2 / (self.count - 1)) if self.count > 1 else 0.0
        return self.count, self.mean, sample_sd


def _integral(times: np.ndarray, rates: np.ndarray, start: float, end: float) -> float:
    if end <= start:
        return 0.0
    total = 0.0
    for index, knot in enumerate(times.tolist()):
        next_knot = float(times[index + 1]) if index + 1 < len(times) else end
        left, right = max(start, float(knot)), min(end, next_knot)
        if right > left:
            total += float(rates[index]) * (right - left) / 60.0
    return total


def _fit_scalers(records) -> dict[str, object]:
    statistics = {name: RunningStatistic() for name in S1_FIELDS}
    dynamic_names = {
        "remifentanil_recent_dose_60s_microgram",
        "remifentanil_cumulative_dose_microgram",
        "remifentanil_cp_microgram_per_l",
        "remifentanil_ce_microgram_per_l",
    }
    rate_names = [name for name in S1_FIELDS if name.startswith("remifentanil_rate_")]
    fixed_zero_names = [
        name for name in S1_FIELDS
        if name.startswith("bis_value_") or name.startswith("propofol_")
    ]
    age_names = [name for name in S1_FIELDS if name.startswith("bis_age_seconds_")]
    mask_names = [name for name in S1_FIELDS if name.startswith("bis_mask_")]
    by_case = {record.caseid: record for record in records}
    for record in records:
        statistics["age_years"].add(record.profile.age_years)
        statistics["sex_binary"].add(1.0 if record.profile.sex.value == "male" else 0.0)
        statistics["height_cm"].add(record.profile.height_cm)
        statistics["weight_kg"].add(record.profile.weight_kg)
        for name in fixed_zero_names:
            statistics[name].add(0.0)
        for name in age_names:
            statistics[name].add(30.0)
        for name in mask_names:
            statistics[name].add(0.0)
    for caseid in sorted(by_case, key=lambda value: (int(value), value)):
        row_directory = PRIVATE_ROOT / "bundles" / bundle_id_for_case(caseid)
        _, metadata = verify_complete_bundle(row_directory)
        times = np.load(row_directory / "remifentanil_timestamp_seconds.npy", allow_pickle=False)
        rates = np.load(row_directory / "remifentanil_rate_microgram_per_min.npy", allow_pickle=False)
        for rate in rates.tolist():
            for name in rate_names:
                statistics[name].add(rate)
        for name in dynamic_names:
            statistics[name].add(0.0)
        horizon = float(metadata["episode_horizon_seconds"])
        cumulative = _integral(times, rates, 0.0, horizon)
        recent = _integral(times, rates, max(0.0, horizon - 60.0), horizon)
        # Scaler fitting must be P-neutral and bounded. Runtime episodes retain the
        # full exact-knot schedule; only the normalization reference uses the
        # case's exact total dose as one case-average ZOH input.
        average_rate = cumulative * 60.0 / horizon
        transition = DualDrugSimulator.from_profile(by_case[caseid].profile).advance(
            horizon, 0.0, average_rate,
        )
        statistics["remifentanil_recent_dose_60s_microgram"].add(recent)
        statistics["remifentanil_cumulative_dose_microgram"].add(cumulative)
        statistics["remifentanil_cp_microgram_per_l"].add(transition.remifentanil_cp_microgram_per_l)
        statistics["remifentanil_ce_microgram_per_l"].add(transition.remifentanil_ce_microgram_per_l)
    triples = {name: statistic.triple() for name, statistic in statistics.items()}
    s0 = StateScaler("S0", make_scaler_fields("S0", triples), state_schema_sha256(S0_FIELDS))
    s1 = StateScaler("S1", make_scaler_fields("S1", triples), state_schema_sha256(S1_FIELDS))
    return {
        "binary_and_mask_fields_unchanged": True,
        "epsilon_policy": "sample_sd_le_1e-12_uses_scale_1",
        "fit_case_count": EXPECTED_TRAIN_CASES,
        "fit_split": "train_only",
        "p0_p1_share_same_scaler_for_each_state": True,
        "preprocessing_condition_used_for_fit": False,
        "scalers": {"S0": s0.as_manifest(), "S1": s1.as_manifest()},
        "source": "preprocessing_neutral_zero_propofol_train_patient_and_case_average_zoh_remifentanil_reference",
        "test_case_count_used": 0,
    }


def _preflight_integration(private_ids: list[str]) -> dict[str, object]:
    from vitaldb_state_selection.rl_integration.train_runtime import make_train_runtime_environment

    scalers = load_scaler_registry(SCALER_PATH)
    store = TrainRuntimeInputStore(PRIVATE_ROOT, ROOT)
    rows = []
    for caseid in private_ids:
        for condition in CONDITIONS:
            scaler = scalers["S0" if condition.endswith("S0") else "S1"]
            environment = make_train_runtime_environment(
                store=store, caseid=caseid, condition_id=condition, scaler=scaler, seed=SEED,
            )
            first, info_one = environment.reset(seed=SEED)
            second, info_two = environment.reset(seed=SEED)
            if not np.array_equal(first, second):
                raise TrainRuntimeInputError("actual train environment reset is not deterministic")
            observation, reward, terminated, truncated, info = environment.step(np.asarray([1.0], dtype=np.float32))
            expected = 34 if condition.endswith("S0") else 42
            if first.shape != (expected,) or observation.shape != (expected,):
                raise TrainRuntimeInputError("actual train environment observation shape mismatch")
            if not np.isfinite(first).all() or not np.isfinite(observation).all() or not math.isfinite(reward):
                raise TrainRuntimeInputError("actual train environment produced a non-finite result")
            if info["action_was_clipped"] or terminated or truncated:
                raise TrainRuntimeInputError("actual train environment preflight transition failed")
            rows.append({"condition": condition, "shape": expected, "passed": True})
            environment.close()
    return {
        "case_count": len(private_ids),
        "condition_case_checks": len(rows),
        "conditions": {condition: {"passed": True, "shape": 34 if condition.endswith("S0") else 42} for condition in CONDITIONS},
        "deterministic_reset": True,
        "finite_observation_and_reward": True,
        "no_future_remifentanil_access": True,
        "test_access_count": 0,
    }


def build() -> None:
    started = time.perf_counter()
    before = _phase8b_root()
    records = load_train_patient_records(ROOT)
    cases = load_train_cases(ROOT)
    by_case = {case.caseid: case for case in cases}
    if len(records) != EXPECTED_TRAIN_CASES or set(by_case) != {record.caseid for record in records}:
        raise TrainRuntimeInputError("train patient/timing accounting mismatch")
    phase8b_index = _phase8b_index()
    access = TrainRemifentanilAccessGuard(ROOT)
    PRIVATE_ROOT.mkdir(parents=True, exist_ok=True)
    partials = sorted(PRIVATE_ROOT.rglob("*.partial"))
    for path in partials:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    selected = _preflight_records(records, cases)
    extracted_by_case: dict[str, ExtractedRuntimeBundle] = {}
    # Operational preflight: three distinct train subjects, exact source/checksum/unit gates.
    for record in selected:
        extracted_by_case[record.caseid] = _build_one(record, by_case[record.caseid], phase8b_index[record.caseid], access)
    atomic_json(PRIVATE_ROOT / "preflight_summary.json", {
        "selected_caseids": [record.caseid for record in selected],
        "selected_subject_count": len({record.subjectid for record in selected}),
        "source_and_checksum_gate_passed": True,
        "test_access_count": 0,
    })
    # The passed preflight automatically continues over every sealed train case.
    for record in records:
        if record.caseid not in extracted_by_case:
            extracted_by_case[record.caseid] = _build_one(record, by_case[record.caseid], phase8b_index[record.caseid], access)
    index_rows = [_bundle_index_row(record, extracted_by_case[record.caseid]) for record in records]
    _atomic_csv(
        PRIVATE_ROOT / "private_index.csv",
        ("bundle_id", "bundle_payload_tree_sha256", "caseid", "relative_bundle_directory", "subjectid"),
        index_rows,
    )
    ledger_rows = access.ledger_rows()
    if len(ledger_rows) != EXPECTED_TRAIN_CASES:
        raise TrainRuntimeInputError("train remifentanil logical access accounting mismatch")
    _atomic_csv(
        PRIVATE_ROOT / "access_ledger.csv",
        ("sequence_number", "caseid", "assigned_split", "track_name", "expected_source_sha256", "observed_source_sha256", "access_purpose", "status"),
        ledger_rows,
    )
    root_lines = "".join(
        f"{row['bundle_id']}\t{row['bundle_payload_tree_sha256']}\n"
        for row in sorted(index_rows, key=lambda row: str(row["bundle_id"]))
    )
    private_root_sha = hashlib.sha256(root_lines.encode("utf-8")).hexdigest()
    scaler_registry = _fit_scalers(records)
    atomic_json(SCALER_PATH, scaler_registry)
    preflight = _preflight_integration([record.caseid for record in selected])
    after = _phase8b_root()
    if before != after:
        raise TrainRuntimeInputError("Phase 8B private root changed during Phase 8C")
    partial_count = sum(1 for path in PRIVATE_ROOT.rglob("*") if ".partial" in path.name or path.suffix == ".tmp")
    if partial_count:
        raise TrainRuntimeInputError("partial runtime-input paths remain")
    durations = [float(case.anesthesia_end - case.anesthesia_start) for case in cases]
    rates, knots, total_doses = [], [], []
    for row in index_rows:
        directory = PRIVATE_ROOT / row["relative_bundle_directory"]
        _, metadata = verify_complete_bundle(directory)
        array_times = np.load(directory / "remifentanil_timestamp_seconds.npy", allow_pickle=False)
        array_rates = np.load(directory / "remifentanil_rate_microgram_per_min.npy", allow_pickle=False)
        rates.extend(array_rates.tolist())
        knots.append(int(array_times.size))
        total_doses.append(_integral(array_times, array_rates, 0.0, float(metadata["episode_horizon_seconds"])))
    profile_values = {
        "age_years": _distribution([record.profile.age_years for record in records]),
        "height_cm": _distribution([record.profile.height_cm for record in records]),
        "weight_kg": _distribution([record.profile.weight_kg for record in records]),
    }
    summary = {
        "approved_fallback_used": False,
        "case_subject_mapping_error_count": 0,
        "completed": True,
        "demographic_summary": profile_values,
        "female_profile_count": sum(record.profile.sex.value == "female" for record in records),
        "invalid_profile_count": 0,
        "male_profile_count": sum(record.profile.sex.value == "male" for record in records),
        "missing_required_profile_count": 0,
        "partial_directory_count": partial_count,
        "phase": "Phase 8C",
        "phase8b_private_root_after": after,
        "phase8b_private_root_before": before,
        "phase8b_template_changed": False,
        "preflight": preflight,
        "private_runtime_root_sha256": private_root_sha,
        "remifentanil_duration_seconds": _distribution(durations),
        "remifentanil_schedule_count": len(index_rows),
        "remifentanil_schedule_knot_count": _distribution([float(value) for value in knots]),
        "remifentanil_schedule_rate_microgram_per_min": _distribution(rates),
        "remifentanil_total_dose_microgram": _distribution(total_doses),
        "remifentanil_track": REMIFENTANIL_TRACK,
        "runtime_format_version": RUNTIME_FORMAT_VERSION,
        "runtime_seconds": time.perf_counter() - started,
        "test_metadata_rows_parsed": 0,
        "test_raw_access_count": 0,
        "test_runtime_bundle_count": 0,
        "train_patient_profile_count": len(records),
        "train_remifentanil_logical_access_count": len(ledger_rows),
    }
    atomic_json(SUMMARY_PATH, summary)
    atomic_json(PRIVATE_ROOT / "STORE_COMPLETE.json", {
        "access_ledger_sha256": sha256_path(PRIVATE_ROOT / "access_ledger.csv"),
        "complete": True,
        "private_index_sha256": sha256_path(PRIVATE_ROOT / "private_index.csv"),
        "private_runtime_root_sha256": private_root_sha,
        "test_bundle_count": 0,
        "train_bundle_count": EXPECTED_TRAIN_CASES,
    })
    store = TrainRuntimeInputStore(PRIVATE_ROOT, ROOT)
    if store.verify_all() != private_root_sha:
        raise TrainRuntimeInputError("Phase 8C private store verify-only root mismatch")
    print(json.dumps({"private_runtime_root_sha256": private_root_sha, "train_bundle_count": EXPECTED_TRAIN_CASES}, indent=2))


def verify_only() -> None:
    before = _phase8b_root()
    complete = _json(PRIVATE_ROOT / "STORE_COMPLETE.json")
    if complete.get("train_bundle_count") != EXPECTED_TRAIN_CASES or complete.get("test_bundle_count") != 0:
        raise TrainRuntimeInputError("Phase 8C STORE_COMPLETE accounting mismatch")
    if sha256_path(PRIVATE_ROOT / "private_index.csv") != complete.get("private_index_sha256"):
        raise TrainRuntimeInputError("Phase 8C private index checksum mismatch")
    if sha256_path(PRIVATE_ROOT / "access_ledger.csv") != complete.get("access_ledger_sha256"):
        raise TrainRuntimeInputError("Phase 8C access ledger checksum mismatch")
    store = TrainRuntimeInputStore(PRIVATE_ROOT, ROOT)
    observed = store.verify_all()
    if observed != complete.get("private_runtime_root_sha256"):
        raise TrainRuntimeInputError("Phase 8C private runtime root mismatch")
    if _phase8b_root() != before:
        raise TrainRuntimeInputError("Phase 8B root changed during verify-only")
    partial_count = sum(1 for path in PRIVATE_ROOT.rglob("*") if ".partial" in path.name or path.suffix == ".tmp")
    if partial_count:
        raise TrainRuntimeInputError("Phase 8C partial paths remain")
    print(json.dumps({"private_runtime_root_sha256": observed, "train_bundle_count": len(store.rows), "partial_count": 0}, indent=2))


def smoke() -> None:
    from vitaldb_state_selection.rl_integration.train_runtime import run_train_condition_smoke

    verify_only()
    scalers = load_scaler_registry(SCALER_PATH)
    private_preflight = _json(PRIVATE_ROOT / "preflight_summary.json")
    smoke_caseid = str(private_preflight["selected_caseids"][1])
    before_files = {path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*") if path.is_file()}
    results = []
    for condition in CONDITIONS:
        results.append(run_train_condition_smoke(
            repository_root=ROOT,
            private_root=PRIVATE_ROOT,
            caseid=smoke_caseid,
            condition_id=condition,
            scaler=scalers["S0" if condition.endswith("S0") else "S1"],
        ))
    after_files = {path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*") if path.is_file()}
    created = sorted(after_files - before_files)
    prohibited = [path for path in created if any(token in path.lower() for token in ("checkpoint", "model", ".pt", ".pth", ".ckpt"))]
    if prohibited:
        raise TrainRuntimeInputError(f"PPO smoke persisted prohibited files: {prohibited}")
    atomic_json(SMOKE_PATH, {
        "condition_order": list(CONDITIONS),
        "correctness_only": True,
        "final_performance_claimed": False,
        "model_or_checkpoint_created": False,
        "performance_ranking_computed": False,
        "results": results,
        "seed": SEED,
        "single_seed_only": True,
        "test_access_count": 0,
        "timestep_budget_per_condition": 128,
    })
    print(json.dumps({"conditions": len(results), "all_passed": all(row["status"] == "passed" for row in results)}, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("build", "verify-only", "smoke"), required=True)
    args = parser.parse_args()
    if args.stage == "build":
        build()
    elif args.stage == "verify-only":
        verify_only()
    else:
        smoke()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
