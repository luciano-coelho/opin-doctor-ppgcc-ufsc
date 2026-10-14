#!/usr/bin/env bash
# B.11: tears down the 3-container local rehearsal (see rehearsal_setup.sh).
set -euo pipefail
docker rm -f mockopin_rehearsal_server mockopin_rehearsal_client mockopin_rehearsal_control >/dev/null 2>&1 || true
docker network rm mockopin_rehearsal_net >/dev/null 2>&1 || true
echo "Rehearsal containers/network removed."
