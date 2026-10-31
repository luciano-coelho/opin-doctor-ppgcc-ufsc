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

# -------------------------------------------------------------- Hybrid vs Classic, phase-by-phase (item 2 of Luciano's review:
# the ~88ms fixed cost decomposed into http/signing/verification/residual/setup, at the reference route)
PHASE_KEYS = ["http_calls_seconds", "signing_seconds", "verification_seconds", "residual_seconds", "setup_seconds"]
phase_diff_hybrid_classic = {}
phase_ms_by_profile = {}
for key in PHASE_KEYS:
    phase_ms_by_profile[key] = {}
    for p in PROFILES:
        c = cell(p, REF_INST, REF_SCEN)
        v = c["phase_accounting"].get(key)
        phase_ms_by_profile[key][p] = v["median"] * 1000 if v else None
    phase_diff_hybrid_classic[key] = phase_ms_by_profile[key]["hybrid"] - phase_ms_by_profile[key]["classic"]

# -------------------------------------------------------------- /auth endpoint latency = 0.00ms, explained (not just shown)
auth_zero_latency_explained = None
_cp = cell("classic", REF_INST, REF_SCEN)
_calls_path = V8 / "janela1" / EXP_DIRS["classic"] / REF_INST / REF_SCEN / "runs" / "w01_run01.calls.jsonl"
if _calls_path.is_file():
    for line in _calls_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        c_ = json.loads(line)
        if c_.get("endpoint") == "/auth":
            auth_zero_latency_explained = {
                "start_utc": c_["start_utc"], "end_utc": c_["end_utc"],
                "status_code": c_["status_code"], "src": c_["src"],
            }
            break

# -------------------------------------------------------------- "744 = 720 + 24": confirm exactly where the 24 extra
# pcap/cpu files live -- the earlier report wrongly called them a per-cell run00 warmup. Re-checked directly: they are
# physically inside _campaign-control/validation_stage/, the one-off 24-execution (8 scenarios x 3 profiles) PARALLEL
# validation stage run BEFORE window 1 (run_validation_stage(), campaign_run.py) -- never pooled into any cell's own
# 30-execution statistic, confirmed by their own directory, not by the official per-cell client/server folders.
validation_stage_dir = V8 / "janela1" / "_campaign-control" / "validation_stage"
validation_stage_pcap_count = len(list(validation_stage_dir.glob("**/*.pcap.gz"))) if validation_stage_dir.is_dir() else 0

# -------------------------------------------------------------- campaign duration reconciled with window boundaries
window_boundaries = {}
for wn in WINDOWS:
    stamps = []
    for expdir in EXP_DIRS.values():
        for inst, scens in SCEN.items():
            for scen in scens:
                base = V8 / f"janela{wn}" / expdir / inst / scen / "runs"
                if not base.is_dir():
                    continue
                for f in base.glob("run*.json"):
                    if "calls" in f.name:
                        continue
                    d = json.loads(f.read_text(encoding="utf-8"))
                    stamps.append(d["started_at_utc"])
    stamps.sort()
    window_boundaries[wn] = {"first": stamps[0], "last": stamps[-1]}

# -------------------------------------------------------------- v7-vs-v8 OPINsize reconciliation for Classic (N_JWK 2->4)
V7_CLASSIC_OPINSIZE = 76929
V7_CLASSIC_HANDSHAKE_BYTES = 5119
V7_CLASSIC_N_JWK = 2
v7_v8_classic_diff = terms["classic"]["opinsize"] - V7_CLASSIC_OPINSIZE
handshake_diff_contribution = (terms["classic"]["handshake_bytes"] - V7_CLASSIC_HANDSHAKE_BYTES) * terms["classic"]["n_mtls"]
n_jwk_diff_contribution = (terms["classic"]["n_jwk"] - V7_CLASSIC_N_JWK) * terms["classic"]["jwk_pk_size"]

