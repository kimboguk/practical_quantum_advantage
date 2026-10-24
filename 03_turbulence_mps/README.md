# Demo C — Turbulence: can a quantum circuit represent what classical compression can't?

**One-line claim (concept):** a **short** quantum circuit can produce a
turbulence-like field that classical tensor-network compression *cannot* squeeze
— a necessary condition for quantum CFD. This is a **representability** demo, not
an application advantage.

## Why this matters (industry)

Turbulence shows up in almost every flow engineering problem: aircraft and car
drag, gas-turbine and engine combustion, chemical-reactor mixing, weather.
Resolving it directly (DNS) costs ~Reynolds-number³, which is impossible at real
aircraft/engine scale — so industry uses turbulence *models* (RANS, LES) whose
errors become design uncertainty. A quantum computer stores 2ⁿ grid values in n
qubits, raising the hope of representing flow fields beyond the classical cost
wall.

## What the demo does

On a 1D grid of 2¹⁶ points we set a Kolmogorov-like spectrum (amplitude
∝ k^(−5/6), energy spectrum ∝ k^(−5/3)) and vary **only the phases**, because the
phase structure is what makes turbulence hard to compress:

| phase structure | corresponding quantum circuit |
|---|---|
| zero | none (coherent) |
| linear polynomial | n single-qubit Rz gates |
| **quadratic polynomial** | **~n²/2 controlled-phase gates (short!)** |
| random | not a short circuit (2ⁿ independent values) |

For each field we compute the **MPS bond dimension χ** — the standard classical
measure of how hard a 1D field is to compress (small χ = easy, large χ = hard).
Pure numpy (`run.py`); the "phase degree → circuit depth" mapping is the quantum
argument.

## Result

![MPS bond dimension by phase structure](figures/compression.png)

| phase | circuit | χ (tol 1e−2) | χ (tol 1e−4) |
|---|---|---:|---:|
| zero | none | 4 | 6 |
| linear | n gates | 4 | 7 |
| **quadratic** | **~n²/2 gates** | **146** | **251** |
| random | — | 143 | 251 |

The surprise: a **quadratic** phase — buildable by a short, ~n²/2-gate circuit
(≈120 gates for n=16) — resists MPS compression **almost exactly as strongly as
fully random phases**. A short quantum circuit can thus express a turbulence-like
field that classical tensor networks cannot compress.

A full quantum recipe would be: prepare the (smooth, efficient) spectrum
amplitudes → apply controlled-phase gates → inverse Quantum Fourier Transform —
all O(n²) gates.

## What this does NOT prove (honest limits)

- **Representability ≠ application advantage** (the latter is unproven).
- Real turbulence phases are not exactly quadratic; coherent vortices may compress
  *better* than this worst-case construction.
- Open problems: efficiently **evolving** Navier–Stokes in this representation,
  and **reading out** useful observables with few measurements. Nonlinearity runs
  into Carleman conditions and the Childs et al. lower bounds.
- This is **1D**; 3D generalization needs separate study.

## Run

```bash
python run.py    # -> results/chi.csv, results/summary.json
python plot.py   # -> figures/compression.png
```
