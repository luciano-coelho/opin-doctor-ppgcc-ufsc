#!/usr/bin/env python3
"""Degrau 1, verificacoes adicionais pedidas apos a auditoria independente:
(1) H2 -- ajuste suplementar restrito a sa-east-1 (unica instalacao com mais
de 2 RTTs distintos), pra checar o efeito de RTT sem misturar instalacoes
(ja mostradas heterogeneas em H4); mesma semente de bootstrap do H2
original (20270102). (2) H4 -- comparacao de steal_pct/util_pct
(cpu_client/cpu_server, ja presentes em cada execucao de piloto_calls.json,
nenhuma captura nova) entre as 3 rotas L0, perfil Classic. So dados
locais, nunca aquecimentos."""
import json
import statistics as st
import numpy as np
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
RAW = REPO_ROOT / "thesis/results/v9/campaign_oficial_conta_nova_raw"
ORG = REPO_ROOT / "thesis/results/v9/campaign_oficial_conta_nova_organized"
OUT = Path(__file__).resolve().parents[1] / "data" / "etapa1_verificacoes_adicionais.json"

BOOTSTRAP_SEED = 20270102
BOOTSTRAP_ITERS = 10000

EXPERIMENT_DIR = {"classico": "experiment1 - Classic", "pqc": "experiment2 - PQC",
                   "hibrido-and": "experiment3 - Hybrid"}
SA_ROUTES = ["L0-sa-east-1", "L123", "L219", "L325"]
L0_ROUTES = ["L0-sa-east-1", "L0-us-east-1", "L0-ap-northeast-1"]


def load_median_metrics(prof, route):
    p = ORG / "latency" / EXPERIMENT_DIR[prof] / route / "median_metrics.json"
    return json.loads(p.read_text(encoding="utf-8"))


def fit_with_ci(prof_b, prof_a, routes, crit7):
    rtts, diffs = [], []
    for route in routes:
        rtt = crit7[route]["rtt_ms_pcap"]
        mb = load_median_metrics(prof_b, route)["median"] * 1000
        ma = load_median_metrics(prof_a, route)["median"] * 1000
        rtts.append(rtt)
        diffs.append(mb - ma)
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
        "n_points": n, "rtts_ms": [float(x) for x in rtts], "diffs_ms": [float(x) for x in diffs],
        "slope_ms_per_ms_rtt": float(slope), "slope_ci95_bootstrap": [float(lo), float(hi)],
    }


def main():
    calls = json.loads((RAW / "piloto_calls.json").read_text(encoding="utf-8"))
    crit7 = json.loads((RAW / "criterio7_rtt_por_rota.json").read_text(encoding="utf-8"))

    # ---- H2 suplementar: regressao restrita a sa-east-1 (4 pontos) ----
    h2_sa_only = {
        "pqc_vs_classico": fit_with_ci("pqc", "classico", SA_ROUTES, crit7),
        "hybrid_vs_pqc": fit_with_ci("hibrido-and", "pqc", SA_ROUTES, crit7),
        "note": (
            "Restrito a sa-east-1 (unica instalacao com mais de 2 RTTs distintos: "
            "L0-sa-east-1, L123, L219, L325) para evitar misturar o efeito de RTT "
            "com o efeito de instalacao (H4 ja mostra as 3 instalacoes heterogeneas "
            "entre si). n=4, fragil (poucos graus de liberdade) -- suplementar, nao "
            "substitui o ajuste agrupado pre-registrado (8 pontos, 3 instalacoes)."
        ),
    }

    # ---- H4 suplementar: steal_pct/util_pct por instalacao (Classic, L0) ----
    cpu_by_installation = {}
    for route in L0_ROUTES:
        execs = [e for e in calls if e["profile"] == "classico" and e["route"] == route]
        cpu_by_installation[route] = {
            "n": len(execs),
            "steal_pct_client_median": st.median(e["cpu_client"]["steal_pct"] for e in execs),
            "steal_pct_server_median": st.median(e["cpu_server"]["steal_pct"] for e in execs),
            "util_pct_client_median": st.median(e["cpu_client"]["util_pct"] for e in execs),
            "util_pct_server_median": st.median(e["cpu_server"]["util_pct"] for e in execs),
        }

    result = {"h2_sa_east_1_only": h2_sa_only, "h4_cpu_steal_util_por_instalacao_classic_l0": cpu_by_installation}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
