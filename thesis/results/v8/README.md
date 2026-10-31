# v8 — Real AWS cross-region latency experiment

Extends v1-v7 (simulated `tc`/`netem` latency) with the same experiment
run across **real** AWS regions. See `DECISIONS.md` for the full rationale.
v7 remains the thesis's official simulated-latency result; v8 is additive.

## Campaign complete, fleet destroyed (2026-10-31)

The real campaign described below as planned/in-progress has since
**run to completion and the fleet has been destroyed** -- the
"Status"/"Resuming" sections further down are kept as the historical
planning record, not current state. Summary:

- **3 official windows, 720 executions, 0 errors**, 3 server
  installations (`sa-east-1`, `us-east-1`, `ap-northeast-1`) x 8 real
  routes x 3 crypto profiles (Classic/PQC/Hybrid), Latin-square
  ordered (seed 0), K=5 warm-up per cell discarded.
- **Final report**: `Consolidated_Metrics_Report_FINAL.md` -- every
  number generated from `global_v2/report_data_v8_combined.json`/
  `consolidated_combined.json` by `thesis/scripts/generate_v8_final_
  report.py` + `render_v8_final_report.py`, independently re-verified
  by `thesis/scripts/audit_v8_from_raw.py` (0 divergences against the
  raw run files/pcaps).
- **Consolidate script, made canonical (Decision 117)**:
  `campaign/scripts/consolidate_v8.py` now has pcap-measured RTT,
  correctly-defined packet loss (retransmissions/segments only, never
  conflated with duplicate-ACK/out-of-order), and the k/delta/order
  models built in -- it is no longer the version with the two bugs
  this project's own review found (`consolidate_v8_legacy.py` keeps
  that old version for history only, never run again).
