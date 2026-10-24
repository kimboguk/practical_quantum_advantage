"""Demo E -- LABS: an optimization problem with a published quantum scaling claim.

Low Autocorrelation Binary Sequences (LABS): find s in {+1,-1}^N minimizing

    E(s) = sum_{k=1}^{N-1} C_k^2,     C_k = sum_i s_i s_{i+k}

(radar / sonar pulse compression). It is classically hard: the best heuristic,
Memetic Tabu Search (MTS), needs time ~1.34^N; exact optima are known only up
to N ~ 66. Shaydulin et al. (Science Advances 2024) simulated QAOA up to N=40
and reported time-to-solution ~1.46^N for QAOA alone and ~1.21^N combined with
quantum minimum finding (a Grover-type routine that needs fault tolerance).

This demo measures the same SCALING EXPONENTS on our own machine:

  QAOA       p layers, linear-ramp schedule (2 parameters) tuned on small N
             and TRANSFERRED unchanged to larger N. TTS = 1/P(optimum) shots.
  QAOA+QMF   idealized amplitude amplification on top: TTS ~ 1/sqrt(P).
  MTS        our implementation; TTS = energy evaluations to first hit the
             optimum (median over runs).
  brute      2^N (reference).

Only exponents are comparable (shots vs evaluations are different units).
QAOA is simulated exactly with a dedicated numpy statevector simulator (the
cost is diagonal). The same QAOA circuit is also built in Qiskit and sampled
on a common/backend.py target (Aer or IonQ) at small N as a cross-check.

Run:   python run.py                         (N=8..20, p=8; ~minutes on CPU)
       python run.py --n-max 24 --p 12
       python run.py --circuit-backend ionq_sim --circuit-n 8  (needs IONQ_API_KEY)
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import sys
import time
from collections import Counter
import numpy as np
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from common.backend import get_backend, check_qubits   # noqa: E402  (also loads .env)
SEED = 11
CHUNK = 1 << 20


# ---- LABS energy ----------------------------------------------------------
def spins(x, N):
    """Integer basis index -> spins; bit i (= qubit i) 0 -> +1, 1 -> -1."""
    return 1 - 2 * ((x[:, None] >> np.arange(N)) & 1).astype(np.int8)


def energy_of(S):
    """LABS energy of each row of a (M, N) +-1 array."""
    N = S.shape[1]
    E = np.zeros(S.shape[0], dtype=np.int64)
    for k in range(1, N):
        C = (S[:, :N - k] * S[:, k:]).sum(axis=1, dtype=np.int64)
        E += C * C
    return E


def all_energies(N):
    """E(x) for every basis index x in [0, 2^N)."""
    out = np.empty(2 ** N, dtype=np.int32)
    for a in range(0, 2 ** N, CHUNK):
        x = np.arange(a, min(a + CHUNK, 2 ** N), dtype=np.int64)
        out[a:a + x.size] = energy_of(spins(x, N))
    return out


def ising_terms(N):
    """E = const + sum_S c_S prod_{i in S} Z_i  (s_i = Z_i eigenvalue)."""
    const, terms = 0, Counter()
    for k in range(1, N):
        for i in range(N - k):
            const += 1                                 # i == j: s^2 s^2 = 1
            for j in range(i + 1, N - k):
                c = Counter([i, i + k, j, j + k])
                S = tuple(sorted(q for q, m in c.items() if m % 2))
                terms[S] += 2                          # (i,j) and (j,i)
    return const, {S: c for S, c in terms.items() if c}


# ---- QAOA statevector (diagonal cost) -------------------------------------
def schedule(dg, db, p):
    t = (np.arange(p) + 0.5) / p
    return dg * t, db * (1 - t)                        # linear ramp


def qaoa_probs(H, gammas, betas, N):
    psi = np.full(2 ** N, 2 ** (-N / 2), dtype=np.complex128)
    for g, b in zip(gammas, betas):
        psi *= np.exp(-1j * g * H)
        c, s = np.cos(b), -1j * np.sin(b)              # exp(-i b X) on each qubit
        for q in range(N):
            v = psi.reshape(-1, 2, 2 ** q)
            a0, a1 = v[:, 0, :].copy(), v[:, 1, :].copy()
            v[:, 0, :] = c * a0 + s * a1
            v[:, 1, :] = s * a0 + c * a1
    return np.abs(psi) ** 2


class Problem:
    def __init__(self, N):
        self.N = N
        self.E = all_energies(N)
        self.Emin = int(self.E.min())
        self.opt = self.E == self.Emin
        self.scale = float(self.E.std())               # makes gamma ~N-independent
        self.H = self.E / self.scale

    def p_opt(self, dg, db, p):
        g, b = schedule(dg, db, p)
        return float(qaoa_probs(self.H, g, b, self.N)[self.opt].sum())


def tune(problems, p):
    """Pick (dgamma, dbeta) maximizing mean log P(opt) over the tuning set."""
    f = lambda x: -np.mean([np.log(pr.p_opt(x[0], x[1], p)) for pr in problems])
    best = None
    for x0 in ([0.5, 0.5], [1.0, 0.8], [2.0, 1.0], [0.3, 1.2]):
        r = minimize(f, x0, method="Nelder-Mead",
                     options={"xatol": 1e-3, "fatol": 1e-4, "maxiter": 300})
        if best is None or r.fun < best.fun:
            best = r
    return best.x


# ---- classical: memetic tabu search ---------------------------------------
def tabu(s, E, rng, max_iter, target, budget):
    N = s.size
    tabu_until = np.zeros(N, dtype=np.int64)
    best_s, best_E, evals = s.copy(), E, 0
    for it in range(max_iter):
        F = np.tile(s, (N, 1)); F[np.arange(N), np.arange(N)] *= -1
        En = energy_of(F); evals += N
        ok = (tabu_until <= it) | (En < best_E)        # aspiration
        if not ok.any():
            continue
        i = int(np.flatnonzero(ok)[np.argmin(En[ok])])
        s[i] *= -1; E = int(En[i])
        tabu_until[i] = it + 1 + rng.integers(max(1, N // 10), max(2, N // 4) + 1)
        if E < best_E:
            best_s, best_E = s.copy(), E
        if best_E <= target or evals >= budget:
            break
    return best_s, best_E, evals


def mts(N, target, rng, pop=20, budget=10 ** 8):
    """Evaluations until MTS first reaches energy <= target (Gallardo et al. 2009)."""
    P = rng.choice(np.array([-1, 1], dtype=np.int8), size=(pop, N))
    PE = energy_of(P)
    evals = pop
    if PE.min() <= target:
        return evals
    while evals < budget:
        a, b = (P[min(rng.integers(pop, size=2), key=lambda i: PE[i])]
                for _ in range(2))                     # tournament selection
        cut = rng.integers(1, N)
        child = np.concatenate([a[:cut], b[cut:]])
        flip = rng.random(N) < 1.0 / N
        child[flip] *= -1
        cE = int(energy_of(child[None])[0]); evals += 1
        child, cE, e = tabu(child, cE, rng, int(rng.integers(N // 2, 3 * N // 2 + 1)),
                            target, budget - evals)
        evals += e
        if cE <= target:
            return evals
        w = int(np.argmax(PE))
        if cE < PE[w]:
            P[w], PE[w] = child, cE
    return evals


# ---- qiskit circuit (Aer / IonQ cross-check) -------------------------------
def qaoa_circuit(N, gammas, betas, scale):
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import PauliEvolutionGate
    from qiskit.quantum_info import SparsePauliOp
    _, terms = ising_terms(N)
    Hc = SparsePauliOp.from_sparse_list(
        [("Z" * len(S), list(S), c / scale) for S, c in terms.items()], num_qubits=N)
    qc = QuantumCircuit(N)
    qc.h(range(N))
    for g, b in zip(gammas, betas):
        # exp(-i g Hc); IonQ's native pauliexp rejects negative time, so fold
        # the sign into the operator
        qc.append(PauliEvolutionGate(np.sign(g) * Hc, time=abs(g)), range(N))
        qc.rx(2 * b, range(N))
    qc.measure_all()
    return qc


def circuit_check(pr, dg, db, p, target, shots):
    from qiskit import transpile
    check_qubits(target, pr.N)
    backend, label = get_backend(target, seed=SEED)
    g, b = schedule(dg, db, p)
    level = 1 if target.startswith("ionq") else 2
    tc = transpile(qaoa_circuit(pr.N, g, b, pr.scale), backend,
                   optimization_level=level, seed_transpiler=SEED)
    counts = backend.run(tc, shots=shots).result().get_counts()
    hits = sum(c for k, c in counts.items()
               if pr.opt[int(k.replace(" ", ""), 2)])  # key: qubit 0 rightmost
    ops = tc.count_ops()
    return dict(backend=label, N=pr.N, p=p, shots=shots, depth=tc.depth(),
                two_qubit_gates=int(sum(v for k, v in ops.items()
                                        if k in ("cx", "cz", "rzz", "ecr", "ms", "zz"))),
                p_opt_sampled=hits / shots, p_opt_exact=pr.p_opt(dg, db, p))


def fit_base(Ns, tts):
    m, c = np.polyfit(Ns, np.log2(tts), 1)
    return float(2 ** m), float(m), float(c)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n-min", type=int, default=8)
    ap.add_argument("--n-max", type=int, default=20)
    ap.add_argument("--p", type=int, default=8, help="QAOA layers")
    ap.add_argument("--tune-ns", default="8,9,10,11,12")
    ap.add_argument("--fit-from", type=int, default=12, help="fit exponents on N >= this")
    ap.add_argument("--mts-runs", type=int, default=20)
    ap.add_argument("--circuit-backend", default="cpu",
                    help="cpu|gpu|ionq_sim|ionq_noise|ionq_qpu|none")
    ap.add_argument("--circuit-n", type=int, default=8)
    ap.add_argument("--shots", type=int, default=4000)
    args = ap.parse_args()
    rng = np.random.default_rng(SEED)

    tune_ns = [int(x) for x in args.tune_ns.split(",")]
    t0 = time.time()
    dg, db = tune([Problem(n) for n in tune_ns], args.p)
    print(f"tuned on N={tune_ns}: dgamma={dg:.4f}, dbeta={db:.4f} "
          f"(p={args.p}, {time.time() - t0:.0f}s)", flush=True)

    rows = []
    for N in range(args.n_min, args.n_max + 1):
        t = time.time()
        pr = Problem(N)
        P = pr.p_opt(dg, db, args.p)
        evals = [mts(N, pr.Emin, rng) for _ in range(args.mts_runs)]
        rows.append(dict(N=N, E_min=pr.Emin, merit_factor=round(N * N / (2 * pr.Emin), 3),
                         n_optima=int(pr.opt.sum()), p_random=pr.opt.mean(),
                         p_opt_qaoa=P, tts_qaoa=1 / P, tts_qaoa_qmf=1 / np.sqrt(P),
                         tts_mts_median=float(np.median(evals)), tts_brute=2.0 ** N))
        r = rows[-1]
        print(f"N={N:2d}  Emin={pr.Emin:4d}  P_opt QAOA={P:.2e} (random {r['p_random']:.1e})  "
              f"MTS evals={r['tts_mts_median']:9.0f}  [{time.time() - t:.0f}s]", flush=True)

    fit = [r for r in rows if r["N"] >= args.fit_from]
    Ns = np.array([r["N"] for r in fit])
    bases = {k: fit_base(Ns, [r[k] for r in fit])
             for k in ("tts_qaoa", "tts_qaoa_qmf", "tts_mts_median")}

    check = None
    if args.circuit_backend != "none":
        if args.circuit_backend.startswith("ionq") and not os.environ.get("IONQ_API_KEY"):
            print("IonQ circuit check skipped: IONQ_API_KEY not set.")
        else:
            if args.circuit_backend == "ionq_qpu":
                print("WARNING: ionq_qpu runs on real hardware and consumes credits.")
            check = circuit_check(Problem(args.circuit_n), dg, db, args.p,
                                  args.circuit_backend, args.shots)
            print(f"circuit check N={check['N']} on {check['backend']}: depth={check['depth']}, "
                  f"2q gates={check['two_qubit_gates']}, P_opt sampled={check['p_opt_sampled']:.4f} "
                  f"vs exact={check['p_opt_exact']:.4f}")

    summary = dict(
        p=args.p, tuned_on=tune_ns, dgamma=float(dg), dbeta=float(db),
        fit_N=[int(Ns.min()), int(Ns.max())],
        base_qaoa=bases["tts_qaoa"][0], base_qaoa_qmf=bases["tts_qaoa_qmf"][0],
        base_mts=bases["tts_mts_median"][0], base_brute=2.0,
        fits={k: dict(base=v[0], slope_log2=v[1], intercept_log2=v[2])
              for k, v in bases.items()},
        literature=dict(qaoa_p12=1.46, qaoa_qmf=1.21, mts=1.34,
                        ref="Shaydulin et al., Sci. Adv. 10, eadm6761 (2024)"),
        circuit_check=check,
        honest_limits=("Exponents fitted on small N are fragile. QAOA+QMF needs "
                       "fault-tolerant hardware; QAOA alone is not faster than "
                       "MTS in the literature. The LABS cost has O(N^3) 4-body "
                       "terms -> deep circuits on today's hardware. Shots and "
                       "MTS evaluations are different units: compare exponents."),
    )
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "tts.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    json.dump({"rows": rows, "summary": summary},
              open(os.path.join(HERE, "results", "summary.json"), "w"), indent=2)

    print("\n=== Analysis (fit N >= %d) ===" % args.fit_from)
    print(f"QAOA p={args.p}:    TTS ~ {summary['base_qaoa']:.3f}^N   (literature p=12: 1.46)")
    print(f"QAOA + QMF:   TTS ~ {summary['base_qaoa_qmf']:.3f}^N   (literature: 1.21)")
    print(f"MTS (ours):   TTS ~ {summary['base_mts']:.3f}^N   (literature: 1.34)")
    print("Saved: results/tts.csv, results/summary.json")


if __name__ == "__main__":
    main()
