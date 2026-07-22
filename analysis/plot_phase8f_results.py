"""Render publication-safe Phase 8F confirmatory figures from frozen CSV tables."""

from __future__ import annotations

import atexit
import hashlib
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# The managed Windows runtime cannot write the user's default Matplotlib cache.
# Use an ephemeral, repository-external cache and remove it on normal exit.
_MPL_CONFIG_DIR = tempfile.mkdtemp(prefix="phase8f-matplotlib-")
os.environ["MPLCONFIGDIR"] = _MPL_CONFIG_DIR
atexit.register(shutil.rmtree, _MPL_CONFIG_DIR, ignore_errors=True)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


SOURCE_COMMIT = "71156050465e64892032b475974787b196eb2c3f"
CONDITION_SHA256 = "9e452bd0ab58228b23aba1cc4052d491564f89944aa64c0caf17fd2dea6675ca"
CONTRAST_SHA256 = "67bedc0a92017adaa07393e5ba31446698ffc3dfc4e3e43592f4085343b585fe"
AGGREGATE_SHA256 = "2939f9580a992ef8f43d9f57bc2c7c5a1159b147d3739a6a8809932ac81fcae1"
STATISTICS_SHA256 = "681926cb34830cf11391994dbc7d7c14352e94527c2f36549a6fe86547def6ff"
SUBJECT_COUNT = 483
PNG_DPI = 600

CONDITIONS = ("P0S0", "P1S0", "P0S1", "P1S1")
PREPROCESSING = ("P0", "P1")
STATES = ("S0", "S1")
CONTRASTS = (
    "P1S0_minus_P0S0",
    "P1S1_minus_P0S1",
    "P0S1_minus_P0S0",
    "P1S1_minus_P1S0",
    "interaction",
)
CONTRAST_LABELS = {
    "P1S0_minus_P0S0": "Preprocessing within S0\nP1S0 − P0S0",
    "P1S1_minus_P0S1": "Preprocessing within S1\nP1S1 − P0S1",
    "P0S1_minus_P0S0": "State within P0\nP0S1 − P0S0",
    "P1S1_minus_P1S0": "State within P1\nP1S1 − P1S0",
    "interaction": "Interaction",
}

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

GROUPS = {
    "accuracy": (
        "mean_absolute_bis_deviation",
        "root_mean_squared_bis_deviation",
        "integrated_absolute_bis_error_bis_seconds",
        "maximum_absolute_bis_deviation",
    ),
    "range": (
        "time_in_bis_40_60_seconds",
        "time_below_bis_40_seconds",
        "time_above_bis_60_seconds",
    ),
    "control": (
        "cumulative_propofol_amount_mg",
        "mean_propofol_infusion_rate_mg_per_min",
        "action_change_magnitude_mg_per_min",
        "cumulative_episode_reward",
    ),
}

MAIN_METRICS = (
    "mean_absolute_bis_deviation",
    "time_in_bis_40_60_seconds",
    "cumulative_propofol_amount_mg",
    "action_change_magnitude_mg_per_min",
)

METRIC_LABELS = {
    "mean_absolute_bis_deviation": "Mean absolute BIS deviation\n(BIS points; lower is better)",
    "root_mean_squared_bis_deviation": "Root mean squared BIS deviation\n(BIS points; lower is better)",
    "time_in_bis_40_60_seconds": "Time in BIS 40–60\n(min; higher is better)",
    "time_below_bis_40_seconds": "Time below BIS 40\n(min; lower is better)",
    "time_above_bis_60_seconds": "Time above BIS 60\n(min; lower is better)",
    "integrated_absolute_bis_error_bis_seconds": "Integrated absolute BIS error\n(BIS-point min; lower is better)",
    "maximum_absolute_bis_deviation": "Maximum absolute BIS deviation\n(BIS points; lower is better)",
    "cumulative_propofol_amount_mg": "Cumulative propofol amount\n(mg)",
    "mean_propofol_infusion_rate_mg_per_min": "Mean propofol infusion rate\n(mg/min)",
    "action_change_magnitude_mg_per_min": "Action-change magnitude\n(mg/min; lower is smoother)",
    "cumulative_episode_reward": "Cumulative episode reward\n(arbitrary reward units)",
}

TIME_TRANSFORMS = {
    "time_in_bis_40_60_seconds",
    "time_below_bis_40_seconds",
    "time_above_bis_60_seconds",
    "integrated_absolute_bis_error_bis_seconds",
}

