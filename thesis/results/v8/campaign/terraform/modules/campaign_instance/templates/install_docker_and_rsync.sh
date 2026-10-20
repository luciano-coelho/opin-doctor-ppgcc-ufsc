#!/bin/bash
set -euo pipefail
# Item 2 (this turn): neither docker nor rsync ship on the Amazon Linux
# 2023 base AMI by default (confirmed empirically for both --
# `docker run --rm amazonlinux:2023 sh -c "command -v docker"`/`rsync`
# both find nothing, dnf has both packages directly, no extras repo
# needed unlike Amazon Linux 2). Applied to EVERY instance (server,
# client, control) -- see this file's own locals block in main.tf for
# why both are unconditional now instead of role-gated.
dnf install -y docker rsync
systemctl enable --now docker
# ec2-user needs to be in the docker group because this project's own
# SSH commands (campaign_run.py, deliver_images.sh) call `docker ...`
# directly, never `sudo docker ...` -- group membership only takes
# effect for NEW login sessions, which is exactly what every SSH
# command here already is (a fresh session per command), so this
# applies cleanly from the very first orchestrator SSH call onward.
usermod -aG docker ec2-user
