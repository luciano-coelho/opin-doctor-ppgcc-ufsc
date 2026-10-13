# AWS region discovery — mesh raw latency data

## What this is

Raw ICMP RTT samples between **every pair** of the 10 AWS regions in this
project's IAM policy (not just `sa-east-1` against the other 9, which is
the earlier, narrower measurement in `../aws-region-discovery-01-single-origin-raw/`). See
`DECISIONS.md` (Decision 10) for the full rationale, and Decision 9 for
why that earlier single-origin measurement didn't find good matches for
the 14ms/30ms targets.

This directory is additive — `../aws-region-discovery-01-single-origin-raw/` is kept
untouched as the historical record of the first (single-origin) run.

## Why it's kept

Same reasons as the first discovery run: traceability (the region(s)
chosen for Phase 4 are backed by measured data, not guesses) and
reproducibility (anyone can re-run `discover_latency_mesh.py` and get
directly comparable output).

## Measurement topology

**Full mesh:** each of the 10 regions takes a turn as origin, pinging the
other 9 — 90 directed measurements (45 unique pairs × 2 directions) per
round. This also gives a free symmetry check: A→B and B→A are both
measured and can be compared directly (see `DECISIONS.md`, Decision 10).

**SSH access stays single-entry** even though ICMP is now mesh-wide: the
operator's machine only ever reaches `sa-east-1` directly; for the other 9
regions it uses `ssh -J` (ProxyJump) through `sa-east-1`. The private key
is used client-side for both hops and is never copied onto any EC2
instance.

## How it was collected

- **Instance type:** `t4g.micro` (free-tier-eligible, disposable; Amazon
  Linux 2023, arm64) — same as the first discovery run.
- **Tool:** ICMP `ping`, run over SSH (direct to `sa-east-1`, ProxyJump to
  the other 9) from each region's instance against each of the other 9
  regions' public IPs.
- **Samples:** `ping -c 20` per directed pair per round, repeated across
  multiple rounds spaced by real time gaps (`rounds[].started_at_utc` in
  the data file records exactly when). Round count and gap are the same
  defaults as the first run (3 rounds, ~1h apart), overridable via
  `MOCKOPIN_DISCOVERY_ROUNDS` / `MOCKOPIN_DISCOVERY_ROUND_GAP_SECONDS`.
- **Aggregation:** `select_regions_mesh.py` pools every sample per
  directed pair across rounds and reports median/min/max/n; selection is
  driven by median, within a ±20% tolerance band of each original v1-v7
  target (see Decision 10 for the exact bounds and the selection
  algorithm).
- **Measures ICMP RTT only**, not the TLS handshake path the real
  experiment uses — Phase 4 cross-checks against the real experiment's own
  pcap capture rather than assuming the two are identical (Decision 10).

## Files

- `latency_mesh_samples.json` — raw per-packet RTT samples, grouped by
  round and by directed pair (`"<origin>-><dest>"` keys). Written by
  `discover_latency_mesh.py`.
- `region_selection_mesh.json` — derived from the above by
  `select_regions_mesh.py`: median/min/max/n per directed pair, and the
  selection result (single qualifying origin if one covers all 5 targets
  within tolerance, or the reported-not-auto-applied mesh-wide best
  candidates if none does). Regenerable from `latency_mesh_samples.json`
  at any time.

Both files contain only region names, IP addresses, and millisecond RTT
numbers — no AWS account ID, no credential, no identifier beyond that.
Confirmed by inspection before this README was written (same check as the
first discovery run); re-confirm the same way if you regenerate the data.

## Reproducing

See `../../README.md` (the main v8 README), section "Phase 2b — Mesh
latency discovery", for the full apply → measure → destroy sequence.

## Status

**Collected 2026-10-11**, 00:27-01:40 UTC (3 rounds, ~1h apart). 90/90
directed pairs responded every round. See `latency_mesh_samples.json`
(raw) and `region_selection_mesh.json` (derived) in this directory, and
`../../DECISIONS.md` (Decision 10) for the full matrix and results
discussion — including an open decision, not yet resolved, about how to
handle the 30ms scenario (no region pair in this mesh matched it within
tolerance).
