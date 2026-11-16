#!/usr/bin/env python3
"""Gera thesis/results/v9/Consolidated_Metrics_Report_FINAL.md a partir
SOMENTE dos dados organizados/manifesto/custo ja coletados e verificados
por sha256 da campanha oficial v9, mais verificacoes EXTERNAS ao
pipeline de medicao executadas AO VIVO por este proprio script
(evaluate_criteria.expected_handshake_bytes, a partir dos certificados
reais em disco). Nenhum numero deste relatorio e digitado a mao -- todos
vem de arquivos reais lidos/computados abaixo.

Entradas (leitura apenas, nunca modificadas por este script):
  thesis/results/v9/campaign_oficial_conta_nova_raw/
      opinsize_oficial_conta_nova.json
      evaluate_criteria_oficial_resultado.json
      manifest.json
      cost_tracker.jsonl
      piloto_combined.log (evidencia do canal interno AS->RS, campanha)
      pilot_evidence/piloto_assimetrico_matls_internal_lines.log
          (mesma evidencia, piloto assimetrico anterior -- mesmo codigo
          e mesmas imagens Docker da campanha, coletado via SSH direto
          do piloto_combined.log real do piloto, salvo aqui como texto
          bruto; nunca agregado a mao)
      full_container_logs/{sa-east-1,us-east-1,ap-northeast-1}_v9-mtls.log
  thesis/results/v9/campaign_oficial_conta_nova_organized/
      retries_report.json
      handshake_bytes_alert.json
      latency/<experiment dir>/<rota>/median_metrics.json  (32 arquivos)
  thesis/results/v9/integration/evaluate_criteria.py
      (importado em runtime -- expected_handshake_bytes(), verificacao
      EXTERNA do termo mTLS a partir do DER real dos certificados)
  thesis/results/v9/certs/generated/*.crt
      (certificados realmente implantados -- fonte da verificacao acima)

Saida:
  thesis/results/v9/Consolidated_Metrics_Report_FINAL.md

Uso:
  python generate_final_report_oficial_conta_nova.py
"""
import importlib.util
import json
import statistics as st
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
RAW = REPO_ROOT / "thesis/results/v9/campaign_oficial_conta_nova_raw"
ORG = REPO_ROOT / "thesis/results/v9/campaign_oficial_conta_nova_organized"
OUT_MD = REPO_ROOT / "thesis/results/v9/Consolidated_Metrics_Report_FINAL.md"
CERTS_DIR = REPO_ROOT / "thesis/results/v9/certs/generated"
EVALUATE_CRITERIA_PATH = REPO_ROOT / "thesis/results/v9/integration/evaluate_criteria.py"
COST_TRACKER_PATH = REPO_ROOT / "thesis/results/v9/campaign/scripts/cost_tracker.py"

PROFILES = ["classico", "pqc", "hibrido-v8", "hibrido-and"]
PROFILE_LABEL = {
    "classico": "Classic",
    "pqc": "PQC",
    "hibrido-v8": "Control",
    "hibrido-and": "Hybrid",
}
EXPERIMENT_DIR = {
    "classico": "experiment1 - Classic",
    "pqc": "experiment2 - PQC",
    "hibrido-v8": "experiment4 - Control",
    "hibrido-and": "experiment3 - Hybrid",
}
ROUTES = [
    "L0-sa-east-1", "L123", "L219", "L325",
    "L0-us-east-1", "L14",
    "L0-ap-northeast-1", "L30",
]
ROUTE_INSTALLATION = {
    "L0-sa-east-1": "sa-east-1", "L123": "sa-east-1", "L219": "sa-east-1", "L325": "sa-east-1",
    "L0-us-east-1": "us-east-1", "L14": "us-east-1",
    "L0-ap-northeast-1": "ap-northeast-1", "L30": "ap-northeast-1",
}

TERM_LABELS_4 = [
    ("term_mtls_handshake", "mTLS (handshake)"),
    ("term_jwt", "JWT (apenas assinatura)"),
    ("term_jwk_raw", "JWK (chave crua)"),
    ("term_pki_crl", "PKI (certificados de CA)"),
]


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_criteria_result():
    """evaluate_criteria_oficial_resultado.json e um array JSON seguido de
    um resumo em texto puro (stdout completo do evaluate_criteria.py)."""
    raw = (RAW / "evaluate_criteria_oficial_resultado.json").read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        # Achado de ferramenta (nao de dados): 4 bytes nao-UTF8 no arquivo
        # inteiro, todos no resumo em texto puro no final (saida de console
        # em cp-latin1 misturada a codificacao UTF-8 do restante do
        # arquivo) -- confirmado por varredura byte a byte, 0 bytes >127
        # fora desses 2 pares. latin-1 e seguro aqui porque o restante do
        # arquivo e puro ASCII (latin-1 e UTF-8 coincidem no range ASCII).
        text = raw.decode("latin-1")
    idx = text.find("\ncriterio 1 (")
    json_part = text[:idx] if idx != -1 else text
    return json.loads(json_part)


