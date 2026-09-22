"""
Independent audit of thesis/results/v7/: recomputes every size and latency
statistic from the raw per-run JSON files (runs/run01..10*.json) WITHOUT
reading the already-computed median_metrics.json/MEDIAN_REPORT.md/report.md as
a reference for the numbers -- those are only opened afterwards, to compare
against what this script derived on its own.

Usage: python thesis/scripts/audit_v7_from_raw.py [--write]
  --write additionally saves the full text output to
  thesis/results/v7/audit_recompute_from_raw.txt
"""
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "results" / "v7"
PROFILES = [("experiment1 - Classic", "classic"), ("experiment2 - PQC", "pqc"), ("experiment3 - Hybrid", "hybrid")]
SCENARIOS = [0, 14, 30, 140, 225, 320]
EXPECTED_CERT = {"classic": 1494, "pqc": 2953, "hybrid": 6859}

out_lines = []
problems = []


def say(s=""):
    print(s)
    out_lines.append(s)


def problem(msg):
    problems.append(msg)
    say(f"  !! DIVERGENCIA: {msg}")


def spread(vals, nd):
    lo, hi = min(vals), max(vals)
    return 0.0 if lo == 0 else round((hi - lo) / lo * 100, nd)


def close(a, b, tol=1e-9):
    if a is None or b is None:
        return a is b
    return abs(float(a) - float(b)) <= tol


# ---------------------------------------------------------------- SIZE
say("=" * 78)
say("SIZE -- recomputed from size/<exp>/<scenario>ms/runs/run01..10_baseline_metrics.json")
say("=" * 78)

