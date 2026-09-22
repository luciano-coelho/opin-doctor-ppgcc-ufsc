"""
Builds thesis/results/v7/CONSOLIDATED_REPORT.md and ARCHITECTURE.md from the
templates in this folder + thesis/results/v7/report_data_v7.json (itself
derived from the raw runs by thesis/scripts/compute_v7_report_data.py).
Run: python thesis/scripts/report_build/build_v7_reports.py Every number that appears in a table or that is
quoted inline from measured data comes from the dict V/T below -- nothing is
typed by hand into the prose.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
V7 = REPO / "thesis" / "results" / "v7"
D = json.loads((V7 / "report_data_v7.json").read_text(encoding="utf-8"))

PROF = ["classic", "pqc", "hybrid"]
NAME = {"classic": "Clássico", "pqc": "PQC", "hybrid": "Híbrido"}
SC = [0, 14, 30, 140, 225, 320]


def nd(x, d=0):
    s = f"{x:,.{d}f}"
    return s.replace(",", "\0").replace(".", ",").replace("\0", ".")


def n0(x):
    return nd(x, 0)


def n2(x):
    return nd(x, 2)


def pct(x, d=2):
    return nd(x, d) + "%"


def sgn(x, d=0):
    return ("+" if x >= 0 else "−") + nd(abs(x), d)


def spct(x, d=2):
    return ("+" if x >= 0 else "−") + nd(abs(x), d) + "%"


def xr(x, d=2):
    return nd(x, d) + "×"


V = {}
S, O, K, P = D["size"], D["opinsize"], D["pki"], D["participants"]

for p in PROF:
    s, o, k, b = S[p], O[p], K[p], P[p]
    V[f"hs_{p}"] = n0(s["handshake_p50"])
    V[f"cert_{p}"] = n0(s["client_cert_der"])
    V[f"jwtmean_{p}"] = n2(s["jwt_mean_exact"])
    V[f"jwtsum_{p}"] = n0(s["jwt_sum"])
    V[f"jwk_{p}"] = n0(s["jwk_pk_size"])
    V[f"total_{p}"] = n0(s["total_bytes"])
    V[f"root_{p}"] = n0(k["root_bytes"])
    V[f"issuer_{p}"] = n0(k["issuer_bytes"])
    V[f"pkimean_{p}"] = n0(k["pki_bytes_mean"])
    V[f"pkimeas_{p}"] = n0(k["measured_sent"])
    V[f"t_hs_{p}"] = n0(o["term_handshake"])
    V[f"t_jwt_{p}"] = n0(o["term_jwt"])
    V[f"t_jwk_{p}"] = n0(o["term_jwk"])
    V[f"t_pki_{p}"] = n0(o["term_pki"])
    V[f"opin0_{p}"] = n0(o["original"])
    V[f"opin1_{p}"] = n0(o["extended"])
    V[f"dpct_{p}"] = pct(o["delta_pct"])
    V[f"share_{p}"] = pct(o["pki_share_of_extended_pct"])
    V[f"opin1meas_{p}"] = n0(o["extended_with_measured_framing"])
    V[f"dpctmeas_{p}"] = pct(o["delta_pct_with_measured_framing"])
    V[f"derbody_{p}"] = n0(k["der_body_total"])
    V[f"opin1der_{p}"] = n0(o["extended_with_der"])
    V[f"dpctder_{p}"] = pct(o["delta_pct_with_der"])
    V[f"rootder_{p}"] = n0(k["root_der"])
    V[f"issuerder_{p}"] = n0(k["issuer_der"])
    V[f"cs_{p}"] = n0(b["Client"]["sent_bytes"])
    V[f"cr_{p}"] = n0(b["Client"]["received_bytes"])
    V[f"os_{p}"] = n0(b["Other"]["sent_bytes"])
    V[f"or_{p}"] = n0(b["Other"]["received_bytes"])
    V[f"ps_{p}"] = n0(b["PKI/CRL"]["sent_bytes"])
    V[f"pr_{p}"] = n0(b["PKI/CRL"]["received_bytes"])

V["n_mtls"] = str(S["classic"]["n_mtls"])
V["n_jwt"] = str(S["classic"]["n_jwt"])
V["n_jwk"] = str(S["classic"]["n_jwk"])
V["n_pki"] = str(K["classic"]["n_pki"])
V["n_root"] = str(K["classic"]["n_root"])
V["n_issuer"] = str(K["classic"]["n_issuer"])
V["n_req"] = str(S["classic"]["total_requests"])
V["frame_each"] = str(D["pki_framing_each_all_profiles"])
V["frame_total"] = str(K["classic"]["framing_total"])
V["req_each"] = n0(D["pki_request_bytes_each_all_profiles"])
for a, b_ in (("pqc", "classic"), ("hybrid", "classic"), ("hybrid", "pqc")):
    V[f"hs_ratio_{a}_{b_}"] = xr(S[a]["handshake_p50"] / S[b_]["handshake_p50"])
    V[f"hs_delta_{a}_{b_}"] = n0(S[a]["handshake_p50"] - S[b_]["handshake_p50"])
    V[f"cert_ratio_{a}_{b_}"] = xr(S[a]["client_cert_der"] / S[b_]["client_cert_der"])
    V[f"jwt_ratio_{a}_{b_}"] = xr(S[a]["jwt_mean_exact"] / S[b_]["jwt_mean_exact"])
    V[f"total_ratio_{a}_{b_}"] = xr(S[a]["total_bytes"] / S[b_]["total_bytes"])
    V[f"opin0_ratio_{a}_{b_}"] = xr(O[a]["original"] / O[b_]["original"])
    V[f"opin1_ratio_{a}_{b_}"] = xr(O[a]["extended"] / O[b_]["extended"])
    V[f"opin0_up_{a}_{b_}"] = spct((O[a]["original"] / O[b_]["original"] - 1) * 100)
    V[f"opin1_up_{a}_{b_}"] = spct((O[a]["extended"] / O[b_]["extended"] - 1) * 100)
    V[f"pki_ratio_{a}_{b_}"] = xr(O[a]["term_pki"] / O[b_]["term_pki"])
    V[f"cr_ratio_{a}_{b_}"] = xr(P[a]["Client"]["received_bytes"] / P[b_]["Client"]["received_bytes"])
V["hyb_pki_over_jwk"] = xr(O["hybrid"]["term_pki"] / O["hybrid"]["term_jwk"], 1)
V["hyb_pki_over_hs"] = pct(O["hybrid"]["term_pki"] / O["hybrid"]["term_handshake"] * 100, 1)
V["pqc_pki_over_jwk"] = xr(O["pqc"]["term_pki"] / O["pqc"]["term_jwk"], 1)
V["cls_pki_over_jwk"] = xr(O["classic"]["term_pki"] / O["classic"]["term_jwk"], 1)
V["cls_pki_over_hs"] = pct(O["classic"]["term_pki"] / O["classic"]["term_handshake"] * 100, 1)
V["pqc_pki_over_hs"] = pct(O["pqc"]["term_pki"] / O["pqc"]["term_handshake"] * 100, 1)

L = D["latency"]
LD = D["latency_deltas"]
HY = D["hypothesis"]
V["lat_max_spread"] = pct(max(L[p][str(s)]["spread_pct"] for p in PROF for s in SC), 2)
mx = max(((L[p][str(s)]["spread_pct"], p, s) for p in PROF for s in SC))
V["lat_max_spread_where"] = f"{NAME[mx[1]]}, {mx[2]} ms"
V["lat_gap_cp_min"] = nd(min(LD[str(s)]["pqc_minus_classic"] for s in SC), 2)
V["lat_gap_cp_max"] = nd(max(LD[str(s)]["pqc_minus_classic"] for s in SC), 2)
V["lat_gap_hc_min"] = nd(min(LD[str(s)]["hybrid_minus_classic"] for s in SC), 2)
V["lat_gap_hc_max"] = nd(max(LD[str(s)]["hybrid_minus_classic"] for s in SC), 2)
V["lat_gap_hp_min"] = nd(min(LD[str(s)]["hybrid_minus_pqc"] for s in SC), 2)
V["lat_gap_hp_max"] = nd(max(LD[str(s)]["hybrid_minus_pqc"] for s in SC), 2)
V["lat_hp_rel_min"] = pct(min((LD[str(s)]["hybrid_over_pqc"] - 1) * 100 for s in SC), 1)
V["lat_hp_rel_max"] = pct(max((LD[str(s)]["hybrid_over_pqc"] - 1) * 100 for s in SC), 1)
V["lat_cp_ratio_0"] = xr(LD["0"]["pqc_over_classic"])
V["lat_cp_ratio_320"] = xr(LD["320"]["pqc_over_classic"])
V["lat_hc_ratio_0"] = xr(LD["0"]["hybrid_over_classic"])
V["lat_hc_ratio_320"] = xr(LD["320"]["hybrid_over_classic"])
V["order_holds_count"] = str(sum(1 for s in SC if HY[str(s)]["order_holds"]))
V["cp_overlap_count"] = str(sum(1 for s in SC if HY[str(s)]["classic_pqc_ranges_overlap"]))
V["hp_overlap_count"] = str(sum(1 for s in SC if HY[str(s)]["pqc_hybrid_ranges_overlap"]))
V["p_cp_max"] = nd(max(HY[str(s)]["p_pqc_gt_classic"] for s in SC), 6)
V["p_hp_max"] = nd(max(HY[str(s)]["p_hybrid_gt_pqc"] for s in SC), 4)
V["classic_growth"] = xr(L["classic"]["320"]["median"] / L["classic"]["0"]["median"], 1)
V["pqc_growth"] = xr(L["pqc"]["320"]["median"] / L["pqc"]["0"]["median"], 1)
V["hybrid_growth"] = xr(L["hybrid"]["320"]["median"] / L["hybrid"]["0"]["median"], 1)


def pfmt(p):
    return "< 0,0001" if p < 0.0001 else nd(p, 4)


PD = D["participants_decomposed"]
for p in PROF:
    b = PD[p]
    V[f"as_s_{p}"] = n0(b["AS"]["sent_bytes"]); V[f"as_r_{p}"] = n0(b["AS"]["received_bytes"])
    V[f"rs_s_{p}"] = n0(b["RS"]["sent_bytes"]); V[f"rs_r_{p}"] = n0(b["RS"]["received_bytes"])
    V[f"assh_{p}"] = pct(b["AS"]["sent_bytes"] / (b["AS"]["sent_bytes"] + b["RS"]["sent_bytes"] + b["PKI/CRL"]["sent_bytes"]) * 100, 1)
    V[f"rssh_{p}"] = pct(b["RS"]["sent_bytes"] / (b["AS"]["sent_bytes"] + b["RS"]["sent_bytes"] + b["PKI/CRL"]["sent_bytes"]) * 100, 1)
    V[f"pkish_{p}"] = pct(b["PKI/CRL"]["sent_bytes"] / (b["AS"]["sent_bytes"] + b["RS"]["sent_bytes"] + b["PKI/CRL"]["sent_bytes"]) * 100, 1)

T = {}
T["size_main"] = "\n".join([
    "| Métrica (por fluxo completo) | Clássico | PQC | Híbrido |",
    "|---|---:|---:|---:|",
    f"| Handshake mTLS, P50 das {V['n_mtls']} conexões (bytes) | {V['hs_classic']} | {V['hs_pqc']} | {V['hs_hybrid']} |",
    f"| Certificado de cliente, DER (bytes) | {V['cert_classic']} | {V['cert_pqc']} | {V['cert_hybrid']} |",
    f"| JWT médio, {V['n_jwt']} tokens (bytes) | {V['jwtmean_classic']} | {V['jwtmean_pqc']} | {V['jwtmean_hybrid']} |",
    f"| Chave pública JWK de assinatura do AS (bytes) | {V['jwk_classic']} | {V['jwk_pqc']} | {V['jwk_hybrid']} |",
    f"| Certificado de CA raiz servido (PEM, bytes) | {V['root_classic']} | {V['root_pqc']} | {V['root_hybrid']} |",
    f"| Certificado de CA emissora servido (PEM, bytes) | {V['issuer_classic']} | {V['issuer_pqc']} | {V['issuer_hybrid']} |",
    f"| Tráfego de aplicação total, {V['n_req']} requisições (bytes) | {V['total_classic']} | {V['total_pqc']} | {V['total_hybrid']} |",
    "| Spread entre as 60 execuções (6 cenários × 10) de cada métrica | 0,00% | 0,00% | 0,00% |",
])
T["size_ratios"] = "\n".join([
    "| Razão | Handshake | Certificado | JWT médio | Tráfego total | Saída dos servidores |",
    "|---|---:|---:|---:|---:|---:|",
    f"| PQC / Clássico | {V['hs_ratio_pqc_classic']} | {V['cert_ratio_pqc_classic']} | {V['jwt_ratio_pqc_classic']} | {V['total_ratio_pqc_classic']} | {V['cr_ratio_pqc_classic']} |",
    f"| Híbrido / Clássico | {V['hs_ratio_hybrid_classic']} | {V['cert_ratio_hybrid_classic']} | {V['jwt_ratio_hybrid_classic']} | {V['total_ratio_hybrid_classic']} | {V['cr_ratio_hybrid_classic']} |",
    f"| Híbrido / PQC | {V['hs_ratio_hybrid_pqc']} | {V['cert_ratio_hybrid_pqc']} | {V['jwt_ratio_hybrid_pqc']} | {V['total_ratio_hybrid_pqc']} | {V['cr_ratio_hybrid_pqc']} |",
])
T["opin"] = "\n".join([
    "| Termo | N | Clássico | PQC | Híbrido |",
    "|---|---:|---:|---:|---:|",
    f"| N_mTLS × handshake_bytes | {V['n_mtls']} | {V['t_hs_classic']} | {V['t_hs_pqc']} | {V['t_hs_hybrid']} |",
    f"| N_JWT × JWT_size | {V['n_jwt']} | {V['t_jwt_classic']} | {V['t_jwt_pqc']} | {V['t_jwt_hybrid']} |",
    f"| N_JWK × JWK_PK_size | {V['n_jwk']} | {V['t_jwk_classic']} | {V['t_jwk_pqc']} | {V['t_jwk_hybrid']} |",
    f"| **OPINsize original (3 termos)** | | **{V['opin0_classic']}** | **{V['opin0_pqc']}** | **{V['opin0_hybrid']}** |",
    f"| N_PKI × PKI_bytes (novo) | {V['n_pki']} | {V['t_pki_classic']} | {V['t_pki_pqc']} | {V['t_pki_hybrid']} |",
    f"| **OPINsize estendido (4 termos)** | | **{V['opin1_classic']}** | **{V['opin1_pqc']}** | **{V['opin1_hybrid']}** |",
    f"| Acréscimo do termo PKI (bytes) | | +{V['t_pki_classic']} | +{V['t_pki_pqc']} | +{V['t_pki_hybrid']} |",
    f"| Acréscimo do termo PKI (% do OPINsize original) | | +{V['dpct_classic']} | +{V['dpct_pqc']} | +{V['dpct_hybrid']} |",
    f"| Peso do termo PKI no OPINsize estendido | | {V['share_classic']} | {V['share_pqc']} | {V['share_hybrid']} |",
])
T["opin_ratios"] = "\n".join([
    "| Razão entre perfis | Fórmula original | Fórmula estendida |",
    "|---|---:|---:|",
    f"| PQC / Clássico | {V['opin0_ratio_pqc_classic']} ({V['opin0_up_pqc_classic']}) | {V['opin1_ratio_pqc_classic']} ({V['opin1_up_pqc_classic']}) |",
    f"| Híbrido / Clássico | {V['opin0_ratio_hybrid_classic']} ({V['opin0_up_hybrid_classic']}) | {V['opin1_ratio_hybrid_classic']} ({V['opin1_up_hybrid_classic']}) |",
    f"| Híbrido / PQC | {V['opin0_ratio_hybrid_pqc']} ({V['opin0_up_hybrid_pqc']}) | {V['opin1_ratio_hybrid_pqc']} ({V['opin1_up_hybrid_pqc']}) |",
])
T["pki_detail"] = "\n".join([
    "| Perfil | CA raiz (bytes) | CA emissora (bytes) | PKI_bytes médio (bytes) | N_PKI | N_PKI × PKI_bytes (bytes) | Medido: resposta HTTP das 4 buscas (bytes) | Enquadramento HTTP (bytes) |",
    "|---|---:|---:|---:|---:|---:|---:|---:|",
] + [
    f"| {NAME[p]} | {V[f'root_{p}']} | {V[f'issuer_{p}']} | {V[f'pkimean_{p}']} | {V['n_pki']} | {V[f't_pki_{p}']} | {V[f'pkimeas_{p}']} | {V['frame_total']} ({V['n_pki']} × {V['frame_each']}) |"
    for p in PROF
])
T["sens"] = "\n".join([
    "| Perfil | OPINsize estendido (corpo PEM) | Acréscimo | OPINsize estendido (resposta HTTP medida) | Acréscimo |",
    "|---|---:|---:|---:|---:|",
] + [
    f"| {NAME[p]} | {V[f'opin1_{p}']} | +{V[f'dpct_{p}']} | {V[f'opin1meas_{p}']} | +{V[f'dpctmeas_{p}']} |"
    for p in PROF
])
T["sens_der"] = "\n".join([
    "| Perfil | CA raiz / emissora (DER, bytes) | N_PKI × PKI_bytes em DER (bytes) | OPINsize estendido (DER) | Acréscimo |",
    "|---|---:|---:|---:|---:|",
] + [
    f"| {NAME[p]} | {V[f'rootder_{p}']} / {V[f'issuerder_{p}']} | {V[f'derbody_{p}']} | {V[f'opin1der_{p}']} | +{V[f'dpctder_{p}']} |"
    for p in PROF
])
T["participants"] = "\n".join([
    "| Participante | Direção | Clássico | PQC | Híbrido |",
    "|---|---|---:|---:|---:|",
    f"| Cliente | enviado (requisições) | {V['cs_classic']} | {V['cs_pqc']} | {V['cs_hybrid']} |",
    f"| Cliente | recebido (respostas) | {V['cr_classic']} | {V['cr_pqc']} | {V['cr_hybrid']} |",
    f"| **AS** (servidor de autorização) | enviado (saída / egress) | {V['as_s_classic']} | {V['as_s_pqc']} | {V['as_s_hybrid']} |",
    f"| **AS** (servidor de autorização) | recebido (entrada) | {V['as_r_classic']} | {V['as_r_pqc']} | {V['as_r_hybrid']} |",
    f"| **RS** (servidor de recursos) | enviado (saída / egress) | {V['rs_s_classic']} | {V['rs_s_pqc']} | {V['rs_s_hybrid']} |",
    f"| **RS** (servidor de recursos) | recebido (entrada) | {V['rs_r_classic']} | {V['rs_r_pqc']} | {V['rs_r_hybrid']} |",
    f"| Diretório / PKI-CRL | enviado (saída / egress) | {V['ps_classic']} | {V['ps_pqc']} | {V['ps_hybrid']} |",
    f"| Diretório / PKI-CRL | recebido (entrada) | {V['pr_classic']} | {V['pr_pqc']} | {V['pr_hybrid']} |",
    f"| **Total enviado por todos os servidores** | | **{n0(P['classic']['Other']['sent_bytes'] + P['classic']['PKI/CRL']['sent_bytes'])}** | **{n0(P['pqc']['Other']['sent_bytes'] + P['pqc']['PKI/CRL']['sent_bytes'])}** | **{n0(P['hybrid']['Other']['sent_bytes'] + P['hybrid']['PKI/CRL']['sent_bytes'])}** |",
])
T["egress_share"] = "\n".join([
    "| Fração da saída total dos servidores | Clássico | PQC | Híbrido |",
    "|---|---:|---:|---:|",
    "| AS |" + "".join(f" {V[f'assh_{p}']} |" for p in PROF),
    "| RS |" + "".join(f" {V[f'rssh_{p}']} |" for p in PROF),
    "| Diretório / PKI-CRL |" + "".join(f" {V[f'pkish_{p}']} |" for p in PROF),
])
rows = ["| Cenário | Clássico | PQC | Híbrido |", "|---:|---:|---:|---:|"]
for s in SC:
    rows.append(f"| {s} ms | " + " | ".join(nd(L[p][str(s)]["median"], 4) for p in PROF) + " |")
T["lat_matrix"] = "\n".join(rows)
rows = ["| Perfil | Cenário | Mediana | Mín. | Máx. | Média | Desvio-padrão | Spread |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
for p in PROF:
    for s in SC:
        r = L[p][str(s)]
        rows.append(f"| {NAME[p]} | {s} ms | {nd(r['median'], 4)} | {nd(r['min'], 4)} | {nd(r['max'], 4)} | {nd(r['mean'], 4)} | {nd(r['stdev'], 4)} | {pct(r['spread_pct'], 2)} |")
T["lat_full"] = "\n".join(rows)
rows = ["| Cenário | PQC − Clássico (s) | Híbrido − Clássico (s) | Híbrido − PQC (s) | PQC / Clássico | Híbrido / Clássico | Híbrido / PQC |", "|---:|---:|---:|---:|---:|---:|---:|"]
for s in SC:
    d = LD[str(s)]
    rows.append(f"| {s} ms | {nd(d['pqc_minus_classic'], 4)} | {nd(d['hybrid_minus_classic'], 4)} | {nd(d['hybrid_minus_pqc'], 4)} | {xr(d['pqc_over_classic'])} | {xr(d['hybrid_over_classic'])} | {xr(d['hybrid_over_pqc'])} |")
T["lat_deltas"] = "\n".join(rows)
rows = ["| Cenário | Ordem Clássico < PQC < Híbrido (medianas) | Intervalos [mín., máx.] Clássico × PQC | Intervalos PQC × Híbrido | p exato (PQC > Clássico) | p exato (Híbrido > PQC) |", "|---:|:---:|:---:|:---:|---:|---:|"]
for s in SC:
    h = HY[str(s)]
    rows.append(f"| {s} ms | {'vale' if h['order_holds'] else 'não vale'} | {'sobrepõem' if h['classic_pqc_ranges_overlap'] else 'separados'} | {'sobrepõem' if h['pqc_hybrid_ranges_overlap'] else 'separados'} | {pfmt(h['p_pqc_gt_classic'])} | {pfmt(h['p_hybrid_gt_pqc'])} |")
T["hypothesis"] = "\n".join(rows)


def render(tpl_name, out_name):
    txt = (HERE / tpl_name).read_text(encoding="utf-8")

    def sub(m):
        key = m.group(1)
        if key.startswith("table:"):
            return T[key[6:]]
        return V[key]

    out = re.sub(r"\{\{([^}]+)\}\}", sub, txt)
    (V7 / out_name).write_text(out, encoding="utf-8")
    print("wrote", out_name, len(out.splitlines()), "lines")


if __name__ == "__main__":
    if "--keys" in sys.argv:
        for k in sorted(V):
            print(k, "=", V[k])
        sys.exit(0)
    render("CONSOLIDATED_REPORT.tpl.md", "CONSOLIDATED_REPORT.md")
    render("ARCHITECTURE.tpl.md", "ARCHITECTURE.md")