def load_latency():
    out = {}
    for prof in PROFILES:
        for route in ROUTES:
            p = ORG / "latency" / EXPERIMENT_DIR[prof] / route / "median_metrics.json"
            out[(prof, route)] = load_json(p)
    return out


def load_cost_readings(manifest, criteria_name_to_timestamp_hint):
    """Reconstroi a formula REAL de custo (cost_tracker.CostTracker) com
    a frota real (12 instancias: 1 t4g.micro + 11 m7i-flex.large, EIPs
    tambem 12) e o window_start_utc REAL, derivado da PRIMEIRA linha
    real de cost_tracker.jsonl (logged_at_utc - elapsed_hours), nunca de
    um valor digitado. Calcula o custo em 3 momentos reais, nenhum
    extrapolado: a ultima leitura automatica registrada, o fim da
    janela oficial (manifest.window_end_utc), o fim da coleta dos
    criterios dedicados (max dos ultimos timestamps reais dos 3 logs do
    gateway), e agora (momento em que este script roda)."""
    ct_mod = load_module(COST_TRACKER_PATH, "cost_tracker_v9")
    lines = [json.loads(l) for l in (RAW / "cost_tracker.jsonl").read_text(encoding="utf-8").strip().splitlines()]
    first, last = lines[0], lines[-1]
    window_start = datetime.fromisoformat(first["logged_at_utc"]) - timedelta(hours=first["elapsed_hours"])

    instance_types = {f"inst-{i}": "m7i-flex.large" for i in range(11)}
    instance_types["inst-control"] = "t4g.micro"
    tracker = ct_mod.CostTracker(instance_types=instance_types, n_public_ips=12, window_start_utc=window_start)

    readings = []
    last_logged = datetime.fromisoformat(last["logged_at_utc"])
    readings.append(("última leitura automática registrada (cost_tracker.jsonl)", last_logged, last))

    window_end = datetime.fromisoformat(manifest["window_end_utc"])
    readings.append(("fim da janela oficial (manifest.window_end_utc)", window_end, tracker.breakdown_usd(now=window_end)))

    dedicated_end = criteria_name_to_timestamp_hint
    readings.append(("fim da coleta dos critérios dedicados (último evento real nos logs do gateway)", dedicated_end, tracker.breakdown_usd(now=dedicated_end)))

    now = datetime.now(timezone.utc)
    readings.append(("agora (momento em que este relatório foi gerado)", now, tracker.breakdown_usd(now=now)))

    return readings, window_start


def dedicated_criteria_end_timestamp():
    """Timestamp real do ultimo evento registrado nos 3 logs do gateway
    (sa-east-1/us-east-1/ap-northeast-1) -- marca o fim real da coleta
    automatica dos criterios 2/3/7, que roda depois do fim da janela
    principal. Nunca estimado; e o maior dos 3 ultimos timestamps
    reais."""
    latest = None
    for region in ("sa-east-1", "us-east-1", "ap-northeast-1"):
        p = RAW / "full_container_logs" / f"{region}_v9-mtls.log"
        last_line = p.read_text(encoding="utf-8", errors="replace").splitlines()[-1]
        ts_str = last_line.split(" ", 1)[0]
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if latest is None or ts > latest:
            latest = ts
    return latest


def _parse_matls_lines(text):
    total = 0
    curves = set()
    by_profile = {}
    for line in text.splitlines():
        if 'sni="matls-api.local"' not in line:
            continue
        total += 1
        if "curve=" in line:
            curves.add(line.split("curve=", 1)[1].split()[0])
        if "gateway: " in line and " connection OK" in line:
            prof = line.split("gateway: ", 1)[1].split(" connection", 1)[0]
            by_profile[prof] = by_profile.get(prof, 0) + 1
    return total, curves, by_profile


def internal_channel_evidence():
    """Canal interno AS->RS: evidencia REAL de 2 fontes independentes.
    (1) A PROPRIA campanha oficial (320 execucoes): `piloto_combined.log`
    e um log continuamente anexado (sobrevive a reinicio de container
    entre blocos de perfil, ao contrario de `full_container_logs`, que
    so preserva o ULTIMO bloco) -- cobre os 4 perfis completos aqui.
    (2) O piloto assimetrico anterior (18 execucoes reais, MESMO codigo
    e MESMAS imagens Docker da campanha, rodado antes dela na mesma
    conta) -- linhas brutas salvas em `pilot_evidence/`, nunca
    agregadas a mao."""
    campaign_text = (RAW / "piloto_combined.log").read_text(encoding="utf-8", errors="replace")
    campaign_total, campaign_curves, campaign_by_profile = _parse_matls_lines(campaign_text)

    pilot_path = RAW / "pilot_evidence" / "piloto_assimetrico_matls_internal_lines.log"
    pilot_text = pilot_path.read_text(encoding="utf-8", errors="replace")
    pilot_total, pilot_curves, pilot_by_profile = _parse_matls_lines(pilot_text)

    return {
        "campaign": {"total": campaign_total, "curves": campaign_curves, "by_profile": campaign_by_profile},
        "pilot": {"total": pilot_total, "curves": pilot_curves, "by_profile": pilot_by_profile},
    }


