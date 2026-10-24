"""Demo B -- tail-risk probability by quantum Amplitude Estimation.

Banks and insurers must estimate the probability of rare, large losses (the
"tail") to set regulatory capital, and they do it with large Monte Carlo (MC)
runs. Quantum Amplitude Estimation (AE) estimates such a probability with a
QUADRATIC speedup in queries: to reach error eps, classical MC needs ~1/eps^2
samples while AE needs ~1/eps oracle calls.

We discretize a heavy-tailed loss distribution (Student-t, nu=3) on 4 qubits,
load it into a quantum state (StatePreparation), flag "loss >= threshold" with
an IntegerComparator, and estimate the tail probability with Iterative
Amplitude Estimation (IQAE). For each target error eps we report the quantum
oracle calls and the classical MC samples needed for the same 95% precision.

Honest takeaway: the quadratic speedup is real, but a single oracle call is a
deep circuit that, on error-corrected hardware with a slow logical clock, is
far slower than one classical sample -- so the real crossover is pushed to much
smaller eps / larger problems, and classical MC also has variance-reduction
tricks (importance sampling). This demo shows BOTH the speedup and why it is
not, by itself, enough.

GPU is used automatically when an Aer GPU build is present; otherwise an exact
CPU statevector sampler is used (reproducible). See ../common/backend.py.

Run:   python run.py        (writes results/estimates.csv, results/summary.json)
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import csv
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))          # for `common`
from common.backend import make_sampler as backend_sampler  # noqa: E402

N_QUBITS = 4            # kept small on purpose: arbitrary StatePreparation has
                        # gate count ~2**N_QUBITS, so this demo does NOT widen.
                        # Qubit-scaling lives in ../04_scaling/.
THRESHOLD = 10          # integer bin index; "loss >= THRESHOLD"
TARGET_ERRORS = [0.005, 0.002, 0.001, 0.0005, 0.0002]
# IonQ cloud: fewer, looser targets so IQAE fires few jobs (each = one job).
TARGET_ERRORS_IONQ = [0.02, 0.01]
SEED = 1
SHOTS = 4096


def build_problem():
    """Student-t(nu=3) tail problem -> (EstimationProblem, exact_probability)."""
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import StatePreparation, IntegerComparator
    from qiskit_algorithms import EstimationProblem

    N = 2 ** N_QUBITS
    x = np.linspace(-4, 8, N)
    p = (1 + x ** 2 / 3) ** (-2)          # unnormalized Student-t(nu=3) density
    p /= p.sum()
    exact = float(p[THRESHOLD:].sum())

    cmp = IntegerComparator(N_QUBITS, THRESHOLD, geq=True)
    A = QuantumCircuit(N_QUBITS + 1 + cmp.num_ancillas)
    A.append(StatePreparation(np.sqrt(p)), range(N_QUBITS))
    A.append(cmp, list(range(N_QUBITS)) + [N_QUBITS]
             + list(range(N_QUBITS + 1, N_QUBITS + 1 + cmp.num_ancillas)))
    A = A.decompose(reps=3)
    problem = EstimationProblem(state_preparation=A, objective_qubits=[N_QUBITS])
    return problem, exact


def make_sampler(backend):
    """Sampler for IQAE, selected by `backend`.

    - "exact" (default): EXACT statevector sampler -- reproducible, matches the
      reference numbers, no shot noise. The AE circuits are tiny (5 qubits), so
      this is the honest default; GPU gives no benefit at this size.
    - "cpu"/"gpu": local Aer shot sampler (adds shot noise; shows the plumbing).
    - "ionq_sim"/"ionq_noise"/"ionq_qpu": the SAME circuit on the IonQ cloud,
      i.e. not local-only. Each IQAE round is one cloud job, so use the smaller
      TARGET_ERRORS_IONQ set. Returns (sampler, label).
    """
    if backend == "exact":
        from qiskit.primitives import StatevectorSampler   # exact, reproducible
        return StatevectorSampler(seed=SEED), "statevector(exact)"
    return backend_sampler(backend, shots=SHOTS, seed=SEED)


def classical_mc_samples(p, eps):
    """MC samples for 95% CI half-width eps on a probability p."""
    return int(np.ceil(1.96 ** 2 * p * (1 - p) / eps ** 2))


def main():
    from qiskit_algorithms import IterativeAmplitudeEstimation

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--backend", default="exact",
                    choices=["exact", "cpu", "gpu", "ionq_sim", "ionq_noise",
                             "ionq_qpu"],
                    help="exact=reproducible default; ionq_*=IonQ cloud")
    args = ap.parse_args()

    problem, exact = build_problem()
    sampler, label = make_sampler(args.backend)
    errors = TARGET_ERRORS_IONQ if args.backend.startswith("ionq") else TARGET_ERRORS
    print(f"Exact tail probability P(loss>=thr) = {exact:.4f}  (backend={label})")
    if args.backend.startswith("ionq"):
        print(f"[ionq] cloud run: {len(errors)} target(s) to bound job count\n")
    else:
        print()

    rows = []
    for eps in errors:
        iae = IterativeAmplitudeEstimation(epsilon_target=eps, alpha=0.05,
                                           sampler=sampler)
        res = iae.estimate(problem)
        mc = classical_mc_samples(exact, eps)
        rows.append(dict(eps=eps, estimate=float(res.estimation), exact=exact,
                         quantum_oracle_calls=int(res.num_oracle_queries),
                         classical_mc_samples=mc,
                         sample_ratio=round(mc / max(1, res.num_oracle_queries), 2)))
        print(f"eps={eps:<7} est={res.estimation:.4f}  "
              f"quantum_oracle={res.num_oracle_queries:>9}  "
              f"classical_MC={mc:>9}", flush=True)

    # crossover: smallest eps where quantum oracle calls < classical MC samples
    cross = next((r["eps"] for r in rows
                  if r["quantum_oracle_calls"] < r["classical_mc_samples"]), None)
    summary = dict(
        n_qubits=N_QUBITS, exact_probability=exact, backend=label,
        crossover_eps=cross,
        scaling=("classical MC ~ 1/eps^2 (halving eps -> 4x samples); "
                 "quantum AE ~ 1/eps (halving eps -> ~2x oracle calls)"),
        honest_limits=("One oracle call is a deep circuit; on error-corrected "
                       "hardware (slow logical clock, ~45 MHz cited for "
                       "derivative pricing) it is far slower than one classical "
                       "sample, pushing the real crossover to much smaller eps / "
                       "larger problems. Classical MC also has importance "
                       "sampling. The quadratic speedup alone is not enough -- "
                       "which is why finance is not the first quantum priority."),
    )
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "estimates.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    json.dump({"rows": rows, "summary": summary},
              open(os.path.join(HERE, "results", "summary.json"), "w"), indent=2)

    print(f"\n=== Analysis ===")
    print(f"Quantum oracle calls scale ~1/eps, classical MC ~1/eps^2.")
    print(f"Crossover (quantum < classical in query count) near eps={cross}.")
    print("But one oracle call >> one MC sample on real hardware (see summary).")
    print("Saved: results/estimates.csv, results/summary.json")


if __name__ == "__main__":
    main()
