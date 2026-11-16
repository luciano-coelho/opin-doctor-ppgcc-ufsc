#!/usr/bin/env python3
"""Degrau 1, Etapa 1: decomposicao do T_fluxo (soma das latency_ms reais
vs. residuo), H2 (regressao Dif vs RTT + K teorico via cwnd/MSS reais) e
H4 (heterogeneidade entre instalacoes, L0). Semente de bootstrap fixa =
20270102 (ver PLANO.md). So dados locais, nunca aquecimentos."""
import json
import statistics as st
import numpy as np
from pathlib import Path
from scipy.stats import mannwhitneyu

REPO_ROOT = Path(__file__).resolve().parents[5]
RAW = REPO_ROOT / "thesis/results/v9/campaign_oficial_conta_nova_raw"
ORG = REPO_ROOT / "thesis/results/v9/campaign_oficial_conta_nova_organized"
OUT = Path(__file__).resolve().parents[1] / "data" / "etapa1_decomp_h2_h4.json"

BOOTSTRAP_SEED = 20270102
BOOTSTRAP_ITERS = 10000

PROFILES = ["classico", "pqc", "hibrido-v8", "hibrido-and"]
EXPERIMENT_DIR = {
    "classico": "experiment1 - Classic", "pqc": "experiment2 - PQC",
    "hibrido-v8": "experiment4 - Control", "hibrido-and": "experiment3 - Hybrid",
}
ROUTES = ["L0-sa-east-1", "L123", "L219", "L325", "L0-us-east-1", "L14", "L0-ap-northeast-1", "L30"]
L0_ROUTES = ["L0-sa-east-1", "L0-us-east-1", "L0-ap-northeast-1"]
NON_L0_ROUTES = [r for r in ROUTES if r not in L0_ROUTES]


def holm_adjust(pvalues):
    n = len(pvalues)
    order = sorted(range(n), key=lambda i: pvalues[i])
    adjusted = [0.0] * n
    running_max = 0.0
    for rank, idx in enumerate(order):
        adj = (n - rank) * pvalues[idx]
        running_max = max(running_max, adj)
        adjusted[idx] = min(running_max, 1.0)
    return adjusted


def load_median_metrics(prof, route):
    p = ORG / "latency" / EXPERIMENT_DIR[prof] / route / "median_metrics.json"
    return json.loads(p.read_text(encoding="utf-8"))


def exec_by_profile_route(calls, prof, route):
    return [e for e in calls if e["profile"] == prof and e["route"] == route]


