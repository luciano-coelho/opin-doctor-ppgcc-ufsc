"""Testes de deliver_source.py (Decisao 58, achado 19/correlatos) --
SSH/SCP/tar stubados via cli._run, nenhuma chamada real, nenhum dado
sensivel. Usa um repositorio FALSO (tmp_path) com os mesmos caminhos
relativos de COMMON_FILES/CLIENT_ONLY_FILES -- nunca o repo real, pra
nao depender do conteudo verdadeiro em disco.

Decisao 168, item 3 (pedido do Luciano): `fake_repo` agora e tambem um
repositorio git real (git init + commit), porque `build_delivery_
manifest`/`assert_no_crlf_for_delivery` leem o BLOB do git (git
ls-tree/cat-file/check-attr), nunca so o disco -- precisam de um
`.git` de verdade pra funcionar, mesmo num repo de teste minusculo."""
import hashlib
import shlex
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cert_manifest  # noqa: E402
import cli  # noqa: E402
import deliver_source as ds  # noqa: E402


class FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


# Decisao 166, item 3: manifesto FALSO (sha256 arbitrario, derivado so
# do NOME -- nunca precisa ser um certificado PEM de verdade, ja que
# verify_delivered_certs so compara texto de sha256sum contra o que o
# manifesto fixa) -- compartilhado entre fake_repo (grava o manifesto)
# e _fake_sha256sum_stdout (resposta do `sha256sum` remoto stubado),
# pra sempre baterem entre si por construcao.
_FAKE_CERT_HASHES = {name: hashlib.sha256(name.encode()).hexdigest() for name in cert_manifest.MANIFEST_FILENAMES}


def _fake_sha256sum_stdout() -> str:
    return "".join(f"{digest}  {name}\n" for name, digest in _FAKE_CERT_HASHES.items())


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _real_git_blob_sha256(repo_root, rel_path):
    proc = subprocess.run(["git", "-C", str(repo_root), "cat-file", "-p", f"HEAD:{rel_path}"],
                           capture_output=True, check=True)
    return hashlib.sha256(proc.stdout).hexdigest()


def make_fake_run_ok(repo_root):
    """Decisao 168, item 3 (pedido do Luciano): stub de cli._run que
    sempre responde OK, tanto ao `sha256sum` do manifesto de
    certificados congelado (verify_delivered_certs, nomes = basename,
    `cd ~/mock-service-os/certs`) quanto ao `sha256sum` da arvore
    inteira (verify_delivered_tree/deliver_to_control, nomes = caminho
    relativo, `cd ~ &&`) -- usado por todo teste que exercita
    deliver_source()/deliver_to_control() mas nao esta testando a
    verificacao em si (ela so teria que FALHAR num teste dedicado,
    nunca de surpresa num teste generico). A resposta da arvore e
    calculada direto do BLOB git real do `repo_root` -- nunca
    hardcoded -- pra sempre bater com build_delivery_manifest por
    construcao."""
    def fake_run(argv, timeout=None):
        if argv and argv[0] == "ssh" and "sha256sum" in argv[-1]:
            cmd = argv[-1]
            if "cd ~/mock-service-os/certs" in cmd:
                return FakeProc(returncode=0, stdout=_fake_sha256sum_stdout())
            names_part = cmd.split("sha256sum", 1)[1].strip()
            names_part = names_part.rstrip("'")
            names = shlex.split(names_part)
            lines = [f"{_real_git_blob_sha256(repo_root, name)}  {name}" for name in names]
            return FakeProc(returncode=0, stdout="\n".join(lines) + ("\n" if lines else ""))
        return FakeProc(returncode=0)
    return fake_run


