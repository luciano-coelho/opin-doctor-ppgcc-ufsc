#!/bin/bash
set -euo pipefail
# Decision 71: neither docker nor rsync ship on the Amazon Linux 2023
# base AMI by default (confirmed empirically: `docker run --rm
# amazonlinux:2023 sh -c "command -v docker"`/`rsync` both find
# nothing). Software-inventory audit (this turn): the SAME empirical
# check against the pinned "minimal" AL2023 variant (al2023-ami-minimal-*,
# what this project actually launches) found FIVE MORE tools missing
# that campaign_run.py already calls remotely via bare command names --
# chronyc, ping, ss, flock, tcpdump -- none of which the orchestrator's
# own abort-on-missing checks would have caught before first use on a
# real instance (chrony/tcpdump failures were the closest to being
# caught -- Decision 63's own abort-on-missing-tcpdump path -- but
# chronyc/ping/flock/ss had no such guard at all). Installed
# unconditionally on EVERY instance (server, client, control) -- see
# this file's own locals block in main.tf for why role-gating isn't
# used here; it's simpler and cheaper (a few more dnf packages) than
# tracking which role needs which subset, and every tool here is small.
# Integrated rehearsal (this turn), real amazonlinux:2023 containers,
# zero pre-installed: found TWO more real gaps neither earlier audit
# caught, both load-bearing for deliver_source.sh's own two jobs --
# `tar` (AL2023 minimal doesn't ship it either; without it the
# `tar -xzf` extraction step on every server/client fails outright,
# "tar: command not found") and `python3-pip` (needed for
# deliver_source.sh's own last step, `pip3 install --user -r
# requirements.txt` -- without it, "pip3: command not found").
dnf install -y docker rsync chrony tcpdump iputils iproute util-linux-core tar python3-pip
systemctl enable --now docker
systemctl enable --now chronyd
# ec2-user needs to be in the docker group because this project's own
# SSH commands (campaign_run.py, deliver_images.sh) call `docker ...`
# directly, never `sudo docker ...` -- group membership only takes
# effect for NEW login sessions, which is exactly what every SSH
# command here already is (a fresh session per command), so this
# applies cleanly from the very first orchestrator SSH call onward.
usermod -aG docker ec2-user

# Integrated rehearsal (this turn): `dnf install -y docker` does NOT
# include the `docker compose` CLI plugin on AL2023 -- confirmed, no
# `docker-compose-plugin`-equivalent package exists in AL2023's own
# repos at all (`dnf search compose` returns nothing relevant).
# switch_crypto_profile.py's own `docker compose up -d --force-recreate
# ...` call (every real profile switch, every settling sequence) would
# fail outright on a real instance with "'compose' is not a docker
# command" -- caught live, this turn, the first time this rehearsal
# actually tried to switch a profile for real, not by reading the code.
# Installed from the official docker/compose GitHub release, pinned to
# an exact version and verified against its own published sha256 --
# BOTH the x86_64 and aarch64 assets were actually downloaded and
# re-hashed this turn (not just copied from GitHub's own published
# .sha256 file) to confirm the pin is correct for either architecture
# before it ever ships in this script.
#
# Role-gated by architecture, not installed unconditionally like the
# rest of this file: in this project's own topology, arm64 means the
# CONTROL instance (t4g.micro, the only arm64 role), and control never
# runs `docker compose` at all -- campaign_run.py never calls it;
# only switch_crypto_profile.py does, and that always runs on a
# SERVER (x86_64). Installing a compose binary control will never use
# would be the same kind of unexamined "install everywhere" this
# file's own Decision 71 rationale otherwise argues FOR (sameness over
# tracking per-role subsets) -- this one specific binary is cheap to
# skip correctly because the architecture check already has to exist
# anyway, to pick the right asset.
if [ "$(uname -m)" = "x86_64" ]; then
  DOCKER_COMPOSE_VERSION="v5.6.0"
  case "$(uname -m)" in
    x86_64)
      DOCKER_COMPOSE_ASSET="docker-compose-linux-x86_64"
      DOCKER_COMPOSE_SHA256="40343e21ca777173e69cff5dbafeb37c6f81f3b0d57d9e597f036e95eb63e76a"
      ;;
    aarch64)
      DOCKER_COMPOSE_ASSET="docker-compose-linux-aarch64"
      DOCKER_COMPOSE_SHA256="733ec76717ceb59052a9609b9dadfb523b2df8eab57a54212872d10a58078ea2"
      ;;
    *)
      echo "FATAL: unrecognized architecture $(uname -m) -- no pinned docker-compose checksum for it." >&2
      exit 1
      ;;
  esac
  mkdir -p /usr/libexec/docker/cli-plugins
  curl -fsSL -o /usr/libexec/docker/cli-plugins/docker-compose \
    "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/${DOCKER_COMPOSE_ASSET}"
  echo "${DOCKER_COMPOSE_SHA256}  /usr/libexec/docker/cli-plugins/docker-compose" | sha256sum -c -
  chmod +x /usr/libexec/docker/cli-plugins/docker-compose
else
  echo "Skipping docker compose plugin install -- $(uname -m) is not x86_64, meaning this is the control instance, which never runs 'docker compose' (only switch_crypto_profile.py does, always on a server)."
fi
