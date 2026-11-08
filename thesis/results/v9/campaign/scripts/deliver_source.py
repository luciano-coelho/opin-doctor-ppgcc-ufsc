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
padrao real de `campaign_run.py`/`campaign_run.service` da v8) -- este
script entrega os arquivos, mas QUEM dispara `cli.run_ssh` contra
servidor/cliente ainda precisa estar executando de dentro do controle;
registrado aqui e em DECISIONS.md (achado adicional desta rodada),
nunca escondido, mas a mudanca de ONDE o orquestrador roda fica fora
do pedido desta rodada (que era so entrega de imagem/arquivo/certificado).

Entrega, pra CADA destino (servidor + cada cliente), `COMMON_FILES`:
  - thesis/scripts/{opin_flow,latency_automation,baseline_automation,
    campaign_client_runner,switch_crypto_profile}.py, requirements.txt
  - mock-service-os/certs (opin_flow.CERTS_DIR -- usado pelo mount
    `/real-certs` do gateway E pelos caminhos de certificado de
    aplicacao do lado do CLIENTE)
E so pra cada CLIENTE, alem disso, `CLIENT_ONLY_FILES`:
  - thesis/results/v9/certs/generated (opin_flow.V9_CERTS_DIR -- mount
    `-cert-dir /certs` do proxy, so no ramo V9_HARNESS)

Extrai em `~/` em cada destino, espelhando o layout relativo do
repositorio sob `~` -- EXATAMENTE a mesma convencao que `deliver_
source.sh` real da v8 ja usava, e que `opin_flow.py` (BASE_DIR =
SCRIPTS_DIR.parent.parent, calculado a partir do PROPRIO arquivo, sem
mudanca de codigo nenhuma) ja presume.
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

REMOTE_STAGING_DIR = "/tmp/mockopin-v9-source-relay"
REMOTE_TARBALL_PATH = "/tmp/mockopin-v9-source.tar.gz"


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


def deliver_source(control_ip, operator_key_path, campaign_key_remote_path, inventory, repo_root=_REPO_ROOT):
    """`inventory`: o mesmo dict que `terraform output -json inventory`
    produz. Entrega `COMMON_FILES` pro servidor + todo cliente;
    `CLIENT_ONLY_FILES` so pros clientes. Devolve um relatorio por
    destino (nunca conteudo de arquivo, so contagem/lista de caminhos
    relativos entregues)."""
    report = []
    with tempfile.TemporaryDirectory(prefix="v9_deliver_source_") as tmp:
        common_tarball = build_tarball(COMMON_FILES, Path(tmp) / "common.tar.gz", repo_root=repo_root)
        client_tarball = build_tarball(COMMON_FILES + CLIENT_ONLY_FILES, Path(tmp) / "client.tar.gz", repo_root=repo_root)

        server_ip = inventory["server"]["public_ip"]
        staged = stage_on_control(control_ip, operator_key_path, common_tarball, "server.tar.gz")
        relay_and_extract(control_ip, operator_key_path, campaign_key_remote_path, server_ip, staged)
        report.append({"target": "server", "ip": server_ip, "files": list(COMMON_FILES)})

        for route, client in inventory["clients"].items():
            client_ip = client["public_ip"]
            staged = stage_on_control(control_ip, operator_key_path, client_tarball, f"{route}.tar.gz")
            relay_and_extract(control_ip, operator_key_path, campaign_key_remote_path, client_ip, staged)
            report.append({"target": route, "ip": client_ip, "files": list(COMMON_FILES) + list(CLIENT_ONLY_FILES)})
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--control-ip", required=True)
    ap.add_argument("--operator-key", required=True)
    ap.add_argument("--campaign-key-remote-path", default="/home/ec2-user/.ssh/campaign_key")
    ap.add_argument("--inventory-json", required=True)
    args = ap.parse_args()

    inventory = json.load(open(args.inventory_json, encoding="utf-8"))
    report = deliver_source(args.control_ip, args.operator_key, args.campaign_key_remote_path, inventory)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