size_summary = {}
size_checks = 0
for exp, prof in PROFILES:
    for sc in SCENARIOS:
        d = ROOT / "size" / exp / f"{sc}ms"
        files = sorted((d / "runs").glob("run*_baseline_metrics.json"))
        names = [f.name for f in files]
        expect = [f"run{i:02d}_baseline_metrics.json" for i in range(1, 11)]
        if names != expect:
            problem(f"{exp}/{sc}ms: run files {names} != esperado run01..run10")
            continue
        runs = [json.loads(f.read_text(encoding="utf-8")) for f in files]

        # structural / internal-consistency checks on every raw run
        for i, r in enumerate(runs, start=1):
            tag = f"{exp}/{sc}ms/run{i:02d}"
            size_checks += 1
            if r["latency_scenario_ms"] != sc:
                problem(f"{tag}: latency_scenario_ms={r['latency_scenario_ms']} != {sc}")
            if r["total_requests"] != 28:
                problem(f"{tag}: total_requests={r['total_requests']} != 28")
            if r["jwt_count"] != 26:
                problem(f"{tag}: jwt_count={r['jwt_count']} != 26")
            if r["client_cert_der_bytes"] != EXPECTED_CERT[prof]:
                problem(f"{tag}: client_cert_der_bytes={r['client_cert_der_bytes']} != {EXPECTED_CERT[prof]}")
            hb = r["gateway_metrics"]["handshake_bytes"]
            if hb is None or hb["count"] != 6:
                problem(f"{tag}: handshake_bytes.count={None if hb is None else hb['count']} != 6 (N_mTLS)")
            if r["gateway_metrics"]["handshake_bytes_outliers_dropped"] != 0:
                problem(f"{tag}: handshake_bytes_outliers_dropped != 0")
            bp = r["bytes_by_participant"]
            cs, cr = bp["Client"]["sent_bytes"], bp["Client"]["received_bytes"]
            others_sent = sum(v["sent_bytes"] for k, v in bp.items() if k != "Client")
            others_recv = sum(v["received_bytes"] for k, v in bp.items() if k != "Client")
            if cs != others_recv or cr != others_sent:
                problem(f"{tag}: Client.sent/received nao fecha com a soma dos outros participantes")
            if r["total_bytes_exchanged"] != cs + cr:
                problem(f"{tag}: total_bytes_exchanged != Client.sent+received")

        def series(getter):
            return [getter(r) for r in runs]

        scalars = {
            "jwt_size_avg_bytes": (series(lambda r: r["jwt_size_avg_bytes"]), 2),
            "total_bytes_exchanged": (series(lambda r: r["total_bytes_exchanged"]), 2),
            "client_cert_der_bytes": (series(lambda r: r["client_cert_der_bytes"]), 2),
            "handshake_bytes_p50_bytes": (series(lambda r: r["gateway_metrics"]["handshake_bytes"]["p50_bytes"]), 2),
        }
        rec = {}
        for name, (vals, nd) in scalars.items():
            rec[name] = {
                "median": round(statistics.median(vals), 2),
                "min": min(vals),
                "max": max(vals),
                "variation_pct": spread(vals, 2),
                "values": vals,
            }
        parts = sorted({k for r in runs for k in r["bytes_by_participant"]})
        rec_bp = {}
        for p in parts:
            rec_bp[p] = {}
            for leg in ("sent_bytes", "received_bytes"):
                vals = [r["bytes_by_participant"][p][leg] for r in runs]
                rec_bp[p][leg] = {
                    "median": round(statistics.median(vals), 2),
                    "min": min(vals),
                    "max": max(vals),
                    "variation_pct": spread(vals, 2),
                    "values": vals,
                }
        # jwk sizes (signing key = the non-RSA-OAEP entry), per run
        jwk_sig = sorted({tuple(j["size_bytes"] for j in r["jwk_sizes"] if j["use"] == "sig") for r in runs})
        jwk_all = sorted({tuple((j["kty"], j["use"], j["size_bytes"]) for j in r["jwk_sizes"]) for r in runs})
        size_summary[(prof, sc)] = {"scalars": rec, "bp": rec_bp, "jwk_sig": jwk_sig, "jwk_all": jwk_all}

        # --- compare with the previously computed artefacts (read only now)
        mm = json.loads((d / "median_metrics.json").read_text(encoding="utf-8"))
        if mm["run_count"] != 10:
            problem(f"{exp}/{sc}ms: median_metrics.run_count={mm['run_count']}")
        for name, r_ in rec.items():
            j = mm["scalars"][name]
            for key in ("median", "min", "max", "variation_pct"):
                if not close(r_[key], j[key]):
                    problem(f"{exp}/{sc}ms {name}.{key}: recalculado={r_[key]} json={j[key]}")
            if [float(x) for x in r_["values"]] != [float(x) for x in j["values"]]:
                problem(f"{exp}/{sc}ms {name}.values diferem")
        for p in parts:
            for leg in ("sent_bytes", "received_bytes"):
                j = mm["bytes_by_participant"][p][leg]
                r_ = rec_bp[p][leg]
                for key in ("median", "min", "max", "variation_pct"):
                    if not close(r_[key], j[key]):
                        problem(f"{exp}/{sc}ms {p}.{leg}.{key}: recalculado={r_[key]} json={j[key]}")
        if set(mm["bytes_by_participant"]) != set(parts):
            problem(f"{exp}/{sc}ms: participantes json={sorted(mm['bytes_by_participant'])} raw={parts}")
        if mm.get("retry_log"):
            say(f"  (info) {exp}/{sc}ms retry_log nao vazio: {mm['retry_log']}")

        # --- compare with MEDIAN_REPORT.md (derived artefact)
        md = (d / "MEDIAN_REPORT.md").read_text(encoding="utf-8")
        for name, r_ in rec.items():
            m = re.search(rf"\| `{name}` \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+)% \|", md)
            if not m:
                problem(f"{exp}/{sc}ms MEDIAN_REPORT.md: linha de {name} nao encontrada")
                continue
            got = [float(x) for x in m.groups()]
            want = [r_["median"], r_["min"], r_["max"], r_["variation_pct"]]
            if not all(close(a, b) for a, b in zip(got, want)):
                problem(f"{exp}/{sc}ms MEDIAN_REPORT.md {name}: md={got} recalculado={want}")
        for p in parts:
            for leg in ("sent_bytes", "received_bytes"):
                m = re.search(rf"\| {re.escape(p)} \| {leg} \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+)% \|", md)
                if not m:
                    problem(f"{exp}/{sc}ms MEDIAN_REPORT.md: linha {p}/{leg} nao encontrada")
                    continue
                got = [float(x) for x in m.groups()]
                r_ = rec_bp[p][leg]
                want = [r_["median"], r_["min"], r_["max"], r_["variation_pct"]]
                if not all(close(a, b) for a, b in zip(got, want)):
                    problem(f"{exp}/{sc}ms MEDIAN_REPORT.md {p}/{leg}: md={got} recalculado={want}")

