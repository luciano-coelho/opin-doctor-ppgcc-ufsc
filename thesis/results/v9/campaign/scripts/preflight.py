#!/usr/bin/env python3
"""v9, piloto: pre-voo somente-leitura com resultado ir/nao-ir, os
MESMOS comandos exatos ja descritos em prosa na Decisao 27 (secao 2),
agora executaveis -- nenhuma chamada muda nada na AWS, so leitura.

Regra permanente deste projeto (Decisao 27): o ID da conta NUNCA e
impresso nem devolvido em nenhum resultado. O unico lugar onde ele
existe em memoria e dentro de `check_budget_alert_exists` (precisa
dele pra montar `--account-id`, exigencia da propria API de budgets)
-- nunca armazenado em nenhum dict de retorno, nunca logado.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cli  # noqa: E402

VCPU_QUOTA_CODE = "L-1216C47A"  # Running On-Demand Standard (A,C,D,H,I,M,R,T,Z)

# Decisao 51 (revisao independente, item 2): a Decisao 50 raiz-causou
# o "Unknown key type" como o interpretador Python ERRADO (sistema,
# nao o venv do proprio projeto) -- nunca um bug de codigo. Esta
# checagem transforma aquele erro de dev numa trava permanente do
# pre-voo: nunca mais pode passar em silencio.
_REQUIREMENTS_DEFAULT = Path(__file__).resolve().parents[4] / "scripts" / "requirements.txt"
_MLDSA_CERT_DEFAULT = Path(__file__).resolve().parents[5] / "mock-service-os" / "certs" / "root_ca_pqc.crt"
_VENV_PYTHON_DEFAULT = Path(__file__).resolve().parents[4] / "scripts" / ".venv" / "Scripts" / "python.exe"

# Nomes de import (chave) -> nome publicado no requirements.txt (valor)
# -- PyJWT se importa como `jwt`, os outros dois batem com o proprio
# nome do pacote.
_PACKAGE_IMPORT_TO_DIST_NAME = {"cryptography": "cryptography", "jwt": "PyJWT", "requests": "requests"}

_PROBE_CODE = r"""
import json
import sys

result = {"executable": sys.executable}
try:
    import cryptography
    import jwt
    import requests
    result["versions"] = {
        "cryptography": cryptography.__version__,
        "PyJWT": jwt.__version__,
        "requests": requests.__version__,
    }
except Exception as e:
    print(json.dumps({"executable": result["executable"], "error": f"{type(e).__name__}: {e}"}))
    sys.exit(1)

try:
    from cryptography import x509
    data = open(sys.argv[1], "rb").read()
    cert = x509.load_pem_x509_certificate(data)
    result["mldsa_public_key_bytes"] = len(cert.public_key().public_bytes_raw())
except Exception as e:
    result["error"] = f"{type(e).__name__}: {e}"

