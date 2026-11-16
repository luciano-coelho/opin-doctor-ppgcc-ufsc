#!/usr/bin/env python3
"""Degrau 1, verificacao critica sobre o PROPRIO artefato de medicao (nao
mais sobre fisica/criptografia): T_fluxo (start_utc/end_utc, orchestrator.py
linha ~1449/1472) envolve a chamada SSH INTEIRA do controle (sa-east-1,
confirmado em host_facts.md) at'e o cliente -- nao so as 44 chamadas HTTP
reais entre cliente e servidor. Esta verificacao mede: (1) duracao real das
capturas dedicadas (pcap, via scapy, offline) pra TODOS os perfis/rotas
disponiveis, nao so Classic/L0 como na Etapa 1 original; (2) decomposicao
PQC-Classic/Hybrid-PQC do residuo (T_fluxo - soma das chamadas) por rota;
(3) residuo das 5 rotas nao-L0 contra o residuo do L0 da MESMA instalacao,
comparado ao RTT real da rota. So dados locais, nunca aquecimentos."""
import json
import statistics as st
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
RAW = REPO_ROOT / "thesis/results/v9/campaign_oficial_conta_nova_raw"
ORG = REPO_ROOT / "thesis/results/v9/campaign_oficial_conta_nova_organized"
PCAP_DIR = RAW / "criterio1_capturas" / "capturas_brutas"
OUT = Path(__file__).resolve().parents[1] / "data" / "etapa1_verificacao_artefato_medicao.json"

EXPERIMENT_DIR = {"classico": "experiment1 - Classic", "pqc": "experiment2 - PQC",
                   "hibrido-v8": "experiment4 - Control", "hibrido-and": "experiment3 - Hybrid"}
PCAP_PROFILE_LABEL = {"classico": "classico", "pqc": "pqc", "hibrido-v8": "hibrido-v8", "hibrido-and": "hibrido-and"}
ROUTES = ["L0-sa-east-1", "L123", "L219", "L325", "L0-us-east-1", "L14", "L0-ap-northeast-1", "L30"]
L0_BY_INSTALLATION = {"sa-east-1": "L0-sa-east-1", "us-east-1": "L0-us-east-1", "ap-northeast-1": "L0-ap-northeast-1"}
NON_L0_INSTALLATION = {"L123": "sa-east-1", "L219": "sa-east-1", "L325": "sa-east-1", "L14": "us-east-1", "L30": "ap-northeast-1"}
PROFILES = ["classico", "pqc", "hibrido-v8", "hibrido-and"]


def exec_by(calls, prof, route):
    return [e for e in calls if e["profile"] == prof and e["route"] == route]


def median_metrics_s(prof, route):
    p = ORG / "latency" / EXPERIMENT_DIR[prof] / route / "median_metrics.json"
    return json.loads(p.read_text(encoding="utf-8"))["median"]


def pcap_duration_seconds(path):
    from scapy.utils import PcapReader
    first_ts = last_ts = None
    n = 0
    with PcapReader(str(path)) as reader:
        for pkt in reader:
            ts = float(pkt.time)
            if first_ts is None:
                first_ts = ts
            last_ts = ts
            n += 1
    if first_ts is None:
        return None, 0
    return last_ts - first_ts, n


def dedicated_pcap_duration(prof, route):
    pattern = f"{PCAP_PROFILE_LABEL[prof]}_{route}_tentativa*.pcap"
    files = sorted(PCAP_DIR.glob(pattern))
    durations = []
    for f in files:
        dur, n = pcap_duration_seconds(f)
        if dur is not None:
            durations.append({"file": f.name, "duration_s": dur, "n_packets": n})
    if not durations:
        return None
    return {
        "n_tentativas": len(durations),
        "median_duration_s": st.median(d["duration_s"] for d in durations),
        "per_tentativa": durations,
    }


