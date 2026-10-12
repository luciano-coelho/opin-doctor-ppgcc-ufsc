#!/usr/bin/env python3
"""Buenos Aires Local Zone test (Decision 17/23/25): measures RTT between
5 nodes -- sa-east-1's 3 AZs (one of them duplicated as a same-AZ pair)
plus the Buenos Aires Local Zone client. Reuses discover_latency_mesh.py's
proven SSH/ProxyCommand/BatchMode approach exactly (see that file's
docstrings for why each of those choices was made), adapted to this
Terraform's different output shape and node set.

SSH topology (orchestration, always public): `sa-east-1-a` is the one
node reachable directly from the operator; every other node is proxied
through it via ProxyCommand, over its public IP.

Ping TARGET address (what's actually measured, Decision 28): between any
two sa-east-1 nodes (a/a2/b/c), the ping targets the destination's
PRIVATE IP -- same VPC/region, no reason to route the measured traffic
out to the internet and back. Between sa-east-1 and Buenos Aires, the
ping targets the PUBLIC IP -- Buenos Aires is a different region/zone
group entirely, no VPC peering exists, only the public path is reachable
at all. Each pair's choice is recorded in the output file.

Nodes: sa-east-1-a (jump host), sa-east-1-a2 (same AZ as a -- the
same-AZ sanity-floor pair), sa-east-1-b, sa-east-1-c, buenos-aires.
Full mesh among all 5 (20 directed pairs/round).
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

TERRAFORM_DIR = Path(__file__).resolve().parent.parent / "terraform-bue-lz-test"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "aws-region-discovery-bue-lz-raw"
PING_COUNT = 20
ROUNDS = int(os.environ.get("MOCKOPIN_DISCOVERY_ROUNDS", "3"))
ROUND_GAP_SECONDS = int(os.environ.get("MOCKOPIN_DISCOVERY_ROUND_GAP_SECONDS", "3600"))
JUMP_NODE = "sa-east-1-a"
SA_EAST_1_NODES = {"sa-east-1-a", "sa-east-1-a2", "sa-east-1-b", "sa-east-1-c"}

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
    pub["buenos-aires"] = data["bue_client_public_ip"]["value"]
    priv["buenos-aires"] = None  # never used -- Buenos Aires has no private-path reachability from sa-east-1
    return pub, priv


def ping_target_ip(origin_node, dest_node, pub, priv):
    """Decision 28: private IP within sa-east-1, public IP crossing to
    Buenos Aires."""
    if origin_node in SA_EAST_1_NODES and dest_node in SA_EAST_1_NODES:
        return priv[dest_node], "private"
    return pub[dest_node], "public"


def parse_samples_ms(ping_output):
    return [float(m) for m in re.findall(r"time=([\d.]+) ms", ping_output)]


def ping_from_origin(origin_node, origin_ssh_ip, dest_node, ping_ip, jump_ssh_ip):
    """origin_ssh_ip/jump_ssh_ip are always the PUBLIC IPs (SSH
    orchestration channel) -- ping_ip is whichever address (private or
    public, per Decision 28) is actually being measured."""
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


def run_origin_sweep(origin_node, origin_ssh_ip, all_nodes, pub, priv, jump_ssh_ip):
    pair_results = {}
    ip_kind_used = {}
    for dest_node in all_nodes:
        if dest_node == origin_node:
            continue
        ping_ip, kind = ping_target_ip(origin_node, dest_node, pub, priv)
        samples = ping_from_origin(origin_node, origin_ssh_ip, dest_node, ping_ip, jump_ssh_ip)
        key = f"{origin_node}->{dest_node}"
        pair_results[key] = samples
        ip_kind_used[key] = kind
    return origin_node, pair_results, ip_kind_used


def run_round(all_nodes, pub, priv, round_num):
    started = datetime.now(timezone.utc)
    print(f"\n=== Round {round_num}/{ROUNDS} -- started {started.isoformat()} ===")
    jump_ssh_ip = pub[JUMP_NODE]
    pairs = {}
    ip_kind = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(all_nodes)) as ex:
        futures = {
            ex.submit(run_origin_sweep, node, pub[node], all_nodes, pub, priv, jump_ssh_ip): node
            for node in all_nodes
        }
        for fut in concurrent.futures.as_completed(futures):
            node = futures[fut]
            try:
                origin_node, pair_results, kinds = fut.result()
            except Exception as e:
                print(f"  {node}: sweep FAILED ({e})")
                continue
            ok = sum(1 for s in pair_results.values() if s)
            print(f"  {origin_node}: {ok}/{len(pair_results)} destinations responded")
            pairs.update(pair_results)
            ip_kind.update(kinds)
    return {"round": round_num, "started_at_utc": started.isoformat(), "pairs": pairs, "ip_kind_used": ip_kind}


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
    out_path = RESULTS_DIR / "latency_bue_lz_samples.json"
    out_path.write_text(
        json.dumps(
            {
                "nodes": sorted(all_nodes),
                "jump_node": JUMP_NODE,
                "note": "sa-east-1-a2 is in the SAME AZ as sa-east-1-a (same-AZ pair); b/c are the other 2 AZs; buenos-aires is the Local Zone client. Decision 28: sa-east-1<->sa-east-1 pairs ping the private IP, any pair touching buenos-aires pings the public IP (see rounds[].ip_kind_used per pair).",
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