- **Destroy**: `terraform apply "tfdestroy"` (saved plan, not
  recalculated) -- 65 resources destroyed, confirmed via the real AWS
  API (`boto3`, not just Terraform's own exit code) across all 7
  regions the campaign used: 0 instances, key pairs, or tagged
  security groups remaining anywhere. Full details, fleet hours, and
  cost: `DECISIONS.md`, Decision 117.
- Tags: `v8-prereg`, `v8-prereg-3`, `v8-official-data`,
  `v8-official-data-2`, `v8-official-data-3` (current).

## Status (historical -- planning phase, see above for what actually ran)

- [x] **Phase 0** — AWS account, root MFA, dedicated IAM user
      (`mockopin-pqc-experiment`, EC2/VPC-only policy scoped to 10
      regions), $20/month budget alert, AWS CLI configured locally under
      profile `mockopin-pqc`.
- [x] **Phase 1** — Repository scaffold, discovery Terraform module
      (`latency-discovery/terraform/`), `latency-discovery/scripts/discover_latency.py` /
      `select_regions.py`, and the shared `scripts/destroy_all.sh`.
      Everything specific to latency discovery lives under
      `latency-discovery/`, separate from `DECISIONS.md`/`README.md`
      (whole-v8 scope) and `scripts/destroy_all.sh` (reused by Phase 4 too).
- [x] **Phase 2** — Discovery sweep run 2026-10-08 (3 rounds, 1h apart,
      20 pings/region/round, 60 samples/region total). All 10 regions up,
      measured, and destroyed cleanly (verified: no instance, security
      group, or key pair left in any region). See "Region selection
      results" below and `DECISIONS.md` (Decision 9).
- [x] **Phase 2b** — Mesh discovery (10 regions, then widened to 12 with
      the author's approval — `ap-northeast-2`, `eu-north-1`) and a full
      3-round confirmation of the two 30ms candidates found. See
      `DECISIONS.md` (Decisions 9-14 for the full discovery trail).
- [x] **Topology finalized (Decision 15)** — Phase 4 uses **one single
      MockOPIN installation, fixed in `sa-east-1`**; only the client
      relocates per scenario. This is a deliberate design choice (one
      installation is simpler to operate/reproduce than five), explicitly
      **not** a legal restriction — see Decision 15, and Decision 8 for why
      Brazil-data-residency doesn't constrain this experiment at all.
      140ms/225ms/320ms already have confirmed `sa-east-1`-anchored pairs
      with full 3-round data (Decision 16); 14ms/30ms are under
      investigation via AWS Local Zones — Buenos Aires/Santiago/Lima exist
      but aren't opted in, Terraform for the proposed test is written and
      `plan`-validated (not applied), waiting on the author (Decision 17,
      23). Instance sizing from **real peak-load measurement** across all
      3 crypto profiles (not just idle): `m6i.large` server (confirmed),
      `c6i.xlarge` clients — revised up from an earlier `t3.small` guess
      after finding the client-side PQC proxy bursts past 1000% CPU on
      multiple consecutive samples (Decision 21). **Topology**: the
      `sa-east-1` server stays up for the whole collection campaign, not
      rebuilt per scenario — only the ingress rule changes between
      scenarios (Decision 22).
- [ ] **Phase 3** — `opin_flow.py` adaptation (`REMOTE_GATEWAY_HOST`).
- [ ] **Phase 4** — Main experiment Terraform: single persistent
      `sa-east-1` server + relocating client, `m6i.large`/`c6i.xlarge`,
      full measurement battery. Security posture and collection protocol
      proposed in Decisions 19-20 (ingress-rule-per-scenario framing
      updated by Decision 22), not yet built.
- [ ] **Phase 5/6** — Teardown verification, results comparison vs. v7.

## Prerequisites

- AWS CLI, profile `mockopin-pqc` already configured (`aws configure
  --profile mockopin-pqc`, or see Phase 0 above — already done for this
  account).
- Terraform >= 1.5 on `PATH`.
- An SSH client (`ssh`, `ssh-keygen`).

## Phase 2 — Running the latency discovery

The discovery Terraform spins up one short-lived `t4g.micro` in
`sa-east-1` (the "prober") plus one in each of 9 candidate regions
(`us-east-1`, `us-east-2`, `us-west-2`, `ca-central-1`, `eu-west-1`,
`eu-central-1`, `ap-northeast-1`, `ap-southeast-1`, `ap-southeast-2`).
**Measurement topology:** a single fixed origin (`sa-east-1`) against all 9
candidates — not all-to-all — because that's the only path that matters:
it mirrors Phase 4's real topology (server fixed in `sa-east-1`, client
relocated per scenario). The prober SSHes out and pings every candidate to
get real AWS-to-AWS RTT (multiple rounds, spread across real time gaps —
see below), then everything is destroyed. Estimated cost: well under $1
(at most a few hours of `t4g.micro` runtime across 10 regions).

### Pre-apply checklist

Verify every item below before running `terraform apply`. If any fails,
stop and report instead of applying — don't proceed past a failed check.

- [x] Instances run **only** the ping-measurement tooling — no part of
      MockOPIN (no `docker-compose`, no `opin_flow.py`, nothing) is
      deployed to them. The Terraform module (`latency-discovery/terraform/`)
      provisions a bare Amazon Linux 2023 AMI with no user-data / startup
      script at all — confirm this is still true if the module is edited.
- [x] No credential, certificate, or real OPIN ecosystem data (including
      the Raidiam sandbox) is copied to any instance — same reason as
      above: nothing is provisioned onto these instances beyond the OS
      itself.
- [x] Measurement origin documented: single fixed origin (`sa-east-1`) vs.
      9 candidates (see "Measurement topology" above).
- [x] Security groups allow only what's necessary: SSH (22) on the
      `sa-east-1` prober only, from the operator's `/32` IP only; ICMP
      only on the 9 candidates, from the prober's `/32` IP only (see
      `DECISIONS.md`, Decision 7). No `0.0.0.0/0` rule anywhere.
- [x] Sampling: `discover_latency.py` runs `MOCKOPIN_DISCOVERY_ROUNDS`
      rounds (default 3) of 20 pings/region, spaced
      `MOCKOPIN_DISCOVERY_ROUND_GAP_SECONDS` apart (default 3600s = 1h) —
      i.e. samples span more than one time of day by default, not a
      single snapshot. `select_regions.py` reports median/min/max/n per
      region from the pooled samples.
