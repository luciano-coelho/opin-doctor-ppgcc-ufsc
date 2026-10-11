#!/usr/bin/env python3
"""Pool all samples (all rounds, all times of day) from
aws-region-discovery-raw/latency_samples.json, compute median/min/max per
region, and pick -- for each v1-v7 simulated-latency target (14/30/140/225/
320ms) -- the candidate region whose measured median RTT is closest to it.

Output: aws-region-discovery-raw/region_selection.json, plus two Markdown
tables printed to stdout (all regions measured; regions selected per
scenario) -- paste both into README.md and DECISIONS.md so the choice stays
transparent and auditable.

A region is only assigned to one target (closest match wins, in ascending
target order); if a target has no candidate region left (either none
responded, or all closer ones were already claimed by an earlier target),
it is reported as NOT REACHABLE -- expanding the candidate region list is a
policy change and requires explicit approval, not something this script
does on its own.
"""
import json
import statistics
from pathlib import Path

TARGETS_MS = [14, 30, 140, 225, 320]
RESULTS_DIR = Path(__file__).resolve().parent.parent / "aws-region-discovery-raw"


def main():
    data = json.loads((RESULTS_DIR / "latency_samples.json").read_text())

    pooled = {}
    for rd in data["rounds"]:
        for region, samples in rd["samples"].items():
            pooled.setdefault(region, []).extend(samples)

    stats = {}
    for region, samples in pooled.items():
        if not samples:
            stats[region] = None
            continue
        stats[region] = {
            "median_ms": statistics.median(samples),
            "min_ms": min(samples),
            "max_ms": max(samples),
            "n_samples": len(samples),
        }

    selection = {}
    used = set()
    for target in TARGETS_MS:
        candidates = sorted(
            (r for r, s in stats.items() if s is not None and r not in used),
            key=lambda r: abs(stats[r]["median_ms"] - target),
        )
        chosen = candidates[0] if candidates else None
        if chosen is not None:
            used.add(chosen)
        selection[target] = chosen

    out = {"all_regions_measured": stats, "selection_by_target_ms": selection}
    (RESULTS_DIR / "region_selection.json").write_text(json.dumps(out, indent=2))

    print("## All regions measured (sa-east-1 origin, pooled across all rounds)\n")
    print("| Region | Median (ms) | Min (ms) | Max (ms) | Samples |")
    print("|---|---|---|---|---|")
    for region in sorted(stats):
        s = stats[region]
        if s is None:
            print(f"| {region} | - | - | - | 0 (no response) |")
        else:
            print(
                f"| {region} | {s['median_ms']:.2f} | {s['min_ms']:.2f} | "
                f"{s['max_ms']:.2f} | {s['n_samples']} |"
            )

    print("\n## Selected regions per scenario\n")
    print("| Target (ms) | Region | Median RTT (ms) | Delta |")
    print("|---|---|---|---|")
    unreachable = []
    for target, region in selection.items():
        if region is None:
            print(f"| {target} | - | - | **NOT REACHABLE** with current candidate regions |")
            unreachable.append(target)
            continue
        s = stats[region]
        print(f"| {target} | {region} | {s['median_ms']:.2f} | {s['median_ms'] - target:+.2f} |")

    print(f"\nWrote {RESULTS_DIR / 'region_selection.json'}")

    if unreachable:
        print(
            f"\nWARNING: no candidate region available for target(s) {unreachable}ms. "
            f"Reaching them would require widening the IAM policy's region list "
            f"(Decision 4 in DECISIONS.md) -- that is an explicit decision for the "
            f"author, not something to do automatically.",
        )


if __name__ == "__main__":
    main()