@pytest.fixture
def fake_repo(tmp_path):
    """Monta, sob tmp_path, a MESMA arvore relativa que COMMON_FILES/
    CLIENT_ONLY_FILES/CONTROL_FILES referenciam -- arquivos com
    conteudo falso (sempre LF puro -- Decisao 168, item 3: `write_text`
    traduziria `\\n` pro separador do SO, CRLF no Windows, o que faria
    assert_no_crlf_for_delivery recusar toda entrega de teste),
    `mock-service-os/certs` e `thesis/results/v9/certs/generated` como
    diretorios com um arquivo falso dentro cada. Grava certs_manifest.
    json FALSO (Decisao 166) no mesmo caminho relativo que deliver_
    source() le de verdade -- sha256 casando com _FAKE_CERT_HASHES.
    Tambem um repositorio GIT REAL (git init + commit) -- Decisao 168,
    item 3: build_delivery_manifest/assert_no_crlf_for_delivery leem o
    BLOB do git (ls-tree/cat-file/check-attr), nunca so o disco."""
    repo = tmp_path / "fake_repo"
    for rel in ds.COMMON_FILES + ds.CONTROL_FILES + ds.SERVER_ONLY_FILES:
        if rel.endswith((".py", ".txt", ".json", ".sh", ".yml", ".conf")):
            p = repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(f"conteudo falso de {rel}\n".encode("utf-8"))
    (repo / "mock-service-os" / "certs").mkdir(parents=True, exist_ok=True)
    (repo / "mock-service-os" / "certs" / "ca.crt").write_bytes(b"cert falso\n")
    (repo / "thesis" / "results" / "v9" / "certs" / "generated").mkdir(parents=True, exist_ok=True)
    (repo / "thesis" / "results" / "v9" / "certs" / "generated" / "classico_client.crt").write_bytes(
        b"cert falso\n")

    manifest_path = repo / "thesis" / "results" / "v9" / "campaign" / "certs_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    fake_manifest = {
        "files": {name: {"sha256": digest, "pem_bytes": 1, "der_bytes": 1} for name, digest in _FAKE_CERT_HASHES.items()}
    }
    import json
    manifest_path.write_bytes(json.dumps(fake_manifest).encode("utf-8"))

    _git(repo, "init", "-q")
    _git(repo, "-c", "user.name=test", "-c", "user.email=test@test.invalid", "add", "-A")
    _git(repo, "-c", "user.name=test", "-c", "user.email=test@test.invalid", "commit", "-q", "-m", "fake")
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


# --- Decisao 89 (achado real, ao vivo): `tar.add()` sem filtro usava
# o modo Unix do `os.stat()` LOCAL -- no Windows (onde o operador
# roda), isso nunca preserva o bit executavel que o git rastreia pra
# `.sh`. `localstack` executa `setup_ssm.sh` (montado como `init-aws.
# sh`) DIRETO via `subprocess.call`, sem `sh` no meio -- sem o bit +x,
# `PermissionError: [Errno 13] Permission denied` real.

def test_build_tarball_forca_bit_executavel_em_arquivos_sh(fake_repo, tmp_path):
    out = ds.build_tarball(ds.SERVER_ONLY_FILES, tmp_path / "out.tar.gz", repo_root=fake_repo)
    with tarfile.open(out, "r:gz") as tar:
        setup_ssm = tar.getmember("mock-service-os/setup_ssm.sh")
    assert setup_ssm.mode & 0o111, f".sh tem que ter o bit executavel -- mode={oct(setup_ssm.mode)}"


def test_build_tarball_arquivo_nao_sh_fica_so_leitura(fake_repo, tmp_path):
    out = ds.build_tarball(ds.SERVER_ONLY_FILES, tmp_path / "out.tar.gz", repo_root=fake_repo)
    with tarfile.open(out, "r:gz") as tar:
        compose_yml = tar.getmember("insurance-server-lambdas/docker-compose.yml")
    assert compose_yml.mode == 0o644, f"arquivo nao-executavel deveria ser 0o644 -- mode={oct(compose_yml.mode)}"


