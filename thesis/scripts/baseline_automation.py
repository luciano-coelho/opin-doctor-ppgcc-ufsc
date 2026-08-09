"""
Baseline (classical cryptography) collection automation for the MockOPIN
Conformance Suite, for the doctoral thesis on PQC migration.

Runs the "happy path" modules (preflight + core/status) of the plans:
  - Insurance consents api test V3.0.0
  - person_test-plan_v2.0.0

Saves raw logs + aggregated metrics under thesis/results/experiment1 - Classic/{latency_ms}ms/
(latency_ms comes from the first CLI arg, matching thesis/scripts/set_latency.sh;
defaults to 0 for ad-hoc local runs). Reads config templates from thesis/config/.

Also collects two more data points added for Experiment 1: bytes exchanged
per OPIN participant (Client/AS/RS/Directory), isolated JWK sizes from any
/jwks response seen, and the mTLS-handshake-vs-OPIN-processing time split
recorded by the gateway itself (see mock-service-os/mock_mtls/main.go).
The gateway also reports the handshake's own wire-level byte size
(mtlsHandshakeBytes, via countingConn) -- the number expected to move most
under PQC, since clientCertBytes only covers one certificate in the chain.

Notes on the results:
- The "preflight" modules always end with result=FAILED: they call an
  internal suite condition (OpinCheckDirectoryDiscoveryUrl/ApiBase) that
  requires Raidiam's real Directory and can't be satisfied running fully
  local. It's "continue on failure", so the rest of the flow runs normally
  -- only the result label ends up FAILED even though the real traffic was
  captured in the log.
- The status/core modules may pause at status=WAITING waiting for a manual
  browser login + consent (see poll_until_terminal). The script prints the
  URL and keeps polling on its own until the suite detects the redirect --
  no manual confirmation step needed. IMPORTANT: open the printed link
  exactly ONCE and never reload/re-click it. Doing so replays an
  already-consumed request_uri/interaction and reliably produces
  INTERRUPTED/SessionNotFound (root-caused during Experiment 1 baseline
  testing; see also the views/error.ejs fix in mock-service-os/mock_as for
  the crash that used to hide this error behind a raw 500).
"""

import base64
import io
import json
import re
import statistics
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Paths relative to the script (not to cwd), so this works regardless of
# where the script is invoked from: thesis/scripts/baseline_automation.py -> thesis/
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
# Set for real in main() from the latency-scenario CLI arg; the module-level
# default here only matters for ad-hoc manual runs / imports (e.g. the
# report-regeneration snippet used once during the English translation pass).
OUTPUT_DIR = BASE_DIR / "results" / "experiment1 - Classic" / "0ms"

BASE_URL = "https://localhost:8443"
GATEWAY_CONTAINER = "insurance-server-lambdas-mtls-1"
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 600
TERMINAL_STATUSES = {"FINISHED", "INTERRUPTED"}

JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)?")

# Maps request URI host -> the OPIN participant that host represents, so
# request/response bytes can be attributed per participant (Experiment 1,
# step 4.1). Order matters: checked as substring membership against the
# host, first match wins.
PARTICIPANT_HOSTS = [
    (("auth.local", "matls-auth.local"), "AS"),
    (("api.local", "matls-api.local"), "RS"),
    (("directory",), "Directory"),
    (("sandbox.pki.opinbrasil.com.br",), "PKI/CRL"),
]

# Each plan has 5-11 modules (the rest are negative/error cases: expired
# token, invalid permission, client limits etc). We only run the two
# "happy" modules of each: preflight (validates certs/SSA) and the module
# that actually creates/queries a consent through the real API.
PLANS = [
    {
        "plan_name": "Insurance consents api test V3.0.0",
        "report_label": "consents_v3",
        "config_file": "config_template_consents_v3.json",
        "happy_path_modules": [
            "opin-consents_api_preflight_test-module_v3",
            "opin-consent-api-status-test-v3",
        ],
    },
    {
        "plan_name": "person_test-plan_v2.0.0",
        "report_label": "person_v2",
        "config_file": "config_template_person_v2.json",
        "happy_path_modules": [
            "opin-consents_api_preflight_test-module_v3",
            "person_api_core_test-module_v2.0.0",
        ],
    },
]


def api_get(path, **params):
    r = requests.get(f"{BASE_URL}{path}", params=params, verify=False, timeout=30)
    return r


def api_post(path, params=None, json_body=None):
    if json_body is None:
        r = requests.post(f"{BASE_URL}{path}", params=params, verify=False, timeout=30)
    else:
        r = requests.post(f"{BASE_URL}{path}", params=params, json=json_body, verify=False, timeout=30)
    return r


