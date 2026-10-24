"""Demo F -- Quantum Signal Processing (QSP): encode an option payoff into an
amplitude with single-qubit rotations instead of quantum arithmetic.

Why: in amplitude-estimation pricing, the payoff f(price) must sit in an
amplitude. Earlier resource estimates computed it with reversible arithmetic
(adders, multipliers, comparators), which dominates logical qubits and T-gates.
QSP instead turns repeated calls of a "signal" rotation W(x) into a polynomial
P(x) of the signal, with the polynomial chosen by d+1 phase angles. This is the
idea behind Stamatopoulos et al., Quantum 8, 1322 (2024).

What this script does (pure numpy/scipy; Qiskit only for a cross-check):
  1. Target: call payoff on a normalized price y in [0,1], strike K,
     g(y) = 0.5 * max(y - K, 0) / (1 - K)   (scaled so |g| <= 0.5).
     QSP polynomials have definite parity, so we use the even extension
     f(x) = g(|x|) on [-1, 1].
  2. For each degree d: Chebyshev interpolant of f (the best practical
     polynomial approximation), then find QSP phases so that
     Re <0| U_phi(x) |0> reproduces that polynomial (optimization-based phase
     finding, Dong-Meng-Whaley-Lin 2021 style).
  3. Report: Chebyshev approximation error, QSP fitting error, number of signal
     calls (= d) and single-qubit rotations (= 2d + 1).
  4. Cross-check: the same phase sequence built as a Qiskit circuit
     (RZ / RX gates) gives the same amplitude via Operator.

QSP convention ("Wx"):  W(x) = exp(i*theta*X) with x = cos(theta),
U_phi(x) = e^{i phi_0 Z} * prod_{k=1..d} [ W(x) e^{i phi_k Z} ].

Run:  python run.py            (~1 s on CPU)
"""
from __future__ import annotations
import json
import os
import time
import numpy as np
from numpy.polynomial import chebyshev as C
from scipy.optimize import least_squares

HERE = os.path.dirname(os.path.abspath(__file__))
STRIKE = 0.5
DEGREES = list(range(4, 52, 4))      # 4, 8, ..., 48
GRID = np.linspace(-1, 1, 2001)


def payoff(y):
    return 0.5 * np.maximum(y - STRIKE, 0.0) / (1.0 - STRIKE)


def target(x):                      # even extension on [-1, 1]
    return payoff(np.abs(x))


def cheb_even(d):
    """Degree-d Chebyshev interpolant of the even target, odd terms removed."""
    c = C.chebinterpolate(target, d)
    c[1::2] = 0.0
    return c


# ---------------------------------------------------------------- QSP core
def qsp_amplitude(phis, x):
    """<0| U_phi(x) |0> for an array of x (vectorized 2x2 products)."""
    x = np.atleast_1d(x).astype(float)
    s = np.sqrt(np.clip(1.0 - x * x, 0.0, None))
    def zrot(p):                     # e^{i p Z} as broadcastable 2x2
        return np.array([[np.exp(1j * p), 0], [0, np.exp(-1j * p)]])
    W = np.empty((x.size, 2, 2), complex)
    W[:, 0, 0] = x; W[:, 1, 1] = x; W[:, 0, 1] = 1j * s; W[:, 1, 0] = 1j * s
    U = np.broadcast_to(zrot(phis[0]), (x.size, 2, 2)).copy()
    for p in phis[1:]:
        U = U @ W @ zrot(p)
    return U[:, 0, 0]


def find_phases(coef, d):
    """Fit symmetric phases so that Re<0|U|0> matches the Chebyshev polynomial."""
    dt = int(np.ceil((d + 1) / 2))
    j = np.arange(1, 2 * dt + 1)
    xs = np.cos((2 * j - 1) * np.pi / (8 * dt))      # Chebyshev nodes in (0, 1]
    ys = C.chebval(xs, coef)

    def full(half):                   # mirror: phi_k = phi_{d-k}
        return np.concatenate([half, half[::-1][(d + 1) % 2:]])

    half0 = np.zeros(dt); half0[0] = np.pi / 4
    res = least_squares(lambda h: qsp_amplitude(full(h), xs).real - ys,
                        half0, xtol=1e-14, ftol=1e-14, gtol=1e-14, max_nfev=20000)
    return full(res.x)


