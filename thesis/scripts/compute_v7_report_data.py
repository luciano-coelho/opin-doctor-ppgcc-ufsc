"""
Derives every number used by thesis/results/v7/CONSOLIDATED_REPORT.md and
ARCHITECTURE.md directly from the raw per-run JSON files (never from
median_metrics.json), plus the PKI/CRL term of the extended OPINsize
equation. Writes thesis/results/v7/report_data_v7.json (derived data; the
raw runs/ remain the source) -- no new measurement of any kind.

PKI certificate bodies: the gateway serves root-ca.pem/issuer-ca.pem
verbatim from mock-service-os/certs/ (mock_mtls/main.go, directoryHandler +
init()); their on-disk byte sizes are cross-validated below against the
measured PKI/CRL response bytes in the raw runs (a constant HTTP-framing
residual across all three profiles proves the served bodies are these files).

Usage: python thesis/scripts/compute_v7_report_data.py
"""
import base64
import json
import re
import statistics
from itertools import combinations
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "thesis" / "results" / "v7"
CERTS = REPO / "mock-service-os" / "certs"
PROFILES = [("experiment1 - Classic", "classic"), ("experiment2 - PQC", "pqc"), ("experiment3 - Hybrid", "hybrid")]
SCENARIOS = [0, 14, 30, 140, 225, 320]
PKI_FILES = {
    "classic": ("root_ca.crt", "issuer_ca.crt"),
    "pqc": ("root_ca_pqc.crt", "issuer_ca_pqc.crt"),
    "hybrid": ("root_ca_hybrid.crt", "issuer_ca_hybrid.crt"),
}


def load_size_runs(exp, sc):
    d = ROOT / "size" / exp / f"{sc}ms" / "runs"
    return [json.loads((d / f"run{i:02d}_baseline_metrics.json").read_text(encoding="utf-8")) for i in range(1, 11)]


def load_lat_runs(exp, sc):
    d = ROOT / "latency" / exp / f"{sc}ms" / "runs"
    return [json.loads((d / f"run{i:02d}.json").read_text(encoding="utf-8")) for i in range(1, 11)]


def mann_whitney_exact_p_greater(a, b):
    """Exact one-sided p-value for H1: values in b tend to be larger than in a
    (Mann-Whitney U, n=m=10, enumerating all C(20,10) group assignments;
    average ranks for ties). Descriptive support only -- runs are sequential,
    not independent draws."""
    pooled = sorted(a + b)
    ranks = {}
    for v in set(pooled):
        idx = [i + 1 for i, x in enumerate(pooled) if x == v]
        ranks[v] = sum(idx) / len(idx)
    all_ranks = [ranks[v] for v in a + b]
    observed = sum(ranks[v] for v in b)
    n = len(a) + len(b)
    total = hits = 0
    for combo in combinations(range(n), len(b)):
        total += 1
        if sum(all_ranks[i] for i in combo) >= observed - 1e-9:
            hits += 1
    return hits / total


def pem_der_len(path):
    """DER length of the single certificate inside a PEM file."""
    raw = path.read_bytes()
    m = re.search(rb"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----", raw, re.S)
    assert m and raw.count(b"BEGIN CERTIFICATE") == 1
    return len(base64.b64decode(m.group(1)))


def const(values, what):
    s = set(values)
    assert len(s) == 1, f"{what} is not constant: {sorted(s)}"
    return next(iter(s))


data = {"size": {}, "latency": {}, "opinsize": {}, "participants": {}, "pki": {}}

