"""
One-shot, non-statistical capture for v8 -- NOT part of the official
720-execution protocol (same category as thesis/results/v8/artifacts/).
Same mechanism as thesis/scripts/capture_participant_decomposition.py
(v7, Decision 10): runs one real, complete flow per profile against the
REAL remote gateway (REMOTE_GATEWAY_HOST) and records, for every call,
its logical destination (host_header: AS, RS, or Directory/PKI-CRL) next
to its exact request/response byte count -- the information v8's own
official pipeline's classify_participant() collapses into "Other" (every
call physically goes through the same REMOTE_GATEWAY_HOST address) plus
"PKI/CRL" (the one case already path-distinguished).

Why one execution per profile is enough (not a new statistical sample):
v8's own audit (thesis/scripts/audit_v8_from_raw.py) already confirms
OPINsize and its 4 terms (handshake_bytes, JWT_size, JWK_PK_size,
PKI_bytes) are constant across all 8 routes and, within a route, this is
a deterministic property of the flow (same calls, same order, same
payload shape every time) -- this capture reveals a decomposition of a
value already implicit in the 720 already-collected executions, it does
not re-measure anything.

Usage (run ON a client instance that already has ~/thesis/scripts/
deployed, with REMOTE_GATEWAY_HOST/CRYPTO_PROFILE/
TLS_KEM_PROXY_USE_PRECOMPILED already set in the environment, same
convention campaign_run.py's _REMOTE_CLIENT_ENV uses):
  CRYPTO_PROFILE=<profile> REMOTE_GATEWAY_HOST=<server_ip> TLS_KEM_PROXY_USE_PRECOMPILED=1 \
    python3 capture_participant_decomposition_v8.py <profile>
Writes participant_decomposition_capture_v8_<profile>.json in the
current directory (pulled back to thesis/results/v8/ afterwards).
"""
import json
import os
import sys

profile = sys.argv[1]
sys.path.insert(0, os.path.dirname(__file__))
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
pqc_signer_started = of.start_pqc_signer_service(profile)
try:
    if of.REMOTE_GATEWAY_HOST:
        print(f"REMOTE_GATEWAY_HOST={of.REMOTE_GATEWAY_HOST} -- skipping set_latency() "
              f"(real remote gateway, no local container to tc/netem into).")
    else:
        raise RuntimeError("REMOTE_GATEWAY_HOST not set -- this capture is meant to run against the real v8 fleet.")
    insurance_calls = of.run_insurance_flow(profile)
    person_calls = of.run_person_flow(profile)
finally:
    of.stop_pqc_signer_service(pqc_signer_started)
    of.stop_tls_kem_proxy(proc)

calls = insurance_calls + person_calls
print(f"{profile}: {len(calls)} calls captured")

HOST_TO_PARTICIPANT = {
    of.AUTH_HOST: "AS",
    of.AUTH_MTLS_HOST_HEADER: "AS",
    of.API_HOST: "RS",
    of.DIRECTORY_HOST: "Directory/PKI-CRL",
}

rows = []
totals = {}
for c in calls:
    hh = c.get("host_header")
    if c["endpoint"].endswith((".pem",)):
        participant = ba.classify_participant(c["full_uri"])
    elif hh is not None:
        participant = HOST_TO_PARTICIPANT.get(hh)
    else:
        # simulate_login()'s automated interaction never calls do_call() (v7
        # Decision 12's own note) -- these are real AS endpoints (login/
        # consent pages), classified by endpoint path instead of host_header.
        participant = "AS" if (c["endpoint"].startswith("/auth") or c["endpoint"].startswith("/interaction")) else None
    if participant is None:
        raise RuntimeError(f"unrecognized host_header {hh!r} for endpoint {c['endpoint']!r} -- extend HOST_TO_PARTICIPANT")
    rows.append({
        "endpoint": c["endpoint"], "host_header": hh, "participant": participant,
        "request_bytes": c["request_bytes"], "response_bytes": c["response_bytes"],
        "method": c["method"], "src": c["src"],
    })
    t = totals.setdefault(participant, {"sent_bytes": 0, "received_bytes": 0, "count": 0})
    t["sent_bytes"] += c["response_bytes"]
    t["received_bytes"] += c["request_bytes"]
    t["count"] += 1

out = {
    "profile": profile,
    "remote_gateway_host": of.REMOTE_GATEWAY_HOST,
    "n_calls": len(calls),
    "totals_by_participant": totals,
    "calls": rows,
}
out_path = f"participant_decomposition_capture_v8_{profile}.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print(f"Wrote {out_path}")
print(json.dumps(totals, indent=2))