def create_plan(plan_name: str, config: dict):
    r = api_post("/api/plan", params={"planName": plan_name}, json_body=config)
    r.raise_for_status()
    data = r.json()
    return data["id"], data["modules"]


def start_module(plan_id: str, test_name: str):
    # IMPORTANT: when 'plan' is supplied, no request body may be sent
    # (the suite returns an empty-body 400 otherwise).
    r = api_post("/api/runner", params={"test": test_name, "plan": plan_id})
    r.raise_for_status()
    data = r.json()
    return data["id"]


def poll_until_terminal(test_id: str, module_label: str):
    # The /api/runner docs explicitly recommend using /api/info/{id} to
    # track the test, not /api/runner/{id} (which also exists but isn't
    # the documented path for this).
    started = time.time()
    already_printed_url = False
    while True:
        elapsed = time.time() - started
        if elapsed > POLL_TIMEOUT_SECONDS:
            print(f"  [{module_label}] TIMEOUT after {POLL_TIMEOUT_SECONDS}s, aborting polling.")
            return None

        r = api_get(f"/api/info/{test_id}")
        r.raise_for_status()
        info = r.json()
        status = info.get("status")
        result = info.get("result")
        print(f"  [{module_label}] status={status} result={result} ({int(elapsed)}s)")

        if status in TERMINAL_STATUSES:
            return info

        if status == "WAITING" and not already_printed_url:
            br = api_get(f"/api/runner/browser/{test_id}")
            if br.status_code == 200:
                try:
                    browser_info = br.json()
                except ValueError:
                    browser_info = br.text
                # The real response uses "urls" (a list) -- we keep the
                # "url"/"redirect" fallback in case the suite changes the
                # format in a future version.
                urls = []
                if isinstance(browser_info, dict):
                    urls = browser_info.get("urls") or []
                    if not urls:
                        single = browser_info.get("url") or browser_info.get("redirect")
                        if single:
                            urls = [single]
                elif isinstance(browser_info, str) and browser_info.startswith("http"):
                    urls = [browser_info]
                if urls:
                    print("\n  " + "=" * 70)
                    print(f"  >>> MANUAL INTERACTION REQUIRED for [{module_label}]")
                    for u in urls:
                        print(f"  >>> Open in browser: {u}")
                    print("  >>> Protocol: open the link ONCE, log in, select all")
                    print("  >>> permissions and confirm, wait for the redirect (even if")
                    print("  >>> the final landing page shows a connection error), then")
                    print("  >>> come back here. Do NOT reload, reopen, or re-click the link:")
                    print("  >>> a second hit on an already-used request_uri/interaction is")
                    print("  >>> rejected by design and was the root cause of the earlier")
                    print("  >>> INTERRUPTED/SessionNotFound failures.")
                    print("  " + "=" * 70 + "\n")
                    # No input() here: this script runs unattended/backgrounded
                    # (no TTY to read a real ENTER from), so synchronization
                    # relies purely on polling, same as before. The printed
                    # protocol above is what prevents the duplicate-navigation
                    # failure -- polling already detects the status change the
                    # moment the real redirect/callback lands, with no need to
                    # wait for a manual confirmation signal here.
                    already_printed_url = True

        time.sleep(POLL_INTERVAL_SECONDS)


def export_log(test_id: str):
    """GET /api/log/export/{id} returns a ZIP containing test-log-<id>.json."""
    r = api_get(f"/api/log/export/{test_id}")
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        names = zf.namelist()
        json_names = [n for n in names if n.endswith(".json")]
        if not json_names:
            raise RuntimeError(f"No .json found in the export ZIP: {names}")
        with zf.open(json_names[0]) as f:
            return json.load(f)


