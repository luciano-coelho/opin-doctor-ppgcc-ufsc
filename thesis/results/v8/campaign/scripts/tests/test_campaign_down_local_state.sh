#!/usr/bin/env bash
# Item 4 (validation-gate turn, thesis/results/v8/DECISIONS.md): tests
# campaign_down.sh's report_and_handle_local_state() function -- the
# fix that replaced its old interactive `read -r -p` prompt (blocked
# forever / failed outright with no TTY attached) with a non-interactive
# default (keep + report) and an explicit opt-in to delete.
#
# Extracts the REAL function body from campaign_down.sh (sed, between
# its own markers) and sources ONLY that -- never a duplicated copy of
# the logic -- so this test exercises exactly what ships, without
# running terraform/boto3/any real AWS call.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAMPAIGN_DOWN="$SCRIPT_DIR/../campaign_down.sh"

FUNC_FILE="$(mktemp)"
trap 'rm -f "$FUNC_FILE"' EXIT
sed -n '/^report_and_handle_local_state() {/,/^}$/p' "$CAMPAIGN_DOWN" > "$FUNC_FILE"
if [ ! -s "$FUNC_FILE" ]; then
  echo "FAIL: could not extract report_and_handle_local_state() from $CAMPAIGN_DOWN -- did it move/get renamed?" >&2
  exit 1
fi
# shellcheck source=/dev/null
source "$FUNC_FILE"

PASS=0
FAIL=0

check() {
  local desc="$1" expected_substr="$2" actual="$3"
  if [[ "$actual" == *"$expected_substr"* ]]; then
    echo "PASS: $desc"
    PASS=$((PASS + 1))
  else
    echo "FAIL: $desc -- expected to find '$expected_substr' in:"
    echo "$actual" | sed 's/^/    /'
    FAIL=$((FAIL + 1))
  fi
}

# Case 1: default (no flag) with real state files present -- must KEEP
# them (not delete) and report their exact paths.
TMP1="$(mktemp -d)"
touch "$TMP1/terraform.tfstate" "$TMP1/terraform.tfstate.backup" "$TMP1/foo.tfplan"
mkdir -p "$TMP1/.terraform"
OUT1="$(report_and_handle_local_state "$TMP1" "0")"
check "default keeps terraform.tfstate on disk" "" "$( [ -f "$TMP1/terraform.tfstate" ] && echo present)"
check "default reports terraform.tfstate path" "terraform.tfstate" "$OUT1"
check "default reports .terraform dir" ".terraform" "$OUT1"
check "default says 'kept as-is'" "kept as-is" "$OUT1"
[ -f "$TMP1/terraform.tfstate" ] || { echo "FAIL: default run deleted terraform.tfstate -- must never delete without the flag"; FAIL=$((FAIL + 1)); }
rm -rf "$TMP1"

# Case 2: --delete-local-state given, with real files present -- must
# remove them and report exactly what it removed.
TMP2="$(mktemp -d)"
touch "$TMP2/terraform.tfstate" "$TMP2/terraform.tfstate.backup"
mkdir -p "$TMP2/.terraform"
OUT2="$(report_and_handle_local_state "$TMP2" "1")"
check "--delete-local-state reports removing terraform.tfstate" "terraform.tfstate" "$OUT2"
check "--delete-local-state says Removed" "Removed." "$OUT2"
if [ -f "$TMP2/terraform.tfstate" ] || [ -d "$TMP2/.terraform" ]; then
  echo "FAIL: --delete-local-state did not actually remove the files"
  FAIL=$((FAIL + 1))
else
  echo "PASS: --delete-local-state actually removed the files"
  PASS=$((PASS + 1))
fi
rm -rf "$TMP2"

# Case 3: no files at all (a campaign never applied, or already cleaned
# up) -- must not error, must say so plainly, in both modes.
TMP3="$(mktemp -d)"
OUT3_KEEP="$(report_and_handle_local_state "$TMP3" "0")"
check "empty dir, default mode: says none found" "none" "$OUT3_KEEP"
OUT3_DEL="$(report_and_handle_local_state "$TMP3" "1")"
check "empty dir, delete mode: says nothing to delete" "nothing to delete" "$OUT3_DEL"
rm -rf "$TMP3"

# Case 4: crucially, the function must never block on stdin -- run it
# with stdin redirected from /dev/null (simulating a non-interactive/
# piped invocation, exactly the scenario that broke the old `read -r -p`)
# and confirm it returns promptly.
TMP4="$(mktemp -d)"
touch "$TMP4/terraform.tfstate"
START="$(date +%s)"
report_and_handle_local_state "$TMP4" "0" < /dev/null > /dev/null
ELAPSED=$(( $(date +%s) - START ))
if [ "$ELAPSED" -le 2 ]; then
  echo "PASS: non-interactive invocation (stdin=/dev/null) returned promptly (${ELAPSED}s), never blocked"
  PASS=$((PASS + 1))
else
  echo "FAIL: non-interactive invocation took ${ELAPSED}s -- still blocking somewhere"
  FAIL=$((FAIL + 1))
fi
rm -rf "$TMP4"

echo
echo "=== $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
