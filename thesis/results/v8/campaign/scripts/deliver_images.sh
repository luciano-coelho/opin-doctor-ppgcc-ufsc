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
# Software-inventory audit (this turn): neither of these ever had ANY
# delivery mechanism to a CLIENT instance -- deliver_images.sh only
# ever distributed to inv["servers"]. mockopin-pqc-signer has no
# auto-build fallback at all in opin_flow.py (a `docker run` against a
# missing local image just fails outright); mockopin/tls_kem_proxy:precompiled
# DOES auto-build on demand (_ensure_precompiled_tls_kem_proxy_image()),
# but only when TLS_KEM_PROXY_USE_PRECOMPILED=1 is set, which
# SSHExecutor never set either -- so every real remote pqc/hybrid
# execution was defaulting to `go run .` against a source directory
# that was never shipped to the client at all. This would have failed
# the FIRST real pqc/hybrid execution of the campaign outright. Fixed
# two ways together: these images are now built locally (same
# "build it first" precondition as the 4 server images above) and
# delivered to every CLIENT, AND campaign_run.py's SSHExecutor now sets
# TLS_KEM_PROXY_USE_PRECOMPILED=1 so the client actually uses what's
# delivered instead of attempting a live `go run .` build it has no
# source for.
CLIENT_IMAGES=(
  "mockopin-pqc-signer:latest"
  "mockopin/tls_kem_proxy:precompiled"
)
# Item 2 (this turn): overridable so the real transport (rsync send/
# interrupt/resume, disk-space check, tarball cleanup) can be rehearsed
# against a throwaway test image/target without touching the real
# IMAGES list or needing a real Terraform `inventory` output -- unset
# in every real run, where the defaults above/below are what's used.
if [ -n "${MOCKOPIN_DELIVER_IMAGES_OVERRIDE:-}" ]; then
  IFS=' ' read -r -a IMAGES <<< "$MOCKOPIN_DELIVER_IMAGES_OVERRIDE"
fi
if [ -n "${MOCKOPIN_DELIVER_CLIENT_IMAGES_OVERRIDE:-}" ]; then
  IFS=' ' read -r -a CLIENT_IMAGES <<< "$MOCKOPIN_DELIVER_CLIENT_IMAGES_OVERRIDE"
fi

if [ -n "${MOCKOPIN_CONTROL_IP_OVERRIDE:-}" ]; then
  CONTROL_IP="$MOCKOPIN_CONTROL_IP_OVERRIDE"
else
  CONTROL_IP="$(cd "$TF_DIR" && terraform output -json inventory | python -c 'import json,sys; raw=json.load(sys.stdin); print((raw["value"] if "value" in raw else raw)["control"]["public_ip"])')"
