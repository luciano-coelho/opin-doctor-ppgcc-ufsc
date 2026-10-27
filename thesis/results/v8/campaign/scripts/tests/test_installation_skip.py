#!/usr/bin/env python3
"""Pilot 2 (2026-10-27), item 3: regression test for the installation-skip
fix in run_window() (campaign_run.py). Before this fix, an installation
with zero enabled client scenarios in a SCOPED inventory (e.g. a pilot
inventory covering only sa-east-1, run against the full-campaign
PROFILES/SCENARIO_ROTATION installation list) made run_window() call
sys.exit() -- a hard abort of the WHOLE campaign process, not just a skip
of that one installation. Found live during pilot 2's real AWS run: the
pilot's own sa-east-1 window had already finished in full before
iteration reached us-east-1 (empty for this scoped run), so the abort was
harmless THIS time only because of iteration order -- it would have
killed other installations' still-pending windows in any run where an
empty installation is iterated before a non-empty one, or where more
than one installation is scoped out.

Three fake-inventory scenarios, run directly: `python
tests/test_installation_skip.py`.
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import campaign_run as cr


def _run_window_recording(installation, inventory_clients, window=1):
    """Runs run_window() against a Mock(spec=SSHExecutor) (isinstance()
    passes, matching the real isinstance(executor, SSHExecutor) check in
    run_window() -- a bare mock.Mock() would NOT trigger the inventory-
    filtering path at all, same reasoning as test_block_order.py's own
    comment about why it uses a bare Mock for the UNFILTERED-path test).
    Returns (calls, raised) -- raised is the exception object if run_window
    raised SystemExit, else None."""
    calls = []

    def fake_start_block_proxies(executor, installation, profile, scenarios, window):
        calls.append(("start_block_proxies", installation, profile, tuple(scenarios), window))

    def fake_stop_block_proxies(executor, installation, profile, scenarios, window):
        calls.append(("stop_block_proxies", installation, profile, tuple(scenarios), window))

    def fake_run_warmup(executor, installation, scenario, profile, window, scenario_path):
        calls.append(("run_warmup", installation, profile, scenario, window))

    def fake_run_one_execution(executor, installation, scenario, profile, window, run_index, scenario_path):
        calls.append(("run_one_execution", installation, profile, scenario, window, run_index))
        return {"call_count": 1}

    def fake_pre_block_checks(executor, installation, profile):
        # Real pre_block_checks() does real SSH/docker-image/gateway-log
        # work for an SSHExecutor (needed here only so isinstance(executor,
        # SSHExecutor) is True and the inventory-filtering branch this test
        # targets actually runs) -- irrelevant to the skip logic under
        # test, same reasoning as test_block_order.py patching the other
        # "real work" functions it isn't testing.
        calls.append(("pre_block_checks", installation, profile))
        return {}

    executor = mock.Mock(spec=cr.SSHExecutor)
    executor.inventory = {"clients": inventory_clients}

    import tempfile
    raised = None
    with tempfile.TemporaryDirectory() as tmp, \
         mock.patch.object(cr, "DATA_ROOT", Path(tmp)), \
         mock.patch.object(cr, "pre_block_checks", fake_pre_block_checks), \
         mock.patch.object(cr, "start_block_proxies", fake_start_block_proxies), \
         mock.patch.object(cr, "stop_block_proxies", fake_stop_block_proxies), \
         mock.patch.object(cr, "run_warmup", fake_run_warmup), \
         mock.patch.object(cr, "run_one_execution", fake_run_one_execution), \
         mock.patch.object(cr, "RUNS_PER_WINDOW", 1):
        try:
            cr.run_window(executor, installation, window=window, seed=42, profile_order=cr.PROFILES[:])
        except SystemExit as e:
            raised = e
    return calls, raised


def test_pilot_inventory_scopes_out_other_installations():
    """Case 1 (the real pilot 2 bug): a pilot inventory with ONLY sa-east-1
    client scenarios. Calling run_window() for us-east-1 (scoped out) must
    NOT raise SystemExit and must NOT call any block/warmup/execution
    function -- just a skip. Calling it for sa-east-1 (present) must
    proceed normally."""
    pilot_clients = {"L0@sa-east-1": {}, "L325@sa-east-1": {}}

    calls, raised = _run_window_recording("us-east-1", pilot_clients)
    ok = raised is None and calls == []
    print(f"{'PASS' if ok else 'FAIL'}: us-east-1 scoped out of a sa-east-1-only pilot inventory "
          f"-> skipped, no SystemExit, no block/warmup/execution calls (raised={raised!r}, calls={calls})")

    calls2, raised2 = _run_window_recording("sa-east-1", pilot_clients)
    kinds2 = [c[0] for c in calls2]
    ok2 = raised2 is None and "start_block_proxies" in kinds2 and "run_one_execution" in kinds2
    print(f"{'PASS' if ok2 else 'FAIL'}: sa-east-1 (present in the same pilot inventory) -> proceeds normally "
          f"(raised={raised2!r}, kinds={kinds2})")
    return ok and ok2


def test_full_campaign_inventory_skips_nothing():
    """Case 2: a full-campaign inventory with every SCENARIO_ROTATION
    installation's scenarios present. No installation should be skipped."""
    full_clients = {}
    for installation, windows in cr.SCENARIO_ROTATION.items():
        for scenario in windows[1]:
            full_clients[f"{scenario}@{installation}"] = {}

    ok = True
    for installation in cr.SCENARIO_ROTATION:
        calls, raised = _run_window_recording(installation, full_clients)
        kinds = [c[0] for c in calls]
        this_ok = raised is None and "start_block_proxies" in kinds and "run_one_execution" in kinds
        ok = ok and this_ok
        print(f"{'PASS' if this_ok else 'FAIL'}: {installation} present in a full-campaign inventory -> "
              f"not skipped (raised={raised!r}, kinds={kinds})")
    return ok


def test_scenario_enabled_but_installation_absent():
    """Case 3: the inventory's clients dict has entries for a DIFFERENT
    installation only (e.g. "L0@sa-east-1" exists, but zero "*@ap-northeast-1"
    keys exist at all) -- ap-northeast-1 has no enabled scenario in this
    run's inventory, same as case 1 but with the installation entirely
    unrepresented rather than partially scoped."""
    clients = {"L0@sa-east-1": {}}
    calls, raised = _run_window_recording("ap-northeast-1", clients)
    ok = raised is None and calls == []
    print(f"{'PASS' if ok else 'FAIL'}: ap-northeast-1 entirely absent from inventory -> skipped, "
          f"no SystemExit, no calls (raised={raised!r}, calls={calls})")
    return ok


if __name__ == "__main__":
    results = [
        test_pilot_inventory_scopes_out_other_installations(),
        test_full_campaign_inventory_skips_nothing(),
        test_scenario_enabled_but_installation_absent(),
    ]
    sys.exit(0 if all(results) else 1)
