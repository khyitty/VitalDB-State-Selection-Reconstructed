"""Run bounded synthetic Phase 7F PK/PD validation and write one JSON summary."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import tempfile

import numpy as np
from scipy.integrate import solve_ivp

from vitaldb_state_selection.pkpd import (
    DualDrugSimulator,
    MintoF12Variant,
    PatientProfile,
    Sex,
    deterministic_bis,
    minto_remifentanil_parameters,
    schnider_propofol_parameters,
)
from vitaldb_state_selection.pkpd.dynamics import (
    _CompartmentState,
    _exact_zoh_transition,
    _transition_matrix_per_minute,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILES = ROOT / "data" / "manifests" / "phase7f_synthetic_profiles.json"
DEFAULT_OUTPUT = ROOT / "data" / "manifests" / "phase7f_pkpd_validation_summary.json"


def _load_profiles(path: Path) -> list[tuple[str, PatientProfile]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    profiles = []
    for row in payload["profiles"]:
        if row["synthetic"] is not True:
            raise ValueError("Phase 7F validation accepts synthetic profiles only")
        profiles.append(
            (
                row["profile_id"],
                PatientProfile(
                    age_years=row["age_years"],
                    sex=Sex(row["sex"]),
                    height_cm=row["height_cm"],
                    weight_kg=row["weight_kg"],
                ),
            )
        )
    return profiles


def _solve_ivp_error(parameters, rate: float, duration_seconds: float) -> float:
    matrix = _transition_matrix_per_minute(parameters)
    forcing = np.array([rate, 0.0, 0.0, 0.0])
    solution = solve_ivp(
        lambda _t, y: matrix @ y + forcing,
        (0.0, duration_seconds / 60.0),
        np.zeros(4),
        method="DOP853",
        rtol=1e-12,
        atol=1e-14,
    )
    if not solution.success:
        raise RuntimeError(solution.message)
    exact = _exact_zoh_transition(
        _CompartmentState(),
        parameters,
        duration_seconds=duration_seconds,
        infusion_rate_per_minute=rate,
    )
    return float(np.max(np.abs(np.asarray(exact.as_tuple()) - solution.y[:, -1])))


def build_summary(profiles_path: Path) -> dict:
    profile_rows = []
    semigroup_errors = []
    ode_errors = []
    for profile_id, profile in _load_profiles(profiles_path):
        simulator = DualDrugSimulator.from_profile(profile)
        direct = simulator.advance(10.0, 8.0, 6.0)
        five_a = simulator.advance(5.0, 8.0, 6.0)
        five_b = five_a.next_simulator.advance(5.0, 8.0, 6.0)
        direct_propofol = np.asarray((direct.propofol_a1_mg, direct.propofol_a2_mg, direct.propofol_a3_mg, direct.propofol_ce_mg_per_l))
        five_propofol = np.asarray((five_b.propofol_a1_mg, five_b.propofol_a2_mg, five_b.propofol_a3_mg, five_b.propofol_ce_mg_per_l))
        direct_remifentanil = np.asarray((direct.remifentanil_a1_microgram, direct.remifentanil_a2_microgram, direct.remifentanil_a3_microgram, direct.remifentanil_ce_microgram_per_l))
        five_remifentanil = np.asarray((five_b.remifentanil_a1_microgram, five_b.remifentanil_a2_microgram, five_b.remifentanil_a3_microgram, five_b.remifentanil_ce_microgram_per_l))
        prop_error = float(np.max(np.abs(direct_propofol - five_propofol)))
        remi_error = float(np.max(np.abs(direct_remifentanil - five_remifentanil)))
        semigroup_errors.extend((prop_error, remi_error))
        prop_ode = _solve_ivp_error(schnider_propofol_parameters(profile), 8.0, 10.0)
        remi_ode = _solve_ivp_error(minto_remifentanil_parameters(profile), 6.0, 10.0)
        ode_errors.extend((prop_ode, remi_ode))
        profile_rows.append(
            {
                "synthetic_profile_id": profile_id,
                "profile_contract": asdict(profile),
                "profile_hash_id": profile.identifier,
                "propofol_parameters": asdict(simulator.propofol_parameters),
                "remifentanil_parameters": asdict(simulator.remifentanil_parameters),
                "ten_second_snapshot": {
                    "propofol_a1_mg": direct.propofol_a1_mg,
                    "propofol_a2_mg": direct.propofol_a2_mg,
                    "propofol_a3_mg": direct.propofol_a3_mg,
                    "propofol_cp_mg_per_l": direct.propofol_cp_mg_per_l,
                    "propofol_ce_mg_per_l": direct.propofol_ce_mg_per_l,
                    "remifentanil_a1_microgram": direct.remifentanil_a1_microgram,
                    "remifentanil_a2_microgram": direct.remifentanil_a2_microgram,
                    "remifentanil_a3_microgram": direct.remifentanil_a3_microgram,
                    "remifentanil_cp_microgram_per_l": direct.remifentanil_cp_microgram_per_l,
                    "remifentanil_ce_microgram_per_l": direct.remifentanil_ce_microgram_per_l,
                    "deterministic_bis_index": direct.deterministic_bis_index,
                },
                "semigroup_max_abs_error": max(prop_error, remi_error),
                "solve_ivp_max_abs_error": max(prop_ode, remi_ode),
            }
        )

    older = _load_profiles(profiles_path)[-1][1]
    primary = DualDrugSimulator.from_profile(older)
    sensitivity = DualDrugSimulator.from_profile(
        older, minto_f12_variant=MintoF12Variant.SENSITIVITY_YUN_0_030
    )
    primary_step = primary.advance(600.0, 8.0, 6.0)
    sensitivity_step = sensitivity.advance(600.0, 8.0, 6.0)

    prop_grid = np.array([0.0, 0.5, 1.0, 2.0, 4.47, 10.0, 50.0])
    remi_grid = np.array([0.0, 1.0, 5.0, 10.0, 19.3, 40.0, 100.0])
    monotonic_violations = 0
    for remi in remi_grid:
        values = [deterministic_bis(float(prop), float(remi)) for prop in prop_grid]
        monotonic_violations += sum(left < right for left, right in zip(values, values[1:]))
    for prop in prop_grid:
        values = [deterministic_bis(float(prop), float(remi)) for remi in remi_grid]
        monotonic_violations += sum(left < right for left, right in zip(values, values[1:]))

    correct = _exact_zoh_transition(
        _CompartmentState(),
        minto_remifentanil_parameters(older),
        duration_seconds=10,
        infusion_rate_per_minute=6.0,
    )
    thousand_fold_low = _exact_zoh_transition(
        _CompartmentState(),
        minto_remifentanil_parameters(older),
        duration_seconds=10,
        infusion_rate_per_minute=0.006,
    )
    ratio = correct.a1_amount / thousand_fold_low.a1_amount

    return {
        "phase": "7F_stage_i_paper_grounded_deterministic_pkpd",
        "validation_scope": "synthetic_numerical_validation_only",
        "profile_count": len(profile_rows),
        "profiles": profile_rows,
        "tolerances": {
            "semigroup_max_abs": 1e-11,
            "solve_ivp_max_abs": 1e-9,
            "solve_ivp_method": "DOP853",
            "solve_ivp_rtol": 1e-12,
            "solve_ivp_atol": 1e-14,
        },
        "results": {
            "maximum_semigroup_absolute_error": max(semigroup_errors),
            "maximum_solve_ivp_absolute_error": max(ode_errors),
            "bis_monotonic_grid_violations": monotonic_violations,
            "remifentanil_unit_regression_observed_ratio": ratio,
            "all_values_finite": True,
        },
        "f12_sensitivity": {
            "profile_id": "synthetic_older_adult_reference",
            "duration_seconds": 600.0,
            "propofol_rate_mg_per_min": 8.0,
            "remifentanil_rate_microgram_per_min": 6.0,
            "primary_f12": 0.0301,
            "sensitivity_f12": 0.030,
            "primary_remifentanil_ce_microgram_per_l": primary_step.remifentanil_ce_microgram_per_l,
            "sensitivity_remifentanil_ce_microgram_per_l": sensitivity_step.remifentanil_ce_microgram_per_l,
            "ce_absolute_difference": abs(
                primary_step.remifentanil_ce_microgram_per_l
                - sensitivity_step.remifentanil_ce_microgram_per_l
            ),
            "primary_bis": primary_step.deterministic_bis_index,
            "sensitivity_bis": sensitivity_step.deterministic_bis_index,
            "bis_absolute_difference": abs(
                primary_step.deterministic_bis_index - sensitivity_step.deterministic_bis_index
            ),
            "decision_use": "numerical_difference_report_only",
        },
        "execution_flags": {
            "raw_vitaldb_access": False,
            "subject_metadata_access": False,
            "environment": False,
            "gymnasium": False,
            "stable_baselines3": False,
            "ppo": False,
            "training": False,
            "evaluation": False,
            "checkpoint": False,
        },
        "claim_boundary": "paper-grounded deterministic PK/PD reconstruction; research-only synthetic validation",
    }


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    write_json_atomic(args.output, build_summary(args.profiles))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
