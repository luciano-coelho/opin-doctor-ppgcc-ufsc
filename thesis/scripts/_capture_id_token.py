"""
One-shot capture script -- NOT part of the official measurement pipeline.
Runs opin_flow.py's real insurance flow under a given CRYPTO_PROFILE,
capturing the raw /token response body (which embeds a real id_token, JWE-
encrypted per Decision 10/thesis/results/v4/DECISIONS.md) for
thesis/results/v7/artifacts/{classico,pqc,hybrid}/README.md's id_token
section. Writes id_token_raw.txt (the id_token JWE, compact form) under
thesis/results/v7/artifacts/<profile_dir>/.

Usage: python thesis/scripts/_capture_id_token.py classic|pqc|hybrid
"""
import json
import os
import sys

sys.argv_profile = sys.argv[1]
profile = sys.argv[1]
profile_dir = {"classic": "classico", "pqc": "pqc", "hybrid": "hybrid"}[profile]

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
os.environ["CRYPTO_PROFILE"] = profile

import opin_flow as of

raw_bodies = []
_orig_do_call = of.do_call


def _capturing_do_call(session, method, url, **kwargs):
    call, resp = _orig_do_call(session, method, url, **kwargs)
    raw_bodies.append({"endpoint": call["endpoint"], "full_uri": call["full_uri"], "body": resp.text})
    return call, resp


of.do_call = _capturing_do_call

if profile == "pqc":
    of.get_client_cert_paths_orig = of.get_client_cert_paths
    # See Decision 5 (v7): opin_flow.py itself no longer presents a cert on
    # the local leg for pqc/hybrid post-fix -- this override is now a no-op
    # safety net, kept only in case this script runs against a pre-fix copy.

proc = of.start_tls_kem_proxy(profile)
try:
    of.set_latency(0)
    calls = of.run_insurance_flow(profile)
    print(f"flow completed, {len(calls)} calls")
finally:
    of.stop_tls_kem_proxy(proc)

token_bodies = [rb["body"] for rb in raw_bodies if rb["endpoint"].rstrip("/").endswith("/token")]
print(f"found {len(token_bodies)} /token response bodies")

id_token = None
for body in token_bodies:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        continue
    if "id_token" in parsed:
        id_token = parsed["id_token"]
        break

if not id_token:
    print("NO id_token FOUND in any /token response")
    sys.exit(1)

out_dir = os.path.join(os.path.dirname(__file__), "..", "results", "v7", "artifacts", profile_dir)
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "id_token_raw.txt")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(id_token)
print(f"Wrote {out_path}: {len(id_token)} chars, {id_token.count('.')+1} segments")
