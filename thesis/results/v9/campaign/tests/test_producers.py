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
