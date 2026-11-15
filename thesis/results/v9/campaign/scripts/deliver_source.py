#!/usr/bin/env python3
"""v9, piloto: entrega da arvore de codigo/certificados que o caminho
remoto do SSHExecutor ja presume presente em cada instancia -- achado
real desta rodada (Decisao 58, achado 19/correlatos): NENHUM script
deste pacote jamais entregava `thesis/scripts/*.py`, `mock-service-os/
certs` ou `thesis/results/v9/certs/generated` pra nenhuma instancia
(confirmado lendo `opin_flow.py`/`campaign_client_runner.py`/
`orchestrator.py._launch_gateway` direto, nunca suposto) -- a MESMA
classe de bug que a v8 real encontrou e corrigiu com `deliver_
source.sh` real ("NOTHING delivers any of insurance-server-lambdas/,
thesis/scripts/*.py, or mock-service-os/ to ANY server or client").

Mesmo rele de 2 saltos que `pki_relay.py` ja usa (operador -> controle
-> destino final, com a chave da CAMPANHA no segundo salto) -- pelo
MESMO motivo real: os Security Groups do servidor e de cada cliente so
aceitam SSH do EIP do PROPRIO controle (`thesis/results/v9/terraform/
main.tf`, `ssh_ingress_cidrs = {"control": "${module.control.public_
ip}/32"}`, nenhuma entrada pro operador) -- o OPERADOR NUNCA alcanca o
servidor/clientes direto numa AWS de verdade; so o controle alcanca.
Isso significa que `orchestrator.py` (SSHExecutor) so funciona de
verdade, contra uma AWS real, quando RODA a partir do controle (mesmo
padrao real de `campaign_run.py`/`campaign_run.service` da v8).
**Decisao 59 (correcao desta rodada):** essa mudanca de ONDE o
orquestrador roda NAO fica mais pendente -- `deliver_to_control()`
(novo, neste arquivo) entrega `orchestrator.py`/`cli.py`/`preflight.py`/
`PINS.json`/`evaluate_criteria.py` + o `inventory.json` gerado direto
pro controle, UM SO salto (operador -> controle, nunca relayado mais
pra frente -- orchestrator.py nao roda em servidor/cliente).

Entrega, pra CADA destino (servidor + cada cliente), `COMMON_FILES`:
  - thesis/scripts/{opin_flow,latency_automation,baseline_automation,
    campaign_client_runner,switch_crypto_profile}.py, requirements.txt
  - mock-service-os/certs (opin_flow.CERTS_DIR -- usado pelo mount
    `/real-certs` do gateway E pelos caminhos de certificado de
    aplicacao do lado do CLIENTE)
E so pra cada CLIENTE, alem disso, `CLIENT_ONLY_FILES`:
  - thesis/results/v9/certs/generated (opin_flow.V9_CERTS_DIR -- mount
    `-cert-dir /certs` do proxy, so no ramo V9_HARNESS)
E so pro SERVIDOR, alem disso, `SERVER_ONLY_FILES` (Decisao 83 --
backend de negocio da v8, portado pro piloto v9): o `docker-compose.
yml` real + os arquivos PEQUENOS de config que ele referencia
(`pg_hba.conf`/`mongod.conf`/`participants.json`/`software_statement.
json`/`setup_ssm.sh`/`ssa/*.json`) -- NUNCA o source de build (as
imagens ja chegam pinadas via `deliver_images.py`, Decisao 83, nunca
`docker build` na instancia)
E so pro CONTROLE (um salto so, `deliver_to_control`), `CONTROL_FILES`:
  - campaign/scripts/{orchestrator,cli,preflight}.py, campaign/PINS.json,
    integration/evaluate_criteria.py, certs/generated (Decisao 75, item
    2 -- precisa pro diagnostico de bytes do smoke gate) (+ inventory.json,
    copiado em separado -- nao e um arquivo do repositorio)

Extrai em `~/` em cada destino, espelhando o layout relativo do
repositorio sob `~` -- EXATAMENTE a mesma convencao que `deliver_
source.sh` real da v8 ja usava, e que `opin_flow.py` (BASE_DIR =
SCRIPTS_DIR.parent.parent, calculado a partir do PROPRIO arquivo, sem
mudanca de codigo nenhuma)/`orchestrator.py` (PINS_PATH = Path(
__file__).resolve().parents[1] / "PINS.json") ja presumem.
"""
import argparse
import hashlib
import json
import shlex
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cli  # noqa: E402
import cert_manifest  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[5]

