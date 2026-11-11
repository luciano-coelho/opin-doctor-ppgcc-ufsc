"""Testes da trava local de custo (Etapa 1 do piloto v9, item 2) --
puramente aritmetico, sem AWS, sem SSH."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cost_tracker as ct  # noqa: E402


def test_status_ok_quando_custo_abaixo_do_alerta():
    tracker = ct.CostTracker(instance_types={"control": "t4g.micro"}, n_public_ips=1,
                              alert_usd=10.0, stop_usd=13.0)
    assert tracker.status() == "ok"
    assert tracker.estimated_cost_usd() < 10.0


def test_status_alert_entre_os_dois_limiares():
    tracker = ct.CostTracker(instance_types={"a": "m7i-flex.large", "b": "m7i-flex.large",
                                              "c": "m7i-flex.large"}, n_public_ips=3,
                              alert_usd=10.0, stop_usd=13.0)
    tracker.window_start_utc = datetime.now(timezone.utc) - timedelta(hours=30)
    assert tracker.status() == "alert"
    cost = tracker.estimated_cost_usd()
    assert 10.0 <= cost < 13.0


def test_status_stop_acima_do_limiar():
    tracker = ct.CostTracker(instance_types={"a": "m7i-flex.large"}, n_public_ips=1,
                              alert_usd=10.0, stop_usd=13.0)
    tracker.window_start_utc = datetime.now(timezone.utc) - timedelta(hours=1000)
    assert tracker.status() == "stop"


def test_tipo_de_instancia_desconhecido_usa_o_maior_preco_conhecido_nunca_subestima():
    preco_desconhecido = ct.hourly_price_for("algum-tipo-nunca-visto.xlarge")
    assert preco_desconhecido == ct._FALLBACK_HOURLY_PRICE_USD
    assert preco_desconhecido == max(ct.HOURLY_PRICE_USD.values())


def test_breakdown_soma_os_4_componentes():
    tracker = ct.CostTracker(instance_types={"a": "t4g.micro"}, n_public_ips=1, data_transfer_gb=10.0)
    tracker.window_start_utc = datetime.now(timezone.utc) - timedelta(hours=2)
    b = tracker.breakdown_usd()
    assert b["total_usd"] == pytest.approx(
        b["compute_usd"] + b["public_ipv4_usd"] + b["ebs_usd"] + b["data_transfer_usd"]
    )
    assert b["data_transfer_usd"] == pytest.approx(10.0 * ct.DATA_TRANSFER_OUT_GB_USD)


def test_add_data_transfer_bytes_acumula_em_gb():
    tracker = ct.CostTracker()
    tracker.add_data_transfer_bytes(1024 ** 3)  # 1 GiB
    assert tracker.data_transfer_gb == pytest.approx(1.0)


def test_zero_instancias_zero_tempo_custo_zero():
    tracker = ct.CostTracker()
    assert tracker.estimated_cost_usd() == 0.0
    assert tracker.status() == "ok"


def test_write_cost_log_entry_append_only(tmp_path):
    ct.write_cost_log_entry(tmp_path, "check", {"total_usd": 1.0})
    ct.write_cost_log_entry(tmp_path, "check", {"total_usd": 2.0})
    lines = (tmp_path / "cost_tracker.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
