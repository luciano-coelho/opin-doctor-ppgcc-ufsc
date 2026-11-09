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
# Decisao 65: ver orchestrator.py -- controle roda Python 3.9, `str |
# None` (PEP 604) so existe a partir do 3.10. Adia a avaliacao de
# anotacao pra string, zero mudanca de comportamento (nada aqui
# inspeciona anotacao em runtime).
from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
from collections import Counter

EXPECTED_CURVE = {
    "classico": "CurveP384",
    "pqc": "MLKEM1024",
    "hibrido-v8": "SecP384r1MLKEM1024",
    "hibrido-and": "SecP384r1MLKEM1024",
}

# DER, bytes -- do certificado REALMENTE embutido nas imagens pinadas
# (SERVER_IPS/SERVER_DNS default do certs/Makefile, Decisao 75 --
# nenhum rebuild de imagem pro piloto). Medido direto nos arquivos
# reais desta sessao (`ssl.PEM_cert_to_DER_cert`) -- confere exatamente
# com a tabela da Decisao 9 (DECISIONS.md linhas 896-901: servidor RSA
# 914, servidor ML-DSA 5.647, cliente RSA 801, cliente ML-DSA 5.534) e
# com a conferencia por sha256 contra `mockopin-v9-gateway:pinned`
# (Decisao 92/93). Movida pra ANTES de `CERTIFICATE_BASELINE` (Decisao
# 93) porque este agora e DERIVADO dela, nunca o contrario.
BASELINE_CERT_DER_SIZES = {
    "classico": {"in": 787, "out": 900},
    "pqc": {"in": 5506, "out": 5619},
    "hibrido-v8": {"in": 6131, "out": 6242},
    "hibrido-and": {"in": 801 + 5534, "out": 914 + 5647},
}


def _tls13_certificate_message_size(leaf_der_sizes: list, extra_extension_bytes: list = None) -> int:
    """Decisao 93 (Emenda -- CERTIFICATE_BASELINE recalibrado):
    deriva o tamanho da mensagem Certificate do TLS 1.3 a partir do(s)
    tamanho(s) DER REAL(is) do(s) certificado(s)-folha -- nunca uma
    constante copiada de uma medicao (pedido explicito do Luciano).
    Framing do RFC 8446, secao 4.4.2, confirmado byte a byte contra 2
    capturas reais independentes (Decisao 84, local; Decisao 92, AWS
    real) nos 4 perfis: 4B de cabecalho de handshake + 1B de
    `certificate_request_context` (sempre vazio aqui, so o byte de
    comprimento 0) + 3B de comprimento da `certificate_list` + por
    folha, 3B de comprimento do certificado + DER + 2B de comprimento
    de extensoes (+ bytes de extensao REAIS, 0 na folha RSA de todo
    perfil -- a UNICA excecao, Hibrido-AND, passa isso explicito)."""
    if extra_extension_bytes is None:
        extra_extension_bytes = [0] * len(leaf_der_sizes)
    content = 1 + 3 + sum(3 + d + 2 + e for d, e in zip(leaf_der_sizes, extra_extension_bytes))
    return content + 4


# Decisao 20 (item e) -- tolerancia POR MENSAGEM, calculada, nao suposta.
# Baseline = o tamanho da mensagem Certificate ISOLADA (Decisao 15),
# NAO o total do flight do servidor (esse e maior, inclui ServerHello/
# EncryptedExtensions/CertificateRequest/CertificateVerify/Finished
# tambem -- um erro real desta primeira versao do script, achado ao
# testar: usar o total do flight aqui reportava FAIL em todos os
# perfis, porque comparava a Certificate isolada contra um numero
# maior que nunca poderia bater).
#
# Decisao 28 (Emenda 1 ao criterio 1) + Decisao 29 (Emenda 2): a
# Emenda 1 PARTIU do valor medido do certificado embutido (o mesmo
# 913/5632/6255/6582 que esta Emenda 93 restaura -- ver o commit que
# introduziu a Emenda 1, "Baseline recalculado: 913-12=901,
# 5632-12=5620, 6255-12=6243, 6582-12=6570") e SUBTRAIU uma estimativa
# aritmetica (-12B) assumindo que o piloto trocaria o SAN de loopback
# (127.0.0.1,::1) por um SAN com dois IPs reais (IP privado + EIP). A
# Emenda 2 MEDIU essa troca de verdade (dois builds reais, so variando
# SERVER_IPS) e corrigiu o delta pra -14B (-28B no Hibrido-AND, 2
# folhas de servidor). As DUAS Emendas, porem, ficaram assentadas sobre
# uma premissa que a Decisao 75 (retomada desta rodada) derrubou
# explicitamente: **o piloto NUNCA troca o SAN** -- usa o certificado
# de loopback tal como ja esta embutido nas imagens pinadas, sem
# nenhum rebuild. A Decisao 75 confirmou isso por sha256 mas nunca
# reconferiu `CERTIFICATE_BASELINE` contra essa reversao -- o numero
# ficou com o delta de uma troca de SAN que nunca aconteceu.
#
# Decisao 93 (Emenda -- pedido do Luciano, opcao 2: corrigir por
# DERIVACAO, nunca por copia de um valor medido): com a premissa da
# Emenda 1/2 falsa (Decisao 75), o baseline correto e o mesmo valor
# MEDIDO que a propria Emenda 1 ja usava como ponto de partida --
# agora DERIVADO pela formula de `_tls13_certificate_message_size`
# a partir do DER REAL (`BASELINE_CERT_DER_SIZES`, acima), nunca
# copiado da medicao na AWS (que so CONFIRMOU o valor derivado,
# nunca foi a fonte dele). Residuo da soma por mensagem contra
# `BASELINE_HANDSHAKE_BYTES` (framing TLS/registro/AEAD, nunca parte
# desta convencao de "+4B por mensagem") fica CONSTANTE nos 4 perfis
# depois desta correcao (121B, saida; 77B, entrada) -- antes, so a
# entrada Certificate tinha residuo variavel (135/135/135/149);
# nenhuma outra entrada da tabela precisa de correcao.
#
# Decisao 42 (revisao independente, item D.10d, ainda valida): com o
# SAN FIXO (Decisao 75, nunca trocado) e o baseline agora DERIVADO (nao
# estimado nem medido-e-copiado), a unica fonte de variabilidade
# legitima que resta e o INTEIRO ASN.1 do numero de serie do
# certificado (1 byte extra de preenchimento sempre que o byte mais
# significativo tem o bit alto ligado -- nunca mais que +-2B por
# certificado-folha; +-4B no pior caso do Hibrido-AND, 2 folhas).
# +-4B flat continua a tolerancia certa.
CERTIFICATE_BASELINE = {
    "classico": _tls13_certificate_message_size([BASELINE_CERT_DER_SIZES["classico"]["out"]]),
    "pqc": _tls13_certificate_message_size([BASELINE_CERT_DER_SIZES["pqc"]["out"]]),
    "hibrido-v8": _tls13_certificate_message_size([BASELINE_CERT_DER_SIZES["hibrido-v8"]["out"]]),
    # Hibrido-AND: 2 folhas de servidor (Decisao 29) -- a formula
    # precisa dos DER INDIVIDUAIS (914 RSA + 5647 ML-DSA), nunca so a
    # soma que BASELINE_CERT_DER_SIZES guarda (confirmado == 6561 pelo
    # assert abaixo). A folha ML-DSA carrega 3B REAIS de extensao por
    # `CertificateEntry` que a folha RSA nao tem -- confirmado via o
    # campo `Certificates Length` do tshark (nunca o sub-parsing ASN.1
    # dessa folha, que o proprio tshark erra pra ML-DSA), igual nas 2
    # capturas reais independentes (Decisao 84 local, Decisao 92 AWS).
    "hibrido-and": _tls13_certificate_message_size([914, 5647], extra_extension_bytes=[0, 3]),
}
assert 914 + 5647 == BASELINE_CERT_DER_SIZES["hibrido-and"]["out"], (
    "DER individuais do Hibrido-AND usados em CERTIFICATE_BASELINE tem que somar "
    "exatamente o total que BASELINE_CERT_DER_SIZES ja guarda -- nunca divergir"
)
CERTIFICATE_TOLERANCE_B = 4

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
# Decisao 40 (revisao independente, item B.7): `ZERO_TOLERANCE_MESSAGES`
# nunca controlava nada depois da Emenda 4 (so documentava o nome) --
# removida, nao so comentada, por pedido explicito ("remova se nao e
# usado").