COMMON_FILES = [
    "thesis/scripts/opin_flow.py",
    "thesis/scripts/latency_automation.py",
    "thesis/scripts/baseline_automation.py",
    "thesis/scripts/campaign_client_runner.py",
    "thesis/scripts/switch_crypto_profile.py",
    "thesis/scripts/requirements.txt",
    "mock-service-os/certs",
    # Decisao 85 (pedido do Luciano): produtor do criterio 7 (RTT por
    # rota) roda nos dois lados -- canal `probe` no CLIENTE, canal
    # `pcap` no SERVIDOR -- por isso vai em COMMON_FILES, nunca so
    # num dos dois.
    "thesis/results/v9/integration/producers/criterio7_rtt.py",
]
CLIENT_ONLY_FILES = [
    "thesis/results/v9/certs/generated",
]
# Decisao 83 (pedido do Luciano): backend de negocio da v8 (auth/
# mockapi/mongo_seed + psql/localstack/mongodb como dependencias do
# proprio compose), portado pro servidor real -- so o docker-compose.
# yml + os arquivos de config PEQUENOS que ele referencia (nunca o
# source de build: as imagens ja chegam pinadas via deliver_images.py/
# _deliver_backend_images, nunca `docker build` na instancia).
SERVER_ONLY_FILES = [
    # Decisao 85 (pedido do Luciano): produtor do criterio 2 (initcwnd
    # real) roda SO no servidor (e quem aceita a conexao de teste).
    "thesis/results/v9/integration/producers/criterio2_probe.py",
    "insurance-server-lambdas/docker-compose.yml",
    "insurance-server-lambdas/pg_hba.conf",
    "insurance-server-lambdas/mongod.conf",
    "insurance-server-lambdas/participants.json",
    "insurance-server-lambdas/software_statement.json",
    "mock-service-os/setup_ssm.sh",
    "mock-service-os/ssa/jwks.json",
    "mock-service-os/ssa/private_jwk.json",
]
CONTROL_FILES = [
    "thesis/results/v9/campaign/scripts/orchestrator.py",
    "thesis/results/v9/campaign/scripts/cli.py",
    "thesis/results/v9/campaign/scripts/preflight.py",
    "thesis/results/v9/campaign/scripts/rehearsal_handshake.sh",
    # Decisao 172 (pedido do Luciano, item 4b da Decisao 171): o
    # piloto/campanha passam a ser lancados PELO LAUNCHER (desacoplado
    # da sessao SSH do operador), nunca mais por orchestrator.py direto
    # numa sessao bloqueante -- os dois precisam estar no controle.
    "thesis/results/v9/campaign/scripts/launch_persistent.py",
    "thesis/results/v9/campaign/scripts/cleanup_campaign_key.py",
    # Decisao 85 (pedido do Luciano): roda DO CONTROLE, igual a
    # orchestrator.py (so o controle alcanca servidor/clientes).
    "thesis/results/v9/campaign/scripts/dedicated_criteria.py",
    "thesis/results/v9/campaign/scripts/deliver_images.py",
    # Achado real (rodada da Decisao 182): orchestrator.py importa
    # `cost_tracker` INCONDICIONALMENTE no topo do modulo (trava de
    # custo, Etapa 1 do piloto v9) e `campaign_topology` quando
    # --campaign/--cells e usado (Decisao 177) -- nenhum dos dois
    # jamais esteve nesta lista. Sem cost_tracker.py, `orchestrator.py
    # --help` no controle quebra com ModuleNotFoundError antes de
    # imprimir qualquer coisa (mesma classe de bug da Decisao 65,
    # achado em paridade, nunca corrigido junto por nao ter sido
    # exercitado ao vivo antes desta rodada). dedicated_criteria.py
    # tambem importa campaign_topology.
    "thesis/results/v9/campaign/scripts/cost_tracker.py",
    "thesis/results/v9/campaign/scripts/campaign_topology.py",
    "thesis/results/v9/campaign/PINS.json",
    "thesis/results/v9/integration/evaluate_criteria.py",
    # Decisao 75, item 2 (pedido do Luciano): run_smoke_gate roda no
    # CONTROLE (SSHExecutor so funciona de verdade a partir dali, ver
    # Decisao 59) e seu diagnostico de bytes (_bytes_diagnostic_for_
    # profile -> ec.expected_handshake_bytes) le certificados reais de
    # `certs_dir` -- sem isto, _DEFAULT_CERTS_DIR nunca existe no
    # controle (FileNotFoundError, antes so evitado por sorte, nunca
    # tratado).
    "thesis/results/v9/certs/generated",
    # Decisao 65 (achado real, ao vivo, no Passo 8 do ensaio real):
    # cli.py importa redact_aws_errors via sys.path relativo
    # (Path(__file__).resolve().parents[3] / "v8" / "campaign" /
    # "scripts") -- presume o repositorio INTEIRO presente, mas so
    # os arquivos acima eram entregues ao controle. Sem este arquivo,
    # `python3 orchestrator.py --help` quebra com ModuleNotFoundError
    # antes de imprimir qualquer coisa.
    "thesis/results/v8/campaign/scripts/redact_aws_errors.py",
]

