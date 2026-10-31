"""Computes every number thesis/results/v8/Consolidated_Metrics_Report_
FINAL.md's render step (render_v8_final_report.py) needs, from
thesis/results/v8/global_v2/{report_data_v8_combined,consolidated_combined}.json,
thesis/results/v8/janela{1,2,3}/_v2/consolidated_v2.json, the raw
run*.json/pcaps across the 3 official windows, and the one-off
participant-decomposition capture (Decision -- Luciano's review round,
2026-10-31, item A). Writes global_v2/report_generation_intermediate.json;
render_v8_final_report.py reads only that file plus the source JSONs,
never a literal typed into either script.

Usage: python thesis/scripts/generate_v8_final_report.py
"""
import itertools
import json
import math
import random
import statistics
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
V8 = REPO_ROOT / "thesis" / "results" / "v8"
import sys
sys.path.insert(0, str(V8 / "campaign" / "scripts"))
from pcap_utils import find_all_syn_synack_rtts  # noqa: E402

report_data = json.loads((V8 / "global_v2" / "report_data_v8_combined.json").read_text(encoding="utf-8"))
consolidated = json.loads((V8 / "global_v2" / "consolidated_combined.json").read_text(encoding="utf-8"))
PROFILES = ["classic", "pqc", "hybrid"]
EXP_DIRS = {"classic": "experiment1 - Classic", "pqc": "experiment2 - PQC", "hybrid": "experiment3 - Hybrid"}
SCEN = {"sa-east-1": ["L0", "L123", "L219", "L325"], "us-east-1": ["L0", "L14"], "ap-northeast-1": ["L0", "L30"]}
ROUTES = [(inst, scen) for inst, scens in SCEN.items() for scen in scens]
WINDOWS = [1, 2, 3]
rows_by_key = {(r["profile"], r["installation"], r["scenario"]): r for r in report_data["rows"]}

window_models = {n: json.loads((V8 / f"janela{n}" / "_v2" / "consolidated_v2.json").read_text(encoding="utf-8"))["models"] for n in WINDOWS}
combined_models = consolidated["models"]
fleet_status = json.loads((V8 / "global_v2" / "fleet_status_snapshot.json").read_text(encoding="utf-8"))


def cell(profile, inst, scen):
    return consolidated["profiles"][profile][inst][scen]


# -------------------------------------------------------------- OPINsize terms
# N_JWK confirmed from the raw data itself (consolidated's own "n_jwk" field,
# NOT assumed from v7's own flow structure) -- 4 real /jwks calls per
# execution (2 carrying the AS's "sig" key, 2 carrying a second, equally-
# sized "sig" entry from a different kid), not 2 as this report's first
# draft wrongly assumed (Luciano's review, item B).
REF_INST, REF_SCEN = "sa-east-1", "L0"
terms = {}
for p in PROFILES:
    c = cell(p, REF_INST, REF_SCEN)
    n_mtls = c["n_mtls"][0]
    n_jwt = c["n_jwt"][0]
    n_jwk = c["n_jwk"][0]
    n_pki = c["n_pki"][0]
    handshake_bytes = c["term_handshake"]["stats"]["median"] / n_mtls
    jwt_size = c["term_jwt"]["median"] / n_jwt
    jwk_pk_size = c["term_jwk"]["median"] / n_jwk
    pki_bytes = c["term_pki"]["median"] / n_pki
    opinsize = rows_by_key[(p, REF_INST, REF_SCEN)]["opinsize_bytes"]
    terms[p] = dict(n_mtls=n_mtls, n_jwt=n_jwt, n_jwk=n_jwk, n_pki=n_pki,
                     handshake_bytes=handshake_bytes, jwt_size=jwt_size,
                     jwk_pk_size=jwk_pk_size, pki_bytes=pki_bytes, opinsize=opinsize)

