"""Shared, publication-oriented Matplotlib styling for the paper figures."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl

SINGLE_COLUMN_WIDTH = 3.50
DOUBLE_COLUMN_WIDTH = 7.16

CONDITION_STYLE = {
    "P0S0": {"color": "#0072B2", "marker": "o", "linestyle": "-"},
    "P0S1": {"color": "#56B4E9", "marker": "^", "linestyle": "--"},
    "P1S0": {"color": "#D55E00", "marker": "o", "linestyle": "-"},
    "P1S1": {"color": "#E69F00", "marker": "^", "linestyle": "--"},
}


def apply_paper_style() -> None:
    """Set compact IEEE-compatible defaults without relying on seaborn."""
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.0,
            "axes.labelsize": 8.0,
            "axes.titlesize": 8.0,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "legend.fontsize": 7.2,
            "axes.linewidth": 0.7,
            "lines.linewidth": 1.25,
            "lines.markersize": 5.0,
            "xtick.major.width": 0.7,
            "ytick.major.width": 0.7,
            "xtick.major.size": 3.0,
            "ytick.major.size": 3.0,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "axes.grid.which": "major",
            "grid.color": "#D9D9D9",
            "grid.linewidth": 0.45,
            "grid.alpha": 0.55,
            "legend.frameon": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.03,
        }
    )


def save_figure(fig, stem: Path) -> tuple[Path, Path]:
    """Save vector PDF and 600-dpi PNG versions of a figure."""
    stem.parent.mkdir(parents=True, exist_ok=True)
    pdf_path = stem.with_suffix(".pdf")
    png_path = stem.with_suffix(".png")
    fig.savefig(pdf_path, format="pdf", bbox_inches="tight")
    fig.savefig(png_path, format="png", dpi=600, bbox_inches="tight")
    return pdf_path, png_path

