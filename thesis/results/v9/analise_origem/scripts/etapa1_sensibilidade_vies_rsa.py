#!/usr/bin/env python3
"""Degrau 1, item 3 (rodada 3, faixa honesta final): faixa de vies que o
custo de reconstrucao de chave RSA introduz nas diferencas PQC-Classic e
Hybrid-PQC JA PUBLICADAS na Secao 5.1 do Consolidated_Metrics_Report_FINAL.md.

Contagem de chamadas (confirmada lendo o codigo, nunca assumida):
load_client_signing_key() e chamada 3x por execucao real -- 1x em
latency_automation.py:257 (pre-aquecimento, ANTES de t_start, cache
vazio -- essa e a UNICA chamada que paga o custo real de
RSAAlgorithm.from_jwk()) + 1x dentro de opin_flow.py:run_insurance_flow
(linha 2501) + 1x dentro de opin_flow.py:run_person_flow (linha 2546) --
essas 2 ultimas sao CACHE HITS (_SIGNING_KEY_CACHE ja populado pelo
pre-aquecimento, retornam ANTES de tocar o timer, confirmado lendo o
codigo: `if crypto_profile in _SIGNING_KEY_CACHE: return ...` antes de
`t0 = time.monotonic()`). O "x2" no comentario da Decisao 99
("median classic/hybrid ~252ms x2, pqc ~0ms x2") descreve o
comportamento ANTIGO, de ANTES do cache existir (quando as 2 chamadas
dentro dos sub-fluxos pagavam o custo cheio cada uma, por isso "~500ms"
no mesmo comentario) -- NAO o comportamento atual. Com o cache (que a
propria Decisao 99 introduziu), o custo real pago por execucao e 1x, nao
2x -- confirmado pela estrutura do codigo (cache hit retorna antes do
timer; o proprio aquecimento tem sua entrada em _SETUP_TIMINGS limpa por
clear_setup_timings() antes de t_start).

Faixa de vies honesta usada aqui: 26-30ms medidos no notebook (Item 7),
com um fator de atencao de ATE 1,5x pra uma possivel diferenca de
desempenho de CPU entre o notebook e as instancias reais m7i-flex.large
(NUNCA medida diretamente -- faixa de incerteza adicional, declarada
como tal, nunca um fato). Faixa final: [26ms; 30ms*1,5=45ms], vezes 1
chamada real (confirmado acima, nao 2)."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "etapa1_sensibilidade_vies_rsa.json"

N_CHAMADAS_REAIS_POR_EXECUCAO = 1  # confirmado no codigo -- so o pre-aquecimento paga custo real
BIAS_LOW_MS = 26.0 * N_CHAMADAS_REAIS_POR_EXECUCAO
BIAS_HIGH_MS = 30.0 * 1.5 * N_CHAMADAS_REAIS_POR_EXECUCAO  # fator de atencao AWS vs. notebook, ate 1,5x

# Dif (ms) citado diretamente da Secao 5.1 do Consolidated_Metrics_Report_FINAL.md
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

# Hodges-Lehmann + IC 95% bootstrap JA PUBLICADOS na Secao 5.1 (citados diretamente,
# nunca recalculados aqui -- so deslocados pelo vies, nunca reprocessado o teste).
OFICIAL_HL_CI_MS = {
    "PQC vs. Classic": {
        "L0-sa-east-1": (-54.7, -105.9, 11.9), "L123": (253.9, 198.3, 319.2), "L219": (421.4, 386.3, 462.5),
        "L325": (622.3, 454.9, 800.5), "L0-us-east-1": (193.9, 138.8, 274.7), "L14": (275.0, 222.7, 311.9),
        "L0-ap-northeast-1": (471.5, 410.8, 544.6), "L30": (552.6, 425.2, 661.6),
    },
    "Hybrid vs. PQC": {
        "L0-sa-east-1": (240.0, 163.8, 310.3), "L123": (204.1, 146.1, 282.0), "L219": (274.1, 138.4, 340.7),
        "L325": (395.4, 149.4, 655.2), "L0-us-east-1": (174.7, 81.7, 278.1), "L14": (189.9, 114.4, 255.8),
        "L0-ap-northeast-1": (332.5, 178.3, 425.9), "L30": (298.4, 181.7, 396.6),
    },
}


def main():
    result = {"bias_range_ms": [BIAS_LOW_MS, BIAS_HIGH_MS], "n_chamadas_reais_por_execucao": N_CHAMADAS_REAIS_POR_EXECUCAO,
               "comparisons": {}, "ci_shift_check": {}}
    any_sign_flip = False
    any_ci_zero_change = False
    for pair, routes in OFICIAL_DIF_MS.items():
        result["comparisons"][pair] = {}
        for route, dif_obs in routes.items():
            if pair == "PQC vs. Classic":
                true_lo, true_hi = dif_obs + BIAS_LOW_MS, dif_obs + BIAS_HIGH_MS
            else:
                true_lo, true_hi = dif_obs - BIAS_HIGH_MS, dif_obs - BIAS_LOW_MS
            sign_flip = (true_lo < 0) != (dif_obs < 0) or (true_hi < 0) != (dif_obs < 0)
            any_sign_flip = any_sign_flip or sign_flip
            result["comparisons"][pair][route] = {
                "dif_observado_ms": dif_obs,
                "dif_corrigido_faixa_ms": [round(true_lo, 1), round(true_hi, 1)],
                "pode_trocar_de_sinal": sign_flip,
            }

    for pair, routes in OFICIAL_HL_CI_MS.items():
        result["ci_shift_check"][pair] = {}
        for route, (hl, lo, hi) in routes.items():
            if pair == "PQC vs. Classic":
                shifted_lo_range = [lo + BIAS_LOW_MS, lo + BIAS_HIGH_MS]
                shifted_hi_range = [hi + BIAS_LOW_MS, hi + BIAS_HIGH_MS]
            else:
                shifted_lo_range = [lo - BIAS_HIGH_MS, lo - BIAS_LOW_MS]
                shifted_hi_range = [hi - BIAS_HIGH_MS, hi - BIAS_LOW_MS]
            included_zero_before = lo <= 0 <= hi
            included_zero_after_any = any(a <= 0 <= b for a, b in [
                (shifted_lo_range[0], shifted_hi_range[1]), (shifted_lo_range[1], shifted_hi_range[0])
            ]) or (shifted_lo_range[0] <= 0) or (shifted_lo_range[1] <= 0)
            changed = included_zero_before != included_zero_after_any
            any_ci_zero_change = any_ci_zero_change or changed
            result["ci_shift_check"][pair][route] = {
                "ci_publicado_ms": [lo, hi], "incluia_zero_antes": included_zero_before,
                "limite_inferior_deslocado_faixa_ms": [round(shifted_lo_range[0], 1), round(shifted_lo_range[1], 1)],
                "cruza_zero_depois_do_deslocamento": included_zero_after_any,
                "mudou": changed,
            }

    result["algum_sinal_trocou_nas_16_comparacoes"] = any_sign_flip
    result["algum_ic_mudou_relacao_com_zero"] = any_ci_zero_change
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