def test_mutante_tarball_sem_filtro_de_permissao_e_pego(fake_repo, tmp_path):
    """Mutante: `tar.add()` SEM o filtro herda o modo local do
    arquivo -- zera o bit +x local deliberadamente (simula o que o
    Windows real sempre reporta pra um arquivo git-tracked 100755) e
    confirma que, SEM o filtro, o tar perderia o +x; o build_tarball
    REAL (com filtro) tem que forcar 0o755 independente disso."""
    import os
    import tarfile as tf
    src = fake_repo / "mock-service-os" / "setup_ssm.sh"
    os.chmod(src, 0o644)  # simula o que o Windows real sempre reporta

    mutant_out = tmp_path / "mutant.tar.gz"
    with tf.open(mutant_out, "w:gz") as tar:
        tar.add(src, arcname="mock-service-os/setup_ssm.sh")  # mutante: sem filter=
    with tf.open(mutant_out, "r:gz") as tar:
        mutant_member = tar.getmember("mock-service-os/setup_ssm.sh")
    assert not (mutant_member.mode & 0o111), "mutante deveria ter perdido o bit +x -- prova que dependia do filtro"

    out = ds.build_tarball(ds.SERVER_ONLY_FILES, tmp_path / "real.tar.gz", repo_root=fake_repo)
    with tf.open(out, "r:gz") as tar:
        real_member = tar.getmember("mock-service-os/setup_ssm.sh")
    assert real_member.mode & 0o111, "build_tarball real tem que forcar o +x, nunca depender do SO local"


def test_deliver_source_rele_de_2_saltos_pro_servidor_e_cada_cliente(monkeypatch, fake_repo):
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        return make_fake_run_ok(fake_repo)(argv, timeout)

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

    # Decisao 83: SERVER_ONLY_FILES (backend de negocio da v8, docker-
    # compose.yml + config) so entra no tarball do SERVIDOR, nunca dos
    # clientes.
    assert "insurance-server-lambdas/docker-compose.yml" in server_report["files"]
    assert "insurance-server-lambdas/docker-compose.yml" not in l0_report["files"]


# --- Generalizacao N-servidores (Decisao 107): inventory["servers"]
# (plural, dict por regiao-servidor) -- mesmo caminho de codigo que
# inventory["server"] (singular) ja testado acima, mas entregando
# SERVER_ONLY_FILES pra CADA servidor, um tarball staged por id.

def test_deliver_source_modo_campanha_entrega_para_cada_servidor(monkeypatch, fake_repo):
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        return make_fake_run_ok(fake_repo)(argv, timeout)

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory = {
        "servers": {
            "sa-east-1": {"public_ip": "203.0.113.10"},
            "us-east-1": {"public_ip": "203.0.113.20"},
            "ap-northeast-1": {"public_ip": "203.0.113.30"},
        },
        "clients": {
            "sa-east-1/L0": {"public_ip": "203.0.113.60"},
        },
    }
    report = ds.deliver_source(
        control_ip="203.0.113.5", operator_key_path="/fake/operator_key",
        campaign_key_remote_path="/home/ec2-user/.ssh/campaign_key",
        inventory=inventory, repo_root=fake_repo,
    )
    assert {r["target"] for r in report} == {"sa-east-1", "us-east-1", "ap-northeast-1", "sa-east-1/L0"}

    relay_cmds = [c[-1] for c in calls if c and c[0] == "ssh" and "tar -xzf" in c[-1]]
    assert len(relay_cmds) == 4, "um rele por servidor (3) + um por cliente (1)"
    for ip in ("203.0.113.10", "203.0.113.20", "203.0.113.30"):
        assert any(f"@{ip}:" in c for c in relay_cmds), f"servidor {ip} nunca recebeu o rele"

    server_report = next(r for r in report if r["target"] == "sa-east-1")
    assert "insurance-server-lambdas/docker-compose.yml" in server_report["files"]


def test_mutante_deliver_source_campanha_so_1_servidor_perderia_entrega(monkeypatch, fake_repo):
    """Mutante: ignorar inventory['servers'] e so entregar pro primeiro
    servidor (comportamento ANTES da generalizacao) deixaria 2 dos 3
    servidores da campanha sem SERVER_ONLY_FILES nenhum -- prova que a
    iteracao sobre todos os servidores e necessaria, nao cosmetica."""
    monkeypatch.setattr(cli, "_run", make_fake_run_ok(fake_repo))
    inventory = {
        "servers": {
            "sa-east-1": {"public_ip": "203.0.113.10"},
            "us-east-1": {"public_ip": "203.0.113.20"},
        },
        "clients": {},
    }
    report = ds.deliver_source(
        control_ip="203.0.113.5", operator_key_path="/fake/operator_key",
        campaign_key_remote_path="/home/ec2-user/.ssh/campaign_key",
        inventory=inventory, repo_root=fake_repo,
    )
    mutant_report = report[:1]  # simula so entregar pro primeiro servidor
    assert {r["target"] for r in mutant_report} != {"sa-east-1", "us-east-1"}, (
        "o mutante (so 1 servidor) tem que divergir do relatorio real (2 servidores)"
    )