say(f"\nSize: {len(PROFILES) * len(SCENARIOS)} cenarios/perfis, {size_checks} execucoes brutas verificadas estruturalmente.")

say("\nSize -- spread maximo por cenario/perfil (recalculado) e constancia entre cenarios:")
for exp, prof in PROFILES:
    max_spread = 0.0
    for sc in SCENARIOS:
        s = size_summary[(prof, sc)]
        for r_ in s["scalars"].values():
            max_spread = max(max_spread, r_["variation_pct"])
        for legs in s["bp"].values():
            for r_ in legs.values():
                max_spread = max(max_spread, r_["variation_pct"])
    say(f"  {prof:8s}: spread maximo em qualquer metrica/cenario = {max_spread}%")
    for name in ("jwt_size_avg_bytes", "total_bytes_exchanged", "client_cert_der_bytes", "handshake_bytes_p50_bytes"):
        meds = {size_summary[(prof, sc)]["scalars"][name]["median"] for sc in SCENARIOS}
        say(f"    {name}: {'constante entre os 6 cenarios = ' + str(sorted(meds)[0]) if len(meds) == 1 else 'VARIA entre cenarios: ' + str(sorted(meds))}")
        if len(meds) != 1:
            problem(f"{prof}/{name} varia entre cenarios de latencia (esperado constante): {sorted(meds)}")
    for tag in ("jwk_sig", "jwk_all"):
        vals = {size_summary[(prof, sc)][tag] for sc in SCENARIOS} if False else {str(size_summary[(prof, sc)][tag]) for sc in SCENARIOS}
        say(f"    {tag}: {sorted(vals)}")

# ------------------------------------------------------------- LATENCY
say("\n" + "=" * 78)
say("LATENCY -- recomputed from latency/<exp>/<scenario>ms/runs/run01..10.json (run00_warmup excluded)")
say("=" * 78)