# ----------------------------------------------------------------- size
for exp, prof in PROFILES:
    all_runs = [r for sc in SCENARIOS for r in load_size_runs(exp, sc)]  # 60 runs per profile
    n = len(all_runs)
    hb = const([r["gateway_metrics"]["handshake_bytes"]["p50_bytes"] for r in all_runs], f"{prof} handshake p50")
    hb_count = const([r["gateway_metrics"]["handshake_bytes"]["count"] for r in all_runs], f"{prof} handshake count")
    jwt_sum = const([sum(r["jwt_sizes_bytes"]) for r in all_runs], f"{prof} jwt sum")
    jwt_n = const([r["jwt_count"] for r in all_runs], f"{prof} jwt count")
    cert = const([r["client_cert_der_bytes"] for r in all_runs], f"{prof} cert")
    total = const([r["total_bytes_exchanged"] for r in all_runs], f"{prof} total bytes")
    reqs = const([r["total_requests"] for r in all_runs], f"{prof} total requests")
    sig_sizes = [const([tuple(j["size_bytes"] for j in r["jwk_sizes"] if j["use"] == "sig") for r in all_runs], f"{prof} jwk sig")][0]
    enc_sizes = const([tuple(j["size_bytes"] for j in r["jwk_sizes"] if j["use"] == "enc") for r in all_runs], f"{prof} jwk enc")
    assert len(set(sig_sizes)) == 1
    n_jwk = len(sig_sizes)
    jwk_pk = sig_sizes[0]

    bp = {}
    for p in ("Client", "Other", "PKI/CRL"):
        bp[p] = {leg: const([r["bytes_by_participant"][p][leg] for r in all_runs], f"{prof} {p} {leg}") for leg in ("sent_bytes", "received_bytes")}

    ep = all_runs[0]["latency_per_endpoint"]
    n_root = const([r["latency_per_endpoint"]["/root-ca.pem"]["count"] for r in all_runs], f"{prof} root count")
    n_issuer = const([r["latency_per_endpoint"]["/issuer-ca.pem"]["count"] for r in all_runs], f"{prof} issuer count")
    n_jwks = const([r["latency_per_endpoint"]["/jwks"]["count"] for r in all_runs], f"{prof} jwks fetches")
    assert n_jwks == n_jwk, "N_JWK (signing entries) must equal number of /jwks fetches"

    root_f, issuer_f = PKI_FILES[prof]
    root_b = (CERTS / root_f).stat().st_size
    issuer_b = (CERTS / issuer_f).stat().st_size
    n_pki = n_root + n_issuer
    pki_body_total = n_root * root_b + n_issuer * issuer_b
    pki_measured_sent = bp["PKI/CRL"]["sent_bytes"]
    pki_measured_recv = bp["PKI/CRL"]["received_bytes"]
    framing_total = pki_measured_sent - pki_body_total
    assert framing_total % n_pki == 0, "PKI/CRL HTTP framing residual not an integer per response"
    framing_each = framing_total // n_pki
    root_der = pem_der_len(CERTS / root_f)
    issuer_der = pem_der_len(CERTS / issuer_f)
    data["pki"][prof] = {
        "root_file": root_f, "issuer_file": issuer_f, "root_bytes": root_b, "issuer_bytes": issuer_b,
        "root_der": root_der, "issuer_der": issuer_der, "der_body_total": n_root * root_der + n_issuer * issuer_der,
        "n_root": n_root, "n_issuer": n_issuer, "n_pki": n_pki,
        "pki_bytes_mean": pki_body_total / n_pki, "pki_body_total": pki_body_total,
        "measured_sent": pki_measured_sent, "measured_received": pki_measured_recv,
        "framing_total": framing_total, "framing_each": framing_each,
    }

    data["size"][prof] = {
        "runs_used": n, "handshake_p50": hb, "n_mtls": hb_count, "jwt_sum": jwt_sum, "n_jwt": jwt_n,
        "jwt_mean_exact": jwt_sum / jwt_n, "client_cert_der": cert, "total_bytes": total, "total_requests": reqs,
        "jwk_pk_size": jwk_pk, "n_jwk": n_jwk, "jwk_enc_sizes": list(enc_sizes),
    }
    data["participants"][prof] = bp

# framing residual must be identical in all profiles (proves bodies == served files)
framings = {data["pki"][p]["framing_each"] for _, p in PROFILES}
assert len(framings) == 1, f"HTTP framing per PKI response differs across profiles: {framings}"
data["pki_framing_each_all_profiles"] = framings.pop()
recv_each = {data["pki"][p]["measured_received"] / data["pki"][p]["n_pki"] for _, p in PROFILES}
assert len(recv_each) == 1
data["pki_request_bytes_each_all_profiles"] = recv_each.pop()

# ------------------------------------------------------------- OPINsize
for _, prof in PROFILES:
    s = data["size"][prof]
    k = data["pki"][prof]
    t_hs = s["n_mtls"] * s["handshake_p50"]
    t_jwt = s["jwt_sum"]  # N_JWT x exact mean JWT size == sum of the 26 token lengths
    t_jwk = s["n_jwk"] * s["jwk_pk_size"]
    original = t_hs + t_jwt + t_jwk
    t_pki = k["pki_body_total"]
    extended = original + t_pki
    t_pki_meas = k["measured_sent"]
    data["opinsize"][prof] = {
        "term_handshake": t_hs, "term_jwt": t_jwt, "term_jwk": t_jwk, "term_pki": t_pki,
        "original": original, "extended": extended,
        "delta_abs": t_pki, "delta_pct": t_pki / original * 100,
        "pki_share_of_extended_pct": t_pki / extended * 100,
        "extended_with_measured_framing": original + t_pki_meas,
        "delta_pct_with_measured_framing": t_pki_meas / original * 100,
        "extended_with_der": original + k["der_body_total"],
        "delta_pct_with_der": k["der_body_total"] / original * 100,
    }

