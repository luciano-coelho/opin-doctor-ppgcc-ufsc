#!/usr/bin/env bash
# Scans every uncommitted file under thesis/results/v8/ (and this script
# itself can be pointed at a git ref instead -- see usage below) for:
#   - AWS access key pattern
#   - inline secret-key assignment
#   - PEM/SSH private key headers
#   - the real AWS account ID and operator public IP (never hardcoded here
#     -- loaded from ../.scan-values.local.sh, gitignored, local-only)
#
# Prints PASS/FAIL per pattern category and file, NEVER the matched text
# itself (grep -l / -c only) -- so a real hit is reported by location, not
# by leaking the secret into this script's own output.
#
# Usage:
#   scripts/scan_secrets.sh                  # scan uncommitted v8/ files
#   scripts/scan_secrets.sh <git-ref>         # scan a specific commit/diff instead
set -uo pipefail

V8_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VALUES_FILE="$V8_DIR/.scan-values.local.sh"

if [ ! -f "$VALUES_FILE" ]; then
  echo "FAIL: $VALUES_FILE not found -- can't check account ID / author IP (see README.md for format)." >&2
  exit 2
fi
# shellcheck source=/dev/null
source "$VALUES_FILE"

if [ -z "${MOCKOPIN_SCAN_ACCOUNT_ID:-}" ] || [ -z "${MOCKOPIN_SCAN_AUTHOR_IP:-}" ]; then
  echo "FAIL: MOCKOPIN_SCAN_ACCOUNT_ID / MOCKOPIN_SCAN_AUTHOR_IP not set after sourcing $VALUES_FILE" >&2
  exit 2
fi

GIT_REF="${1:-}"
FOUND_ANY=0

check_pattern() {
  local label="$1" pattern="$2"
  local hits
  if [ -n "$GIT_REF" ]; then
    hits=$(cd "$V8_DIR/../../.." && git show "$GIT_REF" 2>/dev/null | grep -cE "$pattern" 2>/dev/null)
    if [ "${hits:-0}" != "0" ]; then
      echo "FAIL: $label -- $hits matching line(s) in $GIT_REF"
      FOUND_ANY=1
    else
      echo "PASS: $label -- 0 matches in $GIT_REF"
    fi
  else
    hits=$(grep -rlE "$pattern" "$V8_DIR" --exclude-dir=.terraform --exclude="*.tfstate*" --exclude=".scan-values.local.sh" --exclude="*.auto.tfvars.json" 2>/dev/null)
    if [ -n "$hits" ]; then
      echo "FAIL: $label -- found in:"
      echo "$hits" | sed 's/^/  /'
      FOUND_ANY=1
    else
      echo "PASS: $label -- 0 matches"
    fi
  fi
}

echo "=== Secret scan: $( [ -n "$GIT_REF" ] && echo "git ref $GIT_REF" || echo "uncommitted files under $V8_DIR" ) ==="
check_pattern "AWS access key pattern" 'AKIA[A-Z0-9]{16}'
check_pattern "inline secret-key assignment" 'aws_secret_access_key[[:space:]]*=[[:space:]]*[A-Za-z0-9/+=]{20,}'
check_pattern "PEM/SSH private key header" '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----'
check_pattern "AWS account ID" "$MOCKOPIN_SCAN_ACCOUNT_ID"
check_pattern "operator public IP" "$MOCKOPIN_SCAN_AUTHOR_IP"

echo "==="
if [ "$FOUND_ANY" = "1" ]; then
  echo "RESULT: FAIL -- see above"
  exit 1
else
  echo "RESULT: PASS -- no secrets, account ID, or author IP found"
  exit 0
fi