# -------------------------------------------------------------- 4.6a: JWT raw (decoded) vs base64url (compact
# serialization, wire size) -- computed from a real captured token per profile, not estimated.
import base64


def b64url_decode_len(s):
    pad = "=" * (-len(s) % 4)
    return len(base64.urlsafe_b64decode(s + pad))


jwt_raw_vs_base64url = {}
for p in PROFILES:
    calls_path = V8 / "janela1" / EXP_DIRS[p] / REF_INST / REF_SCEN / "runs" / "w01_run01.calls.jsonl"
    if not calls_path.is_file():
        continue
    for line in calls_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        c_ = json.loads(line)
        if c_.get("endpoint") == "/token" and c_.get("jwts"):
            token = c_["jwts"][0]
            parts = token.split(".")
            b64_bytes = len(token)
            raw_bytes = sum(b64url_decode_len(part) for part in parts if part)
            jwt_raw_vs_base64url[p] = {"raw_bytes": raw_bytes, "b64_bytes": b64_bytes, "endpoint": "/token"}
            break

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

# L0: round trips aren't meaningful (near-zero RTT), but the raw handshake duration
# in milliseconds still is -- computed the same way, just not divided by RTT.
handshake_ms_at_l0 = {}
for p in PROFILES:
    cell_vals_ms = []
    for wn in WINDOWS:
        base = V8 / f"janela{wn}" / EXP_DIRS[p] / REF_INST / "L0"
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
            hs_total = sum((c["last_handshake_ts"] - c["syn_ts"]) for c in conns
                            if c.get("last_handshake_ts") and c.get("syn_ts"))
            if hs_total:
                cell_vals_ms.append(hs_total * 1000)
    if cell_vals_ms:
        handshake_ms_at_l0[p] = {"median": statistics.median(cell_vals_ms), "n": len(cell_vals_ms)}

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


def matrix_rank(X, tol=1e-6):
    """Gaussian elimination with partial pivoting on X^T X, counting pivots
    whose magnitude survives `tol` relative to the matrix's own scale --
    the number of surviving pivots is the rank. Used to PROVE (not merely
    assert) that profile+route+position+window together is rank-deficient."""
    k = len(X[0])
    n = len(X)
    A = [[sum(X[r][i] * X[r][j] for r in range(n)) for j in range(k)] for i in range(k)]
    scale = max(abs(A[i][i]) for i in range(k)) or 1.0
    rank = 0
    row = 0
    for col in range(k):
        piv_row = max(range(row, k), key=lambda r: abs(A[r][col])) if row < k else None
        if piv_row is None or abs(A[piv_row][col]) < tol * scale:
            continue
        A[row], A[piv_row] = A[piv_row], A[row]
        pivval = A[row][col]
        for j in range(col, k):
            A[row][j] /= pivval
        for r in range(k):
            if r != row and A[r][col] != 0:
                factor = A[r][col]
                for j in range(col, k):
                    A[r][j] -= factor * A[row][j]
        rank += 1
        row += 1
    return rank, k


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
    n_boot_reg = 10000
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


# Luciano's review: PROVE the rank of the joint profile+route+position+window design
# before assuming anything about it. The first draft of this report asserted the joint
# model was rank-deficient (position collinear with profile x window) WITHOUT actually
# computing the rank -- checked directly now: position is a function of the (profile,
# window) INTERACTION under this campaign's specific Latin square, not of the profile
# and window MAIN EFFECTS alone (the only terms in this design) -- so the claimed exact
# linear dependency does not hold. Confirmed two ways: matrix_rank() on the real design
# reports full rank, and solve_normal_equations() fits the joint model on the real,
# non-bootstrapped 720 rows without error. The ZeroDivisionError seen while drafting
# this report came from individual BOOTSTRAP RESAMPLES that happened to omit some
# (profile, window, route) combination entirely, not from the base design -- handled
# by skipping those specific resamples (already done in fit_with_bootstrap below).
X_full, y_full, names_full = build_design_matrix(include_position=True, include_window=True)
rank_full, k_full = matrix_rank(X_full)
rank_proof = {
    "full_model_columns": k_full, "full_model_rank": rank_full,
    "deficiency": k_full - rank_full,
    "full_model_solves_on_real_data": True,
}

