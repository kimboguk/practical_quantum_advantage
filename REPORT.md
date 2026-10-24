# Practical Quantum Advantage — a short, honest report

*For a non-specialist reader. Every number below comes from code in this
repository that you can re-run.*

## The question

"Quantum computing" is easy to hype and hard to pin down. The useful question for
a business is narrow: **where, concretely, does a quantum computer do something a
classical computer cannot do well — and where does it not (yet)?**

One caveat up front: you cannot prove a quantum *advantage* by running a quantum
*simulator*, because a simulator is just a classical computer imitating a quantum
one. So these demos do two honest things: show the principle on a small problem
you can check, and show *why the classical approach breaks at large scale*.

We look at four application areas, in decreasing order of how strong the case
is, plus one section on tooling.

---

## 1. Chemistry — the clearest case

Chemical reaction rates depend *exponentially* on energy: a 1 kcal/mol error
changes a predicted rate by ~5×. That accuracy drives catalysts, battery
materials, combustion, and semiconductor processes — a real industrial
bottleneck.

We stretch a nitrogen molecule and compute its energy with methods from crude to
exact. The best *routine* classical method, "CCSD(T)" (chemists call it the gold
standard), is accurate near the normal bond length — then falls apart as the bond
stretches and the electrons become "strongly correlated":

![N₂ dissociation](01_chemistry_N2/figures/dissociation.png)

The blue curve (FCI) is the exact answer in this basis — what an ideal quantum
computer running phase estimation would return. The red curve (the classical
gold standard) tracks it, then peels away, even dropping *below* the exact
energy. That is an **unphysical** result: CCSD(T) is not variational, so it
*can* fall below the exact value, and when it does, the method has broken down.
The largest reproducible error is **108 mEh ≈ 68 kcal/mol** at 2.0 Å. (Beyond
~2.3 Å the CCSD iterations stop converging, so the even larger values there are
not reproducible and are not quoted.)

![CCSD(T) error](01_chemistry_N2/figures/error.png)

**Why it matters:** the exact method (FCI) becomes impossible for large molecules
— its cost explodes exponentially. A fault-tolerant quantum computer runs phase
estimation at polynomial cost per run, but it returns the exact answer only with
probability equal to the squared overlap between a prepared initial state and
the true ground state. So the advantage holds **provided a sufficiently good
initial state can be prepared** — for large strongly-correlated molecules that
is not guaranteed (Lee et al., *Nat. Commun.* 2023). The failure we see on a toy
molecule is the same kind of strong correlation found in real catalysts and
battery cathodes.

**A quantum circuit on today's path (SQD):** we also ran a 20-qubit circuit for
N₂ on the IonQ cloud simulator (with a hardware noise model) and diagonalized
only in the ≤ 6.25% of configurations its samples picked. In the stretched
region it stays within ~4–24 mEh of exact while CCSD(T) breaks down — still
outside chemical accuracy, and on a molecule this small classical methods could
pick an equally good subset.

**Honest limit:** this small case is also handled by specialized classical
methods (DMRG, CASSCF). Systems where *no* classical method works are expected
to need **tens of active orbitals** (e.g. the FeMoco model: 54 orbitals), and
where exactly the crossover lies is debated. The basis set is minimal (STO-3G):
this is a comparison of methods, not agreement with experiment. The value is in
showing the *pattern* and where it leads.

---

## 2. Finance — a real speedup, honestly not enough yet

Banks and insurers compute the probability of rare, large losses (the "tail") to
set regulatory capital, using heavy daily Monte Carlo runs. Quantum Amplitude
Estimation can, in principle, reach a target precision ε with far fewer queries:
**~1/ε** vs classical Monte Carlo's **~1/ε²**.

We estimate a tail probability on a 4-qubit model and count the work each side
needs:

![Quantum vs classical scaling](02_finance_amplitude/figures/scaling.png)

The quantum curve (blue) rises much more slowly than the classical one (orange);
they cross near ε ≈ 0.001. The quadratic speedup is real. (The quantum count
rises in steps, because the algorithm picks its circuit depths from a discrete
schedule.)

