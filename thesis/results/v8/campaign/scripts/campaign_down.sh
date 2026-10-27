#!/usr/bin/env bash
# Decision 49: teardown, with a safety refusal -- this will NOT destroy
# the campaign's infrastructure unless campaign_pull.sh's verified copy
# (a `.pull-verified` marker, written only after the sha256 manifest
# check passes) is found, unless --force is given explicitly.
#
# After destroy, verifies region-by-region via the AWS API directly
# (never trusts Terraform's own exit status alone, same standard as
# every other teardown in this project, Decisions 25/29/33): instances,
# security groups, key pairs, volumes, Elastic IPs, AND the control
# instance specifically.
#
# Usage: campaign_down.sh [path to campaign.vars.example-style env file] [--force] [--delete-local-state] [local pulled-data dir]
#
# --delete-local-state (item 4, validation-gate turn, thesis/results/v8/
# DECISIONS.md): opts into removing the local Terraform state + the
# campaign's own SSH key material after a verified-clean teardown.
# Without it, the default is to KEEP them (the safe side -- both are
# already local-only, gitignored, never committed, Decision 49, so
# keeping them costs nothing but disk) and print exactly which files
# remain. This replaces an interactive `read -r -p` prompt that used to
# run at the very end: it blocked forever (or failed outright under
# `set -e` with no TTY attached -- "read error: 0: Inappropriate ioctl
# for device", confirmed live) with no way to finish teardown without a
# human physically present and typing at that exact moment -- the
# default must not depend on an answer.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="$SCRIPT_DIR/../terraform"

FORCE=0
DELETE_LOCAL_STATE=0
ARGS=()
for a in "$@"; do
  if [ "$a" = "--force" ]; then
    FORCE=1
  elif [ "$a" = "--delete-local-state" ]; then
    DELETE_LOCAL_STATE=1
  else
    ARGS+=("$a")
  fi
done

if [ -n "${ARGS[0]:-}" ]; then
  # shellcheck source=/dev/null
  source "${ARGS[0]}"
fi
DEST="${ARGS[1]:-./campaign-data-pulled}"

if [ "$FORCE" != "1" ]; then
  if [ ! -f "$DEST/.pull-verified" ]; then
    echo "FATAL: $DEST/.pull-verified not found -- campaign_pull.sh has not successfully verified a local copy of the data yet." >&2
    echo "        Run campaign_pull.sh first, or pass --force if you are certain the data is not needed (e.g. a failed pilot)." >&2
    exit 1
  fi
fi

: "${MOCKOPIN_AWS_PROFILE:=mockopin-pqc}"
: "${MOCKOPIN_OPERATOR_SSH_PUBLIC_KEY_FILE:?Set MOCKOPIN_OPERATOR_SSH_PUBLIC_KEY_FILE -- destroy needs the same variable values apply used (Terraform re-evaluates the whole config to plan the destroy).}"
: "${MOCKOPIN_SERVER_CLIENT_INSTANCE_TYPE:?Set MOCKOPIN_SERVER_CLIENT_INSTANCE_TYPE -- same reason as above.}"
export AWS_PROFILE="$MOCKOPIN_AWS_PROFILE"
export TF_VAR_operator_ssh_public_key="$(cat "$MOCKOPIN_OPERATOR_SSH_PUBLIC_KEY_FILE")"
export TF_VAR_server_client_instance_type="$MOCKOPIN_SERVER_CLIENT_INSTANCE_TYPE"
echo "==> Discovering operator public IP (fresh -- destroy re-evaluates the whole config, including the SG rule that references it)..."
OPERATOR_IP="$(curl -s https://checkip.amazonaws.com)"
export TF_VAR_operator_ip_cidr="${OPERATOR_IP}/32"

echo "==> terraform destroy"
# Software-inventory audit (this turn): piped through redact_aws_errors.py
# -- a failed apply/destroy's own error text can embed this account's
# full ARN (confirmed live elsewhere this session, an IAM denial
# message did exactly that). set -o pipefail (already on, top of this
# file) means a failing `terraform destroy` still fails this script,
# despite being the first stage of a pipeline now.
(cd "$TF_DIR" && terraform destroy -input=false -auto-approve) 2>&1 | python3 "$SCRIPT_DIR/redact_aws_errors.py"

echo "==> Verifying teardown directly via the AWS API, region by region (not just Terraform's own exit status)..."
python3 - "$SCRIPT_DIR" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from redact_aws_errors import redact

import boto3
import botocore.exceptions

regions = ["sa-east-1", "us-east-1", "ap-northeast-1", "ca-central-1", "eu-north-1", "ap-southeast-1", "ap-northeast-2"]
tag_filter = [{"Name": "tag:Project", "Values": ["mockopin-pqc-aws"]}]
failed = False

