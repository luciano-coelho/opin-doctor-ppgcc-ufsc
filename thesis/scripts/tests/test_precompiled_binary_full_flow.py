#!/usr/bin/env python3
"""Item 5: validates the precompiled tls_kem_proxy binary
(TLS_KEM_PROXY_USE_PRECOMPILED=1) inside the FULL settling+execution
flow against the REAL local docker-compose stack -- not just an
isolated ClientHello capture (already done separately,
test_tls_kem_proxy_precompiled_regression.py). Runs
LocalExecutor.start_block_proxies() (profile switch, 5 settling runs,
negotiated-group check) + one real execution + stop_block_proxies(),
once with TLS_KEM_PROXY_USE_PRECOMPILED=1 and once with it unset (go
run .), for the classic profile, and compares total bytes exchanged --
the same byte-total regression check this project has used since v1
(total_bytes_exchanged must be identical regardless of HOW the proxy
binary is built/run, only WHAT curve it presents should ever change
that number).

Requires Docker and the real local stack up (`docker compose --profile
main up -d` in insurance-server-lambdas/). Run directly:
`python thesis/scripts/tests/test_precompiled_binary_full_flow.py`
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "results" / "v8" / "campaign" / "scripts"))

PROFILE = "classic"


def run_one_mode(use_precompiled):
    os.environ["TLS_KEM_PROXY_USE_PRECOMPILED"] = "1" if use_precompiled else ""
    os.environ.pop("REMOTE_GATEWAY_HOST", None)

    import campaign_run as cr
    import importlib
    import opin_flow as of
    importlib.reload(of)  # pick up the env var fresh each mode

    executor = cr.LocalExecutor.__new__(cr.LocalExecutor)
    executor.of = of
    import latency_automation as la
    import switch_crypto_profile as scp
    executor.la = la
    executor.scp = scp
    executor._block_state = {}
    executor.allow_tcpdump_skip = True

    label = f"precompiled_{use_precompiled}"
    print(f"=== mode: {'precompiled binary' if use_precompiled else 'go run .'} ===")
    executor.start_block_proxies("sa-east-1", PROFILE, ["L0"], window=99)
    try:
        whole_run_retries = []
        result = la.run_once_timed_with_retry(PROFILE, label, whole_run_retries, return_calls=True)
        calls = result.get("calls", [])
        total_bytes = sum(c.get("request_bytes", 0) + c.get("response_bytes", 0) for c in calls)
        print(f"  execution: call_count={result.get('call_count')}, total_bytes_exchanged={total_bytes}")
        return total_bytes
    finally:
        executor.stop_block_proxies("sa-east-1", PROFILE, ["L0"], window=99)


def run(modes=(False, True)):
    results = {}
    for m in modes:
        results[m] = run_one_mode(use_precompiled=m)
    bytes_go_run = results.get(False)
    bytes_precompiled = results.get(True)
    print(f"\ngo run .:            {bytes_go_run}")
    print(f"precompiled binary:  {bytes_precompiled}")
    if False in results and True in results:
        ok = bytes_go_run is not None and bytes_go_run == bytes_precompiled
        print(f"{'PASS' if ok else 'FAIL'}: total_bytes_exchanged identical between modes")
        return ok
    print("(partial run -- only one mode requested this invocation)")
    return all(v is not None for v in results.values())


if __name__ == "__main__":
    import sys as _sys
    modes = (False, True)
    if "--precompiled-only" in _sys.argv:
        modes = (True,)
    elif "--gorun-only" in _sys.argv:
        modes = (False,)
    ok = run(modes)
    sys.exit(0 if ok else 1)
