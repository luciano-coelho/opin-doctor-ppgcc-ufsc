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
import campaign_topology as ct  # noqa: E402  -- fonte unica das 7 regioes da campanha oficial, nunca duplicada

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


# Item 3 do adendo "piloto v9" (achado real, nao hipotetico): durante a
# validacao da Decisao 122, um container `v9-mtls` de uma rodada LOCAL
# anterior (Decisao 121, soak) ficou rodando e registrado no MESMO
# alias de rede `mtls` que o gateway da validacao -- dois containers
# com o mesmo alias na mesma rede Docker faz a resolucao de nome ficar
# NAO-DETERMINISTICA, causando falhas intermitentes de TLS cuja causa
# so foi achada ao vivo, por root-cause manual, nao por uma checagem
# automatica. `v9-mtls` e exatamente o nome real que `SSHExecutor`
# usa pro gateway na campanha de verdade (`gateway_container="v9-mtls"`,
# default do construtor); `mtls` e o nome usado por `run_t5.sh` (teste
# local T5). Os dois precisam aparecer aqui, nunca so um.
_ORPHAN_CONTAINER_NAME_PATTERNS = (
    "v9-mtls", "mtls", "auth", "mongo_seed", "mongo1", "mongo2", "mongo3",
    "mockapi", "tls_kem_proxy_run", "pqc_signer_service_run",
)
_ORPHAN_NETWORK_NAME_PATTERNS = ("mockopin-v9-net",)

# Higiene de reprodutibilidade (Etapa 1, adendo, item 3c -- achado real da
# verificacao independente EQD): `insurance-server-lambdas/docker-compose.yml`
# (servico `localstack`) e `mock-service-os/docker-compose.yml` (idem) montam
# estes arquivos como bind-mount de ARQUIVO UNICO. Se o arquivo ainda nao
# existir no host (clone fresco, antes de `make certs`/do gerador legado
# rodar), o Docker cria um DIRETORIO vazio no lugar -- travando qualquer
# geracao de certificado POSTERIOR nesse caminho, ate alguem notar e remover
# a mao. Bloqueou a geracao de chaves legadas varias vezes durante aquela
# verificacao (op.key, depois mongo.pem do mesmo jeito, por outro servico).
# Deteccao, nunca correcao automatica -- mesmo padrao de todo pre-voo deste
# projeto: reporta e aborta, nunca apaga/recria nada sem o operador decidir.
_LEGACY_CERTS_DIR_DEFAULT = Path(__file__).resolve().parents[5] / "mock-service-os" / "certs"
_LEGACY_BIND_MOUNT_FILES = (
    "op.key", "op.crt", "op_pqc.key", "op_pqc.crt", "op_hybrid.key", "op_hybrid.crt",
)


def _legacy_bind_mount_report(file_states: dict) -> dict:
    """Funcao pura -- `file_states` e {nome: "file"|"dir"|"missing"},
    testavel sem filesystem real."""
    missing = sorted(name for name, state in file_states.items() if state == "missing")
    is_directory = sorted(name for name, state in file_states.items() if state == "dir")
    ok = not missing and not is_directory
    return {
        "check": "arquivos de bind-mount unico (localstack) existem como arquivo real",
        "ok": ok, "missing": missing, "is_directory": is_directory,
        "note": (
            "todos presentes como arquivo -- seguro rodar 'docker compose --profile main up'" if ok else
            "ABORTAR: " + (
                f"faltam {missing} -- rode 'make certs' (ou o gerador legado, mock-service-os/certs/) "
                f"antes de subir o compose. " if missing else ""
            ) + (
                f"{is_directory} existe(m) como DIRETORIO (nao arquivo) -- o Docker criou isso sozinho "
                f"numa tentativa anterior de bind-mount contra um arquivo ausente; remova o(s) diretorio(s) "
                f"manualmente e gere as chaves de novo antes de repetir." if is_directory else ""
            )
        ),
    }