REMOTE_STAGING_DIR = "/tmp/mockopin-v9-source-relay"
REMOTE_TARBALL_PATH = "/tmp/mockopin-v9-source.tar.gz"
REMOTE_CONTROL_TARBALL_PATH = "/tmp/mockopin-v9-control.tar.gz"
REMOTE_INVENTORY_PATH = "~/thesis/results/v9/campaign/scripts/inventory.json"


def _fix_permissions_filter(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo:
    """Decisao 89 (achado real, ao vivo): `tar.add()` sem filtro usa
    `os.stat()` do arquivo LOCAL pro modo Unix -- no Windows (onde o
    operador roda), isso NUNCA reflete o bit executavel que o git
    rastreia (`git ls-files -s` mostra `100755` pra `setup_ssm.sh`,
    mas o Windows nunca preserva isso no checkout). `localstack`
    executa `init-aws.sh` (== `setup_ssm.sh`, montado por esse nome)
    DIRETO via `subprocess.call` (nunca `sh script.sh`) -- sem o bit
    +x, `PermissionError: [Errno 13] Permission denied` real, achado
    ao vivo rodando o backend de verdade no servidor. Forca 0o755
    (rwxr-xr-x) pra qualquer `.sh`, 0o755 pra diretorios, 0o644
    (rw-r--r--) pro resto -- nunca confia no que o Windows reportou."""
    if tarinfo.isdir():
        tarinfo.mode = 0o755
    elif tarinfo.name.endswith(".sh"):
        tarinfo.mode = 0o755
    else:
        tarinfo.mode = 0o644
    return tarinfo


def build_tarball(rel_paths: list[str], out_path: Path, repo_root: Path = _REPO_ROOT) -> Path:
    """Tarball LOCAL (tarfile puro, sem depender de um binario `tar`
    no PATH do operador) -- cada entrada guarda o caminho RELATIVO ao
    repositorio (`arcname=rel`), pra extrair em `~/` no destino
    reproduzir exatamente o mesmo layout relativo que `opin_flow.py`
    (BASE_DIR) ja presume. Permissoes Unix sempre forcadas (Decisao
    89), nunca herdadas do `os.stat()` local -- ver `_fix_permissions_
    filter`."""
    with tarfile.open(out_path, "w:gz") as tar:
        for rel in rel_paths:
            src = repo_root / rel
            if not src.exists():
                raise RuntimeError(f"build_tarball: {src} nao existe -- nada pra empacotar")
            tar.add(src, arcname=rel, filter=_fix_permissions_filter)
    return out_path


def stage_on_control(control_ip, operator_key_path, tarball_path, staged_name):
    """Passo 1 -- operador copia o tarball pro controle (chave do
    operador), mesmo padrao de `pki_relay.stage_on_control`."""
    staged_path = f"{REMOTE_STAGING_DIR}/{staged_name}"
    # Achado real (piloto, Etapa 2): staged_name pode conter "/" (chaves
    # de rota tipo "regiao/rota" na campanha oficial com N servidores) --
    # mkdir -p so na raiz nunca criava o subdiretorio, scp falhava com
    # "No such file or directory". Cria o diretorio exato do destino.
    remote_dir = staged_path.rsplit("/", 1)[0]
    cli.run_ssh(control_ip, f"mkdir -p {remote_dir}", key_path=operator_key_path)
    proc = cli.run_scp(str(tarball_path), f"ec2-user@{control_ip}:{staged_path}", key_path=operator_key_path)
    if proc.returncode != 0:
        raise RuntimeError(f"stage_on_control: scp do tarball pro controle falhou: {cli.redact(proc.stderr)}")
    return staged_path


def relay_and_extract(control_ip, operator_key_path, campaign_key_remote_path, target_ip, staged_path):
    """Passos 2 e 3 -- do controle, usando a chave da CAMPANHA (nunca
    a do operador): scp o tarball pro destino final, extrai em `~/`,
    remove a copia temporaria dos dois lados SO depois de confirmar
    sucesso (`&&` entre cada etapa -- qualquer falha preserva o
    tarball pra diagnostico, nunca apaga uma entrega parcial em
    silencio, mesma politica de `pki_relay.relay_from_control`)."""
    remote_cmd = (
        f"scp -i {campaign_key_remote_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
        f"{staged_path} ec2-user@{target_ip}:{REMOTE_TARBALL_PATH} && "
        f"ssh -i {campaign_key_remote_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
        f"ec2-user@{target_ip} 'tar -xzf {REMOTE_TARBALL_PATH} -C ~/ && rm -f {REMOTE_TARBALL_PATH}' && "
        f"rm -f {staged_path}"
    )
    proc = cli.run_ssh(control_ip, remote_cmd, key_path=operator_key_path)
    if proc.returncode != 0:
        raise RuntimeError(f"relay_and_extract({target_ip}): rele+extracao falhou: {cli.redact(proc.stderr)}")
    return proc


def verify_delivered_certs(control_ip, operator_key_path, campaign_key_remote_path, target_ip, manifest):
    """Decisao 166, item 3 (pedido do Luciano): fail-closed -- depois
    que `relay_and_extract` entrega `mock-service-os/certs` (sempre em
    COMMON_FILES, pra servidor E todo cliente), confere via `sha256sum`
    REMOTO (segundo salto, chave da CAMPANHA -- mesmo rele de sempre)
    que cada certificado do manifesto (`cert_manifest.MANIFEST_FILENAMES`)
    chegou IDENTICO ao que o manifesto fixa. Levanta RuntimeError (nunca
    silencioso) se QUALQUER arquivo divergir -- aborta a entrega pra
    esse destino antes de start_block tentar usar material corrompido/
    adulterado. Devolve o dict {nome: sha256} obtido, pra o chamador
    cruzar entre hosts (ver `deliver_source`'s checagem de consistencia
    entre servidor e clientes, abaixo)."""
    names = " ".join(manifest["files"].keys())
    remote_cmd = (
        f"ssh -i {campaign_key_remote_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
        f"ec2-user@{target_ip} "
        f"'cd ~/mock-service-os/certs && sha256sum {names}'"
    )
    proc = cli.run_ssh(control_ip, remote_cmd, key_path=operator_key_path)
    if proc.returncode != 0:
        raise RuntimeError(f"verify_delivered_certs({target_ip}): sha256sum remoto falhou: {cli.redact(proc.stderr)}")

    got = {}
    for line in proc.stdout.strip().splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        digest, name = parts
        got[name.strip()] = digest

    mismatches = {
        name: {"expected": info["sha256"], "got": got.get(name)}
        for name, info in manifest["files"].items()
        if got.get(name) != info["sha256"]
    }
    if mismatches:
        raise RuntimeError(
            f"verify_delivered_certs({target_ip}): sha256 divergente do manifesto congelado "
            f"(thesis/results/v9/campaign/certs_manifest.json) -- {mismatches}"
        )
    return got


def _tracked_files_under(repo_root: Path, rel_path: str, ref: str = "HEAD") -> list[str]:
    """Decisao 168, item 3 (pedido do Luciano): expande `rel_path`
    (arquivo ou diretorio) pros caminhos RASTREADOS do git dentro dele,
    na `ref` dada. Um diretorio misto como `mock-service-os/certs`
    (certificado publico rastreado + chave privada gitignorada) devolve
    SO os rastreados -- `git ls-tree` nunca lista o que nao esta no
    blob, entao material privado/gerado fica fora por construcao,
    nunca por um filtro explicito que poderia errar."""
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "ls-tree", "-r", "--name-only", ref, "--", rel_path],
        capture_output=True, text=True, check=True,
    )
    return [line for line in proc.stdout.splitlines() if line]


