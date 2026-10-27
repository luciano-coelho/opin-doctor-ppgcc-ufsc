#!/usr/bin/env python3
"""A.2: confirms run_window()'s real call order is switch-profile (inside
start_block_proxies) -> proxies up -> 5 settling runs -> per-scenario
warmup -> round-robin -- and specifically that warmup happens AFTER
start_block_proxies, not before (the bug this turn fixed: the old code
ran every scenario's warmup BEFORE the block's proxy was even switched
to the right profile). Patches the module-level
start_block_proxies/run_warmup/run_one_execution/stop_block_proxies
functions (not the executor methods) so this needs no Docker/AWS at
all -- it's a pure call-order test. Run directly:
`python tests/test_block_order.py`.
"""
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import campaign_run as cr


def run():
    calls = []

    def fake_start_block_proxies(executor, installation, profile, scenarios, window):
        calls.append(("start_block_proxies", profile, window))

    def fake_stop_block_proxies(executor, installation, profile, scenarios, window):
        calls.append(("stop_block_proxies", profile, window))

    def fake_run_warmup(executor, installation, scenario, profile, window, scenario_path):
        calls.append(("run_warmup", profile, scenario, window))

    def fake_run_one_execution(executor, installation, scenario, profile, window, run_index, scenario_path):
        calls.append(("run_one_execution", profile, scenario, window, run_index))
        return {"call_count": 1}

    with tempfile.TemporaryDirectory() as tmp, \
         mock.patch.object(cr, "DATA_ROOT", Path(tmp)), \
         mock.patch.object(cr, "start_block_proxies", fake_start_block_proxies), \
         mock.patch.object(cr, "stop_block_proxies", fake_stop_block_proxies), \
         mock.patch.object(cr, "run_warmup", fake_run_warmup), \
         mock.patch.object(cr, "run_one_execution", fake_run_one_execution), \
         mock.patch.object(cr, "RUNS_PER_WINDOW", 1):
        executor = mock.Mock()
        cr.run_window(executor, "sa-east-1", window=1, seed=42, profile_order=cr.PROFILES[:])

    print("=== recorded call order ===")
    for c in calls:
        print(" ", c)

    kinds = [c[0] for c in calls]
    # For EVERY profile block: start_block_proxies must appear before
    # ALL of that block's run_warmup calls, and all run_warmup calls
    # before that block's first run_one_execution.
    ok = True
    i = 0
    while i < len(kinds):
        if kinds[i] != "start_block_proxies":
            print(f"FAIL: expected start_block_proxies at position {i}, got {kinds[i]}")
            ok = False
            break
        j = i + 1
        warmups = 0
        while j < len(kinds) and kinds[j] == "run_warmup":
            warmups += 1
            j += 1
        if warmups == 0:
            print(f"FAIL: no run_warmup calls after start_block_proxies at position {i}")
            ok = False
            break
        while j < len(kinds) and kinds[j] == "run_one_execution":
            j += 1
        if j >= len(kinds) or kinds[j] != "stop_block_proxies":
            print(f"FAIL: expected stop_block_proxies at position {j}, got "
                  f"{kinds[j] if j < len(kinds) else '(end)'}")
            ok = False
            break
        i = j + 1

    print(f"\n{'PASS' if ok else 'FAIL'}: start_block_proxies -> run_warmup (all scenarios) -> "
          f"run_one_execution (round-robin) -> stop_block_proxies, per profile block")
    return ok


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
