#!/usr/bin/env python3
"""Desvio documentado do commit congelado 4a1210ea (Decisao 137, Plano
B de retomada) -- ver docstring de `resume_plan.py` nesta mesma pasta.

Consome o plano de `resume_plan.py` e executa, para CADA celula
pendente, uma chamada separada e NAO MODIFICADA de `orchestrator.
run_pilot` (o mesmo modulo congelado, importado direto, nunca uma
copia/fork dele) com `routes=[rota]`/`profiles=[perfil]` e
`n_per_profile`/`n_warmup_per_profile` iguais exatamente ao numero de
execucoes/aquecimentos FALTANTES daquela celula (nunca o total da
janela -- isso reexecutaria o que ja foi persistido). Cada chamada
escreve num subdiretorio proprio de `window2_out/_por_celula/`
(numeracao 1..N sempre local a essa chamada) e e depois RENOMEADA pro
numero real que faltava (`missing_runs[i]`) dentro de `window2_out/
runs_raw/` -- nunca sobrescreve nem duplica o que a janela 1 ja tem
(essa fica INTOCADA, em `out_dir_janela1`, nunca mexida por este
script). As capturas dedicadas ja feitas na janela 1 sao puladas
(`skip_dedicated_captures`); as faltantes rodam normalmente dentro da
propria chamada por celula.

So e invocado de verdade (contra hosts reais) se o Plano B disparar.
Testado aqui SOMENTE com `--mode simulate` (LocalExecutor, nenhuma
rede, nenhuma AWS) -- ver Decisao 137 para o registro do teste local."""
import argparse
import json
import shutil
import sys
from pathlib import Path

_SCRIPTS_DIR = str(Path(__file__).resolve().parents[1] / "scripts")
sys.path.insert(0, _SCRIPTS_DIR)
import orchestrator as orch  # noqa: E402 -- modulo congelado, importado sem modificacao
import resume_plan  # noqa: E402


def run_resume(plan: dict, window2_out: Path, executor_factory, seed: int, cost_tracker=None) -> dict:
    window2_out.mkdir(parents=True, exist_ok=True)
    runs_raw_dir = window2_out / "runs_raw"
    runs_raw_dir.mkdir(parents=True, exist_ok=True)
    capturas_dir = window2_out / "criterio1_capturas"
    capturas_dir.mkdir(parents=True, exist_ok=True)
    per_cell_root = window2_out / "_por_celula"
    per_cell_root.mkdir(parents=True, exist_ok=True)

    cell_reports = []
    for cell in plan["pending_cells"]:
        profile, route = cell["profile"], cell["route"]
        missing_runs = cell["missing_runs"]
        missing_warmups = cell["missing_warmups"]
        need_capture = cell["missing_capture"]
        cell_out = per_cell_root / f"{profile}__{route}"
        executor = executor_factory()
        manifest = orch.run_pilot(
            executor, seed, cell_out,
            n_per_profile=len(missing_runs) if missing_runs else 0,
            n_warmup_per_profile=len(missing_warmups) if missing_warmups else 0,
            routes=[route], profiles=[profile],
            skip_dedicated_captures=not need_capture,
            cost_tracker=cost_tracker,
        )
        # Renumera as execucoes/aquecimentos LOCAIS desta celula (1..N)
        # pro numero real que faltava na janela 1 -- nunca sobrescreve
        # nada em runs_raw_dir se o arquivo de destino ja existir
        # (fail-closed: um nome repetido aqui e sempre bug deste
        # script, nunca um estado aceitavel).
        cell_runs_raw = cell_out / "runs_raw"
        renamed = []
        for local_n, real_n in enumerate(missing_runs, start=1):
            src = cell_runs_raw / f"{profile}__{route}__run{local_n:02d}.json"
            dst = runs_raw_dir / f"{profile}__{route}__run{real_n:02d}.json"
            if dst.exists():
                raise RuntimeError(f"resume_runner: {dst} ja existe -- nunca sobrescrever (bug real)")
            shutil.copy2(src, dst)
            renamed.append({"from": src.name, "to": dst.name})
        for local_n, real_n in enumerate(missing_warmups, start=1):
            src = cell_runs_raw / f"{profile}__{route}__run00_warmup{local_n}.json"
            dst = runs_raw_dir / f"{profile}__{route}__run00_warmup{real_n}.json"
            if dst.exists():
                raise RuntimeError(f"resume_runner: {dst} ja existe -- nunca sobrescrever (bug real)")
            shutil.copy2(src, dst)
            renamed.append({"from": src.name, "to": dst.name})
        if need_capture:
            src_cap = cell_out / "criterio1_capturas" / f"{profile}_{route}.log"
            dst_cap = capturas_dir / f"{profile}_{route}.log"
            if dst_cap.exists():
                raise RuntimeError(f"resume_runner: {dst_cap} ja existe -- nunca sobrescrever (bug real)")
            shutil.copy2(src_cap, dst_cap)
        cell_reports.append({
            "profile": profile, "route": route,
            "executed_runs": len(missing_runs), "executed_warmups": len(missing_warmups),
            "executed_capture": need_capture, "renamed": renamed,
            "cost_stop": manifest.get("cost_stop"),
        })
        if manifest.get("cost_stop"):
            # Decisao 137: mesmo padrao do cost_stop original -- celula
            # em andamento termina, mas nenhuma celula POSTERIOR desta
            # retomada e iniciada. Reporta exatamente onde parou.
            break

    return {"window2_out": str(window2_out), "cells": cell_reports,
            "all_pending_done": len(cell_reports) == len(plan["pending_cells"])
            and not any(c["cost_stop"] for c in cell_reports)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window1-out", required=True)
    ap.add_argument("--window2-out", required=True)
    ap.add_argument("--routes", nargs="+", required=True)
    ap.add_argument("--profiles", nargs="+", default=["classico", "pqc", "hibrido-v8", "hibrido-and"])
    ap.add_argument("--n-per-profile", type=int, required=True)
    ap.add_argument("--n-warmup-per-profile", type=int, default=0)
    ap.add_argument("--seed", type=int, default=20261107)
    ap.add_argument("--mode", choices=["simulate"], default="simulate",
                     help="Decisao 137: este runner so foi testado em --mode simulate (LocalExecutor, "
                          "sem rede/AWS). O modo ssh real so e ligado se/quando o Plano B disparar de "
                          "verdade, fora deste teste local.")
    args = ap.parse_args()

    plan = resume_plan.scan_partial_window(
        Path(args.window1_out), args.profiles, args.routes, args.n_per_profile, args.n_warmup_per_profile)
    if plan["complete"]:
        print(json.dumps({"note": "janela 1 ja completa -- nada a retomar", "plan": plan},
                          indent=2, ensure_ascii=False))
        return

    def executor_factory():
        return orch.LocalExecutor()

    result = run_resume(plan, Path(args.window2_out), executor_factory, args.seed)
    print(json.dumps({"plan": plan, "result": result}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
