#!/usr/bin/env python3
"""v9, piloto: manifesto pre-campanha, somente leitura dos
certificados reais gerados por `thesis/results/v9/certs/` (`make
certs`) -- NUNCA gera nem altera chave alguma, so le o que ja existe
em `certs/generated/`.

Pedido do Luciano, apos a Decisao 120 (SAN e uniforme nos certs reais
da campanha, nunca "SAN-less" -- essa era so a caracterizacao dos
fixtures de teste sinteticos do `and.patch`, nunca os certs reais):
automatizar aquela confirmacao manual (feita uma vez com `openssl
x509 -ext subjectAltName`) num script reexecutavel, que ABORTA (exit
!= 0) se qualquer uma das invariantes de SAN quebrar, e que monta a
matriz artefato x perfil x participante com evidencia fresca a cada
chamada -- nunca copia os numeros de uma rodada anterior.

Nenhum segredo neste manifesto: so hash SHA-256 do DER publico de
cada certificado, SAN, algoritmo e tamanhos em bytes -- nunca chave
privada, nunca ID de conta/perfil/ARN (nao ha nada disso neste
dominio: certificados sao material publico por natureza).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "integration"))
import evaluate_criteria as ec  # noqa: E402  -- mesmo EXPECTED_CURVE que orchestrator.py usa no assert por execucao (_assert_profile_negotiated), nunca reinventado aqui

_DEFAULT_CERTS_DIR = Path(__file__).resolve().parents[2] / "certs" / "generated"

# Pedido do Luciano (Etapa 1, adendo "asserção do grupo TLS"): o
# manifesto pre-campanha tambem registra o grupo de troca de chaves
# ESPERADO por perfil -- fonte unica, igual ao assert ativo por
# execucao (_assert_profile_negotiated em orchestrator.py). Este
# manifesto nao negocia TLS nenhum (so le certificados estaticos), por
# isso so registra o ESPERADO aqui -- a confirmacao do NEGOCIADO de
# verdade, por execucao, e tarefa do assert em orchestrator.py, nunca
# duplicada neste script.
_MANIFEST_PROFILE_TO_EC_PROFILE = {
    "classico": "classico", "pqc": "pqc", "hibrido_v8": "hibrido-v8", "hibrido_and": "hibrido-and",
}

# OIDs das extensoes alt-signature do X.509 estendido (RFC draft de
# assinatura dupla, usado so pelo perfil Hibrido-v8 -- uma UNICA
# cadeia RSA, com a assinatura ML-DSA-65 embutida como extensao,
# nunca uma segunda cadeia separada; distinto do Hibrido-AND, que usa
# duas cadeias de verdade). Ver Decisao 61/68 (PINS.json) e
# `certs/main.go` para o gerador real.
_OID_ALT_SIG_ALGORITHM = x509.ObjectIdentifier("2.5.29.73")
_OID_ALT_SIG_VALUE = x509.ObjectIdentifier("2.5.29.74")
_OID_ALT_SUBJECT_PUBLIC_KEY_INFO = x509.ObjectIdentifier("2.5.29.72")

# Mapa fonte-unica dos nomes de arquivo reais em certs/generated/,
# por perfil e papel. "chains" tem 1 entrada pros perfis de cadeia
# unica (classico/pqc/hibrido_v8) e 2 pro Hibrido-AND (rsa + mldsa,
# cadeias independentes de verdade).
PROFILES = {
    "classico": {"chains": {"default": "classico"}},
    "pqc": {"chains": {"default": "pqc"}},
    "hibrido_v8": {"chains": {"default": "hibrido_v8"}, "has_alt_signature": True},
    "hibrido_and": {"chains": {"rsa": "hibrido_and_rsa", "mldsa": "hibrido_and_mldsa"}},
}
ROLES = ("ca", "server", "client")


def _load_cert(certs_dir: Path, stem: str, role: str) -> x509.Certificate:
    path = certs_dir / f"{stem}_{role}.crt"
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} nao existe -- rode 'make certs' em thesis/results/v9/certs/ antes do manifesto."
        )
    return x509.load_pem_x509_certificate(path.read_bytes())


def _san_dns_names(cert: x509.Certificate):
    try:
        ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    except x509.ExtensionNotFound:
        return []
    return list(ext.value.get_values_for_type(x509.DNSName))


def _pubkey_raw_bytes(cert: x509.Certificate) -> int:
    pk = cert.public_key()
    try:
        return len(pk.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
    except (ValueError, TypeError):
        # RSA e outras chaves classicas nao suportam Encoding.Raw --
        # cai pro tamanho do modulo em bytes (key_size e em bits).
        return pk.key_size // 8


def _describe_cert(cert: x509.Certificate) -> dict:
    der = cert.public_bytes(serialization.Encoding.DER)
    sig_oid = cert.signature_algorithm_oid
    entry = {
        "algoritmo_assinatura": sig_oid._name if sig_oid._name != "Unknown OID" else sig_oid.dotted_string,
        "tamanho_chave_bytes": _pubkey_raw_bytes(cert),
        "tamanho_assinatura_bytes": len(cert.signature),
        "tamanho_artefato_bytes": len(der),
        "sha256_der": hashlib.sha256(der).hexdigest(),
        "san": sorted(_san_dns_names(cert)),
        "subject_cn": cert.subject.rfc4514_string(),
    }
    return entry


def _describe_alt_signature(cert: x509.Certificate) -> dict | None:
    """Hibrido-v8 apenas: le as extensoes alt-signature embutidas no
    MESMO certificado (nao uma segunda cadeia). Os tamanhos aqui sao
    o OCTET STRING da extensao por completo (com o envelope ASN.1 da
    extensao em volta do BIT STRING/SubjectPublicKeyInfo interno),
    por isso ligeiramente maiores que o raw puro (1952/3309 bytes) ja
    confirmado em rodadas anteriores para ML-DSA-65 standalone --
    marcado explicitamente como "bruto da extensao" pra nao confundir
    os dois nessa matriz."""
    try:
        alg = cert.extensions.get_extension_for_oid(_OID_ALT_SIG_ALGORITHM)
        val = cert.extensions.get_extension_for_oid(_OID_ALT_SIG_VALUE)
        pub = cert.extensions.get_extension_for_oid(_OID_ALT_SUBJECT_PUBLIC_KEY_INFO)
    except x509.ExtensionNotFound:
        return None
    return {
        "alt_sig_algorithm_der_bytes": len(alg.value.value),
        "alt_sig_value_der_bytes_bruto_extensao": len(val.value.value),
        "alt_pubkey_der_bytes_bruto_extensao": len(pub.value.value),
    }


def build_manifest(certs_dir: Path) -> dict:
    matrix = {}
    for profile, cfg in PROFILES.items():
        matrix[profile] = {}
        for chain_name, stem in cfg["chains"].items():
            chain_entry = {}
            for role in ROLES:
                cert = _load_cert(certs_dir, stem, role)
                desc = _describe_cert(cert)
                if cfg.get("has_alt_signature") and role in ("server", "client"):
                    alt = _describe_alt_signature(cert)
                    if alt:
                        desc["alt_signature_mldsa65"] = alt
                chain_entry[role] = desc
            matrix[profile][chain_name] = chain_entry
    return matrix


def _san_of(matrix, profile, chain, role):
    return tuple(matrix[profile][chain][role]["san"])


def check_invariants(matrix: dict) -> list:
    """Cada item e (descricao, ok:bool, detalhe). Nunca aborta aqui --
    quem decide abortar e main(), depois de ver a lista completa."""
    checks = []

    # 1) Dentro do Hibrido-AND: a cadeia RSA e a cadeia ML-DSA-65
    # devem declarar o MESMO SAN, pro mesmo papel (server/client) --
    # sao duas cadeias de uma UNICA identidade, nunca duas identidades
    # diferentes coincidindo por acaso.
    for role in ("server", "client"):
        san_rsa = _san_of(matrix, "hibrido_and", "rsa", role)
        san_mldsa = _san_of(matrix, "hibrido_and", "mldsa", role)
        checks.append((
            f"Hibrido-AND, {role}: SAN identico entre a cadeia RSA e a cadeia ML-DSA-65",
            san_rsa == san_mldsa,
            f"rsa={san_rsa!r} mldsa={san_mldsa!r}",
        ))

    # 2) Entre os 4 perfis (achatando o Hibrido-AND pras suas 2
    # cadeias): o SAN do servidor deve ser o MESMO em todo perfil, e
    # o SAN do cliente deve ser o MESMO em todo perfil -- nenhum
    # perfil pode ter uma identidade de teste diferente dos outros 3.
    variants = [
        ("classico", "default"), ("pqc", "default"), ("hibrido_v8", "default"),
        ("hibrido_and", "rsa"), ("hibrido_and", "mldsa"),
    ]
    for role in ("server", "client"):
        sans = {f"{p}/{c}": _san_of(matrix, p, c, role) for p, c in variants}
        unique = set(sans.values())
        checks.append((
            f"Entre os 4 perfis, {role}: SAN identico em toda variante",
            len(unique) == 1,
            json.dumps({k: list(v) for k, v in sans.items()}, ensure_ascii=False) if len(unique) != 1 else "ok",
        ))

    # 3) Nos dois lados do mTLS: os dois checks acima (1 e 2) cobrem
    # tanto o papel "server" quanto o papel "client" -- este item so
    # confirma explicitamente que AMBOS os lados foram de fato
    # cobertos (nao e um check criptografico novo, e uma garantia de
    # cobertura do proprio script).
    sides_covered = {c[0].split(",")[1].strip().split(":")[0] for c in checks}
    checks.append((
        "Cobertura: checks 1 e 2 rodaram para os dois lados do mTLS (server e client)",
        sides_covered == {"server", "client"},
        f"lados cobertos={sorted(sides_covered)!r}",
    ))

    return checks


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--certs-dir", default=str(_DEFAULT_CERTS_DIR))
    ap.add_argument("--out", help="caminho de saida do manifesto JSON (default: stdout)")
    args = ap.parse_args()

    certs_dir = Path(args.certs_dir)
    try:
        matrix = build_manifest(certs_dir)
    except FileNotFoundError as e:
        print(f"ABORTADO: {e}", file=sys.stderr)
        sys.exit(2)

    checks = check_invariants(matrix)
    failed = [c for c in checks if not c[1]]

    manifest = {
        "_policy": "Manifesto pre-campanha, somente leitura. Nenhuma chave privada, ID de conta, ARN ou perfil neste arquivo -- so material publico (certificados) e hashes/tamanhos.",
        "certs_dir": str(certs_dir.resolve()),
        "grupo_tls_esperado_por_perfil": {
            profile: ec.EXPECTED_CURVE.get(ec_profile)
            for profile, ec_profile in _MANIFEST_PROFILE_TO_EC_PROFILE.items()
        },
        "matriz_artefato_perfil_participante": matrix,
        "invariantes_san": [{"check": desc, "ok": ok, "detalhe": detalhe} for desc, ok, detalhe in checks],
        "abortado": bool(failed),
    }

    out_text = json.dumps(manifest, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(out_text, encoding="utf-8")
    else:
        print(out_text)

    if failed:
        print(f"ABORTADO: {len(failed)} invariante(s) de SAN falharam -- ver 'invariantes_san' no manifesto.", file=sys.stderr)
        for desc, _, detalhe in failed:
            print(f"  - {desc}: {detalhe}", file=sys.stderr)
        sys.exit(1)

    print(f"OK: {len(checks)} invariante(s) de SAN confirmadas, manifesto com {sum(len(v) for v in matrix.values())} cadeia(s).", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