- [ ] **225ms and 320ms reachability** — can only be confirmed by actually
      running the sweep. Typical real-world AWS inter-region RTT from
      `sa-east-1` suggests the Asia-Pacific candidates
      (`ap-northeast-1`/`ap-southeast-1`/`ap-southeast-2`) and
      `eu-central-1`/`eu-west-1` are plausible matches for 225-320ms, but
      this is an expectation, not a measurement. If `select_regions.py`
      reports a target as **NOT REACHABLE**, stop and report before doing
      anything else — widening the candidate-region list means widening
      the IAM policy (Decision 4), which is the author's call, not an
      automatic fallback.
- [x] `destroy_all.sh` verifies, per region, that no instance, security
      group, or key pair tagged `Project=mockopin-pqc-aws` /
      `mockopin-pqc-discovery` remains — not just instances.
- [x] AWS Budget alert (`mockopin-pqc-experiment`, $20/month) is active
      (Phase 0).

### Steps

1. Generate a throwaway SSH keypair **outside the repo** (e.g. in a local
   scratch directory — never commit a private key):

   ```bash
   ssh-keygen -t ed25519 -f /path/outside/repo/mockopin_pqc_discovery -N "" -C mockopin-pqc-discovery
   ```

2. Find your current public IP (`curl -s https://checkip.amazonaws.com`)
   and create a var file **outside the repo**:

   ```json
   {
     "my_ip_cidr": "YOUR.PUBLIC.IP.HERE/32",
     "ssh_public_key": "ssh-ed25519 AAAA... mockopin-pqc-discovery"
   }
   ```

3. Apply (with the author present — see `DECISIONS.md`):

   ```bash
   cd latency-discovery/terraform
   terraform init
   terraform plan  -var-file=/path/to/your.tfvars.json
   terraform apply -var-file=/path/to/your.tfvars.json
   ```

4. Run the RTT sweep (default: 3 rounds, 1h apart — adjust via the env
   vars below if a shorter/longer spread across times of day is wanted):

   ```bash
   export MOCKOPIN_SSH_KEY=/path/outside/repo/mockopin_pqc_discovery
   # optional overrides:
   # export MOCKOPIN_DISCOVERY_ROUNDS=3
   # export MOCKOPIN_DISCOVERY_ROUND_GAP_SECONDS=3600
   python3 ../scripts/discover_latency.py
   python3 ../scripts/select_regions.py
   ```

   This writes `latency-discovery/aws-region-discovery-01-single-origin-raw/latency_samples.json`
   (every raw RTT sample, by round) and
   `latency-discovery/aws-region-discovery-01-single-origin-raw/region_selection.json`
   (median/min/max per region + the 5 chosen regions), and prints two
   Markdown tables — paste both into this README's "Region selection
   results" section and into a new `DECISIONS.md` entry once generated, so
   the region choice stays transparent and auditable. See
   `latency-discovery/aws-region-discovery-01-single-origin-raw/README.md` for the data format.

5. **Destroy immediately after** (discovery instances have no reason to
   stay up):

   ```bash
   ../../scripts/destroy_all.sh /path/to/your.tfvars.json
   ```

   The script verifies, per region, that no tagged instance, security
   group, or key pair was left behind, and fails loudly (non-zero exit) if
   anything is.

## Region selection results

Measured 2026-10-08, origin `sa-east-1`, 3 rounds × 20 pings/region spread
across ~1h gaps (60 samples/region total). Full raw data:
`latency-discovery/aws-region-discovery-01-single-origin-raw/latency_samples.json`; derived stats:
`latency-discovery/aws-region-discovery-01-single-origin-raw/region_selection.json`.

### All regions measured

