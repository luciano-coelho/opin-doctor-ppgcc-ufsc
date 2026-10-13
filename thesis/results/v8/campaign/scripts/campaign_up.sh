#!/usr/bin/env bash
# Decision 49: brings up the Phase 4 campaign's 10-instance topology.
#
# - Discovers the operator's own public IP fresh (never trusts a stale
#   value) and passes it to Terraform as an environment variable --
#   never written to any file this repository tracks.
# - Runs `terraform apply` -- ONLY to be invoked with the author present,
#   same standing rule as every other apply in this project. This script
#   does not enforce that itself (it can't know who's at the keyboard);
#   it is a procedural rule, not a technical one.
# - Copies the campaign-exclusive SSH private key (Terraform-generated,
#   Decision 49) onto the control instance -- never writes it to any
#   file this repository tracks, and shreds its own local temp copy
#   immediately after the scp.
# - Copies the inventory (hosts/IPs/roles) onto the control instance.
# - Verifies SSH connectivity to every host (proxied through control)
#   and chrony's sync status on every host -- fails loudly (non-zero
#   exit, clear message) on the first mismatch, does not continue past
#   a failure silently.
#
# Usage:
#   campaign_up.sh [vars file]                      -- normal apply (full flow below)
#   campaign_up.sh [vars file] --update-operator-ip  -- re-discovers the operator's
#       IP and re-applies ONLY the control instance's SSH ingress rule
#       (Decision 52) -- for when the operator's IP changed since the last
#       apply and a full re-apply isn't needed or wanted.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="$SCRIPT_DIR/../terraform"

VARS_FILE="${1:-}"
MODE="${2:-}"
if [ -n "$VARS_FILE" ]; then
  # shellcheck source=/dev/null
  source "$VARS_FILE"
fi

: "${MOCKOPIN_AWS_PROFILE:=mockopin-pqc}"
: "${MOCKOPIN_OPERATOR_SSH_PUBLIC_KEY_FILE:?Set MOCKOPIN_OPERATOR_SSH_PUBLIC_KEY_FILE (the operator's existing discovery key's .pub file).}"
: "${MOCKOPIN_OPERATOR_SSH_PRIVATE_KEY_FILE:?Set MOCKOPIN_OPERATOR_SSH_PRIVATE_KEY_FILE (private half of the same key pair, to reach the control instance directly).}"
: "${MOCKOPIN_SERVER_CLIENT_INSTANCE_TYPE:?Set MOCKOPIN_SERVER_CLIENT_INSTANCE_TYPE -- no default on purpose (Decision 52): Decision 43's launch test hasn't resolved this yet, and a silent placeholder default could get used by accident.}"

export AWS_PROFILE="$MOCKOPIN_AWS_PROFILE"

echo "==> Discovering operator public IP (fresh, not cached)..."
OPERATOR_IP="$(curl -s https://checkip.amazonaws.com)"
if [ -z "$OPERATOR_IP" ]; then
  echo "FATAL: could not discover operator IP -- refusing to apply with a stale/missing value." >&2
  exit 1
fi
echo "    operator IP: ${OPERATOR_IP}/32"
export TF_VAR_operator_ip_cidr="${OPERATOR_IP}/32"
export TF_VAR_operator_ssh_public_key="$(cat "$MOCKOPIN_OPERATOR_SSH_PUBLIC_KEY_FILE")"
export TF_VAR_server_client_instance_type="$MOCKOPIN_SERVER_CLIENT_INSTANCE_TYPE"

if [ "$MODE" = "--update-operator-ip" ]; then
  echo "==> --update-operator-ip: re-applying ONLY the control instance's security group."
  (cd "$TF_DIR" && terraform init -input=false)
  (cd "$TF_DIR" && terraform apply -input=false -auto-approve -target=module.control.aws_security_group.this)
  echo "==> Done -- control instance now accepts SSH from ${OPERATOR_IP}/32 only."
  exit 0
fi

echo "==> terraform init"
(cd "$TF_DIR" && terraform init -input=false)

echo
echo "==> BEFORE APPLYING: confirm you have personally checked, in the AWS"
echo "    console, just now -- not from memory -- both of the following"
echo "    (Decision 44: this project's restricted IAM profile cannot read"
echo "    either value via the API, so this has to be a human check):"
echo "      1. The billing budget alert is configured and has not already fired."
echo "      2. The remaining Free Plan credit balance and its expiration date."
read -r -p "    Type 'checked' to confirm both: " BUDGET_CONFIRM
if [ "$BUDGET_CONFIRM" != "checked" ]; then
  echo "Aborted -- budget/credit confirmation not given." >&2
  exit 1
fi

echo "==> terraform apply -- REQUIRES THE AUTHOR PRESENT. Ctrl-C now if not."
read -r -p "    Type 'apply' to continue: " CONFIRM
if [ "$CONFIRM" != "apply" ]; then
  echo "Aborted -- confirmation not given." >&2
  exit 1
fi
(cd "$TF_DIR" && terraform apply -input=false -auto-approve)

