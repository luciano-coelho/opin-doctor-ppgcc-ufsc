#!/usr/bin/env python3
"""v9, piloto: pre-checagem do IP publico do OPERADOR contra a regra
de ingress SSH gravada no estado do Terraform -- Decisao 75, item 5
(pedido do Luciano, apos o bloqueio real de 8 minutos da Decisao 72,
cuja causa raiz nunca foi determinada com certeza). NUNCA confunde com
a regra controle->servidor/clientes (essa usa o EIP do CONTROLE, ja
correta por design -- ver deliver_source.py); esta aqui e so a regra
que deixa o OPERADOR entrar via SSH no controle
(`module.control.aws_vpc_security_group_ingress_rule.ssh["operator"]`,
terraform/main.tf linha 131: `ssh_ingress_cidrs = {"operator":
var.operator_ip_cidr}`).

Seguranca barata, independente de confirmar aquela causa raiz: se o IP
publico do operador tiver mudado desde o ultimo `terraform apply`
(rede dinamica, VPN, etc.), a regra antiga continua aceita pelo
Security Group, mas o trafego SSH do operador JA NAO BATE com ela --
reaplica so esta regra (`-target`, nunca um apply completo) ANTES de
qualquer fase do roteiro depender de SSH funcionar. Fail-fast: qualquer
falha (curl, terraform show, terraform apply) levanta RuntimeError --
nunca segue em frente com uma regra possivelmente desatualizada.

Uso:
  python check_operator_ip.py --tf-dir <diretorio do terraform>
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cli  # noqa: E402

CHECKIP_URL = "https://checkip.amazonaws.com"
SSH_RULE_ADDRESS = 'module.control.aws_vpc_security_group_ingress_rule.ssh["operator"]'


def current_operator_ip(timeout=10) -> str:
    proc = cli._run(["curl", "-s", CHECKIP_URL], timeout=timeout)
    ip = (proc.stdout or "").strip()
    if proc.returncode != 0 or not ip:
        raise RuntimeError(f"current_operator_ip: curl falhou: {cli.redact(proc.stderr)}")
    return ip


def _iter_modules(module: dict):
    yield module
    for child in module.get("child_modules", []):
        yield from _iter_modules(child)


def _find_resource(state: dict, address: str):
    root = state.get("values", {}).get("root_module", {})
    for module in _iter_modules(root):
        for resource in module.get("resources", []):
            if resource.get("address") == address:
                return resource
    return None


def last_applied_operator_cidr(tf_dir) -> str:
    returncode, stdout, stderr = cli.run_terraform(["show", "-json"], cwd=tf_dir, timeout=60)
    if returncode != 0:
        raise RuntimeError(f"last_applied_operator_cidr: terraform show falhou: {stderr}")
    state = json.loads(stdout)
    resource = _find_resource(state, SSH_RULE_ADDRESS)
    if resource is None:
        raise RuntimeError(
            f"last_applied_operator_cidr: recurso {SSH_RULE_ADDRESS} nao encontrado no state "
            "(fleet nao existe ou endereco mudou)"
        )
    return resource["values"]["cidr_ipv4"]


def ensure_operator_ip_current(tf_dir, timeout=10) -> dict:
    """Decisao 75, item 5. Compara o IP ATUAL do operador contra o /32
    gravado na regra de ingress SSH; se diferente, reaplica SO essa
    regra (-target, nunca um apply completo da fleet inteira) com o IP
    novo. Levanta RuntimeError em qualquer falha -- nunca retorna
    silenciosamente pro chamador seguir com uma regra desatualizada."""
    now_ip = current_operator_ip(timeout=timeout)
    now_cidr = f"{now_ip}/32"
    applied_cidr = last_applied_operator_cidr(tf_dir)
    if now_cidr == applied_cidr:
        return {"changed": False, "cidr": applied_cidr}

    returncode, stdout, stderr = cli.run_terraform(
        ["apply", "-auto-approve", f"-target={SSH_RULE_ADDRESS}", f"-var=operator_ip_cidr={now_cidr}"],
        cwd=tf_dir, timeout=120,
    )
    if returncode != 0:
        raise RuntimeError(f"ensure_operator_ip_current: reaplicar a regra falhou: {stderr}")
    return {"changed": True, "old_cidr": applied_cidr, "new_cidr": now_cidr}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf-dir", required=True)
    args = ap.parse_args()
    try:
        result = ensure_operator_ip_current(args.tf_dir)
    except RuntimeError as e:
        print(json.dumps({"ok": False, "error": str(e)}, indent=2, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps({"ok": True, **result}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