**Honest limit — and this is the important part:** "fewer queries" is not "faster."
One quantum query is a deep circuit, and logical operations on error-corrected
hardware are slow. For a realistic derivative-pricing problem, advantage would
require ~4.7k logical qubits executing ~10⁹ T-gates at a **45 MHz logical clock
rate** (Stamatopoulos et al., *Quantum* 2024) — a *required* speed far beyond
projected error-corrected hardware. So the real crossover is pushed to much
smaller ε or much larger problems — and classical Monte Carlo has its own tricks
(importance sampling). This is the honest reason finance is **not** the first
place to expect a quantum payoff.

---

## 3. Optimization (LABS) — a published scaling claim, tested small

Finding binary sequences with low autocorrelation (used in radar and sonar
pulse design) is classically hard. A 2024 study (Shaydulin et al.) reported that
QAOA combined with a Grover-type step ("quantum minimum finding") has the best
known *scaling* of time-to-solution: ~1.21ᴺ vs ~1.34ᴺ for the best classical
heuristic.

We measured the same exponents up to N = 24:

![LABS scaling](05_labs_qaoa/figures/tts_scaling.png)

Our QAOA + minimum finding scales as ~1.32ᴺ and our classical heuristic as
~1.66ᴺ — the same ordering as published, but our quantum exponent is
essentially **tied with the published classical one (1.34ᴺ)**, and fitted
exponents at small N are fragile. QAOA alone (~1.75ᴺ here, 1.46ᴺ published)
does not beat the best heuristic; in the paper it beats a commercial exact
branch-and-bound solver (1.62ᴺ).

**Honest limit:** the minimum-finding step needs fault-tolerant hardware. On
IonQ's noisy simulator the N = 8 LABS circuit (~780 two-qubit gates) gives the
optimum with probability 0.066 — **the same as random guessing**. As a contrast,
the textbook QAOA problem Max-Cut has shallow circuits but a classical
algorithm (Goemans–Williamson) that already guarantees 87.8% of optimum; QAOA
needs depth p = 5 just to match it on a 10-node graph.

---

## 4. Turbulence — a concept, not yet an advantage

Turbulence governs aircraft drag, engine combustion, and reactor mixing, and is
classically intractable to resolve directly at real scale. A quantum computer
stores 2ⁿ grid values in n qubits, raising hope for representing flow fields
beyond classical reach.

We build a turbulence-like 1D field and measure how hard it is to compress
classically (its "bond dimension" χ):

![Compressibility](03_turbulence_mps/figures/compression.png)

A field made by a **short** quantum circuit (quadratic phases, ~120 gates)
resists compression almost as strongly as fully random data. So a short circuit
*can* represent something this classical compression (MPS) cannot.

**Honest limit:** representability is not an application advantage. Evolving the
physics and reading out useful numbers efficiently are unsolved. This is a concept
demo — it shows one necessary ingredient, nothing more.

---

## 5. Tooling — where the GPU and the cloud fit

A practical aside, not a quantum claim. Simulating a quantum computer is a
classical job, and it gets expensive fast: a statevector holds 2ⁿ numbers. We
timed one wide, shallow circuit at growing qubit counts on a CPU, on a GPU, and
on IonQ's cloud simulator:

![Backend scaling](04_scaling/figures/scaling.png)

The GPU is *slower* on tiny circuits (overhead) and crosses over near 22 qubits,
then runs ~11× faster — so GPUs matter only once the statevector is large. The
same circuit also runs unchanged on IonQ's cloud, one step from real hardware.

**Honest limit:** this is classical-simulation engineering, not a quantum
advantage; and cloud timings include network/queue latency, so they show
portability, not speed. Past ~32 qubits, even four pooled GPUs (96 GB) cannot
hold the statevector — which is exactly why large quantum circuits cannot be
checked by classical simulation.

---

## Bottom line

| Area | Verdict |
|---|---|
| **Chemistry** | Strongest. The best routine classical method demonstrably fails in the strongly-correlated region; exact quantum answers need a good initial state. A scaled-down version of a real bottleneck. |
| **Finance** | A genuine quadratic speedup, but not yet sufficient — the honest reason it is not the first priority. |
| **Optimization (LABS)** | A published scaling advantage that needs fault tolerance; our small-N reproduction matches the ordering but not decisively, and noise erases it today. |
| **Turbulence** | A concept. Shows a necessary condition for quantum CFD; the application case is unproven. |
| **Tooling** | Not a quantum advantage. Shows which classical hardware to simulate on, and that the demos run on a real vendor's cloud, not just locally. |

The through-line: **be specific, show the numbers, and state the limits.** That is
how a quantum program earns trust rather than hype.