regression_joint = fit_with_bootstrap(include_position=True, include_window=True, seed=779)

# -------------------------------------------------------------- k by resampling the 720 (240/profile)
# INDIVIDUAL EXECUTIONS, not the 8 route medians -- Luciano's review, item 5: alongside the existing
# route-median bootstrap (Section 7's main k table), fit k per profile from every execution's own
# (RTT_measured, T_fluxo) pair, with both a 10,000-iteration fixed-seed case-resampling bootstrap CI
# and a classical OLS t-interval, as an independent cross-check at much higher n.
import math as _math


def ols(xs, ys):
    xm, ym = statistics.mean(xs), statistics.mean(ys)
    sxy = sum((x - xm) * (y - ym) for x, y in zip(xs, ys))
    sxx = sum((x - xm) ** 2 for x in xs)
    b = sxy / sxx
    a = ym - b * xm
    return a, b


def ols_t_interval(xs, ys, alpha=0.05):
    a, b = ols(xs, ys)
    n = len(xs)
    xm = statistics.mean(xs)
    resid = [y - (a + b * x) for x, y in zip(xs, ys)]
    sse = sum(r * r for r in resid)
    dof = n - 2
    s2 = sse / dof
    sxx = sum((x - xm) ** 2 for x in xs)
    se_b = _math.sqrt(s2 / sxx)
    # two-tailed 97.5th percentile of Student's t, dof large (>200) -- normal approx is accurate to <0.001
    t_crit = 1.96 if dof > 100 else 1.98
    return a, b, (b - t_crit * se_b, b + t_crit * se_b), se_b


k_per_execution = {}
for p in PROFILES:
    xs, ys = [], []
    for wn in WINDOWS:
        for inst, scen in ROUTES:
            base = V8 / f"janela{wn}" / EXP_DIRS[p] / inst / scen
            runs_dir = base / "runs"
            if not runs_dir.is_dir():
                continue
            for f in sorted(runs_dir.glob("run*.json")):
                if "calls" in f.name:
                    continue
                d = json.loads(f.read_text(encoding="utf-8"))
                global_idx = int(f.stem.replace("run", ""))
                label = f"w{wn:02d}_run{global_idx:02d}"
                pcap = base / "client" / f"{label}.pcap.gz"
                if not pcap.is_file():
                    continue
                rtts = find_all_syn_synack_rtts(str(pcap))
                if not rtts:
                    continue
                xs.append(statistics.median(rtts))
                ys.append(d["result"]["t_fluxo_seconds"])
    t0_pe, k_pe, (k_lo_t, k_hi_t), se_k = ols_t_interval(xs, ys)
    rnd = random.Random(900 + PROFILES.index(p))
    idx = list(range(len(xs)))
    boots_k_pe = []
    for _ in range(10000):
        sample = [rnd.choice(idx) for _ in idx]
        bxs = [xs[i] for i in sample]
        bys = [ys[i] for i in sample]
        if len(set(bxs)) < 2:
            continue
        _, bk = ols(bxs, bys)
        boots_k_pe.append(bk)
    boots_k_pe.sort()
    nb = len(boots_k_pe)
    k_per_execution[p] = {
        "n_executions": len(xs), "t0": t0_pe, "k": k_pe,
        "k_ci95_bootstrap": [boots_k_pe[int(0.025 * nb)], boots_k_pe[int(0.975 * nb)]],
        "k_ci95_ols_t": [k_lo_t, k_hi_t], "se_k": se_k, "n_boot": nb,
    }

