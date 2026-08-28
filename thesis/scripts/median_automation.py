"""
Runs opin_flow.py's flows N times for a single (CRYPTO_PROFILE, latency_ms)
scenario and computes the across-run median for the size metrics that were
confirmed to have no existing cross-run aggregation (see the size-metric
mean/median inventory that preceded this script): jwt_size_avg_bytes,
gateway_metrics.handshake_bytes.p50_bytes, bytes_by_participant (per
participant, sent/received, including the PKI/CRL entry), total_bytes_exchanged,
and the client certificate's own DER byte size. Decision 12's 5-run median
(thesis/results/v4/DECISIONS.md) covered total-flow LATENCY only, computed
manually/out-of-band -- this is the size-metric equivalent, automated.

Only reports a median + min/max/%-spread for the metrics named above.
Everything else in a run's baseline_metrics.json-shaped dict (per-endpoint
latency, handshake_ms, jwt_sizes_bytes, jwk_sizes, ...) is preserved
per-run under runs/run{NN}_baseline_metrics.json for audit, but is NOT
aggregated here -- out of this script's scope.

Usage:
  CRYPTO_PROFILE=classic|pqc|hybrid python median_automation.py <latency_ms> \
      [--runs N] [--experiment-number N] [--results-version vN]

Assumes the backend stack (auth/mtls/mongo_seed/mockapi) is ALREADY running
under the matching CRYPTO_PROFILE -- this script only drives the client
side, exactly like opin_flow.py itself.
"""
import argparse
import json
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import opin_flow as of
import baseline_automation as ba

BASE_DIR = of.BASE_DIR

NAMED_SCALAR_METRICS = {
    "jwt_size_avg_bytes": lambda m: m["jwt_size_avg_bytes"],
    "total_bytes_exchanged": lambda m: m["total_bytes_exchanged"],
    "client_cert_der_bytes": lambda m: m["client_cert_der_bytes"],
    "handshake_bytes_p50_bytes": lambda m: m["gateway_metrics"]["handshake_bytes"]["p50_bytes"],
}


def run_once(crypto_profile: str, latency_ms: int) -> dict:
    run_start = datetime.now(timezone.utc)
    insurance_calls = of.run_insurance_flow(crypto_profile)
    person_calls = of.run_person_flow(crypto_profile)
    run_end = datetime.now(timezone.utc)
    calls = insurance_calls + person_calls
    gateway_entries = ba.collect_gateway_metrics(run_start, run_end)
    cert_bytes = of.client_cert_der_bytes(crypto_profile)
    metrics = ba.compute_metrics(
        calls, gateway_entries, latency_scenario_ms=latency_ms,
        client_cert_bytes=cert_bytes,
    )
    metrics["client_cert_der_bytes"] = cert_bytes
    return metrics


def median_of(values):
    clean = [v for v in values if v is not None]
    return round(statistics.median(clean), 2) if clean else None


def variation_pct(values):
    clean = [v for v in values if v is not None]
    if not clean or min(clean) == 0:
        return 0.0
    return round((max(clean) - min(clean)) / min(clean) * 100, 2)


def summarize(runs: list[dict]) -> dict:
    n = len(runs)
    scalars = {}
    for name, getter in NAMED_SCALAR_METRICS.items():
        values = [getter(r) for r in runs]
        scalars[name] = {
            "median": median_of(values),
            "min": min(v for v in values if v is not None),
            "max": max(v for v in values if v is not None),
            "variation_pct": variation_pct(values),
            "values": values,
        }

    participants = set()
    for r in runs:
        participants.update(r["bytes_by_participant"].keys())
    bytes_by_participant = {}
    for p in sorted(participants):
        entry = {}
        for leg in ("sent_bytes", "received_bytes"):
            values = [r["bytes_by_participant"].get(p, {}).get(leg) for r in runs]
            entry[leg] = {
                "median": median_of(values),
                "min": min(v for v in values if v is not None),
                "max": max(v for v in values if v is not None),
                "variation_pct": variation_pct(values),
                "values": values,
            }
        bytes_by_participant[p] = entry

    return {
        "run_count": n,
        "scalars": scalars,
        "bytes_by_participant": bytes_by_participant,
    }