PROFILES_ALL = ("classico", "pqc", "hibrido-v8", "hibrido-and")
PILOT_ROUTES = ("L0", "L219", "L325")

# Decisao 55 (pedido independente, item 3): handshakeBytesIn/Out
# totais medidos no BUILD de certificado que produziu o historico
# citado (loopback, certs/generated default -- Decisao 14/17/18,
# DECISIONS.md linhas 1511-1519/1750-1751). "in" = bytes que o
# SERVIDOR recebe (cadeia do CLIENTE); "out" = bytes que o servidor
# manda (cadeia do SERVIDOR).
BASELINE_HANDSHAKE_BYTES = {
    "classico": {"in": 1513, "out": 1640},
    "pqc": {"in": 10728, "out": 10878},
    "hibrido-v8": {"in": 8397, "out": 8552},
    "hibrido-and": {"in": 11902, "out": 12177},
}

# Arquivos de certificado (relativos a certs/generated/) que compoem
# a cadeia de CADA lado, por perfil -- hibrido-and manda DUAS folhas
# (RSA+ML-DSA) em cada direcao, os outros 3 so uma.
CERT_FILES_BY_PROFILE = {
    "classico": {"client": ("classico_client.crt",), "server": ("classico_server.crt",)},
    "pqc": {"client": ("pqc_client.crt",), "server": ("pqc_server.crt",)},
    "hibrido-v8": {"client": ("hibrido_v8_client.crt",), "server": ("hibrido_v8_server.crt",)},
    "hibrido-and": {
        "client": ("hibrido_and_rsa_client.crt", "hibrido_and_mldsa_client.crt"),
        "server": ("hibrido_and_rsa_server.crt", "hibrido_and_mldsa_server.crt"),
    },
}

def _cert_der_size(cert_path) -> int:
    """Decisao 75, item 2 (pedido do Luciano): usa so a stdlib
    (`ssl.PEM_cert_to_DER_cert`, base64-decodifica o corpo do PEM --
    nunca reserializa o certificado) em vez de `cryptography`, que o
    controle real nao tem instalado por padrao. Mesmo tamanho DER que
    a implementacao anterior (PEM E base64 do DER, sem diferenca de
    enconding possivel) -- comportamento idêntico, so a dependencia
    muda."""
    pem_text = open(cert_path, "r", encoding="ascii").read()
    return len(ssl.PEM_cert_to_DER_cert(pem_text))


def deployed_cert_der_sizes(profile: str, certs_dir) -> dict:
    """Soma, por direcao, o tamanho DER real dos certificados que vao
    ser efetivamente apresentados nesta implantacao (`certs_dir` --
    tipicamente `certs/generated/` apos um `make certs` com SAN
    diferente do baseline)."""
    files = CERT_FILES_BY_PROFILE[profile]
    client_sum = sum(_cert_der_size(os.path.join(certs_dir, f)) for f in files["client"])
    server_sum = sum(_cert_der_size(os.path.join(certs_dir, f)) for f in files["server"])
    return {"in": client_sum, "out": server_sum}


def expected_handshake_bytes(profile: str, certs_dir) -> dict:
    """Decisao 55, item 3: baseline MEDIDO (Decisao 14) mais a
    diferenca entre a soma dos tamanhos DER dos certificados
    IMPLANTADOS agora e a dos certificados do BASELINE, por sentido --
    nao reestima do zero, so propaga a diferenca de certificado (a
    UNICA fonte de variacao legitima identificada na Decisao 54, item
    3, fora de SNI/tickets/MinVersion, todos ja controlados ou ja
    verificados por outro mecanismo). Diagnostico, NUNCA o gate --
    os limiares pre-registrados (0B ClientHello, +-4B Certificate, 0B
    demais) continuam sendo o criterio 1 oficial; isto so informa um
    desvio pra decisao humana (ver `run_smoke_gate`-like pausa,
    PILOT_READINESS.md)."""
    baseline = BASELINE_HANDSHAKE_BYTES[profile]
    baseline_der = BASELINE_CERT_DER_SIZES[profile]
    deployed_der = deployed_cert_der_sizes(profile, certs_dir)
    return {
        "profile": profile,
        "in": baseline["in"] + (deployed_der["in"] - baseline_der["in"]),
        "out": baseline["out"] + (deployed_der["out"] - baseline_der["out"]),
        "baseline": baseline, "baseline_der": baseline_der, "deployed_der": deployed_der,
    }


def _as_fail(criterion: int, name: str, note: str, **extra) -> dict:
    """Decisao 40 (revisao independente, item B.7, "entrada malformada
    sempre FAIL"): construtor comum pro caminho de erro de TODO
    criterio -- garante o mesmo formato (`pass: False` sempre, nunca
    None, nunca uma excecao sobe pro chamador) em qualquer lugar que
    precise devolver FAIL por dado ausente/malformado."""
    return {"criterion": criterion, "name": name, "pass": False, "note": note, **extra}


def _safe_criterion(criterion_number: int, criterion_name: str):
    """Decisao 40: decorator que envolve CADA funcao de criterio -- se
    qualquer coisa inesperada (tipo errado, campo faltando de um jeito
    que o proprio corpo da funcao nao previu, indice fora de faixa)
    chegar a estourar uma excecao, o resultado e FAIL com a excecao
    registrada na nota, nunca um traceback subindo pro chamador. Isso
    e deliberadamente uma rede de seguranca POR CIMA das checagens
    explicitas que cada funcao ja faz -- as checagens explicitas dao
    a nota especifica e util; este decorator so garante que uma
    checagem ESQUECIDA nunca se torna um crash em vez de um FAIL."""
    import functools

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as e:  # noqa: BLE001 -- intencional, ver docstring
                return _as_fail(criterion_number, criterion_name,
                                 f"entrada malformada, excecao inesperada capturada: {type(e).__name__}: {e}")
        return wrapper
    return decorator

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


def _finalize_message_sizes(profile: str, total_cert_bytes, clienthello_bytes, other: dict, **extra) -> dict:
    """Decisao 91 (Emenda -- bug de parsing do criterio 1, NUNCA mudanca
    de criterio): fatorado da cauda comum de `_message_sizes_for_profile`
    -- os limiares e a logica de pass/fail (0B ClientHello, +-4B
    Certificate, 0B demais mensagens) sao EXATAMENTE os mesmos de
    sempre (Decisao 20/28/29/30/31), venha o `total_cert_bytes`/
    `clienthello_bytes`/`other` do caminho legado (uma linha == um
    flight) ou do caminho consciente de stream/direcao (abaixo) --
    nenhum limiar, baseline ou tolerancia foi tocado por esta Emenda."""
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
    extra_ok = extra.pop("extra_ok", True)
    result = {
        "profile": profile,
        "certificate_bytes": total_cert_bytes, "certificate_baseline": cert_baseline,
        "certificate_tolerance": CERTIFICATE_TOLERANCE_B, "certificate_ok": cert_ok,
        "clienthello_bytes": clienthello_bytes, "clienthello_baseline": ch_baseline,
        "clienthello_tolerance": CLIENTHELLO_TOLERANCE_B, "clienthello_ok": ch_ok,
        "other_messages": other_rows,
        "ok": cert_ok and ch_ok and other_all_ok and extra_ok,
    }
    result.update(extra)
    return result