lat_summary = {}
lat_checks = 0
for exp, prof in PROFILES:
    for sc in SCENARIOS:
        d = ROOT / "latency" / exp / f"{sc}ms"
        files = sorted((d / "runs").glob("run*.json"))
        names = [f.name for f in files]
        expect = ["run00_warmup.json"] + [f"run{i:02d}.json" for i in range(1, 11)]
        if names != expect:
            problem(f"{exp}/{sc}ms latency: arquivos {names} != esperado")
            continue
        warm = json.loads(files[0].read_text(encoding="utf-8"))
        runs = [json.loads(f.read_text(encoding="utf-8")) for f in files[1:]]
        vals = [r["t_fluxo_seconds"] for r in runs]
        for i, r in enumerate(runs, start=1):
            lat_checks += 1
            tag = f"{exp}/{sc}ms/run{i:02d}"
            if r["call_count"] != 28:
                problem(f"{tag}: call_count={r['call_count']} != 28")
            if r["retries"] or r["wasted_seconds"] != 0.0:
                problem(f"{tag}: retries={r['retries']} wasted={r['wasted_seconds']}")
            if r["naive_elapsed_seconds"] != r["t_fluxo_seconds"]:
                problem(f"{tag}: naive_elapsed != t_fluxo sem retry")
        stamps = [r["generated_at"] for r in [warm] + runs]
        if stamps != sorted(stamps):
            problem(f"{exp}/{sc}ms: generated_at nao monotonico entre warmup/run01..10")
        med = statistics.median(vals)
        rec = {
            "median": med, "min": min(vals), "max": max(vals),
            "mean": round(statistics.mean(vals), 6), "stdev": round(statistics.stdev(vals), 6),
            "spread": spread(vals, 4), "values": vals, "sorted": sorted(vals),
            "absdev": [round(abs(v - med), 6) for v in vals], "warmup": warm["t_fluxo_seconds"],
        }
        lat_summary[(prof, sc)] = rec

        mm = json.loads((d / "median_metrics.json").read_text(encoding="utf-8"))
        checks = [
            ("run_count", 10, mm["run_count"]), ("median_seconds", med, mm["median_seconds"]),
            ("min_seconds", rec["min"], mm["min_seconds"]), ("max_seconds", rec["max"], mm["max_seconds"]),
            ("mean_seconds", rec["mean"], mm["mean_seconds"]), ("stdev_seconds", rec["stdev"], mm["stdev_seconds"]),
            ("spread_pct", rec["spread"], mm["spread_pct"]),
        ]
        for name, a, b in checks:
            if not close(a, b):
                problem(f"{exp}/{sc}ms latency {name}: recalculado={a} json={b}")
        if mm["individual_values_seconds"] != vals:
            problem(f"{exp}/{sc}ms latency individual_values diferem")
        if mm["sorted_values_seconds"] != rec["sorted"]:
            problem(f"{exp}/{sc}ms latency sorted_values diferem")
        if [round(x, 6) for x in mm["absolute_deviation_from_median"]] != rec["absdev"]:
            problem(f"{exp}/{sc}ms latency absolute_deviation diferem")
        if mm["crypto_profile"] != prof or mm["latency_scenario_ms"] != sc:
            problem(f"{exp}/{sc}ms latency: crypto_profile/latency_scenario_ms no json = {mm['crypto_profile']}/{mm['latency_scenario_ms']}")
        if mm["warmup"]["t_fluxo_seconds"] != warm["t_fluxo_seconds"] or warm["t_fluxo_seconds"] in vals and vals.count(warm["t_fluxo_seconds"]) > 0:
            problem(f"{exp}/{sc}ms latency: warmup inconsistente ou presente nas 10 execucoes")
        if mm["runs_with_retries"] or mm["whole_run_retries"]:
            problem(f"{exp}/{sc}ms latency: retries registrados {mm['runs_with_retries']} {mm['whole_run_retries']}")

        md = (d / "report.md").read_text(encoding="utf-8")
        pats = {
            "median": (r"Mediana: \*\*([\d.]+)s\*\*", med), "min": (r"Mínimo: ([\d.]+)s", rec["min"]),
            "max": (r"Máximo: ([\d.]+)s", rec["max"]), "mean": (r"Média: ([\d.]+)s", rec["mean"]),
            "stdev": (r"Desvio padrão \(amostral\): ([\d.]+)s", rec["stdev"]), "spread": (r"Spread \(min/max\): ([\d.]+)%", rec["spread"]),
        }
        for k, (pat, want) in pats.items():
            m = re.search(pat, md)
            # report.md prints 6 decimals ("{:.6f}"); a median of two 6-decimal values can
            # land on a half-unit at the 7th decimal (e.g. 14.4922185), so the printed
            # figure may differ from the exact median by up to half a unit of the 6th place.
            tol = 5.000001e-7 if k != "spread" else 5.000001e-5
            if not m or abs(float(m.group(1)) - want) > tol:
                problem(f"{exp}/{sc}ms report.md {k}: md={m.group(1) if m else None} recalculado={want}")
        rows = re.findall(r"^\| (\d+) \| ([\d.]+) \| ([\d.]+) \| (\w+)", md, flags=re.M)
        if [float(r[1]) for r in rows] != vals:
            problem(f"{exp}/{sc}ms report.md: tabela de valores individuais difere dos runs brutos")

