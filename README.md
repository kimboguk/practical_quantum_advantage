# Practical Quantum Advantage — small, honest demonstrations

Can we *show* where a quantum computer helps — with code anyone can run and
numbers anyone can check? These self-contained demos do exactly that, at a
small enough scale to run on a laptop, while being honest about what they do and
do **not** prove. There are six demos: four application areas (chemistry,
finance, turbulence, optimization), a follow-up on the finance case (QSP payoff
encoding), and one backend-scaling study (local GPU and a real quantum vendor's
cloud).

## The ground rule

A classical simulator cannot, by itself, demonstrate a quantum *advantage* —
simulating a quantum computer is a classical computation. So each demo has two
jobs:

1. **Show the principle works at small scale** (run it, check the numbers), and
2. **Show why classical methods hit a wall at large scale**, through the computed
   results and resource-scaling arguments.

Every demo ends with an explicit **"what this does not prove"** section. The
honesty is the point: it is what makes the positive claims trustworthy.

## The demos

| # | Demo | Advantage type | What it shows |
|---|---|---|---|
| **A** | [Quantum chemistry: N₂ dissociation](01_chemistry_N2/) | **Accuracy** | The classical "gold standard" (CCSD(T)) gives the *wrong* energy for strongly-correlated molecules; the error grows as the bond stretches. The exact answer (FCI) is what an ideal quantum computer would return, given a good initial state. Part 2 runs SQD on the IonQ cloud simulator (20 qubits). **Strongest demo.** |
| **B** | [Finance: tail risk via amplitude estimation](02_finance_amplitude/) | **Quadratic speedup** | Quantum needs ~1/ε queries vs classical ~1/ε². Real — **but** a single quantum oracle is a deep, slow circuit, so it is not yet enough. Honest about limits. |
| **C** | [Turbulence: field compressibility](03_turbulence_mps/) | **Representability** (concept) | A short quantum circuit can produce a turbulence-like field that classical tensor-network compression cannot squeeze. A *necessary* condition for quantum CFD — not an application advantage. |
| **D** | [Backend scaling: CPU vs GPU vs IonQ cloud](04_scaling/) | **Engineering** (not an advantage) | Where a GPU earns its keep for *simulation* (~11× past ~22 qubits here), and the same circuit running on a real quantum vendor's cloud. Honest: this measures classical simulation speed, not quantum advantage. |
| **E** | [LABS optimization: QAOA scaling](05_labs_qaoa/) | **Scaling exponent** (claimed in literature) | Time-to-solution exponents for QAOA, QAOA + quantum minimum finding and a classical memetic tabu search, measured up to N = 24. Same ordering as the published claim (QAOA+QMF smallest), but exponents are fragile at small N and QMF needs fault tolerance. |
| **F** | [QSP: payoff encoding without arithmetic](06_qsp_payoff/) | **Mechanism** (constant-factor saving) | Quantum Signal Processing writes an option payoff into an amplitude with single-qubit rotations only; the phase fit is exact to machine precision and the error (~1/d) comes from the polynomial. The idea behind the ~16× T-gate saving reported for derivative pricing — a constant factor, not an advantage by itself. |

Each folder has its own README with the industry context, the result figure, and
the honest limits.

## How the demos are meant to be read

- **Demo A is the headline** — a single graph (classical gold standard peeling
  away from the exact curve) makes the accuracy case visually.
- **Demo B is the credibility** — it shows a genuine speedup *and* why that alone
  does not win yet.
- **Demo C is a concept** — it illustrates one necessary ingredient for quantum
  CFD, nothing more.
- **Demo D is tooling** — classical-simulation speed and cloud portability, not
  a quantum claim.
- **Demo E tests a published claim** — it reproduces the *ordering* of LABS
  scaling exponents at small N, shows noise erasing the effect today, and uses
  Max-Cut as a textbook QAOA control with no advantage claim.
- **Demo F follows up on B** — it shows *how* the cost of one amplitude-estimation
  query is being reduced (QSP instead of quantum arithmetic), and why that is a
  constant-factor saving, not an advantage on its own.

## Reproducibility

- Pinned environment: see [`environment.md`](environment.md) and
  [`requirements.txt`](requirements.txt). Verified with qiskit 2.6.0 /
  qiskit-aer 0.18.0 / pyscf 2.14.0.
- Each demo is standalone: `python run.py && python plot.py`. Results are
  deterministic (fixed seeds; demo B uses an exact statevector sampler), except
  demo A's unconverged CCSD points (flagged in its output) and anything sampled
  on the IonQ cloud.
- A GPU is used automatically when available, with automatic CPU fallback
  (`common/backend.py`); demos A–C are small and run fine on CPU.

## Backends: local GPU and IonQ cloud

`common/backend.py` is a single selector shared by the demos:

| Target | Runs on | Notes |
|---|---|---|
| `cpu` / `gpu` | local Aer | GPU auto-falls back to CPU if no CUDA Aer build |
| `ionq_sim` | **IonQ cloud** (ideal) | not local-only; ≤ 25 qubits (safe), 29 max |
| `ionq_noise` | IonQ cloud (`aria-1` noise) | approximates real hardware |
| `ionq_qpu` | IonQ **real hardware** | opt-in, consumes credits |

IonQ needs `IONQ_API_KEY` (get one at [cloud.ionq.com](https://cloud.ionq.com)):
`cp .env.example .env` and fill it in — `.env` is git-ignored and loaded
automatically by `common/backend.py`; never commit it. Demo B takes
`--backend`; Demo D takes `--backends`. Two honest notes:

- **Demo B stays small (4 qubits).** Arbitrary distribution loading
  (`StatePreparation`) costs ~2ⁿ gates, so it does *not* widen; the IonQ path
  there is for credibility ("runs on a real vendor"), not scale.
- **The GPU and IonQ are mutually exclusive per run** — an IonQ job does not
  touch the local GPU. Qubit-scaling on the GPU lives in Demo D.

## Report

A narrative write-up that stitches the demos' figures together for a
non-specialist reader is in [`REPORT.md`](REPORT.md).

## License

MIT — see [`LICENSE`](LICENSE). The SQD workflow and the `ibm_fez` sample data
in demo A are adapted from the qiskit-community NTU 2026 workshop and remain
under Apache-2.0; see [`NOTICE`](NOTICE) and
[`LICENSES/Apache-2.0.txt`](LICENSES/Apache-2.0.txt).

---

*These demos adapt the design and reference code of an internal study
(Demo Design: Quantum Advantage at Small Scale, 2026-10). They are educational;
nothing here is investment or engineering advice.*