# -------------------------------------------------------------- participant decomposition (item A)
participant_decomp = {}
for p in PROFILES:
    d = json.loads((V8 / f"participant_decomposition_capture_v8_{p}.json").read_text(encoding="utf-8"))
    participant_decomp[p] = d["totals_by_participant"]
    # reconciliation: AS+RS sent/received must equal the official "Other" bucket
    off = cell(p, REF_INST, REF_SCEN)["bytes_by_participant"]
    n_runs = rows_by_key[(p, REF_INST, REF_SCEN)]["n"]
    off_other_sent = off["Other"]["sent_bytes"] / n_runs
    off_other_recv = off["Other"]["received_bytes"] / n_runs
    as_rs_sent = d["totals_by_participant"]["AS"]["sent_bytes"] + d["totals_by_participant"]["RS"]["sent_bytes"]
    as_rs_recv = d["totals_by_participant"]["AS"]["received_bytes"] + d["totals_by_participant"]["RS"]["received_bytes"]
    # this capture's "sent"/"received" is from the PARTICIPANT's own perspective (AS/RS
    # sends responses, receives requests); the official bytes_by_participant's "Other" is
    # from the CLIENT's perspective (client receives what servers send, and vice versa) --
    # opposite legs of the same bytes, same convention difference already noted in Section 3.
    assert abs(as_rs_sent - off_other_recv) < 1, f"{p}: AS+RS sent {as_rs_sent} != official Other received {off_other_recv}"
    assert abs(as_rs_recv - off_other_sent) < 1, f"{p}: AS+RS received {as_rs_recv} != official Other sent {off_other_sent}"

# -------------------------------------------------------------- per-endpoint latency (0ms ref cell)
endpoint_latency = {p: cell(p, REF_INST, REF_SCEN)["latency_per_endpoint_ms"] for p in PROFILES}

# -------------------------------------------------------------- CPU per operation (verification/signing, 0ms ref cell)
cpu_per_op = {}
for p in PROFILES:
    c = cell(p, REF_INST, REF_SCEN)
    cpu_per_op[p] = {
        "verification": c["verification_timings_ms"].get("per_artifact") or {},
        "signing": c["signing_timings_ms"].get("per_artifact") or {},
    }

# -------------------------------------------------------------- Mann-Whitney + effect size per route, pooled (30 vs 30), with Holm correction
def load_pooled_tfluxo(profile, inst, scen):
    vals = []
    for n in WINDOWS:
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


def binom_two_tailed_p(k, n):
    """Exact two-tailed sign-test p-value, Binomial(n, 0.5)."""
    def pmf(i):
        return math.comb(n, i) / (2 ** n)
    p_obs = pmf(k)
    return sum(pmf(i) for i in range(n + 1) if pmf(i) <= p_obs + 1e-12)


pooled_tfluxo = {(p, inst, scen): load_pooled_tfluxo(p, inst, scen) for p in PROFILES for inst, scen in ROUTES}

diff_table = []  # per route, per pair: ms/%/trips diff + MW p + effect + raw p for Holm
for p1, p2 in (("hybrid", "classic"), ("pqc", "classic"), ("hybrid", "pqc")):
    for inst, scen in ROUTES:
        a, b = pooled_tfluxo[(p1, inst, scen)], pooled_tfluxo[(p2, inst, scen)]
        u, pval, eff = mann_whitney_u(a, b)
        med_a, med_b = statistics.median(a), statistics.median(b)
        rtt = cell(p2, inst, scen)["rtt_and_loss"]["rtt_measured_ms"]["median"] / 1000
        diff_s = med_a - med_b
        diff_table.append({
            "pair": f"{p1}>{p2}", "installation": inst, "scenario": scen,
            "diff_ms": diff_s * 1000, "diff_pct": 100 * diff_s / med_b,
            # L0 routes have RTT near 0.2-0.3ms -- dividing by it turns ordinary
            # measurement noise into a "trips" value in the hundreds; not reported there.
            "diff_trips": (diff_s / rtt) if (rtt and scen != "L0") else None,
            "mw_p": pval, "effect": eff, "greater": med_a > med_b,
        })

# Holm-Bonferroni across all 24 tests (3 pairs x 8 routes)
sorted_idx = sorted(range(len(diff_table)), key=lambda i: diff_table[i]["mw_p"])
m = len(diff_table)
holm_adj = [None] * m
running_max = 0.0
for rank, i in enumerate(sorted_idx):
    adj = min(1.0, (m - rank) * diff_table[i]["mw_p"])
    running_max = max(running_max, adj)
    holm_adj[i] = running_max
