#!/usr/bin/env python3
"""Mesh version of discover_latency.py: measures real ICMP RTT between
every pair of the 10 regions (not just sa-east-1 against the other 9).

SSH topology stays single-entry (Decision 10): the operator's machine
SSHes directly into sa-east-1 (the only instance reachable from the
operator's IP) and, for the other 9 regions, proxies through sa-east-1 via
an explicit ProxyCommand (`ssh -W %h:%p` through the prober) -- not
`-J`/ProxyJump, which failed host-key verification in testing even with
StrictHostKeyChecking=no. The private key never touches any EC2 instance
disk; it's used client-side for both hops.

For each of the 10 regions in turn (the "origin"), pings are run FROM that
region's instance TO each of the other 9 -- so every directed pair (90
total: 45 unique pairs x 2 directions) gets measured, which also gives a
free symmetry check (A->B vs B->A).

Rounds are spread across real time gaps, same as discover_latency.py.
Origins within a round run in parallel (ThreadPoolExecutor) to keep each
round's wall-clock time small relative to the inter-round gaps.
"""
import concurrent.futures
import json
import os
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DISCOVERY_DIR = Path(__file__).resolve().parent.parent / os.environ.get("MOCKOPIN_TERRAFORM_DIR", "terraform")
RESULTS_DIR = Path(__file__).resolve().parent.parent / os.environ.get(
    "MOCKOPIN_RESULTS_DIR", "aws-region-discovery-mesh-raw"
)
PING_COUNT = 20
ROUNDS = int(os.environ.get("MOCKOPIN_DISCOVERY_ROUNDS", "3"))
ROUND_GAP_SECONDS = int(os.environ.get("MOCKOPIN_DISCOVERY_ROUND_GAP_SECONDS", "3600"))
ORIGIN_REGION = "sa-east-1"

SSH_KEY = os.environ.get("MOCKOPIN_SSH_KEY")
if not SSH_KEY:
    sys.exit("Set MOCKOPIN_SSH_KEY to the path of the discovery SSH private key.")
SSH_KEY = Path(SSH_KEY)

SSH_OPTS = [
    "-i", str(SSH_KEY),
    "-o", "StrictHostKeyChecking=no",
    "-o", "UserKnownHostsFile=/dev/null",
    "-o", "ConnectTimeout=20",
    "-o", "BatchMode=yes",
]
# BatchMode=yes is critical when run unattended (no tty): without it, any
# prompt ssh would otherwise show (host-key confirmation, passphrase) just
# hangs or fails silently with stdin closed/non-interactive, instead of
# erroring immediately with a message we can see.


def terraform_output():
    result = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=DISCOVERY_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    all_ips = {ORIGIN_REGION: data["prober_public_ip"]["value"]}
    all_ips.update(data["candidate_public_ips"]["value"])
    return all_ips


def parse_samples_ms(ping_output):
    return [float(m) for m in re.findall(r"time=([\d.]+) ms", ping_output)]