def test_build_tarball_do_servidor_inclui_server_only_files(fake_repo, tmp_path):
    out = ds.build_tarball(ds.COMMON_FILES + ds.SERVER_ONLY_FILES, tmp_path / "out.tar.gz", repo_root=fake_repo)
    with tarfile.open(out, "r:gz") as tar:
        names = set(tar.getnames())
    for rel in ds.SERVER_ONLY_FILES:
        assert rel in names, f"{rel} nao esta no tarball ({names})"


# --- Decisao 69 (achado real, ao vivo): nenhum passo deste pacote
# jamais instalava requirements.txt no cliente de verdade --
# ModuleNotFoundError: No module named 'jwt' no primeiro start_block
# real. So o CLIENTE instala (o servidor nunca executa esse codigo).

def test_deliver_source_instala_requirements_so_nos_clientes(monkeypatch, fake_repo):
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        return make_fake_run_ok(fake_repo)(argv, timeout)

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory = {
        "server": {"public_ip": "203.0.113.50"},
        "clients": {"L0": {"public_ip": "203.0.113.60"}, "L219": {"public_ip": "203.0.113.70"}},
    }
    report = ds.deliver_source(
        control_ip="203.0.113.5", operator_key_path="/fake/operator_key",
        campaign_key_remote_path="/home/ec2-user/.ssh/campaign_key",
        inventory=inventory, repo_root=fake_repo,
    )
    pip_cmds = [c[-1] for c in calls if c and c[0] == "ssh" and any("203.0.113.5" in a for a in c) and "pip3 install" in c[-1]]
    assert len(pip_cmds) == 2, "um pip install por CLIENTE, nunca pro servidor -- " + str(pip_cmds)
    assert any("@203.0.113.60" in c and "requirements.txt" in c and "--require-hashes" in c for c in pip_cmds), pip_cmds
    assert any("@203.0.113.70" in c for c in pip_cmds), pip_cmds
    assert not any("@203.0.113.50" in c for c in pip_cmds), "servidor nunca precisa de requirements.txt"

    l0_report = next(r for r in report if r["target"] == "L0")
    assert l0_report["requirements_installed"] is True
    server_report = next(r for r in report if r["target"] == "server")
    assert "requirements_installed" not in server_report


def test_deliver_source_aborta_se_pip_install_falha_no_cliente(monkeypatch, fake_repo):
    def fake_run(argv, timeout=None):
        if argv and argv[0] == "ssh" and "pip3 install" in argv[-1]:
            return FakeProc(returncode=1, stderr="No matching distribution found for PyJWT==2.15.1")
        return make_fake_run_ok(fake_repo)(argv, timeout)

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory = {"server": {"public_ip": "203.0.113.50"}, "clients": {"L0": {"public_ip": "203.0.113.60"}}}
    with pytest.raises(RuntimeError, match="pip install falhou"):
        ds.deliver_source(
            control_ip="203.0.113.5", operator_key_path="/fake/operator_key",
            campaign_key_remote_path="/home/ec2-user/.ssh/campaign_key",
            inventory=inventory, repo_root=fake_repo,
        )


def test_rele_extrai_antes_de_remover_o_tarball(monkeypatch, fake_repo):
    """Mesma politica de ordem que pki_relay.py ja testa pro shred --
    aqui, `tar -xzf` (extracao) tem que vir ANTES de qualquer `rm -f`
    (tanto no destino quanto no estagiamento do controle)."""
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        return make_fake_run_ok(fake_repo)(argv, timeout)

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


# --- Decisao 166, item 3 (pedido do Luciano): fail-closed sha256 dos
# certificados do manifesto congelado, depois de cada entrega real.

