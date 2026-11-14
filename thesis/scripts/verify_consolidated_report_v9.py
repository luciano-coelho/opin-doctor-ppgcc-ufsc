#!/usr/bin/env python3
"""v9, campanha oficial (Decisao 143): recomputa, direto dos dados
brutos em thesis/results/v9_pre_pki_fix/campaign/oficial_raw/
oficial_out/, TODO numero que thesis/results/v9_pre_pki_fix/
Consolidated_Metrics_Report_FINAL.md usa -- nunca le o relatorio,
nunca confia em memoria de sessao anterior. Imprime cada numero com
um rotulo identico ao do relatorio, pra conferencia visual linha a
linha. Sem argumentos: caminhos fixos, sempre os mesmos dados oficiais
da janela v3.

BASE apontava pra thesis/results/v9/... antes da Decisao 150 (achado
real: a correcao do PKI_bytes do Hybrid, Decisao 148, tornou os dados
da janela v3 nao-oficiais) -- os dados e o relatorio que este script
verifica foram movidos pra thesis/results/v9_pre_pki_fix/ (so os
dados, nunca o codigo de infraestrutura, que continua em thesis/
results/v9/), e este caminho foi atualizado junto, senao o script
apontaria pra um diretorio que nao existe mais."""
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "results" / "v9_pre_pki_fix" / "campaign" / "oficial_raw" / "oficial_out"
CALLS_JSON = BASE / "piloto_calls.json"
COMBINED_LOG = BASE / "piloto_combined.log"
CAPTURAS_DIR = BASE / "criterio1_capturas"
MANIFEST = BASE / "manifest.json"

PROFILES = ["classico", "pqc", "hibrido-and", "hibrido-v8"]
NOMINAL_RTT_MS = {
    "L0-sa-east-1": 0, "L123": 123, "L219": 219, "L325": 325,
    "L0-us-east-1": 0, "L14": 14, "L0-ap-northeast-1": 0, "L30": 30,
}


def load_calls():
    return json.loads(CALLS_JSON.read_text(encoding="utf-8"))


def check_counts(execs):
    print("\n=== Contagens do fluxo (44/28/6/4/4) ===")
    n_calls = {len(e["insurance"]) for e in execs}
    n_jwt = {sum(len(c.get("jwt_sig_breakdown", [])) for c in e["insurance"]) for e in execs}
    print("n_calls distintos:", n_calls)
    print("n_jwt distintos:", n_jwt)
    assert n_calls == {44}, n_calls
    assert n_jwt == {28}, n_jwt
    print("OK: 44 chamadas e 28 JWTs, constantes nas", len(execs), "execucoes")


def tfluxo_table(execs):
    print("\n=== T_fluxo por celula (mediana/min/max/desvio) ===")
    by_cell = defaultdict(list)
    for e in execs:
        t0 = datetime.fromisoformat(e["start_utc"])
        t1 = datetime.fromisoformat(e["end_utc"])
        by_cell[(e["profile"], e["route"])].append((t1 - t0).total_seconds())
    for (profile, route), vals in sorted(by_cell.items()):
        med, mn, mx = statistics.median(vals), min(vals), max(vals)
        sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
        print(f"{profile:12s} {route:18s} N={len(vals):2d} mediana={med:.3f}s min={mn:.3f}s max={mx:.3f}s dp={sd:.3f}s")


def retries(execs, warmups):
    print("\n=== Retries ===")
    r = sum(1 for e in execs if e.get("retry_attempts", 1) > 1)
    rw = sum(1 for e in warmups if e.get("retry_attempts", 1) > 1)
    print(f"execucoes com retry: {r}/{len(execs)} | aquecimentos com retry: {rw}/{len(warmups)}")


def opinsize():
    print("\n=== OPINsize (recomputado) ===")
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import opinsize_v9_oficial as op
    report = op.analyze(CALLS_JSON, CAPTURAS_DIR, COMBINED_LOG)
    for p in PROFILES:
        v = report["profiles"][p]
        print(f"{p:12s} handshake={v['handshake_bytes_per_connection']} "
              f"jwt_sig={v['jwt_sig_bytes_avg']} jwt_full={v['jwt_full_token_bytes_avg']} "
              f"jwk_raw={v['jwk_raw_key_bytes_avg']} jwk_envelope={v['jwk_response_bytes_avg']} "
              f"pki={v['pki_response_bytes_avg']} "
              f"3termos(sig+chave_crua,PRINCIPAL)={v['opinsize_3_termos_assinatura_chave_crua_comparavel_schardong_eq3_1']} "
              f"4termos(sig+chave_crua,PRINCIPAL)={v['opinsize_4_termos_assinatura_chave_crua']} "
              f"3termos(full+envelope,complementar)={v['opinsize_3_termos_token_completo']} "
              f"4termos(full+envelope,complementar)={v['opinsize_4_termos_token_completo']}")
    return report


