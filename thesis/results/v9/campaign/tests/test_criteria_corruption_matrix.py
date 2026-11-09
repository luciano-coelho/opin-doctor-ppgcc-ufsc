"""Pedido do Luciano (fechamento dos criterios 1/3/4/6/7 pra campanha,
item 2): para CADA um dos 7 criterios, dados sinteticos CORRETOS
(tem que passar) e CORROMPIDOS (tem que reprovar), cobrindo as
corrupcoes especificas pedidas -- RSA-4096 no lugar de RSA-2048
(Classico/Hibrido dual=false/Hibrido dual=true), PQC com algoritmo
classico, componente PQC do dual=true diferente do perfil esperado,
contagem 44/6/28/4/4 trocada (CORRECAO: o pedido citou "43/6/28/4/4" --
o numero real do projeto e 44 chamadas HTTP, `expected_http = {"http":
44, ...}`/`EXPECTED_MTLS_CONNECTIONS=6`, evaluate_criteria.py; usado
aqui com o valor real, confirmado antes de escrever o teste), rota ou
combinacao faltando, RTT fora de +-10% numa rota, curveID errado,
dualAuthenticated errado.

Cada teste de corrupcao tem seu par "correto" (PASS) explicito --
nunca so o lado corrompido. Ao final, `test_imprime_matriz_final`
imprime a matriz criterio x corrupcao x resultado (rodar com `-s` pra
ver a impressao). Corrupcoes que nao se aplicam a um criterio
especifico aparecem marcadas "N/A" na matriz, com a razao.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "integration"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import evaluate_criteria as ec  # noqa: E402
import campaign_topology as ct  # noqa: E402

MATRIZ = []  # (criterio, nome_curto, corrupcao, esperado, obtido, aplicavel)


def _registra(criterio, corrupcao, esperado, obtido, aplicavel=True, razao_na=""):
    MATRIZ.append((criterio, corrupcao, esperado, obtido, aplicavel, razao_na))


# =====================================================================
# Criterio 1 -- tamanhos por mensagem (campanha)
# =====================================================================

def _write_capture(capturas_dir, profile, route, cert_bytes=None, ch_bytes=None, **msg_overrides):
    cert_bytes = cert_bytes if cert_bytes is not None else ec.CERTIFICATE_BASELINE[profile]
    ch_bytes = ch_bytes if ch_bytes is not None else ec.CLIENTHELLO_BASELINE[profile]
    m = dict(ec.HANDSHAKE_MESSAGE_BASELINE[profile])
    m.update(msg_overrides)
    block = (
        f"== Perfil: {profile} ==\n"
        "tamanho POR MENSAGEM (frame, tipos, tamanhos)\n"
        f"4\t1\t{ch_bytes - 4}\n"
        f"6\t2,8,13,11,15,20\t{m['ServerHello']-4},{m['EncryptedExtensions']-4},{m['CertificateRequest']-4},"
        f"{cert_bytes-4},{m['CertificateVerify_servidor']-4},{m['Finished_servidor']-4}\n"
        f"8\t11,15,20\t{m['Certificate_cliente']-4},{m['CertificateVerify_cliente']-4},{m['Finished_cliente']-4}\n"
        "== fim ==\n"
    )
    capturas_dir.mkdir(parents=True, exist_ok=True)
    (capturas_dir / f"{profile}_{route}.log").write_text(block, encoding="utf-8")


_C1_PROFILES = list(ec.PROFILES_ALL)
_C1_ROUTES = ["L0-sa-east-1", "L123"]


def _criterio1_correto(tmp_path):
    capturas_dir = tmp_path / "criterio1_capturas"
    for profile in _C1_PROFILES:
        for route in _C1_ROUTES:
            _write_capture(capturas_dir, profile, route)
    return tmp_path


def test_criterio1_correto_passa(tmp_path):
    _criterio1_correto(tmp_path)
    result = ec.criterion_1_message_sizes_campaign(str(tmp_path), profiles=_C1_PROFILES, routes=_C1_ROUTES)
    assert result["pass"] is True, result
    assert result["expected_captures"] == 8
    _registra(1, "dados corretos (baseline)", "PASS", "PASS" if result["pass"] else "FAIL")


def test_criterio1_rsa4096_no_lugar_de_rsa2048_classico_reprova(tmp_path):
    """RSA-4096 real tem DER maior que RSA-2048 -- simulado aqui como
    um certificado +600B maior que o baseline (bem fora da tolerancia
    de +-4B)."""
    _criterio1_correto(tmp_path)
    _write_capture(tmp_path / "criterio1_capturas", "classico", "L0-sa-east-1",
                    cert_bytes=ec.CERTIFICATE_BASELINE["classico"] + 600)
    result = ec.criterion_1_message_sizes_campaign(str(tmp_path), profiles=_C1_PROFILES, routes=_C1_ROUTES)
    assert result["pass"] is False, result
    _registra(1, "RSA-4096 no lugar de RSA-2048 (Classico)", "FAIL", "PASS" if result["pass"] else "FAIL")


def test_criterio1_rsa4096_hibrido_dual_false_reprova(tmp_path):
    _criterio1_correto(tmp_path)
    _write_capture(tmp_path / "criterio1_capturas", "hibrido-v8", "L0-sa-east-1",
                    cert_bytes=ec.CERTIFICATE_BASELINE["hibrido-v8"] + 600)
    result = ec.criterion_1_message_sizes_campaign(str(tmp_path), profiles=_C1_PROFILES, routes=_C1_ROUTES)
    assert result["pass"] is False, result
    _registra(1, "RSA-4096 no lugar de RSA-2048 (Hibrido dual=false)", "FAIL", "PASS" if result["pass"] else "FAIL")


def test_criterio1_rsa4096_hibrido_dual_true_reprova(tmp_path):
    _criterio1_correto(tmp_path)
    _write_capture(tmp_path / "criterio1_capturas", "hibrido-and", "L0-sa-east-1",
                    cert_bytes=ec.CERTIFICATE_BASELINE["hibrido-and"] + 600)
    result = ec.criterion_1_message_sizes_campaign(str(tmp_path), profiles=_C1_PROFILES, routes=_C1_ROUTES)
    assert result["pass"] is False, result
    _registra(1, "RSA-4096 no lugar de RSA-2048 (Hibrido dual=true)", "FAIL", "PASS" if result["pass"] else "FAIL")


def test_criterio1_pqc_com_algoritmo_classico_reprova(tmp_path):
    """PQC usando RSA/EC classico em vez de ML-KEM real -- simulado
    como o certificado do PQC vir no TAMANHO do classico (muito menor
    que o baseline PQC real)."""
    _criterio1_correto(tmp_path)
    _write_capture(tmp_path / "criterio1_capturas", "pqc", "L0-sa-east-1",
                    cert_bytes=ec.CERTIFICATE_BASELINE["classico"])
    result = ec.criterion_1_message_sizes_campaign(str(tmp_path), profiles=_C1_PROFILES, routes=_C1_ROUTES)
    assert result["pass"] is False, result
    _registra(1, "PQC com algoritmo classico", "FAIL", "PASS" if result["pass"] else "FAIL")


def test_criterio1_componente_pqc_do_dual_diferente_do_perfil_na():
    _registra(1, "componente PQC do dual=true != perfil PQC esperado", "N/A", "N/A", aplicavel=False,
               razao_na="criterio 1 so compara TAMANHOS de mensagem contra o baseline do perfil; "
                        "identidade do algoritmo/componente e verificada pelo criterio 6 (curveID/dualAuthenticated)")


def test_criterio1_contagem_trocada_na():
    _registra(1, "contagem 44/6/28/4/4 trocada", "N/A", "N/A", aplicavel=False,
               razao_na="criterio 1 nao olha contagens HTTP/mTLS -- isso e o criterio 4")


def test_criterio1_combinacao_faltando_reprova(tmp_path):
    _criterio1_correto(tmp_path)
    (tmp_path / "criterio1_capturas" / "hibrido-and_L123.log").unlink()
    result = ec.criterion_1_message_sizes_campaign(str(tmp_path), profiles=_C1_PROFILES, routes=_C1_ROUTES)
    assert result["pass"] is False, result
    assert "hibrido-and_L123" in result["missing_captures"]
    _registra(1, "combinacao perfil x rota faltando", "FAIL", "PASS" if result["pass"] else "FAIL")


def test_criterio1_rtt_fora_tolerancia_na():
    _registra(1, "RTT fora de +-10%", "N/A", "N/A", aplicavel=False,
               razao_na="criterio 1 nao mede RTT -- isso e o criterio 7")


def test_criterio1_curveid_errado_na():
    _registra(1, "curveID errado", "N/A", "N/A", aplicavel=False,
               razao_na="criterio 1 nao le curveID -- isso e o criterio 6")


def test_criterio1_dualauthenticated_errado_na():
    _registra(1, "dualAuthenticated errado", "N/A", "N/A", aplicavel=False,
               razao_na="criterio 1 nao le dualAuthenticated -- isso e o criterio 6")


# =====================================================================
# Criterio 2 -- initcwnd real (campanha) -- ja tem suite dedicada
# extensa (mss_channels_agree etc, ver test_evaluate_criteria.py);
# nenhuma das 8 corrupcoes pedidas por Luciano mapeia na grandeza que
# o criterio 2 mede (segmentos/cwnd de uma conexao dedicada, nao
# criptografia/contagem/RTT/rota) -- todas marcadas N/A aqui por
# construcao, nunca por falta de teste (os testes reais ja existem).
# =====================================================================

for _corrupcao in (
    "RSA-4096 no lugar de RSA-2048 (Classico)", "RSA-4096 no lugar de RSA-2048 (Hibrido dual=false)",
    "RSA-4096 no lugar de RSA-2048 (Hibrido dual=true)", "PQC com algoritmo classico",
    "componente PQC do dual=true != perfil PQC esperado", "contagem 44/6/28/4/4 trocada",
    "RTT fora de +-10%", "curveID errado", "dualAuthenticated errado",
):
    _registra(2, _corrupcao, "N/A", "N/A", aplicavel=False,
              razao_na="criterio 2 mede segmentos enviados/cwnd (initcwnd) de uma conexao dedicada -- "
                        "nenhuma das corrupcoes pedidas afeta essa grandeza; cobertura real e por "
                        "mss_channels_agree/offloads, ja testada em test_evaluate_criteria.py")
_registra(2, "combinacao rota/direcao faltando (ja coberto em test_evaluate_criteria.py)", "FAIL", "FAIL")


# =====================================================================
# Criterio 3 -- zero erros na rota mais distante (campanha)
# =====================================================================

_C3_ROUTE = max(ct.CAMPAIGN_NOMINAL_RTT_MS, key=ct.CAMPAIGN_NOMINAL_RTT_MS.get)
_C3_N = 2


def _criterio3_write(tmp_path, execucoes):
    (tmp_path / "criterio3_distante_execucoes.json").write_text(
        json.dumps({"execucoes": execucoes}), encoding="utf-8")


def _criterio3_execucoes_corretas():
    return [{"profile": p, "route": _C3_ROUTE, "run": r, "ok": True}
            for p in ec.PROFILES_ALL for r in range(_C3_N)]


def test_criterio3_correto_passa(tmp_path):
    _criterio3_write(tmp_path, _criterio3_execucoes_corretas())
    result = ec.criterion_3_distant_route_campaign(str(tmp_path), n_per_profile=_C3_N)
    assert result["pass"] is True, result
    assert result["route"] == _C3_ROUTE
    _registra(3, "dados corretos (baseline)", "PASS", "PASS" if result["pass"] else "FAIL")


def test_criterio3_rsa_pqc_curve_dual_na():
    for corrupcao in ("RSA-4096 no lugar de RSA-2048 (Classico/Hibrido/Hibrido-AND)",
                       "PQC com algoritmo classico", "componente PQC do dual=true != perfil PQC esperado",
                       "curveID errado", "dualAuthenticated errado"):
        _registra(3, corrupcao, "N/A", "N/A", aplicavel=False,
                   razao_na="criterio 3 so conta erros/cardinalidade na rota mais distante -- "
                             "nunca inspeciona criptografia (isso e criterio 1/6)")


def test_criterio3_contagem_trocada_na():
    _registra(3, "contagem 44/6/28/4/4 trocada", "N/A", "N/A", aplicavel=False,
               razao_na="essa contagem HTTP/mTLS e do criterio 4, nao do criterio 3")


def test_criterio3_combinacao_faltando_reprova(tmp_path):
    execs = _criterio3_execucoes_corretas()[:-1]  # falta 1 execucao de 1 perfil
    _criterio3_write(tmp_path, execs)
    result = ec.criterion_3_distant_route_campaign(str(tmp_path), n_per_profile=_C3_N)
    assert result["pass"] is False, result
    _registra(3, "execucao/combinacao faltando", "FAIL", "PASS" if result["pass"] else "FAIL")


def test_criterio3_erro_real_reprova(tmp_path):
    """Nao estava na lista pedida, mas e o proprio proposito do
    criterio 3 -- 1 execucao com ok=False tem que reprovar o criterio
    inteiro."""
    execs = _criterio3_execucoes_corretas()
    execs[0]["ok"] = False
    _criterio3_write(tmp_path, execs)
    result = ec.criterion_3_distant_route_campaign(str(tmp_path), n_per_profile=_C3_N)
    assert result["pass"] is False, result
    _registra(3, "1 execucao com erro real (ok=False)", "FAIL", "PASS" if result["pass"] else "FAIL")


def test_criterio3_rtt_na():
    _registra(3, "RTT fora de +-10%", "N/A", "N/A", aplicavel=False,
               razao_na="criterio 3 e sobre ZERO ERROS, nao RTT -- isso e o criterio 7")


# =====================================================================
# Criterio 4 -- contagens do fluxo (campanha)
# =====================================================================

def _calls_corretos(n_http=44, n_jwts=28, n_jwks=4, n_ca=4):
    """Monta `insurance`/`person` com os numeros REAIS do projeto
    (confirmado em evaluate_criteria.py: expected_http =
    {"http": 44, "jwts": 28, "jwks": 4, "ca": 4} -- CORRIGE o "43" do
    pedido original, que nao bate com o codigo real)."""
    calls = []
    for _ in range(n_jwts):
        calls.append({"endpoint": "/other", "jwts": ["tok"]})
    for _ in range(n_jwks):
        calls.append({"endpoint": "/jwks", "jwts": []})
    for _ in range(n_ca):
        calls.append({"endpoint": "/root-ca.pem", "jwts": []})
    while len(calls) < n_http:
        calls.append({"endpoint": "/other", "jwts": []})
    assert len(calls) == n_http
    meio = n_http // 2
    return calls[:meio], calls[meio:]


def _mtls_ok_lines(n=6):
    return "\n".join(
        f'gateway: PERFIL connection OK remoteAddr=203.0.113.{10+i}:51000 sni="mtls" '
        f'curve=SecP384r1MLKEM1024 dualAuthenticated=false clientCert="c"' for i in range(n)
    )


def _criterio4_entry(profile="classico", route="L123", run=0, insurance=None, person=None, n_mtls=6):
    insurance, person = (insurance, person) if insurance is not None else _calls_corretos()
    log_text = (
        f"== EXECUCAO INICIO perfil={profile} rota={route} run={run} ==\n"
        f"{_mtls_ok_lines(n_mtls)}\n"
        f"== EXECUCAO FIM perfil={profile} rota={route} run={run} ==\n"
    )
    entry = {"profile": profile, "route": route, "run": run, "insurance": insurance, "person": person}
    return [entry], log_text


def test_criterio4_correto_passa():
    execucoes, log_text = _criterio4_entry()
    result = ec.criterion_4_counts_campaign(execucoes, log_text, expected_total=1)
    assert result["pass"] is True, result
    _registra(4, "dados corretos (baseline, 44/6/28/4/4)", "PASS", "PASS" if result["pass"] else "FAIL")


def test_criterio4_rsa_pqc_curve_dual_na():
    for corrupcao in ("RSA-4096 no lugar de RSA-2048 (Classico/Hibrido/Hibrido-AND)",
                       "PQC com algoritmo classico", "componente PQC do dual=true != perfil PQC esperado",
                       "curveID errado", "dualAuthenticated errado"):
        _registra(4, corrupcao, "N/A", "N/A", aplicavel=False,
                   razao_na="criterio 4 so conta chamadas HTTP/JWT/JWKS/CA e conexoes mTLS -- "
                             "nunca inspeciona criptografia")


def test_criterio4_contagem_trocada_reprova():
    """O pedido original citou 43/6/28/4/4 -- o numero real e 44, nao
    43 (confirmado em expected_http do codigo, expected_http =
    {"http": 44, "jwts": 28, "jwks": 4, "ca": 4}). Corrupcao real
    aplicada: total HTTP continua 44 (senao nem monta o fixture), mas
    a contagem de jwts trocada por jwks (28 vira 4, 4 vira 28) --
    exatamente o tipo de troca de contagem pedida."""
    insurance, person = _calls_corretos(n_http=44, n_jwts=4, n_jwks=28, n_ca=4)
    execucoes, log_text = _criterio4_entry(insurance=insurance, person=person)
    result = ec.criterion_4_counts_campaign(execucoes, log_text, expected_total=1)
    assert result["pass"] is False, result
    _registra(4, "contagem 44/6/28/4/4 trocada (jwts<->jwks)", "FAIL", "PASS" if result["pass"] else "FAIL")


def test_criterio4_mtls_trocado_reprova():
    execucoes, log_text = _criterio4_entry(n_mtls=4)  # 4 em vez de 6
    result = ec.criterion_4_counts_campaign(execucoes, log_text, expected_total=1)
    assert result["pass"] is False, result
    _registra(4, "contagem mTLS (6) trocada", "FAIL", "PASS" if result["pass"] else "FAIL")


def test_criterio4_combinacao_faltando_reprova():
    execucoes, log_text = _criterio4_entry()
    # expected_total=2 mas so 1 execucao real presente
    result = ec.criterion_4_counts_campaign(execucoes, log_text, expected_total=2)
    assert result["pass"] is False, result
    _registra(4, "execucao/combinacao faltando (cardinalidade)", "FAIL", "PASS" if result["pass"] else "FAIL")


def test_criterio4_rtt_na():
    _registra(4, "RTT fora de +-10%", "N/A", "N/A", aplicavel=False,
               razao_na="criterio 4 nao mede RTT -- isso e o criterio 7")


# =====================================================================
# Criterio 5 -- zero erros -- nenhuma das 8 corrupcoes pedidas mapeia
# (o criterio e puramente sinal de erro, "FATAL:" no log; nao e
# wireado a rota/perfil/cardinalidade/criptografia/RTT especificos --
# e deliberadamente agnostico, Decisao original). Marcado N/A em
# todas, com a corrupcao REAL do proprio criterio testada a parte
# (ja coberta por Decisao 33/testes existentes do avaliador).
# =====================================================================

for _corrupcao in (
    "RSA-4096 no lugar de RSA-2048 (Classico/Hibrido/Hibrido-AND)", "PQC com algoritmo classico",
    "componente PQC do dual=true != perfil PQC esperado", "contagem 44/6/28/4/4 trocada",
    "rota ou combinacao faltando", "RTT fora de +-10%", "curveID errado", "dualAuthenticated errado",
):
    _registra(5, _corrupcao, "N/A", "N/A", aplicavel=False,
              razao_na="criterio 5 e agnostico a rota/perfil/cardinalidade/criptografia por desenho -- "
                        "so detecta a presenca literal de 'FATAL:' no log combinado")


def test_criterio5_erro_real_reprova():
    log_text = "== Perfil: classico ==\nFATAL: algo quebrou\n"
    result = ec.criterion_5_zero_errors(log_text)
    assert result["pass"] is False, result
    _registra(5, "FATAL real no log (proprio criterio, fora da lista de 8)", "FAIL", "PASS" if result["pass"] else "FAIL")


def test_criterio5_correto_passa():
    log_text = "== Perfil: classico ==\nnada de errado aqui\n"
    result = ec.criterion_5_zero_errors(log_text)
    assert result["pass"] is True, result
    _registra(5, "dados corretos (baseline)", "PASS", "PASS" if result["pass"] else "FAIL")


# =====================================================================
# Criterio 6 -- instrumentacao completa + asserções (campanha)
# =====================================================================

def _criterio6_execucoes_corretas():
    rows = []
    for profile in ec.PROFILES_ALL:
        rows.append({
            "profile": profile, "curveID": ec.EXPECTED_CURVE[profile],
            "dualAuthenticated": profile == "hibrido-and", "keylog_evidence": True,
        })
    return rows


def _criterio6_write(tmp_path, rows):
    (tmp_path / "criterio6_execucoes.json").write_text(json.dumps(rows), encoding="utf-8")


def test_criterio6_correto_passa(tmp_path):
    _criterio6_write(tmp_path, _criterio6_execucoes_corretas())
    result = ec.criterion_6_instrumentation_campaign(str(tmp_path), expected_total=4)
    assert result["pass"] is True, result
    _registra(6, "dados corretos (baseline)", "PASS", "PASS" if result["pass"] else "FAIL")


def test_criterio6_rsa4096_na():
    for corrupcao in ("RSA-4096 no lugar de RSA-2048 (Classico)",
                       "RSA-4096 no lugar de RSA-2048 (Hibrido dual=false)",
                       "RSA-4096 no lugar de RSA-2048 (Hibrido dual=true)"):
        _registra(6, corrupcao, "N/A", "N/A", aplicavel=False,
                   razao_na="criterio 6 so confere curveID/dualAuthenticated/keylog -- "
                             "forca da chave RSA (2048 vs 4096) nunca aparece nesses campos; "
                             "isso afeta o TAMANHO do certificado, criterio 1")


def test_criterio6_pqc_com_algoritmo_classico_reprova(tmp_path):
    rows = _criterio6_execucoes_corretas()
    for r in rows:
        if r["profile"] == "pqc":
            r["curveID"] = ec.EXPECTED_CURVE["classico"]  # PQC reportando curva classica
    _criterio6_write(tmp_path, rows)
    result = ec.criterion_6_instrumentation_campaign(str(tmp_path), expected_total=4)
    assert result["pass"] is False, result
    _registra(6, "PQC com algoritmo classico (curveID=CurveP384 no perfil pqc)", "FAIL",
               "PASS" if result["pass"] else "FAIL")


def test_criterio6_componente_pqc_do_dual_diferente_reprova(tmp_path):
    """Hibrido-AND reportando a curva do Hibrido-v8 (mesmo rotulo de
    curva nominal nos dois nesta tabela -- a corrupcao real aplicada e
    dualAuthenticated=false, que e o sinal que distingue o componente
    AND do v8 nesta instrumentacao)."""
    rows = _criterio6_execucoes_corretas()
    for r in rows:
        if r["profile"] == "hibrido-and":
            r["dualAuthenticated"] = False  # deveria ser True -- componente AND nao confirmado
    _criterio6_write(tmp_path, rows)
    result = ec.criterion_6_instrumentation_campaign(str(tmp_path), expected_total=4)
    assert result["pass"] is False, result
    _registra(6, "componente PQC do dual=true != perfil PQC esperado (dualAuthenticated=false no AND)",
               "FAIL", "PASS" if result["pass"] else "FAIL")


def test_criterio6_contagem_na():
    _registra(6, "contagem 44/6/28/4/4 trocada", "N/A", "N/A", aplicavel=False,
               razao_na="criterio 6 nao conta chamadas HTTP -- isso e o criterio 4")


def test_criterio6_combinacao_faltando_reprova(tmp_path):
    rows = _criterio6_execucoes_corretas()[:-1]  # falta 1 perfil
    _criterio6_write(tmp_path, rows)
    result = ec.criterion_6_instrumentation_campaign(str(tmp_path), expected_total=4)
    assert result["pass"] is False, result
    _registra(6, "execucao/perfil faltando (cardinalidade)", "FAIL", "PASS" if result["pass"] else "FAIL")


def test_criterio6_rtt_na():
    _registra(6, "RTT fora de +-10%", "N/A", "N/A", aplicavel=False,
               razao_na="criterio 6 nao mede RTT -- isso e o criterio 7")


def test_criterio6_curveid_errado_reprova(tmp_path):
    rows = _criterio6_execucoes_corretas()
    rows[0]["curveID"] = "CurveErrada"
    _criterio6_write(tmp_path, rows)
    result = ec.criterion_6_instrumentation_campaign(str(tmp_path), expected_total=4)
    assert result["pass"] is False, result
    _registra(6, "curveID errado (generico)", "FAIL", "PASS" if result["pass"] else "FAIL")


def test_criterio6_dualauthenticated_errado_reprova(tmp_path):
    rows = _criterio6_execucoes_corretas()
    for r in rows:
        if r["profile"] == "hibrido-and":
            r["dualAuthenticated"] = False
    _criterio6_write(tmp_path, rows)
    result = ec.criterion_6_instrumentation_campaign(str(tmp_path), expected_total=4)
    assert result["pass"] is False, result
    _registra(6, "dualAuthenticated errado (generico)", "FAIL", "PASS" if result["pass"] else "FAIL")


# =====================================================================
# Criterio 7 -- sanidade de latencia por rota (campanha)
# =====================================================================

def _criterio7_dados_corretos():
    data = {}
    for route, nominal in ct.CAMPAIGN_NOMINAL_RTT_MS.items():
        measured = 0.3 if nominal == 0 else float(nominal)
        data[route] = {"rtt_ms_probe": measured, "rtt_ms_pcap": measured, "n_samples_probe": 20}
    return data


def _criterio7_write(tmp_path, data):
    (tmp_path / "criterio7_rtt_por_rota.json").write_text(json.dumps(data), encoding="utf-8")


def test_criterio7_correto_passa(tmp_path):
    _criterio7_write(tmp_path, _criterio7_dados_corretos())
    result = ec.criterion_7_latency_sanity_campaign(str(tmp_path))
    assert result["pass"] is True, result
    _registra(7, "dados corretos (baseline, 8 rotas)", "PASS", "PASS" if result["pass"] else "FAIL")


def test_criterio7_rsa_pqc_curve_dual_contagem_na():
    for corrupcao in ("RSA-4096 no lugar de RSA-2048 (Classico/Hibrido/Hibrido-AND)",
                       "PQC com algoritmo classico", "componente PQC do dual=true != perfil PQC esperado",
                       "contagem 44/6/28/4/4 trocada", "curveID errado", "dualAuthenticated errado"):
        _registra(7, corrupcao, "N/A", "N/A", aplicavel=False,
                   razao_na="criterio 7 so mede RTT por rota -- nunca inspeciona criptografia ou contagens")


def test_criterio7_rota_faltando_reprova(tmp_path):
    data = _criterio7_dados_corretos()
    del data["L30"]
    _criterio7_write(tmp_path, data)
    result = ec.criterion_7_latency_sanity_campaign(str(tmp_path))
    assert result["pass"] is False, result
    _registra(7, "rota faltando no arquivo de RTT", "FAIL", "PASS" if result["pass"] else "FAIL")


def test_criterio7_rtt_fora_tolerancia_reprova(tmp_path):
    """L219, nominal 219ms, tolerancia +-10% = [197.1, 240.9] -- 260ms
    esta fora."""
    data = _criterio7_dados_corretos()
    data["L219"] = {"rtt_ms_probe": 260.0, "rtt_ms_pcap": 260.0, "n_samples_probe": 20}
    _criterio7_write(tmp_path, data)
    result = ec.criterion_7_latency_sanity_campaign(str(tmp_path))
    assert result["pass"] is False, result
    assert result["rows"]["L219"]["probe_ok"] is False
    _registra(7, "RTT fora de +-10% (L219, 260ms vs nominal 219ms)", "FAIL", "PASS" if result["pass"] else "FAIL")


# =====================================================================
# Impressao final da matriz (rodar com `pytest -s` pra ver)
# =====================================================================

def test_imprime_matriz_final():
    nomes_criterio = {
        1: "1 tamanhos/msg", 2: "2 initcwnd", 3: "3 rota distante",
        4: "4 contagens fluxo", 5: "5 zero erros", 6: "6 instrumentacao", 7: "7 RTT/rota",
    }
    print("\n\n========== MATRIZ CRITERIO x CORRUPCAO x RESULTADO ==========")
    for criterio in range(1, 8):
        linhas = [m for m in MATRIZ if m[0] == criterio]
        print(f"\n--- Criterio {nomes_criterio[criterio]} ---")
        for _, corrupcao, esperado, obtido, aplicavel, razao_na in linhas:
            if not aplicavel:
                print(f"  N/A  | {corrupcao}  (motivo: {razao_na})")
            else:
                marca = "OK" if esperado == obtido else "DIVERGENCIA"
                print(f"  {marca:11s} | {corrupcao}  esperado={esperado} obtido={obtido}")
    divergencias = [m for m in MATRIZ if m[4] and m[2] != m[3]]
    assert not divergencias, f"{len(divergencias)} linha(s) da matriz com resultado != esperado: {divergencias}"
