#!/usr/bin/env python3
"""v9, piloto: script de ANALISE. O coletor real
(`thesis/scripts/baseline_automation.py`) persiste tanto o tamanho
TOTAL do token (`jwt_sizes_bytes`, ja existia) quanto, desde a
Decisao [N] desta mesma rodada, a quebra por assinatura
(`jwt_sig_breakdown` -- classica/PQ em bytes brutos, por construcao:
PS256 puro, ML-DSA-65 puro, Strong Nesting, payload extension; ver
jwt_sig_breakdown() em baseline_automation.py) -- nunca o token/
claims brutos.

Pedido do Luciano: emitir o OPINsize em DUAS variantes, EXPLICITAMENTE
rotuladas e nunca confundidas uma com a outra:

  - VARIANTE A (token completo): metrica PROPRIA desta tese --
    header+payload+assinatura, o JWT compacto inteiro no fio. NAO e
    o que Schardong et al. (2022) medem na Eq. 3.1/Tabela 4 -- nenhum
    texto deste script a chama de "equivalente a Eq. 3.1" (correcao
    explicita desta rodada; uma versao anterior deste script cometia
    esse erro).
  - VARIANTE B (assinatura bruta): JWT_sig_size no sentido que o
    Luciano confirmou da tese do Schardong (Cap. 3, Eq. 3.1/Tabela 4)
    -- so a assinatura, decodificada, em bytes brutos, SEM header e
    SEM payload. Esta e a variante comparavel de verdade contra
    Schardong (RSA-2048=256B; o proprio Schardong usa Dilithium3=
    3293B como referencia de outra implementacao -- este projeto usa
    ML-DSA-65, medido em 3309B, NAO 3293: numeros de implementacoes
    diferentes, nao um erro deste script).

O termo de PKI/CRL desta tese (extensao desde a v5, ver Decisao 7 da
v4/v5, "Secao 7" do ARCHITECTURE.md; a Eq. 3.1 original de Schardong
tem so 3 termos, SEM PKI) e mantido SEPARADO dos outros tres em toda
saida, nas DUAS variantes -- nunca somado dentro do termo de token.

Limitacao real, reportada e nao escondida: o pipeline de coleta hoje
(`compute_metrics()`, baseline_automation.py) persiste `jwt_sizes_bytes`
e `jwt_sig_breakdown` (tamanhos apenas) no `baseline_metrics.json`
final -- os textos BRUTOS dos JWTs nunca sao escritos em disco, por
desenho (privacidade dos dados experimentais, pedido explicito do
Luciano). Por isso a Variante B so pode ser calculada com uma lista
de JWTs BRUTOS vinda de uma captura FRESCA (uma chamada a
extract_jwts() que ainda tenha os textos em memoria), nunca
retroativamente a partir de um baseline_metrics.json ja coletado.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))
from baseline_automation import jwt_sig_breakdown  # noqa: E402


def jwt_total_size_bytes(token: str) -> int:
    """Variante A: o token compacto inteiro (header.payload.signature,
    base64url, os tres segmentos e os dois pontos), exatamente como
    aparece no fio -- igual a extract_jwts()/len(token) em
    baseline_automation.py. Metrica PROPRIA desta tese -- NAO e a
    mesma coisa que a Eq. 3.1 de Schardong et al. (ver ressalva abaixo
    e _nota_variantes); nenhum texto deste script a chama de
    'equivalente a Eq. 3.1'."""
    return len(token)


def jwt_signature_size_bytes(token: str) -> int:
    """Variante B: JWT_sig_size no sentido que o Luciano confirmou da
    tese do Schardong (Cap. 3, Eq. 3.1/Tabela 4) -- tamanho da
    assinatura em bytes BRUTOS, sem header e sem payload. Usa
    jwt_sig_breakdown() (baseline_automation.py), a MESMA regra por
    construcao que o coletor real agora persiste (Decisao [N]):
    PS256 puro = so a classica; ML-DSA-65 puro = so a PQ; Strong
    Nesting = sigma1+sigma2 (ja e o unico valor no 3o segmento, soma
    por definicao); payload extension = classica (3o segmento) MAIS a
    PQ embutida na claim 'pqc' (fisicamente separadas, por isso
    PRECISAM ser somadas aqui -- decodificar so o 3o segmento, como a
    rodada anterior deste script fazia, SUBESTIMARIA esses tokens)."""
    b = jwt_sig_breakdown(token)
    classical = b["classical_sig_bytes"] or 0
    pq = b["pq_sig_bytes"] or 0
    if classical == 0 and pq == 0:
        raise ValueError(
            f"jwt_sig_breakdown nao reconheceu a construcao deste token "
            f"(construction={b['construction']!r}) -- nao e um JWS de 3 "
            f"segmentos com alg PS256/ML-DSA-65/MLDSA65-RSA2048-PSS-SHA256: "
            f"{token[:24]}..."
        )
    return classical + pq


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
        # Nomes neutros de proposito -- a rotulagem de qual variante e
        # comparavel a Schardong Eq. 3.1 fica so em
        # compute_opinsize_both_variants(), nunca aqui (os dois
        # variantes compartilham este mesmo schema).
        "opinsize_3_termos_sem_pki": round(term_mtls + term_jwt + term_jwk, 2),
        "opinsize_4_termos_com_pki_extensao_desta_tese": round(term_mtls + term_jwt + term_jwk + term_pki, 2),
    }


def compute_opinsize_both_variants(jwts, **kwargs) -> dict:
    return {
        "variante_a_token_total": {
            **compute_opinsize_variant(jwts, jwt_total_size_bytes, **kwargs),
            "_rotulo": (
                "Variante A -- token JWT completo (header+payload+assinatura). "
                "Metrica PROPRIA desta tese. NAO e equivalente a Eq. 3.1 de "
                "Schardong et al. (2022) -- nao compare estes numeros contra o "
                "artigo dele."
            ),
        },
        "variante_b_assinatura_bruta": {
            **compute_opinsize_variant(jwts, jwt_signature_size_bytes, **kwargs),
            "_rotulo": (
                "Variante B -- so a assinatura, decodificada, em bytes brutos "
                "(classica + PQ quando fisicamente separadas, ex. payload "
                "extension; ver jwt_sig_breakdown()). JWT_sig_size no sentido "
                "da Eq. 3.1/Tabela 4 de Schardong et al. (2022) -- esta e a "
                "variante comparavel contra aquele trabalho."
            ),
        },
        "_nota_termo_pki": (
            "PKI_bytes/term_pki_crl e reportado como linha separada nas duas variantes, "
            "nunca somado dentro do termo de JWT; 'opinsize_3_termos_sem_pki' e a soma "
            "SEM esse termo, 'opinsize_4_termos_com_pki_extensao_desta_tese' e a formula "
            "estendida desta tese desde a v5/v7/v8. So a Variante B (assinatura bruta, "
            "3 termos, sem PKI) e comparavel contra a Eq. 3.1 original de Schardong -- "
            "a Variante A nunca e, em nenhum dos dois somatorios."
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
