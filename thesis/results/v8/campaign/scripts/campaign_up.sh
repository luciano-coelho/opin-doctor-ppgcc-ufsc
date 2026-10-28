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
#   campaign_up.sh [vars file] --allow-destructive   -- Decision 93 (real
#       incident, 2026-10-28: a stale MOCKOPIN_ENABLED_CLIENT_SCENARIOS
#       left set from a previous, smaller pilot made this script's own
#       terraform apply destroy 38 real resources -- 8 full instances --
#       it had no business touching). Without this flag, the script now
#       runs `terraform plan` FIRST, prints the effective variables and
#       the add/change/destroy summary, and ABORTS before ever calling
#       `apply` if the plan shows any destroy (a replace counts as both
#       an add and a destroy in that count, so it's covered too) or if
#       MOCKOPIN_ENABLED_CLIENT_SCENARIOS is set to a strict subset of
#       the full 8-scenario topology. Pass this flag only when a
#       destroy/replace or a scoped-down topology is the actual intent,
#       reviewed by a human first -- never as a default, never to make
#       an abort "go away."
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="$SCRIPT_DIR/../terraform"

# Decision 93: the exact failure mode found live -- `python3` resolved to
# nothing on this operator's PATH, and a bare `python` resolved to the
# Windows Store's own stub (exists on PATH, "succeeds" at being found,
# fails at being Python) rather than a real interpreter. `command -v`
# alone would NOT have caught this -- it only checks PATH presence, not
# whether the candidate actually runs -- so this probes execution too.
resolve_python() {
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "print(1)" >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}
PYTHON_BIN="$(resolve_python)" || {
  echo "FATAL: no working python3/python interpreter found on PATH (tried: python3, python) -- needed for this script's own JSON/redaction helpers. Fix PATH before retrying; this is not something to work around." >&2
  exit 1
}

ALLOW_DESTRUCTIVE=0
ARGS=()
for a in "$@"; do
  if [ "$a" = "--allow-destructive" ]; then
    ALLOW_DESTRUCTIVE=1
  else
    ARGS+=("$a")
  fi
done
VARS_FILE="${ARGS[0]:-}"
MODE="${ARGS[1]:-}"
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
echo "    operator IP: <redacted -- standing rule, never printed in full>"
export TF_VAR_operator_ip_cidr="${OPERATOR_IP}/32"
export TF_VAR_operator_ssh_public_key="$(cat "$MOCKOPIN_OPERATOR_SSH_PUBLIC_KEY_FILE")"
export TF_VAR_server_client_instance_type="$MOCKOPIN_SERVER_CLIENT_INSTANCE_TYPE"

# Decision 93: the full 8-scenario set, for the reduction check below --
# must be kept in sync with terraform/variables.tf's own default list
# by hand (no single source of truth to read it from at this layer
# without invoking terraform first, which this runs before init).
FULL_SCENARIOS="L0@sa-east-1 L123@sa-east-1 L219@sa-east-1 L325@sa-east-1 L0@us-east-1 L14@us-east-1 L0@ap-northeast-1 L30@ap-northeast-1"

# Pilot runbook: a space-separated subset of scenario keys (e.g.
# "L0@sa-east-1 L325@sa-east-1") lets this SAME script bring up a
# smaller topology instead of the full 8-scenario one -- unset (the
# normal case) means the variable's own Terraform default (all 8)
# applies, unchanged. Decision 93 (real incident): this is EXACTLY the
# variable a stale vars file left set, which turned the next
# "full-topology" apply into an unintended destroy of the other 6
# scenarios' worth of resources -- see the reduction check right below.
if [ -n "${MOCKOPIN_ENABLED_CLIENT_SCENARIOS:-}" ]; then
  TF_VAR_enabled_client_scenarios="$("$PYTHON_BIN" - "$MOCKOPIN_ENABLED_CLIENT_SCENARIOS" <<'PY'
import json, sys
print(json.dumps(sys.argv[1].split()))
PY
)"
  export TF_VAR_enabled_client_scenarios
  echo "==> enabled_client_scenarios override: $TF_VAR_enabled_client_scenarios"

  # Decision 93: is this a REDUCTION from the full topology? Compare as
  # sets, not strings (order/whitespace shouldn't matter). A reduction
  # is exactly the condition that destroyed real infrastructure last
  # time, unreviewed -- require the same explicit flag a destructive
  # plan requires, not a second, differently-named one.
  REDUCTION_CHECK="$("$PYTHON_BIN" - "$MOCKOPIN_ENABLED_CLIENT_SCENARIOS" "$FULL_SCENARIOS" <<'PY'
import sys
scoped = set(sys.argv[1].split())
full = set(sys.argv[2].split())
print("REDUCED" if scoped < full else "FULL_OR_SUPERSET")
PY
)"
  if [ "$REDUCTION_CHECK" = "REDUCED" ] && [ "$ALLOW_DESTRUCTIVE" != "1" ]; then
    echo "FATAL: MOCKOPIN_ENABLED_CLIENT_SCENARIOS (\"$MOCKOPIN_ENABLED_CLIENT_SCENARIOS\") is a strict subset of the full 8-scenario topology." >&2
    echo "        If this apply is meant to run against an already-FULLER topology, this would destroy whatever isn't in that subset (Decision 93 -- this exact mistake already happened once)." >&2
    echo "        Re-run with --allow-destructive only after a human has reviewed this on purpose." >&2
    exit 1
  fi
fi