for i, row in enumerate(diff_table):
    row["mw_p_holm"] = holm_adj[i]

sign_counts = {}
for pair in ("hybrid>classic", "pqc>classic", "hybrid>pqc"):
    rows = [r for r in diff_table if r["pair"] == pair]
    greater = sum(1 for r in rows if r["greater"])
    sig = sum(1 for r in rows if r["mw_p"] < 0.05)
    sig_holm = sum(1 for r in rows if r["mw_p_holm"] < 0.05)
    sign_p = binom_two_tailed_p(greater, len(rows))
    sign_counts[pair] = {"greater": greater, "total": len(rows), "sig": sig, "sig_holm": sig_holm, "sign_test_p": sign_p}

# -------------------------------------------------------------- drift summary (within/between windows, magnitudes, Shapiro-Wilk)
import csv
drift_rows = list(csv.DictReader((V8 / "drift_table_72cells.csv").open(encoding="utf-8")))
n_sig_total = sum(1 for r in drift_rows if r["sig"] == "True")
n_total = len(drift_rows)
per_window_sig = {n: sum(1 for r in drift_rows if int(r["window"]) == n and r["sig"] == "True") for n in WINDOWS}
sig_taus = [float(r["tau"]) for r in drift_rows if r["sig"] == "True"]

shapiro_fail = 0
shapiro_total = 0
for p in PROFILES:
    for inst, scen in ROUTES:
        sw = cell(p, inst, scen)["t_fluxo_raw_seconds"] if False else None
# t_fluxo's own shapiro_wilk lives under a stats_block of individual run values -- not
# directly in consolidated's t_fluxo_seconds (a scalar median record); recompute directly.
def shapiro_wilk_normal_at_05(values):
    try:
        from scipy import stats as scipy_stats
        stat, p = scipy_stats.shapiro(values)
        return p >= 0.05
    except Exception:
        return None


for p in PROFILES:
    for inst, scen in ROUTES:
        vals = pooled_tfluxo[(p, inst, scen)]
        res = shapiro_wilk_normal_at_05(vals)
        if res is None:
            continue
        shapiro_total += 1
        if not res:
            shapiro_fail += 1

# -------------------------------------------------------------- handshake-in-trips, pooled ALL 3 windows x the 6
# non-near-zero-RTT routes (L0 excluded: dividing by an RTT of ~0.2ms turns ordinary
# measurement noise into a "trips" value in the hundreds -- the same reason Decision
# 112 (window 1 only) restricted this metric to L123/L219/L325. Pooled here across all
# 3 windows and every non-L0 route (L123/L219/L325/L14/L30), same method Decision 112
# used: per EXECUTION, sum of (last_handshake_ts - syn_ts) across the 6 connections,
# divided by that execution's own median SYN/SYN-ACK RTT -- not the gateway-log-based
# mtls_handshake_duration_sum_ms field, which measures only the server-side portion of
# the handshake and is not directly comparable to a round-trip count.
sys.path.insert(0, str(Path(r"C:\Users\LUCIA_~1\AppData\Local\Temp\claude\c--Users-lucia-csx8nlz-MockOPIN\16762379-6cfe-4d29-9317-63a6f754e3f9\scratchpad")))
import pcap_rtt_lib  # noqa: E402

