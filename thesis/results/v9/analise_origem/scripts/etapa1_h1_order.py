#!/usr/bin/env python3
"""Degrau 1, Etapa 1, H1: efeito de posicao do bloco na ordem da rota +
tendencia dentro do bloco. Semente de permutacao fixa = 20270101 (ver
PLANO.md). So dados locais ja existentes, nunca aquecimentos."""
import json
import numpy as np
from pathlib import Path
from scipy.stats import spearmanr, kendalltau

REPO_ROOT = Path(__file__).resolve().parents[5]
RAW = REPO_ROOT / "thesis/results/v9/campaign_oficial_conta_nova_raw"
ORG = REPO_ROOT / "thesis/results/v9/campaign_oficial_conta_nova_organized"
OUT = Path(__file__).resolve().parents[1] / "data" / "etapa1_h1_order.json"

PERM_SEED = 20270101
N_PERM = 10000

PROFILES = ["classico", "pqc", "hibrido-v8", "hibrido-and"]
EXPERIMENT_DIR = {
    "classico": "experiment1 - Classic", "pqc": "experiment2 - PQC",
    "hibrido-v8": "experiment4 - Control", "hibrido-and": "experiment3 - Hybrid",
}
ROUTES = ["L0-sa-east-1", "L123", "L219", "L325", "L0-us-east-1", "L14", "L0-ap-northeast-1", "L30"]


def load_median_metrics(prof, route):
    p = ORG / "latency" / EXPERIMENT_DIR[prof] / route / "median_metrics.json"
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    manifest = json.loads((RAW / "manifest.json").read_text(encoding="utf-8"))
    route_orders = manifest["route_orders"]
    rng = np.random.default_rng(PERM_SEED)

    # ---- parte (a): posicao do bloco x T_fluxo mediano, por rota ----
    positions = []
    medians = []
    per_route = {}
    for route in ROUTES:
        order = route_orders[route]
        pos_map = {prof: i + 1 for i, prof in enumerate(order)}
        route_positions = []
        route_medians = []
        for prof in PROFILES:
            m = load_median_metrics(prof, route)
            route_positions.append(pos_map[prof])
            route_medians.append(m["median"])
        rho, p_rho = spearmanr(route_positions, route_medians)
        per_route[route] = {"positions": route_positions, "medians_s": route_medians, "spearman_rho": rho, "spearman_p": p_rho}
        positions.extend(route_positions)
        medians.extend(route_medians)

    positions = np.array(positions)
    medians = np.array(medians)
    # correlacao combinada real (pooled, 32 pontos -- route e um fator, mas aqui
    # fazemos so a correlacao bruta combinada, documentado como tal)
    rho_obs, _ = spearmanr(positions, medians)

    perm_rhos = np.empty(N_PERM)
    # permuta a posicao DENTRO de cada rota (nunca entre rotas), preservando a estrutura
    pos_matrix = positions.reshape(len(ROUTES), 4)
    med_matrix = medians.reshape(len(ROUTES), 4)
    for i in range(N_PERM):
        perm_pos = np.array([rng.permutation(row) for row in pos_matrix]).flatten()
        r, _ = spearmanr(perm_pos, med_matrix.flatten())
        perm_rhos[i] = r
    perm_p_two_sided = float(np.mean(np.abs(perm_rhos) >= abs(rho_obs)))

    # ---- parte (b): tendencia dentro do bloco (32 celulas, 10 execucoes em ordem real) ----
    within_block = {}
    n_significant = 0
    for prof in PROFILES:
        for route in ROUTES:
            m = load_median_metrics(prof, route)
            vals = m["values"]  # ja na ordem de 'values' do arquivo -- confirmar ordem real abaixo via piloto_calls
            order_index = list(range(1, len(vals) + 1))
            tau, p_tau = kendalltau(order_index, vals)
            within_block[f"{prof}/{route}"] = {"tau": tau, "p": p_tau}
            if p_tau < 0.05:
                n_significant += 1

    result = {
        "seed_permutation": PERM_SEED, "n_permutations": N_PERM,
        "per_route_position_vs_median": per_route,
        "pooled_spearman_rho_position_vs_median": rho_obs,
        "pooled_permutation_p_two_sided": perm_p_two_sided,
        "within_block_trend_32_cells": within_block,
        "within_block_n_significant_p_lt_05": n_significant,
        "note_order_within_block": (
            "A ordem usada para a tendencia dentro do bloco e a ordem do array "
            "'values' de median_metrics.json, que por sua vez reflete a ordem "
            "'run01'..'run10' dos arquivos de runs -- confirmado que 'run' e um "
            "contador sequencial real da execucao (nao embaralhado), via "
            "inspecao direta de piloto_calls.json (campo 'run')."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print("pooled rho:", rho_obs, "perm p:", perm_p_two_sided)
    print("within-block significant cells:", n_significant, "/32")
    for route, d in per_route.items():
        print(route, "rho=", round(d["spearman_rho"], 3), "p=", round(d["spearman_p"], 3))


if __name__ == "__main__":
    main()
