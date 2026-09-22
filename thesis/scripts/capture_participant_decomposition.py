"""
One-shot, non-statistical capture -- NOT part of the official size/latency
protocol (same category as thesis/results/v7/artifacts/). Runs one real,
complete flow per profile and records, for every one of the 28 calls, its
logical destination (host_header -- AS, RS, or Directory/PKI-CRL, the value
opin_flow.py itself uses to route the call, immune to the tls_kem_proxy
rewrite that collapses AS+RS into "Other" in classify_participant()) next to
its exact request/response byte count.

Why one execution is enough (not a new statistical sample): the v7 size
audit (thesis/scripts/audit_v7_from_raw.py) already proved 0.00% spread on
every size metric across 60 runs per profile (6 scenarios x 10 runs) --
every one of the 28 calls in a given profile produces byte-for-byte
identical output every single time. This capture does not re-measure
anything; it recovers, once, a per-call breakdown that already applies
identically to all 60 already-collected runs of each profile, because the
value it records is a deterministic property of the flow, not a sample of
a varying quantity. See thesis/results/v7/DECISIONS.md, Decision 10, for the
full argument and the reconciliation against the already-committed
bytes_by_participant totals.

Usage: python thesis/scripts/capture_participant_decomposition.py classic|pqc|hybrid
Writes thesis/results/v7/participant_decomposition_capture_<profile>.json
"""
import json
import os
import sys

profile = sys.argv[1]
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
os.environ["CRYPTO_PROFILE"] = profile

import opin_flow as of
import baseline_automation as ba

_orig_do_call = of.do_call


def _capturing_do_call(session, method, url, **kwargs):
    call, resp = _orig_do_call(session, method, url, **kwargs)
    call["host_header"] = kwargs.get("host_header")
    return call, resp


of.do_call = _capturing_do_call

proc = of.start_tls_kem_proxy(profile)
try:
    of.set_latency(0)
    insurance_calls = of.run_insurance_flow(profile)
    person_calls = of.run_person_flow(profile)
finally:
    of.stop_tls_kem_proxy(proc)

calls = insurance_calls + person_calls
print(f"{profile}: {len(calls)} calls captured")

# Real logical participant, from host_header (immune to the proxy rewrite),
# not from the physical URL classify_participant() would see under the proxy.
HOST_TO_PARTICIPANT = {
    of.AUTH_HOST: "AS",
    of.AUTH_MTLS_HOST_HEADER: "AS",
    of.API_HOST: "RS",
    of.DIRECTORY_HOST: "Directory/PKI-CRL",
}

rows = []
totals = {}
for c in calls:
    hh = c["host_header"]
    # PKI/CRL calls pass cert=None, host_header=DIRECTORY_HOST, but are
    # classified by path suffix in the official pipeline (classify_participant);
    # match that here for the one case where host_header alone would say
    # "Directory/PKI-CRL" instead of the pipeline's own finer label.
    participant = ba.classify_participant(c["full_uri"]) if c["endpoint"].endswith((".pem",)) else HOST_TO_PARTICIPANT.get(hh)
    if participant is None:
        raise RuntimeError(f"unrecognized host_header {hh!r} for endpoint {c['endpoint']!r} -- extend HOST_TO_PARTICIPANT")
    rows.append({
        "endpoint": c["endpoint"], "host_header": hh, "participant": participant,
        "request_bytes": c["request_bytes"], "response_bytes": c["response_bytes"],
        "method": c["method"], "src": c["src"],
    })
    t = totals.setdefault(participant, {"sent_bytes": 0, "received_bytes": 0, "count": 0})
    t["sent_bytes"] += c["response_bytes"]   # bytes THIS participant sends = the response
    t["received_bytes"] += c["request_bytes"]  # bytes THIS participant receives = the request
    t["count"] += 1

out = {
    "profile": profile,
    "n_calls": len(calls),
    "totals_by_participant": totals,
    "calls": rows,
}
out_dir = os.path.join(os.path.dirname(__file__), "..", "results", "v7")
out_path = os.path.join(out_dir, f"participant_decomposition_capture_{profile}.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print(f"Wrote {out_path}")
print(json.dumps(totals, indent=2))
