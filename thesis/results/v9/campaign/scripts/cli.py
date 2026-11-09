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
    si, pra isolar completamente qualquer chamada real a aws/ssh/scp.

    `stdin=DEVNULL` explicito -- higiene defensiva (nenhum chamador
    deste modulo jamais precisa de stdin herdado; `pki_relay.py`
    entrega a chave via arquivo temporario + `scp`, nunca via stdin
    de `cli.run_ssh`), nao a causa nem a correcao de nenhum achado
    especifico (ver Decisao 94, `dedicated_criteria.run_criterio2`,
    pra um hang real de SSH cuja causa era outra -- throttling
    transitorio do servidor, nunca sintaxe de comando)."""
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)


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


class _LocalShellShim:
    """Decisao 49: pra PROVAR que o comando remoto real do orquestrador
    funciona (sem SSH, sem AWS), roda o MESMO `remote_cmd` num shell
    LOCAL, contra o stack local da v9 -- nunca usado por padrao, nunca
    em producao. `host`/`user`/`key_path` sao ignorados de proposito
    (o shim nunca disca nada de verdade); so existe pra validacao
    manual/local, ligado explicitamente via `enable()`.

    Reescreve so o que e diferente entre uma instancia EC2 real
    (`~` = `/home/ec2-user`, `python3` no PATH) e esta maquina de
    desenvolvimento: troca o prefixo `cd ~/thesis/scripts && ` pelo
    `cwd` real passado, e injeta um `python3` real no PATH do
    subprocesso (nesta maquina, `python3` resolve pro stub inutil da
    Microsoft Store -- achado ja registrado nesta sessao)."""

    def __init__(self, scripts_cwd, python_exe, shim_bin_dir):
        self.scripts_cwd = str(scripts_cwd)
        self.python_exe = str(python_exe)
        self.shim_bin_dir = str(shim_bin_dir)

    def run(self, remote_cmd, timeout):
        import os
        import shutil

        prefix = "cd ~/thesis/scripts && "
        cmd = remote_cmd[len(prefix):] if remote_cmd.startswith(prefix) else remote_cmd
        Path(self.shim_bin_dir).mkdir(parents=True, exist_ok=True)
        python3_shim = Path(self.shim_bin_dir) / "python3"
        python3_shim.write_text(f'#!/bin/sh\nexec "{self.python_exe}" "$@"\n', encoding="utf-8")
        python3_shim.chmod(0o755)
        env = dict(os.environ)
        env["PATH"] = self.shim_bin_dir + os.pathsep + env.get("PATH", "")
        # MSYS_NO_PATHCONV: sem isso, o git-bash deste ambiente Windows
        # mangla argumentos de `docker run -v <host>:<container>`
        # (confirmado nesta sessao, repetidas vezes) -- o `$(pwd)/...`
        # usado nos comandos remotos reais precisa chegar ao `docker`
        # intacto.
        env["MSYS_NO_PATHCONV"] = "1"
        shell = shutil.which("bash") or shutil.which("sh") or "bash"
        proc = subprocess.run([shell, "-c", cmd], capture_output=True, text=True,
                               cwd=self.scripts_cwd, env=env, timeout=timeout)
        return proc


_local_shell_shim: "_LocalShellShim | None" = None


def enable_local_shell_shim(scripts_cwd, python_exe, shim_bin_dir):
    """SO pra validacao manual/local (Decisao 49) -- NUNCA chamado
    pelo fluxo normal do piloto. Depois de habilitado, `run_ssh()`
    para de discar SSH de verdade e passa a rodar `remote_cmd` num
    shell local, contra `scripts_cwd`."""
    global _local_shell_shim
    _local_shell_shim = _LocalShellShim(scripts_cwd, python_exe, shim_bin_dir)


def disable_local_shell_shim():
    global _local_shell_shim
    _local_shell_shim = None


def run_ssh(host, remote_cmd, user="ec2-user", key_path=None, port=22, connect_timeout=20):
    """SSH pro `host` dado EXATAMENTE como passado -- esta funcao
    nunca escolhe IP publico ou privado por conta propria; Decisao
    43/45 exige que todo CHAMADOR desta funcao, pra SSH
    especificamente, sempre passe o IP PUBLICO do alvo, nunca o
    privado, mesmo pro cliente L0 co-localizado (so o trafego de
    GATEWAY/443 usa o IP privado do L0, Decisao 27 item 1 -- isso e
    decidido pelo orquestrador, nunca aqui).

    Se `enable_local_shell_shim()` tiver sido chamada (so validacao
    manual, Decisao 49), `host`/`user`/`key_path` sao ignorados e o
    comando roda localmente -- ver `_LocalShellShim`."""
    if _local_shell_shim is not None:
        return _local_shell_shim.run(remote_cmd, timeout=connect_timeout + 60)
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
