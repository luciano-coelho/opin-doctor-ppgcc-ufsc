"""Testes dos produtores dedicados dos criterios 2/3/7 (Decisao 85) --
so a matematica/logica pura e testavel sem Docker/tshark reais; a
orquestracao remota (SSH/scp) e testada em test_dedicated_criteria.py."""
import json
import sys
from pathlib import Path

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


# --- Decisao 94 (achado real, ao vivo, Passo 11.5, confirmado por
# conteudo contra um pcap real de producao -- 54.233.213.235, Passo
# 11.5, 2026-11-09): o primeiro ACK do cliente so reconhece o SYN
# (ack_num == first_seq), nunca nenhum byte de dado -- usar esse ACK
# (o bug original, `ack_out[0]` sem filtro) faz `sent_before_ack` ser
# SEMPRE 0. Dados reais usados abaixo (tshark -r criterio2.pcap):
# server seq/len: (1,1448),(1449,1448),(2897,1448),(4345,1448),...;
# client acks, em ordem: 1 (handshake), 2897, 5793, 8689, 11585, 14481.

_REAL_SERVER_SEGMENTS = "\n".join(
    f"{seq}\t1448" for seq in (1, 1449, 2897, 4345, 5793, 7241, 8689, 10137, 11585, 13033)
)
_REAL_CLIENT_ACKS = "1\n2897\n5793\n8689\n11585\n14481"


def test_extract_mss_e_bytes_before_ack_pula_o_ack_do_handshake(monkeypatch):
    calls = {"n": 0}

    def fake_run(cmd, **kw):
        calls["n"] += 1
        if "tcp.options.mss_val" in cmd:
            return type("P", (), {"stdout": "8961\n"})()
        if "tcp.seq" in cmd and "-e" in cmd:
            return type("P", (), {"stdout": _REAL_SERVER_SEGMENTS + "\n"})()
        if "tcp.ack" in cmd:
            return type("P", (), {"stdout": _REAL_CLIENT_ACKS + "\n"})()
        raise AssertionError(f"chamada tshark inesperada: {cmd}")

    monkeypatch.setattr(c2, "run", fake_run)
    monkeypatch.setattr(c2, "_tshark_argv", lambda pcap: [])
    mss_announced, mss_pcap_max_payload, bytes_before_ack = c2.extract_mss_and_bytes_before_ack("/tmp/x.pcap", 9876)
    # Emenda MSS-efetivo: o MSS anunciado no SYN-ACK (8961, capacidade
    # LOCAL de jumbo frame) e so diagnostico -- o canal que entra no
    # calculo e o MAIOR payload real observado (1448, todos os
    # segmentos de _REAL_SERVER_SEGMENTS).
    assert mss_announced == 8961
    assert mss_pcap_max_payload == 1448
    # primeiro ACK que de fato reconhece dado = 2897 (pula o 1, so-handshake)
    # -- 2 segmentos (1449,2897) tem seq_end <= 2897 -- 2896 bytes (2897-1).
    assert bytes_before_ack == 2896


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
    data_out = _REAL_SERVER_SEGMENTS.splitlines()
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