def _message_sizes_legacy(raw_lines: list[str], profile: str) -> dict:
    """Caminho ORIGINAL (de antes da Decisao 91), intocado por ela --
    uma linha do tshark == um flight completo (nunca visto fragmentado
    em loopback, achado da Decisao 90). Mantido byte a byte pra
    reproduzir exatamente os resultados antigos nas capturas de
    loopback de referencia (Decisao 91, item e de regressao) -- usado
    quando o produtor nunca emitiu
    as colunas stream/srcport/tcp.len (measure.sh local, T6, e o
    fixture sintetico do LocalExecutor)."""
    total_cert_bytes = None
    clienthello_bytes = None
    other = {}
    for line in raw_lines:
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
        elif "11" in types:
            if "11" in per_type:
                other["Certificate_cliente"] = per_type["11"]
            if "15" in per_type:
                other["CertificateVerify_cliente"] = per_type["15"]
            if "20" in per_type:
                other["Finished_cliente"] = per_type["20"]
        if types == ["1"]:
            clienthello_bytes = per_type["1"]
    return _finalize_message_sizes(profile, total_cert_bytes, clienthello_bytes, other, format="legacy")


def _parse_gateway_handshake_bytes(block: str):
    """Decisao 91, item (d): le a secao 'handshakeBytesIn/Out do
    gateway' (emitida por `dedicated_capture`, uma linha por conexao
    client-facing REAL, na mesma ordem cronologica que o gateway
    logou) -- `None` se a secao nao existir neste bloco (formato
    legado, que nunca tem nem precisa dela)."""
    m = re.search(r"handshakeBytesIn/Out.*?\n(.*?)(?:\n==|\Z)", block, re.S)
    if not m:
        return None
    pairs = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line:
            continue
        cols = line.split("\t")
        if len(cols) != 2:
            continue
        try:
            pairs.append((int(cols[0]), int(cols[1])))
        except ValueError:
            continue
    return pairs


def _classify_streams(raw_lines: list[str]) -> tuple[list, list, list]:
    """Fatorado de `_message_sizes_stream_aware` (Decisao 91) pra ser
    reusado tambem por `capture_decryption_complete` (pedido do
    Luciano, item 3 da rodada de correcao dos criterios 2/7 -- robustez
    de captura em L0): classifica cada mensagem por QUEM MANDOU
    (srcport == o do ClientHello => cliente, senao => servidor),
    agrupa por `tcp.stream`, mescla fragmentos do MESMO lado em linhas
    diferentes do MESMO stream, e exclui o carve-out interno (SNI !=
    "mtls", Decisao 91/36). Devolve `(stream_results, stream_errors,
    ignored_streams)` -- MESMA classificacao, nunca duplicada entre os
    dois chamadores."""
    rows = []
    for line in raw_lines:
        cols = line.split("\t")
        if len(cols) < 7:
            cols = cols + [""] * (7 - len(cols))
        frame_s, stream, srcport, tcp_len_s, types_s, lengths_s, sni = cols[0], cols[1], cols[2], cols[3], cols[4], cols[5], cols[6]
        if not frame_s or not stream or not srcport:
            continue
        try:
            frame = int(frame_s)
            tcp_len = int(tcp_len_s) if tcp_len_s else 0
        except ValueError:
            continue
        types = [t.strip() for t in types_s.split(",")] if types_s else []
        lengths = [int(x) for x in lengths_s.split(",")] if lengths_s else []
        rows.append({"frame": frame, "stream": stream, "srcport": srcport, "tcp_len": tcp_len,
                     "types": types, "lengths": lengths, "sni": sni})

    streams: dict[str, list] = {}
    for r in rows:
        streams.setdefault(r["stream"], []).append(r)
    stream_ids_in_order = sorted(streams.keys(), key=lambda s: min(rr["frame"] for rr in streams[s]))

    stream_results = []
    stream_errors = []
    ignored_streams = []
    for sid in stream_ids_in_order:
        srows = sorted(streams[sid], key=lambda rr: rr["frame"])
        client_srcport = None
        client_hello_sni = ""
        for r in srows:
            if r["types"] == ["1"]:
                client_srcport = r["srcport"]
                client_hello_sni = r["sni"]
                break
        if client_srcport is None:
            stream_errors.append({"stream": sid, "note": "ClientHello (type 1) nao encontrado neste stream -- direcao nao classificavel"})
            continue
        # Decisao 91 (achado ao validar localmente, item 4 do pedido:
        # "rode localmente... pra confirmar 4/4 perfis", ANTES de
        # qualquer nova tentativa real): o carve-out interno
        # (`matls-api.local`, auth chamando de volta a RS -- Decisao
        # 17/18/36, explicitamente excluido da contagem de criterio 4)
        # tambem atravessa a MESMA porta 443/interface capturada por
        # `dedicated_capture` quando a execucao real de negocio
        # (opin_flow.py) o disparar -- confirmado ao vivo, localmente,
        # contra o stack real (6 streams sni="mtls" + 7 streams
        # sni="matls-api.local" na MESMA captura). Nunca um dos "6"
        # client-facing -- excluido aqui pelo SNI real do ClientHello,
        # nunca contado como erro nem como divergencia.
        if client_hello_sni and client_hello_sni != "mtls":
            ignored_streams.append({"stream": sid, "sni": client_hello_sni,
                                     "note": "carve-out interno (SNI != \"mtls\") -- nunca uma das 6 conexoes client-facing"})
            continue

        server_per_type: dict = {}
        client_per_type: dict = {}
        clienthello_bytes = None
        last_handshake_frame = None
        for r in srows:
            if not r["types"]:
                continue
            last_handshake_frame = r["frame"]
            per_type_here = {t: l + 4 for t, l in zip(r["types"], r["lengths"])}
            if r["types"] == ["1"]:
                clienthello_bytes = per_type_here["1"]
                continue
            side = client_per_type if r["srcport"] == client_srcport else server_per_type
            side.update(per_type_here)

        other = {}
        for t, name in (("2", "ServerHello"), ("8", "EncryptedExtensions"), ("13", "CertificateRequest"),
                        ("15", "CertificateVerify_servidor"), ("20", "Finished_servidor")):
            if t in server_per_type:
                other[name] = server_per_type[t]
        for t, name in (("11", "Certificate_cliente"), ("15", "CertificateVerify_cliente"), ("20", "Finished_cliente")):
            if t in client_per_type:
                other[name] = client_per_type[t]

        raw_bytes = {"client": 0, "server": 0}
        for r in srows:
            if last_handshake_frame is not None and r["frame"] > last_handshake_frame:
                continue
            side_key = "client" if r["srcport"] == client_srcport else "server"
            raw_bytes[side_key] += r["tcp_len"]

        stream_results.append({
            "stream": sid, "clienthello_bytes": clienthello_bytes,
            "certificate_bytes": server_per_type.get("11"), "other_messages": other,
            "raw_bytes": raw_bytes,
        })

    return stream_results, stream_errors, ignored_streams