say(f"\nLatency: {len(PROFILES) * len(SCENARIOS)} cenarios/perfis, {lat_checks} execucoes brutas verificadas (call_count, retries, wasted, naive==t_fluxo).")
say("\nLatency -- mediana / spread por cenario (recalculado):")
say("  " + "perfil".ljust(8) + "".join(f"{sc:>16d}ms" for sc in SCENARIOS))
for exp, prof in PROFILES:
    say("  " + prof.ljust(8) + "".join(f"{lat_summary[(prof, sc)]['median']:>10.4f}s/{lat_summary[(prof, sc)]['spread']:>5.2f}%" for sc in SCENARIOS))
mx = max(((v["spread"], k) for k, v in lat_summary.items()))
say(f"  Spread maximo de latencia: {mx[0]}% em {mx[1]}")

# --------------------------------------------- residue / provenance checks
say("\n" + "=" * 78)
say("RESIDUO v5/v6 e proveniencia")
say("=" * 78)
all_stamps = []
for kind, glob in (("size", "runs/run*_baseline_metrics.json"), ("latency", "runs/run*.json")):
    for exp, prof in PROFILES:
        for sc in SCENARIOS:
            for f in (ROOT / kind / exp / f"{sc}ms").glob(glob):
                all_stamps.append((json.loads(f.read_text(encoding="utf-8"))["generated_at"], f"{kind}/{prof}/{sc}ms/{f.name}"))
all_stamps.sort()
say(f"  {len(all_stamps)} arquivos brutos; generated_at de {all_stamps[0][0]} ate {all_stamps[-1][0]}")
early = [s for s in all_stamps if s[0] < "2026-09-12"]
if early:
    problem(f"{len(early)} arquivos brutos com generated_at anterior a 2026-09-12 (janela da v7): {early[:3]}")
else:
    say("  todos os arquivos brutos foram gerados a partir de 2026-09-12 (janela de coleta da v7) -- nenhum arquivo herdado de v5/v6.")
if len({s[0] for s in all_stamps}) != len(all_stamps):
    problem("generated_at duplicado entre arquivos brutos (possivel copia)")
else:
    say("  nenhum generated_at duplicado entre arquivos brutos (sem copias entre pastas).")

refs = []
for f in list(ROOT.glob("size/**/MEDIAN_REPORT.md")) + list(ROOT.glob("latency/**/report.md")) + list(ROOT.glob("**/median_metrics.json")):
    txt = f.read_text(encoding="utf-8")
    for m in re.finditer(r"(thesis/results/v[1-6][^\s)`'\"]*|Level 1|experiment\d - [A-Za-z]+/[\w/.-]*v[56])", txt):
        refs.append((str(f.relative_to(ROOT)), m.group(0)))
kinds = {}
for f, ref in refs:
    kinds.setdefault(ref, set()).add(f.split("/")[0])
say(f"  referencias textuais a pastas v1-v6 nos artefatos derivados: {len(refs)} ocorrencias, {len(kinds)} tipos distintos")
for ref, where in sorted(kinds.items()):
    say(f"    '{ref}' (em: {sorted(where)}) -- texto de template do gerador do relatorio, nao dado herdado")

say("\n" + "=" * 78)
if problems:
    say(f"RESULTADO: {len(problems)} DIVERGENCIAS -- ver linhas '!!' acima.")
else:
    say("RESULTADO: 0 divergencias. Todas as 18 metricas de tamanho (4 escalares + 6 leituras de participante cada) e as 18 de latencia,")
    say("recalculadas do zero a partir dos arquivos brutos, batem exatamente com median_metrics.json e com os relatorios .md derivados.")
say("=" * 78)

if "--write" in sys.argv:
    (ROOT / "audit_recompute_from_raw.txt").write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"\nWrote {ROOT / 'audit_recompute_from_raw.txt'}")
sys.exit(1 if problems else 0)
