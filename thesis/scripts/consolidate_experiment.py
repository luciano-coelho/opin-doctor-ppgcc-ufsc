"""
Consolidates a single experiment's six per-scenario baseline_metrics.json
files (thesis/results/{RESULTS_VERSION}/experiment{N} - .../{ms}ms/) into:
  - consolidated.json: the six scenarios' summary metrics side by side, for
    programmatic reuse (e.g. plotting later).
  - EXPERIMENT{N}_REPORT.md: the human-readable comparative report (total
    OPINsize, TLS-handshake vs. OPIN-processing split, per-endpoint
    P50/P95/P99, bytes per participant -- all six scenarios side by side).

Same output shape as thesis/results/v1/experiment1 - Classic/scripts/consolidate_experiment1.py
(Experiment 1's original CS-driven consolidation), generalized to work from
any thesis/results/{RESULTS_VERSION}/experiment{N}* folder -- both
opin_flow.py's new runs and any future experiment reuse this, rather than
each getting its own copy-pasted script.

Endpoint paths embed per-run identifiers (consent URNs, JWK/CA filenames
that don't vary, etc.), so latency_per_endpoint keys are normalized (UUIDs
and "urn:raidiaminsurance:..." segments collapsed to "{id}") before being
compared across scenarios -- otherwise every scenario would show up as a
disjoint set of one-off paths instead of the same handful of endpoints.

Usage:
  RESULTS_VERSION=v3 EXPERIMENT_NUMBER=1 python consolidate_experiment.py
"""
import json
import os
import re
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPTS_DIR.parent.parent
SCENARIOS_MS = [0, 14, 30, 140, 225, 320]

UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
URN_RE = re.compile(r"urn:raidiaminsurance:[0-9a-fA-F-]+")


def normalize_endpoint(path: str) -> str:
    path = URN_RE.sub("{id}", path)
    path = UUID_RE.sub("{id}", path)
    return path


def load_scenarios(results_dir: Path):
    scenarios = {}
    for ms in SCENARIOS_MS:
        path = results_dir / f"{ms}ms" / "baseline_metrics.json"
        scenarios[ms] = json.loads(path.read_text(encoding="utf-8"))
    return scenarios


def build_consolidated(scenarios: dict) -> dict:
    return {
        "scenarios_ms": SCENARIOS_MS,
        "by_scenario": {
            str(ms): {
                "generated_at": m["generated_at"],
                "total_bytes_exchanged": m["total_bytes_exchanged"],
                "total_requests": m["total_requests"],
                "jwt_count": m["jwt_count"],
                "jwt_size_avg_bytes": m["jwt_size_avg_bytes"],
                "jwt_size_max_bytes": m["jwt_size_max_bytes"],
                "jwk_sizes": m["jwk_sizes"],
                "bytes_by_participant": m["bytes_by_participant"],
                "gateway_metrics": m["gateway_metrics"],
                "latency_per_endpoint": m["latency_per_endpoint"],
            }
            for ms, m in scenarios.items()
        },
    }