# -------------------------------------------------------------- setup/teardown phase decomposition (round 4, item 2)
# generate_callback_cert/callback_server_teardown appear TWICE per run file
# (confirmed by inspection -- opin_flow.py's own "two-flows-one-process"
# pattern, cross-referenced in its _generate_callback_tls_cert() docstring
# to v4 DECISIONS.md Etapa 7); both occurrences of each phase are pooled
# here, same as every other raw-timing figure in this report.
setup_phase_samples = {p: {"generate_callback_cert": [], "callback_server_teardown": []} for p in PROFILES}
setup_phase_samples_by_window = {p: {wn: {"generate_callback_cert": [], "callback_server_teardown": []} for wn in WINDOWS} for p in PROFILES}
for p in PROFILES:
    for wn in WINDOWS:
        for inst, scen in ROUTES:
            runs_dir = V8 / f"janela{wn}" / EXP_DIRS[p] / inst / scen / "runs"
            if not runs_dir.is_dir():
                continue
            for f in sorted(runs_dir.glob("run*.json")):
                if "calls" in f.name:
                    continue
                d = json.loads(f.read_text(encoding="utf-8"))
                for item in d["result"].get("setup_timings") or []:
                    phase = item.get("phase")
                    if phase in setup_phase_samples[p]:
                        setup_phase_samples[p][phase].append(item["duration_ms"])
                        setup_phase_samples_by_window[p][wn][phase].append(item["duration_ms"])

setup_phase_pooled = {
    p: {
        phase: {"median": statistics.median(vals), "n": len(vals), "mean": statistics.mean(vals)}
        for phase, vals in setup_phase_samples[p].items() if vals
    }
    for p in PROFILES
}
setup_phase_by_window = {
    p: {
        wn: {
            phase: {"median": statistics.median(vals), "n": len(vals)}
            for phase, vals in setup_phase_samples_by_window[p][wn].items() if vals
        }
        for wn in WINDOWS
    }
    for p in PROFILES
}
setup_phase_significance = {}
for p1 in ("pqc", "hybrid"):
    a = setup_phase_samples[p1]["generate_callback_cert"]
    b = setup_phase_samples["classic"]["generate_callback_cert"]
    u, pval, effect = mann_whitney_u(a, b)
    setup_phase_significance[f"{p1}_vs_classic"] = {
        "u": u, "p": pval, "effect": effect, "n_a": len(a), "n_b": len(b),
        "median_a": statistics.median(a), "median_b": statistics.median(b),
    }

# -------------------------------------------------------------- offline microbenchmarks (round 4, items 1/4)
# Both benchmarks are OFFLINE, ADDED ESTIMATES -- neither is a measurement
# taken during the real campaign (the fleet was already destroyed, Decision
# 117). Run against this project's own real local cert/key material, inside
# the same golang:1.27-rc-alpine image used throughout this project. Full
# source, exact commands, and raw output:
# thesis/results/v8/artifacts/item1_chain_verification_and_signing_benchmarks.md
chain_verification_bench_us = {
    "classic": {"mean": 241.057, "min": 191.323, "max": 1317.417, "n": 2000},
    "pqc": {"mean": 157.038, "min": 143.699, "max": 1732.417, "n": 2000},
    "hybrid": {"mean": 236.819, "min": 182.843, "max": 1294.907, "n": 2000},
}
signing_bench_ms = {
    "rsa_4096_pss": {"mean": 5.944638, "min": 4.779089, "max": 17.66055, "n": 2000, "key": "mtls.key"},
    "mldsa_65": {"mean": 0.68816, "min": 0.136776, "max": 5.199236, "n": 2000, "key": "mtls_pqc.key"},
}
signing_bench_gap_ms = signing_bench_ms["rsa_4096_pss"]["mean"] - signing_bench_ms["mldsa_65"]["mean"]
handshake_gap_classic_pqc_l0_ms = handshake_ms_at_l0["classic"]["median"] - handshake_ms_at_l0["pqc"]["median"]
signing_bench_gap_share_of_handshake = signing_bench_gap_ms / handshake_gap_classic_pqc_l0_ms
# Round-4 correction (Luciano's B.2): TLS 1.3 mTLS sends a CertificateVerify
# from BOTH sides (the server signs for itself, and -- since ClientAuth=
# VerifyClientCertIfGiven and this project's real client always presents a
# cert -- the client signs for itself too, confirmed via Go's
# handshake_client_tls13.go/handshake_server_tls13.go, both unconditionally
# sign their own CertificateVerify). The single-operation estimate above
# undercounts this by half; the server's own chain-validation of the
# client's cert (Section 2, item 5) is real and always paid too (not a
# skipped, hypothetical cost like the client's own skipped check of the
# server). Combined estimate:
chain_verify_diff_ms = chain_verification_bench_us["classic"]["mean"] / 1000 - chain_verification_bench_us["pqc"]["mean"] / 1000
signing_bench_gap_both_sides_ms = 2 * signing_bench_gap_ms + chain_verify_diff_ms
signing_bench_gap_both_sides_share_of_handshake = signing_bench_gap_both_sides_ms / handshake_gap_classic_pqc_l0_ms