fi
SSH_PORT="${MOCKOPIN_SSH_PORT:-22}"
SSH_OPTS=(-i "$MOCKOPIN_OPERATOR_SSH_PRIVATE_KEY_FILE" -p "$SSH_PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20 -o BatchMode=yes)
# Item 2 (this turn): found live, running this script for real against
# the rehearsal -- `scp` takes its port flag as `-P` (capital), `ssh`
# as `-p` (lowercase); sharing ONE options array between both (as this
# script did before) means scp silently treats the port NUMBER as a
# positional filename argument instead ("stat local '2222': No such
# file or directory") while still parsing fine for every `ssh` call,
# so the bug stayed invisible until a port other than 22 was ever
# actually used. Real rsync in this same run still worked -- rsync's
# own `-e "ssh ${SSH_OPTS[*]}"` just hands that whole string to ssh,
# where `-p` is correct.
SCP_OPTS=(-i "$MOCKOPIN_OPERATOR_SSH_PRIVATE_KEY_FILE" -P "$SSH_PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20 -o BatchMode=yes)
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

have_rsync_on_control() {
  ssh "${SSH_OPTS[@]}" "ec2-user@${CONTROL_IP}" "command -v rsync >/dev/null 2>&1"
}

# Pilot item 1 (this turn): found live -- `rsync --partial ... -e ssh ...`
# below runs ON THE OPERATOR'S OWN MACHINE (it's the client side of the
# transfer; only `-e ssh` is remote), but the old code only ever checked
# whether CONTROL had rsync, never whether the operator's own machine did.
# On an operator machine without rsync (confirmed live: this Windows/Git-
# Bash environment has none, and no ready winget package either), that
# left `have_rsync_on_control` returning true while the actual `rsync`
# invocation failed outright with "command not found" (exit 127) --
# never reaching the already-existing split+scp fallback below, which
# needs nothing but split/sha256sum/scp/ssh (all present here). Both ends
# need the binary for `-e ssh` rsync to work, so both are now checked.
have_rsync_locally() {
  command -v rsync >/dev/null 2>&1
}

# Refactored (this turn) into a function parameterized by WHICH
# inventory key ("servers" or "clients") receives the images -- the
# whole transport/verify/manifest mechanism is identical either way,
# only the target host set differs. Previously this was a single
# `for image in "${IMAGES[@]}"` loop hardcoded to inv["servers"]; the
# client-image delivery gap above is what forced generalizing it.
deliver_image_set() {
  local inventory_key="$1"; shift
  local images=("$@")
  local image

  for image in "${images[@]}"; do
    echo "==> Building/verifying $image for $PLATFORM (-> $inventory_key)..."
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
    # Item 2 (an earlier turn): found live, running this script for real --
    # `sha256sum "$tarball"` (the OLD line) embeds $tarball's full LOCAL
    # path (under $WORKDIR) as the filename INSIDE the .sha256 file
    # itself. That's exactly what `sha256sum -c` later tries to open on
    # the REMOTE side too, after sha256sum.sh file is scp'd over there --
    # and the remote copy lives at `~/$(basename "$tarball")`, not at the
    # operator's own $WORKDIR path, so the check ALWAYS failed ("No such
    # file or directory") for any transfer, not just an interrupted one.
    # `(cd ... && sha256sum basename)` records just the basename, which
    # resolves correctly on both ends.
    (cd "$(dirname "$tarball")" && sha256sum "$(basename "$tarball")") > "$tarball.sha256"
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
    if have_rsync_locally && have_rsync_on_control; then
      rsync --partial --progress -e "ssh ${SSH_OPTS[*]}" "$tarball" "$tarball.sha256" "ec2-user@${CONTROL_IP}:~/"
    else
      # Fallback: split into 100MB parts, each with its own sha256, so an
      # interrupted transfer only needs to resend the missing parts, not
      # the whole tarball. (rsync is strongly preferred when available --
      # this path exists for a minimal AMI that might lack it.)
      echo "    rsync not available on control -- falling back to split parts + scp."
      split -b 100m "$tarball" "$tarball.part."
      for part in "$tarball".part.*; do
        (cd "$(dirname "$part")" && sha256sum "$(basename "$part")") > "$part.sha256"  # basename only -- same fix as above
        scp "${SCP_OPTS[@]}" "$part" "$part.sha256" "ec2-user@${CONTROL_IP}:~/"
      done
      # Pilot item 1 (this turn): found live -- `cat ....part.*` (the OLD
      # glob) also matches each part's OWN `.sha256` sidecar file (e.g.
      # `...part.aa.sha256` fits `...part.*` just as well as `...part.aa`
      # does), so the sidecars' plain-text content got concatenated INTO
      # the reassembled tarball, interleaved with the real binary parts.
      # Every individual part passed its own sha256 check (they're intact
      # on disk); only the FINAL whole-file check caught the corruption,
      # exactly as that check exists to do -- no corrupted image ever
      # reached `docker load`. Fixed by matching `split`'s own default
      # 2-character suffix width exactly (`part.??`), which a `.sha256`
      # suffix (6+ characters) can never satisfy.
      ssh "${SSH_OPTS[@]}" "ec2-user@${CONTROL_IP}" \
        "cd ~ && for p in $(basename "$tarball").part.*.sha256; do sha256sum -c \"\$p\"; done && cat $(basename "$tarball").part.?? > $(basename "$tarball") && rm -f $(basename "$tarball").part.*"
    fi
    scp "${SCP_OPTS[@]}" "$tarball.sha256" "ec2-user@${CONTROL_IP}:~/"

    echo "    Verifying sha256 on control instance..."
    ssh "${SSH_OPTS[@]}" "ec2-user@${CONTROL_IP}" "cd ~ && sha256sum -c $(basename "$tarball").sha256"

    # Distribute from control to every host under inv[inventory_key],
    # over the campaign key (control -> target, same SSH relationship
    # as everything else in Decision 49/55's architecture) -- AWS-
    # internal network, far faster than the operator's own upload leg
    # above.
    echo "    Distributing to every '$inventory_key' host from control..."
    ssh "${SSH_OPTS[@]}" "ec2-user@${CONTROL_IP}" env MOCKOPIN_SERVER_SSH_PORT="$SSH_PORT" bash -s -- "$(basename "$tarball")" "$inventory_key" <<'REMOTE'
set -euo pipefail
TARBALL="$1"
INVENTORY_KEY="$2"
python3 - "$TARBALL" "$INVENTORY_KEY" <<'PY'
import json, os, subprocess, sys
tarball, inventory_key = sys.argv[1], sys.argv[2]
raw = json.load(open("/home/ec2-user/inventory.json"))
inv = raw["value"] if "value" in raw else raw
campaign_key = "/home/ec2-user/.ssh/campaign_key"
server_port = os.environ.get("MOCKOPIN_SERVER_SSH_PORT", "22")
for name, data in inv[inventory_key].items():
    ip = data["public_ip"]
    scp_cmd = ["scp", "-i", campaign_key, "-P", server_port, "-o", "StrictHostKeyChecking=no",
               "-o", "UserKnownHostsFile=/dev/null", "-o", "BatchMode=yes",
               f"/home/ec2-user/{tarball}", f"ec2-user@{ip}:~/"]
    print(f"  -> {name} ({ip})")
    subprocess.run(scp_cmd, check=True, timeout=600)
    load_cmd = [
        "ssh", "-i", campaign_key, "-p", server_port, "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null", "-o", "BatchMode=yes",
        f"ec2-user@{ip}",
        f"gunzip -c ~/{tarball} | docker load && rm -f ~/{tarball}",
    ]
    subprocess.run(load_cmd, check=True, timeout=300)
PY
REMOTE

    echo "    Comparing loaded image ID across every '$inventory_key' host (Decision 55 -- ID, not a registry digest)..."
    # Item 1 (an earlier turn): `docker images -q | head -1` picked
    # WHICHEVER image happened to be first in `docker images`'s own
    # listing order -- fine by coincidence when a host has exactly one
    # image loaded, silently wrong the moment it has more than one.
    # Pinned to the EXACT image name/tag this loop is already
    # delivering, via Python's own string formatting (no shell quoting
    # to get wrong). Also now APPENDS to
    # /home/ec2-user/delivered_images_manifest.json on the control
    # instance -- item 1's own pre-flight check (campaign_run.py's
    # pre_block_checks()) reads this file locally (it runs ON the
    # control instance) to compare against what's ACTUALLY loaded on a
    # server at block-start time, catching drift between delivery and a
    # later, unexpected reload.
    ssh "${SSH_OPTS[@]}" "ec2-user@${CONTROL_IP}" env MOCKOPIN_SERVER_SSH_PORT="$SSH_PORT" bash -s -- "$image" "$inventory_key" <<'REMOTE'
set -euo pipefail
IMAGE="$1"
INVENTORY_KEY="$2"
python3 - "$IMAGE" "$INVENTORY_KEY" <<'PY'
import json, os, subprocess, sys
image, inventory_key = sys.argv[1], sys.argv[2]
raw = json.load(open("/home/ec2-user/inventory.json"))
inv = raw["value"] if "value" in raw else raw
campaign_key = "/home/ec2-user/.ssh/campaign_key"
server_port = os.environ.get("MOCKOPIN_SERVER_SSH_PORT", "22")
ids = {}
for name, data in inv[inventory_key].items():
    ip = data["public_ip"]
    cmd = ["ssh", "-i", campaign_key, "-p", server_port, "-o", "StrictHostKeyChecking=no",
           "-o", "UserKnownHostsFile=/dev/null", "-o", "BatchMode=yes",
           f"ec2-user@{ip}", "docker", "image", "inspect", "-f", "{{.Id}}", image]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise SystemExit(f"FATAL: 'docker image inspect {image}' failed on {name} ({ip}):\n{r.stderr}")
    ids[name] = r.stdout.strip()
print(f"Image IDs per '{inventory_key}' host for {image}:", ids)
if len(set(ids.values())) != 1:
    raise SystemExit(f"FATAL: image IDs differ across '{inventory_key}' hosts for {image} -- {ids}")
image_id = next(iter(ids.values()))
print(f"OK: identical image ID on all {len(ids)} '{inventory_key}' host(s): {image_id}")

manifest_path = "/home/ec2-user/delivered_images_manifest.json"
try:
    manifest = json.load(open(manifest_path))
except FileNotFoundError:
    manifest = {}
manifest[image] = image_id
json.dump(manifest, open(manifest_path, "w"), indent=2)
print(f"Recorded in {manifest_path}.")
PY
REMOTE

    echo "    Removing the local control-instance copy of the tarball..."
    ssh "${SSH_OPTS[@]}" "ec2-user@${CONTROL_IP}" "rm -f ~/$(basename "$tarball") ~/$(basename "$tarball").sha256"
  done
}

deliver_image_set "servers" "${IMAGES[@]}"
deliver_image_set "clients" "${CLIENT_IMAGES[@]}"

echo "==> deliver_images.sh completed for all $(( ${#IMAGES[@]} + ${#CLIENT_IMAGES[@]} )) images (${#IMAGES[@]} server + ${#CLIENT_IMAGES[@]} client)."
