#!/usr/bin/env python3
"""v9, campanha oficial (Decisao 143): recomputa, direto dos dados
brutos em thesis/results/v9/campaign/oficial_raw/oficial_out/, TODO
numero que thesis/results/v9/Consolidated_Metrics_Report_FINAL.md usa
-- nunca le o relatorio, nunca confia em memoria de sessao anterior.
Imprime cada numero com um rotulo identico ao do relatorio, pra
conferencia visual linha a linha. Sem argumentos: caminhos fixos,
sempre os mesmos dados oficiais da janela v3."""
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "results" / "v9" / "campaign" / "oficial_raw" / "oficial_out"
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
              f"jwk={v['jwk_response_bytes_avg']} pki={v['pki_response_bytes_avg']} "
              f"3termos(sig)={v['opinsize_3_termos_sem_pki_comparavel_schardong_eq3_1']} "
              f"3termos(full)={v['opinsize_3_termos_token_completo']} "
              f"4termos(sig)={v['opinsize_4_termos_com_pki_extensao_desta_tese']} "
              f"4termos(full)={v['opinsize_4_termos_token_completo']}")
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
    manifest_hash_check()
    print("\n=== FIM -- tudo recomputado direto dos dados brutos, 0 valor de memoria/sessao anterior ===")


if __name__ == "__main__":
    main()
