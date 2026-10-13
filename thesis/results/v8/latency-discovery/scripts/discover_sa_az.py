#!/usr/bin/env python3
"""sa-east-1 intra-region AZ-to-AZ RTT test (Decision 30/31): measures RTT
between 4 nodes -- sa-east-1's 3 AZs (one of them duplicated as a same-AZ
pair). No Buenos Aires -- that measurement was abandoned (Decision 31,
Free Tier blocker). Adapted from discover_bue_lz.py with the Buenos Aires
node dropped; reuses discover_latency_mesh.py's proven SSH/ProxyCommand/
BatchMode approach exactly (see that file's docstrings for why each of
those choices was made).

SSH topology (orchestration, always public): `sa-east-1-a` is the one
node reachable directly from the operator; every other node is proxied
through it via ProxyCommand, over its public IP.

Ping TARGET address (what's actually measured): all 4 nodes are in
sa-east-1, so every pair pings the destination's PRIVATE IP -- same
VPC/region, no reason to route the measured traffic out to the internet
and back (Decision 28's rule, applied uniformly since every pair here
qualifies).

Nodes: sa-east-1-a (jump host), sa-east-1-a2 (same AZ as a -- the
same-AZ sanity-floor pair), sa-east-1-b, sa-east-1-c. Full mesh among all
4 (12 directed pairs/round).
"""
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

TERRAFORM_DIR = Path(__file__).resolve().parent.parent / "terraform-sa-az-test"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "aws-region-discovery-05-sa-az-raw"
PING_COUNT = 20
ROUNDS = int(os.environ.get("MOCKOPIN_DISCOVERY_ROUNDS", "3"))
ROUND_GAP_SECONDS = int(os.environ.get("MOCKOPIN_DISCOVERY_ROUND_GAP_SECONDS", "3600"))
JUMP_NODE = "sa-east-1-a"

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


def terraform_output():
    result = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=TERRAFORM_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    pub = {JUMP_NODE: data["sa_east_1_a_public_ip"]["value"]}
    priv = {JUMP_NODE: data["sa_east_1_a_private_ip"]["value"]}
    other_pub = data["sa_east_1_other_public_ips"]["value"]
    other_priv = data["sa_east_1_other_private_ips"]["value"]
    for key, node in (("a2", "sa-east-1-a2"), ("b", "sa-east-1-b"), ("c", "sa-east-1-c")):
        pub[node] = other_pub[key]
        priv[node] = other_priv[key]
    return pub, priv


def parse_samples_ms(ping_output):
    return [float(m) for m in re.findall(r"time=([\d.]+) ms", ping_output)]


def ping_from_origin(origin_node, origin_ssh_ip, dest_node, ping_ip, jump_ssh_ip):
    """origin_ssh_ip/jump_ssh_ip are always the PUBLIC IPs (SSH
    orchestration channel) -- ping_ip is the destination's PRIVATE IP
    (every pair here is sa-east-1<->sa-east-1, Decision 28)."""
    if origin_node == JUMP_NODE:
        cmd = ["ssh", *SSH_OPTS, f"ec2-user@{origin_ssh_ip}", f"ping -c {PING_COUNT} {ping_ip}"]
    else:
        proxy_cmd = (
            f"ssh -i {SSH_KEY.as_posix()} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
            f"-o BatchMode=yes -o ConnectTimeout=20 -W %h:%p ec2-user@{jump_ssh_ip}"
        )
        cmd = [
            "ssh", *SSH_OPTS,
            "-o", f"ProxyCommand={proxy_cmd}",
            f"ec2-user@{origin_ssh_ip}", f"ping -c {PING_COUNT} {ping_ip}",
        ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        print(f"    [{origin_node}->{dest_node}] TIMEOUT after 90s", file=sys.stderr)
        return []
    if r.returncode != 0:
        err = (r.stderr or "").strip().splitlines()
        err_tail = " | ".join(err[-3:]) if err else "(no stderr)"
        print(f"    [{origin_node}->{dest_node}] ssh exit {r.returncode}: {err_tail}", file=sys.stderr)
        return []
    return parse_samples_ms(r.stdout)


def run_origin_sweep(origin_node, origin_ssh_ip, all_nodes, priv, jump_ssh_ip):
    pair_results = {}
    for dest_node in all_nodes:
        if dest_node == origin_node:
            continue
        samples = ping_from_origin(origin_node, origin_ssh_ip, dest_node, priv[dest_node], jump_ssh_ip)
        pair_results[f"{origin_node}->{dest_node}"] = samples
    return origin_node, pair_results


def run_round(all_nodes, pub, priv, round_num):
    started = datetime.now(timezone.utc)
    print(f"\n=== Round {round_num}/{ROUNDS} -- started {started.isoformat()} ===")
    jump_ssh_ip = pub[JUMP_NODE]
    pairs = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(all_nodes)) as ex:
        futures = {
            ex.submit(run_origin_sweep, node, pub[node], all_nodes, priv, jump_ssh_ip): node
            for node in all_nodes
        }
        for fut in concurrent.futures.as_completed(futures):
            node = futures[fut]
            try:
                origin_node, pair_results = fut.result()
            except Exception as e:
                print(f"  {node}: sweep FAILED ({e})")
                continue
            ok = sum(1 for s in pair_results.values() if s)
            print(f"  {origin_node}: {ok}/{len(pair_results)} destinations responded")
            pairs.update(pair_results)
    return {"round": round_num, "started_at_utc": started.isoformat(), "pairs": pairs}


def main():
    pub, priv = terraform_output()
    all_nodes = list(pub)
    print(f"Nodes: {sorted(all_nodes)}")
    print(
        f"Plan: {ROUNDS} rounds, {ROUND_GAP_SECONDS}s apart, {PING_COUNT} pings/pair/round, "
        f"{len(all_nodes)} origins x {len(all_nodes) - 1} destinations = "
        f"{len(all_nodes) * (len(all_nodes) - 1)} directed pairs/round"
    )

    rounds = []
    for i in range(1, ROUNDS + 1):
        rounds.append(run_round(all_nodes, pub, priv, i))
        if i < ROUNDS:
            print(f"Sleeping {ROUND_GAP_SECONDS}s before next round...")
            time.sleep(ROUND_GAP_SECONDS)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "latency_sa_az_samples.json"
    out_path.write_text(
        json.dumps(
            {
                "nodes": sorted(all_nodes),
                "jump_node": JUMP_NODE,
                "note": "sa-east-1-a2 is in the SAME AZ as sa-east-1-a (same-AZ sanity-floor pair); b/c are the other 2 AZs. No Buenos Aires -- abandoned, Decision 31. All pairs ping the destination's private IP (Decision 28).",
                "ping_count_per_round": PING_COUNT,
                "rounds": rounds,
            },
            indent=2,
        )
    )
    print(f"\nWrote {out_path}")

    expected_pairs = len(all_nodes) * (len(all_nodes) - 1)
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
