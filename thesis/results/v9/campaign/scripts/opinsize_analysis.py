#!/usr/bin/env python3
"""v9, piloto: script de ANALISE (nunca altera o coletor real --
`thesis/scripts/baseline_automation.py:extract_jwts()` -- que
continua medindo o token JWT INTEIRO, confirmado nesta mesma rodada
por leitura do codigo real, nao por suposicao).

Pedido do Luciano: emitir o OPINsize em DUAS variantes -- (a) usando
o tamanho TOTAL do token JWT (o que o coletor real ja mede hoje) e
(b) usando SO o tamanho da assinatura isolada (decodificada,
terceira parte do JWT compacto) -- pra comparar contra a Equacao 3.1
de Schardong et al. (2022).

Achado real desta rodada, ao procurar a fonte: o proprio repositorio
(thesis/scripts/report_build/ARCHITECTURE.tpl.md linha 155,
CONSOLIDATED_REPORT.tpl.md linha 72, thesis/results/v7/v8
Consolidated_Metrics_Report_FINAL.md) cita a Eq. 3.1 de Schardong
como as TRES primeiros termos da formula ORIGINAL --

    OPINsize = N_mTLS x handshake_bytes + N_JWT x JWT_size + N_JWK x JWK_PK_size

-- e documenta explicitamente que esta tese ESTENDE essa equacao com
um QUARTO termo, N_PKI x PKI_bytes, desde a v5 (ver Decisao 7 da
v4/v5, "Secao 7" do ARCHITECTURE.md). O termo PKI/CRL e, portanto,
mantido SEPARADO dos outros tres nos DOIS sentidos pedidos pelo
Luciano: (1) e reportado como sua propria linha em toda saida deste
script, nunca somado dentro do termo de token; (2) o script emite as
DUAS somas -- a de 3 termos (equivalente a Eq. 3.1 original, SEM
PKI) e a de 4 termos (formula estendida desta tese, COM PKI) -- pra
cada uma das duas variantes de tamanho de JWT.

O que Schardong et al. definem exatamente por "JWT_size" (token
inteiro ou so a assinatura) NAO esta confirmado: o artigo em si nao
esta neste repositorio (so e citado como referencia bibliografica, a
ser completada pelo autor -- ver ARCHITECTURE.tpl.md linha 255). Por
isso o script emite as duas variantes lado a lado, em vez de assumir
qual delas Schardong realmente mede.

Limitacao real encontrada e reportada, nao escondida: o pipeline de
coleta hoje (`compute_metrics()`, baseline_automation.py:602-715) so
persiste `jwt_sizes_bytes` (uma lista de tamanhos, token inteiro) no
`baseline_metrics.json` final -- os textos BRUTOS dos JWTs (`jwts`,
por chamada, linha 475) nunca sao escritos em disco pelo pipeline
padrao. Por isso a variante (b), so-assinatura, NAO pode ser
recalculada retroativamente a partir de um `baseline_metrics.json`
ja coletado -- so funciona com uma lista de JWTs BRUTOS, vinda de
uma captura fresca (uma nova chamada a `extract_jwts()` que ainda
tenha os textos, ou uma captura de pacote/log que preserve o token
completo).
"""
import argparse
import base64
import json
import statistics
import sys
from pathlib import Path


def jwt_total_size_bytes(token: str) -> int:
    """O que o coletor real mede hoje: o token compacto inteiro
    (header.payload.signature, base64url, os tres segmentos e os
    dois pontos), exatamente como aparece no fio -- igual a
    extract_jwts()/len(token) em baseline_automation.py."""
    return len(token)


