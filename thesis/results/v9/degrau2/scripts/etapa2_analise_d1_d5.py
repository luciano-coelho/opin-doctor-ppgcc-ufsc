#!/usr/bin/env python3
"""Degrau 2, Etapa 2 -- analises D1-D5, exatamente conforme
PLANO_DEGRAU2.md + Emenda 1 (criterios/testes/sementes/regras de
agregacao, sem nenhuma alteracao). Toda entrada vem de arquivo real
(campaign_data/round{1,2}/runs_raw/*.json, hardware_probe/
probe_overhead_result.json) -- nenhum numero digitado a mao.
"""
import glob
import json
import statistics
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
PROBE = json.load(open(ROOT / "hardware_probe" / "probe_overhead_result.json", encoding="utf-8"))
ROUTES = ["L0-sa-east-1", "L0-us-east-1", "L0-ap-northeast-1", "L123"]
PROFILES = ["classico", "pqc", "hibrido-and"]
PHASE_KEYS = ["http_calls_seconds", "signing_seconds", "verification_seconds",
              "explicit_wait_seconds", "setup_seconds", "residual_seconds"]
SEEDS = {"round1": 20261117, "round2": 20261118}
RNG_RESAMPLES = 10000


def load_round(round_name):
    recs = []
    for fp in sorted(glob.glob(str(ROOT / "campaign_data" / round_name / "runs_raw" / "*__run*.json"))):
        if "warmup" in fp:
            continue
        d = json.load(open(fp, encoding="utf-8"))
        start = _parse_iso(d["start_utc"])
        end = _parse_iso(d["end_utc"])
        residuo_fino = d["t_fluxo_fino_seconds"] - sum(c["latency_ms"] for c in d["insurance"]) / 1000.0
        recs.append({
            "round": round_name, "profile": d["profile"], "route": d["route"], "run": d["run"],
            "t_fluxo_fino": d["t_fluxo_fino_seconds"],
            "t_fluxo_parede": (end - start),
            "residuo_fino": residuo_fino,
            **{k: d["phase_accounting"][k] for k in PHASE_KEYS},
        })
    return recs


def _parse_iso(s):
    from datetime import datetime
    return datetime.fromisoformat(s).timestamp()


def hodges_lehmann_diff(a, b):
    diffs = np.subtract.outer(np.array(a), np.array(b)).ravel()
    return float(np.median(diffs))


def bootstrap_ci_hl(a, b, seed, n=RNG_RESAMPLES):
    rng = np.random.default_rng(seed)
    a, b = np.array(a), np.array(b)
    boots = np.empty(n)
    for i in range(n):
        ra = rng.choice(a, size=len(a), replace=True)
        rb = rng.choice(b, size=len(b), replace=True)
        boots[i] = np.median(np.subtract.outer(ra, rb).ravel())
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(lo), float(hi)


def mw_exact(a, b):
    try:
        r = stats.mannwhitneyu(a, b, alternative="two-sided", method="exact")
    except Exception:
        r = stats.mannwhitneyu(a, b, alternative="two-sided", method="asymptotic")
    return float(r.pvalue)


def holm(pvals):
    idx = sorted(range(len(pvals)), key=lambda i: pvals[i])
    m = len(pvals)
    adj = [None] * m
    prev = 0.0
    for rank, i in enumerate(idx):
        val = min(1.0, pvals[i] * (m - rank))
        val = max(val, prev)
        adj[i] = val
        prev = val
    return adj