def _message_sizes_stream_aware(block: str, raw_lines: list[str], profile: str) -> dict:
    """Decisao 91 (Emenda ao mecanismo de medicao do criterio 1 -- NUNCA
    ao criterio em si, ver `_finalize_message_sizes`): caminho novo,
    usado quando o produtor (orchestrator.py `dedicated_capture`, ou
    um fixture sintetico de teste) emite as colunas extras `stream`/
    `srcport`/`tcp.len`. Classificacao por stream/direcao/SNI fatorada
    em `_classify_streams`.

    (c) Cada captura real tem 6 conexoes mTLS verdadeiras por execucao
    (opin_flow.py, `get_local_leg_cert_paths` -- N_mTLS=6, documentado
    e confirmado contra v7 desde 2026-09-14): a PRIMEIRA (cronologica)
    e o valor medido oficial; as outras 5 tem que ser IDENTICAS --
    qualquer divergencia e um achado (`stream_divergences`), nunca
    silenciosamente ignorado.

    (d) Verificacao de consistencia OBRIGATORIA: os bytes brutos TCP de
    cada stream (soma de tcp.len por direcao, do inicio do stream ate o
    ULTIMO frame que carrega uma mensagem de handshake) tem que fechar
    EXATAMENTE com `handshakeBytesIn`/`handshakeBytesOut` que o
    GATEWAY REAL logou pra essa mesma conexao (`countingConn`,
    business_server.go linha 90/116 -- conta bytes crus no socket, ANTES
    de qualquer TLS, exatamente o que tcpdump tambem ve) -- confirmado
    empiricamente contra uma captura local real antes desta Emenda
    (classico: raw_in=1513==gateway handshakeBytesIn=1513,
    raw_out=1640==handshakeBytesOut=1640, piloto/.../local_validation_
    criterio1_v2/classico_gateway_log.txt). Qualquer stream que nao
    fechar e REPROVADO -- nunca passa (`consistency`, dobra em `ok`)."""
    stream_results, stream_errors, ignored_streams = _classify_streams(raw_lines)

    # (c) divergencia entre as 6 conexoes -- a primeira e o valor medido.
    divergences = []
    if stream_results:
        rep = stream_results[0]
        for s in stream_results[1:]:
            if s["clienthello_bytes"] != rep["clienthello_bytes"]:
                divergences.append({"stream": s["stream"], "field": "clienthello_bytes",
                                     "representative": rep["clienthello_bytes"], "measured": s["clienthello_bytes"]})
            if s["certificate_bytes"] != rep["certificate_bytes"]:
                divergences.append({"stream": s["stream"], "field": "certificate_bytes",
                                     "representative": rep["certificate_bytes"], "measured": s["certificate_bytes"]})
            for key in set(rep["other_messages"]) | set(s["other_messages"]):
                rep_v, meas_v = rep["other_messages"].get(key), s["other_messages"].get(key)
                if rep_v != meas_v:
                    divergences.append({"stream": s["stream"], "field": key, "representative": rep_v, "measured": meas_v})

    # (d) consistencia obrigatoria contra handshakeBytesIn/Out do gateway real.
    gw_pairs = _parse_gateway_handshake_bytes(block)
    consistency = []
    if gw_pairs is None:
        consistency.append({"ok": False, "note": "secao 'handshakeBytesIn/Out do gateway' ausente -- "
                                                   "consistencia (Decisao 91, item d) nao verificavel, FAIL-closed"})
    else:
        for idx, s in enumerate(stream_results):
            if idx >= len(gw_pairs):
                consistency.append({"stream": s["stream"], "ok": False,
                                     "note": "sem linha correspondente de handshakeBytesIn/Out do gateway pra este stream"})
                continue
            gw_in, gw_out = gw_pairs[idx]
            raw_in, raw_out = s["raw_bytes"]["client"], s["raw_bytes"]["server"]
            consistency.append({
                "stream": s["stream"], "raw_in": raw_in, "raw_out": raw_out,
                "gateway_in": gw_in, "gateway_out": gw_out,
                "ok": raw_in == gw_in and raw_out == gw_out,
            })

    rep = stream_results[0] if stream_results else None
    extra_ok = (
        bool(stream_results) and not stream_errors and not divergences
        and all(c.get("ok") for c in consistency)
    )
    return _finalize_message_sizes(
        profile,
        rep["certificate_bytes"] if rep else None,
        rep["clienthello_bytes"] if rep else None,
        rep["other_messages"] if rep else {},
        format="stream_aware", n_streams=len(stream_results),
        stream_errors=stream_errors, ignored_streams=ignored_streams, stream_divergences=divergences,
        consistency=consistency, extra_ok=extra_ok,
    )


EXPECTED_MTLS_STREAMS_PER_CAPTURE = 6


def capture_decryption_complete(raw_lines: list[str], expected_streams: int = EXPECTED_MTLS_STREAMS_PER_CAPTURE) -> dict:
    """Pedido do Luciano (item 3, rodada de correcao dos criterios
    2/7): antes de aceitar uma captura dedicada do criterio 1 como
    final, confere decifragem IMEDIATA e COMPLETA -- cada uma das
    `expected_streams` conexoes mTLS client-facing reais (carve-out
    interno ja excluido por SNI, `_classify_streams`/Decisao 91)
    precisa ter o Certificate do SERVIDOR decifrado
    (`tls.handshake.type==11` legivel -- o sintoma real observado na
    Decisao 95 foi so ClientHello/ServerHello decifrarem em L0, nada
    depois, hipotese de keylog ainda nao totalmente flushado em disco
    quando `docker exec cat` roda, RTT quase zero nao da tempo de
    sobra). NUNCA decide tamanho nem divergencia -- so SE a captura
    decifrou o suficiente pra ser avaliada; `_message_sizes_stream_
    aware` continua sendo quem decide pass/fail de tamanho. Chamado
    por `orchestrator.py dedicated_capture` ANTES de aceitar uma
    tentativa como final -- decifragem incompleta aciona um RETRY
    (ate 3x), nunca mascara nem adivinha a causa; divergencia de
    TAMANHO (mesmo com decifragem completa) nunca aciona retry, e
    reportada como esta."""
    stream_results, stream_errors, ignored_streams = _classify_streams(raw_lines)
    missing_certificate = [s["stream"] for s in stream_results if s["certificate_bytes"] is None]
    complete = (
        len(stream_results) == expected_streams
        and not stream_errors
        and not missing_certificate
    )
    return {
        "complete": complete, "n_streams_classified": len(stream_results),
        "expected_streams": expected_streams, "streams_missing_certificate": missing_certificate,
        "stream_errors": stream_errors, "ignored_streams": ignored_streams,
    }


def _message_sizes_for_profile(block: str, profile: str) -> dict:
    """Extrai e confere os tamanhos por mensagem de UM bloco de log (um
    perfil, uma captura) -- fatorado pra ser chamado tanto no modo
    local (um log so, varios blocos '== Perfil:') quanto no modo
    piloto (Decisao 40, item B.7 -- 12 arquivos de captura separados,
    um por perfil x rota, cada um com exatamente este formato).

    Decisao 91 (Emenda -- bug de parsing, NUNCA mudanca do criterio 1
    nem dos limiares/baselines): despacha pro caminho legado (formato
    de 3 colunas, frame/tipos/tamanhos -- measure.sh local e o fixture
    sintetico, NUNCA fragmentados, preservado byte a byte pra
    regressao) ou pro caminho consciente de stream/direcao (formato de
    6 colunas, frame/stream/srcport/tcp.len/tipos/tamanhos --
    `dedicated_capture` real, onde a Decisao 90 achou que o flight do
    servidor pode chegar fragmentado em mais de uma linha sob rede
    real) conforme o numero de colunas que o PRODUTOR de fato emitiu."""
    msg_section = re.search(r"tamanho POR MENSAGEM.*?\n(.*?)(?:\n==|\Z)", block, re.S)
    if not msg_section:
        return _finalize_message_sizes(profile, None, None, {})
    raw_lines = [l for l in msg_section.group(1).splitlines() if l.strip()]
    if not raw_lines:
        return _finalize_message_sizes(profile, None, None, {})
    n_cols = len(raw_lines[0].split("\t"))
    if n_cols >= 6:
        return _message_sizes_stream_aware(block, raw_lines, profile)
    return _message_sizes_legacy(raw_lines, profile)


@_safe_criterion(1, "tamanhos por mensagem")
def criterion_1_message_sizes(log_text: str, aws_dir=None) -> dict:
    """Decisao 40 (revisao independente, item B.7): o criterio REAL
    exige as 12 capturas do piloto (4 perfis x 3 rotas) -- nao so "o
    que tiver no log local". Com `aws_dir`, le
    `<aws_dir>/criterio1_capturas/<perfil>_<rota>.log` pras 12
    combinacoes e EXIGE as 12 presentes, cada uma passando; sem
    `aws_dir` (modo local, Fase 1), mantem o comportamento anterior
    de ler os blocos '== Perfil:' do `log_text` dado, mas o resultado
    fica marcado explicitamente como parcial (nunca basta pra PASS
    sozinho fora do contexto do piloto real)."""
    if aws_dir:
        capturas_dir = os.path.join(aws_dir, "criterio1_capturas")
        results = []
        missing = []
        for profile in PROFILES_ALL:
            for route in PILOT_ROUTES:
                path = os.path.join(capturas_dir, f"{profile}_{route}.log")
                if not os.path.isfile(path):
                    missing.append(f"{profile}_{route}")
                    continue
                block = open(path, encoding="utf-8", errors="replace").read()
                row = _message_sizes_for_profile(block, profile)
                row["route"] = route
                results.append(row)
        ok = len(missing) == 0 and len(results) == 12 and all(r["ok"] for r in results)
        return {"criterion": 1, "name": "tamanhos por mensagem", "rows": results,
                "missing_captures": missing, "expected_captures": 12,
                "pass": ok,
                "note": "modo piloto -- exige as 12 capturas (4 perfis x 3 rotas)"}

    results = []
    for profile_block in re.finditer(
        r"== Perfil: (\S+), modo normal.*?(?=== Perfil:|\Z)", log_text, re.S
    ):
        profile = profile_block.group(1)
        results.append(_message_sizes_for_profile(profile_block.group(0), profile))
    # Decisao 33 (avaliador fail-closed): sem nenhum bloco de perfil no
    # log (arquivo vazio, caminho errado, execucao que nunca rodou),
    # o criterio tem que FALHAR -- nao "sem dados" (None), que o
    # relatorio final poderia confundir com "ainda nao relevante".
    # Ausencia de dado NUNCA e PASS nem N/A pra um criterio de ir/nao
    # ir -- e FAIL, ate prova em contrario.
    return {"criterion": 1, "name": "tamanhos por mensagem", "rows": results,
            "pass": all(r["ok"] for r in results) if results else False,
            "note": "avaliado so com o que o log local forneceu -- o criterio real exige as 12 capturas do piloto (4 perfis x 3 rotas)"}


