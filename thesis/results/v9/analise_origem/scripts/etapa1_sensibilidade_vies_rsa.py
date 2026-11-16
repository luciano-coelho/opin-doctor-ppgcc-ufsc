#!/usr/bin/env python3
"""Degrau 1, item 3: faixa de viés possível que o custo de reconstrução
de chave RSA (CORRIGIDO para ~25-30ms, RSA-2048 -- ver achado da quinta
auditoria independente e etapa1_microbench_custos_por_perfil.py: a
chave real do client_one foi rotacionada de 4096 para 2048 bits em
2026-11-10, Decisao 113, ANTES da campanha oficial rodar) introduz nas
diferenças PQC-Classic e Hybrid-PQC JA PUBLICADAS na Secao 5.1 do
Consolidated_Metrics_Report_FINAL.md (relatorio oficial). Os 16 valores
de "Dif (ms)" abaixo sao citados diretamente dessa tabela (ja gerada
pelo script oficial, ja auditada antes) -- este script so faz o AJUSTE
ARITMETICO de sensibilidade, nunca reroda o teste estatistico (isso
exigiria dados brutos corrigidos, fora do escopo desta verificacao).

VERSAO ANTERIOR (incorreta, premissa de RSA-4096, ~218-252ms) mantida
comentada abaixo so por transparencia -- nunca reusada no calculo."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "etapa1_sensibilidade_vies_rsa.json"

# CORRIGIDO (RSA-2048 real, Decisao 113): min/max do microbenchmark local.
BIAS_LOW_MS = 25.84
BIAS_HIGH_MS = 29.78
# Versao anterior (incorreta, premissa RSA-4096): BIAS_LOW_MS=218.53, BIAS_HIGH_MS=252.0

# Dif (ms) citado diretamente da Secao 5.1 do Consolidated_Metrics_Report_FINAL.md
# (relatorio oficial ja publicado, tabela de 16 testes principais).
OFICIAL_DIF_MS = {
    "PQC vs. Classic": {
        "L0-sa-east-1": -69.0, "L123": 263.4, "L219": 422.3, "L325": 577.3,
        "L0-us-east-1": 223.4, "L14": 287.9, "L0-ap-northeast-1": 462.4, "L30": 554.8,
    },
    "Hybrid vs. PQC": {
        "L0-sa-east-1": 275.7, "L123": 205.9, "L219": 290.9, "L325": 395.1,
        "L0-us-east-1": 167.7, "L14": 170.1, "L0-ap-northeast-1": 367.7, "L30": 259.2,
    },
}


def main():
    result = {"bias_range_ms": [BIAS_LOW_MS, BIAS_HIGH_MS], "comparisons": {}}
    for pair, routes in OFICIAL_DIF_MS.items():
        result["comparisons"][pair] = {}
        for route, dif_obs in routes.items():
            if pair == "PQC vs. Classic":
                # Classic paga o vies (~230ms), PQC nao -- Dif_true = Dif_obs + vies
                true_lo = dif_obs + BIAS_LOW_MS
                true_hi = dif_obs + BIAS_HIGH_MS
            else:
                # Hybrid paga o vies (~230ms), PQC nao -- Dif_true = Dif_obs - vies
                true_lo = dif_obs - BIAS_HIGH_MS
                true_hi = dif_obs - BIAS_LOW_MS
            sign_flip = (true_lo < 0) != (dif_obs < 0) or (true_hi < 0) != (dif_obs < 0)
            result["comparisons"][pair][route] = {
                "dif_observado_ms": dif_obs,
                "dif_corrigido_faixa_ms": [round(true_lo, 1), round(true_hi, 1)],
                "pode_trocar_de_sinal": sign_flip,
            }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
