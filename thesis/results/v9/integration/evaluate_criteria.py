#!/usr/bin/env python3
"""
v9, Fase 1, T7/piloto: avalia os 7 criterios de ir/nao-ir
(DECISIONS.md, Decisao 21, ponto 4) a partir dos artefatos coletados
-- nao julga por olho, calcula.

Criterios 1, 4, 5, 6: avaliaveis com dados LOCAIS (Fase 1), testados
aqui. Criterios 2, 3, 7: dependem de dados reais de AWS (initcwnd,
execucoes na rota mais distante, RTT real por rota) -- a logica existe,
mas so pode ser exercitada de verdade com os artefatos do piloto.

Uso:
  python evaluate_criteria.py --run-t6-log <arquivo> [--calls-json <arquivo>] [--aws-dir <diretorio>]

run_t6.sh/measure.sh ja produzem, por perfil, no mesmo log: as linhas
JSON de "side":"gateway"/"side":"proxy" (bytes de handshake, CurveID,
DualAuthenticated) e a secao "tamanho POR MENSAGEM" do tshark -- este
script le as duas do MESMO arquivo de log, sem reimplementar nenhuma
medicao, so reconferindo contra os limiares ja definidos.
"""
import argparse
import json
import re
import sys

EXPECTED_CURVE = {
    "classico": "CurveP384",
    "pqc": "MLKEM1024",
    "hibrido-v8": "SecP384r1MLKEM1024",
    "hibrido-and": "SecP384r1MLKEM1024",
}

# Decisao 20 (item e) -- tolerancia POR MENSAGEM, calculada, nao suposta.
# Baseline = o tamanho da mensagem Certificate ISOLADA (Decisao 15),
# NAO o total do flight do servidor (esse e maior, inclui ServerHello/
# EncryptedExtensions/CertificateRequest/CertificateVerify/Finished
# tambem -- um erro real desta primeira versao do script, achado ao
# testar: usar o total do flight aqui reportava FAIL em todos os
# perfis, porque comparava a Certificate isolada contra um numero
# maior que nunca poderia bater).
#
# Decisao 28 (Emenda 1 ao criterio 1) + Decisao 29 (Emenda 2): o
# servidor do piloto precisa de DOIS IPs no SAN (IP privado, pro L0
# co-localizado; EIP, pro L219/L325 cross-region -- confirmado na v8
# real, Decisao 52/53 dela) em vez do par loopback (127.0.0.1,::1)
# usado nos testes locais. A Emenda 1 estimou o delta por aritmetica
# de DER (-12B) -- a Emenda 2 MEDIU de verdade (dois builds reais de
# certificado, mesmo pipeline, so variando SERVER_IPS) e achou -14B
# pros perfis de certificado unico (a aritmetica errou por ~2B, efeito
# de fronteira na codificacao de comprimento do DER, nao decomposto
# byte a byte) e -28B pro Hibrido-AND especificamente -- CONFIRMADO no
# codigo (`certs/main.go`, `sameSANs(andRSAServer, andMLDSAServer)`)
# que esse perfil tem DOIS certificados-folha de servidor, cada um
# carregando o mesmo SAN, dobrando o efeito. Valores adotados: os
# MEDIDOS (Decisao 29), nao os aritmeticos (Decisao 28, superados).
CERTIFICATE_BASELINE = {"classico": 899, "pqc": 5618, "hibrido-v8": 6241, "hibrido-and": 6554}
CERTIFICATE_TOLERANCE_B = 50
CLIENTHELLO_TOLERANCE_B = 15
ZERO_TOLERANCE_MESSAGES = {"ServerHello", "EncryptedExtensions", "CertificateRequest", "CertificateVerify", "Finished"}


def criterion_1_message_sizes(log_text: str) -> dict:
    """Extrai os tamanhos por mensagem do log do measure.sh (secao
    'tamanho POR MENSAGEM de handshake') e confere contra a tolerancia.
    So pode confirmar o criterio completo (100% das 12 capturas) quando
    rodado contra os artefatos REAIS do piloto (4 perfis x 3 rotas); aqui,
    local, confere o que os dados fornecidos tiverem."""
    results = []
    # Cada bloco comeca em "== Perfil: X, modo normal" e tem uma secao
    # "tshark: tamanho POR MENSAGEM..." com linhas "frame tipo(s) tamanho(s)"
    for profile_block in re.finditer(
        r"== Perfil: (\S+), modo normal.*?(?=== Perfil:|\Z)", log_text, re.S
    ):
        profile = profile_block.group(1)
        block = profile_block.group(0)
        msg_section = re.search(
            r"tamanho POR MENSAGEM.*?\n(.*?)(?:\n==|\Z)", block, re.S
        )
        if not msg_section:
            continue
        total_cert_bytes = None
        for line in msg_section.group(1).splitlines():
            cols = line.split("\t")
            if len(cols) < 3:
                continue
            types = [t.strip() for t in cols[1].split(",")]
            lengths = cols[2].split(",")
            # Both the server's AND the client's flight contain a
            # Certificate message (type 11) -- summing every "11" found
            # anywhere in the profile block double-counts them (found
            # live: the first version of this reported ~12.4KB for
            # Hibrido-v8 against an 8.5KB baseline, nearly 2x, exactly
            # consistent with counting both). Only the frame that ALSO
            # contains ServerHello (type 2) is the server's own flight --
            # that frame's "11" is the one the Decisao 20 tolerance is
            # actually about.
            if "2" not in types or "11" not in types:
                continue
            total_cert_bytes = int(lengths[types.index("11")]) + 4
        baseline = CERTIFICATE_BASELINE.get(profile)
        ok = baseline is not None and total_cert_bytes is not None and abs(total_cert_bytes - baseline) <= CERTIFICATE_TOLERANCE_B
        results.append({
            "profile": profile, "certificate_bytes": total_cert_bytes,
            "baseline": baseline, "tolerance": CERTIFICATE_TOLERANCE_B, "ok": ok,
        })
    return {"criterion": 1, "name": "tamanhos por mensagem", "rows": results,
            "pass": all(r["ok"] for r in results) if results else None,
            "note": "avaliado so com o que o log local forneceu -- o criterio real exige as 12 capturas do piloto (4 perfis x 3 rotas)"}


