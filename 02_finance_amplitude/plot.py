"""Figure for Demo B -- quantum oracle calls vs classical MC samples.

  scaling.png : log-log of required work vs target error eps, showing the
                classical 1/eps^2 curve crossing the quantum ~1/eps curve.

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
rows = sorted(data["rows"], key=lambda r: -r["eps"])
eps = np.array([r["eps"] for r in rows])
oracle = np.array([r["quantum_oracle_calls"] for r in rows])
mc = np.array([r["classical_mc_samples"] for r in rows])

fig, ax = plt.subplots()
ax.loglog(1 / eps, mc, "s--", color=ORANGE, lw=2,
          label="Classical Monte Carlo  (∝ 1/ε²)")
ax.loglog(1 / eps, oracle, "o-", color=BLUE, lw=2,
          label="Quantum amplitude estimation  (∝ 1/ε)")
ax.set_xlabel("Precision  1/ε   (higher = more precise)")
ax.set_ylabel("Work required  (samples / oracle calls, log scale)")
ax.set_title("Quadratic speedup — but one quantum oracle call ≫ one MC sample")
ax.legend(loc="upper left", fontsize=10)
cross = data["summary"]["crossover_eps"]
if cross:
    ax.axvline(1 / cross, color="gray", ls=":",
               label=f"crossover ε≈{cross}")
    ax.annotate("below here, quantum needs\nfewer queries than classical",
                xy=(1 / cross, oracle[np.argmin(np.abs(eps - cross))]),
                xytext=(1 / cross * 0.12, oracle.max() * 0.6),
                fontsize=9, color="dimgray",
                arrowprops=dict(arrowstyle="->", color="gray"))
save(fig, os.path.join(HERE, "figures", "scaling.png"))