def write_median_report(summary: dict, crypto_profile: str, latency_ms: int, path: Path):
    lines = []
    lines.append(f"# Median Report ({crypto_profile}, {latency_ms}ms, {summary['run_count']} runs)")
    lines.append("")
    lines.append(f"Generated at: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    lines.append(
        "Median, min, max and %-spread (`(max-min)/min * 100`) across the "
        f"{summary['run_count']} runs for the size metrics named in scope "
        "(see thesis/results/v5/DECISIONS.md). Every other field in a "
        "run's baseline_metrics.json is preserved per-run under `runs/` "
        "but not aggregated here."
    )
    lines.append("")
    lines.append("## Scalar metrics")
    lines.append("")
    lines.append("| Metric | Median | Min | Max | Spread |")
    lines.append("|---|---|---|---|---|")
    for name, s in summary["scalars"].items():
        lines.append(f"| `{name}` | {s['median']} | {s['min']} | {s['max']} | {s['variation_pct']}% |")
    lines.append("")
    lines.append("## bytes_by_participant")
    lines.append("")
    lines.append("| Participant | Leg | Median | Min | Max | Spread |")
    lines.append("|---|---|---|---|---|---|")
    for p, entry in summary["bytes_by_participant"].items():
        for leg, s in entry.items():
            lines.append(f"| {p} | {leg} | {s['median']} | {s['min']} | {s['max']} | {s['variation_pct']}% |")
    lines.append("")

    flagged = [
        name for name, s in summary["scalars"].items() if s["variation_pct"] > 5.0
    ] + [
        f"{p}.{leg}" for p, entry in summary["bytes_by_participant"].items()
        for leg, s in entry.items() if s["variation_pct"] > 5.0
    ]
    lines.append("## Flagged (>5% min/max spread)")
    lines.append("")
    lines.append(", ".join(flagged) if flagged else "None -- every metric stayed within 5% across all runs.")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("latency_ms", type=int, choices=of.ALLOWED_LATENCY_MS)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--experiment-number", default=os.environ.get("EXPERIMENT_NUMBER", "1"))
    parser.add_argument("--results-version", default=os.environ.get("RESULTS_VERSION", "v5"))
    args = parser.parse_args()

    crypto_profile = os.environ.get("CRYPTO_PROFILE", "classic")
    print(
        f"CRYPTO_PROFILE={crypto_profile}  latency={args.latency_ms}ms  runs={args.runs}  "
        f"RESULTS_VERSION={args.results_version}  EXPERIMENT_NUMBER={args.experiment_number}"
    )

    results_root = BASE_DIR / "thesis" / "results" / args.results_version
    experiment_dir = None
    for candidate in results_root.glob(f"experiment{args.experiment_number}*"):
        experiment_dir = candidate
        break
    if experiment_dir is None:
        raise SystemExit(
            f"No {results_root}/experiment{args.experiment_number}* folder found -- create it first."
        )
    output_dir = experiment_dir / f"{args.latency_ms}ms"
    runs_dir = output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    of.set_latency(args.latency_ms)

    runs = []
    for i in range(1, args.runs + 1):
        print(f"\n=== Run {i}/{args.runs} ===")
        metrics = run_once(crypto_profile, args.latency_ms)
        runs.append(metrics)
        (runs_dir / f"run{i:02d}_baseline_metrics.json").write_text(
            json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(
            f"  jwt_size_avg_bytes={metrics['jwt_size_avg_bytes']}  "
            f"total_bytes_exchanged={metrics['total_bytes_exchanged']}  "
            f"handshake_bytes.p50={metrics['gateway_metrics']['handshake_bytes']['p50_bytes']}  "
            f"client_cert_der_bytes={metrics['client_cert_der_bytes']}"
        )

    summary = summarize(runs)
    (output_dir / "median_metrics.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_median_report(summary, crypto_profile, args.latency_ms, output_dir / "MEDIAN_REPORT.md")

    print(f"\nWrote {output_dir / 'median_metrics.json'}")
    print(f"Wrote {output_dir / 'MEDIAN_REPORT.md'}")
    print(f"Wrote {args.runs} raw run captures under {runs_dir}")

    print("\n=== Summary ===")
    for name, s in summary["scalars"].items():
        print(f"  {name}: median={s['median']}  min={s['min']}  max={s['max']}  spread={s['variation_pct']}%")
    for p, entry in summary["bytes_by_participant"].items():
        for leg, s in entry.items():
            print(f"  bytes_by_participant.{p}.{leg}: median={s['median']}  min={s['min']}  max={s['max']}  spread={s['variation_pct']}%")


if __name__ == "__main__":
    main()
