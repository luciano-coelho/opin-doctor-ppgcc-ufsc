#!/usr/bin/env python3
"""v9, campanha oficial (Decisao 140): calcula o OPINsize sobre o JSON
BRUTO das 320 execucoes oficiais reais -- script NOVO, versionado,
separado do orchestrator.py (etapa de analise independente, nunca
roda durante a campanha, nunca e importado por ela).

Fontes de cada insumo, TODAS medidas nos dados reais desta campanha,
nunca estimadas:
  - N_mTLS=6: contagem real de streams TCP distintos com SNI "mtls"
    numa captura dedicada (confirmado nas 32 capturas, constante nos
    4 perfis -- ver Decisao 140).
  - N_JWT=28: contagem real de entradas em `jwt_sig_breakdown` por
    execucao (= contagem do campo `jwts`), constante nos 4 perfis e
    nas 320 execucoes (recomputado aqui, nunca copiado de memoria).
  - N_JWK=4: contagem real de chamadas `/jwks` por execucao (2
    sessoes x 2 chamadas cada), constante.
  - N_PKI=4: contagem real de chamadas `/root-ca.pem`+`/issuer-ca.pem`
    por execucao (2+2), constante.
  - handshake_bytes: soma real dos tamanhos de mensagem de handshake
    TLS (coluna de tamanhos do tshark, NUNCA o tcp.len bruto do
    segmento -- esse inclui dados de aplicacao da mesma conexao
    reaproveitada) de UM stream mTLS (stream 0) nas capturas
    dedicadas (`criterio1_capturas/{perfil}_{rota}.log`) -- idem
    pros 4 perfis, confirmado identico em qualquer rota testada.
    Nota de transparencia: este valor diverge em ~238B, CONSISTENTE
    nos 4 perfis, do campo `handshakeBytesIn+handshakeBytesOut` que o
    proprio gateway loga por conexao real -- a causa exata dessa
    diferenca (provavel contabilidade de registro TLS/MAC nao
    marcada com tipo de handshake pelo filtro do tshark) nao foi
    investigada a fundo; reportado aqui como esta, nunca escondido
    nem forcado a bater.
  - jwt_sig_bytes / jwk_response_bytes / pki_response_bytes: media
    real, calculada direto de `piloto_calls.json` (`jwt_sig_breakdown`,
    `jwk_sizes`/`response_bytes` dos campos `/jwks`, `response_bytes`
    dos campos `/root-ca.pem`/`/issuer-ca.pem`), agregada nas 320
    execucoes reais.

Formula (identica a `campaign/scripts/opinsize_analysis.py`, nunca
reinventada): OPINsize = N_mTLS*handshake_bytes + N_JWT*jwt_sig_bytes
+ N_JWK*jwk_bytes [+ N_PKI*pki_bytes, so na variante de 4 termos desta
tese]. A variante de TRES termos (sem PKI) e a diretamente comparavel
contra a Eq. 3.1 de Schardong et al. (CANS 2022) -- reportada em
separado, nunca somada silenciosamente com o termo de PKI/CRL.

Uso:
  python thesis/scripts/opinsize_v9_oficial.py \
    --calls-json <piloto_calls.json real> \
    --capturas-dir <criterio1_capturas/ real> \
    --out <opinsize_v9_oficial.json>
"""
import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

PROFILES = ["classico", "pqc", "hibrido-v8", "hibrido-and"]
PKI_ENDPOINTS = {"/root-ca.pem", "/issuer-ca.pem"}


def _handshake_bytes_from_capture(capturas_dir: Path, profile: str) -> tuple[int, str]:
    """Soma real dos tamanhos de mensagem de handshake (coluna 6,
    NUNCA tcp.len/coluna 4) de UM stream mTLS (stream 0) -- pega a
    PRIMEIRA captura real encontrada pra este perfil (qualquer rota
    serve, confirmado identico em todas: Decisao 140)."""
    for fp in sorted(capturas_dir.glob(f"{profile}_*.log")):
        lines = fp.read_text(encoding="utf-8").splitlines()[2:]
        total = 0
        found_stream0 = False
        for line in lines:
            parts = line.split("\t")
            if len(parts) < 6:
                continue
            stream, sizes_col = parts[1], parts[5]
            if stream != "0" or not sizes_col:
                continue
            found_stream0 = True
            total += sum(int(x) for x in sizes_col.split(","))
        if found_stream0:
            return total, fp.name
    raise RuntimeError(f"nenhuma captura com stream 0 encontrada pro perfil {profile} em {capturas_dir}")