# Decisao 36 (Emenda 8 ao criterio 4, poluicao do probe): "6
# conexoes mTLS client-facing" (Decisao 17/18, 44/6/28/4/4) nunca
# tinha sido wireada neste avaliador -- so verificada manualmente
# naquela rodada. Adicionada agora, contando as linhas "gateway: ...
# connection OK ..." que o `business_server.go` real escreve (linha
# 103, `acceptBusinessConn`) -- cada handshake TLS COMPLETO E BEM
# SUCEDIDO produz exatamente uma. O carve-out interno
# (`matls-api.local`, `internalCallerSNI`, auth chamando de volta a
# RS) e explicitamente EXCLUIDO da contagem -- nao e um dos "6"
# client-facing, e um canal interno separado (mesma logica da
# Decisao 18/19). O probe TCP/443 dedicado (Decisao 35) nunca produz
# essa linha -- ele nunca completa o handshake TLS (fecha a conexao
# antes de mandar qualquer coisa, ou nunca manda ClientHello), entao
# `tlsConn.Handshake()` retorna erro e o codigo real escreve
# "gateway: PERFIL: handshake failed: ..." (texto puro, linha 75 de
# `business_server.go`) em vez de "connection OK" -- EXCLUIDO POR
# CONSTRUCAO, sem precisar de nenhum filtro especial pro probe
# especificamente: so contar "connection OK" ja ignora qualquer
# tentativa que nao terminou um handshake de verdade.
_MTLS_CONNECTION_OK_RE = re.compile(r'gateway: \S+ connection OK remoteAddr=\S+ sni="([^"]*)"')
_INTERNAL_CALLER_SNI = "matls-api.local"
EXPECTED_MTLS_CONNECTIONS = 6
EXPECTED_EXECUCOES_PILOTO = 60


def _execucao_window(log_text: str, profile: str, route: str, run) -> str | None:
    """Decisao 40 (revisao independente, item B.6): a sondagem de
    prontidao (disparada uma vez por TROCA DE BLOCO DE PERFIL,
    Decisao 23) tambem completa um handshake mTLS de verdade (o proxy
    sempre disca a montante com seu certificado de cliente real,
    Decisao 18) -- contar "connection OK" no log INTEIRO, como a
    Decisao 36 fazia, soma a sondagem E as outras execucoes do mesmo
    bloco junto, nunca batendo com 6 por execucao. Corrigido: cada
    execucao e isolada por marcadores proprios no log combinado do
    piloto (emitidos pelo orquestrador, nao por esta funcao) --
    "== EXECUCAO INICIO perfil=X rota=Y run=N ==" ... "== EXECUCAO FIM
    ...==". A sondagem roda ANTES do primeiro marcador INICIO de cada
    bloco (na troca de perfil, Decisao 23), nunca entre um INICIO e um
    FIM -- estruturalmente fora de qualquer janela, sem filtro
    especial precisar reconhece-la."""
    pattern = re.compile(
        rf"== EXECUCAO INICIO perfil={re.escape(profile)} rota={re.escape(route)} run={re.escape(str(run))} ==(.*?)"
        rf"== EXECUCAO FIM perfil={re.escape(profile)} rota={re.escape(route)} run={re.escape(str(run))} ==",
        re.S,
    )
    m = pattern.search(log_text)
    return m.group(1) if m else None


def _http_counts_for_calls(calls_entry: dict) -> dict:
    calls1 = calls_entry.get("insurance", [])
    calls2 = calls_entry.get("person", [])
    all_calls = calls1 + calls2
    return {
        "http": len(all_calls),
        "jwts": sum(len(c.get("jwts") or []) for c in all_calls),
        "jwks": sum(1 for c in all_calls if c.get("endpoint") == "/jwks"),
        "ca": sum(1 for c in all_calls if c.get("endpoint") in ("/root-ca.pem", "/issuer-ca.pem")),
    }


@_safe_criterion(4, "contagens do fluxo")
def criterion_4_counts(execucoes: list | None, log_text: str = "") -> dict:
    """Decisao 40 (revisao independente, item B.6): avalia as 60/60
    execucoes do piloto (4 perfis x 3 rotas x N=5), nao um arquivo
    unico -- `execucoes` e uma LISTA de
    `{"profile", "route", "run", "insurance": [...], "person": [...]}`,
    uma por execucao real. Pra cada uma: as contagens HTTP vem do seu
    proprio `insurance`/`person`; a contagem mTLS (6, client-facing)
    vem SO da janela daquela execucao especifica no log combinado
    (`_execucao_window`), nunca do log inteiro."""
    if not execucoes:
        return {"criterion": 4, "name": "contagens do fluxo", "pass": False,
                "note": "nenhuma lista de execucoes fornecida -- precisa das 60 execucoes reais do piloto (T6b)"}
    expected_http = {"http": 44, "jwts": 28, "jwks": 4, "ca": 4}
    rows = []
    for entry in execucoes:
        profile, route, run = entry.get("profile"), entry.get("route"), entry.get("run")
        http_counts = _http_counts_for_calls(entry)
        window = _execucao_window(log_text, profile, route, run)
        if window is None:
            rows.append({"profile": profile, "route": route, "run": run,
                         "actual": http_counts, "expected": expected_http,
                         "mtls": None, "ok": False,
                         "note": "marcador de inicio/fim nao encontrado no log para esta execucao"})
            continue
        mtls = sum(1 for sni in _MTLS_CONNECTION_OK_RE.findall(window) if sni != _INTERNAL_CALLER_SNI)
        actual = {**http_counts, "mtls": mtls}
        expected = {**expected_http, "mtls": EXPECTED_MTLS_CONNECTIONS}
        rows.append({"profile": profile, "route": route, "run": run,
                     "actual": actual, "expected": expected, "ok": actual == expected})
    count_ok = len(execucoes) == EXPECTED_EXECUCOES_PILOTO
    all_ok = all(r["ok"] for r in rows)
    return {"criterion": 4, "name": "contagens do fluxo",
            "total_execucoes": len(execucoes), "expected_total": EXPECTED_EXECUCOES_PILOTO,
            "rows": rows, "pass": count_ok and all_ok}


@_safe_criterion(5, "zero erros")
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


