#!/usr/bin/env python3
"""Decision 49/40/53's campaign orchestrator -- runs ON the control
instance, under systemd (campaign_run.service, same directory), never on
the operator's own machine.

Writes directly into the same relative path layout the repository itself
uses (Decision 53) -- not a separate ad-hoc scheme -- so campaign_pull.sh's
rsync is a straight mirror and the sha256 manifest's paths match the
repo's own paths one-to-one:

  v8/latency/experiment{1,2,3} - {Classic,PQC,Hybrid}/{server}/{scenario}/
    runs/run{NN}.json           (window, server, client, instance_type)
    runs/run{NN}.calls.jsonl    (per-call record, one file per execution)
    run00_warmup.json           (separate, never mixed into runs/)
    server/run{NN}_gateway.log, run{NN}_cpu.jsonl, run{NN}.pcap.gz
    client/run{NN}_cpu.jsonl, run{NN}_ping.json, run{NN}.pcap.gz
    median_metrics.json, report.md   (written by local post-processing, NOT here)

  v8/latency/_campaign-control/
    schedule.json                (copy of what this run actually used)
    windows/{server}/window{NN}.json   (seed, profile_order, scenario_rotation)
    orchestrator.log

Scenarios, per server (Decision 53 -- L0 added to every installation, not
just the original 4-scenario sa-east-1 chain): `sa-east-1`: L0, L123,
L219, L325. `us-east-1`: L0, L14. `ap-northeast-1`: L0, L30. 8 scenarios
total, 30 runs/profile/scenario, 720 executions campaign-wide.

Implements: parameterized window scheduling (real UTC timestamps),
automatic resume (each execution's own JSON is the resume marker),
per-server scenario rotation across the 3 windows (Decision 40/53 --
registered per server, since each server now has its own scenario set),
randomized profile order per window (seed logged), the pre-block checks
(negotiated key-exchange group, image ID, disk space), and the
renewable safety timer.

Decision 56 -- round-robin within each profile block (supersedes
Decision 40's "run all 30 of scenario A, then all 30 of scenario B"
ordering, kept there, not deleted): within a block, executions alternate
across that server's scenarios one at a time (run 1 of every scenario,
then run 2 of every scenario, ...), not scenario-by-scenario. Rationale:
spreads any time-dependent drift within a block (network weather,
however small, over the block's own ~minutes-to-an-hour span) evenly
across every scenario in that block, instead of letting one scenario
systematically land in the block's "early" minutes and another in its
"late" minutes, every single window -- a confound round-robin removes
by construction. Per-scenario warmup still happens once per scenario
per block (unchanged count), but now upfront, before the round-robin
loop starts, not interleaved into it. Each scenario's client-side proxy
must stay active for the WHOLE block, not just its own contiguous
run-span -- `start_block_proxies()`/`stop_block_proxies()` below are the
seams for that lifecycle (implemented for both executors, Decision 60/67).

Effect on total time: none -- same number of runs, same number of
profile switches (9/window, unchanged by Decision 40's math), same
per-run durations; only the ORDER changes. Effect on orchestrator
complexity: real, not cosmetic -- every one of a block's scenario
proxies must be started before round-robin begins and kept alive
(tracked, health-checked) for the entire block instead of one at a
time, and the run loop itself inverts (scenario the inner loop, run
index the outer one).

Decision 60: `run_one_execution()`/`run_warmup()`/`start_block_proxies()`/
`stop_block_proxies()` are implemented via an Executor abstraction
(`LocalExecutor`, against the real local docker-compose stack;
`SSHExecutor`, real SSH/SCP transport, against a real remote server/
client -- see their own classes below). `LocalExecutor.run_one_execution()`
calls `latency_automation.py`'s own `run_once_timed_with_retry()` directly
(the monotonic clock, discarded retry-attempt time excluded, a
whole-execution retry marked and recorded -- never reimplemented) and
writes every artifact Decision 53's tree specifies for one execution:
`runs/run{NN}.json`, `runs/run{NN}.calls.jsonl`, the server/client
`_gateway.log`/`_cpu.jsonl`/`.pcap.gz`/`_ping.json` files. `run_warmup()`
reuses the same function for latency_automation.py's own single-warmup-
run convention (not Decision 4's separate 5-flow container-settling,
which is a different, server-side, profile-switch-time concern --
flagged explicitly in `run_warmup()`'s own docstring so the two are
never conflated). `SSHExecutor`'s live SSH execution was validated
against a real 3-container local rehearsal (sshd, not AWS) before being
trusted against real instances -- fabricating untested SSH calls would
not have been "prepared"; testing them for real, once there was
something real to test against, is.
"""
import gzip
import json
import os
import random
import re
import shlex
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Decision 60: lets this file import thesis/scripts' own modules
# (latency_automation.py, opin_flow.py) directly -- LocalExecutor calls
# their functions in-process; it does not reimplement them.
THESIS_SCRIPTS_DIR = Path(__file__).resolve().parents[4] / "scripts"
if str(THESIS_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(THESIS_SCRIPTS_DIR))

CONFIG_PATH = Path("/home/ec2-user/campaign_schedule.json")
INVENTORY_PATH = Path("/home/ec2-user/inventory.json")
CAMPAIGN_KEY = "/home/ec2-user/.ssh/campaign_key"
DATA_ROOT = Path("/home/ec2-user/campaign-data")  # mirrors the repo's v8/ subtree, Decision 53
# A.4: the operator-readable status file -- main() writes to this on every
# state transition (started/running/aborted/completed) so "is it alive and
# doing what" doesn't require tailing journalctl. Overridable via env var
# so the local rehearsal (item 11) doesn't need root on /home/ec2-user.
STATUS_FILE_PATH = Path(os.environ.get("CAMPAIGN_STATUS_FILE", "/home/ec2-user/campaign-status.json"))


def write_status(state, detail=""):
    """A.4: best-effort -- a status-file write failure must never mask
    or replace the real error that's actually aborting the process, so
    this only prints a warning on failure, never raises."""
    try:
        STATUS_FILE_PATH.write_text(json.dumps({
            "state": state,
            "detail": detail,
            "pid": os.getpid(),
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        }, indent=2))
    except OSError as e:
        print(f"WARNING: could not write status file {STATUS_FILE_PATH}: {e}", file=sys.stderr)


# Pilot item 3 (this turn): a real pilot can run far longer than
# planned while real AWS debugging happens (Decision 83's own turn:
# ~1-2h estimated, ~9h actual) -- this budget makes that impossible to
# miss and, critically, never lets the orchestrator decide on its own
# to keep going OR to tear anything down. Overridable; the default (3h)
# is deliberately short, matching this pilot's own ~1-2h estimate plus
# margin, not the full campaign's much longer one.
PILOT_TIME_BUDGET_HOURS = float(os.environ.get("PILOT_TIME_BUDGET_HOURS", "3"))
TIME_BUDGET_OVERRIDE_MARKER = Path("/home/ec2-user/campaign_time_budget_override")
TIME_BUDGET_POLL_SECONDS = 60
_CAMPAIGN_START_UTC = None  # set once, at the top of main()


def check_time_budget():
    """Pilot item 3 (this turn): called once per profile block (the
    start of run_window()'s own per-profile loop), BEFORE
    start_block_proxies() spends any more real time/money. Past
    PILOT_TIME_BUDGET_HOURS, this BLOCKS (not exits -- exiting would
    just re-enter the same wait on systemd's own restart, burning the
    unit's restart budget for no reason) until the operator creates
    TIME_BUDGET_OVERRIDE_MARKER on control -- the orchestrator never
    destroys anything itself and never silently keeps spending past
    the budget unattended. Logs a reminder every
    TIME_BUDGET_POLL_SECONDS so this is visible in journalctl, not a
    silent hang indistinguishable from one."""
    if _CAMPAIGN_START_UTC is None:
        return  # defensive -- main() always sets this before run_window() is ever called
    elapsed_hours = (datetime.now(timezone.utc) - _CAMPAIGN_START_UTC).total_seconds() / 3600
    if elapsed_hours < PILOT_TIME_BUDGET_HOURS:
        return
    write_status("paused_time_budget", f"elapsed_hours={elapsed_hours:.2f} budget_hours={PILOT_TIME_BUDGET_HOURS}")
    print(f"=== PILOT_TIME_BUDGET_HOURS ({PILOT_TIME_BUDGET_HOURS}h) EXCEEDED after {elapsed_hours:.2f}h ===")
    print(f"    This orchestrator will NOT continue on its own and will NOT destroy anything itself.")
    print(f"    Decide: to KEEP GOING, create {TIME_BUDGET_OVERRIDE_MARKER} on this control instance "
          f"(e.g. 'touch {TIME_BUDGET_OVERRIDE_MARKER}'). To TEAR DOWN instead, run campaign_down.sh "
          f"from the operator's own machine -- PILOT_RUNBOOK.md's own criterion: past budget, destroy "
          f"and reassess, don't debug with the meter still running.")
    while not TIME_BUDGET_OVERRIDE_MARKER.exists():
        time.sleep(TIME_BUDGET_POLL_SECONDS)
        elapsed_hours = (datetime.now(timezone.utc) - _CAMPAIGN_START_UTC).total_seconds() / 3600
        print(f"    ... still waiting for {TIME_BUDGET_OVERRIDE_MARKER} (elapsed {elapsed_hours:.2f}h)")
    print(f"    {TIME_BUDGET_OVERRIDE_MARKER} found -- continuing.")
    TIME_BUDGET_OVERRIDE_MARKER.unlink()


# Overridable via env var for a short rehearsal schedule (item 4) --
# the real campaign always uses the default 10/3 (30 runs/profile/
# scenario total, Decision 53).
RUNS_PER_WINDOW = int(os.environ.get("CAMPAIGN_RUNS_PER_WINDOW", "10"))
WINDOWS_PER_CAMPAIGN = int(os.environ.get("CAMPAIGN_WINDOWS_PER_CAMPAIGN", "3"))
PROFILES = ["classic", "pqc", "hybrid"]
# Item 2 (order/warm-up turn, thesis/results/v8/DECISIONS.md): a freshly
# launched EC2 instance's own cold-start (cold EBS reads, cold OS page
# cache, cold interpreter/JIT caches, a not-yet-settled network stack) is
# a broader disturbance than a container recreation on an already-warm
# instance -- Decision 4 (switch_crypto_profile.py) found THAT settling
# window closed by about the 7th-8th execution, ~2 minutes of wall-clock.
# This instance-level warmup runs once per installation, before the
# campaign's first block, for a fixed TIME instead of a fixed count --
# 180s is a 50% margin over Decision 4's own ~2-minute figure for a
# strictly lighter disturbance, not a number picked after looking at
# results from this fixed-time warmup itself.
INSTANCE_WARMUP_SECONDS = int(os.environ.get("CAMPAIGN_INSTANCE_WARMUP_SECONDS", "180"))
INSTANCE_WARMUP_PROFILE = "classic"
PROFILE_TO_EXPERIMENT_DIR = {"classic": "experiment1 - Classic", "pqc": "experiment2 - PQC", "hybrid": "experiment3 - Hybrid"}
SAFETY_TIMER_RENEW_HOURS = 48  # Decision 49 -- must match the Terraform default
# Decision -- raised from 128 to 256 (2026-10-22 investigation, DECISIONS.md):
# 128 bytes cannot capture the ClientHello's own SNI extension (measured at
# TLS-payload offset ~97, needing ~101 bytes of payload -- 128 only yields
# ~62 after real Ethernet/IP/TCP(+options) header overhead); 256 recovers
# it exactly, confirmed against a real local capture. Measured real cost of
# this change: +47.6% pcap size for one connection's own capture (44,774 ->
# 66,098 bytes) -- see this file's own README/storage-estimate update for
# the extrapolated campaign-wide effect.
TCPDUMP_SNAPLEN_BYTES = 256

# Decision 40/53 -- fixed, pre-registered per server per window (NOT
# re-derived at runtime, so a restart can't silently pick a different
# rotation). Note on the 2-scenario installations (us-east-1,
# ap-northeast-1): a 2-item list only has 2 distinct orderings, so
# "rotated" (window 3) can't be a third, distinct pattern the way it is
# for sa-east-1's 4-item list -- window 3 repeats window 1's order here,
# registered explicitly rather than silently reusing it.
SCENARIO_ROTATION = {
    "sa-east-1": {
        1: ["L0", "L123", "L219", "L325"],   # increasing by RTT
        2: ["L325", "L219", "L123", "L0"],   # decreasing by RTT
        3: ["L219", "L325", "L0", "L123"],   # rotated (cyclic shift of window 1 by 2)
    },
    "us-east-1": {
        1: ["L0", "L14"],
        2: ["L14", "L0"],
        3: ["L0", "L14"],  # only 2 orderings exist for a 2-item list -- repeats window 1, not a distinct 3rd pattern
    },
    "ap-northeast-1": {
        1: ["L0", "L30"],
        2: ["L30", "L0"],
        3: ["L0", "L30"],  # same note as us-east-1
    },
}


def load_config():
    if not CONFIG_PATH.exists():
        sys.exit(f"Missing {CONFIG_PATH} -- campaign_up.sh should have written this.")
    return json.loads(CONFIG_PATH.read_text())


def load_inventory():
    raw = json.loads(INVENTORY_PATH.read_text())
    return raw["value"] if "value" in raw else raw


def pick_gateway_ip(inventory, installation, scenario_key):
    """Pilot item 2 (this turn): the IP a CLIENT uses to reach the
    server's own gateway (REMOTE_GATEWAY_HOST, the client-side
    reference ping, and the pre-flight connectivity check below) is
    NOT always the server's public IP -- a co-located client (L0, any
    region) cannot reach the server via its public IP at all
    (Decision 83's real finding: same-VPC traffic to another
    instance's public/Elastic IP hairpins through the Internet
    Gateway, which rewrites the source to the sender's OWN public IP
    by the time it reaches the destination's security group -- the
    server's own SG only ever allows a co-located client's PRIVATE
    IP, confirmed statically in terraform/main.tf's own
    gateway_ingress_cidrs for every one of the 3 server regions).
    SSHExecutor's own `_server_ip()` stays unchanged and correct for
    every place CONTROL reaches the server directly (the profile
    switch, docker logs, tcpdump, cpu/mem sampling, scp pcap pull) --
    control's own SSH security group rule already uses the right IP
    for THAT relationship, a separate one from a client's own path to
    the gateway.

    A module-level function, not a method, so both SSHExecutor
    (_server_gateway_ip()) and the pre-flight connectivity check
    (verify_gateway_connectivity(), run before any executor exists)
    share one real implementation.

    Fails loudly, never with a silent default, if `colocated` is
    missing from this scenario's inventory entry, or if the IP it
    calls for (private when colocated, public otherwise) isn't
    present -- this project's standing style of never fabricating a
    guarantee the data doesn't actually back."""
    client = inventory["clients"][scenario_key]
    if "colocated" not in client:
        raise RuntimeError(
            f"{scenario_key}: inventory has no 'colocated' field -- refusing to "
            f"guess which of the server's IPs to use (Decision 83)."
        )
    server = inventory["servers"][installation]
    ip_field = "private_ip" if client["colocated"] else "public_ip"
    ip_value = server.get(ip_field)
    if not ip_value:
        raise RuntimeError(
            f"{installation}: server inventory has no usable '{ip_field}' -- "
            f"needed because {scenario_key}'s own colocated={client['colocated']!r}."
        )
    return ip_value


def all_server_client_ips(inventory):
    ips = []
    for name, data in inventory.get("servers", {}).items():
        ips.append((f"server:{name}", data["public_ip"]))
    for name, data in inventory.get("clients", {}).items():
        ips.append((f"client:{name}", data["public_ip"]))
    return ips


def all_instance_ips(inventory):
    """Item 2 (this turn): every instance INCLUDING control -- unlike
    all_server_client_ips() (used only for safety-timer renewal, which
    deliberately excludes control, Decision 49). Environment recording
    has no such exclusion: control is a real instance with its own AMI/
    kernel/instance-type/AZ worth recording too."""
    return [("control", inventory["control"]["public_ip"])] + all_server_client_ips(inventory)