def jwt_signature_size_bytes(token: str) -> int:
    """Variante nova pedida pelo Luciano: SO o terceiro segmento do
    JWT compacto, decodificado de base64url pros bytes brutos da
    assinatura (nunca o texto base64url, que e ~33% maior que o
    binario que representa)."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError(
            f"token nao esta no formato JWS compacto (esperado 3 partes separadas por '.', "
            f"recebido {len(parts)}): {token[:24]}..."
        )
    sig_b64url = parts[2]
    padded = sig_b64url + "=" * (-len(sig_b64url) % 4)
    return len(base64.urlsafe_b64decode(padded))


def _term(n, per_item_bytes):
    return n * per_item_bytes


def compute_opinsize_variant(jwts, jwt_size_fn, n_mtls, handshake_bytes, n_jwk, jwk_pk_size, n_pki, pki_bytes) -> dict:
    jwt_sizes = [jwt_size_fn(j) for j in jwts]
    n_jwt = len(jwt_sizes)
    jwt_size_avg = round(statistics.mean(jwt_sizes), 2) if jwt_sizes else 0.0

    term_mtls = _term(n_mtls, handshake_bytes)
    term_jwt = round(n_jwt * jwt_size_avg, 2)
    term_jwk = _term(n_jwk, jwk_pk_size)
    term_pki = _term(n_pki, pki_bytes)

    return {
        "n_mtls": n_mtls, "handshake_bytes": handshake_bytes, "term_mtls_handshake": term_mtls,
        "n_jwt": n_jwt, "jwt_size_avg_bytes": jwt_size_avg, "jwt_sizes_bytes": jwt_sizes, "term_jwt": term_jwt,
        "n_jwk": n_jwk, "jwk_pk_size_bytes": jwk_pk_size, "term_jwk": term_jwk,
        "n_pki": n_pki, "pki_bytes": pki_bytes, "term_pki_crl": term_pki,
        "opinsize_eq31_schardong_3_termos_sem_pki": round(term_mtls + term_jwt + term_jwk, 2),
        "opinsize_estendido_4_termos_com_pki": round(term_mtls + term_jwt + term_jwk + term_pki, 2),
    }


def compute_opinsize_both_variants(jwts, **kwargs) -> dict:
    return {
        "variante_a_token_total": compute_opinsize_variant(jwts, jwt_total_size_bytes, **kwargs),
        "variante_b_so_assinatura": compute_opinsize_variant(jwts, jwt_signature_size_bytes, **kwargs),
        "_nota_termo_pki": (
            "PKI_bytes/term_pki_crl e reportado como linha separada nas duas variantes, "
            "nunca somado dentro do termo de JWT; 'eq31_schardong_3_termos_sem_pki' e a soma "
            "SEM esse termo (equivalente a formula original de Schardong et al. 2022), "
            "'estendido_4_termos_com_pki' e a formula desta tese desde a v5/v7/v8."
        ),
    }


def _load_jwts_from_input(path: Path) -> list:
    """Aceita dois formatos: (1) uma lista JSON simples de strings
    JWT; (2) um objeto com uma lista de 'calls', cada um com um campo
    'jwts' (o mesmo formato que baseline_automation.py produz POR
    CHAMADA, antes de ser reduzido a so tamanhos em compute_metrics())."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list) and (not data or isinstance(data[0], str)):
        return data
    if isinstance(data, dict) and "calls" in data:
        jwts = []
        for c in data["calls"]:
            jwts.extend(c.get("jwts", []))
        return jwts
    raise ValueError(
        "formato de entrada nao reconhecido -- esperado uma lista JSON de strings JWT, "
        "ou um objeto {'calls': [{'jwts': [...]}, ...]}."
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jwts-file", required=True, help="JSON com os JWTs BRUTOS (lista de strings, ou {'calls':[{'jwts':[...]}]})")
    ap.add_argument("--n-mtls", type=int, required=True)
    ap.add_argument("--handshake-bytes", type=float, required=True)
    ap.add_argument("--n-jwk", type=int, required=True)
    ap.add_argument("--jwk-pk-size-bytes", type=float, required=True)
    ap.add_argument("--n-pki", type=int, required=True)
    ap.add_argument("--pki-bytes", type=float, required=True)
    ap.add_argument("--out", help="caminho de saida do JSON (default: stdout)")
    args = ap.parse_args()

    jwts = _load_jwts_from_input(Path(args.jwts_file))
    if not jwts:
        print("ABORTADO: nenhum JWT bruto encontrado no arquivo de entrada.", file=sys.stderr)
        sys.exit(2)

    result = compute_opinsize_both_variants(
        jwts,
        n_mtls=args.n_mtls, handshake_bytes=args.handshake_bytes,
        n_jwk=args.n_jwk, jwk_pk_size=args.jwk_pk_size_bytes,
        n_pki=args.n_pki, pki_bytes=args.pki_bytes,
    )
    out_text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(out_text, encoding="utf-8")
    else:
        print(out_text)


if __name__ == "__main__":
    main()
