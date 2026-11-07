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
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cli  # noqa: E402

REMOTE_STAGING_DIR = "/tmp/mockopin-v9-pki-relay"
REMOTE_DEST_DIR = "/home/ec2-user/pki"


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
    ap.add_argument("--pki-dir", required=True, help="diretorio local com <nome>.crt/<nome>.key por destino + CAs publicas")
    ap.add_argument("--inventory-json", required=True)
    args = ap.parse_args()

    import json
    inventory = json.load(open(args.inventory_json, encoding="utf-8"))
    pki_dir = Path(args.pki_dir)
    ca_files = sorted(pki_dir.glob("*ca*.crt"))

    targets = [{"name": "server", "ip": inventory["server"]["public_ip"],
                "files": [pki_dir / "server.crt", pki_dir / "server.key", *ca_files]}]
    for route, client in inventory["clients"].items():
        targets.append({"name": route, "ip": client["public_ip"],
                         "files": [pki_dir / f"{route}.crt", pki_dir / f"{route}.key", *ca_files]})

    report = relay_pki(args.control_ip, args.operator_key, args.campaign_key_remote_path, targets)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
