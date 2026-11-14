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

Decisao 157 (item 4, pedido do Luciano): este script, sozinho, nao
sabia distinguir "destino vazio, primeira rodada" de "destino ja tem
uma campanha anterior" -- reexecutar apontando pra um --out-dir ja
populado silenciosamente mistura dados de duas campanhas diferentes
(mesmo mecanismo de risco que a Decisao 156/auditoria independente
achou em thesis/results/v9/ como um todo, agora fechado aqui tambem
no nivel deste script). `_refuse_if_populated_without_flag` abaixo
recusa (RuntimeError, antes de escrever qualquer arquivo) sempre que
--out-dir ja existir e tiver qualquer conteudo, a menos que
--allow-overwrite-populated seja passado explicitamente -- e quando
passado, isso fica registrado em report_data_v9.json
(`overwrite_populated_dest_authorized: true`), nunca silencioso.

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
from collections import Counter, defaultdict
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


def _refuse_if_populated_without_flag(out_dir: Path, allow_overwrite_populated: bool) -> None:
    """Decisao 157: --out-dir ja existente e com qualquer conteudo e
    tratado como "campanha anterior ja esta ai" -- recusa alto, antes
    de tocar em qualquer arquivo, a menos que o chamador passe
    --allow-overwrite-populated explicitamente. Diretorio inexistente
    ou existente-mas-vazio (ex.: criado por mkdir -p sem nada dentro)
    e o caminho feliz, nunca recusado."""
    if not out_dir.exists():
        return
    if any(out_dir.iterdir()):
        if not allow_overwrite_populated:
            raise RuntimeError(
                f"--out-dir {out_dir} ja existe e NAO esta vazio -- "
                "provavel campanha anterior. Recusando misturar dados sem "
                "autorizacao explicita. Passe --allow-overwrite-populated "
                "se a intencao e mesmo sobrescrever (fica registrado em "
                "report_data_v9.json)."
            )


_VALID_REAL_MODES = {"ssh"}  # unico mode real que orchestrator.py produz hoje (_EXECUTOR_CLASS_TO_MODE)


def _refuse_simulated_data_outside_piloto(manifest: dict, label_piloto: bool) -> None:
    """Decisao 161 (item 3) + Decisao 167 (pedido do Luciano, "torne
    fail-closed"): orchestrator.py grava "mode"/"executor_class" em
    todo manifesto -- "mode"=="simulate" significa `LocalExecutor`,
    que NUNCA toca rede/infra real, so fabrica um resultado plausivel.
    Dados simulados sao uteis pra exercitar o pipeline localmente
    (por isso continuam aceitos quando --label-piloto esta presente --
    o relatorio ja sai marcado "(PILOTO)", ninguem le como resultado
    oficial), mas NUNCA podem entrar numa arvore organizada SEM esse
    rotulo (o caso "oficial" por definicao, `--out-dir thesis/results/
    v9` sem --label-piloto) -- recusa alto, antes de qualquer escrita,
    igual a `_refuse_if_populated_without_flag`.

    Decisao 167 amplia a trava: antes, so "mode"=="simulate" era
    checado -- um manifesto SEM a chave "mode" (ausente/vazia/valor
    desconhecido, por exemplo um orchestrator.py antigo ou corrompido)
    passava direto, sem ser nem "simulate" nem um modo real reconhecido.
    Agora o fail-closed e por ALLOWLIST (`_VALID_REAL_MODES`, so "ssh"
    hoje): "simulate" mantem a excecao de --label-piloto de sempre;
    qualquer outro valor que NAO esteja na allowlist (ausente, "",
    "unknown", typo, etc.) e recusado SEMPRE, independente de
    --label-piloto -- nunca ha um "piloto com modo desconhecido"
    legitimo, so "piloto com dado simulado conhecido" ou "campanha real
    com SSHExecutor"."""
    mode = manifest.get("mode")
    if mode == "simulate":
        if not label_piloto:
            raise RuntimeError(
                f"manifest.json tem mode={mode!r} (executor_class={manifest.get('executor_class')!r}) -- "
                "dados SIMULADOS (LocalExecutor, nunca tocou rede/infra real) nunca podem entrar numa "
                "arvore organizada sem --label-piloto. Passe --label-piloto se a intencao e mesmo "
                "organizar dado simulado pra teste local do pipeline, ou confirme que o executor "
                "usado foi SSHExecutor (mode=\"ssh\") antes de tentar de novo."
            )
        return
    if mode not in _VALID_REAL_MODES:
        raise RuntimeError(
            f"manifest.json tem mode={mode!r} (executor_class={manifest.get('executor_class')!r}) -- "
            f"nao e um modo real aceito ({sorted(_VALID_REAL_MODES)!r}) nem \"simulate\". Fail-closed: "
            "ausente, vazio ou desconhecido NUNCA autoriza organizar dados, nem como campanha oficial "
            "nem como piloto (--label-piloto so cobre o caso \"simulate\" conhecido, nunca um modo "
            "nao reconhecido). Confirme que orchestrator.py gravou \"mode\" corretamente (SSHExecutor "
            "-> \"ssh\") antes de tentar de novo."
        )


