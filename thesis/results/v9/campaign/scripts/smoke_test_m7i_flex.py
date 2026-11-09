#!/usr/bin/env python3
"""Smoke test REAL (pedido do Luciano, item 5 -- fechamento dos
criterios 1/3/4/6/7 pra campanha): 1 lancamento real de
`m7i-flex.large` (o tipo REAL da campanha, nunca t4g.micro) em CADA
uma das 7 regioes, com teardown completo e verificacao de zero sobra,
mesmo padrao do smoke test anterior (Decisao 108) -- API EC2 crua
(`run-instances`/`terminate-instances`), NUNCA terraform apply da
pilha inteira. ca-central-1 usa a AZ `ca-central-1b` (achado real do
smoke test anterior -- `ca-central-1a` deu InsufficientInstanceCapacity
pra t4g.micro; aqui testado de novo com o tipo real).

NUNCA imprime account ID/ARN/IP do operador."""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone

PROFILE = "mockopin-pqc"
PROJECT_TAG = "mockopin-pqc-v9-campanha-smoketest"
INSTANCE_TYPE = "m7i-flex.large"

# Mesmas AMIs pinadas que terraform_campanha_oficial/main.tf ja usa
# (al2023 x86_64, resolvidas ao vivo nesta conta em 2026-11-09 --
# reaproveitadas aqui, nunca uma segunda resolucao divergente).
AMI_BY_REGION = {
    "sa-east-1": "ami-0947d58e57fa20c5f",
    "us-east-1": "ami-0cf4b3ccd41c5a321",
    "ap-northeast-1": "ami-04ff541c93bef7350",
    "ca-central-1": "ami-0f39320fcf308a07f",
    "eu-north-1": "ami-072b92f3846437950",
    "ap-southeast-1": "ami-0e5c4d93500d698da",
    "ap-northeast-2": "ami-0bef747b3acf85e8f",
}
REGIONS = list(AMI_BY_REGION.keys())
# Decisao 108 -- ca-central-1a deu InsufficientInstanceCapacity real;
# ca-central-1b funcionou. Fixado aqui tambem, mesma AZ que o
# terraform_campanha_oficial/main.tf ja fixa agora (data.aws_subnets.
# ca_central_1_b).
# us-east-1: achado real desta propria rodada (smoke test com
# m7i-flex.large) -- a subnet default escolhida sem filtro de AZ caiu
# em us-east-1e, que NAO suporta m7i-flex.large nesta conta (erro real
# da AWS, "Unsupported ... Please retry ... us-east-1a/b/c/d/f").
# us-east-1a == AZ-id `use1-az1` NESTA conta (confirmado via
# describe-availability-zones) -- a MESMA AZ que
# terraform_campanha_oficial/main.tf ja fixa para o servidor real
# (`data.aws_subnets.us_east_1_az1`, filtro por availability-zone-id),
# entao nao e um bug do Terraform real, so deste script de smoke test
# que nao tinha overrode de AZ pra us-east-1.
AZ_OVERRIDE = {"ca-central-1": "ca-central-1b", "us-east-1": "us-east-1a"}

# Precos on-demand publicos de referencia (USD/h, Linux, us-east-1 como
# base -- a AWS nao varia m7i-flex.large tanto quanto instancias mais
# antigas entre regioes, mas o preco REAL de cada regiao e usado onde
# conhecido; onde nao, marcado explicitamente como estimativa da
# regiao mais proxima com preco publico conhecido).
PRICE_USD_PER_HOUR = {
    "sa-east-1": 0.1613, "us-east-1": 0.1008, "ap-northeast-1": 0.1310,
    "ca-central-1": 0.1109, "eu-north-1": 0.0959, "ap-southeast-1": 0.1211,
    "ap-northeast-2": 0.1211,
}


def run(args, timeout=120):
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"comando falhou ({' '.join(args[:4])}...): {r.stderr.strip()[:500]}")
    return r.stdout


def aws_json(region, *args):
    out = run(["aws", "--profile", PROFILE, "--region", region, "--output", "json"] + list(args))
    return json.loads(out) if out.strip() else {}


def default_subnet(region):
    vpcs = aws_json(region, "ec2", "describe-vpcs", "--filters", "Name=isDefault,Values=true")
    vpc_id = vpcs["Vpcs"][0]["VpcId"]
    filters = [f"Name=vpc-id,Values={vpc_id}"]
    if region in AZ_OVERRIDE:
        filters.append(f"Name=availability-zone,Values={AZ_OVERRIDE[region]}")
    subnets = aws_json(region, "ec2", "describe-subnets", "--filters", *filters)
    if not subnets["Subnets"]:
        raise RuntimeError(f"{region}: nenhuma subnet default encontrada (AZ={AZ_OVERRIDE.get(region, 'qualquer')})")
    return subnets["Subnets"][0]["SubnetId"], subnets["Subnets"][0]["AvailabilityZone"]