LINE_STYLES = {
    "P0": {"color": "#111111", "linestyle": "-", "marker": "o", "label": "P0 preprocessing"},
    "P1": {"color": "#6b6b6b", "linestyle": "--", "marker": "s", "label": "P1 preprocessing"},
}

EXPECTED_OUTPUTS = {
    "figure_main_interaction": (7.2, 5.6),
    "figure_main_contrast_forest": (7.2, 6.4),
    "figure_mae_interaction": (3.5, 3.0),
    "figure_supp_accuracy_interactions": (7.2, 6.0),
    "figure_supp_range_interactions": (7.2, 5.6),
    "figure_supp_control_interactions": (7.2, 6.0),
    "figure_supp_accuracy_forest": (7.2, 6.4),
    "figure_supp_range_forest": (7.2, 6.4),
    "figure_supp_control_forest": (7.2, 6.4),
}


class PlotInputError(RuntimeError):
    """Raised when a frozen publication input differs from its contract."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_repository_root() -> Path:
    candidates = [Path.cwd(), Path(__file__).resolve().parent]
    for candidate in candidates:
        for root in (candidate, *candidate.parents):
            if (root / ".git").exists() and (root / "paper/generated/tables/condition_metrics.csv").is_file():
                return root
    raise PlotInputError("repository root not found; run inside the project checkout")


def assert_sha(path: Path, expected: str) -> None:
    observed = sha256(path)
    if observed != expected:
        raise PlotInputError(f"frozen checksum mismatch: {path.name}: {observed}")


def assert_decimal(value: float, expected: str, label: str) -> None:
    if f"{float(value):.{len(expected.split('.')[-1])}f}" != expected:
        raise PlotInputError(f"numeric verification failed for {label}: {value!r} != {expected}")


def load_and_validate(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Path]]:
    paths = {
        "condition": root / "paper/generated/tables/condition_metrics.csv",
        "contrast": root / "paper/generated/tables/paired_contrasts.csv",
        "aggregate": root / "paper/generated/phase8e_aggregate_results.json",
        "statistics": root / "paper/generated/phase8e_statistics_results.json",
    }
    for key, expected in (
        ("condition", CONDITION_SHA256),
        ("contrast", CONTRAST_SHA256),
        ("aggregate", AGGREGATE_SHA256),
        ("statistics", STATISTICS_SHA256),
    ):
        assert_sha(paths[key], expected)

    source_is_ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", SOURCE_COMMIT, "HEAD"],
        cwd=root, text=True, capture_output=True, check=False,
    )
    if source_is_ancestor.returncode != 0:
        raise PlotInputError("frozen source commit is not an ancestor of HEAD")

    condition = pd.read_csv(paths["condition"])
    contrast = pd.read_csv(paths["contrast"])
    expected_condition_columns = (
        "metric_name", "unit", "condition_id", "subject_count", "mean", "sd",
        "median", "q1", "q3", "minimum", "maximum",
    )
    expected_contrast_columns = (
        "metric_name", "unit", "contrast_id", "subject_count", "mean_difference",
        "median_difference", "ci_95_lower", "ci_95_upper", "raw_p", "holm_adjusted_p", "cohens_dz",
    )
    if tuple(condition.columns) != expected_condition_columns:
        raise PlotInputError("condition CSV schema mismatch")
    if tuple(contrast.columns) != expected_contrast_columns:
        raise PlotInputError("contrast CSV schema mismatch")
    if len(condition) != 44 or len(contrast) != 55:
        raise PlotInputError("source row accounting mismatch")
    if condition.isna().any().any() or contrast.isna().any().any():
        raise PlotInputError("source table contains missing values")
    if set(condition["subject_count"]) != {SUBJECT_COUNT} or set(contrast["subject_count"]) != {SUBJECT_COUNT}:
        raise PlotInputError("subject count differs from 483")
    if tuple(condition["metric_name"].drop_duplicates()) != METRICS:
        raise PlotInputError("condition metric order mismatch")
    if tuple(contrast["metric_name"].drop_duplicates()) != METRICS:
        raise PlotInputError("contrast metric order mismatch")
    for metric in METRICS:
        if tuple(condition.loc[condition.metric_name == metric, "condition_id"]) != CONDITIONS:
            raise PlotInputError(f"condition order mismatch for {metric}")
        if tuple(contrast.loc[contrast.metric_name == metric, "contrast_id"]) != CONTRASTS:
            raise PlotInputError(f"contrast order mismatch for {metric}")
    if not np.isfinite(condition.select_dtypes(include=[np.number]).to_numpy()).all():
        raise PlotInputError("non-finite condition value")
    if not np.isfinite(contrast.select_dtypes(include=[np.number]).to_numpy()).all():
        raise PlotInputError("non-finite contrast value")
    if (contrast["ci_95_lower"] > contrast["ci_95_upper"]).any():
        raise PlotInputError("forest interval lower bound exceeds upper bound")

    for condition_id, expected_mae, expected_action in (
        ("P0S0", "12.781", "0.0044"),
        ("P1S0", "5.421", "0.2409"),
        ("P0S1", "7.673", "0.0087"),
        ("P1S1", "6.954", "0.0128"),
    ):
        mae = condition.loc[
            (condition.metric_name == "mean_absolute_bis_deviation")
            & (condition.condition_id == condition_id), "mean"
        ].iloc[0]
        action = condition.loc[
            (condition.metric_name == "action_change_magnitude_mg_per_min")
            & (condition.condition_id == condition_id), "mean"
        ].iloc[0]
        assert_decimal(mae, expected_mae, f"{condition_id} MAE")
        assert_decimal(action, expected_action, f"{condition_id} action change")

    for contrast_id, expected in (
        ("P1S0_minus_P0S0", "-7.360"),
        ("P0S1_minus_P0S0", "-5.108"),
        ("P1S1_minus_P1S0", "1.533"),
        ("interaction", "6.641"),
    ):
        row = contrast.loc[
            (contrast.metric_name == "mean_absolute_bis_deviation")
            & (contrast.contrast_id == contrast_id)
        ].iloc[0]
        assert_decimal(row.mean_difference, expected, f"{contrast_id} MAE contrast")
        if contrast_id == "interaction":
            assert_decimal(row.ci_95_lower, "6.289", "interaction CI lower")
            assert_decimal(row.ci_95_upper, "6.979", "interaction CI upper")
    return condition, contrast, paths


def transformed(values: np.ndarray, metric: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    return result / 60.0 if metric in TIME_TRANSFORMS else result


def format_value(value: float, metric: str) -> str:
    if metric == "mean_absolute_bis_deviation":
        return f"{value:.3f}"
    if metric == "action_change_magnitude_mg_per_min":
        return f"{value:.4f}"
    if metric in TIME_TRANSFORMS or metric == "cumulative_propofol_amount_mg":
        return f"{value:.1f}"
    return f"{value:.3g}"


def configure_style() -> None:
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["DejaVu Serif"],
        "font.size": 8.5,
        "axes.titlesize": 9,
        "axes.labelsize": 8.5,
        "xtick.labelsize": 8,
        "ytick.labelsize": 7.5,
        "legend.fontsize": 8,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#222222",
        "axes.linewidth": 0.7,
        "axes.grid": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def interaction_panel(ax: plt.Axes, data: pd.DataFrame, metric: str, *, labels: bool) -> None:
    subset = data.loc[data.metric_name == metric].set_index("condition_id")
    for preprocessing in PREPROCESSING:
        condition_ids = [f"{preprocessing}{state}" for state in STATES]
        values = transformed(subset.loc[condition_ids, "mean"].to_numpy(), metric)
        style = LINE_STYLES[preprocessing]
        ax.plot(
            STATES, values, color=style["color"], linestyle=style["linestyle"],
            marker=style["marker"], markersize=5.2, linewidth=1.25,
            markerfacecolor="white", markeredgewidth=1.0, label=style["label"], zorder=3,
        )
        if labels:
            y_offset = 7 if preprocessing == "P0" else -11
            for x_value, y_value in zip(STATES, values, strict=True):
                ax.annotate(
                    format_value(y_value, metric), (x_value, y_value), xytext=(0, y_offset),
                    textcoords="offset points", ha="center", va="bottom" if y_offset > 0 else "top",
                    fontsize=7, color=style["color"], clip_on=False,
                )
    ax.set_title(METRIC_LABELS[metric], pad=7)
    ax.set_xlabel("State representation")
    ax.margins(x=0.18, y=0.20 if labels else 0.12)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(direction="out", length=3, width=0.7)


def forest_panel(ax: plt.Axes, data: pd.DataFrame, metric: str) -> None:
    subset = data.loc[data.metric_name == metric].set_index("contrast_id").loc[list(CONTRASTS)]
    means = transformed(subset["mean_difference"].to_numpy(), metric)
    lowers = transformed(subset["ci_95_lower"].to_numpy(), metric)
    uppers = transformed(subset["ci_95_upper"].to_numpy(), metric)
    if np.any(lowers > means) or np.any(means > uppers):
        raise PlotInputError(f"forest interval does not contain mean for {metric}")
    y = np.arange(len(CONTRASTS))
    ax.errorbar(
        means, y, xerr=np.vstack((means - lowers, uppers - means)), fmt="o",
        color="#222222", ecolor="#555555", elinewidth=1.0, capsize=2.3,
        markersize=4.2, markerfacecolor="white", markeredgewidth=1.0, zorder=3,
    )
    ax.axvline(0.0, color="#8a8a8a", linestyle=":", linewidth=0.9, zorder=1)
    ax.set_yticks(y, [CONTRAST_LABELS[item] for item in CONTRASTS])
    ax.invert_yaxis()
    ax.set_title(METRIC_LABELS[metric], pad=7)
    ax.set_xlabel("Mean paired difference")
    ax.margins(x=0.12, y=0.10)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", direction="out", length=3, width=0.7)


def save_pair(fig: plt.Figure, output_dir: Path, stem: str, dimensions: tuple[float, float]) -> None:
    width, height = dimensions
    fig.set_size_inches(width, height, forward=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf"):
        target = output_dir / f"{stem}.{suffix}"
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{stem}.", suffix=f".partial.{suffix}", dir=output_dir
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            if suffix == "png":
                fig.savefig(
                    temporary, format="png", dpi=PNG_DPI, facecolor="white",
                    metadata={"Software": "Python/Matplotlib Phase 8F renderer"},
                )
            else:
                fig.savefig(
                    temporary, format="pdf", facecolor="white",
                    metadata={
                        "Creator": "Python/Matplotlib Phase 8F renderer",
                        "Producer": "Matplotlib",
                        "CreationDate": None,
                        "ModDate": None,
                    },
                )
            if temporary.stat().st_size == 0:
                raise RuntimeError(f"empty figure output: {target.name}")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)


def interaction_figure(
    condition: pd.DataFrame,
    metrics: tuple[str, ...],
    *,
    title: str,
    subtitle: str,
    dimensions: tuple[float, float],
    labels: bool,
) -> plt.Figure:
    columns = 2
    rows = math.ceil(len(metrics) / columns)
    fig, axes = plt.subplots(rows, columns, figsize=dimensions, squeeze=False)
    for ax, metric in zip(axes.flat, metrics, strict=False):
        interaction_panel(ax, condition, metric, labels=labels)
    for ax in axes.flat[len(metrics):]:
        ax.remove()
    handles = [
        plt.Line2D([], [], color=LINE_STYLES[p]["color"], linestyle=LINE_STYLES[p]["linestyle"],
                   marker=LINE_STYLES[p]["marker"], markerfacecolor="white", linewidth=1.25,
                   label=LINE_STYLES[p]["label"])
        for p in PREPROCESSING
    ]
    fig.suptitle(title, fontsize=12, fontweight="bold", y=0.985)
    fig.text(0.5, 0.945, subtitle, ha="center", va="top", fontsize=8.5)
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.915), ncol=2, frameon=False)
    fig.subplots_adjust(left=0.10, right=0.98, bottom=0.10, top=0.82, hspace=0.62, wspace=0.32)
    return fig


def forest_figure(
    contrast: pd.DataFrame,
    metrics: tuple[str, ...],
    *,
    title: str,
    subtitle: str,
    dimensions: tuple[float, float],
) -> plt.Figure:
    columns = 2
    rows = math.ceil(len(metrics) / columns)
    fig, axes = plt.subplots(rows, columns, figsize=dimensions, squeeze=False)
    for ax, metric in zip(axes.flat, metrics, strict=False):
        forest_panel(ax, contrast, metric)
    for ax in axes.flat[len(metrics):]:
        ax.remove()
    fig.suptitle(title, fontsize=12, fontweight="bold", y=0.985)
    fig.text(0.5, 0.95, subtitle, ha="center", va="top", fontsize=8.5)
    fig.subplots_adjust(left=0.25, right=0.98, bottom=0.09, top=0.86, hspace=0.52, wspace=0.62)
    return fig


def mae_figure(condition: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=EXPECTED_OUTPUTS["figure_mae_interaction"])
    interaction_panel(ax, condition, "mean_absolute_bis_deviation", labels=True)
    ax.set_ylim(bottom=3.0)
    ax.set_ylabel("Mean absolute BIS\ndeviation", fontsize=7.2, labelpad=7)
    fig.suptitle("MAE interaction", fontsize=11, fontweight="bold", y=0.985)
    fig.text(0.5, 0.91, "Lower values indicate more accurate latent-BIS control", ha="center", fontsize=7.5)
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.78), ncol=2, frameon=False, fontsize=7)
    fig.subplots_adjust(left=0.23, right=0.97, bottom=0.18, top=0.58)
    return fig


def render_figures(condition: pd.DataFrame, contrast: pd.DataFrame, output_dir: Path) -> None:
    configure_style()
    figures: list[tuple[str, plt.Figure]] = []
    figures.append((
        "figure_main_interaction",
        interaction_figure(
            condition, MAIN_METRICS,
            title="Interaction between BIS preprocessing and state representation",
            subtitle="Subject-level means across 483 sealed-test subjects",
            dimensions=EXPECTED_OUTPUTS["figure_main_interaction"], labels=True,
        ),
    ))
    figures.append((
        "figure_main_contrast_forest",
        forest_figure(
            contrast, MAIN_METRICS,
            title="Prespecified paired contrasts",
            subtitle="Mean paired differences with subject-level bootstrap 95% confidence intervals",
            dimensions=EXPECTED_OUTPUTS["figure_main_contrast_forest"],
        ),
    ))
    figures.append(("figure_mae_interaction", mae_figure(condition)))
    group_titles = {
        "accuracy": "BIS accuracy interactions",
        "range": "BIS range and safety interactions",
        "control": "Drug use, action behavior, and reward interactions",
    }
    forest_titles = {
        "accuracy": "Prespecified contrasts: BIS accuracy",
        "range": "Prespecified contrasts: BIS range and safety",
        "control": "Prespecified contrasts: drug use, action behavior, and reward",
    }
    for group, metrics in GROUPS.items():
        stem = f"figure_supp_{group}_interactions"
        figures.append((
            stem,
            interaction_figure(
                condition, metrics, title=group_titles[group],
                subtitle="Subject-level means across 483 sealed-test subjects",
                dimensions=EXPECTED_OUTPUTS[stem], labels=False,
            ),
        ))
    for group, metrics in GROUPS.items():
        stem = f"figure_supp_{group}_forest"
        figures.append((
            stem,
            forest_figure(
                contrast, metrics, title=forest_titles[group],
                subtitle="Mean paired differences with subject-level bootstrap 95% confidence intervals",
                dimensions=EXPECTED_OUTPUTS[stem],
            ),
        ))
    for stem, fig in figures:
        try:
            save_pair(fig, output_dir, stem, EXPECTED_OUTPUTS[stem])
        finally:
            plt.close(fig)
    if plt.get_fignums():
        raise RuntimeError("matplotlib figure leak detected")


def captions_text() -> str:
    return """# Phase 8F confirmatory figure captions

