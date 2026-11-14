#!/usr/bin/env python3
"""Decisao 166, item 3 (pedido do Luciano): congela o conjunto de
certificados PUBLICOS de `mock-service-os/certs` que a campanha
entrega (`deliver_source.py`'s COMMON_FILES ja inclui o diretorio
inteiro, pra todo servidor e cliente) -- so os arquivos listados em
`MANIFEST_FILENAMES` abaixo: a CA, o par root/issuer de cada perfil
(classico/pqc/hibrido-v8), o certificado de servidor da carve-out
interna do gateway (`mtls_internal_server.crt`), e os certificados de
cliente/servidor do mTLS real (`client_one*`/`mtls*`).

Registra, por arquivo, SO sha256 + tamanho DER + tamanho PEM -- NUNCA
chave privada nem qualquer material secreto (os `.key` correspondentes
ficam de fora deste manifesto, permanecem gitignorados como sempre).

Regenerar certificados (mock-service-os/certs/main.go) ANTES de uma
campanha oficial muda o sha256/tamanho de qualquer arquivo listado
aqui -- exige recalcular este manifesto (rode `--write` de novo) E o
termo de PKI do gabarito que thesis/results/v9/integration/gateway/
ca_handler_test.go's TestDirectoryHandlerResponseBytesMatchesFrozenManifest
fixa (ver Decisao 166, DECISIONS.md) ANTES de rodar qualquer campanha
contra o novo conjunto -- os dois tem que andar juntos ou os criterios
de byte-size da campanha ficam incoerentes com o que o gateway serve
de verdade.

Uso:
  python cert_manifest.py --write ../certs_manifest.json   # (re)gera
  python cert_manifest.py --verify ../certs_manifest.json  # confere
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization

MANIFEST_FILENAMES = [
    "ca.crt",
    "root_ca.crt",
    "root_ca_rsa2048.crt",
    "root_ca_pqc.crt",
    "root_ca_hybrid.crt",
    "issuer_ca.crt",
    "issuer_ca_rsa2048.crt",
    "issuer_ca_pqc.crt",
    "issuer_ca_hybrid.crt",
    "mtls_internal_server.crt",
    "client_one.crt",
    "client_one_hybrid.crt",
    "client_one_pqc.crt",
    "mtls.crt",
    "mtls_hybrid.crt",
    "mtls_pqc.crt",
]

_POLICY = (
    "Decisao 166. Regenerar qualquer certificado listado aqui exige recalcular "
    "este manifesto (python cert_manifest.py --write) E o gabarito de PKI que "
    "ca_handler_test.go's TestDirectoryHandlerResponseBytesMatchesFrozenManifest "
    "fixa, ANTES de qualquer campanha oficial contra o novo conjunto -- ver "
    "DECISIONS.md. So sha256 + tamanho (DER/PEM); nenhuma chave privada aqui."
)


def _cert_entry(path: Path) -> dict:
    pem_bytes = path.read_bytes()
    cert = x509.load_pem_x509_certificate(pem_bytes)
    der_bytes = cert.public_bytes(serialization.Encoding.DER)
    return {
        "sha256": hashlib.sha256(pem_bytes).hexdigest(),
        "pem_bytes": len(pem_bytes),
        "der_bytes": len(der_bytes),
    }


def compute_manifest(certs_dir: Path) -> dict:
    files = {}
    for name in MANIFEST_FILENAMES:
        path = certs_dir / name
        if not path.exists():
            raise RuntimeError(f"compute_manifest: {path} nao existe -- manifesto exige todos os {len(MANIFEST_FILENAMES)} arquivos")
        files[name] = _cert_entry(path)
    return {"_policy": _POLICY, "files": files}


def load_manifest(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify_manifest(certs_dir: Path, manifest: dict) -> dict:
    """Compara o manifesto contra os arquivos reais em `certs_dir`
    (local -- comparacao byte a byte completa, usada pelo item 3's
    confirmacao de que o conjunto do repositorio e o oficial). Devolve
    {} se tudo bate; um dict de divergencias (nome -> {esperado, obtido})
    caso contrario -- nunca levanta excecao aqui (quem chama decide se
    e fail-closed ou so relatorio)."""
    current = compute_manifest(certs_dir)
    mismatches = {}
    for name, expected in manifest["files"].items():
        got = current["files"].get(name)
        if got != expected:
            mismatches[name] = {"expected": expected, "got": got}
    return mismatches


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--certs-dir", default=str(Path(__file__).resolve().parents[5] / "mock-service-os" / "certs"))
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", metavar="PATH", help="(re)gera o manifesto e grava em PATH")
    group.add_argument("--verify", metavar="PATH", help="confere o conjunto atual contra o manifesto em PATH")
    args = ap.parse_args()

    certs_dir = Path(args.certs_dir)
    if args.write:
        manifest = compute_manifest(certs_dir)
        Path(args.write).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"manifesto gravado em {args.write} ({len(manifest['files'])} certificados)")
        return 0

    manifest = load_manifest(Path(args.verify))
    mismatches = verify_manifest(certs_dir, manifest)
    if mismatches:
        print(json.dumps(mismatches, indent=2, ensure_ascii=False))
        return 1
    print(f"OK -- {len(manifest['files'])} certificados batem com {args.verify}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
