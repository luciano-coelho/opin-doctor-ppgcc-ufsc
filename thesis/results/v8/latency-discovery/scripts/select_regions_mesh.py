#!/usr/bin/env python3
"""Analyze the full 10x10 mesh (aws-region-discovery-mesh-raw/latency_mesh_samples.json):

1. Build the median RTT matrix (every directed pair, pooled across rounds).
2. Symmetry check: for every unordered pair {A,B}, compare median(A->B) vs
   median(B->A).
3. Selection, per the criterion agreed before measuring:
   - Tolerance band per target is +-20% (hardcoded below, matching the
     approved values exactly).
   - First, check whether any SINGLE region, used as a fixed origin,
     covers all 5 targets within tolerance (closest-first greedy
     assignment among its 9 outgoing pairs, no destination reused). If one
     or more origins qualify, the one with the lowest total |delta| wins
     -- this keeps the Phase 4 topology unchanged (fixed server, roaming
     client).
   - If no single origin covers all 5, this script does NOT pick a
     per-scenario (client, server) pair on its own -- it stops and reports
     the best mesh-wide candidate per target instead, for the author to
     confirm before Phase 4's topology changes.
   - Every scenario is labeled by its actual measured RTT, with the
     original target in parentheses (e.g. "112ms (target 140ms)").
4. Any target with literally no pair inside its tolerance band anywhere in
   the mesh is reported as such, not forced.
"""
import json
import os
import statistics
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / os.environ.get(
    "MOCKOPIN_RESULTS_DIR", "aws-region-discovery-mesh-raw"
)

# Agreed 2026-10-08: +-20% of each original v1-v7 target.
TOLERANCE = {
    14: (11, 17),
    30: (24, 36),
    140: (112, 168),
    225: (180, 270),
    320: (256, 384),
}


def pooled_stats(samples_by_pair):
    stats = {}
    for pair, samples in samples_by_pair.items():
        if not samples:
            stats[pair] = None
            continue
        stats[pair] = {
            "median_ms": statistics.median(samples),
            "min_ms": min(samples),
            "max_ms": max(samples),
            "n_samples": len(samples),
        }
    return stats


def in_tolerance(median_ms, target):
    lo, hi = TOLERANCE[target]
    return lo <= median_ms <= hi


def greedy_cover(origin, regions, stats):
    """Try to assign each of the 5 targets a distinct destination from
    `origin`, within tolerance, ascending target order. Returns the
    assignment dict (target -> dest) if all 5 succeed, else None."""
    used = set()
    assignment = {}
    for target in sorted(TOLERANCE):
        candidates = []
        for dest in regions:
            if dest == origin or dest in used:
                continue
            s = stats.get(f"{origin}->{dest}")
            if s is None:
                continue
            if in_tolerance(s["median_ms"], target):
                candidates.append((abs(s["median_ms"] - target), dest, s["median_ms"]))
        if not candidates:
            return None
        candidates.sort()
        _, dest, median_ms = candidates[0]
        used.add(dest)
        assignment[target] = {"region": dest, "median_ms": median_ms}
    return assignment