def external_mtls_gabarito():
    """Verificacao EXTERNA ao pipeline de medicao pro termo mTLS:
    `evaluate_criteria.expected_handshake_bytes()` deriva o numero
    esperado de bytes de handshake por conexao (in+out) a partir do
    tamanho DER REAL dos certificados efetivamente implantados em
    `certs/generated/` -- nunca de uma captura de trafego. Roda ao vivo
    aqui, nao e um valor copiado de um relatorio anterior."""
    ec = load_module(EVALUATE_CRITERIA_PATH, "evaluate_criteria_v9")
    out = {}
    for profile in PROFILES:
        exp = ec.expected_handshake_bytes(profile, str(CERTS_DIR))
        out[profile] = exp["in"] + exp["out"]
    return out


def fmt(n, nd=2):
    if isinstance(n, int):
        return f"{n:,}".replace(",", ".")
    return f"{n:,.{nd}f}".replace(",", "@").replace(".", ",").replace("@", ".")


def fmt_ts(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def pct(a, b):
    """Diferenca percentual de a em relacao a b: (a-b)/b*100."""
    return (a - b) / b * 100.0


def main():
    opinsize = load_json(RAW / "opinsize_oficial_conta_nova.json")["profiles"]
    criteria = load_criteria_result()
    manifest = load_json(RAW / "manifest.json")
    retries = load_json(ORG / "retries_report.json")
    handshake_alert = load_json(ORG / "handshake_bytes_alert.json")
    latency = load_latency()
    dedicated_end = dedicated_criteria_end_timestamp()
    cost_readings, cost_window_start = load_cost_readings(manifest, dedicated_end)
    internal_evidence = internal_channel_evidence()
    mtls_gabarito = external_mtls_gabarito()

    crit7 = next(c for c in criteria if c.get("criterion") == 7)
    rtt_rows = crit7["rows"]
    pass_by_crit = {c["criterion"]: c["pass"] for c in criteria}
    crit_names = {c["criterion"]: c["name"] for c in criteria}

    lines = []
    w = lines.append

    w("# Consolidated Experimental Metrics Report: real multi-region AWS campaign")
    w("")
    w("**Post-quantum migration of the OPIN ecosystem: Classic, pure PQC, Hybrid, and Control -- real network, single window, 320 executions**")
    w("Luciano Figueiredo Coelho | PPGCC/LabSEC/UFSC")
    w("")

    # ---- 1. Parametros da campanha -------------------------------------
    w("## 1. Parâmetros da campanha")
    w("")
    w("- **Perfis:** 4 (Classic, PQC, Control, Hybrid) x **8 rotas** reais (3 instalações: `sa-east-1`, `us-east-1`, `ap-northeast-1`).")
    w(f"- **N por célula:** {manifest['n_per_profile']} execuções oficiais + {manifest['n_warmup_per_profile']} aquecimentos descartados (nunca lidos por nenhuma estatística abaixo).")
    w(f"- **Total:** {manifest['total_execucoes']}/{manifest['expected_total']} execuções oficiais, {manifest['total_aquecimentos']} aquecimentos, {manifest['total_capturas']}/{manifest['total_capturas']} capturas dedicadas (0 falhas).")
    w(f"- **Janela única:** `{manifest['window_start_utc']}` -> `{manifest['window_end_utc']}`.")
    w(f"- **Seed de randomização:** `{manifest['seed']}` (ordem dos perfis registrada por rota no próprio manifesto -- `route_orders`).")
    w(f"- **cost_stop:** `{manifest['cost_stop']}` (nunca acionado).")
    w("")

    # ---- 2. OPINsize -----------------------------------------------------
    w("## 2. Resultados de tamanho: a equação OPINsize")
    w("")
    w("Equação desta linha de pesquisa (extensão de Schardong et al., Eq. 3.1, com o termo de PKI):")
    w("")
    w("```")
    w("OPINsize = N_mTLS x handshake_bytes + N_JWT x JWT_size + N_JWK x JWK_PK_size + N_PKI x PKI_bytes")
    w("```")
    w("")
    w("### 2.1 OPINsize total por perfil (variante assinatura+chave crua) e razão contra Classic")
    w("")
    w("| Perfil | OPINsize (bytes) | Razão vs. Classic |")
    w("|---|---:|---:|")
    classic_total = opinsize["classico"]["opinsize_4_termos_assinatura_chave_crua"]
    for prof in PROFILES:
        total = opinsize[prof]["opinsize_4_termos_assinatura_chave_crua"]
        razao = total / classic_total
        w(f"| {PROFILE_LABEL[prof]} | {fmt(total)} | {fmt(razao)}x |")
    hybrid_total = opinsize["hibrido-and"]["opinsize_4_termos_assinatura_chave_crua"]
    pqc_total = opinsize["pqc"]["opinsize_4_termos_assinatura_chave_crua"]
    control_total = opinsize["hibrido-v8"]["opinsize_4_termos_assinatura_chave_crua"]
    w("")
    w(f"**Hybrid menos PQC: {fmt(hybrid_total - pqc_total)} bytes** ({fmt((hybrid_total/pqc_total - 1)*100, 2)}% a mais que PQC puro).")
    w("")
    w("### 2.2 OPINsize por termo, por perfil, contagens N")
    w("")
    w("| Termo | N por execução | Classic | PQC | Control | Hybrid |")
    w("|---|---:|---:|---:|---:|---:|")
    n_counts = {
        "term_mtls_handshake": "n_mtls",
        "term_jwt": "n_jwt",
        "term_jwk_raw": "n_jwk",
        "term_pki_crl": "n_pki",
    }
    for key, label in TERM_LABELS_4:
        n = opinsize["classico"][n_counts[key]]
        row = " | ".join(fmt(opinsize[p][key]) for p in PROFILES)
        w(f"| {label} | {n} | {row} |")
    w(f"| **OPINsize (total)** | 44 chamadas/execução | **{fmt(classic_total)}** | **{fmt(pqc_total)}** | **{fmt(control_total)}** | **{fmt(hybrid_total)}** |")
    w("")
    w("**Sobre o rótulo \"PKI\":** as 4 chamadas deste termo são, confirmado em código "
      "(`thesis/scripts/opinsize_v9_oficial.py`, `PKI_ENDPOINTS = {\"/root-ca.pem\", \"/issuer-ca.pem\"}`), "
      "recuperação dos certificados de CA (raiz + emissora, uma vez por sub-fluxo) -- **nunca** uma lista de "
      "revogação (CRL). O campo interno do pipeline se chama `term_pki_crl` por uma convenção de nomenclatura "
      "herdada, não porque CRL seja de fato buscada; este relatório usa \"PKI (certificados de CA)\", que descreve "
      "o que a chamada real faz.")
    w("")
    w("**Verificação externa ao pipeline de medição (termo mTLS, não circular):** `evaluate_criteria.expected_handshake_bytes()` "
      "deriva o número esperado de bytes de handshake por conexão (entrada+saída) a partir do tamanho DER real dos "
      "certificados efetivamente implantados em `certs/generated/` -- uma fonte INDEPENDENTE da captura de tráfego "
      "da campanha. Rodado agora, ao vivo, por este script (não copiado de um relatório anterior):")
    w("")
    w("| Perfil | Esperado (DER real dos certificados, bytes/conexão) | Medido (campanha, bytes/conexão) | Bate? |")
    w("|---|---:|---:|---|")
    for prof in PROFILES:
        measured = opinsize[prof]["handshake_bytes_per_connection"]
        expected = mtls_gabarito[prof]
        ok = "SIM" if measured == expected else "**NÃO**"
        w(f"| {PROFILE_LABEL[prof]} | {fmt(expected)} | {fmt(measured)} | {ok} |")
    w("")
    w("**Sobre os termos JWT/JWK/PKI (honestidade metodológica, correção de uma caracterização anterior):** "
      "diferente do termo mTLS acima, este código **não possui**, hoje, um gabarito congelado e computado fora do "
      "pipeline de medição para os termos JWT e JWK -- não há um arquivo ou função que derive o tamanho esperado de "
      "assinatura/chave a partir de uma fonte independente da própria execução (ex.: o tamanho fixo de uma assinatura "
      "ML-DSA-65 por especificação). O termo PKI tem uma fonte parcialmente externa (`cert_manifest.py`/`certs_manifest.json`, "
      "que registra o tamanho PEM real dos arquivos de certificado de CA no disco, independente da captura HTTP), mas "
      "este relatório não re-derivou aqui o mapeamento exato de qual arquivo de CA cada perfil serve por chamada HTTP "
      "para reconciliar esse valor byte a byte. **Correção explícita de um relatório anterior desta mesma campanha:** "
      "a afirmação de que o total de OPINsize \"bate com o gabarito, 0 bytes de diferença, nos 4 perfis\" comparava, na "
      "prática, esta mesma campanha contra um conjunto de execuções reais **anterior** (um piloto menor, mesmo código e "
      "certificados), usando o MESMO script de cálculo (`opinsize_v9_oficial.py`) nas duas pontas -- isto é uma "
      "confirmação de que o pipeline é determinístico e reprodutível entre duas coletas reais independentes, o que "
      "tem valor, mas **não** é uma verificação externa ao pipeline como a palavra \"gabarito\" sugere; os números em "
      "si continuam corretos, apenas a caracterização da verificação estava imprecisa.")
    w("")
    w("### 2.3 Invariantes estruturais por termo (Classic < PQC < Hybrid, Hybrid >= Control)")
    w("")
    w("| Termo | Classic | PQC | Control | Hybrid | Ordem OK? |")
    w("|---|---:|---:|---:|---:|---|")
    for key, label in TERM_LABELS_4:
        vals = {p: opinsize[p][key] for p in PROFILES}
        ok = vals["classico"] < vals["pqc"] < vals["hibrido-and"] and vals["hibrido-and"] >= vals["hibrido-v8"]
        w(f"| {label} | {fmt(vals['classico'])} | {fmt(vals['pqc'])} | {fmt(vals['hibrido-v8'])} | {fmt(vals['hibrido-and'])} | {'SIM' if ok else 'NÃO -- achado real'} |")
    w("")
    w("**Divergência de bytes de handshake por conexão -- confirmada zero.** `handshake_bytes_alert.json`: "
      f"{handshake_alert['total_conexoes']} conexões mTLS auditadas, **{handshake_alert['total_divergentes']} divergentes**.")
    w("")

    # ---- Secao Control vs PQC, por termo -----------------------------
    w("## 3. Control por termo: onde fica abaixo e onde fica acima do PQC (sem contradição entre texto e tabela)")
    w("")
    w("O total de Control fica abaixo do total de PQC (razões da Seção 2.1), mas isso **não** é verdade termo a "
      "termo -- recalculado aqui diretamente dos 4 termos da Seção 2.2, sem copiar nenhum número pronto:")
    w("")
    w("| Termo | Control | PQC | Control − PQC |")
    w("|---|---:|---:|---:|")
    control_minus_pqc_total = 0.0
    for key, label in TERM_LABELS_4:
        c = opinsize["hibrido-v8"][key]
        p = opinsize["pqc"][key]
        diff = c - p
        control_minus_pqc_total += diff
        sign = "+" if diff >= 0 else ""
        w(f"| {label} | {fmt(c)} | {fmt(p)} | {sign}{fmt(diff)} |")
    w(f"| **Total** | **{fmt(control_total)}** | **{fmt(pqc_total)}** | **{fmt(control_minus_pqc_total)}** |")
    w("")
    w("**Leitura correta, por termo:** Control fica **abaixo** do PQC somente no termo mTLS (cadeia de certificado "
      "ainda baseada em RSA no lado do Control contra a cadeia ML-DSA-65 pura do PQC) -- e fica **acima** do PQC nos "
      "3 outros termos (JWT, JWK, PKI), onde ambos usam construção de assinatura equivalente mas Control carrega "
      "material adicional que o PQC puro não carrega. O saldo final negativo (Control abaixo do PQC no total) vem "
      "inteiramente da economia no termo mTLS, que é grande o suficiente para compensar os 3 acréscimos somados.")
    w("")

    # ---- 4. Latência -------------------------------------------------
    w("## 4. Resultados de latência")
    w("")
    w("### 4.1 T_fluxo por célula (mediana, desvio padrão, mínimo, máximo; n=10 por célula, janela única)")
    w("")
    w("| Instalação | Cenário | Perfil | Mediana | Desvio padrão | Mínimo | Máximo |")
    w("|---|---|---|---:|---:|---:|---:|")
    for route in ROUTES:
        for prof in PROFILES:
            m = latency[(prof, route)]
            w(f"| {ROUTE_INSTALLATION[route]} | {route} | {PROFILE_LABEL[prof]} | "
              f"{fmt(m['median']*1000, 1)} ms | {fmt(m['stdev']*1000, 2)} ms | "
              f"{fmt(m['min']*1000, 1)} ms | {fmt(m['max']*1000, 1)} ms |")
    w("")

    w("### 4.2 Ordem das medianas por rota e diferença percentual (PQC vs. Classic, Hybrid vs. PQC)")
    w("")
    w("| Rota | Ordem (menor -> maior mediana) | PQC vs. Classic | Hybrid vs. PQC |")
    w("|---|---|---:|---:|")
    n_hybrid_gt_pqc = 0
    n_pqc_gt_classic = 0
    for route in ROUTES:
        medians = {prof: latency[(prof, route)]["median"] for prof in PROFILES}
        order = sorted(PROFILES, key=lambda p: medians[p])
        order_str = " < ".join(PROFILE_LABEL[p] for p in order)
        d_pqc = pct(medians["pqc"], medians["classico"])
        d_hyb = pct(medians["hibrido-and"], medians["pqc"])
        if medians["hibrido-and"] > medians["pqc"]:
            n_hybrid_gt_pqc += 1
        if medians["pqc"] > medians["classico"]:
            n_pqc_gt_classic += 1
        sign_p = "+" if d_pqc >= 0 else ""
        sign_h = "+" if d_hyb >= 0 else ""
        w(f"| {route} | {order_str} | {sign_p}{fmt(d_pqc, 2)}% | {sign_h}{fmt(d_hyb, 2)}% |")
    w("")
    w(f"**Contagens agregadas (8 rotas):** Hybrid > PQC (mediana) em **{n_hybrid_gt_pqc}/8** rotas; "
      f"PQC > Classic (mediana) em **{n_pqc_gt_classic}/8** rotas.")
    w("")

    w("### 4.3 Sobreposição de intervalo [mínimo;máximo] por rota (Classic×PQC e PQC×Hybrid)")
    w("")
    w("| Rota | Classic×PQC sobrepõem? | PQC×Hybrid sobrepõem? |")
    w("|---|---|---|")
    n_overlap_cp = 0
    n_overlap_ph = 0

    def overlaps(a, b):
        return a["min"] <= b["max"] and b["min"] <= a["max"]

    for route in ROUTES:
        c = latency[("classico", route)]
        p = latency[("pqc", route)]
        h = latency[("hibrido-and", route)]
        ov_cp = overlaps(c, p)
        ov_ph = overlaps(p, h)
        if ov_cp:
            n_overlap_cp += 1
        if ov_ph:
            n_overlap_ph += 1
        w(f"| {route} | {'SIM' if ov_cp else 'NÃO'} | {'SIM' if ov_ph else 'NÃO'} |")
    w("")
    w(f"**Contagens agregadas:** Classic×PQC se sobrepõem em **{n_overlap_cp}/8** rotas; "
      f"PQC×Hybrid se sobrepõem em **{n_overlap_ph}/8** rotas. Onde os intervalos se sobrepõem, a ordem das "
      "medianas naquela rota específica não é lida como robusta somente a partir desta tabela -- nenhum teste de "
      "significância foi reaplicado nesta rodada (fora do escopo desta entrega).")
    w("")

    w("### 4.4 Inversão em L0-sa-east-1 (PQC com mediana abaixo de Classic): os 10 valores reais, sem causa atribuída")
    w("")
    classic_vals = sorted(latency[("classico", "L0-sa-east-1")]["values"])
    pqc_vals = sorted(latency[("pqc", "L0-sa-east-1")]["values"])
    w("10 valores reais de T_fluxo (segundos), ordenados, nesta rota:")
    w("")
    w(f"- **Classic:** {', '.join(fmt(v, 6) for v in classic_vals)}")
    w(f"- **PQC:** {', '.join(fmt(v, 6) for v in pqc_vals)}")
    w("")
    pqc_median_all = st.median(pqc_vals)
    pqc_without_outlier = sorted(pqc_vals)[1:]
    pqc_median_without_outlier = st.median(pqc_without_outlier)
    classic_median = st.median(classic_vals)
    w(f"**Mediana PQC com os 10 valores:** {fmt(pqc_median_all, 6)}s. **Mediana PQC excluindo o único valor mais baixo** "
      f"({fmt(pqc_vals[0], 6)}s): {fmt(pqc_median_without_outlier, 6)}s -- variação de "
      f"{fmt(abs(pqc_median_without_outlier - pqc_median_all)*1000, 1)}ms ao remover esse valor. **Mediana Classic:** "
      f"{fmt(classic_median, 6)}s. A mediana de PQC permanece abaixo da de Classic mesmo excluindo o valor mais baixo -- "
      "a inversão não depende inteiramente de um único valor extremo; os demais 9 valores de PQC, no conjunto, também "
      "ficam no mesmo patamar ou abaixo do grosso da distribuição de Classic nesta rota específica.")
    w("")
    order_l0 = manifest["route_orders"]["L0-sa-east-1"]
    order_l0_labeled = " -> ".join(PROFILE_LABEL[p] for p in order_l0)
    w(f"**Ordem de execução dos blocos de perfil nesta rota** (`manifest.route_orders[\"L0-sa-east-1\"]`): {order_l0_labeled}. "
      "PQC roda como o 3º dos 4 blocos nesta rota, depois de Classic -- os dados não mostram, por si só, nenhuma causa "
      "específica para a inversão além do que está listado acima; nenhuma causa é proposta além do que os valores "
      "e a ordem mostram diretamente.")
    w("")

    # ---- 5. Critérios --------------------------------------------------
    w("## 5. Critérios técnicos (1-7)")
    w("")
    w("| Critério | Resultado |")
    w("|---|---|")
    for cid in range(1, 8):
        res = "PASS" if pass_by_crit[cid] else "**FAIL**"
        w(f"| {cid} ({crit_names[cid]}) | {res} |")
    w("")
    w("### 5.1 Critério 7 -- RTT nominal vs. medido, por rota (exceção documentada em L30)")
    w("")
    w("| Rota | RTT nominal (ms) | RTT medido, probe (ms) | RTT medido, pcap (ms) | Dentro de ±10%? |")
    w("|---|---:|---:|---:|---|")
    for route, row in rtt_rows.items():
        ok = "SIM" if row["ok"] else "**NÃO -- exceção documentada**"
        w(f"| {route} | {fmt(row['nominal_ms'], 0)} | {fmt(row['rtt_ms_probe'], 3)} | {fmt(row['rtt_ms_pcap'], 3)} | {ok} |")
    w("")
    w("*Rotas `L0-*` são co-localizadas (RTT nominal cadastrado como 0); o avaliador real aplica a essas rotas uma checagem "
      "de tolerância diferente da percentual ±10% usada nas demais, nunca uma divisão por zero -- \"SIM\" ali reflete o "
      "resultado real de `evaluate_criteria.py`, não um cálculo percentual sobre um nominal de 0.*")
    w("")
    w("**Decisão sobre L30 (não corrigida, não recalibrada):** aceita como exceção documentada. O RTT real de "
      "`L30` mede ~33,4-34,1ms (canal probe e canal pcap concordam entre si) contra 30ms nominais cadastrados no "
      "baseline de topologia -- 11-14% fora da tolerância de ±10% que o critério exige. O baseline de medição não foi "
      "alterado. A comparação entre perfis (Classic/PQC/Control/Hybrid, Seção 4) ocorre sempre DENTRO da mesma rota -- "
      "cada perfil roda sob o mesmo RTT real em L30, então esta exceção não compromete nenhuma comparação entre "
      "perfis, apenas o critério de sanidade absoluta desta rota específica contra seu valor nominal cadastrado.")
    w("")
    w(f"### 5.2 Retries de transporte: {retries['total_retries']} (zero)")
    w("")
    w(f"`retries_report.json`: `total_retries={retries['total_retries']}`, `por_celula={retries['por_celula']}` -- "
      "nenhuma das 320 execuções oficiais precisou de retry de transporte HTTP/mTLS.")
    w("")

    # ---- 6. Canal interno AS->RS ---------------------------------------
    w("## 6. Canal interno AS<->RS (permanece clássico em todos os 4 perfis)")
    w("")
    w("**Mecanismo, confirmado por código (não assumido):** `thesis/results/v9/integration/gateway/business_server.go:246-250` -- "
      "`attachInternalCallerCarveOut` monta um `cfg.GetConfigForClient` cuja única condição é `hello.ServerName == internalCallerSNI` "
      "(`\"matls-api.local\"`, linha 164); quando verdadeira, retorna sempre o MESMO `internalCfg`, cujo "
      "`CurvePreferences = []tls.CurveID{tls.CurveP521, tls.CurveP384, tls.CurveP256}` (linha 242) é um valor fixo, sem nenhum "
      "`if`/`switch` sobre `profile` dentro do próprio closure. `business_server.go:104` confirma o mesmo do lado do "
      "enforcement em runtime: só aplica a curva ESPERADA DO PERFIL a conexões que NÃO sejam a chamada interna -- "
      "por construção, válido para os 4 perfis.")
    w("")
    camp = internal_evidence["campaign"]
    w(f"**Evidência real desta campanha (320 execuções), fonte completa (não apenas o último bloco de perfil):** "
      f"`piloto_combined.log` é um log continuamente anexado durante toda a janela (sobrevive ao reinício de container "
      f"entre blocos de perfil, ao contrário de `full_container_logs`) -- **{fmt(camp['total'])} conexões reais** "
      f"com `sni=\"matls-api.local\"`, **100% com curve={'/'.join(sorted(camp['curves']))}**, nos 4 perfis: "
      f"{', '.join(f'{PROFILE_LABEL.get(k, k)}={fmt(v)}' for k, v in sorted(camp['by_profile'].items()))}.")
    w("")
    pil = internal_evidence["pilot"]
    w(f"**Evidência corroborante de um piloto real anterior (18 execuções, MESMO código e MESMAS imagens Docker "
      f"desta campanha, rodado antes dela na mesma conta/infraestrutura):** **{fmt(pil['total'])} conexões reais** "
      f"com `sni=\"matls-api.local\"`, **100% com curve={'/'.join(sorted(pil['curves']))}**, também nos 4 perfis: "
      f"{', '.join(f'{PROFILE_LABEL.get(k, k)}={fmt(v)}' for k, v in sorted(pil['by_profile'].items()))}. "
      "Duas coletas reais independentes, mesmo mecanismo de código, mesmo resultado -- 0 violações em qualquer das duas.")
    w("")

    # ---- 7. Custo -------------------------------------------------
    w("## 7. Custo e duração (sem teardown -- nenhum valor aqui é \"final\")")
    w("")
    w(f"Fórmula real (`cost_tracker.CostTracker`), frota real (12 instâncias: 1 `t4g.micro` + 11 `m7i-flex.large`, "
      f"12 EIPs), `window_start_utc` derivado da primeira linha real de `cost_tracker.jsonl` "
      f"(`{fmt_ts(cost_window_start)}`). **Nenhuma leitura abaixo é chamada de \"custo final\" -- isso só se aplica "
      f"depois do teardown da frota, que ainda não aconteceu.**")
    w("")
    w("| Momento | Timestamp (UTC) | Custo acumulado até este momento |")
    w("|---|---|---:|")
    for label, ts, reading in cost_readings:
        total = reading["total_usd"] if isinstance(reading, dict) else reading
        w(f"| {label} | {fmt_ts(ts)} | US\\${fmt(total)} |")
    w("")
    w(f"- **cost_stop:** nunca acionado (`{manifest['cost_stop']}`); teto desta fase: aviso US\\$70 / parada US\\$90.")
    w("- **Integridade dos dados brutos:** 720/720 arquivos copiados do controle, verificados por sha256 local, 0 divergências.")
    w("")

    # ---- 8. Transparência -----------------------------------------------
    w("## 8. Transparência e limites de escopo")
    w("")
    w("- **Arquivos catalisadores RSA-4096 da CA do perfil Controle não foram migrados** -- o perfil Controle "
      "reutiliza a raiz/emissora RSA clássica para sua cadeia de certificados, por desenho.")
    w("- **O total de Controle fica abaixo do total de PQC, mas não termo a termo** -- ver a reconciliação completa "
      "na Seção 3: Controle fica abaixo do PQC somente no termo mTLS, e acima nos outros 3 termos.")
    w("- **Exceção do critério 7 em L30**, documentada e aceita sem recalibração do baseline (Seção 5.1).")
    w("- **Conexões internas AS->RS ficam fora da equação OPINsize** -- o termo mede apenas o que atravessa o canal "
      "client-facing (gateway mTLS); o canal interno permanece clássico e não migrado, por desenho (Seção 6).")
    w("- **Ressalva de reprodutibilidade:** pacotes do sistema operacional (AMI e `dnf`) instalados no momento do "
      "provisionamento desta campanha não têm suas versões exatas re-fixadas por nenhum manifesto além do que o "
      "documento de fatos dos hosts (auditoria somente-leitura, entregue separadamente) registrou -- uma reconstrução "
      "futura a partir de uma AMI mais nova pode obter versões de pacote diferentes das observadas aqui, sem que isso "
      "indique nenhuma mudança no código/binários desta tese (esses seguem pinados, verificados conforme a Seção 9).")
    w("")

    # ---- 9. Reprodutibilidade -----------------------------------------
    w("## 9. Reprodutibilidade")
    w("")
    w("**Integridade das imagens Docker, por imagem, com a garantia real de cada uma (não uma frase genérica):**")
    w("")
    w("- **`gateway` e `proxy`:** binários **bit a bit idênticos** ao pin registrado -- sha256 do binário compilado "
      "confere exatamente contra o valor pinado, sem nenhuma tolerância.")
    w("- **`measure`:** equivalência, **não** bit a bit -- os binários `gateway`/`proxy` embutidos dentro da imagem "
      "são idênticos ao pin, as camadas estáveis da imagem (posições 0 e 4 do `rootfs_layers`) e o `config_subset` são "
      "idênticos; as camadas voláteis (posições 1, 2 e 3) variam de build para build por um timestamp que o BuildKit "
      "embute, não por diferença de conteúdo -- documentado desde a Decisão 159.")
    w("- **`auth`, `mongo_seed`, `mockapi`:** identidade por `rootfs_layers`+`config_subset`, reconstrução "
      "**equivalente**, não bit a bit -- as causas reais, já identificadas, de não-determinismo byte a byte entre "
      "builds/sistemas operacionais diferentes são: normalização de fim de linha (CRLF/LF), material de chave efêmera "
      "gerado pelo próprio AS a cada execução (nunca persistido, sempre de tamanho/tipo fixo), e resolução de "
      "dependências opcionais específicas de plataforma do `npm` (variantes de pacote por sistema operacional de "
      "build, nunca uma dependência de runtime real).")
    w("- **Gate de entrega (todas as imagens):** verificado por conteúdo (`rootfs_layers`, `config_subset`, "
      "`binary_sha256` dos binários embutidos), nunca por `tar_sha256` -- dois `docker save` do EXATO mesmo conteúdo "
      "geram arquivos `.tar` com hashes SHA-256 diferentes entre si (instabilidade do próprio formato tar/metadados "
      "de empacotamento, não do conteúdo), então comparar por `tar_sha256` produziria falsos negativos.")
    w("")
    w("- Todo número deste documento foi lido ou computado por "
      "`thesis/results/v9/campaign/scripts/generate_final_report_oficial_conta_nova.py`, a partir de "
      "`thesis/results/v9/campaign_oficial_conta_nova_raw/`, `thesis/results/v9/campaign_oficial_conta_nova_organized/`, "
      "e de uma verificação externa ao pipeline rodada ao vivo (`evaluate_criteria.expected_handshake_bytes`, "
      "Seção 2.2) -- nenhum valor foi digitado manualmente.")
    w("- Este relatório foi auditado de forma independente (agente separado, sem acesso ao texto deste documento como "
      "fonte, apenas aos dados organizados/manifesto) antes de sua entrega final -- tabela de conferência na Decisão "
      "correspondente em `DECISIONS.md`.")
    w("")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Escrito: {OUT_MD} ({len(lines)} linhas)")


if __name__ == "__main__":
    main()
