#!/usr/bin/env bash
# Decision 49/53: idempotent pull of campaign data from the control
# instance to the operator's own machine, with a sha256 manifest
# verified on both ends -- a partial/corrupted transfer is caught here,
# not discovered later while writing the thesis.
#
# Decision 53: pulls into $DEST/v8/..., mirroring the repository's own
# `thesis/results/v8/` subtree exactly (campaign_run.py writes into
# /home/ec2-user/campaign-data/v8/... using that same relative layout) --
# so the sha256 manifest's paths ("v8/latency/experiment1 - Classic/
# sa-east-1/L0/runs/run01.json", etc.) are the SAME relative paths the
# repository itself uses, not a separate ad-hoc scheme requiring
# translation.
#
# Safe to re-run: rsync only transfers new/changed files, and the
# manifest is regenerated fresh on the control instance every time, so a
# second run after a first interrupted one picks up exactly what's
# missing.
#
# Usage: campaign_pull.sh [path to campaign.vars.example-style env file] [local destination dir]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="$SCRIPT_DIR/../terraform"

if [ -n "${1:-}" ]; then
  # shellcheck source=/dev/null
  source "$1"
fi
: "${MOCKOPIN_OPERATOR_SSH_PRIVATE_KEY_FILE:?Set MOCKOPIN_OPERATOR_SSH_PRIVATE_KEY_FILE.}"
DEST="${2:-./campaign-data-pulled}"
mkdir -p "$DEST"

CONTROL_IP="$(cd "$TF_DIR" && terraform output -json inventory | python -c 'import json,sys; raw=json.load(sys.stdin); print((raw["value"] if "value" in raw else raw)["control"]["public_ip"])')"
SSH_OPTS=(-i "$MOCKOPIN_OPERATOR_SSH_PRIVATE_KEY_FILE" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20 -o BatchMode=yes)

echo "==> Regenerating the sha256 manifest on the control instance (${CONTROL_IP})..."
ssh "${SSH_OPTS[@]}" "ec2-user@${CONTROL_IP}" \
  "cd /home/ec2-user/campaign-data && find v8 -type f -print0 | xargs -0 sha256sum > /home/ec2-user/campaign-data.sha256"

echo "==> rsync (idempotent -- only new/changed files transfer)..."
rsync -avz -e "ssh ${SSH_OPTS[*]}" \
  "ec2-user@${CONTROL_IP}:/home/ec2-user/campaign-data/v8/" "$DEST/v8/"
rsync -avz -e "ssh ${SSH_OPTS[*]}" \
  "ec2-user@${CONTROL_IP}:/home/ec2-user/campaign-data.sha256" "$DEST/campaign-data.sha256"

echo "==> Verifying the manifest against what actually landed locally..."
(
  cd "$DEST"
  # The manifest's paths are already relative ("v8/...", generated with
  # `cd campaign-data && find v8 ...` above) -- they match this pulled
  # copy's own layout directly, no path rewriting needed.
  if sha256sum -c campaign-data.sha256 --quiet; then
    echo "OK: every pulled file matches its sha256."
  else
    echo "FATAL: at least one pulled file does not match its manifest hash -- re-run this script, do not trust this copy." >&2
    exit 1
  fi
)

date -u +"%Y-%m-%dT%H:%M:%SZ" > "$DEST/.pull-verified"
echo "==> campaign_pull.sh completed, verified copy at: $DEST"
echo "    (.pull-verified written -- campaign_down.sh checks for this before it will destroy anything)"
