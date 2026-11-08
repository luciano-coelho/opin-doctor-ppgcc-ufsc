"""Testes de deliver_images.py (Decisao 59) -- docker/ssh/scp stubados
via cli._run, nenhuma chamada real, nenhum dado sensivel."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cli  # noqa: E402
import deliver_images as di  # noqa: E402


class FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


_FAKE_BIN_BYTES = b"binario fake do gateway, so para teste\n"
_FAKE_BIN_SHA256 = hashlib.sha256(_FAKE_BIN_BYTES).hexdigest()


@pytest.fixture(autouse=True)
def _fake_pins(monkeypatch):
    monkeypatch.setattr(di, "load_pins", lambda: {"images": {
        "gateway": {"docker_image": "mockopin-v9-gateway", "binary_sha256": _FAKE_BIN_SHA256},
        "proxy": {"docker_image": "mockopin-v9-proxy"},
        "pqc-signer": {"docker_image": "mockopin-pqc-signer"},
        "measure": {"docker_image": "mockopin-v9-measure"},
    }})


def _run_factory(calls, df_avail_kb="999999999"):
    def fake_run(argv, timeout=None):
        calls.append(argv)
        if argv[0] == "docker" and len(argv) > 1 and argv[1] == "cp":
            # docker cp <container>:/gateway <dest> -- precisa escrever
            # um arquivo real (o codigo real faz read_bytes() depois).
            Path(argv[3]).write_bytes(b"binario fake do gateway, so para teste\n")
            return FakeProc()
        if argv[0] == "docker" and "version" in argv and "-m" in argv:
            return FakeProc(stdout="/verify/gateway: go1.27.3\n")
        if argv[0] == "docker" and "cat" in argv:
            return FakeProc(stdout='{"go_tag": "go1.27.3"}')
        if argv[0] == "docker":
            return FakeProc()  # docker create / docker rm -f
        if argv[0] == "sh" and "docker save" in argv[2]:
            # escreve um .tar fake no caminho pedido pelo comando real
            # (`docker save <img> > <tar_path>`), pro resto do pipeline
            # (sha256/scp) ter um arquivo de verdade pra ler.
            tar_path = argv[2].split(">")[-1].strip()
            Path(tar_path).write_bytes(b"tar fake, so para teste\n" * 1000)  # ~25KB, da pra exercitar a checagem de espaco
            return FakeProc()
        if argv[0] == "ssh" and "df --output=avail" in argv[-1]:
            return FakeProc(stdout=f"{df_avail_kb}\n")
        if argv[0] == "ssh" and "sha256sum -c" in argv[-1]:
            return FakeProc(stdout="OK\n")
        return FakeProc()
    return fake_run


def test_extract_gateway_binary_info_confere_sha256_e_devolve_metadata(monkeypatch, tmp_path):
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        if argv[0] == "docker" and len(argv) > 1 and argv[1] == "cp":
            dest = Path(argv[3])
            dest.write_bytes(b"binario fake do gateway, so para teste\n")
            return FakeProc()
        if argv[0] == "docker" and "version" in argv and "-m" in argv:
            return FakeProc(stdout="/verify/gateway: go1.27.3\n")
        if argv[0] == "docker" and "cat" in argv:
            return FakeProc(stdout='{"go_tag": "go1.27.3"}')
        return FakeProc()

    monkeypatch.setattr(cli, "_run", fake_run)
    import hashlib
    expected_sha = hashlib.sha256(b"binario fake do gateway, so para teste\n").hexdigest()
    monkeypatch.setattr(di, "load_pins", lambda: {"images": {"gateway": {"binary_sha256": expected_sha}}})

    info = di.extract_gateway_binary_info(tmp_path)
    assert info["sha256"] == expected_sha
    assert info["go_build_version"] == "go1.27.3"
    assert info["toolchain_build_metadata"] == {"go_tag": "go1.27.3"}


def test_extract_gateway_binary_info_aborta_se_sha256_diverge_do_pin(monkeypatch, tmp_path):
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        if argv[0] == "docker" and len(argv) > 1 and argv[1] == "cp":
            Path(argv[3]).write_bytes(b"binario ADULTERADO\n")
            return FakeProc()
        return FakeProc()

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr(di, "load_pins", lambda: {"images": {"gateway": {"binary_sha256": "0" * 64}}})
    with pytest.raises(RuntimeError, match="NAO bate com PINS.json"):
        di.extract_gateway_binary_info(tmp_path)


def test_deliver_images_nunca_fala_com_servidor_ou_cliente(monkeypatch):
    """So o controle aparece em QUALQUER argv -- nenhum IP de
    servidor/cliente (este script e o PRIMEIRO salto, operador ->
    controle, nunca mais longe)."""
    calls = []
    monkeypatch.setattr(cli, "_run", _run_factory(calls))
    di.deliver_images("203.0.113.5", "/fake/operator_key", images=("gateway", "proxy"))
    flat = " ".join(a for c in calls for a in c)
    assert "203.0.113.5" in flat
    assert "203.0.113.60" not in flat and "203.0.113.50" not in flat  # nenhum IP de host hipotetico


def test_deliver_images_checa_espaco_antes_de_enviar(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", _run_factory(calls, df_avail_kb="1"))  # 1KB -- claramente insuficiente
    with pytest.raises(RuntimeError, match="controle tem"):
        di.deliver_images("203.0.113.5", "/fake/operator_key", images=("gateway", "proxy"))
    flat = [" ".join(c) for c in calls]
    assert not any("scp" in c for c in flat), "nenhum scp pode acontecer se o espaco em disco for insuficiente"


def test_deliver_images_aborta_se_sha256sum_c_falha_no_controle(monkeypatch):
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        base = _run_factory([])(argv, timeout)
        if argv[0] == "ssh" and "sha256sum -c" in argv[-1]:
            return FakeProc(returncode=1, stderr="sha256sum: WARNING: 1 computed checksum did NOT match")
        return base

    monkeypatch.setattr(cli, "_run", fake_run)
    with pytest.raises(RuntimeError, match="sha256sum -c falhou no controle"):
        di.deliver_images("203.0.113.5", "/fake/operator_key", images=("proxy",))


def test_deliver_images_entrega_gateway_binary_info_e_binario_so_se_gateway_estiver_na_lista(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", _run_factory(calls))
    report = di.deliver_images("203.0.113.5", "/fake/operator_key", images=("gateway", "proxy"))
    assert report["gateway_binary_info_delivered"] is True
    flat = " ".join(a for c in calls for a in c)
    assert "gateway_binary_info.json" in flat

    calls2 = []
    monkeypatch.setattr(cli, "_run", _run_factory(calls2))
    report2 = di.deliver_images("203.0.113.5", "/fake/operator_key", images=("proxy", "measure"))
    assert "gateway_binary_info_delivered" not in report2
    flat2 = " ".join(a for c in calls2 for a in c)
    assert "gateway_binary_info.json" not in flat2
