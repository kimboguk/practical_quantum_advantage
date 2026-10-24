#!/usr/bin/env python
"""Plot backend scaling: wall-clock vs qubit count, per backend."""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.plotting import BLUE, ORANGE, GREEN, PURPLE, save  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
COLORS = {"aer-CPU": ORANGE, "aer-GPU": BLUE}
_EXTRA = [GREEN, PURPLE]


def load():
    series = defaultdict(lambda: ([], []))
    with open(HERE / "results" / "scaling.csv") as f:
        for r in csv.DictReader(f):
            xs, ys = series[r["backend"]]
            xs.append(int(r["n_qubits"]))
            ys.append(float(r["seconds"]))
    return series


def main():
    series = load()
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ei = 0
    for label, (xs, ys) in sorted(series.items()):
        c = COLORS.get(label)
        if c is None:
            c = _EXTRA[ei % len(_EXTRA)]
            ei += 1
        ax.plot(xs, ys, "o-", color=c, label=label, linewidth=2, markersize=6)
    ax.set_yscale("log")
    ax.set_xlabel("Number of qubits")
    ax.set_ylabel("Wall-clock per run (seconds, log scale)")
    ax.set_title("Statevector simulation cost vs qubit count\n"
                 "(wide shallow entangling circuit, 1024 shots)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(title="backend")
    save(fig, HERE / "figures" / "scaling.png")
    print(f"wrote {HERE/'figures'/'scaling.png'}")


if __name__ == "__main__":
    main()
