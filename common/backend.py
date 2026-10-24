"""Backend selection: local Aer (CPU/GPU) or IonQ cloud, one interface.

Targets
-------
- ``cpu``        : local Aer statevector on CPU.
- ``gpu``        : local Aer statevector on GPU (auto-falls back to CPU if no
                   CUDA Aer build is present).
- ``ionq_sim``   : IonQ **cloud** ideal simulator (needs IONQ_API_KEY).
- ``ionq_noise`` : IonQ cloud simulator with a hardware noise model
                   (default ``aria-1``).
- ``ionq_qpu``   : IonQ **real hardware** (consumes credits; opt-in).

Why both?  Local GPU shows wall-clock acceleration on *our* 4090s; the IonQ
cloud shows the same circuit running on a real quantum vendor and is one line
from real hardware.  They are mutually exclusive per run: an IonQ job does not
touch the local GPU.

Qubit caps (statevector = 16 bytes x 2**n):
- IonQ ideal cloud simulator: recommended <= 29; we use a safe default of 25.
- One RTX 4090 (24 GB): ~30 qubits; four pooled (cuStateVec): ~32.

Credentials: read from the ``IONQ_API_KEY`` environment variable, which is
filled from the git-ignored ``.env`` at the repo root if not already set (see
``.env.example``). Never hard-code a token or commit / log one.
"""
from __future__ import annotations

import os
from pathlib import Path


