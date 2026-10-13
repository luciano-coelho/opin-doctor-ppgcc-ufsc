#!/usr/bin/env bash
# Decision 57: for the commit, bundles each (scenario, window)'s
# per-execution pcaps into ONE file -- preserving one file per execution
# INSIDE it, not concatenating their contents. Each run{NN}.pcap.gz is
# already gzip-compressed on its own (Decision 42); re-gzipping already-
# compressed data buys essentially nothing and costs CPU, so this uses
# plain `tar` (no extra -z) as the bundle container, not `tar.gz` --
# "um arquivo comprimido" here means a single file whose CONTENTS are
# compressed, which plain tar over already-gzipped members already is.
#
# Run against a pulled copy (campaign-data-pulled/v8/...) or directly
# against the repo tree (thesis/results/v8/latency/...) -- both have the
# identical layout (Decision 53).
#
# Usage: package_pcaps.sh <v8-latency-root>
#   e.g. package_pcaps.sh ./campaign-data-pulled/v8/latency
#        package_pcaps.sh thesis/results/v8/latency
set -euo pipefail

ROOT="${1:?Usage: package_pcaps.sh <v8-latency-root>}"
if [ ! -d "$ROOT" ]; then
  echo "FATAL: $ROOT is not a directory." >&2
  exit 1
fi

count=0
# Each scenario directory has server/ and client/ subdirs, each holding
# run{NN}.pcap.gz, 1..30 across 3 windows (10 runs/window). Bundle per
# window, per side, per scenario -- window01.pcaps.tar holds that
# window's 10 run pcaps for that one side.
while read -r side_dir; do
  for window in 01 02 03; do
    start=$(( (10#$window - 1) * 10 + 1 ))
    end=$(( 10#$window * 10 ))
    members=()
    for i in $(seq -f "%02g" "$start" "$end"); do
      f="$side_dir/run${i}.pcap.gz"
      [ -f "$f" ] && members+=("$(basename "$f")")
    done
    if [ "${#members[@]}" -eq 0 ]; then
      continue # nothing captured yet for this window on this side -- not an error, just not run yet
    fi
    bundle="$side_dir/window${window}.pcaps.tar"
    echo "==> $bundle <- ${#members[@]} file(s): ${members[*]}"
    tar -cf "$bundle" -C "$side_dir" "${members[@]}"
    # Remove the now-bundled originals only after the tar is verified
    # readable -- never destroy data on an unverified archive.
    tar -tf "$bundle" >/dev/null
    for m in "${members[@]}"; do
      rm -f "$side_dir/$m"
    done
    count=$((count + 1))
  done
done < <(find "$ROOT" -type d \( -name server -o -name client \))

echo "==> package_pcaps.sh completed: $count bundle(s) created."
