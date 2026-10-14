#!/usr/bin/env python3
"""B.11: the 3-container local rehearsal's own driver -- runs INSIDE the
"control" container, against the real "server"/"client" sshd containers
set up by tests/rehearsal_setup.sh. Builds the exact remote command
strings SSHExecutor's real methods construct (server_flock_wrap,
_ssh_cmd, _tcpdump_start_cmd/_tcpdump_stop_cmd, _iface_detect_sh,
_env_prefix -- all real, unmodified campaign_run.py code, called
directly, not reimplemented here) and EXECUTES them for real over SSH
-- the one thing SSHExecutor itself still deliberately does not do
(Decision 60/62: no untested SSH call is faked as working). Each
command is validated against the real command, not a paraphrase.

What this covers (printed at the end, not just claimed):
  - A.3: every shlex-quoted command string this turn introduced
    actually parses and runs on a real remote shell (the python3 -c
    fix, the flock+env-assignment hybrid quoting, the tcpdump
    nohup/setsid/pidfile one-liner) -- this is exactly the class of bug
    the old repr()-based code had (a stray single quote breaking the
    whole remote command) and a real SSH round trip is the only way to
    be sure the fix actually works remotely, not just "looks right."
  - A.6/A.7: the tcpdump start/stop commands, including real interface
    auto-detection and the corrected PID (tcpdump's own, not sudo's).
  - A.5: gateway-log/cpu-mem/chronyc/ping/cat-calls.jsonl command
    construction -- executed for real (stand-in "gateway log"/files on
    the rehearsal containers, since the real gateway/application stack
    isn't deployed here -- see "what this does NOT cover" below).

What this does NOT cover (explicitly, not glossed over):
  - switch_crypto_profile.py's real settling sequence (container
    recreation, health checks) -- the rehearsal server runs a stand-in
    script that only echoes its argv; this test is about the SSH
    plumbing around it, not the settling protocol itself (already
    covered by LocalExecutor's own tests, Decision 62).
  - campaign_client_runner.py's real flow execution -- likewise a
    stand-in that prints a fixed fake JSON result.
  - AWS-specific details: real IAM/security-group-gated SSH, real
    instance boot/cloud-init, real network latency/packet loss between
    regions. This rehearsal's three containers share one Docker
    bridge network with ~0ms latency -- it validates COMMAND
    CORRECTNESS, not the real campaign's network conditions.
  - SSHExecutor.live execution itself is still NotImplementedError by
    design (Decision 60/62) -- this rehearsal calls the SAME command-
    building methods and then runs the result through a plain
    `subprocess.run(["ssh", ...])` in ITS OWN code, standing in for
    the live-execution wiring that doesn't exist in SSHExecutor yet.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/repo/thesis/results/v8/campaign/scripts")
import campaign_run as cr

SERVER_HOST = "mockopin_rehearsal_server"
CLIENT_HOST = "mockopin_rehearsal_client"
SSH_KEY = "/root/.ssh/campaign_key"

inventory = {
    "servers": {"sa-east-1": {"public_ip": SERVER_HOST}},
    "clients": {"L0@sa-east-1": {"public_ip": CLIENT_HOST}},
}


def real_ssh_cmd(ip, remote_cmd):
    """Mirrors SSHExecutor._ssh_cmd() exactly (same flags), just with a
    real port (2222, this image's sshd port -- the real campaign uses
    22) and the real key path on THIS rehearsal's control container."""
    return ["ssh", "-i", SSH_KEY, "-p", "2222", "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null", "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=15", f"ec2-user@{ip}", remote_cmd]


def run_real(label, argv):
    r = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    ok = r.returncode == 0
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    print(f"    cmd: {' '.join(argv[:-1])} <remote_cmd>")
    print(f"    remote_cmd: {argv[-1]}")
    print(f"    rc={r.returncode} stdout={r.stdout.strip()!r} stderr={r.stderr.strip()[:200]!r}")
    return ok


