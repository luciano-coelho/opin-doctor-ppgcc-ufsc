#!/usr/bin/env python3
"""v9, piloto: limpeza por tags nas 3 regioes + verificacao final com
5 chamadas (describe-instances/addresses/security-groups/key-pairs/
volumes), equivalente reduzido ao `campaign_down.sh` real da v8
(Decisao 26 item 2, Decisao 43 item 2/45) -- com dois acrescimos que
a v8 real nao tinha e que a Decisao 43/45 pediu explicitamente:

1. Deteccao de "drift por autodesligamento": ANTES do
   `terraform destroy`, conta quantas das 5 instancias esperadas
   (controle+servidor+3 clientes) ainda aparecem rodando via
   `describe-instances` -- se MENOS que 5, o autodesligamento por
   tempo ja terminou alguma por fora do Terraform. Isso NUNCA bloqueia
   o destroy (que segue precisando rodar do mesmo jeito -- Decisao
   45: um `aws_eip` e liberado pela sua PROPRIA destruicao, nao pela
   da instancia associada), so avisa alto e explicito em vez de um
   teardown silenciosamente "normal".
2. Liberacao de EIPs orfaos: a verificacao final, nas 3 regioes,
   identifica qualquer Elastic IP SEM instancia associada
   (`"InstanceId" not in addr`) -- com `--release-eips`, libera de
   verdade (`ec2:ReleaseAddress`); sem a flag, so reporta (mesma
   politica de "deteccao antes de automacao nova" da Decisao 43).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cli  # noqa: E402

REGIONS = ["sa-east-1", "eu-north-1", "ap-southeast-1"]
PROJECT_TAG = "mockopin-pqc-v9-piloto"
EXPECTED_RUNNING_INSTANCES = 5  # controle + servidor + L0 + L219 + L325


def _describe_instances(region, profile):
    data = cli.run_aws_json(
        ["ec2", "describe-instances", "--filters", f"Name=tag:Project,Values={PROJECT_TAG}"],
        profile=profile, region=region) or {"Reservations": []}
    return [i for r in data["Reservations"] for i in r["Instances"]
            if i["State"]["Name"] not in ("terminated", "shutting-down")]


def count_running_instances_all_regions(profile) -> dict:
    """Snapshot ANTES do destroy -- base da deteccao de drift (item 1)."""
    return {region: len(_describe_instances(region, profile)) for region in REGIONS}


def check_self_terminate_drift(profile) -> dict:
    counts = count_running_instances_all_regions(profile)
    total = sum(counts.values())
    drifted = total < EXPECTED_RUNNING_INSTANCES
    return {
        "counts_by_region": counts, "total_running": total,
        "expected": EXPECTED_RUNNING_INSTANCES, "drift_detected": drifted,
        "note": (
            f"{EXPECTED_RUNNING_INSTANCES - total} instancia(s) esperada(s) ja nao aparecem rodando -- "
            "provavel autodesligamento por tempo ja disparado em pelo menos uma. O terraform destroy "
            "a seguir e OBRIGATORIO do mesmo jeito (Decisao 45: so ele libera o(s) aws_eip)."
        ) if drifted else "nenhum drift -- todas as instancias esperadas ainda aparecem rodando.",
    }


def terraform_destroy(tf_dir):
    rc, out, err = cli.run_terraform(["destroy", "-input=false", "-auto-approve"], cwd=tf_dir, timeout=600)
    return rc, out, err


def verify_region(region, profile) -> dict:
    """As 5 chamadas reais, mesma filtragem por tag/nome que a v8
    real usa no `campaign_down.sh` -- `describe-instances`,
    `describe-addresses`, `describe-security-groups`,
    `describe-key-pairs`, `describe-volumes`."""
    running = _describe_instances(region, profile)
    addresses = (cli.run_aws_json(
        ["ec2", "describe-addresses", "--filters", f"Name=tag:Project,Values={PROJECT_TAG}"],
        profile=profile, region=region) or {"Addresses": []})["Addresses"]
    sgs = (cli.run_aws_json(
        ["ec2", "describe-security-groups", "--filters", f"Name=group-name,Values={PROJECT_TAG}-*"],
        profile=profile, region=region) or {"SecurityGroups": []})["SecurityGroups"]
    key_pairs = (cli.run_aws_json(
        ["ec2", "describe-key-pairs", "--filters", f"Name=key-name,Values={PROJECT_TAG}*"],
        profile=profile, region=region) or {"KeyPairs": []})["KeyPairs"]
    volumes_data = (cli.run_aws_json(
        ["ec2", "describe-volumes", "--filters", f"Name=tag:Project,Values={PROJECT_TAG}"],
        profile=profile, region=region) or {"Volumes": []})["Volumes"]
    active_volumes = [v for v in volumes_data if v["State"] != "deleted"]
    orphaned_eips = [a for a in addresses if "InstanceId" not in a]

    return {
        "region": region,
        "instances": len(running), "security_groups": len(sgs),
        "key_pairs": len(key_pairs), "volumes": len(active_volumes), "eips": len(addresses),
        "orphaned_eips": orphaned_eips,
        "clean": not running and not sgs and not key_pairs and not active_volumes and not addresses,
    }


def release_orphaned_eips(region, profile, orphaned_eips, actually_release=False):
    """Sem `actually_release`, so lista os AllocationIds que SERIAM
    liberados -- nunca chama `release-address` por padrao (Decisao
    43: deteccao antes de automacao nova)."""
    allocation_ids = [a["AllocationId"] for a in orphaned_eips]
    if actually_release:
        for allocation_id in allocation_ids:
            cli.run_aws(["ec2", "release-address", "--allocation-id", allocation_id], profile=profile, region=region)
    return allocation_ids


def full_cleanup(tf_dir, profile, release_eips=False, pull_verified_marker=None, force=False, reason=None) -> dict:
    """Pedido do Luciano (item 0, regra fail-closed nova): o teardown
    (`terraform destroy`, logo abaixo) so pode rodar depois que os
    brutos estejam coletados e VERIFICADOS por sha256 -- 12 pcaps, 12
    keylogs, flights extraidos, logs de todas as instancias e dos
    conteineres, artefatos das 60 execucoes (tudo isso cabe dentro do
    MESMO `pull_verified_marker`, que `collect_artifacts.py` so
    escreve DEPOIS de hashear por completo o diretorio -- ver Decisao
    [N], `orchestrator.py dedicated_capture`/`dedicated_criteria.py
    collect_full_logs`/`run_criterio2`, que agora alimentam esse MESMO
    diretorio).

    Achado real desta rodada: o `PILOT_RUNBOOK.md` ate aqui mandava
    `--force` como o comando PRINCIPAL de teardown (nunca `--pull-
    verified-marker`) -- o gate acima existia em codigo mas NUNCA era
    de fato exercitado em nenhuma tentativa real. `force=True` agora
    exige `reason` (string nao-vazia) -- reservado EXPLICITAMENTE pra
    excecao de custo/seguranca (regra 7 do piloto), nunca um jeito de
    pular a verificacao por conveniencia. A `reason` entra no
    resultado -- auditavel, nunca um bypass silencioso."""
    if force:
        if not reason or not str(reason).strip():
            raise RuntimeError(
                "force=True exige 'reason' nao-vazia -- reservado pra excecao de custo/seguranca (regra 7), "
                "nunca um bypass sem motivo declarado."
            )
    else:
        if pull_verified_marker is None or not Path(pull_verified_marker).is_file():
            raise RuntimeError(
                f"{pull_verified_marker} nao encontrado -- rode collect_artifacts.py primeiro, "
                "ou passe force=True com uma 'reason' explicita (excecao de custo/seguranca) se tiver "
                "certeza que os dados nao sao necessarios."
            )

    drift = check_self_terminate_drift(profile)
    destroy_rc, destroy_out, destroy_err = terraform_destroy(tf_dir)
    if destroy_rc != 0:
        raise RuntimeError(f"terraform destroy falhou: {destroy_err}")

    regions_report = {}
    for region in REGIONS:
        report = verify_region(region, profile)
        if report["orphaned_eips"]:
            report["eips_released"] = release_orphaned_eips(region, profile, report["orphaned_eips"], actually_release=release_eips)
        regions_report[region] = report

    any_unreleased_orphan = any(r["orphaned_eips"] and not release_eips for r in regions_report.values())
    all_clean = all(r["clean"] for r in regions_report.values()) and not any_unreleased_orphan
    return {
        "drift": drift, "destroy_rc": destroy_rc,
        "regions": regions_report, "all_clean": all_clean,
        "forced": bool(force), "reason": reason if force else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf-dir", required=True)
    ap.add_argument("--profile", default="mockopin-pqc")
    ap.add_argument("--release-eips", action="store_true")
    ap.add_argument("--pull-verified-marker")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--reason", help="obrigatorio com --force -- motivo explicito (excecao de custo/seguranca, regra 7)")
    args = ap.parse_args()
    result = full_cleanup(args.tf_dir, args.profile, release_eips=args.release_eips,
                           pull_verified_marker=args.pull_verified_marker, force=args.force, reason=args.reason)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result["all_clean"] else 1)


if __name__ == "__main__":
    main()