| Region | Median (ms) | Min (ms) | Max (ms) | Samples |
|---|---|---|---|---|
| us-east-1 | 112.00 | 112.00 | 112.00 | 60 |
| us-east-2 | 120.00 | 112.00 | 122.00 | 60 |
| ca-central-1 | 123.00 | 123.00 | 124.00 | 60 |
| us-west-2 | 172.00 | 172.00 | 172.00 | 60 |
| eu-west-1 | 176.00 | 176.00 | 176.00 | 60 |
| eu-central-1 | 201.00 | 201.00 | 201.00 | 60 |
| ap-northeast-1 | 257.00 | 257.00 | 268.00 | 60 |
| ap-southeast-2 | 308.00 | 308.00 | 309.00 | 60 |
| ap-southeast-1 | 326.00 | 322.00 | 342.00 | 60 |

### Selected regions per scenario

| Target (ms) | Region | Median RTT (ms) | Delta |
|---|---|---|---|
| 14 | us-east-1 | 112.00 | +98.00 |
| 30 | us-east-2 | 120.00 | +90.00 |
| 140 | ca-central-1 | 123.00 | -17.00 |
| 225 | eu-central-1 | 201.00 | -24.00 |
| 320 | ap-southeast-1 | 326.00 | +6.00 |

**Open question before Phase 4:** the 14ms and 320ms targets land at very
different fidelities. 320ms is matched almost exactly (+6ms). 14ms and
30ms are not reachable by any real AWS inter-region pair from `sa-east-1`
at all — ~110ms is close to the physical floor for continental
inter-region RTT, so the nearest real regions overshoot both low targets
by +90-98ms. This suggests the original v1-v7 14/30ms scenarios may have
been modeling same-region/LAN-scale latency rather than inter-region
latency — worth confirming against Schardong et al.'s methodology (to the
extent accessible) before treating `us-east-1`/`us-east-2` as valid
stand-ins for those two scenarios in the final comparison. See
`DECISIONS.md`, Decision 9, for the full discussion.

## Phase 2b — Mesh latency discovery

Approved 2026-10-08 after Phase 2 found no real-region match for the
14ms/30ms targets: that measurement only tried `sa-east-1` as origin.
Phase 2b measures **every pair** of the same 10 regions against each
other (90 directed measurements/round: 45 unique pairs × 2 directions),
to check whether some *other* region is a better fixed-server candidate,
or whether 14ms/30ms simply aren't reachable from any AWS region pair at
all. See `DECISIONS.md`, Decision 10, for the full design (why ICMP opens
to `0.0.0.0/0` while SSH stays single-entry via `sa-east-1`, the ±20%
tolerance bands, and the selection algorithm).

**Important:** the result depends on what gets measured at run time — the
specific regions and deltas in this README are whatever the latest sweep
produced, not a fixed design decision. Re-running `discover_latency_mesh.py`
can produce different numbers (network paths change), and the selection
should always be read as "as measured on `<date>`," not as a permanent
assignment.

Same regions, same IAM policy — no policy change needed. Estimated cost
and duration are essentially the same as Phase 2 (same 10 `t4g.micro`
instances, same ~2h10min wall-clock dominated by the two 1h inter-round
gaps): well under $1, ~2h10min end-to-end. **Keep the machine on and
connected for the full run** — it's one unattended background process
from apply through final teardown, but the machine itself needs to stay
up throughout.

### Steps

1-2. Same as Phase 2 (SSH keypair + var file) — reuse the existing ones if
   you still have them; regenerate if not (same format).

3. Apply (with the author present):

   ```bash
   cd latency-discovery/terraform
   terraform plan  -var-file=/path/to/your.tfvars.json
   terraform apply -var-file=/path/to/your.tfvars.json
   ```

4. Run the mesh sweep + selection + teardown (same pattern as Phase 2 —
   can be chained into one background run):

   ```bash
   export MOCKOPIN_SSH_KEY=/path/outside/repo/mockopin_pqc_discovery
   python3 ../scripts/discover_latency_mesh.py
   python3 ../scripts/select_regions_mesh.py
   ../../scripts/destroy_all.sh /path/to/your.tfvars.json
   ```

   Writes `latency-discovery/aws-region-discovery-02-full-mesh-raw/latency_mesh_samples.json`
   (raw) and `latency-discovery/aws-region-discovery-02-full-mesh-raw/region_selection_mesh.json`
   (derived), and prints the 10×10 matrix, the symmetry check, and the
   selection result (or, if no single origin covers all 5 targets within
   tolerance, the best mesh-wide candidates per target, flagged as
   pending author confirmation rather than auto-applied).