def handshake_composition():
    print("\n=== Composicao do handshake por mensagem (stream 0, L0-ap-northeast-1) ===")
    for profile in PROFILES:
        fp = CAPTURAS_DIR / f"{profile}_L0-ap-northeast-1.log"
        lines = fp.read_text(encoding="utf-8").splitlines()[2:]
        rows = []
        for line in lines:
            parts = line.split("\t")
            if len(parts) < 6:
                continue
            stream, types, sizes = parts[1], parts[4], parts[5]
            if stream != "0" or not types:
                continue
            rows.append((types, sizes))
        print(profile, rows)


def dual_authenticated_check():
    """Pedido do autor (item 3, acrescentar ao piloto): confere, direto
    do log combinado real (nunca de um resumo por execucao), que TODAS
    as conexoes hibrido-and client-facing (sni="mtls" -- as 6 por
    execucao, nao so uma representante) tem dualAuthenticated=true.

    Achado ao vivo escrevendo este check: o log TAMBEM tem linhas
    "hibrido-and connection OK" pro carve-out interno (sni=
    "matls-api.local", business_server.go:107 as EXCLUI da exigencia
    de dualAuthenticated de proposito -- o caller interno nunca
    apresenta certificado dual). Sem filtrar por sni="mtls", a
    primeira versao deste check contou 1048 conexoes com 560
    dualAuthenticated=false -- parecia uma falha real, mas eram todas
    do carve-out interno (esperado, correto, documentado). Filtrado
    aqui pra nunca repetir esse falso alarme."""
    print("\n=== dualAuthenticated=true em TODAS as conexoes Hybrid client-facing (sni=\"mtls\", nao so 1/execucao) ===")
    text = COMBINED_LOG.read_text(encoding="utf-8", errors="replace")
    rows, internal_rows = [], []
    for line in text.splitlines():
        m = re.search(r'hibrido-and connection OK .*?sni="([^"]*)".*?dualAuthenticated=(true|false)', line)
        if not m:
            continue
        sni, dual = m.group(1), m.group(2) == "true"
        if sni == "mtls":
            rows.append(dual)
        else:
            internal_rows.append((sni, dual))
    n = len(rows)
    n_true = sum(rows)
    print(f"conexoes client-facing (sni=\"mtls\") encontradas: {n}; dualAuthenticated=true: {n_true}/{n}")
    print(f"conexoes do carve-out interno (sni != \"mtls\") encontradas, separadas e NAO exigidas: {len(internal_rows)} "
          f"(dualAuthenticated=true nelas: {sum(d for _, d in internal_rows)}/{len(internal_rows)}, esperado baixo/zero -- "
          f"business_server.go:107 as exclui de proposito)")
    assert n > 0, "nenhuma conexao hibrido-and client-facing encontrada no log combinado -- caminho do arquivo errado?"
    assert n_true == n, f"{n - n_true} conexao(oes) hibrido-and CLIENT-FACING com dualAuthenticated=false -- FALHA REAL"
    print("OK: dualAuthenticated=true em 100% das conexoes hibrido-and client-facing (sni=\"mtls\").")


def manifest_hash_check():
    print("\n=== Manifesto / hash do congelamento ===")
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    print("total_execucoes:", m["total_execucoes"], "expected_total:", m["expected_total"])
    print("total_capturas:", m["total_capturas"], "feitas:", m["capturas_dedicadas_feitas"],
          "falhas:", len(m["capturas_dedicadas_falhas"]))
    gw = m.get("gateway_binary_verifications", [])
    shas = {g["sha256_expected"] for g in gw}
    print("sha256 esperado do gateway (todas as verificacoes, deve ser 1 valor so):", shas)
    matched = {g["pin_matched"] for g in gw}
    print("pin_matched (deve ser {True}):", matched)


def main():
    execs = load_calls()
    warmups = json.loads((BASE / "aquecimento_execucoes.json").read_text(encoding="utf-8"))
    check_counts(execs)
    tfluxo_table(execs)
    retries(execs, warmups)
    opinsize()
    handshake_composition()
    dual_authenticated_check()
    manifest_hash_check()
    print("\n=== FIM -- tudo recomputado direto dos dados brutos, 0 valor de memoria/sessao anterior ===")


if __name__ == "__main__":
    main()
