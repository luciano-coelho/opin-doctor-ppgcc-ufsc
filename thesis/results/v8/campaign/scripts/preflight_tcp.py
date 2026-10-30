"""TCP pre-flight check (port 443), once per client, before any window
starts -- part of the justification for removing the per-execution
reference ping (Decision 105): basic reachability is confirmed here,
once, instead of via a per-execution ICMP ping that was always blocked
anyway. MUST run the actual connect attempt FROM each client itself
(via SSH, same campaign_key relay every other script here uses) --
checking from control directly would test a different network path
(control is not a client in the inventory, has no gateway_ingress_cidrs
SG rule, and a co-located client's own path specifically depends on
using the PRIVATE ip, Decision 83 -- control's own route to that
private IP is not guaranteed to exist or behave the same way).

Usage: python3 preflight_tcp.py
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/home/ec2-user/campaign/scripts")
import campaign_run as cr  # noqa: E402

CAMPAIGN_KEY = "/home/ec2-user/.ssh/campaign_key"


def tcp_check_from_client(client_ip, gateway_ip, port=443, timeout=5):
    cmd = [
        "ssh", "-i", CAMPAIGN_KEY, "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
        "-o", "BatchMode=yes", "-o", f"ConnectTimeout={timeout}", f"ec2-user@{client_ip}",
        f"timeout {timeout} bash -c 'echo > /dev/tcp/{gateway_ip}/{port}' && echo OK || echo FAIL",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
        ok = "OK" in r.stdout
        return ok, None if ok else (r.stdout.strip() + r.stderr.strip())
    except subprocess.TimeoutExpired:
        return False, "ssh timeout"


def main():
    inventory = cr.load_inventory()
    results = {}
    all_ok = True
    for scenario_key, client in inventory.get("clients", {}).items():
        installation = scenario_key.split("@", 1)[1]
        gateway_ip = cr.pick_gateway_ip(inventory, installation, scenario_key)
        client_ip = client["public_ip"]
        ok, err = tcp_check_from_client(client_ip, gateway_ip)
        results[scenario_key] = {"gateway_ip": gateway_ip, "ok": ok, "error": err}
        all_ok = all_ok and ok
        print(f"{'OK  ' if ok else 'FAIL'} {scenario_key} -> {gateway_ip}:443"
              + ("" if ok else f" ({err})"))
    Path("/home/ec2-user/preflight_tcp_result.json").write_text(json.dumps(results, indent=2))
    print(f"=== pre-flight TCP: {'ALL OK' if all_ok else 'FAILURES PRESENT'} "
          f"({sum(r['ok'] for r in results.values())}/{len(results)}) ===")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
