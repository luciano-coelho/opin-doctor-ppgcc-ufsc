"""
Experiment 1 (classical baseline) consolidation -- step 5.2/5.3.

Reads the six per-scenario thesis/results/experiment1 - Classic/{ms}ms/baseline_metrics.json
files produced by baseline_automation.py and combines them into:
  - thesis/results/experiment1 - Classic/consolidated.json: the six scenarios'
    summary metrics side by side, for programmatic reuse (e.g. plotting later).
  - thesis/results/experiment1 - Classic/EXPERIMENT1_REPORT.md: the human-readable
    comparative report requested in step 5.3 (total OPINsize, TLS-handshake
    vs. OPIN-processing split, per-endpoint P50/P95/P99, bytes per
    participant -- all six scenarios side by side).

Endpoint paths embed per-run identifiers (consent URNs, JWK/CA filenames
that don't vary, etc.), so latency_per_endpoint keys are normalized (UUIDs
and "urn:raidiaminsurance:..." segments collapsed to "{id}") before being
compared across scenarios -- otherwise every scenario would show up as a
disjoint set of one-off paths instead of the same handful of endpoints.
"""
import json
import re
from pathlib import Path

# This script lives in .../experiment1 - Classic/scripts/, so parent.parent
# is the "experiment1 - Classic" results folder itself.
RESULTS_DIR = Path(__file__).resolve().parent.parent
SCENARIOS_MS = [0, 14, 30, 140, 225, 320]

UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
URN_RE = re.compile(r"urn:raidiaminsurance:[0-9a-fA-F-]+")


def normalize_endpoint(path: str) -> str:
    path = URN_RE.sub("{id}", path)
    path = UUID_RE.sub("{id}", path)
    return path


def load_scenarios():
    scenarios = {}
    for ms in SCENARIOS_MS:
        path = RESULTS_DIR / f"{ms}ms" / "baseline_metrics.json"
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


def write_report(scenarios: dict, path: Path):
    lines = []
    lines.append("# Experiment 1 Report -- Classical Baseline vs. Latency")
    lines.append("")
    lines.append(
        "Comparative report across the six WAN-latency scenarios "
        "(0/14/30/140/225/320ms, see thesis/scripts/set_latency.sh) run "
        "against the classical-cryptography baseline "
        "(thesis/scripts/baseline_automation.py)."
    )
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
        "the classical baseline doesn't change algorithms between them."
    )
    lines.append("")
    lines.append("| Latency | Samples | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |")
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
        "**Client** is the Conformance Suite itself (the OPIN client in "
        "this test harness) -- it is one of the two parties on every "
        "logged call, so its row always equals that scenario's total bytes "
        "exchanged (see the first table) by construction, not a measurement "
        "of a separate category. AS/RS/Directory/PKI-CRL are the actual "
        "breakdown of who the client was talking to on each call, and they "
        "sum to that same total."
    )
    lines.append("")
    participants = sorted({p for m in scenarios.values() for p in m["bytes_by_participant"]})
    header = "| Participant | " + " | ".join(f"{ms}ms" for ms in SCENARIOS_MS) + " |"
    lines.append(header)
    lines.append("|---|" + "---|" * len(SCENARIOS_MS))
    for participant in participants:
        label = "Client (test tool, total traffic)" if participant == "Client" else participant
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
        "- **Keep-alive connections**: the mTLS handshake cost is counted "
        "once per TCP connection, not once per HTTP request. A connection "
        "kept alive across several requests (including, in a few cases, "
        "across a scenario boundary) reports the same cached handshake "
        "timestamp for every request it serves -- expected behavior of the "
        "gateway instrumentation (mock-service-os/mock_mtls/main.go), not a "
        "measurement error."
    )
    lines.append(
        "- **Outliers filtered**: mTLS handshake samples were dropped when "
        "more than 3x the scenario's median handshake time "
        "(`filter_handshake_outliers` in baseline_automation.py), applied "
        "iteratively. This exists because of the point above: a handful of "
        "genuinely slow keep-alive connections replay the same extreme "
        "value across several requests, so a plain P99-based threshold is "
        "self-defeating in samples this small (P99 already sits near the "
        "duplicated extreme values, so \"3x P99\" never clears its own "
        "threshold) -- the median stays representative as long as the "
        "outlier cluster is a minority of the sample, which held for every "
        "scenario here. Per-scenario counts of dropped samples are in "
        "`gateway_metrics.handshake_outliers_dropped` in each scenario's "
        "baseline_metrics.json."
    )
    lines.append(
        "- **Known person_api_core failure**: `person_api_core_test-module_v2.0.0` "
        "failed in all 6 scenarios on the same pre-existing, unrelated "
        "issue -- a schema validation failure on the `address` field of the "
        "mock's person data (0 of 2 valid schemas), reproduced identically "
        "each time (1095 log entries). This is a mock data/schema issue, "
        "not a cryptography- or latency-related finding, and doesn't affect "
        "the `opin-consent-api-status-test-v3` results this experiment is "
        "built on (6/6 PASSED)."
    )
    lines.append(
        "- **Environment stability**: during earlier test passes, the "
        "highest-latency scenario (320ms) occasionally needed a retry after "
        "transient failures (an aborted mTLS handshake, an internal 401 on "
        "the auth server's consent-revalidation call, a gateway<->auth "
        "proxy EOF/502, or a SessionNotFound tied to accumulated browser "
        "session state after many manual logins in one sitting). None of "
        "these repeated deterministically, and container health (CPU/"
        "memory) was consistently normal when checked -- the data in this "
        "report is from a run where every scenario, including 320ms, "
        "completed cleanly on the first attempt."
    )
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    scenarios = load_scenarios()

    consolidated = build_consolidated(scenarios)
    consolidated_path = RESULTS_DIR / "consolidated.json"
    consolidated_path.write_text(json.dumps(consolidated, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Consolidated data saved to {consolidated_path}")

    report_path = RESULTS_DIR / "EXPERIMENT1_REPORT.md"
    write_report(scenarios, report_path)
    print(f"Report saved to {report_path}")


if __name__ == "__main__":
    main()
