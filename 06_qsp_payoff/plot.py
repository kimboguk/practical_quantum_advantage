"""Figures for Demo F (QSP payoff encoding).

  qsp_payoff.png : left  - target payoff vs QSP amplitude for a few degrees d
                   right - max error vs number of signal calls d (log-log)
Reads results/summary.json (run.py must be run first).
"""
from __future__ import annotations
import json
import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
from common.plotting import plt, save, BLUE, ORANGE, GREEN, RED   # noqa: E402
from run import qsp_amplitude, payoff, STRIKE                    # noqa: E402

data = json.load(open(os.path.join(HERE, "results", "summary.json")))
rows = {r["degree"]: r for r in data["rows"]}
y = np.linspace(0, 1, 801)

fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5))
a1.plot(y, payoff(y), color="black", lw=2.5, label="target payoff (scaled)")
for d, col in ((4, ORANGE), (12, GREEN), (48, BLUE)):
    if d in rows:
        amp = qsp_amplitude(np.array(rows[d]["phases"]), y).real
        a1.plot(y, amp, color=col, lw=1.6, label=f"QSP, d = {d} signal calls")
a1.axvline(STRIKE, color="gray", ls=":", lw=1)
a1.set_xlabel("normalized underlying price  y")
a1.set_ylabel("amplitude  Re⟨0|U(y)|0⟩")
a1.set_title("Payoff encoded by single-qubit rotations")
a1.legend(fontsize=9, loc="upper left")

ds = np.array(sorted(rows))
err = np.array([rows[d]["err_total"] for d in ds])
fit = np.array([rows[d]["err_qsp_fit"] for d in ds])
a2.loglog(ds, err, "o-", color=BLUE, lw=2, label="max |QSP − payoff|")
a2.loglog(ds, fit, "s--", color=RED, lw=1.2,
          label="max |QSP − Chebyshev polynomial|  (phase fit)")
a2.loglog(ds, err[0] * ds[0] / ds, ":", color="gray", label="∝ 1/d guide")
a2.set_xticks([4, 8, 16, 32, 48]); a2.set_xticklabels(["4", "8", "16", "32", "48"])
a2.minorticks_off()
a2.set_xlabel("signal calls  d  (= polynomial degree)")
a2.set_ylabel("max error (log scale)")
a2.set_title("Accuracy is set by the polynomial, not by arithmetic")
a2.legend(fontsize=9, loc="center right")
save(fig, os.path.join(HERE, "figures", "qsp_payoff.png"))
