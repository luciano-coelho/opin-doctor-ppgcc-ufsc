#!/usr/bin/env python3
"""Decision 43's flex-instance launch test: for every (region, type) pair
in terraform-flex-launch-test's output, SSH in, run a short synthetic
CPU load (stress-ng -- a labeled proxy for tls_kem_proxy's real shape,
NOT the real cryptographic workload), and sample /proc/stat's steal and
overall CPU fields before/during/after. Reports steal% and a CPU-drop
check per instance; does not itself decide pass/fail against the
pre-registered 5% steal threshold (left for direct inspection of the
written results, so the threshold isn't silently moved).

NOT RUN YET -- `terraform apply` for this root hasn't happened. This
script is prepared so that once the author approves an apply, the actual
launch test needs no further development, only execution.
"""
import concurrent.futures
import json
import os
import subprocess
import sys
import time
from pathlib import Path

TERRAFORM_DIR = Path(__file__).resolve().parent.parent / "terraform-flex-launch-test"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "aws-flex-launch-test-raw"
LOAD_SECONDS = int(os.environ.get("MOCKOPIN_FLEX_LOAD_SECONDS", "60"))

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

# cpu line: user nice system idle iowait irq softirq steal guest guest_nice
PROC_STAT_CMD = "grep '^cpu ' /proc/stat"


def terraform_outputs():
    result = subprocess.run(
        ["terraform", "output", "-json", "public_ips_by_region"],
        cwd=TERRAFORM_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)["value"]


def parse_cpu_line(line):
    fields = [int(x) for x in line.strip().split()[1:]]
    # pad in case an older kernel has fewer fields
    while len(fields) < 10:
        fields.append(0)
    user, nice, system, idle, iowait, irq, softirq, steal = fields[:8]
    total = sum(fields)
    busy = total - idle - iowait
    return {"total": total, "busy": busy, "steal": steal}


def ssh_run(ip, cmd, timeout=90):
    full = ["ssh", *SSH_OPTS, f"ec2-user@{ip}", cmd]
    r = subprocess.run(full, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout, r.stderr


def ensure_stress_ng(ip):
    # Amazon Linux 2023: stress-ng is in the default repos.
    ssh_run(ip, "sudo dnf install -y stress-ng >/dev/null 2>&1 || true", timeout=120)


def sample_cpu(ip):
    rc, out, _ = ssh_run(ip, PROC_STAT_CMD)
    if rc != 0 or not out.strip():
        return None
    return parse_cpu_line(out)


def run_one(region, itype, ip):
    ensure_stress_ng(ip)
    before = sample_cpu(ip)
    ssh_run(ip, f"nproc > /tmp/nproc.txt")
    rc, nproc_out, _ = ssh_run(ip, "cat /tmp/nproc.txt")
    vcpus = int(nproc_out.strip() or "2")

    # Launch load in the background on the instance, wait LOAD_SECONDS
    # locally, then sample again -- this approximates "during load"
    # without needing a second SSH session.
    ssh_run(ip, f"nohup stress-ng --cpu {vcpus} --timeout {LOAD_SECONDS}s >/tmp/stress.log 2>&1 &", timeout=20)
    time.sleep(LOAD_SECONDS / 2)
    during = sample_cpu(ip)
    time.sleep(LOAD_SECONDS / 2 + 5)
    after = sample_cpu(ip)

    def pct(a, b):
        if a is None or b is None or b["total"] == a["total"]:
            return None
        dt = b["total"] - a["total"]
        return {
            "busy_pct": 100.0 * (b["busy"] - a["busy"]) / dt,
            "steal_pct": 100.0 * (b["steal"] - a["steal"]) / dt,
        }

    return {
        "region": region,
        "instance_type": itype,
        "public_ip": ip,
        "vcpus": vcpus,
        "load_seconds": LOAD_SECONDS,
        "idle_to_during": pct(before, during),
        "during_to_after": pct(during, after),
        "idle_to_after": pct(before, after),
    }


def main():
    outputs = terraform_outputs()
    jobs = []
    for region, by_type in outputs.items():
        for itype, ip in by_type.items():
            jobs.append((region, itype, ip))

    print(f"Plan: {len(jobs)} (region, type) pairs, {LOAD_SECONDS}s synthetic load each, run in parallel.")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        futures = {ex.submit(run_one, r, t, ip): (r, t) for r, t, ip in jobs}
        for fut in concurrent.futures.as_completed(futures):
            region, itype = futures[fut]
            try:
                res = fut.result()
                print(f"  {region}/{itype}: steal(during)={res['idle_to_during']}, steal(after)={res['during_to_after']}")
                results.append(res)
            except Exception as e:
                print(f"  {region}/{itype}: FAILED ({e})", file=sys.stderr)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "flex_launch_test_results.json"
    out_path.write_text(json.dumps({"load_seconds": LOAD_SECONDS, "results": results}, indent=2))
    print(f"\nWrote {out_path}")
    print(
        "Pass/fail against the pre-registered 5% steal threshold (Decision 43) "
        "is a manual read of this file, not decided by this script."
    )


if __name__ == "__main__":
    main()
