#!/usr/bin/env python3
"""Pilot item 2 (this turn): unit tests for SSHExecutor._server_gateway_ip()
(Decision 83) -- the colocated-aware IP a CLIENT uses to reach the
server's own gateway. Fake inventories only, no Docker/AWS/SSH at all.
Run directly: `python tests/test_server_gateway_ip.py`.
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import campaign_run as cr


def case_colocated_client_uses_private_ip():
    """L0 (colocated=True) must get the server's private_ip, not public_ip."""
    inventory = {
        "servers": {"sa-east-1": {"public_ip": "56.126.104.57", "private_ip": "172.31.2.152"}},
        "clients": {"L0@sa-east-1": {"colocated": True, "public_ip": "54.20.165.107", "private_ip": "172.31.12.103"}},
    }
    executor = cr.SSHExecutor(inventory, dry_run=True)
    ip = executor._server_gateway_ip("sa-east-1", "L0@sa-east-1")
    ok = ip == "172.31.2.152"
    print(f"  [{'PASS' if ok else 'FAIL'}] colocated client -> server private_ip (got {ip!r})")
    return ok


def case_remote_client_uses_public_ip():
    """L325 (colocated=False, different region) must get the server's public_ip."""
    inventory = {
        "servers": {"sa-east-1": {"public_ip": "56.126.104.57", "private_ip": "172.31.2.152"}},
        "clients": {"L325@sa-east-1": {"colocated": False, "public_ip": "47.128.175.221", "private_ip": "172.31.10.122"}},
    }
    executor = cr.SSHExecutor(inventory, dry_run=True)
    ip = executor._server_gateway_ip("sa-east-1", "L325@sa-east-1")
    ok = ip == "56.126.104.57"
    print(f"  [{'PASS' if ok else 'FAIL'}] remote client -> server public_ip (got {ip!r})")
    return ok


def case_missing_colocated_field_raises():
    """A client entry with no 'colocated' field at all must fail loudly,
    never silently default to either IP."""
    inventory = {
        "servers": {"sa-east-1": {"public_ip": "56.126.104.57", "private_ip": "172.31.2.152"}},
        "clients": {"L0@sa-east-1": {"public_ip": "54.20.165.107", "private_ip": "172.31.12.103"}},
    }
    executor = cr.SSHExecutor(inventory, dry_run=True)
    try:
        executor._server_gateway_ip("sa-east-1", "L0@sa-east-1")
        ok = False
        print("  [FAIL] missing 'colocated' field did not raise")
    except RuntimeError as e:
        ok = "colocated" in str(e)
        print(f"  [{'PASS' if ok else 'FAIL'}] missing 'colocated' field raises RuntimeError: {e}")
    return ok


def case_missing_required_ip_raises():
    """colocated=True but the server has no private_ip at all -- must
    fail loudly, never fall back to public_ip silently."""
    inventory = {
        "servers": {"sa-east-1": {"public_ip": "56.126.104.57"}},
        "clients": {"L0@sa-east-1": {"colocated": True, "public_ip": "54.20.165.107"}},
    }
    executor = cr.SSHExecutor(inventory, dry_run=True)
    try:
        executor._server_gateway_ip("sa-east-1", "L0@sa-east-1")
        ok = False
        print("  [FAIL] missing private_ip did not raise")
    except RuntimeError as e:
        ok = "private_ip" in str(e)
        print(f"  [{'PASS' if ok else 'FAIL'}] colocated=True with no server private_ip raises RuntimeError: {e}")
    return ok


def case_missing_required_public_ip_raises():
    """colocated=False but the server has no public_ip at all (an
    unlikely but real possible inventory gap) -- same explicit-failure
    requirement as the private_ip case above."""
    inventory = {
        "servers": {"sa-east-1": {"private_ip": "172.31.2.152"}},
        "clients": {"L325@sa-east-1": {"colocated": False, "public_ip": "47.128.175.221"}},
    }
    executor = cr.SSHExecutor(inventory, dry_run=True)
    try:
        executor._server_gateway_ip("sa-east-1", "L325@sa-east-1")
        ok = False
        print("  [FAIL] missing public_ip did not raise")
    except RuntimeError as e:
        ok = "public_ip" in str(e)
        print(f"  [{'PASS' if ok else 'FAIL'}] colocated=False with no server public_ip raises RuntimeError: {e}")
    return ok


