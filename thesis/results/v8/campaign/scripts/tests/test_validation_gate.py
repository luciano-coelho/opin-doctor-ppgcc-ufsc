"""Validation-gate turn (item 3, thesis/results/v8/DECISIONS.md):
regression tests for run_validation_stage() (24 executions, 1/profile x
8 scenarios, before window 1) and wait_for_operator_gate() (blocks until
an explicit operator marker file exists). Same fake-inventory pattern as
test_installation_skip.py -- pilot-only inventory, full-campaign
inventory, and an installation entirely absent.
"""
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import campaign_run as cr


def _run_validation_stage_recording(installations, inventory_clients):
    calls = []

    def fake_pre_block_checks(executor, installation, profile):
        calls.append(("pre_block_checks", installation, profile))
        return {}

    def fake_start_block_proxies(executor, installation, profile, scenarios, window):
        calls.append(("start_block_proxies", installation, profile, tuple(scenarios), window))

    def fake_stop_block_proxies(executor, installation, profile, scenarios, window):
        calls.append(("stop_block_proxies", installation, profile, tuple(scenarios), window))

    def fake_run_one_execution(executor, installation, scenario, profile, window, run_index, scenario_path):
        calls.append(("run_one_execution", installation, profile, scenario, window, run_index, str(scenario_path)))
        return {"call_count": 1, "t_fluxo_seconds": 1.0}

    executor = mock.Mock(spec=cr.SSHExecutor)
    executor.inventory = {"clients": inventory_clients}

    with tempfile.TemporaryDirectory() as tmp, \
         mock.patch.object(cr, "DATA_ROOT", Path(tmp)), \
         mock.patch.object(cr, "pre_block_checks", fake_pre_block_checks), \
         mock.patch.object(cr, "start_block_proxies", fake_start_block_proxies), \
         mock.patch.object(cr, "stop_block_proxies", fake_stop_block_proxies), \
         mock.patch.object(cr, "run_one_execution", fake_run_one_execution), \
         mock.patch.object(cr, "wait_for_operator_gate", lambda *a, **k: calls.append(("wait_for_operator_gate", a))):
        cr.run_validation_stage(executor, installations)
    return calls


def test_full_campaign_inventory_runs_24_executions():
    """Full inventory (all 3 installations' own 8 scenarios total) must
    run exactly 1 execution x 3 profiles x 8 scenarios = 24, and call the
    operator gate exactly once at the end."""
    full_clients = {}
    for installation, windows in cr.SCENARIO_ROTATION.items():
        for scenario in windows[1]:
            full_clients[f"{scenario}@{installation}"] = {}

    calls = _run_validation_stage_recording(list(cr.SCENARIO_ROTATION.keys()), full_clients)
    run_calls = [c for c in calls if c[0] == "run_one_execution"]
    assert len(run_calls) == 24, f"expected 24 executions, got {len(run_calls)}: {run_calls}"
    gate_calls = [c for c in calls if c[0] == "wait_for_operator_gate"]
    assert len(gate_calls) == 1
    assert gate_calls[0][1][0] == "validation_stage"
    # None of the 24 executions write into a real scenario_dir() path.
    for c in run_calls:
        assert "validation_stage" in c[-1], f"execution wrote outside validation_stage/: {c}"


def test_pilot_inventory_scopes_out_other_installations():
    """A pilot inventory covering only sa-east-1 (2 scenarios): must run
    1 x 3 x 2 = 6 executions, skipping us-east-1/ap-northeast-1 cleanly
    (no exception), same 'skip, don't abort' philosophy as the earlier
    installation-skip fix."""
    pilot_clients = {"L0@sa-east-1": {}, "L325@sa-east-1": {}}
    calls = _run_validation_stage_recording(list(cr.SCENARIO_ROTATION.keys()), pilot_clients)
    run_calls = [c for c in calls if c[0] == "run_one_execution"]
    assert len(run_calls) == 6, f"expected 6 executions (3 profiles x 2 scenarios), got {len(run_calls)}"
    assert all(c[1] == "sa-east-1" for c in run_calls)
    # Still reaches and calls the gate even though 2/3 installations were skipped.
    assert any(c[0] == "wait_for_operator_gate" for c in calls)


def test_installation_entirely_absent_is_skipped_not_aborted():
    clients = {"L0@sa-east-1": {}}
    calls = _run_validation_stage_recording(["ap-northeast-1"], clients)
    run_calls = [c for c in calls if c[0] == "run_one_execution"]
    assert run_calls == [], f"expected no executions for an absent installation, got {run_calls}"
    # Gate is still reached (the function doesn't abort).
    assert any(c[0] == "wait_for_operator_gate" for c in calls)


def test_wait_for_operator_gate_returns_immediately_once_marker_exists():
    with tempfile.TemporaryDirectory() as tmp:
        with mock.patch.object(cr, "DATA_ROOT", Path(tmp)), \
             mock.patch.object(cr, "write_status", lambda *a, **k: None):
            marker_path = Path(tmp) / "v8" / "latency" / "_campaign-control" / "gates" / "some_gate.approved"
            marker_path.parent.mkdir(parents=True, exist_ok=True)
            marker_path.write_text("approved")
            t0 = time.monotonic()
            cr.wait_for_operator_gate("some_gate", poll_seconds=9999)
            elapsed = time.monotonic() - t0
            assert elapsed < 2, f"expected an immediate return (marker already exists), took {elapsed:.2f}s"


def test_wait_for_operator_gate_blocks_until_marker_appears():
    with tempfile.TemporaryDirectory() as tmp:
        with mock.patch.object(cr, "DATA_ROOT", Path(tmp)), \
             mock.patch.object(cr, "write_status", lambda *a, **k: None):
            marker_path = Path(tmp) / "v8" / "latency" / "_campaign-control" / "gates" / "slow_gate.approved"

            def create_marker_after_delay():
                time.sleep(0.2)
                marker_path.parent.mkdir(parents=True, exist_ok=True)
                marker_path.write_text("approved")

            threading.Thread(target=create_marker_after_delay, daemon=True).start()
            t0 = time.monotonic()
            cr.wait_for_operator_gate("slow_gate", poll_seconds=0.05)
            elapsed = time.monotonic() - t0
            assert 0.15 < elapsed < 5, f"expected to block roughly until the marker appeared, took {elapsed:.2f}s"


if __name__ == "__main__":
    test_full_campaign_inventory_runs_24_executions()
    test_pilot_inventory_scopes_out_other_installations()
    test_installation_entirely_absent_is_skipped_not_aborted()
    test_wait_for_operator_gate_returns_immediately_once_marker_exists()
    test_wait_for_operator_gate_blocks_until_marker_appears()
    print("PASS: all validation gate tests")
