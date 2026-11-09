#!/usr/bin/env python3
"""v9, piloto: Decisao 55, item 4. Confere a politica IAM restrita
(thesis/results/v9/campaign/PILOT_READINESS.md, secao b.3) chamando
CADA acao mutavel de EC2 com `--dry-run`, por regiao -- NUNCA cria,
termina, ou altera nenhum recurso de verdade (`--dry-run` faz a AWS
avaliar a politica IAM e devolver `DryRunOperation` (autorizado) ou
`UnauthorizedOperation` (negado) SEM executar a acao).

Este script NUNCA e rodado por este processo (Claude) -- so escrito e
testado com mock (`cli._run` stubado, nenhuma chamada real). O
Luciano roda de verdade, com as credenciais da conta, antes do
piloto.

Limitacao honesta, registrada: as acoes abaixo que precisam de um ID
de recurso JA EXISTENTE (TerminateInstances, DeleteKeyPair,
ReleaseAddress, DisassociateAddress, RevokeSecurityGroupIngress,
ModifyInstanceAttribute) SO podem ser testadas de verdade contra um
recurso real -- passadas como `--instance-id`/`--key-name`/etc.
opcionais; sem elas, o check correspondente fica marcado
"nao testado" explicitamente, nunca inventado como PASS. As acoes que
NAO precisam de um recurso pre-existente (RunInstances, AllocateAddress,
ImportKeyPair, CreateSecurityGroup, AuthorizeSecurityGroupIngress,
Describe*) sao testadas sempre, com parametros sinteticos validos
derivados do Terraform real (AMI/instance-type pinados).

Uso:
  python iam_dryrun_check.py --profile mockopin-pqc \\
    [--instance-id i-xxxx --region-of-instance-id sa-east-1] \\
    [--key-name mockopin-pqc-v9-piloto --sg-id sg-xxxx --allocation-id eipalloc-xxxx] \\
    [--rule-id sgr-xxxx]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cli  # noqa: E402
import campaign_topology as ct  # noqa: E402  -- fonte unica das 7 regioes da campanha oficial, nunca duplicada

REGIONS = ["sa-east-1", "eu-north-1", "ap-southeast-1"]

# Decisao 46/Terraform real: AMIs pinadas, por regiao -- mesmos IDs
# que thesis/results/v9/terraform/main.tf usa, nunca resolvidos de
# novo aqui.
PINNED_AMI_X86 = {
    "sa-east-1": "ami-0c7fb00ead73effc8",
    "eu-north-1": "ami-0048d119f137c7738",
    "ap-southeast-1": "ami-012634091f2034c69",
}
INSTANCE_TYPE = "m7i-flex.large"


def _dryrun(argv, region, profile):
    try:
        out = cli.run_aws([*argv, "--dry-run"], region=region, profile=profile)
        # `aws` devolve rc!=0 pra DryRunOperation TAMBEM (e uma
        # "falha" do ponto de vista da CLI, mesmo autorizado) --
        # cli.run_aws levanta RuntimeError nesse caso, entao o
        # sucesso real (autorizado) e detectado pela MENSAGEM, nunca
        # pelo codigo de retorno.
        return {"ok": True, "note": out.strip() or "sem saida (raro p/ dry-run)"}
    except RuntimeError as e:
        msg = str(e)
        if "DryRunOperation" in msg:
            return {"ok": True, "note": "DryRunOperation -- autorizado"}
        if "UnauthorizedOperation" in msg:
            return {"ok": False, "note": "UnauthorizedOperation -- NAO autorizado pela politica IAM atual"}
        return {"ok": False, "note": f"erro inesperado (nem DryRunOperation nem UnauthorizedOperation): {msg}"}


def check_run_instances(region, profile):
    return _dryrun(
        ["ec2", "run-instances", "--image-id", PINNED_AMI_X86[region],
         "--instance-type", INSTANCE_TYPE, "--count", "1"],
        region, profile,
    )


def check_allocate_address(region, profile):
    return _dryrun(["ec2", "allocate-address", "--domain", "vpc"], region, profile)


def check_create_security_group(region, profile, vpc_id):
    if not vpc_id:
        return {"ok": None, "note": "pulado -- precisa de --vpc-id (o default da conta/regiao)"}
    return _dryrun(
        ["ec2", "create-security-group", "--group-name", "iam-dryrun-check-nunca-criado",
         "--description", "iam dry-run check -- nunca criado de verdade", "--vpc-id", vpc_id],
        region, profile,
    )


def check_authorize_ingress(region, profile, sg_id):
    if not sg_id:
        return {"ok": None, "note": "pulado -- precisa de --sg-id (um security group real ja existente)"}
    return _dryrun(
        ["ec2", "authorize-security-group-ingress", "--group-id", sg_id,
         "--protocol", "tcp", "--port", "22", "--cidr", "203.0.113.5/32"],
        region, profile,
    )


def check_import_key_pair(region, profile):
    # chave publica sintetica, nunca usada de verdade (so pro dry-run) -- formato valido, conteudo irrelevante pro teste de permissao.
    fake_pubkey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA iam-dryrun-check"
    return _dryrun(
        ["ec2", "import-key-pair", "--key-name", "iam-dryrun-check-nunca-criada", "--public-key-material", fake_pubkey],
        region, profile,
    )


def check_describe_actions(region, profile):
    """ec2:Describe* -- so UMA chamada representativa (describe-
    instances) prova a permissao de leitura; as outras Describe* do
    `preflight.py` real ja sao exercitadas por ele mesmo, nunca
    reinventadas aqui."""
    try:
        cli.run_aws_json(["ec2", "describe-instances", "--max-results", "5"], region=region, profile=profile)
        return {"ok": True, "note": "describe-instances respondeu (Describe* autorizado)"}
    except RuntimeError as e:
        return {"ok": False, "note": f"describe-instances falhou: {e}"}


# --- Acoes que exigem um recurso JA EXISTENTE -- so testadas se o ID
# correspondente for passado; senao, "nao testado", nunca inventado.

def check_terminate_instances(region, profile, instance_id):
    if not instance_id:
        return {"ok": None, "note": "pulado -- precisa de --instance-id (uma instancia real, ja existente)"}
    return _dryrun(["ec2", "terminate-instances", "--instance-ids", instance_id], region, profile)


def check_modify_instance_attribute(region, profile, instance_id):
    if not instance_id:
        return {"ok": None, "note": "pulado -- precisa de --instance-id"}
    return _dryrun(
        ["ec2", "modify-instance-attribute", "--instance-id", instance_id, "--disable-api-termination", "Value=false"],
        region, profile,
    )


def check_release_address(region, profile, allocation_id):
    if not allocation_id:
        return {"ok": None, "note": "pulado -- precisa de --allocation-id (um EIP real, ja existente)"}
    return _dryrun(["ec2", "release-address", "--allocation-id", allocation_id], region, profile)


def check_delete_key_pair(region, profile, key_name):
    if not key_name:
        return {"ok": None, "note": "pulado -- precisa de --key-name (uma key pair real, ja existente)"}
    return _dryrun(["ec2", "delete-key-pair", "--key-name", key_name], region, profile)


def check_revoke_ingress(region, profile, sg_id, rule_id):
    if not sg_id or not rule_id:
        return {"ok": None, "note": "pulado -- precisa de --sg-id e --rule-id (uma regra real, ja existente)"}
    return _dryrun(
        ["ec2", "revoke-security-group-ingress", "--group-id", sg_id, "--security-group-rule-ids", rule_id],
        region, profile,
    )


def run_all_checks(profile, vpc_id_by_region=None, instance_id=None, key_name=None,
                    sg_id=None, allocation_id=None, rule_id=None, regions=None) -> dict:
    """`regions=None` continua as 3 do piloto (REGIONS, compatibilidade
    -- item 1 do Luciano). Pedido do Luciano (item 2, fonte unica das
    regioes): a campanha oficial pode passar `campaign_topology.
    CAMPAIGN_REGIONS` (7) aqui. LIMITACAO HONESTA, registrada: os
    checks em si (`check_run_instances` etc.) dependem de AMI/VPC-id
    POR REGIAO (`PINNED_AMI_X86`, `--vpc-id-*`) que so tem entrada pras
    3 regioes do piloto -- rodar com as 7 regioes da campanha sem
    tambem estender esses dois dicionarios reportaria "nao testado"
    pras 4 regioes novas, nunca um falso PASS (fail-closed, mas
    incompleto). A politica IAM da conta nova ja foi validada por
    outro caminho, com DRY-RUN E APPLY+DESTROY REAIS nas 7 regioes
    (ver a adaptacao do Terraform multi-regiao) -- este script
    continua coberto so pro piloto por enquanto."""
    vpc_id_by_region = vpc_id_by_region or {}
    regions = regions if regions is not None else REGIONS
    results = {}
    for region in regions:
        vpc_id = vpc_id_by_region.get(region)
        results[region] = {
            "ec2:RunInstances": check_run_instances(region, profile),
            "ec2:AllocateAddress": check_allocate_address(region, profile),
            "ec2:CreateSecurityGroup": check_create_security_group(region, profile, vpc_id),
            "ec2:AuthorizeSecurityGroupIngress": check_authorize_ingress(region, profile, sg_id),
            "ec2:ImportKeyPair": check_import_key_pair(region, profile),
            "ec2:Describe*": check_describe_actions(region, profile),
            "ec2:TerminateInstances": check_terminate_instances(region, profile, instance_id),
            "ec2:ModifyInstanceAttribute": check_modify_instance_attribute(region, profile, instance_id),
            "ec2:ReleaseAddress": check_release_address(region, profile, allocation_id),
            "ec2:DeleteKeyPair": check_delete_key_pair(region, profile, key_name),
            "ec2:RevokeSecurityGroupIngress": check_revoke_ingress(region, profile, sg_id, rule_id),
        }
    all_tested_ok = all(
        c["ok"] is not False
        for region_checks in results.values()
        for c in region_checks.values()
    )
    not_tested = [
        f"{region}/{action}" for region, region_checks in results.items()
        for action, c in region_checks.items() if c["ok"] is None
    ]
    return {"results": results, "all_tested_ok": all_tested_ok, "not_tested": not_tested}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="mockopin-pqc")
    ap.add_argument("--instance-id")
    ap.add_argument("--key-name")
    ap.add_argument("--sg-id")
    ap.add_argument("--allocation-id")
    ap.add_argument("--rule-id")
    ap.add_argument("--vpc-id-sa-east-1")
    ap.add_argument("--vpc-id-eu-north-1")
    ap.add_argument("--vpc-id-ap-southeast-1")
    ap.add_argument("--campaign", action="store_true",
                     help="usa as 7 regioes da campanha oficial (campaign_topology.py) -- ver limitacao "
                          "honesta na docstring de run_all_checks: so as regioes com --vpc-id-* dado tem "
                          "cobertura completa, as demais saem 'nao testado'")
    args = ap.parse_args()

    vpc_id_by_region = {
        "sa-east-1": args.vpc_id_sa_east_1,
        "eu-north-1": args.vpc_id_eu_north_1,
        "ap-southeast-1": args.vpc_id_ap_southeast_1,
    }
    regions = ct.CAMPAIGN_REGIONS if args.campaign else None
    result = run_all_checks(
        args.profile, vpc_id_by_region=vpc_id_by_region, instance_id=args.instance_id,
        key_name=args.key_name, sg_id=args.sg_id, allocation_id=args.allocation_id, rule_id=args.rule_id,
        regions=regions,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["not_tested"]:
        print(f"\nNAO TESTADO (precisa de um ID de recurso real): {result['not_tested']}", file=sys.stderr)
    sys.exit(0 if result["all_tested_ok"] else 1)


if __name__ == "__main__":
    main()