def write_report(scenarios: dict, experiment_number: str, path: Path):
    lines = []
    lines.append(f"# Experiment {experiment_number} Report -- opin_flow.py vs. Latency")
    lines.append("")
    if experiment_number == "3":
        methodology_note = (
            "Comparative report across the six WAN-latency scenarios "
            "(0/14/30/140/225/320ms, see thesis/scripts/set_latency.sh) run "
            "with thesis/scripts/opin_flow.py in hybrid mode (direct AS/RS "
            "traffic, no Conformance Suite -- CRYPTO_PROFILE=classic|pqc "
            "originally justified in thesis/results/experiment2 - PQC/"
            "DECISIONS.md, Decisions 6-8; the hybrid profile and everything "
            "specific to it -- Strong Nesting response signing, hybrid "
            "JWKS, hybrid mTLS certificates -- is documented in "
            "thesis/results/v4/DECISIONS.md, see in particular Decision 2 "
            "(Strong Nesting signing architecture) and Decision 6 (hybrid "
            "mTLS certificates, the dual nested combiner))."
        )
    else:
        methodology_note = (
            "Comparative report across the six WAN-latency scenarios "
            "(0/14/30/140/225/320ms, see thesis/scripts/set_latency.sh) run "
            "with thesis/scripts/opin_flow.py (direct AS/RS traffic, no "
            "Conformance Suite -- see thesis/results/experiment2 - PQC/DECISIONS.md, "
            "Decisions 6-8, for why)."
        )
    lines.append(methodology_note)
    lines.append("")

    lines.append("## Total OPINsize and request count")
    lines.append("")
    lines.append("| Latency | Total bytes exchanged | Total requests | JWTs found | Avg JWT size (bytes) |")
    lines.append("|---|---|---|---|---|")
    for ms in SCENARIOS_MS:
        m = scenarios[ms]
        lines.append(
            f"| {ms}ms | {m['total_bytes_exchanged']} | {m['total_requests']} | "
            f"{m['jwt_count']} | {m['jwt_size_avg_bytes']} |"
        )
    lines.append("")

    lines.append("## mTLS handshake vs. OPIN processing time (gateway-side)")
    lines.append("")
    lines.append("| Latency | Requests logged | Handshake mean (ms) | Handshake P95 (ms) | OPIN proc. mean (ms) | OPIN proc. P95 (ms) |")
    lines.append("|---|---|---|---|---|---|")
    for ms in SCENARIOS_MS:
        gw = scenarios[ms]["gateway_metrics"]
        hs = gw["handshake_ms"]
        op = gw["opin_processing_ms"]
        lines.append(
            f"| {ms}ms | {gw['requests_logged']} | "
            f"{hs['mean_ms'] if hs else '-'} | {hs['p95_ms'] if hs else '-'} | "
            f"{op['mean_ms'] if op else '-'} | {op['p95_ms'] if op else '-'} |"
        )
    lines.append("")

    lines.append("## mTLS handshake size (wire bytes, gateway-side)")
    lines.append("")
    lines.append(
        "Total bytes read+written at the raw TCP level during the "
        "handshake (ClientHello through Finished) -- see countingConn in "
        "mock-service-os/mock_mtls/main.go. This is the number expected to "
        "move most under PQC (larger KEM public keys/ciphertexts and "
        "signatures); it should be flat across latency scenarios here since "
        "this baseline doesn't change algorithms between them. Samples are "
        "deduplicated per physical TCP connection before P50/P95/P99 are "
        "computed (baseline_automation.py's dedupe_handshake_samples_by_connection) "
        "-- opin_flow.py reuses connections within a flow, so a naive "
        "one-sample-per-request count would over-weight whichever "
        "connection happened to carry the most requests."
    )
    lines.append("")
    lines.append("| Latency | Connections (samples) | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |")
    lines.append("|---|---|---|---|---|---|")
    for ms in SCENARIOS_MS:
        hb = scenarios[ms]["gateway_metrics"].get("handshake_bytes")
        lines.append(
            f"| {ms}ms | {hb['count'] if hb else 0} | "
            f"{hb['mean_bytes'] if hb else '-'} | {hb['p50_bytes'] if hb else '-'} | "
            f"{hb['p95_bytes'] if hb else '-'} | {hb['p99_bytes'] if hb else '-'} |"
        )
    lines.append("")

    lines.append("## Bytes by participant")
    lines.append("")
    lines.append(
        "**Client** is opin_flow.py itself -- it is one of the two parties "
        "on every logged call, so its row always equals that scenario's "
        "total bytes exchanged (see the first table) by construction, not "
        "a measurement of a separate category. AS/RS/Directory/PKI-CRL are "
        "the actual breakdown of who the client was talking to on each "
        "call, and they sum to that same total."
    )
    lines.append("")
    participants = sorted({p for m in scenarios.values() for p in m["bytes_by_participant"]})
    header = "| Participant | " + " | ".join(f"{ms}ms" for ms in SCENARIOS_MS) + " |"
    lines.append(header)
    lines.append("|---|" + "---|" * len(SCENARIOS_MS))
    for participant in participants:
        label = "Client (opin_flow.py, total traffic)" if participant == "Client" else participant
        row = [label]
        for ms in SCENARIOS_MS:
            b = scenarios[ms]["bytes_by_participant"].get(participant)
            total = (b["sent_bytes"] + b["received_bytes"]) if b else 0
            row.append(str(total))
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    lines.append("(Total bytes -- sent + received -- per participant, per scenario.)")
    lines.append("")

    lines.append("## Latency per endpoint (client-side, P50/P95/P99 in ms)")
    lines.append("")
    lines.append(
        "Endpoint paths are normalized (consent URNs and UUIDs collapsed to "
        "`{id}`) so the same logical endpoint can be compared across scenarios."
    )
    lines.append("")

    normalized = {}
    for ms in SCENARIOS_MS:
        for endpoint, stats in scenarios[ms]["latency_per_endpoint"].items():
            key = normalize_endpoint(endpoint)
            normalized.setdefault(key, {})[ms] = stats

    for endpoint in sorted(normalized):
        lines.append(f"### `{endpoint}`")
        lines.append("")
        header = "| Metric | " + " | ".join(f"{ms}ms" for ms in SCENARIOS_MS) + " |"
        lines.append(header)
        lines.append("|---|" + "---|" * len(SCENARIOS_MS))
        for metric, label in (("p50_ms", "P50"), ("p95_ms", "P95"), ("p99_ms", "P99")):
            row = [label]
            for ms in SCENARIOS_MS:
                stats = normalized[endpoint].get(ms)
                row.append(str(stats[metric]) if stats else "-")
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    lines.append("## Methodological notes")
    lines.append("")
    lines.append(
        "- **Connection reuse by design**: opin_flow.py's do_call() shares "
        "one requests.Session per flow (see its docstring), so unlike "
        "Experiment 1's Conformance Suite runs, most requests within a "
        "flow reuse the same TCP+TLS connection deliberately, not "
        "incidentally. The mTLS handshake cost is still counted once per "
        "physical connection (mock-service-os/mock_mtls/main.go), and "
        "compute_metrics() deduplicates by connection before computing "
        "handshake percentiles (see the note on the handshake-size table "
        "above) -- without that dedup, connection reuse would silently "
        "skew the percentiles toward whichever connection carried the "
        "most requests."
    )
    lines.append(
        "- **Outliers filtered**: mTLS handshake samples were dropped when "
        "more than 3x the scenario's median handshake time "
        "(`filter_handshake_outliers` in baseline_automation.py), applied "
        "iteratively, after the per-connection dedup above. Per-scenario "
        "counts of dropped samples are in "
        "`gateway_metrics.handshake_outliers_dropped` in each scenario's "
        "baseline_metrics.json."
    )
    lines.append(
        "- **PAR request_uri TTL at high injected latency**: oidc-provider's "
        "default 60s TTL for pushed authorization request_uris (not "
        "overridden in mock_as/utils/opin/configuration.js) is tight "
        "relative to the 225ms/320ms scenarios once round-trip cost "
        "compounds across the calls between PAR and login completion -- "
        "those two scenarios occasionally needed a retry "
        "(invalid_request_uri: expired) during data collection. This is an "
        "artifact of the measurement environment's security TTL, not a "
        "cryptography- or latency-*algorithm* finding; the data in this "
        "report is from the run that completed successfully for each "
        "scenario."
    )
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    experiment_number = os.environ.get("EXPERIMENT_NUMBER", "1")
    results_version = os.environ.get("RESULTS_VERSION", "v3")

    results_root = BASE_DIR / "thesis" / "results" / results_version
    results_dir = None
    for candidate in results_root.glob(f"experiment{experiment_number}*"):
        results_dir = candidate
        break
    if results_dir is None:
        raise SystemExit(f"No {results_root}/experiment{experiment_number}* folder found.")

    print(f"Consolidating {results_dir} ...")
    scenarios = load_scenarios(results_dir)

    consolidated = build_consolidated(scenarios)
    consolidated_path = results_dir / "consolidated.json"
    consolidated_path.write_text(json.dumps(consolidated, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Consolidated data saved to {consolidated_path}")

    report_path = results_dir / f"EXPERIMENT{experiment_number}_REPORT.md"
    write_report(scenarios, experiment_number, report_path)
    print(f"Report saved to {report_path}")


if __name__ == "__main__":
    main()
