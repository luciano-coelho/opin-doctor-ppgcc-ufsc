"""
Measures T_fluxo (wall-clock, monotonic) for opin_flow.py's full flow
(run_insurance_flow + run_person_flow combined -- same scope
total_bytes_exchanged already uses in the size batch) across N=10 runs
per (CRYPTO_PROFILE, latency_ms) scenario.

T_fluxo = t_fim - t_início, both from time.monotonic() (never time.time()/
wall-clock, which can jump under NTP adjustment) -- t_início immediately
before run_insurance_flow()'s first call, t_fim immediately after
run_person_flow()'s last call, MINUS any wasted_seconds opin_flow.py's
timing instrumentation recorded for a discarded PAR-TTL or login-race
sub-attempt within this same run (see wait_for_authorization_code()'s and
create_and_authorize_consent()'s `timing` parameter, thesis/results/v5/
latency/DECISIONS.md). A discarded attempt is measurement-environment
noise, not real flow cost -- the same principle already applied to bytes
(a discarded PAR call was never added to `calls` either).

Containers are reused across all 10 runs of one scenario -- this script
does NOT recreate them between runs, only when the caller switches
CRYPTO_PROFILE between scenarios/profiles (unlike the size batch, which
had no such constraint since it wasn't measuring time).

One extra "warmup" run is always taken first, right after this script
starts against a (possibly freshly reconciled) profile, unconditionally,
and reported separately in run00_warmup.json -- never counted among the
10, never fed into any statistic. This is a pre-committed methodology
choice, not a post-hoc outlier judgment call: deciding after seeing the
data whether run 1 "looks like" a cold start would risk exactly the kind
of data-fits-the-hypothesis cherry-picking this batch's own methodology
rules out.

No outlier removal of any kind on the 10 counted runs -- median/min/max/
mean/stdev computed over all 10 raw values always; retries and any other
anomaly are recorded as structured data (never removed from the
statistics) and narrated in report.md.

File convention: run*.json and median_metrics.json are raw experimental
data only, no interpretive prose -- report.md is entirely derived from
them and can be regenerated from the JSONs alone, without rerunning
anything (see write_report()).

Usage:
  CRYPTO_PROFILE=classic|pqc|hybrid python latency_automation.py <latency_ms> \
      [--runs N] [--experiment-number N] [--results-version vN]

Assumes the backend stack (auth/mtls/mongo_seed/mockapi) is ALREADY
running under the matching CRYPTO_PROFILE -- this script only drives the
client side, exactly like opin_flow.py itself.
"""
import argparse
import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import opin_flow as of

BASE_DIR = of.BASE_DIR


# Whole-run retry, mirroring median_automation.py's RUN_RETRY_LIMIT
# (Decision 5, thesis/results/v5/DECISIONS.md): the rare reentrant
# auth<->mock_mtls introspection race recurred in the latency batch
# (Decision 9, thesis/results/v5/latency/DECISIONS.md) at a different call
# site (InsurerAdapter.getConsent() during interaction/login rendering,
# not just the /token exchange) -- same underlying mechanism, confirmed by
# the identical stack trace/error. Unlike the PAR-TTL/login-race/
# interaction-session-lost retries (which exclude only the wasted sub-
# interval from an otherwise-successful run), a whole-run failure here
# happens before anything worth keeping exists, so the entire attempt
# (time and data) is discarded and retried from scratch -- there is no
# partial T_fluxo to salvage.
RUN_RETRY_LIMIT = 2


def run_once_timed_with_retry(crypto_profile: str, label: str, whole_run_retries: list) -> dict:
    last_error = None
    for attempt in range(1, RUN_RETRY_LIMIT + 1):
        try:
            return run_once_timed(crypto_profile)
        except Exception as e:
            last_error = e
            if attempt < RUN_RETRY_LIMIT:
                print(f"  [{label}] attempt {attempt} failed ({type(e).__name__}: {e}) -- discarding whole "
                      "attempt and retrying from scratch (see thesis/results/v5/latency/DECISIONS.md, Decision 9)")
                whole_run_retries.append({"run": label, "attempt": attempt, "error": f"{type(e).__name__}: {e}"})
    raise SystemExit(
        f"{label} failed on both attempts -- stopping (not retrying further; this is no longer the "
        f"known rare race, treat as a new failure). Last error: {last_error}"
    )


