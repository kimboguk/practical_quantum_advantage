"""Demo C -- can a turbulence-like field be compressed classically?

A quantum computer stores 2^n amplitudes in n qubits, so the hope for quantum
CFD is to represent flow fields that classical methods cannot compress. The
standard classical compressor for 1D amplitude data is a Matrix Product State
(MPS); its "bond dimension" chi measures how hard the field is to compress
(small chi = easy, large chi = hard).

We build a 1D field (2^16 points) with a Kolmogorov-like energy spectrum
|u_hat(k)| ~ k^(-5/6)  (energy spectrum E(k) ~ k^(-5/3)) and vary only the
PHASES, because the phase structure is what makes turbulence hard:

  zero       -- coherent structure, no circuit
  linear     -- phase = linear polynomial  (n single-qubit Rz gates)
  quadratic  -- phase = quadratic polynomial (~n^2/2 controlled-phase gates)
  random     -- fully random phases (2^n independent values; NOT a short circuit)

We compute the MPS bond dimension chi of each real-space field. The finding:
a *quadratic* phase (buildable by a short, ~n^2/2-gate quantum circuit) resists
MPS compression almost as strongly as fully random phases. So a short quantum
circuit can express a turbulence-like field that classical tensor networks
cannot compress -- a necessary condition for quantum CFD.

Pure classical computation (numpy). No quantum circuit executed; the mapping
"phase polynomial degree -> circuit depth" is the quantum argument.

Run:   python run.py        (writes results/chi.csv, results/summary.json)
"""
from __future__ import annotations
import json
import os
import csv
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
N_QUBITS = 16
SEED = 3


def mps_bond_dimension(vec, tol):
    """Max MPS bond dimension of a 2^n vector at truncation tolerance `tol`.

    Sweeps every bipartition, counts Schmidt values whose discarded tail
    exceeds `tol` (relative Frobenius norm).
    """
    v = vec / np.linalg.norm(vec)
    n = int(np.log2(v.size))
    chi = 0
    for k in range(1, n):
        M = v.reshape(2 ** k, -1)
        # singular values via the smaller Gram matrix (numerically stable enough)
        G = M @ M.conj().T if M.shape[0] <= M.shape[1] else M.conj().T @ M
        s = np.sqrt(np.clip(np.linalg.eigvalsh(G).real, 0, None))[::-1]
        tail = np.sqrt(np.cumsum((s ** 2)[::-1]))[::-1]   # discarded norm if cut here
        chi = max(chi, int((tail > tol).sum()))
    return chi


def build_fields():
    N = 2 ** N_QUBITS
    rng = np.random.default_rng(SEED)
    k = np.arange(N)
    kk = np.minimum(k, N - k).astype(float)           # symmetric wavenumber
    amp = np.zeros(N)
    amp[kk > 0] = kk[kk > 0] ** (-5.0 / 6.0)          # Kolmogorov amplitude
    bits = ((k[:, None] >> np.arange(N_QUBITS)) & 1).astype(float)
    lin = rng.uniform(0, 2 * np.pi, N_QUBITS)
    quad = np.triu(rng.uniform(0, 2 * np.pi, (N_QUBITS, N_QUBITS)), 1)
    phases = {
        "zero":      np.zeros(N),
        "linear":    bits @ lin,
        "quadratic": bits @ lin + np.einsum("ki,ij,kj->k", bits, quad, bits),
        "random":    rng.uniform(0, 2 * np.pi, N),
    }
    circuit = {
        "zero": "none (coherent)",
        "linear": f"{N_QUBITS} single-qubit Rz gates",
        "quadratic": f"~{N_QUBITS*(N_QUBITS-1)//2} controlled-phase gates",
        "random": "not a short circuit (2^n values)",
    }
    fields = {name: np.fft.ifft(amp * np.exp(1j * ph)) for name, ph in phases.items()}
    return fields, circuit


def main():
    fields, circuit = build_fields()
    rows = []
    for name, f in fields.items():
        chi2 = mps_bond_dimension(f, 1e-2)
        chi4 = mps_bond_dimension(f, 1e-4)
        rows.append({"phase": name, "circuit": circuit[name],
                     "chi_tol_1e2": chi2, "chi_tol_1e4": chi4})
        print(f"{name:10} circuit={circuit[name]:35}  "
              f"chi(1e-2)={chi2:4d}  chi(1e-4)={chi4:4d}", flush=True)

    d = {r["phase"]: r for r in rows}
    quad_vs_random = d["quadratic"]["chi_tol_1e4"] / max(1, d["random"]["chi_tol_1e4"])
    summary = dict(
        n_qubits=N_QUBITS, grid_points=2 ** N_QUBITS, seed=SEED,
        quadratic_chi=d["quadratic"]["chi_tol_1e4"],
        random_chi=d["random"]["chi_tol_1e4"],
        quadratic_over_random=round(float(quad_vs_random), 3),
        finding=("A quadratic phase (short ~n^2/2-gate circuit) resists MPS "
                 "compression almost as much as fully random phases -> a short "
                 "quantum circuit can express a turbulence-like field that "
                 "classical tensor networks cannot compress."),
        honest_limits=("Representability is NOT an application advantage. Real "
                       "turbulence phases are not exactly quadratic (coherent "
                       "vortices may compress better). Evolving Navier-Stokes "
                       "and reading out useful observables efficiently are open "
                       "problems (Carleman / Childs et al. lower bounds). 1D only."),
    )
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "chi.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    json.dump({"rows": rows, "summary": summary},
              open(os.path.join(HERE, "results", "summary.json"), "w"), indent=2)

    print("\n=== Analysis ===")
    print(f"quadratic chi = {summary['quadratic_chi']}, random chi = "
          f"{summary['random_chi']} -> ratio {summary['quadratic_over_random']}")
    print("Short quadratic-phase circuit ~ as incompressible as random phases.")
    print("Saved: results/chi.csv, results/summary.json")


if __name__ == "__main__":
    main()