All panels show latent-BIS simulator outcomes for the 483 sealed-test subjects. Interaction figures show condition means in the fixed P0S0, P1S0, P0S1, P1S1 design order. Forest figures show paired subject-level mean differences and 2,000-replicate subject-level bootstrap 95% confidence intervals in the five prespecified contrast directions. Time and BIS-point-time values labeled in minutes use a visualization-only division by 60; source CSV values remain in seconds. The meaning of a positive or negative contrast depends on the metric direction. No figure ranks conditions or selects a best condition.

## Main interaction figure

`figure_main_interaction` shows the 2 × 2 preprocessing-by-state interactions for mean absolute BIS deviation, time in BIS 40–60, cumulative propofol amount, and action-change magnitude. Point labels are the corresponding condition means.

## Main paired-contrast forest figure

`figure_main_contrast_forest` shows the five prespecified paired contrasts for the four main metrics. Points are mean paired differences, horizontal intervals are bootstrap 95% confidence intervals, and the dotted vertical line is zero.

## Standalone MAE interaction figure

`figure_mae_interaction` shows mean absolute BIS deviation for the four conditions, with condition means labeled to three decimal places.

## Supplementary accuracy interaction and forest figures

`figure_supp_accuracy_interactions` and `figure_supp_accuracy_forest` show mean absolute deviation, root mean squared deviation, integrated absolute BIS error, and maximum absolute deviation as condition means and prespecified paired contrasts, respectively.