def run_once_timed(crypto_profile: str) -> dict:
    timing = {"wasted_seconds": 0.0, "retries": []}
    t_start = time.monotonic()
    insurance_calls = of.run_insurance_flow(crypto_profile, timing=timing)
    person_calls = of.run_person_flow(crypto_profile, timing=timing)
    t_end = time.monotonic()

    naive_elapsed_seconds = t_end - t_start
    t_fluxo_seconds = naive_elapsed_seconds - timing["wasted_seconds"]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "t_fluxo_seconds": round(t_fluxo_seconds, 6),
        "naive_elapsed_seconds": round(naive_elapsed_seconds, 6),
        "wasted_seconds": round(timing["wasted_seconds"], 6),
        "retries": timing["retries"],
        "call_count": len(insurance_calls) + len(person_calls),
    }


def summarize(runs: list[dict]) -> dict:
    values = [r["t_fluxo_seconds"] for r in runs]
    med = statistics.median(values)
    return {
        "run_count": len(runs),
        "individual_values_seconds": values,
        "sorted_values_seconds": sorted(values),
        "median_seconds": med,
        "min_seconds": min(values),
        "max_seconds": max(values),
        "mean_seconds": round(statistics.mean(values), 6),
        "stdev_seconds": round(statistics.stdev(values), 6) if len(values) > 1 else 0.0,
        "spread_pct": round((max(values) - min(values)) / min(values) * 100, 4) if min(values) else 0.0,
        "absolute_deviation_from_median": [round(abs(v - med), 6) for v in values],
        "runs_with_retries": [
            {"run": i + 1, "retries": r["retries"]} for i, r in enumerate(runs) if r["retries"]
        ],
    }