def _blob_sha256(repo_root: Path, rel_path: str, ref: str = "HEAD") -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "-p", f"{ref}:{rel_path}"],
        capture_output=True, check=True,
    )
    return hashlib.sha256(proc.stdout).hexdigest()


def build_delivery_manifest(rel_paths: list[str], repo_root: Path = _REPO_ROOT, ref: str = "HEAD") -> dict[str, str]:
    """Decisao 168, item 3 (pedido do Luciano): manifesto sha256 de
    TODO arquivo RASTREADO entregue (scripts/config/certificado
    publico), calculado direto do BLOB do git na `ref` dada -- nunca
    do disco local do operador, que pode estar em qualquer estado de
    eol (ver Decisao 167/168 sobre CRLF). Material gerado/gitignorado
    (ex. `thesis/results/v9/certs/generated`, as chaves privadas
    dentro de `mock-service-os/certs`) fica FORA deste manifesto por
    construcao -- continua sem verificacao de integridade byte a byte,
    mesma situacao de antes desta Decisao (nunca material pra
    verificar contra um blob que nao existe)."""
    manifest: dict[str, str] = {}
    for rel in rel_paths:
        for f in _tracked_files_under(repo_root, rel, ref=ref):
            manifest[f] = _blob_sha256(repo_root, f, ref=ref)
    return manifest


