#!/usr/bin/env python3
"""Decisao 172: launcher de persistencia pro orquestrador (pedido do
Luciano, item 4b da Decisao 171 -- o procedimento documentado ate aqui
rodava `orchestrator.py` direto dentro de uma sessao SSH bloqueante do
operador; uma queda de internet do operador matava a execucao real no
meio de uma janela). Este script NUNCA altera `orchestrator.py` nem
nenhum codigo medido -- so ENVOLVE a mesma chamada que o runbook ja usa,
desacoplada da sessao que a lancou:

  - `start`  -- lanca um processo supervisor DETACHED (setsid no
    controle real/Linux; equivalente mais proximo disponivel no
    Windows, usado so nesta rodada de teste local), que primeiro
    adquire um lock exclusivo e nao-bloqueante (flock no Linux real;
    `msvcrt.locking` no Windows de teste -- mesma semantica de exclusao
    mutua livre de corrida entre checar e escrever, nunca um
    "ler PID e comparar"), grava o PID proprio, e so entao executa
    `python3 orchestrator.py <args>` como filho, com stdout/stderr
    redirecionados pro arquivo de log. O comando `start` que o operador
    roda retorna em segundos (nao fica bloqueado esperando o
    orquestrador terminar) -- a sessao SSH pode cair depois disso sem
    afetar o supervisor, que nao e filho dela.
  - `status` -- vivo ou nao (PID real verificado, nao so o arquivo
    presente), ultima linha do log, e progresso real (le
    `manifest_partial.json` do `--out` da chamada, se existir --
    `orchestrator.py` ja grava isso incrementalmente por celula,
    Decisao 133 item 3; nunca inventado aqui).
  - `tail`  -- ultimas N linhas do log real.
  - `stop`  -- SIGTERM gracioso, so quando pedido explicitamente
    (nunca automatico, nunca chamado por `start`/`status`/`tail`).

Uma segunda instancia tentando `start` com o MESMO `--name` enquanto a
primeira ainda detem o lock recebe erro e sai sem tocar em nada --
nunca duas instancias do mesmo orquestrador correndo em paralelo contra
o mesmo estado.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

_ORCHESTRATOR_PATH = Path(__file__).resolve().parent / "orchestrator.py"
_SUPERVISE_START_TIMEOUT_S = 15.0
_SUPERVISE_POLL_INTERVAL_S = 0.05


def _state_dir(explicit: str | None) -> Path:
    if explicit:
        d = Path(explicit)
    else:
        d = Path(__file__).resolve().parent / "launcher_state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _paths(state_dir: Path, name: str) -> dict[str, Path]:
    return {
        "lock": state_dir / f"{name}.lock",
        "pid": state_dir / f"{name}.pid",
        "child_pid": state_dir / f"{name}.child.pid",
        "log": state_dir / f"{name}.log",
        "cmd": state_dir / f"{name}.cmd.json",
        "result": state_dir / f"{name}.start_result",
    }


def _is_alive(pid: int) -> bool:
    if sys.platform.startswith("win"):
        completed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True,
        )
        return str(pid) in completed.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _extract_out_dir(orchestrator_args: list[str]) -> str | None:
    for i, arg in enumerate(orchestrator_args):
        if arg == "--out" and i + 1 < len(orchestrator_args):
            return orchestrator_args[i + 1]
        if arg.startswith("--out="):
            return arg.split("=", 1)[1]
    return None


def _tail_lines(path: Path, n: int) -> list[str]:
    if not path.is_file():
        return []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    return [line.rstrip("\n") for line in lines[-n:]]


def _read_manifest_progress(orchestrator_args: list[str]) -> dict | None:
    out_dir = _extract_out_dir(orchestrator_args)
    if not out_dir:
        return None
    partial = Path(out_dir) / "manifest_partial.json"
    manifest = Path(out_dir) / "manifest.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return {"source": "manifest.json", "complete": True, **data}
    if partial.is_file():
        try:
            data = json.loads(partial.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return {"source": "manifest_partial.json", **data}
    return None


def cmd_start(args: argparse.Namespace) -> int:
    state_dir = _state_dir(args.state_dir)
    paths = _paths(state_dir, args.name)

    existing_pid = _read_pid(paths["pid"])
    if existing_pid is not None and _is_alive(existing_pid):
        print(json.dumps({
            "started": False,
            "reason": "already_running",
            "existing_pid": existing_pid,
        }))
        return 1

    for p in (paths["result"],):
        if p.exists():
            p.unlink()

    paths["cmd"].write_text(json.dumps({
        "orchestrator_args": args.orchestrator_args,
        "started_at_requested_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }), encoding="utf-8")

    supervise_cmd = [
        sys.executable, str(Path(__file__).resolve()),
        "--state-dir", str(state_dir), "--name", args.name,
        "_supervise", "--",
    ] + args.orchestrator_args

    popen_kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if sys.platform.startswith("win"):
        popen_kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        # setsid real: nova sessao, sem terminal de controle -- sobrevive
        # ao fim da sessao SSH que lancou o `start`.
        popen_kwargs["start_new_session"] = True

    subprocess.Popen(supervise_cmd, **popen_kwargs)

    deadline = time.monotonic() + _SUPERVISE_START_TIMEOUT_S
    while time.monotonic() < deadline:
        if paths["result"].exists():
            break
        time.sleep(_SUPERVISE_POLL_INTERVAL_S)

    if not paths["result"].exists():
        print(json.dumps({
            "started": False,
            "reason": "supervise_did_not_report_in_time",
        }))
        return 1

    result = paths["result"].read_text(encoding="utf-8").strip()
    if result == "lock_busy":
        print(json.dumps({"started": False, "reason": "lock_busy"}))
        return 1
    if result == "started":
        pid = _read_pid(paths["pid"])
        print(json.dumps({"started": True, "pid": pid, "log": str(paths["log"])}))
        return 0
    print(json.dumps({"started": False, "reason": f"unexpected_result:{result}"}))
    return 1


def _read_pid(pid_path: Path) -> int | None:
    if not pid_path.is_file():
        return None
    try:
        return int(pid_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def cmd_status(args: argparse.Namespace) -> int:
    state_dir = _state_dir(args.state_dir)
    paths = _paths(state_dir, args.name)
    pid = _read_pid(paths["pid"])
    alive = pid is not None and _is_alive(pid)
    cmd_info = {}
    if paths["cmd"].is_file():
        try:
            cmd_info = json.loads(paths["cmd"].read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            cmd_info = {}
    progress = _read_manifest_progress(cmd_info.get("orchestrator_args", []))
    tail = _tail_lines(paths["log"], 1)
    child_pid = _read_pid(paths["child_pid"])
    status = {
        "alive": alive,
        "pid": pid,
        "child_pid": child_pid,
        "last_log_line": tail[0] if tail else None,
        "progress": progress,
    }
    print(json.dumps(status, indent=2))
    return 0 if alive else 3


def cmd_tail(args: argparse.Namespace) -> int:
    state_dir = _state_dir(args.state_dir)
    paths = _paths(state_dir, args.name)
    for line in _tail_lines(paths["log"], args.n):
        print(line)
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    state_dir = _state_dir(args.state_dir)
    paths = _paths(state_dir, args.name)
    pid = _read_pid(paths["pid"])
    if pid is None or not _is_alive(pid):
        print(json.dumps({"stopped": False, "reason": "not_running"}))
        return 1
    if not args.confirm:
        print(json.dumps({
            "stopped": False,
            "reason": "confirmation_required",
            "hint": "rode de novo com --confirm pra mandar SIGTERM de verdade",
        }))
        return 2
    if sys.platform.startswith("win"):
        # Windows nao tem SIGTERM real (nenhum console-control-handler
        # registrado nem aqui nem em orchestrator.py pra reagir a um
        # fechamento "gentil") -- `/F` e o equivalente pratico disponivel
        # nesta rodada de teste local. No controle real (Linux), o ramo
        # abaixo manda SIGTERM de verdade via `os.kill`.
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    else:
        os.kill(pid, signal.SIGTERM)
    print(json.dumps({"stopped": True, "pid": pid, "signal": "SIGTERM"}))
    return 0


def _acquire_lock(lock_path: Path):
    """Devolve um file handle com lock exclusivo e nao-bloqueante, ou
    None se outra instancia ja o detem. No controle real (Linux):
    `fcntl.flock`. Nesta rodada de teste local (Windows, sem `fcntl`):
    `msvcrt.locking` sobre o mesmo arquivo -- mesma semantica de
    exclusao mutua atomica, nunca um fallback de "ler PID e comparar"
    que teria corrida entre checar e escrever."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    f = open(lock_path, "a+b")
    if sys.platform.startswith("win"):
        import msvcrt
        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            f.close()
            return None
    else:
        import fcntl
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            f.close()
            return None
    return f


