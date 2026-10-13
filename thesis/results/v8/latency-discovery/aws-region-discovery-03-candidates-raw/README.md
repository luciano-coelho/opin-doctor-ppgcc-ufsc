# AWS region discovery — candidate-region raw latency data

## What this is

A small, targeted follow-up to the main mesh discovery
(`../aws-region-discovery-02-full-mesh-raw/`): real ICMP RTT between the two
candidate regions proposed in `DECISIONS.md` (Decision 10) —
`ap-northeast-2` (Seoul) and `eu-north-1` (Stockholm) — and their proposed
partners already in the main 10-region set (`ap-northeast-1`, `eu-west-1`,
`eu-central-1`). This exists because the main mesh found no real region
pair matching the 30ms target within ±20% tolerance (24-36ms) among the
original 10 regions — see Decision 10's "Open decision for the author."

## Why it's kept

Same reasons as the other discovery data: traceability (any region
eventually chosen for the 30ms scenario is backed by a real measurement,
not a guess) and reproducibility.

## Measurement topology

Same jump-host pattern as the main mesh (`sa-east-1` as the one
SSH-reachable instance, proxied access to the other 5), but only 6
regions total, not the full 10 — `sa-east-1`, `ap-northeast-1`,
`ap-northeast-2`, `eu-west-1`, `eu-central-1`, `eu-north-1`. Every region
pinged every other (30 directed pairs), but only the 3 pairs actually
proposed as 30ms candidates matter here; the rest is incidental bonus
data from reusing the same mesh script.

## How it was collected

- **Instance type:** `t4g.micro`, same as all other discovery runs —
  availability in `ap-northeast-2` and `eu-north-1` is confirmed by this
  run itself (the instances launched successfully).
- **Samples:** `ping -c 20` per pair, **1 round only** (not the usual 3
  rounds / ~1h gaps) — this was explicitly a quick first look, not the
  full validated measurement. `MOCKOPIN_DISCOVERY_ROUNDS=1` was set for
  this run via the normal `discover_latency_mesh.py`/env-var mechanism.
- **Terraform root:** `../terraform-candidates/` — a separate, smaller
  Terraform config from the main `../terraform/` 10-region mesh, reusing
  the same `../terraform/modules/prober` module. Created and destroyed
  within this single run; not meant to be a permanent fixture.

## Results (2026-10-11, single round, 20 samples/pair)

| Pair | Median RTT | Target (30ms, ±20%) | In tolerance? |
|---|---|---|---|
| `ap-northeast-2` <-> `ap-northeast-1` (Seoul <-> Tokyo) | 33.2ms | 24-36ms | **yes** |
| `eu-north-1` <-> `eu-west-1` (Stockholm <-> Ireland) | 34.5ms | 24-36ms | **yes** |
| `eu-north-1` <-> `eu-central-1` (Stockholm <-> Frankfurt) | 23.7ms | 24-36ms | no (just below the lower bound) |

Both Seoul<->Tokyo and Stockholm<->Ireland land squarely within
tolerance. See `DECISIONS.md`, Decision 12, for the full discussion and
what this means for Phase 4.

## Files

- `latency_mesh_samples.json` — raw per-packet RTT samples (single round).
  Same format as the main mesh's file, written by the same script.

Contains only region names, IP addresses, and millisecond RTT numbers —
no AWS account ID, no credential. Confirmed by inspection.

## Reproducing

```bash
cd ../terraform-candidates
terraform init
terraform apply -var-file=/path/to/your.tfvars.json
cd ../scripts
export MOCKOPIN_SSH_KEY=/path/outside/repo/mockopin_pqc_discovery
export MOCKOPIN_TERRAFORM_DIR=terraform-candidates
export MOCKOPIN_RESULTS_DIR=../aws-region-discovery-03-candidates-raw
export MOCKOPIN_DISCOVERY_ROUNDS=1   # or 3 for full rigor, matching the other runs
python discover_latency_mesh.py
cd ../terraform-candidates
terraform destroy -var-file=/path/to/your.tfvars.json
```

**Note the `MOCKOPIN_RESULTS_DIR` value above is `../aws-region-discovery-03-candidates-raw`
relative to `scripts/`** (i.e. `latency-discovery/aws-region-discovery-03-candidates-raw`) —
get this path wrong and the output lands one level too high. Verify
`candidate_public_ips`/`prober_public_ip` appear in `terraform output`
before running the Python script, and check where the JSON actually
landed afterward.

## Status

**Collected 2026-10-11**, single round only (not the full 3-round/~1h-gap
rigor used elsewhere in this project) — a quick first look, confirmed
promising enough to report. If either candidate is adopted for Phase 4,
consider a full 3-round confirmation run before locking it in, consistent
with the rest of this project's sampling standard.