def main():
    calls = json.loads((RAW / "piloto_calls.json").read_text(encoding="utf-8"))
    crit7 = json.loads((RAW / "criterio7_rtt_por_rota.json").read_text(encoding="utf-8"))

    # ---- (1) decomposicao completa, todos os perfis/rotas (precisao real, sem arredondar antes de subtrair) ----
    decomp = {}
    for prof in PROFILES:
        for route in ROUTES:
            execs = exec_by(calls, prof, route)
            sums_s = []
            tflux_s = []
            for e in execs:
                call_sum = sum(c["latency_ms"] for c in e["insurance"]) / 1000.0
                from datetime import datetime
                tf = (datetime.fromisoformat(e["end_utc"]) - datetime.fromisoformat(e["start_utc"])).total_seconds()
                sums_s.append(call_sum)
                tflux_s.append(tf)
            decomp[f"{prof}/{route}"] = {
                "median_call_sum_s": st.median(sums_s),
                "median_t_fluxo_s": st.median(tflux_s),
            }

    # ---- (2) excesso: T_fluxo mediano (median_metrics.json, ja usado no resto do doc) vs duracao da captura dedicada ----
    excess = {}
    for prof in PROFILES:
        for route in ROUTES:
            tflux_med = median_metrics_s(prof, route)
            pcap = dedicated_pcap_duration(prof, route)
            if pcap is None:
                excess[f"{prof}/{route}"] = {"t_fluxo_median_s": tflux_med, "pcap": None, "excess_s": None}
                continue
            exc = tflux_med - pcap["median_duration_s"]
            excess[f"{prof}/{route}"] = {
                "t_fluxo_median_s": tflux_med, "pcap_median_duration_s": pcap["median_duration_s"],
                "pcap_n_tentativas": pcap["n_tentativas"], "excess_s": exc,
            }

    # ---- (3) RTT real vs aproximado, por rota, pro controle (sa-east-1) ----
    # Real: L0-sa-east-1/L123/L219/L325 (servidor sa-east-1, co-localizado com o controle,
    # confirmado em host_facts.md) -- RTT cliente-servidor real = proxy real de RTT controle-cliente.
    # L14: cliente ca-central-1, MESMA regiao de cliente de L123 -- usa o RTT real de L123 como proxy
    # derivado (mesma regiao de cliente, destino diferente nao importa pra essa distancia).
    # L0-us-east-1/L0-ap-northeast-1/L30: SEM nenhuma medicao real ou derivavel desta campanha --
    # aproximacao EXTERNA, faixa, declarada explicitamente (nunca um numero preciso inventado).
    control_client_rtt_ms = {
        "L0-sa-east-1": {"value": crit7["L0-sa-east-1"]["rtt_ms_pcap"], "source": "real (controle e cliente co-localizados em sa-east-1)"},
        "L123": {"value": crit7["L123"]["rtt_ms_pcap"], "source": "real (servidor sa-east-1 co-localizado com o controle)"},
        "L219": {"value": crit7["L219"]["rtt_ms_pcap"], "source": "real (servidor sa-east-1 co-localizado com o controle)"},
        "L325": {"value": crit7["L325"]["rtt_ms_pcap"], "source": "real (servidor sa-east-1 co-localizado com o controle)"},
        "L14": {"value": crit7["L123"]["rtt_ms_pcap"], "source": "derivado (cliente L14 e L123 estao na MESMA regiao, ca-central-1; usa o RTT real de L123 como proxy)"},
        "L0-us-east-1": {"value": None, "range_ms": [105, 120], "source": "APROXIMACAO EXTERNA (nao medida nesta campanha) -- faixa tipica publicamente conhecida de RTT sa-east-1<->us-east-1"},
        "L0-ap-northeast-1": {"value": None, "range_ms": [270, 300], "source": "APROXIMACAO EXTERNA (nao medida nesta campanha) -- faixa tipica publicamente conhecida de RTT sa-east-1<->ap-northeast-1"},
        "L30": {"value": None, "range_ms": [275, 305], "source": "APROXIMACAO EXTERNA (nao medida nesta campanha) -- faixa tipica de sa-east-1<->ap-northeast-2, proxima da faixa sa-east-1<->ap-northeast-1 + RTT real medido ap-northeast-1<->ap-northeast-2 (33,423ms)"},
    }

    # ---- (4) decomposicao PQC-Classic / Hybrid-PQC por rota (Dsum vs Dresiduo, precisao real) ----
    pair_decomp = {}
    for b, a, label in [("pqc", "classico", "PQC-Classic"), ("hibrido-and", "pqc", "Hybrid-PQC")]:
        per_route = {}
        for route in ROUTES:
            db = decomp[f"{b}/{route}"]
            da = decomp[f"{a}/{route}"]
            d_tfluxo_s = db["median_t_fluxo_s"] - da["median_t_fluxo_s"]
            d_sum_s = db["median_call_sum_s"] - da["median_call_sum_s"]
            d_residual_s = d_tfluxo_s - d_sum_s  # derivado, consistente por construcao
            per_route[route] = {
                "d_t_fluxo_s": d_tfluxo_s, "d_sum_calls_s": d_sum_s, "d_residual_s": d_residual_s,
                "residual_quase_constante": None,  # avaliado no relatorio, nao aqui
            }
        pair_decomp[label] = per_route

    # ---- (5) residuo das rotas nao-L0 vs residuo do L0 da mesma instalacao, perfil Classic, vs RTT real ----
    non_l0_vs_rtt = {}
    for route, installation in NON_L0_INSTALLATION.items():
        l0_route = L0_BY_INSTALLATION[installation]
        resid_route = decomp[f"classico/{route}"]["median_t_fluxo_s"] - decomp[f"classico/{route}"]["median_call_sum_s"]
        resid_l0 = decomp[f"classico/{l0_route}"]["median_t_fluxo_s"] - decomp[f"classico/{l0_route}"]["median_call_sum_s"]
        d_resid_s = resid_route - resid_l0
        rtt_real_ms = crit7[route]["rtt_ms_pcap"]
        non_l0_vs_rtt[route] = {
            "installation": installation, "l0_route": l0_route,
            "residual_route_s": resid_route, "residual_l0_s": resid_l0,
            "d_residual_vs_l0_s": d_resid_s, "rtt_real_cliente_servidor_ms": rtt_real_ms,
            "d_residual_ms_per_rtt_ms": (d_resid_s * 1000) / rtt_real_ms if rtt_real_ms else None,
        }

    result = {
        "decomposicao_precisao_real": decomp,
        "excesso_t_fluxo_vs_pcap_dedicado": excess,
        "control_client_rtt_ms_por_rota": control_client_rtt_ms,
        "decomposicao_par_perfis_por_rota": pair_decomp,
        "residuo_nao_l0_vs_l0_mesma_instalacao": non_l0_vs_rtt,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