def test_deliver_source_verifica_certs_contra_manifesto_apos_entrega(monkeypatch, fake_repo):
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        return make_fake_run_ok(fake_repo)(argv, timeout)

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory = {"server": {"public_ip": "203.0.113.50"}, "clients": {"L0": {"public_ip": "203.0.113.60"}}}
    report = ds.deliver_source(
        control_ip="203.0.113.5", operator_key_path="/fake/operator_key",
        campaign_key_remote_path="/home/ec2-user/.ssh/campaign_key",
        inventory=inventory, repo_root=fake_repo,
    )
    sha256sum_cmds = [c[-1] for c in calls if c and c[0] == "ssh" and "sha256sum" in c[-1]]
    cert_cmds = [c for c in sha256sum_cmds if "cd ~/mock-service-os/certs" in c]
    tree_cmds = [c for c in sha256sum_cmds if "cd ~ &&" in c]
    assert len(cert_cmds) == 2, "um sha256sum de certs por destino (servidor + 1 cliente) -- " + str(cert_cmds)
    assert len(tree_cmds) == 2, (
        "Decisao 168, item 3: um sha256sum de arvore por destino (servidor + 1 cliente) -- " + str(tree_cmds)
    )
    assert any("@203.0.113.50" in c for c in cert_cmds)
    assert any("@203.0.113.60" in c for c in cert_cmds)
    assert all(r["certs_verified"] for r in report)
    assert all(r["tree_verified"] for r in report)


def test_deliver_source_aborta_se_sha256_de_um_cert_diverge_do_manifesto(monkeypatch, fake_repo):
    def fake_run(argv, timeout=None):
        if argv and argv[0] == "ssh" and "sha256sum" in argv[-1] and "cd ~/mock-service-os/certs" in argv[-1]:
            # ca.crt volta com um sha256 ERRADO -- qualquer outro arquivo bate.
            bad = _fake_sha256sum_stdout().replace(_FAKE_CERT_HASHES["ca.crt"], "0" * 64)
            return FakeProc(returncode=0, stdout=bad)
        return make_fake_run_ok(fake_repo)(argv, timeout)

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory = {"server": {"public_ip": "203.0.113.50"}, "clients": {}}
    with pytest.raises(RuntimeError, match="sha256 divergente do manifesto"):
        ds.deliver_source(
            control_ip="203.0.113.5", operator_key_path="/fake/operator_key",
            campaign_key_remote_path="/home/ec2-user/.ssh/campaign_key",
            inventory=inventory, repo_root=fake_repo,
        )


def test_deliver_source_aborta_se_sha256sum_remoto_falha(monkeypatch, fake_repo):
    def fake_run(argv, timeout=None):
        if argv and argv[0] == "ssh" and "sha256sum" in argv[-1] and "cd ~/mock-service-os/certs" in argv[-1]:
            return FakeProc(returncode=1, stderr="No such file or directory")
        return make_fake_run_ok(fake_repo)(argv, timeout)

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory = {"server": {"public_ip": "203.0.113.50"}, "clients": {}}
    with pytest.raises(RuntimeError, match="sha256sum remoto falhou"):
        ds.deliver_source(
            control_ip="203.0.113.5", operator_key_path="/fake/operator_key",
            campaign_key_remote_path="/home/ec2-user/.ssh/campaign_key",
            inventory=inventory, repo_root=fake_repo,
        )


# --- Decisao 168, item 3 (pedido do Luciano): fail-closed sha256 de
# TODO arquivo rastreado entregue (nao so os certificados do manifesto
# congelado), contra o BLOB do git -- e fail-closed de CRLF, ANTES de
# empacotar.

def test_deliver_source_aborta_se_sha256_da_arvore_diverge_do_blob(monkeypatch, fake_repo):
    def fake_run(argv, timeout=None):
        if argv and argv[0] == "ssh" and "sha256sum" in argv[-1] and "cd ~ &&" in argv[-1]:
            return FakeProc(returncode=0, stdout="0" * 64 + "  thesis/scripts/opin_flow.py\n")
        return make_fake_run_ok(fake_repo)(argv, timeout)

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory = {"server": {"public_ip": "203.0.113.50"}, "clients": {}}
    with pytest.raises(RuntimeError, match="sha256 divergente do blob git"):
        ds.deliver_source(
            control_ip="203.0.113.5", operator_key_path="/fake/operator_key",
            campaign_key_remote_path="/home/ec2-user/.ssh/campaign_key",
            inventory=inventory, repo_root=fake_repo,
        )


