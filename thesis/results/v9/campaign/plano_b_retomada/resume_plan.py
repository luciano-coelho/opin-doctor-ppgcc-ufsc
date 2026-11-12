#!/usr/bin/env python3
"""Desvio documentado do commit congelado 4a1210ea (Decisao 137, Plano
B de retomada) -- NAO faz parte do codigo da campanha oficial em si
(orchestrator.py/preflight.py/etc. permanecem intocados, byte a byte
identicos ao commit congelado, ver verificacao de sha256 da Decisao
136/relatorio parcial). Este arquivo e `resume_runner.py` so existem
para o caso do teto de custo do processo em execucao (US$35) disparar
antes da janela terminar -- Plano B pre-autorizado pelo Luciano: ao
disparar, retomar SO as celulas ainda nao concluidas, numa segunda
janela, nunca repetir o que ja foi persistido.

So LEITURA do `out_dir` de uma janela (completa ou parcial, real ou de
teste local) -- nunca escreve nada aqui. Computa, por (perfil, rota):
quantas execucoes medidas (`run{NN}.json`, N de 1 a `n_per_profile`)
ja existem em `runs_raw/`, quantos aquecimentos (`run00_warmupN.json`)
e se a captura dedicada (`criterio1_capturas/{perfil}_{rota}.log`) ja
existe. Produz um plano (JSON) com exatamente o que falta -- nunca
decide por conta propria se o Plano B deve ou nao ser executado
(isso e decisao do chamador/operador, ja pre-autorizada por Luciano
para o caso real)."""
import argparse
import json
import re
import sys
from pathlib import Path

_RUN_RE = re.compile(r"^(?P<profile>.+)__(?P<route>.+)__run(?P<run>\d\d)(?:_warmup(?P<warmup>\d+))?\.json$")


def scan_partial_window(out_dir: Path, profiles: list[str], routes: list[str],
                         n_per_profile: int, n_warmup_per_profile: int) -> dict:
    runs_raw_dir = out_dir / "runs_raw"
    capturas_dir = out_dir / "criterio1_capturas"

    done_runs = {}      # (profile, route) -> set of run numbers (1..n_per_profile) present
    done_warmups = {}   # (profile, route) -> set of warmup numbers present
    done_captures = set()  # (profile, route) with a capture log present

    if runs_raw_dir.is_dir():
        for fp in runs_raw_dir.iterdir():
            m = _RUN_RE.match(fp.name)
            if not m:
                continue
            profile, route = m.group("profile"), m.group("route")
            if m.group("warmup") is not None:
                done_warmups.setdefault((profile, route), set()).add(int(m.group("warmup")))
            elif int(m.group("run")) > 0:
                done_runs.setdefault((profile, route), set()).add(int(m.group("run")))

    if capturas_dir.is_dir():
        for profile in profiles:
            for route in routes:
                if (capturas_dir / f"{profile}_{route}.log").is_file():
                    done_captures.add((profile, route))

    pending = []
    for route in routes:
        for profile in profiles:
            key = (profile, route)
            have_runs = done_runs.get(key, set())
            have_warm = done_warmups.get(key, set())
            missing_runs = sorted(set(range(1, n_per_profile + 1)) - have_runs)
            missing_warm = sorted(set(range(1, n_warmup_per_profile + 1)) - have_warm)
            missing_capture = key not in done_captures
            if missing_runs or missing_warm or missing_capture:
                pending.append({
                    "profile": profile, "route": route,
                    "done_runs": sorted(have_runs), "missing_runs": missing_runs,
                    "done_warmups": sorted(have_warm), "missing_warmups": missing_warm,
                    "missing_capture": missing_capture,
                })

    total_expected_runs = len(profiles) * len(routes) * n_per_profile
    total_done_runs = sum(len(v) for v in done_runs.values())
    total_expected_captures = len(profiles) * len(routes)
    total_done_captures = len(done_captures)

    return {
        "out_dir": str(out_dir),
        "n_per_profile": n_per_profile, "n_warmup_per_profile": n_warmup_per_profile,
        "profiles": profiles, "routes": routes,
        "total_expected_runs": total_expected_runs, "total_done_runs": total_done_runs,
        "total_expected_captures": total_expected_captures, "total_done_captures": total_done_captures,
        "complete": total_done_runs == total_expected_runs and total_done_captures == total_expected_captures,
        "pending_cells": pending,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="out_dir da janela 1 (parcial ou completa)")
    ap.add_argument("--profiles", nargs="+", default=["classico", "pqc", "hibrido-v8", "hibrido-and"])
    ap.add_argument("--routes", nargs="+", required=True)
    ap.add_argument("--n-per-profile", type=int, required=True)
    ap.add_argument("--n-warmup-per-profile", type=int, default=0)
    args = ap.parse_args()
    plan = scan_partial_window(Path(args.out), args.profiles, args.routes,
                                args.n_per_profile, args.n_warmup_per_profile)
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    sys.exit(0 if plan["complete"] else 2)


if __name__ == "__main__":
    main()
