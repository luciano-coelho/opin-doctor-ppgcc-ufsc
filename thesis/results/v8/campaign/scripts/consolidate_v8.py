#!/usr/bin/env python3
"""Reads the real `v8/latency/...` tree (Decision 53's own layout -- see
METRICS_COVERAGE.md) and writes `consolidated.json` (source) and
`CONSOLIDATED_REPORT.md` (derived) into the given output directory, with
the same field structure as v7's own `report_data_v7.json`/
`Consolidated_Metrics_Report_FINAL.md` wherever v8's data supports it.

Reuses v7's own computation, never reimplements it: `pem_der_len()` is
copied verbatim from `compute_v7_report_data.py` (same helper, same
contract), and the statistics (median/min/max/mean/stdev/spread) follow
the same definitions as `compute_v7_report_data.py`/the v7 report's own
Section 1.5 -- only the bootstrap CI of the median is new (v8-only,
Decision -- see METRICS_COVERAGE.md "New in v8").

term_handshake (the mTLS handshake bytes term) is read from
`server/run{NN}_gateway.log`'s own "mTLS handshake complete" lines
(`mock_mtls/main.go`'s `countingConn`, unchanged since v7, still logs
`mtlsHandshakeBytes` per connection) -- NOT from a pcap capture. This
was investigated and corrected (Decision -- see DECISIONS.md, the entry
superseding Decision 76's "needs a pcap extractor" framing): the
gateway already logs the exact field v7's own `compute_v7_report_data.py`
read as `gateway_metrics.handshake_bytes`, and `campaign_pull.sh`
already pulls `server/run{NN}_gateway.log` generically (`find v8 -type
f | xargs sha256sum`, no exclusions) -- no collection or pull-side fix
was needed, only this parser. Reuses `campaign_run.py`'s own
`_parse_gateway_log_lines()`/`_HANDSHAKE_COMPLETE_MSG`/`_CARVEOUT_MSG`/
`_CLIENT_EXPECTED_CURVE` rather than reimplementing the client-facing
vs. internal-AS-to-RS-channel disambiguation (the same gateway also logs
the AS's own internal mTLS calls to the RS, Decision 76's own flow-time
section -- these must be excluded, same rule `verify_negotiated_groups()`
already uses). Pcap remains independent verification only, for whatever
it can show that the gateway log cannot (RTT, packet loss, ClientHello
as a standalone figure) -- not a second handshake-bytes source.

opin_processing_ms (server-processing leg of the flow-time decomposition,
investigated 2026-10-22) is read the same way, from the SAME gateway log's
"access log" lines (one per HTTP request, not one per connection --
`mock_mtls/main.go` line 790, field `opinDurationMs`, line 768). v7's own
`baseline_automation.py` (`collect_gateway_metrics()`/`compute_metrics()`)
reads this from `docker logs` live; this module reuses its own
`dedupe_handshake_samples_by_connection()`/`filter_handshake_outliers()`/
`latency_stats()` directly (not reimplemented) against entries parsed
from the already-saved `server/run{NN}_gateway.log` text instead of a
live `docker logs` call.

term_handshake_pcap (2026-10-22, DECISIONS.md): a SECOND, independent
measurement of the same term, from the client's own pcap
(`client/run{NN}.pcap.gz`) via `pilot_acceptance.py`'s
`extract_clean_handshake_bytes()` -- ClientHello through the client's
own Finished only, excluding the first-request leakage the gateway's own
`countingConn` boundary lets through (Decision 78). `HANDSHAKE_SOURCE`
(module constant below) picks which one feeds OPINsize's own total;
`pilot_acceptance.py`'s own Criterion 11 is what should inform changing
it, based on real campaign data (not something this module decides by
itself).

Usage:
  consolidate_v8.py <v8-latency-root> <output-dir>
    e.g. consolidate_v8.py thesis/results/v8/latency thesis/results/v8/latency
"""
import base64
import gzip
import json
import random
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from campaign_run import (  # reused, not reimplemented -- see module docstring above
    _parse_gateway_log_lines,
    _HANDSHAKE_COMPLETE_MSG,
    _CARVEOUT_MSG,
    _CLIENT_EXPECTED_CURVE,
    _CORRELATION_WINDOW_SECONDS,
)
from pcap_utils import extract_clean_handshake_bytes, detect_loss_signals  # noqa: E402 -- shared, see pcap_utils.py's own docstring

_REPO_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO_ROOT / "thesis" / "scripts"))
import baseline_automation as ba  # noqa: E402 -- reused for dedupe/outlier-filter/stats, not reimplemented

_ACCESS_LOG_MSG = "access log"

# Which measurement feeds OPINsize's own handshake term. Default stays
# "gateway" (comparability with v7's own historical figures, Decision --
# see DECISIONS.md: the countingConn boundary artifact is a KNOWN,
# documented limitation, deliberately not changed). Flip to "pcap" only
# on Luciano's own call, informed by pilot_acceptance.py's Criterion 11
# (gateway-vs-pcap diff across real scenarios at different RTT) -- not
# something this module decides automatically.
HANDSHAKE_SOURCE = "gateway"

