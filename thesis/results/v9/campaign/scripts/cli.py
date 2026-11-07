#!/usr/bin/env python3
"""v9, piloto: unica fronteira por onde qualquer script do piloto fala
com `aws`/`ssh`/`scp` de verdade -- todo o resto deste pacote chama
SO estas funcoes, nunca subprocess diretamente, pra que os testes
consigam substituir exatamente este ponto (stub da CLI, nenhuma
chamada real, nenhuma credencial) sem reimplementar nada da logica
real em cada teste.

`redact()` e reaproveitada direto do arquivo real da v8
(`v8/campaign/scripts/redact_aws_errors.py`), via sys.path -- nunca
duplicada aqui.
"""
import json
import subprocess
import sys
from pathlib import Path

_V8_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "v8" / "campaign" / "scripts"
if str(_V8_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_V8_SCRIPTS_DIR))
from redact_aws_errors import redact  # noqa: E402  (reaproveitado da v8, nao duplicado)

__all__ = ["redact", "run_aws", "run_aws_json", "run_ssh", "run_scp", "run_terraform"]


def _run(argv, timeout=None):
    """Unico lugar que de fato chama subprocess.run -- os testes
    monkeypatcham ISTO (cli._run), nunca o subprocess do Python em
    si, pra isolar completamente qualquer chamada real a aws/ssh/scp."""
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)


def run_aws(args, profile=None, region=None, timeout=30):
    """`aws <args...>` com --output json POR PADRAO -- se o chamador
    ja pedir um --output especifico (ex.: "text", pra extrair um
    valor escalar como o Account ID sem decodificar JSON), esse
    pedido e respeitado, nunca duplicado (dois --output na mesma
    chamada faria a CLI real obedecer so o ultimo, silenciosamente
    ignorando o do chamador). Levanta RuntimeError (texto JA redigido)
    se o comando falhar -- nunca deixa um ARN/account ID de verdade
    escapar pro chamador sem passar por `redact()`."""
    argv = ["aws", *args]
    if "--output" not in args:
        argv += ["--output", "json"]
    if profile:
        argv += ["--profile", profile]
    if region:
        argv += ["--region", region]
    proc = _run(argv, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"aws {' '.join(args)} falhou: {redact(proc.stderr)}")
    return proc.stdout


def run_aws_json(args, profile=None, region=None, timeout=30):
    """Como run_aws(), mas decodifica o JSON -- None se a saida vier
    vazia (comportamento real de alguns comandos `aws` de escrita)."""
    text = run_aws(args, profile=profile, region=region, timeout=timeout).strip()
    if not text:
        return None
    return json.loads(text)


def run_ssh(host, remote_cmd, user="ec2-user", key_path=None, port=22, connect_timeout=20):
    """SSH pro `host` dado EXATAMENTE como passado -- esta funcao
    nunca escolhe IP publico ou privado por conta propria; Decisao
    43/45 exige que todo CHAMADOR desta funcao, pra SSH
    especificamente, sempre passe o IP PUBLICO do alvo, nunca o
    privado, mesmo pro cliente L0 co-localizado (so o trafego de
    GATEWAY/443 usa o IP privado do L0, Decisao 27 item 1 -- isso e
    decidido pelo orquestrador, nunca aqui)."""
    argv = ["ssh", "-p", str(port),
             "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
             "-o", f"ConnectTimeout={connect_timeout}", "-o", "BatchMode=yes"]
    if key_path:
        argv += ["-i", str(key_path)]
    argv += [f"{user}@{host}", remote_cmd]
    return _run(argv, timeout=connect_timeout + 30)


def run_scp(src, dst, key_path=None, port=22, connect_timeout=20, recursive=False):
    argv = ["scp", "-P", str(port),
            "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", f"ConnectTimeout={connect_timeout}", "-o", "BatchMode=yes"]
    if recursive:
        argv.insert(1, "-r")
    if key_path:
        argv += ["-i", str(key_path)]
    argv += [src, dst]
    return _run(argv, timeout=connect_timeout + 120)


def run_terraform(args, cwd, timeout=120):
    """`terraform <args...>` dentro de `cwd` -- saida redigida antes
    de subir pro chamador, mesma politica de campaign_down.sh real da
    v8 (erro de apply/destroy pode embutir ARN de conta)."""
    proc = subprocess.run(["terraform", *args], capture_output=True, text=True, cwd=cwd, timeout=timeout)
    stdout, stderr = redact(proc.stdout), redact(proc.stderr)
    return proc.returncode, stdout, stderr
