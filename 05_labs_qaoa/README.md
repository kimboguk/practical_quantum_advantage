# Demo E — LABS: an optimization problem with a published quantum scaling claim

**One-line claim (tested, small scale):** for the LABS problem, the literature
reports that QAOA combined with quantum minimum finding scales better than the
best classical heuristic. We measure the same scaling exponents on our own
machine — and show how fragile they are at small N.

## The problem

Find a sequence of N signs s ∈ {+1, −1}ᴺ whose shifted copies overlap as little
as possible:

E(s) = Σₖ Cₖ²,  Cₖ = Σᵢ sᵢ sᵢ₊ₖ  (k = 1 … N−1)

Low-autocorrelation sequences are used for **radar / sonar pulse compression**
and communications. The problem is classically hard: the best heuristic,
Memetic Tabu Search (MTS), needs time ≈ 1.34ᴺ; exact optima are known only up
to N ≈ 66.

## Why this problem (vs. Max-Cut)

- It has a **published scaling-advantage claim**: Shaydulin et al.,
  *Sci. Adv.* 10, eadm6761 (2024), simulated QAOA up to N = 40:
  QAOA (p = 12) ≈ **1.46ᴺ**, QAOA + quantum minimum finding ≈ **1.21ᴺ**,
  classical MTS ≈ **1.34ᴺ**.
- Max-Cut has a classical approximation guarantee (Goemans–Williamson, 0.878)
  and excellent heuristics; there is no comparable advantage claim.

## What the demo does

| method | how TTS is measured |
|---|---|
| QAOA (p layers) | exact statevector simulation (own numpy simulator; the cost is diagonal). Linear-ramp schedule, 2 parameters tuned on N = 8–12 and **transferred unchanged** to larger N. TTS = 1 / P(optimum) shots |
| QAOA + QMF | idealized amplitude amplification on top: TTS = 1 / √P. Needs fault-tolerant hardware |
| MTS | our implementation of memetic tabu search; TTS = energy evaluations until the optimum is first hit (median of 20 runs) |
| brute force | 2ᴺ |

Only **exponents** are comparable — shots and classical evaluations are
different units. Correctness checks: the Ising expansion reproduces the
brute-force energies, the numpy simulator matches Qiskit's `Statevector`
(max diff 4e-17), and the minimal energies match the known LABS optima.

The same QAOA circuit is built in Qiskit (`PauliEvolutionGate` of the 2- and
4-body Z terms) and sampled on a `common/backend.py` target (Aer or IonQ) at
small N as a cross-check.

## Result (p = 12, N = 8–24, fit N = 14–24)

![LABS time-to-solution scaling](figures/tts_scaling.png)

| method | ours | literature |
|---|---:|---:|
| QAOA p = 12 | 1.75ᴺ | 1.46ᴺ |
| QAOA + QMF | 1.32ᴺ | 1.21ᴺ |
| MTS | 1.66ᴺ | 1.34ᴺ |
| brute force | 2ᴺ | 2ᴺ |

Circuit cross-check, N = 8, p = 12 (exact P(opt) = 0.614; random guessing = 0.0625):

| backend | shots | P(opt) sampled |
|---|---:|---:|
| Aer (local) | 4000 | 0.616 |
| IonQ ideal simulator | 1000 | 0.620 |
| IonQ noisy simulator (`aria-1`) | 1000 | **0.066** |

The circuit is already depth 675 with 783 two-qubit gates at N = 8 (Aer basis;
IonQ receives the Pauli rotations natively). Under a realistic noise model the
QAOA advantage over random guessing **disappears entirely** — LABS QAOA at
useful depth needs error-corrected hardware.

Reading:
- Same **ordering** as the literature: QAOA + QMF has the smallest exponent.
  QAOA alone is not better than the classical heuristic.
- Our absolute exponents are **worse** than published, for both sides: the
  2-parameter linear-ramp schedule is cruder than the paper's optimized fixed
  parameters, and our MTS is a basic version (population 20).
- The exponents are **fragile**: individual N values are unusually easy or
  hard (N = 14 is easy, N = 21 is hard), so the fitted base moves noticeably
  with the fit range. At p = 8, N = 8–20, fitting from N = 12 gave 1.57 / 1.25 / 1.55
  instead.

## What this does NOT prove (honest limits)

- Exponents fitted on N ≤ 24 do not establish asymptotic behaviour.
- The QMF speedup assumes **fault-tolerant** hardware; it is not available today.
- The LABS Hamiltonian has O(N³) four-body terms → deep circuits; on noisy
  hardware only very small N is feasible (IonQ's all-to-all connectivity helps).
- Classical solvers keep improving (e.g. GPU-parallel tabu search).
- Tuning the QAOA schedule used knowledge of the optimum at small N (as in the
  literature); that tuning cost is not counted.

## Run

```bash
python run.py                                    # N=8..20, p=8  (~35 s on CPU)
python run.py --n-max 24 --p 12 --fit-from 14    # result above (~6 min)
python run.py --circuit-backend ionq_sim --circuit-n 8   # IonQ cloud (needs IONQ_API_KEY)
python plot.py                                   # -> figures/tts_scaling.png
```
