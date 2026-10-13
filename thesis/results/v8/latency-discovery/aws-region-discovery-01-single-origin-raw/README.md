# AWS region discovery — raw latency data

## What this is

Raw ICMP RTT samples from `sa-east-1` (the thesis's server region) to each
of 9 candidate AWS regions, collected to pick — empirically, not from
assumption — which 5 real region-pairs best approximate v1-v7's simulated
`tc`/`netem` latency targets (14/30/140/225/320ms). See `DECISIONS.md`
("Decision 3: Region selection is empirical, not assumed" and the dated
discovery-results decision) and `../../README.md` (the main v8 README) for
the full experiment context.

## Why it's kept

- **Traceability.** The 5 regions used in the main experiment (Phase 4)
  were chosen by this data, not guessed — anyone reviewing the thesis can
  see exactly which measurement justified which choice.
- **Reproducibility.** Running `discover_latency.py` again (e.g. to
  sanity-check before Phase 4, or if AWS network paths shift over time)
  produces directly comparable output in the same format.

## Measurement origin and topology

All RTT is measured **from the `sa-east-1` prober instance**, against
each of the 9 candidate instances — a single fixed origin against 9
destinations, not all-to-all. This matches the real experiment's topology
(Phase 4: server fixed in `sa-east-1`, client relocated per scenario), so
the measured RTT is the one that actually matters for the thesis, not a
generic mesh of unrelated region pairs.

## How it was collected

- **Instance type:** `t4g.micro` (free-tier-eligible, disposable;
  Amazon Linux 2023, arm64).
- **Tool:** ICMP `ping`, run over SSH from the `sa-east-1` instance against
  each candidate's public IP.
- **Samples:** `ping -c 20` per region per round (20 individual RTT
  samples), repeated across multiple rounds spaced by real time gaps so
  the distribution isn't a single time-of-day snapshot. Round count and
  gap are recorded in `latency_samples.json` itself
  (`rounds[].started_at_utc`).
- **Aggregation:** `select_regions.py` pools every sample from every round
  per region and reports median/min/max/n — median is what drives region
  selection (less sensitive to one-off spikes than a mean would be).

## Files

- `latency_samples.json` — raw per-packet RTT samples, grouped by round and
  region. Written by `discover_latency.py`. Structure:
  ```json
  {
    "origin_region": "sa-east-1",
    "instance_type": "t4g.micro",
    "ping_count_per_round": 20,
    "rounds": [
      {
        "round": 1,
        "started_at_utc": "2026-...",
        "samples": { "us-east-1": [12.3, 12.1, ...], "...": [...] }
      }
    ]
  }
  ```
- `region_selection.json` — derived from the above by `select_regions.py`:
  per-region median/min/max/n, plus the final target→region selection.
  Not raw data; regenerable from `latency_samples.json` at any time.

Both files contain only region names, IP addresses, and millisecond RTT
numbers — no AWS account ID, no credential, no identifier beyond that.
Confirmed by inspection before this README was written; re-confirm the
same way if you regenerate the data.

## Reproducing

See `../../README.md` (the main v8 README), section "Phase 2 — Running the
latency discovery", for the full apply → measure → destroy sequence.

## Status

**Collected 2026-10-08**, 03:00-05:10 UTC (3 rounds, ~1h apart). See
`latency_samples.json` (raw) and `region_selection.json` (derived) in this
directory, and `../../DECISIONS.md` (Decision 9, the main v8 decisions
log) for the full results table and region-selection rationale, including
an open
caveat about the 14ms/30ms targets not being realistically reachable
inter-region (see Decision 9).