def cmd_supervise(args: argparse.Namespace) -> int:
    """Subcomando interno, nunca chamado diretamente pelo operador --
    so pelo `start` acima, ja detached. Adquire o lock, grava o PID
    proprio, executa `orchestrator.py` como filho com stdout/stderr no
    log, espera terminar, e so entao libera o lock (ao sair)."""
    state_dir = _state_dir(args.state_dir)
    paths = _paths(state_dir, args.name)

    lock_handle = _acquire_lock(paths["lock"])
    if lock_handle is None:
        paths["result"].write_text("lock_busy", encoding="utf-8")
        return 1

    paths["pid"].write_text(str(os.getpid()), encoding="utf-8")
    paths["result"].write_text("started", encoding="utf-8")

    orchestrator_cmd = [sys.executable, str(_ORCHESTRATOR_PATH)] + args.orchestrator_args
    with open(paths["log"], "ab") as logf:
        logf.write(
            f"\n=== launch_persistent: iniciando {' '.join(orchestrator_cmd)} "
            f"em {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} ===\n".encode("utf-8")
        )
        logf.flush()
        proc = subprocess.Popen(
            orchestrator_cmd, stdout=logf, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, cwd=str(_ORCHESTRATOR_PATH.parent),
        )
        paths["child_pid"].write_text(str(proc.pid), encoding="utf-8")
        returncode = proc.wait()
        if paths["child_pid"].is_file():
            paths["child_pid"].unlink()
        logf.write(
            f"=== launch_persistent: orchestrator.py saiu com codigo {returncode} "
            f"em {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} ===\n".encode("utf-8")
        )

    if paths["pid"].is_file():
        paths["pid"].unlink()
    lock_handle.close()
    return returncode


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="launch_persistent.py",
        description="Lanca/supervisiona orchestrator.py desacoplado da sessao SSH que o invocou.",
    )
    ap.add_argument("--state-dir", default=None,
                     help="Diretorio de estado (lock/pid/log). Default: launcher_state/ ao lado deste script.")
    ap.add_argument("--name", default="pilot",
                     help="Identificador da instancia (permite estados paralelos p/ propositos distintos). Default: pilot.")
    sub = ap.add_subparsers(dest="subcommand", required=True)

    p_start = sub.add_parser("start", help="Lanca orchestrator.py detached.")
    p_start.add_argument("orchestrator_args", nargs=argparse.REMAINDER,
                          help="Argumentos passados direto pro orchestrator.py (use -- antes deles).")
    p_start.set_defaults(func=cmd_start)

    p_status = sub.add_parser("status", help="Reporta vivo/morto, PID e progresso real.")
    p_status.set_defaults(func=cmd_status)

    p_tail = sub.add_parser("tail", help="Ultimas N linhas do log real.")
    p_tail.add_argument("-n", type=int, default=20)
    p_tail.set_defaults(func=cmd_tail)

    p_stop = sub.add_parser("stop", help="SIGTERM gracioso -- so com --confirm.")
    p_stop.add_argument("--confirm", action="store_true")
    p_stop.set_defaults(func=cmd_stop)

    p_supervise = sub.add_parser("_supervise", help=argparse.SUPPRESS)
    p_supervise.add_argument("orchestrator_args", nargs=argparse.REMAINDER)
    p_supervise.set_defaults(func=cmd_supervise)

    return ap


def main() -> int:
    ap = build_parser()
    args = ap.parse_args()
    orchestrator_args = getattr(args, "orchestrator_args", None)
    if orchestrator_args and orchestrator_args[0] == "--":
        args.orchestrator_args = orchestrator_args[1:]
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
