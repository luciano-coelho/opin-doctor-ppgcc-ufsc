"""Decisao 157 (item 4, pedido do Luciano): trava de
organize_v9_results.py contra escrever sobre um --out-dir ja populado
sem autorizacao explicita. Roda o script real via subprocess (mesma
forma que a campanha realmente invoca), nunca importa main() direto --
isola qualquer side effect de argparse/sys.exit entre os casos."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "organize_v9_results.py"


def _write_fixtures(tmp_path: Path, network_transport_retries=None, handshake_bytes_per_connection=None):
    calls = [{
        "profile": "classico", "route": "L0", "run": 1,
        "start_utc": "2026-11-14T00:00:00+00:00", "end_utc": "2026-11-14T00:00:01+00:00",
        "insurance": [{"total_bytes": 100}], "person": [{"total_bytes": 50}],
        "network_transport_retries": network_transport_retries or [],
        "handshake_bytes_per_connection": handshake_bytes_per_connection or [],
    }]
    criterio6 = [{"profile": "classico", "dualAuthenticated": False}]
    manifest = {
        "total_execucoes": 1, "expected_total": 1, "window_end_utc": "2026-11-14T00:00:02+00:00",
        "capturas_dedicadas_falhas": [], "capturas_dedicadas_feitas": 0,
    }
    calls_json = tmp_path / "calls.json"
    criterio6_json = tmp_path / "criterio6.json"
    manifest_json = tmp_path / "manifest.json"
    calls_json.write_text(json.dumps(calls), encoding="utf-8")
    criterio6_json.write_text(json.dumps(criterio6), encoding="utf-8")
    manifest_json.write_text(json.dumps(manifest), encoding="utf-8")
    return calls_json, criterio6_json, manifest_json


def _run(tmp_path, out_dir, extra_args=(), network_transport_retries=None, handshake_bytes_per_connection=None):
    calls_json, criterio6_json, manifest_json = _write_fixtures(
        tmp_path, network_transport_retries, handshake_bytes_per_connection)
    args = [
        sys.executable, "-I", str(SCRIPT),
        "--calls-json", str(calls_json),
        "--criterio6-json", str(criterio6_json),
        "--manifest-json", str(manifest_json),
        "--out-dir", str(out_dir),
        "--expected-runs-per-cell", "1",
        *extra_args,
    ]
    return subprocess.run(args, capture_output=True, text=True)


def test_happy_path_nonexistent_dest(tmp_path):
    """Destino que ainda nao existe: roda normal, sem flag nenhuma."""
    out_dir = tmp_path / "out"
    result = _run(tmp_path, out_dir)
    assert result.returncode == 0, result.stderr
    report = json.loads((out_dir / "report_data_v9.json").read_text(encoding="utf-8"))
    assert report["overwrite_populated_dest_authorized"] is False


def test_happy_path_empty_existing_dest(tmp_path):
    """Destino que existe mas esta vazio (ex.: mkdir -p previo): tambem roda normal."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = _run(tmp_path, out_dir)
    assert result.returncode == 0, result.stderr