def main():
    r1 = load_round("round1")
    r2 = load_round("round2")
    out = {}

    # ---- Regra das 2 rodadas: 4 rotas x 7 metricas = 28 testes, Holm ----
    metrics = ["t_fluxo_fino"] + PHASE_KEYS
    tests = []
    for route in ROUTES:
        for metric in metrics:
            a = [x[metric] for x in r1 if x["route"] == route]
            b = [x[metric] for x in r2 if x["route"] == route]
            p = mw_exact(a, b)
            tests.append({"route": route, "metric": metric, "p": p, "n1": len(a), "n2": len(b)})
    pvals = [t["p"] for t in tests]
    adj = holm(pvals)
    for t, pa in zip(tests, adj):
        t["p_holm"] = pa
        t["pode_agrupar"] = pa >= 0.05
    out["regra_2_rodadas"] = tests
    divergent = {(t["route"], t["metric"]) for t in tests if not t["pode_agrupar"]}
    out["regra_2_rodadas_divergencias"] = [list(d) for d in divergent]

    def pooled_or_separate(route, metric, profile=None):
        """Retorna (valores, agrupado:bool) -- agrupado=False se a regra das
        2 rodadas achou divergencia nesta rota/metrica. Achado de auditoria:
        quando agrupado=False, um chamador que ignora o retorno `agrupado`
        (faz `vals, _, agr = ...` e segue usando `vals` sem checar `agr`)
        descartaria a Rodada 2 silenciosamente. D1 trata isso explicitamente
        (ver bloco acima, branch `if not agrupado`); D2/D3 abaixo checam
        `agr`/`agra`/`agrb` e levantam erro alto se algum vier False, em vez
        de seguir silenciosamente -- nunca manifesta nesta rodada porque
        `divergent` esta vazio, mas protege contra regressao futura."""
        filt1 = [x for x in r1 if x["route"] == route and (profile is None or x["profile"] == profile)]
        filt2 = [x for x in r2 if x["route"] == route and (profile is None or x["profile"] == profile)]
        v1 = [x[metric] for x in filt1]
        v2 = [x[metric] for x in filt2]
        if (route, metric) in divergent:
            return v1, v2, False
        return v1 + v2, None, True

    # ---- D1: heterogeneidade entre instalacoes (Classic, T_fluxo fino, 3 rotas L0) ----
    l0_routes = ["L0-sa-east-1", "L0-us-east-1", "L0-ap-northeast-1"]
    pairs = [("L0-sa-east-1", "L0-us-east-1"), ("L0-sa-east-1", "L0-ap-northeast-1"),
             ("L0-us-east-1", "L0-ap-northeast-1")]
    d1 = {"pairs": []}
    for ra, rb in pairs:
        va, agr_a, pooled_a = pooled_or_separate(ra, "t_fluxo_fino", "classico")
        vb, agr_b, pooled_b = pooled_or_separate(rb, "t_fluxo_fino", "classico")
        agrupado = pooled_a and pooled_b
        if not agrupado:
            entry = {"par": [ra, rb], "agrupado": False,
                     "nota": "regra das 2 rodadas impede agrupar -- reportando rodadas separadamente",
                     "round1": {"a": [x["t_fluxo_fino"] for x in r1 if x["route"] == ra and x["profile"] == "classico"],
                                "b": [x["t_fluxo_fino"] for x in r1 if x["route"] == rb and x["profile"] == "classico"]},
                     "round2": {"a": [x["t_fluxo_fino"] for x in r2 if x["route"] == ra and x["profile"] == "classico"],
                                "b": [x["t_fluxo_fino"] for x in r2 if x["route"] == rb and x["profile"] == "classico"]}}
            for rk in ("round1", "round2"):
                aa, bb = entry[rk]["a"], entry[rk]["b"]
                p = mw_exact(aa, bb)
                hl = hodges_lehmann_diff(aa, bb)
                lo, hi = bootstrap_ci_hl(aa, bb, SEEDS[rk])
                entry[rk] = {"p": p, "hl_diff_s": hl, "ci95": [lo, hi],
                             "median_a": statistics.median(aa), "median_b": statistics.median(bb)}
            d1["pairs"].append(entry)
            continue
        p = mw_exact(va, vb)
        hl = hodges_lehmann_diff(va, vb)
        # Escolha metodologica explicita (plano nao cobre o caso agrupado --
        # so define "semente da rodada correspondente"): usa a semente da
        # Rodada 1 (20261117) pro bootstrap quando as 2 rodadas sao
        # agrupadas. Deterministico/reprodutivel, disclosed aqui.
        lo, hi = bootstrap_ci_hl(va, vb, SEEDS["round1"])
        smaller_median = min(statistics.median(va), statistics.median(vb))
        band = 0.15 * smaller_median
        dentro = (-band <= lo) and (hi <= band)
        fora = (hi < -band) or (lo > band)
        d1["pairs"].append({
            "par": [ra, rb], "agrupado": True, "n": [len(va), len(vb)],
            "p": p, "hl_diff_s": hl, "ci95": [lo, hi],
            "median_a_s": statistics.median(va), "median_b_s": statistics.median(vb),
            "banda_15pct_s": band, "ic_dentro_banda": dentro, "ic_fora_banda": fora,
        })
    # Convencao geral de testes do plano (secao "Testes exatos", nunca
    # revogada pela Emenda 1 para D1): Holm sobre os 3 testes/instalacao.
    # So descritivo -- a decisao SUSTENTADA/REFUTADA/PARCIAL de D1 usa
    # exclusivamente o criterio de IC-vs-banda da Emenda 1, nunca p-valor.
    d1_pvals = [e["p"] for e in d1["pairs"] if "p" in e]
    if d1_pvals:
        d1_holm = holm(d1_pvals)
        i = 0
        for e in d1["pairs"]:
            if "p" in e:
                e["p_holm"] = d1_holm[i]
                i += 1
    n_fora = sum(1 for e in d1["pairs"] if e.get("ic_fora_banda"))
    n_dentro = sum(1 for e in d1["pairs"] if e.get("ic_dentro_banda"))
    n_nao_agrupado = sum(1 for e in d1["pairs"] if not e.get("agrupado", True))
    if n_nao_agrupado > 0:
        d1["veredito"] = "PARCIAL (regra das 2 rodadas impediu agrupar >=1 par -- ver detalhe por rodada)"
    elif n_fora >= 1:
        d1["veredito"] = "REFUTADA (heterogeneidade real persiste, nao e so artefato de medicao)"
    elif n_dentro == 3:
        d1["veredito"] = "SUSTENTADA (heterogeneidade e majoritariamente artefato de medicao)"
    else:
        d1["veredito"] = "PARCIAL"
    out["D1"] = d1

    # ---- D2: overhead (parede-fino) vs RTT real, 4 rotas, pooling perfis ----
    d2_points = []
    for route in ROUTES:
        vals_fino, _, agr = pooled_or_separate(route, "t_fluxo_fino")
        vals_parede, _, agr2 = pooled_or_separate(route, "t_fluxo_parede")
        if not agr:
            raise RuntimeError(f"D2: regra das 2 rodadas divergiu em ({route!r}, 't_fluxo_fino') -- trate manualmente.")
        overhead_ms = (statistics.median(vals_parede) - statistics.median(vals_fino)) * 1000
        rtt_ms = PROBE[route]["tcp_connect_ms"]["median_ms"]
        d2_points.append({"route": route, "overhead_ms": overhead_ms, "rtt_real_ms": rtt_ms,
                           "agrupado_rodadas": agr and agr2})
    xs = np.array([p["rtt_real_ms"] for p in d2_points])
    ys = np.array([p["overhead_ms"] for p in d2_points])
    slope, intercept = np.polyfit(xs, ys, 1)
    d2 = {"points": d2_points, "slope_ms_per_ms": float(slope), "intercept_ms": float(intercept)}
    slope_ok = bool(12.2 <= slope <= 15.3)
    intercept_ok = bool(0 <= intercept <= 1925)
    d2["veredito"] = "SUSTENTADA" if (slope_ok and intercept_ok) else "REFUTADA"
    d2["slope_in_range"] = slope_ok
    d2["intercept_in_range"] = intercept_ok
    out["D2"] = d2

    # ---- D2b: regressao SSH puro vs RTT real (so dados de probe, 4 pontos) ----
    xs_b = np.array([PROBE[r]["tcp_connect_ms"]["median_ms"] for r in ROUTES])
    ys_b = np.array([PROBE[r]["ssh_handshake_ms"]["median_ms"] for r in ROUTES])
    slope_b, intercept_b = np.polyfit(xs_b, ys_b, 1)
    out["D2b"] = {
        "slope_ms_per_ms": float(slope_b), "intercept_ms": float(intercept_b),
        "b_degrau1": 13.17, "slope_comparavel_a_b": True,
        "nota": "so a inclinacao e comparavel a b -- nivel absoluto (intercepto) nao previsto por nenhum modelo anterior",
    }

    # ---- D3: ordem Classic/PQC/Hibrido + testes por par (8 testes, Holm) ----
    order_official = {
        "L0-sa-east-1": ["pqc", "classico", "hibrido-and"],
        "L0-us-east-1": ["classico", "pqc", "hibrido-and"],
        "L0-ap-northeast-1": ["classico", "pqc", "hibrido-and"],
        "L123": ["classico", "pqc", "hibrido-and"],
    }
    d3 = {"por_rota": []}
    pair_tests = []
    for route in ROUTES:
        medians = {}
        for profile in PROFILES:
            vals, _, agr = pooled_or_separate(route, "t_fluxo_fino", profile)
            if not agr:
                raise RuntimeError(f"D3: regra das 2 rodadas divergiu em ({route!r}, 't_fluxo_fino') -- trate manualmente.")
            medians[profile] = statistics.median(vals)
        observed_order = sorted(PROFILES, key=lambda p: medians[p])
        persists = observed_order == order_official[route]
        d3["por_rota"].append({"route": route, "medians_s": medians,
                                "ordem_observada": observed_order,
                                "ordem_oficial": order_official[route],
                                "ordem_persiste": persists})
        for pa, pb in [("classico", "pqc"), ("pqc", "hibrido-and")]:
            va, _, agra = pooled_or_separate(route, "t_fluxo_fino", pa)
            vb, _, agrb = pooled_or_separate(route, "t_fluxo_fino", pb)
            if not (agra and agrb):
                raise RuntimeError(f"D3 pares: regra das 2 rodadas divergiu em ({route!r}, 't_fluxo_fino') -- trate manualmente.")
            p = mw_exact(va, vb)
            pair_tests.append({"route": route, "par": [pa, pb], "p": p,
                                "diff_ms": (statistics.median(vb) - statistics.median(va)) * 1000,
                                "agrupado": agra and agrb})
    adjp = holm([t["p"] for t in pair_tests])
    for t, pa in zip(pair_tests, adjp):
        t["p_holm"] = pa
        t["significativo"] = pa < 0.05
    d3["testes_por_par"] = pair_tests
    n_persist = sum(1 for e in d3["por_rota"] if e["ordem_persiste"])
    d3["veredito"] = ("SUSTENTADA" if n_persist >= 3 else
                       "REFUTADA" if n_persist <= 1 else "INCONCLUSIVA")
    l0sa_pqc_classic = next(t for t in pair_tests if t["route"] == "L0-sa-east-1" and t["par"] == ["classico", "pqc"])
    # t["diff_ms"] ja e median(pqc)-median(classico) = PQC-Classic (ver loop
    # acima: diff_ms = median(vb)-median(va), com pb=pqc/va=classico para
    # este par) -- a Emenda 1 preve a faixa [-43;-24]ms PARA PQC-Classic
    # diretamente, nunca precisa de negacao (achado de auditoria: a versao
    # anterior negava aqui, um erro de sinal, nunca propagado ao veredito
    # porque a magnitude observada ficava fora da faixa nos dois sinais).
    diff_pqc_menos_classico_ms = l0sa_pqc_classic["diff_ms"]
    d3["previsao_l0sa_pqc_classic"] = {
        "diff_observado_pqc_menos_classico_ms": diff_pqc_menos_classico_ms,
        "faixa_prevista_ms": [-43, -24],
        "dentro_da_faixa": -43 <= diff_pqc_menos_classico_ms <= -24,
        "p_holm": l0sa_pqc_classic["p_holm"],
        "nao_significativo_como_previsto": not l0sa_pqc_classic["significativo"],
    }
    out["D3"] = d3

    # ---- D4a: 3 rotas L0, signing+verification >=60% de Δfino, http_calls<20% ----
    def decompose_pair(route, pa, pb):
        meds_a = {k: statistics.median([x[k] for x in (r1 + r2) if x["route"] == route and x["profile"] == pa])
                  for k in (["t_fluxo_fino"] + PHASE_KEYS)}
        meds_b = {k: statistics.median([x[k] for x in (r1 + r2) if x["route"] == route and x["profile"] == pb])
                  for k in (["t_fluxo_fino"] + PHASE_KEYS)}
        delta_fino = meds_b["t_fluxo_fino"] - meds_a["t_fluxo_fino"]
        deltas = {k: meds_b[k] - meds_a[k] for k in PHASE_KEYS}
        # Fracao PRE-REGISTRADA (plano: "responda por >=60% de Δ(T_fluxo
        # fino)"): divide pelo proprio delta_fino (escalar), nunca pela soma
        # das magnitudes dos componentes -- achado de auditoria: uma versao
        # anterior usava sum(abs(deltas)) como denominador, uma substituicao
        # nao-declarada que muda o que "60%" significa. Pode dar fracoes
        # >100% ou com sinal instavel quando ha cancelamento entre
        # componentes com sinais opostos (delta_fino pequeno) -- isso e
        # reportado explicitamente, nunca escondido.
        denom_literal = delta_fino if abs(delta_fino) > 1e-9 else 1e-12
        fracs_literal = {k: deltas[k] / denom_literal for k in PHASE_KEYS}
        # Fracao EXPLORATORIA (nao pre-registrada, so para dar contexto de
        # estabilidade numerica quando delta_fino e pequeno/cancela): fracao
        # de cada componente sobre a soma das magnitudes absolutas dos 6.
        denom_abs = sum(abs(deltas[k]) for k in PHASE_KEYS) or 1e-12
        fracs_abs = {k: deltas[k] / denom_abs for k in PHASE_KEYS}
        return {"delta_fino_s": delta_fino, "deltas_s": deltas,
                "fracoes": fracs_literal, "fracoes_exploratorio_abs": fracs_abs}

    # Guarda explicita (achado de auditoria: decompose_pair sempre agrupa
    # r1+r2 incondicionalmente, nunca consulta `divergent` como D1/D2/D3
    # fazem via pooled_or_separate -- violaria a regra geral das 2 rodadas
    # SE alguma divergencia real existisse). Nesta rodada `divergent` esta
    # vazio (ver regra_2_rodadas_divergencias), entao nao ha efeito real --
    # mas se isso mudar numa rodada futura, falha alto e claro em vez de
    # silenciosamente agrupar dados que a regra das 2 rodadas probe.
    d4_metrics_used = ["t_fluxo_fino"] + PHASE_KEYS
    d4_routes_used = ["L0-sa-east-1", "L0-us-east-1", "L0-ap-northeast-1", "L123"]
    d4_violacoes = [d for d in divergent if d[0] in d4_routes_used and d[1] in d4_metrics_used]
    if d4_violacoes:
        raise RuntimeError(
            f"D4a/D4b: regra das 2 rodadas achou divergencia em {d4_violacoes} "
            "mas decompose_pair sempre agrupa incondicionalmente -- pare e "
            "trate manualmente antes de aceitar qualquer resultado de D4a/D4b."
        )

    d4a = {"por_rota": []}
    for route in ["L0-sa-east-1", "L0-us-east-1", "L0-ap-northeast-1"]:
        pc = decompose_pair(route, "classico", "pqc")
        hp = decompose_pair(route, "pqc", "hibrido-and")
        def confirma(dec):
            sv = abs(dec["fracoes"]["signing_seconds"]) + abs(dec["fracoes"]["verification_seconds"])
            hc = abs(dec["fracoes"]["http_calls_seconds"])
            return sv >= 0.60 and hc < 0.20
        conf = confirma(pc) and confirma(hp)
        d4a["por_rota"].append({"route": route, "pqc_classico": pc, "hibrido_pqc": hp, "confirma": conf})
    n_conf = sum(1 for e in d4a["por_rota"] if e["confirma"])
    d4a["veredito"] = "SUSTENTADA" if n_conf >= 2 else "REFUTADA"
    out["D4a"] = d4a

    # ---- D4b: incremento L0-sa -> L123, residual+http>=60%, signing+verif<40% ----
    d4b = {"pares": []}
    for pa, pb in [("classico", "pqc"), ("pqc", "hibrido-and")]:
        dec_sa = decompose_pair("L0-sa-east-1", pa, pb)
        dec_l123 = decompose_pair("L123", pa, pb)
        incremento_total = dec_l123["delta_fino_s"] - dec_sa["delta_fino_s"]
        inc_components = {k: dec_l123["deltas_s"][k] - dec_sa["deltas_s"][k] for k in PHASE_KEYS}
        # Fracao PRE-REGISTRADA: divide pelo proprio incremento_total
        # (escalar), mesma correcao aplicada em decompose_pair/D4a acima.
        denom_literal = incremento_total if abs(incremento_total) > 1e-9 else 1e-12
        inc_fracs = {k: v / denom_literal for k, v in inc_components.items()}
        denom_abs = sum(abs(v) for v in inc_components.values()) or 1e-12
        inc_fracs_abs = {k: v / denom_abs for k, v in inc_components.items()}
        residual_http = abs(inc_fracs["residual_seconds"]) + abs(inc_fracs["http_calls_seconds"])
        sign_verif = abs(inc_fracs["signing_seconds"]) + abs(inc_fracs["verification_seconds"])
        confirma = residual_http >= 0.60 and sign_verif < 0.40
        d4b["pares"].append({"par": [pa, pb], "incremento_total_s": incremento_total,
                              "incremento_componentes_s": inc_components, "fracoes": inc_fracs,
                              "fracoes_exploratorio_abs": inc_fracs_abs,
                              "residual_mais_http": residual_http, "signing_mais_verif": sign_verif,
                              "confirma": confirma})
    n_conf_b = sum(1 for e in d4b["pares"] if e["confirma"])
    d4b["veredito"] = ("SUSTENTADA" if n_conf_b == 2 else "REFUTADA" if n_conf_b == 0 else "PARCIAL")
    out["D4b"] = d4b

    # ---- D5: residuo_fino, Classic, L123 vs L0-sa-east-1, razao com RTT real ----
    res_sa = [x["residuo_fino"] for x in (r1 + r2) if x["route"] == "L0-sa-east-1" and x["profile"] == "classico"]
    res_l123 = [x["residuo_fino"] for x in (r1 + r2) if x["route"] == "L123" and x["profile"] == "classico"]
    med_sa = statistics.median(res_sa)
    med_l123 = statistics.median(res_l123)
    delta_residuo_ms = (med_l123 - med_sa) * 1000
    rtt_real_l123 = PROBE["L123"]["tcp_connect_ms"]["median_ms"]
    razao = delta_residuo_ms / rtt_real_l123
    if 13.6 <= razao <= 26:
        veredito5 = "SUSTENTADA"
    elif 26 < razao <= 42.4:
        veredito5 = "ALTERNATIVA"
    else:
        veredito5 = "ACHADO NOVO"
    out["D5"] = {
        "median_residuo_fino_L0sa_ms": med_sa * 1000, "median_residuo_fino_L123_ms": med_l123 * 1000,
        "delta_residuo_fino_ms": delta_residuo_ms, "rtt_real_l123_ms": rtt_real_l123,
        "razao": razao, "veredito": veredito5,
    }

    out_path = ROOT / "ETAPA2_RESULTADOS.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"gravado em {out_path}")
    print(json.dumps({k: (v.get("veredito") if isinstance(v, dict) else None) for k, v in out.items()
                       if k in ("D1", "D2", "D3", "D4a", "D4b", "D5")}, indent=2, ensure_ascii=False))
    print("divergencias regra 2 rodadas:", out["regra_2_rodadas_divergencias"])


if __name__ == "__main__":
    main()