## Mesh selection results

Measured 2026-10-11, 00:27-01:40 UTC, all 10 regions as origin against the
other 9 (90 directed pairs, 3 rounds, 60 samples/pair). 90/90 pairs
responded every round — no missing data. Symmetry: max |A→B − B→A| across
all 45 pairs was 1.0ms. Full data:
`latency-discovery/aws-region-discovery-02-full-mesh-raw/latency_mesh_samples.json`;
derived stats: `.../region_selection_mesh.json`. Full matrix and discussion
in `DECISIONS.md`, Decision 10.

| Target | Best pair | Measured | Delta | In tolerance (±20%)? |
|---|---|---|---|---|
| 14ms | us-east-1→ca-central-1 | 15ms | +0.7 | yes |
| 30ms | eu-west-1→eu-central-1 | 20ms | -10.4 | **no** |
| 140ms | us-west-2→ap-southeast-2 | 140ms | +0.0 | yes |
| 225ms | eu-central-1→ap-northeast-1 | 226ms | +1.0 | yes |
| 320ms | sa-east-1→ap-southeast-1 | 325ms | +5.0 | yes |

**No single origin covers all 5 targets within tolerance** — checked
exhaustively across all 10 regions, not just `sa-east-1`. The 4 good
matches come from **4 different origin regions** (`us-east-1`,
`us-west-2`, `eu-central-1`, `sa-east-1` — no two sharing one), not a
single-origin coverage gap. 30ms has no match anywhere in this
**10-region** mesh — the matrix shows a gap between ~13-20ms neighbors and
the next tier at ~60ms+ among these specific 10 regions. This is not a
claim about AWS's full region footprint (34+ regions exist; this mesh
tested 10) — confirmed: see "30ms gap closed" below.

### 30ms gap closed (Decision 12)

With the author's approval, the IAM policy was widened by exactly 2
regions (`ap-northeast-2`, `eu-north-1` — see `DECISIONS.md`, Decision 11
for the exact change and verification). A quick single-round check found
**two real pairs inside the 30ms tolerance band**:

| Pair | Measured | In tolerance (24-36ms)? |
|---|---|---|
| `ap-northeast-2` ↔ `ap-northeast-1` (Seoul ↔ Tokyo) | 33.2ms | **yes** |
| `eu-north-1` ↔ `eu-west-1` (Stockholm ↔ Ireland) | 34.5ms | **yes** |

Full data: `latency-discovery/aws-region-discovery-03-candidates-raw/`. This
was a fast single-round look, not the full 3-round standard used
elsewhere — confirmed properly below.

### Final scenario pairs — SUPERSEDED by Decision 15, see below

_(The single-origin check and the 30ms Seoul↔Tokyo confirmation this
section described are still accurate, measured facts — see `DECISIONS.md`,
Decision 13 for them, kept for the record. What's superseded is the
**topology conclusion**: "independent pair per scenario." Decision 15
replaced that with a single fixed `sa-east-1` installation instead, by
deliberate design choice, not because the finding was wrong — see
`DECISIONS.md`, Decision 15 for the full reasoning, and "Scenario clients"
below for the current plan.)_

### Final Phase 4 topology: 8 scenarios (L0 per server), labeled by measured RTT (Decisions 30, 53)

**The experiment's focus is application behavior as a function of latency
level, not of region** — scenarios are labeled only by their measured
RTT, never by region name or the original nominal target. Internally,
scenarios use fixed short names (`L0`, `L14`, `L30`, `L123`, `L219`,
`L325`) — region names are implementation detail, documented here and in
`DECISIONS.md`, never part of the scenario's identity.