def _inventory_two_clients():
    return {
        "servers": {"sa-east-1": {"public_ip": "56.126.104.57", "private_ip": "172.31.2.152"}},
        "clients": {
            "L0@sa-east-1": {"colocated": True, "public_ip": "54.20.165.107", "private_ip": "172.31.12.103"},
            "L325@sa-east-1": {"colocated": False, "public_ip": "47.128.175.221", "private_ip": "172.31.10.122"},
        },
    }


class _FakeCompletedProcess:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def case_connectivity_refused_counts_as_ok():
    """Found live, the pilot's own first real run after this check was
    added: verify_gateway_connectivity() runs BEFORE the first profile
    switch, so the gateway isn't listening yet -- a fast "Connection
    refused" is the EXPECTED, GOOD state (PILOT_RUNBOOK.md's own
    standing distinction), not a failure. Treating every nonzero exit
    as FAIL made this abort on literally every real run. Mocks
    subprocess.run to return "Connection refused" (exit 1) for both
    clients -- must NOT raise."""
    inventory = _inventory_two_clients()
    def fake_run(cmd, **kwargs):
        return _FakeCompletedProcess(1, stderr="bash: connect: Connection refused\n")
    with mock.patch.object(cr.subprocess, "run", fake_run):
        try:
            cr.verify_gateway_connectivity(inventory)
            ok = True
        except SystemExit as e:
            ok = False
            print(f"    unexpected SystemExit: {e}")
    print(f"  [{'PASS' if ok else 'FAIL'}] refused (exit!=0, 'Connection refused' in output) does not raise")
    return ok


def case_connectivity_timeout_is_a_real_failure():
    """A genuine timeout (no refusal text, the full probe duration
    elapses) must still abort loudly -- this is the actual broken-path
    case the check exists to catch."""
    inventory = _inventory_two_clients()
    def fake_run(cmd, **kwargs):
        return _FakeCompletedProcess(1, stdout="", stderr="")  # no "Connection refused" -- a real timeout
    with mock.patch.object(cr.subprocess, "run", fake_run):
        try:
            cr.verify_gateway_connectivity(inventory)
            ok = False
            print("    did not raise on a genuine timeout")
        except SystemExit:
            ok = True
    print(f"  [{'PASS' if ok else 'FAIL'}] a genuine timeout (no refusal) still raises SystemExit")
    return ok


def case_connectivity_connected_is_ok():
    """A real successful connection (exit 0) must also count as OK --
    the stack already up and serving (e.g. a resumed, mid-campaign run)."""
    inventory = _inventory_two_clients()
    def fake_run(cmd, **kwargs):
        return _FakeCompletedProcess(0)
    with mock.patch.object(cr.subprocess, "run", fake_run):
        try:
            cr.verify_gateway_connectivity(inventory)
            ok = True
        except SystemExit as e:
            ok = False
            print(f"    unexpected SystemExit: {e}")
    print(f"  [{'PASS' if ok else 'FAIL'}] a real successful connection does not raise")
    return ok


def run():
    results = {
        "colocated_client_uses_private_ip": case_colocated_client_uses_private_ip(),
        "remote_client_uses_public_ip": case_remote_client_uses_public_ip(),
        "missing_colocated_field_raises": case_missing_colocated_field_raises(),
        "missing_required_ip_raises": case_missing_required_ip_raises(),
        "missing_required_public_ip_raises": case_missing_required_public_ip_raises(),
        "connectivity_refused_counts_as_ok": case_connectivity_refused_counts_as_ok(),
        "connectivity_timeout_is_a_real_failure": case_connectivity_timeout_is_a_real_failure(),
        "connectivity_connected_is_ok": case_connectivity_connected_is_ok(),
    }
    return results


if __name__ == "__main__":
    results = run()
    print("\n=== SUMMARY ===")
    for k, v in results.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
    sys.exit(0 if all(results.values()) else 1)
