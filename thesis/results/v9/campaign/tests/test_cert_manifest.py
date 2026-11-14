"""Testes de cert_manifest.py (Decisao 166, item 3) -- certificados
RSA reais e descartaveis gerados na hora (nunca os certificados de
producao, nunca uma chave privada no manifesto)."""
import datetime
import sys
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cert_manifest  # noqa: E402


def _throwaway_cert_pem(common_name: str) -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject).issuer_name(issuer).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now).not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM)


@pytest.fixture
def fake_certs_dir(tmp_path):
    d = tmp_path / "certs"
    d.mkdir()
    for name in cert_manifest.MANIFEST_FILENAMES:
        (d / name).write_bytes(_throwaway_cert_pem(name))
    return d


def test_compute_manifest_cobre_todos_os_arquivos(fake_certs_dir):
    manifest = cert_manifest.compute_manifest(fake_certs_dir)
    assert set(manifest["files"]) == set(cert_manifest.MANIFEST_FILENAMES)


def test_compute_manifest_nunca_inclui_chave_privada(fake_certs_dir):
    manifest = cert_manifest.compute_manifest(fake_certs_dir)
    dump = str(manifest)
    assert "PRIVATE KEY" not in dump and "BEGIN RSA" not in dump


def test_compute_manifest_falha_se_arquivo_ausente(tmp_path):
    empty = tmp_path / "vazio"
    empty.mkdir()
    with pytest.raises(RuntimeError, match="nao existe"):
        cert_manifest.compute_manifest(empty)


def test_verify_manifest_sem_divergencia_quando_conjunto_bate(fake_certs_dir):
    manifest = cert_manifest.compute_manifest(fake_certs_dir)
    assert cert_manifest.verify_manifest(fake_certs_dir, manifest) == {}


def test_verify_manifest_detecta_arquivo_regenerado(fake_certs_dir):
    manifest = cert_manifest.compute_manifest(fake_certs_dir)
    (fake_certs_dir / "ca.crt").write_bytes(_throwaway_cert_pem("ca.crt (regenerado, outro lote)"))
    mismatches = cert_manifest.verify_manifest(fake_certs_dir, manifest)
    assert "ca.crt" in mismatches
    assert len(mismatches) == 1, f"so ca.crt deveria divergir -- {mismatches}"


def test_pem_bytes_e_der_bytes_diferem_e_sao_positivos(fake_certs_dir):
    manifest = cert_manifest.compute_manifest(fake_certs_dir)
    entry = manifest["files"]["ca.crt"]
    assert entry["pem_bytes"] > entry["der_bytes"] > 0, (
        "PEM (base64 + marcadores) tem que ser maior que o DER cru -- " + str(entry)
    )


def test_repo_real_bate_com_o_manifesto_congelado():
    """O proprio conjunto comitado em mock-service-os/certs tem que
    bater com thesis/results/v9/campaign/certs_manifest.json -- se
    este teste falhar, o conjunto real foi regenerado e o manifesto
    (alem do gabarito de ca_handler_test.go) precisa ser recalculado
    antes de qualquer campanha oficial (ver Decisao 166)."""
    repo_root = Path(__file__).resolve().parents[5]
    manifest_path = repo_root / "thesis" / "results" / "v9" / "campaign" / "certs_manifest.json"
    certs_dir = repo_root / "mock-service-os" / "certs"
    manifest = cert_manifest.load_manifest(manifest_path)
    mismatches = cert_manifest.verify_manifest(certs_dir, manifest)
    assert mismatches == {}, f"conjunto real divergiu do manifesto congelado -- {mismatches}"