def test_refuses_populated_dest_without_flag(tmp_path):
    """Destino ja populado (campanha anterior) + sem flag: recusa alto,
    ANTES de escrever nada -- nenhum arquivo do destino e tocado."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    sentinel = out_dir / "campanha_anterior.json"
    sentinel.write_text('{"de":"outra campanha"}', encoding="utf-8")

    result = _run(tmp_path, out_dir)

    assert result.returncode != 0
    assert "ja existe e NAO esta vazio" in result.stderr
    # nada novo foi escrito, o sentinel da campanha anterior continua intocado
    assert sentinel.read_text(encoding="utf-8") == '{"de":"outra campanha"}'
    assert not (out_dir / "report_data_v9.json").exists()


def test_retries_report_summed_per_cell(tmp_path):
    """Decisao 158 (item 6a): network_transport_retries de cada
    execucao real tem que virar retries_report.json, somado por celula
    (profile/route) -- nunca perdido, nunca misturado com outra
    celula."""
    out_dir = tmp_path / "out"
    retries = [
        {"run": "run01", "attempt": 1, "profile": "classico", "error": "ConnectionError: reset",
         "failure_class": "network_transport", "at_utc": "2026-11-14T00:00:00+00:00"},
    ]
    result = _run(tmp_path, out_dir, network_transport_retries=retries)
    assert result.returncode == 0, result.stderr

    report = json.loads((out_dir / "retries_report.json").read_text(encoding="utf-8"))
    assert report["total_retries"] == 1
    assert "classico/L0" in report["por_celula"]
    assert report["por_celula"]["classico/L0"]["n_retries"] == 1
    assert report["por_celula"]["classico/L0"]["entries"][0]["failure_class"] == "network_transport"

    report_data = json.loads((out_dir / "report_data_v9.json").read_text(encoding="utf-8"))
    assert report_data["network_transport_retries_total"] == 1


def test_retries_report_empty_when_no_retries(tmp_path):
    out_dir = tmp_path / "out"
    result = _run(tmp_path, out_dir)
    assert result.returncode == 0, result.stderr
    report = json.loads((out_dir / "retries_report.json").read_text(encoding="utf-8"))
    assert report == {"total_retries": 0, "por_celula": {}}


def test_handshake_bytes_alert_empty_when_all_connections_match(tmp_path):
    """Decisao 160 (item 1): todas as conexoes da celula com o mesmo
    in/out -- zero divergentes, mas a celula aparece no relatorio."""
    out_dir = tmp_path / "out"
    conns = [{"in": 1485, "out": 1640}, {"in": 1485, "out": 1640}, {"in": 1485, "out": 1640}]
    result = _run(tmp_path, out_dir, handshake_bytes_per_connection=conns)
    assert result.returncode == 0, result.stderr

    report = json.loads((out_dir / "handshake_bytes_alert.json").read_text(encoding="utf-8"))
    assert report["total_divergentes"] == 0
    cell = report["por_celula"]["classico/L0"]
    assert cell["n_conexoes"] == 3
    assert cell["valor_esperado"] == {"in": 1485, "out": 1640}
    assert cell["divergentes"] == []


def test_handshake_bytes_alert_flags_divergent_connection_without_excluding_it(tmp_path):
    """Decisao 160: uma conexao fora do valor esperado da celula
    (ex.: o leak de +71B voltando) e REGISTRADA, nunca descartada --
    size/latency continuam calculados sobre as mesmas execucoes
    normalmente (este campo nunca entra no calculo delas)."""
    out_dir = tmp_path / "out"
    conns = [{"in": 1485, "out": 1640}, {"in": 1485, "out": 1640}, {"in": 1556, "out": 1640}]
    result = _run(tmp_path, out_dir, handshake_bytes_per_connection=conns)
    assert result.returncode == 0, result.stderr

    report = json.loads((out_dir / "handshake_bytes_alert.json").read_text(encoding="utf-8"))
    assert report["total_divergentes"] == 1
    cell = report["por_celula"]["classico/L0"]
    assert cell["n_conexoes"] == 3, "a conexao divergente continua contada, nunca excluida"
    assert cell["valor_esperado"] == {"in": 1485, "out": 1640}
    assert cell["n_divergentes"] == 1
    assert cell["divergentes"] == [{"run": 1, "in": 1556, "out": 1640}]

    report_data = json.loads((out_dir / "report_data_v9.json").read_text(encoding="utf-8"))
    assert report_data["handshake_bytes_divergentes_total"] == 1
    # a divergencia nunca afeta median_metrics -- mesma execucao, mesmos bytes de size
    median = json.loads((out_dir / "size" / "experiment1 - Classic" / "L0" / "median_metrics.json").read_text(encoding="utf-8"))
    assert median["n"] == 1
    assert median["values"] == [150]


def test_allows_populated_dest_with_explicit_flag_and_records_it(tmp_path):
    """Destino ja populado + --allow-overwrite-populated: prossegue, e o
    report_data_v9.json resultante registra a autorizacao explicitamente
    (nunca silencioso)."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "campanha_anterior.json").write_text('{"de":"outra campanha"}', encoding="utf-8")

    result = _run(tmp_path, out_dir, extra_args=["--allow-overwrite-populated"])

    assert result.returncode == 0, result.stderr
    report = json.loads((out_dir / "report_data_v9.json").read_text(encoding="utf-8"))
    assert report["overwrite_populated_dest_authorized"] is True
