#!/usr/bin/env python3
"""v9, piloto: Decisao 55, item 5. Parada de emergencia INDEPENDENTE
do state do Terraform -- por TAG `Project=mockopin-pqc-v9-piloto`,
nas 3 regioes, direto pela API da AWS. Existe pro caso em que o
`terraform destroy` do `cleanup.py` nao pode rodar (state perdido,
corrompido, ou inacessivel) mas os recursos ainda existem de verdade
na conta.

Cada acao destrutiva so roda sobre um ID que veio de uma chamada
`describe-*` FILTRADA por essa mesma tag -- nunca um ID passado
solto por fora (confere a tag ANTES de cada acao, nunca confia num
ID generico).

Ordem: instancias primeiro (termina), depois EIPs (desassocia +
libera), depois grupos de seguranca (so depois que as instancias
realmente terminaram -- AWS nao deixa apagar um SG ainda em uso) e
key pairs por ultimo (nunca dependem de nada anterior).

Este processo (Claude) NUNCA executa este script de verdade -- so
escreve e testa com mock. O Luciano roda, com as credenciais da
conta, se precisar.

Uso:
  python emergency_stop.py --profile mockopin-pqc [--execute] [--regions sa-east-1 eu-north-1 ap-southeast-1]

Sem `--execute`, so LISTA o que seria feito (modo dry, padrao -- nunca
destroi nada por acidente so por rodar o script sem pensar).
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cli  # noqa: E402

REGIONS = ["sa-east-1", "eu-north-1", "ap-southeast-1"]
PROJECT_TAG = "mockopin-pqc-v9-piloto"
TERMINATE_WAIT_SECONDS = 20
TERMINATE_WAIT_RETRIES = 6  # ate 2 minutos, ate os SGs ficarem livres pra deletar


def _tagged_instances(region, profile) -> list:
    data = cli.run_aws_json(
        ["ec2", "describe-instances", "--filters", f"Name=tag:Project,Values={PROJECT_TAG}"],
        region=region, profile=profile) or {"Reservations": []}
    return [i for r in data["Reservations"] for i in r["Instances"]
            if i["State"]["Name"] not in ("terminated", "shutting-down")]


def _tagged_addresses(region, profile) -> list:
    data = cli.run_aws_json(
        ["ec2", "describe-addresses", "--filters", f"Name=tag:Project,Values={PROJECT_TAG}"],
        region=region, profile=profile) or {"Addresses": []}
    return data["Addresses"]


def _tagged_security_groups(region, profile) -> list:
    data = cli.run_aws_json(
        ["ec2", "describe-security-groups", "--filters", f"Name=tag:Project,Values={PROJECT_TAG}"],
        region=region, profile=profile) or {"SecurityGroups": []}
    return data["SecurityGroups"]


def _tagged_key_pairs(region, profile) -> list:
    data = cli.run_aws_json(
        ["ec2", "describe-key-pairs", "--filters", f"Name=tag:Project,Values={PROJECT_TAG}"],
        region=region, profile=profile) or {"KeyPairs": []}
    return data["KeyPairs"]


def stop_region(region, profile, execute=False, wait_fn=time.sleep) -> dict:
    """Decisao 55, item 5: UMA regiao -- cada lista vem de uma
    `describe-*` filtrada pela tag, cada ID destruido veio DESSA
    lista, nunca de outro lugar. `execute=False` (default): so lista
    o que seria feito, nenhuma chamada mutavel roda."""
    report = {"region": region, "execute": execute}

    instances = _tagged_instances(region, profile)
    instance_ids = [i["InstanceId"] for i in instances]
    report["instances_found"] = instance_ids
    if execute and instance_ids:
        cli.run_aws(["ec2", "terminate-instances", "--instance-ids", *instance_ids], region=region, profile=profile)
        for _ in range(TERMINATE_WAIT_RETRIES):
            still_running = _tagged_instances(region, profile)
            if not still_running:
                break
            wait_fn(TERMINATE_WAIT_SECONDS)
        report["instances_terminated"] = instance_ids
    else:
        report["instances_terminated"] = []

    addresses = _tagged_addresses(region, profile)
    report["eips_found"] = [a.get("AllocationId") for a in addresses]
    released = []
    if execute:
        for addr in addresses:
            alloc_id = addr.get("AllocationId")
            assoc_id = addr.get("AssociationId")
            if assoc_id:
                cli.run_aws(["ec2", "disassociate-address", "--association-id", assoc_id], region=region, profile=profile)
            cli.run_aws(["ec2", "release-address", "--allocation-id", alloc_id], region=region, profile=profile)
            released.append(alloc_id)
    report["eips_released"] = released

    sgs = _tagged_security_groups(region, profile)
    sg_ids = [sg["GroupId"] for sg in sgs]
    report["security_groups_found"] = sg_ids
    deleted_sgs = []
    if execute:
        for sg_id in sg_ids:
            try:
                cli.run_aws(["ec2", "delete-security-group", "--group-id", sg_id], region=region, profile=profile)
                deleted_sgs.append(sg_id)
            except RuntimeError as e:  # noqa: BLE001 -- ainda em uso (instancia nao terminou a tempo) -- reportado, nunca escondido
                report.setdefault("security_groups_errors", []).append({"group_id": sg_id, "error": str(e)})
    report["security_groups_deleted"] = deleted_sgs

    keys = _tagged_key_pairs(region, profile)
    key_names = [k["KeyName"] for k in keys]
    report["key_pairs_found"] = key_names
    deleted_keys = []
    if execute:
        for key_name in key_names:
            cli.run_aws(["ec2", "delete-key-pair", "--key-name", key_name], region=region, profile=profile)
            deleted_keys.append(key_name)
    report["key_pairs_deleted"] = deleted_keys

    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="mockopin-pqc")
    ap.add_argument("--regions", nargs="+", default=REGIONS)
    ap.add_argument("--execute", action="store_true", help="sem isso, so lista o que seria feito (dry, default)")
    args = ap.parse_args()

    reports = [stop_region(r, args.profile, execute=args.execute) for r in args.regions]
    print(json.dumps(reports, indent=2, ensure_ascii=False))
    if not args.execute:
        print("\nMODO DRY (padrao) -- nada foi destruido. Rode com --execute pra agir de verdade.", file=sys.stderr)


if __name__ == "__main__":
    main()