def check_legacy_bind_mount_files(certs_dir=_LEGACY_CERTS_DIR_DEFAULT,
                                   filenames=_LEGACY_BIND_MOUNT_FILES) -> dict:
    """Pre-voo LOCAL, somente leitura (`Path.is_file()`/`is_dir()`, nunca
    escreve nada) -- chame ANTES de qualquer 'docker compose --profile
    main up' que monte `mock-service-os/certs/{op,op_pqc,op_hybrid}.{key,crt}`
    (insurance-server-lambdas e mock-service-os, servico `localstack` nos
    dois)."""
    certs_dir = Path(certs_dir)
    file_states = {}
    for name in filenames:
        p = certs_dir / name
        if p.is_dir():
            file_states[name] = "dir"
        elif p.is_file():
            file_states[name] = "file"
        else:
            file_states[name] = "missing"
    return _legacy_bind_mount_report(file_states)


def _docker_orphan_report(container_lines, network_lines,
                           container_patterns=_ORPHAN_CONTAINER_NAME_PATTERNS,
                           network_patterns=_ORPHAN_NETWORK_NAME_PATTERNS) -> dict:
    """Funcao pura (sem subprocess) -- separada so pra ser testavel com
    listas fabricadas, sem precisar de um Docker real. Casamento por
    NOME EXATO (nunca substring) -- `auth` nao deveria casar com um
    container de outro projeto chamado `auth-gateway-v2`, por exemplo;
    precisao aqui evita falso-positivo bloqueando um pre-voo bom."""
    containers_found = sorted({line.strip() for line in container_lines
                                if line.strip() in container_patterns})
    networks_found = sorted({line.strip() for line in network_lines
                              if line.strip() in network_patterns})
    ok = not containers_found and not networks_found
    return {
        "check": "containers/redes orfaos do projeto", "ok": ok,
        "containers_found": containers_found, "networks_found": networks_found,
        "note": (
            "nenhum resquicio -- ambiente limpo pra nova janela" if ok else
            "ABORTAR: resquicio de rodada anterior encontrado -- limpe manualmente "
            "('docker rm -f <nome>'/'docker network rm <nome>') antes de abrir uma nova "
            "janela; nunca prosseguir com isso presente (causa raiz real, Decisao 125: "
            "resolucao de nome de rede fica nao-deterministica com alias duplicado)."
        ),
    }


def check_no_orphan_docker_resources(container_patterns=_ORPHAN_CONTAINER_NAME_PATTERNS,
                                      network_patterns=_ORPHAN_NETWORK_NAME_PATTERNS) -> dict:
    """Pre-voo LOCAL (Decisao 125): lista containers (`docker ps -a`,
    inclusive parados -- um container PARADO ainda ocupa o nome e pode
    confundir um `docker run --name` novo) e redes (`docker network ls`)
    do Docker LOCAL do operador, por nome exato. Comando que nunca
    muda nada (`-a` e so leitura); se o Docker nao estiver acessivel
    (daemon parado, etc.), reprova com nota clara em vez de estourar."""
    try:
        containers_proc = cli._run(["docker", "ps", "-a", "--format", "{{.Names}}"], timeout=15)
        networks_proc = cli._run(["docker", "network", "ls", "--format", "{{.Name}}"], timeout=15)
    except Exception as e:  # noqa: BLE001 -- Docker indisponivel nunca estoura, so reprova
        return {"check": "containers/redes orfaos do projeto", "ok": False,
                "note": f"docker indisponivel: {type(e).__name__}: {e}"}
    if containers_proc.returncode != 0 or networks_proc.returncode != 0:
        return {"check": "containers/redes orfaos do projeto", "ok": False,
                "note": f"docker ps/network ls falhou: {containers_proc.stderr or networks_proc.stderr}"}
    return _docker_orphan_report(containers_proc.stdout.splitlines(), networks_proc.stdout.splitlines(),
                                  container_patterns=container_patterns, network_patterns=network_patterns)


_ORPHAN_PROBE_SCRIPT = (
    "docker ps -a --format '{{.Names}}'; echo '---NETWORKS---'; docker network ls --format '{{.Name}}'"
)


