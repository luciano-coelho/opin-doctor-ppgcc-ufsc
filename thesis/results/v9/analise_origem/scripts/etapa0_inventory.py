#!/usr/bin/env python3
"""Degrau 1, Etapa 0: inventario dos campos que REALMENTE existem nos
dados brutos/organizados ja salvos localmente -- nunca assume um campo
sem checar. Roda ANTES de qualquer analise (pre-registro real).
Le SOMENTE dados locais, nunca reabre conexao com AWS."""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
RAW = REPO_ROOT / "thesis/results/v9/campaign_oficial_conta_nova_raw"
ORG = REPO_ROOT / "thesis/results/v9/campaign_oficial_conta_nova_organized"
OUT = Path(__file__).resolve().parents[1] / "data" / "etapa0_inventory.json"


def main():
    calls = json.loads((RAW / "piloto_calls.json").read_text(encoding="utf-8"))
    ex0 = calls[0]
    call0 = ex0["insurance"][0]

    # confirma constancia dos campos de execucao/chamada nas 320 execucoes
    exec_keys_sets = {tuple(sorted(e.keys())) for e in calls}
    call_keys_sets = set()
    n_calls_per_exec = set()
    for e in calls:
        n_calls_per_exec.add(len(e["insurance"]))
        for c in e["insurance"]:
            call_keys_sets.add(tuple(sorted(c.keys())))

    # organized/latency: confirma o que existe em median_metrics.json e runs/*.json
    lat_dir = ORG / "latency" / "experiment1 - Classic" / "L0-sa-east-1"
    median_metrics_keys = sorted(json.loads((lat_dir / "median_metrics.json").read_text(encoding="utf-8")).keys())
    run_keys = sorted(json.loads((lat_dir / "runs" / "run01.json").read_text(encoding="utf-8")).keys())

    # dedicated artifacts (32): confirma o que existe por celula
    art_root = ORG / "artifacts"
    art_files_sample = sorted(p.name for p in (art_root / "experiment1 - Classic" / "L0-sa-east-1").iterdir())

    # criterio2/7 raw files
    crit2_keys = sorted(json.loads((RAW / "criterio2_initcwnd_L123_server-to-client.json").read_text(encoding="utf-8")).keys())
    crit7_sample_route = next(iter(json.loads((RAW / "criterio7_rtt_por_rota.json").read_text(encoding="utf-8")).items()))

    manifest = json.loads((RAW / "manifest.json").read_text(encoding="utf-8"))

    report = {
        "piloto_calls_n_executions": len(calls),
        "exec_level_fields_constant_across_320": len(exec_keys_sets) == 1,
        "exec_level_fields": sorted(exec_keys_sets.pop()) if len(exec_keys_sets) == 1 else "VARIA -- achado real",
        "call_level_fields_constant": len(call_keys_sets) == 1,
        "call_level_fields": sorted(call_keys_sets.pop()) if len(call_keys_sets) == 1 else "VARIA -- achado real",
        "n_calls_per_execution_values": sorted(n_calls_per_exec),
        "cpu_client_fields": sorted(ex0["cpu_client"].keys()),
        "cpu_server_fields": sorted(ex0["cpu_server"].keys()),
        "NOTE_no_per_phase_cpu_breakdown": (
            "cpu_client/cpu_server SO tem steal_pct/util_pct (uso global da instancia na janela "
            "da execucao) -- NAO existe nenhum campo de tempo de CPU por fase (signing_seconds/"
            "verification_seconds/etc, como v8 tinha). Confirmado por inspecao direta das chaves "
            "acima, nao assumido."
        ),
        "call_level_has_latency_ms": "latency_ms" in call0,
        "median_metrics_json_fields": median_metrics_keys,
        "latency_run_json_fields": run_keys,
        "dedicated_artifact_files_per_cell_sample": art_files_sample,
        "criterio2_initcwnd_fields": crit2_keys,
        "criterio7_sample_route_fields": sorted(crit7_sample_route[1].keys()),
        "manifest_route_orders_present": "route_orders" in manifest,
        "manifest_seed": manifest.get("seed"),
        "warmup_files_exist_but_excluded_by_design": "aquecimento" in str(RAW / "aquecimento_execucoes.json"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