# Item 2 (this turn): queried from INSIDE each instance via its own
# IMDSv2 (not Terraform state/output, which this never reads) -- the
# ground truth of what's actually running, since pinning the AMI in
# terraform/main.tf's own locals doesn't, by itself, prove a given real
# instance booted from it (a stale instance predating a pin change,
# launched manually outside Terraform, etc.). Built as a self-contained
# python3 script (same `python3 -c` + shlex.quote pattern as the CPU/mem
# sampler) so the JSON is assembled by json.dumps(), never hand-built
# string concatenation of command output that could contain a quote.
_ENVIRONMENT_PROBE_SCRIPT = (
    "import json, subprocess, urllib.request\n"
    "def sh(cmd):\n"
    "    try:\n"
    "        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10).stdout.strip()\n"
    "    except Exception as e:\n"
    "        return f'ERROR: {e}'\n"
    "try:\n"
    "    token_req = urllib.request.Request('http://169.254.169.254/latest/api/token', method='PUT',\n"
    "                                        headers={'X-aws-ec2-metadata-token-ttl-seconds': '60'})\n"
    "    token = urllib.request.urlopen(token_req, timeout=5).read().decode()\n"
    "    def imds(path):\n"
    "        req = urllib.request.Request('http://169.254.169.254/latest/meta-data/' + path,\n"
    "                                      headers={'X-aws-ec2-metadata-token': token})\n"
    "        return urllib.request.urlopen(req, timeout=5).read().decode()\n"
    "    ami_id = imds('ami-id')\n"
    "    instance_type = imds('instance-type')\n"
    "    az_id = imds('placement/availability-zone-id')\n"
    "except Exception as e:\n"
    "    ami_id = instance_type = az_id = f'ERROR: {e}'\n"
    "print(json.dumps({\n"
    "    'ami_id': ami_id,\n"
    "    'instance_type': instance_type,\n"
    "    'availability_zone_id': az_id,\n"
    "    'kernel': sh('uname -r'),\n"
    "    'docker_version': sh('docker --version'),\n"
    "    'chrony_version': sh('chronyd -v 2>&1 || rpm -q chrony 2>&1'),\n"
    "    'rsync_version': sh('rsync --version | head -1'),\n"
    "}))\n"
)


