#!/usr/bin/env python3
"""Degrau 2, Rodada 3 -- porta de seguranca (item 4 da instrucao): assim
que o primeiro run01.json real da primeira celula aparecer em disco,
confere os campos exigidos pelas 5 hipoteses (t_fluxo_fino_seconds +
phase_accounting com os 6 componentes + insurance[].latency_ms +
start_utc/end_utc). Se faltar algo, aborta a campanha via
launch_persistent.py stop --confirm e grava gate_result.json com
ok=false. Se tudo presente, grava gate_result.json com ok=true e sai --
nunca interfere de novo depois disso."""
import json
import subprocess
import sys
import time
from pathlib import Path

RUNS_RAW_DIR = Path(sys.argv[1])
LAUNCHER_NAME = sys.argv[2]
GATE_RESULT_PATH = Path(sys.argv[3])
TIMEOUT_SECONDS = int(sys.argv[4]) if len(sys.argv) > 4 else 1800

REQUIRED_PHASE_KEYS = [
    "http_calls_seconds", "signing_seconds", "verification_seconds",
    "explicit_wait_seconds", "setup_seconds", "residual_seconds",
]


def check_record(d: dict) -> list:
    problems = []
    if d.get("t_fluxo_fino_seconds") is None:
        problems.append("t_fluxo_fino_seconds ausente ou nulo")
    pa = d.get("phase_accounting")
    if not isinstance(pa, dict) or not pa:
        problems.append("phase_accounting ausente ou vazio")
    else:
        for k in REQUIRED_PHASE_KEYS:
            if pa.get(k) is None:
                problems.append(f"phase_accounting.{k} ausente ou nulo")
    if not d.get("start_utc") or not d.get("end_utc"):
        problems.append("start_utc/end_utc ausente")
    insurance = d.get("insurance", [])
    if not insurance:
        problems.append("insurance vazio")
    elif not all("latency_ms" in c for c in insurance):
        problems.append("algum item de insurance sem latency_ms")
    return problems


def find_first_run01():
    if not RUNS_RAW_DIR.exists():
        return None
    candidates = sorted(RUNS_RAW_DIR.glob("*__run01.json"))
    return candidates[0] if candidates else None


deadline = time.time() + TIMEOUT_SECONDS
found = None
while time.time() < deadline:
    found = find_first_run01()
    if found is not None:
        break
    time.sleep(5)

if found is None:
    result = {"ok": False, "reason": f"nenhum run01.json apareceu em {TIMEOUT_SECONDS}s", "file": None}
else:
    time.sleep(1)
    d = json.loads(found.read_text(encoding="utf-8"))
    problems = check_record(d)
    result = {
        "ok": not problems,
        "file": str(found),
        "problems": problems,
        "t_fluxo_fino_seconds": d.get("t_fluxo_fino_seconds"),
        "phase_accounting_keys": sorted((d.get("phase_accounting") or {}).keys()),
    }

GATE_RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

if not result["ok"]:
    # Precisa rodar com cwd igual ao de launch_persistent.py (mesma
    # convencao usada pra iniciar a campanha) -- este script e invocado
    # ja de dentro desse diretorio.
    subprocess.run(["python3", "launch_persistent.py", "--name", LAUNCHER_NAME, "stop", "--confirm"])
    print(f"GATE FALHOU: {result}", file=sys.stderr)
    sys.exit(1)

print(f"GATE OK: {result}")
sys.exit(0)
