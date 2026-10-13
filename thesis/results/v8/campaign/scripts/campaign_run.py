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
new seams for that lifecycle (as unimplemented as `run_one_execution()`
itself, same reasoning).

Effect on total time: none -- same number of runs, same number of
profile switches (9/window, unchanged by Decision 40's math), same
per-run durations; only the ORDER changes. Effect on orchestrator
complexity: real, not cosmetic -- every one of a block's scenario
proxies must be started before round-robin begins and kept alive
(tracked, health-checked) for the entire block instead of one at a
time, and the run loop itself inverts (scenario the inner loop, run
index the outer one).

Deliberately NOT implemented here (same reasoning as before -- a call
to a mechanism that doesn't fully exist yet would be fabricated, not
prepared):
  - `run_one_execution()`: the real per-run invocation. Decision 53's
    spec (not an implementation): it must call the SAME functions the
    local lab already uses for T_fluxo -- the monotonic clock, discarded
    retry-attempt time excluded from the timed window, a whole-execution
    retry marked and recorded (not silently absorbed), warmup kept
    separate -- exactly `latency_automation.py`'s own existing
    architecture (Decision 26 already confirmed it starts the proxy
    once per scenario, before the timed window, specifically to avoid
    this kind of contamination). This function's job, once implemented,
    is to invoke that existing machinery over SSH against the right
    client instance with `REMOTE_GATEWAY_HOST` set -- not to reimplement
    T_fluxo measurement from scratch.
  - `run_warmup()`: same seam, for the settling runs (Decision 4's 5
    discarded flows), writing `run00_warmup.json` once per block.
  - `start_block_proxies()`/`stop_block_proxies()`: Decision 56's new
    seam -- starts every scenario's client-side proxy for a block before
    round-robin begins, stops them only after the whole block completes.
"""
import json
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

CONFIG_PATH = Path("/home/ec2-user/campaign_schedule.json")
INVENTORY_PATH = Path("/home/ec2-user/inventory.json")
CAMPAIGN_KEY = "/home/ec2-user/.ssh/campaign_key"
DATA_ROOT = Path("/home/ec2-user/campaign-data")  # mirrors the repo's v8/ subtree, Decision 53
RUNS_PER_WINDOW = 10
WINDOWS_PER_CAMPAIGN = 3
PROFILES = ["classic", "pqc", "hybrid"]
PROFILE_TO_EXPERIMENT_DIR = {"classic": "experiment1 - Classic", "pqc": "experiment2 - PQC", "hybrid": "experiment3 - Hybrid"}
SAFETY_TIMER_RENEW_HOURS = 48  # Decision 49 -- must match the Terraform default

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


def all_server_client_ips(inventory):
    ips = []
    for name, data in inventory.get("servers", {}).items():
        ips.append((f"server:{name}", data["public_ip"]))
    for name, data in inventory.get("clients", {}).items():
        ips.append((f"client:{name}", data["public_ip"]))
    return ips


def renew_safety_timers(inventory):
    """Decision 49: the orchestrator renews every server/client's
    safety-timer deadline -- the control instance is deliberately
    exempt (no timer to renew there). Called at startup and before each
    window so a multi-day campaign never trips the default 48h timer
    while legitimately still running."""
    deadline_cmd = (
        f"sudo mkdir -p /etc/mockopin-campaign && "
        f"date -d '+{SAFETY_TIMER_RENEW_HOURS} hours' +%s | sudo tee /etc/mockopin-campaign/deadline >/dev/null"
    )
    for label, ip in all_server_client_ips(inventory):
        r = subprocess.run(
            ["ssh", "-i", CAMPAIGN_KEY, "-o", "StrictHostKeyChecking=no",
             "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=15",
             "-o", "BatchMode=yes", f"ec2-user@{ip}", deadline_cmd],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            print(f"WARNING: could not renew safety timer on {label} ({ip}): {r.stderr.strip()}", file=sys.stderr)
        else:
            print(f"Renewed safety timer on {label} ({ip}): +{SAFETY_TIMER_RENEW_HOURS}h")


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


def pre_block_checks(installation, profile):
    """Decision 49/53: at the start of every profile block, verify the
    negotiated key-exchange group, the loaded image's ID (Decision 54 --
    image ID, not a registry digest, since image delivery is a local
    tarball load, not a registry pull), and disk space -- before
    spending any run on a block that's already wrong."""
    checks = {}
    df = subprocess.run(["df", "-h", "/"], capture_output=True, text=True)
    checks["disk_space_df_output"] = df.stdout.strip()
    checks["image_id"] = "NOT YET AVAILABLE -- Decision 50/54 not implemented"
    checks["negotiated_group"] = "NOT YET AVAILABLE -- Decision 45/51 wiring not implemented"
    return checks


def run_warmup(installation, scenario, profile, window):
    """Decision 4's settling protocol (5 discarded flows), run once per
    block, written to its own file -- never mixed into runs/'s
    numbering. NOT IMPLEMENTED: same reasoning as run_one_execution()."""
    raise NotImplementedError(
        "run_warmup: depends on the same SSH-to-client wiring as "
        "run_one_execution() -- not yet built."
    )


def start_block_proxies(installation, profile, scenarios):
    """Decision 56: round-robin means every scenario's client-side proxy
    in this block must be up BEFORE round-robin begins, not started one
    at a time as each scenario's turn comes up -- each proxy stays alive
    for the whole block, torn down only by stop_block_proxies() after
    the round-robin loop finishes. NOT IMPLEMENTED: same reasoning as
    run_one_execution() -- depends on the same SSH-to-client wiring."""
    raise NotImplementedError(
        "start_block_proxies: depends on the same SSH-to-client wiring as "
        "run_one_execution() -- not yet built."
    )