@_safe_criterion(6, "instrumentacao completa + asserções")
def criterion_6_instrumentation(log_text: str, aws_dir=None) -> dict:
    """CurveID e DualAuthenticated por conexao, conferidos contra o
    esperado do perfil -- igual ao que a Decisao 14 ja fazia, so
    reempacotado como um criterio formal, automatico.

    Decisao 40 (revisao independente, item B.7, reconciliando com a
    Decisao 24): o TEXTO do criterio 6 pede "CurveID e
    DualAuthenticated em 60/60 execucoes, 0 falhas" -- nao "o que
    tiver no log local". Com `aws_dir`, le
    `<aws_dir>/criterio6_execucoes.json` (lista de 60
    `{"profile","route","run","curveID","dualAuthenticated",
    "keylog_evidence": bool}`) e EXIGE as 60 presentes, cada uma
    passando; sem `aws_dir` (modo local), mantem o comportamento
    anterior de contar as linhas "side":"gateway"/"proxy" do log
    dado, sem cardinalidade de 60 exigida (uso de desenvolvimento,
    nunca suficiente pro criterio real sozinho)."""
    if aws_dir:
        path = os.path.join(aws_dir, "criterio6_execucoes.json")
        if not os.path.isfile(path):
            return {"criterion": 6, "name": "instrumentacao completa + asserções", "pass": False,
                    "note": f"arquivo nao encontrado: {path}"}
        try:
            execucoes = json.load(open(path, encoding="utf-8"))
        except json.JSONDecodeError as e:
            return {"criterion": 6, "name": "instrumentacao completa + asserções", "pass": False,
                    "note": f"arquivo malformado ({e})"}
        if not isinstance(execucoes, list):
            return {"criterion": 6, "name": "instrumentacao completa + asserções", "pass": False,
                    "note": f"esperada uma lista, recebido {type(execucoes).__name__}"}
        rows = []
        for entry in execucoes:
            profile = entry.get("profile")
            curve, dual = entry.get("curveID"), entry.get("dualAuthenticated")
            keylog_ok = entry.get("keylog_evidence") is True
            want = EXPECTED_CURVE.get(profile)
            curve_ok = curve == want
            dual_ok = True
            if profile == "hibrido-and":
                dual_ok = dual is True
            ok = curve_ok and dual_ok and keylog_ok
            rows.append({**entry, "curve_expected": want, "curve_ok": curve_ok,
                         "dual_ok": dual_ok, "keylog_ok": keylog_ok, "ok": ok})
        count_ok = len(execucoes) == EXPECTED_EXECUCOES_PILOTO
        all_ok = all(r["ok"] for r in rows)
        return {"criterion": 6, "name": "instrumentacao completa + asserções",
                "total_execucoes": len(execucoes), "expected_total": EXPECTED_EXECUCOES_PILOTO,
                "rows": rows, "pass": count_ok and all_ok}

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
            "pass": all_ok and has_keylog_evidence and len(rows) > 0,
            "note": "modo local (sem --aws-dir) -- nao exige cardinalidade de 60, uso de desenvolvimento apenas"}


INITCWND_MIN_SEGMENTS = 10
INITCWND_MIN_BYTES_SENT = 64 * 1024  # 64KB -- o teste dedicado precisa mandar isso ou mais
# Decisao 37 (Emenda 9): diferenca maxima aceitavel, em SEGMENTOS,
# entre os dois canais independentes (bytes/MSS vs `ss -ti` cwnd).
# 2 segmentos -- margem suficiente pra absorver um pequeno desvio de
# tempo do snapshot do `ss -ti` (se uma ou duas ACKs iniciais ja
# chegaram antes do snapshot, o cwnd ja pode ter crescido um passo
# de slow-start alem do initcwnd puro) sem ser tao larga que deixe
# de detectar uma discordancia real entre os dois metodos.
INITCWND_MAX_DIFF_SEGMENTS = 2
L325_PROFILES = ("classico", "pqc", "hibrido-v8", "hibrido-and")
L325_N_PER_PROFILE = 5