def run_module(plan_id: str, plan_alias: str, test_name: str):
    print(f"\n=== Module: {test_name} (plan {plan_alias}) ===")
    test_id = start_module(plan_id, test_name)
    print(f"  test_id={test_id}")
    info = poll_until_terminal(test_id, test_name)
    if info is None:
        print(f"  [{test_name}] no terminal status, skipping export.")
        return None

    log_export = export_log(test_id)
    # The export wraps the real log entries inside log_export["results"],
    # alongside metadata (exportedAt, testInfo etc). We keep the full dict
    # in the file (raw JSON required by the thesis) but only the "results"
    # list is used for parsing.
    log_entries = log_export.get("results", []) if isinstance(log_export, dict) else log_export
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_name = test_name.replace("/", "_")
    out_path = OUTPUT_DIR / f"{plan_alias}__{safe_name}_{timestamp}.json"
    out_path.write_text(json.dumps(log_export, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  log saved to {out_path} ({len(log_entries)} entries)")

    return {
        "plan_alias": plan_alias,
        "module": test_name,
        "test_id": test_id,
        "status": info.get("status"),
        "result": info.get("result"),
        "log_file": str(out_path),
        "log": log_entries,
    }


def header_bytes(headers: dict) -> int:
    # Approximation of the "on the wire" header size ("Name: value\r\n"
    # format). Doesn't include the request/status line or TLS/TCP overhead
    # -- consistent enough to compare classical vs PQC, not an exact
    # network byte counter.
    if not headers:
        return 0
    total = 0
    for k, v in headers.items():
        total += len(f"{k}: {v}\r\n".encode("utf-8"))
    return total


def extract_jwts(*texts):
    # Scans request/response body + the Authorization header for any string
    # in JWT format (client_assertion, request object, access/id_token).
    # The size of these tokens is the central data point for the thesis
    # (comparing classical vs PQC signature size).
    found = []
    for text in texts:
        if not text:
            continue
        if isinstance(text, dict):
            text = json.dumps(text)
        for m in JWT_RE.finditer(text):
            token = m.group(0)
            if len(token) > 20:
                found.append(token)
    return found


def classify_participant(uri: str) -> str:
    """Maps a request URI to the OPIN participant it targets (AS/RS/Directory/...)."""
    host = urlparse(uri).netloc or uri
    for hostnames, participant in PARTICIPANT_HOSTS:
        if any(h in host for h in hostnames):
            return participant
    return "Other"


def b64url_decode_len(value: str) -> int:
    """Byte length of a base64url-encoded JWK field (n, x, y, ...), padded as needed."""
    padded = value + "=" * (-len(value) % 4)
    return len(base64.urlsafe_b64decode(padded))


def extract_jwk_sizes(response_body):
    """
    Parses a /jwks-style response body and returns the size in bytes of each
    individual public key: the modulus (n) for RSA, x+y for EC. This is the
    isolated key-material size, distinct from the JWT sizes extract_jwts()
    finds elsewhere (a JWT's header/claims add overhead on top of whichever
    key signed it).
    """
    if not response_body:
        return []
    try:
        data = json.loads(response_body)
    except (ValueError, TypeError):
        return []
    keys = data.get("keys") if isinstance(data, dict) else None
    if not isinstance(keys, list):
        return []

    sizes = []
    for key in keys:
        if not isinstance(key, dict):
            continue
        kty = key.get("kty")
        try:
            if kty == "RSA" and "n" in key:
                size_bytes = b64url_decode_len(key["n"])
            elif kty == "EC" and "x" in key and "y" in key:
                size_bytes = b64url_decode_len(key["x"]) + b64url_decode_len(key["y"])
            else:
                continue
        except Exception:
            continue
        sizes.append({
            "kid": key.get("kid"),
            "kty": kty,
            "use": key.get("use"),
            "size_bytes": size_bytes,
        })
    return sizes


def collect_gateway_metrics(since: datetime, until: datetime = None):
    """
    Reads the mTLS gateway's own access log (docker logs, JSON lines -- see
    Experiment 1 step 2's instrumentation in mock-service-os/mock_mtls/main.go)
    for everything logged since `since` (and, if given, before `until`), and
    extracts the mtlsHandshakeDurationMs / opinDurationMs split per request.
    This is a second, independent vantage point on latency (measured at the
    gateway) alongside the Conformance Suite's own client-side timestamps
    used elsewhere in this script -- it is NOT joined/correlated to
    individual parse_calls() entries, since the two logs have no shared
    request ID to match on.

    `until` matters for retroactive recomputation (e.g. re-collecting a past
    scenario's gateway metrics after the fact): without it, an open-ended
    `--since` picks up every later scenario's traffic too.
    """
    # Must keep the UTC offset: docker's --since/--until parse a bare
    # "YYYY-MM-DDTHH:MM:SS" (no offset) as local time, which would silently
    # shift the window by however many hours this machine's timezone differs
    # from UTC.
    cmd = ["docker", "logs", "--since", since.isoformat(), GATEWAY_CONTAINER]
    if until is not None:
        cmd = ["docker", "logs", "--since", since.isoformat(), "--until", until.isoformat(), GATEWAY_CONTAINER]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (subprocess.SubprocessError, OSError) as e:
        print(f"  [gateway metrics] could not read {GATEWAY_CONTAINER} logs: {e}")
        return []

    entries = []
    for line in (result.stdout + result.stderr).splitlines():
        line = line.strip()
        if not line or '"msg":"access log"' not in line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        entries.append({
            "host": entry.get("host"),
            "request": entry.get("request"),
            "status": entry.get("status"),
            "opinDurationMs": entry.get("opinDurationMs"),
            "mtlsHandshakeDurationMs": entry.get("mtlsHandshakeDurationMs"),
            "mtlsHandshakeBytes": entry.get("mtlsHandshakeBytes"),
            "tlsVersion": entry.get("tlsVersion"),
            "cipherSuite": entry.get("cipherSuite"),
            "clientCertBytes": entry.get("clientCertBytes"),
            # remoteIP:port identifies the physical TCP connection -- see
            # compute_metrics()'s handshake dedup, which needs this to avoid
            # counting one connection's handshake once per request it served.
            "remoteIP": entry.get("remoteIP"),
        })
    return entries


def parse_calls(log_entries):
    """Pairs consecutive request/response log entries into HTTP 'calls'."""
    # The suite's log has no explicit ID linking request to response: each
    # HTTP call becomes two separate entries (msg="HTTP request" / "HTTP
    # response") in the order they happened. Empirically the response
    # always comes right after its matching request, so we pair by
    # adjacency in the array instead of by some correlation field.
    calls = []
    i = 0
    n = len(log_entries)
    while i < n:
        entry = log_entries[i]
        if entry.get("http") == "request":
            req = entry
            resp = None
            if i + 1 < n and log_entries[i + 1].get("http") == "response":
                resp = log_entries[i + 1]
                i += 1

            req_headers = req.get("request_headers") or {}
            req_body = req.get("request_body") or ""
            req_bytes = header_bytes(req_headers) + len(req_body.encode("utf-8"))

            resp_headers = (resp or {}).get("response_headers") or {}
            resp_body = (resp or {}).get("response_body") or ""
            resp_bytes = header_bytes(resp_headers) + len(str(resp_body).encode("utf-8"))

            latency_ms = None
            if resp is not None and "time" in req and "time" in resp:
                latency_ms = resp["time"] - req["time"]

            uri = req.get("request_uri", "")
            endpoint = urlparse(uri).path or uri
            participant = classify_participant(uri)

            jwts = extract_jwts(req_body, req_headers.get("Authorization"), resp_body)

            jwk_sizes = []
            if endpoint.rstrip("/").endswith("jwks"):
                jwk_sizes = extract_jwk_sizes(resp_body)

            calls.append({
                "endpoint": endpoint,
                "full_uri": uri,
                "method": req.get("request_method"),
                "src": req.get("src"),
                # "Client" always sends the request and receives the response;
                # `participant` is who's on the other end of this call (who
                # received the request bytes and sent the response bytes).
                "participant": participant,
                "request_bytes": req_bytes,
                "response_bytes": resp_bytes,
                "total_bytes": req_bytes + resp_bytes,
                "latency_ms": latency_ms,
                "authorization_header": req_headers.get("Authorization"),
                "jwts": jwts,
                "jwt_sizes": [len(j) for j in jwts],
                "jwk_sizes": jwk_sizes,
                "status_code": (resp or {}).get("response_status_code"),
            })
        i += 1
    return calls


def percentile(values, pct):
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * (pct / 100)
    f = int(k)
    c = min(f + 1, len(values) - 1)
    if f == c:
        return values[f]
    return values[f] + (values[c] - values[f]) * (k - f)


def latency_stats(values):
    """Shared mean/P50/P95/P99 helper -- used per-endpoint (4.4) and for the
    gateway-side handshake-vs-OPIN split (4.3), so both go through the same
    percentile math."""
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return {
        "count": len(clean),
        "mean_ms": round(statistics.mean(clean), 2),
        "p50_ms": round(percentile(clean, 50), 2),
        "p95_ms": round(percentile(clean, 95), 2),
        "p99_ms": round(percentile(clean, 99), 2),
    }


def size_stats(values):
    """Same as latency_stats, but for byte-size samples (mtlsHandshakeBytes)
    -- separate from latency_stats so the returned keys read as sizes
    (mean_bytes/p50_bytes/...) rather than durations."""
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return {
        "count": len(clean),
        "mean_bytes": round(statistics.mean(clean), 2),
        "p50_bytes": round(percentile(clean, 50), 2),
        "p95_bytes": round(percentile(clean, 95), 2),
        "p99_bytes": round(percentile(clean, 99), 2),
    }


def filter_handshake_outliers(values, multiplier=3):
    """
    Drops mTLS handshake samples more than `multiplier` x the scenario's
    typical (median) handshake time -- e.g. a keep-alive connection that
    stays open across a scenario boundary reports the SAME cached handshake
    duration for every request it serves, so the real Experiment 1 data has
    small *clusters* of identical extreme values (four ~29.4s samples in the
    14ms scenario, six in 30ms -- one physical connection's genuinely slow
    handshake, replayed by every request that reused it), not lone outliers.

    P99 doesn't work as the reference here even applied iteratively/
    leave-one-out: with dozens of samples per scenario, comparing the
    largest value against "the rest" still leaves the other members of the
    same duplicate cluster in the reference set, which drags that P99 up
    with it and the cluster clears its own inflated threshold. The median is
    unmoved by a handful of correlated duplicates as long as they're a
    minority of the sample (true here: 4-6 out of ~55-90), so it's used as
    the base instead. Applied iteratively since removing part of a cluster
    can lower the median enough to catch the rest of it.
    """
    clean = [v for v in values if v is not None]
    total_dropped = 0
    while clean:
        threshold = statistics.median(clean) * multiplier
        filtered = [v for v in clean if v <= threshold]
        dropped = len(clean) - len(filtered)
        if dropped == 0:
            break
        clean = filtered
        total_dropped += dropped
    return clean, total_dropped


def dedupe_handshake_samples_by_connection(gateway_entries, field):
    """
    One handshake sample per physical TCP connection (remoteIP:port), not
    one per HTTP request. mock_mtls/main.go's connStateHandshakeLogger
    records mtlsHandshakeDurationMs/mtlsHandshakeBytes exactly once per
    connection (cached at handshake completion) and every subsequent
    request that reuses that connection's keep-alive reports the identical
    cached value -- so a naive "one sample per access-log line" list isn't
    a fair per-handshake distribution, it's request-count-weighted: a
    connection that happened to carry many requests dominates the
    percentiles, a connection that carried one request barely counts.

    This was harmless when the client rarely reused connections (true of
    Experiment 1's Conformance Suite runs, where per-request and
    per-connection counts were close), but opin_flow.py's shared-Session
    fix (see thesis/scripts/opin_flow.py, do_call()) makes connection reuse
    the norm, not the exception -- confirmed empirically on a live 0ms run:
    64 access-log entries over only 19 distinct connections, naive
    per-request P50 9529 bytes vs. true per-connection P50 11455 bytes.

    Entries missing remoteIP (older logs predating that field) fall back to
    being counted individually rather than silently dropped, matching the
    pre-dedup behavior for just that entry.
    """
    seen_connections = set()
    values = []
    for entry in gateway_entries:
        value = entry.get(field)
        if value is None:
            continue
        remote = entry.get("remoteIP")
        if remote is None:
            values.append(value)
            continue
        if remote in seen_connections:
            continue
        seen_connections.add(remote)
        values.append(value)
    return values


def compute_metrics(all_calls, gateway_entries=None, latency_scenario_ms=None, client_cert_bytes=None):
    """
    client_cert_bytes, when given, restricts gateway_entries (and therefore
    every gateway_metrics figure below -- requests_logged, handshake_ms,
    handshake_bytes, opin_processing_ms) to connections whose
    clientCertBytes exactly matches it, before any stats are computed.

    Opt-in and None by default: collect_gateway_metrics() captures every
    request the gateway sees, not just the ones the measuring client
    itself made -- e.g. the AS's own InsurerAdapter calls the RS
    server-side (to render the consent screen) using a separate
    "transport_certificate" loaded from SSM, unrelated to CRYPTO_PROFILE
    and always classical, over the same gateway, polluting handshake
    percentiles with the wrong population -- exactly the thesis's most
    latency/algorithm-sensitive metric.

    This used to filter by remoteIP prefix (the host-gateway address) on
    the theory that "connections from the host" == "connections this
    script made". That's wrong: Docker Desktop's NAT rewrites the source
    address of *every* host-to-container connection to the same internal
    gateway IP, regardless of which process on the host initiated it --
    confirmed empirically when a stray classical-cert connection (from an
    unrelated command run on the same host during the same investigation)
    showed up under the "filtered" IP in a pqc run, blending clusters again
    (10-12KB classical mixed with 15-18KB pqc, this time within the
    "filtered" set). clientCertBytes identifies the actual key material
    presented -- 1494 bytes for the classical client_one.crt, 2953 for
    client_one_pqc.crt (both confirmed via each cert's own DER length) --
    which is what the measurement actually needs to isolate, independent of
    network topology. Left unfiltered (None) by default since it's
    opin_flow.py-specific; a Conformance-Suite-driven run (v1,
    baseline_automation.py's own CS-driving path) has no equivalent
    single-client-cert assumption to make.
    """
    gateway_entries = gateway_entries or []
    if client_cert_bytes is not None:
        gateway_entries = [
            e for e in gateway_entries
            if e.get("clientCertBytes") == client_cert_bytes
        ]

    total_bytes = sum(c["total_bytes"] for c in all_calls)
    total_requests = len(all_calls)

    # 4.4: latency P50/P95/P99 per endpoint, as measured client-side by the
    # Conformance Suite (request_uri path -> list of latencies -> stats).
    by_endpoint = {}
    for c in all_calls:
        by_endpoint.setdefault(c["endpoint"], []).append(c["latency_ms"])
    latency_per_endpoint = {
        endpoint: stats
        for endpoint, latencies in by_endpoint.items()
        if (stats := latency_stats(latencies)) is not None
    }

    # 4.1: bytes sent/received per participant. Every call has two legs: the
    # Client sending the request and receiving the response, and the
    # counterpart participant (AS/RS/Directory/...) doing the reverse.
    bytes_by_participant = {}
    for c in all_calls:
        client = bytes_by_participant.setdefault("Client", {"sent_bytes": 0, "received_bytes": 0})
        client["sent_bytes"] += c["request_bytes"]
        client["received_bytes"] += c["response_bytes"]

        other = bytes_by_participant.setdefault(c["participant"], {"sent_bytes": 0, "received_bytes": 0})
        other["sent_bytes"] += c["response_bytes"]
        other["received_bytes"] += c["request_bytes"]

    all_jwt_sizes = []
    all_jwk_sizes = []
    for c in all_calls:
        all_jwt_sizes.extend(c["jwt_sizes"])
        all_jwk_sizes.extend(c["jwk_sizes"])

    # 4.3: handshake vs. OPIN-processing time, as measured at the gateway
    # itself (see collect_gateway_metrics) -- an independent vantage point
    # from the client-side latency_per_endpoint above. Handshake samples are
    # deduplicated per physical connection (see dedupe_handshake_samples_by_connection)
    # and then outlier-filtered (see filter_handshake_outliers); OPIN
    # processing time is neither, since it's a genuine per-request measure
    # with no reused-connection artifact.
    handshake_ms_raw = dedupe_handshake_samples_by_connection(gateway_entries, "mtlsHandshakeDurationMs")
    handshake_ms, handshake_outliers_dropped = filter_handshake_outliers(handshake_ms_raw)
    opin_ms = [e["opinDurationMs"] for e in gateway_entries if e.get("opinDurationMs") is not None]
    # Wire-level size of the mTLS handshake itself (ClientHello..Finished),
    # counted at the raw net.Conn level by the gateway (see countingConn in
    # mock_mtls/main.go) -- this is the number that's expected to grow
    # sharply under PQC (larger KEM public keys/ciphertexts, bigger
    # signatures), unlike clientCertBytes which only covers one certificate.
    # Cached per-connection just like the duration, so it gets the same dedup.
    handshake_bytes_raw = dedupe_handshake_samples_by_connection(gateway_entries, "mtlsHandshakeBytes")
    handshake_bytes, handshake_bytes_outliers_dropped = filter_handshake_outliers(handshake_bytes_raw)
    gateway_metrics = {
        "requests_logged": len(gateway_entries),
        "handshake_ms": latency_stats(handshake_ms),
        "handshake_outliers_dropped": handshake_outliers_dropped,
        "handshake_bytes": size_stats(handshake_bytes),
        "handshake_bytes_outliers_dropped": handshake_bytes_outliers_dropped,
        "opin_processing_ms": latency_stats(opin_ms),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latency_scenario_ms": latency_scenario_ms,
        "total_bytes_exchanged": total_bytes,
        "total_requests": total_requests,
        "latency_per_endpoint": latency_per_endpoint,
        "bytes_by_participant": bytes_by_participant,
        "jwt_sizes_bytes": all_jwt_sizes,
        "jwt_count": len(all_jwt_sizes),
        "jwt_size_avg_bytes": round(statistics.mean(all_jwt_sizes), 2) if all_jwt_sizes else None,
        "jwt_size_max_bytes": max(all_jwt_sizes) if all_jwt_sizes else None,
        "jwk_sizes": all_jwk_sizes,
        "gateway_metrics": gateway_metrics,
    }


def write_report_md(metrics, module_results, path: Path):
    lines = []
    lines.append("# Baseline Report (Classical Cryptography)")
    lines.append("")
    lines.append(f"Generated at: {metrics['generated_at']}")
    if metrics.get("latency_scenario_ms") is not None:
        lines.append(f"Latency scenario: **{metrics['latency_scenario_ms']}ms** (see thesis/scripts/set_latency.sh)")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(f"- Total bytes exchanged across the full flow (classical OPINsize): **{metrics['total_bytes_exchanged']} bytes**")
    lines.append(f"- Total HTTP requests: **{metrics['total_requests']}**")
    lines.append(f"- JWTs found: **{metrics['jwt_count']}**")
    if metrics["jwt_size_avg_bytes"] is not None:
        lines.append(f"- Average JWT size: **{metrics['jwt_size_avg_bytes']} bytes** (max: {metrics['jwt_size_max_bytes']} bytes)")
    lines.append("")
    lines.append("## Modules run")
    lines.append("")
    lines.append("| Plan | Module | Status | Result | Log |")
    lines.append("|---|---|---|---|---|")
    for m in module_results:
        if m is None:
            continue
        lines.append(f"| {m['plan_alias']} | {m['module']} | {m['status']} | {m['result']} | `{m['log_file']}` |")
    lines.append("")
    lines.append("## Latency per endpoint (client-side, Conformance Suite)")
    lines.append("")
    lines.append("| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |")
    lines.append("|---|---|---|---|---|---|")
    for endpoint, stats in sorted(metrics["latency_per_endpoint"].items()):
        lines.append(
            f"| `{endpoint}` | {stats['count']} | {stats['mean_ms']} | {stats['p50_ms']} | {stats['p95_ms']} | {stats['p99_ms']} |"
        )
    lines.append("")

    lines.append("## mTLS handshake vs. OPIN processing time (gateway-side)")
    lines.append("")
    gw = metrics["gateway_metrics"]
    lines.append(f"Requests logged by the gateway in this run: **{gw['requests_logged']}**")
    lines.append("")
    lines.append("| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |")
    lines.append("|---|---|---|---|---|---|")
    for label, stats in (("mTLS handshake", gw["handshake_ms"]), ("OPIN processing", gw["opin_processing_ms"])):
        if stats is None:
            lines.append(f"| {label} | 0 | - | - | - | - |")
        else:
            lines.append(
                f"| {label} | {stats['count']} | {stats['mean_ms']} | {stats['p50_ms']} | {stats['p95_ms']} | {stats['p99_ms']} |"
            )
    lines.append("")
    lines.append(
        "Note: for keep-alive connections, only the first request on a given "
        "connection pays the handshake cost -- every subsequent request on "
        "that same connection reports the same (already-past) handshake "
        "timestamps, which is expected."
    )
    lines.append(
        f"{gw.get('handshake_outliers_dropped', 0)} handshake duration "
        "sample(s) discarded as outliers (> 3x this scenario's median; see "
        "filter_handshake_outliers)."
    )
    lines.append("")

    lines.append("### mTLS handshake size (wire bytes)")
    lines.append("")
    lines.append(
        "Total bytes read+written at the raw TCP level during the "
        "handshake (ClientHello through Finished), counted below "
        "crypto/tls so it captures the actual negotiated messages "
        "regardless of algorithm -- see countingConn in "
        "mock-service-os/mock_mtls/main.go. This is the number expected to "
        "grow substantially under PQC (larger KEM public keys/ciphertexts "
        "and signatures), unlike clientCertBytes above which is only one "
        "certificate."
    )
    lines.append("")
    hb = gw.get("handshake_bytes")
    if hb is None:
        lines.append("No handshake byte-size samples in this run.")
    else:
        lines.append("| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |")
        lines.append("|---|---|---|---|---|")
        lines.append(f"| {hb['count']} | {hb['mean_bytes']} | {hb['p50_bytes']} | {hb['p95_bytes']} | {hb['p99_bytes']} |")
        lines.append("")
        lines.append(
            f"{gw.get('handshake_bytes_outliers_dropped', 0)} handshake "
            "byte-size sample(s) discarded as outliers (same filter/"
            "reasoning as the duration outliers above)."
        )
    lines.append("")

    lines.append("## Bytes by participant")
    lines.append("")
    lines.append(
        "**Client** is the Conformance Suite itself (the OPIN client in "
        "this test harness) -- it is one of the two parties on every call "
        "this table is built from, so its sent+received always equals the "
        "scenario's total bytes exchanged by construction, not a "
        "measurement of a separate category. AS/RS/Directory/PKI-CRL are "
        "the actual breakdown: who specifically the client was talking to "
        "on each call, and they sum to the same total."
    )
    lines.append("")
    lines.append("| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |")
    lines.append("|---|---|---|---|")
    for participant, b in sorted(metrics["bytes_by_participant"].items()):
        label = "Client (test tool, total traffic)" if participant == "Client" else participant
        lines.append(f"| {label} | {b['sent_bytes']} | {b['received_bytes']} | {b['sent_bytes'] + b['received_bytes']} |")
    lines.append("")

    lines.append("## JWK sizes found (isolated public key material)")
    lines.append("")
    if metrics["jwk_sizes"]:
        lines.append("| # | kid | kty | use | Size (bytes) |")
        lines.append("|---|---|---|---|---|")
        for idx, jwk in enumerate(metrics["jwk_sizes"], start=1):
            lines.append(f"| {idx} | {jwk.get('kid')} | {jwk.get('kty')} | {jwk.get('use')} | {jwk['size_bytes']} |")
    else:
        lines.append("No /jwks endpoint response found in this run.")
    lines.append("")

    lines.append("## JWT sizes found")
    lines.append("")
    if metrics["jwt_sizes_bytes"]:
        lines.append("| # | Size (bytes) |")
        lines.append("|---|---|")
        for idx, size in enumerate(metrics["jwt_sizes_bytes"], start=1):
            lines.append(f"| {idx} | {size} |")
    else:
        lines.append("No JWT found in the payloads.")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_latency_arg():
    """
    First CLI arg is the latency scenario in ms (matches thesis/scripts/set_latency.sh);
    defaults to 0 for ad-hoc local runs. Determines where results are saved
    (thesis/results/experiment1 - Classic/{ms}ms/) -- it does NOT itself apply the tc
    delay, that's set_latency.sh's job (run separately, see Experiment 1
    step 5).
    """
    if len(sys.argv) > 1:
        try:
            return int(sys.argv[1])
        except ValueError:
            print(f"Invalid latency argument {sys.argv[1]!r}, expected an integer (ms).", file=sys.stderr)
            sys.exit(1)
    return 0


def main():
    global OUTPUT_DIR
    latency_ms = parse_latency_arg()
    OUTPUT_DIR = BASE_DIR / "results" / "experiment1 - Classic" / f"{latency_ms}ms"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Latency scenario: {latency_ms}ms -> results go to {OUTPUT_DIR}")

    run_start = datetime.now(timezone.utc)
    module_results = []
    all_calls = []

    for plan_spec in PLANS:
        config = json.loads((CONFIG_DIR / plan_spec["config_file"]).read_text(encoding="utf-8"))
        # plan_alias is just a label used to organize files/report. The
        # config["alias"] field must literally be "mock" for both plans: the
        # suite builds the redirect_uri as https://.../test/a/{alias}/callback,
        # and the only redirect_uri registered for client_one is
        # ".../test/a/mock/callback" (hardcoded in software_statement.json).
        # A different alias causes
        # "redirect_uri did not match any of the client's registered redirect_uris".
        plan_alias = plan_spec["report_label"]

        print(f"\n############ Plan: {plan_spec['plan_name']} (alias={plan_alias}) ############")
        plan_id, _modules = create_plan(plan_spec["plan_name"], config)
        print(f"plan_id={plan_id}")

        for module_name in plan_spec["happy_path_modules"]:
            result = run_module(plan_id, plan_alias, module_name)
            module_results.append(result)
            if result is not None:
                all_calls.extend(parse_calls(result["log"]))

    print("\nCollecting gateway handshake/OPIN-processing metrics...")
    gateway_entries = collect_gateway_metrics(run_start)
    print(f"  {len(gateway_entries)} gateway access-log entries captured since {run_start.isoformat()}")

    metrics = compute_metrics(all_calls, gateway_entries=gateway_entries, latency_scenario_ms=latency_ms)
    metrics_path = OUTPUT_DIR / "baseline_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nMetrics saved to {metrics_path}")

    report_path = OUTPUT_DIR / "BASELINE_REPORT.md"
    write_report_md(metrics, module_results, report_path)
    print(f"Report saved to {report_path}")


if __name__ == "__main__":
    main()
