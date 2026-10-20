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
dnf install -y docker rsync chrony tcpdump iputils iproute util-linux-core
systemctl enable --now docker
systemctl enable --now chronyd
# ec2-user needs to be in the docker group because this project's own
# SSH commands (campaign_run.py, deliver_images.sh) call `docker ...`
# directly, never `sudo docker ...` -- group membership only takes
# effect for NEW login sessions, which is exactly what every SSH
# command here already is (a fresh session per command), so this
# applies cleanly from the very first orchestrator SSH call onward.
usermod -aG docker ec2-user
