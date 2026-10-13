#!/usr/bin/env python3
"""Decision 55/58: derives `v8/size/` entirely from `v8/latency/`'s own
raw run records -- never a separate collection batch, never hand-edited.
Reusable, reproducible: re-run any time after a pull and it recomputes
`median_metrics.json`/`report.md` fresh from whatever runs exist so far
(including a partial campaign -- it does not require all 720 to be
present).

Official size (Decision 53): every run across ALL FOUR of `sa-east-1`'s
scenarios (L0, L123, L219, L325), pooled -- sizes are deterministic
per-profile (v7's own Decisions 10-12 found 0% spread), so pooling
across scenarios is just more samples of the same value, not a mixing
of unrelated things.

Complementary verification (Decision 53): `us-east-1` and
`ap-northeast-1` each get their OWN `v8/size/.../{server}/` report,
built from that server's `L0` runs only (not its other scenario) --
deliberately scoped, so the cross-machine comparison stays clean.

Retried executions (Decision 53/58): a run whose JSON has
`"retried": true` is EXCLUDED from the primary (clean) statistics and
reported separately, flagged -- never silently pooled in, never
discarded outright.

Variation reported, per Decision 58: across executions (min/max/stdev
within one scenario) AND across latency levels (median per scenario,
compared against each other) -- sizes are expected to be latency-
independent; this is where that expectation actually gets checked with
real data, not assumed.

Usage:
  compute_v8_size_report.py <v8-root> <profile>
    e.g. compute_v8_size_report.py thesis/results/v8 classic
"""
import json
import statistics
import sys
from pathlib import Path

PROFILE_TO_EXPERIMENT_DIR = {
    "classic": "experiment1 - Classic",
    "pqc": "experiment2 - PQC",
    "hybrid": "experiment3 - Hybrid",
}
SA_EAST_1_SCENARIOS = ["L0", "L123", "L219", "L325"]
BYTE_FIELDS = [
    "total_bytes_exchanged", "jwt_size_avg_bytes", "jwt_size_max_bytes", "jwt_count",
]


def load_runs(latency_root, experiment_dir, server, scenarios):
    """Loads every runN.json's "result" dict across the given scenarios
    for one server, tagging each with its scenario and retry status."""
    rows = []
    for scenario in scenarios:
        runs_dir = latency_root / experiment_dir / server / scenario / "runs"
        if not runs_dir.is_dir():
            continue
        for run_file in sorted(runs_dir.glob("run*.json")):
            if run_file.name.endswith(".calls.jsonl"):
                continue
            data = json.loads(run_file.read_text())
            result = data.get("result") or {}
            rows.append({
                "scenario": scenario,
                "run_file": str(run_file),
                "retried": bool(data.get("retried", False)),
                "result": result,
            })
    return rows


def pooled_stats(rows, field_path):
    """field_path: dotted path into each row's "result" dict, e.g.
    "total_bytes_exchanged" or "gateway_metrics.handshake_bytes.mean_bytes"."""
    values = []
    for row in rows:
        node = row["result"]
        ok = True
        for part in field_path.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                ok = False
                break
        if ok and isinstance(node, (int, float)):
            values.append(node)
    if not values:
        return None
    stats = {
        "n": len(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }
    if len(values) > 1:
        stats["stdev"] = statistics.stdev(values)
    return stats


def build_report(server_label, rows, byte_fields):
    clean = [r for r in rows if not r["retried"]]
    retried = [r for r in rows if r["retried"]]

    by_scenario = {}
    for scenario in sorted({r["scenario"] for r in rows}):
        scenario_rows = [r for r in clean if r["scenario"] == scenario]
        by_scenario[scenario] = {
            field: pooled_stats(scenario_rows, field) for field in byte_fields
        }

    pooled_all_scenarios = {field: pooled_stats(clean, field) for field in byte_fields}

    return {
        "server": server_label,
        "n_clean_runs": len(clean),
        "n_retried_runs": len(retried),
        "retried_run_files": [r["run_file"] for r in retried],
        "pooled_across_all_scenarios": pooled_all_scenarios,
        "by_scenario": by_scenario,
    }


def render_markdown(report):
    lines = [f"# Size report -- {report['server']}", ""]
    lines.append(f"Clean runs pooled: {report['n_clean_runs']}. "
                 f"Retried runs excluded from stats, flagged separately: {report['n_retried_runs']}.")
    if report["n_retried_runs"]:
        lines.append("")
        lines.append("## Retried executions (excluded above, listed here)")
        for f in report["retried_run_files"]:
            lines.append(f"- `{f}`")
    lines.append("")
    lines.append("## Pooled across all scenarios (this server)")
    for field, stats in report["pooled_across_all_scenarios"].items():
        if stats:
            lines.append(f"- `{field}`: n={stats['n']} median={stats['median']} "
                          f"min={stats['min']} max={stats['max']} "
                          f"stdev={stats.get('stdev', 'n/a')}")
    lines.append("")
    lines.append("## By scenario (variation across latency levels)")
    for scenario, fields in report["by_scenario"].items():
        lines.append(f"### {scenario}")
        for field, stats in fields.items():
            if stats:
                lines.append(f"- `{field}`: n={stats['n']} median={stats['median']} "
                              f"min={stats['min']} max={stats['max']}")
    lines.append("")
    lines.append(
        "Sizes are expected to be latency-independent (deterministic per "
        "profile, v7 Decisions 10-12). Any scenario whose median differs "
        "from the others by more than ordinary run-to-run noise is a "
        "finding to investigate, not something this report resolves on "
        "its own."
    )
    return "\n".join(lines) + "\n"


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: compute_v8_size_report.py <v8-root> <profile>")
    v8_root = Path(sys.argv[1])
    profile = sys.argv[2]
    if profile not in PROFILE_TO_EXPERIMENT_DIR:
        sys.exit(f"profile must be one of {list(PROFILE_TO_EXPERIMENT_DIR)}")
    experiment_dir = PROFILE_TO_EXPERIMENT_DIR[profile]
    latency_root = v8_root / "latency"
    size_root = v8_root / "size" / experiment_dir

    targets = [
        ("sa-east-1", SA_EAST_1_SCENARIOS, "official"),
        ("us-east-1", ["L0"], "complementary"),
        ("ap-northeast-1", ["L0"], "complementary"),
    ]

    for server, scenarios, role in targets:
        rows = load_runs(latency_root, experiment_dir, server, scenarios)
        if not rows:
            print(f"[{server}] no runs found yet -- skipping (not an error, campaign may be partial).")
            continue
        report = build_report(f"{server} ({role})", rows, BYTE_FIELDS)
        out_dir = size_root / server
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "median_metrics.json").write_text(json.dumps(report, indent=2, default=str))
        (out_dir / "report.md").write_text(render_markdown(report))
        print(f"[{server}] wrote {out_dir}/median_metrics.json and report.md "
              f"({report['n_clean_runs']} clean, {report['n_retried_runs']} retried)")


if __name__ == "__main__":
    main()
