"""
One-shot capture script -- NOT part of the official measurement pipeline.
Captures a real client_assertion (private_key_jwt) sent by opin_flow.py to
POST /token, for thesis/results/v7/artifacts/{classic,pqc,hybrid}/README.md's
client_assertion section -- proving the real client-side signature that
backs the "access token" step of the SAD (Security Architecture Document,
step 8, corrected: the access token itself is opaque; the real hybrid/PQC
signature lives here).

Usage: python thesis/scripts/_capture_client_assertion.py classic|pqc|hybrid
"""
import os
import sys
from urllib.parse import parse_qs

profile = sys.argv[1]
profile_dir = {"classic": "classic", "pqc": "pqc", "hybrid": "hybrid"}[profile]

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
os.environ["CRYPTO_PROFILE"] = profile

import opin_flow as of

req_bodies = []
_orig_do_call = of.do_call


def _capturing_do_call(session, method, url, **kwargs):
    call, resp = _orig_do_call(session, method, url, **kwargs)
    body = resp.request.body
    if body:
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="replace")
        req_bodies.append({"endpoint": call["endpoint"], "body": body})
    return call, resp


of.do_call = _capturing_do_call

proc = of.start_tls_kem_proxy(profile)
pqc_signer_started = of.start_pqc_signer_service(profile)  # persistent ML-DSA-65 signer
try:
    of.set_latency(0)
    calls = of.run_insurance_flow(profile)
    print(f"flow completed, {len(calls)} calls")
finally:
    of.stop_pqc_signer_service(pqc_signer_started)
    of.stop_tls_kem_proxy(proc)

assertion = None
for rb in req_bodies:
    if rb["endpoint"].rstrip("/").endswith("/token"):
        parsed = parse_qs(rb["body"])
        if "client_assertion" in parsed:
            assertion = parsed["client_assertion"][0]
            break

if not assertion:
    print("NO client_assertion FOUND")
    sys.exit(1)

out_dir = os.path.join(os.path.dirname(__file__), "..", "results", "v7", "artifacts", profile_dir)
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "client_assertion_raw.txt")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(assertion)
print(f"Wrote {out_path}: {len(assertion)} chars, {assertion.count('.')+1} segments")
