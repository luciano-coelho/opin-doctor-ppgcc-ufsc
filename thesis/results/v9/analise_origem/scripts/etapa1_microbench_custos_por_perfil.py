#!/usr/bin/env python3
"""Degrau 1, verificacao do intercepto `a` (item 5b): custos DEPENDENTES
DE PERFIL que ocorrem dentro da janela do orquestrador (t0..t1) mas FORA
de t_start..t_end de latency_automation.run_once_timed() -- confirmados
no codigo (opin_flow.py load_client_signing_key(), orchestrator.py
start_block()). Microbenchmark LOCAL (notebook do operador, MESMO
hardware ja declarado em data/microbench_hardware.txt), usando chaves
RSA GERADAS AQUI (nunca a chave real da campanha/client_one.jwks --
nunca lida nem copiada, nem de nenhum worktree de outra sessao).

CORRECAO (achado da quinta auditoria independente, nao da primeira
versao deste script): thesis/results/v9/DECISIONS.md, Decisao 113
(2026-11-10) -- as chaves RSA proprias do client_one foram ROTACIONADAS
de 4096 para 2048 bits, em TODOS os 4 perfis, ANTES do congelamento. A
campanha oficial real (Decisao 188/189, janela 2026-11-15/16) rodou
DEPOIS dessa rotacao -- ou seja, a chave REAL usada por
load_client_signing_key() na campanha e RSA-2048, nao RSA-4096. Este
script agora mede AMBOS os tamanhos: RSA-2048 (o tamanho REAL,
confirmado pela Decisao 113 em DECISIONS.md -- NUNCA confirmado lendo o
arquivo de chave privada real em si, que nao e tocado por este
script) e RSA-4096 (mantido so por transparencia -- era a premissa
ERRADA da primeira versao desta analise, superada por este achado).
So dados locais, nunca aquecimentos."""
import json
import statistics as st
import time
from pathlib import Path

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

OUT = Path(__file__).resolve().parents[1] / "data" / "etapa1_microbench_custos_por_perfil.json"
N_REPS = 30


def bench_from_jwk(key_size_bits):
    key = rsa.generate_private_key(public_exponent=65537, key_size=key_size_bits)
    priv_jwk = json.loads(jwt.algorithms.RSAAlgorithm(jwt.algorithms.RSAAlgorithm.SHA256).to_jwk(key))
    durations_ms = []
    for _ in range(N_REPS):
        t0 = time.monotonic()
        jwt.algorithms.RSAAlgorithm(jwt.algorithms.RSAAlgorithm.SHA256).from_jwk(json.dumps(priv_jwk))
        durations_ms.append((time.monotonic() - t0) * 1000.0)
    return {
        "median": st.median(durations_ms), "mean": st.mean(durations_ms),
        "min": min(durations_ms), "max": max(durations_ms), "stdev": st.stdev(durations_ms),
    }


def main():
    bench_2048 = bench_from_jwk(2048)
    bench_4096 = bench_from_jwk(4096)

    result = {
        "note_correcao": (
            "RSA-2048 e o tamanho REAL usado pela campanha oficial (confirmado via "
            "thesis/results/v9/DECISIONS.md, Decisao 113 -- rotacao 4096->2048 em "
            "2026-11-10, ANTES da janela oficial 2026-11-15/16 -- nunca confirmado "
            "lendo o arquivo de chave privada real, que este script nao toca). "
            "RSA-4096 mantido abaixo so por transparencia -- era a premissa ERRADA "
            "da primeira versao desta analise."
        ),
        "hardware": "notebook do operador, Intel Core 7 150U (mesmo de data/microbench_hardware.txt)",
        "n_repetitions": N_REPS,
        "from_jwk_duration_ms": {
            "rsa_2048_REAL": bench_2048,
            "rsa_4096_premissa_anterior_incorreta": bench_4096,
        },
        "razao_4096_vs_2048": bench_4096["median"] / bench_2048["median"],
        "campaign_documented_value_ms": {
            "value": 252, "key_size_assumed_in_comment": "nao especificado no comentario, mas calculado na era RSA-4096 (anterior a Decisao 113)",
            "source": (
                "Comentario em thesis/scripts/opin_flow.py, load_client_signing_key() "
                "(linhas ~574-594), citando 'Decision 99' e 'the diagnostic's own real "
                "setup_timings (median classic/hybrid ~252ms x2, pqc ~0ms x2)'. NENHUM "
                "outro documento (DECISIONS.md de v9 ou anteriores) contem o diagnostico "
                "original com data/hardware -- so esta referencia dentro do proprio "
                "comentario de codigo foi encontrada (busca feita, nao assumida). O "
                "comentario nunca foi atualizado apos a Decisao 113 (rotacao de chave) "
                "-- plausivelmente medido quando a chave ainda era RSA-4096."
            ),
        },
        "profile_dependence_confirmed_in_code": {
            "classico": "SIM -- cai no ramo else de load_client_signing_key() (opin_flow.py:650-655), chama RSAAlgorithm.from_jwk()",
            "hibrido-and": "SIM -- ramo elif explicito (opin_flow.py:628-649), chama RSAAlgorithm.from_jwk() pra classic_key (metade classica do par)",
            "hibrido-v8": "SIM (por eliminacao de ramo -- nao tem elif proprio, cai no ramo else igual a classico, opin_flow.py:650-655)",
            "pqc": "NAO -- ramo if crypto_profile=='pqc' (opin_flow.py:623-627) retorna o JWK bruto, nunca chama RSAAlgorithm.from_jwk()",
        },
        "node_signer_process_start_per_execution": {
            "confirmed": False,
            "evidence": (
                "campaign_client_runner.py (docstring): 'Does NOT manage the TLS proxy / "
                "PQC signer service lifecycle -- that is scoped to the whole profile BLOCK "
                "(Decision 56), started once before round-robin begins and stopped once "
                "after'. Confirmado em orchestrator.py: start_block() (que chama "
                "of.start_pqc_signer_service()/of.start_tls_kem_proxy()) e invocado UMA VEZ "
                "por bloco perfil/rota (linha 2280), ANTES do loop de run_execution() "
                "(linha 2317-2319) -- NUNCA dentro da janela t0..t1 de uma execucao "
                "individual. O custo de start do processo Node/Go e amortizado sobre as "
                "N_PER_PROFILE execucoes do bloco, nao pago a cada execucao."
            ),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
