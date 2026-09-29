#!/bin/bash
# Re-collects the v7 latency dataset (T_fluxo, 10 runs x 6 scenarios x 3
# profiles) under the already-committed persistent-signer architecture,
# to remove the container-spawn signing overhead that contaminated the
# original v7 latency runs (see DECISIONS.md). Overwrites
# thesis/results/v7/latency/experimentN - <Profile>/<ms>ms/ in place --
# v7 stays the official version; this is a fix to it, not a new version.
set -e
cd "C:/Users/lucia_csx8nlz/MockOPIN"
PY="./thesis/scripts/.venv/Scripts/python.exe"
SCENARIOS="0 14 30 140 225 320"

declare -A EXPNUM=( [classic]=1 [pqc]=2 [hybrid]=3 )

for profile in classic pqc hybrid; do
  echo "=== SWITCH -> $profile ==="
  python thesis/scripts/switch_crypto_profile.py "$profile"
  for ms in $SCENARIOS; do
    echo "=== RUN profile=$profile ms=$ms ==="
    CRYPTO_PROFILE=$profile "$PY" thesis/scripts/latency_automation.py "$ms" \
      --runs 10 --experiment-number "${EXPNUM[$profile]}" --results-version v7
  done
done

echo "=== LATENCY RECOLLECTION COMPLETE ==="
