"""Shared plotting setup -- headless (Agg) figures for the demos.

A consistent, clean style so the three "money shot" figures read as one set.
Non-expert friendly: large fonts, clear titles, annotations over jargon.
"""
from __future__ import annotations
import matplotlib
matplotlib.use("Agg")          # headless: save to file, no display
import matplotlib.pyplot as plt

plt.rcParams.update({
    "figure.figsize": (8, 5),
    "figure.dpi": 130,
    "font.size": 12,
    "axes.titlesize": 14,
    "axes.titleweight": "bold",
    "axes.grid": True,
    "grid.alpha": 0.3,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "savefig.bbox": "tight",
})

# colorblind-safe
BLUE, ORANGE, GREEN, RED, PURPLE = (
    "#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7")


def save(fig, path):
    fig.savefig(path)
    plt.close(fig)
    print(f"[plot] saved {path}")
