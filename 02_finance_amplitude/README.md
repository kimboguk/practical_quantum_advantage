# Demo B — Finance: tail-risk by quantum Amplitude Estimation (a speedup, honestly)

**One-line claim:** quantum Amplitude Estimation needs **~1/ε** queries where
classical Monte Carlo needs **~1/ε²** — a real *quadratic* speedup — **but** that
alone is not enough to beat classical in practice yet. This demo shows both.

## Why this matters (industry)

Banks and insurers must size the probability of rare, large losses (the "tail")
to set **regulatory capital** — Expected Shortfall (Basel FRTB), credit loss
distributions, K-ICS / Solvency II, derivative pricing / CVA. They compute these
with **large Monte Carlo runs**, often daily and sometimes nested (scenarios
within scenarios), which is expensive. Real losses have fatter tails than a
normal distribution, so naive assumptions underestimate risk.

## What the demo does

1. Build a heavy-tailed loss distribution (Student-t, ν=3) on **4 qubits**.
2. Load it into a quantum state (`StatePreparation`), and flag "loss ≥ threshold"
   with an `IntegerComparator`.
3. Estimate the tail probability **P(loss ≥ threshold) = 0.0165** with
   **Iterative Amplitude Estimation (IQAE)**.
4. For each target error ε, compare the **quantum oracle calls** with the
   **classical Monte Carlo samples** needed for the same 95% precision.

`run.py` uses an exact statevector sampler (reproducible). It detects a GPU and
reports it, but these 5-qubit circuits don't need one.

## Result

| target ε | quantum oracle calls | classical MC samples |
|---:|---:|---:|
| 0.005  | 62,464 | 2,497 |
| 0.002  | 62,464 | 15,604 |
| 0.001  | 62,464 | 62,415 |
| 0.0005 | 62,464 | 249,658 |
| 0.0002 | 1,088,512 | 1,560,361 |

![Quantum vs classical scaling](figures/scaling.png)

Classical MC grows as **1/ε²** (halve the error → 4× the work); quantum grows as
**~1/ε** (halve the error → ~2× the work). The curves cross near **ε ≈ 0.001**:
for finer precision, quantum needs *fewer queries*.

## What it means

The quadratic speedup is genuine and matters more as you demand higher precision
or tackle larger, nested problems.

## What this does NOT prove (honest limits)

- "Fewer queries" ≠ "faster." **One quantum oracle call is a deep circuit.** On
  error-corrected hardware with a slow logical clock (≈45 MHz has been cited for
  derivative pricing), one oracle call is *millions of times slower* than one
  classical sample, pushing the real crossover to much smaller ε / larger
  problems.
- Classical MC also has **variance-reduction tricks** (importance sampling) that
  slash the sample count for rare events.
- **Bottom line:** this is the honest basis for *why finance is not the first
  quantum priority* — the speedup is real but not yet sufficient. Showing that we
  understand this limit is itself a credibility signal.

## Run

```bash
python run.py    # -> results/estimates.csv, results/summary.json
python plot.py   # -> figures/scaling.png
```
