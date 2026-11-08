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
import json
import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cli  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[5]

COMMON_FILES = [
    "thesis/scripts/opin_flow.py",
    "thesis/scripts/latency_automation.py",
    "thesis/scripts/baseline_automation.py",
    "thesis/scripts/campaign_client_runner.py",
    "thesis/scripts/switch_crypto_profile.py",
    "thesis/scripts/requirements.txt",
    "mock-service-os/certs",
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


def build_tarball(rel_paths: list[str], out_path: Path, repo_root: Path = _REPO_ROOT) -> Path:
    """Tarball LOCAL (tarfile puro, sem depender de um binario `tar`
    no PATH do operador) -- cada entrada guarda o caminho RELATIVO ao
    repositorio (`arcname=rel`), pra extrair em `~/` no destino
    reproduzir exatamente o mesmo layout relativo que `opin_flow.py`
    (BASE_DIR) ja presume."""
    with tarfile.open(out_path, "w:gz") as tar:
        for rel in rel_paths:
            src = repo_root / rel
            if not src.exists():
                raise RuntimeError(f"build_tarball: {src} nao existe -- nada pra empacotar")
            tar.add(src, arcname=rel)
    return out_path


def stage_on_control(control_ip, operator_key_path, tarball_path, staged_name):
    """Passo 1 -- operador copia o tarball pro controle (chave do
    operador), mesmo padrao de `pki_relay.stage_on_control`."""
    staged_path = f"{REMOTE_STAGING_DIR}/{staged_name}"
    cli.run_ssh(control_ip, f"mkdir -p {REMOTE_STAGING_DIR}", key_path=operator_key_path)
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
    lista de caminhos relativos entregues)."""
    report = []
    with tempfile.TemporaryDirectory(prefix="v9_deliver_source_") as tmp:
        server_tarball = build_tarball(COMMON_FILES + SERVER_ONLY_FILES, Path(tmp) / "server.tar.gz", repo_root=repo_root)
        client_tarball = build_tarball(COMMON_FILES + CLIENT_ONLY_FILES, Path(tmp) / "client.tar.gz", repo_root=repo_root)

        server_ip = inventory["server"]["public_ip"]
        staged = stage_on_control(control_ip, operator_key_path, server_tarball, "server.tar.gz")
        relay_and_extract(control_ip, operator_key_path, campaign_key_remote_path, server_ip, staged)
        report.append({"target": "server", "ip": server_ip, "files": list(COMMON_FILES) + list(SERVER_ONLY_FILES)})

        for route, client in inventory["clients"].items():
            client_ip = client["public_ip"]
            staged = stage_on_control(control_ip, operator_key_path, client_tarball, f"{route}.tar.gz")
            relay_and_extract(control_ip, operator_key_path, campaign_key_remote_path, client_ip, staged)
            install_client_requirements(control_ip, operator_key_path, campaign_key_remote_path, client_ip)
            report.append({"target": route, "ip": client_ip, "files": list(COMMON_FILES) + list(CLIENT_ONLY_FILES),
                            "requirements_installed": True})
    return report


def deliver_to_control(control_ip, operator_key_path, inventory_json_path, repo_root=_REPO_ROOT):
    """Decisao 59: UM SO salto (operador -> controle direto, igual a
    `deliver_images.py`) -- orchestrator.py NAO roda em servidor/
    cliente, entao nunca e relayado mais pra frente. `inventory.json`
    e copiado em separado (nao esta no repositorio -- e gerado por
    `terraform output -json inventory` a cada apply, pela maquina do
    OPERADOR, que tem o state do Terraform)."""
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

        inv_scp = cli.run_scp(str(inventory_json_path), f"ec2-user@{control_ip}:{REMOTE_INVENTORY_PATH}", key_path=operator_key_path)
        if inv_scp.returncode != 0:
            raise RuntimeError(f"deliver_to_control: scp do inventory.json falhou: {cli.redact(inv_scp.stderr)}")

    return {"target": "control", "ip": control_ip, "files": list(CONTROL_FILES) + ["inventory.json (gerado, nao versionado)"]}


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