PROFILE_TO_EXPERIMENT_DIR = {
    "classic": "experiment1 - Classic",
    "pqc": "experiment2 - PQC",
    "hybrid": "experiment3 - Hybrid",
}
PROFILES = ["classic", "pqc", "hybrid"]
PKI_ENDPOINTS = ("/root-ca.pem", "/issuer-ca.pem")
PKI_HTTP_FRAMING_BYTES = 103  # per response; same constant v7 found (compute_v7_report_data.py:116-118)


def pem_der_len(path):
    """DER length of the single certificate inside a PEM file. Copied
    verbatim from compute_v7_report_data.py:66-71 -- same contract,
    reused rather than reimplemented."""
    raw = path.read_bytes()
    m = re.search(rb"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----", raw, re.S)
    assert m and raw.count(b"BEGIN CERTIFICATE") == 1
    return len(base64.b64decode(m.group(1)))


def bootstrap_median_ci(values, n_resamples=2000, ci=0.95, seed=1234):
    """New in v8 (not in v7): a bootstrap confidence interval around the
    median, added because v8's real-AWS campaign runs fewer repetitions
    per scenario (30, Decision 53) than v7's lab setup (60) -- a bare
    median alone understates the uncertainty at that sample size. Fixed
    seed so re-running the generator on the same data reproduces the
    same interval (consolidate_v8.py's own output must be deterministic,
    same expectation as every other number in this pipeline)."""
    if len(values) < 2:
        return (values[0], values[0]) if values else (None, None)
    rng = random.Random(seed)
    medians = []
    n = len(values)
    for _ in range(n_resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        medians.append(statistics.median(sample))
    medians.sort()
    lo_idx = int((1 - ci) / 2 * n_resamples)
    hi_idx = int((1 + ci) / 2 * n_resamples) - 1
    return (medians[max(0, lo_idx)], medians[min(n_resamples - 1, hi_idx)])


def stats_block(values):
    """Same statistics as v7's own Section 1.5: median, min, max, mean,
    stdev, spread (max-min)/min. Plus v8's new bootstrap CI."""
    if not values:
        return None
    out = {
        "n": len(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "mean": statistics.mean(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }
    out["spread_pct"] = ((out["max"] - out["min"]) / out["min"] * 100) if out["min"] else 0.0
    out["bootstrap_median_ci95"] = bootstrap_median_ci(values)
    return out


def load_calls(calls_path):
    if not calls_path.is_file():
        return []
    return [json.loads(line) for line in calls_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_ping(ping_path):
    """New in v8: parses `ping -c 10 -q <ip>`'s own text output for RTT
    (min/avg/max/mdev) and packet loss. `ping -c 10` only resolves loss
    in 10% increments, so loss is reported as an upper bound, not a
    point estimate (METRICS_COVERAGE.md, "New in v8")."""
    if not ping_path.is_file():
        return None
    raw = json.loads(ping_path.read_text(encoding="utf-8")).get("raw_ping_output", "")
    if not raw:
        return None
    loss_m = re.search(r"(\d+)% packet loss", raw)
    rtt_m = re.search(r"= ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms", raw)
    out = {}
    if loss_m:
        out["loss_pct_upper_bound"] = int(loss_m.group(1))
    if rtt_m:
        out["rtt_min_ms"], out["rtt_avg_ms"], out["rtt_max_ms"], out["rtt_mdev_ms"] = (float(g) for g in rtt_m.groups())
    return out or None


def load_cpu_mem(cpu_jsonl_path):
    """New in v8: CPU/steal/memory samples from `_sample_cpu_mem_steal()`
    (campaign_run.py:638-701), one point-in-time sample per line."""
    if not cpu_jsonl_path.is_file():
        return None
    # Pilot item 3 (this turn): found live, real pilot data -- a line
    # can be a null-byte gap (concurrent writers to the same path when
    # a timed-out execution's own background sampler was never stopped
    # before a retry reused the same filename, now fixed in
    # campaign_run.py; see DECISIONS.md). One bad line used to crash
    # this whole script; skipped here instead, same as
    # pilot_acceptance.py's own equivalent fix.
    samples = []
    for line in cpu_jsonl_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            samples.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not samples:
        return None
    cpu_totals = [s["cpu"]["total"] for s in samples if s.get("cpu")]
    cpu_steals = [s["cpu"]["steal"] for s in samples if s.get("cpu")]
    cpu_idles = [s["cpu"]["idle"] for s in samples if s.get("cpu")]
    out = {"n_samples": len(samples)}
    if cpu_totals and cpu_idles:
        util_pct = [100 * (1 - idle / total) for total, idle in zip(cpu_totals, cpu_idles) if total]
        out["cpu_utilization_pct_mean"] = statistics.mean(util_pct) if util_pct else None
    if cpu_steals and cpu_totals:
        steal_pct = [100 * steal / total for steal, total in zip(cpu_steals, cpu_totals) if total]
        out["cpu_steal_pct_mean"] = statistics.mean(steal_pct) if steal_pct else None
    mem_samples = [s["memory"] for s in samples if s.get("memory")]
    if mem_samples:
        out["memory_samples"] = mem_samples
    return out


def term_jwt(calls):
    return sum(sum(c.get("jwt_sizes", [])) for c in calls)


def n_jwt(calls):
    return sum(len(c.get("jwt_sizes", [])) for c in calls)


def term_jwk(calls):
    """Counts (and sizes) exactly one "sig" JWK per `/jwks` response.

    Fixed 2026-10-25 (DECISIONS.md, "fluxo completo" follow-up): a real
    hybrid `/jwks` response now publishes TWO "sig" entries for the SAME
    key, confirmed live, same kid on both -- the composed `kty: "HYBRID"`
    entry (`pk_hybrid`, 2208 bytes: classic 256-byte modulus + pqc
    1952-byte raw key) AND a plain `kty: "RSA"` duplicate of just its
    classical half (256 bytes), published "so a real, standards-
    compliant JWKS consumer doing ordinary kid+alg discovery can find a
    key that matches what a payload-extension-signed JWT's header
    actually says" (ResponseSigningService.java's own comment). The
    original assert here assumed exactly one "sig" entry per response --
    true for classic/pqc, no longer true for hybrid. Takes the LARGEST
    "sig" entry per call instead of asserting a single constant size:
    the composed HYBRID entry is the real signing key (confirmed against
    v7's own hybrid figure -- 2 fetches x 2208 bytes = 4,416, exactly
    v7's `term_jwk`); the smaller plain-RSA duplicate is a discovery-
    compatibility shim for the SAME key, not a second artifact to count
    again."""
    sig_sizes = []
    for c in calls:
        call_sig_sizes = [jwk["size_bytes"] for jwk in c.get("jwk_sizes", []) if jwk.get("use") == "sig"]
        if call_sig_sizes:
            sig_sizes.append(max(call_sig_sizes))
    if not sig_sizes:
        return 0, 0
    assert len(set(sig_sizes)) == 1, f"jwk sig size not constant across calls: {set(sig_sizes)}"
    return len(sig_sizes), len(sig_sizes) * sig_sizes[0]


def n_pki_and_term_pki(calls):
    pki_calls = [c for c in calls if c.get("endpoint") in PKI_ENDPOINTS]
    n = len(pki_calls)
    body_total = sum(c["response_bytes"] for c in pki_calls) - n * PKI_HTTP_FRAMING_BYTES
    return n, body_total


def n_mtls(calls):
    """DIAGNOSTIC ONLY -- not the authoritative N_mTLS (see
    consolidate_profile_scenario()'s own comment). Distinct `pool_label`
    values in campaign_client_runner.py's own per-call output undercount
    the real TLS connection total (confirmed 4 vs. the gateway log's own
    real 6, 2026-10-22 investigation): opin_flow.py's own connection
    pooling can reuse one pool label across more than one underlying
    TLS handshake. Kept only so a real mismatch between this and the
    gateway-log-derived count is visible in consolidated.json, not
    hidden."""
    return len({c["pool_label"] for c in calls if c.get("pool_label")})


def client_facing_handshakes(gateway_log_text, profile, window_seconds=_CORRELATION_WINDOW_SECONDS):
    """Parses `server/run{NN}_gateway.log` (the mtls gateway's own real
    slog JSON output, `mock_mtls/main.go`'s `countingConn`) and returns
    the list of "mTLS handshake complete" events for the CLIENT-FACING
    channel only -- excluding the AS's own internal mTLS calls to the RS
    (`InsurerAdapter.getConsent()`, also logged as handshake-complete
    events on this same gateway). Same remoteAddr-based pairing rule as
    `campaign_run.py`'s own `verify_negotiated_groups()` (a handshake
    with a paired carve-out line within the window is the internal
    channel; one with no pair is client-facing) -- reused directly, not
    reimplemented, because duplicating that pairing logic independently
    risks the two drifting apart silently."""
    entries = _parse_gateway_log_lines(gateway_log_text)
    handshakes = [(ts, obj) for ts, obj in entries if obj.get("msg") == _HANDSHAKE_COMPLETE_MSG]
    carveouts = [(ts, obj) for ts, obj in entries if obj.get("msg") == _CARVEOUT_MSG]
    carveouts_by_addr = {}
    for ts, obj in carveouts:
        carveouts_by_addr.setdefault(obj.get("remoteAddr"), []).append((ts, obj))
    matched = set()
    client_facing = []
    for ts, hs in handshakes:
        addr = hs.get("remoteAddr")
        paired = False
        for i, (cts, _cobj) in enumerate(carveouts_by_addr.get(addr, [])):
            if (addr, i) in matched:
                continue
            if abs((cts - ts).total_seconds()) <= window_seconds:
                matched.add((addr, i))
                paired = True
                break
        if not paired:
            client_facing.append(hs)
    expected_curve = _CLIENT_EXPECTED_CURVE.get(profile)
    if expected_curve:
        off_curve = [h for h in client_facing if h.get("curveID") != expected_curve]
        if off_curve:
            raise ValueError(
                f"{len(off_curve)} client-facing handshake(s) negotiated a curve other than "
                f"{expected_curve!r} expected for profile {profile!r} -- a real negotiated-group "
                f"regression (same class as campaign_run.py's own verify_negotiated_groups() check), "
                f"not something this generator should silently average over.")
    return client_facing


def term_handshake(gateway_log_text, profile):
    """Covered (METRICS_COVERAGE.md, corrected): reads real per-connection
    `mtlsHandshakeBytes` values from the gateway's own log -- the SAME
    source v7's `compute_v7_report_data.py` read as `gateway_metrics.
    handshake_bytes` (that field just came from a different capture
    layer in v7's own pipeline; the underlying measurement, `countingConn`
    in `mock_mtls/main.go`, is unchanged). Returns (count, total_bytes)
    using the MEDIAN handshake size x count, same definition as v7's own
    `N_mTLS x handshake_bytes` term (`compute_v7_report_data.py:149`),
    not a mean or a sum of raw values."""
    if not gateway_log_text:
        return None, None
    handshakes = client_facing_handshakes(gateway_log_text, profile)
    sizes = [h["mtlsHandshakeBytes"] for h in handshakes if "mtlsHandshakeBytes" in h]
    if not sizes:
        return None, None
    median_bytes = statistics.median(sizes)
    return len(sizes), len(sizes) * median_bytes


def term_handshake_pcap(client_pcap_path, gateway_log_text, profile):
    """Independent, second measurement of term_handshake -- from the
    client's own pcap (`extract_clean_handshake_bytes()`,
    `pilot_acceptance.py`), ClientHello through the client's own Finished
    only, excluding the first-request leakage `term_handshake()`'s own
    gateway-log source carries (Decision 78). Filtered to the SAME
    client-facing connections `term_handshake()` already identifies,
    matched by the client's own source PORT alone -- not the full (ip,
    port) tuple as originally assumed here. Confirmed real and necessary
    2026-10-25 (DECISIONS.md, Decision 85): a non-colocated scenario
    (L325) routes client->server traffic over the client's own Internet
    Gateway to the server's public IP, which SNATs the client's pcap-
    visible private IP (e.g. `172.31.3.110`) to its own public/Elastic IP
    (e.g. `13.228.42.155`) by the time the server's gateway log sees it --
    confirmed live, byte for byte, same 6 ephemeral ports present on both
    sides of a real L325 run, different IP. Standard SNAT/PAT preserves
    the source port whenever possible (and did, in every real connection
    checked); IP-based matching only ever happened to work for L0, where
    `pick_gateway_ip()`'s own private-IP routing means there is no NAT to
    begin with. A port-collision false match is not a practical risk at
    this project's own concurrency (a handful of client-facing
    connections per execution, ephemeral high port range). Returns
    (count, total_bytes) -- same median x count definition as
    `term_handshake()`. Needs BOTH files (pcap for the real bytes, the
    gateway log for which connections are client-facing) -- returns
    (None, None) if either is missing, never a guess from one alone."""
    if not client_pcap_path or not Path(client_pcap_path).is_file() or not gateway_log_text:
        return None, None
    client_facing_ports = set()
    for h in client_facing_handshakes(gateway_log_text, profile):
        addr = h.get("remoteAddr")
        if addr:
            _ip, _, port = addr.rpartition(":")
            client_facing_ports.add(int(port))
    if not client_facing_ports:
        return None, None
    pcap_connections = extract_clean_handshake_bytes(client_pcap_path)
    sizes = [v["clean_handshake_bytes"] for (_ip, port), v in pcap_connections.items() if port in client_facing_ports]
    if not sizes:
        return None, None
    median_bytes = statistics.median(sizes)
    return len(sizes), len(sizes) * median_bytes


def pcap_loss_summary(client_pcap_paths):
    """Aggregates `detect_loss_signals()` (pcap_utils.py) across every
    execution's own client pcap in a scenario, into one estimate.
    Added 2026-10-25 (DECISIONS.md, Decision 85): the real campaign's
    security groups block ICMP (PILOT_RUNBOOK.md's own abort-criteria
    table), so the pre-existing ping-based loss figure above is never
    populated against real pilot data -- this is TCP's own, always-
    available loss evidence instead, read from the same pcaps already
    collected for the handshake-bytes term, not a new collection need.

    When zero loss events are observed across every segment seen, "0%"
    would overstate the confidence a small sample actually supports --
    the rule of three (the standard ~95% one-sided upper bound on a
    true event rate, given zero occurrences in n independent trials) is
    reported instead, so "no loss observed" and "loss is impossible"
    stay visibly different."""
    total_segments = 0
    totals = {"retransmissions": 0, "out_of_order": 0, "duplicate_ack_events": 0, "loss_events": 0}
    n_pcaps = 0
    for p in client_pcap_paths:
        if not p:
            continue
        r = detect_loss_signals(p)
        n_pcaps += 1
        total_segments += r["total_segments"]
        for k in totals:
            totals[k] += r[k]
    if n_pcaps == 0:
        return None
    out = {"n_executions": n_pcaps, "total_segments": total_segments, **totals}
    if totals["loss_events"] == 0:
        out["loss_pct"] = None
        out["loss_pct_upper_bound_rule_of_three"] = round(3 / total_segments * 100, 4) if total_segments else None
    else:
        out["loss_pct"] = round(totals["loss_events"] / total_segments * 100, 4) if total_segments else None
        out["loss_pct_upper_bound_rule_of_three"] = None
    return out


def parse_access_log_entries(gateway_log_text):
    """Offline equivalent of `baseline_automation.collect_gateway_metrics()`
    (which runs `docker logs` live) -- same line filter (`"msg":"access
    log"` substring + json.loads) and the same field subset, applied to an
    already-saved `server/run{NN}_gateway.log` text instead. Kept as a thin
    parsing-only adapter so the real work (dedup, outlier filtering, stats)
    stays in `baseline_automation.py`, not duplicated here."""
    entries = []
    for line in gateway_log_text.splitlines():
        line = line.strip()
        if not line or f'"msg":"{_ACCESS_LOG_MSG}"' not in line:
            continue
        _ts, _, rest = line.partition(" ")
        try:
            entry = json.loads(rest)
        except ValueError:
            continue
        entries.append({
            "host": entry.get("host"), "request": entry.get("request"), "status": entry.get("status"),
            "opinDurationMs": entry.get("opinDurationMs"),
            "mtlsHandshakeDurationMs": entry.get("mtlsHandshakeDurationMs"),
            "mtlsHandshakeBytes": entry.get("mtlsHandshakeBytes"),
            "tlsVersion": entry.get("tlsVersion"), "cipherSuite": entry.get("cipherSuite"),
            "clientCertBytes": entry.get("clientCertBytes"), "remoteIP": entry.get("remoteIP"),
        })
    return entries


def opin_processing_stats(gateway_log_text, profile):
    """Server-processing leg of the flow-time decomposition (v7's own
    Section 4, "Where the flow's time actually goes"). NOT deduped by
    connection -- unlike handshake bytes/duration, processing time
    genuinely varies per REQUEST, same as `baseline_automation.compute_
    metrics()`'s own treatment (`opin_ms` there is built from every
    access-log entry directly, no `dedupe_handshake_samples_by_
    connection()` call on that field).

    v7's own `compute_metrics()` restricts `gateway_entries` to
    `clientCertBytes == <the profile's own client cert size>` before
    computing this, to exclude the AS's own internal mTLS calls to the
    RS (a real, separate population logged on the same gateway -- same
    issue `term_handshake()`/`client_facing_handshakes()` already solve
    for the bytes term). Reuses THAT SAME mechanism here (remoteAddr
    correlation against the carve-out lines) instead of hardcoding a
    second, parallel clientCertBytes-equality constant per profile --
    one definition of "client-facing" for both metrics, not two."""
    if not gateway_log_text:
        return None
    client_facing_addrs = {h.get("remoteAddr") for h in client_facing_handshakes(gateway_log_text, profile)}
    entries = parse_access_log_entries(gateway_log_text)
    client_facing_entries = [e for e in entries if e.get("remoteIP") in client_facing_addrs]
    opin_ms = [e["opinDurationMs"] for e in client_facing_entries if e.get("opinDurationMs") is not None]
    return {"requests_logged": len(client_facing_entries), **(ba.latency_stats(opin_ms) or {})}


def bytes_by_participant(calls):
    out = {}
    for c in calls:
        p = c.get("participant", "Other")
        out.setdefault(p, {"sent_bytes": 0, "received_bytes": 0})
        out[p]["sent_bytes"] += c.get("request_bytes", 0)
        out[p]["received_bytes"] += c.get("response_bytes", 0)
    return out


def latency_per_endpoint(calls):
    by_ep = {}
    for c in calls:
        by_ep.setdefault(c["endpoint"], []).append(c["latency_ms"])
    return {ep: stats_block(v) for ep, v in by_ep.items()}


def discover_scenarios(experiment_dir_path):
    """experiment_dir_path: v8_latency_root / "experiment1 - Classic".
    Returns {server: [scenario, ...]} -- discovered, not hardcoded, so a
    partial campaign (not every server/scenario populated yet) still
    consolidates whatever exists (same principle as compute_v8_size_
    report.py's own docstring: "does not require all 720 to be present")."""
    out = {}
    if not experiment_dir_path.is_dir():
        return out
    for server_dir in sorted(p for p in experiment_dir_path.iterdir() if p.is_dir()):
        scenarios = sorted(p.name for p in server_dir.iterdir() if p.is_dir() and (p / "runs").is_dir())
        if scenarios:
            out[server_dir.name] = scenarios
    return out


def load_gateway_log(scenario_path, run_stem):
    log_path = scenario_path / "server" / f"{run_stem}_gateway.log"
    return log_path.read_text(encoding="utf-8") if log_path.is_file() else None


def find_client_pcap(scenario_path, run_stem):
    """Returns the client pcap's path (gzipped or plain, whichever
    exists) or None -- never decompresses it here, `read_pcap_packets()`
    (`pilot_acceptance.py`) auto-detects by extension."""
    for suffix in (".pcap.gz", ".pcap"):
        p = scenario_path / "client" / f"{run_stem}{suffix}"
        if p.is_file():
            return p
    return None


def consolidate_profile_scenario(scenario_path, profile):
    runs_dir = scenario_path / "runs"
    run_files = sorted(p for p in runs_dir.glob("run*.json"))
    rows = []
    for run_file in run_files:
        data = json.loads(run_file.read_text(encoding="utf-8"))
        result = data.get("result", {})
        # Pilot item 3 (this turn): found live, real pilot data -- the
        # run's own summary file is "run{NN}.json" (no window prefix),
        # but every AUXILIARY file campaign_run.py's own SSHExecutor
        # writes alongside it (gateway log, client pcap, cpu/mem, ping,
        # calls.jsonl) uses "w{window:02d}_run{NN}" as its own stem
        # ("A.1: window folded into the remote label too" -- added to
        # stop window 2/3 overwriting window 1's own files, but
        # consolidate_v8.py was never updated to match it: every lookup
        # here used the bare run_file.stem, which never matched any real
        # SSHExecutor auxiliary file for ANY window -- term_handshake/
        # term_jwt/term_jwk/term_pki all silently came back "missing"
        # for every real pilot run, until caught here). LocalExecutor
        # uses the bare stem with NO window prefix for the same files
        # (confirmed live, pilot_acceptance.py's own load_runs() already
        # documents and handles this exact split) -- same
        # check-what's-actually-on-disk strategy reused here, not a
        # second, separately-maintained guess.
        window = data.get("window")
        run_stem = run_file.stem
        if window is not None:
            ssh_stem = f"w{window:02d}_{run_file.stem}"
            local_stem = run_file.stem
            if (runs_dir / f"{local_stem}.calls.jsonl").exists() and not (runs_dir / f"{ssh_stem}.calls.jsonl").exists():
                run_stem = local_stem
            else:
                run_stem = ssh_stem
        calls_file = runs_dir / f"{run_stem}.calls.jsonl"
        calls = load_calls(calls_file)
        gateway_log = load_gateway_log(scenario_path, run_stem)
        client_pcap = find_client_pcap(scenario_path, run_stem)
        rows.append({"run_file": run_file.name, "run_stem": run_stem, "retried": bool(data.get("retried", False)),
                      "result": result, "calls": calls, "gateway_log": gateway_log,
                      "client_pcap": client_pcap})

    clean_rows = [r for r in rows if not r["retried"]]
    retried_rows = [r for r in rows if r["retried"]]
    if not clean_rows:
        return None

    t_fluxo = [r["result"]["t_fluxo_seconds"] for r in clean_rows if "t_fluxo_seconds" in r["result"]]
    call_counts = {r["result"].get("call_count") for r in clean_rows if "call_count" in r["result"]}

    agg_calls_per_run = [r["calls"] for r in clean_rows if r["calls"]]
    jwt_sums = [term_jwt(c) for c in agg_calls_per_run]
    jwt_counts = {n_jwt(c) for c in agg_calls_per_run}
    jwk_results = [term_jwk(c) for c in agg_calls_per_run]
    pki_results = [n_pki_and_term_pki(c) for c in agg_calls_per_run]
    pool_label_counts = {n_mtls(c) for c in agg_calls_per_run}  # diagnostic only -- see n_mtls()'s own note

    handshake_results = [term_handshake(r["gateway_log"], profile) for r in clean_rows]
    handshake_known = [h for h in handshake_results if h[1] is not None]
    # N_mTLS authoritative source is the real gateway-log handshake count
    # (term_handshake's own first element), not pool_label grouping: a
    # real cross-check (2026-10-22 investigation) found pool_label
    # undercounts (4 distinct labels for 6 real TLS connections --
    # opin_flow.py's own connection pooling reuses a pool label across
    # more than one underlying handshake) -- pool_label_counts above is
    # kept only as a diagnostic, never reported as N_mTLS.
    mtls_counts = {h[0] for h in handshake_known}

    handshake_pcap_results = [term_handshake_pcap(r["client_pcap"], r["gateway_log"], profile) for r in clean_rows]
    handshake_pcap_known = [h for h in handshake_pcap_results if h[1] is not None]

    opin_processing_results = [opin_processing_stats(r["gateway_log"], profile) for r in clean_rows]
    opin_processing_known = [o for o in opin_processing_results if o and o.get("p50_ms") is not None]

    ping_samples = [load_ping(scenario_path / "client" / f"{r['run_stem']}_ping.json") for r in clean_rows]
    ping_samples = [p for p in ping_samples if p]
    pcap_loss = pcap_loss_summary([r["client_pcap"] for r in clean_rows])
    cpu_server = [load_cpu_mem(scenario_path / "server" / f"{r['run_stem']}_cpu.jsonl") for r in clean_rows]
    cpu_server = [c for c in cpu_server if c]
    cpu_client = [load_cpu_mem(scenario_path / "client" / f"{r['run_stem']}_cpu.jsonl") for r in clean_rows]
    cpu_client = [c for c in cpu_client if c]

    out = {
        "runs_used": len(clean_rows),
        "runs_retried_excluded": len(retried_rows),
        "t_fluxo_seconds": stats_block(t_fluxo),
        "call_count": sorted(call_counts) if len(call_counts) == 1 else {"not_constant": sorted(call_counts)},
        "term_jwt": stats_block(jwt_sums),
        "n_jwt": sorted(jwt_counts) if len(jwt_counts) == 1 else {"not_constant": sorted(jwt_counts)},
        "n_jwk": sorted({j[0] for j in jwk_results}),
        "term_jwk": stats_block([j[1] for j in jwk_results]),
        "n_pki": sorted({p[0] for p in pki_results}),
        "term_pki": stats_block([p[1] for p in pki_results]),
        "n_mtls": sorted(mtls_counts) if len(mtls_counts) == 1 else {"not_constant": sorted(mtls_counts)},
        "n_mtls_pool_label_diagnostic": sorted(pool_label_counts),
        "term_handshake": {
            "status": "covered" if handshake_known else "missing_gateway_log",
            "stats": stats_block([h[1] for h in handshake_known]) if handshake_known else None,
            "source": "server/run{NN}_gateway.log (mtlsHandshakeBytes) -- known to include some "
                      "first-request leakage, Decision 78; kept for comparability with v7",
        },
        "term_handshake_pcap": {
            "status": "covered" if handshake_pcap_known else "missing_client_pcap_or_gateway_log",
            "stats": stats_block([h[1] for h in handshake_pcap_known]) if handshake_pcap_known else None,
            "source": "client/run{NN}.pcap.gz (ClientHello..client Finished, no first-request leakage) "
                      "-- a second, independent measurement of the same term, pilot_acceptance.py "
                      "Criterion 11 is what should inform switching HANDSHAKE_SOURCE to this one",
        },
        "opin_processing_ms": {
            "status": "covered" if opin_processing_known else "missing_gateway_log",
            # p50_ms per run, pooled into the same median/min/max/bootstrap
            # block as every other v8 metric -- NOT the raw per-request
            # values (those live in calls.jsonl's own latency_ms already).
            "stats": stats_block([o["p50_ms"] for o in opin_processing_known]) if opin_processing_known else None,
            "requests_logged_per_run": sorted({o["requests_logged"] for o in opin_processing_known}),
        },
        "opinsize": None,
        "bytes_by_participant": bytes_by_participant([c for calls in agg_calls_per_run for c in calls]) if agg_calls_per_run else None,
        "latency_per_endpoint_ms": latency_per_endpoint([c for calls in agg_calls_per_run for c in calls]) if agg_calls_per_run else None,
        "rtt_and_loss": {
            "n_samples": len(ping_samples),
            "rtt_avg_ms": stats_block([p["rtt_avg_ms"] for p in ping_samples if "rtt_avg_ms" in p]) if ping_samples else None,
            "loss_pct_upper_bound_max_from_ping": max((p["loss_pct_upper_bound"] for p in ping_samples if "loss_pct_upper_bound" in p), default=None) if ping_samples else None,
            "pcap_loss_signals": pcap_loss,
        } if (ping_samples or pcap_loss) else None,
        "cpu_server": cpu_server or None,
        "cpu_client": cpu_client or None,
    }

    if out["term_handshake"]["stats"] and out["term_handshake_pcap"]["stats"]:
        gw_med = out["term_handshake"]["stats"]["median"]
        pcap_med = out["term_handshake_pcap"]["stats"]["median"]
        out["term_handshake_gateway_vs_pcap_diff"] = {
            "diff_bytes": pcap_med - gw_med,
            "diff_pct": (pcap_med - gw_med) / gw_med * 100 if gw_med else None,
        }
    else:
        out["term_handshake_gateway_vs_pcap_diff"] = None

    if jwt_sums and jwk_results and pki_results:
        term_jwt_med = out["term_jwt"]["median"]
        term_jwk_med = out["term_jwk"]["median"]
        term_pki_med = out["term_pki"]["median"]
        # HANDSHAKE_SOURCE (module constant, top of file) picks gateway
        # or pcap -- default "gateway" for v7 comparability (Decision --
        # the countingConn boundary is a documented limitation, not
        # fixed); only switch on Luciano's own call per Criterion 11.
        handshake_block = out["term_handshake"] if HANDSHAKE_SOURCE == "gateway" else out["term_handshake_pcap"]
        if handshake_block["stats"]:
            term_hs_med = handshake_block["stats"]["median"]
            out["opinsize"] = {
                "status": "complete",
                "value_bytes": term_hs_med + term_jwt_med + term_jwk_med + term_pki_med,
                "handshake_source": HANDSHAKE_SOURCE,
            }
        else:
            out["opinsize"] = {
                "status": "incomplete_missing_term_handshake",
                "partial_value_bytes_excl_handshake": term_jwt_med + term_jwk_med + term_pki_med,
                "note": f"term_handshake (source={HANDSHAKE_SOURCE}) not covered for this run -- "
                        f"this is the sum of term_jwt+term_jwk+term_pki only, NOT the full OPINsize.",
            }
    return out


def build_consolidated(v8_latency_root):
    out = {"profiles": {}}
    for profile in PROFILES:
        exp_dir = v8_latency_root / PROFILE_TO_EXPERIMENT_DIR[profile]
        servers = discover_scenarios(exp_dir)
        if not servers:
            continue
        out["profiles"][profile] = {}
        for server, scenarios in servers.items():
            out["profiles"][profile][server] = {}
            for scenario in scenarios:
                result = consolidate_profile_scenario(exp_dir / server / scenario, profile)
                if result is not None:
                    out["profiles"][profile][server][scenario] = result
    return out


def render_report(data):
    lines = ["# v8 Consolidated Report (derived)", "",
             "Generated by `consolidate_v8.py` from `v8/latency/...`'s own raw run records.",
             "Field structure follows v7's own `Consolidated_Metrics_Report_FINAL.md` wherever",
             "v8's data supports it -- see `METRICS_COVERAGE.md` for exactly which fields and why.",
             ""]
    for profile, servers in data["profiles"].items():
        lines.append(f"## Profile: {profile}")
        for server, scenarios in servers.items():
            lines.append(f"### Server: {server}")
            for scenario, m in scenarios.items():
                lines.append(f"#### Scenario: {scenario} ({m['runs_used']} clean runs"
                              + (f", {m['runs_retried_excluded']} retried/excluded" if m["runs_retried_excluded"] else "") + ")")
                tf = m["t_fluxo_seconds"]
                if tf:
                    lines.append(f"- T_fluxo median: {tf['median']:.3f}s "
                                  f"(min {tf['min']:.3f}, max {tf['max']:.3f}, "
                                  f"bootstrap 95% CI {tf['bootstrap_median_ci95']})")
                lines.append(f"- call_count: {m['call_count']}")
                lines.append(f"- N_mTLS: {m['n_mtls']}  N_JWT: {m['n_jwt']}  N_JWK: {m['n_jwk']}  N_PKI: {m['n_pki']}")
                if m["opinsize"]:
                    if m["opinsize"]["status"] == "complete":
                        lines.append(f"- OPINsize: {m['opinsize']['value_bytes']:.0f} bytes")
                    else:
                        lines.append(f"- OPINsize: INCOMPLETE -- {m['opinsize']['note']} "
                                      f"(partial, excl. handshake: {m['opinsize']['partial_value_bytes_excl_handshake']:.0f} bytes)")
                if m["rtt_and_loss"]:
                    rtt = m["rtt_and_loss"]["rtt_avg_ms"]
                    lines.append(f"- RTT avg: {rtt['median']:.2f}ms (median of samples)" if rtt else "- RTT: no samples")
                    ping_loss = m["rtt_and_loss"]["loss_pct_upper_bound_max_from_ping"]
                    if ping_loss is not None:
                        lines.append(f"- Packet loss (ICMP ping upper bound): {ping_loss}%")
                    pl = m["rtt_and_loss"]["pcap_loss_signals"]
                    if pl:
                        if pl["loss_events"] == 0:
                            lines.append(f"- Packet loss (TCP pcap evidence, {pl['n_executions']} executions, "
                                          f"{pl['total_segments']} segments): 0 events observed -- "
                                          f"upper bound {pl['loss_pct_upper_bound_rule_of_three']}% (rule of three)")
                        else:
                            lines.append(f"- Packet loss (TCP pcap evidence, {pl['n_executions']} executions, "
                                          f"{pl['total_segments']} segments): {pl['loss_pct']}% "
                                          f"({pl['retransmissions']} retransmissions, {pl['out_of_order']} "
                                          f"out-of-order, {pl['duplicate_ack_events']} duplicate-ACK events)")
                lines.append("")
    return "\n".join(lines)


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    v8_latency_root = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    data = build_consolidated(v8_latency_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "consolidated.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "CONSOLIDATED_REPORT.md").write_text(render_report(data), encoding="utf-8")
    print(f"Wrote {out_dir / 'consolidated.json'} and {out_dir / 'CONSOLIDATED_REPORT.md'}")


if __name__ == "__main__":
    main()
