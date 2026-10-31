"""Generates thesis/results/v8/Consolidated_Metrics_Report_FINAL.md
(English, same structure/tone as thesis/results/v7/Consolidated_Metrics_
Report_FINAL.md) -- every number in the output is read or computed here
from thesis/results/v8/global_v2/{report_data_v8_combined,
consolidated_combined}.json, the per-window thesis/results/v8/janela{1,2,3}/
_v2/consolidated_v2.json, and thesis/results/v8/drift_table_72cells.csv --
never hand-typed into this file's own text.

Usage: python thesis/scripts/generate_v8_final_report.py
"""
import csv
import json
import math
import statistics
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
V8 = REPO_ROOT / "thesis" / "results" / "v8"

report_data = json.loads((V8 / "global_v2" / "report_data_v8_combined.json").read_text(encoding="utf-8"))
consolidated = json.loads((V8 / "global_v2" / "consolidated_combined.json").read_text(encoding="utf-8"))
PROFILES = ["classic", "pqc", "hybrid"]
EXP_DIRS = {"classic": "experiment1 - Classic", "pqc": "experiment2 - PQC", "hybrid": "experiment3 - Hybrid"}
SCEN = {"sa-east-1": ["L0", "L123", "L219", "L325"], "us-east-1": ["L0", "L14"], "ap-northeast-1": ["L0", "L30"]}
ROUTES = [(inst, scen) for inst, scens in SCEN.items() for scen in scens]
rows_by_key = {(r["profile"], r["installation"], r["scenario"]): r for r in report_data["rows"]}

window_models = {}
for n in (1, 2, 3):
    window_models[n] = json.loads((V8 / f"janela{n}" / "_v2" / "consolidated_v2.json").read_text(encoding="utf-8"))["models"]
combined_models = consolidated["models"]

drift_rows = list(csv.DictReader((V8 / "drift_table_72cells.csv").open(encoding="utf-8")))


def fmt(x, nd=2):
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def ratio_pct(a, b):
    r = a / b
    return r, (r - 1) * 100


def cell(profile, inst, scen):
    return consolidated["profiles"][profile][inst][scen]


# -------------------------------------------------------------- OPINsize terms
# Constant across all 8 routes for a given profile (verified by audit_v8_from_raw.py) --
# sa-east-1/L0 (co-located client+server, near-zero real RTT) used as the representative
# cell, same role as v7's "0 ms" scenario.
REF_INST, REF_SCEN = "sa-east-1", "L0"
terms = {}
for p in PROFILES:
    c = cell(p, REF_INST, REF_SCEN)
    n_mtls, n_jwt, n_jwk, n_pki = 6, 28, 2, 4
    handshake_bytes = c["term_handshake"]["stats"]["median"] / n_mtls
    jwt_size = c["term_jwt"]["median"] / n_jwt
    jwk_pk_size = c["term_jwk"]["median"] / n_jwk
    pki_bytes = c["term_pki"]["median"] / n_pki
    opinsize = rows_by_key[(p, REF_INST, REF_SCEN)]["opinsize_bytes"]
    terms[p] = dict(n_mtls=n_mtls, n_jwt=n_jwt, n_jwk=n_jwk, n_pki=n_pki,
                     handshake_bytes=handshake_bytes, jwt_size=jwt_size,
                     jwk_pk_size=jwk_pk_size, pki_bytes=pki_bytes, opinsize=opinsize)

# -------------------------------------------------------------- bytes by participant
bp_per_exec = {}
for p in PROFILES:
    c = cell(p, REF_INST, REF_SCEN)
    bp = c["bytes_by_participant"]
    n_runs = rows_by_key[(p, REF_INST, REF_SCEN)]["n"]
    bp_per_exec[p] = {k: {"sent": v["sent_bytes"] / n_runs, "received": v["received_bytes"] / n_runs} for k, v in bp.items()}

# -------------------------------------------------------------- per-endpoint latency (0ms ref cell)
endpoint_latency = {}
for p in PROFILES:
    c = cell(p, REF_INST, REF_SCEN)
    endpoint_latency[p] = c["latency_per_endpoint_ms"]

# -------------------------------------------------------------- T_fluxo table, all 24 cells
tfluxo_table = {(r["profile"], r["installation"], r["scenario"]): r for r in report_data["rows"]}