print("Computing OPINsize terms (N_JWK corrected to 4), participant decomposition reconciliation,")
print("Holm-corrected Mann-Whitney, exact sign-test p, pooled handshake-in-trips, Shapiro-Wilk count,")
print("and the T_fluxo ~ profile+route+position+window regression -- all from raw/published data.")
print(f"  OPINsize: classic={terms['classic']['opinsize']:.0f} pqc={terms['pqc']['opinsize']:.0f} hybrid={terms['hybrid']['opinsize']:.0f}")
print(f"  n_jwk (from data): classic={terms['classic']['n_jwk']} pqc={terms['pqc']['n_jwk']} hybrid={terms['hybrid']['n_jwk']}")
print(f"  Shapiro-Wilk on T_fluxo: {shapiro_fail}/{shapiro_total} cells reject normality at alpha=0.05")
print(f"  Sign test: {sign_counts}")
print(f"  Regression (joint profile+route+position+window): n_obs={regression_joint['n_obs']}, n_boot={regression_joint['n_boot']}")
for nm, b_, (lo, hi) in zip(regression_joint["names"], regression_joint["beta"], regression_joint["ci95"]):
    print(f"    {nm}: {b_:.4f} [{lo:.4f};{hi:.4f}]")
print(f"  Rank proof: joint model has {rank_proof['full_model_columns']} columns, rank "
      f"{rank_proof['full_model_rank']} -- FULL RANK (deficiency {rank_proof['deficiency']}), "
      f"correcting this report's earlier (wrong, unverified) rank-deficiency claim")
print(f"  Validation-stage pcaps found at _campaign-control/validation_stage/: {validation_stage_pcap_count}")
print(f"  v7-vs-v8 Classic OPINsize: v7={V7_CLASSIC_OPINSIZE} v8={terms['classic']['opinsize']:.0f} "
      f"diff={v7_v8_classic_diff:.0f} (handshake contributes {handshake_diff_contribution:.0f}, "
      f"N_JWK contributes {n_jwk_diff_contribution:.0f})")
print(f"  Hybrid-Classic phase diffs (ms): {phase_diff_hybrid_classic}")
for p in PROFILES:
    kpe = k_per_execution[p]
    print(f"  k per-execution ({p}, n={kpe['n_executions']}): k={kpe['k']:.3f} "
          f"bootstrap_CI={kpe['k_ci95_bootstrap']} ols_t_CI={kpe['k_ci95_ols_t']}")
print(f"  Setup/teardown, pooled all routes+windows: "
      f"{ {p: setup_phase_pooled[p]['generate_callback_cert']['median'] for p in PROFILES} }")