@_safe_criterion(2, "initcwnd real")
def criterion_2_initcwnd(aws_dir) -> dict:
    """Decisao 34 (correcao de metodo -- a versao da Decisao 32/33
    estava errada por construcao): contar segmentos dentro do
    handshake TLS normal NUNCA prova initcwnd, porque o primeiro
    voo do servidor (1,6-12KB entre os 4 perfis, Decisao 31) e MENOR
    que 10xMSS (~14,5KB a MSS~1448B num path de MTU 1500) -- o
    servidor fica limitado por FALTA DE DADOS, nunca pelo cwnd, e
    contar segmentos ali so mediria "quantos segmentos cabem no
    handshake", nao o initcwnd real.

    Metodo redesenhado -- teste DEDICADO, separado das 60 execucoes
    estatisticas (mesma logica de separar captura de medicao
    cronometrada, Decisao 24): numa conexao NOVA, o servidor manda
    >=64KB (bem mais que qualquer cwnd inicial razoavel cobriria) --
    `bytes_sent_before_first_client_ack / mss_bytes` da o numero de
    segmentos que o cwnd inicial permitiu enviar sem esperar ACK.
    Confirmado por DOIS canais independentes: (1) `bytes_antes_do_
    ACK / MSS`, calculado aqui; (2) `ss -ti` logo depois da conexao,
    campo `cwnd` reportado pelo proprio kernel.

    Emenda MSS-efetivo (pedido do Luciano, apos a Decisao 95 achar que
    `mss_bytes` vinha do MSS ANUNCIADO no SYN-ACK do servidor --
    capacidade LOCAL da NIC/jumbo frame, nunca o MSS que de fato e
    usado no caminho real entre regioes, reduzido por PMTU discovery
    -- a AWS real mediu 8961B anunciado vs 1448B efetivo): desvio
    formal do pre-registro (Decisao 34 dizia "MSS lido das opcoes do
    SYN da mesma conexao" -- o codigo lia literalmente a opcao do
    SYN-ACK, que e exatamente a capacidade local, nunca o efetivo).
    `mss_bytes` agora so existe quando DOIS canais do MSS EFETIVO
    concordam (`criterio2_probe.py effective_mss`): (1) `ss -ti`,
    campo `mss` do proprio kernel; (2) o MAIOR payload real (`tcp.
    len`) que o servidor de fato colocou no fio. Se os dois
    discordarem, `mss_bytes` vem `None` no JSON e o criterio FALHA por
    essa razao especificamente (`mss_channels_agree=False`), nunca
    tenta adivinhar qual canal "esta certo". O MSS anunciado no
    SYN-ACK continua registrado (`mss_synack_announced_bytes`), so
    como diagnostico -- nunca entra no calculo de `segments_computed`.

    Decisao 37 (Emenda 9, corrige a Decisao 34): **reprovar so porque
    TSO/GSO estao ligados tornaria o criterio praticamente
    inalcancavel** -- GSO em particular costuma vir ligado por
    PADRAO no kernel das instancias EC2 usadas aqui (`m7i-flex.large`),
    e desliga-lo so pra este teste divergiria da v8 real (que nunca
    tocou nos offloads de nenhuma instancia) sem necessidade: contar
    bytes ENVIADOS antes do ACK e dividir pelo MSS NEGOCIADO
    independe de quantos "superpacotes" a NIC decidiu fazer no meio
    do caminho -- o numero de bytes e o MSS sao os mesmos, TSO/GSO
    ligado ou nao. **Corrigido: `ethtool -k` e sempre REGISTRADO como
    evidencia (nunca reprova por si so), e os offloads das instancias
    NAO sao alterados (equivalencia com a v8 real, que nunca mexeu
    nisso).** A decisao de pass/fail vem da CONCORDANCIA entre os
    dois canais independentes -- `segments_computed` (bytes/MSS) e
    `ss_ti_cwnd` -- dentro de `INITCWND_MAX_DIFF_SEGMENTS` (ver
    constante, com a justificativa de porque esse numero, nao outro).

    Formato esperado em `<aws_dir>/criterio2_initcwnd.json`:
    `{"bytes_sent_total": int, "bytes_sent_within_first_rtt_window": int,
    "mss_bytes": int|None, "mss_channels_agree": bool, "ss_ti_cwnd": int,
    "offloads": {"tso": "on"|"off", "gso": "on"|"off", "gro": "on"|"off"}}`
    -- `offloads` e sempre exigido no arquivo (pra garantir que foi de
    fato registrado), mas seu CONTEUDO nunca decide pass/fail.
    `mss_channels_agree` e exigido explicitamente -- ausente ou False
    reprova por si so (Emenda MSS-efetivo).

    Emenda robustez-de-janela (pedido do Luciano, achado real contra a
    AWS real -- Decisao 101 atribuiu `segments_computed=2,0` errado a
    TCP pacing; o pcap real provou que nao havia pacing nenhum, so um
    bug de contagem): `bytes_sent_within_first_rtt_window` (antes
    `bytes_sent_before_first_client_ack`) conta por TIMESTAMP DE ENVIO
    do servidor, dentro de 1 RTT medido na MESMA conexao -- nunca mais
    pelo numero do primeiro pacote de ACK visto (que sob RTT real pode
    cobrir so uma FRACAO do voo real, se o cliente mandar varios ACKs
    em cluster apertado, como confirmado por conteudo real)."""
    if not aws_dir:
        return {"criterion": 2, "name": "initcwnd real", "pass": False,
                "note": "nenhum --aws-dir fornecido -- sem teste dedicado, nao ha evidencia de initcwnd"}
    path = os.path.join(aws_dir, "criterio2_initcwnd.json")
    if not os.path.isfile(path):
        return {"criterion": 2, "name": "initcwnd real", "pass": False,
                "note": f"arquivo nao encontrado: {path}"}
    try:
        data = json.load(open(path, encoding="utf-8"))
        total = data["bytes_sent_total"]
        bytes_in_window = data["bytes_sent_within_first_rtt_window"]
        mss = data["mss_bytes"]
        mss_channels_agree = data["mss_channels_agree"]
        ss_cwnd = data["ss_ti_cwnd"]
        offloads = data["offloads"]
        # Decisao 40 (revisao independente, item B.8): o JSON precisa
        # identificar QUAL rota/instancia/perfil o teste dedicado
        # rodou em -- sem isso, um resultado isolado nao e
        # rastreavel de volta a onde (e em que contexto de perfil,
        # que afeta o tamanho do primeiro voo) ele foi medido.
        route = data["route"]
        instance_type = data["instance_type"]
        profile = data["profile"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return {"criterion": 2, "name": "initcwnd real", "pass": False,
                "note": f"arquivo malformado ou campo ausente ({e})"}
    if route not in PILOT_ROUTES or profile not in PROFILES_ALL:
        return {"criterion": 2, "name": "initcwnd real", "pass": False,
                "note": f"route={route!r}/profile={profile!r} nao reconhecidos"}
    # Pre-condicao: o proprio teste precisa ter mandado dado suficiente,
    # senao o resultado nao prova nada (mesmo problema que motivou a
    # correcao -- um teste pequeno de novo so mediria "quanto dado
    # havia", nao o cwnd). `offloads` e exigido no arquivo (confirma
    # que foi registrado) mas nunca participa do calculo de pass/fail
    # -- Decisao 37.
    if not isinstance(offloads, dict) or "tso" not in offloads or "gso" not in offloads or "gro" not in offloads:
        return {"criterion": 2, "name": "initcwnd real", "pass": False,
                "note": "campo 'offloads' ausente ou incompleto -- precisa ser registrado (tso/gso/gro), mesmo que nao decida o resultado"}
    # Emenda MSS-efetivo: `mss_channels_agree` precisa ser o booleano
    # True estritamente -- ausente, None ou False reprova por si so,
    # ANTES de qualquer calculo de segmentos (um `mss_bytes` vindo de
    # canais discordantes nunca pode ser usado, mesmo que por acidente
    # o resultado parecesse bater).
    if mss_channels_agree is not True:
        return {"criterion": 2, "name": "initcwnd real",
                "route": route, "instance_type": instance_type, "profile": profile,
                "mss_channels_agree": mss_channels_agree, "pass": False,
                "note": "os dois canais do MSS efetivo (ss -ti e maior payload real do pcap) discordam "
                        "(ou 'mss_channels_agree' ausente) -- Emenda MSS-efetivo, nunca usa um canal por default"}
    test_valid = isinstance(total, (int, float)) and total >= INITCWND_MIN_BYTES_SENT
    segments_computed = (bytes_in_window / mss) if (isinstance(bytes_in_window, (int, float)) and isinstance(mss, (int, float)) and mss > 0) else None
    segments_ok = segments_computed is not None and segments_computed >= INITCWND_MIN_SEGMENTS
    ss_ok = isinstance(ss_cwnd, (int, float)) and ss_cwnd >= INITCWND_MIN_SEGMENTS
    agree = (segments_computed is not None and isinstance(ss_cwnd, (int, float))
             and abs(segments_computed - ss_cwnd) <= INITCWND_MAX_DIFF_SEGMENTS)
    ok = test_valid and segments_ok and ss_ok and agree
    return {"criterion": 2, "name": "initcwnd real",
            "route": route, "instance_type": instance_type, "profile": profile,
            "mss_channels_agree": mss_channels_agree,
            "bytes_sent_total": total, "min_bytes_required": INITCWND_MIN_BYTES_SENT, "test_valid": test_valid,
            "segments_computed": segments_computed, "ss_ti_cwnd": ss_cwnd, "threshold": INITCWND_MIN_SEGMENTS,
            "max_diff_segments": INITCWND_MAX_DIFF_SEGMENTS, "agree": agree,
            "offloads": offloads,
            "pass": ok}


@_safe_criterion(3, "zero erros na rota mais distante")
def criterion_3_distant_route(aws_dir) -> dict:
    """Decisao 24, criterio 3: 0 erros em 20/20 execucoes (4 perfis x
    N=5) especificamente na rota `sa-east-1/L325`. Formato esperado
    em `<aws_dir>/criterio3_l325_execucoes.json`:
    `{"execucoes": [{"profile": ..., "route": "L325", "ok": true}, ...]}`
    -- exatamente 20 entradas, todas route=="L325", 4 perfis distintos
    x 5 cada, todas ok=true.

    Decisao 40 (revisao independente, item B.7): `ok` precisa ser o
    BOOLEANO `True`, estritamente -- `not e.get("ok")` (a versao
    anterior) e FALSO pra QUALQUER string nao-vazia, incluindo a
    string de texto `"false"` (um erro real de confusao de tipo: um
    JSON malformado com `"ok": "false"` em vez de `"ok": false`
    passaria como "sem erro" silenciosamente)."""
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
    if not isinstance(execs, list):
        return {"criterion": 3, "name": "zero erros na rota mais distante", "pass": False,
                "note": f"'execucoes' nao e uma lista ({type(execs).__name__})"}
    all_l325 = all(e.get("route") == "L325" for e in execs)
    count_ok = len(execs) == len(L325_PROFILES) * L325_N_PER_PROFILE
    per_profile = Counter(e.get("profile") for e in execs)
    profiles_ok = all(per_profile.get(p) == L325_N_PER_PROFILE for p in L325_PROFILES)
    errors = [e for e in execs if e.get("ok") is not True]
    ok = all_l325 and count_ok and profiles_ok and len(errors) == 0
    return {"criterion": 3, "name": "zero erros na rota mais distante",
            "total_execucoes": len(execs), "expected_total": len(L325_PROFILES) * L325_N_PER_PROFILE,
            "all_route_l325": all_l325, "profile_distribution_ok": profiles_ok,
            "errors_found": len(errors), "pass": ok}


# Decisao 38 (Emenda 10 ao criterio 7): limiar de concordancia
# EXPLICITO entre os dois canais (probe TCP/443 e pcap SYN/SYN-ACK),
# nunca deixado implicito. L0 usa diferenca ABSOLUTA (nominal 0ms,
# percentual nao faz sentido aqui pela mesma razao da Emenda 5) --
# 0,5ms da margem generosa sobre a propria precisao esperada dos dois
# metodos nessa escala (a v8 real mediu 0,14-0,18ms, uma dispersao de
# 0,04ms entre amostras do MESMO metodo -- 0,5ms cobre isso com
# folga, sem ser tao largo que aceite dois metodos discordando de
# verdade). L219/L325 usam diferenca PERCENTUAL -- 5% do NOMINAL da
# rota, deliberadamente MAIS ESTRITO que a faixa de aceitacao do
# criterio em si (±10%, Decisao 20/24): concordancia entre dois
# metodos medindo a MESMA grandeza fisica deve ser mais apertada que
# "dentro da faixa aceitavel", senao o cross-check nao adiciona rigor
# nenhum sobre o criterio individual.
RTT_CONSISTENCY_ABS_MS = {"L0": 0.5}
RTT_CONSISTENCY_FRACTION = 0.05
# Decisao 40 (revisao independente, item B.7): numero MINIMO de
# amostras do probe TCP/443 -- mesmo N=20 que a "Pre-flight TCP/443"
# real da v8 usou (v8/DECISIONS.md, linha 8546).
RTT_MIN_SAMPLES = 20


def _rtt_consistent(route: str, a: float, b: float) -> bool:
    """Decisao 35/38: os dois canais de RTT (probe TCP e pcap
    SYN/SYN-ACK) devem concordar dentro de uma margem EXPLICITA --
    nao e so cada um passar sozinho, e os dois baterem um com o outro
    (confirmacao cruzada de verdade, nao dois numeros soltos que por
    acaso passam cada um na sua faixa)."""
    if route in RTT_CONSISTENCY_ABS_MS:
        return abs(a - b) <= RTT_CONSISTENCY_ABS_MS[route]
    nominal = NOMINAL_RTT_MS[route]
    return abs(a - b) <= RTT_CONSISTENCY_FRACTION * nominal


@_safe_criterion(7, "sanidade de latencia por rota")
def criterion_7_latency_sanity(aws_dir) -> dict:
    """Decisao 24/32 (Emenda 5) + Decisao 35 (metodo corrigido): o
    desenho de seguranca do piloto (Decisao 27) so abre as portas 443
    e 22 -- ICMP (ping) NUNCA passaria pelo grupo de seguranca sem
    uma regra nova. Pesquisado direto `v8/DECISIONS.md` (linha 8546-
    8554) pra ver como a v8 real mediu RTT dentro de uma campanha
    TAMBEM restrita: **"Pre-flight TCP/443 (8 clientes, 20 amostras,
    3 perfis)"** -- um probe de CONEXAO TCP na porta 443 (nao ICMP),
    cujas medianas (L0 0,14-0,18ms, L123 122,9ms, L14 15,4ms, L219
    219,9ms, L30 32,3ms, L325 330,3ms) sao exatamente os numeros que
    este projeto ja vinha citando como "o que a v8 mediu". A v8 real
    TAMBEM tem um segundo metodo, usado na analise pos-campanha
    (linha 9970-9971): RTT = mediana do SYN->SYN-ACK das proprias
    conexoes TLS medidas, direto do pcap -- sem nenhuma conexao ou
    porta extra.

    **Metodo adotado pra v9, os dois juntos (confirmacao cruzada
    real, nao decorativa) -- nenhum dos dois precisa de ICMP:**
    1. `rtt_ms_probe`: probe de CONEXAO TCP na porta 443 (mesmo
       metodo da v8 real, "Pre-flight TCP/443") -- N amostras,
       mediana.
    2. `rtt_ms_pcap`: Emenda RTT-pcap (pedido do Luciano, apos a
       Decisao 95 achar que o metodo original -- SYN do cliente
       CHEGANDO -> SYN-ACK do servidor SAINDO, os DOIS eventos na
       MESMA interface do servidor -- media so tempo de PROCESSAMENTO
       local, zero propagacao de rede, nunca RTT real): agora mede a
       SEGUNDA metade do 3-way handshake, SYN-ACK do servidor SAINDO
       -> ACK do cliente fechando o handshake CHEGANDO de volta (ida+
       volta completas, servidor->cliente->servidor), direto da MESMA
       captura dedicada (criterio 1/2) das conexoes TLS reais, pareado
       por `tcp.stream` -- zero custo extra, zero ponto de captura
       novo, zero regra de SG nova.
    Os dois precisam (a) passar `_rtt_ok` individualmente e (b)
    CONCORDAR entre si (`_rtt_consistent`) -- se um canal disser
    "dentro da faixa" e o outro disser algo muito diferente, isso e
    sinal de erro de metodo, nao uma rota aprovada.

    **Nao precisa de regra de ICMP no grupo de seguranca** -- nenhum
    dos dois metodos usa ping. Se o Luciano quiser ping como um
    TERCEIRO canal (nao exigido por este criterio), precisa de uma
    regra nova explicita (echo request/reply, cada cliente <-> o
    servidor) -- nao incluida no roteiro por nao ser necessaria.

    Formato esperado em `<aws_dir>/criterio7_rtt_por_rota.json`:
    `{"L0": {"rtt_ms_probe": ..., "n_samples_probe": ..., "rtt_ms_pcap": ...}, "L219": {...}, "L325": {...}}`
    -- `n_samples_probe` e exigido (Decisao 40, item B.7): o numero de
    amostras do probe TCP/443 -- `RTT_MIN_SAMPLES` abaixo, o mesmo N=20
    que a "Pre-flight TCP/443" real da v8 usou.
    """
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
    if not isinstance(data, dict):
        return {"criterion": 7, "name": "sanidade de latencia por rota", "pass": False,
                "note": f"esperado um objeto JSON, recebido {type(data).__name__}"}
    rows = {}
    all_ok = True
    for route in NOMINAL_RTT_MS:
        entry = data.get(route)
        if not isinstance(entry, dict) or "rtt_ms_probe" not in entry or "rtt_ms_pcap" not in entry or "n_samples_probe" not in entry:
            rows[route] = {"rtt_ms_probe": None, "rtt_ms_pcap": None, "ok": False,
                           "note": "campos ausentes (rtt_ms_probe/rtt_ms_pcap/n_samples_probe)"}
            all_ok = False
            continue
        probe, pcap, n_samples = entry["rtt_ms_probe"], entry["rtt_ms_pcap"], entry["n_samples_probe"]
        # Decisao 40 (revisao independente, item B.7): RTT precisa ser
        # NUMERICO e NAO-NEGATIVO antes de qualquer outra checagem --
        # um bool `True` passaria `isinstance(x, (int,float))` em
        # Python (bool e subclasse de int), entao e explicitamente
        # excluido tambem.
        numeric_ok = (
            isinstance(probe, (int, float)) and not isinstance(probe, bool) and probe >= 0
            and isinstance(pcap, (int, float)) and not isinstance(pcap, bool) and pcap >= 0
        )
        samples_ok = isinstance(n_samples, int) and not isinstance(n_samples, bool) and n_samples >= RTT_MIN_SAMPLES
        if not (numeric_ok and samples_ok):
            rows[route] = {"rtt_ms_probe": probe, "rtt_ms_pcap": pcap, "n_samples_probe": n_samples,
                           "numeric_ok": numeric_ok, "samples_ok": samples_ok, "ok": False}
            all_ok = False
            continue
        probe_ok = _rtt_ok(route, probe)
        pcap_ok = _rtt_ok(route, pcap)
        consistent = _rtt_consistent(route, probe, pcap)
        ok = probe_ok and pcap_ok and consistent
        all_ok = all_ok and ok
        rows[route] = {
            "rtt_ms_probe": probe, "rtt_ms_pcap": pcap, "n_samples_probe": n_samples, "nominal_ms": NOMINAL_RTT_MS[route],
            "probe_ok": probe_ok, "pcap_ok": pcap_ok, "consistent": consistent, "ok": ok,
        }
    return {"criterion": 7, "name": "sanidade de latencia por rota", "rows": rows, "pass": all_ok}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-t6-log", required=True)
    ap.add_argument("--calls-json",
                     help="JSON com uma LISTA de execucoes (Decisao 40): "
                          '[{"profile","route","run","insurance":[...],"person":[...]}, ...]')
    ap.add_argument("--aws-dir")
    args = ap.parse_args()

    log_text = open(args.run_t6_log, encoding="utf-8", errors="replace").read()
    execucoes = json.load(open(args.calls_json)) if args.calls_json else None

    results = [
        criterion_1_message_sizes(log_text, args.aws_dir),
        criterion_2_initcwnd(args.aws_dir),
        criterion_3_distant_route(args.aws_dir),
        criterion_4_counts(execucoes, log_text),
        criterion_5_zero_errors(log_text),
        criterion_6_instrumentation(log_text, args.aws_dir),
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