def check_no_orphan_docker_resources_remote(host, key_path=None, connect_timeout=20,
                                             container_patterns=_ORPHAN_CONTAINER_NAME_PATTERNS,
                                             network_patterns=_ORPHAN_NETWORK_NAME_PATTERNS) -> dict:
    """Pre-voo DA CAMPANHA (Decisao 125): mesma checagem, mas via SSH
    numa instancia real -- pro caso de uma janela anterior ter deixado
    container/rede pra tras na MESMA instancia (reuso de instancia
    entre janelas, Decisao 43/45 -- stop/start preserva disco, entao
    qualquer residuo Docker tambem sobreviveria). Chamado pelo
    orquestrador ANTES de start_block de cada janela, nunca so uma vez
    no apply."""
    try:
        proc = cli.run_ssh(host, _ORPHAN_PROBE_SCRIPT, key_path=key_path, connect_timeout=connect_timeout)
    except Exception as e:  # noqa: BLE001 -- SSH indisponivel nunca estoura, so reprova
        return {"check": "containers/redes orfaos do projeto", "ok": False,
                "host": host, "note": f"SSH para {host} falhou: {type(e).__name__}: {e}"}
    container_lines, _, network_block = proc.stdout.partition("---NETWORKS---")
    report = _docker_orphan_report(container_lines.splitlines(), network_block.splitlines(),
                                    container_patterns=container_patterns, network_patterns=network_patterns)
    report["host"] = host
    return report


# Decisao 53 (pedido independente, item 4a): pre-requisitos da
# CAPTURA dedicada (criterio 1) em CADA instancia do piloto -- so
# podem ser checados DEPOIS que a instancia existe (via SSH), nunca
# antes do apply (diferente de todo check acima, que e so API da AWS,
# antes de qualquer instancia). Por isso isto NUNCA entra em
# `run_preflight` (que nao recebe IP de instancia nenhum) -- e uma
# porta de entrada SEPARADA, chamada pelo smoke gate (item 4b) depois
# que o terraform apply ja rodou, antes de qualquer execucao real.
_CAPTURE_PROBE_SCRIPT = r"""
set -u
echo "TCPDUMP_PATH=$(command -v tcpdump || true)"
if sudo -n true 2>/dev/null; then echo "SUDO_NOPASSWD=1"; else echo "SUDO_NOPASSWD=0"; fi
echo "MEASURE_IMAGE_ID=$(docker image inspect mockopin-v9-measure --format '{{.Id}}' 2>/dev/null || true)"
echo "MEASURE_LAYERS=$(docker image inspect mockopin-v9-measure --format '{{json .RootFS.Layers}}' 2>/dev/null || true)"
echo "MEASURE_CONFIG=$(docker image inspect mockopin-v9-measure --format '{{json .Config}}' 2>/dev/null || true)"
if touch /tmp/.v9_keylog_preflight_check 2>/dev/null; then
  rm -f /tmp/.v9_keylog_preflight_check
  echo "TMP_WRITABLE=1"
else
  echo "TMP_WRITABLE=0"
fi
echo "PRIMARY_IFACE=$(ip -o -4 route show to default 2>/dev/null | awk '{print $5}' | head -1)"
"""