def verify_ready_marker(inventory, ssh_port=22, ssh_key_path=None):
    """Software-inventory audit (this turn): the user-data script
    (install_common_packages.sh) now writes /var/lib/mockopin-ready as
    its own LAST line, only reachable if every earlier line succeeded
    (the script's own `set -euo pipefail`, line 2). This is the
    orchestrator's own check of that signal, run BEFORE anything else
    in main() -- record_environment()/renew_safety_timers() calling
    into an instance that never finished booting would fail with a
    confusing SSH-level or command-level error; this instead aborts
    loudly, immediately, naming every instance missing the marker (not
    just the first one found), so a half-booted fleet is caught before
    any real work is attempted on it. Control is checked as a local
    file (this process already runs ON control); server/client are
    checked over SSH."""
    ssh_key_path = ssh_key_path or CAMPAIGN_KEY
    missing = []
    local_marker = Path("/var/lib/mockopin-ready")
    if not local_marker.exists():
        missing.append("control (local)")
    for label, ip in all_server_client_ips(inventory):
        r = subprocess.run(
            ["ssh", "-i", ssh_key_path, "-p", str(ssh_port), "-o", "StrictHostKeyChecking=no",
             "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=15", "-o", "BatchMode=yes",
             f"ec2-user@{ip}", "cat /var/lib/mockopin-ready"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            missing.append(f"{label} ({ip})")
        else:
            print(f"Ready: {label} ({ip}) -- user-data finished at {r.stdout.strip()}")
    if missing:
        sys.exit(
            "FATAL: /var/lib/mockopin-ready missing on: " + ", ".join(missing) +
            " -- user-data did not finish successfully there (set -euo pipefail means a failure anywhere in "
            "install_common_packages.sh prevents this file from ever being written). Refusing to start the "
            "campaign against a half-booted fleet. Investigate directly (SSH in, check cloud-init's own log) "
            "before retrying."
        )
    print(f"Ready: control (local) -- user-data finished at {local_marker.read_text().strip()}")


GATEWAY_CONNECTIVITY_TIMEOUT_SECONDS = 5


def verify_gateway_connectivity(inventory, ssh_port=22, ssh_key_path=None,
                                 timeout_seconds=GATEWAY_CONNECTIVITY_TIMEOUT_SECONDS):
    """Pilot item 2 (this turn): confirms, before spending any real
    time on settling/execution, that every client can actually reach
    the server's own gateway on port 443 using the SAME IP
    (pick_gateway_ip(), colocated-aware) this file will hand it as
    REMOTE_GATEWAY_HOST -- exactly the check that would have caught
    Decision 83's own real finding (a co-located client's public-IP
    path silently hanging) before a single real AWS minute was spent
    on it. PILOT_RUNBOOK.md's own step 4 only ever tested from L325
    (the public-IP case); this covers every client, including every
    co-located L0, automatically.

    Explicit failure, never a hang: a short TCP connect timeout
    (`timeout_seconds`, default 5s) inside the remote probe itself
    (bash's own `/dev/tcp`, no extra tooling needed), wrapped in a
    generous SSH-level timeout -- the same "abort loudly, not
    silently" standard every other pre-flight check in this file
    already uses. Called from main() right after verify_ready_marker(),
    BEFORE the first profile switch ever runs -- which means the
    gateway (mtls) isn't listening yet at this point in a real run
    (PILOT_RUNBOOK.md's own standing distinction, unchanged by this
    check): a fast "Connection refused" is the EXPECTED, GOOD outcome
    here (the network path and security group are open, nothing is
    listening yet), while an actual timeout (the full
    `timeout_seconds` elapses with no refusal) means the path itself
    is broken. Found live, the first real run of this exact check:
    treating every nonzero exit as FAIL (ignoring this distinction)
    made it fail loudly on the normal, expected pre-stack state every
    single time -- fixed by checking the probe's own output for an
    explicit refusal, not just its exit code."""
    ssh_key_path = ssh_key_path or CAMPAIGN_KEY
    rows = []
    failed = False
    for scenario_key, client in inventory.get("clients", {}).items():
        installation = scenario_key.split("@", 1)[1]
        client_ip = client["public_ip"]
        try:
            gateway_ip = pick_gateway_ip(inventory, installation, scenario_key)
        except RuntimeError as e:
            rows.append((scenario_key, "N/A", "FAIL", f"inventory error: {e}"))
            failed = True
            continue
        probe_cmd = f"timeout {timeout_seconds} bash -c 'echo > /dev/tcp/{gateway_ip}/443' 2>&1"
        t0 = time.monotonic()
        try:
            r = subprocess.run(
                ["ssh", "-i", ssh_key_path, "-p", str(ssh_port), "-o", "StrictHostKeyChecking=no",
                 "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=15", "-o", "BatchMode=yes",
                 f"ec2-user@{client_ip}", probe_cmd],
                capture_output=True, text=True, timeout=timeout_seconds + 20,
            )
            connected = r.returncode == 0
            refused = "Connection refused" in (r.stdout + r.stderr)
            ok = connected or refused
            outcome = "connected" if connected else ("refused -- path open, nothing listening yet" if refused else "TIMED OUT")
        except subprocess.TimeoutExpired:
            ok = False
            outcome = "TIMED OUT (SSH-level)"
        elapsed = time.monotonic() - t0
        rows.append((scenario_key, gateway_ip, "OK" if ok else "FAIL", f"{elapsed:.2f}s ({outcome})"))
        if not ok:
            failed = True

    print(f"{'client':<20} {'gateway_ip':<16} {'result':<6} {'time'}")
    for scenario_key, gateway_ip, result, elapsed in rows:
        print(f"{scenario_key:<20} {gateway_ip:<16} {result:<6} {elapsed}")
    if failed:
        sys.exit(
            "FATAL: at least one client cannot reach the server's own gateway on port 443 "
            "using the IP it would actually be given (see table above) -- investigate "
            "directly before spending any real time on settling/execution."
        )


def record_environment(inventory, ssh_port=22, ssh_key_path=None):
    """Item 2 (this turn): records, once per instance, at campaign
    start, into v8/latency/_campaign-control/environment/<instance>.json
    -- AMI ID, kernel, docker/chrony/rsync versions, instance type, and
    availability-zone ID. This is the audit trail a later check compares
    against terraform/main.tf's own pinned_ami_x86_by_region/
    pinned_ami_arm64_sa_east_1 map, to catch drift between "what was
    pinned" and "what actually booted." A probe failure on one instance
    is reported but does not abort the campaign (environment recording
    is observational, not a precondition any execution depends on)."""
    ssh_key_path = ssh_key_path or CAMPAIGN_KEY
    env_dir = DATA_ROOT / "v8" / "latency" / "_campaign-control" / "environment"
    env_dir.mkdir(parents=True, exist_ok=True)
    remote_cmd = f"python3 -c {shlex.quote(_ENVIRONMENT_PROBE_SCRIPT)}"
    for label, ip in all_instance_ips(inventory):
        safe_label = label.replace("/", "_").replace("@", "_at_").replace(":", "_")
        try:
            r = subprocess.run(
                ["ssh", "-i", ssh_key_path, "-p", str(ssh_port), "-o", "StrictHostKeyChecking=no",
                 "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=15",
                 "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=3",
                 "-o", "BatchMode=yes", f"ec2-user@{ip}", remote_cmd],
                capture_output=True, text=True, timeout=30,
            )
        except subprocess.TimeoutExpired:
            print(f"WARNING: environment probe for {label} ({ip}) timed out -- skipping", file=sys.stderr)
            continue
        if r.returncode != 0:
            print(f"WARNING: could not record environment for {label} ({ip}): {r.stderr.strip()}", file=sys.stderr)
            continue
        try:
            info = json.loads(r.stdout)
        except ValueError:
            print(f"WARNING: environment probe for {label} ({ip}) did not return valid JSON: {r.stdout!r}",
                  file=sys.stderr)
            continue
        info["recorded_at_utc"] = datetime.now(timezone.utc).isoformat()
        info["label"] = label
        info["ip"] = ip
        (env_dir / f"{safe_label}.json").write_text(json.dumps(info, indent=2))
        print(f"Recorded environment for {label} ({ip}): ami={info.get('ami_id')}, "
              f"type={info.get('instance_type')}, az={info.get('availability_zone_id')}")


def renew_safety_timers(inventory, ssh_port=22, ssh_key_path=None):
    """Decision 49: the orchestrator renews every server/client's
    safety-timer deadline -- the control instance is deliberately
    exempt (no timer to renew there). Called at startup and before each
    window so a multi-day campaign never trips the default 48h timer
    while legitimately still running.

    `ssh_port`/`ssh_key_path` default to the real campaign's own
    values (22/`CAMPAIGN_KEY`) -- `main()` passes through the same
    `CAMPAIGN_SSH_PORT`/`CAMPAIGN_SSH_KEY_PATH` overrides it gives
    `SSHExecutor`, so this function's own SSH call (separate from
    SSHExecutor's, since it runs before any executor's block loop)
    doesn't fall out of sync with the rest of the real-vs-rehearsal
    targeting."""
    ssh_key_path = ssh_key_path or CAMPAIGN_KEY
    deadline_cmd = (
        f"sudo mkdir -p /etc/mockopin-campaign && "
        f"date -d '+{SAFETY_TIMER_RENEW_HOURS} hours' +%s | sudo tee /etc/mockopin-campaign/deadline >/dev/null"
    )
    for label, ip in all_server_client_ips(inventory):
        r = subprocess.run(
            ["ssh", "-i", ssh_key_path, "-p", str(ssh_port), "-o", "StrictHostKeyChecking=no",
             "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=15",
             "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=3",
             "-o", "BatchMode=yes", f"ec2-user@{ip}", deadline_cmd],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            print(f"WARNING: could not renew safety timer on {label} ({ip}): {r.stderr.strip()}", file=sys.stderr)
        else:
            print(f"Renewed safety timer on {label} ({ip}): +{SAFETY_TIMER_RENEW_HOURS}h")


SINGLE_INSTANCE_LOCK_PATH = "/tmp/mockopin-campaign-run.lock"


class SingleInstanceLock:
    """Decision 64: only one campaign_run.py process may run at a time
    on the control instance -- a second launch (operator error, a
    leftover process from a previous session, systemd restarting it
    while an old one is still alive) must fail loudly on startup, not
    silently run two orchestrators against the same servers. Uses
    `fcntl.flock` (Linux-only, which is all this ever runs on in
    practice -- the control instance). On a non-Linux host (this
    project's own Windows dev machine, where `fcntl` doesn't exist at
    all), falls back to a no-op with a clear warning rather than
    crashing on import -- so the local test below can still run, with
    this guarantee explicitly NOT exercised there."""
    def __init__(self, path=SINGLE_INSTANCE_LOCK_PATH):
        self.path = path
        self._fh = None

    def __enter__(self):
        try:
            import fcntl
        except ImportError:
            print(f"WARNING: fcntl not available on this platform -- SingleInstanceLock is a no-op here "
                  f"(expected on this project's Windows dev machine; real on Linux).", file=sys.stderr)
            return self
        self._fh = open(self.path, "w")
        try:
            fcntl.flock(self._fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._fh.close()
            raise RuntimeError(
                f"Another campaign_run.py is already running (lock held on {self.path}) -- "
                f"refusing to start a second orchestrator instance (Decision 64)."
            )
        return self

    def __exit__(self, *exc):
        if self._fh is not None:
            import fcntl
            fcntl.flock(self._fh, fcntl.LOCK_UN)
            self._fh.close()


def server_flock_wrap(remote_cmd, lock_path="/tmp/mockopin-server.lock"):
    """Decision 64: wraps a remote command so the SERVER-side flock is
    held for exactly the command's duration -- `flock` is a real binary
    (util-linux, present on Amazon Linux 2023 by default), not a Python
    mechanism, so this works regardless of which process on the server
    side ends up running the wrapped command (relevant for SSHExecutor,
    where each execution is its own separate SSH invocation, not one
    long-lived process that could hold an in-memory lock the way
    LocalExecutor's `_SERVER_LOCKS` threading.Lock does).

    A.10: this flock covers ONLY the profile switch (the command passed
    in here, always the `switch_crypto_profile.py` invocation) -- it is
    NOT what makes "one execution at a time" true in general. That
    guarantee has two layers: (1) the orchestrator's own sequential
    control flow (no threading in run_window()'s round-robin loop --
    one execution is started, awaited, and written to disk before the
    next begins) and (2) `_SERVER_LOCKS`, an in-memory per-installation
    lock that is defense-in-depth against a future concurrent-windows
    change reintroducing an overlap (see its own docstring above).
    Individual `run_one_execution()` calls are NOT flock-wrapped on the
    server side at all -- only the profile switch is, because that is
    the one server-side operation that mutates shared state (the
    running containers) and could plausibly race with a stray manual
    `switch_crypto_profile.py` invocation or a second orchestrator
    instance SSHing in. A single execution's own request against an
    already-switched, already-stable server has nothing server-side to
    race on.

    A.3: `remote_cmd` is a single shell command STRING (shell syntax --
    `&&`, env-var-assignment prefixes -- is meant to be interpreted by
    the remote shell, so it is not flattened into argv tokens here); any
    VARIABLE piece inside it must already have been through
    `shlex.quote()` by the caller before this function sees it. This
    function itself never uses `repr()` -- `shlex.quote()` on the whole
    command is what's needed to pass it safely as `flock -c`'s single
    argument (handles embedded quotes/spaces/$ correctly, unlike
    `!r}`, which breaks the instant `remote_cmd` itself contains a
    single quote -- exactly the python3 -c bug SSHExecutor had)."""
    # Software-inventory audit (this turn): absolute path, not a bare
    # `flock` -- a plain `ssh host "cmd"` (no -t, no login shell) is
    # NOT guaranteed to source /etc/profile's own non-root PATH
    # addition of /usr/sbin and /usr/local/sbin (where flock, ping, ss,
    # tcpdump actually live on AL2023's MINIMAL AMI, confirmed via a
    # real amazonlinux:2023 container) -- untested on a real EC2 sshd
    # session, so hardcoded rather than assumed. Same reasoning applies
    # to every other bare remote command this file issues for a tool
    # that lives in /usr/sbin.
    return f"/usr/bin/flock -n {lock_path} -c {shlex.quote(remote_cmd)}"


# ---------------------------------------------------------------------------
# B.12: negotiated key-exchange group verification, correlated by TCP
# connection (remoteAddr) rather than compared as one flat set across the
# whole block -- see verify_negotiated_groups()'s own docstring for the
# full rule. Curve-ID strings below are tls.CurveID.String() values as
# logged by mock_mtls/main.go's slog.JSONHandler (confirmed live during
# this project's own testing, not guessed).
# ---------------------------------------------------------------------------
_HANDSHAKE_COMPLETE_MSG = "mTLS handshake complete"
_CARVEOUT_MSG = "GetConfigForClient: internal-caller classical carve-out applied"
_INTERNAL_CARVEOUT_SNI = "matls-api.local"
_INTERNAL_CARVEOUT_EXPECTED_CURVE = "CurveP256"
_CLIENT_EXPECTED_CURVE = {
    "classic": "CurveP384",
    "pqc": "MLKEM1024",
    "hybrid": "SecP384r1MLKEM1024",
}
_CORRELATION_WINDOW_SECONDS = 5.0


def _parse_gateway_log_lines(log_text):
    """B.12: parses `docker logs -t ...`'s line format -- an RFC3339Nano
    timestamp, one space, then the gateway's own slog JSON object -- into
    (timestamp, dict) pairs. Silently skips any line that isn't both (a
    container-runtime line, a multi-line stack trace, etc.) -- never
    raises on a malformed line, never fabricates a missing field."""
    entries = []
    for line in log_text.splitlines():
        line = line.strip()
        if not line:
            continue
        ts_str, _, rest = line.partition(" ")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        try:
            obj = json.loads(rest)
        except ValueError:
            continue
        entries.append((ts, obj))
    return entries


def verify_negotiated_groups(log_text, expected_client_curve, window_seconds=_CORRELATION_WINDOW_SECONDS):
    """B.12: separates the TWO coexisting TLS channels (v7 Decision 15)
    by correlating each "mTLS handshake complete" line (has curveID, no
    SNI) against the "GetConfigForClient: internal-caller classical
    carve-out applied" line (has SNI, no curveID) sharing the SAME
    remoteAddr -- an EXACT string match is correct here, not fuzzy,
    because both lines read remoteAddr off the identical net.Conn (same
    TCP connection, same host:port string) -- within a short time window
    (guards only against a reused ephemeral port across two distinct,
    sequential connections being miscorrelated; it is not compensating
    for any fuzziness in the remoteAddr match itself).

    Rule (this turn's spec):
      - A handshake whose remoteAddr has a paired carve-out line is the
        INTERNAL (AS->RS) channel: its curveID must be exactly
        _INTERNAL_CARVEOUT_EXPECTED_CURVE ("CurveP256"). Any other value
        is a regression of the SNI carve-out itself, not a settling
        fluke, and is reported as a problem.
      - A handshake with NO paired carve-out line is the CLIENT-FACING
        channel: its curveID must be exactly `expected_client_curve`
        (the profile's own group). Any divergence is reported as a
        problem.
      - A carve-out line with NO paired handshake-complete line within
        the window is an UNPAIRED FAILURE (the ClientHello was parsed
        but the connection never completed/reached StateActive, or
        correlation genuinely failed) -- reported as a problem.

    Never raises or aborts anything itself -- callers (the settling
    check, the warmup check, and this function's own unit test) decide
    what to do with a non-empty `problems` list. Returns:
      {"client_curves": [...], "internal_curves": [...],
       "problems": [...], "ok": bool}
    """
    entries = _parse_gateway_log_lines(log_text)
    handshakes = [(ts, obj) for ts, obj in entries if obj.get("msg") == _HANDSHAKE_COMPLETE_MSG]
    carveouts = [(ts, obj) for ts, obj in entries if obj.get("msg") == _CARVEOUT_MSG]

    carveouts_by_addr = {}
    for ts, obj in carveouts:
        carveouts_by_addr.setdefault(obj.get("remoteAddr"), []).append((ts, obj))

    problems = []
    client_curves = set()
    internal_curves = set()
    matched_carveout_keys = set()

    for ts, hs in handshakes:
        addr = hs.get("remoteAddr")
        curve = hs.get("curveID")
        pair = None
        for i, (cts, cobj) in enumerate(carveouts_by_addr.get(addr, [])):
            if (addr, i) in matched_carveout_keys:
                continue
            if abs((cts - ts).total_seconds()) <= window_seconds:
                pair = (cts, cobj)
                matched_carveout_keys.add((addr, i))
                break
        if pair is not None:
            internal_curves.add(curve)
            if curve != _INTERNAL_CARVEOUT_EXPECTED_CURVE:
                problems.append(
                    f"INTERNAL channel (remoteAddr={addr}, SNI={pair[1].get('sni')}) negotiated "
                    f"{curve!r}, expected {_INTERNAL_CARVEOUT_EXPECTED_CURVE!r} -- regression of the "
                    f"matls-api.local SNI carve-out (Decision 15)."
                )
        else:
            client_curves.add(curve)
            if curve != expected_client_curve:
                problems.append(
                    f"CLIENT-FACING channel (remoteAddr={addr}) negotiated {curve!r}, "
                    f"expected {expected_client_curve!r} for this profile."
                )

    for addr, pairs in carveouts_by_addr.items():
        for i, (cts, cobj) in enumerate(pairs):
            if (addr, i) not in matched_carveout_keys:
                problems.append(
                    f"UNPAIRED carve-out (remoteAddr={addr}, SNI={cobj.get('sni')}) -- no matching "
                    f"'{_HANDSHAKE_COMPLETE_MSG}' line within {window_seconds}s; treated as a failure."
                )

    return {
        "client_curves": sorted(client_curves),
        "internal_curves": sorted(internal_curves),
        "problems": problems,
        "ok": not problems,
    }


def _default_route_interface():
    """A.7: the real default-route network interface, read straight from
    /proc/net/route (destination 00000000) -- not `eth0` hardcoded, and
    not even a call out to the `ip` binary (which isn't installed in
    every minimal image, e.g. netshoot's busybox-based `ip` is present
    but a bare Alpine's often isn't) -- /proc/net/route is a kernel
    interface, present on every real Linux host unconditionally. Returns
    None (never fabricates "eth0") on any non-Linux host or if no
    default route is configured."""
    try:
        with open("/proc/net/route") as f:
            lines = f.readlines()[1:]
    except FileNotFoundError:
        return None
    for line in lines:
        fields = line.split()
        if len(fields) >= 2 and fields[1] == "00000000":
            return fields[0]
    return None


def _parse_chrony_tracking_text(text):
    """A.8: parses `chronyc tracking`'s own "System time" line --
    positive means the host this text came from is ahead of its sync
    reference. Pure-text parser, reused both by `_chrony_tracking_offset()`
    (runs chronyc locally) and by `SSHExecutor.run_one_execution()`
    (parses chronyc's output already fetched over SSH from a real
    remote instance) -- one parser, two sources, not two
    implementations. Returns None (never a fabricated 0.0) if `text` is
    None/empty or doesn't match (chronyc not installed, chronyd not
    tracking yet)."""
    if not text:
        return None
    m = re.search(r"System time\s*:\s*([\d.]+)\s*seconds\s*(fast|slow)", text)
    if not m:
        return None
    offset = float(m.group(1))
    return -offset if m.group(2) == "slow" else offset


def _chrony_tracking_offset():
    """A.8: this host's own clock offset from ITS sync reference (NTP /
    Amazon Time Sync) -- the correct building block for a CLIENT-vs-
    SERVER drift measurement (each real instance reports its own
    offset-from-truth; the difference between the two is the client/
    server drift -- see `client_server_clock_drift_seconds`), unlike
    the old container-vs-host reading this replaces, which compared
    two clocks that are never meaningfully out of sync in the first
    place (same kernel clock, Docker containers don't have their own
    hardware clock). Returns None if chronyc isn't installed locally."""
    try:
        r = subprocess.run(["chronyc", "tracking"], capture_output=True, text=True, timeout=5)
    except FileNotFoundError:
        return None
    if r.returncode != 0:
        return None
    return _parse_chrony_tracking_text(r.stdout)


def _sample_cpu_mem_steal():
    """A.9: one point-in-time sample of /proc/stat's cpu line (steal
    time included -- see the module's own long-standing explanation of
    why this has to be /proc/stat, never `docker stats`) AND
    /proc/meminfo (new this turn -- the old sampler read /proc/stat
    only). Returns None for either half independently on a non-Linux
    host, never a fabricated value; always returns a dict with a
    timestamp so repeated samples (via _PeriodicSampler below) can be
    told apart."""
    sample = {"sampled_at_utc": datetime.now(timezone.utc).isoformat()}
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        fields = [int(x) for x in line.split()[1:]]
        while len(fields) < 8:
            fields.append(0)
        user, nice, system, idle, iowait, irq, softirq, steal = fields[:8]
        sample["cpu"] = {"total": sum(fields), "steal": steal, "idle": idle}
    except FileNotFoundError:
        sample["cpu"] = None
    try:
        meminfo = {}
        with open("/proc/meminfo") as f:
            for line in f:
                key, _, rest = line.partition(":")
                meminfo[key.strip()] = rest.strip()
        sample["mem"] = {k: meminfo.get(k) for k in ("MemTotal", "MemFree", "MemAvailable")}
    except FileNotFoundError:
        sample["mem"] = None
    return sample


class _PeriodicSampler:
    """A.9: samples CPU(+steal)/memory on an interval THROUGHOUT an
    execution via a background thread, not just at 3 discrete
    before/during/after points -- `start()` takes one sample
    immediately, then one every `interval_seconds` until `stop()`, which
    takes one final sample and returns the full list. A plain daemon
    thread, not a subprocess -- each sample is a handful of open/read/
    close syscalls, cheap enough that the sampling itself is not a
    meaningful confound next to what it's measuring."""
    def __init__(self, interval_seconds=1.0):
        self.interval_seconds = interval_seconds
        self.samples = []
        self._stop_event = threading.Event()
        self._thread = None

    def _run(self):
        while not self._stop_event.is_set():
            self._stop_event.wait(self.interval_seconds)
            if not self._stop_event.is_set():
                self.samples.append(_sample_cpu_mem_steal())

    def start(self):
        self.samples.append(_sample_cpu_mem_steal())
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self.samples.append(_sample_cpu_mem_steal())
        return self.samples


def wait_until(iso_timestamp):
    """Blocks until the given ISO-8601 UTC timestamp. A no-op (returns
    immediately) if that time has already passed -- resuming after a
    restart doesn't wait for a window that's already open."""
    target = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    while True:
        now = datetime.now(timezone.utc)
        remaining = (target - now).total_seconds()
        if remaining <= 0:
            return
        sleep_for = min(remaining, 300)  # wake at least every 5min to stay responsive
        print(f"Waiting for window start {iso_timestamp} -- {remaining:.0f}s remaining...")
        time.sleep(sleep_for)


def scenario_dir(installation, scenario, profile):
    exp_dir = PROFILE_TO_EXPERIMENT_DIR[profile]
    return DATA_ROOT / "v8" / "latency" / exp_dir / installation / scenario


def already_done(scenario_path, run_index):
    return (scenario_path / "runs" / f"run{run_index:02d}.json").exists()


def warmup_done(scenario_path, window):
    # One warmup per (scenario, profile, window) block -- Decision 53
    # keeps it separate from runs/, never mixed into the run numbering.
    return (scenario_path / f"run00_warmup_window{window:02d}.json").exists()


# Item 1 (this turn): the gateway image -- the one whose ID actually
# matters for the campaign's crypto correctness (auth/mockapi/
# mongo_seed's own IDs aren't gated here; deliver_images.sh delivers
# and checks all 4, this pre-flight is specifically about what's
# running the TLS handshake). Matches deliver_images.sh's own IMAGES
# list entry for mtls.
GATEWAY_IMAGE_NAME = "insurance-server-lambdas-mtls:latest"
DELIVERED_IMAGES_MANIFEST_PATH = Path("/home/ec2-user/delivered_images_manifest.json")


def pre_block_checks(executor, installation, profile):
    """Decision 49/53: at the start of every profile block, verify the
    loaded gateway image's ID against deliver_images.sh's own delivery
    manifest, take an INFORMATIONAL look at the negotiated key-exchange
    group, and check disk space -- before spending any run on a block
    that's already wrong.

    Item 1 (this turn) wires both the image_id and negotiated_group
    fields for real (were literal "NOT YET AVAILABLE" placeholders):
      - image_id: `docker image inspect` ON THE SERVER, compared
        against `/home/ec2-user/delivered_images_manifest.json`
        (written by deliver_images.sh after its own per-server ID
        comparison succeeds) -- a MISMATCH ABORTS THE BLOCK (a
        different image is running than what delivery actually
        shipped). Missing manifest (deliver_images.sh never run, or
        LocalExecutor) is reported, not fatal -- there's nothing to
        compare against yet.
      - negotiated_group: a short recent gateway-log slice through
        `verify_negotiated_groups()` -- REPORTED ONLY, never aborts
        here. This runs BEFORE this block's own profile switch, so
        "wrong curve" at this point is routinely just the PREVIOUS
        block's own correct state, not a real problem; the real,
        abort-worthy check is `start_block_proxies()`'s own settling
        verification (B.12), which runs AFTER the switch, for real.
    """
    checks = {}
    df = subprocess.run(["df", "-h", "/"], capture_output=True, text=True)
    checks["disk_space_df_output"] = df.stdout.strip()

    if not isinstance(executor, SSHExecutor):
        checks["image_id"] = "N/A -- local executor, no delivery manifest to compare against"
        checks["negotiated_group"] = "N/A -- local executor; see B.12's own check inside start_block_proxies()"
        return checks

    server_ip = executor._server_ip(installation)
    try:
        manifest = json.loads(DELIVERED_IMAGES_MANIFEST_PATH.read_text())
    except FileNotFoundError:
        manifest = None

    if manifest is None:
        checks["image_id"] = f"N/A -- no delivery manifest at {DELIVERED_IMAGES_MANIFEST_PATH} (deliver_images.sh not yet run)"
    else:
        expected_id = manifest.get(GATEWAY_IMAGE_NAME)
        inspect_cmd = f"docker image inspect -f {shlex.quote('{{.Id}}')} {shlex.quote(GATEWAY_IMAGE_NAME)}"
        actual_id = executor._run_or_print(
            f"[{installation}/{profile}] pre-flight: inspect loaded gateway image",
            executor._ssh_cmd(server_ip, inspect_cmd),
        )
        actual_id = (actual_id or "").strip() or None
        checks["image_id"] = {"expected": expected_id, "actual": actual_id}
        if expected_id and actual_id and expected_id != actual_id:
            raise RuntimeError(
                f"[{installation}/{profile}] pre-flight: loaded gateway image ID ({actual_id}) does not "
                f"match the delivery manifest ({expected_id}) -- a different image is running than what "
                f"was actually delivered. Aborting before spending any run on it."
            )

    gateway_log = executor._run_tolerant(
        f"[{installation}/{profile}] pre-flight: recent gateway log (informational only)",
        executor._ssh_cmd(server_ip, "docker logs -t --since 2m insurance-server-lambdas-mtls-1"),
    )
    if gateway_log:
        checks["negotiated_group"] = verify_negotiated_groups(gateway_log, _CLIENT_EXPECTED_CURVE[profile])
    else:
        checks["negotiated_group"] = "N/A -- no recent gateway log yet (first block, or server unreachable)"
    return checks


# Decision 60: never two executions on the same server at once. Today's
# control flow is fully sequential (no threading anywhere in main()/
# run_window()), so this is already true by construction -- the lock is
# defense-in-depth against a future change (e.g. running installations'
# windows concurrently) silently reintroducing an overlap. One lock per
# installation (= per physical server), not global -- different servers
# running concurrently is fine and intended.
_SERVER_LOCKS = {name: threading.Lock() for name in SCENARIO_ROTATION}


SSH_TIMEOUT_SECONDS = 30
# Pilot item 2 (this turn): found live -- the "switch profile on server"
# SSH call runs switch_crypto_profile.py's ENTIRE switch() end to end
# (two fixed sleeps totaling 18s, up to MTLS_READY_TIMEOUT_SECONDS=30s
# waiting for the gateway, psql's own now-real healthcheck wait before
# mockapi even starts, a psql CHECKPOINT health probe, then
# SETTLING_WARMUP_RUNS=5 discarded full two-flow executions) inside the
# SAME 30s budget every short status/docker command also uses -- always
# too short for this one call (switch_crypto_profile.py's own docstring
# already says "~1 minute per switch"), not something this pilot's own
# fixes made worse so much as finally exercised for real against actual
# AWS network/boot timing. A generous, explicit ceiling for this one
# call only -- every other `_run_or_print()` call keeps the original,
# tighter SSH_TIMEOUT_SECONDS, so a genuinely dead connection on a quick
# command is still caught quickly.
SWITCH_PROFILE_TIMEOUT_SECONDS = 240
# Pilot item 2 (this turn): found live -- starting the client's own
# detached tls_kem_proxy calls opin_flow._wait_for_tls_kem_proxy_ready_detached(),
# which has its OWN internal readiness-poll budget of 30s -- wrapping
# that in the SAME 30s SSH_TIMEOUT_SECONDS leaves zero margin for the
# SSH connection itself, process startup, or `docker rm -f` of a stale
# container, so this timed out for real the first time the network fix
# above let it actually reach this far. Generous but bounded -- well
# under SWITCH_PROFILE_TIMEOUT_SECONDS, since this call does no
# settling runs of its own.
PROXY_START_TIMEOUT_SECONDS = 90
# Pilot item 2 (this turn): found live, mid-pilot, first time this exact
# call ran a hybrid-profile execution cross-region (L325) -- a real
# campaign_client_runner.py execution (insurance + person flows, several
# HTTP round trips each, under pqc/hybrid crypto and real inter-region
# RTT) can legitimately take more than the default 30s SSH_TIMEOUT_SECONDS,
# which killed it mid-flight ("SSH command timed out after 30s") even
# though the remote process was still genuinely working, not hung. This
# timeout governs only how long the ORCHESTRATOR waits for the SSH
# command to return -- it does not touch campaign_client_runner.py's own
# T_fluxo measurement (a separate, monotonic clock on the remote side),
# so raising it does not affect what gets measured, only whether a
# legitimately slower real execution is given time to finish. Applied to
# every call that runs campaign_client_runner.py for real: settling,
# warmup, and the measured execution itself.
EXECUTION_TIMEOUT_SECONDS = 120
SETTLING_RUNS = 5  # mirrors switch_crypto_profile.py's SETTLING_WARMUP_RUNS / Decision 62's local-executor count

# Pilot acceptance criterion 7: T_fluxo with vs. without tcpdump. This
# toggle exists ONLY for the pilot's own A/B test -- never the full
# campaign's default, which is always capture-on (unset ==
# CAMPAIGN_TCPDUMP_AB_TEST is falsy below). When explicitly turned on,
# capture alternates ONE BY ONE across global run indices (odd ON, even
# OFF) rather than an arbitrary subset, so the with/without comparison
# is interleaved across the whole run instead of confounded by a block
# of consecutive skipped (or captured) runs. A failure to actually
# start capture on an ENABLED run still aborts the block exactly as
# before (_verify_tcpdump_started()'s own abort path below is
# untouched by this toggle) -- alternating only decides, per run,
# whether capture is attempted at all, never whether a failed attempt
# is tolerated.
CAMPAIGN_TCPDUMP_AB_TEST = os.environ.get("CAMPAIGN_TCPDUMP_AB_TEST", "").strip().lower() in ("1", "true", "yes")


def _tcpdump_enabled_for_run(run_index):
    """True (capture) unless the pilot's own A/B test is explicitly
    enabled, in which case odd/even GLOBAL run indices alternate --
    run 1 always captures, so the very first execution of any cell
    still has a pcap baseline available regardless of the toggle."""
    if not CAMPAIGN_TCPDUMP_AB_TEST:
        return True
    return run_index % 2 == 1


def _REMOTE_CLIENT_ENV(profile, server_ip):
    """Software-inventory audit (this turn): every remote
    `campaign_client_runner.py`/`of.start_tls_kem_proxy(...)` invocation
    on the client now ALSO sets TLS_KEM_PROXY_USE_PRECOMPILED=1 -- the
    default (unset) path is `go run .` against
    thesis/scripts/tls_kem_proxy/'s own SOURCE directory, which no
    mechanism ever shipped to a real remote client (deliver_images.sh
    only ever distributed to servers until this same turn's fix). The
    precompiled image (`mockopin/tls_kem_proxy:precompiled`) IS now
    delivered to every client by `deliver_images.sh`'s own
    `CLIENT_IMAGES` list -- this env var is what makes the client
    actually use it instead of a live build with no source to build
    from."""
    return {"CRYPTO_PROFILE": profile, "REMOTE_GATEWAY_HOST": server_ip, "TLS_KEM_PROXY_USE_PRECOMPILED": "1"}


class SSHExecutor:
    """Real-AWS executor -- control instance SSHing into the client
    (to run campaign_client_runner.py) and into the server (profile
    switches, gateway logs, CPU/steal, tcpdump).

    Real SSH/SCP transport, wired this turn: `_run_or_print()` calls
    `subprocess.run(["ssh", ...], timeout=SSH_TIMEOUT_SECONDS)` for
    real when `dry_run=False` -- a nonzero exit or a timeout both raise
    `RuntimeError` (never silently swallowed), exactly matching A.4's
    "abort loudly" requirement for the real-mode path as a whole.
    `--dry-run` is unaffected: it still only ever prints, same command
    construction either way (Decision 62's original point). Validated
    against a real 3-container local rehearsal (B.11) running the real
    orchestrator end to end, not just against SSHExecutor in
    isolation -- see DECISIONS.md for what that rehearsal does and does
    not cover.

    `ssh_port`/`ssh_key_path` are overridable (default 22 and
    `CAMPAIGN_KEY`, matching the real campaign's own control-instance
    layout) so the rehearsal can point this SAME, unmodified class at
    its own sshd containers (port 2222) without any code forking
    between "real" and "rehearsal" paths."""
    def __init__(self, inventory, dry_run=False, ssh_port=22, ssh_key_path=None):
        self.inventory = inventory
        self.dry_run = dry_run
        self.ssh_port = ssh_port
        self.ssh_key_path = ssh_key_path or CAMPAIGN_KEY

    def _client_ip(self, scenario_key):
        return self.inventory["clients"][scenario_key]["public_ip"]

    def _server_ip(self, installation):
        return self.inventory["servers"][installation]["public_ip"]

    def _server_gateway_ip(self, installation, scenario_key):
        """See module-level pick_gateway_ip() for the real logic and
        its own full docstring -- this just supplies self.inventory,
        so every SSHExecutor call site keeps its existing shape."""
        return pick_gateway_ip(self.inventory, installation, scenario_key)

    def _ssh_cmd(self, ip, remote_cmd):
        """A.3: `remote_cmd` is a single shell command STRING, built by
        the caller with shell syntax (&&, $(...), env-var prefixes) left
        as literal, correct shell syntax, and every VARIABLE piece
        (profile name, path, IP, label) already run through
        `shlex.quote()` -- never `repr()`/hand-nested quotes. This
        function hands `remote_cmd` to ssh as ONE argv element (ssh
        joins its trailing args and runs them via the remote shell --
        no local shell is involved here, so no extra quoting layer is
        needed around `remote_cmd` itself). Returns an argv LIST, ready
        for `subprocess.run()` with no `shell=True` on either end.

        Uses `self.ssh_key_path` (an ABSOLUTE path, `CAMPAIGN_KEY` by
        default) rather than a `~/.ssh/...`-relative one passed as a
        bare argv element -- no local shell is involved to expand that
        `~` here, and while OpenSSH's own `-i` option handling does
        tilde-expand internally, there is no reason to depend on that
        when an absolute path is just as correct and is what this same
        file already assumes everywhere else (CONFIG_PATH, DATA_ROOT,
        A.6's `/home/ec2-user/...` fix).

        `ServerAliveInterval=10`/`ServerAliveCountMax=3` (item 4, this
        turn): without these, a connection that goes quiet (the remote
        command is still running but producing no output) under real
        packet loss/a dead path can sit unnoticed by the SSH CLIENT
        until the underlying TCP connection itself times out, which can
        take far longer than `ConnectTimeout` (that option only governs
        the initial handshake, not an already-established session).
        With them, ssh sends a keepalive every 10s and gives up after 3
        unanswered ones (30s) -- generous next to even this project's
        own worst-case simulated RTT (320ms) or the real inter-region
        latency v8 measures, but short enough that a genuinely dead
        connection is detected and reported (nonzero exit, caught by
        `_run_or_print`) rather than hanging indefinitely."""
        return ["ssh", "-i", self.ssh_key_path, "-p", str(self.ssh_port),
                "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
                "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=3",
                f"ec2-user@{ip}", remote_cmd]

    def _scp_pull(self, ip, remote_path, local_path):
        """Pulls one remote file back to `local_path` -- used for the
        binary pcaps (A.5); text artifacts are read directly over SSH's
        own stdout instead (one round trip fewer). Same real-vs-dry-run
        split and the same exit-code/timeout handling as `_run_or_print`
        -- not a second, separately-tested code path."""
        cmd = ["scp", "-i", self.ssh_key_path, "-P", str(self.ssh_port),
               "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
               "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
               "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=3",
               f"ec2-user@{ip}:{remote_path}", str(local_path)]
        if self.dry_run:
            print(f"[DRY-RUN] scp pull {ip}:{remote_path} -> {local_path}: {shlex.join(cmd)}")
            return
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=SSH_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"scp pull {ip}:{remote_path} timed out after {SSH_TIMEOUT_SECONDS}s") from e
        if r.returncode != 0:
            raise RuntimeError(f"scp pull {ip}:{remote_path} -> {local_path} failed (exit {r.returncode}): {r.stderr}")

    def _run_or_print(self, label, cmd, timeout_seconds=SSH_TIMEOUT_SECONDS):
        if self.dry_run:
            print(f"[DRY-RUN] {label}: {shlex.join(cmd)}")
            return None
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"[{label}] SSH command timed out after {timeout_seconds}s") from e
        if r.returncode != 0:
            raise RuntimeError(
                f"[{label}] SSH command failed (exit {r.returncode}):\n"
                f"  cmd: {shlex.join(cmd)}\n  stdout: {r.stdout.strip()}\n  stderr: {r.stderr.strip()}"
            )
        return r.stdout

    def _run_tolerant(self, label, cmd):
        """For AUXILIARY measurements only (reference ping, chronyc
        tracking) -- found live, this turn's real-mode rehearsal run:
        `chronyc tracking` failing (chronyd not running/not synced yet)
        went through the same `_run_or_print` as every core action and
        aborted the WHOLE execution, which is wrong for data that's
        supplementary (A.8's clock-drift field already tolerates
        `None` by design -- LocalExecutor's own `_chrony_tracking_offset()`
        returns None rather than raising). Core actions (profile
        switch, proxy start, tcpdump start+liveness, the execution
        itself, gateway log/CPU fetch) stay on `_run_or_print` and keep
        aborting loudly (A.4) -- only ping/chronyc are reclassified."""
        try:
            return self._run_or_print(label, cmd)
        except RuntimeError as e:
            print(f"  WARNING: {e} -- treated as auxiliary data, continuing without it", file=sys.stderr)
            return None

    def _verify_tcpdump_started(self, ip, label, pid_path):
        """A.6/Decision 63: a backgrounded `nohup tcpdump ... &` inside
        `sudo setsid sh -c '...'` can fail (bad interface, tcpdump
        missing) WITHOUT the outer SSH command itself returning
        nonzero -- the `&` means the outer command's own exit code
        reflects `setsid`/`sh -c` launching successfully, not whether
        the backgrounded tcpdump is actually still alive a moment
        later. This follow-up command is what actually catches that:
        `test -s pidfile` (non-empty) `&& kill -0 $(cat pidfile)` (that
        PID is alive) -- either failing makes THIS command exit
        nonzero, which `_run_or_print` turns into a loud abort (A.4),
        not a silently-missing capture. `sudo kill -0` (not a bare
        `kill -0`) -- found live, this turn's real-mode rehearsal run:
        tcpdump itself runs as root (started via `sudo setsid ...`,
        A.6), so a signal-0 existence check from the unprivileged
        ec2-user session this SSH command runs as fails with "Operation
        not permitted" even when the process is alive and well; `sudo`
        here checks the SAME thing `sudo setsid` started."""
        check_cmd = f"sleep 1; test -s {pid_path} && sudo kill -0 $(cat {pid_path})"
        self._run_or_print(f"{label}: verify tcpdump actually started", self._ssh_cmd(ip, check_cmd))

    @staticmethod
    def _env_prefix(env):
        """A.3: KEY=VALUE shell-assignment prefix, each VALUE through
        shlex.quote -- the assignment syntax itself is meant to be
        interpreted by the remote shell, only the values are untrusted/
        variable."""
        return " ".join(f"{k}={shlex.quote(str(v))}" for k, v in env.items())

    @staticmethod
    def _iface_detect_sh(var_name="IFACE"):
        """A.7: detects the default-route interface from /proc/net/route
        (destination field 00000000) INLINE in the remote shell -- not a
        separate round trip (none of this class's remote reads are wired
        to live execution yet, Decision 60/62), and not a hardcoded
        `eth0` -- the `eth0` here is only a last-resort fallback if
        detection itself yields nothing (a genuinely interface-less
        instance, which would be a real problem either way), never the
        primary source of truth. The detected name is also written to
        `/home/ec2-user/{label}.{side}.iface` so the collection step
        (A.5) can fold it into the run's own JSON instead of assuming
        it."""
        return (f'{var_name}=$(awk \'$2 == "00000000" {{print $1; exit}}\' /proc/net/route 2>/dev/null); '
                f'{var_name}=${{{var_name}:-eth0}}')

    def _tcpdump_start_cmd(self, label, side, interface_var="IFACE"):
        """A.6: fixes the `sudo tcpdump ... & echo $!` PID bug -- that
        captures sudo's own PID, not tcpdump's, because the backgrounding
        happens OUTSIDE the sudo'd process. Here, `setsid sh -c '...'` is
        what sudo elevates, and the backgrounding (`nohup ... &`) plus
        `echo $!` both happen INSIDE that sudo'd shell, so `$!` is
        tcpdump's own PID. `setsid` detaches the whole thing from this
        SSH session's controlling terminal so it survives the session
        closing (A.6's "ciclo de vida"); stdout/stderr are redirected to
        a log file (never left attached to the dying SSH pipe).

        B.11's local rehearsal caught two real bugs in earlier versions
        of this function. First: `pcap_path`/`pid_path`/`log_path` used
        `~/...` and were passed through `shlex.join()`/`shlex.quote()`
        -- quoting a `~`-prefixed token defeats the shell's own tilde
        expansion (it only fires on an UNQUOTED leading `~`), so the
        remote shell tried to create a file literally named `~`, which
        doesn't exist ("nonexistent directory"). Switching to `$HOME`
        and dropping shlex.quote/join on these self-constructed,
        fixed-template paths (they contain no untrusted content -- no
        spaces, no shell metacharacters, built only from `label`/`side`,
        both from a small fixed set -- so there is nothing to escape,
        and quoting them only breaks the expansion they rely on) fixed
        that. Second, found by the SAME rehearsal run: `$HOME` INSIDE
        `sudo setsid sh -c '...'` resolves to ROOT's home, not the
        invoking user's -- `sudo` resets `$HOME` by default (no
        `--preserve-env`/`sudoers env_keep`), so the pid/log/pcap files
        landed in `/root/...`, invisible to the next (non-sudo) SSH
        command reading `$HOME/...` as ec2-user. Fixed by using the
        LITERAL path `/home/ec2-user` instead of `$HOME` -- consistent
        with every other hardcoded `/home/ec2-user/...` path this file
        already assumes (CONFIG_PATH, CAMPAIGN_KEY, DATA_ROOT), not a
        new assumption, and immune to sudo's env reset since it's not a
        variable at all.

        Third bug the rehearsal caught, same root cause as the second:
        `$IFACE` itself also can't cross the `sudo` boundary as a
        variable reference -- `IFACE=...` in the login shell is a
        plain, unexported local variable, and even exporting it
        wouldn't survive `sudo`'s default env_reset. Single-quoting
        `inner` (the first fix's approach) made this worse: it froze
        `$IFACE` as a literal, unexpanded string all the way into the
        inner shell, which then ran `tcpdump -i $IFACE` with NO
        variable of that name set there at all -- empty expansion,
        tcpdump misparsed `-s` as `-i`'s argument ("-s: No such device
        exists"). Fixed by DOUBLE-quoting `inner` instead of single-
        quoting it: a double-quoted string IS expanded by the OUTER
        (login) shell before sudo ever runs, so `$IFACE` resolves to
        the real, already-detected interface name THERE, crossing the
        sudo boundary as a plain literal word -- exactly like the
        `/home/ec2-user` fix above. The one thing that must NOT be
        expanded by the outer shell is `$!` (tcpdump's own PID, only
        meaningful once the INNER sh -c backgrounds it) -- escaped as
        `\\$!`, which double quotes turn back into a literal `$!` for
        the inner shell to evaluate for real. All three bugs (and the
        fixes) were found/confirmed by actually running these commands
        over real SSH against real sshd containers (B.11's rehearsal),
        not by inspection."""
        home = "/home/ec2-user"
        pcap_path = f"{home}/{label}.{side}.pcap"
        pid_path = f"{home}/{label}.{side}.tcpdump.pid"
        log_path = f"{home}/{label}.{side}.tcpdump.log"
        inner = f"nohup /usr/sbin/tcpdump -i ${interface_var} -s {TCPDUMP_SNAPLEN_BYTES} port 443 -w {pcap_path} > {log_path} 2>&1 & echo \\$! > {pid_path}"
        iface_detect = self._iface_detect_sh(interface_var)
        remote_cmd = f'{iface_detect}; echo ${interface_var} > {home}/{label}.{side}.iface; sudo setsid sh -c "{inner}"'
        return remote_cmd, pid_path, log_path, pcap_path

    @staticmethod
    def _tcpdump_stop_cmd(pid_path):
        """Kills the real tcpdump PID captured by _tcpdump_start_cmd --
        `2>/dev/null; true` so a PID that's already gone (process died
        on its own) doesn't make the SSH command itself look failed.
        `pid_path` is NOT shlex.quote()'d here -- it's already a
        trusted, fixed-template literal path (see _tcpdump_start_cmd's
        own docstring), no expansion involved any more after the
        $HOME->literal-path fix, so quoting would add nothing."""
        return f"sudo kill $(cat {pid_path}) 2>/dev/null; sleep 1; true"

    def _cpu_mem_sampler_start_cmd(self, label, side):
        """Pilot acceptance criterion 4 (this turn): `steal` is a DELTA
        between two `/proc/stat` readings, not a single counter value
        -- a single before/after-less snapshot (what this class did
        until now) cannot compute it at all, only `LocalExecutor`'s own
        A.9 periodic sampler could. Fixed by backgrounding a small
        Python loop (via `python3 -c`, same safe-quoting approach as
        the proxy-start command, A.3) that appends one JSON line per
        second to a file for the execution's whole duration -- no
        `sudo` needed (`/proc/stat`/`/proc/meminfo` are world-readable),
        so none of tcpdump's sudo-PID-capture pitfalls (A.6) apply
        here; `echo $!` directly captures the backgrounded loop's own
        PID."""
        home = "/home/ec2-user"
        out_path = f"{home}/{label}.{side}.cpu_mem.jsonl"
        pid_path = f"{home}/{label}.{side}.cpu_mem.pid"
        sampler_script = (
            "import time, json\n"
            "while True:\n"
            "    with open('/proc/stat') as f:\n"
            "        stat_line = f.readline().strip()\n"
            "    with open('/proc/meminfo') as f:\n"
            "        meminfo_raw = f.read()\n"
            "    print(json.dumps({'sampled_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),"
            " 'proc_stat_line': stat_line, 'proc_meminfo_raw': meminfo_raw}), flush=True)\n"
            "    time.sleep(1)\n"
        )
        inner = f"nohup python3 -c {shlex.quote(sampler_script)} > {out_path} 2>&1 & echo $! > {pid_path}"
        remote_cmd = f"setsid sh -c {shlex.quote(inner)}"
        return remote_cmd, pid_path, out_path

    @staticmethod
    def _cpu_mem_sampler_stop_cmd(pid_path):
        """Same `kill`-a-real-PID pattern as `_tcpdump_stop_cmd` -- no
        `sudo` needed here either, since the sampler never used it."""
        return f"kill $(cat {pid_path}) 2>/dev/null; sleep 1; true"

    def start_block_proxies(self, installation, profile, scenarios, window):
        server_ip = self._server_ip(installation)
        # Decision 64/A.10: flock-wrapped -- the profile switch touches
        # the whole server's stack and must never overlap with anything
        # else running against this same server. This is the ONLY
        # server-side action that is flock-wrapped (see
        # server_flock_wrap()'s own docstring, A.10, for why individual
        # executions below are not).
        # Audit (v8 pilot, this turn): found live -- switch_crypto_profile.py's
        # OWN internal settling step (Decision 4, inside switch()) runs
        # ON THE SERVER and starts its own LOCAL tls_kem_proxy (same
        # single-host assumption that script was originally written
        # under, before the real split-host v8 topology existed).
        # TLS_KEM_PROXY_USE_PRECOMPILED=1 was already set for the
        # CLIENT side (_REMOTE_CLIENT_ENV()) but never for this one --
        # opin_flow.start_tls_kem_proxy() defaulted to `go run .`
        # against Go source that was never delivered here either
        # ("go.mod file not found"). deliver_images.sh now also ships
        # CLIENT_IMAGES to "servers"; this sets the matching env var so
        # the server actually uses what's delivered.
        switch_cmd = (
            f"cd insurance-server-lambdas && CRYPTO_PROFILE={shlex.quote(profile)} "
            f"TLS_KEM_PROXY_USE_PRECOMPILED=1 "
            f"python3 ../thesis/scripts/switch_crypto_profile.py {shlex.quote(profile)}"
        )
        self._run_or_print(
            f"[{installation}/w{window}] switch profile on server",
            self._ssh_cmd(server_ip, server_flock_wrap(switch_cmd)),
            timeout_seconds=SWITCH_PROFILE_TIMEOUT_SECONDS,
        )
        # A.6: the proxy now starts detached (docker run -d, via
        # opin_flow.start_tls_kem_proxy(..., detached=True)) -- a
        # service in the Decision 6/60 sense: its lifecycle is the
        # container's own, independent of this SSH session, torn down
        # explicitly by stop_block_proxies() below via `docker stop`,
        # not by this process exiting.
        for scenario in scenarios:
            client_ip = self._client_ip(f"{scenario}@{installation}")
            gateway_ip = self._server_gateway_ip(installation, f"{scenario}@{installation}")
            py_code = "import opin_flow as of; of.start_tls_kem_proxy(%s, detached=True)" % json.dumps(profile)
            remote_argv = ["python3", "-c", py_code]
            remote_cmd = f"cd ~/thesis/scripts && {self._env_prefix(_REMOTE_CLIENT_ENV(profile, gateway_ip))} {shlex.join(remote_argv)}"
            self._run_or_print(
                f"[{installation}/{scenario}/w{window}] start client proxy (detached)",
                self._ssh_cmd(client_ip, remote_cmd),
                timeout_seconds=PROXY_START_TIMEOUT_SECONDS,
            )

        # Settling (wired for real this turn, mirroring LocalExecutor's
        # own Decision 62 sequence): SETTLING_RUNS executions against
        # the server, then the SAME correlated negotiated-group check
        # (B.12) LocalExecutor uses, aborting the block on a real
        # mismatch. Real HTTP traffic needs A client -- the FIRST
        # scenario's is used; settling verifies the SERVER's negotiated
        # group, which doesn't depend on which scenario's client
        # happens to generate the traffic (a deliberate choice, not an
        # oversight -- there is no "settling's own" client in the real
        # 8-scenario topology, unlike LocalExecutor's single-host test).
        settling_scenario = scenarios[0]
        settling_client_ip = self._client_ip(f"{settling_scenario}@{installation}")
        settling_gateway_ip = self._server_gateway_ip(installation, f"{settling_scenario}@{installation}")
        settle_start = datetime.now(timezone.utc)
        for i in range(1, SETTLING_RUNS + 1):
            remote_argv = ["python3", "campaign_client_runner.py", "--label", f"w{window:02d}_settling{i}"]
            remote_cmd = f"cd ~/thesis/scripts && {self._env_prefix(_REMOTE_CLIENT_ENV(profile, settling_gateway_ip))} {shlex.join(remote_argv)}"
            stdout = self._run_or_print(
                f"[{installation}/{profile}/w{window}] settling run {i}/{SETTLING_RUNS}",
                self._ssh_cmd(settling_client_ip, remote_cmd),
                timeout_seconds=EXECUTION_TIMEOUT_SECONDS,
            )
            if stdout is not None:  # real mode -- dry-run has nothing to parse
                result = json.loads(stdout)
                if result.get("call_count", 0) <= 0:
                    raise RuntimeError(
                        f"[{installation}/{profile}/w{window}] settling run {i}/{SETTLING_RUNS} on "
                        f"{settling_client_ip} completed but call_count={result.get('call_count')} -- not verified"
                    )
        settle_end = datetime.now(timezone.utc)

        gateway_log = self._run_or_print(
            f"[{installation}/{profile}/w{window}] fetch settling gateway log",
            self._ssh_cmd(server_ip, f"docker logs -t --since {settle_start.isoformat()} "
                                      f"--until {settle_end.isoformat()} insurance-server-lambdas-mtls-1"),
        )
        if gateway_log is not None:  # real mode
            verification = verify_negotiated_groups(gateway_log, _CLIENT_EXPECTED_CURVE[profile])
            print(f"  [{installation}/{profile}/w{window}] settling: client curves={verification['client_curves']}, "
                  f"internal curves={verification['internal_curves']}")
            if not verification["ok"]:
                raise RuntimeError(
                    f"[{installation}/{profile}/w{window}] settling: negotiated-group verification "
                    f"FAILED (B.12):\n  " + "\n  ".join(verification["problems"])
                )

    def stop_block_proxies(self, installation, profile, scenarios, window):
        # A.6: no Popen to join on this side (the proxy was started
        # detached, via opin_flow.start_tls_kem_proxy(..., detached=True)
        # -- a plain container name, see its docstring) -- tearing it
        # down is `docker stop` + `docker rm -f` by its fixed name
        # (TLS_KEM_PROXY_CONTAINER_NAME = "tls_kem_proxy_run"), the exact
        # same two calls stop_tls_kem_proxy() itself makes for the str
        # case, reused here as the literal remote command rather than
        # re-importing opin_flow just to read one constant.
        for scenario in scenarios:
            client_ip = self._client_ip(f"{scenario}@{installation}")
            remote_cmd = "docker stop tls_kem_proxy_run 2>/dev/null; docker rm -f tls_kem_proxy_run 2>/dev/null; true"
            self._run_or_print(
                f"[{installation}/{scenario}/w{window}] stop client proxy (docker stop)",
                self._ssh_cmd(client_ip, remote_cmd),
            )

    def run_warmup(self, installation, scenario, profile, window, scenario_path):
        """A.2/B.12 extended to the real path: verifies the negotiated
        group during warmup too, same as LocalExecutor's own
        run_warmup() -- a mismatch aborts before any of the block's
        real runs are spent on it."""
        client_ip = self._client_ip(f"{scenario}@{installation}")
        server_ip = self._server_ip(installation)
        gateway_ip = self._server_gateway_ip(installation, f"{scenario}@{installation}")
        since_dt = datetime.now(timezone.utc)
        remote_argv = ["python3", "campaign_client_runner.py", "--label", f"w{window:02d}_warmup"]
        remote_cmd = f"cd ~/thesis/scripts && {self._env_prefix(_REMOTE_CLIENT_ENV(profile, gateway_ip))} {shlex.join(remote_argv)}"
        stdout = self._run_or_print(
            f"[{installation}/{scenario}/w{window}] warmup",
            self._ssh_cmd(client_ip, remote_cmd),
            timeout_seconds=EXECUTION_TIMEOUT_SECONDS,
        )
        until_dt = datetime.now(timezone.utc)
        if stdout is None:
            return  # dry-run

        result = json.loads(stdout)
        if result.get("call_count", 0) <= 0:
            raise RuntimeError(f"[{installation}/{scenario}/{profile}/w{window}] warmup completed but "
                                f"call_count={result.get('call_count')} -- not verified")
        gateway_log = self._run_or_print(
            f"[{installation}/{scenario}/w{window}] fetch warmup gateway log",
            self._ssh_cmd(server_ip, f"docker logs -t --since {since_dt.isoformat()} "
                                      f"--until {until_dt.isoformat()} insurance-server-lambdas-mtls-1"),
        )
        verification = verify_negotiated_groups(gateway_log, _CLIENT_EXPECTED_CURVE[profile])
        if not verification["ok"]:
            raise RuntimeError(
                f"[{installation}/{scenario}/{profile}/w{window}] warmup: negotiated-group verification "
                f"FAILED (A.2/B.12):\n  " + "\n  ".join(verification["problems"])
            )
        result.pop("calls", None)
        result["negotiated_group_verification"] = verification
        (scenario_path / f"run00_warmup_window{window:02d}.json").write_text(json.dumps(result, indent=2))

    def run_one_execution(self, installation, scenario, profile, window, run_index, scenario_path):
        lock = _SERVER_LOCKS[installation]
        if not lock.acquire(blocking=False):
            raise RuntimeError(
                f"OVERLAP DETECTED: another execution is already running on server {installation} -- "
                f"refusing to start a second one concurrently (Decision 60's guarantee, A.10)."
            )
        try:
            client_ip = self._client_ip(f"{scenario}@{installation}")
            server_ip = self._server_ip(installation)
            gateway_ip = self._server_gateway_ip(installation, f"{scenario}@{installation}")
            label = f"w{window:02d}_run{run_index:02d}"  # A.1: window folded into the remote label too
            tcpdump_enabled = _tcpdump_enabled_for_run(run_index)
            skip_tcpdump = not tcpdump_enabled

            if not skip_tcpdump:
                server_tcpdump_cmd, server_pid, server_log, server_pcap = self._tcpdump_start_cmd(label, "server")
                client_tcpdump_cmd, client_pid, client_log, client_pcap = self._tcpdump_start_cmd(label, "client")
                self._run_or_print(f"[{installation}/{scenario}] tcpdump start (server)",
                                    self._ssh_cmd(server_ip, server_tcpdump_cmd))
                self._run_or_print(f"[{installation}/{scenario}] tcpdump start (client)",
                                    self._ssh_cmd(client_ip, client_tcpdump_cmd))
                # A.6/Decision 63: a backgrounded start succeeding at the SSH
                # level doesn't mean tcpdump itself is actually alive (bad
                # interface, binary missing) -- this follow-up check aborts
                # loudly if it isn't, same as LocalExecutor's own liveness
                # check.
                self._verify_tcpdump_started(server_ip, f"[{installation}/{scenario}] tcpdump (server)", server_pid)
                self._verify_tcpdump_started(client_ip, f"[{installation}/{scenario}] tcpdump (client)", client_pid)
            else:
                print(f"  [{installation}/{scenario}] run {label}: tcpdump DELIBERATELY SKIPPED "
                      f"(CAMPAIGN_TCPDUMP_AB_TEST alternation, pilot acceptance criterion 7)")
                server_pid = client_pid = server_pcap = client_pcap = None

            # Pilot acceptance criterion 4: periodic CPU/steal/mem
            # sampling, independent of whether tcpdump itself is
            # running this execution -- started/stopped around the
            # SAME window as tcpdump (if any), not gated by
            # `skip_tcpdump`.
            server_sampler_cmd, server_sampler_pid, server_sampler_out = self._cpu_mem_sampler_start_cmd(label, "server")
            client_sampler_cmd, client_sampler_pid, client_sampler_out = self._cpu_mem_sampler_start_cmd(label, "client")
            self._run_or_print(f"[{installation}/{scenario}] CPU/mem sampler start (server)",
                                self._ssh_cmd(server_ip, server_sampler_cmd))
            self._run_or_print(f"[{installation}/{scenario}] CPU/mem sampler start (client)",
                                self._ssh_cmd(client_ip, client_sampler_cmd))

            since_dt = datetime.now(timezone.utc)
            remote_argv = ["python3", "campaign_client_runner.py", "--label", label]
            remote_cmd = f"cd ~/thesis/scripts && {self._env_prefix(_REMOTE_CLIENT_ENV(profile, gateway_ip))} {shlex.join(remote_argv)}"
            try:
                stdout = self._run_or_print(
                    f"[{installation}/{scenario}] run execution {label}",
                    self._ssh_cmd(client_ip, remote_cmd),
                    timeout_seconds=EXECUTION_TIMEOUT_SECONDS,
                )
            except Exception:
                # Pilot item 3 (this turn): found live, real pilot data --
                # tcpdump/the CPU sampler are `nohup`/`setsid`-backgrounded
                # on the remote hosts specifically so they survive THIS
                # SSH session ending (A.6) -- which means a failure HERE
                # (e.g. the execution itself timing out) left them running
                # with no cleanup at all, since the stop calls below only
                # ran on the success path. A retry then reused the SAME
                # label/filenames while the orphaned sampler from the
                # failed attempt was STILL writing to them -- confirmed
                # live: a null-byte gap in one real run's own server-side
                # cpu.jsonl, from two processes racing on the same path.
                # Best-effort (`_run_tolerant`, never raises) so a cleanup
                # failure doesn't mask the real error below.
                if not skip_tcpdump:
                    self._run_tolerant(f"[{installation}/{scenario}] tcpdump stop (server, cleanup after failure)",
                                        self._ssh_cmd(server_ip, self._tcpdump_stop_cmd(server_pid)))
                    self._run_tolerant(f"[{installation}/{scenario}] tcpdump stop (client, cleanup after failure)",
                                        self._ssh_cmd(client_ip, self._tcpdump_stop_cmd(client_pid)))
                self._run_tolerant(f"[{installation}/{scenario}] CPU/mem sampler stop (server, cleanup after failure)",
                                    self._ssh_cmd(server_ip, self._cpu_mem_sampler_stop_cmd(server_sampler_pid)))
                self._run_tolerant(f"[{installation}/{scenario}] CPU/mem sampler stop (client, cleanup after failure)",
                                    self._ssh_cmd(client_ip, self._cpu_mem_sampler_stop_cmd(client_sampler_pid)))
                raise
            until_dt = datetime.now(timezone.utc)

            if not skip_tcpdump:
                self._run_or_print(f"[{installation}/{scenario}] tcpdump stop (server)",
                                    self._ssh_cmd(server_ip, self._tcpdump_stop_cmd(server_pid)))
                self._run_or_print(f"[{installation}/{scenario}] tcpdump stop (client)",
                                    self._ssh_cmd(client_ip, self._tcpdump_stop_cmd(client_pid)))

            self._run_or_print(f"[{installation}/{scenario}] CPU/mem sampler stop (server)",
                                self._ssh_cmd(server_ip, self._cpu_mem_sampler_stop_cmd(server_sampler_pid)))
            self._run_or_print(f"[{installation}/{scenario}] CPU/mem sampler stop (client)",
                                self._ssh_cmd(client_ip, self._cpu_mem_sampler_stop_cmd(client_sampler_pid)))
            server_cpu_mem_samples = self._run_or_print(f"[{installation}/{scenario}] fetch CPU/mem samples (server)",
                                                         self._ssh_cmd(server_ip, f"cat {server_sampler_out}"))
            client_cpu_mem_samples = self._run_or_print(f"[{installation}/{scenario}] fetch CPU/mem samples (client)",
                                                         self._ssh_cmd(client_ip, f"cat {client_sampler_out}"))

            # A.5: the full remote-data surface -- gateway log, reference
            # ping, chronyc tracking, and the detected interfaces. Real
            # round trips now (not previews only); results are folded
            # into the run's own JSON/files, mirroring LocalExecutor's
            # own artifact layout exactly so campaign_pull.sh's tree
            # doesn't need to know which executor produced them.
            gateway_log = self._run_or_print(
                f"[{installation}/{scenario}] fetch gateway log (server)",
                self._ssh_cmd(server_ip, f"docker logs -t --since {since_dt.isoformat()} "
                                          f"--until {until_dt.isoformat()} insurance-server-lambdas-mtls-1"),
            )
            # Software-inventory audit (this turn): absolute paths
            # (/usr/sbin/ping, /usr/bin/chronyc) -- see server_flock_wrap()'s
            # own comment for why a bare command name isn't trusted here.
            # Pilot item 2 (this turn): pings the same IP the client's own
            # REMOTE_GATEWAY_HOST actually dials (gateway_ip, colocated-
            # aware) -- pinging server_ip (always public) would silently
            # measure a DIFFERENT path than the one the real execution
            # just used for a co-located client, corrupting the reference
            # RTT's own meaning.
            ping_output = self._run_tolerant(f"[{installation}/{scenario}] reference ping (client -> server)",
                                              self._ssh_cmd(client_ip, f"/usr/sbin/ping -c 10 -q {shlex.quote(gateway_ip)}"))
            server_chrony = self._run_tolerant(f"[{installation}/{scenario}] clock: chronyc tracking (server)",
                                                self._ssh_cmd(server_ip, "/usr/bin/chronyc tracking"))
            client_chrony = self._run_tolerant(f"[{installation}/{scenario}] clock: chronyc tracking (client)",
                                                self._ssh_cmd(client_ip, "/usr/bin/chronyc tracking"))
            server_iface = self._run_or_print(f"[{installation}/{scenario}] fetch detected interface (server)",
                                               self._ssh_cmd(server_ip, f"cat /home/ec2-user/{label}.server.iface"))
            client_iface = self._run_or_print(f"[{installation}/{scenario}] fetch detected interface (client)",
                                               self._ssh_cmd(client_ip, f"cat /home/ec2-user/{label}.client.iface"))

            if stdout is None:
                return None  # dry-run -- nothing real happened, nothing to write

            # campaign_client_runner.py's own stdout IS the complete
            # result, "calls" included (latency_automation.py's
            # run_once_timed(..., return_calls=True)) -- there is no
            # separate remote calls.jsonl file to fetch; the earlier
            # "cat .../calls.jsonl" command this turn's rehearsal
            # exposed as pointing at a file nothing ever writes has
            # been removed, not just left unreachable.
            result = json.loads(stdout)
            calls = result.pop("calls", [])
            server_dir, client_dir = scenario_path / "server", scenario_path / "client"
            with open(scenario_path / "runs" / f"{label}.calls.jsonl", "w") as f:
                for call in calls:
                    f.write(json.dumps(call) + "\n")
            (server_dir / f"{label}_gateway.log").write_text(gateway_log or "")
            # Pilot acceptance criterion 4: the fetched content IS
            # already one JSON object per line (the remote sampler's
            # own `print()` per sample) -- written through as-is, same
            # jsonl convention LocalExecutor's own A.9 sampler uses.
            (server_dir / f"{label}_cpu.jsonl").write_text(server_cpu_mem_samples or "")
            (client_dir / f"{label}_cpu.jsonl").write_text(client_cpu_mem_samples or "")
            (client_dir / f"{label}_ping.json").write_text(json.dumps({"raw_ping_output": ping_output}) + "\n")

            # A.8: client-vs-server drift from each side's own chronyc
            # tracking offset -- not a container-vs-host reading.
            server_offset = _parse_chrony_tracking_text(server_chrony)
            client_offset = _parse_chrony_tracking_text(client_chrony)
            result["client_server_clock_drift_seconds"] = (
                (client_offset - server_offset) if (server_offset is not None and client_offset is not None) else None
            )
            result["network_interface"] = {
                "server": (server_iface or "").strip() or None,
                "client": (client_iface or "").strip() or None,
            }

            # A.5: pcaps pulled back and gzipped locally, same as
            # LocalExecutor's own convention. Pilot acceptance
            # criterion 7: skipped entirely when tcpdump itself was
            # deliberately skipped -- nothing to pull.
            result["tcpdump_enabled"] = tcpdump_enabled
            if not skip_tcpdump:
                for side, remote_pcap, local_dir in (("server", server_pcap, server_dir), ("client", client_pcap, client_dir)):
                    local_pcap = local_dir / f"{label}.pcap"
                    try:
                        self._scp_pull(server_ip if side == "server" else client_ip, remote_pcap, local_pcap)
                    except RuntimeError as e:
                        print(f"  WARNING: {e} -- continuing without this side's pcap", file=sys.stderr)
                        continue
                    with open(local_pcap, "rb") as f_in, gzip.open(local_dir / f"{label}.pcap.gz", "wb") as f_out:
                        f_out.write(f_in.read())
                    local_pcap.unlink()

            return result
        finally:
            lock.release()


class LocalExecutor:
    """Decision 60: runs everything in-process, for the local-stack test
    (no AWS, no SSH) -- "server" and "client" are both the local
    machine, exactly like switch_crypto_profile.py/latency_automation.py
    already assume when run directly. Calls `latency_automation.py`'s
    and `opin_flow.py`'s own functions directly -- reused, not
    reimplemented. REMOTE_GATEWAY_HOST must already be set in the
    environment by the caller (the local test below sets it to the
    local stack's own gateway address) before this executor is used.
    """
    def __init__(self, allow_tcpdump_skip=False):
        import opin_flow as of
        import latency_automation as la
        import switch_crypto_profile as scp
        self.of = of
        self.la = la
        self.scp = scp
        self._block_state = {}
        # Decision 63: the ONLY way to get the old best-effort-skip
        # behavior back -- default is now "abort the block loudly if
        # capture can't start," matching the remote-mode requirement.
        # An explicit local flag, never silent, never the default.
        self.allow_tcpdump_skip = allow_tcpdump_skip

    def start_block_proxies(self, installation, profile, scenarios, window):
        """Decision 62's full per-block settling sequence, local part --
        A.2 confirms/documents the order explicitly: (a) switch profile
        on the server (reuses switch_crypto_profile.py's own helpers --
        does not reimplement container recreation/health-check logic),
        (b) start the client proxy/signer with the profile's own curve,
        (c) run 5 settling executions -- SAVED, not discarded, each
        verified -- (d) check the gateway log's negotiated curveID,
        correlated by channel (B.12), hard-aborts on mismatch. Per-
        scenario warmup and the round-robin loop happen AFTER this
        returns, in run_window() below -- this function's own job ends
        at (d). The SSH part (doing (a)/(c)/(d) against a real remote
        server) is SSHExecutor's job, not built here (Decision 60/62)."""
        scp = self.scp
        print(f"  [{installation}/{profile}] settling: switching server profile...")
        result = scp._compose("up", "-d", "--force-recreate", *scp.PROFILE_DEPENDENT_SERVICES, env_profile=profile)
        if result.returncode != 0:
            raise RuntimeError(f"docker compose up failed:\n{result.stdout}\n{result.stderr}")
        time.sleep(10)
        for name in ("insurance-server-lambdas-auth-1", "insurance-server-lambdas-mtls-1",
                     "insurance-server-lambdas-mockapi-1"):
            scp._start_if_exited(name)
        time.sleep(8)
        for name in ("insurance-server-lambdas-auth-1", "insurance-server-lambdas-mtls-1",
                     "insurance-server-lambdas-mockapi-1"):
            status = scp._container_status(name)
            if status != "running":
                raise RuntimeError(f"{name} is '{status}' after retry -- settling failed, inspect manually")
        scp._wait_for_mtls_ready()
        scp._check_psql_checkpoint_health()
        print(f"  [{installation}/{profile}] settling: server profile switched, containers healthy.")

        # A.8: renamed from clock_drift_seconds, and no longer a
        # container-vs-host reading -- the gateway container and this
        # Windows dev host share the SAME underlying kernel clock
        # (Docker Desktop's Linux VM), so that comparison could never
        # show a real drift in the first place, local-test artifact
        # only. The real quantity A.8 asks for is CLIENT-vs-SERVER
        # drift, measured via `chronyc tracking` on each real instance
        # (see _chrony_tracking_offset()'s own docstring for why that's
        # the right building block) -- not applicable to a single-host
        # local test at all (there is no second instance here), so this
        # stays None with the reason recorded, never a fabricated 0.0;
        # SSHExecutor's real per-instance chronyc readings (A.5) are
        # what populates this for real.
        client_server_clock_drift_seconds = None
        client_server_clock_drift_note = (
            "single-host local test -- no second real instance to compare chronyc tracking "
            "against; populated for real by SSHExecutor's per-instance chronyc readings (A.5/A.8)."
        )

        block_start_utc = datetime.now(timezone.utc)
        proc = self.of.start_tls_kem_proxy(profile)
        signer_started = self.of.start_pqc_signer_service(profile)
        # Recorded as soon as the containers are up, BEFORE the settling
        # loop and the negotiated-group check (both of which can still
        # raise) -- so a failure there still leaves stop_block_proxies()
        # with real state to tear down instead of leaking these
        # containers (run_window() now calls start_block_proxies() INSIDE
        # its try/finally for exactly this reason).
        self._block_state[(installation, profile)] = {
            "tls_kem_proxy_proc": proc,
            "pqc_signer_started": signer_started,
            "block_start_utc": block_start_utc,
            "gateway_log_lines": [],
        }

        settling_results = []
        curve_ids_seen = set()
        settle_start = datetime.now(timezone.utc)
        for i in range(1, 6):
            whole_run_retries = []
            t0 = time.monotonic()
            try:
                r = self.la.run_once_timed_with_retry(profile, f"settling{i}", whole_run_retries, return_calls=False)
                ok = r.get("call_count", 0) > 0  # "verified" -- completed without exception and did real work
                r["verified"] = ok
                if not ok:
                    raise RuntimeError(f"settling run {i} completed but call_count={r.get('call_count')} -- not verified")
            except Exception as e:
                raise RuntimeError(f"settling run {i}/5 failed ({type(e).__name__}: {e}) -- aborting block") from e
            print(f"    settling run {i}/5: {time.monotonic() - t0:.3f}s (saved, verified)")
            settling_results.append(r)
        settle_end = datetime.now(timezone.utc)

        # B.12: negotiated-group check -- now a correlated, per-channel
        # check (verify_negotiated_groups(), module-level above) instead
        # of the old flat "all curveIDs equal" comparison that produced
        # a false positive on classic ({"CurveP256", "CurveP384"} is
        # NOT a failure -- it's the client channel's P384 plus the
        # internal AS->RS carve-out's P256, two different, both-correct
        # channels, v7 Decision 15). This now ABORTS the block on any
        # real problem (client channel wrong curve, internal channel
        # drifted off P256, or an unpaired carve-out) -- the loose
        # "WARN on any mix" compromise from the prior session is
        # superseded by this turn's exact spec, not kept alongside it.
        log_r = subprocess.run(
            ["docker", "logs", "-t", "--since", settle_start.isoformat(), "--until", settle_end.isoformat(),
             self.of.GATEWAY_CONTAINER],
            capture_output=True, text=True, timeout=30,
        )
        gateway_log_text = log_r.stdout + log_r.stderr
        verification = verify_negotiated_groups(gateway_log_text, _CLIENT_EXPECTED_CURVE[profile])
        print(f"  [{installation}/{profile}] settling: client curves={verification['client_curves']}, "
              f"internal curves={verification['internal_curves']}")
        if not verification["ok"]:
            raise RuntimeError(
                f"[{installation}/{profile}] settling: negotiated-group verification FAILED (B.12):\n  "
                + "\n  ".join(verification["problems"])
            )
        curve_ids_seen = set(verification["client_curves"]) | set(verification["internal_curves"])

        # A.1: window folded into every settling/gateway-log filename --
        # these used to be shared across all 3 windows of a campaign,
        # so window 2's settling run silently overwrote window 1's.
        # Verified by test_window_no_overwrite.py (item A.1's own test).
        meta_dir = DATA_ROOT / "v8" / "latency" / "_campaign-control" / "windows" / installation
        meta_dir.mkdir(parents=True, exist_ok=True)
        for i, r in enumerate(settling_results, start=1):
            (meta_dir / f"settling_{profile}_window{window:02d}_run{i}.json").write_text(json.dumps(r, indent=2))
        (meta_dir / f"settling_{profile}_window{window:02d}_meta.json").write_text(json.dumps({
            "client_server_clock_drift_seconds": client_server_clock_drift_seconds,
            "client_server_clock_drift_note": client_server_clock_drift_note,
            "negotiated_curve_ids": sorted(curve_ids_seen),
            "negotiated_group_verification": verification,
        }, indent=2))

    def stop_block_proxies(self, installation, profile, scenarios, window):
        state = self._block_state.pop((installation, profile), None)
        if state is None:
            return
        block_end_utc = datetime.now(timezone.utc)
        # Decision 62: ONE continuous raw capture for the whole block,
        # not a fresh `docker logs` call per execution -- saved as-is;
        # per-run slices are DERIVED from this by _slice_gateway_log(),
        # not captured live.
        log_r = subprocess.run(
            ["docker", "logs", "-t", "--since", state["block_start_utc"].isoformat(),
             "--until", block_end_utc.isoformat(), self.of.GATEWAY_CONTAINER],
            capture_output=True, text=True, timeout=30,
        )
        meta_dir = DATA_ROOT / "v8" / "latency" / "_campaign-control" / "windows" / installation
        meta_dir.mkdir(parents=True, exist_ok=True)
        # A.1: window folded in -- see start_block_proxies()'s matching note.
        block_log_path = meta_dir / f"gateway_block_{profile}_window{window:02d}.log"
        block_log_path.write_text(log_r.stdout + log_r.stderr)
        state["block_log_path"] = block_log_path

        self.of.stop_pqc_signer_service(state["pqc_signer_started"])
        self.of.stop_tls_kem_proxy(state["tls_kem_proxy_proc"])
        self._last_block_log = block_log_path  # so run_one_execution's slicing (called before stop) still has a path to fall back to post-hoc, if ever needed

    def run_warmup(self, installation, scenario, profile, window, scenario_path):
        """A.2: the warmup itself now also verifies the negotiated
        key-exchange group (B.12's correlated check) over its own time
        window -- not just the 5 settling runs. A mismatch here means
        the profile switch "succeeded" by the settling check but this
        scenario's own client-facing connection still negotiated the
        wrong curve (e.g. a stale client-side TLS session reusing an
        old group) -- aborts before any of the block's real runs are
        spent on a broken warmup."""
        whole_run_retries = []
        since_dt = datetime.now(timezone.utc)
        result = self.la.run_once_timed_with_retry(profile, "warmup", whole_run_retries, return_calls=False)
        until_dt = datetime.now(timezone.utc)
        result["whole_run_retries"] = whole_run_retries

        gateway_log_text = self._slice_gateway_log_live(since_dt, until_dt)
        verification = verify_negotiated_groups(gateway_log_text, _CLIENT_EXPECTED_CURVE[profile])
        result["negotiated_group_verification"] = verification
        if not verification["ok"]:
            raise RuntimeError(
                f"[{installation}/{scenario}/{profile}/w{window}] warmup: negotiated-group verification "
                f"FAILED (A.2/B.12):\n  " + "\n  ".join(verification["problems"])
            )

        (scenario_path / f"run00_warmup_window{window:02d}.json").write_text(
            json.dumps(result, indent=2)
        )

    def _slice_gateway_log_live(self, since_dt, until_dt, margin_seconds=2):
        """Decision 62: derives a per-run slice from a FRESH `docker
        logs --since/--until` call widened by a margin -- used here
        because the continuous block-level file (stop_block_proxies)
        isn't finalized until the block ends, so a per-run artifact
        needed during the block itself has to re-query the running
        container's own log buffer, not read a file that doesn't exist
        yet. This still reads the gateway's own cumulative log (nothing
        is captured freshly PER RUN in the tcpdump sense) -- the
        "continuous capture, derived slices" principle is about not
        spinning up a NEW capture mechanism per run, which this
        doesn't."""
        since_m = since_dt - timedelta(seconds=margin_seconds)
        until_m = until_dt + timedelta(seconds=margin_seconds)
        r = subprocess.run(
            ["docker", "logs", "-t", "--since", since_m.isoformat(), "--until", until_m.isoformat(),
             self.of.GATEWAY_CONTAINER],
            capture_output=True, text=True, timeout=30,
        )
        return r.stdout + r.stderr

    def _try_tcpdump(self, label, out_path, interface=None):
        """Decision 63: explicit interface (never "any"), port-443
        filter, liveness + file-growth check after a short grace period,
        kernel-dropped-packet count captured from tcpdump's own summary
        line. Default behavior is to ABORT THE BLOCK loudly if capture
        can't start -- the old best-effort skip only happens now with
        self.allow_tcpdump_skip explicitly set, and that fact is
        recorded in the run's own JSON, never silent.

        A.7: `interface=None` (the default, replacing the old hardcoded
        "eth0" literal callers used to pass in) auto-detects the
        default-route interface via `_default_route_interface()`
        (module-level, /proc/net/route-based). Detection failing counts
        as the SAME class of problem as tcpdump itself being missing --
        abort unless allow_tcpdump_skip. The resolved interface name is
        returned in the result dict so the caller can record it in the
        run's own JSON instead of assuming it."""
        if interface is None:
            interface = _default_route_interface()
            if interface is None:
                if not self.allow_tcpdump_skip:
                    raise RuntimeError(
                        f"[{label}] could not detect a default-route interface (/proc/net/route) and "
                        f"allow_tcpdump_skip is not set -- aborting the block loudly (A.7/Decision 63)."
                    )
                print(f"    [{label}] could not detect a default-route interface -- SKIPPING pcap capture "
                      f"(allow_tcpdump_skip explicitly set).", file=sys.stderr)
                return {"process": None, "skipped": True, "skip_reason": "no default-route interface detected",
                        "interface": None}

        if subprocess.run(["which", "tcpdump"], capture_output=True).returncode != 0:
            if not self.allow_tcpdump_skip:
                raise RuntimeError(
                    f"[{label}] tcpdump not available and allow_tcpdump_skip is not set -- "
                    f"aborting the block loudly (Decision 63). Pass allow_tcpdump_skip=True "
                    f"explicitly to permit running without pcap capture."
                )
            print(f"    [{label}] tcpdump not available -- SKIPPING pcap capture "
                  f"(allow_tcpdump_skip explicitly set).", file=sys.stderr)
            return {"process": None, "skipped": True, "skip_reason": "tcpdump not installed", "interface": interface}

        proc = subprocess.Popen(
            ["sudo", "tcpdump", "-i", interface, "-s", str(TCPDUMP_SNAPLEN_BYTES), "port", "443", "-w", str(out_path)],
            stderr=subprocess.PIPE, text=True,
        )
        time.sleep(0.5)
        if proc.poll() is not None:
            msg = f"[{label}] tcpdump exited immediately (code {proc.returncode}) -- capture never started."
            if not self.allow_tcpdump_skip:
                raise RuntimeError(msg + " Aborting the block loudly (Decision 63).")
            print(f"    {msg} SKIPPING (allow_tcpdump_skip explicitly set).", file=sys.stderr)
            return {"process": None, "skipped": True, "skip_reason": msg, "interface": interface}
        time.sleep(1.0)
        grew = out_path.exists() and out_path.stat().st_size > 0
        if not grew:
            proc.terminate()
            msg = f"[{label}] tcpdump process is alive but {out_path} isn't growing -- capture is not actually working."
            if not self.allow_tcpdump_skip:
                raise RuntimeError(msg + " Aborting the block loudly (Decision 63).")
            print(f"    {msg} SKIPPING (allow_tcpdump_skip explicitly set).", file=sys.stderr)
            return {"process": None, "skipped": True, "skip_reason": msg, "interface": interface}
        return {"process": proc, "skipped": False, "skip_reason": None, "interface": interface}

    def run_one_execution(self, installation, scenario, profile, window, run_index, scenario_path):
        lock = _SERVER_LOCKS[installation]
        if not lock.acquire(blocking=False):
            raise RuntimeError(
                f"OVERLAP DETECTED: another execution is already running on server {installation} -- "
                f"refusing to start a second one concurrently (Decision 60's guarantee)."
            )
        try:
            label = f"run{run_index:02d}"
            server_dir = scenario_path / "server"
            client_dir = scenario_path / "client"

            server_pcap = server_dir / f"{label}.pcap"
            client_pcap = client_dir / f"{label}.pcap"
            # A.7: interface=None -> auto-detected from /proc/net/route,
            # never the old hardcoded "eth0" literal.
            server_tcpdump = self._try_tcpdump(f"{installation}/server", server_pcap)
            client_tcpdump = self._try_tcpdump(f"{installation}/client", client_pcap)

            # A.9: periodic sampling throughout the execution (not just
            # 3 discrete before/during/after points), /proc/meminfo
            # included alongside /proc/stat -- see _PeriodicSampler's
            # own docstring.
            sampler = _PeriodicSampler(interval_seconds=1.0)
            sampler.start()
            since_dt = datetime.now(timezone.utc)

            whole_run_retries = []
            result = self.la.run_once_timed_with_retry(profile, label, whole_run_retries, return_calls=True)
            result["whole_run_retries"] = whole_run_retries
            result["retried"] = bool(result.get("retries"))

            until_dt = datetime.now(timezone.utc)
            cpu_mem_samples = sampler.stop()
            gateway_log_slice = self._slice_gateway_log_live(since_dt, until_dt)

            dropped_packets = {}
            for side, tcpdump_info, pcap_path, gz_path in (
                ("server", server_tcpdump, server_pcap, server_dir / f"{label}.pcap.gz"),
                ("client", client_tcpdump, client_pcap, client_dir / f"{label}.pcap.gz"),
            ):
                proc = tcpdump_info["process"]
                if proc is not None:
                    proc.terminate()
                    try:
                        _, stderr_text = proc.communicate(timeout=10)
                    except subprocess.TimeoutExpired:
                        stderr_text = ""
                    m = re.search(r"(\d+) packets dropped by kernel", stderr_text or "")
                    dropped_packets[side] = int(m.group(1)) if m else None
                    if pcap_path.exists():
                        with open(pcap_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
                            f_out.write(f_in.read())
                        pcap_path.unlink()
                else:
                    dropped_packets[side] = None

            calls = result.pop("calls", [])
            with open(scenario_path / "runs" / f"{label}.calls.jsonl", "w") as f:
                for call in calls:
                    f.write(json.dumps(call) + "\n")

            (server_dir / f"{label}_gateway.log").write_text(gateway_log_slice)
            # A.9: one JSON object per sample, one per line -- jsonl, not
            # a single before/during/after object -- /proc/stat AND
            # /proc/meminfo in every sample (_sample_cpu_mem_steal()).
            cpu_jsonl_text = "".join(json.dumps(s) + "\n" for s in cpu_mem_samples)
            (server_dir / f"{label}_cpu.jsonl").write_text(cpu_jsonl_text)
            (client_dir / f"{label}_cpu.jsonl").write_text(
                cpu_jsonl_text  # same machine as server in the local test; a real remote
                                 # client samples its own /proc/stat+/proc/meminfo independently
            )
            (client_dir / f"{label}_ping.json").write_text(
                json.dumps({"note": "reference ping: not applicable in the local test (no real network hop)"}) + "\n"
            )
            # Same field name as SSHExecutor's own result["tcpdump_enabled"]
            # (every execution JSON registers it) -- here it means "both
            # sides actually captured", distinct from the pilot's own
            # A/B-test alternation (LocalExecutor never runs the AWS
            # pilot); per-side skip reasons stay available for
            # debugging under their own, differently-named key.
            result["tcpdump_enabled"] = not (server_tcpdump["skipped"] or client_tcpdump["skipped"])
            result["tcpdump_skip_detail"] = {"server": server_tcpdump["skipped"], "client": client_tcpdump["skipped"]}
            result["dropped_packets"] = dropped_packets
            # A.7: the detected interface, recorded instead of assumed.
            result["network_interface"] = {"server": server_tcpdump.get("interface"),
                                            "client": client_tcpdump.get("interface")}

            return result
        finally:
            lock.release()


def run_warmup(executor, installation, scenario, profile, window, scenario_path):
    """latency_automation.py's OWN single-warmup-run convention (its
    `run00_warmup.json`, one discarded flow before the counted runs) --
    reused as-is via the executor, once per scenario per block. NOT the
    same thing as Decision 4's separate 5-flow container-settling
    protocol, which happens when switch_crypto_profile.py recreates
    containers at profile-switch time -- that is a server-side,
    profile-switch-time concern this orchestrator does not build yet
    (pre_block_checks() is the natural home for it once it exists;
    flagged here explicitly so the two are never conflated). Written to
    its own file, never mixed into runs/'s numbering."""
    executor.run_warmup(installation, scenario, profile, window, scenario_path)


def start_block_proxies(executor, installation, profile, scenarios, window):
    executor.start_block_proxies(installation, profile, scenarios, window)


def stop_block_proxies(executor, installation, profile, scenarios, window):
    executor.stop_block_proxies(installation, profile, scenarios, window)


def run_one_execution(executor, installation, scenario, profile, window, run_index, scenario_path):
    """Delegates to the executor (Decision 60) -- LocalExecutor (real,
    in-process, reuses latency_automation.py's run_once_timed_with_retry()
    directly) for the local test, SSHExecutor (not implemented) for real
    AWS. Never reimplements T_fluxo measurement itself."""
    return executor.run_one_execution(installation, scenario, profile, window, run_index, scenario_path)


def build_latin_square_profile_orders(seed: int) -> dict:
    """Item 2 (order/warm-up turn, thesis/results/v8/DECISIONS.md):
    replaces run_window()'s former independent-per-window
    `rng.shuffle(profile_order)` -- which confounded profile identity
    with window/position (Decision 89: pilot 2's single real window drew
    PQC first and Hybrid last, every time, by construction) -- with a
    proper 3x3 Latin square across the campaign's WINDOWS_PER_CAMPAIGN
    windows: each profile occupies each of the 3 within-window block
    positions (1st/2nd/3rd) exactly once over the 3 windows.

    ONE seed, registered once per campaign (not once per window): draws
    a uniformly random base permutation of PROFILES (1 of 3! = 6) and a
    uniformly random rotation direction (+1 or -1); the windows' own
    profile_order are the base permutation and its cyclic rotations in
    that direction. A circulant Latin square this way automatically
    satisfies the column constraint too (each position also sees every
    profile exactly once) with no rejection sampling -- 6 base
    permutations x 2 directions = 12, the full count of 3x3 Latin
    squares, every one of them reachable by this seed."""
    if len(PROFILES) != WINDOWS_PER_CAMPAIGN:
        raise ValueError(
            f"build_latin_square_profile_orders() needs len(PROFILES) == WINDOWS_PER_CAMPAIGN "
            f"({len(PROFILES)} != {WINDOWS_PER_CAMPAIGN}) -- the Latin-square guarantee (each "
            f"profile once per window AND once per position) only holds for a square matrix."
        )
    rng = random.Random(seed)
    base = PROFILES[:]
    rng.shuffle(base)
    direction = rng.choice([1, -1])
    n = len(base)
    return {
        window: base[(direction * (window - 1)) % n:] + base[:(direction * (window - 1)) % n]
        for window in range(1, WINDOWS_PER_CAMPAIGN + 1)
    }


def _pick_instance_warmup_scenario(executor, installation):
    """Reuses run_window()'s own inventory-scoping rule (SSHExecutor
    only -- see its own comment) to pick ONE scenario the instance
    warmup can safely run, instead of hardcoding SCENARIO_ROTATION's
    window-1 entry and risking a KeyError against a scoped pilot
    inventory that doesn't happen to include it. Returns None (caller
    skips the warmup for this installation, with a warning -- same
    "don't abort the whole campaign over one installation" philosophy
    as item 3's orchestrator fix) when nothing in SCENARIO_ROTATION's
    own window-1 list is available."""
    candidates = SCENARIO_ROTATION[installation][1]
    if isinstance(executor, SSHExecutor):
        available_clients = executor.inventory.get("clients", {})
        candidates = [s for s in candidates if f"{s}@{installation}" in available_clients]
    return candidates[0] if candidates else None


def run_instance_warmup(executor, installation, duration_seconds=INSTANCE_WARMUP_SECONDS):
    """Item 2 (order/warm-up turn, thesis/results/v8/DECISIONS.md): a
    freshly launched EC2 instance's own cold-start (cold EBS reads, cold
    OS page cache, cold interpreter/JIT caches, a not-yet-settled network
    stack) is a broader disturbance than a container recreation on an
    already-warm instance -- see INSTANCE_WARMUP_SECONDS's own module-
    level comment for the 180s figure's justification. Runs once per
    installation, before the campaign's very first block (main() calls
    this before the window loop starts).

    Reuses run_warmup() unchanged (same negotiated-group verification it
    already does for a real block) in a loop keyed by wall-clock time
    instead of a fixed count -- NOT run_one_execution()/the real
    runs/run{NN}.json numbering, and NOT scenario_dir()'s own real-data
    tree: every throwaway flow here writes into its own side directory
    under _campaign-control/instance_warmup/, so it can never be mistaken
    for real campaign data by a later pull or consolidation pass.
    start_block_proxies()/stop_block_proxies() give it the same profile-
    switch-and-settle lifecycle a real block gets (window=0 is a
    sentinel, distinct from every real window 1..WINDOWS_PER_CAMPAIGN)."""
    scenario = _pick_instance_warmup_scenario(executor, installation)
    if scenario is None:
        print(f"[{installation}] instance warmup: no scenario in this run's own inventory -- skipping "
              f"(not aborting the campaign).")
        return
    warmup_dir = DATA_ROOT / "v8" / "latency" / "_campaign-control" / "instance_warmup" / installation
    warmup_dir.mkdir(parents=True, exist_ok=True)
    print(f"[{installation}] instance warmup: {duration_seconds}s of disposable "
          f"{INSTANCE_WARMUP_PROFILE}/{scenario} flows before the campaign's first block "
          f"(recorded separately under {warmup_dir}, never in a scenario's real data)")
    start_block_proxies(executor, installation, INSTANCE_WARMUP_PROFILE, [scenario], window=0)
    try:
        deadline = time.monotonic() + duration_seconds
        i = 0
        while time.monotonic() < deadline:
            i += 1
            run_warmup(executor, installation, scenario, INSTANCE_WARMUP_PROFILE, window=i, scenario_path=warmup_dir)
    finally:
        stop_block_proxies(executor, installation, INSTANCE_WARMUP_PROFILE, [scenario], window=0)
    print(f"[{installation}] instance warmup: {i} disposable flow(s) run in {duration_seconds}s")


def wait_for_operator_gate(gate_name: str, poll_seconds: int = 60) -> None:
    """Validation-gate turn (item 3, thesis/results/v8/DECISIONS.md):
    blocks until the operator creates this gate's own marker file -- the
    orchestrator itself cannot run pilot_acceptance.py against the gate's
    sample (that needs a PULLED data root, campaign_pull.sh's own
    rsync+manifest layout, reviewed off-instance -- this process only
    ever runs ON the control instance, which never holds the pcaps
    itself). No timeout: an unattended campaign must never silently
    "pass" a gate nobody actually reviewed."""
    marker_path = DATA_ROOT / "v8" / "latency" / "_campaign-control" / "gates" / f"{gate_name}.approved"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    write_status("waiting_operator", f"gate={gate_name}: touch {marker_path} to continue")
    print(f"=== GATE: {gate_name} -- waiting for operator approval ===")
    print(f"    Pull this stage's own sample (campaign_pull.sh), run pilot_acceptance.py against it "
          f"off-instance, then on the control instance: touch {marker_path}")
    while not marker_path.exists():
        time.sleep(poll_seconds)
    print(f"=== GATE: {gate_name} -- approved (marker found), continuing ===")


def run_validation_stage(executor, installations):
    """Item 3 (validation-gate turn, thesis/results/v8/DECISIONS.md): ONE
    execution per profile, in every one of the campaign's 8 scenarios
    (SCENARIO_ROTATION[installation][1] is already each installation's
    full, non-rotated scenario set -- 4 sa-east-1 + 2 us-east-1 + 2
    ap-northeast-1 = 8; x 3 profiles = 24 executions total), BEFORE
    window 1's own first block. Written to its own side directory under
    _campaign-control/validation_stage/, never a real scenario_dir()
    path -- this sample is for the operator's own pilot_acceptance.py
    review (wait_for_operator_gate() below), not for pooling into the
    campaign's real 30-runs-per-cell dataset.

    Mirrors run_window()'s own block loop (switch profile once per
    profile via start_block_proxies()/stop_block_proxies(), round-robin
    scenarios inside it) at N=1 instead of RUNS_PER_WINDOW -- same
    inventory-scoping rule as run_window() (SSHExecutor only), same
    "skip an installation with nothing available in this run's own
    inventory, don't abort the whole campaign" philosophy as the earlier
    installation-skip orchestrator fix."""
    for installation in installations:
        scenarios = SCENARIO_ROTATION[installation][1]
        if isinstance(executor, SSHExecutor):
            available_clients = executor.inventory.get("clients", {})
            scenarios = [s for s in scenarios if f"{s}@{installation}" in available_clients]
        if not scenarios:
            print(f"[{installation}] validation stage: no scenario in this run's own inventory -- skipping "
                  f"(not aborting the campaign).")
            continue
        for profile in PROFILES:
            check_time_budget()
            pre_block_checks(executor, installation, profile)
            start_block_proxies(executor, installation, profile, scenarios, window=0)
            try:
                for scenario in scenarios:
                    out_dir = (DATA_ROOT / "v8" / "latency" / "_campaign-control" / "validation_stage"
                               / installation / profile / scenario)
                    out_dir.mkdir(parents=True, exist_ok=True)
                    result = run_one_execution(executor, installation, scenario, profile, 0, 1, out_dir)
                    (out_dir / "run01.json").write_text(json.dumps({
                        "started_at_utc": datetime.now(timezone.utc).isoformat(),
                        "server": installation, "client": scenario, "profile": profile,
                        "result": result,
                    }, indent=2))
            finally:
                stop_block_proxies(executor, installation, profile, scenarios, window=0)
    print("=== validation stage: 24 executions complete (see _campaign-control/validation_stage/) ===")
    wait_for_operator_gate("validation_stage")


def run_window(executor, installation, window, seed, profile_order):
    """profile_order: this window's row of the campaign-wide Latin square
    (build_latin_square_profile_orders(), item 2) -- no longer derived
    here from an independent per-window shuffle; `seed` is kept as a
    parameter purely so window{NN}.json below can still record which
    seed produced the square this window's row came from (traceability),
    not to re-derive the order itself."""
    scenarios = SCENARIO_ROTATION[installation][window]
    # Pilot item 2 (this turn): found live -- SCENARIO_ROTATION above is
    # the FULL campaign's own hardcoded 4-scenario list for sa-east-1,
    # with no notion of a scoped topology (MOCKOPIN_ENABLED_CLIENT_SCENARIOS,
    # the pilot's own L0+L325-only inventory). Every downstream IP lookup
    # (_client_ip(), "L123@sa-east-1") raised KeyError the moment it ran
    # against this pilot's inventory -- deterministic, on literally every
    # block, never reaching a single real execution. Filtered down to
    # whatever this run's own inventory actually has, in the same order,
    # rather than assuming the full list is always present.
    # LocalExecutor (the rehearsal/regression-test executor, single-host,
    # no multi-client inventory concept at all) has no `.inventory` --
    # this filtering is SSHExecutor-only, found live against the real
    # pilot's own scoped topology; LocalExecutor's own tests keep their
    # original, unfiltered scenario list exactly as before. Checked by
    # isinstance, not getattr/hasattr -- test_block_order.py's own bare
    # mock.Mock() executor auto-vivifies ANY attribute access (including
    # `.inventory`) into another Mock, which would pass a truthy getattr
    # check and then break on `.get()` not behaving like a real dict;
    # isinstance only ever matches the real SSHExecutor.
    if isinstance(executor, SSHExecutor):
        available_clients = executor.inventory.get("clients", {})
        missing_scenarios = [s for s in scenarios if f"{s}@{installation}" not in available_clients]
        if missing_scenarios:
            print(f"[{installation}] window {window}: {missing_scenarios} not in this run's own inventory "
                  f"(scoped topology, e.g. the pilot's MOCKOPIN_ENABLED_CLIENT_SCENARIOS) -- skipping them.")
        scenarios = [s for s in scenarios if f"{s}@{installation}" in available_clients]
        if not scenarios:
            # Pilot 2 (this turn, item 3): this used to be sys.exit(), a hard
            # abort of the WHOLE campaign process the moment iteration
            # reached the first installation with zero enabled scenarios in
            # a scoped-topology run (e.g. a pilot inventory covering only
            # sa-east-1, while PROFILES/installations still lists every
            # full-campaign server). Confirmed live: harmless for a
            # single-installation pilot only because that installation's
            # own window had already completed in full before iteration
            # reached the next, empty one -- for any run with more than one
            # installation and an uneven scoped inventory, this would have
            # killed already-healthy installations' remaining windows too.
            # A missing scenario set for ONE installation is not a reason to
            # stop every other installation's own campaign -- skip with a
            # warning and let the caller's per-installation loop continue.
            print(f"[{installation}] window {window}: no enabled scenario is in this run's own inventory "
                  f"-- skipping this installation for this window (not aborting the campaign).")
            return
    print(f"[{installation}] window {window}: profile order = {profile_order}, "
          f"scenario order = {scenarios} (seed={seed})")

    # Registered per server per window (Decision 53), under
    # _campaign-control/ -- not nested inside each scenario's own
    # directory, so the control/schedule metadata is never mistaken for
    # collected experiment data.
    meta_dir = DATA_ROOT / "v8" / "latency" / "_campaign-control" / "windows" / installation
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / f"window{window:02d}.json").write_text(json.dumps({
        "installation": installation,
        "window": window,
        # Item 2: this is the campaign-wide latin_square_seed (same value
        # across all 3 windows and all installations), not a per-window
        # seed any more -- kept here so this window's own row is still
        # traceable back to the square it came from without needing
        # build_latin_square_profile_orders() re-run to confirm it.
        "seed": seed,
        "profile_order": profile_order,
        "scenario_rotation": scenarios,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    }, indent=2))

    # A.2: block order, confirmed/fixed this turn --
    #   (1) switch profile + bring up proxies (start_block_proxies,
    #       which ALSO runs the 5 settling executions and the
    #       negotiated-group check internally -- Decision 62),
    #   (2) per-scenario warmup (once this block's proxies are actually
    #       up and switched to the right profile -- the OLD code ran
    #       warmup BEFORE start_block_proxies, against whatever profile
    #       the client proxy happened to still be running from the
    #       PREVIOUS block; a real, silent bug, not a style issue --
    #       fixed here, not just confirmed),
    #   (3) round-robin.
    # A.4: real mode must abort the whole process on NotImplementedError,
    # not swallow it into a clean per-window `return` that exits 0 --
    # none of the three stages below catch it any more; it propagates
    # out of run_window(), out of main(), to the interpreter's own
    # uncaught-exception handler (nonzero exit, traceback on stderr).
    # --dry-run never raises it in the first place (SSHExecutor._run_or_print
    # only raises when dry_run=False), so dry-run runs are unaffected.
    for block_position, profile in enumerate(profile_order):
        check_time_budget()  # pilot item 3 -- before spending any more real time/money on this block
        checks = pre_block_checks(executor, installation, profile)
        print(f"  [{installation}/{profile}] pre-block checks: {checks}")

        scenario_paths = {}
        for scenario in scenarios:
            scenario_path = scenario_dir(installation, scenario, profile)
            (scenario_path / "runs").mkdir(parents=True, exist_ok=True)
            (scenario_path / "server").mkdir(parents=True, exist_ok=True)
            (scenario_path / "client").mkdir(parents=True, exist_ok=True)
            scenario_paths[scenario] = scenario_path

        try:
            # Step 1: switch profile, bring up proxies, 5 settling runs,
            # negotiated-group check -- all inside start_block_proxies().
            # Inside the try/finally too (not before it): if this raises
            # PARTWAY through (e.g. the negotiated-group check fails
            # after the proxy/signer containers are already up),
            # stop_block_proxies() below still runs and tears those
            # containers down -- LocalExecutor records _block_state as
            # soon as the containers start, before anything that can
            # still fail, exactly so this cleanup path has something to
            # clean up.
            start_block_proxies(executor, installation, profile, scenarios, window)

            # Step 2: per-scenario warmup, now AFTER the block's proxies
            # are up and switched (A.2's fix) -- still once per scenario
            # per block, still its own file, never mixed into runs/.
            for scenario in scenarios:
                scenario_path = scenario_paths[scenario]
                if not warmup_done(scenario_path, window):
                    run_warmup(executor, installation, scenario, profile, window, scenario_path)

            # Step 3: round-robin -- run index is the OUTER loop,
            # scenario the inner one -- run 1 of every scenario, then
            # run 2 of every scenario, ... (Decision 56, supersedes
            # Decision 40's scenario-by-scenario ordering).
            #
            # GLOBAL run numbering across the whole campaign (this
            # turn's fix -- a real bug, not just A.1's settling/meta/
            # gateway-log files): `i` here is 1..RUNS_PER_WINDOW,
            # reused identically in every window. The file's own
            # docstring says "30 runs/profile/scenario" (10/window x 3
            # windows) -- using `i` directly as the run number/filename
            # would make window 2's run01..run10 overwrite window 1's,
            # exactly the class of bug A.1 fixed for the settling files,
            # just not caught there because runs/ wasn't in scope yet.
            # `global_run_index` is what already_done()/run_one_execution()/
            # the run JSON's filename all use instead -- window 1 is
            # runs 1-10, window 2 is runs 11-20, window 3 is runs 21-30.
            for i in range(1, RUNS_PER_WINDOW + 1):
                global_run_index = (window - 1) * RUNS_PER_WINDOW + i
                for scenario in scenarios:
                    scenario_path = scenario_paths[scenario]
                    if already_done(scenario_path, global_run_index):
                        print(f"    [{installation}/{scenario}/{profile}/w{window}] run {global_run_index:02d} "
                              f"(window-local {i:02d}) already done -- resuming past it")
                        continue
                    started = datetime.now(timezone.utc).isoformat()
                    result = run_one_execution(executor, installation, scenario, profile, window, global_run_index, scenario_path)
                    (scenario_path / "runs" / f"run{global_run_index:02d}.json").write_text(json.dumps({
                        "started_at_utc": started,
                        "window": window,
                        "window_local_run_index": i,
                        # Item 2: this profile's position (0/1/2) within
                        # this window's own Latin-square row -- the
                        # covariate pilot 2's single-window data couldn't
                        # provide (profile identity and position were
                        # perfectly confounded there, Decision 89).
                        "profile_position_in_window": block_position,
                        "server": installation,
                        "client": scenario,
                        "result": result,
                    }, indent=2))
        finally:
            # Decision 56: torn down once, after the whole block's
            # round-robin is done (or abandoned) -- never per scenario.
            # A.4: no NotImplementedError catch here either -- if
            # teardown itself isn't implemented, that must abort too,
            # not be swallowed into a print.
            stop_block_proxies(executor, installation, profile, scenarios, window)


def main():
    global _CAMPAIGN_START_UTC
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                         help="Decision 62: print every SSH command SSHExecutor would run, execute nothing.")
    args = parser.parse_args()

    # Pilot item 3 (this turn): set once, here -- a restart (systemd's
    # own Restart=on-failure) re-runs main() from scratch, which
    # correctly resets the budget's own clock too, since a restarted
    # run has its own fresh real-time cost from this point forward.
    _CAMPAIGN_START_UTC = datetime.now(timezone.utc)
    write_status("starting", f"dry_run={args.dry_run}")
    config = load_config()
    inventory = load_inventory()
    # Overridable via env vars (same pattern as STATUS_FILE_PATH/
    # CAMPAIGN_STATUS_FILE) -- defaults are the real campaign's own
    # values; CAMPAIGN_INSTALLATIONS/SSH_PORT/SSH_KEY_PATH exist so
    # item-4's real-mode local rehearsal (3 containers, port 2222) can
    # run this SAME main(), unmodified, instead of a parallel
    # reimplementation of it.
    installations = os.environ.get("CAMPAIGN_INSTALLATIONS", "sa-east-1,us-east-1,ap-northeast-1").split(",")
    ssh_port = int(os.environ.get("CAMPAIGN_SSH_PORT", "22"))
    ssh_key_path = os.environ.get("CAMPAIGN_SSH_KEY_PATH", CAMPAIGN_KEY)

    # Decision 60/67: real campaign runs use SSHExecutor (real SSH/SCP
    # transport); LocalExecutor is only ever constructed directly by
    # this file's own tests, never via main() -- main() always means a
    # real remote target (or a --dry-run preview of it).
    executor = SSHExecutor(inventory, dry_run=args.dry_run, ssh_port=ssh_port, ssh_key_path=ssh_key_path)

    # Software-inventory audit (this turn): checked BEFORE anything
    # else -- a half-booted instance should abort the campaign with a
    # clear message, not a confusing failure three steps later inside
    # record_environment()/renew_safety_timers().
    verify_ready_marker(inventory, ssh_port=ssh_port, ssh_key_path=ssh_key_path)

    # Pilot item 2 (this turn): checked right after the ready marker,
    # still before any settling/execution work -- Decision 83's own
    # real finding (a co-located client silently hanging on the
    # server's public IP) would have been caught here, in seconds,
    # instead of discovered mid-settling after real AWS time was spent.
    print("==> Verifying every client can reach the server's gateway (port 443) on its own real IP...")
    verify_gateway_connectivity(inventory, ssh_port=ssh_port, ssh_key_path=ssh_key_path)

    window_times = config.get("window_start_times_utc", {})
    if not window_times:
        sys.exit(
            "campaign_schedule.json must set window_start_times_utc "
            "(e.g. {\"1\": \"2026-10-13T19:00:00Z\", \"2\": \"...\", \"3\": \"...\"}) "
            "-- 'janelas em horários parametrizados' means real timestamps, not an implicit back-to-back loop."
        )

    # Decision 53: the schedule this run actually used is copied into the
    # repo-mirroring tree too, not just read from -- so a pulled copy of
    # the data carries its own schedule alongside it.
    control_dir = DATA_ROOT / "v8" / "latency" / "_campaign-control"
    control_dir.mkdir(parents=True, exist_ok=True)
    (control_dir / "schedule.json").write_text(json.dumps(config, indent=2))

    # Item 2 (this turn): once per campaign start, per instance -- not
    # repeated per window (the environment isn't expected to change
    # mid-campaign; if it does, that's exactly the drift this is meant
    # to catch on a later audit, not something to keep re-recording).
    record_environment(inventory, ssh_port=ssh_port, ssh_key_path=ssh_key_path)

    renew_safety_timers(inventory, ssh_port=ssh_port, ssh_key_path=ssh_key_path)  # at startup, before any waiting

    # Order/warm-up turn (item 2, thesis/results/v8/DECISIONS.md): once
    # per installation, before the campaign's first block of window 1 --
    # see run_instance_warmup()'s own docstring. Must happen before
    # wait_until() below blocks for window 1's own scheduled start time,
    # not after, so the instance has already settled by the time the
    # first real block begins.
    for installation in installations:
        write_status("running", f"instance_warmup installation={installation}")
        run_instance_warmup(executor, installation)

    # Validation-gate turn (item 3, thesis/results/v8/DECISIONS.md):
    # 24 executions (1/profile x 8 scenarios), then block for an explicit
    # operator marker -- see run_validation_stage()/wait_for_operator_gate()'s
    # own docstrings. After the instance warmup (so the validation sample
    # itself isn't measuring cold-instance noise) and before window 1's
    # own wait_until(), so the gate's wait time doesn't eat into window
    # 1's scheduled start.
    write_status("running", "validation_stage")
    run_validation_stage(executor, installations)

    # ONE seed for the whole campaign (not one per window, see
    # build_latin_square_profile_orders()'s own docstring) -- read once,
    # before the window loop, so every window's row comes from the same
    # registered square.
    latin_square_seed = config.get("latin_square_seed", int(time.time()))
    profile_orders_by_window = build_latin_square_profile_orders(latin_square_seed)

    for window in range(1, WINDOWS_PER_CAMPAIGN + 1):
        start_time = window_times.get(str(window))
        if not start_time:
            sys.exit(f"campaign_schedule.json is missing window_start_times_utc['{window}'].")
        wait_until(start_time)
        renew_safety_timers(inventory, ssh_port=ssh_port, ssh_key_path=ssh_key_path)  # again right before each window
        for installation in installations:
            write_status("running", f"window={window} installation={installation}")
            run_window(executor, installation, window, latin_square_seed, profile_orders_by_window[window])
        if window == 1:
            # Validation-gate turn (item 3): same stop as the pre-window-1
            # gate above, this time over window 1's own full, real
            # dataset (every installation's own 10 runs/profile/scenario)
            # instead of the 24-execution smoke sample -- full acceptance
            # before spending window 2/3's own time/money.
            print("=== window 1 complete for every installation -- full acceptance gate before window 2 ===")
            wait_for_operator_gate("window1_acceptance")
    write_status("completed", f"windows={WINDOWS_PER_CAMPAIGN}")


if __name__ == "__main__":
    # A.4: this is the operator's ONLY safety net against a deterministic
    # failure (e.g. SSHExecutor's own NotImplementedError, still real
    # today) silently looking like success -- write_status() records the
    # failure for the operator to `cat` without tailing journalctl, and
    # `raise` (not sys.exit(0), not a bare `return`) so the process exits
    # NONZERO either way, which is what lets systemd's Restart=on-failure
    # + the campaign_run.service StartLimitBurst/StartLimitIntervalSec
    # (added this turn) actually kick in instead of looking clean.
    #
    # SingleInstanceLock() itself is OUTSIDE the write_status try/except
    # -- found live, this turn's real-mode rehearsal (item 4's overlap
    # check): a SECOND process that gets refused by the lock (Decision
    # 64's own guarantee working exactly as intended) would otherwise
    # overwrite the FIRST, legitimately-running instance's status file
    # with its own "aborted: already running" -- corrupting the one
    # thing the operator relies on to monitor the run that's actually
    # in progress. A refused second instance writes NOTHING; only a
    # process that actually acquired the lock (and is therefore the
    # one responsible for this campaign) gets to report its own
    # outcome into the shared status file.
    with SingleInstanceLock():
        try:
            main()
        except BaseException as e:
            write_status("aborted", f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
            raise
