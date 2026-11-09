#!/usr/bin/env python3
"""v9, piloto: rele da PKI operador -> controle -> instancias (servidor
+ 3 clientes), 2 saltos, exatamente a sequencia descrita em
thesis/results/v9/DECISIONS.md, Decisao 26 item 3 -- nunca exposta em
codigo antes desta rodada.

1. Operador `scp` o material de CADA destino pro controle (chave do
   OPERADOR), pra um diretorio de estadia temporaria.
2. Controle, usando a chave EXCLUSIVA da campanha (nunca a do
   operador), `scp` cada pedaco pro destino final certo.
3. Controle `shred -u` o material assim que a entrega de CADA destino
   e confirmada -- nunca fica retido mais tempo que o necessario pra
   relayar.

Nenhuma chave privada e impressa; so NOMES de arquivo aparecem em
qualquer saida deste script (mesma regra que a Decisao 26 ja
registrou pra v8).

**Decisao 59 (achado real, mesma classe do achado 19):**
`relay_from_control`/`deliver_source.relay_and_extract`/`orchestrator.
SSHExecutor` todos ASSUMEM `campaign_key_remote_path` (default
`/home/ec2-user/.ssh/campaign_key`) ja presente no controle pro
segundo salto -- nenhum script deste pacote jamais o entregava
(`terraform output -raw campaign_private_key`, nunca escrito em
arquivo pelo proprio Terraform -- so o operador le e entrega, mesmo
padrao real de `campaign_up.sh` da v8: `scp "$TMP_KEY" "ec2-user@
${CONTROL_IP}:~/.ssh/campaign_key"`). `deliver_campaign_key()` (novo)
fecha esse gap -- UM SO salto, nunca relayado mais pra frente, chmod
600 no destino, arquivo temporario local SEMPRE num `with
TemporaryDirectory` (removido automaticamente, mesmo em erro).
"""
import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cli  # noqa: E402

REMOTE_STAGING_DIR = "/tmp/mockopin-v9-pki-relay"
REMOTE_DEST_DIR = "/home/ec2-user/pki"


def deliver_campaign_key(control_ip, operator_key_path, campaign_private_key_pem,
                          campaign_key_remote_path="/home/ec2-user/.ssh/campaign_key"):
    """Pre-requisito de TUDO que faz um segundo salto (`relay_from_
    control` aqui, `deliver_source.relay_and_extract`, e o proprio
    `orchestrator.py` rodando do controle) -- sem isso, nenhum deles
    consegue de fato alcancar servidor/clientes a partir do controle.
    `campaign_private_key_pem`: o CONTEUDO (nunca um caminho) -- quem
    chama le via `terraform output -raw campaign_private_key`, nunca
    deste modulo. Nunca aparece em nenhuma mensagem de log/excecao
    deste modulo, so o CAMINHO de destino."""
    with tempfile.TemporaryDirectory(prefix="v9_campaign_key_") as tmp:
        local_key_path = Path(tmp) / "campaign_key"
        # Achado real (execucao real do piloto): `write_text` em modo
        # texto, no Windows, traduz todo "\n" pra "\r\n" (newline
        # default do SO) -- uma chave SSH com CRLF e rejeitada pelo
        # proprio ssh/scp do destino ("invalid format"). Normaliza
        # primeiro (caso o PEM recebido ja venha com \r\n de algum
        # pipe) e escreve em BINARIO, byte a byte, sem nenhuma
        # traducao de newline.
        normalized = campaign_private_key_pem.replace("\r\n", "\n")
        if not normalized.endswith("\n"):
            normalized += "\n"
        local_key_path.write_bytes(normalized.encode("utf-8"))
        local_key_path.chmod(0o600)

        mkdir_proc = cli.run_ssh(control_ip, "mkdir -p ~/.ssh && chmod 700 ~/.ssh", key_path=operator_key_path)
        if mkdir_proc.returncode != 0:
            raise RuntimeError(f"deliver_campaign_key: mkdir ~/.ssh no controle falhou: {cli.redact(mkdir_proc.stderr)}")

        scp_proc = cli.run_scp(str(local_key_path), f"ec2-user@{control_ip}:{campaign_key_remote_path}", key_path=operator_key_path)
        if scp_proc.returncode != 0:
            raise RuntimeError(f"deliver_campaign_key: scp da chave pro controle falhou: {cli.redact(scp_proc.stderr)}")

    chmod_proc = cli.run_ssh(control_ip, f"chmod 600 {campaign_key_remote_path}", key_path=operator_key_path)
    if chmod_proc.returncode != 0:
        raise RuntimeError(f"deliver_campaign_key: chmod no controle falhou: {cli.redact(chmod_proc.stderr)}")
    return {"target": "control", "ip": control_ip, "campaign_key_remote_path": campaign_key_remote_path}