def test_deliver_source_aborta_antes_de_empacotar_se_arquivo_rastreado_esta_em_crlf(monkeypatch, fake_repo):
    """CRLF introduzido no disco do operador (ex. checkout obsoleto)
    tem que abortar a entrega inteira, ANTES de qualquer scp/ssh --
    nunca so um aviso, nunca entregue."""
    (fake_repo / "thesis" / "scripts" / "opin_flow.py").write_bytes(b"conteudo com crlf\r\n")

    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        return make_fake_run_ok(fake_repo)(argv, timeout)

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory = {"server": {"public_ip": "203.0.113.50"}, "clients": {}}
    with pytest.raises(RuntimeError, match="CRLF"):
        ds.deliver_source(
            control_ip="203.0.113.5", operator_key_path="/fake/operator_key",
            campaign_key_remote_path="/home/ec2-user/.ssh/campaign_key",
            inventory=inventory, repo_root=fake_repo,
        )
    assert calls == [], "CRLF tem que abortar ANTES de qualquer chamada ssh/scp -- nada foi entregue de verdade"


def test_build_delivery_manifest_usa_o_blob_git_nao_o_disco(fake_repo):
    manifest = ds.build_delivery_manifest(["thesis/scripts/opin_flow.py"], repo_root=fake_repo)
    assert list(manifest) == ["thesis/scripts/opin_flow.py"]
    expected = _real_git_blob_sha256(fake_repo, "thesis/scripts/opin_flow.py")
    assert manifest["thesis/scripts/opin_flow.py"] == expected


def test_build_delivery_manifest_expande_diretorio_so_pros_arquivos_rastreados(fake_repo):
    manifest = ds.build_delivery_manifest(["mock-service-os/certs"], repo_root=fake_repo)
    assert list(manifest) == ["mock-service-os/certs/ca.crt"]


def test_assert_no_crlf_for_delivery_aceita_arvore_limpa(fake_repo):
    ds.assert_no_crlf_for_delivery(ds.COMMON_FILES, repo_root=fake_repo)  # nao levanta


def test_assert_no_crlf_for_delivery_recusa_crlf(fake_repo):
    (fake_repo / "thesis" / "scripts" / "opin_flow.py").write_bytes(b"conteudo com crlf\r\n")
    with pytest.raises(RuntimeError, match="CRLF"):
        ds.assert_no_crlf_for_delivery(ds.COMMON_FILES, repo_root=fake_repo)


def test_deliver_source_aborta_se_hosts_divergem_entre_si(monkeypatch, fake_repo):
    """Mesmo se cada host, isoladamente, bater com o manifesto (nao
    reproduzido aqui -- ver teste acima), _assert_certs_consistent_
    across_hosts tem que pegar uma divergencia ENTRE hosts -- testada
    direto (unidade), ja que simular 2 hosts com conjuntos diferentes
    mas os DOIS batendo com o mesmo manifesto e impossivel por
    construcao (o manifesto so tem 1 valor por arquivo)."""
    with pytest.raises(RuntimeError, match="diverge de"):
        ds._assert_certs_consistent_across_hosts({
            "server": {"ca.crt": "aaaa"},
            "L0": {"ca.crt": "bbbb"},
        })


def test_assert_certs_consistent_aceita_hosts_identicos():
    ds._assert_certs_consistent_across_hosts({
        "server": {"ca.crt": "aaaa"},
        "L0": {"ca.crt": "aaaa"},
    })  # nao levanta


def test_verify_delivered_certs_devolve_o_sha256_obtido(monkeypatch, fake_repo):
    monkeypatch.setattr(cli, "_run", make_fake_run_ok(fake_repo))
    manifest = cert_manifest.load_manifest(fake_repo / "thesis/results/v9/campaign/certs_manifest.json")
    got = ds.verify_delivered_certs(
        "203.0.113.5", "/fake/operator_key", "/home/ec2-user/.ssh/campaign_key", "203.0.113.50", manifest)
    assert got == _FAKE_CERT_HASHES


