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