def criterion_4_counts(calls_json: dict | None) -> dict:
    if calls_json is None:
        return {"criterion": 4, "name": "contagens do fluxo", "pass": None,
                "note": "nenhum --calls-json fornecido -- precisa de uma rodada T6b (opin_flow.py) real"}
    calls1 = calls_json.get("insurance", [])
    calls2 = calls_json.get("person", [])
    total_calls = len(calls1) + len(calls2)
    total_jwts = sum(len(c.get("jwts") or []) for c in calls1 + calls2)
    total_jwks = sum(1 for c in calls1 + calls2 if c.get("endpoint") == "/jwks")
    total_ca = sum(1 for c in calls1 + calls2 if c.get("endpoint") in ("/root-ca.pem", "/issuer-ca.pem"))
    expected = {"http": 44, "jwts": 28, "jwks": 4, "ca": 4}
    actual = {"http": total_calls, "jwts": total_jwts, "jwks": total_jwks, "ca": total_ca}
    ok = actual == expected
    return {"criterion": 4, "name": "contagens do fluxo", "expected": expected,
            "actual": actual, "pass": ok}


def criterion_5_zero_errors(log_text: str) -> dict:
    errors = re.findall(r'"ok":false[^}]*"error":"([^"]+)"', log_text)
    # Excludes lines that are the Dockerfile's OWN echoed command text
    # (`echo "FATAL: ..." >&2; exit 1; }`), which Docker reprints as
    # part of normal build-step output even on a cache hit/success --
    # found live, the first time this ran: it flagged a passing build
    # as an error purely because the command that WOULD print "FATAL"
    # on real failure is itself visible in the log. A genuine failure
    # line never contains shell syntax like `>&2`/`exit 1` alongside it.
    for line in log_text.splitlines():
        if "FATAL:" in line and ">&2" not in line and "exit 1" not in line:
            errors.append(line.strip())
    return {"criterion": 5, "name": "zero erros", "errors_found": errors,
            "pass": len(errors) == 0}


def criterion_6_instrumentation(log_text: str) -> dict:
    """CurveID e DualAuthenticated por conexao, conferidos contra o
    esperado do perfil -- igual ao que a Decisao 14 ja fazia, so
    reempacotado como um criterio formal, automatico."""
    rows = []
    for m in re.finditer(r'\{"side":"(gateway|proxy)","profile":"([^"]+)".*?"curveID":"([^"]+)".*?"dualAuthenticated":(true|false)', log_text):
        side, profile, curve, dual = m.groups()
        want = EXPECTED_CURVE.get(profile)
        curve_ok = curve == want
        dual_ok = True
        if profile == "hibrido-and":
            dual_ok = dual == "true"
        rows.append({"side": side, "profile": profile, "curve": curve, "curve_expected": want,
                     "curve_ok": curve_ok, "dualAuthenticated": dual, "dual_ok": dual_ok})
    has_keylog_evidence = "tshark: registros TLS decifrados" in log_text and "nao produziu" not in log_text
    all_ok = all(r["curve_ok"] and r["dual_ok"] for r in rows) if rows else False
    return {"criterion": 6, "name": "instrumentacao completa + asserções",
            "connections_checked": len(rows), "rows": rows,
            "keylog_decryption_evidence": has_keylog_evidence,
            "pass": all_ok and has_keylog_evidence and len(rows) > 0}


def criterion_2_initcwnd(aws_dir) -> dict:
    return {"criterion": 2, "name": "initcwnd real", "pass": None,
            "note": "exige `ss --info` nas instancias reais do piloto -- nao avaliavel localmente"}


def criterion_3_distant_route(aws_dir) -> dict:
    return {"criterion": 3, "name": "zero erros na rota mais distante", "pass": None,
            "note": "exige as 20 execucoes reais em sa-east-1/L325 -- nao avaliavel localmente"}


def criterion_7_latency_sanity(aws_dir) -> dict:
    return {"criterion": 7, "name": "sanidade de latencia por rota", "pass": None,
            "note": "exige RTT medido real por rota -- nao avaliavel localmente"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-t6-log", required=True)
    ap.add_argument("--calls-json")
    ap.add_argument("--aws-dir")
    args = ap.parse_args()

    log_text = open(args.run_t6_log, encoding="utf-8", errors="replace").read()
    calls_json = json.load(open(args.calls_json)) if args.calls_json else None

    results = [
        criterion_1_message_sizes(log_text),
        criterion_2_initcwnd(args.aws_dir),
        criterion_3_distant_route(args.aws_dir),
        criterion_4_counts(calls_json),
        criterion_5_zero_errors(log_text),
        criterion_6_instrumentation(log_text),
        criterion_7_latency_sanity(args.aws_dir),
    ]

    print(json.dumps(results, indent=2, ensure_ascii=False))
    print()
    for r in results:
        status = {"True": "PASS", "False": "FAIL", "None": "N/A (sem dados)"}[str(r["pass"])]
        print(f"criterio {r['criterion']} ({r['name']}): {status}")

    if any(r["pass"] is False for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
