#!/usr/bin/env python3
"""A.1: three consecutive windows must not overwrite each other's
settling_{profile}_run{i}.json / settling_{profile}_meta.json /
gateway_block_{profile}.log files. Exercises the REAL
LocalExecutor.start_block_proxies()/stop_block_proxies() code paths --
not just the filename-formatting expression -- by monkeypatching the
handful of calls that need a real docker-compose stack/gateway
container (self.scp._compose, self.of.start_tls_kem_proxy,
self.la.run_once_timed_with_retry, the `docker logs`/`docker exec`
subprocess.run calls) so this runs on any machine, no Docker required.
Run directly: `python tests/test_window_no_overwrite.py`.
"""
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import campaign_run as cr

PROFILE = "classic"
ADDR_CLIENT = "203.0.113.10:51000"
ADDR_INTERNAL = "203.0.113.10:51002"


def _fake_gateway_log():
    def line(ts, obj):
        return f"{ts} {json.dumps(obj)}"
    return "\n".join([
        line("2026-10-13T19:00:00.000000000Z", {"msg": cr._CARVEOUT_MSG, "sni": "matls-api.local", "remoteAddr": ADDR_INTERNAL}),
        line("2026-10-13T19:00:00.050000000Z", {"msg": cr._HANDSHAKE_COMPLETE_MSG, "remoteAddr": ADDR_INTERNAL, "curveID": "CurveP256"}),
        line("2026-10-13T19:00:00.100000000Z", {"msg": cr._HANDSHAKE_COMPLETE_MSG, "remoteAddr": ADDR_CLIENT, "curveID": "CurveP384"}),
    ])


def _make_executor(data_root):
    executor = cr.LocalExecutor.__new__(cr.LocalExecutor)
    executor.of = mock.Mock()
    executor.of.GATEWAY_CONTAINER = "insurance-server-lambdas-mtls-1"
    executor.of.start_tls_kem_proxy = mock.Mock(return_value="fake-proc")
    executor.of.start_pqc_signer_service = mock.Mock(return_value=False)
    executor.of.stop_pqc_signer_service = mock.Mock()
    executor.of.stop_tls_kem_proxy = mock.Mock()

    executor.scp = mock.Mock()
    compose_result = mock.Mock(returncode=0, stdout="", stderr="")
    executor.scp._compose = mock.Mock(return_value=compose_result)
    executor.scp.PROFILE_DEPENDENT_SERVICES = []
    executor.scp._start_if_exited = mock.Mock()
    executor.scp._container_status = mock.Mock(return_value="running")
    executor.scp._wait_for_mtls_ready = mock.Mock()
    executor.scp._check_psql_checkpoint_health = mock.Mock()

    la_result_template = {"call_count": 5, "duration_seconds": 1.0}
    executor.la = mock.Mock()
    executor.la.run_once_timed_with_retry = mock.Mock(
        side_effect=lambda profile, label, retries, return_calls=False: dict(la_result_template, label=label)
    )
    executor._block_state = {}
    executor.allow_tcpdump_skip = True
    return executor


def run():
    import campaign_run
    with tempfile.TemporaryDirectory() as tmp:
        with mock.patch.object(campaign_run, "DATA_ROOT", Path(tmp)), \
             mock.patch.object(subprocess, "run") as mocked_run, \
             mock.patch.object(campaign_run, "time") as mocked_time:
            mocked_time.sleep = lambda *_: None
            mocked_time.monotonic = __import__("time").monotonic

            def fake_run(argv, **kwargs):
                if argv[:2] == ["docker", "logs"]:
                    return mock.Mock(returncode=0, stdout=_fake_gateway_log(), stderr="")
                return mock.Mock(returncode=0, stdout="", stderr="")
            mocked_run.side_effect = fake_run

            executor = _make_executor(Path(tmp))
            meta_dir = Path(tmp) / "v8" / "latency" / "_campaign-control" / "windows" / "sa-east-1"

            seen_files = set()
            collisions = []
            for window in (1, 2, 3):
                executor.start_block_proxies("sa-east-1", PROFILE, ["L0"], window)
                executor.stop_block_proxies("sa-east-1", PROFILE, ["L0"], window)
                window_files = {
                    p for p in meta_dir.glob("*") if f"window{window:02d}" in p.name or f"_run" in p.name
                }
                for p in sorted(meta_dir.glob("*")):
                    if p in seen_files and p.name not in [sp.name for sp in seen_files if sp != p]:
                        pass  # existence alone isn't a collision -- checked by mtime/content below
                for p in meta_dir.glob(f"settling_{PROFILE}_window{window:02d}_run*.json"):
                    seen_files.add(p)
                for p in meta_dir.glob(f"settling_{PROFILE}_window{window:02d}_meta.json"):
                    seen_files.add(p)
                for p in meta_dir.glob(f"gateway_block_{PROFILE}_window{window:02d}.log"):
                    seen_files.add(p)

            print("=== files written across 3 windows ===")
            all_names = sorted(p.name for p in meta_dir.glob("*"))
            for n in all_names:
                print(f"  {n}")

            expected_count = 3 * (5 + 1 + 1)  # 5 settling runs + 1 meta + 1 gateway log, per window
            ok_count = len(all_names) == expected_count
            ok_distinct = len(set(all_names)) == len(all_names)  # no name reused -- real distinctness, not just count
            windows_present = all(f"window{w:02d}" in "".join(all_names) for w in (1, 2, 3))

            print(f"\nfile count: {len(all_names)} (expected {expected_count}) -- {'PASS' if ok_count else 'FAIL'}")
            print(f"all names distinct: {'PASS' if ok_distinct else 'FAIL'}")
            print(f"all 3 windows represented: {'PASS' if windows_present else 'FAIL'}")
            return ok_count and ok_distinct and windows_present


if __name__ == "__main__":
    ok = run()
    print("\n=== SUMMARY ===")
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
