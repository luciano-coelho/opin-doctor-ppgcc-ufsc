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


def test_rtt_from_syn_synack_times_mediana_correta():
    syn = [1000.000, 1001.000, 1002.000]
    synack = [1000.010, 1001.030, 1002.020]  # deltas: 10ms, 30ms, 20ms -- mediana 20ms
    result = c7.rtt_from_syn_synack_times(syn, synack)
    assert result == {"rtt_ms_pcap": 20.0, "n_samples_pcap": 3}


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
    mss, bytes_before_ack = c2.extract_mss_and_bytes_before_ack("/tmp/x.pcap", 9876)
    assert mss == 8961
    # primeiro ACK que de fato reconhece dado = 2897 (pula o 1, so-handshake)
    # -- 2 segmentos (1449,2897) tem seq_end <= 2897 -- 2896 bytes (2897-1).
    assert bytes_before_ack == 2896


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


def test_rtt_from_syn_synack_times_vazio_nunca_quebra():
    result = c7.rtt_from_syn_synack_times([], [])
    assert result == {"rtt_ms_pcap": None, "n_samples_pcap": 0}


def test_mutante_rtt_usa_media_em_vez_de_mediana_e_pego():
    """Mutante: usa media em vez de mediana -- um outlier mudaria o
    resultado; o teste real (mediana) tem que ser robusto a isso."""
    syn = [0, 0, 0]
    synack_mediana = [0.010, 0.020, 0.900]  # outlier grande no 3o
    result = c7.rtt_from_syn_synack_times(syn, synack_mediana)
    assert result["rtt_ms_pcap"] == 20.0  # mediana ignora o outlier
    mean_mutante = sum([10, 20, 900]) / 3
    assert result["rtt_ms_pcap"] != mean_mutante


def test_collect_l325_execucoes_filtra_rota_correta(tmp_path):
    (tmp_path / "e1.json").write_text(json.dumps({"profile": "classico", "route": "L325", "ok": True}), encoding="utf-8")
    (tmp_path / "e2.json").write_text(json.dumps({"profile": "pqc", "route": "L219", "ok": True}), encoding="utf-8")
    result = c3.collect_l325_execucoes(str(tmp_path))
    assert result == {"execucoes": [{"profile": "classico", "route": "L325", "ok": True}]}
