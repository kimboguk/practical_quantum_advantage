"""Demo A -- bond dissociation: where the classical gold standard breaks.

Computes the ground-state energy of a small molecule (default N2) as a bond is
stretched, with four methods of increasing accuracy:

  HF        -- mean-field (independent electrons)
  CCSD      -- coupled cluster, singles+doubles
  CCSD(T)   -- CCSD + perturbative triples  ("gold standard" of quantum chemistry)
  FCI       -- full configuration interaction = the EXACT answer in this basis.
               An ideal quantum phase estimation (QPE) would return this value.

Near equilibrium every method agrees. As the bond stretches the electrons
become strongly correlated (multi-reference), and CCSD(T) -- the best routine
classical method -- diverges from the exact FCI curve, even going below it
(unphysical). That failure is the point: in strongly correlated regions the
classical gold standard is unreliable, and FCI (hence QPE) is the exact
reference. FCI cost grows exponentially with system size, so for large
molecules there is no exact classical fallback -- which is the opening for a
fault-tolerant quantum computer.

Pure classical computation (PySCF). No quantum circuit is executed here; the
quantum-advantage claim is about the *scaling* argument stated above.

Molecules (closed-shell only, RHF reference):
  n2   N2 triple bond      -- strongest breakdown (default)
  f2   F2 single bond
  h2   H2 single bond      -- 2 electrons: CCSD is already exact (control case)
  lih  LiH single bond
  h2o  H2O symmetric O-H stretch (HOH angle fixed at 104.5 deg)

Run:   python run.py                       (N2 -> results/)
       python run.py --molecule h2o        (-> results/h2o/)
       python run.py --molecule f2 --basis 6-31g --bonds 1.2,1.4,2.0
"""
from __future__ import annotations
import argparse
import json
import math
import os
import numpy as np

HARTREE_TO_KCAL = 627.509
CHEM_ACCURACY_MEH = 1.6  # 1 kcal/mol in milli-Hartree
FCI_WARN_NAO = 16        # FCI gets slow / memory-hungry beyond ~16 orbitals
HERE = os.path.dirname(os.path.abspath(__file__))


def _diatomic(a, b):
    return lambda R: f"{a} 0 0 0; {b} 0 0 {R}"


def _water(R, angle_deg=104.5):
    th = math.radians(angle_deg / 2)
    x, z = R * math.sin(th), R * math.cos(th)
    return f"O 0 0 0; H {x} 0 {z}; H {-x} 0 {z}"


# name -> (label, geometry(R) -> PySCF atom string, default bond lengths in A)
MOLECULES = {
    "n2": ("N2", _diatomic("N", "N"),
           [0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.7, 2.0, 2.3, 2.5, 2.8, 3.0]),
    "f2": ("F2", _diatomic("F", "F"),
           [1.1, 1.2, 1.3, 1.4, 1.5, 1.7, 2.0, 2.3, 2.6, 3.0]),
    "h2": ("H2", _diatomic("H", "H"),
           [0.5, 0.6, 0.74, 0.9, 1.1, 1.4, 1.7, 2.0, 2.5, 3.0]),
    "lih": ("LiH", _diatomic("Li", "H"),
            [1.0, 1.3, 1.6, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]),
    "h2o": ("H2O", _water,
            [0.7, 0.8, 0.96, 1.1, 1.3, 1.5, 1.8, 2.1, 2.5]),
}


def classical_point(atom, basis):
    """RHF, CCSD, CCSD(T), FCI at one geometry. Returns (mf, ccsd, e_ccsd_t, e_fci)."""
    from pyscf import gto, scf, cc, fci
    mol = gto.M(atom=atom, basis=basis, verbose=0)
    mf = scf.RHF(mol).run()
    ccsd = cc.CCSD(mf).run()
    et = ccsd.ccsd_t()                     # perturbative triples correction
    e_fci = fci.FCI(mf).kernel()[0]
    return mf, ccsd, ccsd.e_tot + et, e_fci


def compute_curve(geometry, bond_lengths, basis):
    rows = []
    for R in bond_lengths:
        mf, ccsd, e_ccsd_t, e_fci = classical_point(geometry(R), basis)
        rows.append(dict(
            R=R,
            HF=float(mf.e_tot),
            CCSD=float(ccsd.e_tot),
            CCSD_T=float(e_ccsd_t),
            FCI=float(e_fci),
            err_ccsd_t_meh=float((e_ccsd_t - e_fci) * 1000.0),   # signed, mEh
            # unconverged CCSD (common when stretched) is not reproducible
            ccsd_converged=bool(ccsd.converged),
        ))
        flag = "" if ccsd.converged else "  [CCSD not converged]"
        print(f"R={R:4.2f}A  HF={mf.e_tot:11.5f}  CCSD(T)={e_ccsd_t:11.5f}  "
              f"FCI={e_fci:11.5f}  err={rows[-1]['err_ccsd_t_meh']:+8.1f} mEh"
              f"{flag}", flush=True)
    return rows


