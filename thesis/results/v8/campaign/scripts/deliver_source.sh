#!/usr/bin/env bash
# Software-inventory audit (this turn): confirmed by reading
# campaign_run.py's own remote commands literally, not assumed --
# start_block_proxies() runs, ON THE SERVER, `cd insurance-server-lambdas
# && ... python3 ../thesis/scripts/switch_crypto_profile.py ...`; every
# real execution runs, ON THE CLIENT, `python3 campaign_client_runner.py
# ...` (which imports opin_flow.py, which computes
# CERTS_DIR = BASE_DIR/"mock-service-os"/"certs" from its OWN file
# location via THESIS_DIR = SCRIPTS_DIR.parent -- i.e. it assumes the
# real repo's own relative nesting, thesis/scripts/ two levels under
# the tree root). NOTHING delivers any of insurance-server-lambdas/,
# thesis/scripts/*.py, or mock-service-os/ to ANY server or client --
# deliver_images.sh only ever shipped docker image TARBALLS. This would
# have failed the very FIRST profile switch / first execution of the
# real campaign, on every server and every client, for every profile --
# not a conditional gap like the tls_kem_proxy one, this is universal.
#
# Mirrors the real repo's own relative layout under each remote host's
# home directory (~/thesis/scripts/, ~/mock-service-os/,
# ~/insurance-server-lambdas/) specifically so opin_flow.py's existing,
# untouched path computation resolves correctly with ZERO code changes
# to that logic -- only the client invocation itself (campaign_run.py)
# gained the matching `cd ~/thesis/scripts &&` it was missing, alongside
# this script.
#
# Same operator -> control -> {servers, clients} relay as
# deliver_images.sh (server/client security groups only accept SSH from
# control's own EIP, Decision 49 -- the operator cannot reach them
# directly). Pip dependencies (thesis/scripts/requirements.txt) are
# installed on the remote side as the LAST step, after the files they
# describe are already in place.
#
# WRITTEN NOW, NOT EXECUTED -- no AWS instance reachable this turn to
# run it against (this turn's own no-AWS-mutation instruction). Requires
# the campaign Terraform already applied (reads its `inventory` output).
#
# Usage: deliver_source.sh [path to campaign.vars.example-style env file]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="$SCRIPT_DIR/../terraform"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"

if [ -n "${1:-}" ]; then
  # shellcheck source=/dev/null
  source "$1"
fi
: "${MOCKOPIN_OPERATOR_SSH_PRIVATE_KEY_FILE:?Set MOCKOPIN_OPERATOR_SSH_PRIVATE_KEY_FILE.}"

if [ -n "${MOCKOPIN_CONTROL_IP_OVERRIDE:-}" ]; then
  CONTROL_IP="$MOCKOPIN_CONTROL_IP_OVERRIDE"
else
  CONTROL_IP="$(cd "$TF_DIR" && terraform output -json inventory | python -c 'import json,sys; raw=json.load(sys.stdin); print((raw["value"] if "value" in raw else raw)["control"]["public_ip"])')"
