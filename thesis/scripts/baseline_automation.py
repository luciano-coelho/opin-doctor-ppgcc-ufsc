"""
Baseline (classical cryptography) collection automation for the MockOPIN
Conformance Suite, for the doctoral thesis on PQC migration.

Runs the "happy path" modules (preflight + core/status) of the plans:
  - Insurance consents api test V3.0.0
  - person_test-plan_v2.0.0

Saves raw logs + aggregated metrics under thesis/results/baseline/.
Reads config templates from thesis/config/.

Notes on the results:
- The "preflight" modules always end with result=FAILED: they call an
  internal suite condition (OpinCheckDirectoryDiscoveryUrl/ApiBase) that
  requires Raidiam's real Directory and can't be satisfied running fully
  local. It's "continue on failure", so the rest of the flow runs normally
  -- only the result label ends up FAILED even though the real traffic was
  captured in the log.
- The status/core modules may pause at status=WAITING waiting for a manual
  browser login + consent (see poll_until_terminal). The script prints the
  URL and keeps polling on its own until the suite detects the redirect.
"""

import io
import json
import re
import statistics
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
OUTPUT_DIR = BASE_DIR / "results" / "baseline"

BASE_URL = "https://localhost:8443"
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 600
TERMINAL_STATUSES = {"FINISHED", "INTERRUPTED"}

JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)?")

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
                    # No input() on purpose: polling already detects the status
                    # change as soon as the browser completes the real redirect,
                    # so there's no need (and no way, in a non-interactive
                    # terminal) to wait for manual confirmation here.
                    print("  >>> Polling continues automatically; no need to confirm here.")
                    print("  " + "=" * 70 + "\n")
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

            jwts = extract_jwts(req_body, req_headers.get("Authorization"), resp_body)

            calls.append({
                "endpoint": endpoint,
                "full_uri": uri,
                "method": req.get("request_method"),
                "src": req.get("src"),
                "request_bytes": req_bytes,
                "response_bytes": resp_bytes,
                "total_bytes": req_bytes + resp_bytes,
                "latency_ms": latency_ms,
                "authorization_header": req_headers.get("Authorization"),
                "jwts": jwts,
                "jwt_sizes": [len(j) for j in jwts],
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


def compute_metrics(all_calls):
    total_bytes = sum(c["total_bytes"] for c in all_calls)
    total_requests = len(all_calls)

    by_endpoint = {}
    for c in all_calls:
        by_endpoint.setdefault(c["endpoint"], []).append(c["latency_ms"])

    latency_per_endpoint = {}
    for endpoint, latencies in by_endpoint.items():
        clean = [l for l in latencies if l is not None]
        if not clean:
            continue
        latency_per_endpoint[endpoint] = {
            "count": len(clean),
            "mean_ms": round(statistics.mean(clean), 2),
            "p50_ms": round(percentile(clean, 50), 2),
            "p95_ms": round(percentile(clean, 95), 2),
            "p99_ms": round(percentile(clean, 99), 2),
        }

    all_jwt_sizes = []
    for c in all_calls:
        all_jwt_sizes.extend(c["jwt_sizes"])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_bytes_exchanged": total_bytes,
        "total_requests": total_requests,
        "latency_per_endpoint": latency_per_endpoint,
        "jwt_sizes_bytes": all_jwt_sizes,
        "jwt_count": len(all_jwt_sizes),
        "jwt_size_avg_bytes": round(statistics.mean(all_jwt_sizes), 2) if all_jwt_sizes else None,
        "jwt_size_max_bytes": max(all_jwt_sizes) if all_jwt_sizes else None,
    }


def write_report_md(metrics, module_results, path: Path):
    lines = []
    lines.append("# Baseline Report (Classical Cryptography)")
    lines.append("")
    lines.append(f"Generated at: {metrics['generated_at']}")
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
    lines.append("## Latency per endpoint")
    lines.append("")
    lines.append("| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |")
    lines.append("|---|---|---|---|---|---|")
    for endpoint, stats in sorted(metrics["latency_per_endpoint"].items()):
        lines.append(
            f"| `{endpoint}` | {stats['count']} | {stats['mean_ms']} | {stats['p50_ms']} | {stats['p95_ms']} | {stats['p99_ms']} |"
        )
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


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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

    metrics = compute_metrics(all_calls)
    metrics_path = OUTPUT_DIR / "baseline_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nMetrics saved to {metrics_path}")

    report_path = OUTPUT_DIR / "BASELINE_REPORT.md"
    write_report_md(metrics, module_results, report_path)
    print(f"Report saved to {report_path}")


if __name__ == "__main__":
    main()
