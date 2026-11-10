#!/usr/bin/env python3
"""Adapta o `terraform output -json inventory` real de
`terraform_campanha_oficial` (formato aninhado, rotulo de cliente
"{servidor}/{rota}") pro formato FLAT que `orchestrator.py SSHExecutor`
realmente espera (achado real ao preparar o ensaio de 64 execucoes --
`terraform_campanha_oficial/outputs.tf` foi escrito pelo BLOCO A em
isolamento, nunca cross-conferido byte a byte contra o formato real de
`campaign_topology.CAMPAIGN_ROUTES`/`SSHExecutor.__init__`): o cliente
"sa-east-1/L0" no Terraform precisa virar a chave "L0-sa-east-1" no
inventario (rotulo global unico, Decisao -- generalizacao N-servidores),
"sa-east-1/L123" precisa virar so "L123" (ja globalmente unico). Formula:
pra cada rota R de `campaign_topology.CAMPAIGN_ROUTES`, servidor S =
CAMPAIGN_ROUTE_SERVER[R]; chave do terraform = f"{S}/L0" se R comeca com
"L0-", senao f"{S}/{R}"."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import campaign_topology as ct  # noqa: E402


def adapt(tf_inventory: dict) -> dict:
    tf_clients = tf_inventory["clients"]
    clients = {}
    for route in ct.CAMPAIGN_ROUTES:
        server = ct.CAMPAIGN_ROUTE_SERVER[route]
        tf_key = f"{server}/L0" if route.startswith("L0-") else f"{server}/{route}"
        if tf_key not in tf_clients:
            raise RuntimeError(f"adapt: chave esperada '{tf_key}' (pra rota '{route}') "
                                f"nao encontrada no inventario real do terraform -- chaves disponiveis: "
                                f"{sorted(tf_clients.keys())}")
        c = tf_clients[tf_key]
        clients[route] = {"public_ip": c["public_ip"], "private_ip": c["private_ip"],
                           "colocated": c.get("colocated", route.startswith("L0-"))}
    servers = {region: {"public_ip": s["public_ip"], "private_ip": s["private_ip"]}
               for region, s in tf_inventory["servers"].items()}
    control = {"public_ip": tf_inventory["control"]["public_ip"],
               "private_ip": tf_inventory["control"]["private_ip"]}
    return {"control": control, "servers": servers, "clients": clients}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf-inventory-json", required=True, help="arquivo com a saida de 'terraform output -json inventory'")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    tf_inventory = json.loads(Path(args.tf_inventory_json).read_text(encoding="utf-8"))
    adapted = adapt(tf_inventory)
    Path(args.out).write_text(json.dumps(adapted, indent=2, ensure_ascii=False), encoding="utf-8")
    n_clients = len(adapted["clients"])
    n_servers = len(adapted["servers"])
    print(json.dumps({"ok": True, "n_servers": n_servers, "n_clients": n_clients, "out": args.out}, indent=2))


if __name__ == "__main__":
    main()