def qiskit_check(phis, xs):
    """Same sequence as a 1-qubit Qiskit circuit; return <0|U|0> per x."""
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Operator
    out = []
    for x in xs:
        theta = np.arccos(x)
        qc = QuantumCircuit(1)
        # rightmost factor acts first: e^{i phi_d Z}, W, ..., W, e^{i phi_0 Z}
        qc.rz(-2 * phis[-1], 0)
        for p in phis[-2::-1]:
            qc.rx(-2 * theta, 0)         # W(x) = exp(i theta X) = RX(-2 theta)
            qc.rz(-2 * p, 0)             # e^{i p Z} = RZ(-2 p)
        out.append(Operator(qc).data[0, 0])
    return np.array(out)


def main():
    rows = []
    t0 = time.time()
    for d in DEGREES:
        coef = cheb_even(d)
        cheb = C.chebval(GRID, coef)
        phis = find_phases(coef, d)
        qsp = qsp_amplitude(phis, GRID).real
        err_cheb = float(np.max(np.abs(cheb - target(GRID))))
        err_fit = float(np.max(np.abs(qsp - cheb)))
        err_tot = float(np.max(np.abs(qsp - target(GRID))))
        rows.append(dict(degree=d, signal_calls=d, single_qubit_rotations=2 * d + 1,
                         err_chebyshev=err_cheb, err_qsp_fit=err_fit,
                         err_total=err_tot, phases=[float(p) for p in phis]))
        print(f"d={d:>3}  signal calls={d:>3}  max|cheb-f|={err_cheb:.4f}  "
              f"max|QSP-cheb|={err_fit:.1e}  max|QSP-f|={err_tot:.4f}", flush=True)

    # Qiskit cross-check on the largest degree
    xs = np.linspace(-1, 1, 41)
    ref = qsp_amplitude(np.array(rows[-1]["phases"]), xs)
    qk = qiskit_check(np.array(rows[-1]["phases"]), xs)
    qk_diff = float(np.max(np.abs(qk - ref)))
    print(f"Qiskit circuit cross-check (d={rows[-1]['degree']}): "
          f"max |amp_qiskit - amp_numpy| = {qk_diff:.1e}")

    # error scaling: kinked payoff -> Chebyshev error ~ 1/d
    ds = np.array([r["degree"] for r in rows], float)
    es = np.array([r["err_total"] for r in rows])
    slope = float(np.polyfit(np.log(ds), np.log(es), 1)[0])
    print(f"max error ~ d^{slope:.2f}  (kink at the strike -> ~1/d)")

    summary = dict(
        strike=STRIKE, target="0.5*max(y-K,0)/(1-K), even extension",
        error_scaling_exponent=slope, qiskit_crosscheck_max_diff=qk_diff,
        honest_limits=("Shows the encoding mechanism only. The resource saving "
                       "reported in the literature is a constant factor (~16x "
                       "fewer T-gates, ~4x fewer logical qubits), not an "
                       "exponential speedup; advantage for derivative pricing "
                       "still needs ~4.7k logical qubits and ~1e9 T-gates at a "
                       "45 MHz logical clock (Stamatopoulos et al. 2024). The "
                       "signal here is an explicit 1-qubit rotation; in a real "
                       "pricer it is a block-encoding of the price register."),
    )
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    import csv
    with open(os.path.join(HERE, "results", "qsp.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[k for k in rows[0] if k != "phases"])
        w.writeheader()
        for r in rows:
            w.writerow({k: v for k, v in r.items() if k != "phases"})
    json.dump(dict(rows=rows, summary=summary),
              open(os.path.join(HERE, "results", "summary.json"), "w"), indent=2)
    print(f"Saved: results/qsp.csv, results/summary.json  ({time.time() - t0:.1f} s)")


if __name__ == "__main__":
    main()