def launch_and_teardown(region):
    ami = AMI_BY_REGION[region]
    subnet_id, az = default_subnet(region)
    tag_spec = f"ResourceType=instance,Tags=[{{Key=Project,Value={PROJECT_TAG}}}]"
    launch_t0 = time.time()
    try:
        result = aws_json(region, "ec2", "run-instances",
                           "--image-id", ami, "--instance-type", INSTANCE_TYPE,
                           "--subnet-id", subnet_id, "--count", "1",
                           "--tag-specifications", tag_spec)
        instance_id = result["Instances"][0]["InstanceId"]
    except RuntimeError as e:
        return {"region": region, "az": az, "ok": False, "stage": "run-instances", "error": str(e)}

    try:
        run(["aws", "--profile", PROFILE, "--region", region, "ec2", "wait", "instance-running",
             "--instance-ids", instance_id], timeout=180)
        running_t = time.time()
        run(["aws", "--profile", PROFILE, "--region", region, "ec2", "terminate-instances",
             "--instance-ids", instance_id, "--output", "json"])
        run(["aws", "--profile", PROFILE, "--region", region, "ec2", "wait", "instance-terminated",
             "--instance-ids", instance_id], timeout=180)
        terminated_t = time.time()
    except RuntimeError as e:
        return {"region": region, "az": az, "ok": False, "stage": "lifecycle", "instance_id": instance_id, "error": str(e)}

    running_seconds = terminated_t - running_t
    billed_seconds = terminated_t - launch_t0  # conservador -- inclui o tempo de boot tambem
    price_h = PRICE_USD_PER_HOUR[region]
    cost_usd = (billed_seconds / 3600.0) * price_h

    # Verificacao de zero sobra -- mesmas 5 chamadas que cleanup.py ja usa.
    # Achado real desta rodada: `Reservations[].Instances[?...]` sem um
    # `[]` final devolve uma lista de UMA LISTA POR RESERVATION (ex.:
    # `[[]]` quando a unica reservation nao tem mais nenhuma instancia
    # ativa) -- `not remaining` e `False` pra essa forma (lista externa
    # nao-vazia), reportando falso-positivo de sobra mesmo com ZERO
    # instancias reais. Corrigido: flatten explicito antes de decidir.
    remaining_raw = aws_json(region, "ec2", "describe-instances", "--filters",
                              f"Name=tag:Project,Values={PROJECT_TAG}", "--query",
                              "Reservations[].Instances[?State.Name!=`terminated`]")
    remaining = [i for sub in remaining_raw for i in sub]
    addresses = aws_json(region, "ec2", "describe-addresses", "--filters", f"Name=tag:Project,Values={PROJECT_TAG}")
    volumes = aws_json(region, "ec2", "describe-volumes", "--filters", f"Name=tag:Project,Values={PROJECT_TAG}")
    clean = (not remaining) and not addresses.get("Addresses") and not volumes.get("Volumes")

    return {
        "region": region, "az": az, "ok": True, "instance_id": instance_id,
        "running_seconds": round(running_seconds, 1), "billed_seconds_conservative": round(billed_seconds, 1),
        "price_usd_per_hour": price_h, "cost_usd_conservative": round(cost_usd, 6),
        "zero_leftover": clean,
        "leftover_detail": {"instances": remaining, "addresses": addresses.get("Addresses", []),
                             "volumes": volumes.get("Volumes", [])} if not clean else None,
    }


def main():
    results = []
    for region in REGIONS:
        print(f"=== {region} ===", file=sys.stderr)
        r = launch_and_teardown(region)
        results.append(r)
        print(json.dumps(r, indent=2, default=str), file=sys.stderr)
    total_cost = sum(r.get("cost_usd_conservative", 0) for r in results if r["ok"])
    all_clean = all(r.get("zero_leftover") for r in results if r["ok"])
    all_ok = all(r["ok"] for r in results)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "instance_type": INSTANCE_TYPE, "n_regions": len(REGIONS),
        "results": results, "all_launches_ok": all_ok, "all_zero_leftover": all_clean,
        "total_cost_usd_conservative": round(total_cost, 6),
    }
    print(json.dumps(summary, indent=2, default=str))
    return 0 if (all_ok and all_clean) else 1


if __name__ == "__main__":
    sys.exit(main())
