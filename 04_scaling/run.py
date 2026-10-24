#!/usr/bin/env python
"""Demo D -- backend scaling: local CPU vs local GPU vs IonQ cloud.

Demos A-C are small by design. This one answers a different question:
*when does the local GPU (and a real quantum vendor's cloud) actually earn
its keep?*  We simulate a wide, shallow, entangling circuit at a growing
number of qubits and measure wall-clock time on each backend.

- A statevector simulator must track 2**n complex amplitudes, so cost grows
  exponentially with qubit count. The GPU parallelises that inner work; it
  loses to the CPU on tiny circuits (launch/transfer overhead) and wins once
  the statevector is large. That crossover is the point of this demo.
- The *same* circuit runs on the IonQ cloud (ideal simulator), showing it is
  not local-only. IonQ returns samples, so we use it only for small sizes
  (<= 25 qubits) and few of them -- cloud jobs queue and cost.

Pure sampling (counts) + timing, so every backend is comparable. Run:
    python run.py                         # local CPU + GPU sweep
    python run.py --backends cpu,gpu,ionq_sim   # + one cloud point (needs token)
    python run.py --max-qubits 30         # push the local sweep
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit, transpile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.backend import check_qubits, get_backend, IONQ_SIM_SAFE  # noqa: E402

HERE = Path(__file__).resolve().parent
SEED = 7
SHOTS = 1024
DEPTH = 6                     # entangling layers (shallow, hardware-friendly)
DEFAULT_SWEEP = [20, 22, 24, 26, 28]   # local sweep; ionq capped separately


def build_circuit(n_qubits: int, depth: int = DEPTH, seed: int = SEED):
    """Wide, shallow, entangling circuit: RY layers + CX ladder, then measure.

    Random (seeded) RY angles make the output non-trivial so the simulator
    cannot shortcut it; the CX ladder entangles across all qubits.
    """
    rng = np.random.default_rng(seed + n_qubits)
    qc = QuantumCircuit(n_qubits)
    for _ in range(depth):
        for q in range(n_qubits):
            qc.ry(float(rng.uniform(0, 2 * np.pi)), q)
        for q in range(n_qubits - 1):      # linear entangling ladder
            qc.cx(q, q + 1)
    qc.measure_all()
    return qc


def time_run(backend, circuit, shots: int = SHOTS) -> tuple[float, int]:
    """Transpile then run; return (wall_seconds, distinct_outcomes)."""
    tqc = transpile(circuit, backend)
    t0 = time.perf_counter()
    result = backend.run(tqc, shots=shots).result()
    dt = time.perf_counter() - t0
    counts = result.get_counts()
    return dt, len(counts)


def run_sweep(targets: list[str], sweep: list[int]) -> list[dict]:
    rows = []
    for target in targets:
        is_ionq = target.startswith("ionq")
        sizes = [n for n in sweep if n <= IONQ_SIM_SAFE] if is_ionq else sweep
        if is_ionq and len(sizes) > 2:
            sizes = sizes[:2]          # keep cloud jobs few
        try:
            backend, label = get_backend(target)
        except Exception as exc:
            print(f"[skip] {target}: {type(exc).__name__}: {exc}")
            continue
        for n in sizes:
            try:
                check_qubits(target, n)
            except ValueError as exc:
                print(f"[skip] {label} n={n}: {exc}")
                continue
            circ = build_circuit(n)
            try:
                secs, n_out = time_run(backend, circ)
            except Exception as exc:
                print(f"[skip] {label} n={n}: run failed {type(exc).__name__}: {exc}")
                continue
            print(f"  {label:20s} n={n:2d} depth={DEPTH}  {secs:8.3f}s  "
                  f"outcomes={n_out}")
            rows.append(dict(backend=label, target=target, n_qubits=n,
                             depth=DEPTH, shots=SHOTS, seconds=round(secs, 4),
                             distinct_outcomes=n_out))
    return rows


def analyze(rows: list[dict]) -> dict:
    cpu = {r["n_qubits"]: r["seconds"] for r in rows if r["target"] == "cpu"}
    gpu = {r["n_qubits"]: r["seconds"] for r in rows if r["target"] == "gpu"}
    speedups, crossover = {}, None
    for n in sorted(set(cpu) & set(gpu)):
        sp = cpu[n] / gpu[n] if gpu[n] > 0 else float("nan")
        speedups[n] = round(sp, 3)
        if crossover is None and sp >= 1.0:
            crossover = n
    return dict(
        gpu_speedup_vs_cpu=speedups,
        gpu_crossover_qubits=crossover,
        max_n=max((r["n_qubits"] for r in rows), default=None),
        honest_limits=(
            "Simulating a quantum computer is a classical computation, so this "
            "measures classical statevector-simulation speed, not a quantum "
            "advantage. GPU wins only once the statevector is large enough to "
            "amortise launch/transfer overhead. IonQ cloud timings include "
            "network/queue latency and are not comparable wall-clock to local "
            "runs -- they show portability, not speed."
        ),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backends", default="cpu,gpu",
                    help="comma list: cpu,gpu,ionq_sim,ionq_noise,ionq_qpu")
    ap.add_argument("--max-qubits", type=int, default=max(DEFAULT_SWEEP))
    args = ap.parse_args()

    targets = [t.strip() for t in args.backends.split(",") if t.strip()]
    sweep = [n for n in DEFAULT_SWEEP if n <= args.max_qubits]
    for n in range(max(DEFAULT_SWEEP) + 2, args.max_qubits + 1, 2):
        sweep.append(n)      # extend sweep if user asked for more

    print(f"[scaling] backends={targets} sweep={sweep} depth={DEPTH} shots={SHOTS}")
    if any(t.startswith("ionq") for t in targets) and not os.environ.get("IONQ_API_KEY"):
        print("[note] IONQ_API_KEY not set -> ionq targets will be skipped.")

    rows = run_sweep(targets, sweep)
    summary = analyze(rows)

    res = HERE / "results"
    res.mkdir(exist_ok=True)
    import csv
    with open(res / "scaling.csv", "w", newline="") as f:
        if rows:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    with open(res / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print("\n[summary]")
    print(json.dumps(summary, indent=2))
    print(f"\nwrote {res/'scaling.csv'} and {res/'summary.json'}")


if __name__ == "__main__":
    main()