def _git_text_attr(repo_root: Path, rel_path: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "check-attr", "text", "--", rel_path],
        capture_output=True, text=True, check=True,
    )
    return proc.stdout.strip().rsplit(":", 1)[-1].strip()


def assert_no_crlf_for_delivery(rel_paths: list[str], repo_root: Path = _REPO_ROOT) -> None:
    """Decisao 168, item 3 (pedido do Luciano): fail-closed LOCAL,
    ANTES de empacotar -- qualquer arquivo RASTREADO entregue, marcado
    como texto pelo `.gitattributes` (nao `-text`; certificado/chave
    publica ficam fora desta checagem por desenho, ver Decisao 167),
    que esteja em CRLF no disco do operador aborta a entrega inteira.
    Nunca um aviso silencioso: o `.gitattributes` global (Decisao 167)
    ja devia ter normalizado tudo -- CRLF aqui e sinal de checkout
    obsoleto/config local quebrada, nunca aceitavel numa entrega real."""
    violations = []
    for rel in rel_paths:
        for f in _tracked_files_under(repo_root, rel):
            if _git_text_attr(repo_root, f) == "unset":
                continue
            data = (repo_root / f).read_bytes()
            if b"\r\n" in data:
                violations.append(f)
    if violations:
        raise RuntimeError(
            f"assert_no_crlf_for_delivery: arquivo(s) de texto em CRLF, entrega recusada (fail-closed): {violations}"
        )