def ping_from_origin(origin_region, origin_ip, dest_region, dest_ip, prober_ip):
    """Run `ping -c PING_COUNT dest_ip` on the origin instance. Direct SSH
    if origin is sa-east-1, proxied through sa-east-1 otherwise.

    Uses an explicit ProxyCommand (not -J/ProxyJump) because -J failed
    host-key verification in testing despite StrictHostKeyChecking=no --
    with -J, those -o options don't reliably apply to the inner jump
    connection. ProxyCommand spawns a fully independent ssh invocation for
    the jump hop, so the same options apply to both hops explicitly.

    The ProxyCommand value is a single string that ssh hands to an inner
    shell to execute -- on Windows, str(SSH_KEY) renders backslashes
    (WindowsPath), and the shell parsing that string treats '\\' as an
    escape character, silently corrupting the identity-file path and
    causing pubkey auth to fail for the proxied hop only (confirmed live:
    every non-sa-east-1 origin failed with "Permission denied" on the
    proxy hop, while direct connections -- which pass -i as a separate
    argv element, never shell-reparsed -- worked fine). Fix: use
    .as_posix() here specifically, so the embedded path always uses
    forward slashes regardless of platform."""
    if origin_region == ORIGIN_REGION:
        cmd = ["ssh", *SSH_OPTS, f"ec2-user@{origin_ip}", f"ping -c {PING_COUNT} {dest_ip}"]
    else:
        proxy_cmd = (
            f"ssh -i {SSH_KEY.as_posix()} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
            f"-o BatchMode=yes -o ConnectTimeout=20 -W %h:%p ec2-user@{prober_ip}"
        )
        cmd = [
            "ssh", *SSH_OPTS,
            "-o", f"ProxyCommand={proxy_cmd}",
            f"ec2-user@{origin_ip}", f"ping -c {PING_COUNT} {dest_ip}",
        ]
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=90, stdin=subprocess.DEVNULL
        )
    except subprocess.TimeoutExpired:
        print(f"    [{origin_region}->{dest_region}] TIMEOUT after 90s", file=sys.stderr)
        return []
    if r.returncode != 0:
        err = (r.stderr or "").strip().splitlines()
        err_tail = " | ".join(err[-3:]) if err else "(no stderr)"
        print(
            f"    [{origin_region}->{dest_region}] ssh exit {r.returncode}: {err_tail}",
            file=sys.stderr,
        )
        return []
    return parse_samples_ms(r.stdout)


def run_origin_sweep(origin_region, origin_ip, all_ips, prober_ip):
    pair_results = {}
    for dest_region, dest_ip in all_ips.items():
        if dest_region == origin_region:
            continue
        samples = ping_from_origin(origin_region, origin_ip, dest_region, dest_ip, prober_ip)
        pair_results[f"{origin_region}->{dest_region}"] = samples
    return origin_region, pair_results


def run_round(all_ips, round_num):
    started = datetime.now(timezone.utc)
    print(f"\n=== Round {round_num}/{ROUNDS} -- started {started.isoformat()} ===")
    prober_ip = all_ips[ORIGIN_REGION]
    pairs = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(all_ips)) as ex:
        futures = {
            ex.submit(run_origin_sweep, region, ip, all_ips, prober_ip): region
            for region, ip in all_ips.items()
        }
        for fut in concurrent.futures.as_completed(futures):
            region = futures[fut]
            try:
                origin_region, pair_results = fut.result()
            except Exception as e:
                print(f"  {region}: sweep FAILED ({e})")
                continue
            ok = sum(1 for s in pair_results.values() if s)
            print(f"  {origin_region}: {ok}/{len(pair_results)} destinations responded")
            pairs.update(pair_results)
    return {"round": round_num, "started_at_utc": started.isoformat(), "pairs": pairs}


def main():
    all_ips = terraform_output()
    print(f"Regions: {sorted(all_ips)}")
    print(
        f"Plan: {ROUNDS} rounds, {ROUND_GAP_SECONDS}s apart, {PING_COUNT} pings/pair/round, "
        f"{len(all_ips)} origins x {len(all_ips) - 1} destinations = {len(all_ips) * (len(all_ips) - 1)} directed pairs/round"
    )

    rounds = []
    for i in range(1, ROUNDS + 1):
        rounds.append(run_round(all_ips, i))
        if i < ROUNDS:
            print(f"Sleeping {ROUND_GAP_SECONDS}s before next round...")
            time.sleep(ROUND_GAP_SECONDS)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "latency_mesh_samples.json"
    out_path.write_text(
        json.dumps(
            {
                "regions": sorted(all_ips),
                "instance_type": "t4g.micro",
                "ping_count_per_round": PING_COUNT,
                "ssh_topology": "direct to sa-east-1; ProxyJump through sa-east-1 for the other 9",
                "rounds": rounds,
            },
            indent=2,
        )
    )
    print(f"\nWrote {out_path}")

    expected_pairs = len(all_ips) * (len(all_ips) - 1)
    ever_ok = {k for rd in rounds for k, s in rd["pairs"].items() if s}
    missing = expected_pairs - len(ever_ok)
    if missing:
        print(
            f"WARNING: {missing}/{expected_pairs} directed pairs never produced a single "
            f"sample across any round -- check security groups / SSH connectivity.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
