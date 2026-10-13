#!/usr/bin/env bash
# Scans three things, with NO filename-based exceptions (gitignored files
# such as .scan-values.local.sh or *.auto.tfvars.json are excluded
# automatically, simply because they are never tracked or staged -- not
# via a special-case exclude rule):
#   1. TRACKED  -- every git-tracked file's current content under
#      thesis/results/v8/ (`git grep`, which only ever looks at tracked
#      content).
#   2. STAGED   -- the currently staged diff under thesis/results/v8/
#      (`git diff --cached`), so a secret added with `git add` is caught
#      before it's committed, not after.
#   3. HISTORY  -- every commit on every branch/ref (`git log --all -p`),
#      unscoped (the whole repository, not just v8/) -- catches a secret
#      that was committed and later removed, which 1/2 alone would miss.
#
# Checked patterns:
#   - AWS access key pattern
#   - inline secret-key assignment
#   - PEM/SSH private key headers
#   - the real AWS account ID and operator public IP (never hardcoded here
#     -- loaded from ../.scan-values.local.sh, gitignored, local-only)
#
# Prints PASS/FAIL per pattern category and scan type, NEVER the matched
# text itself (-l / -c counts only) -- a real hit is reported by location
# (file, or "N commits"), not by leaking the secret into this script's own
# output.
#
# Usage:
#   scripts/scan_secrets.sh                  # tracked + staged + full history
#   scripts/scan_secrets.sh <git-ref>         # scan one specific commit/diff instead
set -uo pipefail

V8_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$V8_DIR/../../.." && pwd)"
V8_RELPATH="thesis/results/v8"
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

check_one_ref() {
  local label="$1" pattern="$2" ref="$3"
  local hits
  hits=$(cd "$REPO_ROOT" && git show "$ref" 2>/dev/null | grep -cE "$pattern" 2>/dev/null)
  if [ "${hits:-0}" != "0" ]; then
    echo "FAIL: $label -- $hits matching line(s) in $ref"
    FOUND_ANY=1
  else
    echo "PASS: $label -- 0 matches in $ref"
  fi
}

check_tracked() {
  local label="$1" pattern="$2"
  local hits
  hits=$(cd "$REPO_ROOT" && git grep -lE "$pattern" -- "$V8_RELPATH" 2>/dev/null)
  if [ -n "$hits" ]; then
    echo "FAIL: $label (tracked) -- found in:"
    echo "$hits" | sed 's/^/  /'
    FOUND_ANY=1
  else
    echo "PASS: $label (tracked) -- 0 matches"
  fi
}

check_staged() {
  local label="$1" pattern="$2"
  local hits
  hits=$(cd "$REPO_ROOT" && git diff --cached -- "$V8_RELPATH" 2>/dev/null | grep -cE "$pattern" 2>/dev/null)
  if [ "${hits:-0}" != "0" ]; then
    echo "FAIL: $label (staged) -- $hits matching line(s)"
    FOUND_ANY=1
  else
    echo "PASS: $label (staged) -- 0 matches"
  fi
}

check_history() {
  local label="$1" pattern="$2"
  local hits
  # Unscoped (whole repo, not just v8/) and across every branch/ref --
  # a secret could have been committed under a path that no longer
  # exists or was later moved out of v8/.
  hits=$(cd "$REPO_ROOT" && git log --all -p 2>/dev/null | grep -cE "$pattern" 2>/dev/null)
  if [ "${hits:-0}" != "0" ]; then
    echo "FAIL: $label (full history, all refs) -- $hits matching line(s) across all commits"
    FOUND_ANY=1
  else
    echo "PASS: $label (full history, all refs) -- 0 matches"
  fi
}

PATTERNS=(
  "AWS access key pattern|AKIA[A-Z0-9]{16}"
  "inline secret-key assignment|aws_secret_access_key[[:space:]]*=[[:space:]]*[A-Za-z0-9/+=]{20,}"
  "PEM/SSH private key header|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"
  "AWS account ID|$MOCKOPIN_SCAN_ACCOUNT_ID"
  "operator public IP|$MOCKOPIN_SCAN_AUTHOR_IP"
)

check_no_tracked_tfstate() {
  # Decision 49: Terraform state is local/gitignored by convention, but
  # that's a convention, not a guarantee (`git add -f` bypasses it) --
  # this checks directly that no *.tfstate* file was ever tracked, now
  # or at any point in history, rather than trusting .gitignore alone.
  local hits
  hits=$(cd "$REPO_ROOT" && git ls-files -- "$V8_RELPATH" | grep -E '\.tfstate' || true)
  if [ -n "$hits" ]; then
    echo "FAIL: Terraform state file tracked right now -- found:"
    echo "$hits" | sed 's/^/  /'
    FOUND_ANY=1
  else
    echo "PASS: Terraform state file (tracked now) -- 0 matches"
  fi
  hits=$(cd "$REPO_ROOT" && git log --all --diff-filter=A --name-only --pretty=format: -- '*.tfstate*' 2>/dev/null | grep -v '^$' || true)
  if [ -n "$hits" ]; then
    echo "FAIL: Terraform state file added at some point in history -- found:"
    echo "$hits" | sort -u | sed 's/^/  /'
    FOUND_ANY=1
  else
    echo "PASS: Terraform state file (full history, all refs) -- 0 matches"
  fi
}

if [ -n "$GIT_REF" ]; then
  echo "=== Secret scan: single ref $GIT_REF ==="
  for p in "${PATTERNS[@]}"; do
    check_one_ref "${p%%|*}" "${p#*|}" "$GIT_REF"
  done
else
  echo "=== Secret scan: tracked content + staged diff under $V8_RELPATH, plus full history (all refs, whole repo) ==="
  echo "--- tracked ($V8_RELPATH) ---"
  for p in "${PATTERNS[@]}"; do
    check_tracked "${p%%|*}" "${p#*|}"
  done
  echo "--- staged ($V8_RELPATH) ---"
  for p in "${PATTERNS[@]}"; do
    check_staged "${p%%|*}" "${p#*|}"
  done
  echo "--- full history (all refs, whole repo) ---"
  for p in "${PATTERNS[@]}"; do
    check_history "${p%%|*}" "${p#*|}"
  done
  echo "--- Terraform state, never tracked (Decision 49) ---"
  check_no_tracked_tfstate
fi

echo "==="
if [ "$FOUND_ANY" = "1" ]; then
  echo "RESULT: FAIL -- see above"
  exit 1
else
  echo "RESULT: PASS -- no secrets, account ID, or author IP found"
  exit 0
fi