# --- Decisao 59: deliver_to_control -- UM SO salto (operador ->
# controle direto), orchestrator.py + deps + inventory.json, nunca
# relayado mais pra frente (nunca fala com servidor/cliente nenhum).

def test_deliver_to_control_um_so_salto_nunca_fala_com_servidor_ou_cliente(monkeypatch, fake_repo, tmp_path):
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        return make_fake_run_ok(fake_repo)(argv, timeout)

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
        return make_fake_run_ok(fake_repo)(argv, timeout)

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
        return make_fake_run_ok(fake_repo)(argv, timeout)

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text('{"server": {}, "clients": {}}', encoding="utf-8")

    ds.deliver_to_control("203.0.113.5", "/fake/operator_key", str(inventory_path), repo_root=fake_repo)
    extract_cmd = next(c[-1] for c in calls if c and c[0] == "ssh" and "tar -xzf" in c[-1])
    assert extract_cmd.index("tar -xzf") < extract_cmd.rindex("rm -f"), extract_cmd


# --- Decisao 75, item 2 (pedido do Luciano): o diagnostico de bytes
# do smoke gate roda no controle e precisa de certs/generated de
# verdade -- sem isso, _DEFAULT_CERTS_DIR nunca existe la.

def test_control_files_inclui_certs_generated():
    assert "thesis/results/v9/certs/generated" in ds.CONTROL_FILES


def test_deliver_to_control_tarball_inclui_certs_generated(fake_repo, tmp_path):
    out = ds.build_tarball(ds.CONTROL_FILES, tmp_path / "control.tar.gz", repo_root=fake_repo)
    with tarfile.open(out, "r:gz") as tar:
        names = set(tar.getnames())
    rel = "thesis/results/v9/certs/generated"
    assert any(n == rel or n.startswith(rel + "/") for n in names), f"{rel} nao esta no tarball ({names})"


def test_deliver_to_control_falha_no_scp_do_inventory_nunca_e_engolida(monkeypatch, fake_repo, tmp_path):
    def fake_run(argv, timeout=None):
        if argv[0] == "scp" and "inventory.json" in argv[-1]:
            return FakeProc(returncode=1, stderr="Permission denied")
        return make_fake_run_ok(fake_repo)(argv, timeout)

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text('{"server": {}, "clients": {}}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="scp do inventory.json falhou"):
        ds.deliver_to_control("203.0.113.5", "/fake/operator_key", str(inventory_path), repo_root=fake_repo)


def test_deliver_to_control_aborta_se_sha256_da_arvore_diverge_do_blob(monkeypatch, fake_repo, tmp_path):
    def fake_run(argv, timeout=None):
        if argv and argv[0] == "ssh" and "sha256sum" in argv[-1]:
            return FakeProc(returncode=0, stdout="0" * 64 + "  thesis/results/v9/campaign/scripts/orchestrator.py\n")
        return make_fake_run_ok(fake_repo)(argv, timeout)

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text('{"server": {}, "clients": {}}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="sha256 divergente do blob git"):
        ds.deliver_to_control("203.0.113.5", "/fake/operator_key", str(inventory_path), repo_root=fake_repo)


def test_deliver_to_control_aborta_antes_de_empacotar_se_arquivo_rastreado_esta_em_crlf(monkeypatch, fake_repo, tmp_path):
    (fake_repo / "thesis" / "results" / "v9" / "campaign" / "scripts" / "orchestrator.py").write_bytes(
        b"conteudo com crlf\r\n")
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        return make_fake_run_ok(fake_repo)(argv, timeout)

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text('{"server": {}, "clients": {}}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="CRLF"):
        ds.deliver_to_control("203.0.113.5", "/fake/operator_key", str(inventory_path), repo_root=fake_repo)
    assert calls == [], "CRLF tem que abortar ANTES de qualquer chamada ssh/scp -- nada foi entregue de verdade"
