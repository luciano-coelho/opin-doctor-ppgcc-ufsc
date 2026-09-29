"""
Applies a documented correction to thesis/results/v7/report_data_v7.json's
OPINsize computation: N_JWT was 26, missing the 2 JARM (FAPI Advanced
authorization response) tokens the flow actually signs and transmits, one
per sub-flow, embedded in the `response=` query parameter of the Location
header on the final "resume" redirect of the automated login/consent
simulation.

Root cause: opin_flow.py's simulate_login()/wait_for_authorization_code()
never routed this response through do_call() (the function every other
tracked call goes through), so it was invisible to both byte accounting
(total_bytes_exchanged, bytes_by_participant) and JWT extraction
(baseline_automation.extract_jwts(), which only ever scanned request/
response bodies and the Authorization header -- never Location). Fixed at
the source in this same commit (opin_flow.py's simulate_login() now
captures it via a response hook, verified end-to-end through the official
pipeline: jwt_count is now 28 for a fresh run in all three profiles).

The already-collected v7 raw run files (180 of them) were captured before
that fix and cannot retroactively contain this data -- there is no
raw-file field to re-derive it from. This script instead applies the
correction analytically, using JARM sizes measured live, once per profile,
directly from the running system (deterministic: JARM content depends only
on the fixed claims + the profile's signing scheme, confirmed 0% spread on
every other size metric in this same dataset), each verified by decoding
the JWT header's own `alg` field:

    classic: 621  bytes, alg=PS256
    pqc:     4696 bytes, alg=ML-DSA-65
    hybrid:  5061 bytes, alg=MLDSA65-RSA2048-PSS-SHA256 (Strong Nesting)

Usage: python thesis/scripts/apply_jarm_correction.py
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA_PATH = REPO / "thesis" / "results" / "v7" / "report_data_v7.json"

JARM_BYTES = {"classic": 621, "pqc": 4696, "hybrid": 5061}
JARM_COUNT_PER_FLOW = 2  # one per sub-flow (insurance, person)

data = json.loads(DATA_PATH.read_text(encoding="utf-8"))

print(f"{'profile':10s} {'N_JWT (old->new)':20s} {'JWT_size avg (old->new)':28s} {'OPINsize (old->new)':24s} {'delta':>10s}")
for prof, jarm_size in JARM_BYTES.items():
    s = data["size"][prof]
    o = data["opinsize"][prof]

    old_n_jwt = s["n_jwt"]
    old_jwt_sum = s["jwt_sum"]
    new_n_jwt = old_n_jwt + JARM_COUNT_PER_FLOW
    new_jwt_sum = old_jwt_sum + JARM_COUNT_PER_FLOW * jarm_size
    new_jwt_avg = new_jwt_sum / new_n_jwt

    old_opinsize = o["extended"]
    new_opinsize = old_opinsize - o["term_jwt"] + new_jwt_sum

    s["n_jwt_corrected"] = new_n_jwt
    s["jwt_sum_corrected"] = new_jwt_sum
    s["jwt_mean_corrected"] = new_jwt_avg
    s["jarm_bytes"] = jarm_size
    s["jarm_count_per_flow"] = JARM_COUNT_PER_FLOW

    o["term_jwt_corrected"] = new_jwt_sum
    o["extended_corrected"] = new_opinsize
    o["delta_from_jarm_correction"] = new_opinsize - old_opinsize
    o["delta_pct_from_jarm_correction"] = (new_opinsize / old_opinsize - 1) * 100

    print(f"{prof:10s} {old_n_jwt:3d} -> {new_n_jwt:<14d} "
          f"{old_jwt_sum/old_n_jwt:9.2f} -> {new_jwt_avg:<14.2f} "
          f"{old_opinsize:10.2f} -> {new_opinsize:<10.2f} "
          f"+{new_opinsize - old_opinsize:8.2f} (+{(new_opinsize/old_opinsize-1)*100:.3f}%)")

print()
c, p, h = (data["opinsize"][x]["extended_corrected"] for x in ("classic", "pqc", "hybrid"))
print("Corrected ratios:")
print(f"  PQC/Classic: {p/c:.4f}x (+{(p/c-1)*100:.2f}%)")
print(f"  Hybrid/Classic: {h/c:.4f}x (+{(h/c-1)*100:.2f}%)")
print(f"  Hybrid/PQC: {h/p:.4f}x (+{(h/p-1)*100:.2f}%)")

DATA_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nWrote corrected fields into {DATA_PATH}")
