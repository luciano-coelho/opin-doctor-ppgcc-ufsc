"""Testes de opin_flow.verify_ca_chain() -- os 4 perfis reais, mais
casos negativos. Classico nunca precisa do servico pqc-signer (so
RSA, via `cryptography`); pqc/hibrido-and precisam dele pra verificar
a metade ML-DSA-65 (fixture de modulo, subindo/parando o container
real UMA vez pra todos os testes deste arquivo -- nunca mockado,
nunca um segredo real envolvido, so material publico de CA)."""
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))
import opin_flow as of  # noqa: E402

CERTS = Path(__file__).resolve().parents[3] / "mock-service-os" / "certs"


def _docker_available() -> bool:
    try:
        return subprocess.run(["docker", "ps"], capture_output=True, timeout=10).returncode == 0
    except Exception:
        return False


@pytest.fixture(scope="module")
def pqc_signer():
    if not _docker_available():
        pytest.skip("Docker indisponivel nesta maquina/sessao -- verify_ca_chain com metade ML-DSA-65 precisa do servico pqc-signer real")
    started = of.start_pqc_signer_service("pqc")
    yield
    of.stop_pqc_signer_service(started)


@pytest.fixture(scope="module")
def certs():
    return {
        "root_rsa2048": (CERTS / "root_ca_rsa2048.crt").read_bytes(),
        "issuer_rsa2048": (CERTS / "issuer_ca_rsa2048.crt").read_bytes(),
        "root_pqc": (CERTS / "root_ca_pqc.crt").read_bytes(),
        "issuer_pqc": (CERTS / "issuer_ca_pqc.crt").read_bytes(),
        "root_hybrid": (CERTS / "root_ca_hybrid.crt").read_bytes(),
        "issuer_hybrid": (CERTS / "issuer_ca_hybrid.crt").read_bytes(),
    }


def test_classico_bundle_passa(certs):
    # Nunca precisa do pqc-signer -- so RSA.
    of.verify_ca_chain(certs["root_rsa2048"], certs["issuer_rsa2048"], "classico")


def test_pqc_bundle_passa(certs, pqc_signer):
    of.verify_ca_chain(certs["root_pqc"], certs["issuer_pqc"], "pqc")


def test_hibrido_v8_bundle_passa(certs, pqc_signer):
    of.verify_ca_chain(certs["root_hybrid"], certs["issuer_hybrid"], "hybrid")


def test_hibrido_and_bundle_passa(certs, pqc_signer):
    root_bundle = certs["root_rsa2048"] + certs["root_pqc"]
    issuer_bundle = certs["issuer_rsa2048"] + certs["issuer_pqc"]
    of.verify_ca_chain(root_bundle, issuer_bundle, "hibrido-and")


def test_negativo_issuer_no_lugar_de_root_classico(certs):
    """issuer_ca_rsa2048 nao e autoassinado (seu issuer e root_ca_rsa2048)
    -- colocado na posicao de "root", a checagem de autoassinatura
    tem que falhar."""
    with pytest.raises(of.SignatureVerificationError):
        of.verify_ca_chain(certs["issuer_rsa2048"], certs["issuer_rsa2048"], "classico")


def test_negativo_certificado_adulterado_classico(certs):
    """1 caractere base64 trocado no corpo do certificado -- base64/PEM
    ainda decodifica (sem exceção de parsing), mas o DER fica diferente
    do original, quebrando a assinatura."""
    lines = certs["root_rsa2048"].decode("ascii").splitlines()
    body_idx = [i for i, l in enumerate(lines) if l and not l.startswith("-----")]
    mid = body_idx[len(body_idx) // 2]
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    original_char = lines[mid][10]
    swap_char = next(c for c in alphabet if c != original_char)
    lines[mid] = lines[mid][:10] + swap_char + lines[mid][11:]
    tampered = ("\n".join(lines) + "\n").encode("ascii")
    with pytest.raises(of.SignatureVerificationError):
        of.verify_ca_chain(tampered, certs["issuer_rsa2048"], "classico")


def test_negativo_hibrido_and_bundle_com_so_1_certificado(certs, pqc_signer):
    """hibrido-and exige 2 blocos CERTIFICATE por endpoint -- um
    bundle com so 1 (ex.: so a metade RSA, sem a ML-DSA-65) tem que
    falhar explicitamente, nunca verificar silenciosamente so a
    metade presente."""
    with pytest.raises(of.SignatureVerificationError, match="2-certificate bundle"):
        of.verify_ca_chain(certs["root_rsa2048"], certs["issuer_rsa2048"], "hibrido-and")


def test_negativo_hibrido_and_metade_pqc_trocada_pela_do_controle(certs, pqc_signer):
    """A metade ML-DSA-65 do bundle hibrido-and tem que ser
    root_ca_pqc (autoassinada) -- trocando por root_ca_hybrid (RSA
    "catalyst" com extensao ML-DSA-65, estrutura totalmente
    diferente), a verificacao ML-DSA-65 tem que falhar."""
    root_bundle = certs["root_rsa2048"] + certs["root_hybrid"]
    issuer_bundle = certs["issuer_rsa2048"] + certs["issuer_pqc"]
    with pytest.raises(of.SignatureVerificationError):
        of.verify_ca_chain(root_bundle, issuer_bundle, "hibrido-and")