def _write_retries_report(out_dir: Path, calls: list, aquecimentos: list) -> dict:
    """Decisao 158 (item 6a): "arquivo de repetições", somado por
    célula (profile, route) -- deriva de `network_transport_retries`
    (ja presente em cada execucao/aquecimento real, gravado por
    orchestrator.py a partir do que latency_automation.py classificou
    como "network_transport"). Nunca inclui falha_closed (essa aborta
    a execucao, nunca chega a um `run*.json` persistido) nem retries de
    transporte SSH (Decisao 139, campo separado `retry_failures`)."""
    by_cell = defaultdict(list)
    for e in list(calls) + list(aquecimentos):
        for r in e.get("network_transport_retries", []):
            by_cell[(e["profile"], e["route"])].append(r)
    por_celula = {
        f"{profile}/{route}": {"n_retries": len(entries), "entries": entries}
        for (profile, route), entries in sorted(by_cell.items())
    }
    report = {"total_retries": sum(v["n_retries"] for v in por_celula.values()), "por_celula": por_celula}
    (out_dir / "retries_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def _write_handshake_bytes_alert(out_dir: Path, calls: list, aquecimentos: list) -> dict:
    """Decisao 160 (item 1, pedido do Luciano): alerta -- NUNCA
    gate, NUNCA descarta nada -- pra qualquer conexao cliente-gateway
    cujo handshakeBytesIn/Out (log do PROPRIO gateway,
    `handshake_bytes_per_connection`, ja presente em cada execucao/
    aquecimento real gravado por orchestrator.py) divirja do valor
    ESTABELECIDO (o modal -- o par (in,out) mais comum) da MESMA
    celula (profile, route). A conexao divergente continua contando
    normalmente em todo o resto do pipeline (OPINsize, criterios,
    median_metrics) -- isto so REGISTRA o desvio, informativo,
    jamais excluindo nem recalculando nada em cima dele."""
    by_cell = defaultdict(list)
    for e in list(calls) + list(aquecimentos):
        key = (e["profile"], e["route"])
        run_label = e.get("run", e.get("warmup"))
        for conn in e.get("handshake_bytes_per_connection", []):
            by_cell[key].append({"run": run_label, "in": conn["in"], "out": conn["out"]})

    por_celula = {}
    for (profile, route), conns in sorted(by_cell.items()):
        pairs = Counter((c["in"], c["out"]) for c in conns)
        expected_in, expected_out = pairs.most_common(1)[0][0] if pairs else (None, None)
        divergentes = [c for c in conns if (c["in"], c["out"]) != (expected_in, expected_out)]
        por_celula[f"{profile}/{route}"] = {
            "n_conexoes": len(conns),
            "valor_esperado": {"in": expected_in, "out": expected_out},
            "n_divergentes": len(divergentes),
            "divergentes": divergentes,
        }
    report = {
        "total_conexoes": sum(v["n_conexoes"] for v in por_celula.values()),
        "total_divergentes": sum(v["n_divergentes"] for v in por_celula.values()),
        "por_celula": por_celula,
    }
    (out_dir / "handshake_bytes_alert.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


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
    ap.add_argument("--allow-overwrite-populated", action="store_true",
                     help="Decisao 157: autoriza explicitamente escrever sobre um --out-dir "
                          "ja populado (fica registrado em report_data_v9.json). Sem esta "
                          "flag, um --out-dir nao-vazio e recusado antes de qualquer escrita.")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    _refuse_if_populated_without_flag(out_dir, args.allow_overwrite_populated)
    calls = json.loads(Path(args.calls_json).read_text(encoding="utf-8"))
    criterio6 = json.loads(Path(args.criterio6_json).read_text(encoding="utf-8"))
    aquecimentos = json.loads(Path(args.aquecimento_json).read_text(encoding="utf-8")) if args.aquecimento_json else []
    manifest = json.loads(Path(args.manifest_json).read_text(encoding="utf-8"))
    _refuse_simulated_data_outside_piloto(manifest, args.label_piloto)

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
    retries_report = _write_retries_report(out_dir, calls, aquecimentos)
    handshake_bytes_alert = _write_handshake_bytes_alert(out_dir, calls, aquecimentos)
    report_data = {
        "gerado_em_utc": manifest.get("window_end_utc"),
        "piloto": args.label_piloto,
        "expected_runs_per_cell": args.expected_runs_per_cell,
        "total_execucoes": manifest["total_execucoes"],
        "total_capturas_dedicadas": manifest.get("capturas_dedicadas_feitas"),
        "criterios": criterios_report,
        "divergencias_encontradas": divergences,
        "provenance": provenance,
        "overwrite_populated_dest_authorized": args.allow_overwrite_populated,
        "network_transport_retries_total": retries_report["total_retries"],
        "handshake_bytes_divergentes_total": handshake_bytes_alert["total_divergentes"],
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
