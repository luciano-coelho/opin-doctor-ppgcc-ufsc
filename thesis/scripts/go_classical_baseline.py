"""
Measures handshake_bytes for the "Go-clássico" auxiliary baseline (thesis/
results/v6/Level 1/DECISIONS.md): the same Go TLS client tls_kem_proxy/
go_handshake_probe use, configured with classical-only CurvePreferences,
presenting the real profile client certificate, over the gateway's
matls-api.local SNI carve-out (the only path that accepts classical curves
while CRYPTO_PROFILE=pqc/hybrid -- see mock_mtls/main.go's
GetConfigForClient).

This is NOT a remeasurement of JWT size, certificate size, or any other
size metric -- those don't depend on which TLS client negotiated the
connection, only on the CRYPTO_PROFILE's own certs/signing logic, already
correctly captured by median_automation.py. This script exists solely to
get a same-client-implementation reference point for handshake_bytes, so
the ML-KEM delta can be computed Go-vs-Go instead of Go-vs-Python (which
Decision 1 in this directory's DECISIONS.md found to be invalid: the
client TLS stack itself, not the KEM group, dominated that comparison).

Usage:
  python go_classical_baseline.py <latency_ms> --profile pqc|hybrid \
      [--runs N] [--experiment-number N] [--results-version vN/subpath]

Assumes the backend stack is already running under the matching
CRYPTO_PROFILE (mirrors median_automation.py's own assumption).
"""
import argparse
import json
import os
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import opin_flow as of
import baseline_automation as ba

BASE_DIR = of.BASE_DIR
PROBE_SRC_DIR = BASE_DIR / "thesis" / "scripts" / "go_handshake_probe"


def run_once(profile: str) -> dict:
    crt_path, key_path = of.get_client_cert_paths(profile)
    run_start = datetime.now(timezone.utc)
    result = subprocess.run(
        [
            "docker", "run", "--rm",
            "--network", "insurance-server-lambdas_default",
            "-v", f"{PROBE_SRC_DIR}:/src",
            "-v", f"{of.CERTS_DIR}:/certs:ro",
            "-w", "/src",
            of.TLS_KEM_PROXY_GO_IMAGE,  # pinned by digest, not the floating tag
            "go", "run", ".",
            "-target", "mtls:443",
            "-sni", "matls-api.local",
            "-host", "auth.local",
            "-curve", "classical",
            "-cert", f"/certs/{Path(crt_path).name}",
            "-key", f"/certs/{Path(key_path).name}",
        ],
        capture_output=True, text=True, timeout=60,
    )
    run_end = datetime.now(timezone.utc)
    if result.returncode != 0:
        raise RuntimeError(f"go_handshake_probe failed: {result.stdout}\n{result.stderr}")

    gateway_entries = ba.collect_gateway_metrics(run_start, run_end)
    samples = ba.dedupe_handshake_samples_by_connection(gateway_entries, "mtlsHandshakeBytes")
    curve_samples = [e.get("cipherSuite") for e in gateway_entries]
    if len(samples) != 1:
        raise RuntimeError(
            f"expected exactly 1 handshake sample in this run's window, got {len(samples)}: {samples} "
            f"-- another process may have hit the gateway during this run's window"
        )
    return {"mtls_handshake_bytes": samples[0], "probe_stdout": result.stdout.strip(),
            "gateway_entries_seen": len(gateway_entries)}


def median_of(values):
    return round(statistics.median(values), 2)


def variation_pct(values):
    if min(values) == 0:
        return 0.0
    return round((max(values) - min(values)) / min(values) * 100, 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("latency_ms", type=int, choices=of.ALLOWED_LATENCY_MS)
    parser.add_argument("--profile", required=True, choices=["pqc", "hybrid"])
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--experiment-number", default=os.environ.get("EXPERIMENT_NUMBER", "1"))
    parser.add_argument("--results-version", default=os.environ.get("RESULTS_VERSION", "v6/Level 1"))
    args = parser.parse_args()

    print(f"Go-clássico baseline: profile={args.profile}  latency={args.latency_ms}ms  runs={args.runs}")

    results_root = BASE_DIR / "thesis" / "results" / args.results_version
    experiment_dir = None
    for candidate in results_root.glob(f"experiment{args.experiment_number}*"):
        experiment_dir = candidate
        break
    if experiment_dir is None:
        raise SystemExit(f"No {results_root}/experiment{args.experiment_number}* folder found -- create it first.")
    output_dir = experiment_dir / "go-classical-baseline" / f"{args.latency_ms}ms"
    runs_dir = output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    of.set_latency(args.latency_ms)

    values = []
    for i in range(1, args.runs + 1):
        print(f"\n=== Run {i}/{args.runs} ===")
        r = run_once(args.profile)
        values.append(r["mtls_handshake_bytes"])
        (runs_dir / f"run{i:02d}.json").write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  mtls_handshake_bytes={r['mtls_handshake_bytes']}")

    summary = {
        "profile": args.profile,
        "latency_scenario_ms": args.latency_ms,
        "run_count": len(values),
        "mtls_handshake_bytes": {
            "median": median_of(values), "min": min(values), "max": max(values),
            "variation_pct": variation_pct(values), "values": values,
        },
    }
    (output_dir / "median_metrics.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {output_dir / 'median_metrics.json'}")
    print(f"median mtls_handshake_bytes = {summary['mtls_handshake_bytes']['median']}  "
          f"spread = {summary['mtls_handshake_bytes']['variation_pct']}%")


if __name__ == "__main__":
    main()
