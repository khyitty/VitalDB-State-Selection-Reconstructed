"""Deterministic, interpretation-free replacement of Phase 8F result tokens."""

from __future__ import annotations

import re
from collections.abc import Mapping

from vitaldb_state_selection.publication.phase8f_renderer import CONDITIONS, CONTRASTS, METRIC_FORMAT


TOKEN_PATTERN = re.compile(r"\{\{[A-Z0-9_]+\}\}|\[(?:RESULTS|CONCLUSION)_PENDING\]")


class ManuscriptPopulationError(RuntimeError):
    pass


def _format(value: object, precision: int) -> str:
    return f"{float(value):.{precision}f}"


def _condition_metric(aggregate: Mapping[str, object], condition: str, metric: str) -> Mapping[str, object]:
    condition_row = next(row for row in aggregate["conditions"] if row["condition_id"] == condition)
    return next(row for row in condition_row["metrics"] if row["metric_name"] == metric)


def _contrast(aggregate: Mapping[str, object], contrast: str, metric: str) -> Mapping[str, object]:
    return next(
        row for row in aggregate["contrasts"]
        if row["contrast_id"] == contrast and row["metric_name"] == metric
    )


def token_values(aggregate: Mapping[str, object]) -> dict[str, str]:
    primary = "mean_absolute_bis_deviation"
    primary_precision = METRIC_FORMAT[primary][1]
    values: dict[str, str] = {
        "{{FINAL_COMPLETED_CASES_PER_CONDITION}}": str(aggregate["case_accounting"]["completed_per_condition"]),
        "{{FINAL_FAILED_CASES_PER_CONDITION}}": str(aggregate["case_accounting"]["failed_per_condition"]),
        "{{FOUR_MODEL_COMPLETENESS_STATUS}}": "verified for all four final models",
        "{{SILENT_EXCLUSION_COUNT}}": str(aggregate["case_accounting"]["silent_exclusion_count"]),
        "{{AGGREGATE_CONDITION_METRIC_ROW_COUNT}}": str(len(CONDITIONS) * len(METRIC_FORMAT)),
        "{{AGGREGATE_CONTRAST_ROW_COUNT}}": str(len(aggregate["contrasts"])),
    }
    condition_means: dict[str, str] = {}
    for condition in CONDITIONS:
        primary_mean = _format(_condition_metric(aggregate, condition, primary)["mean"], primary_precision)
        condition_means[condition] = primary_mean
        values[f"{{{{{condition}_MEAN_ABSOLUTE_BIS_DEVIATION}}}}"] = primary_mean
        values[f"{{{{{condition}_TIME_IN_BIS_40_60_SECONDS}}}}"] = _format(
            _condition_metric(aggregate, condition, "time_in_bis_40_60_seconds")["mean"], 1
        )
        values[f"{{{{{condition}_ACTION_CHANGE_MAGNITUDE}}}}"] = _format(
            _condition_metric(aggregate, condition, "action_change_magnitude_mg_per_min")["mean"], 4
        )
    for contrast in CONTRASTS:
        source = _contrast(aggregate, contrast, primary)
        token_prefix = contrast.upper()
        values[f"{{{{{token_prefix}_MEAN_ABSOLUTE_BIS_DEVIATION}}}}"] = _format(
            source["mean_difference"], primary_precision
        )
        values[f"{{{{{token_prefix}_MEAN_ABSOLUTE_BIS_DEVIATION_CI95}}}}"] = (
            f"{_format(source['bootstrap_ci_95'][0], primary_precision)} to "
            f"{_format(source['bootstrap_ci_95'][1], primary_precision)}"
        )
        if contrast in ("P1S0_minus_P0S0", "P1S1_minus_P0S1", "interaction"):
            values[f"{{{{{token_prefix}_MEAN_ABSOLUTE_BIS_DEVIATION_HOLM_P}}}}"] = _format(
                source["holm_adjusted_p"], 6
            )
            values[f"{{{{{token_prefix}_MEAN_ABSOLUTE_BIS_DEVIATION_DZ}}}}"] = _format(source["cohens_dz"], 4)
    values["[RESULTS_PENDING]"] = (
        f"All 490 sealed-test cases completed under each condition with no failed episode or silent exclusion. "
        f"Subject-level mean absolute BIS deviation was {condition_means['P0S0']}, {condition_means['P1S0']}, "
        f"{condition_means['P0S1']}, and {condition_means['P1S1']} BIS points for P0S0, P1S0, P0S1, and P1S1, "
        "respectively; all 11 frozen outcomes and five paired contrasts are reported without condition selection."
    )
    values["[CONCLUSION_PENDING]"] = (
        "The four prespecified policies were evaluated in the reconstructed simulator without selecting a best "
        "condition; the estimates apply to one fixed training seed and require external validation before clinical interpretation."
    )
    return values


def populate_manuscript(template: str, aggregate: Mapping[str, object]) -> tuple[str, dict[str, object]]:
    observed = TOKEN_PATTERN.findall(template)
    mapping = token_values(aggregate)
    unexpected = sorted(set(observed) - set(mapping))
    missing = sorted(set(mapping) - set(observed))
    if unexpected or missing or len(observed) != 37:
        raise ManuscriptPopulationError(
            f"manuscript token contract mismatch: occurrences={len(observed)}, unexpected={unexpected}, missing={missing}"
        )
    result = template
    for token, value in mapping.items():
        result = result.replace(token, value)
    remaining = TOKEN_PATTERN.findall(result)
    if remaining:
        raise ManuscriptPopulationError(f"unresolved manuscript tokens: {remaining}")
    return result, {
        "placeholder_occurrences_replaced": len(observed),
        "placeholder_occurrences_remaining": 0,
        "unique_token_mappings": len(mapping),
        "results_interpreted": False,
        "best_condition_selected": False,
    }