## Supplementary range and safety interaction and forest figures

`figure_supp_range_interactions` and `figure_supp_range_forest` show time in BIS 40–60, time below BIS 40, and time above BIS 60. Seconds are divided by 60 only for visualization.

## Supplementary control interaction and forest figures

`figure_supp_control_interactions` and `figure_supp_control_forest` show cumulative propofol amount, mean propofol infusion rate, action-change magnitude, and cumulative episode reward as condition means and prespecified paired contrasts, respectively.
"""


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".partial", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def report_text(root: Path, paths: dict[str, Path], output_dir: Path) -> str:
    lines = [
        "# Phase 8F confirmatory plot generation report",
        "",
        f"- Source commit SHA: `{SOURCE_COMMIT}`",
        f"- Python: `{sys.version.split()[0]}`",
        f"- pandas: `{pd.__version__}`",
        f"- matplotlib: `{matplotlib.__version__}`",
        f"- numpy: `{np.__version__}`",
        "- Renderer: Python/Matplotlib, used because the local R 4.5.2 base initialization path crashed before plotting code",
        f"- Condition source: `paper/generated/tables/condition_metrics.csv` (`{sha256(paths['condition'])}`)",
        f"- Contrast source: `paper/generated/tables/paired_contrasts.csv` (`{sha256(paths['contrast'])}`)",
        f"- Frozen aggregate checksum: `{sha256(paths['aggregate'])}`",
        f"- Frozen statistics checksum: `{sha256(paths['statistics'])}`",
        "- Source rows: 44 condition-metric rows and 55 paired-contrast rows",
        "- Analysis unit: 483 subjects",
        "- Condition order: P0S0, P1S0, P0S1, P1S1",
        "- Plotting-only transformations: time-in-range, below-range, above-range, and integrated BIS-point-time values divided by 60 when labeled in minutes",
        "- Private, case-level, subject-level, or event-level input rows used: 0",
        "- Evaluation/training/simulator reruns: 0",
        "- Bootstrap/permutation reruns: 0",
        "- Scientific value modifications: 0",
        "- Condition ranking or best-condition selection: 0",
        "",
        "## Generated figures",
        "",
        "All PNG outputs were requested at 600 dpi. PDF outputs use the Matplotlib vector PDF backend.",
        "",
        "| Figure | Dimensions (in) | PNG SHA-256 | PDF SHA-256 |",
        "|---|---:|---|---|",
    ]
    for stem, (width, height) in EXPECTED_OUTPUTS.items():
        png = output_dir / f"{stem}.png"
        pdf = output_dir / f"{stem}.pdf"
        lines.append(f"| `{stem}` | {width:.1f} × {height:.1f} | `{sha256(png)}` | `{sha256(pdf)}` |")
    lines.extend((
        "",
        "## Numeric verification",
        "",
        "The source tables passed exact display-value checks for the four MAE condition means, four action-change condition means, the three named MAE component contrasts, and the MAE interaction estimate and confidence interval. All interval lower bounds were less than or equal to their means and all means were less than or equal to their upper bounds.",
        "",
    ))
    return "\n".join(lines)


def main() -> int:
    root = find_repository_root()
    condition, contrast, paths = load_and_validate(root)
    output_dir = root / "paper/generated/figures"
    render_figures(condition, contrast, output_dir)
    atomic_write_text(output_dir / "figure_captions.md", captions_text())
    report = report_text(root, paths, output_dir)
    atomic_write_text(root / "docs/phase8f_plot_generation_report.md", report)
    for key, expected in (
        ("condition", CONDITION_SHA256), ("contrast", CONTRAST_SHA256),
        ("aggregate", AGGREGATE_SHA256), ("statistics", STATISTICS_SHA256),
    ):
        assert_sha(paths[key], expected)
    print(
        f"Phase 8F figures generated: {len(EXPECTED_OUTPUTS)} PNG/PDF pairs; "
        f"condition_rows={len(condition)} contrast_rows={len(contrast)} subjects={SUBJECT_COUNT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