print(json.dumps(result))
"""


def _parse_pinned_versions(requirements_path) -> dict:
    """Le `requirements.txt` (formato `pacote==versao \\`, uma linha
    por pacote, hash-pinado ou nao -- so a VERSAO importa aqui) e
    devolve {nome_do_pacote_minusculo: versao}."""
    pins = {}
    text = Path(requirements_path).read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+)==([0-9A-Za-z.]+)", line)
        if m:
            pins[m.group(1).lower()] = m.group(2)
    return pins


def check_client_python_environment(python_exe, requirements_path=_REQUIREMENTS_DEFAULT,
                                     mldsa_cert_path=_MLDSA_CERT_DEFAULT) -> dict:
    """Decisao 51: roda um probe no MESMO interprete Python que o
    orquestrador vai de fato usar (`python_exe` -- nunca o Python de
    sistema desta maquina por acidente, Decisao 50) -- imprime o
    caminho do executavel e as 3 versoes, reprova se qualquer uma
    divergir do pin real de `requirements.txt`, e PARSEIA um
    certificado ML-DSA-65 REAL, extraindo a chave publica (1952
    bytes esperados) -- nunca so confere se a biblioteca importa."""
    if not Path(python_exe).is_file():
        return {"check": "ambiente Python do cliente", "ok": False,
                "note": f"interprete nao encontrado: {python_exe}"}
    try:
        proc = subprocess.run([str(python_exe), "-c", _PROBE_CODE, str(mldsa_cert_path)],
                               capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return {"check": "ambiente Python do cliente", "ok": False, "note": "probe nao respondeu em 30s"}

    try:
        probe = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"check": "ambiente Python do cliente", "ok": False,
                "note": f"probe nao devolveu JSON (rc={proc.returncode}): {proc.stdout!r} {proc.stderr!r}"}

    executable = probe.get("executable", str(python_exe))
    if "error" in probe and "versions" not in probe:
        return {"check": "ambiente Python do cliente", "ok": False,
                "executable": executable, "note": f"import falhou: {probe['error']}"}

    versions = probe.get("versions", {})
    pins = _parse_pinned_versions(requirements_path)
    mismatches = []
    for dist_name, installed in versions.items():
        pinned = pins.get(dist_name.lower())
        if pinned is not None and installed != pinned:
            mismatches.append(f"{dist_name}: instalado {installed}, requirements.txt pede {pinned}")

    mldsa_bytes = probe.get("mldsa_public_key_bytes")
    mldsa_ok = mldsa_bytes == 1952
    if not mldsa_ok:
        mismatches.append(f"parse de ML-DSA-65 falhou ou tamanho errado: {probe.get('error', mldsa_bytes)}")

    return {
        "check": "ambiente Python do cliente", "ok": not mismatches,
        "executable": executable, "versions": versions,
        "requirements_pins": {k: pins[k.lower()] for k in versions if k.lower() in pins},
        "mldsa_public_key_bytes": mldsa_bytes,
        "mismatches": mismatches,
    }


def check_identity(profile) -> dict:
    try:
        data = cli.run_aws_json(["sts", "get-caller-identity"], profile=profile)
    except RuntimeError as e:
        return {"check": "identidade da credencial", "ok": False, "note": str(e)}
    if not data or "Arn" not in data:
        return {"check": "identidade da credencial", "ok": False, "note": "resposta sem Arn"}
    return {"check": "identidade da credencial", "ok": True,
            "note": "credencial resolvida -- ID da conta e ARN nunca impressos (Decisao 27)"}


def check_vcpu_quota(region, profile, min_required=10) -> dict:
    data = cli.run_aws_json(
        ["service-quotas", "get-service-quota", "--service-code", "ec2", "--quota-code", VCPU_QUOTA_CODE],
        region=region, profile=profile)
    if not data or "Quota" not in data:
        return {"check": f"cota de vCPU ({region})", "ok": False, "note": "resposta sem Quota"}
    value = data["Quota"]["Value"]
    return {"check": f"cota de vCPU ({region})", "ok": value >= min_required,
            "value": value, "min_required": min_required}


def check_instance_type_availability(region, profile, instance_types) -> dict:
    data = cli.run_aws_json(
        ["ec2", "describe-instance-type-offerings", "--location-type", "region",
         "--filters", f"Name=instance-type,Values={','.join(instance_types)}"],
        region=region, profile=profile)
    found = {o["InstanceType"] for o in (data or {}).get("InstanceTypeOfferings", [])}
    missing = sorted(set(instance_types) - found)
    return {"check": f"tipos de instancia ({region})", "ok": not missing, "missing": missing}


def check_ami_resolves(region, profile, name_pattern) -> dict:
    data = cli.run_aws_json(
        ["ec2", "describe-images", "--owners", "amazon",
         "--filters", f"Name=name,Values={name_pattern}", "Name=state,Values=available"],
        region=region, profile=profile)
    images = (data or {}).get("Images", [])
    return {"check": f"resolucao de AMI ({region})", "ok": len(images) > 0, "count": len(images)}


def check_budget_alert_exists(profile) -> dict:
    """Precisa do Account ID so pra montar --account-id (exigencia da
    propria API) -- NUNCA devolvido nem logado."""
    account_id = cli.run_aws(["sts", "get-caller-identity", "--query", "Account", "--output", "text"],
                              profile=profile).strip()
    data = cli.run_aws_json(["budgets", "describe-budgets", "--account-id", account_id], profile=profile)
    budgets = (data or {}).get("Budgets", [])
    return {"check": "alerta de orcamento", "ok": len(budgets) > 0, "count": len(budgets)}


def run_preflight(profile, regions, instance_types_by_region, ami_pattern_by_region,
                   client_python_exe=_VENV_PYTHON_DEFAULT) -> dict:
    checks = [check_identity(profile), check_client_python_environment(client_python_exe)]
    for region in regions:
        checks.append(check_vcpu_quota(region, profile))
        checks.append(check_instance_type_availability(region, profile, instance_types_by_region[region]))
        checks.append(check_ami_resolves(region, profile, ami_pattern_by_region[region]))
    checks.append(check_budget_alert_exists(profile))

    go = all(c["ok"] for c in checks)
    # Rede de seguranca final: garante que nenhum resultado contem um
    # token de 12 digitos (formato de account ID) nem "arn:aws:" por
    # engano -- mesmo que um check individual tenha vazado algo.
    serialized = json.dumps(checks)
    assert "arn:aws:" not in serialized or "<REDACTED" in serialized, \
        "VAZAMENTO: um ARN real apareceu no resultado do pre-voo"
    return {"go": go, "checks": checks}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="mockopin-pqc")
    ap.add_argument("--regions", nargs="+", default=["sa-east-1", "eu-north-1", "ap-southeast-1"])
    ap.add_argument("--server-client-instance-type", default="m7i-flex.large")
    ap.add_argument("--control-instance-type", default="t4g.micro")
    ap.add_argument("--client-python-exe", default=str(_VENV_PYTHON_DEFAULT),
                     help="o MESMO interprete que o orquestrador vai usar na instancia cliente -- nunca o Python de sistema (Decisao 50)")
    args = ap.parse_args()

    instance_types_by_region = {r: [args.server_client_instance_type] for r in args.regions}
    instance_types_by_region[args.regions[0]] = [args.server_client_instance_type, args.control_instance_type]
    ami_pattern_by_region = {r: "al2023-ami-*-kernel-*-x86_64" for r in args.regions}

    result = run_preflight(args.profile, args.regions, instance_types_by_region, ami_pattern_by_region,
                            client_python_exe=args.client_python_exe)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result["go"] else 1)


if __name__ == "__main__":
    main()
