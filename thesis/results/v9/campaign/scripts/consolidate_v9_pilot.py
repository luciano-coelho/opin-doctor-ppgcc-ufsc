#!/usr/bin/env python3
"""v9, piloto: consolidacao final -- Decisao 75, item 3/4 (pedido do
Luciano: "organize depois em piloto/dados_oficiais/ no padrao v8").

Le o diretorio JA coletado e verificado por `collect_artifacts.py`
(`manifest.json`, `piloto_combined.log`, `piloto_calls.json`,
`criterio6_execucoes.json`, `criterio1_capturas/`, e os arquivos
dedicados de criterio 2/3/7 QUANDO existirem -- nunca obrigatorios,
ver DECISIONS.md: a producao desses 3 nunca foi fiada neste piloto),
roda `evaluate_criteria.py` sobre eles (reaproveitado direto, nunca
reimplementado -- a MESMA lista de 7 chamadas que `evaluate_criteria.
main()` ja faz), e escreve o par fonte+derivado no MESMO padrao
ESTRUTURAL que a v8 ja usa (`consolidate_v8.py`: um JSON fonte +
um Markdown derivado, num diretorio final limpo, nunca misturado com
o scratch de campanha) -- adaptado, nunca os MESMOS calculos: a v8 e
uma campanha continua de semanas/3 regioes com estatistica
distribucional (mediana/CI bootstrap entre MUITAS execucoes); o
piloto v9 e um sanity-check de passagem/reprovacao UNICO, ja resolvido
por completo pelos limiares pre-registrados de `evaluate_criteria.py`
-- nao ha nenhuma estatistica adicional genuina a herdar dali, so a
FORMA (fonte json + relatorio md, diretorio final separado do raw).

Escreve em `--out-dir` (convencao: `thesis/results/v9/piloto/
dados_oficiais/<run_label>/`):
  - `raw/` -- copia intacta de `--collected-dir` (nunca movida -- a
    copia que `collect_artifacts.py` ja verificou por sha256
    permanece intocada como evidencia primaria)
  - `criteria_evaluation.json` -- saida crua dos 7 criterios
  - `RELATORIO_PILOTO.md` -- derivado, legivel por humano
"""
import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "integration"))
import evaluate_criteria as ec  # noqa: E402


def run_evaluate_criteria(collected_dir: Path) -> list[dict]:
    """Mesma lista, MESMA ordem, que `evaluate_criteria.main()` ja
    monta -- nunca reimplementada aqui, so reaproveitada em processo
    (nunca via subprocess+parse de stdout, que seria mais fragil)."""
    run_t6_log = collected_dir / "piloto_combined.log"
    if not run_t6_log.is_file():
        raise RuntimeError(f"run_evaluate_criteria: {run_t6_log} nao encontrado -- coleta incompleta?")
    log_text = run_t6_log.read_text(encoding="utf-8", errors="replace")
    calls_json_path = collected_dir / "piloto_calls.json"
    execucoes = json.loads(calls_json_path.read_text(encoding="utf-8")) if calls_json_path.is_file() else None
    aws_dir = str(collected_dir)
    return [
        ec.criterion_1_message_sizes(log_text, aws_dir),
        ec.criterion_2_initcwnd(aws_dir),
        ec.criterion_3_distant_route(aws_dir),
        ec.criterion_4_counts(execucoes, log_text),
        ec.criterion_5_zero_errors(log_text),
        ec.criterion_6_instrumentation(log_text, aws_dir),
        ec.criterion_7_latency_sanity(aws_dir),
    ]


def render_markdown_report(criteria_results: list[dict], manifest: dict, run_label: str) -> str:
    lines = [f"# Piloto v9 -- relatorio consolidado ({run_label})", "",
             f"Gerado em: {datetime.now(timezone.utc).isoformat()}", ""]
    if manifest:
        lines.append(f"Execucoes: {manifest.get('total_execucoes')}/{manifest.get('expected_total')} -- "
                      f"capturas: {manifest.get('total_capturas')} -- smoke: {manifest.get('smoke')}")
        if "bytes_diagnostic_needs_decision" in manifest:
            lines.append(f"Diagnostico de bytes (nunca o gate oficial): "
                          f"needs_decision={manifest['bytes_diagnostic_needs_decision']}")
        lines.append("")
    lines += ["| Criterio | Nome | Resultado |", "|---|---|---|"]
    for r in criteria_results:
        lines.append(f"| {r['criterion']} | {r['name']} | {'PASS' if r['pass'] else 'FAIL'} |")
    lines.append("")
    all_pass = all(r["pass"] for r in criteria_results)
    lines.append(f"**Resultado geral: {'PASS' if all_pass else 'FAIL'}**")
    failing = [r for r in criteria_results if not r["pass"]]
    if failing:
        lines.append("")
        lines.append("Criterios reprovados/sem evidencia:")
        for r in failing:
            lines.append(f"- Criterio {r['criterion']} ({r['name']}): {r.get('note', 'sem nota')}")
    return "\n".join(lines) + "\n"


def consolidate(collected_dir: Path, out_dir: Path, run_label: str) -> dict:
    manifest_path = collected_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    criteria_results = run_evaluate_criteria(collected_dir)

    out_dir.mkdir(parents=True, exist_ok=True)
    dest_raw = out_dir / "raw"
    if dest_raw.exists():
        shutil.rmtree(dest_raw)
    shutil.copytree(collected_dir, dest_raw)

    (out_dir / "criteria_evaluation.json").write_text(
        json.dumps(criteria_results, indent=2, ensure_ascii=False), encoding="utf-8")
    report_md = render_markdown_report(criteria_results, manifest, run_label)
    (out_dir / "RELATORIO_PILOTO.md").write_text(report_md, encoding="utf-8")

    all_pass = all(r["pass"] for r in criteria_results)
    return {"run_label": run_label, "out_dir": str(out_dir),
            "all_criteria_pass": all_pass, "criteria_results": criteria_results}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collected-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--run-label", required=True)
    args = ap.parse_args()
    result = consolidate(Path(args.collected_dir), Path(args.out_dir), args.run_label)
    print(json.dumps({"run_label": result["run_label"], "out_dir": result["out_dir"],
                       "all_criteria_pass": result["all_criteria_pass"]}, indent=2, ensure_ascii=False))
    if not result["all_criteria_pass"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