def verify_delivered_tree(control_ip, operator_key_path, campaign_key_remote_path, target_ip, manifest: dict) -> dict:
    """Decisao 168, item 3 (pedido do Luciano): generaliza
    `verify_delivered_certs` pra TODO arquivo rastreado entregue (nao
    so os certificados do manifesto congelado) -- UM `sha256sum`
    remoto (mesmo rele de 2 saltos) pra todos os caminhos do manifesto
    de uma vez, comparado contra o BLOB do git (`build_delivery_
    manifest`), fail-closed em qualquer divergencia ou arquivo
    ausente. `manifest` vazio (nenhum arquivo rastreado no conjunto
    entregue) e um no-op, nunca um erro."""
    if not manifest:
        return {}
    names = " ".join(shlex.quote(p) for p in manifest)
    remote_cmd = (
        f"ssh -i {campaign_key_remote_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
        f"ec2-user@{target_ip} "
        f"'cd ~ && sha256sum {names}'"
    )
    proc = cli.run_ssh(control_ip, remote_cmd, key_path=operator_key_path)
    if proc.returncode != 0:
        raise RuntimeError(f"verify_delivered_tree({target_ip}): sha256sum remoto falhou: {cli.redact(proc.stderr)}")

    got = {}
    for line in proc.stdout.strip().splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        digest, name = parts
        got[name.strip()] = digest

    mismatches = {
        name: {"expected": expected, "got": got.get(name)}
        for name, expected in manifest.items()
        if got.get(name) != expected
    }
    if mismatches:
        raise RuntimeError(f"verify_delivered_tree({target_ip}): sha256 divergente do blob git -- {mismatches}")
    return got


def _assert_certs_consistent_across_hosts(certs_by_target: dict) -> None:
    """Decisao 166, item 3: alem de cada host bater com o manifesto
    (ja fail-closed em `verify_delivered_certs`), confere que os
    hosts batem ENTRE SI -- redundante em teoria (os dois lados ja
    bateram com o mesmo manifesto), mas pega direto um manifesto
    desatualizado que, por coincidencia, nenhum host individual
    detectou (nunca deveria acontecer -- ver abaixo), sem depender
    so da comparacao indireta via manifesto."""
    if not certs_by_target:
        return
    targets = list(certs_by_target)
    reference_target, reference = targets[0], certs_by_target[targets[0]]
    for target in targets[1:]:
        if certs_by_target[target] != reference:
            raise RuntimeError(
                f"_assert_certs_consistent_across_hosts: {target} diverge de {reference_target} -- "
                f"{certs_by_target[target]} != {reference}"
            )


def install_client_requirements(control_ip, operator_key_path, campaign_key_remote_path, target_ip):
    """Decisao 69 (achado real, ao vivo, retomando a Fase A real):
    NENHUM passo deste pacote jamais instalava `thesis/scripts/
    requirements.txt` no cliente de verdade -- a v8 real original
    fazia isso como o ULTIMO passo do proprio `deliver_source.sh`
    (ver comentario em `install_common_packages.sh`); a reescrita em
    Python (`deliver_source.py`, Decisao 58) entregava o ARQUIVO
    `requirements.txt` mas nunca o instalava. Mascarado at agora
    porque a validacao LOCAL via shim usa o `.venv` do PROPRIO
    operador (`preflight.check_client_python_environment`), nunca pip
    no cliente remoto -- so apareceu ao vivo no primeiro
    `start_block` real (`ModuleNotFoundError: No module named
    'jwt'`, importado por `opin_flow.py`)."""
    remote_cmd = (
        f"ssh -i {campaign_key_remote_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
        f"ec2-user@{target_ip} "
        f"'pip3 install --user --require-hashes -r ~/thesis/scripts/requirements.txt'"
    )
    proc = cli.run_ssh(control_ip, remote_cmd, key_path=operator_key_path, connect_timeout=90)
    if proc.returncode != 0:
        raise RuntimeError(f"install_client_requirements({target_ip}): pip install falhou: {cli.redact(proc.stderr)}")
    return proc