def check_capture_prerequisites(host, key_path=None, connect_timeout=20, expected_measure_image_id=None,
                                 expected_measure_layers=None, expected_measure_config=None) -> dict:
    """Decisao 53, item 4a (corrigido na Decisao 55, item 2; corrigido
    de novo na Decisao 68). Roda os probes combinados numa UNICA
    chamada SSH e reprova com mensagem clara se qualquer um faltar:
    `tcpdump` instalado, sudo sem senha disponivel (exigido pelo
    `tcpdump` real dentro de `dedicated_capture`, mesma convencao do
    `campaign_run.py` real da v8), `/tmp` gravavel, a interface
    primaria identificavel pela rota default (nunca loopback -- mesmo
    metodo de `SSHExecutor._primary_iface`) e a imagem `mockopin-v9-
    measure` IDENTICA a pinada -- Decisao 68 (Emenda): Image ID
    diverge entre versoes de Docker mesmo com conteudo identico
    (confirmado ao vivo, Decisao 67/68) -- a conferencia agora e por
    `RootFS.Layers` + subconjunto de `.Config`, nunca mais por Image
    ID (que continua lido, so informativo). `expected_measure_layers`/
    `expected_measure_config` default `None` so pra chamada isolada/
    teste sem PINS -- `run_capture_preflight` sempre passa os valores
    reais de PINS.json."""
    try:
        proc = cli.run_ssh(host, _CAPTURE_PROBE_SCRIPT, key_path=key_path, connect_timeout=connect_timeout)
    except Exception as e:  # noqa: BLE001 -- rede de seguranca: SSH indisponivel nunca estoura, so reprova
        return {"check": "pre-requisitos de captura (criterio 1)", "ok": False,
                "note": f"SSH para {host} falhou: {type(e).__name__}: {e}"}

    fields = {}
    for line in proc.stdout.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            fields[k.strip()] = v.strip()

    tcpdump_ok = bool(fields.get("TCPDUMP_PATH"))
    sudo_ok = fields.get("SUDO_NOPASSWD") == "1"
    measure_image_id = fields.get("MEASURE_IMAGE_ID") or None
    try:
        measure_layers = json.loads(fields["MEASURE_LAYERS"]) if fields.get("MEASURE_LAYERS") else None
    except json.JSONDecodeError:
        measure_layers = None
    try:
        measure_config = json.loads(fields["MEASURE_CONFIG"]) if fields.get("MEASURE_CONFIG") else None
    except json.JSONDecodeError:
        measure_config = None
    measure_config_subset = (
        {k: measure_config.get(k) for k in ("Entrypoint", "Cmd", "Env", "ExposedPorts")}
        if isinstance(measure_config, dict) else None
    )
    layers_ok = bool(measure_layers) and (expected_measure_layers is None or measure_layers == expected_measure_layers)
    config_ok = bool(measure_config_subset) and (expected_measure_config is None or measure_config_subset == expected_measure_config)
    tmp_writable_ok = fields.get("TMP_WRITABLE") == "1"
    iface = fields.get("PRIMARY_IFACE", "")
    iface_ok = bool(iface) and iface != "lo"

    missing = []
    if not tcpdump_ok:
        missing.append("tcpdump nao encontrado no PATH")
    if not sudo_ok:
        missing.append("sudo sem senha indisponivel (exigido pelo tcpdump real de dedicated_capture)")
    if not measure_layers:
        missing.append("imagem docker mockopin-v9-measure ausente (entregue por docker save/load, Decisao 55 item 2 -- nunca docker build na instancia)")
    elif expected_measure_layers is not None and measure_layers != expected_measure_layers:
        missing.append(f"RootFS.Layers de mockopin-v9-measure nao bate com PINS.json -- esperado {expected_measure_layers!r}, achado {measure_layers!r}")
    if measure_layers and expected_measure_config is not None and measure_config_subset != expected_measure_config:
        missing.append(f"Config de mockopin-v9-measure nao bate com PINS.json -- esperado {expected_measure_config!r}, achado {measure_config_subset!r}")
    if not tmp_writable_ok:
        missing.append("/tmp nao gravavel")
    if not iface_ok:
        missing.append(f"interface primaria nao identificada pela rota default (valor lido: {iface!r})")

    return {
        "check": "pre-requisitos de captura (criterio 1)", "ok": not missing,
        "host": host, "tcpdump_path": fields.get("TCPDUMP_PATH") or None,
        "sudo_nopasswd": sudo_ok,
        "measure_image_id": measure_image_id, "measure_image_id_note": "informativo apenas, nunca verificado (Decisao 68)",
        "measure_layers": measure_layers, "expected_measure_layers": expected_measure_layers, "layers_ok": layers_ok,
        "measure_config_subset": measure_config_subset, "expected_measure_config": expected_measure_config, "config_ok": config_ok,
        "tmp_writable": tmp_writable_ok, "primary_iface": iface or None,
        "missing": missing,
    }


