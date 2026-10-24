"""Control for Demo E -- Max-Cut QAOA: the textbook QAOA problem, with NO
advantage claim.

Max-Cut (split a graph's nodes in two to cut as many edges as possible) is the
standard first QAOA example, and a useful one: the cost has only 2-qubit ZZ
terms, so circuits are shallow. But classically it is the wrong place to look
for an advantage: Goemans-Williamson (GW, SDP relaxation + random hyperplane
rounding) GUARANTEES an expected cut >= 0.878 x optimum, and simple local
search reaches the optimum on graphs like this almost immediately.

For an Erdos-Renyi graph we report, for p = 1..5:
  QAOA      expected cut / optimum and P(optimal cut), exact statevector,
            parameters optimized per p (warm-started from p-1)
  sampled   the same circuits sampled on a common/backend.py target
            (Aer or IonQ; with --backend ionq_noise the hardware noise model)
and the classical baselines:
  GW        SDP via Burer-Monteiro low-rank optimization + 500 roundings
  local     greedy 1-flip local search from random starts

Contrast with LABS (run.py): there the cost has O(N^3) 4-body terms, there is
no classical approximation guarantee, and a published QAOA scaling claim
exists. Max-Cut is the clean QAOA tutorial; LABS is the advantage candidate.

Run:   python maxcut_control.py                         (N=10, Aer CPU)
       python maxcut_control.py --backend ionq_noise --sample-ps 1,3   (IonQ key in .env)
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import sys
import numpy as np
import networkx as nx
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from common.backend import get_backend, check_qubits   # noqa: E402  (also loads .env)
from run import qaoa_probs                              # noqa: E402

SEED = 7
GW_ALPHA = 0.87856   # Goemans-Williamson approximation guarantee


def cut_values(edges, N):
    """Cut size of every basis state; bit i of the index = qubit i = node i."""
    bits = (np.arange(2 ** N)[:, None] >> np.arange(N)) & 1
    return sum((bits[:, u] != bits[:, v]) for u, v in edges).astype(float)


def qaoa_circuit(N, edges, gammas, betas):
    from qiskit import QuantumCircuit
    qc = QuantumCircuit(N)
    qc.h(range(N))
    for g, b in zip(gammas, betas):
        for u, v in edges:
            # exp(-i g/2 Z_u Z_v) == exp(-i g * (-cut)) up to a global phase,
            # matching the numpy simulator's cost H = -cut
            qc.rzz(g, u, v)
        qc.rx(2 * b, range(N))
    qc.measure_all()
    return qc


def optimize_qaoa(cuts, N, ps):
    """Maximize the exact expected cut for each p, warm-starting from p-1."""
    H = -cuts
    out, prev = {}, None
    for p in ps:
        f = lambda x: -float(qaoa_probs(H, x[:p], x[p:], N) @ cuts)
        if prev is None:
            starts = [np.array([0.8, 0.4]), np.array([0.4, 0.8]), np.array([1.2, 0.3])]
        else:   # stretch the p-1 schedule to p points
            g, b = prev[:len(prev) // 2], prev[len(prev) // 2:]
            t_old, t_new = np.linspace(0, 1, len(g)), np.linspace(0, 1, p)
            starts = [np.concatenate([np.interp(t_new, t_old, g),
                                      np.interp(t_new, t_old, b)])]
        res = min((minimize(f, x0, method="COBYLA", options={"maxiter": 500})
                   for x0 in starts), key=lambda r: r.fun)
        prev = res.x
        out[p] = res.x
    return out


def goemans_williamson(edges, N, rng, n_round=500):
    """SDP value (Burer-Monteiro) and hyperplane-rounding cuts."""
    eu, ev = np.array(edges).T
    r = int(np.ceil(np.sqrt(2 * len(edges)))) + 1

    def neg_sdp(x):
        V = x.reshape(N, r)
        V = V / np.linalg.norm(V, axis=1, keepdims=True)
        return -0.5 * float((1 - (V[eu] * V[ev]).sum(axis=1)).sum())

    best = min((minimize(neg_sdp, rng.normal(size=N * r), method="L-BFGS-B")
                for _ in range(5)), key=lambda res: res.fun)
    V = best.x.reshape(N, r)
    V /= np.linalg.norm(V, axis=1, keepdims=True)
    side = (V @ rng.normal(size=(r, n_round))) > 0          # one column per hyperplane
    cuts = (side[eu] != side[ev]).sum(axis=0)
    return -best.fun, cuts


def local_search_restarts(edges, N, best, rng, trials=50):
    """Random restarts of greedy 1-flip descent until the optimum is hit."""
    nbr = [[] for _ in range(N)]
    for u, v in edges:
        nbr[u].append(v); nbr[v].append(u)
    counts = []
    for _ in range(trials):
        k = 0
        while True:
            k += 1
            x = rng.integers(0, 2, N)
            while True:   # gain of flipping i = same-side nbrs - other-side nbrs
                gain = np.array([sum(x[j] == x[i] for j in nbr[i]) -
                                 sum(x[j] != x[i] for j in nbr[i]) for i in range(N)])
                i = int(np.argmax(gain))
                if gain[i] <= 0:
                    break
                x[i] ^= 1
            if sum(x[u] != x[v] for u, v in edges) == best:
                break
        counts.append(k)
    return counts


def sample(N, edges, params, p, cuts, best, target, shots):
    from qiskit import transpile
    check_qubits(target, N)
    backend, label = get_backend(target, seed=SEED)
    level = 1 if target.startswith("ionq") else 2
    tc = transpile(qaoa_circuit(N, edges, params[:p], params[p:]), backend,
                   optimization_level=level, seed_transpiler=SEED)
    counts = backend.run(tc, shots=shots).result().get_counts()
    idx = np.array([int(k.replace(" ", ""), 2) for k in counts])   # qubit 0 rightmost
    w = np.array(list(counts.values()), dtype=float) / shots
    ops = tc.count_ops()
    return dict(backend=label, depth=tc.depth(),
                two_qubit_gates=int(sum(v for k, v in ops.items()
                                        if k in ("cx", "cz", "rzz", "ecr", "ms", "zz"))),
                ratio_sampled=float(w @ cuts[idx]) / best,
                p_opt_sampled=float(w[cuts[idx] == best].sum()))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--nodes", type=int, default=10)
    ap.add_argument("--edge-prob", type=float, default=0.5)
    ap.add_argument("--max-p", type=int, default=5)
    ap.add_argument("--backend", default="cpu",
                    help="cpu|gpu|ionq_sim|ionq_noise|ionq_qpu|none")
    ap.add_argument("--sample-ps", default=None,
                    help="comma-separated p values to sample (default: all)")
    ap.add_argument("--shots", type=int, default=4000)
    args = ap.parse_args()
    rng = np.random.default_rng(SEED)

    N = args.nodes
    G = nx.erdos_renyi_graph(n=N, p=args.edge_prob, seed=SEED)
    edges = list(G.edges())
    cuts = cut_values(edges, N)
    best = float(cuts.max())
    p_rand = float((cuts == best).mean())
    print(f"graph: {N} nodes, {len(edges)} edges, optimal cut = {best:.0f} "
          f"(random guess: ratio {cuts.mean() / best:.3f}, P(opt) {p_rand:.4f})")

    sdp, gw_cuts = goemans_williamson(edges, N, rng)
    ls = local_search_restarts(edges, N, best, rng)
    classical = dict(gw_sdp_bound_ratio=sdp / best,
                     gw_mean_ratio=float(gw_cuts.mean()) / best,
                     gw_best_ratio=float(gw_cuts.max()) / best,
                     gw_p_opt=float((gw_cuts == best).mean()),
                     local_search_median_restarts=float(np.median(ls)))
    print(f"GW: SDP bound {classical['gw_sdp_bound_ratio']:.3f}, rounding mean "
          f"{classical['gw_mean_ratio']:.3f} (guarantee {GW_ALPHA}), "
          f"P(opt) {classical['gw_p_opt']:.2f}; local search: optimum after "
          f"median {classical['local_search_median_restarts']:.0f} restart(s)")

    ps = list(range(1, args.max_p + 1))
    sample_ps = set(ps) if args.sample_ps is None else \
        {int(x) for x in args.sample_ps.split(",")}
    if args.backend.startswith("ionq") and not os.environ.get("IONQ_API_KEY"):
        print("IonQ sampling skipped: IONQ_API_KEY not set (see .env.example).")
        args.backend = "none"
    if args.backend == "ionq_qpu":
        print("WARNING: ionq_qpu runs on real hardware and consumes credits.")

    rows = []
    for p, x in optimize_qaoa(cuts, N, ps).items():
        probs = qaoa_probs(-cuts, x[:p], x[p:], N)
        row = dict(p=p, ratio_exact=float(probs @ cuts) / best,
                   p_opt_exact=float(probs[cuts == best].sum()))
        if args.backend != "none" and p in sample_ps:
            row.update(sample(N, edges, x, p, cuts, best, args.backend, args.shots))
        rows.append(row)
        s = (f"  sampled on {row['backend']}: ratio {row['ratio_sampled']:.3f}, "
             f"P(opt) {row['p_opt_sampled']:.3f}, 2q gates {row['two_qubit_gates']}"
             if "backend" in row else "")
        print(f"p={p}: ratio {row['ratio_exact']:.3f}, P(opt) {row['p_opt_exact']:.3f}{s}",
              flush=True)

    summary = dict(nodes=N, edges=len(edges), seed=SEED, optimal_cut=best,
                   random_ratio=float(cuts.mean()) / best, random_p_opt=p_rand,
                   gw_guarantee=GW_ALPHA, classical=classical,
                   backend=args.backend, shots=args.shots)
    out = os.path.join(HERE, "results", "maxcut")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, f"maxcut_{args.backend}.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(max(rows, key=len)))   # unsampled p: blank
        w.writeheader(); w.writerows(rows)
    json.dump({"rows": rows, "summary": summary},
              open(os.path.join(out, f"summary_{args.backend}.json"), "w"), indent=2)
    print(f"Saved: results/maxcut/maxcut_{args.backend}.csv, "
          f"results/maxcut/summary_{args.backend}.json")
    plot(rows, summary)


def plot(rows, s):
    from common.plotting import plt, save, BLUE, ORANGE, GREEN, RED, PURPLE
    p = [r["p"] for r in rows]
    fig, ax = plt.subplots()
    ax.plot(p, [r["ratio_exact"] for r in rows], "o-", color=BLUE,
            label="QAOA expected cut (exact)")
    sp = [r for r in rows if "ratio_sampled" in r]
    if sp:
        ax.plot([r["p"] for r in sp], [r["ratio_sampled"] for r in sp], "s--",
                color=PURPLE, label=f"QAOA sampled on {sp[0]['backend']}")
    c = s["classical"]
    ax.axhline(c["gw_mean_ratio"], color=RED, lw=2,
               label=f"Goemans–Williamson (mean of roundings) {c['gw_mean_ratio']:.3f}")
    ax.axhline(s["gw_guarantee"], color=RED, ls=":", label="GW guarantee 0.878")
    ax.axhline(s["random_ratio"], color="gray", ls="--",
               label=f"random guess {s['random_ratio']:.3f}")
    ax.axhline(1.0, color=GREEN, ls="-", alpha=0.5,
               label=f"optimum (local search: ~{c['local_search_median_restarts']:.0f} restart)")
    ax.set_xticks(p)
    ax.set_xlabel("QAOA depth p")
    ax.set_ylabel("expected cut / optimal cut")
    ax.set_title(f"Max-Cut ({s['nodes']} nodes): QAOA vs classical baselines")
    ax.legend(loc="lower right", fontsize=9)
    os.makedirs(os.path.join(HERE, "figures"), exist_ok=True)
    save(fig, os.path.join(HERE, "figures", f"maxcut_{s['backend']}.png"))


if __name__ == "__main__":
    main()