NON_ZERO_RTT_ROUTES = [(inst, scen) for inst, scen in ROUTES if scen != "L0"]
trips_by_profile = {p: [] for p in PROFILES}
trips_by_cell = {}
for p in PROFILES:
    for inst, scen in NON_ZERO_RTT_ROUTES:
        cell_vals = []
        for wn in WINDOWS:
            base = V8 / f"janela{wn}" / EXP_DIRS[p] / inst / scen
            runs_dir = base / "runs"
            if not runs_dir.is_dir():
                continue
            for f in sorted(runs_dir.glob("run*.json")):
                if "calls" in f.name:
                    continue
                global_idx = int(f.stem.replace("run", ""))
                label = f"w{wn:02d}_run{global_idx:02d}"
                pcap = base / "client" / f"{label}.pcap.gz"
                if not pcap.is_file():
                    continue
                conns = pcap_rtt_lib.extract_connections(str(pcap))
                rtts = [c["tcp_connect_rtt_ms"] for c in conns if "tcp_connect_rtt_ms" in c]
                hs_total = sum((c["last_handshake_ts"] - c["syn_ts"]) for c in conns
                                if c.get("last_handshake_ts") and c.get("syn_ts"))
                if rtts and hs_total:
                    trips = (hs_total * 1000) / statistics.median(rtts)
                    cell_vals.append(trips)
        if cell_vals:
            trips_by_cell[(p, inst, scen)] = statistics.median(cell_vals)
            trips_by_profile[p].append(statistics.median(cell_vals))

# -------------------------------------------------------------- Hybrid's measured signing-time difference vs Classic
signing_diff_ms = None
if cpu_per_op["hybrid"]["signing"] and cpu_per_op["classic"]["signing"]:
    hy_sign_total = sum(v["median"] for v in cpu_per_op["hybrid"]["signing"].values())
    cl_sign_total = sum(v["median"] for v in cpu_per_op["classic"]["signing"].values())
    signing_diff_ms = hy_sign_total - cl_sign_total

# -------------------------------------------------------------- T_fluxo ~ profile + route + position + window (OLS, dummy-coded)
# IMPORTANT, found while building this model: `profile_position_in_window` is
# identical across all 3 installations for a given (profile, window) -- the
# Latin square assigns one profile order per WINDOW, shared by every
# installation's block, by design (campaign_run.py's
# build_latin_square_profile_orders()). Position is therefore perfectly
# collinear with the (profile x window) interaction and cannot be estimated
# alongside both main effects in one design matrix (confirmed: including all
# four terms together produces a singular normal-equations matrix). Two
# reduced models are fit instead, each internally identifiable, and the
# confound is reported rather than hidden:
#   Model 1: T_fluxo ~ profile + route + window   (drops position)
#   Model 2: T_fluxo ~ profile + route + position (drops window)
def build_design_matrix(include_position, include_window):
    rows_y = []
    rows_x = []
    for n in WINDOWS:
        for p in PROFILES:
            for inst, scen in ROUTES:
                base = V8 / f"janela{n}" / EXP_DIRS[p] / inst / scen / "runs"
                for f in sorted(base.glob("run*.json")):
                    if "calls" in f.name:
                        continue
                    d = json.loads(f.read_text(encoding="utf-8"))
                    y = d["result"]["t_fluxo_seconds"]
                    pos = d["profile_position_in_window"]
                    row = [1.0]
                    row.append(1.0 if p == "pqc" else 0.0)
                    row.append(1.0 if p == "hybrid" else 0.0)
                    for inst2, scen2 in ROUTES[1:]:
                        row.append(1.0 if (inst, scen) == (inst2, scen2) else 0.0)
                    if include_position:
                        row.append(1.0 if pos == 1 else 0.0)
                        row.append(1.0 if pos == 2 else 0.0)
                    if include_window:
                        row.append(1.0 if n == 2 else 0.0)
                        row.append(1.0 if n == 3 else 0.0)
                    rows_x.append(row)
                    rows_y.append(y)
    names = (["intercept", "profile_pqc", "profile_hybrid"] +
             [f"route_{i}_{s}" for i, s in ROUTES[1:]])
    if include_position:
        names += ["position_1", "position_2"]
    if include_window:
        names += ["window_2", "window_3"]
    return rows_x, rows_y, names


def solve_normal_equations(X, y):
    k = len(X[0])
    n = len(X)
    XtX = [[sum(X[r][i] * X[r][j] for r in range(n)) for j in range(k)] for i in range(k)]
    Xty = [sum(X[r][i] * y[r] for r in range(n)) for i in range(k)]
    # Gaussian elimination with partial pivoting
    A = [row[:] + [Xty[i]] for i, row in enumerate(XtX)]
    for col in range(k):
        piv = max(range(col, k), key=lambda r: abs(A[r][col]))
        A[col], A[piv] = A[piv], A[col]
        pivval = A[col][col]
        for j in range(col, k + 1):
            A[col][j] /= pivval
        for r in range(k):
            if r != col and A[r][col] != 0:
                factor = A[r][col]
                for j in range(col, k + 1):
                    A[r][j] -= factor * A[col][j]
    return [A[i][k] for i in range(k)]


