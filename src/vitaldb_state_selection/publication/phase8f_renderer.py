"""Strict, interpretation-free rendering of frozen Phase 8E aggregate results."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

from jsonschema import Draft202012Validator


CONDITIONS = ("P0S0", "P1S0", "P0S1", "P1S1")
METRICS = (
    "mean_absolute_bis_deviation",
    "root_mean_squared_bis_deviation",
    "time_in_bis_40_60_seconds",
    "time_below_bis_40_seconds",
    "time_above_bis_60_seconds",
    "integrated_absolute_bis_error_bis_seconds",
    "maximum_absolute_bis_deviation",
    "cumulative_propofol_amount_mg",
    "mean_propofol_infusion_rate_mg_per_min",
    "action_change_magnitude_mg_per_min",
    "cumulative_episode_reward",
)
CONTRASTS = (
    "P1S0_minus_P0S0",
    "P1S1_minus_P0S1",
    "P0S1_minus_P0S0",
    "P1S1_minus_P1S0",
    "interaction",
)
METRIC_FORMAT = {
    "mean_absolute_bis_deviation": ("BIS points", 3),
    "root_mean_squared_bis_deviation": ("BIS points", 3),
    "time_in_bis_40_60_seconds": ("seconds", 1),
    "time_below_bis_40_seconds": ("seconds", 1),
    "time_above_bis_60_seconds": ("seconds", 1),
    "integrated_absolute_bis_error_bis_seconds": ("BIS-point seconds", 1),
    "maximum_absolute_bis_deviation": ("BIS points", 3),
    "cumulative_propofol_amount_mg": ("mg", 3),
    "mean_propofol_infusion_rate_mg_per_min": ("mg/min", 4),
    "action_change_magnitude_mg_per_min": ("mg/min", 4),
    "cumulative_episode_reward": ("arbitrary reward units", 3),
}
OUTPUT_NAMES = (
    "condition_metrics.csv",
    "condition_metrics.md",
    "condition_metrics.tex",
    "paired_contrasts.csv",
    "paired_contrasts.md",
    "paired_contrasts.tex",
    "publication_summary.json",
)


class Phase8FRenderError(ValueError):
    """Raised before any output write when an aggregate is unsafe or invalid."""


def _duplicate_refusing_object(pairs: Sequence[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise Phase8FRenderError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_aggregate(path: Path | str) -> dict[str, object]:
    try:
        value = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_duplicate_refusing_object,
        )
    except (OSError, json.JSONDecodeError) as error:
        raise Phase8FRenderError(f"aggregate JSON cannot be read: {error}") from error
    if not isinstance(value, dict):
        raise Phase8FRenderError("aggregate root must be an object")
    return value


def _walk(value: object, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise Phase8FRenderError(f"nonfinite value at {path}")
    if isinstance(value, str):
        lowered = value.lower().replace("\\", "/")
        absolute_path = re.match(r"^(?:[a-z]:/|//|/)", lowered) is not None
        if absolute_path or "data/processed/" in lowered:
            raise Phase8FRenderError(f"private or local path leakage at {path}")
    if isinstance(value, Mapping):
        forbidden = ("caseid", "subjectid", "timestamp", "trajectory", "event_value", "raw_value", "private_path", "local_path")
        for key, child in value.items():
            normalized = str(key).lower().replace("_", "")
            if any(token.replace("_", "") in normalized for token in forbidden):
                raise Phase8FRenderError(f"case/event/private payload key is prohibited: {path}.{key}")
            _walk(child, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            _walk(child, f"{path}[{index}]")


def validate_aggregate(payload: Mapping[str, object], schema: Mapping[str, object]) -> None:
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda item: list(item.path))
    if errors:
        message = "; ".join(f"{'.'.join(map(str, error.path)) or '$'}: {error.message}" for error in errors[:12])
        raise Phase8FRenderError(f"aggregate schema validation failed: {message}")
    _walk(payload)
    accounting = payload["case_accounting"]
    if accounting["completed_per_condition"] + accounting["failed_per_condition"] != 490:
        raise Phase8FRenderError("completed plus failed case accounting must equal 490")
    condition_rows = payload["conditions"]
    if tuple(row["condition_id"] for row in condition_rows) != CONDITIONS:
        raise Phase8FRenderError("conditions must be unique and in frozen order")
    for row in condition_rows:
        if row["failed_case_count"] != accounting["failed_per_condition"]:
            raise Phase8FRenderError("condition failure count disagrees with explicit accounting")
        names = tuple(metric["metric_name"] for metric in row["metrics"])
        if names != METRICS:
            raise Phase8FRenderError("condition metrics must be unique and in frozen order")
        for metric in row["metrics"]:
            expected_unit, _ = METRIC_FORMAT[metric["metric_name"]]
            if metric["unit"] != expected_unit:
                raise Phase8FRenderError(f"metric unit mismatch: {metric['metric_name']}")
            if not (metric["minimum"] <= metric["q1"] <= metric["median"] <= metric["q3"] <= metric["maximum"]):
                raise Phase8FRenderError(f"metric order-statistic inconsistency: {metric['metric_name']}")
    expected_pairs = [(metric, contrast) for metric in METRICS for contrast in CONTRASTS]
    observed_pairs = [(row["metric_name"], row["contrast_id"]) for row in payload["contrasts"]]
    if observed_pairs != expected_pairs:
        raise Phase8FRenderError("contrast rows must cover every frozen metric/contrast exactly once in order")
    for row in payload["contrasts"]:
        expected_unit, _ = METRIC_FORMAT[row["metric_name"]]
        if row["unit"] != expected_unit:
            raise Phase8FRenderError(f"contrast unit mismatch: {row['metric_name']}")
        if row["bootstrap_ci_95"][0] > row["bootstrap_ci_95"][1]:
            raise Phase8FRenderError("bootstrap interval bounds are reversed")
        if row["holm_adjusted_p"] + 1e-15 < row["paired_sign_flip_permutation_p"]:
            raise Phase8FRenderError("Holm-adjusted p-value cannot be below its raw p-value")


def _format(value: float, precision: int) -> str:
    return f"{float(value):.{precision}f}"


def condition_table_rows(payload: Mapping[str, object]) -> list[dict[str, object]]:
    by_condition = {row["condition_id"]: row for row in payload["conditions"]}
    rows: list[dict[str, object]] = []
    for metric_name in METRICS:
        unit, precision = METRIC_FORMAT[metric_name]
        for condition in CONDITIONS:
            metric = next(row for row in by_condition[condition]["metrics"] if row["metric_name"] == metric_name)
            rows.append({
                "metric_name": metric_name,
                "unit": unit,
                "condition_id": condition,
                "subject_count": metric["subject_count"],
                "mean": _format(metric["mean"], precision),
                "sd": _format(metric["sd"], precision),
                "median": _format(metric["median"], precision),
                "q1": _format(metric["q1"], precision),
                "q3": _format(metric["q3"], precision),
                "minimum": _format(metric["minimum"], precision),
                "maximum": _format(metric["maximum"], precision),
            })
    return rows


def contrast_table_rows(payload: Mapping[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for source in payload["contrasts"]:
        _, precision = METRIC_FORMAT[source["metric_name"]]
        rows.append({
            "metric_name": source["metric_name"],
            "unit": source["unit"],
            "contrast_id": source["contrast_id"],
            "subject_count": source["subject_count"],
            "mean_difference": _format(source["mean_difference"], precision),
            "median_difference": _format(source["median_difference"], precision),
            "ci_95_lower": _format(source["bootstrap_ci_95"][0], precision),
            "ci_95_upper": _format(source["bootstrap_ci_95"][1], precision),
            "raw_p": _format(source["paired_sign_flip_permutation_p"], 6),
            "holm_adjusted_p": _format(source["holm_adjusted_p"], 6),
            "cohens_dz": _format(source["cohens_dz"], 4),
        })
    return rows


def _csv(rows: Sequence[Mapping[str, object]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def _markdown(rows: Sequence[Mapping[str, object]]) -> str:
    fields = list(rows[0])
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    lines.extend("| " + " | ".join(str(row[field]) for field in fields) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def _latex_escape(value: object) -> str:
    text = str(value)
    for source, target in (("\\", r"\textbackslash{}"), ("_", r"\_"), ("%", r"\%"), ("&", r"\&"), ("#", r"\#")):
        text = text.replace(source, target)
    return text


def _latex(rows: Sequence[Mapping[str, object]]) -> str:
    fields = list(rows[0])
    row_end = r" \\"
    lines = [
        r"\begin{tabular}{" + "l" * len(fields) + "}",
        r"\hline",
        " & ".join(_latex_escape(field) for field in fields) + row_end,
        r"\hline",
    ]
    lines.extend(" & ".join(_latex_escape(row[field]) for field in fields) + row_end for row in rows)
    lines.extend((r"\hline", r"\end{tabular}"))
    return "\n".join(lines) + "\n"


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"


def render_payloads(payload: Mapping[str, object], *, source_sha256: str | None = None) -> dict[str, bytes]:
    condition_rows = condition_table_rows(payload)
    contrast_rows = contrast_table_rows(payload)
    canonical_sha = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    source_sha = source_sha256 or canonical_sha
    summary = {
        "schema_version": "phase8f-publication-summary-v1",
        "source_aggregate_sha256": source_sha,
        "source_checksum_basis": "input_file_bytes" if source_sha256 else "canonical_json",
        "canonical_aggregate_sha256": canonical_sha,
        "data_origin": payload["data_origin"],
        "condition_order": list(CONDITIONS),
        "metric_order": list(METRICS),
        "contrast_order": list(CONTRASTS),
        "condition_metric_row_count": len(condition_rows),
        "contrast_row_count": len(contrast_rows),
        "condition_metrics": condition_rows,
        "paired_contrasts": contrast_rows,
        "interpretation_performed": False,
        "best_condition_selected": False,
        "public_case_level_row_count": 0,
        "public_event_level_row_count": 0,
    }
    text = {
        "condition_metrics.csv": _csv(condition_rows),
        "condition_metrics.md": _markdown(condition_rows),
        "condition_metrics.tex": _latex(condition_rows),
        "paired_contrasts.csv": _csv(contrast_rows),
        "paired_contrasts.md": _markdown(contrast_rows),
        "paired_contrasts.tex": _latex(contrast_rows),
        "publication_summary.json": canonical_json(summary),
    }
    return {name: value.encode("utf-8") for name, value in text.items()}


def write_outputs(output_dir: Path | str, outputs: Mapping[str, bytes], *, overwrite: bool) -> None:
    destination = Path(output_dir)
    existing = [destination / name for name in OUTPUT_NAMES if (destination / name).exists()]
    if existing and not overwrite:
        raise Phase8FRenderError("publication output exists; pass --overwrite to replace only known aggregate files")
    destination.mkdir(parents=True, exist_ok=True)
    for name in OUTPUT_NAMES:
        path = destination / name
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{name}.", suffix=".tmp", dir=destination)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(outputs[name])
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
