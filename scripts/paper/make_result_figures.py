"""Build result figures only from frozen, public Phase 8E/8F artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "vitaldb-paper-mpl"))

import matplotlib.pyplot as plt
import numpy as np

from plot_style import CONDITION_STYLE, DOUBLE_COLUMN_WIDTH, apply_paper_style, save_figure

ROOT = Path(__file__).resolve().parents[2]
AGGREGATE = ROOT / "paper/generated/phase8e_aggregate_results.json"
STATISTICS = ROOT / "paper/generated/phase8e_statistics_results.json"
INTEGRITY = ROOT / "data/manifests/phase8e_final_results_integrity.json"
FIGURE_DIR = ROOT / "paper/figures"
DATA_DIR = ROOT / "paper/figure_data"

CONDITION_ORDER = ("P0S0", "P1S0", "P0S1", "P1S1")
RESULT_METRICS = (
    ("mean_absolute_bis_deviation", "Absolute BIS deviation (BIS points)"),
    ("time_above_bis_60_seconds", "Time with BIS > 60 (s)"),
)
CONTRAST_ORDER = (
    "P1S0_minus_P0S0",
    "P1S1_minus_P0S1",
    "P0S1_minus_P0S0",
    "P1S1_minus_P1S0",
)
CONTRAST_LABEL = {
    "P1S0_minus_P0S0": "P1S0 − P0S0",
    "P1S1_minus_P0S1": "P1S1 − P0S1",
    "P0S1_minus_P0S0": "P0S1 − P0S0",
    "P1S1_minus_P1S0": "P1S1 − P1S0",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def load_frozen_artifacts() -> tuple[dict, dict]:
    integrity = json.loads(INTEGRITY.read_text(encoding="utf-8"))
    if sha256(AGGREGATE) != integrity["aggregate_sha256"]:
        raise RuntimeError("aggregate artifact checksum does not match frozen integrity record")
    if sha256(STATISTICS) != integrity["statistics_sha256"]:
        raise RuntimeError("statistics artifact checksum does not match frozen integrity record")
    if integrity["completed_per_condition"] != 490 or integrity["failed_per_condition"] != 0:
        raise RuntimeError("final evaluation accounting is incomplete")
    if integrity["public_case_level_row_count"] != 0 or integrity["public_event_level_row_count"] != 0:
        raise RuntimeError("unexpected public case/event rows; disclosure contract changed")
    return (
        json.loads(AGGREGATE.read_text(encoding="utf-8")),
        json.loads(STATISTICS.read_text(encoding="utf-8")),
    )


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def extract_condition_rows(aggregate: dict) -> list[dict]:
    rows: list[dict] = []
    by_condition = {row["condition_id"]: row for row in aggregate["conditions"]}
    for metric_name, _ in RESULT_METRICS:
        for condition in CONDITION_ORDER:
            item = next(
                metric
                for metric in by_condition[condition]["metrics"]
                if metric["metric_name"] == metric_name
            )
            rows.append(
                {
                    "condition_id": condition,
                    "preprocessing_profile": condition[:2],
                    "state_profile": condition[2:],
                    "metric_name": metric_name,
                    "unit": item["unit"],
                    "median": item["median"],
                    "q1": item["q1"],
                    "q3": item["q3"],
                    "case_count": by_condition[condition]["case_count"],
                    "subject_count": item["subject_count"],
                    "seed": by_condition[condition]["seed"],
                    "source_artifact": AGGREGATE.relative_to(ROOT).as_posix(),
                    "source_sha256": sha256(AGGREGATE),
                    "source_field": "conditions[].metrics[]",
                }
            )
    return rows


def extract_contrast_rows(statistics: dict) -> list[dict]:
    selected = set(CONTRAST_ORDER)
    metrics = {name for name, _ in RESULT_METRICS}
    rows: list[dict] = []
    for item in statistics["contrasts"]:
        if item["contrast_id"] not in selected or item["metric_name"] not in metrics:
            continue
        rows.append(
            {
                "contrast_id": item["contrast_id"],
                "metric_name": item["metric_name"],
                "unit": item["unit"],
                "mean_difference": item["mean_difference"],
                "ci_95_low": item["bootstrap_ci_95"][0],
                "ci_95_high": item["bootstrap_ci_95"][1],
                "cohens_dz": item["cohens_dz"],
                "subject_count": item["subject_count"],
                "bootstrap_replicates": statistics["bootstrap_replicates"],
                "random_seed": statistics["random_seed"],
                "source_artifact": STATISTICS.relative_to(ROOT).as_posix(),
                "source_sha256": sha256(STATISTICS),
                "source_field": "contrasts[]",
            }
        )
    expected = len(CONTRAST_ORDER) * len(RESULT_METRICS)
    if len(rows) != expected:
        raise RuntimeError(f"expected {expected} frozen contrast rows, found {len(rows)}")
    return rows


def make_main_figure(rows: list[dict]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(DOUBLE_COLUMN_WIDTH, 2.55))
    for panel, ((metric_name, ylabel), ax) in enumerate(zip(RESULT_METRICS, axes)):
        selected = [row for row in rows if row["metric_name"] == metric_name]
        x = np.arange(len(selected), dtype=float)
        for index, row in enumerate(selected):
            style = CONDITION_STYLE[row["condition_id"]]
            y = float(row["median"])
            yerr = np.array([[y - float(row["q1"])], [float(row["q3"]) - y]])
            ax.errorbar(
                x[index],
                y,
                yerr=yerr,
                color=style["color"],
                marker=style["marker"],
                linestyle="none",
                capsize=3,
                capthick=0.8,
                markeredgecolor="black",
                markeredgewidth=0.35,
                zorder=3,
            )
        ax.set_xticks(x, [row["condition_id"] for row in selected])
        ax.set_ylabel(ylabel)
        ax.set_xlabel("Configuration")
        ax.text(0.01, 0.98, f"({chr(97 + panel)})", transform=ax.transAxes, va="top", fontweight="bold")
        ax.set_xlim(-0.55, len(selected) - 0.45)
    fig.subplots_adjust(wspace=0.34)
    save_figure(fig, FIGURE_DIR / "main_control_performance")
    plt.close(fig)


def target_condition(contrast_id: str) -> str:
    return contrast_id.split("_minus_")[0]


def make_paired_figure(rows: list[dict]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(DOUBLE_COLUMN_WIDTH, 2.75))
    for panel, ((metric_name, xlabel), ax) in enumerate(zip(RESULT_METRICS, axes)):
        indexed = {(row["metric_name"], row["contrast_id"]): row for row in rows}
        selected = [indexed[(metric_name, contrast)] for contrast in CONTRAST_ORDER]
        y = np.arange(len(selected))[::-1]
        for ypos, row in zip(y, selected):
            style = CONDITION_STYLE[target_condition(row["contrast_id"])]
            mean = float(row["mean_difference"])
            low = float(row["ci_95_low"])
            high = float(row["ci_95_high"])
            ax.errorbar(
                mean,
                ypos,
                xerr=np.array([[mean - low], [high - mean]]),
                color=style["color"],
                marker=style["marker"],
                linestyle="none",
                capsize=3,
                capthick=0.8,
                markeredgecolor="black",
                markeredgewidth=0.35,
                zorder=3,
            )
        ax.axvline(0.0, color="#4D4D4D", linewidth=0.8, linestyle=":")
        ax.set_yticks(y, [CONTRAST_LABEL[row["contrast_id"]] for row in selected])
        ax.set_xlabel(f"Mean paired difference\n{xlabel}")
        ax.grid(axis="x")
        ax.grid(axis="y", visible=False)
        ax.set_title(f"({chr(97 + panel)})", loc="left", pad=2, fontweight="bold")
    fig.subplots_adjust(wspace=0.48)
    save_figure(fig, FIGURE_DIR / "paired_control_effects")
    plt.close(fig)


def verify_csv_rows(condition_rows: list[dict], contrast_rows: list[dict]) -> None:
    with (DATA_DIR / "main_control_summary.csv").open(encoding="utf-8", newline="") as stream:
        observed_condition = list(csv.DictReader(stream))
    with (DATA_DIR / "paired_control_effects.csv").open(encoding="utf-8", newline="") as stream:
        observed_contrast = list(csv.DictReader(stream))
    if len(observed_condition) != len(condition_rows) or len(observed_contrast) != len(contrast_rows):
        raise RuntimeError("plot-ready CSV row count mismatch")
    for expected, observed in zip(condition_rows, observed_condition):
        for key in ("median", "q1", "q3"):
            if float(observed[key]) != float(expected[key]):
                raise RuntimeError(f"condition CSV value mismatch: {key}")
    for expected, observed in zip(contrast_rows, observed_contrast):
        for key in ("mean_difference", "ci_95_low", "ci_95_high"):
            if float(observed[key]) != float(expected[key]):
                raise RuntimeError(f"contrast CSV value mismatch: {key}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    aggregate, statistics = load_frozen_artifacts()
    condition_rows = extract_condition_rows(aggregate)
    contrast_rows = extract_contrast_rows(statistics)
    condition_fields = list(condition_rows[0])
    contrast_fields = list(contrast_rows[0])
    if not args.verify_only:
        write_csv(DATA_DIR / "main_control_summary.csv", condition_fields, condition_rows)
        write_csv(DATA_DIR / "paired_control_effects.csv", contrast_fields, contrast_rows)
        apply_paper_style()
        make_main_figure(condition_rows)
        make_paired_figure(contrast_rows)
    verify_csv_rows(condition_rows, contrast_rows)
    print(
        json.dumps(
            {
                "verified": True,
                "condition_rows": len(condition_rows),
                "contrast_rows": len(contrast_rows),
                "aggregate_sha256": sha256(AGGREGATE),
                "statistics_sha256": sha256(STATISTICS),
                "figures_written": 0 if args.verify_only else 2,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