def deliver_source(control_ip, operator_key_path, campaign_key_remote_path, inventory, repo_root=_REPO_ROOT):
    """`inventory`: o mesmo dict que `terraform output -json inventory`
    produz. Entrega `COMMON_FILES` pro servidor + todo cliente;
    `CLIENT_ONLY_FILES` so pros clientes, e so pros clientes tambem
    instala `requirements.txt` (Decisao 69 -- o servidor nunca executa
    nenhum codigo Python que precise dessas dependencias). Devolve um
    relatorio por destino (nunca conteudo de arquivo, so contagem/
    lista de caminhos relativos entregues).

    Generalizacao N-servidores (Decisao 107): o piloto expoe `inventory
    ["server"]` (UM so, singular); a campanha oficial expoe `inventory
    ["servers"]` (dict, uma entrada por regiao-servidor, achado real
    desta rodada -- `deliver_source` so entregava pro primeiro/unico
    servidor, igual ao achado ja documentado no proprio `outputs.tf`
    da campanha). `servers = {"server": inventory["server"]}` reproduz
    o piloto byte a byte (mesma chave "server", mesmo nome de tarball
    staged, "server.tar.gz", mesmo `target` no relatorio) quando so
    `inventory["server"]` existe; iterar sobre `inventory["servers"]`
    quando presente entrega pra CADA servidor da campanha, sem mudar
    nada do caminho do piloto."""
    manifest = cert_manifest.load_manifest(repo_root / "thesis/results/v9/campaign/certs_manifest.json")
    server_rel_paths = COMMON_FILES + SERVER_ONLY_FILES
    client_rel_paths = COMMON_FILES + CLIENT_ONLY_FILES
    # Decisao 168, item 3: fail-closed LOCAL antes de empacotar qualquer
    # coisa -- um CRLF obsoleto aborta a entrega inteira, nunca so o
    # destino que teria recebido o arquivo ruim.
    assert_no_crlf_for_delivery(server_rel_paths, repo_root)
    assert_no_crlf_for_delivery(client_rel_paths, repo_root)
    server_tree_manifest = build_delivery_manifest(server_rel_paths, repo_root)
    client_tree_manifest = build_delivery_manifest(client_rel_paths, repo_root)

    certs_by_target = {}
    report = []
    with tempfile.TemporaryDirectory(prefix="v9_deliver_source_") as tmp:
        server_tarball = build_tarball(server_rel_paths, Path(tmp) / "server.tar.gz", repo_root=repo_root)
        client_tarball = build_tarball(client_rel_paths, Path(tmp) / "client.tar.gz", repo_root=repo_root)

        servers = inventory["servers"] if "servers" in inventory else {"server": inventory["server"]}
        for server_id, server in servers.items():
            server_ip = server["public_ip"]
            staged = stage_on_control(control_ip, operator_key_path, server_tarball, f"{server_id}.tar.gz")
            relay_and_extract(control_ip, operator_key_path, campaign_key_remote_path, server_ip, staged)
            verify_delivered_tree(control_ip, operator_key_path, campaign_key_remote_path, server_ip, server_tree_manifest)
            certs_by_target[server_id] = verify_delivered_certs(
                control_ip, operator_key_path, campaign_key_remote_path, server_ip, manifest)
            report.append({"target": server_id, "ip": server_ip, "files": list(COMMON_FILES) + list(SERVER_ONLY_FILES),
                            "certs_verified": True, "tree_verified": True})

        for route, client in inventory["clients"].items():
            client_ip = client["public_ip"]
            staged = stage_on_control(control_ip, operator_key_path, client_tarball, f"{route}.tar.gz")
            relay_and_extract(control_ip, operator_key_path, campaign_key_remote_path, client_ip, staged)
            verify_delivered_tree(control_ip, operator_key_path, campaign_key_remote_path, client_ip, client_tree_manifest)
            certs_by_target[route] = verify_delivered_certs(
                control_ip, operator_key_path, campaign_key_remote_path, client_ip, manifest)
            install_client_requirements(control_ip, operator_key_path, campaign_key_remote_path, client_ip)
            report.append({"target": route, "ip": client_ip, "files": list(COMMON_FILES) + list(CLIENT_ONLY_FILES),
                            "requirements_installed": True, "certs_verified": True, "tree_verified": True})

        _assert_certs_consistent_across_hosts(certs_by_target)
    return report


