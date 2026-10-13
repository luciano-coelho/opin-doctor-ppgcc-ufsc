#!/usr/bin/env bash
# Decision 50/55/57: delivers the 4 custom-built MockOPIN images (mtls,
# auth, mockapi, mongo_seed -- NOT the 3 stock images postgres/localstack/
# mongo, which each server pulls directly from their own public registry,
# Decision 55) from the operator's own machine to the control instance,
# then from the control instance to each of the 3 servers, entirely over
# SSH/SCP/rsync -- no AWS credential, no registry, anywhere in this path.
#
# WRITTEN NOW, NOT EXECUTED (Decision 55's instruction) -- no apply, no
# instance launch. Requires the 12-instance Terraform to already be up
# (reads its `inventory` output) and the images to already be built
# locally.
#
# Usage: deliver_images.sh [path to campaign.vars.example-style env file]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="$SCRIPT_DIR/../terraform"

if [ -n "${1:-}" ]; then
  # shellcheck source=/dev/null
  source "$1"
fi
: "${MOCKOPIN_OPERATOR_SSH_PRIVATE_KEY_FILE:?Set MOCKOPIN_OPERATOR_SSH_PRIVATE_KEY_FILE.}"

# Decision 55: --platform linux/amd64 pinned explicitly on every build/
# save/load -- prevents an accidental ARM image if ever built on an ARM
# host (e.g. Apple Silicon), which `docker load` would otherwise accept
# silently as a different, incompatible image.
PLATFORM="linux/amd64"
IMAGES=(
  "insurance-server-lambdas-mtls:latest"
  "insurance-server-lambdas-auth:latest"
  "raidiam-insurance-lambdas:latest"
  "insurance-server-lambdas-mongo_seed:latest"
)

CONTROL_IP="$(cd "$TF_DIR" && terraform output -json inventory | python -c 'import json,sys; print(json.load(sys.stdin)["value"]["control"]["public_ip"])')"
SSH_OPTS=(-i "$MOCKOPIN_OPERATOR_SSH_PRIVATE_KEY_FILE" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20 -o BatchMode=yes)
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

have_rsync_on_control() {
  ssh "${SSH_OPTS[@]}" "ec2-user@${CONTROL_IP}" "command -v rsync >/dev/null 2>&1"
}

for image in "${IMAGES[@]}"; do
  echo "==> Building/verifying $image for $PLATFORM..."
  docker image inspect "$image" >/dev/null 2>&1 || {
    echo "FATAL: $image not found locally -- build it first (docker build --platform $PLATFORM ...)." >&2
    exit 1
  }
  actual_platform="$(docker image inspect "$image" --format '{{.Os}}/{{.Architecture}}')"
  if [ "$actual_platform" != "$PLATFORM" ]; then
    echo "FATAL: $image is $actual_platform, not $PLATFORM -- rebuild with --platform $PLATFORM explicitly." >&2
    exit 1
  fi

  safe_name="$(echo "$image" | tr '/:' '__')"
  tarball="$WORKDIR/${safe_name}.tar.gz"
  echo "    docker save | gzip -> $tarball"
  docker save "$image" | gzip > "$tarball"
  sha256sum "$tarball" > "$tarball.sha256"
  size_bytes="$(stat -c%s "$tarball" 2>/dev/null || stat -f%z "$tarball")"
  echo "    size: $size_bytes bytes"

  echo "    Checking disk space on control instance before sending..."
  avail_kb="$(ssh "${SSH_OPTS[@]}" "ec2-user@${CONTROL_IP}" "df --output=avail -k / | tail -1")"
  needed_kb=$(( (size_bytes / 1024) * 2 )) # headroom: tarball + its eventual docker-load expansion
  if [ "$avail_kb" -lt "$needed_kb" ]; then
    echo "FATAL: control instance has ${avail_kb}KB free, need ~${needed_kb}KB for $image -- aborting before sending." >&2
    exit 1
  fi

  echo "    Sending $image to control instance (resumable)..."
  if have_rsync_on_control; then
    rsync --partial --progress -e "ssh ${SSH_OPTS[*]}" "$tarball" "$tarball.sha256" "ec2-user@${CONTROL_IP}:~/"
  else
    # Fallback: split into 100MB parts, each with its own sha256, so an
    # interrupted transfer only needs to resend the missing parts, not
    # the whole tarball. (rsync is strongly preferred when available --
    # this path exists for a minimal AMI that might lack it.)
    echo "    rsync not available on control -- falling back to split parts + scp."
    split -b 100m "$tarball" "$tarball.part."
    for part in "$tarball".part.*; do
      sha256sum "$part" > "$part.sha256"
      scp "${SSH_OPTS[@]}" "$part" "$part.sha256" "ec2-user@${CONTROL_IP}:~/"
    done
    ssh "${SSH_OPTS[@]}" "ec2-user@${CONTROL_IP}" \
      "cd ~ && for p in $(basename "$tarball").part.*.sha256; do sha256sum -c \"\$p\"; done && cat $(basename "$tarball").part.* > $(basename "$tarball") && rm -f $(basename "$tarball").part.*"
  fi
  scp "${SSH_OPTS[@]}" "$tarball.sha256" "ec2-user@${CONTROL_IP}:~/"

  echo "    Verifying sha256 on control instance..."
  ssh "${SSH_OPTS[@]}" "ec2-user@${CONTROL_IP}" "cd ~ && sha256sum -c $(basename "$tarball").sha256"

  # Distribute from control to each of the 3 servers, over the campaign
  # key (control -> server, same SSH relationship as everything else in
  # Decision 49/55's architecture) -- AWS-internal network, far faster
  # than the operator's own upload leg above.
  echo "    Distributing to the 3 servers from control..."
  ssh "${SSH_OPTS[@]}" "ec2-user@${CONTROL_IP}" bash -s -- "$(basename "$tarball")" <<'REMOTE'