echo "==> Extracting outputs..."
CONTROL_IP="$(cd "$TF_DIR" && terraform output -json inventory | python -c 'import json,sys; print(json.load(sys.stdin)["value"]["control"]["public_ip"])')"
TMP_KEY="$(mktemp)"
TMP_INVENTORY="$(mktemp)"
trap 'shred -u "$TMP_KEY" 2>/dev/null || rm -f "$TMP_KEY"; rm -f "$TMP_INVENTORY"' EXIT

(cd "$TF_DIR" && terraform output -raw campaign_private_key) > "$TMP_KEY"
chmod 600 "$TMP_KEY"
(cd "$TF_DIR" && terraform output -json inventory) > "$TMP_INVENTORY"

SSH_OPTS_OPERATOR=(-i "$MOCKOPIN_OPERATOR_SSH_PRIVATE_KEY_FILE" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20 -o BatchMode=yes)

echo "==> Building the campaign schedule (window start times, fixed UTC clock times, parameterized)..."
: "${MOCKOPIN_WINDOW1_START_UTC:=}"
: "${MOCKOPIN_WINDOW2_START_UTC:=}"
: "${MOCKOPIN_WINDOW3_START_UTC:=}"
if [ -z "$MOCKOPIN_WINDOW1_START_UTC" ]; then
  # Default (Decision 52): fixed UTC clock times, not a relative offset --
  # 19:00 today (or tomorrow, if 19:00 UTC has already passed today),
  # 03:00 the day after that, 11:00 the same day as window 2. Always
  # overridable via MOCKOPIN_WINDOW{1,2,3}_START_UTC in the vars file.
  TODAY="$(date -u +%Y-%m-%d)"
  NOW_HHMM="$(date -u +%H%M)"
  if [ "$NOW_HHMM" -lt "1900" ]; then
    W1_DATE="$TODAY"
  else
    W1_DATE="$(date -u -d "$TODAY +1 day" +%Y-%m-%d)"
  fi
  W2_DATE="$(date -u -d "$W1_DATE +1 day" +%Y-%m-%d)"
  MOCKOPIN_WINDOW1_START_UTC="${W1_DATE}T19:00:00Z"
  MOCKOPIN_WINDOW2_START_UTC="${W2_DATE}T03:00:00Z"
  MOCKOPIN_WINDOW3_START_UTC="${W2_DATE}T11:00:00Z"
fi
TMP_SCHEDULE="$(mktemp)"
python - "$MOCKOPIN_WINDOW1_START_UTC" "$MOCKOPIN_WINDOW2_START_UTC" "$MOCKOPIN_WINDOW3_START_UTC" > "$TMP_SCHEDULE" <<'PY'
import json, random, sys
w1, w2, w3 = sys.argv[1:4]
print(json.dumps({
    "window_start_times_utc": {"1": w1, "2": w2, "3": w3},
    "window_seeds": {str(w): random.SystemRandom().randrange(2**31) for w in (1, 2, 3)},
}, indent=2))
PY
echo "    window 1: $MOCKOPIN_WINDOW1_START_UTC"
echo "    window 2: $MOCKOPIN_WINDOW2_START_UTC"
echo "    window 3: $MOCKOPIN_WINDOW3_START_UTC"

echo "==> Copying the campaign key, inventory, and schedule onto the control instance (${CONTROL_IP})..."
scp "${SSH_OPTS_OPERATOR[@]}" "$TMP_KEY" "ec2-user@${CONTROL_IP}:~/.ssh/campaign_key"
scp "${SSH_OPTS_OPERATOR[@]}" "$TMP_INVENTORY" "ec2-user@${CONTROL_IP}:~/inventory.json"
scp "${SSH_OPTS_OPERATOR[@]}" "$TMP_SCHEDULE" "ec2-user@${CONTROL_IP}:~/campaign_schedule.json"
ssh "${SSH_OPTS_OPERATOR[@]}" "ec2-user@${CONTROL_IP}" "chmod 600 ~/.ssh/campaign_key"
rm -f "$TMP_SCHEDULE"

echo "==> Verifying SSH connectivity and clock sync on every host (proxied through control)..."
ssh "${SSH_OPTS_OPERATOR[@]}" "ec2-user@${CONTROL_IP}" bash -s <<'REMOTE'
set -euo pipefail
python3 - <<'PY'
import json, subprocess, sys
raw = json.load(open("/home/ec2-user/inventory.json"))
inv = raw["value"] if "value" in raw else raw
hosts = []
for role, entry in inv.items():
    if role == "control":
        continue
    if role == "servers":
        for name, data in entry.items():
            hosts.append((f"server:{name}", data["public_ip"]))
    if role == "clients":
        for name, data in entry.items():
            hosts.append((f"client:{name}", data["public_ip"]))

failed = False
for label, ip in hosts:
    ssh_cmd = [
        "ssh", "-i", "/home/ec2-user/.ssh/campaign_key",
        "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=15", "-o", "BatchMode=yes",
        f"ec2-user@{ip}", "chronyc tracking | head -5"
    ]
    r = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        print(f"FATAL: {label} ({ip}) unreachable or chrony not ready: {r.stderr.strip()}", file=sys.stderr)
        failed = True
    else:
        print(f"OK: {label} ({ip})")
        print(r.stdout)
if failed:
    sys.exit(1)
PY
REMOTE

echo "==> campaign_up.sh completed: 10 instances up, connectivity and clock sync verified."