def write_report(summary: dict, warmup: dict, crypto_profile: str, latency_ms: int, path: Path):
    lines = []
    lines.append(f"# Latency Report ({crypto_profile}, {latency_ms}ms, {summary['run_count']} runs)")
    lines.append("")
    lines.append(f"Experimento (perfil): **{crypto_profile}**")
    lines.append(f"Latência aplicada (cenário): **{latency_ms}ms**")
    lines.append("")
    lines.append(
        f"Warmup (execução 0, descartada, não entra em nenhuma estatística): "
        f"T_fluxo = {warmup['t_fluxo_seconds']:.4f}s"
        + (f", com retry(s): {warmup['retries']}" if warmup["retries"] else ", sem retry.")
    )
    lines.append("")
    lines.append("## As 10 execuções -- valores individuais (ordem coletada)")
    lines.append("")
    lines.append("| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |")
    lines.append("|---|---|---|---|")
    for i, (v, dev) in enumerate(zip(summary["individual_values_seconds"], summary["absolute_deviation_from_median"]), start=1):
        has_retry = any(rr["run"] == i for rr in summary["runs_with_retries"])
        lines.append(f"| {i} | {v:.6f} | {dev:.6f} | {'SIM' if has_retry else 'não'} |")
    lines.append("")
    lines.append("## Valores ordenados (ordem crescente)")
    lines.append("")
    lines.append(", ".join(f"{v:.6f}" for v in summary["sorted_values_seconds"]))
    lines.append("")
    lines.append("## Mediana e dispersão")
    lines.append("")
    lines.append(f"- Mediana: **{summary['median_seconds']:.6f}s**")
    lines.append(f"- Mínimo: {summary['min_seconds']:.6f}s")
    lines.append(f"- Máximo: {summary['max_seconds']:.6f}s")
    lines.append(f"- Média: {summary['mean_seconds']:.6f}s")
    lines.append(f"- Desvio padrão (amostral): {summary['stdev_seconds']:.6f}s")
    lines.append(f"- Spread (min/max): {summary['spread_pct']:.4f}%")
    lines.append("")
    lines.append("## Anomalias")
    lines.append("")
    if summary["runs_with_retries"]:
        lines.append(
            f"{len(summary['runs_with_retries'])} de {summary['run_count']} execuções precisaram de retry "
            "(tempo do retry excluído do T_fluxo medido -- ver thesis/results/v5/latency/DECISIONS.md):"
        )
        lines.append("")
        for entry in summary["runs_with_retries"]:
            lines.append(f"- Execução {entry['run']}: {entry['retries']}")
    else:
        lines.append("Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.")
    lines.append("")
    whole_run_retries = summary.get("whole_run_retries") or []
    if whole_run_retries:
        lines.append(
            f"{len(whole_run_retries)} execução(ões) inteira(s) descartada(s) e refeita(s) do zero "
            "(race reentrante auth<->mock_mtls, Decision 9 -- não é a mesma coisa que o retry parcial acima):"
        )
        lines.append("")
        for entry in whole_run_retries:
            lines.append(f"- {entry['run']}, tentativa {entry['attempt']}: {entry['error']}")
        lines.append("")
    lines.append("## Observações")
    lines.append("")
    lines.append(
        f"Spread de {summary['spread_pct']:.4f}% entre as 10 execuções. "
        + ("Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana." if summary["spread_pct"] < 20 else "**Spread elevado -- investigar antes de aceitar este cenário como concluído.**")
    )
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("latency_ms", type=int, choices=of.ALLOWED_LATENCY_MS)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--experiment-number", default=os.environ.get("EXPERIMENT_NUMBER", "1"))
    parser.add_argument("--results-version", default=os.environ.get("RESULTS_VERSION", "v5"))
    args = parser.parse_args()

    crypto_profile = os.environ.get("CRYPTO_PROFILE", "classic")
    print(
        f"CRYPTO_PROFILE={crypto_profile}  latency={args.latency_ms}ms  runs={args.runs}  "
        f"RESULTS_VERSION={args.results_version}  EXPERIMENT_NUMBER={args.experiment_number}"
    )

    results_root = BASE_DIR / "thesis" / "results" / args.results_version / "latency"
    experiment_dir = None
    for candidate in results_root.glob(f"experiment{args.experiment_number}*"):
        experiment_dir = candidate
        break
    if experiment_dir is None:
        raise SystemExit(
            f"No {results_root}/experiment{args.experiment_number}* folder found -- create it first."
        )
    output_dir = experiment_dir / f"{args.latency_ms}ms"
    runs_dir = output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    of.set_latency(args.latency_ms)

    whole_run_retries = []

    print("\n=== Warmup run (discarded, not counted) ===")
    warmup = run_once_timed_with_retry(crypto_profile, "warmup", whole_run_retries)
    (runs_dir / "run00_warmup.json").write_text(
        json.dumps(warmup, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  T_fluxo={warmup['t_fluxo_seconds']:.4f}s  retries={warmup['retries']}")

    runs = []
    for i in range(1, args.runs + 1):
        print(f"\n=== Run {i}/{args.runs} ===")
        r = run_once_timed_with_retry(crypto_profile, f"run{i:02d}", whole_run_retries)
        runs.append(r)
        (runs_dir / f"run{i:02d}.json").write_text(
            json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"  T_fluxo={r['t_fluxo_seconds']:.4f}s  retries={r['retries']}")

    summary = summarize(runs)
    summary["crypto_profile"] = crypto_profile
    summary["latency_scenario_ms"] = args.latency_ms
    summary["warmup"] = warmup
    summary["whole_run_retries"] = whole_run_retries
    (output_dir / "median_metrics.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_report(summary, warmup, crypto_profile, args.latency_ms, output_dir / "report.md")

    print(f"\nWrote {output_dir / 'median_metrics.json'}")
    print(f"Wrote {output_dir / 'report.md'}")
    print(f"\n=== Summary ===")
    print(f"  median_seconds={summary['median_seconds']:.6f}  min={summary['min_seconds']:.6f}  "
          f"max={summary['max_seconds']:.6f}  spread_pct={summary['spread_pct']:.4f}%")
    if summary["runs_with_retries"]:
        print(f"  {len(summary['runs_with_retries'])} run(s) needed a retry: {summary['runs_with_retries']}")


if __name__ == "__main__":
    main()
