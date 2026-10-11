#!/usr/bin/env bash
# Teardown for the v8 AWS experiment. Safe to run even if nothing is up
# (terraform destroy on empty state is a no-op) and safe to re-run.
set -euo pipefail

export PATH="$HOME/bin:$HOME/AppData/Roaming/Python/Python313/Scripts:$PATH"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VAR_FILE="${1:-}"

# latency-discovery/terraform and (once it exists) terraform/main live in
# different places -- latency-discovery/ groups everything specific to
# latency discovery, while terraform/main (the Phase 4 experiment) stays at
# the v8 root
# alongside this script. See DECISIONS.md for why.
for pair in "latency-discovery/terraform:latency-discovery" "terraform/main:main"; do
  relpath="${pair%%:*}"
  label="${pair##*:}"
  dir="$ROOT/$relpath"
  [ -d "$dir" ] || continue
  echo "=== terraform destroy: $label ==="
  if [ -n "$VAR_FILE" ] && [ -f "$VAR_FILE" ]; then
    (cd "$dir" && terraform destroy -auto-approve -input=false -var-file="$VAR_FILE")
  else
    (cd "$dir" && terraform destroy -auto-approve -input=false)
  fi
done

echo "=== Verifying no mockopin-pqc-aws instances, security groups, or key pairs remain, across all candidate regions ==="
CLEAN=1
for region in sa-east-1 us-east-1 us-east-2 us-west-2 ca-central-1 eu-west-1 eu-central-1 ap-northeast-1 ap-southeast-1 ap-southeast-2; do
  instances=$(aws ec2 describe-instances \
    --profile mockopin-pqc --region "$region" \
    --filters "Name=tag:Project,Values=mockopin-pqc-aws" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
    --query "length(Reservations[].Instances[])" --output text)
  sgs=$(aws ec2 describe-security-groups \
    --profile mockopin-pqc --region "$region" \
    --filters "Name=tag:Project,Values=mockopin-pqc-aws" \
    --query "length(SecurityGroups[])" --output text)
  keypair=$(aws ec2 describe-key-pairs \
    --profile mockopin-pqc --region "$region" \
    --key-names mockopin-pqc-discovery --query "length(KeyPairs[])" --output text 2>/dev/null || echo 0)

  status="clean"
  if [ "$instances" != "0" ]; then status="WARNING: $instances instance(s) not terminated"; CLEAN=0; fi
  if [ "$sgs" != "0" ]; then status="$status; WARNING: $sgs security group(s) left"; CLEAN=0; fi
  if [ "$keypair" != "0" ]; then status="$status; WARNING: key pair still registered"; CLEAN=0; fi
  echo "$region: $status"
done

if [ "$CLEAN" = "1" ]; then
  echo "=== All regions confirmed clean: no instances, security groups, or key pairs left. ==="
else
  echo "=== TEARDOWN INCOMPLETE -- see WARNINGs above. Investigate before considering this done. ==="
  exit 1
fi