def analyze(rows, label, basis, nao, nelec):
    errs = np.array([r["err_ccsd_t_meh"] for r in rows])
    Rs = np.array([r["R"] for r in rows])
    abs_err = np.abs(errs)
    i_worst = int(np.nanargmax(abs_err))   # diverged CCSD can give NaN
    # first R where CCSD(T) leaves chemical accuracy
    beyond = Rs[abs_err > CHEM_ACCURACY_MEH]
    r_break = float(beyond.min()) if beyond.size else None
    summary = dict(
        molecule=label, basis=basis.upper(),
        active_space=f"{nao} orbitals / {nelec} electrons ({2 * nao} qubits, JW)",
        chem_accuracy_meh=CHEM_ACCURACY_MEH,
        worst=dict(R=float(Rs[i_worst]), err_meh=float(errs[i_worst]),
                   err_kcal=float(errs[i_worst] / 1000.0 * HARTREE_TO_KCAL)),
        first_R_beyond_chem_accuracy=r_break,
        max_abs_err_meh=float(np.nanmax(abs_err)),
        ccsd_unconverged_R=[r["R"] for r in rows if not r["ccsd_converged"]],
        note=("CCSD(T) is the classical 'gold standard'; its growing, "
              "eventually unphysical error vs exact FCI marks the strong-"
              "correlation breakdown. FCI == ideal QPE in this basis."),
        honest_limits=("This small case is solved exactly by FCI and also well "
                       "by classical strong-correlation methods (DMRG, CASSCF/"
                       "MRCI). The real crossover where no classical method "
                       "suffices is estimated around ~50 active orbitals."),
    )
    return summary


def results_dir(name):
    """N2 keeps the original results/ path; other molecules get a subfolder."""
    return os.path.join(HERE, "results") if name == "n2" else \
        os.path.join(HERE, "results", name)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--molecule", "-m", default="n2", choices=sorted(MOLECULES))
    ap.add_argument("--basis", default="sto-3g")
    ap.add_argument("--bonds", default=None,
                    help="comma-separated bond lengths in A (default: per molecule)")
    args = ap.parse_args()

    label, geometry, default_bonds = MOLECULES[args.molecule]
    bonds = [float(x) for x in args.bonds.split(",")] if args.bonds \
        else default_bonds

    from pyscf import gto
    probe = gto.M(atom=geometry(bonds[0]), basis=args.basis, verbose=0)
    nao, nelec = probe.nao, probe.nelectron
    print(f"{label} / {args.basis.upper()}: {nao} orbitals, {nelec} electrons "
          f"({2 * nao} qubits, JW)")
    if nao > FCI_WARN_NAO:
        print(f"WARNING: {nao} orbitals > {FCI_WARN_NAO}; FCI may be very slow "
              f"or run out of memory.")

    rows = compute_curve(geometry, bonds, args.basis)
    summary = analyze(rows, label, args.basis, nao, nelec)

    out = results_dir(args.molecule)
    os.makedirs(out, exist_ok=True)
    # CSV
    import csv
    csv_path = os.path.join(out, "energies.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    json.dump({"rows": rows, "summary": summary},
              open(os.path.join(out, "summary.json"), "w"), indent=2)

    print("\n=== Analysis ===")
    w = summary["worst"]
    print(f"Worst CCSD(T) error: {w['err_meh']:+.1f} mEh "
          f"(= {w['err_kcal']:+.0f} kcal/mol) at R={w['R']} A")
    print(f"CCSD(T) leaves chemical accuracy ({CHEM_ACCURACY_MEH} mEh) "
          f"beyond R={summary['first_R_beyond_chem_accuracy']} A")
    if summary["ccsd_unconverged_R"]:
        print(f"CCSD did not converge at R={summary['ccsd_unconverged_R']} A "
              f"-- CCSD(T) values there are not reproducible (FCI is).")
    rel = os.path.relpath(out, HERE)
    print(f"Saved: {rel}/energies.csv, {rel}/summary.json")


if __name__ == "__main__":
    main()
