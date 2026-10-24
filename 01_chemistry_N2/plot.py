"""Figures for Demo A -- bond dissociation (default N2).

  dissociation.png : energy curves (HF, CCSD, CCSD(T), FCI) vs bond length.
  error.png        : |CCSD(T) - FCI| error vs bond length (log scale).

Reads results/[<molecule>/]summary.json (run.py must be run first) and writes
figures/[<molecule>/]. N2 uses the top-level folders.

Run:   python plot.py                  (N2)
       python plot.py --molecule h2o
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from common.plotting import plt, save, BLUE, ORANGE, GREEN, RED   # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--molecule", "-m", default="n2")
args = ap.parse_args()
sub = "" if args.molecule == "n2" else args.molecule
res_dir = os.path.join(HERE, "results", sub)
fig_dir = os.path.join(HERE, "figures", sub)
os.makedirs(fig_dir, exist_ok=True)

data = json.load(open(os.path.join(res_dir, "summary.json")))
rows = data["rows"]
label = data["summary"].get("molecule", "N2")
R = np.array([r["R"] for r in rows])
HF = np.array([r["HF"] for r in rows])
CCSD = np.array([r["CCSD"] for r in rows])
CCSDT = np.array([r["CCSD_T"] for r in rows])
FCI = np.array([r["FCI"] for r in rows])
err = np.abs(np.array([r["err_ccsd_t_meh"] for r in rows]))

# ---- Figure 1: energy curves ----
fig, ax = plt.subplots()
ax.plot(R, HF, "o-", color="gray", label="HF (mean field)", alpha=0.7)
ax.plot(R, CCSD, "s-", color=ORANGE, label="CCSD")
ax.plot(R, CCSDT, "^-", color=RED, label="CCSD(T)  — classical 'gold standard'", lw=2.2)
ax.plot(R, FCI, "D-", color=BLUE, label="FCI (exact = ideal quantum QPE)", lw=2.2)
ax.set_xlabel("Bond length (Å)")
ax.set_ylabel("Energy (Hartree)")
ax.set_title(f"{label} dissociation: does the classical gold standard hold?")
ax.legend(loc="lower right", fontsize=10)
if args.molecule == "n2":   # hand-placed annotation for the reference N2 curve
    ax.annotate("CCSD(T) dives below the exact\ncurve (unphysical) & oscillates\n— strong correlation",
                xy=(2.0, CCSDT[np.argmin(np.abs(R - 2.0))]), xytext=(1.25, -106.95),
                fontsize=9, color=RED,
                arrowprops=dict(arrowstyle="->", color=RED))
save(fig, os.path.join(fig_dir, "dissociation.png"))

# ---- Figure 2: error vs bond length ----
fig, ax = plt.subplots()
ax.semilogy(R, np.clip(err, 1e-2, None), "^-", color=RED, lw=2, label="|CCSD(T) − FCI| error")
ax.axhline(1.6, color=GREEN, ls="--", label="chemical accuracy (1.6 mEh ≈ 1 kcal/mol)")
ax.set_xlabel("Bond length (Å)")
ax.set_ylabel("Energy error vs exact (mEh, log scale)")
ax.set_title(f"{label}: CCSD(T) error vs exact FCI")
ax.legend(loc="upper left", fontsize=10)
w = data["summary"]["worst"]
ax.annotate(f"worst: {w['err_meh']:+.0f} mEh\n(≈ {w['err_kcal']:+.0f} kcal/mol)",
            xy=(w["R"], max(1.6, abs(w["err_meh"]))),
            **(dict(xytext=(1.3, 200)) if args.molecule == "n2" else
               dict(xytext=(0.35, 0.8), textcoords="axes fraction")),
            fontsize=10, color=RED, arrowprops=dict(arrowstyle="->", color=RED))
save(fig, os.path.join(fig_dir, "error.png"))