fi
SSH_PORT="${MOCKOPIN_SSH_PORT:-22}"
SSH_OPTS=(-i "$MOCKOPIN_OPERATOR_SSH_PRIVATE_KEY_FILE" -p "$SSH_PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20 -o BatchMode=yes)
SCP_OPTS=(-i "$MOCKOPIN_OPERATOR_SSH_PRIVATE_KEY_FILE" -P "$SSH_PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20 -o BatchMode=yes)
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

echo "==> Building source tarball from $REPO_ROOT (excludes build-context/source subdirs -- images are pre-built and delivered separately, deliver_images.sh)..."
TARBALL="$WORKDIR/mockopin-source.tar.gz"
tar -C "$REPO_ROOT" -czf "$TARBALL" \
  thesis/scripts/opin_flow.py \
  thesis/scripts/latency_automation.py \
  thesis/scripts/baseline_automation.py \
  thesis/scripts/campaign_client_runner.py \
  thesis/scripts/switch_crypto_profile.py \
  thesis/scripts/requirements.txt \
  mock-service-os/certs \
  mock-service-os/ssa \
  mock-service-os/setup_ssm.sh \
  insurance-server-lambdas/docker-compose.yml \
  insurance-server-lambdas/participants.json \
  insurance-server-lambdas/software_statement.json \
  insurance-server-lambdas/mongod.conf \
  insurance-server-lambdas/pg_hba.conf \
  thesis/results/v8/campaign/scripts/campaign_run.py \
  thesis/results/v8/campaign/scripts/templates/campaign_run.service
size_bytes="$(stat -c%s "$TARBALL" 2>/dev/null || stat -f%z "$TARBALL")"
echo "    $TARBALL: $size_bytes bytes"

echo "==> Sending to control instance..."
scp "${SCP_OPTS[@]}" "$TARBALL" "ec2-user@${CONTROL_IP}:~/mockopin-source.tar.gz"

# Software-inventory audit (pilot item 1, this turn): found live -- this
# tarball reached control only to be RELAYED onward to every server/
# client below; control itself never extracted its own copy, so
# campaign_run.py (the orchestrator THIS turn's own 60 real executions
# depend on) and campaign_run.service had never actually been delivered
# to control by any script, ever, despite README.md/PILOT_RUNBOOK.md
# describing the service as "already written." Extracted here, on
# control itself, same tarball, before it's relayed onward -- mirrors
# the repo's own relative layout exactly like every other target.
echo "==> Extracting onto control itself (campaign_run.py + the orchestrator's systemd unit)..."
ssh "${SSH_OPTS[@]}" "ec2-user@${CONTROL_IP}" \
  "tar -xzf ~/mockopin-source.tar.gz -C ~/ && \
   sudo cp ~/thesis/results/v8/campaign/scripts/templates/campaign_run.service /etc/systemd/system/campaign_run.service && \
   sudo systemctl daemon-reload && \
   mkdir -p ~/campaign/scripts && \
   cp ~/thesis/results/v8/campaign/scripts/campaign_run.py ~/campaign/scripts/campaign_run.py"

echo "==> Distributing to every server and client from control, extracting into each home directory..."
ssh "${SSH_OPTS[@]}" "ec2-user@${CONTROL_IP}" env MOCKOPIN_SERVER_SSH_PORT="$SSH_PORT" bash -s <<'REMOTE'
set -euo pipefail
python3 - <<'PY'
import json, os, subprocess, sys
raw = json.load(open("/home/ec2-user/inventory.json"))
inv = raw["value"] if "value" in raw else raw
campaign_key = "/home/ec2-user/.ssh/campaign_key"
server_port = os.environ.get("MOCKOPIN_SERVER_SSH_PORT", "22")

targets = []
for name, data in inv.get("servers", {}).items():
    targets.append((f"server:{name}", data["public_ip"]))
for name, data in inv.get("clients", {}).items():
    targets.append((f"client:{name}", data["public_ip"]))

for label, ip in targets:
    print(f"  -> {label} ({ip})")
    scp_cmd = ["scp", "-i", campaign_key, "-P", server_port, "-o", "StrictHostKeyChecking=no",
               "-o", "UserKnownHostsFile=/dev/null", "-o", "BatchMode=yes",
               "/home/ec2-user/mockopin-source.tar.gz", f"ec2-user@{ip}:~/"]
    subprocess.run(scp_cmd, check=True, timeout=300)
    extract_cmd = [
        "ssh", "-i", campaign_key, "-p", server_port, "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null", "-o", "BatchMode=yes",
        f"ec2-user@{ip}",
        "tar -xzf ~/mockopin-source.tar.gz -C ~/ && rm -f ~/mockopin-source.tar.gz && "
        # --require-hashes (this turn): requirements.txt now carries a
        # real sha256 per wheel (direct AND transitive deps) --
        # --require-hashes makes pip REFUSE to install anything that
        # isn't byte-for-byte one of those exact files, instead of
        # silently accepting whatever PyPI serves for that version
        # string at install time.
        "pip3 install --user --require-hashes -r ~/thesis/scripts/requirements.txt",
    ]
    subprocess.run(extract_cmd, check=True, timeout=180)
PY
rm -f /home/ec2-user/mockopin-source.tar.gz
REMOTE

echo "==> deliver_source.sh completed."
