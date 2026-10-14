#!/usr/bin/env python3
"""Proves that three consecutive windows of the REAL run_window() --
not a narrower slice of it -- produce 30 DISTINCT runs/run{NN}.json
files per scenario+profile (GLOBAL run numbering across the campaign:
window 1 -> runs 1-10, window 2 -> runs 11-20, window 3 -> runs 21-30),
plus the settling/meta/gateway-log files (A.1), with NOTHING
overwritten anywhere. This is the test that caught a second,
more serious window-overwrite bug than A.1's: `run_window()`'s
round-robin loop reused the window-LOCAL index `i` (1..RUNS_PER_WINDOW)
directly as the run's global file name, so window 2's run01..run10
would have silently overwritten window 1's -- the file's own docstring
says "30 runs/profile/scenario" (10/window x 3 windows), which is only
true with GLOBAL numbering. Fixed in run_window() (global_run_index =
(window-1)*RUNS_PER_WINDOW + i).

Exercises the REAL run_window()/LocalExecutor code paths end to end
(round-robin, warmup, settling, the correlated negotiated-group check)
-- only the genuinely-remote/slow pieces are mocked (docker
compose/exec/logs via subprocess.run, latency_automation's own flow
execution, tcpdump's absence on this dev machine). Run directly:
`python tests/test_full_campaign_no_overwrite.py`.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import campaign_run as cr

INSTALLATION = "sa-east-1"
ADDR_CLIENT = "203.0.113.10:51000"
ADDR_INTERNAL = "203.0.113.10:51002"

_current_profile = {"value": "classic"}


def _log_line(ts, obj):
    return f"{ts} {json.dumps(obj)}"


def _fake_gateway_log_for(profile):
    """A log with the CORRECT client-facing curve for whichever profile
    is currently active -- a static log (one fixed curve) would make
    verify_negotiated_groups() correctly abort on pqc/hybrid (their
    expected curve differs from classic's), which would be a false
    failure of THIS test's mocking, not a real campaign_run.py bug."""
    client_curve = cr._CLIENT_EXPECTED_CURVE[profile]
    return "\n".join([
        _log_line("2026-10-13T19:00:00.000000000Z",
                  {"msg": cr._CARVEOUT_MSG, "sni": "matls-api.local", "remoteAddr": ADDR_INTERNAL}),
        _log_line("2026-10-13T19:00:00.050000000Z",
                  {"msg": cr._HANDSHAKE_COMPLETE_MSG, "remoteAddr": ADDR_INTERNAL, "curveID": "CurveP256"}),
        _log_line("2026-10-13T19:00:00.100000000Z",
                  {"msg": cr._HANDSHAKE_COMPLETE_MSG, "remoteAddr": ADDR_CLIENT, "curveID": client_curve}),
    ])


def _make_executor():
    executor = cr.LocalExecutor.__new__(cr.LocalExecutor)
    executor.of = mock.Mock()
    executor.of.GATEWAY_CONTAINER = "insurance-server-lambdas-mtls-1"
    executor.of.start_tls_kem_proxy = mock.Mock(return_value="fake-proc")
    executor.of.start_pqc_signer_service = mock.Mock(return_value=False)
    executor.of.stop_pqc_signer_service = mock.Mock()
    executor.of.stop_tls_kem_proxy = mock.Mock()

    executor.scp = mock.Mock()
    executor.scp._compose = mock.Mock(return_value=mock.Mock(returncode=0, stdout="", stderr=""))
    executor.scp.PROFILE_DEPENDENT_SERVICES = []
    executor.scp._start_if_exited = mock.Mock()
    executor.scp._container_status = mock.Mock(return_value="running")
    executor.scp._wait_for_mtls_ready = mock.Mock()
    executor.scp._check_psql_checkpoint_health = mock.Mock()

    def fake_run_once(profile, label, retries, return_calls=False):
        _current_profile["value"] = profile
        result = {"call_count": 5, "duration_seconds": 1.0, "label": label}
        if return_calls:
            result["calls"] = [{"endpoint": "fake", "latency_ms": 1.0}]
        return result

    executor.la = mock.Mock()
    executor.la.run_once_timed_with_retry = mock.Mock(side_effect=fake_run_once)
    executor._block_state = {}
    executor.allow_tcpdump_skip = True  # tcpdump genuinely isn't installed on this dev machine
    return executor


def fake_subprocess_run(argv, **kwargs):
    if argv[:2] == ["docker", "logs"]:
        return mock.Mock(returncode=0, stdout=_fake_gateway_log_for(_current_profile["value"]), stderr="")
    if argv == ["which", "tcpdump"]:
        return mock.Mock(returncode=1, stdout="", stderr="")  # honestly not installed here
    return mock.Mock(returncode=0, stdout="", stderr="")


def run():
    with tempfile.TemporaryDirectory() as tmp:
        with mock.patch.object(cr, "DATA_ROOT", Path(tmp)), \
             mock.patch.object(subprocess, "run", side_effect=fake_subprocess_run), \
             mock.patch.object(cr, "time") as mocked_time:
            mocked_time.sleep = lambda *_: None
            mocked_time.monotonic = __import__("time").monotonic

            executor = _make_executor()
            for window in (1, 2, 3):
                cr.run_window(executor, INSTALLATION, window, seed=42)

            scenarios = set()
            for w in cr.SCENARIO_ROTATION[INSTALLATION].values():
                scenarios.update(w)

            print("=== runs/ file check: 30 distinct files per scenario+profile, global numbering ===")
            all_ok = True
            for profile in cr.PROFILES:
                for scenario in scenarios:
                    scenario_path = cr.scenario_dir(INSTALLATION, scenario, profile)
                    run_files = sorted((scenario_path / "runs").glob("run*.json"))
                    names = [p.name for p in run_files]
                    expected = {f"run{n:02d}.json" for n in range(1, 31)}
                    got = set(names)
                    ok = got == expected
                    # Content check: run01's content must say window=1, run11's
                    # window=2, run21's window=3 -- proving window 2 didn't just
                    # overwrite window 1's run01 with its OWN run01 content under
                    # a coincidentally-matching name (the real failure mode of
                    # the bug this test exists to catch).
                    content_ok = True
                    for n, expected_window in ((1, 1), (11, 2), (21, 3)):
                        f = scenario_path / "runs" / f"run{n:02d}.json"
                        if not f.exists() or json.loads(f.read_text())["window"] != expected_window:
                            content_ok = False
                    ok = ok and content_ok
                    all_ok = all_ok and ok
                    print(f"  {profile}/{scenario}: {len(got)} files, all 30 present={ok}, "
                          f"content-correct={content_ok} {'PASS' if ok else 'FAIL'}")

            print("\n=== settling/meta/gateway-log files: 3 windows x 3 profiles, none overwritten ===")
            meta_dir = Path(tmp) / "v8" / "latency" / "_campaign-control" / "windows" / INSTALLATION
            settling_ok = True
            for profile in cr.PROFILES:
                for window in (1, 2, 3):
                    names = [f"settling_{profile}_window{window:02d}_run{i}.json" for i in range(1, 6)]
                    names.append(f"settling_{profile}_window{window:02d}_meta.json")
                    names.append(f"gateway_block_{profile}_window{window:02d}.log")
                    for n in names:
                        if not (meta_dir / n).exists():
                            print(f"  MISSING: {n}")
                            settling_ok = False
            all_names = [p.name for p in meta_dir.glob("*") if p.name.startswith(("settling_", "gateway_block_"))]
            settling_distinct = len(all_names) == len(set(all_names))
            expected_settling_count = 3 * 3 * 7  # 3 profiles x 3 windows x (5 run + 1 meta + 1 gw log)
            settling_count_ok = len(all_names) == expected_settling_count
            print(f"  all present: {settling_ok}; all distinct: {settling_distinct}; "
                  f"count: {len(all_names)}/{expected_settling_count}")

            overall = all_ok and settling_ok and settling_distinct and settling_count_ok
            return overall


if __name__ == "__main__":
    ok = run()
    print("\n=== SUMMARY ===")
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
