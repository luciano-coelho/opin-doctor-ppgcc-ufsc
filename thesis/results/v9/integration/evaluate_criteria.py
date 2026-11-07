#!/usr/bin/env python3
"""
v9, Fase 1, T7/piloto: avalia os 7 criterios de ir/nao-ir
(DECISIONS.md, Decisao 21, ponto 4) a partir dos artefatos coletados
-- nao julga por olho, calcula.

Criterios 1, 4, 5, 6: avaliaveis com dados LOCAIS (Fase 1), testados
aqui. Criterios 2, 3, 7: dependem de dados reais de AWS (initcwnd,
execucoes na rota mais distante, RTT real por rota) -- a logica ja
existe e e testada com dados sinteticos (Decisao 33), mas so vira
PASS de verdade com os artefatos reais do piloto em `--aws-dir`.

Decisao 33: o avaliador e FAIL-CLOSED -- nenhum criterio retorna
`pass: None`. Dado ausente, arquivo nao encontrado, ou formato
invalido sempre resultam em `pass: False`, nunca em "sem dados"
silencioso. Um criterio de ir/nao-ir sem evidencia nunca autoriza a
campanha por omissao.

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
import os
import re
import sys
from collections import Counter

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

# Decisao 30 (Emenda 3 ao criterio 1): a Decisao 20/21 original supunha
# que o SNI do ClientHello no piloto seria um hostname de deploy real
# (~40-49 chars), com +36B esperados e +-15B de tolerancia em torno
# disso -- NUNCA verificado contra o codigo. Lendo `proxy/main.go`
# (singleChainClientConfig/dualClientConfig) e `proxy/relay.go` (o
# modo usado no piloto de verdade, nao o one-shot): `ServerName:
# "mtls"` e FIXO, hardcoded, nos dois construtores de tls.Config, e
# nunca depende do endereco de `-target` (que so afeta o `tls.Dial`,
# nunca o SNI). A verificacao do certificado do servidor e por
# `cert.VerifyHostname("mtls")` -- como "mtls" nao e um IP valido, o
# Go compara contra `DNSNames`, NUNCA contra `IPAddresses` (confirma
# que os IPs do SAN, Decisao 28/29, nunca entram na verificacao desta
# arquitetura especifica -- so os IPs reais que a AWS atribuir, a
# verificacao sempre casa com a string fixa "mtls"). Conclusao: o SNI
# do piloto e BYTE A BYTE igual ao do loopback -- confirmado medindo
# (nao so lendo o codigo): measure.sh de hoje (Decisao 29, as mesmas
# duas rodadas de medicao, loopback e SAN doc-range) deu o MESMO
# tamanho de ClientHello nas duas, pros 4 perfis -- esperado, ja que
# o ClientHello e inteiramente gerado pelo CLIENTE antes do servidor
# mandar qualquer coisa, nunca depende do certificado do servidor.
# Tolerancia corrigida de +-15B pra **0B** -- nao ha NENHUMA fonte de
# variabilidade entre loopback e piloto nesta mensagem especifica.
CLIENTHELLO_BASELINE = {"classico": 336, "pqc": 1779, "hibrido-v8": 1876, "hibrido-and": 1858}
CLIENTHELLO_TOLERANCE_B = 0

# Decisao 31 (Emenda 4 ao criterio 1) -- auditoria pedida pelo Luciano
# achou que `ZERO_TOLERANCE_MESSAGES` (abaixo, mantida so pra nao
# apagar o nome antigo) NUNCA foi de fato extraida nem comparada em
# lugar nenhum do codigo -- a mesma classe de bug que a Emenda 3 ja
# achou pro ClientHello, agora encontrada pras outras 5 mensagens MAIS
# a Certificate do CLIENTE (que tambem nunca era extraida). Corrigido:
# toda mensagem do handshake agora e extraida da SECAO "tamanho POR
# MENSAGEM" e comparada. Confirmado por medicao (nao suposto) que
# NENHUMA destas varia entre as duas rodadas de SAN da Decisao 29/30
# (loopback vs documentacao) -- so a Certificate do SERVIDOR varia
# (depende do SAN) -- entao tolerancia 0B se aplica a todas as outras,
# `+4B` de cabecalho por mensagem (mesma convencao da Certificate/
# ClientHello). Valores medidos hoje, measure.sh, 4 perfis:
HANDSHAKE_MESSAGE_BASELINE = {
    "classico": {
        "ServerHello": 187, "EncryptedExtensions": 10, "CertificateRequest": 109,
        "Certificate_cliente": 800, "CertificateVerify_servidor": 264,
        "CertificateVerify_cliente": 264, "Finished_servidor": 36, "Finished_cliente": 36,
    },
    "pqc": {
        "ServerHello": 1658, "EncryptedExtensions": 10, "CertificateRequest": 104,
        "Certificate_cliente": 5519, "CertificateVerify_servidor": 3317,
        "CertificateVerify_cliente": 3317, "Finished_servidor": 36, "Finished_cliente": 36,
    },
    "hibrido-v8": {
        "ServerHello": 1755, "EncryptedExtensions": 10, "CertificateRequest": 111,
        "Certificate_cliente": 6144, "CertificateVerify_servidor": 264,
        "CertificateVerify_cliente": 264, "Finished_servidor": 36, "Finished_cliente": 36,
    },
    "hibrido-and": {
        "ServerHello": 1755, "EncryptedExtensions": 10, "CertificateRequest": 98,
        "Certificate_cliente": 6356, "CertificateVerify_servidor": 3575,
        "CertificateVerify_cliente": 3575, "Finished_servidor": 36, "Finished_cliente": 36,
    },
}
HANDSHAKE_MESSAGE_TOLERANCE_B = 0
# Mantida so por retrocompatibilidade de nome -- nao e mais usada pra
# controlar nenhum comportamento (ver HANDSHAKE_MESSAGE_BASELINE acima,
# que e o que o codigo realmente confere agora).
ZERO_TOLERANCE_MESSAGES = {"ServerHello", "EncryptedExtensions", "CertificateRequest", "CertificateVerify", "Finished"}

# Decisao 32 (Emenda 5 ao criterio 7): o nominal de L0 e 0ms -- +-10%
# de 0 e 0, uma faixa vazia/indefinida, nunca satisfazivel por
# qualquer RTT real medido (mesmo os ~0,14-0,18ms que a v8 real mediu
# nesse mesmo cenario co-localizado). Corrigido: L0 usa um PISO
# ABSOLUTO (RTT < 1ms), nao uma fracao do nominal -- 1ms da margem
# confortavel sobre o que a v8 real ja mediu (0,14-0,18ms) sem abrir
# a porta pra uma rota que na verdade atravessou rede real. L219 e
# L325 mantem +-10% do NOMINAL da rota (219ms/325ms -- nao do valor
# que a v8 mediu, 219,9/330,3ms, que e so contexto confirmando que o
# nominal e realista, nao o alvo da tolerancia em si).
NOMINAL_RTT_MS = {"L0": 0, "L219": 219, "L325": 325}
L0_RTT_ABSOLUTE_FLOOR_MS = 1.0
RTT_TOLERANCE_FRACTION = 0.10


def _rtt_ok(route: str, measured_ms: float) -> bool:
    if route == "L0":
        return measured_ms < L0_RTT_ABSOLUTE_FLOOR_MS
    nominal = NOMINAL_RTT_MS[route]
    lo, hi = nominal * (1 - RTT_TOLERANCE_FRACTION), nominal * (1 + RTT_TOLERANCE_FRACTION)
    return lo <= measured_ms <= hi


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
        clienthello_bytes = None
        other = {}  # key (ver _HANDSHAKE_TYPE_NAMES/sufixo) -> bytes medidos
        for line in msg_section.group(1).splitlines():
            cols = line.split("\t")
            if len(cols) < 3:
                continue
            types = [t.strip() for t in cols[1].split(",")]
            lengths = cols[2].split(",")
            per_type = {t: int(l) + 4 for t, l in zip(types, lengths)}
            # Both the server's AND the client's flight contain a
            # Certificate message (type 11) -- summing every "11" found
            # anywhere in the profile block double-counts them (found
            # live: the first version of this reported ~12.4KB for
            # Hibrido-v8 against an 8.5KB baseline, nearly 2x, exactly
            # consistent with counting both). Only the frame that ALSO
            # contains ServerHello (type 2) is the server's own flight.
            if "2" in types and "11" in types:
                total_cert_bytes = per_type["11"]
                # Decisao 31 (Emenda 4): o resto do flight do SERVIDOR
                # tambem precisa ser conferido, nao so a Certificate --
                # ServerHello/EncryptedExtensions/CertificateRequest nunca
                # tinham sido extraidos antes desta emenda.
                if "2" in per_type:
                    other["ServerHello"] = per_type["2"]
                if "8" in per_type:
                    other["EncryptedExtensions"] = per_type["8"]
                if "13" in per_type:
                    other["CertificateRequest"] = per_type["13"]
                if "15" in per_type:
                    other["CertificateVerify_servidor"] = per_type["15"]
                if "20" in per_type:
                    other["Finished_servidor"] = per_type["20"]
            # O flight do CLIENTE (Certificate/CertificateVerify/Finished
            # dele) tem "11" mas NUNCA "2" (ServerHello e so do servidor)
            # -- nunca era extraido antes desta emenda, nem a Certificate
            # do cliente nem o resto do flight dele.
            elif "11" in types:
                if "11" in per_type:
                    other["Certificate_cliente"] = per_type["11"]
                if "15" in per_type:
                    other["CertificateVerify_cliente"] = per_type["15"]
                if "20" in per_type:
                    other["Finished_cliente"] = per_type["20"]
            # ClientHello (type 1) is always alone in the client's own
            # first frame -- confirmed never sharing a frame with any
            # other handshake type in any of this project's captures.
            if types == ["1"]:
                clienthello_bytes = per_type["1"]
        cert_baseline = CERTIFICATE_BASELINE.get(profile)
        cert_ok = cert_baseline is not None and total_cert_bytes is not None and abs(total_cert_bytes - cert_baseline) <= CERTIFICATE_TOLERANCE_B
        ch_baseline = CLIENTHELLO_BASELINE.get(profile)
        ch_ok = ch_baseline is not None and clienthello_bytes is not None and abs(clienthello_bytes - ch_baseline) <= CLIENTHELLO_TOLERANCE_B
        other_baseline = HANDSHAKE_MESSAGE_BASELINE.get(profile, {})
        other_rows = {}
        other_all_ok = True
        for key, baseline in other_baseline.items():
            measured = other.get(key)
            ok = measured is not None and abs(measured - baseline) <= HANDSHAKE_MESSAGE_TOLERANCE_B
            other_all_ok = other_all_ok and ok
            other_rows[key] = {"bytes": measured, "baseline": baseline, "ok": ok}
        results.append({
            "profile": profile,
            "certificate_bytes": total_cert_bytes, "certificate_baseline": cert_baseline,
            "certificate_tolerance": CERTIFICATE_TOLERANCE_B, "certificate_ok": cert_ok,
            "clienthello_bytes": clienthello_bytes, "clienthello_baseline": ch_baseline,
            "clienthello_tolerance": CLIENTHELLO_TOLERANCE_B, "clienthello_ok": ch_ok,
            "other_messages": other_rows,
            "ok": cert_ok and ch_ok and other_all_ok,
        })
    # Decisao 33 (avaliador fail-closed): sem nenhum bloco de perfil no
    # log (arquivo vazio, caminho errado, execucao que nunca rodou),
    # o criterio tem que FALHAR -- nao "sem dados" (None), que o
    # relatorio final poderia confundir com "ainda nao relevante".
    # Ausencia de dado NUNCA e PASS nem N/A pra um criterio de ir/nao
    # ir -- e FAIL, ate prova em contrario.
    return {"criterion": 1, "name": "tamanhos por mensagem", "rows": results,
            "pass": all(r["ok"] for r in results) if results else False,
            "note": "avaliado so com o que o log local forneceu -- o criterio real exige as 12 capturas do piloto (4 perfis x 3 rotas)"}


def criterion_4_counts(calls_json: dict | None) -> dict:
    # Decisao 33 (avaliador fail-closed): "nenhum dado fornecido" e
    # FAIL, nao None -- um criterio de ir/nao-ir sem evidencia nunca
    # autoriza a campanha por omissao.
    if calls_json is None:
        return {"criterion": 4, "name": "contagens do fluxo", "pass": False,
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
    # Decisao 33 (avaliador fail-closed): "nenhum erro encontrado" so
    # significa algo se o log realmente tem execucoes reais dentro --
    # um arquivo vazio tambem teria zero ocorrencias de "ok":false,
    # mas isso NAO E evidencia de zero erros, e ausencia de qualquer
    # evidencia. Exige pelo menos um bloco "== Perfil:" real (mesmo
    # marcador que o criterio 1 ja usa) antes de aceitar a contagem de
    # erros como significativa.
    if "== Perfil:" not in log_text:
        return {"criterion": 5, "name": "zero erros", "errors_found": [],
                "pass": False,
                "note": "log sem nenhum bloco '== Perfil:' -- nao ha evidencia de execucao real, zero erros encontrados nao significa zero erros ocorridos"}
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


INITCWND_MIN_SEGMENTS = 10
L325_PROFILES = ("classico", "pqc", "hibrido-v8", "hibrido-and")
L325_N_PER_PROFILE = 5


def criterion_2_initcwnd(aws_dir) -> dict:
    """Decisao 32/34: initcwnd real das instancias do piloto.

    Metodo (descrito aqui, nao reimplementado dentro desta funcao --
    ela confere um RESULTADO ja computado, mesmo padrao de confianca
    que o criterio 4 ja tem com --calls-json): `ip route show` SO
    mostra initcwnd quando ha um override explicito de rota -- o
    valor efetivo do kernel (`TCP_INIT_CWND`, hoje tipicamente 10)
    nao aparece ali quando ninguem configurou nada. Em vez de
    confiar nisso, o metodo primario e a CAPTURA dedicada (Decisao
    24, criterio 1): contar quantos SEGMENTOS TCP o SERVIDOR manda,
    na origem (porta 443), ANTES do primeiro ACK do CLIENTE que
    reconhece esses bytes -- esse numero de segmentos e o que o
    initcwnd real da instancia permite enviar sem esperar um ACK.
    `sysctl net.ipv4.tcp_...`/a configuracao do sistema e lida como
    REFERENCIA cruzada, nunca como fonte primaria (pode nao refletir
    o que o kernel realmente aplica numa conexao especifica).

    Limites do metodo: precisa de uma captura `tcpdump -s 0` real
    (nao fragmentada) com numeros de sequencia/ACK TCP preservados;
    em loopback local o MSS e grande o bastante pra nunca segmentar
    de verdade, entao esse criterio estruturalmente NAO pode ser
    exercitado contra dados locais -- so contra a captura real do
    piloto, numa rota com RTT > 0 (initcwnd so importa quando ha
    espera de rede entre o envio e o ACK).

    Formato esperado em `<aws_dir>/criterio2_initcwnd.json`:
    `{"server_segments_before_client_ack": <int>, "sysctl_reference": {...}}`.
    """
    if not aws_dir:
        return {"criterion": 2, "name": "initcwnd real", "pass": False,
                "note": "nenhum --aws-dir fornecido -- sem captura real, nao ha evidencia de initcwnd"}
    path = os.path.join(aws_dir, "criterio2_initcwnd.json")
    if not os.path.isfile(path):
        return {"criterion": 2, "name": "initcwnd real", "pass": False,
                "note": f"arquivo nao encontrado: {path}"}
    try:
        data = json.load(open(path, encoding="utf-8"))
        segments = data["server_segments_before_client_ack"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return {"criterion": 2, "name": "initcwnd real", "pass": False,
                "note": f"arquivo malformado ou campo ausente ({e})"}
    ok = isinstance(segments, int) and segments >= INITCWND_MIN_SEGMENTS
    return {"criterion": 2, "name": "initcwnd real",
            "segments_measured": segments, "threshold": INITCWND_MIN_SEGMENTS,
            "sysctl_reference": data.get("sysctl_reference"),
            "pass": ok}


def criterion_3_distant_route(aws_dir) -> dict:
    """Decisao 24, criterio 3: 0 erros em 20/20 execucoes (4 perfis x
    N=5) especificamente na rota `sa-east-1/L325`. Formato esperado
    em `<aws_dir>/criterio3_l325_execucoes.json`:
    `{"execucoes": [{"profile": ..., "route": "L325", "ok": true}, ...]}`
    -- exatamente 20 entradas, todas route=="L325", 4 perfis distintos
    x 5 cada, todas ok=true."""
    if not aws_dir:
        return {"criterion": 3, "name": "zero erros na rota mais distante", "pass": False,
                "note": "nenhum --aws-dir fornecido -- sem log de execucoes, nao ha evidencia"}
    path = os.path.join(aws_dir, "criterio3_l325_execucoes.json")
    if not os.path.isfile(path):
        return {"criterion": 3, "name": "zero erros na rota mais distante", "pass": False,
                "note": f"arquivo nao encontrado: {path}"}
    try:
        execs = json.load(open(path, encoding="utf-8"))["execucoes"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return {"criterion": 3, "name": "zero erros na rota mais distante", "pass": False,
                "note": f"arquivo malformado ou campo ausente ({e})"}
    all_l325 = all(e.get("route") == "L325" for e in execs)
    count_ok = len(execs) == len(L325_PROFILES) * L325_N_PER_PROFILE
    per_profile = Counter(e.get("profile") for e in execs)
    profiles_ok = all(per_profile.get(p) == L325_N_PER_PROFILE for p in L325_PROFILES)
    errors = [e for e in execs if not e.get("ok")]
    ok = all_l325 and count_ok and profiles_ok and len(errors) == 0
    return {"criterion": 3, "name": "zero erros na rota mais distante",
            "total_execucoes": len(execs), "expected_total": len(L325_PROFILES) * L325_N_PER_PROFILE,
            "all_route_l325": all_l325, "profile_distribution_ok": profiles_ok,
            "errors_found": len(errors), "pass": ok}


def criterion_7_latency_sanity(aws_dir) -> dict:
    """Decisao 24, criterio 7 + Decisao 32 (Emenda 5): RTT medido por
    rota, via `ping -c 20 <endereco>` (media), contra a tabela
    nominal -- L0 com piso absoluto (<1ms), L219/L325 com +-10% do
    nominal (ver NOMINAL_RTT_MS/_rtt_ok). Formato esperado em
    `<aws_dir>/criterio7_rtt_por_rota.json`:
    `{"L0": {"rtt_ms": ...}, "L219": {"rtt_ms": ...}, "L325": {"rtt_ms": ...}}`."""
    if not aws_dir:
        return {"criterion": 7, "name": "sanidade de latencia por rota", "pass": False,
                "note": "nenhum --aws-dir fornecido -- sem medicao de RTT, nao ha evidencia"}
    path = os.path.join(aws_dir, "criterio7_rtt_por_rota.json")
    if not os.path.isfile(path):
        return {"criterion": 7, "name": "sanidade de latencia por rota", "pass": False,
                "note": f"arquivo nao encontrado: {path}"}
    try:
        data = json.load(open(path, encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"criterion": 7, "name": "sanidade de latencia por rota", "pass": False,
                "note": f"arquivo malformado ({e})"}
    rows = {}
    all_ok = True
    for route in NOMINAL_RTT_MS:
        entry = data.get(route)
        if not entry or "rtt_ms" not in entry:
            rows[route] = {"rtt_ms": None, "ok": False}
            all_ok = False
            continue
        rtt = entry["rtt_ms"]
        ok = _rtt_ok(route, rtt)
        all_ok = all_ok and ok
        rows[route] = {"rtt_ms": rtt, "nominal_ms": NOMINAL_RTT_MS[route], "ok": ok}
    return {"criterion": 7, "name": "sanidade de latencia por rota", "rows": rows, "pass": all_ok}


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
    # Decisao 33: "pass" so pode ser True ou False agora -- nunca None.
    # Deixado sem fallback de proposito: se algum criterio algum dia
    # voltar a devolver None, isso deve estourar aqui (KeyError),
    # alto e visivel, em vez de imprimir silenciosamente "N/A" e
    # deixar passar por omissao.
    for r in results:
        status = {"True": "PASS", "False": "FAIL"}[str(r["pass"])]
        print(f"criterio {r['criterion']} ({r['name']}): {status}")

    if any(r["pass"] is False for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
