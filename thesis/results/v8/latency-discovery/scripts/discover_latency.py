#!/usr/bin/env python3
"""Measure real ICMP RTT from the sa-east-1 prober instance to each
candidate region's prober instance, via SSH.

Reads the Terraform discovery module's outputs (prober_public_ip,
candidate_public_ips), SSHes into the sa-east-1 instance, and runs a ping
sweep against every candidate from there -- so the measurement reflects
real AWS-to-AWS network path, not this machine's local ISP route.

Runs multiple rounds, spaced by real time gaps, so each region's RTT
distribution is sampled across more than one time of day rather than a
single snapshot. All individual per-packet samples are kept (not just an
average) in aws-region-discovery-01-single-origin-raw/latency_samples.json; select_regions.py
computes median/min/max from them.
"""
import json
import os
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DISCOVERY_DIR = Path(__file__).resolve().parent.parent / "terraform"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "aws-region-discovery-01-single-origin-raw"
PING_COUNT = 20
ROUNDS = int(os.environ.get("MOCKOPIN_DISCOVERY_ROUNDS", "3"))
ROUND_GAP_SECONDS = int(os.environ.get("MOCKOPIN_DISCOVERY_ROUND_GAP_SECONDS", "3600"))

# The SSH private key is never stored in the repo. Point this at wherever
# you generated it (see README.md) -- e.g. your scratchpad directory.
SSH_KEY = os.environ.get("MOCKOPIN_SSH_KEY")
if not SSH_KEY:
    sys.exit("Set MOCKOPIN_SSH_KEY to the path of the discovery SSH private key.")
SSH_KEY = Path(SSH_KEY)


def terraform_output():
    result = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=DISCOVERY_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    return data["prober_public_ip"]["value"], data["candidate_public_ips"]["value"]


def ssh_run(host, command, timeout=60):
    return subprocess.run(
        [
            "ssh",
            "-i", str(SSH_KEY),
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", f"ConnectTimeout={timeout}",
            f"ec2-user@{host}",
            command,
        ],
        capture_output=True,
        text=True,
        timeout=timeout + 10,
    )


def parse_samples_ms(ping_output):
    # Each reply line: "64 bytes from 1.2.3.4: icmp_seq=1 ttl=51 time=12.3 ms"
    return [float(m) for m in re.findall(r"time=([\d.]+) ms", ping_output)]


def run_round(prober_ip, candidates, round_num):
    started = datetime.now(timezone.utc)
    print(f"\n=== Round {round_num}/{ROUNDS} -- started {started.isoformat()} ===")
    samples_by_region = {}
    for region, ip in candidates.items():
        print(f"  sa-east-1 -> {region} ({ip}) ...", end=" ", flush=True)
        r = ssh_run(prober_ip, f"ping -c {PING_COUNT} {ip}")
        samples = parse_samples_ms(r.stdout) if r.returncode == 0 else []
        if not samples:
            print(f"FAILED: {(r.stderr or '').strip() or 'no samples parsed'}")
        else:
            print(f"{len(samples)} samples, median={statistics.median(samples):.2f}ms")
        samples_by_region[region] = samples
    return {
        "round": round_num,
        "started_at_utc": started.isoformat(),
        "samples": samples_by_region,
    }


def main():
    prober_ip, candidates = terraform_output()
    print(f"Prober (sa-east-1): {prober_ip}")
    print(
        f"Plan: {ROUNDS} rounds, {ROUND_GAP_SECONDS}s apart "
        f"(spreading samples across different times of day), "
        f"{PING_COUNT} pings/region/round"
    )

    rounds = []
    for i in range(1, ROUNDS + 1):
        rounds.append(run_round(prober_ip, candidates, i))
        if i < ROUNDS:
            print(f"Sleeping {ROUND_GAP_SECONDS}s before next round...")
            time.sleep(ROUND_GAP_SECONDS)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "latency_samples.json"
    out_path.write_text(
        json.dumps(
            {
                "origin_region": "sa-east-1",
                "instance_type": "t4g.micro",
                "ping_count_per_round": PING_COUNT,
                "rounds": rounds,
            },
            indent=2,
        )
    )
    print(f"\nWrote {out_path}")

    all_regions = set(candidates)
    ever_ok = {r for rd in rounds for r, s in rd["samples"].items() if s}
    missing = all_regions - ever_ok
    if missing:
        print(
            f"WARNING: these regions never responded in any round: {sorted(missing)} "
            f"-- check security groups / instance state.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
