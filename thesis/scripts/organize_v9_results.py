"""
Organizador + consolidador de resultados do v9 (piloto ou oficial),
no layout pedido pelo Luciano (Decisao 134): results/v9_pilot/ (piloto)
ou results/v9/ (oficial), com artifacts/, size/ e latency/, cada um
com experiment1 - Classic / experiment2 - PQC / experiment3 - Hybrid /
experiment4 - Control, uma pasta por rota (sem "/"), runs/runNN.json
(latency tambem run00_warmup.json), mais median_metrics.json e
MEDIAN_REPORT.md derivados por rota.

NUNCA move/altera os dados brutos de origem -- so LE deles (copia/
deriva pro layout novo). Reexecutavel sem efeito colateral destrutivo
(idempotente: sobrescreve o destino, nunca o que ja existia antes de
rodar). `--expected-runs-per-cell` falha alto se o numero encontrado
divergir do esperado (2 no piloto, 10 na oficial).

Usage:
  python thesis/scripts/organize_v9_results.py \
    --calls-json <piloto_calls.json> \
    --criterio6-json <criterio6_execucoes.json> \
    --aquecimento-json <aquecimento_execucoes.json> \
    --manifest-json <manifest.json> \
    --capturas-dir <criterio1_capturas/> \
    --out-dir thesis/results/v9_pilot \
    --expected-runs-per-cell 2 \
    --label-piloto  # marca o CONSOLIDATED_REPORT.md como piloto, nao resultado final
"""
import argparse
import json
import shutil
import statistics
import sys
from collections import defaultdict
from pathlib import Path

PROFILE_TO_EXPERIMENT = {
    "classico": "experiment1 - Classic",
    "pqc": "experiment2 - PQC",
    "hibrido-and": "experiment3 - Hybrid",
    "hibrido-v8": "experiment4 - Control",
}
CONTROL_PROFILE = "hibrido-v8"


def _t_fluxo(entry):
    from datetime import datetime
    t0 = datetime.fromisoformat(entry["start_utc"])
    t1 = datetime.fromisoformat(entry["end_utc"])
    return (t1 - t0).total_seconds()


def _total_bytes(entry):
    total = 0
    for c in entry.get("insurance", []) + entry.get("person", []):
        total += c.get("total_bytes", 0) or 0
    return total


