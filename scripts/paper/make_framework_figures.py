"""Create vector concept and train/evaluation workflow figures."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "vitaldb-paper-mpl"))

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from plot_style import DOUBLE_COLUMN_WIDTH, apply_paper_style, save_figure

ROOT = Path(__file__).resolve().parents[2]
FIGURE_DIR = ROOT / "paper/figures"
BLUE = "#0072B2"
LIGHT_BLUE = "#56B4E9"
VERMILLION = "#D55E00"
ORANGE = "#E69F00"
NEUTRAL = "#F2F2F2"


def box(ax, xy, width, height, text, *, face=NEUTRAL, edge="#4D4D4D", fontsize=8.0):
    patch = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle="round,pad=0.012,rounding_size=0.015",
        facecolor=face,
        edgecolor=edge,
        linewidth=0.8,
    )
    ax.add_patch(patch)
    ax.text(xy[0] + width / 2, xy[1] + height / 2, text, ha="center", va="center", fontsize=fontsize)
    return patch


def arrow(ax, start, end, *, color="#4D4D4D", style="-|>", connectionstyle="arc3", dashed=False):
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle=style,
        mutation_scale=9,
        linewidth=0.9,
        color=color,
        linestyle="--" if dashed else "-",
        connectionstyle=connectionstyle,
    )
    ax.add_patch(patch)


def concept_figure() -> None:
    fig, ax = plt.subplots(figsize=(DOUBLE_COLUMN_WIDTH, 3.0))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    box(
        ax,
        (0.015, 0.40),
        0.205,
        0.24,
        "VitalDB-derived\ninputs",
        face="#F7F7F7",
        fontsize=8.4,
    )
    ax.text(
        0.1175,
        0.33,
        "BIS, infusion histories,\nand demographics",
        ha="center",
        va="center",
        fontsize=7.8,
        color="#4D4D4D",
    )
    arrow(ax, (0.22, 0.52), (0.255, 0.52))

    matrix_x, matrix_y, cell_w, cell_h = 0.305, 0.27, 0.12, 0.18
    ax.text(
        matrix_x + cell_w,
        0.90,
        "Only preprocessing and\nstate representation vary",
        ha="center",
        va="center",
        fontsize=8.6,
        fontweight="bold",
    )
    for col, (label, color) in enumerate((("P0", BLUE), ("P1", VERMILLION))):
        ax.text(
            matrix_x + (col + 0.5) * cell_w,
            matrix_y + 2 * cell_h + 0.035,
            label,
            ha="center",
            va="bottom",
            color=color,
            fontsize=8.4,
            fontweight="bold",
        )
    for row, label in enumerate(("S1", "S0")):
        ax.text(
            matrix_x - 0.025,
            matrix_y + (row + 0.5) * cell_h,
            label,
            ha="right",
            va="center",
            fontsize=8.4,
            fontweight="bold",
        )
    matrix = (
        (("P0S1", LIGHT_BLUE, "///"), ("P1S1", ORANGE, "///")),
        (("P0S0", BLUE, ""), ("P1S0", VERMILLION, "")),
    )
    for row, entries in enumerate(matrix):
        for col, (label, color, hatch) in enumerate(entries):
            left = matrix_x + col * cell_w
            bottom = matrix_y + row * cell_h
            rect = FancyBboxPatch(
                (left, bottom),
                cell_w - 0.008,
                cell_h - 0.01,
                boxstyle="round,pad=0.004,rounding_size=0.008",
                facecolor=color,
                edgecolor="white",
                linewidth=1.0,
                hatch=hatch,
            )
            ax.add_patch(rect)
            ax.text(
                left + (cell_w - 0.008) / 2,
                bottom + (cell_h - 0.01) / 2,
                label,
                ha="center",
                va="center",
                color="white" if label != "P1S1" else "black",
                fontsize=9.0,
                fontweight="bold",
            )

    arrow(ax, (matrix_x + 2 * cell_w + 0.005, 0.52), (0.595, 0.52))
    box(ax, (0.60, 0.40), 0.18, 0.24, "Fixed PPO + PK–PD\nclosed loop", fontsize=7.9)
    arrow(ax, (0.78, 0.52), (0.805, 0.52))
    box(ax, (0.81, 0.40), 0.17, 0.24, "Fixed-case control\nevaluation", fontsize=7.9)
    ax.text(
        0.595,
        0.17,
        "Fixed across conditions: architecture, reward, training budget,\nseed, and test cases.",
        ha="left",
        va="center",
        fontsize=7.8,
        color="#595959",
    )
    save_figure(fig, FIGURE_DIR / "controlled_experiment_framework")
    plt.close(fig)


def workflow_figure() -> None:
    fig, ax = plt.subplots(figsize=(DOUBLE_COLUMN_WIDTH, 2.25))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    labels = (
        ("Observation\nhistory", NEUTRAL, "#4D4D4D"),
        ("Preprocessing", "#FFF2E8", VERMILLION),
        ("State\nrepresentation", "#EAF5FB", BLUE),
        ("PPO policy", NEUTRAL, "#4D4D4D"),
        ("Propofol\naction", NEUTRAL, "#4D4D4D"),
        ("Patient\nsimulator", NEUTRAL, "#4D4D4D"),
        ("Next BIS/state\nand metrics", NEUTRAL, "#4D4D4D"),
    )
    widths = (0.13, 0.135, 0.15, 0.11, 0.115, 0.12, 0.16)
    gap = 0.01
    xs = [0.008]
    for width in widths[:-1]:
        xs.append(xs[-1] + width + gap)
    for x, width, (label, face, edge) in zip(xs, widths, labels):
        box(ax, (x, 0.42), width, 0.24, label, face=face, edge=edge, fontsize=8.0)
    for x, width, next_x in zip(xs[:-1], widths[:-1], xs[1:]):
        arrow(ax, (x + width, 0.54), (next_x, 0.54))
    arrow(
        ax,
        (xs[-1] + widths[-1] - 0.01, 0.67),
        (xs[3] + widths[3] / 2, 0.67),
        dashed=True,
        connectionstyle="arc3,rad=0.18",
        color="#6B6B6B",
    )
    ax.text(
        0.72,
        0.88,
        "PPO update: training only",
        ha="center",
        va="center",
        fontsize=8.0,
        color="#595959",
    )
    ax.text(
        0.5,
        0.18,
        "Evaluation uses a frozen policy and frozen preprocessing statistics.",
        ha="center",
        va="center",
        fontsize=8.2,
        color="#595959",
    )
    save_figure(fig, FIGURE_DIR / "training_evaluation_workflow")
    plt.close(fig)


def main() -> None:
    apply_paper_style()
    concept_figure()
    workflow_figure()
    print("Wrote 2 vector figures and matching 600-dpi PNG files.")


if __name__ == "__main__":
    main()
