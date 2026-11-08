"""Testes de deliver_source.py (Decisao 58, achado 19/correlatos) --
SSH/SCP/tar stubados via cli._run, nenhuma chamada real, nenhum dado
sensivel. Usa um repositorio FALSO (tmp_path) com os mesmos caminhos
relativos de COMMON_FILES/CLIENT_ONLY_FILES -- nunca o repo real, pra
nao depender do conteudo verdadeiro em disco."""
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cli  # noqa: E402
import deliver_source as ds  # noqa: E402


class FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


@pytest.fixture
def fake_repo(tmp_path):
    """Monta, sob tmp_path, a MESMA arvore relativa que COMMON_FILES/
    CLIENT_ONLY_FILES/CONTROL_FILES referenciam -- arquivos com
    conteudo falso, `mock-service-os/certs` e `thesis/results/v9/
    certs/generated` como diretorios com um arquivo falso dentro cada."""
    repo = tmp_path / "fake_repo"
    for rel in ds.COMMON_FILES + ds.CONTROL_FILES:
        if rel.endswith((".py", ".txt", ".json", ".sh")):
            p = repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"conteudo falso de {rel}\n", encoding="utf-8")
    (repo / "mock-service-os" / "certs").mkdir(parents=True, exist_ok=True)
    (repo / "mock-service-os" / "certs" / "ca.crt").write_text("cert falso\n", encoding="utf-8")
    (repo / "thesis" / "results" / "v9" / "certs" / "generated").mkdir(parents=True, exist_ok=True)
    (repo / "thesis" / "results" / "v9" / "certs" / "generated" / "classico_client.crt").write_text(
        "cert falso\n", encoding="utf-8")
    return repo


def test_build_tarball_usa_caminhos_relativos_ao_repo(fake_repo, tmp_path):
    out = ds.build_tarball(ds.COMMON_FILES, tmp_path / "out.tar.gz", repo_root=fake_repo)
    with tarfile.open(out, "r:gz") as tar:
        names = set(tar.getnames())
    for rel in ds.COMMON_FILES:
        assert any(n == rel or n.startswith(rel + "/") for n in names), f"{rel} nao esta no tarball ({names})"


def test_build_tarball_falha_se_arquivo_ausente(tmp_path):
    repo_vazio = tmp_path / "repo_vazio"
    repo_vazio.mkdir()
    with pytest.raises(RuntimeError, match="nao existe"):
        ds.build_tarball(ds.COMMON_FILES, tmp_path / "out.tar.gz", repo_root=repo_vazio)


def test_deliver_source_rele_de_2_saltos_pro_servidor_e_cada_cliente(monkeypatch, fake_repo):
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        return FakeProc(returncode=0)

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory = {
        "server": {"public_ip": "203.0.113.50"},
        "clients": {
            "L0": {"public_ip": "203.0.113.60"},
            "L219": {"public_ip": "203.0.113.70"},
        },
    }
    report = ds.deliver_source(
        control_ip="203.0.113.5", operator_key_path="/fake/operator_key",
        campaign_key_remote_path="/home/ec2-user/.ssh/campaign_key",
        inventory=inventory, repo_root=fake_repo,
    )
    assert {r["target"] for r in report} == {"server", "L0", "L219"}

    scp_to_control = [c for c in calls if c[0] == "scp" and any("@203.0.113.5:" in a for a in c)]
    assert len(scp_to_control) == 3, "um scp (operador->controle) por destino (servidor + 2 clientes)"

    # Os comandos de rele (ssh pro controle com o comando combinado
    # scp+ssh+rm, distinto do `mkdir -p` que `stage_on_control` tambem
    # dispara contra o mesmo controle) -- identificados pelo "tar -xzf"
    # literal, que so o comando de rele contem.
    relay_cmds = [c[-1] for c in calls if c and c[0] == "ssh" and any("203.0.113.5" in a for a in c) and "tar -xzf" in c[-1]]
    assert len(relay_cmds) == 3, "um rele (ssh pro controle) por destino"

    server_relay = next(c for c in relay_cmds if "@203.0.113.50:" in c)
    l0_relay = next(c for c in relay_cmds if "@203.0.113.60:" in c)
    l219_relay = next(c for c in relay_cmds if "@203.0.113.70:" in c)

    # Entrega usa a chave da CAMPANHA no segundo salto, nunca a do operador.
    for relay_cmd in (server_relay, l0_relay, l219_relay):
        assert "/home/ec2-user/.ssh/campaign_key" in relay_cmd
        assert "/fake/operator_key" not in relay_cmd

    # CLIENT_ONLY_FILES (certs/generated) so entra no tarball dos CLIENTES --
    # conferido indiretamente via o relatorio devolvido (nunca abre o
    # tarball de novo aqui, isso ja e testado em test_build_tarball_*).
    server_report = next(r for r in report if r["target"] == "server")
    l0_report = next(r for r in report if r["target"] == "L0")
    assert "thesis/results/v9/certs/generated" not in server_report["files"]
    assert "thesis/results/v9/certs/generated" in l0_report["files"]