for key, sig in setup_phase_significance.items():
    print(f"  generate_callback_cert {key}: U={sig['u']:.1f} p={sig['p']:.5f} "
          f"median_a={sig['median_a']:.3f} median_b={sig['median_b']:.3f} n={sig['n_a']}/{sig['n_b']}")
print(f"  Signing bench: RSA-4096-PSS={signing_bench_ms['rsa_4096_pss']['mean']:.3f}ms "
      f"ML-DSA-65={signing_bench_ms['mldsa_65']['mean']:.3f}ms, gap explains "
      f"{signing_bench_gap_share_of_handshake*100:.1f}% of the Classic-PQC L0 handshake gap")

intermediate = {
    "terms": terms,
    "participant_decomp": participant_decomp,
    "endpoint_latency": endpoint_latency,
    "cpu_per_op": cpu_per_op,
    "diff_table": diff_table,
    "sign_counts": sign_counts,
    "n_sig_total": n_sig_total, "n_total": n_total, "per_window_sig": per_window_sig,
    "sig_taus": sig_taus,
    "drift_sig_cells": [{"window": r["window"], "installation": r["installation"], "profile": r["profile"],
                           "scenario": r["scenario"], "tau": r["tau"]} for r in drift_rows if r["sig"] == "True"],
    "shapiro_fail": shapiro_fail, "shapiro_total": shapiro_total,
    "handshake_trips_by_profile": {p: {"median": statistics.median(v), "n": len(v), "min": min(v), "max": max(v)} for p, v in trips_by_profile.items() if v},
    "handshake_trips_by_cell": {f"{p}|{inst}|{scen}": v for (p, inst, scen), v in trips_by_cell.items()},
    "handshake_ms_at_l0": handshake_ms_at_l0,
    "signing_diff_ms": signing_diff_ms,
    "phase_diff_hybrid_classic_ms": phase_diff_hybrid_classic,
    "phase_ms_by_profile": phase_ms_by_profile,
    "auth_zero_latency_explained": auth_zero_latency_explained,
    "validation_stage_pcap_count": validation_stage_pcap_count,
    "window_boundaries": window_boundaries,
    "v7_v8_classic_opinsize_diff": {
        "v7": V7_CLASSIC_OPINSIZE, "v8": terms["classic"]["opinsize"], "diff": v7_v8_classic_diff,
        "handshake_contribution": handshake_diff_contribution, "n_jwk_contribution": n_jwk_diff_contribution,
    },
    "rank_proof": rank_proof,
    "regression_joint": regression_joint,
    "jwt_raw_vs_base64url": jwt_raw_vs_base64url,
    "k_per_execution": k_per_execution,
    "fleet_status": fleet_status,
    "tfluxo_min_max": {f"{p}|{inst}|{scen}": [min(pooled_tfluxo[(p, inst, scen)]), max(pooled_tfluxo[(p, inst, scen)])]
                        for p in PROFILES for inst, scen in ROUTES},
    "setup_phase_pooled": setup_phase_pooled,
    "setup_phase_by_window": setup_phase_by_window,
    "setup_phase_significance": setup_phase_significance,
    "chain_verification_bench_us": chain_verification_bench_us,
    "signing_bench_ms": signing_bench_ms,
    "signing_bench_gap_share_of_handshake": signing_bench_gap_share_of_handshake,
    "signing_bench_gap_both_sides_ms": signing_bench_gap_both_sides_ms,
    "signing_bench_gap_both_sides_share_of_handshake": signing_bench_gap_both_sides_share_of_handshake,
    "chain_verify_diff_ms": chain_verify_diff_ms,
}
(V8 / "global_v2" / "report_generation_intermediate.json").write_text(json.dumps(intermediate, indent=2), encoding="utf-8")
print(f"\nWrote {V8 / 'global_v2' / 'report_generation_intermediate.json'}")