def deliver_to_control(control_ip, operator_key_path, inventory_json_path, repo_root=_REPO_ROOT):
    """Decisao 59: UM SO salto (operador -> controle direto, igual a
    `deliver_images.py`) -- orchestrator.py NAO roda em servidor/
    cliente, entao nunca e relayado mais pra frente. `inventory.json`
    e copiado em separado (nao esta no repositorio -- e gerado por
    `terraform output -json inventory` a cada apply, pela maquina do
    OPERADOR, que tem o state do Terraform)."""
    assert_no_crlf_for_delivery(CONTROL_FILES, repo_root)
    control_tree_manifest = build_delivery_manifest(CONTROL_FILES, repo_root)

    with tempfile.TemporaryDirectory(prefix="v9_deliver_control_") as tmp:
        tarball = build_tarball(CONTROL_FILES, Path(tmp) / "control.tar.gz", repo_root=repo_root)

        mkdir_proc = cli.run_ssh(control_ip, "mkdir -p ~/thesis", key_path=operator_key_path)
        if mkdir_proc.returncode != 0:
            raise RuntimeError(f"deliver_to_control: mkdir no controle falhou: {cli.redact(mkdir_proc.stderr)}")

        scp_proc = cli.run_scp(str(tarball), f"ec2-user@{control_ip}:{REMOTE_CONTROL_TARBALL_PATH}", key_path=operator_key_path)
        if scp_proc.returncode != 0:
            raise RuntimeError(f"deliver_to_control: scp do tarball pro controle falhou: {cli.redact(scp_proc.stderr)}")

        extract_proc = cli.run_ssh(
            control_ip,
            f"tar -xzf {REMOTE_CONTROL_TARBALL_PATH} -C ~/ && rm -f {REMOTE_CONTROL_TARBALL_PATH}",
            key_path=operator_key_path,
        )
        if extract_proc.returncode != 0:
            raise RuntimeError(f"deliver_to_control: extracao no controle falhou: {cli.redact(extract_proc.stderr)}")

        # Decisao 168, item 3: deliver_to_control e UM SO salto (operador
        # -> controle, nunca a chave da campanha) -- verify_delivered_tree
        # embute um 2o salto (ssh DENTRO do comando remoto, chave da
        # campanha) que nao existe aqui; checagem direta, 1 salto so.
        if control_tree_manifest:
            names = " ".join(shlex.quote(p) for p in control_tree_manifest)
            check_proc = cli.run_ssh(control_ip, f"cd ~ && sha256sum {names}", key_path=operator_key_path)
            if check_proc.returncode != 0:
                raise RuntimeError(f"deliver_to_control: sha256sum remoto falhou: {cli.redact(check_proc.stderr)}")
            got = {}
            for line in check_proc.stdout.strip().splitlines():
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    digest, name = parts
                    got[name.strip()] = digest
            mismatches = {
                name: {"expected": expected, "got": got.get(name)}
                for name, expected in control_tree_manifest.items()
                if got.get(name) != expected
            }
            if mismatches:
                raise RuntimeError(f"deliver_to_control: sha256 divergente do blob git -- {mismatches}")

        inv_scp = cli.run_scp(str(inventory_json_path), f"ec2-user@{control_ip}:{REMOTE_INVENTORY_PATH}", key_path=operator_key_path)
        if inv_scp.returncode != 0:
            raise RuntimeError(f"deliver_to_control: scp do inventory.json falhou: {cli.redact(inv_scp.stderr)}")

    return {"target": "control", "ip": control_ip, "files": list(CONTROL_FILES) + ["inventory.json (gerado, nao versionado)"],
            "tree_verified": True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--control-ip", required=True)
    ap.add_argument("--operator-key", required=True)
    ap.add_argument("--campaign-key-remote-path", default="/home/ec2-user/.ssh/campaign_key")
    ap.add_argument("--to-control", action="store_true",
                     help="Decisao 59: entrega so pro controle (orchestrator.py + deps + inventory.json), "
                          "um salto, sem relay pro servidor/clientes")
    ap.add_argument("--inventory-json", required=True)
    args = ap.parse_args()

    if args.to_control:
        report = deliver_to_control(args.control_ip, args.operator_key, args.inventory_json)
    else:
        inventory = json.load(open(args.inventory_json, encoding="utf-8"))
        report = deliver_source(args.control_ip, args.operator_key, args.campaign_key_remote_path, inventory)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
