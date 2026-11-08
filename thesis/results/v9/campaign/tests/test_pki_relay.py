"""Testes do rele de PKI -- SSH/SCP stubados via cli._run, nenhuma
chamada real, nenhuma chave de verdade (so arquivos vazios de teste)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cli  # noqa: E402
import pki_relay  # noqa: E402


class FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.fixture
def pki_files(tmp_path):
    files = []
    for name in ("server.crt", "server.key", "ca_root.crt"):
        p = tmp_path / name
        p.write_text(f"conteudo falso de {name}, nunca uma chave real", encoding="utf-8")
        files.append(p)
    return files


def test_rele_faz_2_saltos_scp_depois_shred(monkeypatch, pki_files):
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        return FakeProc(returncode=0)

    monkeypatch.setattr(cli, "_run", fake_run)
    pki_relay.relay_pki(
        control_ip="203.0.113.5", operator_key_path="/fake/operator_key",
        campaign_key_remote_path="/home/ec2-user/.ssh/campaign_key",
        targets=[{"name": "server", "ip": "203.0.113.9", "files": pki_files}],
    )

    ssh_calls = [c for c in calls if c[0] == "ssh"]
    scp_calls = [c for c in calls if c[0] == "scp"]
    assert len(scp_calls) == 3, "um scp (operador->controle) por arquivo"
    assert any("@203.0.113.5" in a for c in scp_calls for a in c), "scp deveria ir pro IP do CONTROLE"
    assert len(ssh_calls) == 2, "um ssh pro mkdir + um ssh pro comando combinado scp-pro-destino+shred"
    relay_cmd = ssh_calls[-1][-1]
    assert "scp -i /home/ec2-user/.ssh/campaign_key" in relay_cmd
    assert "@203.0.113.9:" in relay_cmd, "o scp de dentro do controle deveria ir pro IP do DESTINO (servidor), nao do controle"
    assert "shred -u" in relay_cmd
    assert relay_cmd.index("scp -i") < relay_cmd.index("shred -u"), "shred tem que vir DEPOIS do(s) scp, nunca antes"


def test_nenhum_conteudo_de_chave_aparece_nos_argv(monkeypatch, pki_files):
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        return FakeProc(returncode=0)

    monkeypatch.setattr(cli, "_run", fake_run)
    pki_relay.relay_pki(
        control_ip="203.0.113.5", operator_key_path="/fake/operator_key",
        campaign_key_remote_path="/home/ec2-user/.ssh/campaign_key",
        targets=[{"name": "server", "ip": "203.0.113.9", "files": pki_files}],
    )
    flat = " ".join(a for c in calls for a in c)
    assert "conteudo falso" not in flat, "o CONTEUDO do arquivo nunca deveria aparecer num argv -- so o caminho"


def test_scp_falho_para_controle_nunca_chega_a_tentar_o_rele(monkeypatch, pki_files):
    def fake_run(argv, timeout=None):
        if argv[0] == "scp":
            return FakeProc(returncode=1, stderr="Permission denied")
        return FakeProc(returncode=0)

    monkeypatch.setattr(cli, "_run", fake_run)
    with pytest.raises(RuntimeError, match="scp pro controle falhou"):
        pki_relay.relay_pki(
            control_ip="203.0.113.5", operator_key_path="/fake/operator_key",
            campaign_key_remote_path="/home/ec2-user/.ssh/campaign_key",
            targets=[{"name": "server", "ip": "203.0.113.9", "files": pki_files}],
        )


# --- Decisao 59: deliver_campaign_key -- pre-requisito de qualquer
# rele/orchestrator.py, achado real (a chave da campanha nunca era
# entregue pro controle por nenhum script antes desta rodada).

def test_deliver_campaign_key_um_so_salto_nunca_imprime_o_conteudo(monkeypatch):
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        return FakeProc(returncode=0)

    monkeypatch.setattr(cli, "_run", fake_run)
    report = pki_relay.deliver_campaign_key("203.0.113.5", "/fake/operator_key", "-----BEGIN FAKE KEY-----\nconteudo\n-----END FAKE KEY-----\n")
    assert report["campaign_key_remote_path"] == "/home/ec2-user/.ssh/campaign_key"
    flat = " ".join(a for c in calls for a in c)
    assert "FAKE KEY" not in flat and "conteudo" not in flat, "o CONTEUDO da chave nunca pode aparecer num argv"
    scp_calls = [c for c in calls if c[0] == "scp"]
    assert len(scp_calls) == 1, "um unico salto -- operador -> controle, nunca relayado mais pra frente"
    assert any("@203.0.113.5:" in a for a in scp_calls[0])


def test_deliver_campaign_key_grava_bytes_sem_cr(monkeypatch):
    """Achado real (execucao real desta rodada): `write_text` em modo
    texto, no Windows, traduz \\n pra \\r\\n -- uma chave SSH com CRLF
    e rejeitada pelo ssh/scp real do destino ("invalid format"). O
    arquivo local tem que sair sempre com \\n puro, byte a byte, mesmo
    recebendo um PEM com \\r\\n (ex.: de algum pipe que introduza isso
    antes de chegar aqui) -- capturado DENTRO do fake, antes do `with
    TemporaryDirectory` remover o arquivo."""
    captured = {}

    def fake_run(argv, timeout=None):
        if argv[0] == "scp":
            local_path = Path(argv[-2])
            captured["bytes"] = local_path.read_bytes()
        return FakeProc(returncode=0)

    monkeypatch.setattr(cli, "_run", fake_run)
    pem_com_crlf = "-----BEGIN FAKE KEY-----\r\nconteudo\r\n-----END FAKE KEY-----\r\n"
    pki_relay.deliver_campaign_key("203.0.113.5", "/fake/operator_key", pem_com_crlf)
    assert b"\r\n" not in captured["bytes"], "o arquivo local nunca pode conter CRLF -- ssh/scp real rejeita a chave"
    assert captured["bytes"].count(b"\n") == 3


def test_deliver_campaign_key_arquivo_local_e_removido_depois(monkeypatch):
    captured_paths = []

    def fake_run(argv, timeout=None):
        if argv[0] == "scp":
            captured_paths.append(argv[-2])  # caminho LOCAL (origem do scp)
        return FakeProc(returncode=0)

    monkeypatch.setattr(cli, "_run", fake_run)
    pki_relay.deliver_campaign_key("203.0.113.5", "/fake/operator_key", "conteudo falso de chave\n")
    assert len(captured_paths) == 1
    assert not Path(captured_paths[0]).exists(), "o arquivo temporario local tem que ser removido apos o scp"


def test_deliver_campaign_key_falha_no_scp_nunca_e_engolida(monkeypatch):
    def fake_run(argv, timeout=None):
        if argv[0] == "scp":
            return FakeProc(returncode=1, stderr="Permission denied")
        return FakeProc(returncode=0)

    monkeypatch.setattr(cli, "_run", fake_run)
    with pytest.raises(RuntimeError, match="scp da chave pro controle falhou"):
        pki_relay.deliver_campaign_key("203.0.113.5", "/fake/operator_key", "conteudo falso\n")


def test_mutante_shred_antes_do_scp_e_detectado(monkeypatch, pki_files):
    """Mutacao: shred() escrito ANTES do scp pro destino (ordem
    errada no `&&`) -- o teste de ordem acima deve reprovar."""
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        return FakeProc(returncode=0)

    monkeypatch.setattr(cli, "_run", fake_run)

    def mutated_relay_from_control(control_ip, operator_key_path, campaign_key_remote_path, target_ip, staged_paths):
        scp_cmds = [f"scp -i {campaign_key_remote_path} {p} ec2-user@{target_ip}:/home/ec2-user/pki/" for p in staged_paths]
        remote_cmd = "shred -u " + " ".join(staged_paths) + " && " + " && ".join(scp_cmds)  # ORDEM TROCADA, mutante
        return cli.run_ssh(control_ip, remote_cmd, key_path=operator_key_path)

    monkeypatch.setattr(pki_relay, "relay_from_control", mutated_relay_from_control)
    pki_relay.relay_pki(
        control_ip="203.0.113.5", operator_key_path="/fake/operator_key",
        campaign_key_remote_path="/home/ec2-user/.ssh/campaign_key",
        targets=[{"name": "server", "ip": "203.0.113.9", "files": pki_files}],
    )
    relay_cmd = [c for c in calls if c[0] == "ssh"][-1][-1]
    with pytest.raises(AssertionError):
        assert relay_cmd.index("scp -i") < relay_cmd.index("shred -u")