def _jwt_sig_bytes(entry: dict) -> int:
    """Bytes de assinatura de UM JWT (classical+pq somados, 0 se for
    `jwe` -- encriptado, sem assinatura propria). Nunca usa o token
    bruto (nao persistido por desenho, Decisao 139/140) -- so os
    campos ja calculados por `baseline_automation.jwt_sig_breakdown`
    na hora da execucao real."""
    c = entry.get("classical_sig_bytes") or 0
    p = entry.get("pq_sig_bytes") or 0
    return c + p


def analyze(calls_json: Path, capturas_dir: Path) -> dict:
    executions = json.loads(calls_json.read_text(encoding="utf-8"))

    by_profile = defaultdict(list)
    for e in executions:
        by_profile[e["profile"]].append(e)

    report = {"source_executions": calls_json.name, "n_total_executions": len(executions), "profiles": {}}

    for profile in PROFILES:
        execs = by_profile.get(profile, [])
        if not execs:
            continue

        n_jwt_per_exec = []
        n_jwk_per_exec = []
        n_pki_per_exec = []
        jwt_sig_sizes_all = []
        jwk_response_sizes_all = []
        pki_response_sizes_all = []
        construction_counts = Counter()

        for e in execs:
            calls = e["insurance"]
            jwt_count = 0
            jwk_count = 0
            pki_count = 0
            for c in calls:
                breakdown = c.get("jwt_sig_breakdown", [])
                jwt_count += len(breakdown)
                for b in breakdown:
                    construction_counts[b["construction"]] += 1
                    jwt_sig_sizes_all.append(_jwt_sig_bytes(b))
                if c["endpoint"] == "/jwks":
                    jwk_count += 1
                    jwk_response_sizes_all.append(c["response_bytes"])
                if c["endpoint"] in PKI_ENDPOINTS:
                    pki_count += 1
                    pki_response_sizes_all.append(c["response_bytes"])
            n_jwt_per_exec.append(jwt_count)
            n_jwk_per_exec.append(jwk_count)
            n_pki_per_exec.append(pki_count)

        n_jwt_distinct = sorted(set(n_jwt_per_exec))
        n_jwk_distinct = sorted(set(n_jwk_per_exec))
        n_pki_distinct = sorted(set(n_pki_per_exec))
        if len(n_jwt_distinct) != 1 or len(n_jwk_distinct) != 1 or len(n_pki_distinct) != 1:
            raise RuntimeError(
                f"{profile}: N_JWT/N_JWK/N_PKI NAO constantes entre as {len(execs)} execucoes reais "
                f"-- N_JWT={n_jwt_distinct} N_JWK={n_jwk_distinct} N_PKI={n_pki_distinct} "
                f"(abortando, nunca assumindo um valor fixo sobre dado divergente)"
            )
        n_jwt, n_jwk, n_pki = n_jwt_distinct[0], n_jwk_distinct[0], n_pki_distinct[0]
        n_mtls = 6  # Decisao 140: confirmado real nas 32 capturas dedicadas, constante nos 4 perfis

        handshake_bytes, capture_source = _handshake_bytes_from_capture(capturas_dir, profile)
        jwt_sig_avg = round(statistics.mean(jwt_sig_sizes_all), 2)
        jwk_avg = round(statistics.mean(jwk_response_sizes_all), 2)
        pki_avg = round(statistics.mean(pki_response_sizes_all), 2)

        term_mtls = n_mtls * handshake_bytes
        term_jwt = round(n_jwt * jwt_sig_avg, 2)
        term_jwk = round(n_jwk * jwk_avg, 2)
        term_pki = round(n_pki * pki_avg, 2)

        report["profiles"][profile] = {
            "n_executions": len(execs),
            "n_mtls": n_mtls,
            "n_jwt": n_jwt, "n_jwk": n_jwk, "n_pki": n_pki,
            "handshake_bytes_per_connection": handshake_bytes,
            "handshake_bytes_source_capture": capture_source,
            "jwt_sig_bytes_avg": jwt_sig_avg,
            "jwt_construction_counts_per_execution": dict(construction_counts),
            "jwk_response_bytes_avg": jwk_avg,
            "pki_response_bytes_avg": pki_avg,
            "term_mtls_handshake": term_mtls,
            "term_jwt": term_jwt,
            "term_jwk": term_jwk,
            "term_pki_crl": term_pki,
            "opinsize_3_termos_sem_pki_comparavel_schardong_eq3_1": round(term_mtls + term_jwt + term_jwk, 2),
            "opinsize_4_termos_com_pki_extensao_desta_tese": round(term_mtls + term_jwt + term_jwk + term_pki, 2),
        }

    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calls-json", required=True, type=Path)
    ap.add_argument("--capturas-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    report = analyze(args.calls_json, args.capturas_dir)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
