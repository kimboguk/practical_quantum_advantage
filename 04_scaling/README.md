# Demo D — Backend scaling: local CPU vs local GPU vs IonQ cloud

Demos A–C are deliberately small. This one answers a different, practical
question: **when does a GPU (or a real quantum vendor's cloud) actually earn
its keep for quantum-circuit simulation — and when does it not?**

## What it does

It builds one **wide, shallow, entangling circuit** (random-angle `RY` layers
plus a `CX` ladder), then runs it at a growing number of qubits on each
backend and measures wall-clock time. A statevector simulator must track
`2ⁿ` complex amplitudes, so the work grows exponentially with qubit count —
exactly the regime where parallel hardware can help.

Pure sampling (counts) + timing, so every backend is directly comparable.

## Backends

| Target | Where it runs | Note |
|---|---|---|
| `cpu` | local Aer, CPU | baseline |
| `gpu` | local Aer, GPU | auto CPU-fallback if no CUDA Aer |
| `ionq_sim` | **IonQ cloud**, ideal simulator | needs `IONQ_API_KEY`; ≤ 25 qubits |
| `ionq_noise` | IonQ cloud, noise model (`aria-1`) | approximates real hardware |
| `ionq_qpu` | IonQ **real hardware** | opt-in, consumes credits |

```bash
python run.py                                  # local cpu + gpu sweep
python run.py --backends cpu,gpu --max-qubits 30
python run.py --backends ionq_sim              # one cloud point (token required)
python plot.py
```

## Result

![Backend scaling](figures/scaling.png)

Measured on this workstation (4× RTX 4090, i9-10980XE), depth-6 circuit,
1024 shots:

| qubits | CPU (s) | GPU (s) | GPU speedup |
|---|---|---|---|
| 20 | 0.15 | 0.67 | 0.35× (GPU slower) |
| 22 | 0.30 | 0.05 | 6.9× |
| 24 | 1.37 | 0.12 | 10.7× |
| 26 | 5.30 | 0.47 | 11.4× |
| 28 | 22.0 | 1.96 | 11.2× |

The GPU **loses** on tiny circuits (launch/transfer overhead) and crosses over
around **22 qubits**, then holds a ~11× lead. That crossover is the whole
point: GPUs help only once the statevector is large enough.

## Honest limits

- **This is not a quantum advantage.** Simulating a quantum computer is a
  *classical* computation; this measures classical statevector-simulation
  speed. It shows which classical hardware to use for simulation, not that
  quantum beats classical.
- **IonQ timings are not comparable wall-clock** to local runs — they include
  network and queue latency. The cloud run demonstrates *portability* (the
  same circuit runs on a real vendor, one line from real hardware), not speed.
- Memory wall: statevector = 16 bytes × 2ⁿ. One 24 GB RTX 4090 tops out near
  30 qubits; four pooled (cuStateVec) near 32. Beyond that, exact statevector
  simulation is infeasible on this machine — which is itself the reason large
  quantum circuits cannot be checked classically.
