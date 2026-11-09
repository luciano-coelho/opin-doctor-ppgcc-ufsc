"""Decisao 91 (Emenda -- bug de parsing do criterio 1, NUNCA mudanca do
criterio em si, achado original na Decisao 90): testes do mecanismo NOVO
de `_message_sizes_for_profile` (evaluate_criteria.py) -- classificacao
por direcao (srcport), consciente de stream, com (c) deteccao de
divergencia entre as 6 conexoes mTLS reais de uma execucao e (d)
verificacao de consistencia obrigatoria contra handshakeBytesIn/Out do
gateway. Cobre tambem a REGRESSAO (item e): o caminho legado (3
colunas, measure.sh local/fixture sintetico) tem que continuar byte a
byte igual ao de antes desta Emenda, inclusive nas capturas de
loopback/rede-local REAIS de referencia (thesis/results/v9/campaign/
local_validation_criterio1_v2/, Decisao 84) -- usadas aqui tambem
porque, ao serem reextraidas com os campos novos, confirmam
empiricamente (nao so por fixture sintetico) que raw bytes TCP batem
exatamente com handshakeBytesIn/Out reais do gateway (ver DECISIONS.md,
Decisao 91)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "integration"))
import evaluate_criteria as ec  # noqa: E402

_REF_DIR = Path(__file__).resolve().parents[2] / "campaign" / "local_validation_criterio1_v2"


# --- Decisao 91, item (e): regressao byte a byte contra o caminho
# legado, usando capturas REAIS de referencia (nao so sinteticas).

_LEGACY_CLASSICO_BLOCK = """== Perfil: classico ==
tamanho POR MENSAGEM (frame, tipos, tamanhos)
4\t1\t332
6\t2,8,13,11,15,20\t183,6,105,909,260,32
8\t11,15,20\t796,260,32
== fim ==
"""

_STREAM_AWARE_CLASSICO_BLOCK = """== Perfil: classico ==
tamanho POR MENSAGEM (frame, stream, srcport, tcp.len, tipos, tamanhos)
4\t0\t52342\t341\t1\t332
6\t0\t443\t1640\t2,8,13,11,15,20\t183,6,105,909,260,32
8\t0\t52342\t1172\t11,15,20\t796,260,32
11\t0\t443\t24\t\t
== secao seguinte ==
handshakeBytesIn/Out do gateway, por conexao client-facing (ordem cronologica)
1513\t1640
== fim ==
"""
# Numeros reais, extraidos (Decisao 84/90) de classico.pcap/classico.
# keylog/classico_gateway_log.txt (thesis/results/v9/campaign/
# local_validation_criterio1_v2/) -- NUNCA inventados: handshakeBytesIn=
# 1513/handshakeBytesOut=1640 e o que o gateway REAL logou pra essa
# conexao; raw_in/raw_out abaixo fecham com eles byte a byte.


def test_regressao_legado_vs_stream_aware_batem_byte_a_byte_em_captura_real():
    legacy = ec._message_sizes_for_profile(_LEGACY_CLASSICO_BLOCK, "classico")
    new = ec._message_sizes_for_profile(_STREAM_AWARE_CLASSICO_BLOCK, "classico")
    assert legacy["format"] == "legacy"
    assert new["format"] == "stream_aware"
    for key in ("certificate_bytes", "certificate_ok", "clienthello_bytes", "clienthello_ok",
                "other_messages", "ok"):
        assert legacy[key] == new[key], f"{key}: legado={legacy[key]!r} novo={new[key]!r}"


def test_consistencia_do_item_d_fecha_com_handshake_bytes_reais_do_gateway():
    row = ec._message_sizes_for_profile(_STREAM_AWARE_CLASSICO_BLOCK, "classico")
    assert row["consistency"] == [
        {"stream": "0", "raw_in": 1513, "raw_out": 1640, "gateway_in": 1513, "gateway_out": 1640, "ok": True}
    ]


def test_mutante_gateway_bytes_divergentes_e_reprovado():
    """Mutacao: o log do gateway desta MESMA captura diz um numero
    diferente do que o pcap realmente mostrou -- tem que REPROVAR
    (Decisao 91, item d: "se nao fechar, o resultado e REPROVADO,
    nunca passa"), nunca passar so porque os limiares de criterio 1
    continuam batendo."""
    mutant_block = _STREAM_AWARE_CLASSICO_BLOCK.replace("1513\t1640", "1500\t1640")
    row = ec._message_sizes_for_profile(mutant_block, "classico")
    assert row["consistency"][0]["ok"] is False
    assert row["ok"] is False
    # confirma que o teste real (nao mutado) de fato passava antes:
    real_row = ec._message_sizes_for_profile(_STREAM_AWARE_CLASSICO_BLOCK, "classico")
    assert real_row["ok"] is True or not real_row["certificate_ok"]  # so o +14B de SAN documentado, nunca consistencia


def test_consistencia_ausente_e_fail_closed():
    """Decisao 33 (avaliador fail-closed) aplicada ao item (d): sem a
    secao de handshakeBytesIn/Out do gateway, a consistencia nunca
    pode passar por omissao."""
    block = _STREAM_AWARE_CLASSICO_BLOCK.split("== secao seguinte ==")[0] + "== fim ==\n"
    row = ec._message_sizes_for_profile(block, "classico")
    assert row["ok"] is False
    assert row["consistency"][0]["ok"] is False
    assert "ausente" in row["consistency"][0]["note"]


# --- Decisao 91, item (b): fragmentacao real -- o flight do servidor
# chega em DUAS linhas separadas (CertificateVerify+Finished numa
# linha sem ServerHello/Certificate junto) -- o bug ORIGINAL que a
# Decisao 90 achou ao vivo contra AWS real, reproduzido aqui como
# fixture sintetico determinístico pra nunca depender de rede real
# num teste.

_FRAGMENTED_BLOCK = """== Perfil: classico ==
tamanho POR MENSAGEM (frame, stream, srcport, tcp.len, tipos, tamanhos)
4\t7\t52342\t341\t1\t332
6\t7\t443\t950\t2,8,13,11\t183,6,105,909
7\t7\t443\t690\t15,20\t260,32
9\t7\t52342\t1172\t11,15,20\t796,260,32
== secao seguinte ==
handshakeBytesIn/Out do gateway, por conexao client-facing (ordem cronologica)
1513\t1640
== fim ==
"""


def test_flight_do_servidor_fragmentado_em_duas_linhas_e_reconstruido():
    """O achado da Decisao 90: sob rede real, tshark pode reportar
    CertificateVerify(15)+Finished(20) do SERVIDOR numa linha SEM
    ServerHello(2)/Certificate(11) -- o parser tem que classificar
    pela direcao (srcport), nunca pela coocorrencia de tipos na MESMA
    linha."""
    row = ec._message_sizes_for_profile(_FRAGMENTED_BLOCK, "classico")
    assert row["other_messages"]["CertificateVerify_servidor"]["bytes"] == 264
    assert row["other_messages"]["Finished_servidor"]["bytes"] == 36
    assert row["other_messages"]["CertificateVerify_servidor"]["ok"] is True
    assert row["other_messages"]["Finished_servidor"]["ok"] is True
    assert row["consistency"][0]["ok"] is True


def test_mutante_formato_legado_contra_a_mesma_fragmentacao_e_cego():
    """Mutacao = o comportamento ANTES desta Emenda: usando so 3
    colunas (sem stream/srcport), a mesma fragmentacao faz o parser
    legado NUNCA achar CertificateVerify_servidor/Finished_servidor
    (nenhuma linha tem "2" E "15"/"20" juntos) -- prova que o bug era
    real e que o teste acima de fato depende da correcao, nao passa
    por acidente."""
    legacy_text = "\n".join(
        line.split("\t", 1)[0] + "\t" + "\t".join(line.split("\t")[4:])
        for line in _FRAGMENTED_BLOCK.splitlines()
        if line and line[0].isdigit()
    )
    legacy_block = (
        "== Perfil: classico ==\ntamanho POR MENSAGEM (frame, tipos, tamanhos)\n"
        + legacy_text + "\n== fim ==\n"
    )
    row = ec._message_sizes_for_profile(legacy_block, "classico")
    assert row["other_messages"]["CertificateVerify_servidor"]["bytes"] is None
    assert row["other_messages"]["Finished_servidor"]["bytes"] is None
    assert row["ok"] is False


# --- Decisao 91, item (c): 6 conexoes mTLS reais por execucao
# (opin_flow.py, N_mTLS=6) -- a primeira e o valor medido, as outras 5
# tem que ser identicas.

def _six_identical_streams_block(profile="classico"):
    one = (
        "{frame0}\t{s}\t52342\t341\t1\t332\n"
        "{frame1}\t{s}\t443\t1640\t2,8,13,11,15,20\t183,6,105,909,260,32\n"
        "{frame2}\t{s}\t52342\t1172\t11,15,20\t796,260,32"
    )
    lines = ["tamanho POR MENSAGEM (frame, stream, srcport, tcp.len, tipos, tamanhos)"]
    gw_lines = ["handshakeBytesIn/Out do gateway, por conexao client-facing (ordem cronologica)"]
    base = 0
    for s in range(6):
        lines.append(one.format(frame0=base + 4, frame1=base + 6, frame2=base + 8, s=s))
        gw_lines.append("1513\t1640")
        base += 20
    return (f"== Perfil: {profile} ==\n" + "\n".join(lines) + "\n== secao seguinte ==\n"
            + "\n".join(gw_lines) + "\n== fim ==\n")


def test_seis_conexoes_identicas_passam_sem_divergencia():
    row = ec._message_sizes_for_profile(_six_identical_streams_block(), "classico")
    assert row["n_streams"] == 6
    assert row["stream_divergences"] == []
    assert all(c["ok"] for c in row["consistency"])
    assert len(row["consistency"]) == 6


def test_mutante_sexta_conexao_diverge_e_e_relatada_nunca_ignorada():
    """Mutacao: a SEXTA conexao mede um Certificate 2 bytes maior que
    as outras 5 -- Decisao 91, item (c): "qualquer divergencia e um
    achado a relatar, nunca ignorado" -- tem que aparecer em
    `stream_divergences` E reprovar `ok`."""
    block = _six_identical_streams_block()
    # a 6a conexao (stream "5") comeca em frame 4+5*20=104; sua linha
    # de servidor e frame0+2=106; seu Certificate (909) -> 911.
    mutant_block = block.replace(
        "106\t5\t443\t1640\t2,8,13,11,15,20\t183,6,105,909,260,32",
        "106\t5\t443\t1642\t2,8,13,11,15,20\t183,6,105,911,260,32",
    )
    assert mutant_block != block, "a substituicao da 6a conexao precisa casar com o texto gerado"
    row = ec._message_sizes_for_profile(mutant_block, "classico")
    assert row["ok"] is False
    assert any(d["field"] == "certificate_bytes" and d["stream"] == "5" for d in row["stream_divergences"])
    # confirma que a versao SEM mutacao de fato nao tinha esse achado:
    real_row = ec._message_sizes_for_profile(block, "classico")
    assert real_row["stream_divergences"] == []


def test_stream_sem_clienthello_e_relatado_e_reprova():
    """Um stream sem ClientHello (type 1) nao e classificavel por
    direcao -- fail-closed, nunca ignorado em silencio (vira `stream_
    errors`, nunca um stream_results fantasma)."""
    block = (
        "== Perfil: classico ==\n"
        "tamanho POR MENSAGEM (frame, stream, srcport, tcp.len, tipos, tamanhos)\n"
        "4\t0\t52342\t341\t1\t332\n"
        "6\t0\t443\t1640\t2,8,13,11,15,20\t183,6,105,909,260,32\n"
        "8\t0\t52342\t1172\t11,15,20\t796,260,32\n"
        "104\t1\t443\t1640\t2,8,13,11,15,20\t183,6,105,909,260,32\n"  # stream 1: sem ClientHello
        "== secao seguinte ==\n"
        "handshakeBytesIn/Out do gateway, por conexao client-facing (ordem cronologica)\n"
        "1513\t1640\n"
        "== fim ==\n"
    )
    row = ec._message_sizes_for_profile(block, "classico")
    assert row["ok"] is False
    assert row["stream_errors"] == [
        {"stream": "1", "note": "ClientHello (type 1) nao encontrado neste stream -- direcao nao classificavel"}
    ]
    # o stream 0 (valido) ainda e usado como representante -- nunca
    # None so porque outro stream do mesmo perfil deu erro.
    assert row["certificate_bytes"] == 913


# --- Decisao 91, achado AO VALIDAR LOCALMENTE (item 4 do pedido do
# Luciano, "rode localmente... pra confirmar 4/4 perfis" ANTES de
# qualquer nova tentativa real): rodando o fluxo de negocio REAL
# localmente (campaign_client_runner.py/opin_flow.py, nao so negtest),
# a MESMA captura "tcp port 443" tambem pega o carve-out interno de
# auth (sni="matls-api.local", Decisao 17/18/36 -- ja excluido da
# contagem do criterio 4) -- 7 streams extras na captura real, ao lado
# dos 6 "mtls" de verdade (ver thesis/results/v9/piloto/dados_oficiais/
# validacao-local-decisao-91/). Sem o 7o campo (SNI do ClientHello),
# esses 7 contaminariam `n_streams`/`stream_divergences` com uma
# negociacao TLS completamente diferente (CurveP256, outro cert).

_SIX_MTLS_PLUS_CARVEOUT_BLOCK = """== Perfil: classico ==
tamanho POR MENSAGEM (frame, stream, srcport, tcp.len, tipos, tamanhos, sni)
4\t0\t52342\t341\t1\t332\tmtls
6\t0\t443\t1640\t2,8,13,11,15,20\t183,6,105,909,260,32\t
8\t0\t52342\t1172\t11,15,20\t796,260,32\t
82\t3\t60942\t500\t1\t400\tmatls-api.local
88\t3\t443\t2000\t2,8,13,11,15,20\t183,6,105,4000,260,32\t
== secao seguinte ==
handshakeBytesIn/Out do gateway, por conexao client-facing (ordem cronologica)
1513\t1640
== fim ==
"""


def test_carve_out_interno_e_excluido_pelo_sni_nunca_contado_como_stream():
    row = ec._message_sizes_for_profile(_SIX_MTLS_PLUS_CARVEOUT_BLOCK, "classico")
    assert row["n_streams"] == 1
    assert row["stream_errors"] == []
    assert row["stream_divergences"] == []
    assert row["ignored_streams"] == [
        {"stream": "3", "sni": "matls-api.local",
         "note": "carve-out interno (SNI != \"mtls\") -- nunca uma das 6 conexoes client-facing"}
    ]
    # o Certificate do carve-out (4000+4=4004) NUNCA pode vazar pro
    # valor medido oficial (que tem que continuar vindo so do stream 0).
    assert row["certificate_bytes"] == 913


def test_mutante_sem_filtro_de_sni_carve_out_contaminaria_a_divergencia():
    """Mutacao = o comportamento ANTES deste achado: sem a coluna/
    filtro de SNI, o carve-out (Certificate=4004, bem diferente do
    stream 0) seria tratado como uma 2a conexao real e dispararia uma
    divergencia falsa -- prova que o filtro de SNI e necessario, nunca
    um acidente de teste."""
    # remove a 7a coluna (SNI) de toda linha, simulando o formato de
    # 6 colunas de ANTES deste achado.
    lines = []
    for line in _SIX_MTLS_PLUS_CARVEOUT_BLOCK.splitlines():
        cols = line.split("\t")
        if len(cols) == 7:
            lines.append("\t".join(cols[:6]))
        else:
            lines.append(line)
    mutant_block = "\n".join(lines)
    row = ec._message_sizes_for_profile(mutant_block, "classico")
    assert row["n_streams"] == 2  # o carve-out agora conta como stream real
    assert any(d["field"] == "certificate_bytes" and d["stream"] == "3" for d in row["stream_divergences"])
    assert row["ok"] is False


# --- Decisao 91, item (f): nunca ajustar o parser so pra passar -- se
# os totais fecham mas uma mensagem diverge do baseline, PARA e
# relata (continua FAIL, nunca vira PASS por acidente da correcao).

def test_item_f_totais_fecham_mas_mensagem_individual_diverge_continua_fail():
    """Mesmo com (c) e (d) OK (uma unica conexao, consistente), uma
    mensagem que mede fora do baseline pre-registrado tem que
    continuar FAIL -- a correcao desta Emenda NUNCA afrouxa os
    limiares oficiais do criterio 1."""
    # ServerHello 1 byte maior que o baseline (187 esperado -> 188).
    block = (
        "== Perfil: classico ==\n"
        "tamanho POR MENSAGEM (frame, stream, srcport, tcp.len, tipos, tamanhos)\n"
        "4\t0\t52342\t341\t1\t332\n"
        "6\t0\t443\t1641\t2,8,13,11,15,20\t184,6,105,909,260,32\n"
        "8\t0\t52342\t1172\t11,15,20\t796,260,32\n"
        "== secao seguinte ==\n"
        "handshakeBytesIn/Out do gateway, por conexao client-facing (ordem cronologica)\n"
        "1513\t1641\n"
        "== fim ==\n"
    )
    row = ec._message_sizes_for_profile(block, "classico")
    assert row["consistency"][0]["ok"] is True  # bytes brutos fecham...
    assert row["other_messages"]["ServerHello"]["ok"] is False  # ...mas a mensagem individual diverge
    assert row["ok"] is False  # ...e isso tem que continuar reprovando, nunca passar


# --- regressao adicional: os outros 3 perfis de referencia real
# (Decisao 84), legado vs stream-aware, mesma garantia da classico.

_REF_PROFILES = {
    "pqc": {
        "legacy": "4\t1\t1775\n6\t2,8,13\t1654,6,100\n8\t11,15,20\t5628,3313,32\n10\t11\t5515\n12\t15,20\t3313,32",
        "stream_aware": (
            "4\t0\t54408\t1784\t1\t1775\n"
            "6\t0\t443\t7240\t2,8,13\t1654,6,100\n"
            "8\t0\t443\t3638\t11,15,20\t5628,3313,32\n"
            "10\t0\t54408\t7240\t11\t5515\n"
            "12\t0\t54408\t1704\t15,20\t3313,32"
        ),
        "gateway": "10728\t10878",
    },
    "hibrido-v8": {
        "legacy": "4\t1\t1872\n6\t2,8,13\t1751,6,107\n8\t11,15,20\t6251,260,32\n10\t11,15,20\t6140,260,32",
        "stream_aware": (
            "4\t0\t43112\t1881\t1\t1872\n"
            "6\t0\t443\t7240\t2,8,13\t1751,6,107\n"
            "8\t0\t443\t1312\t11,15,20\t6251,260,32\n"
            "10\t0\t43112\t6516\t11,15,20\t6140,260,32"
        ),
        "gateway": "8397\t8552",
    },
    "hibrido-and": {
        "legacy": "4\t1\t1854\n6\t2,8,13\t1751,6,94\n8\t11,15,20\t6578,3571,32\n10\t11\t6352\n12\t15,20\t3571,32",
        "stream_aware": (
            "4\t0\t47650\t1863\t1\t1854\n"
            "6\t0\t443\t7240\t2,8,13\t1751,6,94\n"
            "8\t0\t443\t4937\t11,15,20\t6578,3571,32\n"
            "10\t0\t47650\t7240\t11\t6352\n"
            "12\t0\t47650\t2799\t15,20\t3571,32"
        ),
        "gateway": "11902\t12177",
    },
}


def test_regressao_e_consistencia_real_para_os_3_outros_perfis():
    """Mesmos numeros REAIS extraidos (Decisao 84/90) de pqc/hibrido-
    v8/hibrido-and.pcap+keylog+gateway_log.txt. Diferente do classico
    (unico dos 4 cuja captura de referencia NUNCA fragmenta o flight
    do servidor em mais de uma linha): estas 3 JA fragmentavam
    (Certificate do servidor sozinho, ou Certificate+CertificateVerify
    +Finished juntos mas SEM ServerHello na mesma linha) mesmo nesta
    rede LOCAL (Decisao 84, bridge Docker -- nunca precisou de AWS pra
    aparecer). O caminho LEGADO ja errava pra elas, de verdade, antes
    desta Emenda -- o teste documenta esse erro historico (nunca
    reescreve pra "passar"); o caminho novo acerta as 3, E fecha a
    consistencia (d) contra os handshakeBytesIn/Out reais."""
    for profile, data in _REF_PROFILES.items():
        legacy_block = f"== Perfil: {profile} ==\ntamanho POR MENSAGEM (frame, tipos, tamanhos)\n{data['legacy']}\n== fim ==\n"
        new_block = (
            f"== Perfil: {profile} ==\n"
            f"tamanho POR MENSAGEM (frame, stream, srcport, tcp.len, tipos, tamanhos)\n{data['stream_aware']}\n"
            f"== secao seguinte ==\n"
            f"handshakeBytesIn/Out do gateway, por conexao client-facing (ordem cronologica)\n{data['gateway']}\n"
            f"== fim ==\n"
        )
        legacy = ec._message_sizes_for_profile(legacy_block, profile)
        new = ec._message_sizes_for_profile(new_block, profile)

        # ClientHello nunca fragmenta (sempre a primeira mensagem,
        # sozinha) -- os dois caminhos SEMPRE tem que bater nele.
        assert legacy["clienthello_bytes"] == new["clienthello_bytes"], profile

        # Bug historico do caminho legado (real, nestas 3 capturas, ja
        # antes desta Emenda) -- documentado, nunca escondido:
        # ServerHello/CertificateVerify_servidor/Finished_servidor e o
        # proprio certificate_bytes do servidor nunca eram extraidos
        # (nenhuma linha tinha "2" E "11" juntos).
        assert legacy["certificate_bytes"] is None, f"{profile}: bug historico esperado (legado)"
        assert legacy["other_messages"]["ServerHello"]["bytes"] is None, profile
        assert legacy["other_messages"]["CertificateVerify_servidor"]["bytes"] is None, profile
        assert legacy["other_messages"]["Finished_servidor"]["bytes"] is None, profile
        assert legacy["ok"] is False

        # Caminho novo: acerta TODAS as mensagens do servidor contra o
        # baseline oficial (0B de tolerancia pras nao-Certificate).
        for key in ("ServerHello", "EncryptedExtensions", "CertificateRequest",
                    "CertificateVerify_servidor", "Finished_servidor",
                    "Certificate_cliente", "CertificateVerify_cliente", "Finished_cliente"):
            assert new["other_messages"][key]["ok"] is True, f"{profile}/{key}: {new['other_messages'][key]}"

        # (d) fecha exatamente contra o handshakeBytesIn/Out real.
        gw_in, gw_out = (int(x) for x in data["gateway"].split("\t"))
        assert new["consistency"] == [
            {"stream": "0", "raw_in": gw_in, "raw_out": gw_out, "gateway_in": gw_in, "gateway_out": gw_out, "ok": True}
        ]

        # Decisao 93: com o baseline corrigido (derivado do DER real),
        # o Certificate do servidor TAMBEM bate -- `ok` geral fica
        # True nos 4 perfis, nunca so as outras mensagens.
        assert new["certificate_ok"] is True, f"{profile}: {new['certificate_bytes']} vs {new['certificate_baseline']}"
        assert new["ok"] is True, profile


# --- Decisao 93 (Emenda -- CERTIFICATE_BASELINE recalibrado por
# DERIVACAO, nunca por copia de um valor medido): a Decisao 75 (mesma
# sessao) ja tinha revertido a premissa da Decisao 28/29 (SAN com IPs
# reais) -- o piloto usa o certificado de loopback tal como embutido
# nas imagens pinadas, sem rebuild -- mas CERTIFICATE_BASELINE nunca
# foi reconferido contra essa reversao. Corrigido aqui: derivado pela
# formula do RFC 8446 a partir do DER REAL (BASELINE_CERT_DER_SIZES,
# ja correto, nunca tocado), nunca copiado da medicao na AWS.

def test_formula_tls13_reproduz_o_baseline_derivado_para_1_folha():
    """Formula validada contra o unico caso sem nenhuma extensao de
    certificado: message = DER + 13 (4 cabecalho + 1 contexto + 3
    comprimento da lista + 3 comprimento do cert + 2 comprimento de
    extensoes)."""
    for profile in ("classico", "pqc", "hibrido-v8"):
        der = ec.BASELINE_CERT_DER_SIZES[profile]["out"]
        assert ec._tls13_certificate_message_size([der]) == der + 13
        assert ec.CERTIFICATE_BASELINE[profile] == der + 13


def test_formula_tls13_hibrido_and_duas_folhas_com_extensao_real_na_mldsa():
    """Hibrido-AND: 2 folhas de servidor -- formula generaliza pra
    message = 8 + soma_por_folha(DER_i + 5 + extensao_i); a folha
    ML-DSA carrega 3B reais de extensao (confirmado via 2 capturas
    reais independentes, Decisao 84/92), a RSA nao carrega nenhuma."""
    assert ec._tls13_certificate_message_size([914, 5647], extra_extension_bytes=[0, 3]) == 6582
    assert ec.CERTIFICATE_BASELINE["hibrido-and"] == 6582


def test_mutante_formula_sem_a_extensao_da_folha_mldsa_erra_o_hibrido_and():
    """Mutacao: omitir os 3B de extensao reais da folha ML-DSA (o
    mesmo erro que uma formula "generica demais" cometeria) erra o
    valor real por exatamente 3B -- prova que esse termo e necessario,
    nunca um ajuste cosmetico pra "fazer passar"."""
    mutant_value = ec._tls13_certificate_message_size([914, 5647])  # sem extra_extension_bytes
    assert mutant_value == 6579
    assert mutant_value != ec.CERTIFICATE_BASELINE["hibrido-and"]


def test_residuo_da_soma_por_mensagem_fica_constante_nos_4_perfis():
    """Decisao 93, item (c) do pedido do Luciano: com o Certificate
    corrigido, a soma dos baselines por mensagem contra o baseline de
    bytes totais do handshake (BASELINE_HANDSHAKE_BYTES) fecha com o
    MESMO residuo constante nos 4 perfis e nas 2 direcoes (121B saida,
    77B entrada -- framing de registro TLS/AEAD/ChangeCipherSpec, nunca
    parte da convencao "+4B por mensagem") -- prova que NENHUMA outra
    entrada da tabela precisa de correcao."""
    residuos_out, residuos_in = set(), set()
    for profile in ec.PROFILES_ALL:
        hb = ec.HANDSHAKE_MESSAGE_BASELINE[profile]
        total = ec.BASELINE_HANDSHAKE_BYTES[profile]
        out_sum = (hb["ServerHello"] + hb["EncryptedExtensions"] + hb["CertificateRequest"]
                   + ec.CERTIFICATE_BASELINE[profile] + hb["CertificateVerify_servidor"] + hb["Finished_servidor"])
        in_sum = (ec.CLIENTHELLO_BASELINE[profile] + hb["Certificate_cliente"]
                  + hb["CertificateVerify_cliente"] + hb["Finished_cliente"])
        residuos_out.add(total["out"] - out_sum)
        residuos_in.add(total["in"] - in_sum)
    assert residuos_out == {121}, residuos_out
    assert residuos_in == {77}, residuos_in


def test_mutante_certificate_baseline_nao_corrigido_dava_residuo_nao_constante():
    """Mutacao = o estado ANTES desta Emenda (899/5618/6241/6554,
    derivados da premissa falsa da Decisao 28/29) -- o residuo da
    soma por mensagem NUNCA era constante (variava 135/135/135/149,
    so por causa do Certificate), provando que essa era de fato a
    UNICA entrada inconsistente e que esta Emenda a corrigiu."""
    old_certificate_baseline = {"classico": 899, "pqc": 5618, "hibrido-v8": 6241, "hibrido-and": 6554}
    residuos_out = set()
    for profile in ec.PROFILES_ALL:
        hb = ec.HANDSHAKE_MESSAGE_BASELINE[profile]
        total = ec.BASELINE_HANDSHAKE_BYTES[profile]
        out_sum = (hb["ServerHello"] + hb["EncryptedExtensions"] + hb["CertificateRequest"]
                   + old_certificate_baseline[profile] + hb["CertificateVerify_servidor"] + hb["Finished_servidor"])
        residuos_out.add(total["out"] - out_sum)
    assert residuos_out == {135, 149}, residuos_out
    assert len(residuos_out) > 1  # nao-constante -- exatamente o sintoma que motivou a correcao


# --- Pedido do Luciano (item 3, rodada de correcao dos criterios 2/7):
# `capture_decryption_complete` -- confere decifragem IMEDIATA e
# COMPLETA das 6 conexoes mTLS reais ANTES de `dedicated_capture`
# aceitar uma tentativa de captura como final. Nunca decide tamanho.

def _stream_lines(n_complete=6, missing_certificate_in=(), carve_out_streams=0, frame_start=1):
    """Monta linhas sinteticas no formato de 7 colunas (frame, stream,
    srcport, tcp.len, tipos, tamanhos, sni) -- `n_complete` streams
    client-facing (sni=mtls), com Certificate (tipo 11) do servidor
    OMITIDO nos streams cujo indice esta em `missing_certificate_in`
    (simula decifragem parcial -- so ClientHello/ServerHello, nada
    depois, o sintoma real da Decisao 95 em L0); `carve_out_streams`
    streams adicionais com sni != "mtls" (carve-out interno, Decisao
    91/36), que precisam ser EXCLUIDOS, nunca contados."""
    lines = []
    frame = frame_start
    for i in range(n_complete):
        sid = str(i)
        lines.append(f"{frame}\t{sid}\t52342\t332\t1\t332\tmtls"); frame += 1
        if i in missing_certificate_in:
            lines.append(f"{frame}\t{sid}\t443\t189\t2\t183\t"); frame += 1
        else:
            lines.append(f"{frame}\t{sid}\t443\t1640\t2,8,13,11,15,20\t183,6,105,909,260,32\t"); frame += 1
    for j in range(carve_out_streams):
        sid = str(100 + j)
        lines.append(f"{frame}\t{sid}\t52342\t332\t1\t332\tmatls-api.local"); frame += 1
        lines.append(f"{frame}\t{sid}\t443\t1640\t2,8,13,11,15,20\t183,6,105,909,260,32\t"); frame += 1
    return lines


def test_capture_decryption_complete_6_streams_decifrados_e_completa():
    lines = _stream_lines(n_complete=6, carve_out_streams=1)
    result = ec.capture_decryption_complete(lines)
    assert result["complete"] is True
    assert result["n_streams_classified"] == 6
    assert result["streams_missing_certificate"] == []
    assert len(result["ignored_streams"]) == 1  # carve-out excluido, nunca contado


def test_capture_decryption_complete_l0_parcial_e_incompleta():
    """Reproduz o sintoma real da Decisao 95 em L0: 1 das 6 conexoes
    so decifrou ClientHello/ServerHello (Certificate do servidor
    ausente) -- precisa ser detectado como incompleto, pra acionar o
    retry de captura (orchestrator.py), nunca aceito como final."""
    lines = _stream_lines(n_complete=6, missing_certificate_in=(3,))
    result = ec.capture_decryption_complete(lines)
    assert result["complete"] is False
    assert result["streams_missing_certificate"] == ["3"]


def test_capture_decryption_complete_menos_de_6_streams_e_incompleta():
    lines = _stream_lines(n_complete=5)
    result = ec.capture_decryption_complete(lines)
    assert result["complete"] is False
    assert result["n_streams_classified"] == 5


def test_mutante_capture_decryption_complete_ignora_certificate_ausente():
    """Mutante: aceita como completo so por contar streams, sem
    conferir se o Certificate de cada um decifrou -- tem que divergir
    do resultado real (que reprova por causa do stream 3)."""
    lines = _stream_lines(n_complete=6, missing_certificate_in=(3,))
    stream_results, stream_errors, ignored_streams = ec._classify_streams(lines)
    mutant_complete = len(stream_results) == 6 and not stream_errors  # mutante: nunca confere certificate_bytes
    real = ec.capture_decryption_complete(lines)
    assert mutant_complete is True
    assert real["complete"] is False
    assert mutant_complete != real["complete"]


# --- Emenda MSS-efetivo ao criterio 2 (pedido do Luciano, apos a
# Decisao 95 achar que `mss_bytes` vinha do MSS anunciado no SYN-ACK,
# nunca o MSS efetivo real): `criterion_2_initcwnd` agora exige
# `mss_channels_agree` == True estritamente, antes de qualquer calculo
# de segmentos.

def _criterio2_json(tmp_path, **overrides):
    import json as _json
    data = {
        "route": "L219", "instance_type": "m7i-flex.large", "profile": "classico",
        "bytes_sent_total": 71680, "bytes_sent_within_first_rtt_window": 14480,
        "mss_bytes": 1448, "mss_channels_agree": True, "ss_ti_cwnd": 10,
        "offloads": {"tso": "off", "gso": "off", "gro": "off"},
    }
    data.update(overrides)
    (tmp_path / "criterio2_initcwnd.json").write_text(_json.dumps(data), encoding="utf-8")
    return tmp_path


def test_criterion_2_passa_quando_canais_de_mss_concordam(tmp_path):
    _criterio2_json(tmp_path)
    result = ec.criterion_2_initcwnd(str(tmp_path))
    assert result["pass"] is True, result
    assert result["segments_computed"] == 10.0


def test_criterion_2_reprova_quando_mss_channels_agree_e_false(tmp_path):
    """Reproduz o achado real da Decisao 95: canais discordando
    (SYN-ACK anunciava 8961, efetivo real era 1448) -- tem que
    reprovar por essa razao especificamente, mesmo que `mss_bytes`
    estivesse preenchido com algum numero."""
    _criterio2_json(tmp_path, mss_channels_agree=False)
    result = ec.criterion_2_initcwnd(str(tmp_path))
    assert result["pass"] is False
    assert result["mss_channels_agree"] is False


def test_criterion_2_reprova_quando_mss_channels_agree_ausente(tmp_path):
    data_path = tmp_path / "criterio2_initcwnd.json"
    _criterio2_json(tmp_path)
    import json as _json
    data = _json.loads(data_path.read_text(encoding="utf-8"))
    del data["mss_channels_agree"]
    data_path.write_text(_json.dumps(data), encoding="utf-8")
    result = ec.criterion_2_initcwnd(str(tmp_path))
    assert result["pass"] is False
    assert "malformado ou campo ausente" in result["note"]


def test_mutante_criterion_2_sem_exigir_mss_channels_agree_passaria_errado(tmp_path):
    """Mutante = o comportamento ANTIGO (antes da Emenda MSS-efetivo):
    nunca confere `mss_channels_agree`, so usa `mss_bytes` direto --
    com o MESMO JSON que discorda de verdade (Decisao 95), o mutante
    passaria incorretamente onde o codigo real reprova."""
    _criterio2_json(tmp_path, mss_bytes=8961, mss_channels_agree=False,
                     bytes_sent_within_first_rtt_window=2896)
    real = ec.criterion_2_initcwnd(str(tmp_path))
    assert real["pass"] is False

    # mutante: replica a logica ANTIGA (sem o bloqueio de mss_channels_agree)
    segments_mutante = 2896 / 8961
    mutant_pass = segments_mutante >= ec.INITCWND_MIN_SEGMENTS  # nunca bate (0,32 < 10) neste caso real,
    assert mutant_pass is False  # mas o PONTO é que o mutante nem olha mss_channels_agree pra decidir --
    # um JSON formulado pra enganar o mutante (ss_ti_cwnd baixo TAMBEM, concordando com o numero errado
    # do SYN-ACK) mostra a lacuna real: o mutante aceitaria uma concordancia ACIDENTAL entre
    # segments_computed (com MSS errado) e ss_ti_cwnd, enquanto o codigo real bloqueia MESMO ASSIM
    # por causa de mss_channels_agree=False.
    _criterio2_json(tmp_path, mss_bytes=8961, mss_channels_agree=False,
                     bytes_sent_within_first_rtt_window=89610, ss_ti_cwnd=10)
    real2 = ec.criterion_2_initcwnd(str(tmp_path))
    assert real2["pass"] is False  # bloqueado por mss_channels_agree, nunca chega a calcular segments
    segments_mutante2 = 89610 / 8961  # = 10.0 -- bateria "certo" com ss_ti_cwnd=10 por ACIDENTE
    assert segments_mutante2 == 10.0
    assert segments_mutante2 >= ec.INITCWND_MIN_SEGMENTS  # o mutante passaria aqui -- a razao exata da Emenda