# Software-inventory audit (this turn): a ClientError's own message
# text can embed this account's ARN (confirmed live elsewhere this
# session, a real AccessDeniedException did exactly that) -- caught
# and redacted here before ever reaching print()/the raised
# SystemExit, rather than trusting boto3's own exception text not to
# mention it.
try:
    for region in regions:
        s = boto3.Session(profile_name="mockopin-pqc", region_name=region)
        ec2 = s.client("ec2")

        insts = ec2.describe_instances(Filters=tag_filter)
        running = [i for r in insts["Reservations"] for i in r["Instances"] if i["State"]["Name"] not in ("terminated", "shutting-down")]
        sgs = ec2.describe_security_groups(Filters=[{"Name": "group-name", "Values": ["mockopin-pqc-campaign-*"]}])
        kps = ec2.describe_key_pairs(Filters=[{"Name": "key-name", "Values": ["mockopin-pqc-campaign*"]}])
        vols = ec2.describe_volumes(Filters=tag_filter)
        active_vols = [v for v in vols["Volumes"] if v["State"] != "deleted"]
        addrs = ec2.describe_addresses(Filters=tag_filter)

        control_note = " (includes the control instance -- sa-east-1 only)" if region == "sa-east-1" else ""
        print(f"{region}{control_note}: instances={len(running)} sgs={len(sgs['SecurityGroups'])} "
              f"key_pairs={len(kps['KeyPairs'])} volumes={len(active_vols)} eips={len(addrs['Addresses'])}")

        if running or sgs["SecurityGroups"] or kps["KeyPairs"] or active_vols or addrs["Addresses"]:
            failed = True
except botocore.exceptions.ClientError as e:
    raise SystemExit(f"FATAL: AWS API call failed during teardown verification: {redact(str(e))}") from None

if failed:
    raise SystemExit("FATAL: at least one region still has a resource after destroy -- see counts above.")
print("All regions confirmed clean.")
PY

echo
echo "==> Teardown verified clean. Decision 52: once nothing remains in AWS,"
echo "    the local Terraform state and the campaign's own SSH key material"
echo "    (both already local-only, gitignored, never committed -- Decision 49)"
echo "    no longer protect anything real."

# Item 4 (validation-gate turn, thesis/results/v8/DECISIONS.md): no
# interactive prompt -- the default (no flag) is to KEEP local state/key
# material and report exactly what remains and where. Pass
# --delete-local-state explicitly to opt into removing it instead; the
# removal path, when taken, reports exactly what it removed too (never
# a silent "deleted" with nothing to show for it). Factored into its own
# function (tests/test_campaign_down_local_state.sh extracts and calls
# this exact function body against fake directories -- no AWS, no
# terraform -- rather than duplicating its logic in the test).
report_and_handle_local_state() {
  local tf_dir="$1" delete_flag="$2"
  local local_state_files=()
  for f in "$tf_dir"/terraform.tfstate "$tf_dir"/terraform.tfstate.backup "$tf_dir"/*.tfplan; do
    [ -e "$f" ] && local_state_files+=("$f")
  done
  local local_state_dirs=()
  [ -d "$tf_dir/.terraform" ] && local_state_dirs+=("$tf_dir/.terraform")

  if [ "$delete_flag" = "1" ]; then
    if [ "${#local_state_files[@]}" -eq 0 ] && [ "${#local_state_dirs[@]}" -eq 0 ]; then
      echo "    --delete-local-state given, but nothing to delete -- no local state/cache files found."
    else
      echo "    --delete-local-state given -- removing:"
      for f in "${local_state_files[@]}" "${local_state_dirs[@]}"; do
        echo "      - $f"
      done
      rm -f "$tf_dir"/terraform.tfstate "$tf_dir"/terraform.tfstate.backup "$tf_dir"/*.tfplan
      rm -rf "$tf_dir"/.terraform
      echo "    Removed. (The campaign SSH private key lived only in that state and in the control"
      echo "    instance's own ~/.ssh/campaign_key, which no longer exists now that the control"
      echo "    instance itself is destroyed -- nothing further to delete for it.)"
    fi
  else
    echo "    Default: kept as-is (pass --delete-local-state to remove). Remaining local files:"
    if [ "${#local_state_files[@]}" -eq 0 ] && [ "${#local_state_dirs[@]}" -eq 0 ]; then
      echo "      (none -- no local Terraform state/cache files exist at $tf_dir)"
    else
      for f in "${local_state_files[@]}" "${local_state_dirs[@]}"; do
        echo "      - $f"
      done
    fi
  fi
}

report_and_handle_local_state "$TF_DIR" "$DELETE_LOCAL_STATE"

echo "==> campaign_down.sh completed."
