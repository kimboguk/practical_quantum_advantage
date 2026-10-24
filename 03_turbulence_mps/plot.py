"""Figure for Demo C -- MPS compressibility by phase structure.

  compression.png : bond dimension chi (how hard to compress classically) for
                    each phase structure, at two truncation tolerances.

Reads results/summary.json (run.py must be run first).
"""
from __future__ import annotations
import json
import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from common.plotting import plt, save, BLUE, ORANGE   # noqa: E402

data = json.load(open(os.path.join(HERE, "results", "summary.json")))
rows = data["rows"]
labels = [r["phase"] for r in rows]
chi2 = [r["chi_tol_1e2"] for r in rows]
chi4 = [r["chi_tol_1e4"] for r in rows]

x = np.arange(len(labels))
w = 0.38
fig, ax = plt.subplots()
ax.bar(x - w / 2, chi2, w, color=BLUE, label="tolerance 1e−2")
ax.bar(x + w / 2, chi4, w, color=ORANGE, label="tolerance 1e−4")
ax.set_xticks(x)
ax.set_xticklabels(["zero\n(no circuit)", "linear\n(n gates)",
                    "quadratic\n(~n²/2 gates)", "random\n(not a circuit)"],
                   fontsize=10)
ax.set_ylabel("MPS bond dimension χ  (higher = harder to compress)")
ax.set_title("A short quadratic-phase circuit resists compression like random noise")
ax.legend()
ax.annotate("short quantum circuit,\nyet ~ as incompressible\nas fully random",
            xy=(2, chi4[2]), xytext=(0.6, chi4[2] * 0.72), fontsize=9, color=BLUE,
            arrowprops=dict(arrowstyle="->", color=BLUE))
save(fig, os.path.join(HERE, "figures", "compression.png"))