def load_env(path: Path = Path(__file__).resolve().parent.parent / ".env") -> None:
    """Load KEY=VALUE lines from .env into os.environ (existing vars win)."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip("'\""))


load_env()

# ---- qubit caps -----------------------------------------------------------
IONQ_SIM_SAFE = 25     # default ceiling we enforce for cloud jobs
IONQ_SIM_HARD = 29     # IonQ ideal simulator documented maximum
GPU_SINGLE = 30        # one 24 GB 4090
GPU_POOLED = 32        # four 4090 pooled via cuStateVec

_IONQ_TARGETS = {"ionq_sim", "ionq_noise", "ionq_qpu"}


def pick_device(verbose: bool = True) -> str:
    """Return 'GPU' if an Aer GPU simulator is available, else 'CPU'."""
    try:
        from qiskit_aer import AerSimulator
        if "GPU" in AerSimulator().available_devices():
            if verbose:
                print("[backend] Aer GPU detected -> device='GPU'")
            return "GPU"
    except Exception as exc:  # qiskit-aer missing, or no GPU build
        if verbose:
            print(f"[backend] GPU probe failed ({type(exc).__name__}) -> CPU")
    if verbose:
        print("[backend] no Aer GPU -> device='CPU'")
    return "CPU"


def check_qubits(target: str, n_qubits: int) -> None:
    """Raise if n_qubits exceeds the cap for the chosen target."""
    if target in _IONQ_TARGETS:
        if n_qubits > IONQ_SIM_HARD:
            raise ValueError(
                f"{n_qubits} qubits exceeds IonQ cloud simulator max "
                f"({IONQ_SIM_HARD}). Use <= {IONQ_SIM_SAFE}."
            )
        if n_qubits > IONQ_SIM_SAFE:
            print(f"[backend] WARNING: {n_qubits} qubits > safe cap "
                  f"{IONQ_SIM_SAFE} (hard max {IONQ_SIM_HARD}); cloud job may "
                  f"be slow/queued.")
    elif target == "gpu" and n_qubits > GPU_POOLED:
        need_gb = 16 * (2 ** n_qubits) / (1024 ** 3)
        raise ValueError(
            f"{n_qubits} qubits needs {need_gb:.0f} GB statevector; "
            f"exceeds pooled 4x4090 (96 GB). Max {GPU_POOLED} qubits."
        )


class _TranspilingSamplerV2:
    """SamplerV2 wrapper that transpiles each pub to the backend first.

    Needed because neither the Aer-native SamplerV2 nor BackendSamplerV2
    transpiles composite instructions (e.g. the IQAE Grover operator "Q"),
    raising 'unknown instruction: Q'. We transpile (optimization_level=0) so
    the operator is decomposed to the backend basis before running. Works for
    both local Aer and IonQ cloud backends.
    """

    def __init__(self, backend, shots: int, opt_level: int = 0):
        from qiskit.primitives import BackendSamplerV2
        self._be = backend
        self._opt = opt_level
        self._inner = BackendSamplerV2(backend=backend,
                                       options={"default_shots": shots})

    def _tp(self, circ):
        from qiskit import transpile
        return transpile(circ, self._be, optimization_level=self._opt)

    def run(self, pubs, *, shots=None):
        tpubs = []
        for pub in pubs:
            if isinstance(pub, (tuple, list)):
                tpubs.append((self._tp(pub[0]),) + tuple(pub[1:]))
            else:
                tpubs.append(self._tp(pub))
        return self._inner.run(tpubs, shots=shots) if shots is not None \
            else self._inner.run(tpubs)


def _ionq_backend(target: str, noise_model: str | None):
    """Build an IonQ cloud backend (BackendV2). Needs IONQ_API_KEY."""
    token = os.environ.get("IONQ_API_KEY")
    if not token:
        raise RuntimeError(
            "IonQ target requires the IONQ_API_KEY environment variable "
            "(get a token at cloud.ionq.com; never commit it)."
        )
    from qiskit_ionq import IonQProvider
    provider = IonQProvider(token)
    if target == "ionq_qpu":
        backend = provider.get_backend("ionq_qpu")
    else:
        backend = provider.get_backend("ionq_simulator")
        if target == "ionq_noise":
            backend.set_options(noise_model=noise_model or "aria-1")
    return backend


def get_backend(target: str = "cpu", *, noise_model: str | None = None,
                seed: int | None = None, verbose: bool = True):
    """Return (backend, label) where backend exposes ``.run(circ, shots=...)``.

    Use this for raw circuit execution (counts), e.g. the scaling benchmark.
    """
    target = target.lower()
    if target in _IONQ_TARGETS:
        backend = _ionq_backend(target, noise_model)
        label = target if target != "ionq_noise" else \
            f"ionq_noise({noise_model or 'aria-1'})"
        if verbose:
            print(f"[backend] IonQ cloud -> {label} (local GPU unused)")
        return backend, label
    # local Aer
    from qiskit_aer import AerSimulator
    device = "GPU" if target == "gpu" else "CPU"
    if device == "GPU" and pick_device(verbose=False) != "GPU":
        if verbose:
            print("[backend] gpu requested but none present -> CPU fallback")
        device = "CPU"
    opts = {"device": device}
    if seed is not None:
        opts["seed_simulator"] = seed
    backend = AerSimulator(**opts)
    label = f"aer-{device}"
    if verbose:
        print(f"[backend] local -> {label}")
    return backend, label


def make_sampler(target: str = "cpu", *, shots: int = 4096,
                 seed: int | None = None, noise_model: str | None = None,
                 verbose: bool = True):
    """Return (SamplerV2-compatible sampler, label) for qiskit-algorithms.

    Used by demo B (IQAE). IonQ targets are wrapped with BackendSamplerV2 so
    each sampler call becomes one cloud job (keep circuit/eval counts small).
    """
    target = target.lower()
    if target in _IONQ_TARGETS:
        backend, label = get_backend(target, noise_model=noise_model,
                                     verbose=verbose)
        return _TranspilingSamplerV2(backend, shots), label
    # local Aer, wrapped in BackendSamplerV2 so arbitrary gates (e.g. the IQAE
    # Grover operator "Q") are TRANSPILED to Aer's basis before simulation.
    # The aer-native SamplerV2 does not transpile and raises
    # "unknown instruction: Q". Seed is set at construction (seed_simulator in
    # run options collides with the one qiskit-algorithms passes).
    try:
        from qiskit_aer import AerSimulator
        from qiskit.primitives import BackendSamplerV2
        device = "GPU" if target == "gpu" else "CPU"
        if device == "GPU" and pick_device(verbose=False) != "GPU":
            device = "CPU"
        be_opts = {"device": device}
        if seed is not None:
            be_opts["seed_simulator"] = seed
        backend = AerSimulator(**be_opts)
        if verbose:
            print(f"[backend] sampler -> aer-{device} (transpiling)")
        return _TranspilingSamplerV2(backend, shots), f"aer-{device}"
    except Exception:
        from qiskit.primitives import StatevectorSampler
        if verbose:
            print("[backend] sampler -> StatevectorSampler (exact fallback)")
        return StatevectorSampler(seed=seed), "statevector(exact)"


# ---- backward-compat shim (older demo code) -------------------------------
def aer_sampler(shots: int = 4096, seed: int | None = None):
    """Deprecated: use make_sampler('gpu'|'cpu', ...). Kept for old imports."""
    dev = pick_device(verbose=False)
    s, label = make_sampler("gpu" if dev == "GPU" else "cpu",
                            shots=shots, seed=seed, verbose=False)
    return s, label
