"""Figures for Demo F (QSP payoff encoding).

  qsp_payoff.png : left   - target payoff vs QSP amplitude for a few degrees d
                   middle - max |QSP - payoff| vs signal calls d (linear)
                   right  - max |QSP - Chebyshev| vs d, in 1e-15 (linear)
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

fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(18, 5))
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

# middle: the error that matters -- vs the payoff, linear scale
a2.plot(ds, err, "o-", color=BLUE, lw=2, label="max |QSP − payoff|")
a2.plot(ds, err[0] * ds[0] / ds, ":", color="gray", label="∝ 1/d guide")
a2.set_ylim(0, None)
a2.set_xticks(ds[1::2])
a2.set_xlabel("signal calls  d  (= polynomial degree)")
a2.set_ylabel("max error vs payoff")
a2.set_title("Total error: polynomial approximation (~1/d)")
a2.legend(fontsize=9, loc="upper right")

# right: the quantum encoding itself -- vs the Chebyshev polynomial, in 1e-15
EPS = np.finfo(float).eps
a3.plot(ds, fit / 1e-15, "s-", color=RED, lw=1.6,
        label="max |QSP − Chebyshev polynomial|")
a3.axhline(EPS / 1e-15, color="gray", ls=":", label="float64 machine epsilon")
a3.set_ylim(0, None)
a3.set_xticks(ds[1::2])
a3.set_xlabel("signal calls  d  (= polynomial degree)")
a3.set_ylabel("max difference  (× 10⁻¹⁵)")
a3.set_title("Phase fit: exact up to rounding")
a3.legend(fontsize=9, loc="upper left")
save(fig, os.path.join(HERE, "figures", "qsp_payoff.png"))