def stage_on_control(control_ip, operator_key_path, target_name, local_files):
    """Passo 1 -- operador copia pro controle (chave do operador)."""
    staged_paths = []
    cli.run_ssh(control_ip, f"mkdir -p {REMOTE_STAGING_DIR}/{target_name}", key_path=operator_key_path)
    for local_path in local_files:
        remote_path = f"{REMOTE_STAGING_DIR}/{target_name}/{Path(local_path).name}"
        proc = cli.run_scp(str(local_path), f"ec2-user@{control_ip}:{remote_path}", key_path=operator_key_path)
        if proc.returncode != 0:
            raise RuntimeError(f"scp pro controle falhou ({Path(local_path).name}): {cli.redact(proc.stderr)}")
        staged_paths.append(remote_path)
    return staged_paths


def relay_from_control(control_ip, operator_key_path, campaign_key_remote_path, target_ip, staged_paths):
    """Passos 2 e 3 -- UM comando remoto no controle: scp (chave da
    campanha) pro destino final, shred -u so DEPOIS de todos os scp
    terem sucesso (`&&` entre cada um -- se qualquer scp falhar, o
    shred nunca roda, o material fica preservado pra diagnostico em
    vez de apagado silenciosamente numa entrega parcial)."""
    scp_cmds = [
        f"scp -i {campaign_key_remote_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
        f"{p} ec2-user@{target_ip}:{REMOTE_DEST_DIR}/"
        for p in staged_paths
    ]
    remote_cmd = (
        f"mkdir -p {REMOTE_DEST_DIR} && "
        + " && ".join(scp_cmds)
        + " && shred -u " + " ".join(staged_paths)
    )
    proc = cli.run_ssh(control_ip, remote_cmd, key_path=operator_key_path)
    if proc.returncode != 0:
        raise RuntimeError(f"rele controle->destino falhou: {cli.redact(proc.stderr)}")
    return proc


def relay_pki(control_ip, operator_key_path, campaign_key_remote_path, targets):
    """`targets`: lista de dicts {"name", "ip", "files": [Path,...]}.
    Retorna um relatorio por destino (nunca conteudo de chave, so
    contagem de arquivos e nomes)."""
    report = []
    for target in targets:
        staged = stage_on_control(control_ip, operator_key_path, target["name"], target["files"])
        relay_from_control(control_ip, operator_key_path, campaign_key_remote_path, target["ip"], staged)
        report.append({
            "target": target["name"], "ip": target["ip"],
            "files_relayed": [Path(f).name for f in target["files"]],
            "shredded_on_control": True,
        })
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--control-ip", required=True)
    ap.add_argument("--operator-key", required=True)
    ap.add_argument("--campaign-key-remote-path", default="/home/ec2-user/.ssh/campaign_key")
    ap.add_argument("--deliver-campaign-key", action="store_true",
                     help="Decisao 59: entrega SO a chave SSH da campanha pro controle (le "
                          "`terraform output -raw campaign_private_key` do stdin), pre-requisito "
                          "de qualquer rele/orchestrator.py -- nunca roda junto com --pki-dir")
    ap.add_argument("--pki-dir", help="diretorio local com <nome>.crt/<nome>.key por destino + CAs publicas")
    ap.add_argument("--inventory-json", required=True)
    args = ap.parse_args()

    import json

    if args.deliver_campaign_key:
        campaign_private_key_pem = sys.stdin.read()
        report = deliver_campaign_key(args.control_ip, args.operator_key, campaign_private_key_pem,
                                       campaign_key_remote_path=args.campaign_key_remote_path)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    if not args.pki_dir:
        ap.error("--pki-dir e obrigatorio fora do modo --deliver-campaign-key")
    inventory = json.load(open(args.inventory_json, encoding="utf-8"))
    pki_dir = Path(args.pki_dir)
    ca_files = sorted(pki_dir.glob("*ca*.crt"))

    # Generalizacao N-servidores (Decisao 107): mesmo raciocinio de
    # `deliver_source.deliver_source` -- `inventory["server"]`
    # (singular) e o piloto, reproduzido byte a byte (mesmo "name"
    # "server", mesmo par "server.crt"/"server.key"); `inventory
    # ["servers"]` (plural, dict por regiao-servidor) e a campanha
    # oficial, um alvo de PKI por servidor, arquivo nomeado pelo
    # proprio id do servidor (ex. "sa-east-1.crt").
    if "servers" in inventory:
        targets = [
            {"name": server_id, "ip": server["public_ip"],
             "files": [pki_dir / f"{server_id}.crt", pki_dir / f"{server_id}.key", *ca_files]}
            for server_id, server in inventory["servers"].items()
        ]
    else:
        targets = [{"name": "server", "ip": inventory["server"]["public_ip"],
                    "files": [pki_dir / "server.crt", pki_dir / "server.key", *ca_files]}]
    for route, client in inventory["clients"].items():
        targets.append({"name": route, "ip": client["public_ip"],
                         "files": [pki_dir / f"{route}.crt", pki_dir / f"{route}.key", *ca_files]})

    report = relay_pki(args.control_ip, args.operator_key, args.campaign_key_remote_path, targets)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
