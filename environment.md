# Environment setup

The demos are small and run on CPU. A GPU (CUDA + Aer GPU build) is used
automatically when present, with automatic CPU fallback (see `common/backend.py`).

## Recommended: conda (GPU-capable Aer)

```bash
conda create -n practical_quantum_advantage -c conda-forge -y --solver=libmamba \
  python=3.11 "qiskit-aer=*=cuda129*" qiskit qiskit-algorithms qiskit-optimization \
  numpy scipy matplotlib pandas pyscf

conda run -n practical_quantum_advantage pip install \
  qiskit-ionq qiskit-nature qiskit-machine-learning qiskit-finance dwave-ocean-sdk
```

- `qiskit-aer=*=cuda129*` pulls the CUDA 12.9 GPU build (match your CUDA; drop the
  `=*=cuda129*` for a CPU-only Aer).
- Verified versions: qiskit 2.6.0, qiskit-aer 0.18.0 (CPU+GPU), pyscf 2.14.0.

## CPU-only alternative (pip / venv)

```bash
python -m venv .venv && source .venv/bin/activate
pip install qiskit qiskit-aer qiskit-algorithms numpy scipy matplotlib pyscf
# optional: pip install qiskit-nature qiskit-finance qiskit-machine-learning qiskit-ionq dwave-ocean-sdk
```

PySCF wheels exist for Linux/macOS; on other platforms use conda-forge.

## Run

```bash
# each demo is standalone
cd 01_chemistry_N2      && python run.py && python plot.py
cd 02_finance_amplitude && python run.py && python plot.py   # add --backend cpu|gpu|ionq_sim
cd 03_turbulence_mps    && python run.py && python plot.py
cd 04_scaling           && python run.py && python plot.py   # --backends cpu,gpu[,ionq_sim]
```

Each writes `results/*.csv`, `results/summary.json`, and `figures/*.png`.
Results are deterministic (fixed seeds; demo B's default is an exact statevector
sampler — shot-based backends add sampling noise).

## IonQ cloud (optional)

Backends `ionq_sim` / `ionq_noise` / `ionq_qpu` run on IonQ's cloud, not
locally. Get a token at [cloud.ionq.com](https://cloud.ionq.com) and put it in a
`.env` file at the repo root (git-ignored; `common/backend.py` loads it
automatically, and an already-exported variable takes precedence):

```bash
cp .env.example .env           # then edit: IONQ_API_KEY=<your key>; never commit .env
python run.py --backend ionq_sim          # demo B on the cloud (small)
python run.py --backends ionq_sim         # demo D, one cloud point (<= 25 qubits)
```

`ionq_qpu` runs on **real hardware** and consumes credits — opt-in only. The
local GPU is unused for any IonQ target (cloud job). If `IONQ_API_KEY` is unset,
IonQ targets are skipped with a message.