def test_rele_extrai_antes_de_remover_o_tarball(monkeypatch, fake_repo):
    """Mesma politica de ordem que pki_relay.py ja testa pro shred --
    aqui, `tar -xzf` (extracao) tem que vir ANTES de qualquer `rm -f`
    (tanto no destino quanto no estagiamento do controle)."""
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        return FakeProc(returncode=0)

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory = {"server": {"public_ip": "203.0.113.50"}, "clients": {}}
    ds.deliver_source(
        control_ip="203.0.113.5", operator_key_path="/fake/operator_key",
        campaign_key_remote_path="/home/ec2-user/.ssh/campaign_key",
        inventory=inventory, repo_root=fake_repo,
    )
    relay_cmd = next(c[-1] for c in calls if c and c[0] == "ssh" and "tar -xzf" in c[-1])
    assert relay_cmd.index("tar -xzf") < relay_cmd.rindex("rm -f"), relay_cmd


def test_falha_no_scp_pro_controle_nunca_chega_a_tentar_o_rele(monkeypatch, fake_repo):
    def fake_run(argv, timeout=None):
        if argv[0] == "scp":
            return FakeProc(returncode=1, stderr="Permission denied")
        return FakeProc(returncode=0)

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory = {"server": {"public_ip": "203.0.113.50"}, "clients": {}}
    with pytest.raises(RuntimeError, match="scp do tarball pro controle falhou"):
        ds.deliver_source(
            control_ip="203.0.113.5", operator_key_path="/fake/operator_key",
            campaign_key_remote_path="/home/ec2-user/.ssh/campaign_key",
            inventory=inventory, repo_root=fake_repo,
        )


def test_falha_no_rele_e_reportada_nunca_engolida(monkeypatch, fake_repo):
    def fake_run(argv, timeout=None):
        if argv[0] == "ssh" and "tar -xzf" in argv[-1]:
            return FakeProc(returncode=1, stderr="No route to host")
        return FakeProc(returncode=0)

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory = {"server": {"public_ip": "203.0.113.50"}, "clients": {}}
    with pytest.raises(RuntimeError, match="rele\\+extracao falhou"):
        ds.deliver_source(
            control_ip="203.0.113.5", operator_key_path="/fake/operator_key",
            campaign_key_remote_path="/home/ec2-user/.ssh/campaign_key",
            inventory=inventory, repo_root=fake_repo,
        )


# --- Decisao 59: deliver_to_control -- UM SO salto (operador ->
# controle direto), orchestrator.py + deps + inventory.json, nunca
# relayado mais pra frente (nunca fala com servidor/cliente nenhum).

def test_deliver_to_control_um_so_salto_nunca_fala_com_servidor_ou_cliente(monkeypatch, fake_repo, tmp_path):
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        return FakeProc(returncode=0)

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text('{"server": {"public_ip": "203.0.113.50"}, "clients": {}}', encoding="utf-8")

    report = ds.deliver_to_control("203.0.113.5", "/fake/operator_key", str(inventory_path), repo_root=fake_repo)
    assert report["target"] == "control"
    flat = " ".join(a for c in calls for a in c)
    assert "203.0.113.5" in flat
    # nunca fala com nenhum IP de servidor/cliente -- so com o controle.
    assert "203.0.113.50" not in flat
    assert "/home/ec2-user/.ssh/campaign_key" not in flat, (
        "deliver_to_control e UM SO salto (operador -> controle) -- nunca usa a chave da campanha"
    )


def test_deliver_to_control_entrega_inventory_json_tambem(monkeypatch, fake_repo, tmp_path):
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        return FakeProc(returncode=0)

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text('{"server": {}, "clients": {}}', encoding="utf-8")

    ds.deliver_to_control("203.0.113.5", "/fake/operator_key", str(inventory_path), repo_root=fake_repo)
    scp_calls = [c for c in calls if c[0] == "scp"]
    assert any(str(inventory_path) in a for c in scp_calls for a in c), (
        "inventory.json tem que ser copiado pro controle -- " + str(scp_calls)
    )
    assert any("inventory.json" in a for c in scp_calls for a in c)


def test_deliver_to_control_extrai_antes_de_remover_o_tarball(monkeypatch, fake_repo, tmp_path):
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        return FakeProc(returncode=0)

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text('{"server": {}, "clients": {}}', encoding="utf-8")

    ds.deliver_to_control("203.0.113.5", "/fake/operator_key", str(inventory_path), repo_root=fake_repo)
    extract_cmd = next(c[-1] for c in calls if c and c[0] == "ssh" and "tar -xzf" in c[-1])
    assert extract_cmd.index("tar -xzf") < extract_cmd.rindex("rm -f"), extract_cmd


def test_deliver_to_control_falha_no_scp_do_inventory_nunca_e_engolida(monkeypatch, fake_repo, tmp_path):
    def fake_run(argv, timeout=None):
        if argv[0] == "scp" and "inventory.json" in argv[-1]:
            return FakeProc(returncode=1, stderr="Permission denied")
        return FakeProc(returncode=0)

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text('{"server": {}, "clients": {}}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="scp do inventory.json falhou"):
        ds.deliver_to_control("203.0.113.5", "/fake/operator_key", str(inventory_path), repo_root=fake_repo)