def fit_with_bootstrap(include_position, include_window, seed):
    X, y, names = build_design_matrix(include_position, include_window)
    beta = solve_normal_equations(X, y)
    rnd = random.Random(seed)
    n_boot_reg = 300
    boot_betas = []
    idx_all = list(range(len(X)))
    for _ in range(n_boot_reg):
        sample = [rnd.choice(idx_all) for _ in idx_all]
        bx = [X[i] for i in sample]
        by = [y[i] for i in sample]
        try:
            boot_betas.append(solve_normal_equations(bx, by))
        except ZeroDivisionError:
            continue
    reg_ci = []
    for j in range(len(names)):
        col = sorted(b[j] for b in boot_betas)
        nci = len(col)
        reg_ci.append((col[int(0.025 * nci)], col[int(0.975 * nci)]))
    return {"names": names, "beta": beta, "ci95": reg_ci, "n_obs": len(X), "n_boot": len(boot_betas)}


regression_window = fit_with_bootstrap(include_position=False, include_window=True, seed=777)
regression_position = fit_with_bootstrap(include_position=True, include_window=False, seed=778)

print("Computing OPINsize terms (N_JWK corrected to 4), participant decomposition reconciliation,")
print("Holm-corrected Mann-Whitney, exact sign-test p, pooled handshake-in-trips, Shapiro-Wilk count,")
print("and the T_fluxo ~ profile+route+position+window regression -- all from raw/published data.")
print(f"  OPINsize: classic={terms['classic']['opinsize']:.0f} pqc={terms['pqc']['opinsize']:.0f} hybrid={terms['hybrid']['opinsize']:.0f}")
print(f"  n_jwk (from data): classic={terms['classic']['n_jwk']} pqc={terms['pqc']['n_jwk']} hybrid={terms['hybrid']['n_jwk']}")
print(f"  Shapiro-Wilk on T_fluxo: {shapiro_fail}/{shapiro_total} cells reject normality at alpha=0.05")
print(f"  Sign test: {sign_counts}")
for label, reg in (("window model", regression_window), ("position model", regression_position)):
    print(f"  Regression ({label}): n_obs={reg['n_obs']}, n_boot={reg['n_boot']}")
    for nm, b_, (lo, hi) in zip(reg["names"], reg["beta"], reg["ci95"]):
        print(f"    {nm}: {b_:.4f} [{lo:.4f};{hi:.4f}]")

intermediate = {
    "terms": terms,
    "participant_decomp": participant_decomp,
    "endpoint_latency": endpoint_latency,
    "cpu_per_op": cpu_per_op,
    "diff_table": diff_table,
    "sign_counts": sign_counts,
    "n_sig_total": n_sig_total, "n_total": n_total, "per_window_sig": per_window_sig,
    "shapiro_fail": shapiro_fail, "shapiro_total": shapiro_total,
    "handshake_trips_by_profile": {p: {"median": statistics.median(v), "n": len(v), "min": min(v), "max": max(v)} for p, v in trips_by_profile.items() if v},
    "signing_diff_ms": signing_diff_ms,
    "regression_window": regression_window,
    "regression_position": regression_position,
    "fleet_status": fleet_status,
    "tfluxo_min_max": {f"{p}|{inst}|{scen}": [min(pooled_tfluxo[(p, inst, scen)]), max(pooled_tfluxo[(p, inst, scen)])]
                        for p in PROFILES for inst, scen in ROUTES},
}
(V8 / "global_v2" / "report_generation_intermediate.json").write_text(json.dumps(intermediate, indent=2), encoding="utf-8")
print(f"\nWrote {V8 / 'global_v2' / 'report_generation_intermediate.json'}")