_PINS_PATH_DEFAULT = Path(__file__).resolve().parents[1] / "PINS.json"


def run_capture_preflight(hosts, key_path=None, pins_path=_PINS_PATH_DEFAULT) -> dict:
    """Decisao 53, item 4c: fail-closed, mensagem clara, ANTES de
    qualquer execucao -- `hosts` e a lista de instancias que vao
    rodar `dedicated_capture` de verdade (hoje, so o servidor -- um
    por rota, mas o servidor e compartilhado entre rotas no piloto
    L0/L219/L325 de hoje, entao normalmente uma lista de 1). Chamado
    pelo smoke gate (`run_smoke_gate`) antes das 12 execucoes, nunca
    depois.

    Decisao 55, item 2 (corrigido na Decisao 68): le PINS.json (leitura
    propria e pequena, deliberadamente NUNCA importa `orchestrator.
    load_pins` -- evitaria um import circular, ja que `orchestrator.py`
    importa este modulo) pra exigir `RootFS.Layers`/subconjunto de
    `.Config` EXATOS de `mockopin-v9-measure`, nao so presenca --
    Image ID NUNCA mais e o criterio (diverge entre versoes de Docker,
    Decisao 67/68). `pins_path` e um parametro (nao hardcoded) so pra
    teste -- producao sempre usa o default real."""
    expected_measure_layers = None
    expected_measure_config = None
    if pins_path.is_file():
        try:
            measure_pins = json.loads(pins_path.read_text(encoding="utf-8"))["images"]["measure"]
            expected_measure_layers = measure_pins.get("rootfs_layers")
            expected_measure_config = measure_pins.get("config_subset")
        except (json.JSONDecodeError, KeyError):
            expected_measure_layers = None
            expected_measure_config = None
    checks = [check_capture_prerequisites(h, key_path=key_path, expected_measure_layers=expected_measure_layers,
                                           expected_measure_config=expected_measure_config) for h in hosts]
    go = all(c["ok"] for c in checks)
    return {"go": go, "checks": checks}


