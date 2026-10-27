"""Order/image-provenance turn (item 4, thesis/results/v8/DECISIONS.md,
Decision 91): regression tests for get_gateway_image_digest() (recorded
once per window) and CODE_HASH/code_hash (stamped per run). Implemented
before pilot 3, per Luciano's own instruction, so it never counts as a
mid-window intervention.
"""
import json
import re
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import campaign_run as cr


def test_code_hash_is_a_real_deterministic_sha256():
    assert re.fullmatch(r"[0-9a-f]{64}", cr.CODE_HASH), f"CODE_HASH doesn't look like sha256 hex: {cr.CODE_HASH!r}"
    assert cr._compute_code_hash() == cr.CODE_HASH, "recomputing CODE_HASH must be deterministic for the same files"


def test_code_hash_changes_if_a_watched_file_changes():
    """Not a guess -- actually edits a temp copy of one watched file and
    confirms the hash differs, proving the function really reads file
    content, not just names/paths."""
    with tempfile.TemporaryDirectory() as tmp:
        fake_opin_flow = Path(tmp) / "opin_flow.py"
        fake_client_runner = Path(tmp) / "campaign_client_runner.py"
        fake_opin_flow.write_text("print('v1')")
        fake_client_runner.write_text("print('runner')")
        with mock.patch.object(cr, "THESIS_SCRIPTS_DIR", Path(tmp)):
            h1 = cr._compute_code_hash()
            fake_opin_flow.write_text("print('v2')")
            h2 = cr._compute_code_hash()
    assert h1 != h2, "CODE_HASH did not change after a watched file's content changed"


def test_get_gateway_image_digest_ssh_executor_runs_inspect_and_returns_real_output():
    calls = []

    def fake_run_tolerant(label, cmd):
        calls.append((label, cmd))
        return "sha256:abc123\n"

    executor = mock.Mock(spec=cr.SSHExecutor)
    executor._server_ip = mock.Mock(return_value="10.0.0.5")
    executor._ssh_cmd = mock.Mock(side_effect=lambda ip, cmd: f"ssh {ip} {cmd}")
    executor._run_tolerant = fake_run_tolerant

    digest = cr.get_gateway_image_digest(executor, "sa-east-1")
    assert digest == "sha256:abc123"
    assert len(calls) == 1
    assert "docker image inspect" in calls[0][1]
    assert cr.GATEWAY_IMAGE_NAME in calls[0][1]
    executor._server_ip.assert_called_once_with("sa-east-1")


def test_get_gateway_image_digest_ssh_executor_returns_none_on_empty_output():
    executor = mock.Mock(spec=cr.SSHExecutor)
    executor._server_ip = mock.Mock(return_value="10.0.0.5")
    executor._ssh_cmd = mock.Mock(return_value="whatever")
    executor._run_tolerant = mock.Mock(return_value="")
    assert cr.get_gateway_image_digest(executor, "sa-east-1") is None


def test_get_gateway_image_digest_local_executor_uses_real_docker_inspect():
    """A bare Mock() (no spec=SSHExecutor) takes the LocalExecutor branch,
    which shells out to a REAL `docker image inspect` -- mocked here via
    subprocess.run so the test doesn't depend on Docker being available."""
    executor = mock.Mock()  # isinstance(executor, SSHExecutor) is False

    fake_result = mock.Mock(returncode=0, stdout="sha256:local123\n")
    with mock.patch.object(cr.subprocess, "run", return_value=fake_result) as run_mock:
        digest = cr.get_gateway_image_digest(executor, "sa-east-1")
    assert digest == "sha256:local123"
    argv = run_mock.call_args[0][0]
    assert argv[:3] == ["docker", "image", "inspect"]
    assert cr.GATEWAY_IMAGE_NAME in argv


def test_get_gateway_image_digest_local_executor_missing_image_returns_none():
    executor = mock.Mock()
    fake_result = mock.Mock(returncode=1, stdout="")
    with mock.patch.object(cr.subprocess, "run", return_value=fake_result):
        assert cr.get_gateway_image_digest(executor, "sa-east-1") is None


def test_window_json_carries_gateway_image_id():
    """End-to-end through run_window(): window{NN}.json must carry the
    real (mocked here) image digest, not a missing/null field by
    omission."""
    calls = []

    def fake_pre_block_checks(executor, installation, profile):
        return {}

    def fake_start_block_proxies(executor, installation, profile, scenarios, window):
        calls.append(("start", profile))

    def fake_stop_block_proxies(executor, installation, profile, scenarios, window):
        calls.append(("stop", profile))

    def fake_run_warmup(executor, installation, scenario, profile, window, scenario_path):
        pass

    def fake_run_one_execution(executor, installation, scenario, profile, window, run_index, scenario_path):
        return {"call_count": 1}

    executor = mock.Mock(spec=cr.SSHExecutor)
    executor.inventory = {"clients": {f"{s}@sa-east-1": {} for s in cr.SCENARIO_ROTATION["sa-east-1"][1]}}

    with tempfile.TemporaryDirectory() as tmp, \
         mock.patch.object(cr, "DATA_ROOT", Path(tmp)), \
         mock.patch.object(cr, "pre_block_checks", fake_pre_block_checks), \
         mock.patch.object(cr, "start_block_proxies", fake_start_block_proxies), \
         mock.patch.object(cr, "stop_block_proxies", fake_stop_block_proxies), \
         mock.patch.object(cr, "run_warmup", fake_run_warmup), \
         mock.patch.object(cr, "run_one_execution", fake_run_one_execution), \
         mock.patch.object(cr, "get_gateway_image_digest", lambda executor, installation: "sha256:windowtest"), \
         mock.patch.object(cr, "RUNS_PER_WINDOW", 1):
        cr.run_window(executor, "sa-east-1", window=1, seed=42, profile_order=cr.PROFILES[:])

        window_path = Path(tmp) / "v8" / "latency" / "_campaign-control" / "windows" / "sa-east-1" / "window01.json"
        data = json.loads(window_path.read_text())
        assert data["gateway_image_id"] == "sha256:windowtest"

        run_files = list((Path(tmp) / "v8" / "latency").glob("*/sa-east-1/*/runs/run01.json"))
        assert run_files, "expected at least one run01.json to have been written"
        for rf in run_files:
            run_data = json.loads(rf.read_text())
            assert run_data["code_hash"] == cr.CODE_HASH


if __name__ == "__main__":
    test_code_hash_is_a_real_deterministic_sha256()
    test_code_hash_changes_if_a_watched_file_changes()
    test_get_gateway_image_digest_ssh_executor_runs_inspect_and_returns_real_output()
    test_get_gateway_image_digest_ssh_executor_returns_none_on_empty_output()
    test_get_gateway_image_digest_local_executor_uses_real_docker_inspect()
    test_get_gateway_image_digest_local_executor_missing_image_returns_none()
    test_window_json_carries_gateway_image_id()
    print("PASS: all image/code hash tests")
