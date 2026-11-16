#!/usr/bin/env python3
"""Degrau 1, correcao do item 5 da verificacao critica: o teste
(residuo_rota - residuo_L0_mesma_instalacao) CANCELA qualquer overhead
constante de SSH que dependa so da regiao do cliente (rota e seu proprio
L0 compartilham a mesma distancia controle<->cliente) -- por construcao,
aquele teste nao pode refutar nem confirmar o overhead de SSH; so prova
que existe, ADICIONALMENTE, um componente que escala com RTT
cliente-servidor. Este script ajusta o modelo linear
residuo_ms = a + b*RTT_controle_cliente_ms + c*RTT_cliente_servidor_ms
nas 8 rotas (perfil Classic), com IC bootstrap (semente 20270102, mesma
registrada no PLANO.md, 10000 iteracoes). So dados locais, nunca
aquecimentos."""
import json
import numpy as np
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
RAW = REPO_ROOT / "thesis/results/v9/campaign_oficial_conta_nova_raw"
ORG = REPO_ROOT / "thesis/results/v9/campaign_oficial_conta_nova_organized"
OUT = Path(__file__).resolve().parents[1] / "data" / "etapa1_regressao_ssh_vs_rtt.json"

BOOTSTRAP_SEED = 20270102
BOOTSTRAP_ITERS = 10000

EXPERIMENT_DIR = {"classico": "experiment1 - Classic"}
ROUTES = ["L0-sa-east-1", "L123", "L219", "L325", "L0-us-east-1", "L14", "L0-ap-northeast-1", "L30"]

# RTT(controle,cliente) por rota -- transparencia total (mesma convencao do item 3
# anterior): REAL quando o servidor da rota e sa-east-1 (co-localizado com o
# controle, confirmado em host_facts.md) ou quando o cliente da rota esta na MESMA
# regiao de uma rota com servidor sa-east-1 (L14 ~ mesma regiao de cliente de L123,
# ca-central-1); APROXIMACAO EXTERNA (ponto medio da faixa ja declarada no item 3)
# nas 3 rotas sem nenhuma medicao real ou derivavel desta campanha.
RTT_CONTROL_CLIENT_MS = {
    "L0-sa-east-1": {"value": 0.129, "kind": "real"},
    "L123": {"value": 122.642, "kind": "real"},
    "L219": {"value": 220.151, "kind": "real"},
    "L325": {"value": 323.406, "kind": "real"},
    "L14": {"value": 122.642, "kind": "derivado (mesma regiao de cliente que L123, ca-central-1)"},
    "L0-us-east-1": {"value": 112.5, "kind": "APROXIMACAO EXTERNA (ponto medio da faixa 105-120ms, nao medida)"},
    "L0-ap-northeast-1": {"value": 285.0, "kind": "APROXIMACAO EXTERNA (ponto medio da faixa 270-300ms, nao medida)"},
    "L30": {"value": 290.0, "kind": "APROXIMACAO EXTERNA (ponto medio da faixa 275-305ms, nao medida)"},
}


def exec_by(calls, prof, route):
    return [e for e in calls if e["profile"] == prof and e["route"] == route]


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def main():
    calls = json.loads((RAW / "piloto_calls.json").read_text(encoding="utf-8"))
    crit7 = json.loads((RAW / "criterio7_rtt_por_rota.json").read_text(encoding="utf-8"))

    rows = []
    for route in ROUTES:
        execs = exec_by(calls, "classico", route)
        from datetime import datetime
        sums_s = [sum(c["latency_ms"] for c in e["insurance"]) / 1000.0 for e in execs]
        tflux_s = [(datetime.fromisoformat(e["end_utc"]) - datetime.fromisoformat(e["start_utc"])).total_seconds() for e in execs]
        residual_ms = (median(tflux_s) - median(sums_s)) * 1000.0
        rtt_cc = RTT_CONTROL_CLIENT_MS[route]
        rtt_cs = crit7[route]["rtt_ms_pcap"]
        rows.append({
            "route": route, "residual_ms": residual_ms,
            "rtt_control_client_ms": rtt_cc["value"], "rtt_control_client_kind": rtt_cc["kind"],
            "rtt_client_server_ms": rtt_cs,
        })

    y = np.array([r["residual_ms"] for r in rows])
    X = np.array([[1.0, r["rtt_control_client_ms"], r["rtt_client_server_ms"]] for r in rows])

    coef, residuals_lsq, rank, sv = np.linalg.lstsq(X, y, rcond=None)
    a, b, c = (float(v) for v in coef)

    cond_number = float(sv[0] / sv[-1]) if sv[-1] > 0 else float("inf")

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    n = len(rows)
    boot_coefs = np.empty((BOOTSTRAP_ITERS, 3))
    for i in range(BOOTSTRAP_ITERS):
        idx = rng.integers(0, n, size=n)
        Xb, yb = X[idx], y[idx]
        cb, _, _, _ = np.linalg.lstsq(Xb, yb, rcond=None)
        boot_coefs[i] = cb
    ci = np.percentile(boot_coefs, [2.5, 97.5], axis=0)

    # referencia: ~13 viagens de rede (RTT completo = ida+volta) sugerida pelo
    # usuario para o coeficiente b -- confirmado ou refutado pelo IC, nunca forcado.
    k_estimate_point = b  # b*RTT_ms = contribuicao em ms; dividido por RTT_ms(=1 unidade) o proprio b JA e "ms de residuo por ms de RTT controle-cliente" = numero de viagens
    k_ci = [float(ci[0][1]), float(ci[1][1])]

    result = {
        "rows": rows,
        "design_matrix_note": (
            "Para L0-sa-east-1/L123/L219/L325, RTT_controle_cliente == RTT_cliente_servidor "
            "EXATAMENTE (servidor dessas rotas e sa-east-1, co-localizado com o controle) -- "
            "colinearidade perfeita nesses 4 pontos; so os outros 4 (L0-us-east-1/L14/"
            "L0-ap-northeast-1/L30), onde as duas distancias divergem, separam de fato b de c."
        ),
        "fit_point_estimate": {"a_ms": a, "b_ms_per_ms_rtt_cc": b, "c_ms_per_ms_rtt_cs": c},
        "fit_condition_number": cond_number,
        "bootstrap_ci95": {
            "a_ms": [float(ci[0][0]), float(ci[1][0])],
            "b_ms_per_ms_rtt_cc": k_ci,
            "c_ms_per_ms_rtt_cs": [float(ci[0][2]), float(ci[1][2])],
        },
        "b_compatible_with_13_round_trips": (k_ci[0] <= 13.0 <= k_ci[1]),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