| Internal name | Server | Client | Notes |
|---|---|---|---|
| `L0` | `sa-east-1` | same AZ ID, private IP (co-located) | region + same-machine-type control |
| `L0` | `us-east-1` | same AZ ID, private IP (co-located) | region + same-machine-type control |
| `L0` | `ap-northeast-1` | same AZ ID, private IP (co-located) | region + same-machine-type control |
| `L14` (14.7ms) | `us-east-1` | `ca-central-1` | 3 rounds, 60 samples/direction |
| `L30` (33.2ms) | `ap-northeast-1` | `ap-northeast-2` | 3 rounds confirmed, ~0.7ms round-to-round variation |
| `L123` (123ms) | `sa-east-1` | `ca-central-1` | 3 rounds, 60 samples/direction |
| `L219` (219ms) | `sa-east-1` | `eu-north-1` | 4 rounds (1+3), 80 samples/direction |
| `L325` (325ms) | `sa-east-1` | `ap-southeast-1` | 3 rounds, 60 samples/direction |

**3 server installations, not 1, each with its own `L0`** — `sa-east-1`
covers 4 of 8 scenarios (Decision 1's thematic rationale remains the
dominant choice), `us-east-1`/`ap-northeast-1` each cover 2 (their own
`L0` plus `L14`/`L30`). This supersedes Decision 15's single-installation
design (kept in `DECISIONS.md`, not deleted) — not because that reasoning
was wrong, but because the AWS Local Zone path to a
`sa-east-1`-reachable 14ms/30ms hit a hard account-level blocker (below),
while 14.7ms and 33.2ms were *already* sitting there as real,
properly-sampled, unused measurements. Decision 22's "server stays up
for the whole campaign" rule applies per installation, not globally.
**Each server's own `L0` is not just "the lowest scenario" repeated three
times** — it doubles as a region control and a same-machine-type control
(Decision 53), since the region-control *procedure* itself was discarded
(Decision 39) but these three real measurements answer a similar question
for free. See `DECISIONS.md`, Decisions 30, 41, 53 for the full
reasoning, including the pre-registered, descriptive-only comparison
criterion for the three `L0`s.

**720 executions total** (8 scenarios x 3 profiles x 30 runs), across
**12 instances** (3 servers + 8 clients + 1 control instance, never a
client or server itself). Infrastructure for all of this
(`thesis/results/v8/campaign/`) is prepared and `terraform plan`-clean
(45 resources) but **not applied** — see `DECISIONS.md`, Decisions
49-59.

**Within a profile block, executions round-robin across that server's
scenarios** (run 1 of every scenario, then run 2 of every scenario, …),
not scenario-by-scenario — spreads any within-block time drift evenly
across scenarios instead of letting ordering itself become a confound
(Decision 56, supersedes Decision 40's ordering specifically; the math
on switch counts/duration is unaffected). `v8/size/` is always
**derived** from `v8/latency/`'s own raw runs via
`campaign/scripts/compute_v8_size_report.py` — never collected
separately, never hand-edited (Decision 58). Pcaps are bundled per
scenario+window for the commit (`package_pcaps.sh`, Decision 57); image
delivery (`deliver_images.sh`, Decision 59) is written, not yet run.

