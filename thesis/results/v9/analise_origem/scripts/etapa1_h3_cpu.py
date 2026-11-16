#!/usr/bin/env python3
"""Degrau 1, Etapa 1, H3: custo de CPU previsto (microbenchmark local,
item 5) x diferenca real observada nas rotas L0 (RTT~0). Numeros do
microbenchmark vem de data/microbench_primitives_raw.txt e
microbench_chain_raw.txt (rodados ao vivo via Docker, mockopin-v9-toolchain,
maquina local do operador -- nunca a AWS). Contagens de operacao por
execucao vem de dados reais (piloto_calls.json/opinsize), nunca assumidas."""
import json
import statistics as st
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
RAW = REPO_ROOT / "thesis/results/v9/campaign_oficial_conta_nova_raw"
ORG = REPO_ROOT / "thesis/results/v9/campaign_oficial_conta_nova_organized"
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OUT = DATA_DIR / "etapa1_h3_cpu.json"

L0_ROUTES = ["L0-sa-east-1", "L0-us-east-1", "L0-ap-northeast-1"]
EXPERIMENT_DIR = {
    "classico": "experiment1 - Classic", "pqc": "experiment2 - PQC",
    "hibrido-v8": "experiment4 - Control", "hibrido-and": "experiment3 - Hybrid",
}

# Microbenchmark real (ns/op), lido manualmente do output salvo em
# data/microbench_primitives_raw.txt e microbench_chain_raw.txt -- citados
# aqui como constantes pra clareza do calculo, nunca re-digitados em outro
# lugar do relatorio sem apontar pra este arquivo.
NS = {
    "rsa_sign": 902882, "rsa_verify": 30604,
    "mldsa_sign": 535535, "mldsa_verify": 144189,
    "ecdh_keygen": 108071, "ecdh_compute": 494856,
    "mlkem_keygen": 74711, "mlkem_encapsulate": 49449, "mlkem_decapsulate": 72132,
    "chain_classic": 30621, "chain_pqc": 151844, "chain_hybrid_rsa_only": 23191,
}

N_MTLS = 6  # confirmado real, Decisao 140/opinsize


def kex_cost_ns(profile):
    if profile == "classico":
        return N_MTLS * (NS["ecdh_keygen"] + NS["ecdh_compute"])
    if profile == "pqc":
        return N_MTLS * (NS["mlkem_keygen"] + NS["mlkem_encapsulate"] + NS["mlkem_decapsulate"])
    if profile in ("hibrido-v8", "hibrido-and"):
        # Hibrido/AND e Control (perfil "hibrido-v8") no handshake client-facing
        # usam o grupo SecP384r1MLKEM1024 (combinador) -- soma das duas KEX.
        # Confirmado no CurveID real medido (Secao 2.2.1 dedicated_criteria), nao assumido.
        return N_MTLS * (NS["ecdh_keygen"] + NS["ecdh_compute"] + NS["mlkem_keygen"] + NS["mlkem_encapsulate"] + NS["mlkem_decapsulate"])
    raise ValueError(profile)


def sign_cost_ns(profile, n_signed):
    if profile == "classico":
        return n_signed * NS["rsa_sign"]
    if profile == "pqc":
        return n_signed * NS["mldsa_sign"]
    if profile in ("hibrido-v8", "hibrido-and"):
        return n_signed * (NS["rsa_sign"] + NS["mldsa_sign"])
    raise ValueError(profile)


def chain_cost_ns(profile):
    if profile == "classico":
        return N_MTLS * NS["chain_classic"]
    if profile == "pqc":
        return N_MTLS * NS["chain_pqc"]
    if profile == "hibrido-v8":
        return N_MTLS * NS["chain_classic"]  # Control usa cadeia RSA, mesma ordem de grandeza de Classic
    if profile == "hibrido-and":
        return N_MTLS * NS["chain_hybrid_rsa_only"]  # so a cadeia RSA primaria -- limitacao de escopo (ver bench_chain)
    raise ValueError(profile)


def load_median_ms(prof, route):
    p = ORG / "latency" / EXPERIMENT_DIR[prof] / route / "median_metrics.json"
    return json.loads(p.read_text(encoding="utf-8"))["median"] * 1000


def main():
    # n_signed real por perfil: confirmado na Secao 2.4.1 do relatorio oficial
    # (classic_only/pqc_pure/payload_extension+strong_nesting = 26 tokens nao-jwe)
    n_signed = {"classico": 26, "pqc": 26, "hibrido-v8": 26, "hibrido-and": 26}

    predicted_total_ns = {}
    for prof in ["classico", "pqc", "hibrido-v8", "hibrido-and"]:
        predicted_total_ns[prof] = kex_cost_ns(prof) + sign_cost_ns(prof, n_signed[prof]) + chain_cost_ns(prof)

    pairs = [("pqc", "classico", "PQC vs Classic"), ("hibrido-and", "pqc", "Hybrid vs PQC")]
    results = {}
    for prof_b, prof_a, label in pairs:
        predicted_diff_ms = (predicted_total_ns[prof_b] - predicted_total_ns[prof_a]) / 1e6
        per_route = {}
        for route in L0_ROUTES:
            mb = load_median_ms(prof_b, route)
            ma = load_median_ms(prof_a, route)
            observed_diff_ms = mb - ma
            ratio = predicted_diff_ms / observed_diff_ms if observed_diff_ms != 0 else None
            same_order = ratio is not None and (
                (observed_diff_ms > 0 and 0.5 <= ratio <= 2.0) or
                (observed_diff_ms < 0 and 0.5 <= ratio <= 2.0 and predicted_diff_ms < 0)
            )
            per_route[route] = {
                "observed_diff_ms": observed_diff_ms, "predicted_diff_ms": predicted_diff_ms,
                "ratio_predicted_over_observed": ratio,
                "same_order_of_magnitude_0.5x_to_2x": same_order,
            }
        results[label] = {"predicted_diff_ms": predicted_diff_ms, "per_route": per_route}

    out = {
        "predicted_total_cpu_ns_per_profile": predicted_total_ns,
        "n_signed_per_exec": n_signed,
        "comparisons": results,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    for label, r in results.items():
        print(label, "predicted_diff_ms=", round(r["predicted_diff_ms"], 2))
        for route, d in r["per_route"].items():
            print(" ", route, "observed=", round(d["observed_diff_ms"], 1), "ratio=", d["ratio_predicted_over_observed"], "same_order=", d["same_order_of_magnitude_0.5x_to_2x"])


if __name__ == "__main__":
    main()
