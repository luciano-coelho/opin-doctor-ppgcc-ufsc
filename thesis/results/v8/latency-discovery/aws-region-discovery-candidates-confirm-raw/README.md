# AWS region discovery — candidate-pair confirmation raw data

## What this is

The full 3-round confirmation (same sampling standard as every other
discovery run in this project) of the two 30ms candidate pairs that a
quick single-round look (`../aws-region-discovery-candidates-raw/`) found
promising: `ap-northeast-2` ↔ `ap-northeast-1` (Seoul ↔ Tokyo) and
`eu-north-1` ↔ `eu-west-1` (Stockholm ↔ Ireland). See `DECISIONS.md`,
Decision 13, for the full results and the selection made from them.

## Why it's kept

Same reasons as every other discovery dataset here: traceability (the
30ms region chosen for Phase 4 is backed by a properly-sampled
measurement, not a single lucky round) and reproducibility.

## Measurement topology

Identical to `../aws-region-discovery-candidates-raw/`: 6 regions
(`sa-east-1` as SSH jump host + `ap-northeast-1`, `ap-northeast-2`,
`eu-west-1`, `eu-central-1`, `eu-north-1`), full mesh among them (30
directed pairs/round), only the 4 directed pairs between the two
candidate pairs matter for this decision — the rest is incidental bonus
data from reusing the same script.

## How it was collected

- **Instance type:** `t4g.micro`.
- **Samples:** `ping -c 20` per pair per round, **3 rounds, ~1h apart**
  (matching Decisions 9 and 10's standard — unlike the earlier
  single-round quick look). `MOCKOPIN_DISCOVERY_ROUNDS=3` (the script's
  default).
- **Terraform root:** `../terraform-candidates/` (same one reused from the
  quick look — applied fresh, destroyed again at the end of this run).

## Results (2026-10-11, 3 rounds, 20 samples/pair/round, both directions)

| Pair | Round 1 median | Round 2 median | Round 3 median | Pooled median | Pooled min–max | Round-to-round variation |
|---|---|---|---|---|---|---|
| `ap-northeast-2`→`ap-northeast-1` | 33.20 | 33.20 | 33.90 | 33.20 | 33.10–34.50 | 0.70 |
| `ap-northeast-1`→`ap-northeast-2` | 33.20 | 33.20 | 33.85 | 33.30 | 33.10–49.50* | 0.65 |
| `eu-north-1`→`eu-west-1` | 34.40 | 35.70 | 35.60 | 35.60 | 34.40–38.40 | 1.30 |
| `eu-west-1`→`eu-north-1` | 34.40 | 35.60 | 35.65 | 35.60 | 34.40–36.00 | 1.25 |

*One single-packet outlier (49.5ms, round 2) in an otherwise tight
33.1-34.0ms spread — doesn't move the median, noted for transparency.

**Selection: `ap-northeast-2` ↔ `ap-northeast-1` (Seoul ↔ Tokyo)**,
labeled **33.2ms (target 30ms)**. Wins on both criteria from
`DECISIONS.md`'s selection rule: closer to the 30ms target (+3.2ms vs.
Stockholm↔Ireland's +5.6ms) and lower round-to-round variation (~0.7ms
vs. ~1.3ms).

## Files

- `latency_mesh_samples.json` — raw per-packet RTT samples, all 3 rounds,
  all 30 directed pairs/round (most pairs beyond the 4 of interest are
  bonus data from reusing the full-mesh script on a 6-region subset).

Contains only region names, IP addresses, and millisecond RTT numbers —
no AWS account ID, no credential. Confirmed by inspection.

## Status

**Collected 2026-10-11**, 02:42–04:48 UTC. Infrastructure (18 resources
across 6 regions) destroyed and verified clean immediately after — see
`DECISIONS.md`, Decision 13.