if [ "$MODE" = "--update-operator-ip" ]; then
  echo "==> --update-operator-ip: re-applying ONLY the control instance's security group."
  (cd "$TF_DIR" && terraform init -input=false)
  (cd "$TF_DIR" && terraform apply -input=false -auto-approve -target=module.control.aws_security_group.this) 2>&1 | "$PYTHON_BIN" "$SCRIPT_DIR/redact_aws_errors.py"
  echo "==> Done -- control instance now accepts SSH from the operator's (redacted) IP only."
  exit 0
fi

echo "==> terraform init"
(cd "$TF_DIR" && terraform init -input=false)

echo
echo "==> Effective variables for this apply (Decision 93 -- always shown,"
echo "    never assumed from memory):"
echo "    server_client_instance_type = $MOCKOPIN_SERVER_CLIENT_INSTANCE_TYPE"
if [ -n "${MOCKOPIN_ENABLED_CLIENT_SCENARIOS:-}" ]; then
  echo "    enabled_client_scenarios    = $MOCKOPIN_ENABLED_CLIENT_SCENARIOS  (SCOPED, not the full 8)"
else
  echo "    enabled_client_scenarios    = (unset -- Terraform default, full 8-scenario topology)"
fi
echo "    operator_ip_cidr            = <redacted>"
echo "    operator_ssh_public_key     = <redacted, from $MOCKOPIN_OPERATOR_SSH_PUBLIC_KEY_FILE>"

echo
echo "==> terraform plan (Decision 93 -- always run and checked BEFORE any apply,"
echo "    never skipped): aborting below if it shows any destroy/replace, unless"
echo "    --allow-destructive was given."
PLAN_OUT="$(mktemp)"
(cd "$TF_DIR" && terraform plan -input=false -no-color \
  -var="operator_ip_cidr=$TF_VAR_operator_ip_cidr" \
  -var="operator_ssh_public_key=$TF_VAR_operator_ssh_public_key" \
  -var="server_client_instance_type=$TF_VAR_server_client_instance_type" \
  ${TF_VAR_enabled_client_scenarios+-var="enabled_client_scenarios=$TF_VAR_enabled_client_scenarios"}) \
  > "$PLAN_OUT" 2>&1 || { "$PYTHON_BIN" "$SCRIPT_DIR/redact_aws_errors.py" < "$PLAN_OUT"; rm -f "$PLAN_OUT"; echo "FATAL: terraform plan itself failed -- see above." >&2; exit 1; }
"$PYTHON_BIN" "$SCRIPT_DIR/redact_aws_errors.py" < "$PLAN_OUT" | grep -A2 "^Plan:" || true
PLAN_SUMMARY="$(grep "^Plan:" "$PLAN_OUT" || echo "Plan: 0 to add, 0 to change, 0 to destroy.")"
echo "    $PLAN_SUMMARY"
TO_DESTROY="$(echo "$PLAN_SUMMARY" | grep -oE '[0-9]+ to destroy' | grep -oE '^[0-9]+' || echo 0)"
rm -f "$PLAN_OUT"
if [ "${TO_DESTROY:-0}" != "0" ] && [ "$ALLOW_DESTRUCTIVE" != "1" ]; then
  echo "FATAL: this plan would destroy $TO_DESTROY resource(s) (a replace counts here too -- it's both an add and a destroy)." >&2
  echo "        Decision 93: this is exactly the failure mode that destroyed 38 real resources unreviewed. Re-run with" >&2
  echo "        --allow-destructive only after a human has reviewed the plan above and confirms this destroy is intended." >&2
  exit 1
fi

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
# Software-inventory audit (this turn): piped through redact_aws_errors.py
# -- a failed apply's own error text can embed this account's full ARN
# (confirmed live elsewhere this session). pipefail (set at the top of
# this file) means a failing `terraform apply` still fails this script.
(cd "$TF_DIR" && terraform apply -input=false -auto-approve) 2>&1 | "$PYTHON_BIN" "$SCRIPT_DIR/redact_aws_errors.py"

echo "==> Extracting outputs..."
CONTROL_IP="$(cd "$TF_DIR" && terraform output -json inventory | "$PYTHON_BIN" -c 'import json,sys; raw=json.load(sys.stdin); print((raw["value"] if "value" in raw else raw)["control"]["public_ip"])')"
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
"$PYTHON_BIN" - "$MOCKOPIN_WINDOW1_START_UTC" "$MOCKOPIN_WINDOW2_START_UTC" "$MOCKOPIN_WINDOW3_START_UTC" > "$TMP_SCHEDULE" <<'PY'
import json, random, sys
w1, w2, w3 = sys.argv[1:4]
print(json.dumps({
    "window_start_times_utc": {"1": w1, "2": w2, "3": w3},
    # Order turn (item 2, thesis/results/v8/DECISIONS.md): ONE seed for
    # the whole campaign, not one per window -- it picks which 3x3 Latin
    # square of profile orders (classic/pqc/hybrid x 3 window positions)
    # campaign_run.py's build_latin_square_profile_orders() uses, so each
    # profile occupies each of the 3 within-window block positions
    # exactly once across the 3 windows (replaces the old per-window
    # independent shuffle, which confounded profile identity with
    # position -- the single-window pilot 2 data that first surfaced this,
    # Decision 89). The per-window "window_seeds" key this replaces is no
    # longer read by campaign_run.py.
    "latin_square_seed": random.SystemRandom().randrange(2**31),
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
        f"ec2-user@{ip}", "/usr/bin/chronyc tracking | head -5"
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

echo "==> campaign_up.sh completed: instances up (12, or fewer if MOCKOPIN_ENABLED_CLIENT_SCENARIOS scoped this apply), connectivity and clock sync verified."
