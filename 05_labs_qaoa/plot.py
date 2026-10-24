"""Figure for Demo E -- LABS time-to-solution scaling.

  tts_scaling.png : TTS vs N (log2 scale) for QAOA, QAOA+QMF, MTS, brute force,
                    with fitted exponential bases.

Reads results/summary.json (run.py must be run first).
"""
from __future__ import annotations
import json
import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from common.plotting import plt, save, BLUE, ORANGE, GREEN, RED, PURPLE   # noqa: E402

data = json.load(open(os.path.join(HERE, "results", "summary.json")))
rows, s = data["rows"], data["summary"]
N = np.array([r["N"] for r in rows])
lo, hi = s["fit_N"]
Nf = np.linspace(lo, hi, 50)

fig, ax = plt.subplots()
series = [
    ("tts_brute", "brute force", "gray", "x"),
    ("tts_mts_median", "MTS (classical, evaluations)", RED, "s"),
    ("tts_qaoa", f"QAOA p={s['p']} (shots)", BLUE, "o"),
    ("tts_qaoa_qmf", "QAOA + QMF (idealized, needs fault tolerance)", PURPLE, "^"),
]
for key, label, color, marker in series:
    y = np.array([r[key] for r in rows])
    if key == "tts_brute":
        ax.semilogy(N, y, "--", color=color, label=f"{label}: 2.00^N", base=2)
        continue
    f = s["fits"][key]
    ax.semilogy(N, y, marker, color=color, alpha=0.8, base=2)
    ax.semilogy(Nf, 2 ** (f["slope_log2"] * Nf + f["intercept_log2"]), "-",
                color=color, base=2, label=f"{label}: {f['base']:.2f}^N")
ax.axvspan(lo, hi, color=GREEN, alpha=0.06)
ax.set_xlabel("sequence length N")
ax.set_ylabel("time to solution (log scale)")
ax.set_title("LABS: how fast does time-to-solution grow?")
ax.legend(loc="upper left", fontsize=9)
ax.text(0.98, 0.03, f"shaded: fit range N={lo}..{hi}\nliterature: QAOA p=12 1.46, "
        f"QMF 1.21, MTS 1.34", transform=ax.transAxes, ha="right", fontsize=9,
        color="dimgray")
os.makedirs(os.path.join(HERE, "figures"), exist_ok=True)
save(fig, os.path.join(HERE, "figures", "tts_scaling.png"))
