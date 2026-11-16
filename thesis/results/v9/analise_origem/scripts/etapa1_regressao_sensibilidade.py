#!/usr/bin/env python3
"""Degrau 1, item 4 (analise de sensibilidade): repete o ajuste
residuo_ms = a + b*RTT(controle,cliente) + c*RTT(cliente,servidor) do
etapa1_regressao_ssh_vs_rtt.py, mas propagando os limites INFERIOR e
SUPERIOR das 3 faixas aproximadas (L0-us-east-1/L0-ap-northeast-1/L30,
sem medicao real) em vez de so o ponto medio -- pra ver quanto a/b/c se
deslocam. Mesma semente de bootstrap 20270102, mesma metodologia."""
import json
import numpy as np
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
RAW = REPO_ROOT / "thesis/results/v9/campaign_oficial_conta_nova_raw"
ORG = REPO_ROOT / "thesis/results/v9/campaign_oficial_conta_nova_organized"
OUT = Path(__file__).resolve().parents[1] / "data" / "etapa1_regressao_sensibilidade.json"

BOOTSTRAP_SEED = 20270102
BOOTSTRAP_ITERS = 10000
ROUTES = ["L0-sa-east-1", "L123", "L219", "L325", "L0-us-east-1", "L14", "L0-ap-northeast-1", "L30"]

RTT_CC_FIXED = {  # reais/derivados, nunca variados nesta sensibilidade
    "L0-sa-east-1": 0.129, "L123": 122.642, "L219": 220.151, "L325": 323.406, "L14": 122.642,
}
RTT_CC_RANGE = {  # faixas externas, ja declaradas no relatorio
    "L0-us-east-1": (105.0, 120.0), "L0-ap-northeast-1": (270.0, 300.0), "L30": (275.0, 305.0),
}


def exec_by(calls, prof, route):
    return [e for e in calls if e["profile"] == prof and e["route"] == route]


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def fit_and_bootstrap(X, y, seed):
    coef, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    rng = np.random.default_rng(seed)
    n = len(y)
    boot = np.empty((BOOTSTRAP_ITERS, 3))
    for i in range(BOOTSTRAP_ITERS):
        idx = rng.integers(0, n, size=n)
        cb, _, _, _ = np.linalg.lstsq(X[idx], y[idx], rcond=None)
        boot[i] = cb
    ci = np.percentile(boot, [2.5, 97.5], axis=0)
    return coef, ci


def main():
    calls = json.loads((RAW / "piloto_calls.json").read_text(encoding="utf-8"))
    crit7 = json.loads((RAW / "criterio7_rtt_por_rota.json").read_text(encoding="utf-8"))

    residual_ms = {}
    for route in ROUTES:
        execs = exec_by(calls, "classico", route)
        from datetime import datetime
        sums_s = [sum(c["latency_ms"] for c in e["insurance"]) / 1000.0 for e in execs]
        tflux_s = [(datetime.fromisoformat(e["end_utc"]) - datetime.fromisoformat(e["start_utc"])).total_seconds() for e in execs]
        residual_ms[route] = (median(tflux_s) - median(sums_s)) * 1000.0

    scenarios = {"ponto_medio": {k: (v[0] + v[1]) / 2 for k, v in RTT_CC_RANGE.items()},
                 "limite_inferior": {k: v[0] for k, v in RTT_CC_RANGE.items()},
                 "limite_superior": {k: v[1] for k, v in RTT_CC_RANGE.items()}}

    result = {}
    for label, rtt_cc_approx in scenarios.items():
        rtt_cc = {**RTT_CC_FIXED, **rtt_cc_approx}
        y = np.array([residual_ms[r] for r in ROUTES])
        X = np.array([[1.0, rtt_cc[r], crit7[r]["rtt_ms_pcap"]] for r in ROUTES])
        coef, ci = fit_and_bootstrap(X, y, BOOTSTRAP_SEED)
        result[label] = {
            "rtt_cc_usado": rtt_cc_approx,
            "point_estimate": {"a_ms": float(coef[0]), "b": float(coef[1]), "c": float(coef[2])},
            "ci95": {
                "a_ms": [float(ci[0][0]), float(ci[1][0])],
                "b": [float(ci[0][1]), float(ci[1][1])],
                "c": [float(ci[0][2]), float(ci[1][2])],
            },
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