def main():
    calls = json.loads((RAW / "piloto_calls.json").read_text(encoding="utf-8"))
    crit7 = json.loads((RAW / "criterio7_rtt_por_rota.json").read_text(encoding="utf-8"))

    # ---- decomposicao: soma(latency_ms) vs residuo, por celula ----
    decomp = {}
    for prof in PROFILES:
        for route in ROUTES:
            execs = exec_by_profile_route(calls, prof, route)
            sums_ms = []
            tflux_ms = []
            for e in execs:
                call_sum = sum(c["latency_ms"] for c in e["insurance"])
                from datetime import datetime
                tf = (datetime.fromisoformat(e["end_utc"]) - datetime.fromisoformat(e["start_utc"])).total_seconds() * 1000
                sums_ms.append(call_sum)
                tflux_ms.append(tf)
            residuals = [t - s for t, s in zip(tflux_ms, sums_ms)]
            decomp[f"{prof}/{route}"] = {
                "median_call_sum_ms": st.median(sums_ms),
                "median_t_fluxo_ms": st.median(tflux_ms),
                "median_residual_ms": st.median(residuals),
                "residual_pct_of_tfluxo": st.median(residuals) / st.median(tflux_ms) * 100,
            }

    # ---- H2: regressao Dif vs RTT (PQC-Classic, Hybrid-PQC) ----
    def diffs_vs_rtt(prof_b, prof_a):
        rtts = []
        diffs = []
        per_route = {}
        for route in ROUTES:
            rtt = crit7[route]["rtt_ms_pcap"]
            mb = load_median_metrics(prof_b, route)["median"] * 1000
            ma = load_median_metrics(prof_a, route)["median"] * 1000
            rtts.append(rtt)
            diffs.append(mb - ma)
            per_route[route] = {"rtt_ms_pcap": rtt, "diff_ms": mb - ma}
        rtts = np.array(rtts)
        diffs = np.array(diffs)
        slope, intercept = np.polyfit(rtts, diffs, 1)
        rng = np.random.default_rng(BOOTSTRAP_SEED)
        n = len(rtts)
        slopes = np.empty(BOOTSTRAP_ITERS)
        for i in range(BOOTSTRAP_ITERS):
            idx = rng.integers(0, n, size=n)
            s, _ = np.polyfit(rtts[idx], diffs[idx], 1)
            slopes[i] = s
        lo, hi = np.percentile(slopes, [2.5, 97.5])
        return {
            "per_route": per_route, "slope_ms_per_ms_rtt": float(slope), "intercept_ms": float(intercept),
            "slope_ci95_bootstrap": [float(lo), float(hi)],
        }

    h2_pqc_classic = diffs_vs_rtt("pqc", "classico")
    h2_hybrid_pqc = diffs_vs_rtt("hibrido-and", "pqc")

    # K teorico via cwnd/MSS reais (criterio 2) -- slow start: apos k RTTs completos
    # com cwnd dobrando a cada RTT a partir de initcwnd=10 segmentos, bytes
    # cumulativos enviáveis = MSS * initcwnd * (2^k - 1). Resolve k dado bytes extras.
    crit2 = json.loads((RAW / "criterio2_initcwnd_L123_server-to-client.json").read_text(encoding="utf-8"))
    initcwnd = crit2["ss_ti_cwnd"]
    mss = crit2["mss_bytes"]
    opinsize = json.loads((RAW / "opinsize_oficial_conta_nova.json").read_text(encoding="utf-8"))["profiles"]

    def extra_rtts_needed(extra_bytes):
        if extra_bytes <= 0:
            return 0.0
        import math
        # bytes cumulativos apos k RTTs completos de slow start: MSS*initcwnd*(2^k - 1)
        # resolve k: 2^k = extra_bytes/(MSS*initcwnd) + 1
        ratio = extra_bytes / (mss * initcwnd) + 1
        return math.log2(ratio)

    # bytes extras por execucao: handshake (N_mTLS*handshake_bytes) + payload real (response/request bytes somados)
    def total_bytes_per_exec(prof):
        e = exec_by_profile_route(calls, prof, "L123")[0]
        return sum(c["total_bytes"] for c in e["insurance"])

    bytes_classico = total_bytes_per_exec("classico")
    bytes_pqc = total_bytes_per_exec("pqc")
    bytes_hybrid = total_bytes_per_exec("hibrido-and")
    k_theoretical_pqc_classic = extra_rtts_needed(bytes_pqc - bytes_classico)
    k_theoretical_hybrid_pqc = extra_rtts_needed(bytes_hybrid - bytes_pqc)

    h2 = {
        "initcwnd_real": initcwnd, "mss_real_bytes": mss,
        "total_bytes_per_exec": {"classico": bytes_classico, "pqc": bytes_pqc, "hibrido-and": bytes_hybrid},
        "pqc_vs_classico": h2_pqc_classic,
        "hybrid_vs_pqc": h2_hybrid_pqc,
        "k_theoretical_extra_rtts_pqc_vs_classico": k_theoretical_pqc_classic,
        "k_theoretical_extra_rtts_hybrid_vs_pqc": k_theoretical_hybrid_pqc,
        "note": (
            "slope_ms_per_ms_rtt e adimensional (ms de diferenca por ms de RTT) -- "
            "comparavel diretamente a k_theoretical (num. de RTTs extras) SE a "
            "diferenca fosse inteiramente round-trips extras. k_theoretical vem da "
            "formula padrao de slow-start (cwnd dobra por RTT) usando cwnd/MSS REAIS "
            "do criterio 2 (nao assumidos) e os bytes totais REAIS por execucao."
        ),
    }

    # ---- H4: heterogeneidade entre instalacoes (Classic, rotas L0) ----
    l0_pairs = [("L0-sa-east-1", "L0-us-east-1"), ("L0-sa-east-1", "L0-ap-northeast-1"), ("L0-us-east-1", "L0-ap-northeast-1")]
    h4_tests = []
    for r1, r2 in l0_pairs:
        v1 = load_median_metrics("classico", r1)["values"]
        v2 = load_median_metrics("classico", r2)["values"]
        res = mannwhitneyu(v1, v2, alternative="two-sided", method="exact")
        h4_tests.append({"pair": f"{r1} vs {r2}", "p_raw": float(res.pvalue),
                          "median_1_ms": st.median(v1) * 1000, "median_2_ms": st.median(v2) * 1000})
    h4_adj = holm_adjust([t["p_raw"] for t in h4_tests])
    for t, a in zip(h4_tests, h4_adj):
        t["p_holm"] = a

    h4_residuals_l0 = {route: decomp[f"classico/{route}"] for route in L0_ROUTES}

    result = {
        "decomposicao_por_celula_ms": decomp,
        "h2": h2,
        "h4_mannwhitney_3_pares_classic_l0": h4_tests,
        "h4_residuos_classic_l0": h4_residuals_l0,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print("H2 PQC-Classic slope:", h2_pqc_classic["slope_ms_per_ms_rtt"], "CI:", h2_pqc_classic["slope_ci95_bootstrap"])
    print("H2 Hybrid-PQC slope:", h2_hybrid_pqc["slope_ms_per_ms_rtt"], "CI:", h2_hybrid_pqc["slope_ci95_bootstrap"])
    print("K teorico PQC-Classic:", k_theoretical_pqc_classic, "Hybrid-PQC:", k_theoretical_hybrid_pqc)
    print("H4 tests:", h4_tests)
    print("H4 residuals L0:", h4_residuals_l0)


if __name__ == "__main__":
    main()