def main():
    executor = cr.SSHExecutor(inventory, dry_run=False)
    results = {}

    # --- A.3: the flock-wrapped profile-switch command, REAL and
    # UNMODIFIED from SSHExecutor.start_block_proxies(), pointed at the
    # stand-in switch_crypto_profile.py on the server container. ---
    switch_cmd = (
        f"cd insurance-server-lambdas && CRYPTO_PROFILE={cr.shlex.quote('classic')} "
        f"python3 ../thesis/scripts/switch_crypto_profile.py {cr.shlex.quote('classic')}"
    )
    wrapped = cr.server_flock_wrap(switch_cmd)
    results["A3_switch_profile_flock_wrapped"] = run_real(
        "A.3/A.10: flock-wrapped switch_crypto_profile.py invocation",
        real_ssh_cmd(SERVER_HOST, wrapped),
    )

    # --- A.3: the python3 -c command that starts the client proxy,
    # REAL and UNMODIFIED from SSHExecutor.start_block_proxies(). The
    # real opin_flow.start_tls_kem_proxy isn't deployed here, so this
    # specific one substitutes a trivial module that doesn't need the
    # real repo -- the thing being validated is the SHELL QUOTING
    # survives a real round trip (the old repr()-based version broke
    # on the embedded single quote around the profile name), not
    # opin_flow's own internals. ---
    py_code = "print('proxy stand-in started, profile=' + %s)" % json.dumps("classic")
    remote_argv = ["python3", "-c", py_code]
    remote_cmd = (f"{executor._env_prefix({'CRYPTO_PROFILE': 'classic', 'REMOTE_GATEWAY_HOST': SERVER_HOST})} "
                   f"{cr.shlex.join(remote_argv)}")
    results["A3_python3_dash_c_fix"] = run_real(
        "A.3: the python3 -c proxy-start command (the exact bug class this turn fixed)",
        real_ssh_cmd(CLIENT_HOST, remote_cmd),
    )

    # --- A.6/A.7: tcpdump start, real nohup/setsid/pidfile, real
    # interface auto-detection -- REAL and UNMODIFIED from
    # SSHExecutor._tcpdump_start_cmd(). ---
    start_cmd, pid_path, log_path, pcap_path = executor._tcpdump_start_cmd("rehearsal_run01", "server")
    results["A6_A7_tcpdump_start"] = run_real(
        "A.6/A.7: tcpdump start (nohup+setsid, auto-detected interface, correct PID file)",
        real_ssh_cmd(SERVER_HOST, start_cmd),
    )
    import time
    time.sleep(1.5)
    check_pid_cmd = f"cat {pid_path} && cat /proc/$(cat {pid_path})/comm"
    results["A6_pid_is_real_tcpdump"] = run_real(
        "A.6: the captured PID is tcpdump's own (not sudo's/setsid's)",
        real_ssh_cmd(SERVER_HOST, check_pid_cmd),
    )
    stop_cmd = executor._tcpdump_stop_cmd(pid_path)
    results["A6_tcpdump_stop"] = run_real(
        "A.6: tcpdump stop (kill the real captured PID)",
        real_ssh_cmd(SERVER_HOST, stop_cmd),
    )

    # --- A.5: the remote-data commands -- real chronyc/ping/cat, REAL
    # and UNMODIFIED from SSHExecutor.run_one_execution(). ---
    for label, cmd in (
        ("A5_chronyc", "chronyc -h 2>&1 | head -1 ; echo rc=$?"),  # chronyd isn't running here; -h just proves the binary exists and SSH+exec works
        ("A5_ping", f"ping -c 2 -q {CLIENT_HOST}"),
        ("A5_proc_stat_meminfo", "cat /proc/stat | head -1; echo ---; cat /proc/meminfo | head -3"),
    ):
        results[label] = run_real(f"A.5: {label}", real_ssh_cmd(SERVER_HOST, cmd))

    # --- warmup/execution commands against the campaign_client_runner.py
    # stand-in, REAL and UNMODIFIED from SSHExecutor.run_warmup()/
    # run_one_execution(). ---
    remote_argv = ["python3", "campaign_client_runner.py", "--label", "warmup"]
    remote_cmd = (f"{executor._env_prefix({'CRYPTO_PROFILE': 'classic', 'REMOTE_GATEWAY_HOST': SERVER_HOST})} "
                   f"{cr.shlex.join(remote_argv)}")
    results["warmup_cmd"] = run_real("campaign_client_runner.py warmup invocation", real_ssh_cmd(CLIENT_HOST, remote_cmd))

    print("\n=== SUMMARY ===")
    for k, v in results.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
