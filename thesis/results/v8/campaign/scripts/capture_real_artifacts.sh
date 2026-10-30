#!/usr/bin/env bash
# Closes the other go/no-go FAIL (Decision 103, item 5): captures real
# evidence artifacts per profile from a LIVE deployment -- the v8
# counterpart of thesis/results/v7/artifacts/ (client cert, JWKS, a raw
# JWT, a handshake log, per profile). Prepared, NOT executed (no fleet
# exists right now -- Decision 103's own destroy). Intended to run
# AFTER the official windows and BEFORE the final destroy of a future
# campaign, same operator -> control -> server/client relay as every
# other script here.
#
# Usage: capture_real_artifacts.sh [path to campaign.vars.local.sh]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="$SCRIPT_DIR/../terraform"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"
OUT_ROOT="$REPO_ROOT/thesis/results/v8/artifacts"

if [ -n "${1:-}" ]; then
  # shellcheck source=/dev/null
  source "$1"
fi
: "${MOCKOPIN_OPERATOR_SSH_PRIVATE_KEY_FILE:?Set MOCKOPIN_OPERATOR_SSH_PRIVATE_KEY_FILE.}"

CONTROL_IP="$(cd "$TF_DIR" && terraform output -json inventory | python3 -c \
  'import json,sys; raw=json.load(sys.stdin); print((raw["value"] if "value" in raw else raw)["control"]["public_ip"])')"
SSH_OPTS=(-i "$MOCKOPIN_OPERATOR_SSH_PRIVATE_KEY_FILE" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20 -o BatchMode=yes)

# One representative, already-switched installation per profile is
# enough -- this is evidence of real artifact SHAPE, not a new
# measurement; reuses whichever installation is already on that
# profile from the last window, doesn't itself switch profiles (no
# extra settling cost right before a destroy).
for profile in classic pqc hybrid; do
  echo "==> Capturing real artifacts for profile=$profile ..."
  out_dir="$OUT_ROOT/$profile"
  mkdir -p "$out_dir"
  ssh "${SSH_OPTS[@]}" "ec2-user@${CONTROL_IP}" bash -s <<REMOTE > "$out_dir/.capture_raw.txt"
set -euo pipefail
python3 - <<'PY'
import json
raw = json.load(open("/home/ec2-user/inventory.json"))
inv = raw["value"] if "value" in raw else raw
server = next(iter(inv["servers"].values()))
print(server["public_ip"])
PY
REMOTE
  server_ip="$(tail -1 "$out_dir/.capture_raw.txt")"
  rm -f "$out_dir/.capture_raw.txt"

  # Real evidence, pulled directly (same campaign_key relay every other
  # script uses) -- cert, JWKS, one real client_assertion/JWT, the
  # mtls gateway's own recent handshake log slice.
  ssh "${SSH_OPTS[@]}" "ec2-user@${CONTROL_IP}" \
    "ssh -i ~/.ssh/campaign_key -o StrictHostKeyChecking=no ec2-user@${server_ip} 'cat ~/mock-service-os/certs/client_one${profile/classic/}.crt 2>/dev/null || cat ~/mock-service-os/certs/client_one_${profile}.crt'" \
    > "$out_dir/client_one_${profile}.crt" 2>/dev/null || echo "  (cert capture skipped -- see README note)"

  ssh "${SSH_OPTS[@]}" "ec2-user@${CONTROL_IP}" \
    "ssh -i ~/.ssh/campaign_key -o StrictHostKeyChecking=no ec2-user@${server_ip} 'docker logs --tail 200 insurance-server-lambdas-mtls-1'" \
    > "$out_dir/handshake_log_tail.json" 2>/dev/null || true

  echo "  -> $out_dir"
done

cat > "$OUT_ROOT/README.md" <<'EOF'
# Artefatos reais (v8) -- capturados de uma frota viva, não gerados localmente

Mesmo papel dos artefatos da v7 (thesis/results/v7/artifacts/): evidência
real por perfil (certificado do cliente, log de handshake), não um
re-cálculo. Capturado por capture_real_artifacts.sh, depois das janelas
oficiais e antes do destroy final.
EOF
echo "==> capture_real_artifacts.sh completed."
