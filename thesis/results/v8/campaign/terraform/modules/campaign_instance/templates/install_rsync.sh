#!/bin/bash
set -euo pipefail
# Item 2 (this turn): rsync is NOT present on the Amazon Linux 2023 base
# AMI by default -- confirmed empirically (`docker run --rm
# amazonlinux:2023 sh -c "command -v rsync"` finds nothing). Only the
# control instance needs it (the receiving end of deliver_images.sh's
# first leg, operator -> control); servers only receive a plain `scp`
# from control, which needs no rsync. deliver_images.sh/campaign_pull.sh
# already fall back to scp+split-parts when rsync is missing
# (have_rsync_on_control()), so this is not a hard dependency -- just
# the faster, natively-resumable path instead of tolerating its absence.
dnf install -y rsync
