"""Testes dos produtores dedicados dos criterios 2/3/7 (Decisao 85) --
so a matematica/logica pura e testavel sem Docker/tshark reais; a
orquestracao remota (SSH/scp) e testada em test_dedicated_criteria.py."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "integration" / "producers"))
import criterio2_probe as c2  # noqa: E402
import criterio3_collector as c3  # noqa: E402
import criterio7_rtt as c7  # noqa: E402


def test_tshark_argv_roda_dentro_do_measure_nunca_bare_no_host():
    """Decisao 85 (achado real): o servidor real nunca tem `tshark` no
    PATH do host -- os dois produtores tem que rodar via `docker run
    ... mockopin-v9-measure`, nunca `tshark` bare."""
    argv_c2 = c2._tshark_argv("/tmp/criterio2.pcap")
    assert argv_c2[:2] == ["docker", "run"]
    assert "mockopin-v9-measure" in argv_c2
    assert "/tmp/criterio2.pcap" in argv_c2

    argv_c7 = c7._tshark_argv("/tmp/criterio1_classico_L219.pcap")
    assert argv_c7[:2] == ["docker", "run"]
    assert "mockopin-v9-measure" in argv_c7


def test_mutante_tshark_bare_e_pego():
    """Mutante: volta pro `tshark` bare -- os dois testes acima tem
    que reprovar com essa mutacao."""
    mutant_argv = ["tshark", "-r", "/tmp/x.pcap"]
    assert mutant_argv[:2] != ["docker", "run"]


def test_rtt_from_synack_ack_times_mediana_correta():
    pairs = [(1000.000, 1000.010), (1001.000, 1001.030), (1002.000, 1002.020)]  # deltas: 10ms, 30ms, 20ms -- mediana 20ms
    result = c7.rtt_from_synack_ack_times(pairs)
    assert result == {"rtt_ms_pcap": 20.0, "n_samples_pcap": 3}


# --- Emenda RTT-pcap (pedido do Luciano, apos a Decisao 95): o canal
# pcap tinha que medir SYN-ACK(saida)->ACK(entrada) no servidor
# (segunda metade do round-trip, RTT real), nunca SYN(entrada)->
# SYN-ACK(saida) (os dois na MESMA interface, so tempo de
# processamento local, zero propagacao de rede).

def test_pair_synack_ack_by_stream_pareia_por_stream_nunca_por_ordem():
    # 2 streams intercalados (Decisao 91 ja confirmou isso acontece sob
    # rede real) -- synack do stream 1 chega DEPOIS do synack do stream
    # 0, mas o ACK do stream 0 chega DEPOIS do ACK do stream 1.
    synack_lines = ["0\t1000.000", "1\t1000.005"]
    ack_lines = ["1\t1000.025", "0\t1000.040"]  # stream 1: RTT=20ms; stream 0: RTT=40ms
    result = c7.pair_synack_ack_by_stream(synack_lines, ack_lines)
    assert result == {"rtt_ms_pcap": 30.0, "n_samples_pcap": 2}  # mediana de [40,20]


def test_mutante_syn_synack_mede_so_processamento_local_nunca_rtt():
    """Mutante = o metodo ANTIGO (SYN chegando -> SYN-ACK saindo, os
    dois na MESMA interface do servidor): mesmo cenario realista (RTT
    real de 40ms, mas o servidor so leva 2ms pra responder) -- o
    metodo antigo mediria 2ms (tempo de processamento), nunca os 40ms
    reais que o metodo novo (SYN-ACK saida -> ACK volta) mede."""
    syn_in = [1000.000]
    synack_out = [1000.002]  # 2ms de processamento local
    ack_in = [1000.042]      # 40ms depois do SYN-ACK sair = RTT real
    old_method = c7.rtt_from_synack_ack_times(list(zip(syn_in, synack_out)))  # SYN->SYN-ACK
    new_method = c7.rtt_from_synack_ack_times(list(zip(synack_out, ack_in)))  # SYN-ACK->ACK
    assert old_method["rtt_ms_pcap"] == 2.0
    assert new_method["rtt_ms_pcap"] == 40.0
    assert old_method["rtt_ms_pcap"] != new_method["rtt_ms_pcap"]


# --- Decisao 94 (achado real, ao vivo, Passo 11.5): a AMI real
# (Amazon Linux 2023) nao tem `ethtool` instalado -- um
# `FileNotFoundError` aqui derrubava o script INTEIRO, mesmo este
# campo (Decisao 37) nunca decidindo o resultado do criterio 2.

def test_ethtool_offloads_ausente_nunca_derruba_o_script(monkeypatch):
    def fake_run_sem_ethtool(cmd, **kw):
        raise FileNotFoundError(2, "No such file or directory", "ethtool")

    monkeypatch.setattr(c2, "run", fake_run_sem_ethtool)
    result = c2.ethtool_offloads("eth0")
    assert result == {"tso": "indisponivel", "gso": "indisponivel", "gro": "indisponivel"}


def test_mutante_ethtool_offloads_sem_try_except_quebra_o_script(monkeypatch):
    """Mutacao = o comportamento ANTES desta Decisao: sem o try/except,
    a mesma situacao (ethtool ausente) propaga `FileNotFoundError`
    cru -- prova que o teste acima de fato depende do tratamento,
    nunca passa por acidente."""
    def fake_run_sem_ethtool(cmd, **kw):
        raise FileNotFoundError(2, "No such file or directory", "ethtool")

    monkeypatch.setattr(c2, "run", fake_run_sem_ethtool)

    def mutant_ethtool_offloads(iface):
        out = c2.run(["ethtool", "-k", iface]).stdout  # mutante: nunca captura a excecao
        return out

    import pytest
    with pytest.raises(FileNotFoundError):
        mutant_ethtool_offloads("eth0")


# --- Decisao 94 (achado real, confirmado por conteudo contra um pcap
# real de producao, Passo 11.5): o primeiro ACK do cliente so
# reconhece o SYN, nunca dado -- corrigido entao pra pular esse ACK e
# usar o PRIMEIRO pacote de ACK que de fato reconhece dado real.
#
# Emenda robustez-de-janela (pedido do Luciano, achado real contra a
# AWS real desta rodada -- Decisao 101 relatou segments_computed=2,0
# e atribuiu, ERRADO, a TCP pacing): mesmo a correcao da Decisao 94
# ainda discorda sob RTT real, porque o cliente manda VARIOS pacotes
# de ACK chegando num cluster bem apertado -- o PRIMEIRO deles so
# cobre 2 dos 10 segmentos REALMENTE mandados no 1o voo. Dados reais
# usados abaixo, extraidos por tshark do pcap real desta rodada
# (thesis/results/v9/piloto/dados_oficiais/piloto-real-aws-2026-11-09-
# v2/raw/criterio2_probe.pcap, L219, classico): SYN-ACK do servidor
# sai em t=1794237381.245875; handshake ACK do cliente chega em
# t=1794237381.465820 (RTT real = 219,945ms, bate com ss -ti:
# rtt=219,99ms); os 10 segmentos do 1o voo saem entre t=.484441 e
# t=.484522 (seq 1 a 13033+1448=14481, todos 1448B); o CLUSTER de 5
# ACKs do cliente chega so em t=.704618-.704619 (acks 2897/5793/8689/
# 11585/14481) -- o PRIMEIRO (2897) cobre so os 2 primeiros segmentos.
# O 2o voo (20 segmentos, slow-start dobrando de 10) comeca em
# t=.704672, DEPOIS do fim da janela de 1 RTT (.484441+0,219945=
# .704386) -- confirma que a janela corrigida inclui o 1o voo
# completo e exclui corretamente o 2o.

_REAL_SYNACK_OUT_EPOCH = "1794237381.245875"
_REAL_HANDSHAKE_ACK_IN_EPOCH = "1794237381.465820"
_REAL_RTT_S = float(_REAL_HANDSHAKE_ACK_IN_EPOCH) - float(_REAL_SYNACK_OUT_EPOCH)  # 0.219945

_REAL_FIRST_FLIGHT_TIMES = [
    "1794237381.484441", "1794237381.484447", "1794237381.484455", "1794237381.484455",
    "1794237381.484484", "1794237381.484485", "1794237381.484488", "1794237381.484489",
    "1794237381.484522", "1794237381.484523",
]
_REAL_SECOND_FLIGHT_TIMES = [f"1794237381.70467{d}" for d in range(2, 9, 3)]  # amostra do 2o voo real
_REAL_DATA_SEGMENTS = "\n".join(f"{t}\t1448" for t in _REAL_FIRST_FLIGHT_TIMES + _REAL_SECOND_FLIGHT_TIMES)
_REAL_SERVER_SEGMENTS_BY_SEQ = "\n".join(
    f"{seq}\t1448" for seq in (1, 1449, 2897, 4345, 5793, 7241, 8689, 10137, 11585, 13033)
)
_REAL_CLIENT_ACKS = "1\n2897\n5793\n8689\n11585\n14481"


def _fake_run_criterio2_real_pcap(cmd, **kw):
    argv_str = " ".join(cmd)
    if "tcp.options.mss_val" in argv_str:
        return type("P", (), {"stdout": "8961\n"})()
    if "tcp.seq" in argv_str:
        return type("P", (), {"stdout": _REAL_SERVER_SEGMENTS_BY_SEQ + "\n"})()
    if "tcp.flags.syn==0" in argv_str:
        # ack_in: tcp.dstport==... && tcp.flags.ack==1 && tcp.flags.syn==0
        if "frame.time_epoch" in argv_str:
            return type("P", (), {"stdout": _REAL_HANDSHAKE_ACK_IN_EPOCH + "\n"})()
        return type("P", (), {"stdout": _REAL_CLIENT_ACKS + "\n"})()
    if "tcp.flags.syn==1" in argv_str and "tcp.flags.ack==1" in argv_str and "frame.time_epoch" in argv_str:
        return type("P", (), {"stdout": _REAL_SYNACK_OUT_EPOCH + "\n"})()
    if "frame.time_epoch" in argv_str and "tcp.len" in argv_str:
        return type("P", (), {"stdout": _REAL_DATA_SEGMENTS + "\n"})()
    raise AssertionError(f"chamada tshark inesperada: {cmd}")


def test_extract_mss_separado_do_bug_antigo_de_bytes(monkeypatch):
    monkeypatch.setattr(c2, "run", _fake_run_criterio2_real_pcap)
    monkeypatch.setattr(c2, "_tshark_argv", lambda pcap: [])
    mss_announced, mss_pcap_max_payload = c2.extract_mss("/tmp/x.pcap", 9876)
    assert mss_announced == 8961
    assert mss_pcap_max_payload == 1448


def test_rtt_from_handshake_same_connection_bate_o_real():
    import unittest.mock as mock
    with mock.patch.object(c2, "run", _fake_run_criterio2_real_pcap), \
         mock.patch.object(c2, "_tshark_argv", lambda pcap: []):
        rtt_s = c2.rtt_from_handshake_same_connection("/tmp/x.pcap", 9876)
    assert rtt_s == pytest.approx(_REAL_RTT_S, abs=1e-6)


def test_bytes_sent_within_first_rtt_window_conta_o_1o_voo_completo():
    """O achado real: o metodo ANTIGO (ate a Decisao 94) contava so
    2896B (2 segmentos) porque parava no PRIMEIRO pacote de ACK visto
    -- o voo real tinha 10 segmentos (14480B), confirmado por ss -ti
    (cwnd:10) E pela contagem real de segmentos no pcap. O metodo
    NOVO, contando por timestamp de envio dentro de 1 RTT, acerta os
    10 segmentos completos (14480B) -- nunca mais refem de quantos
    pacotes de ACK chegaram juntos."""
    import unittest.mock as mock
    with mock.patch.object(c2, "run", _fake_run_criterio2_real_pcap), \
         mock.patch.object(c2, "_tshark_argv", lambda pcap: []):
        bytes_in_window = c2.extract_bytes_sent_within_rtt_window("/tmp/x.pcap", 9876, _REAL_RTT_S)
    assert bytes_in_window == 14480  # 10 segmentos x 1448B -- o voo REAL completo
    assert bytes_in_window != 2896  # o numero ERRADO que o metodo antigo dava


def test_mutante_contar_por_numero_de_ack_da_o_numero_antigo_errado():
    """Mutante = a logica ANTES desta Emenda (Decisao 94): conta so os
    bytes cobertos pelo PRIMEIRO pacote de ACK que reconhece dado real
    -- com os MESMOS dados reais, da 2896B (2 segmentos), nunca os
    14480B (10 segmentos) que o metodo novo (por timestamp de envio)
    acerta."""
    ack_out = _REAL_CLIENT_ACKS.splitlines()
    data_out = _REAL_SERVER_SEGMENTS_BY_SEQ.splitlines()
    first_seq = int(data_out[0].split("\t")[0])
    server_bytes_by_seq_end = [int(line.split("\t")[0]) + int(line.split("\t")[1]) for line in data_out]
    first_client_ack_mutante = None
    for line in ack_out:
        candidate = int(line)
        if candidate > first_seq:
            first_client_ack_mutante = candidate
            break
    sent_before_ack = sum(1 for end in server_bytes_by_seq_end if end <= first_client_ack_mutante)
    bytes_mutante = server_bytes_by_seq_end[sent_before_ack - 1] - first_seq
    assert bytes_mutante == 2896  # o bug antigo, reproduzido
    assert bytes_mutante != 14480  # nunca o valor real do voo completo


def test_mutante_janela_de_1_rtt_errada_da_resposta_errada():
    """Mutante: janela MUITO CURTA (metade do RTT real) exclui parte
    do 1o voo real; janela MUITO LONGA (2x o RTT real) inclui parte
    do 2o voo (amostrado em _REAL_SECOND_FLIGHT_TIMES) -- as duas
    dao um numero DIFERENTE do real (14480B), provando que a janela
    de EXATAMENTE 1 RTT (nem menos, nem mais) e o que importa."""
    import unittest.mock as mock
    # janela curta demais: menor que a propria duracao do 1o voo real
    # (~81us entre o 1o e o 10o segmento) -- corta o voo no meio.
    janela_curta_s = 0.00005
    with mock.patch.object(c2, "run", _fake_run_criterio2_real_pcap), \
         mock.patch.object(c2, "_tshark_argv", lambda pcap: []):
        bytes_janela_curta = c2.extract_bytes_sent_within_rtt_window("/tmp/x.pcap", 9876, janela_curta_s)
        bytes_janela_longa = c2.extract_bytes_sent_within_rtt_window("/tmp/x.pcap", 9876, _REAL_RTT_S * 2)
        bytes_janela_certa = c2.extract_bytes_sent_within_rtt_window("/tmp/x.pcap", 9876, _REAL_RTT_S)
    assert bytes_janela_certa == 14480
    assert bytes_janela_curta < 14480  # janela curta demais perde parte do 1o voo
    assert bytes_janela_longa > 14480  # janela longa demais pega parte do 2o voo


# --- Emenda MSS-efetivo (pedido do Luciano, apos a Decisao 95): MSS
# do SYN-ACK e so capacidade LOCAL da NIC (jumbo), nunca o MSS
# EFETIVO do caminho real -- `mss_bytes` so existe quando `ss -ti` e o
# maior payload real do pcap CONCORDAM.

def test_ss_ti_snapshot_extrai_mss_junto_com_cwnd(monkeypatch):
    fake_ss_output = "ESTAB 0 0 10.0.1.5:9876 10.0.2.9:51000 timer:(on,200ms,0) cwnd:10 mss:1448 rtt:0.5/0.2"

    class _FakeProc:
        stdout = fake_ss_output

    monkeypatch.setattr(c2, "run", lambda cmd, **kw: _FakeProc())
    result = c2.ss_ti_snapshot(9876)
    assert result["cwnd"] == 10
    assert result["mss"] == 1448


def test_effective_mss_concorda_usa_o_valor():
    mss_bytes, agree = c2.effective_mss(1448, 1448)
    assert mss_bytes == 1448
    assert agree is True


def test_effective_mss_discorda_mss_bytes_vira_none():
    """Reproduz o achado real da Decisao 95: SYN-ACK anuncia 8961
    (jumbo local), mas o MSS efetivo real (ss -ti) e 1448 -- se o
    canal do pcap (por bug/TSO) reportasse o valor anunciado em vez do
    payload real, os dois discordariam e `mss_bytes` tem que sair
    None, nunca escolher um dos dois."""
    mss_bytes, agree = c2.effective_mss(1448, 8961)
    assert mss_bytes is None
    assert agree is False


def test_mutante_effective_mss_usaria_synack_anunciado_por_default():
    """Mutante = o comportamento ANTIGO (criterion_2_initcwnd lia
    `mss_bytes` do SYN-ACK direto, sem nenhum cross-check) -- prova
    que o teste real de fato depende da concordancia, nunca aceita o
    valor anunciado so porque ele veio preenchido."""
    mss_synack_anunciado = 8961
    ss_ti_mss_real = 1448
    mutant_mss_bytes = mss_synack_anunciado  # mutante: usa o anunciado direto
    real_mss_bytes, _ = c2.effective_mss(ss_ti_mss_real, 1448)  # pcap concorda com ss -ti
    assert mutant_mss_bytes != real_mss_bytes
    assert real_mss_bytes == 1448


def test_mutante_extract_mss_sem_pular_o_ack_do_handshake_sempre_da_none(monkeypatch):
    """Mutacao = o comportamento ANTES desta Decisao: usa `ack_out[0]`
    sem filtro -- `sent_before_ack` fica SEMPRE 0, `bytes_before_ack`
    SEMPRE None, mesmo com os MESMOS dados reais onde a resposta
    certa e 2896."""
    ack_out = _REAL_CLIENT_ACKS.splitlines()
    data_out = _REAL_SERVER_SEGMENTS_BY_SEQ.splitlines()
    first_seq = int(data_out[0].split("\t")[0])
    server_bytes_by_seq_end = [int(l.split("\t")[0]) + int(l.split("\t")[1]) for l in data_out]
    first_client_ack_mutante = int(ack_out[0])  # mutante: nunca filtra
    sent_before_ack = sum(1 for end in server_bytes_by_seq_end if end <= first_client_ack_mutante)
    assert sent_before_ack == 0  # confirma o bug: nunca reconhece nenhum segmento


def test_start_tcpdump_usa_sudo(monkeypatch):
    """Decisao 94 (achado real, ao vivo, Passo 11.5): sem `sudo`,
    `tcpdump` falha com 'CAP_NET_RAW may be required' -- silenciosamente
    (Popen nunca checa o retorno), nunca escreve pcap nenhum."""
    captured = {}

    class _FakePopen:
        def __init__(self, argv, **kw):
            captured["argv"] = argv

    import subprocess as _subprocess
    monkeypatch.setattr(_subprocess, "Popen", _FakePopen)
    monkeypatch.setattr(c2.time, "sleep", lambda s: None)
    c2.start_tcpdump("eth0", "/tmp/x.pcap", 9876)
    assert captured["argv"][:2] == ["sudo", "tcpdump"]


def test_mutante_start_tcpdump_sem_sudo_e_pego(monkeypatch):
    """Mutacao = o comportamento ANTES desta Decisao -- sem `sudo`, o
    teste acima tem que reprovar."""
    mutant_argv = ["tcpdump", "-i", "eth0"]
    assert mutant_argv[:2] != ["sudo", "tcpdump"]


def test_ethtool_offloads_disponivel_extrai_on_off_normalmente():
    class _FakeProc:
        stdout = "tcp-segmentation-offload: on\ngeneric-segmentation-offload: off\ngeneric-receive-offload: on\n"

    import unittest.mock as mock
    with mock.patch.object(c2, "run", lambda cmd, **kw: _FakeProc()):
        result = c2.ethtool_offloads("eth0")
    assert result == {"tso": "on", "gso": "off", "gro": "on"}


def test_rtt_from_synack_ack_times_vazio_nunca_quebra():
    result = c7.rtt_from_synack_ack_times([])
    assert result == {"rtt_ms_pcap": None, "n_samples_pcap": 0}


def test_mutante_rtt_usa_media_em_vez_de_mediana_e_pego():
    """Mutante: usa media em vez de mediana -- um outlier mudaria o
    resultado; o teste real (mediana) tem que ser robusto a isso."""
    pairs = [(0, 0.010), (0, 0.020), (0, 0.900)]  # outlier grande no 3o
    result = c7.rtt_from_synack_ack_times(pairs)
    assert result["rtt_ms_pcap"] == 20.0  # mediana ignora o outlier
    mean_mutante = sum([10, 20, 900]) / 3
    assert result["rtt_ms_pcap"] != mean_mutante


def test_collect_l325_execucoes_filtra_rota_correta(tmp_path):
    (tmp_path / "e1.json").write_text(json.dumps({"profile": "classico", "route": "L325", "ok": True}), encoding="utf-8")
    (tmp_path / "e2.json").write_text(json.dumps({"profile": "pqc", "route": "L219", "ok": True}), encoding="utf-8")
    result = c3.collect_l325_execucoes(str(tmp_path))
    assert result == {"execucoes": [{"profile": "classico", "route": "L325", "ok": True}]}