def _write_cell(base_dir: Path, entries: list, warmups: list, expected_runs: int, kind: str):
    """kind: 'size' ou 'latency'. Escreve runs/runNN.json (+ run00_warmup.json
    pra latency) e deriva median_metrics.json/MEDIAN_REPORT.md."""
    runs_dir = base_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    entries_sorted = sorted(entries, key=lambda e: e["run"])
    if len(entries_sorted) != expected_runs:
        raise RuntimeError(
            f"{base_dir}: {len(entries_sorted)} execucoes encontradas, "
            f"esperado {expected_runs} (--expected-runs-per-cell)")
    for e in entries_sorted:
        (runs_dir / f"run{int(e['run']):02d}.json").write_text(
            json.dumps(e, indent=2, ensure_ascii=False), encoding="utf-8")
    if kind == "latency" and warmups:
        # Decisao 134: run00_warmup.json = o ULTIMO aquecimento (mais
        # "aquecido", mais representativo do estado estavel) -- nao
        # os 5, so 1 arquivo, nome exato pedido pelo Luciano.
        last_warmup = sorted(warmups, key=lambda w: w["warmup"])[-1]
        (runs_dir / "run00_warmup.json").write_text(
            json.dumps(last_warmup, indent=2, ensure_ascii=False), encoding="utf-8")

    if kind == "size":
        values = [_total_bytes(e) for e in entries_sorted]
        metric_name = "total_bytes"
    else:
        values = [_t_fluxo(e) for e in entries_sorted]
        metric_name = "t_fluxo_seconds"
    median_metrics = {
        "metric": metric_name, "n": len(values),
        "median": statistics.median(values),
        "mean": statistics.mean(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values), "max": max(values),
        "values": values,
    }
    (base_dir / "median_metrics.json").write_text(
        json.dumps(median_metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    (base_dir / "MEDIAN_REPORT.md").write_text(
        f"# {metric_name} -- {base_dir.name}\n\n"
        f"N={median_metrics['n']}  \n"
        f"Mediana: {median_metrics['median']:.3f}  \n"
        f"Media: {median_metrics['mean']:.3f}  \n"
        f"Desvio padrao: {median_metrics['stdev']:.3f}  \n"
        f"Min/Max: {median_metrics['min']:.3f} / {median_metrics['max']:.3f}  \n",
        encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calls-json", required=True)
    ap.add_argument("--criterio6-json", required=True)
    ap.add_argument("--aquecimento-json")
    ap.add_argument("--manifest-json", required=True)
    ap.add_argument("--capturas-dir")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--expected-runs-per-cell", type=int, required=True)
    ap.add_argument("--label-piloto", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    calls = json.loads(Path(args.calls_json).read_text(encoding="utf-8"))
    criterio6 = json.loads(Path(args.criterio6_json).read_text(encoding="utf-8"))
    aquecimentos = json.loads(Path(args.aquecimento_json).read_text(encoding="utf-8")) if args.aquecimento_json else []
    manifest = json.loads(Path(args.manifest_json).read_text(encoding="utf-8"))

    by_cell = defaultdict(list)
    for e in calls:
        by_cell[(e["profile"], e["route"])].append(e)
    warmups_by_cell = defaultdict(list)
    for w in aquecimentos:
        warmups_by_cell[(w["profile"], w["route"])].append(w)

    provenance = []
    divergences = []

    for (profile, route), entries in by_cell.items():
        experiment = PROFILE_TO_EXPERIMENT[profile]
        route_name = route.replace("/", "_")
        for kind in ("size", "latency"):
            base = out_dir / kind / experiment / route_name
            _write_cell(base, entries, warmups_by_cell.get((profile, route), []),
                        args.expected_runs_per_cell, kind)
            provenance.append({
                "destino": str(base), "origem": args.calls_json,
                "filtro": f"profile=={profile!r} route=={route!r}",
            })

    # artifacts/ -- capturas dedicadas (Decisao 134, item 1): uma
    # subpasta por perfil/rota, copiando os arquivos reais (nunca
    # movendo a origem).
    if args.capturas_dir:
        capturas_dir = Path(args.capturas_dir)
        artifacts_dir = out_dir / "artifacts"
        for profile, route in by_cell:
            experiment = PROFILE_TO_EXPERIMENT[profile]
            route_name = route.replace("/", "_")
            dest = artifacts_dir / experiment / route_name
            dest.mkdir(parents=True, exist_ok=True)
            found_any = False
            for pattern in (f"{profile}_{route}*", f"{profile}_{route.replace('/', '_')}*"):
                for f in capturas_dir.glob(pattern):
                    shutil.copy2(f, dest / f.name)
                    found_any = True
            if not found_any:
                divergences.append(
                    f"artifacts: nenhuma captura dedicada encontrada pra profile={profile} route={route}")
            provenance.append({
                "destino": str(dest), "origem": str(capturas_dir),
                "filtro": f"arquivos com prefixo {profile}_{route}",
            })

    # Resultado dos 6 criterios da autorizacao condicional -- so
    # RELATADO aqui (nao decide nada sobre eles).
    reference = None
    criterios_report = {}
    by_profile_shape = {}
    for profile in PROFILE_TO_EXPERIMENT:
        total = sum(len(c.get("insurance", [])) + len(c.get("person", [])) for c in by_cell_values(by_cell, profile))
        by_profile_shape[profile] = total
    valores = set(by_profile_shape.values())
    criterios_report["criterio_3_contagens_iguais_entre_perfis"] = {
        "ok": len(valores) == 1, "por_perfil": by_profile_shape,
    }
    criterios_report["criterio_1_total_execucoes"] = {
        "ok": manifest["total_execucoes"] == manifest["expected_total"],
        "total_execucoes": manifest["total_execucoes"], "expected_total": manifest["expected_total"],
    }
    criterios_report["criterio_1_capturas_dedicadas"] = {
        "ok": not manifest.get("capturas_dedicadas_falhas"),
        "feitas": manifest.get("capturas_dedicadas_feitas"), "falhas": manifest.get("capturas_dedicadas_falhas"),
    }
    expected_dual = {"classico": False, "pqc": False, "hibrido-v8": False, "hibrido-and": True}
    tls_divergencias = [
        row for row in criterio6
        if row.get("dualAuthenticated") != expected_dual.get(row["profile"])
    ]
    criterios_report["criterio_1_tls_dual_assertado"] = {
        "ok": not tls_divergencias, "divergencias": tls_divergencias,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    report_data = {
        "gerado_em_utc": manifest.get("window_end_utc"),
        "piloto": args.label_piloto,
        "expected_runs_per_cell": args.expected_runs_per_cell,
        "total_execucoes": manifest["total_execucoes"],
        "total_capturas_dedicadas": manifest.get("capturas_dedicadas_feitas"),
        "criterios": criterios_report,
        "divergencias_encontradas": divergences,
        "provenance": provenance,
    }
    (out_dir / "report_data_v9.json").write_text(
        json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")

    piloto_warning = (
        "\n> **ESTE E O PILOTO** -- 2 execucoes por celula, so pra validar o pipeline "
        "de ponta a ponta e calibrar a oficial. As medianas aqui NUNCA sao um resultado "
        "cientifico (N=2 por celula nao sustenta nenhuma conclusao estatistica) -- "
        "a oficial (N=10/celula) e quem produz o dado real.\n"
        if args.label_piloto else ""
    )
    consolidated_md = (
        f"# Relatório consolidado v9{' (PILOTO)' if args.label_piloto else ''}\n"
        f"{piloto_warning}\n"
        f"Gerado em: {report_data['gerado_em_utc']}\n\n"
        f"## Critérios (relatados, não decididos aqui)\n\n"
        f"```json\n{json.dumps(criterios_report, indent=2, ensure_ascii=False)}\n```\n\n"
        f"## Divergências encontradas no pós-processamento\n\n"
        + ("\n".join(f"- {d}" for d in divergences) if divergences else "Nenhuma.")
        + "\n"
    )
    (out_dir / "CONSOLIDATED_REPORT.md").write_text(consolidated_md, encoding="utf-8")

    print(json.dumps({"ok": True, "out_dir": str(out_dir), "divergencias": divergences,
                       "criterios": criterios_report}, indent=2, ensure_ascii=False))


def by_cell_values(by_cell, profile):
    for (p, r), entries in by_cell.items():
        if p == profile:
            yield from entries


if __name__ == "__main__":
    main()
