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


def _write_fixtures(tmp_path: Path):
    calls = [{
        "profile": "classico", "route": "L0", "run": 1,
        "start_utc": "2026-11-14T00:00:00+00:00", "end_utc": "2026-11-14T00:00:01+00:00",
        "insurance": [{"total_bytes": 100}], "person": [{"total_bytes": 50}],
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


def _run(tmp_path, out_dir, extra_args=()):
    calls_json, criterio6_json, manifest_json = _write_fixtures(tmp_path)
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