# -------------------------------------------------------------- latency
for exp, prof in PROFILES:
    for sc in SCENARIOS:
        runs = load_lat_runs(exp, sc)
        vals = [r["t_fluxo_seconds"] for r in runs]
        warm = json.loads((ROOT / "latency" / exp / f"{sc}ms" / "runs" / "run00_warmup.json").read_text(encoding="utf-8"))
        data["latency"].setdefault(prof, {})[str(sc)] = {
            "values": vals, "median": statistics.median(vals), "min": min(vals), "max": max(vals),
            "mean": statistics.mean(vals), "stdev": statistics.stdev(vals),
            "spread_pct": (max(vals) - min(vals)) / min(vals) * 100, "warmup": warm["t_fluxo_seconds"],
        }

lat = data["latency"]
data["latency_deltas"] = {}
data["hypothesis"] = {}
for sc in SCENARIOS:
    c, p, h = (lat[x][str(sc)] for x in ("classic", "pqc", "hybrid"))
    data["latency_deltas"][str(sc)] = {
        "pqc_minus_classic": p["median"] - c["median"], "hybrid_minus_classic": h["median"] - c["median"],
        "hybrid_minus_pqc": h["median"] - p["median"],
        "pqc_over_classic": p["median"] / c["median"], "hybrid_over_classic": h["median"] / c["median"],
        "hybrid_over_pqc": h["median"] / p["median"],
    }
    data["hypothesis"][str(sc)] = {
        "order_holds": c["median"] < p["median"] < h["median"],
        "classic_pqc_ranges_overlap": not (c["max"] < p["min"]),
        "pqc_hybrid_ranges_overlap": not (p["max"] < h["min"]),
        "p_pqc_gt_classic": mann_whitney_exact_p_greater(c["values"], p["values"]),
        "p_hybrid_gt_pqc": mann_whitney_exact_p_greater(p["values"], h["values"]),
    }

# ---------------------------------------------- participant decomposition
# Supplementary, one-shot, non-statistical capture (thesis/scripts/
# capture_participant_decomposition.py) -- NOT part of the 180x2 official
# raw-run corpus loaded above. See DECISIONS.md, Decision 10, for why one
# execution per profile is sufficient (0.00% size spread already proven) and
# how each profile's AS+RS split was cross-validated to reconcile exactly
# with that profile's already-committed "Other" totals before being used
# here.
data["participants_decomposed"] = {}
for _, prof in PROFILES:
    cap_path = ROOT / f"participant_decomposition_capture_{prof}.json"
    cap = json.loads(cap_path.read_text(encoding="utf-8"))
    t = cap["totals_by_participant"]
    official_other = data["participants"][prof]["Other"]
    recombined_sent = t["AS"]["sent_bytes"] + t["RS"]["sent_bytes"]
    recombined_received = t["AS"]["received_bytes"] + t["RS"]["received_bytes"]
    assert recombined_sent == official_other["sent_bytes"], (prof, recombined_sent, official_other["sent_bytes"])
    assert recombined_received == official_other["received_bytes"], (prof, recombined_received, official_other["received_bytes"])
    assert t["PKI/CRL"]["sent_bytes"] == data["participants"][prof]["PKI/CRL"]["sent_bytes"]
    assert t["PKI/CRL"]["received_bytes"] == data["participants"][prof]["PKI/CRL"]["received_bytes"]
    assert t["AS"]["count"] + t["RS"]["count"] + t["PKI/CRL"]["count"] == data["size"][prof]["total_requests"]
    data["participants_decomposed"][prof] = {
        "Client": data["participants"][prof]["Client"],
        "AS": {"sent_bytes": t["AS"]["sent_bytes"], "received_bytes": t["AS"]["received_bytes"]},
        "RS": {"sent_bytes": t["RS"]["sent_bytes"], "received_bytes": t["RS"]["received_bytes"]},
        "PKI/CRL": data["participants"][prof]["PKI/CRL"],
    }

(ROOT / "report_data_v7.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print("Wrote", ROOT / "report_data_v7.json")
for _, prof in PROFILES:
    o = data["opinsize"][prof]
    print(prof, "OPINsize original", o["original"], "-> extended", o["extended"], f"(+{o['delta_abs']}, +{o['delta_pct']:.2f}%)")
print("PKI framing per response (all profiles):", data["pki_framing_each_all_profiles"], "B; request bytes per fetch:", data["pki_request_bytes_each_all_profiles"])
print("hypothesis:", {k: v["order_holds"] for k, v in data["hypothesis"].items()})
print("overlaps classic/pqc:", {k: v["classic_pqc_ranges_overlap"] for k, v in data["hypothesis"].items()})
print("overlaps pqc/hybrid:", {k: v["pqc_hybrid_ranges_overlap"] for k, v in data["hypothesis"].items()})
print("exact one-sided MW p (pqc>classic):", {k: round(v["p_pqc_gt_classic"], 6) for k, v in data["hypothesis"].items()})
print("exact one-sided MW p (hybrid>pqc):", {k: round(v["p_hybrid_gt_pqc"], 4) for k, v in data["hypothesis"].items()})