def main():
    data = json.loads((RESULTS_DIR / "latency_mesh_samples.json").read_text())
    regions = data["regions"]

    pooled = {}
    for rd in data["rounds"]:
        for pair, samples in rd["pairs"].items():
            pooled.setdefault(pair, []).extend(samples)
    stats = pooled_stats(pooled)

    # ---- 1. Matrix ----
    print("## 10x10 median RTT matrix (ms, pooled across all rounds)\n")
    header = "| origin \\ dest | " + " | ".join(regions) + " |"
    print(header)
    print("|" + "---|" * (len(regions) + 1))
    for origin in regions:
        row = [origin]
        for dest in regions:
            if origin == dest:
                row.append("-")
                continue
            s = stats.get(f"{origin}->{dest}")
            row.append(f"{s['median_ms']:.0f}" if s else "N/A")
        print("| " + " | ".join(row) + " |")

    # ---- 2. Symmetry check ----
    print("\n## Symmetry check (A->B vs B->A)\n")
    print("| Pair | A->B median | B->A median | Delta |")
    print("|---|---|---|---|")
    seen = set()
    max_asym = 0.0
    for a in regions:
        for b in regions:
            if a >= b:
                continue
            s_ab = stats.get(f"{a}->{b}")
            s_ba = stats.get(f"{b}->{a}")
            if s_ab is None or s_ba is None:
                ab_disp = "N/A" if not s_ab else f"{s_ab['median_ms']:.0f}"
                ba_disp = "N/A" if not s_ba else f"{s_ba['median_ms']:.0f}"
                print(f"| {a} <-> {b} | {ab_disp} | {ba_disp} | missing data |")
                continue
            delta = s_ab["median_ms"] - s_ba["median_ms"]
            max_asym = max(max_asym, abs(delta))
            print(f"| {a} <-> {b} | {s_ab['median_ms']:.0f} | {s_ba['median_ms']:.0f} | {delta:+.1f} |")
    print(f"\nLargest |A->B - B->A| observed: {max_asym:.1f}ms")

    # ---- 3. Selection ----
    print("\n## Selection\n")
    qualifying = []
    for origin in regions:
        assignment = greedy_cover(origin, regions, stats)
        if assignment is not None:
            total_delta = sum(abs(v["median_ms"] - t) for t, v in assignment.items())
            qualifying.append((total_delta, origin, assignment))

    if qualifying:
        qualifying.sort(key=lambda x: x[0])
        total_delta, origin, assignment = qualifying[0]
        print(f"**Single origin covers all 5 targets within tolerance: `{origin}`** "
              f"(total |delta| = {total_delta:.1f}ms across 5 scenarios)")
        if len(qualifying) > 1:
            others = ", ".join(f"{o} ({d:.1f}ms)" for d, o, _ in qualifying[1:])
            print(f"(Other qualifying origins, not selected: {others})")
        print("\n| Target (nominal) | Label (measured) | Region | Delta |")
        print("|---|---|---|---|")
        for target in sorted(TOLERANCE):
            v = assignment[target]
            print(f"| {target}ms | {v['median_ms']:.0f}ms (target {target}ms) | {v['region']} | "
                  f"{v['median_ms'] - target:+.1f} |")
        print(f"\nPhase 4 topology unchanged: fixed server `{origin}`, client relocated per scenario.")
    else:
        print("**No single origin covers all 5 targets within tolerance.** "
              "Per the agreed criterion, this script stops here rather than picking a "
              "per-scenario (client, server) pair automatically -- that changes Phase 4's "
              "topology (Decision 2) and needs explicit author confirmation.\n")
        print("Best mesh-wide candidate per target (any pair, for reference only):\n")
        print("| Target (nominal) | Best pair found | Label (measured) | Delta | In tolerance? |")
        print("|---|---|---|---|---|")
        for target in sorted(TOLERANCE):
            best = None
            for pair, s in stats.items():
                if s is None:
                    continue
                d = abs(s["median_ms"] - target)
                if best is None or d < best[0]:
                    best = (d, pair, s["median_ms"])
            if best is None:
                print(f"| {target}ms | - | - | - | NOT REACHABLE (no data) |")
                continue
            _, pair, median_ms = best
            ok = "yes" if in_tolerance(median_ms, target) else "**no**"
            print(f"| {target}ms | {pair} | {median_ms:.0f}ms (target {target}ms) | "
                  f"{median_ms - target:+.1f} | {ok} |")

    out = {
        "matrix_median_ms": {p: (s["median_ms"] if s else None) for p, s in stats.items()},
        "pair_stats": stats,
        "qualifying_single_origins": [
            {"origin": o, "total_abs_delta_ms": d, "assignment": a} for d, o, a in qualifying
        ],
    }
    out_path = RESULTS_DIR / "region_selection_mesh.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
