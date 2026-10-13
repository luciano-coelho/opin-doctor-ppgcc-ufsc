#!/usr/bin/env bash
# Copy this file to campaign.vars.local.sh (gitignored -- never commit
# the copy), fill in the real paths, then pass it as the first argument
# to every campaign_*.sh script.
#
#   cp campaign.vars.example.sh campaign.vars.local.sh
#   # edit campaign.vars.local.sh
#   ./campaign_up.sh campaign.vars.local.sh

export MOCKOPIN_AWS_PROFILE="mockopin-pqc"

# The operator's OWN, already-existing discovery key pair (same one
# used throughout this project) -- NOT the campaign-exclusive key, which
# Terraform generates itself and campaign_up.sh distributes on its own.
export MOCKOPIN_OPERATOR_SSH_PUBLIC_KEY_FILE="/path/to/mockopin_pqc_discovery.pub"
export MOCKOPIN_OPERATOR_SSH_PRIVATE_KEY_FILE="/path/to/mockopin_pqc_discovery"

# No default on purpose (Decision 52) -- Decision 43's launch test hasn't
# resolved which type to use yet. Must be set explicitly, every time.
export MOCKOPIN_SERVER_CLIENT_INSTANCE_TYPE="REPLACE_ME"

# Optional -- override the default fixed UTC window times (19:00 today/
# tomorrow, 03:00 the next day, 11:00 that same day). ISO-8601 UTC.
# export MOCKOPIN_WINDOW1_START_UTC="2026-10-13T19:00:00Z"
# export MOCKOPIN_WINDOW2_START_UTC="2026-10-14T03:00:00Z"
# export MOCKOPIN_WINDOW3_START_UTC="2026-10-14T11:00:00Z"
