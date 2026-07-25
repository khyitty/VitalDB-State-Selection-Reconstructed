"""Render the exact feed-forward PPO actor--critic architecture."""

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
NEUTRAL_FACE = "#F2F2F2"
NEUTRAL_EDGE = "#555555"
ACTOR_FACE = "#E5F2EC"
ACTOR_EDGE = "#2E7D5B"
CRITIC_FACE = "#EEEAF5"
CRITIC_EDGE = "#6C5B7B"


def node(
    ax,
    x,
    y,
    w,
    h,
    text,
    *,
    face=NEUTRAL_FACE,
    edge=NEUTRAL_EDGE,
    fontsize=8.2,
    linewidth=0.9,
):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.008,rounding_size=0.012",
        facecolor=face,
        edgecolor=edge,
        linewidth=linewidth,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize)
    return patch


def arrow(ax, start, end, *, color=NEUTRAL_EDGE):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=9,
            linewidth=0.9,
            color=color,
            connectionstyle="arc3",
        )
    )


def make_figure() -> None:
    fig, ax = plt.subplots(figsize=(DOUBLE_COLUMN_WIDTH, 2.75))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # The controller receives a state vector that has already been constructed.
    node(
        ax,
        0.015,
        0.41,
        0.145,
        0.20,
        "S0 or S1\n34-D / 42-D",
        face="#EAF5FB",
        edge=BLUE,
    )
    node(
        ax,
        0.195,
        0.41,
        0.12,
        0.20,
        "Flatten\n(no weights)",
    )
    arrow(ax, (0.160, 0.51), (0.195, 0.51))

    # SB3 MlpExtractor: separate one-hidden-layer policy and value branches.
    node(
        ax,
        0.365,
        0.67,
        0.12,
        0.17,
        "Linear\n$d \\rightarrow 128$",
        face=ACTOR_FACE,
        edge=ACTOR_EDGE,
    )
    node(
        ax,
        0.515,
        0.67,
        0.09,
        0.17,
        "Tanh",
        face=ACTOR_FACE,
        edge=ACTOR_EDGE,
    )
    node(
        ax,
        0.635,
        0.67,
        0.12,
        0.17,
        "Action net\n$128 \\rightarrow 1$",
        face=ACTOR_FACE,
        edge=ACTOR_EDGE,
    )
    node(
        ax,
        0.365,
        0.18,
        0.12,
        0.17,
        "Linear\n$d \\rightarrow 128$",
        face=CRITIC_FACE,
        edge=CRITIC_EDGE,
    )
    node(
        ax,
        0.515,
        0.18,
        0.09,
        0.17,
        "Tanh",
        face=CRITIC_FACE,
        edge=CRITIC_EDGE,
    )
    node(
        ax,
        0.635,
        0.18,
        0.12,
        0.17,
        "Value net\n$128 \\rightarrow 1$",
        face=CRITIC_FACE,
        edge=CRITIC_EDGE,
    )

    arrow(ax, (0.315, 0.51), (0.365, 0.755), color=ACTOR_EDGE)
    arrow(ax, (0.315, 0.51), (0.365, 0.265), color=CRITIC_EDGE)
    arrow(ax, (0.485, 0.755), (0.515, 0.755), color=ACTOR_EDGE)
    arrow(ax, (0.604, 0.755), (0.635, 0.755), color=ACTOR_EDGE)
    arrow(ax, (0.485, 0.265), (0.515, 0.265), color=CRITIC_EDGE)
    arrow(ax, (0.604, 0.265), (0.635, 0.265), color=CRITIC_EDGE)

    node(
        ax,
        0.795,
        0.63,
        0.19,
        0.25,
        "Gaussian policy\n$\\mu_\\theta(s),\\ \\log\\sigma$",
        face=ACTOR_FACE,
        edge=ACTOR_EDGE,
        fontsize=8.0,
    )
    node(
        ax,
        0.795,
        0.18,
        0.19,
        0.17,
        "State value\n$V_\\phi(s)$",
        face=CRITIC_FACE,
        edge=CRITIC_EDGE,
    )
    arrow(ax, (0.755, 0.755), (0.795, 0.755), color=ACTOR_EDGE)
    arrow(ax, (0.755, 0.265), (0.795, 0.265), color=CRITIC_EDGE)

    ax.text(
        0.89,
        0.55,
        "1-D propofol action\nBox [0, 27.7] mg/10 s",
        ha="center",
        va="center",
        fontsize=7.8,
        color=ACTOR_EDGE,
    )
    ax.text(
        0.0875,
        0.65,
        "Constructed state vector",
        ha="center",
        va="bottom",
        fontsize=8.0,
        color=BLUE,
    )
    ax.text(0.425, 0.90, "Actor", ha="center", va="center", fontsize=8.5, color=ACTOR_EDGE)
    ax.text(0.425, 0.10, "Critic", ha="center", va="center", fontsize=8.5, color=CRITIC_EDGE)

    save_figure(fig, FIGURE_DIR / "ppo_actor_critic_architecture")
    plt.close(fig)


def main() -> None:
    apply_paper_style()
    make_figure()
    print("Wrote exact MLP PPO architecture as vector PDF and 600-dpi PNG.")


if __name__ == "__main__":
    main()
