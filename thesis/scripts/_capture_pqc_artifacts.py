"""
One-shot capture script for thesis/results/v7/artifacts/pqc/ -- NOT part of
the official size/latency measurement pipeline (median_automation.py /
latency_automation.py), which does not use this workaround and is
unaffected by it.

Runs opin_flow.py's real insurance+person flows under CRYPTO_PROFILE=pqc to
capture one genuine JWKS response and one genuine ML-DSA-65-signed JWT for
the artifacts README. Needs one workaround: opin_flow.py's do_call() passes
get_client_cert_paths("pqc")'s result (client_one_pqc.crt/.key, a native
ML-DSA-65 keypair) to `requests`' `cert=` argument even for the local
Python->tls_kem_proxy leg -- which this host's stock OpenSSL 3.0 cannot
parse at all (confirmed: SSLContext.load_cert_chain on that exact file
fails with EE_KEY_TOO_SMALL/X509_LIB, independent of any network activity).
That local leg never actually needs a client certificate: tls_kem_proxy's
own listener (thesis/scripts/tls_kem_proxy/main.go, generateLocalListenerCert())
sets no ClientAuth requirement at all -- the REAL mTLS identity is
established entirely on the far leg (Go proxy -> gateway), using the cert
path baked into the already-running proxy process's own CLI args. So this
script starts the proxy first (with the real pqc cert/key), then monkeypatches
get_client_cert_paths to return the classical, loadable client_one.crt/.key
for the rest of the run -- cosmetic-only on the local leg, no effect on the
real backend authentication.

Usage: CRYPTO_PROFILE is set internally; just run
  python thesis/scripts/_capture_pqc_artifacts.py
Writes into thesis/results/v7/artifacts/pqc/: jwks_auth.json,
example_jwt_premium_compact.txt, _all_calls_dump.json (full call list, for
inspection -- not itself a committed artifact).
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
os.environ["CRYPTO_PROFILE"] = "pqc"

import opin_flow as of

raw_bodies = []
_orig_do_call = of.do_call


def _capturing_do_call(session, method, url, **kwargs):
    call, resp = _orig_do_call(session, method, url, **kwargs)
    raw_bodies.append({"endpoint": call["endpoint"], "full_uri": call["full_uri"], "body": resp.text})
    return call, resp


of.do_call = _capturing_do_call

proc = of.start_tls_kem_proxy("pqc")
pqc_signer_started = of.start_pqc_signer_service("pqc")  # persistent ML-DSA-65 signer

of.get_client_cert_paths = lambda profile: (str(of.CERTS_DIR / "client_one.crt"), str(of.CERTS_DIR / "client_one.key"))

try:
    of.set_latency(0)
    insurance_calls = of.run_insurance_flow("pqc")
    person_calls = of.run_person_flow("pqc")
finally:
    of.stop_pqc_signer_service(pqc_signer_started)
    of.stop_tls_kem_proxy(proc)

calls = insurance_calls + person_calls

out_dir = os.path.join(os.path.dirname(__file__), "..", "results", "v7", "artifacts", "pqc")
os.makedirs(out_dir, exist_ok=True)

jwks_body = None
premium_body = None
for rb in raw_bodies:
    if rb["endpoint"].rstrip("/").endswith("jwks") and jwks_body is None:
        jwks_body = rb["body"]
    if "premium" in rb["endpoint"]:
        premium_body = rb["body"]

with open(os.path.join(out_dir, "jwks_auth.json"), "w", encoding="utf-8") as f:
    f.write(jwks_body)
print("Wrote jwks_auth.json:", len(jwks_body), "bytes")

premium_jwt = None
for c in insurance_calls + person_calls:
    if "premium" in c["endpoint"] and c["jwts"]:
        premium_jwt = c["jwts"][0]
        break

if premium_jwt:
    with open(os.path.join(out_dir, "example_jwt_premium_compact.txt"), "w", encoding="utf-8") as f:
        f.write(premium_jwt)
    print("Wrote example_jwt_premium_compact.txt:", len(premium_jwt), "chars")
else:
    print("NO PREMIUM JWT FOUND")

with open(os.path.join(out_dir, "_all_calls_dump.json"), "w", encoding="utf-8") as f:
    json.dump(calls, f, indent=2, ensure_ascii=False)
print("Wrote _all_calls_dump.json")