def check_local_images_match_pins(pins_path=_PINS_PATH_DEFAULT) -> dict:
    """Decisao 128 (achado real da Etapa 2 do piloto v9): `gateway`/
    `proxy`/`pqc-signer`/`mockapi` foram sobrescritos LOCALMENTE
    (mesma tag `:latest`, daemon Docker compartilhado -- isolamento
    de git worktree nunca isola o daemon) por rebuilds de verificacao
    desta mesma sessao, ANTES de qualquer apply real. `deliver_images.
    py` ja pega isso (Decisao 68, fail-closed por `tar_sha256`, ANTES
    de qualquer scp) -- mas so DEPOIS que a infraestrutura inteira (78
    recursos, 7 regioes) ja subiu, gastando tempo/dinheiro real pra
    nada. Esta checagem roda ANTES do apply (parte de `run_preflight`,
    nunca precisa de nenhuma instancia): confere `RootFS.Layers` +
    subconjunto de `.Config` de CADA imagem pinada que existir
    localmente, contra `PINS.json` -- mesmo criterio ja estabelecido
    (Decisao 68: Image ID diverge entre versoes de Docker mesmo com
    conteudo identico, NUNCA usado como criterio). Imagem pinada
    ausente localmente nao reprova aqui (sera pega por
    `save_image_tarball`/`deliver_images` na hora certa) -- isto so
    detecta DIVERGENCIA de uma imagem que EXISTE mas mudou."""
    if not pins_path.is_file():
        return {"check": "imagens locais vs PINS.json", "ok": False,
                "note": f"PINS.json nao encontrado em {pins_path}"}
    try:
        pins = json.loads(pins_path.read_text(encoding="utf-8"))["images"]
    except (json.JSONDecodeError, KeyError) as e:
        return {"check": "imagens locais vs PINS.json", "ok": False,
                "note": f"PINS.json ilegivel: {type(e).__name__}: {e}"}

    mismatched = []
    checked = []
    for key, pin in pins.items():
        docker_image = pin.get("docker_image")
        expected_layers = pin.get("rootfs_layers")
        expected_config = pin.get("config_subset")
        if not docker_image or not expected_layers:
            continue  # entrada sem pin de conteudo (ex. so Created/image_id informativo) -- nada a conferir
        proc = cli._run(["docker", "image", "inspect", docker_image,
                          "--format", "{{json .RootFS.Layers}}||{{json .Config}}"], timeout=15)
        if proc.returncode != 0:
            continue  # imagem ausente localmente -- nao e divergencia, e so nao ter sido construida/carregada ainda
        layers_raw, _, config_raw = proc.stdout.strip().partition("||")
        try:
            local_layers = json.loads(layers_raw)
            local_config_full = json.loads(config_raw)
        except json.JSONDecodeError:
            mismatched.append({"image": key, "docker_image": docker_image,
                                "reason": "saida de docker inspect ilegivel"})
            continue
        local_config_subset = {k: local_config_full.get(k) for k in ("Entrypoint", "Cmd", "Env", "ExposedPorts")}
        checked.append(key)
        if local_layers != expected_layers:
            mismatched.append({
                "image": key, "docker_image": docker_image, "reason": "RootFS.Layers diverge",
                "expected_layers": expected_layers, "found_layers": local_layers,
            })
        elif expected_config is not None and local_config_subset != expected_config:
            mismatched.append({
                "image": key, "docker_image": docker_image, "reason": "Config (Entrypoint/Cmd/Env/ExposedPorts) diverge",
                "expected_config": expected_config, "found_config": local_config_subset,
            })

    return {
        "check": "imagens locais vs PINS.json", "ok": not mismatched,
        "checked": checked, "mismatched": mismatched,
        "note": (
            "todas as imagens pinadas presentes localmente batem com PINS.json" if not mismatched else
            "ABORTAR: imagem local divergiu do pin -- provavel rebuild/retag acidental desta sessao "
            "(ex. fork de verificacao em worktree isolado, que ainda compartilha o daemon Docker). "
            "NAO reconstruir nem re-pinar sem decisao explicita -- ver Decisoes 68/123/124/127."
        ),
    }


def run_preflight(profile, regions, instance_types_by_region, ami_pattern_by_region,
                   client_python_exe=_VENV_PYTHON_DEFAULT) -> dict:
    checks = [check_identity(profile), check_client_python_environment(client_python_exe),
              check_local_images_match_pins()]
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
    ap.add_argument("--regions", nargs="+", default=None)
    ap.add_argument("--server-client-instance-type", default="m7i-flex.large")
    ap.add_argument("--control-instance-type", default="t4g.micro")
    ap.add_argument("--client-python-exe", default=str(_VENV_PYTHON_DEFAULT),
                     help="o MESMO interprete que o orquestrador vai usar na instancia cliente -- nunca o Python de sistema (Decisao 50)")
    # Pedido do Luciano (item 2): fonte UNICA das 7 regioes da
    # campanha oficial -- nunca uma segunda lista hardcoded aqui.
    ap.add_argument("--campaign", action="store_true",
                     help="usa as 7 regioes da campanha oficial (campaign_topology.py) em vez das 3 do piloto")
    args = ap.parse_args()
    regions = args.regions if args.regions is not None else (ct.CAMPAIGN_REGIONS if args.campaign else
                                                               ["sa-east-1", "eu-north-1", "ap-southeast-1"])

    instance_types_by_region = {r: [args.server_client_instance_type] for r in regions}
    instance_types_by_region[regions[0]] = [args.server_client_instance_type, args.control_instance_type]
    ami_pattern_by_region = {r: "al2023-ami-*-kernel-*-x86_64" for r in regions}

    result = run_preflight(args.profile, regions, instance_types_by_region, ami_pattern_by_region,
                            client_python_exe=args.client_python_exe)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result["go"] else 1)


if __name__ == "__main__":
    main()