# -------------------------------------------------------------- Mann-Whitney + effect size per route, pooled (30 vs 30)
def load_pooled_tfluxo(profile, inst, scen):
    vals = []
    for n in (1, 2, 3):
        base = V8 / f"janela{n}" / EXP_DIRS[profile] / inst / scen / "runs"
        for f in sorted(base.glob("run*.json")):
            if "calls" in f.name:
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            vals.append(d["result"]["t_fluxo_seconds"])
    return vals


def mann_whitney_u(a, b):
    pooled = sorted(a + b)
    ranks = {}
    for v in set(pooled):
        idx = [i + 1 for i, x in enumerate(pooled) if x == v]
        ranks[v] = sum(idx) / len(idx)
    ra = sum(ranks[v] for v in a)
    na, nb = len(a), len(b)
    u1 = ra - na * (na + 1) / 2
    u2 = na * nb - u1
    u = min(u1, u2)
    mu = na * nb / 2
    sigma = math.sqrt(na * nb * (na + nb + 1) / 12)
    z = (u - mu) / sigma if sigma else 0
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    effect = 1 - (2 * u) / (na * nb)
    return u, p, effect


pooled_tfluxo = {(p, inst, scen): load_pooled_tfluxo(p, inst, scen) for p in PROFILES for inst, scen in ROUTES}
mw_results = {}
for inst, scen in ROUTES:
    for p1, p2 in (("hybrid", "classic"), ("pqc", "classic"), ("hybrid", "pqc")):
        a, b = pooled_tfluxo[(p1, inst, scen)], pooled_tfluxo[(p2, inst, scen)]
        u, pval, eff = mann_whitney_u(a, b)
        mw_results[(p1, p2, inst, scen)] = (u, pval, eff, statistics.median(a) > statistics.median(b))

sign_counts = {}
for p1, p2 in (("hybrid", "classic"), ("pqc", "classic"), ("hybrid", "pqc")):
    sign_counts[(p1, p2)] = sum(1 for inst, scen in ROUTES if mw_results[(p1, p2, inst, scen)][3])
    sig_counts = sum(1 for inst, scen in ROUTES if mw_results[(p1, p2, inst, scen)][1] < 0.05)
    sign_counts[(p1, p2, "sig")] = sig_counts

# -------------------------------------------------------------- drift summary
n_sig_total = sum(1 for r in drift_rows if r["sig"] == "True")
n_total = len(drift_rows)
per_window_sig = {n: sum(1 for r in drift_rows if int(r["window"]) == n and r["sig"] == "True") for n in (1, 2, 3)}
sig_taus = [float(r["tau"]) for r in drift_rows if r["sig"] == "True"]

print("Computing OPINsize terms, bytes-by-participant, per-endpoint latency, 24-cell T_fluxo table,")
print("pooled Mann-Whitney/effect-size per route, and drift summary -- all from already-published JSON/CSV.")
print(f"  OPINsize: classic={terms['classic']['opinsize']:.0f} pqc={terms['pqc']['opinsize']:.0f} hybrid={terms['hybrid']['opinsize']:.0f}")
print(f"  Drift: {n_sig_total}/{n_total} significant cells, per-window: {per_window_sig}")
print(f"  Sign test (Hybrid>Classic): {sign_counts[('hybrid','classic')]}/8 routes, {sign_counts[('hybrid','classic','sig')]}/8 statistically significant (p<0.05)")
print(f"  Sign test (PQC>Classic): {sign_counts[('pqc','classic')]}/8 routes, {sign_counts[('pqc','classic','sig')]}/8 statistically significant (p<0.05)")

# write intermediate data for the report-building step (kept separate for clarity/length)
intermediate = {
    "terms": terms, "bp_per_exec": bp_per_exec, "endpoint_latency": endpoint_latency,
    "mw_results": {f"{k[0]}|{k[1]}|{k[2]}|{k[3]}": v for k, v in mw_results.items()},
    "sign_counts": {f"{k[0]}|{k[1]}" if len(k) == 2 else f"{k[0]}|{k[1]}|{k[2]}": v for k, v in sign_counts.items()},
    "n_sig_total": n_sig_total, "n_total": n_total, "per_window_sig": per_window_sig,
    "tfluxo_min_max": {f"{p}|{inst}|{scen}": [min(pooled_tfluxo[(p, inst, scen)]), max(pooled_tfluxo[(p, inst, scen)])]
                        for p in PROFILES for inst, scen in ROUTES},
}
(V8 / "global_v2" / "report_generation_intermediate.json").write_text(json.dumps(intermediate, indent=2), encoding="utf-8")
print(f"\nWrote {V8 / 'global_v2' / 'report_generation_intermediate.json'} (intermediate values for the report text)")