def stop_block_proxies(installation, profile, scenarios):
    """Counterpart to start_block_proxies() -- torn down once, after
    every scenario's 30 round-robin'd runs in this block are done, not
    per-scenario. NOT IMPLEMENTED, same reasoning."""
    raise NotImplementedError(
        "stop_block_proxies: depends on the same SSH-to-client wiring as "
        "run_one_execution() -- not yet built."
    )


def run_one_execution(installation, scenario, profile, window, run_index):
    """The single seam where a real execution gets triggered.

    Specification (Decision 53), not an implementation: this must call
    the SAME functions the local lab already uses for T_fluxo --
    `time.monotonic()` (never wall-clock), discarded-retry-attempt time
    excluded from the timed window, a whole-execution retry marked and
    recorded in the run's own JSON (not silently retried and forgotten),
    warmup handled by `run_warmup()` above, never inline here. This
    means invoking `opin_flow.py`/`latency_automation.py`'s existing
    machinery over SSH with `REMOTE_GATEWAY_HOST` set, not
    reimplementing T_fluxo measurement from scratch -- the lab's own
    timing code is already correct (Decision 26) and should be reused
    as-is, not duplicated.
    """
    raise NotImplementedError(
        "run_one_execution: depends on opin_flow.py's REMOTE_GATEWAY_HOST "
        "(Decision 51, implemented as a diff, not yet committed/approved) "
        "and on the SSH-to-client wiring to actually invoke it -- not yet built."
    )


def run_window(installation, window, seed):
    rng = random.Random(seed)
    profile_order = PROFILES[:]
    rng.shuffle(profile_order)
    scenarios = SCENARIO_ROTATION[installation][window]
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
        "seed": seed,
        "profile_order": profile_order,
        "scenario_rotation": scenarios,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    }, indent=2))

    for profile in profile_order:
        checks = pre_block_checks(installation, profile)
        print(f"  [{installation}/{profile}] pre-block checks: {checks}")

        scenario_paths = {}
        for scenario in scenarios:
            scenario_path = scenario_dir(installation, scenario, profile)
            (scenario_path / "runs").mkdir(parents=True, exist_ok=True)
            (scenario_path / "server").mkdir(parents=True, exist_ok=True)
            (scenario_path / "client").mkdir(parents=True, exist_ok=True)
            scenario_paths[scenario] = scenario_path

            # Decision 56: warmup still happens once per scenario per
            # block, but upfront now -- before round-robin starts, not
            # interleaved into it.
            if not warmup_done(scenario_path, window):
                try:
                    run_warmup(installation, scenario, profile, window)
                except NotImplementedError as e:
                    print(f"    [{installation}/{scenario}/{profile}/w{window}] warmup: {e}", file=sys.stderr)
                    return  # stop this window cleanly -- nothing fabricated, nothing half-written

        # Decision 56: every scenario's proxy for this block starts here,
        # once, and stays up for the whole round-robin loop below -- not
        # started/stopped per scenario the way sequential execution could.
        try:
            start_block_proxies(installation, profile, scenarios)
        except NotImplementedError as e:
            print(f"    [{installation}/{profile}/w{window}] start_block_proxies: {e}", file=sys.stderr)
            return

        # Round-robin: run index is the OUTER loop, scenario the inner
        # one -- run 1 of every scenario, then run 2 of every scenario,
        # ... (Decision 56, supersedes Decision 40's scenario-by-scenario
        # ordering).
        try:
            for i in range(1, RUNS_PER_WINDOW + 1):
                for scenario in scenarios:
                    scenario_path = scenario_paths[scenario]
                    if already_done(scenario_path, i):
                        print(f"    [{installation}/{scenario}/{profile}/w{window}] run {i:02d} already done -- resuming past it")
                        continue
                    started = datetime.now(timezone.utc).isoformat()
                    result = run_one_execution(installation, scenario, profile, window, i)
                    (scenario_path / "runs" / f"run{i:02d}.json").write_text(json.dumps({
                        "started_at_utc": started,
                        "window": window,
                        "server": installation,
                        "client": scenario,
                        "result": result,
                    }, indent=2))
        except NotImplementedError as e:
            print(f"    [{installation}/{profile}/w{window}] round-robin loop: {e}", file=sys.stderr)
            return
        finally:
            # Decision 56: torn down once, after the whole block's
            # round-robin is done (or abandoned) -- never per scenario.
            try:
                stop_block_proxies(installation, profile, scenarios)
            except NotImplementedError as e:
                print(f"    [{installation}/{profile}/w{window}] stop_block_proxies: {e}", file=sys.stderr)


def main():
    config = load_config()
    inventory = load_inventory()
    installations = ["sa-east-1", "us-east-1", "ap-northeast-1"]

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

    renew_safety_timers(inventory)  # at startup, before any waiting
    for window in range(1, WINDOWS_PER_CAMPAIGN + 1):
        start_time = window_times.get(str(window))
        if not start_time:
            sys.exit(f"campaign_schedule.json is missing window_start_times_utc['{window}'].")
        wait_until(start_time)
        renew_safety_timers(inventory)  # again right before each window -- cheap, keeps a multi-day campaign safe
        seed = config.get("window_seeds", {}).get(str(window), int(time.time()))
        for installation in installations:
            run_window(installation, window, seed)


if __name__ == "__main__":
    main()