set -euo pipefail
TARBALL="$1"
python3 - "$TARBALL" <<'PY'
import json, subprocess, sys
tarball = sys.argv[1]
raw = json.load(open("/home/ec2-user/inventory.json"))
inv = raw["value"] if "value" in raw else raw
campaign_key = "/home/ec2-user/.ssh/campaign_key"
for name, data in inv["servers"].items():
    ip = data["public_ip"]
    scp_cmd = ["scp", "-i", campaign_key, "-o", "StrictHostKeyChecking=no",
               "-o", "UserKnownHostsFile=/dev/null", "-o", "BatchMode=yes",
               f"/home/ec2-user/{tarball}", f"ec2-user@{ip}:~/"]
    print(f"  -> {name} ({ip})")
    subprocess.run(scp_cmd, check=True, timeout=600)
    load_cmd = [
        "ssh", "-i", campaign_key, "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null", "-o", "BatchMode=yes",
        f"ec2-user@{ip}",
        f"gunzip -c ~/{tarball} | docker load && rm -f ~/{tarball}",
    ]
    subprocess.run(load_cmd, check=True, timeout=300)
PY
REMOTE

  echo "    Comparing loaded image ID across the 3 servers (Decision 55 -- ID, not a registry digest)..."
  ssh "${SSH_OPTS[@]}" "ec2-user@${CONTROL_IP}" bash -s <<'REMOTE'
set -euo pipefail
python3 - <<'PY'
import json, subprocess
raw = json.load(open("/home/ec2-user/inventory.json"))
inv = raw["value"] if "value" in raw else raw
campaign_key = "/home/ec2-user/.ssh/campaign_key"
ids = {}
for name, data in inv["servers"].items():
    ip = data["public_ip"]
    cmd = ["ssh", "-i", campaign_key, "-o", "StrictHostKeyChecking=no",
           "-o", "UserKnownHostsFile=/dev/null", "-o", "BatchMode=yes",
           f"ec2-user@{ip}", "docker image inspect --format='{{.Id}}' $(docker images -q | head -1)"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    ids[name] = r.stdout.strip()
print("Image IDs per server:", ids)
if len(set(ids.values())) != 1:
    raise SystemExit(f"FATAL: image IDs differ across servers -- {ids}")
print("OK: identical image ID on all 3 servers.")
PY
REMOTE

  echo "    Removing the local control-instance copy of the tarball..."
  ssh "${SSH_OPTS[@]}" "ec2-user@${CONTROL_IP}" "rm -f ~/$(basename "$tarball") ~/$(basename "$tarball").sha256"
done

echo "==> deliver_images.sh completed for all ${#IMAGES[@]} images."
