"""Demo A2 -- SQD: quantum samples pick the configurations, a classical
computer diagonalizes in that small subspace.

Sample-based Quantum Diagonalization (SQD) is the practical answer to "why use
a quantum computer if FCI exists?": FCI diagonalizes in the *full* space of
electron configurations, which grows exponentially. SQD runs a short circuit
(LUCJ ansatz, built from CCSD amplitudes), samples bitstrings = configurations,
and diagonalizes the Hamiltonian only in the subspace those samples span
(after "configuration recovery" fixes samples with the wrong electron count).

Here the subspace is capped at --max-dim strings per spin (default 30 -> at
most 900 determinants, ~6% of N2/STO-3G's 14,400), and the result is compared
against HF, CCSD(T) and exact FCI at each bond length.

Sample sources (--backend):
  ibm_fez_cached  10,000 REAL shots from IBM's ibm_fez (N2, R=1.1 A only),
                  from the qiskit-community NTU 2026 workshop (see data/)
  random          CONTROL: uniform random bitstrings, no circuit at all
  cpu | gpu       local Aer (noiseless) sampling of the same circuit
  ionq_sim        IonQ cloud ideal simulator          (needs IONQ_API_KEY)
  ionq_noise      IonQ cloud sim + hardware noise     (needs IONQ_API_KEY)
  ionq_qpu        IonQ real hardware -- consumes credits, opt-in

Honest limits: with noiseless samples the subspace is close to ideal; on this
tiny case classical selected-CI picks the same determinants without any
quantum computer. Whether quantum sampling beats classical selection at scale
is an open, actively debated question.

Run:   python run_sqd.py                                  (N2, cpu, 4 bond lengths)
       python run_sqd.py --backend ibm_fez_cached         (real hardware samples)
       python run_sqd.py -m h2o --backend ionq_sim --bonds 0.96,1.8
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import sys
import warnings
from math import comb
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from common.backend import get_backend, check_qubits   # noqa: E402
from run import MOLECULES, classical_point              # noqa: E402

CACHED_R = 1.1   # geometry of the cached ibm_fez job (energies match run.py at 1.1 A)
SEED = 0


def lucj_t2(mf, ccsd):
    """CCSD t2 when CCSD converged; MP2 t2 otherwise (stretched bonds)."""
    if ccsd.converged and np.all(np.isfinite(ccsd.t2)):
        return ccsd.t2, "ccsd"
    from pyscf import mp
    return mp.MP2(mf).run(verbose=0).t2, "mp2"


def lucj_circuit(norb, nelec, t2):
    import ffsim
    from qiskit import QuantumCircuit, QuantumRegister
    op = ffsim.UCJOpSpinBalanced.from_t_amplitudes(t2, n_reps=1)
    q = QuantumRegister(2 * norb, name="q")
    circ = QuantumCircuit(q)
    circ.append(ffsim.qiskit.PrepareHartreeFockJW(norb, nelec), q)
    circ.append(ffsim.qiskit.UCJOpSpinBalancedJW(op), q)
    circ.measure_all()
    return circ


def sample_backend(circ, target, shots):
    """Transpile (ffsim pre-init) and sample on a common/backend.py target."""
    import ffsim
    from qiskit.primitives import BitArray
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    check_qubits(target, circ.num_qubits)
    backend, label = get_backend(target, seed=SEED)
    # IonQ (QIS) recommends optimization_level 0-1 to avoid re-synthesis
    level = 1 if target.startswith("ionq") else 3
    pm = generate_preset_pass_manager(optimization_level=level, backend=backend)
    pm.pre_init = ffsim.qiskit.PRE_INIT   # merges orbital rotations -> shallower
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tc = pm.run(circ)
    n2q = sum(v for k, v in tc.count_ops().items()
              if k in ("rxx", "ryy", "rzz", "cx", "cz", "cp", "ecr", "ms", "zz"))
    print(f"  circuit on {label}: depth={tc.depth()}, 2q gates={n2q}", flush=True)
    counts = backend.run(tc, shots=shots).result().get_counts()
    return BitArray.from_counts(counts, num_bits=circ.num_qubits), label


def load_cached():
    from qiskit.primitives import BitArray
    d = np.load(os.path.join(HERE, "data", "n2_ibm_fez_samples.npz"))
    return BitArray(d["array"], int(d["num_bits"])), "ibm_fez (cached real shots)"


def run_sqd(mf, bit_array, norb, nelec, args):
    import ffsim
    from qiskit_addon_sqd.fermion import diagonalize_fermionic_hamiltonian
    ham = ffsim.MolecularData.from_scf(mf).hamiltonian
    energies, occ, res = [], None, None
    # one iteration per call, carrying occupancies forward (self-consistent
    # configuration recovery, as in the NTU workshop notebook)
    for it in range(args.iterations):
        res = diagonalize_fermionic_hamiltonian(
            ham.one_body_tensor, ham.two_body_tensor, bit_array,
            samples_per_batch=args.samples_per_batch, norb=norb, nelec=nelec,
            num_batches=args.batches, max_iterations=1, symmetrize_spin=True,
            max_dim=args.max_dim, initial_occupancies=occ, seed=SEED + it)
        occ = res.orbital_occupancies
        energies.append(res.energy + ham.constant)
    dim = res.sci_state.ci_strs_a.size * res.sci_state.ci_strs_b.size
    return energies[-1], dim


def results_dir(name):
    return os.path.join(HERE, "results", "sqd") if name == "n2" else \
        os.path.join(HERE, "results", "sqd", name)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--molecule", "-m", default="n2", choices=sorted(MOLECULES))
    ap.add_argument("--basis", default="sto-3g")
    ap.add_argument("--bonds", default="1.1,1.5,2.0,2.5",
                    help="comma-separated bond lengths in A")
    ap.add_argument("--backend", default="cpu",
                    choices=["ibm_fez_cached", "random", "cpu", "gpu",
                             "ionq_sim", "ionq_noise", "ionq_qpu"])
    ap.add_argument("--shots", type=int, default=10_000)
    ap.add_argument("--max-dim", type=int, default=30,
                    help="max strings per spin (subspace <= max_dim^2)")
    ap.add_argument("--samples-per-batch", type=int, default=300)
    ap.add_argument("--batches", type=int, default=3)
    ap.add_argument("--iterations", type=int, default=5)
    args = ap.parse_args()

    label, geometry, _ = MOLECULES[args.molecule]
    bonds = [float(x) for x in args.bonds.split(",")]
    if args.backend == "ibm_fez_cached":
        if args.molecule != "n2" or args.basis.lower() != "sto-3g":
            sys.exit("ibm_fez_cached samples exist only for N2 / STO-3G")
        bonds = [CACHED_R]
    if args.backend.startswith("ionq") and not os.environ.get("IONQ_API_KEY"):
        sys.exit("IonQ backends need IONQ_API_KEY (set it in the repo-root .env; "
                 "see .env.example).")
    if args.backend == "ionq_qpu":
        print("WARNING: ionq_qpu runs on real hardware and consumes credits.")

    rows = []
    for R in bonds:
        mf, ccsd, e_ccsd_t, e_fci = classical_point(geometry(R), args.basis)
        norb, nelec = mf.mol.nao, (mf.mol.nelectron // 2,) * 2
        full = comb(norb, nelec[0]) * comb(norb, nelec[1])
        print(f"R={R:.2f}A  {norb} orbitals, {2 * norb} qubits, FCI space {full:,}",
              flush=True)
        if args.backend == "ibm_fez_cached":
            bit_array, src = load_cached()
            amp = "ccsd"
        elif args.backend == "random":
            from qiskit_addon_sqd.counts import generate_bit_array_uniform
            bit_array = generate_bit_array_uniform(args.shots, 2 * norb, rand_seed=SEED)
            src, amp = "uniform random bitstrings (no circuit)", "none"
        else:
            t2, amp = lucj_t2(mf, ccsd)
            bit_array, src = sample_backend(lucj_circuit(norb, nelec, t2),
                                            args.backend, args.shots)
        e_sqd, dim = run_sqd(mf, bit_array, norb, nelec, args)
        rows.append(dict(
            R=R, HF=float(mf.e_tot), CCSD_T=float(e_ccsd_t), FCI=float(e_fci),
            SQD=float(e_sqd), sqd_dim=int(dim), full_dim=int(full),
            subspace_frac=round(dim / full, 4),
            err_sqd_meh=float((e_sqd - e_fci) * 1000.0),
            err_ccsd_t_meh=float((e_ccsd_t - e_fci) * 1000.0),
            ccsd_converged=bool(ccsd.converged), lucj_amplitudes=amp,
            samples=src,
        ))
        r = rows[-1]
        print(f"  SQD={e_sqd:11.5f} (dim {dim:,} = {100 * r['subspace_frac']:.1f}%)  "
              f"err SQD={r['err_sqd_meh']:+7.2f} mEh  "
              f"err CCSD(T)={r['err_ccsd_t_meh']:+8.1f} mEh"
              f"{'' if ccsd.converged else '  [CCSD not converged]'}", flush=True)

    summary = dict(
        molecule=label, basis=args.basis.upper(), backend=args.backend,
        shots=args.shots if args.backend != "ibm_fez_cached" else 10_000,
        max_dim_per_spin=args.max_dim,
        note=("SQD energy is variational (>= FCI). Its error vs FCI comes from "
              "the truncated subspace; CCSD(T) error comes from the method."),
        honest_limits=("Tiny system: classical selected-CI finds the same "
                       "subspace. Noiseless simulated samples are optimistic; "
                       "real-hardware advantage of SQD is unproven."),
    )
    out = results_dir(args.molecule)
    os.makedirs(out, exist_ok=True)
    tag = args.backend if args.max_dim == 30 else f"{args.backend}_dim{args.max_dim}"
    with open(os.path.join(out, f"sqd_{tag}.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    json.dump({"rows": rows, "summary": summary},
              open(os.path.join(out, f"summary_{tag}.json"), "w"), indent=2)
    rel = os.path.relpath(out, HERE)
    print(f"Saved: {rel}/sqd_{tag}.csv, {rel}/summary_{tag}.json")


if __name__ == "__main__":
    main()