**AWS Local Zones (Buenos Aires) — investigated, then abandoned.**
Buenos Aires, Santiago, and Lima all exist near São Paulo (Rio de Janeiro
doesn't exist as a Local Zone); Buenos Aires was opted into
(2026-10-12) and its instance catalog confirmed
(`DECISIONS.md`, Decision 25) — but **none of it is free-tier-eligible
on this account**, confirmed by an actual failed launch attempt, and this
account is currently on the free "6 meses" plan. That's a hard blocker,
not a Terraform bug (`DECISIONS.md`, Decision 29) — resolving it would
need an account upgrade, which wasn't pursued since 14.7ms/33.2ms already
cover the same gap. **The measurement was abandoned** (Decision 31); the
opt-in stays in effect (not self-service to reverse — AWS's own API docs
say reversing it requires an AWS Support ticket, not a CLI call; see
[AWS docs](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_ModifyAvailabilityZoneGroup.html)),
but the zone holds zero resources, verified directly, no ongoing cost.

Instance type for Phase 4: candidates from real peak-load measurement
(`DECISIONS.md`, Decision 21) were `m6i.large` (server) / `c6i.xlarge`
(clients) — **neither is free-tier-eligible**, and this account's free
plan was confirmed (Decision 29) to reject non-free-tier launches, so
whether these actually work on this account is **still an open
question**, not yet tested with a real launch. `m7i-flex.large` and
`c7i-flex.large` are free-tier-eligible alternatives confirmed available
in all 7 campaign regions (Decision 32) — both offer 40% baseline CPU
per vCPU with the ability to burst to full performance "the majority of
the time" ([AWS docs](https://aws.amazon.com/ec2/instance-types/m7i/)),
which real measurement (Decisions 18, 21) suggests should comfortably
cover this workload. Not decided which family Phase 4 actually uses.

## Resuming

If you're picking this back up: the topology is final (8 scenarios, 3
server installations each with their own `L0`, Decisions 30/53), all
RTT discovery is done and nothing is currently running on AWS (every
discovery run tears itself down and gets verified clean, including the
sa-east-1 AZ-to-AZ test). `thesis/results/v8/campaign/` has the full
12-instance Terraform (`terraform plan`-clean, 45 resources) and all 4
orchestration scripts (`campaign_up.sh`/`campaign_run.py`/
`campaign_pull.sh`/`campaign_down.sh`) — **none applied yet**.
`REMOTE_GATEWAY_HOST` is implemented in `opin_flow.py`/`tls_kem_proxy`
(diff ready, regression-tested across all 3 profiles, **not yet
committed** — pending the author's review).

**Sequence to the first real execution** (Decision 55's full version,
with the author's dependencies marked):
1. Flex launch test (Decision 43) — **author present**.
2. 12-instance Terraform apply (Decision 54) — **author present**,
   budget/credit confirmation (Decision 52).
3. Build `deliver_images.sh` (Decision 50) — not yet built.
4. Author reviews/approves the `REMOTE_GATEWAY_HOST` diff — then commit.
5. Pilot (Decision 46) — **author present** — validates `L0`'s
   public-IP RTT, the ClientHello size/SNI acceptance criterion, tcpdump
   overhead, written tc/netem confirmation.
6. ~~Implement `run_one_execution()`/`run_warmup()` for real.~~ Done —
   both executors implement the full per-block sequence (profile
   switch, 5 settling runs, correlated negotiated-group check,
   per-scenario warmup, round-robin, periodic CPU/mem sampling,
   auto-detected network interface) for real: `LocalExecutor` against
   the real local stack (Decisions 60-67), `SSHExecutor` with real
   SSH/SCP transport (Decision 68), run end to end against a
   3-container `sshd` rehearsal (`campaign/scripts/tests/rehearsal_*`)
   covering the full folder tree, the hash manifest, resume after a
   real kill mid-run, the instance lock, and a loud abort on a wrong
   curve or a missing capture tool — all 3 crypto profiles. Still
   untested: real AWS conditions (IAM/security groups, instance boot,
   real inter-region latency/packet loss) and genuine per-scenario
   client machine isolation — both only testable once real instances
   exist (Decision 68's own "after-pilot" list).
7. First real campaign execution (window 1).

See `campaign/scripts/tests/` for the automated tests backing step 6
(window-overwrite at two levels, block-order, negotiated-group
correlation, the rehearsal and its real-mode extension, and a
regression guard against new local-lab assumptions creeping into
`thesis/scripts/*.py`) — none require AWS.

## Teardown / cost safety

- `scripts/destroy_all.sh [var-file]` tears down both `latency-discovery/terraform`
  and `terraform/main` (once it exists) and verifies no tagged instance,
  security group, or key pair (`Project=mockopin-pqc-aws` /
  `mockopin-pqc-discovery`) is left in any of the 10 regions — exits
  non-zero if anything remains.
- The AWS Budget alert (`mockopin-pqc-experiment`, $20/month, configured in
  Phase 0) emails on threshold regardless of what Terraform state thinks
  happened — check the Billing Dashboard after any run as a second check.
