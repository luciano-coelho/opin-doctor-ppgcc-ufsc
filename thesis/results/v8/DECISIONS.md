# Decisions — v8 (real AWS cross-region latency)

## 1. Scope: replace simulated latency with real inter-region network latency, additive to v7, not a replacement

v1-v7 measured the cost of the PQC migration with **simulated** network
latency, injected via `tc`/`netem` at the gateway (6 fixed scenarios:
0/14/30/140/225/320ms, chosen to approximate real AWS inter-region RTTs
reported by Schardong et al. 2022, the paper this thesis extends). v7
remains the thesis's official source of truth for those simulated-latency
results.

v8 closes that loop: the same experiment (Classic / PQC / Hybrid, same
`opin_flow.py` client, same metrics), but run across **real** AWS regions,
with real network latency instead of injected delay. This is additive —
it validates whether the simulated numbers track real-world behavior, it
does not supersede v7.

**Decision.** Keep v1-v7's `tc`/`netem` apparatus completely untouched.
Build v8 as a parallel, self-contained experiment under
`thesis/results/v8/`, reusing `opin_flow.py`'s existing metrics collection
unchanged, with only a minimal, additive code path for pointing the client
at a remote (non-localhost) gateway.

## 2. Topology isolates the "real network" variable at the same point tc/netem did

**Context.** `tc`/`netem` injected delay on exactly one hop: client <->
gateway. Everything downstream of the gateway (mock_mtls, mock_as,
mockapi) ran colocated via `docker-compose`, untouched by the injected
delay.

**Decision.** v8 mirrors this exactly: one "server" EC2 instance runs the
full `docker-compose` stack unmodified (identical to a local run), and one
"client" EC2 instance runs only `opin_flow.py` + `tls_kem_proxy`, same as
local. Real AWS inter-region network now sits exactly where `tc`/`netem`
used to inject delay. Risk is minimized: nothing already validated on the
server side changes at all.

## 3. Region selection is empirical, not assumed

**Context.** The original delay values (14/30/140/225/320ms) were meant to
approximate Schardong et al.'s measured AWS region-pairs, but that paper is
paywalled and its exact region pairs could not be confirmed.

**Decision.** Don't assume which AWS region-pairs reproduce those RTTs.
Measure real RTT from `sa-east-1` (the server region, chosen for thematic
alignment with OPIN / Brazilian regulation) against 9 geographically
spread candidate regions, using short-lived `t4g.micro` discovery
instances (Phase 2), then pick the 5 candidates whose measured RTT is
closest to each of the 5 non-zero targets. The resulting region-to-target
mapping is documented transparently in README.md once measured — not
assumed from the literature.

Candidate regions tested: `us-east-1`, `us-east-2`, `us-west-2`,
`ca-central-1`, `eu-west-1`, `eu-central-1`, `ap-northeast-1`,
`ap-southeast-1`, `ap-southeast-2`.

## 4. Minimal IAM scope: EC2/VPC only, region-restricted, no console access

**Decision.** The dedicated IAM user (`mockopin-pqc-experiment`) has a
single custom policy: `ec2:*` (which covers VPC, since VPC resources are
part of the EC2 API namespace) restricted by `aws:RequestedRegion` to the
10 regions this experiment can touch, plus `sts:GetCallerIdentity` (needed
by the Terraform AWS provider to validate credentials). No IAM, no
Organizations, no console password — access-key-only, CLI/Terraform-driven.
Verified directly: `ec2:DescribeInstances` in an out-of-scope region
(`us-west-1`) and `iam:ListUsers` both return `AccessDenied`/
`UnauthorizedOperation` as expected.

A monthly AWS Budget of $20 with email alerts was configured before any
`terraform apply`, per the thesis's standing policy of guarding real-money
experiments with a spend ceiling before execution.

## 5. Discovery instances use each region's default VPC, not a dedicated one

**Decision.** Every AWS account has a default VPC (with an internet
gateway and public-IP-on-launch already wired up) in every region unless
explicitly deleted. Since this is a brand-new account, Phase 2's discovery
Terraform uses `data "aws_vpc" "default"` / `data "aws_subnets" "default"`
instead of provisioning a dedicated VPC per region — these instances live
for minutes and get destroyed immediately after the RTT sweep, so the
extra isolation of a custom VPC isn't worth the added Terraform surface.
The Phase 4 main experiment (server + client, longer-lived) will revisit
this if network isolation becomes a concern.

## 6. AMI resolution via `ec2:DescribeImages`, not SSM Parameter Store

**Context.** The common Terraform pattern for "latest Amazon Linux AMI" is
`data "aws_ssm_parameter"` against the public
`/aws/service/ami-amazon-linux-latest/...` parameter. That requires
`ssm:GetParameter`, which is outside this project's deliberately
EC2-only IAM policy (Decision 4).

**Decision.** Use `data "aws_ami"` (owner `amazon`, name filter
`al2023-ami-*-kernel-*-arm64`, `most_recent = true`) instead --
`ec2:DescribeImages` is already covered by the existing `ec2:*` grant, so
no policy widening was needed just to find an AMI.

## 7. SSH access to discovery instances: sa-east-1 prober only, scoped to the operator's IP

**Decision.** Only the `sa-east-1` discovery instance is SSH-reachable
(port 22, from the operator's `/32` public IP only) -- it's the one
instance the RTT-measuring script logs into, matching the real
client-to-server network path. The 9 candidate instances accept **ICMP
only**, and only from the `sa-east-1` prober's public IP (not
`0.0.0.0/0`), despite being short-lived -- least-privilege by default even
for disposable infrastructure. A throwaway ed25519 keypair is generated
per run and never stored inside the repo (not even gitignored-in; see
README.md) -- its public half is passed to Terraform via an untracked
`*.auto.tfvars.json` file outside the repo tree.

## 8. OPIN's Brazil-data-residency restriction does not apply to this experiment

**Context.** The real OPIN ecosystem (Open Insurance Brasil) restricts
where participant data may be processed, as a regulatory requirement.
Since v8 relocates the "client" side of the experiment across 9 AWS
regions outside Brazil, it's worth stating explicitly why that restriction
isn't a constraint here.

**Decision.** It isn't, because **MockOPIN uses only synthetic data** --
there is no real participant, consumer, or account data anywhere in this
codebase or in any instance this experiment provisions -- and because the
experiment's entire purpose is to measure **network latency's effect on
the PQC handshake**, not to evaluate OPIN's behavior, compliance, or
viability in any jurisdiction. Running the mock client in Tokyo or Dublin
says nothing about whether real OPIN data could lawfully be processed
there; this thesis makes **no claim, and should be read as suggesting
none**, about the legal or regulatory viability of operating OPIN (real or
mock) outside Brazil. Given that, every region in the candidate list
(Decision 3) remains eligible for all 5 non-zero latency scenarios
(14/30/140/225/320ms) -- region choice is driven purely by which measured
RTT is closest to each target.

## 9. Discovery sweep results (2026-10-08) and region selection

**Context.** Phase 2 (Decision 3) was executed 2026-10-08: 10 `t4g.micro`
instances (prober in `sa-east-1` + 9 candidates), 3 ping rounds of 20
packets/region spread across real ~1h gaps (03:00-05:10 UTC), 60 samples
per region pooled for median/min/max. Full raw samples:
`latency-discovery/aws-region-discovery-raw/latency_samples.json`. All 10 instances, their
security groups, and the discovery key pair were destroyed immediately
after, verified clean per-region via `destroy_all.sh`'s own `aws ec2
describe-instances`/`describe-security-groups`/`describe-key-pairs` checks
(all nine candidates plus `sa-east-1` reported "clean").

**All regions measured** (sa-east-1 origin, pooled across all 3 rounds):

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

All 9 candidates responded in every round -- no missing data, no region
excluded.

**Selection** (closest median RTT to each target, each region used once,
ascending target order -- see Decision 3 and `select_regions.py`):

| Target (ms) | Selected region | Median RTT (ms) | Delta | Why |
|---|---|---|---|---|
| 14 | `us-east-1` | 112.00 | +98.00 | Closest available -- see caveat below |
| 30 | `us-east-2` | 120.00 | +90.00 | Closest available -- see caveat below |
| 140 | `ca-central-1` | 123.00 | -17.00 | Closest median to 140ms among remaining candidates |
| 225 | `eu-central-1` | 201.00 | -24.00 | Closest median to 225ms among remaining candidates |
| 320 | `ap-southeast-1` | 326.00 | +6.00 | Closest median to 320ms; also the highest-RTT candidate measured |

All 5 scenarios are reachable with the current 9-candidate list -- no
target came back `NOT REACHABLE`, so the IAM policy's region list
(Decision 4) did not need widening.

**Caveat -- 14ms and 30ms are not realistically reachable inter-region.**
Unlike 140/225/320ms (deltas under 25ms), the two lowest targets have
deltas of +90 to +98ms: no AWS region pair from `sa-east-1` gets anywhere
close, because ~110-120ms is close to the physical RTT floor between
continental regions (speed-of-light + routing overhead on submarine/
long-haul links). `select_regions.py` still assigns a "closest available"
region to them (`us-east-1`, `us-east-2`) because the script's job is to
report the best fit, not to judge fitness -- but a 90ms+ delta is not the
same kind of result as the other three scenarios, and should not be
presented as equivalent precision in the final report. This suggests the
original v1-v7 14ms/30ms scenarios may have approximated same-region or
LAN-scale latency rather than real inter-region AWS latency; worth
revisiting against Schardong et al.'s methodology before treating
`us-east-1`/`us-east-2` as like-for-like stand-ins for those two
scenarios. Decision deferred to the author before Phase 4 locks in these
two regions.

**Root cause, confirmed 2026-10-10.** The hypothesis above is correct, and
the actual origin of the 14ms/30ms targets is now known precisely: they
come from real measurements Frederico took from a single fixed point --
his own machine in Palhoça, SC -- to two nearby real-world destinations:
~14ms to Córrego Grande, Florianópolis (UFSC), and ~30ms to São Paulo.
Both are short, same-region/same-state or neighboring-state residential-ISP
hops over tens to a few hundred km -- not inter-datacenter links at all.
This is a different *kind* of network path than AWS inter-region
backbone links, which is why no AWS region pair anchored at `sa-east-1`
(or, as Decision 10 will show, anchored at any single region) can be
expected to reproduce them with the same fidelity as 140/225/320ms, whose
originals likely *were* AWS-region-scale distances to begin with. This
closes the open question from Decision 9 -- it is not a measurement gap in
this thesis's discovery process, it is a real category difference in the
original source data.

## 10. Mesh discovery: full 10x10 RTT, not single-origin

**Correcting the timeline.** Decision 9's measurement origin was already
`sa-east-1` **as an AWS EC2 instance** -- `discover_latency.py` uses SSH
only to trigger the `ping` command, which runs on the `sa-east-1`
instance itself, not on the operator's local machine. The result was
already AWS-to-AWS and reproducible by a third party running the same
script. The actual limitation was narrower: **only one origin was
measured** (`sa-east-1` against the other 9), so the 14ms/30ms gap
observed in Decision 9 reflected that one region's neighborhood, not the
full 45-pair space between all 10 regions in the IAM policy. The "LAN-scale
scenario" hypothesis from Decision 9 was speculative, not confirmed --
this decision tests it properly by measuring every pair.

**Decision — full mesh.** All 10 regions (same list as Decision 3/4, still
fully inside the IAM policy -- no policy change needed) take turns as
origin, pinging the other 9, giving 90 directed measurements (45 unique
pairs x 2 directions) per round, same sampling as Decision 9 (3 rounds,
~1h apart, 20 pings/pair/round, median/min/max from pooled samples). The
two directions of each pair also serve as a free symmetry check.

**Decision — SSH stays single-entry, ICMP opens.** The operator's IP can
only reach `sa-east-1` (unchanged from Decision 7); the other 9 accept SSH
only from `sa-east-1`'s IP, reached via `ssh -J` (ProxyJump) -- the private
key is used client-side for both hops and never touches any EC2 instance's
disk. ICMP, however, is opened to `0.0.0.0/0` on all 10 instances (a
change from Decision 7's `/32`-scoped rule), because mesh pinging needs
every instance reachable by ICMP from every other, and pre-computing a
precise 9-entry CIDR allowlist per instance would need a two-phase
Terraform apply (security-group rules can't reference sibling modules'
post-creation IPs without a dependency cycle). Accepted because: the
instances are temporary (torn down within ~2h of creation), run no
service at all beyond `sshd` (bare Amazon Linux 2023, no user-data), and
ICMP echo carries no exploitable surface on a host with nothing listening
behind it -- unlike SSH, which stays strictly scoped. The two-phase
alternative (a precise mesh of `/32` rules via a post-apply script) would
have made the setup, and third-party reproduction of it, more fragile for
no real security gain here.

**Selection criterion, registered before measuring.** Tolerance band is
+-20% of each original v1-v7 target: 14ms -> 11-17, 30ms -> 24-36, 140ms ->
112-168, 225ms -> 180-270, 320ms -> 256-384. First choice: a single region
used as a fixed origin that covers all 5 targets within tolerance
(preserves Phase 4's existing fixed-server topology, Decision 2). If no
single origin qualifies, this is reported, not auto-resolved -- picking an
independent (client, server) pair per scenario changes Decision 2's
topology and needs the author's explicit sign-off before Phase 4 is built
around it. Every scenario is labeled by its measured RTT with the original
target in parentheses (e.g. "112ms (target 140ms)"), never silently
renamed to the nominal target.

**Measurement caveat for Phase 4.** This decision (and Decision 9) measure
ICMP RTT only. The actual experiment's bottleneck is the TLS handshake
over TCP, not ICMP -- Phase 4 will cross-check the effective network RTT
against the real experiment's own pcap capture, not assume ICMP and TCP
RTT are identical on the same path.

**Results, measured 2026-10-11 00:27-01:40 UTC** (3 rounds, ~1h apart, 20
pings/pair/round, 60 samples/pair pooled; 90/90 directed pairs responded in
every round -- no missing data). Symmetry check: median |A->B - B->A|
across all 45 pairs was 0.0ms, max 1.0ms -- the measurement is internally
consistent, direction doesn't matter.

10x10 median RTT matrix (ms):

| origin \ dest | ap-ne-1 | ap-se-1 | ap-se-2 | ca-c-1 | eu-c-1 | eu-w-1 | sa-e-1 | us-e-1 | us-e-2 | us-w-2 |
|---|---|---|---|---|---|---|---|---|---|---|
| ap-northeast-1 | - | 69 | 102 | 141 | 226 | 203 | 255 | 147 | 133 | 99 |
| ap-southeast-1 | 69 | - | 165 | 205 | 160 | 167 | 325 | 220 | 216 | 172 |
| ap-southeast-2 | 102 | 165 | - | 195 | 285 | 253 | 308 | 213 | 188 | 140 |
| ca-central-1 | 141 | 205 | 195 | - | 90 | 68 | 123 | 15 | 18 | 65 |
| eu-central-1 | 226 | 160 | 285 | 90 | - | 20 | 200 | 91 | 95 | 142 |
| eu-west-1 | 203 | 167 | 253 | 68 | 20 | - | 176 | 68 | 77 | 125 |
| sa-east-1 | 256 | 325 | 308 | 123 | 200 | 176 | - | 111 | 120 | 180 |
| us-east-1 | 147 | 220 | 213 | 15 | 91 | 68 | 111 | - | 13 | 71 |
| us-east-2 | 133 | 216 | 188 | 18 | 95 | 77 | 120 | 13 | - | 60 |
| us-west-2 | 99 | 172 | 140 | 65 | 142 | 125 | 180 | 71 | 60 | - |

Selection, applying the criterion above exactly (greedy, every single
origin checked for all-5 coverage first):

| Target (nominal) | Best pair | Measured | Delta | In tolerance (±20%)? |
|---|---|---|---|---|
| 14ms | us-east-1->ca-central-1 | 15ms | +0.7 | yes (11-17) |
| 30ms | eu-west-1->eu-central-1 | 20ms | -10.4 | **no** (24-36) |
| 140ms | us-west-2->ap-southeast-2 | 140ms | +0.0 | yes (112-168) |
| 225ms | eu-central-1->ap-northeast-1 | 226ms | +1.0 | yes (180-270) |
| 320ms | sa-east-1->ap-southeast-1 | 325ms | +5.0 | yes (256-384) |

**No single origin covers all 5 targets within tolerance** -- confirmed
exhaustively (every one of the 10 regions checked as a candidate fixed
origin, not just `sa-east-1`). 4 of 5 targets land extremely close
(deltas of 0-5ms) from *some* origin, but the 4 "good" matches come from
**4 different origin regions, no two sharing one** (`us-east-1` for 14ms,
`us-west-2` for 140ms, `eu-central-1` for 225ms, `sa-east-1` for 320ms) --
not just a single-origin coverage gap, these are 4 genuinely independent
pairs. Only 30ms has no match anywhere in the mesh. The matrix shows a gap
**among these specific 10 regions** (not a claim about AWS's full region
footprint, which this mesh never tested) between short-hop neighbors
(~13-20ms: `us-east-1<->us-east-2`, `eu-central-1<->eu-west-1`,
`ca-central-1<->us-east-1/2`) and the next tier out (~60ms+:
`us-east-2<->us-west-2`, `ca-central-1<->us-west-2`) -- nothing lands in
the 24-36ms band anywhere in this 10-region set. Whether that band exists
between OTHER AWS region pairs outside this set is an open question this
mesh cannot answer -- see the candidate-region proposal below.

**Open decision for the author** (per the pre-registered criterion, not
resolved automatically): since no origin covers 30ms, Phase 4's topology
needs one of:
1. Keep a single fixed server region covering 14/140/225/320ms well, and
   accept a *different*, dedicated client/server pair just for the 30ms
   scenario (breaks Decision 2's "one fixed hop" assumption for exactly
   one of five scenarios).
2. Move to independent (client, server) pairs for all 5 scenarios (breaks
   Decision 2 fully, but keeps the topology uniform across scenarios).
3. Treat 30ms as unreachable with real AWS infrastructure at the measured
   precision, and report it as such rather than forcing a worse-fitting
   substitute (e.g. documenting the `eu-west-1->eu-central-1` 20ms result
   as the closest real value, with its -10.4ms/-35% deviation stated
   plainly rather than silently accepted).

Not decided here -- this blocks Phase 4's Terraform design until the
author picks one.

**Candidate regions that might bridge the 30ms gap (hypothesis, not
measured).** None of these have been tested -- they are proposed based on
known approximate geographic distance to regions already in our policy,
not on any live measurement. Confirming any of them requires the author
to approve a small policy widening first (see below); nothing here was
created or measured to produce this list.

| Candidate region | Pairs with (already in policy) | Why it's plausible | Confidence |
|---|---|---|---|
| `ap-northeast-2` (Seoul) | `ap-northeast-1` (Tokyo) | Seoul-Tokyo is a commonly cited ~30-35ms submarine-cable RTT in cloud networking benchmarks -- directly in our 24-36ms tolerance band | High |
| `eu-north-1` (Stockholm) | `eu-west-1` (Ireland) and/or `eu-central-1` (Frankfurt) | ~1500-1800km to either; Northern-to-Central/Western Europe fiber paths commonly land in the 25-35ms range, above the tight ~13-20ms cluster our existing Western/Central European regions already show | Medium-high |
| `ap-east-1` (Hong Kong) -- optional 3rd | `ap-southeast-1` (Singapore) | HK-Singapore commonly cited ~35-40ms -- slightly above the tolerance band's upper edge, so lower confidence than the other two. **Caveat:** this is an AWS "opt-in" region (launched after March 2019) -- it must be explicitly enabled in Account Settings before any API call against it works at all, a one-time step separate from the IAM policy change, free but an extra piece of friction. Proposed only if the first two don't pan out. |

Both `ap-northeast-2` and `eu-north-1` are standard (non-opt-in) regions,
already enabled by default on this account -- no extra account-level step
needed for those two, only the IAM policy change below.

**Exact IAM policy change needed** (in
`mockopin-pqc-experiment-policy`'s `Condition.StringEquals.aws:RequestedRegion`
list, Decision 4): add `"ap-northeast-2"` and `"eu-north-1"` (plus
`"ap-east-1"` only if the 3rd candidate is wanted). No other policy change
-- same `ec2:*` + `sts:GetCallerIdentity` actions, same structure.

**Estimated cost and duration.** A dedicated sub-check (not a full
10-region mesh): the 2-3 new candidates plus their 1-2 existing partner
regions each (`ap-northeast-1`, `eu-west-1`, `eu-central-1`,
`ap-southeast-1` if Hong Kong is included) -- at most 7 instances, fewer
than the 10 used in both discovery runs so far. Same `t4g.micro`
instance type, same 3-round/~1h-gap sampling pattern if full rigor is
wanted (~2h10min, matching both prior runs) or a faster single-round
pass (~5-10 minutes) if a quick first look is preferred before committing
to the full validated run. Cost: same order of magnitude as the prior two
discovery runs -- well under $1.

**Instance type (`t4g.micro`) availability.** Confirmed empirically,
not assumed, for every region in the 4 selected pairs (`us-east-1`,
`ca-central-1`, `us-west-2`, `ap-southeast-2`, `eu-central-1`,
`ap-northeast-1`, `sa-east-1`, `ap-southeast-1`) -- we successfully
launched `t4g.micro` instances in all of them, multiple times, across
both the single-origin and mesh discovery runs. For the 2-3 new
candidates, availability is **not yet confirmed** -- our current IAM
policy doesn't permit any API call (including read-only
`describe-instance-type-offerings`) outside the existing 10-region list,
by design (Decision 4), so this can't be checked without the policy
change above happening first. Expectation, not fact: `t4g` (Graviton2) has
had broad rollout across standard AWS regions since ~2020, so
`ap-northeast-2` and `eu-north-1` (both long-established, non-opt-in
regions) are likely to support it -- but "likely" is exactly what the
discovery run above would confirm or refute. `ap-east-1` (Hong Kong),
being newer and smaller, is the least certain of the three and would need
explicit verification regardless.

## 11. IAM policy widened to add ap-northeast-2 and eu-north-1 (2026-10-11)

**Context.** Decision 10's candidate-region proposal needed the IAM
policy's region allowlist widened to test `ap-northeast-2` (Seoul) and
`eu-north-1` (Stockholm) as possible bridges for the 30ms gap. Widening
the policy is explicitly the author's call (Decision 4), never automatic.

**Decision.** The author approved adding exactly these two regions --
`ap-east-1` (Hong Kong) was explicitly excluded, per the author's
instruction, since it's an opt-in region with lower confidence and was
proposed only as an optional third fallback. Applied by the author
directly in the AWS Console (IAM -> Policies ->
`mockopin-pqc-experiment-policy` -> Edit -> JSON), using their own
administrator credentials -- Claude never had, requested, stored, or saw
any administrator access key or secret for this step; the change was
guided verbally (exact before/after JSON diff) and applied by the author
themselves, consistent with this project's "ampliar a policy e decisao do
Luciano" rule. The edit created a new policy version via the IAM console's
normal "Edit policy" flow (up to 5 versions retained, old version not
deleted), touching only the `aws:RequestedRegion` list -- no change to
`Action`, `Effect`, `Resource`, or the `STSCallerIdentity` statement.

Diff (only change made):
```diff
             "ap-southeast-2",
+            "ap-northeast-2",
+            "eu-north-1"
```

**Verified immediately after, from the restricted `mockopin-pqc` profile**
(the one this project's scripts actually use -- never the admin
credentials used to make the change):
- `ec2:DescribeRegions` in `ap-northeast-2` -- succeeds, confirms
  `OptInStatus: opt-in-not-required` (matches Decision 10's expectation).
- `ec2:DescribeRegions` in `eu-north-1` -- succeeds, same confirmation.
- `ec2:DescribeInstances` in `us-west-1` (a region outside even the new,
  widened list) -- still `UnauthorizedOperation`, confirming the
  restriction still works for everything not explicitly allowed.
- `iam:ListUsers` -- still `AccessDenied`, confirming the policy still
  grants nothing beyond `ec2:*` + `sts:GetCallerIdentity`; IAM actions
  remain completely out of this profile's reach.

**No administrator credential was ever stored anywhere in this project.**
Confirmed: no key or secret appears in any file under `thesis/results/v8/`
(the author typed it directly into `aws configure`/the AWS Console
locally, never pasted into this conversation or into a file Claude
wrote), no reference to an admin profile name or credential in this
repository's git history (nothing in `v8/` has ever been committed,
per the project's standing "don't commit v8" working practice until the
author says otherwise), and Terraform's local state (`.tfstate`, itself
gitignored) only ever contains resource attributes from the restricted
`mockopin-pqc` profile's own `t4g.micro`/security-group/key-pair
resources -- never any IAM entity or credential material, since this
project's Terraform has never managed IAM resources at all.

## 12. 30ms gap closed: ap-northeast-2 and eu-north-1 both land in tolerance

**Context.** Immediately after Decision 11's policy widening, a quick
single-round check (not the full 3-round rigor -- see caveat below)
measured the two candidates against their proposed partners from Decision
10, using a small dedicated Terraform root
(`latency-discovery/terraform-candidates/`, 6 regions: `sa-east-1` as
jump host + the 5 regions actually being tested) rather than the full
10-region mesh. Full data and reproduction steps:
`latency-discovery/aws-region-discovery-candidates-raw/`.

**Results** (single round, 20 pings/pair):

| Pair | Median RTT | In 30ms tolerance (24-36ms)? |
|---|---|---|
| `ap-northeast-2` <-> `ap-northeast-1` (Seoul <-> Tokyo) | 33.2ms | **yes** |
| `eu-north-1` <-> `eu-west-1` (Stockholm <-> Ireland) | 34.5ms | **yes** |
| `eu-north-1` <-> `eu-central-1` (Stockholm <-> Frankfurt) | 23.7ms | no (0.3-0.4ms below the lower bound) |

**This resolves Decision 10's open question in the author's favor:** 30ms
*is* reachable with real AWS infrastructure -- just not within the
original 10-region set tested in Decisions 9/10. Both `t4g.micro`
availability (Decision 10's other open item) and the RTT target are now
confirmed for `ap-northeast-2` and `eu-north-1` -- the instances launched
and measured successfully in this run.

**This also confirms Decision 10's correction stands**: the gap was
specific to the original 10 regions, not a property of AWS as a whole --
exactly as the author pointed out. Widening the search by 2 regions found
not one but two matches.

**Caveat -- not yet the full standard.** This was deliberately a fast,
single-round look (no 1h-spaced repeat rounds), unlike every other
measurement in this project (Decisions 9 and 10 both used 3 rounds across
~2h to guard against a single-snapshot artifact). Before either pair is
locked in for Phase 4, a full 3-round confirmation run is recommended,
consistent with this project's own sampling standard -- cheap to do
(same small 6-region Terraform root, ~2h10min, well under $1).

**Still open:** which of the two (Seoul<->Tokyo or Stockholm<->Ireland) to
actually use for Phase 4 -- and, per Decision 10's original framing, this
still doesn't resolve by itself whether Phase 4 uses one fixed server
region (now potentially covering all 5 targets if `ap-northeast-1` or
`eu-west-1` turns out to also work as origin for the other 4 -- not yet
checked) or independent pairs per scenario. Both remain the author's
decision.

## 13. Single-origin check (now including the 2 new regions) and 30ms confirmation -- Phase 4 uses independent pairs

**SUPERSEDED 2026-10-11 (Decision 15) for Part C's topology conclusion
only.** Parts A and B below (the single-origin coverage table and the
30ms confirmation matrix) remain valid, accurate, measured data -- nothing
about them is wrong or retracted. What changed is the *design response* to
Part A's finding: Part C concluded Phase 4 should use one independent
(client, server) pair per scenario, since no region covers all 5 targets.
Decision 15 replaces that conclusion with a deliberate design choice
instead: **one fixed MockOPIN installation in `sa-east-1`, only the client
relocates** -- not because some origin turned out to cover all 5 after
all (none does; Part A's finding still stands), but because a single
installation is simpler to operate, reproduce, and reason about than five
independent server deployments, and `sa-east-1` was already the thesis's
server region by Decision 1. See Decision 15 for the full reasoning. The
region-pair data below is kept as-is for the record (and parts of it feed
directly into Decision 16's `sa-east-1`-anchored scenario table).

**Part A -- single-origin coverage, combining all data to date.** Pooled
the original 10-region mesh (Decision 10) with the candidate-pair data
(Decision 12) -- 12 regions total with at least some pairwise data -- and
re-ran the exact same greedy single-origin-covers-all-5 check from
Decision 10/12, now including `ap-northeast-2` and `eu-north-1` as
possible origins too. No AWS calls were made for this part -- pure
analysis of already-collected data.

| Origin | 14ms | 30ms | 140ms | 225ms | 320ms | Covers all 5? |
|---|---|---|---|---|---|---|
| `us-east-1` | `ca-central-1`=14.7 | - | `ap-northeast-1`=147 | `ap-southeast-1`=220 | - | No |
| `ca-central-1` | `us-east-1`=14.7 | - | `ap-northeast-1`=141 | `ap-southeast-1`=205 | - | No |
| `ap-northeast-1` | - | `ap-northeast-2`=33.3 | `ca-central-1`=141 | `eu-central-1`=226.5 | - | No |
| `ap-northeast-2` | - | `ap-northeast-1`=33.2 | - | `eu-central-1`=226 | `sa-east-1`=294 | No |
| `eu-west-1` | - | `eu-north-1`=34.5 | `us-west-2`=125 | `ap-northeast-2`=227 | - | No |
| `eu-north-1` | - | `eu-west-1`=34.5 | - | `sa-east-1`=219 | - | No |
| `eu-central-1` | - | - | `us-west-2`=142 | `ap-northeast-2`=226 | `ap-southeast-2`=285 | No |
| `sa-east-1` | - | - | `ca-central-1`=123 | `eu-north-1`=219 | `ap-southeast-1`=325 | No |
| `us-east-2` | `us-east-1`=13.1 | - | `ap-northeast-1`=133 | `ap-southeast-1`=216 | - | No |
| `us-west-2` | - | - | `ap-southeast-2`=140 | `sa-east-1`=180 | - | No |
| `ap-southeast-1` | - | - | `eu-central-1`=160 | `us-east-1`=220 | `sa-east-1`=325 | No |
| `ap-southeast-2` | - | - | `us-west-2`=140 | `us-east-1`=213 | `sa-east-1`=308 | No |

**No origin covers all 5, even with the 2 new regions included.** The
pattern holds for a structural reason, not a data gap: 14ms needs a very
close neighbor (same small cluster: `us-east-1`/`us-east-2`/
`ca-central-1`), 320ms needs a very distant one (`sa-east-1`/
`ap-southeast-1`-scale separation) -- no region in this 12-region set is
simultaneously that close to something and that far from something else
while also hitting 30/140/225 in between.

**Part B -- full 3-round confirmation of the two 30ms candidates.**
Measured 2026-10-11, 02:42-04:48 UTC, same sampling standard as Decisions
9 and 10 (3 rounds, ~1h apart, 20 pings/pair/round, both directions).
Infrastructure (18 resources, 6 regions) destroyed and verified clean
immediately after. Full data:
`latency-discovery/aws-region-discovery-candidates-confirm-raw/`.

| Pair | Round 1 | Round 2 | Round 3 | Pooled median | Round-to-round variation |
|---|---|---|---|---|---|
| `ap-northeast-2`<->`ap-northeast-1` (Seoul<->Tokyo) | 33.20 | 33.20 | 33.90 | 33.2-33.3ms | ~0.7ms |
| `eu-north-1`<->`eu-west-1` (Stockholm<->Ireland) | 34.40 | 35.70 | 35.60 | 35.6ms | ~1.3ms |

**Selection: `ap-northeast-2` <-> `ap-northeast-1` (Seoul <-> Tokyo),
labeled 33.2ms (target 30ms).** Wins on both criteria agreed in advance:
closer to target (+3.2ms vs. +5.6ms) and lower round-to-round variation
(~0.7ms vs. ~1.3ms, i.e. roughly half).

**Part C -- Decision 2 revision, confirmed by the author (SUPERSEDED, see
note above Part A).** Since no single origin covers all 5 targets (Part A,
exhaustive across 12 regions), **Phase 4 uses one independent (client,
server) pair per scenario**, not a single fixed server region -- this was
the conclusion at the time. Decision 15 (2026-10-11) replaced it with a
fixed single installation in `sa-east-1` instead, by deliberate design
choice, not because this finding was wrong. Final 5 scenario pairs as
originally proposed here (same `instance_type` across all -- see Decision
14 for which) -- kept for the record, not the design Phase 4 now follows:

| Scenario (nominal) | Label (measured) | Region pair |
|---|---|---|
| 14ms | 14.7ms (target 14ms) | `us-east-1` <-> `ca-central-1` |
| 30ms | 33.2ms (target 30ms) | `ap-northeast-2` <-> `ap-northeast-1` |
| 140ms | 140.0ms (target 140ms) | `us-west-2` <-> `ap-southeast-2` |
| 225ms | 226ms (target 225ms) | `eu-central-1` <-> `ap-northeast-1` |
| 320ms | 325ms (target 320ms) | `sa-east-1` <-> `ap-southeast-1` |

Note `ap-northeast-1` appears in both the 30ms and 225ms pairs (as a
different partner each time) -- not a conflict, Phase 4 stands up a
separate client+server instance pair per scenario, so the same region can
host different roles in different scenarios without interference. Which
region in each pair is "client" vs. "server" is not fixed by the RTT
data (symmetric either way) -- `sa-east-1` is proposed as server for the
320ms pair for consistency with Decision 1's thematic rationale (OPIN /
Brazilian regulation); the other 4 pairs' client/server assignment is
still open, to be settled when Phase 4's Terraform is actually designed.

## 14. Dedicated (non-burstable) instance type candidates for Phase 4

**Partially superseded 2026-10-11 by Decision 18.** The candidates and
region-availability check below remain accurate and useful background,
but they were sized for the "server in every scenario region" topology
Decision 13 Part C proposed. Decision 15 fixes the server to `sa-east-1`
only; Decision 18 does the real instance-type sizing (from measured idle
memory footprint of the actual stack) for that narrower topology --
consult Decision 18 for the current recommendation, not this one.

**Context.** `t4g.micro` (burstable, ARM/Graviton) was deliberately chosen
for all discovery work -- cheap, fast to launch, fine for a ping sweep
with nothing else running. It's the wrong choice for Phase 4's actual
experiment: a burstable instance throttles under sustained load, and the
real experiment runs the full `docker-compose` stack (`mock_mtls`,
`mock_as`, `mockapi`, TLS handshakes with ML-KEM) under repeated load --
exactly the sustained-CPU workload `t4g` is unsuited for.

**Two x86, non-burstable candidates proposed:**
- **`m6i.large`** (general purpose, 2 vCPU / 8GiB RAM) -- balances CPU and
  memory, comfortable headroom for running several containers
  simultaneously (the full `docker-compose` stack, not just one service).
- **`c6i.large`** (compute-optimized, 2 vCPU / 4GiB RAM) -- less memory
  headroom, but if the PQC handshake's CPU cost (ML-KEM key generation/
  encapsulation) turns out to dominate over memory pressure, this gets
  more CPU per dollar.

**Availability confirmed, read-only, no infrastructure created** (the
widened policy from Decision 11 already permits this -- all 10 regions
below were already in-policy):

| Region | `m6i.large` | `c6i.large` |
|---|---|---|
| `us-east-1` | yes | yes |
| `ca-central-1` | yes | yes |
| `us-west-2` | yes | yes |
| `ap-southeast-2` | yes | yes |
| `eu-central-1` | yes | yes |
| `ap-northeast-1` | yes | yes |
| `sa-east-1` | yes | yes |
| `ap-southeast-1` | yes | yes |
| `ap-northeast-2` | yes | yes |
| `eu-north-1` | yes | yes |

Both instance types are available in every region used by all 5 Decision
13 scenario pairs. Choosing between `m6i.large` and `c6i.large` (and
confirming it performs acceptably under the real workload) is left for
when Phase 4's Terraform is actually built -- not decided here.

## 15. Single fixed MockOPIN installation in sa-east-1 -- design choice, not legal restriction

**SUPERSEDED 2026-10-12 (Decision 30) -- partially.** A single installation
is no longer true for all 6 scenarios: Decision 30 introduces 2 more
MockOPIN installations (`us-east-1`, `ap-northeast-1`) for the 14.7ms and
33.2ms scenarios specifically, which this decision's original reasoning
didn't anticipate (it assumed, incorrectly as it turned out, that a single
installation could cover every reachable scenario). The reasoning here
(operational simplicity, `sa-east-1`'s thematic role) still holds for the
4 scenarios it still covers (0/123/219/325ms) -- see Decision 30 for the
full picture.

**Context.** Decision 13 Part C concluded Phase 4 should use one
independent (client, server) region pair per scenario, since no single
region covers all 5 RTT targets. That conclusion is still factually
correct -- no region does. What changes here is the response to it.

**Decision.** Phase 4 runs **one single MockOPIN installation, always in
`sa-east-1`** (the full `docker-compose` stack, unmodified). Only the
*client* (`opin_flow.py` + `tls_kem_proxy`) relocates per scenario. This
replaces Decision 13 Part C's "independent pair per scenario" topology and
Decision 14's "server sizing per scenario region" framing (both marked
superseded above, not deleted).

**Why.** Operational simplicity and reproducibility: one installation to
deploy, monitor, and tear down is simpler to operate and simpler for a
third party to reproduce than five independent server deployments, each
potentially needing its own troubleshooting. `sa-east-1` was already this
thesis's server region since Decision 1 (thematic alignment with OPIN /
Brazilian regulation) -- this just extends that choice to the real-AWS
phase instead of introducing a different server per scenario.

**This is explicitly not a legal or regulatory constraint.** Decision 8
already established that MockOPIN's Brazil-data-residency question doesn't
apply to this experiment (synthetic data only, no conclusion drawn about
real OPIN's legal viability outside Brazil) -- that finding is unaffected
and still means a client (or, hypothetically, a server) could legally run
anywhere from this project's standpoint. Decision 15 doesn't reopen that
question; it's a separate, voluntary engineering choice about how many
server installations to operate, made independently of Decision 8's legal
analysis. Fixing the server to `sa-east-1` is simply the simpler design,
not a requirement.

**Consequence.** The region-pair proposals in Decisions 13/14 (us-east-1,
us-west-2, eu-central-1, ap-southeast-2, ap-northeast-1, etc. each hosting
a dedicated server) no longer apply as written. Decision 16 re-derives
each scenario's client region from `sa-east-1`'s own already-measured
pairs.

## 16. Scenario clients, all measured from sa-east-1

**No AWS calls made for this decision** -- pure analysis of data already
collected in Decisions 9/10/12/13.

For each scenario (except 0ms, see below), the table shows: the proposed
client region, its measured RTT from `sa-east-1`, how many sampling
rounds exist and from which prior run, sample count in both directions,
and the two next-closest alternatives also measured from `sa-east-1`.

| Scenario | Proposed client | RTT | Rounds (source) | Samples (both directions) | Next 2 closest alternatives |
|---|---|---|---|---|---|
| 0ms | `sa-east-1` itself | n/a | none -- never measured (self-pairs are excluded by design from every mesh run) | 0 | n/a |
| 140ms | `ca-central-1` | 123ms | 3 (Decision 9/10 main mesh) | 60 fwd + 60 bwd | `us-east-2` (120ms, 3 rounds), `us-east-1` (111ms, 3 rounds) |
| 225ms | `eu-north-1` | 219ms | 4 total: 1 (Decision 12 quick pass) + 3 (Decision 13 confirmation) | 80 fwd + 80 bwd | `eu-central-1` (200ms, 3 rounds, Decision 9/10), `ap-northeast-1` (255ms, 7 rounds across 3 runs) |
| 320ms | `ap-southeast-1` | 325ms | 3 (Decision 9/10 main mesh) | 60 fwd + 60 bwd | `ap-southeast-2` (308ms, 3 rounds), `ap-northeast-2` (283.5ms, 4 rounds: 1+3) |

**0ms has no measurement and needs none.** Every discovery run in this
project explicitly skips self-pairs (`if dest_region == origin_region:
continue` in `discover_latency_mesh.py`) -- a region was never pinged
against itself. This is fine: 0ms represents "no real inter-region network
hop," which is exactly what "client co-located with the server" already
is by construction, matching v1-v7's 0ms baseline (no injected delay)
conceptually. No infrastructure or confirmation run is needed for this
scenario.

**140ms and 320ms already meet the project's 3-round standard** -- both
come straight from the original 10-region mesh (Decisions 9/10), already
sampled 3 rounds, ~1h apart, 20 pings/pair/round. **225ms already exceeds
it**: `eu-north-1`'s pairing with `sa-east-1` was measured once in the
quick candidate pass (Decision 12) and then again as bonus data across all
3 rounds of the dedicated 30ms confirmation run (Decision 13 Part B),
since that run's 6-region mesh happened to include both `sa-east-1` and
`eu-north-1`. **No new infrastructure or confirmation run is needed for
140ms, 225ms, or 320ms** -- all three already have real, properly-spaced,
multi-round data.

14ms and 30ms are not in this table -- `sa-east-1` has no neighbor close
to either (closest is `us-east-1` at 111ms); see Decision 17.

## 17. 14ms/30ms from sa-east-1: AWS Local Zones investigated

**Context.** Under Decision 15's fixed-server topology, 14ms and 30ms need
a client close enough to `sa-east-1` (São Paulo) to produce single-digit-
to-low-double-digit RTT -- no standard AWS region qualifies (the closest,
`us-east-1`, is 111ms away). AWS Local Zones are small, metro-adjacent
extensions of a parent region, specifically meant for exactly this kind of
low-latency-to-a-specific-metro use case, so they were investigated as a
candidate. All of this was a read-only check with the restricted
`mockopin-pqc` profile -- no policy change, no infrastructure created.

**Local Zones found** (via `aws ec2 describe-availability-zones
--all-availability-zones --filters Name=zone-type,Values=local-zone`,
region `us-east-1`, since Local Zones are organized under a parent
region's API even though they're physically remote from it):

| City | Zone name | State | Opt-in status |
|---|---|---|---|
| Buenos Aires | `us-east-1-bue-1a` | available | not-opted-in |
| Santiago | `us-east-1-scl-1a` | available | not-opted-in |
| Lima | `us-east-1-lim-1a` | available | not-opted-in |
| Rio de Janeiro | -- | **does not exist** | -- |

No Rio de Janeiro Local Zone exists at all (confirmed -- it's simply not
in the list AWS returns). The other three exist and are `available`
(meaning AWS offers them), but this account has never opted into any of
them, and a check of their instance type catalog returned zero offerings
for all three (`describe-instance-type-offerings` by availability-zone-id)
-- expected, since nothing is queryable about an un-opted-in zone's
catalog until it's activated. **No action was denied by the IAM policy**
-- every call above succeeded; the empty results are because the zones
aren't active, not because of a permissions problem.

**Proposed measurement (not executed, cost/duration estimated only):**
1. Opt into the Buenos Aires Local Zone group (`us-east-1-bue-1`) -- an
   account-level action separate from the IAM policy (similar in kind to
   Decision 10's opt-in-region caveat for `ap-east-1`, but Local Zones use
   their own `ModifyAvailabilityZoneGroup` opt-in, not region opt-in).
   Instance type catalog there is unknown until this happens -- Local
   Zones typically offer a narrower selection than full regions (often
   `t3`/`m5`/`c5`-class, not necessarily `t4g`/Graviton) and this would
   need confirming once opted in.
2. Launch one client instance in `us-east-1-bue-1a`, ping `sa-east-1`.
3. Separately, launch 3 instances across `sa-east-1`'s own 3 availability
   zones and measure AZ-to-AZ RTT within the region -- this is new; no
   intra-region measurement has been taken anywhere in this project so
   far, and it's relevant context for interpreting whatever the Buenos
   Aires number turns out to be.
4. Same 3-round/~1h-apart standard as every other measurement here.

**Estimated cost and duration:** a handful of instances (1 Buenos Aires +
up to 3 for the `sa-east-1` intra-region check), same order of magnitude
as every prior discovery run here -- well under $1, ~2h10min for full
3-round rigor (or a faster single-round look first, consistent with how
Decision 12's candidates were first screened before Decision 13's full
confirmation). **Not run -- waiting on the author's go-ahead before any
infrastructure is created**, including the Local Zone opt-in step itself.

**Remaining fallback options, if Local Zones don't pan out** (listed, not
chosen):
1. **Client outside AWS entirely** (e.g. a non-AWS VPS, or a machine
   physically close to São Paulo) -- would need to be explicitly labeled
   as a different *kind* of validation than the rest of this project (real
   -network / not pure-AWS-to-AWS), since it breaks the "everything is
   AWS infrastructure" property every other scenario here has.
2. **Report 14ms and 30ms as not reproducible with pure-cloud AWS
   infrastructure at this precision**, documented plainly rather than
   forcing a poor-fitting substitute -- consistent with how Decision 13
   handled 30ms before the Seoul/Stockholm candidates were found (back
   when the topology was still "any region, not just `sa-east-1`").

Not decided here -- the author chooses between pursuing Local Zones,
accepting an outside-AWS client, or reporting these two scenarios as
cloud-unreachable.

## 18. Instance sizing from real local measurement

**Partially superseded 2026-10-11 by Decision 21.** The idle-footprint
measurement and server recommendation below hold up (Decision 21's peak
data confirms `m6i.large` independently). **The "manual browser login"
claim in the caveat below is wrong and retracted** -- `opin_flow.py`'s
`simulate_login()` already fully automates the login/consent flow over
plain HTTP (no browser, no manual step at all; confirmed live by actually
running it -- see Decision 21). The client recommendation (`t3.small`) is
also superseded -- Decision 21 found a real, large, multi-core CPU burst
in the client-side crypto proxy that `t3.small`'s 2 vCPUs can't realize.

**Context.** `t4g.micro` was correct for discovery (bare ping, no
service) but wrong for Phase 4, which runs the real `docker-compose`
stack under the same PQC handshake load the rest of this thesis measures.
Sizing needs real data, not a guess.

**Measurement.** Brought up the actual stack locally (`auth`, `mtls`,
`mockapi`, `psql`, `mongodb`, `localstack`, `mongo_seed`, via `docker
compose --profile main up`, `CRYPTO_PROFILE=hybrid`) and read
`docker stats` once everything reported healthy/listening:

| Container | CPU (idle) | Memory (idle) |
|---|---|---|
| `mtls` (gateway) | ~0% | 6.5MiB |
| `auth` | ~0% | 60MiB |
| `mockapi` | ~0.1% | 515-540MiB |
| `mongodb` | ~0.5-0.8% | 203-229MiB |
| `localstack` | ~0.03-2.5% | 190-571MiB |
| `psql` | ~0.03% | 92-93MiB |
| **Total** | | **~1.1-1.5GiB** |

**Caveat (WRONG, retracted -- see Decision 21).** This was originally
written as: this is the stack's idle/steady-state footprint, not peak
load, and a proper peak-CPU measurement needs `opin_flow.py`'s full
authenticated flow, which requires a manual, interactive browser login
step that isn't automatable. **That's incorrect.** `opin_flow.py` already
has `simulate_login()`, which drives the entire login/consent interaction
over plain HTTP, fully automated, no browser involved -- confirmed by
actually running it (Decision 21). The `thesis/scripts/README.md` text
this claim was based on was stale documentation describing an earlier,
pre-automation version of the flow. Peak-load data now exists; see
Decision 21.

**Recommendation, server (sa-east-1, the one real MockOPIN installation):
`m6i.large`** (x86, non-burstable, 2 vCPU / 8GiB) -- comfortable headroom
over the measured ~1.1-1.5GiB idle footprint, with room for the PQC
handshake's CPU burst and concurrent containers, consistent with Decision
14's original reasoning (kept valid even though Decision 14's broader
per-scenario-server framing is superseded).

**Recommendation, clients -- SUPERSEDED, see Decision 21.** Originally
`t3.small` (x86, burstable, 2 vCPU/2GiB), reasoned from the client being
"lighter than the full stack." Decision 21's real measurement found the
client-side `tls_kem_proxy` alone bursts well past 2 vCPUs' worth of
parallel CPU during a hybrid handshake -- `t3.small` is too small. The
x86-over-ARM reasoning below is still valid and carries over to Decision
21's revised pick:

Kept x86 (not `t4g`/ARM) deliberately, for the same
confound-avoidance reasoning Decision 1 applied project-wide: an ARM vs.
x86 architecture difference between client and server could itself affect
measured crypto performance, which this thesis has repeatedly gone to
lengths to rule out as a variable (see `thesis/results/v6/Level 1/
DECISIONS.md`, Decision 2, for the canonical example of exactly this kind
of confound being found and eliminated).

**Availability confirmed, read-only, no infrastructure created**, for the
four regions Decision 16 already locked in:

| Region | `m6i.large` | `t3.small` |
|---|---|---|
| `sa-east-1` | yes | yes |
| `ca-central-1` | yes | yes |
| `eu-north-1` | yes | yes |
| `ap-southeast-1` | yes | yes |

(Whichever region eventually serves the 14ms/30ms client, per Decision
17, would need the same check once chosen -- not done here since that
region isn't picked yet.)

## 19. Proposed security posture for the exposed Phase 4 server (not yet implemented)

**Context.** Unlike discovery's throwaway instances (bare AMI, no
service, minutes of life), Phase 4's `sa-east-1` server runs the real
MockOPIN stack and needs to accept connections from whichever region is
currently acting as client -- for hours, across multiple scenarios, not
minutes.

**Proposal:**
- **Restrict server ingress to the current client's IP only**, not
  `0.0.0.0/0` -- either via a Terraform-managed security group rule
  referencing the client instance's Elastic IP (parameterized per
  scenario, same pattern already used throughout `latency-discovery/`'s
  Terraform: `ssh_cidr`/`icmp_cidr` computed from a sibling module's
  output), or an Elastic IP allocated to the client and referenced
  directly. Either way, the rule is specific to whichever client region
  is active for that scenario, not a standing broad allowlist.
- **Open only for the duration of that scenario's data collection**, not
  for the whole Phase 4 run -- `terraform apply` brings up the pairing for
  one scenario, collects, then `terraform destroy` (reusing the pattern
  already proven across every discovery run: a verified-clean teardown,
  checked per region via the AWS API directly, not just trusted from
  Terraform's own state).
- **No credential or real OPIN data on any instance** -- same invariant
  every discovery instance in this project has already held throughout
  (bare/unmodified `docker-compose` stack, synthetic data only, consistent
  with Decision 8's "MockOPIN uses only synthetic data" finding).

Not yet implemented -- this is the proposed shape for Phase 4's Terraform
when it's actually built, not a change made now.

## 20. Proposed Phase 4 data-collection protocol (not yet implemented)

**Proposal:**
- **Each scenario collected across 2-3 time-of-day windows**, not a single
  continuous sitting -- same rationale Decisions 9/10 already established
  for latency discovery (guards against one window's network conditions
  being unrepresentative), extended to the real experiment's actual
  request-level measurements, not just ICMP.
- **pcap captured per execution, on both the server and the client** --
  gives an independent, protocol-level cross-check of the measured RTT
  (addressing Decision 10's standing caveat that ICMP RTT and the real
  TLS-handshake path aren't guaranteed identical), and a forensic record
  if any run's numbers look anomalous.

Not yet implemented -- proposed shape for Phase 4, to be refined when its
Terraform and run scripts are actually built.

## 21. Real peak-load measurement, all 3 crypto profiles -- corrected instance recommendations

**Context.** Decision 18's "manual login blocks peak measurement" claim
was wrong (see the correction there). `opin_flow.py`'s `simulate_login()`
fully automates the login/consent flow -- confirmed by actually running
it, no code change needed. This decision replaces Decision 18's idle-only
data with real peak measurement during actual automated flow execution,
across all 3 crypto profiles.

**Method.** Brought up the real stack locally via
`switch_crypto_profile.py` (the project's own canonical tool, which
itself runs 5 full automated flows per profile switch as a settling
protocol before any measurement -- Decision 4), then ran one additional
`opin_flow.py 0` per profile while sampling `docker stats --no-stream`
every 0.3-0.5s for the duration. Peak (not average) CPU/memory reported
per container, pooled across whichever profile produced the highest
reading.

**Server-side containers** (what would run on the Phase 4 `sa-east-1`
instance):

| Container | Peak CPU (any profile) | Peak memory (any profile) |
|---|---|---|
| `mockapi` | 23.4% (classic) | 673MiB (pqc) |
| `auth` | 12.4% (pqc) | 93MiB (pqc) |
| `mongodb` | 3.8% (pqc) | 198MiB (classic) |
| `mtls` (gateway) | 8.1% (pqc) | 19MiB (classic) |
| `psql` | 1.7% (pqc) | 72MiB (pqc) |

All comfortably light -- `mockapi`'s 23.4% peak is less than a quarter of
one vCPU (Docker's CPU% is normalized to 100% = one full core), and total
peak memory across all 5 stays under ~1.1GiB. **`m6i.large` (2 vCPU/8GiB)
remains the right call for the server** -- now confirmed by real peak
data, not just idle, with ample headroom either way.

**Client-side crypto tooling** (what would run on whichever instance is
the client that scenario) -- this is the real finding:

| Container | Peak CPU | Peak memory | Samples (profile: hybrid) |
|---|---|---|---|
| `tls_kem_proxy` | **1001.5%** | 281MiB | 687% -> 726% -> **1002%** -> 482% -> 490% -> drops to ~0% |
| `pqc_signer_service_run` | 1.1% | 24MiB | negligible |

`tls_kem_proxy` (the Go client that negotiates the PQC/hybrid key
exchange) sustained **multiple consecutive samples above 480%, peaking
past 1000%**, on a 12-core host -- not a single-sample fluke. This is
genuine parallel CPU use during the handshake (ML-KEM/X25519 operations
across the flow's concurrent requests), not an idle-adjacent number like
everything else measured in this project so far.

**Recommendation, clients -- revised: `c6i.xlarge`** (x86, non-burstable,
4 vCPU/8GiB), not `t3.small`. Reasoning and an honest limit on it:
- A 2-vCPU instance (`t3.small`, or `c6i.large`) would simply never reach
  the parallelism this dev machine's 12 cores allowed -- Go's scheduler
  uses whatever `GOMAXPROCS` (default: available cores) gives it, so the
  "1000%" figure is this machine's ceiling, not a hard requirement.
- But under-provisioning here risks a real confound this thesis has
  repeatedly worked to avoid: if the client CPU-throttles during the
  handshake, the *measured* timing reflects CPU contention, not network
  latency -- exactly the kind of non-network variable Decision 1 and
  Decision 18's x86-over-ARM reasoning both exist to rule out.
- `c6i.xlarge` (4 vCPU) is a reasonable middle ground, not a proven
  sufficient one -- **this should be validated directly** (e.g. compare
  completion time/variance on a CPU-limited local Docker run approximating
  2 vs. 4 vCPUs) before Phase 4 locks it in. Not done here.

**Availability confirmed, read-only, no infrastructure created**, for the
four regions Decision 16 locked in:

| Region | `c6i.xlarge` | `m6i.large` |
|---|---|---|
| `sa-east-1` | yes | yes |
| `ca-central-1` | yes | yes |
| `eu-north-1` | yes | yes |
| `ap-southeast-1` | yes | yes |

(Local Zone candidates for 14ms/30ms: see Decision 23 -- `c6i.xlarge`
availability there is unknown until the zone is opted into, same as every
other instance-type question about those zones.)

## 22. Topology fix: server persists through the whole collection campaign

**SUPERSEDED 2026-10-12 (Decision 30) -- scope narrowed, not reasoning
overturned.** With 3 server installations instead of 1 (Decision 30), this
decision's rule applies **per installation**: each of `sa-east-1`,
`us-east-1`, and `ap-northeast-1` stays up for its own scenario(s)'
collection, not rebuilt between them -- `sa-east-1` across its 4
scenarios, the other two across their 1 scenario each (so the
"persists across scenarios" framing is most visible for `sa-east-1`,
trivially true for the other two since they each only ever serve one
scenario). The underlying reasoning (don't pay container-startup +
settling cost more than once per installation) is unchanged.

**Context.** Decision 15 fixed the server to a single `sa-east-1`
installation. Left unspecified: does the server get destroyed and
recreated between scenarios (matching every discovery run's
apply-measure-destroy pattern so far), or does it stay up while only the
client changes? The author clarified this should be the latter.

**Decision.** For Phase 4's actual data-collection campaign:
- **The `sa-east-1` server instance is created once and stays up for the
  entire campaign** (all 5 scenarios), not recreated per scenario -- this
  is a deliberate departure from every discovery run in this project,
  which tore down and rebuilt everything each time (appropriate there,
  since discovery instances ran minutes and carried no state; Phase 4's
  server runs the full stack and benefits from not re-paying container
  startup + settling cost 5 times).
- **Between scenarios, only the security group's ingress rule changes**
  -- narrowed to whichever client region is currently active (Decision 19's
  security proposal), via Terraform, not a server rebuild.
- **Crypto profile switches follow the lab's existing settling protocol**
  (`switch_crypto_profile.py`, Decision 4): 5 discarded full-flow
  executions after each profile switch, before any measurement run counts
  -- same procedure already used and reused throughout this thesis, not a
  new one invented for Phase 4.
- **Everything is destroyed only at the end of the full campaign** (all 5
  scenarios collected), with the same region-by-region verification
  (`aws ec2 describe-instances`/`describe-security-groups`/
  `describe-key-pairs`, checked directly, not trusted from Terraform state
  alone) already proven across every discovery run so far.

This updates Decision 19's security proposal's framing slightly: "open
only for the duration of that scenario's data collection" now means
*changing the ingress rule* for that duration, not standing up a fresh
server each time.

## 23. AWS Local Zone instance types, opt-in command, and prepared (not applied) Terraform

**Instance type availability in the 3 candidate Local Zones.** Still
**unknown** -- re-checked (`describe-instance-type-offerings`,
`location-type=availability-zone`, both by zone name and by filter) for
`us-east-1-bue-1a`, `us-east-1-scl-1a`, `us-east-1-lim-1a`: all three
return an empty offering list. This is consistent with Decision 17's
earlier finding, not a new problem -- AWS genuinely does not expose a
non-opted-in zone's instance catalog via this API, confirmed by trying
multiple query forms. No policy or permission issue; the calls succeed,
they're just empty. **This can only be resolved by opting in.**

**Exact opt-in command (NOT executed -- for the author to run with an
admin profile, same pattern as Decision 11's IAM policy change):**

```bash
aws ec2 modify-availability-zone-group \
  --profile <admin-profile> \
  --region us-east-1 \
  --group-name us-east-1-bue-1 \
  --opt-in-status opted-in
```

(`us-east-1-bue-1` is the zone *group* name for Buenos Aires, confirmed
from Decision 17's `describe-availability-zones` output -- distinct from
the zone name itself, `us-east-1-bue-1a`.)

**Terraform prepared for the proposed test, plan-only, not applied.** New
directory: `latency-discovery/terraform-bue-lz-test/`. Topology:
- One client instance in the Buenos Aires Local Zone (`us-east-1-bue-1a`)
  -- needs its own subnet + route table + IGW route, since Local Zone
  subnets aren't created automatically the way standard-AZ default
  subnets are (confirmed: `172.31.128.0/20` picked as an unused block in
  the default VPC's `172.31.0.0/16`, verified against existing subnets'
  CIDRs before writing this). `instance_type` is a **placeholder**
  (`t3.medium`) -- unconfirmed until the opt-in above happens and the
  catalog can actually be queried; must be re-verified before applying.
- Three instances across `sa-east-1`'s existing 3 AZs (`sa-east-1a/b/c`,
  default subnets already exist there, confirmed), measuring RTT among
  themselves (same-AZ and cross-AZ) and reachable from the Buenos Aires
  client. `sa-east-1-a` is the SSH jump host, same minimal-exposure
  pattern as every other discovery Terraform in this project (Decision 7).
  `t4g.micro`, consistent with this project's discovery-instance standard.
- ICMP open (`0.0.0.0/0`) on all instances, same accepted tradeoff as
  Decision 10 (bare AMI, no service, short-lived).

`terraform init` + `terraform validate` + `terraform plan` all ran
successfully (read-only AWS calls only -- AMI/VPC/subnet lookups, no
resources created): **plan: 13 to add, 0 to change, 0 to destroy**. The
plan succeeding even with Buenos Aires not yet opted in confirms the
Terraform structure itself is sound (zone-activation is only checked by
AWS at apply time, not plan time) -- but it is **not applied**.

**Estimated cost and duration.** 4 instances total (1 `t3.medium`-class
Buenos Aires + 3 `t4g.micro` in `sa-east-1`), same 3-round/~1h-apart
standard as every other confirmed measurement in this project --
~2h10min, well under $1 (same order of magnitude as every prior discovery
run; `t3.medium` is a few cents/hour more than `t4g.micro` but doesn't
change the order of magnitude). **Not run** -- waiting on the author's
go-ahead on both the opt-in step and the measurement itself.

## 24. Secret scan confirmed on both pushed commits

Re-scanned the actual committed diffs (not just the pre-commit working
tree) for `6abc057` (code/infrastructure) and `6ef90f7` (data/docs) --
`git show <hash> | grep` for: AWS access key pattern (`AKIA[A-Z0-9]{16}`),
inline secret-key assignment, PEM/SSH private key headers, the AWS account
ID (`<ID_DA_CONTA>`), and the operator's public IP
(`<IP_DO_AUTOR>`). **Zero matches in either commit, for any of the five.**
Confirms the pre-push scan (Decision 11's section on this, and the report
given when the commits were made) was accurate -- nothing slipped through
between that scan and the actual push.

## 25. Buenos Aires Local Zone opted in -- instance catalog found, client type left open

**Opt-in completed 2026-10-12.** The author opted into the
`us-east-1-bue-1` zone group via the AWS Console (Visualização global da
AWS -> Regiões e zonas -> "Argentina (Buenos Aires)" -> Aceitar). Verified
from the restricted `mockopin-pqc` profile: `describe-instance-type-
offerings` for `us-east-1-bue-1a`, empty before the opt-in (Decision 17,
23), now returns a real catalog. (Note: `describe-availability-zones`'
own `OptInStatus` field briefly still read `not-opted-in` right after
accepting -- a metadata-propagation lag, not a sign the opt-in failed;
the functional signal, the instance-type catalog, is what actually
confirmed activation. Re-checked again 2026-10-12: `State: available`,
`OptInStatus: opted-in` -- stable, not a fluke.

**Opting out is NOT self-service, corrected.** An earlier answer in this
project's conversation said opt-out was reversible via CLI/console once
resources are cleared -- **that was wrong.** AWS's own API reference for
`ModifyAvailabilityZoneGroup` states plainly: *"The only valid value is
`opted-in`. You must contact AWS Support to opt out of a Local Zone or
Wavelength Zone group."* ([AWS docs -- ModifyAvailabilityZoneGroup, EC2
API Reference](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_ModifyAvailabilityZoneGroup.html),
confirmed by fetching the page directly, not assumed). Opting in itself
is still free (no charge for the opt-in action -- only for resources
actually launched in the zone), but reversing it requires a support
ticket, not a CLI call. Worth knowing before opting into further zones
(Santiago, Lima) if either isn't going to be used.

**Instance catalog, `us-east-1-bue-1a`:**
```
t3.medium, t3.xlarge, m5.2xlarge, m5.4xlarge, m5.8xlarge, m5.12xlarge,
r5.xlarge, r5.2xlarge, r5.4xlarge, r5.8xlarge, r5.12xlarge,
c5.2xlarge, c5.4xlarge, c5.12xlarge, g4dn.2xlarge
```

**Notable gap: no small non-burstable sizes.** `c5`/`m5` jump straight to
`2xlarge` (8 vCPU) -- nothing at `large`/`xlarge` size for either
non-burstable family. The smallest non-burstable option here is 8 vCPUs,
far more than Decision 21's `c6i.xlarge` (4 vCPU) target; `c6i`/`m6i`
(the newer generation Decision 21 picked for the other 4 client regions)
aren't offered in this Local Zone at all -- only up to the `c5`/`m5`/`r5`
generation. The only size-matched (4 vCPU) non-burstable-*adjacent*
option is `t3.xlarge`, which is burstable, not non-burstable.

**Client instance type for Buenos Aires: not decided here, deliberately.**
This is conditioned on the measured RTT, not chosen in advance:
- If the real Buenos Aires <-> `sa-east-1` RTT lands in the 24-36ms
  tolerance band (making Buenos Aires the actual 14ms or 30ms client),
  the author chooses between `t3.xlarge` (size-matched, burstable, same
  credit-throttling risk Decision 21 tried to avoid) and `c5.2xlarge`
  (non-burstable, but 8 vCPU -- oversized relative to every other client
  region's `c6i.xlarge`, breaking the "one uniform type" goal).
- If the RTT doesn't land in tolerance, this question doesn't arise at
  all -- Buenos Aires wouldn't be used as a client.
Not resolved now -- waiting on the actual measurement (still not run; see
Decision 23's prepared-but-not-applied Terraform, now updated per Decision
26 below).

**`c5.2xlarge` on-demand pricing, approximate, as of 2026-10-12.** The
Price List API (`pricing:GetProducts`) is outside this project's IAM
policy by design -- confirmed denied live (`AccessDeniedException`), not
worked around. Figures below are general public AWS on-demand pricing
knowledge as recalled on the date above, **not a live query and not
re-verified against a current source** -- AWS pricing changes over time,
so treat as order-of-magnitude only; verify exactly via the AWS Pricing
Calculator or Billing Console before any cost commitment, especially if
this decision is read significantly later than 2026-10-12:

| Region | `c5.2xlarge` on-demand (approx., 2026-10-12) |
|---|---|
| `sa-east-1` | ~$0.49/hr (São Paulo carries a real premium over US regions) |
| `ca-central-1` | ~$0.37/hr |
| `eu-north-1` | ~$0.37/hr |
| `ap-southeast-1` | ~$0.43/hr |

**T3 "unlimited" credit mode, from AWS's own documented behavior (not a
live account check -- this is fixed platform behavior, not account
state).** T3 instances (unlike the older T2 generation) default to
**"unlimited"** credit specification when launched without an explicit
override, regardless of launch method (console, CLI, or Terraform).
Unlimited mode lets the instance burst above its baseline CPU for as long
as needed without throttling -- but if sustained above-baseline usage
exceeds the instance's earned credit balance, AWS charges a flat
surplus-credit rate per vCPU-hour for that excess, on top of the
instance's normal price. For a single short compile burst (Decision 26
below), this is very unlikely to exceed the credit balance; across an
extended Phase 4 campaign running many flows back-to-back, cumulative
burst time could plausibly exceed it, which is the real-world version of
the "CPU contention confound" risk Decision 21 raised -- except here it
would show up as an unexpected cost, not (necessarily) throttling, since
unlimited mode pays its way out of throttling instead.

## 26. Correction: the tls_kem_proxy CPU spike is compilation, not handshake cost

**Decision 21's attribution was incomplete, corrected here.** The
1000%+ CPU burst measured for `tls_kem_proxy` was described as happening
"during the hybrid handshake" -- true only in the sense of overlapping
with that run, not in the sense of being handshake computation. Checked
directly: `start_tls_kem_proxy()` (`thesis/scripts/opin_flow.py`) launches
the proxy via `docker run ... go run .` -- **`go run` compiles the entire
Go module from source on every single invocation**, before the proxy
process itself ever calls `ListenAndServe`. The function's own docstring
confirms this explicitly ("`go run` first compiles the module ... before
the Go process itself calls ListenAndServe/Accept"), and
`_wait_for_tls_kem_proxy_ready()`'s docstring independently confirms the
same thing from the readiness-probe side.

**This matches the measured sample pattern exactly:** a concentrated
burst cluster right at the start of the run (687% -> 726% -> 1002%,
consistent with the Go compiler parallelizing across available cores),
tapering to a second smaller cluster (482%, 490%, likely compilation
finishing + the first real request), then dropping to near-zero (2.88%,
0.26%, 0.00%) for the rest of the run -- **one burst per run, not one
burst per handshake**, which is what a compile-once-at-startup cost looks
like, not a per-request crypto cost. If the burst were handshake-driven,
it would recur across the run's many requests, which it doesn't.

**Steady-state (post-compile) consumption is low**: the samples after the
initial burst cluster show `tls_kem_proxy` under 3% CPU for the remainder
of the run -- the actual per-request ML-KEM/hybrid handshake computation,
once the binary is already running, is cheap on this hardware.

**Where the compile sits relative to T_fluxo's clock -- checked directly,
and it's good news.** My own benchmark (above) ran `opin_flow.py`
directly, which starts/stops `tls_kem_proxy` fresh inside every single
invocation -- that's what produced one compile burst per profile in my 3
runs. But **that is not how this project's actual T_fluxo measurements are
taken.** `latency_automation.py` (the real driver behind every T_fluxo
number in `thesis/results/v7/`) starts `tls_kem_proxy` **once per
scenario**, before the warmup run, *outside* `run_once_timed()`'s
`t_start = time.monotonic()` / `t_end = time.monotonic()` window entirely
-- and the project's own existing code comment already explains exactly
why, verbatim:

> "not inside any timed region, and not restarted per run (`go run .`
> recompiles cold each start, several real seconds, which would otherwise
> pollute every single run's own T_fluxo)"
> -- `thesis/scripts/latency_automation.py`, around the `start_tls_kem_proxy`
> call in `main()`

So: **the compile does not land inside the timed region, by design, and
this was already solved in the codebase before this question was ever
asked.** T_fluxo is not polluted by it. The one proxy process started this
way is then reused across the warmup run and every one of the scenario's
`--runs` timed attempts -- meaning the real compile cost is paid **once
per scenario** (however many regions/latencies Phase 4 runs), not once
per individual flow execution.

**This revises the client-sizing urgency down, not the finding itself.**
The 1000%+ burst is real and still something a too-small instance would
feel -- but only once when a scenario's proxy first starts, not
repeatedly throughout a long campaign of many runs per scenario, *if*
Phase 4's own run script follows `latency_automation.py`'s existing
pattern (start once per scenario, reuse across runs) rather than
`opin_flow.py`'s standalone per-invocation pattern my benchmark happened
to use. Decision 21's `c6i.xlarge` recommendation is still reasonable --
a one-time-per-scenario multi-core compile burst is still worth having
headroom for -- but it is no longer "every single flow pays this," it's
"every scenario's setup pays this once."

**Worth surfacing, not deciding or implementing here:** pre-compiling
`tls_kem_proxy` once (`go build`, ship the binary, run it directly instead
of `go run .`) would eliminate even the once-per-scenario compile burst,
on top of `latency_automation.py`'s existing once-per-scenario mitigation
-- lower-priority now that the burst is already confirmed to not recur
per-run and to already sit outside T_fluxo's timed window, but still a
legitimate option if the author wants to shrink the client instance
further. A change to how the tooling runs, not a Terraform/instance-sizing
decision -- left for the author, not decided or implemented here.

## 27. Document hygiene: Decision 8 was out of physical order, numbering now sequential

**Found:** Decision 8 ("OPIN's Brazil-data-residency restriction does not
apply") was physically located between Decision 3 and Decision 4 in the
file, breaking reading order (it was inserted early, out of its
chronological turn, in an earlier session). **Fixed:** moved the Decision
8 section to its correct chronological position, immediately before
Decision 9 -- its number was never changed, only its physical location,
so every existing cross-reference to "Decision 8" elsewhere in this file
remains correct. Verified: `## N.` headings now read 1 through 27 in
file order with no gaps or out-of-sequence entries.

## 28. Buenos Aires LZ test: private IP within sa-east-1, public IP crossing to Buenos Aires

**Decision.** For `terraform-bue-lz-test`'s RTT measurement, each
directed pair targets a different address depending on what it's actually
measuring:
- **`sa-east-1-*` <-> `sa-east-1-*`** (any of `a`/`a2`/`b`/`c` against each
  other): pings the destination's **private IP**. All 4 instances share
  the same default VPC -- there's no reason to route the measured traffic
  out through the internet gateway and back when a direct private path
  exists; using the public IP here would measure something closer to
  "NAT/IGW round-trip," not the region's real internal network latency.
- **`sa-east-1-*` <-> `buenos-aires`** (either direction): pings the
  **public IP**. Buenos Aires is a separate zone group in `us-east-1`
  entirely -- no VPC peering or private connectivity exists between it and
  `sa-east-1`'s VPC, so the public path is the only one that's actually
  reachable, and also the only honest measurement of what Phase 4's real
  client-server traffic would use if Buenos Aires became a scenario's
  client.

Each measured pair's choice is recorded directly in the output JSON
(`rounds[].ip_kind_used`, keyed the same way as `rounds[].pairs`) --
auditable per-pair, not just asserted here. SSH *orchestration* (how the
operator's machine reaches each instance to run the `ping` command)
always uses public IPs regardless of this choice -- that's a separate
concern from what's being measured, and the existing single-jump-host
pattern (Decision 7) doesn't change.

**Opting out of Buenos Aires requires an AWS Support ticket, not a CLI
call -- confirmed from AWS's own API documentation, repeated here for
visibility (see Decision 25 for the first citation).** The
`ModifyAvailabilityZoneGroup` API reference states: *"The only valid value
is `opted-in`. You must contact AWS Support to opt out of a Local Zone or
Wavelength Zone group."* ([AWS docs](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_ModifyAvailabilityZoneGroup.html)).
Opting in remains free; only resources actually launched in the zone
cost anything. This is now also noted in `README.md`.

## 29. Hard blocker: this account's Free Tier plan can't launch Buenos Aires's instance catalog at all -- and casts doubt on Decision 14/18/21's bigger-type recommendations too

**Context.** The Buenos Aires apply attempt (Decision 28's fix applied)
failed again, differently: `InvalidParameterCombination: The specified
instance type is not eligible for Free Tier.` Everything created up to
that point (14 resources) was destroyed and verified clean -- same
region-by-region + Local Zone check as the first failure (Decision 25's
protocol), zero instances/security groups/subnets/volumes/key pairs left
in `sa-east-1` or `us-east-1`/Buenos Aires.

**This account was created on the free "6 meses" plan** (Phase 0's own
record). Querying `describe-instance-types --filters
free-tier-eligible=true` shows this account can currently only launch:
`t4g.micro`, `t4g.small`, `t3.micro`, `t3.small`, `c7i-flex.large`,
`m7i-flex.large`.

**Checked directly: Buenos Aires's entire instance catalog has zero
overlap with that list.** Every one of the 6 free-tier types was checked
against `us-east-1-bue-1a`'s offerings individually -- all 6 came back
"not available." Buenos Aires only offers `t3.medium`/`t3.xlarge`, the
`m5`/`r5`/`c5` families, and `g4dn.2xlarge` -- none free-tier-eligible.
**This specific test cannot run on this account's current plan, full
stop** -- not a bug in this project's Terraform, not something a
different instance-type choice from Buenos Aires's catalog can route
around.

**Bigger implication, not yet confirmed either way: Decisions 14/18/21's
`m6i.large`/`c6i.xlarge`/`c5.2xlarge` recommendations for Phase 4 may have
the same problem.** Those were confirmed *available* via
`describe-instance-type-offerings` (which only checks whether the region
offers the type at all) -- never actually *launched*, so free-tier
eligibility was never tested for them the way it was just tested, by
accident, for Buenos Aires's `t3.medium`. None of `m6i.large`,
`c6i.xlarge`, or `c5.2xlarge` appear on this account's free-tier-eligible
list either. Whether that means they're *also* blocked, or whether the
restriction is specific to something else about this particular attempt,
is **not yet confirmed** -- would need an actual launch attempt (real
cost, however small) in a standard region to know for sure, which hasn't
been done.

**Two ways forward, not decided here:**
1. **Upgrade the account from the free "6 meses" plan to a standard
   (Pay-As-You-Go) plan** in Billing settings -- resolves this test AND
   removes the open question about Phase 4's bigger instance types, at
   the cost of losing the $200 free-tier credit's remaining headroom
   protection (still pay-as-you-go pricing either way; the main loss is
   the credit itself and the softer guardrail against a runaway bill that
   the free-plan structure provides).
2. **Abandon the Buenos Aires Local Zone measurement** on this account as
   it stands -- Decision 17's third fallback option (report 14ms/30ms as
   not reproducible at this precision) becomes the practical default,
   independent of whether Santiago/Lima's catalogs have the same problem
   (not checked -- no reason to expect they'd differ, same account-level
   restriction).

Author's call -- not decided or acted on here.

## 30. Final Phase 4 topology: 6 scenarios, labeled by measured RTT, 3 server installations

**The experiment's focus is application behavior as a function of latency
level, not of region.** Scenarios are labeled **only by their measured
RTT** -- not by nominal targets (14/30/140/225/320ms, the original v1-v7
labels) and not by region names. Region names are implementation detail:
they appear in `README.md` and `DECISIONS.md` (where the *why* of each
choice needs to be traceable), but not as the scenario's identity.
Concretely, Phase 4's result folders should follow the same convention
v1-v7 already use for `{latency_ms}ms/` -- real measured values
(`123ms/`, `219ms/`, etc.), not region-named folders -- consistent with
how this thesis has structured every result set so far, just now applied
to real-AWS numbers instead of `tc`/`netem` targets.

**Final design -- 6 scenarios, 3 server installations:**

| Label (measured RTT) | Server | Client |
|---|---|---|
| 0ms | `sa-east-1` | `sa-east-1` (co-located, no real hop) |
| 14.7ms | `us-east-1` | `ca-central-1` |
| 33.2ms | `ap-northeast-1` | `ap-northeast-2` |
| 123ms | `sa-east-1` | `ca-central-1` |
| 219ms | `sa-east-1` | `eu-north-1` |
| 325ms | `sa-east-1` | `ap-southeast-1` |

This supersedes Decision 15's single-installation design (marked above,
not deleted) and narrows Decision 22's scope to per-installation (marked
above). **Why not a single installation after all:** Decision 17's search
for a `sa-east-1`-reachable 14ms/30ms client (Local Zones) hit a hard
account-level blocker (Decision 29) with no resolution available without
either an account upgrade or abandoning the measurement (Decision 31
below) -- but 14.7ms and 33.2ms were *already* confirmed, real, properly
3-round-sampled measurements sitting unused (Decisions 16 and 13 Part B)
from region pairs that don't involve `sa-east-1` at all. Rather than
leave two already-measured, high-quality data points unused while
chasing a third that this account can't currently produce, Phase 4 uses
all three: one shared `sa-east-1` installation for the 4 scenarios it
does reach well, plus two small dedicated installations for the two it
doesn't.

`sa-east-1` remains the server for 4 of 6 scenarios -- Decision 1's
thematic rationale (OPIN / Brazilian regulation) stays the dominant
choice, not abandoned, just no longer exclusive.

## 31. Buenos Aires Local Zone measurement abandoned

**Decision.** Per Decision 29's hard blocker (no instance type in Buenos
Aires's catalog is free-tier-eligible on this account) and Decision 30's
resolution (14.7ms and 33.2ms already covered by other, unblocked
measurements), the Buenos Aires Local Zone measurement is **abandoned**,
not pursued further. Decision 17's third fallback option ("report as not
reproducible at this precision") doesn't even apply -- the question these
two targets were meant to answer already has a better answer (Decision 30)
than Buenos Aires would have given.

**The opt-in already performed stays in effect.** Per Decision 25/28,
opting out is not self-service -- it requires an AWS Support ticket, not
a CLI call ([AWS docs](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_ModifyAvailabilityZoneGroup.html)).
Opting in itself was free and remains free to leave as-is; no action is
taken to reverse it, since doing so would cost a support interaction for
no benefit.

**No resources remain in the zone** -- verified directly (not assumed)
after both failed apply attempts (Decisions 25 and 29): `describe-
instances`/`describe-security-groups`/`describe-subnets`/`describe-
volumes`/`describe-key-pairs` in `us-east-1` scoped to
`us-east-1-bue-1a`/the `mockopin-pqc-aws` tag all returned zero, both
times. The zone sits opted-in and empty -- no ongoing cost, nothing to
clean up later.

## 32. `m7i-flex.large`/`c7i-flex.large` as a Free-Plan-compatible alternative to Decision 21's instance types -- CPU behavior, availability, cost estimate

**Context.** Decision 29 left open whether Decision 14/18/21's
`m6i.large`/`c6i.xlarge`/`c5.2xlarge` recommendations are actually
launchable on this account -- none of them are on the confirmed
free-tier-eligible list, and none has been launch-tested. `m7i-flex.large`
and `c7i-flex.large` **are** on that list (same list as Decision 29), so
they're investigated here as a cheaper, almost-certainly-launchable
alternative -- not yet decided as Phase 4's actual choice.

**CPU behavior** (official AWS docs,
[m7i-flex product page](https://aws.amazon.com/ec2/instance-types/m7i/),
checked 2026-10-12): "M7i-flex instances efficiently use compute resources
with the ability to scale up to the full compute performance a majority
of the time," with **40% baseline performance per vCPU** and bursts to
100% on demand. `c7i-flex` documents the same baseline/burst model. No
credit-surcharge mechanism is documented (unlike T3 "unlimited" mode's
surplus-credit billing).

**Availability**, confirmed via `describe-instance-type-offerings`: both
types are offered in all 7 campaign regions (`sa-east-1`, `us-east-1`,
`ca-central-1`, `ap-northeast-1`, `ap-northeast-2`, `eu-north-1`,
`ap-southeast-1`).

**Cost -- estimate only, not independently re-confirmed per region,
checked 2026-10-12:**

| Component | Source | Rate used |
|---|---|---|
| Compute | [instances.vantage.sh](https://instances.vantage.sh/aws/ec2/m7i-flex.large) (mirrors AWS on-demand) | `m7i-flex.large` $0.085-0.096/hr, `c7i-flex.large` ~$0.085/hr (us-east-1 baseline); assume up to ~1.5x in pricier regions (`sa-east-1`, `ap-northeast-*`), not independently confirmed |
| EBS (30GB root, per AMI snapshot minimum) | [aws.amazon.com/ebs/pricing](https://aws.amazon.com/ebs/pricing/) (AWS's own worked examples) | gp3 $0.08/GB-mo, gp2 $0.10/GB-mo |
| Public IPv4 | [AWS blog, Public IP Insights](https://aws.amazon.com/blogs/aws/new-aws-public-ipv4-address-charge-public-ip-insights/) | $0.005/hr/address, in effect since 2024-02-01, charged whether idle or attached |
| Data transfer OUT | [aws.amazon.com/ec2/pricing/on-demand](https://aws.amazon.com/ec2/pricing/on-demand/) | first 100GB/month free account-wide (confirmed); this workload's traffic is small TLS/HTTP flows + header-only pcaps, almost certainly under that allowance |

**Rough estimate for the full campaign** (3 server installations + 6
client instances, generous multi-day up-time budget, ~276 instance-hours):
roughly **$30-50 total**, an order of magnitude under the $200 Free Plan
credit. Still an estimate, not a commitment -- not independently verified
per-region, and neither type has actually been launch-tested yet (same
gap Decision 29 flagged for the bigger types -- the free-tier-eligible
flag is a stronger signal than mere regional availability, but isn't a
substitute for a real launch).

**Not decided:** whether Phase 4 actually uses `m7i-flex`/`c7i-flex`
instead of Decision 21's types. A real, brief launch-and-destroy test
(proposed, not yet run) would close this gap -- see the "launch test"
proposal recorded alongside Decision 33.

## 33. sa-east-1 intra-region AZ-to-AZ RTT measured (no Buenos Aires) -- proposed lowest scenario

**Measurement.** 4 nodes in `sa-east-1`, all `t4g.micro` (free-tier-
eligible, Decision 29): `sa-east-1-a` (AZ ID `sae1-az1`, jump host),
`sa-east-1-a2` (same AZ ID `sae1-az1` -- same-AZ pair), `sa-east-1-b`
(`sae1-az2`), `sa-east-1-c` (`sae1-az3`). 3 rounds ~1h apart, 20
pings/pair/round, both directions, 12 directed pairs/round -- same
sampling standard as every other measurement in this project. 100%
response rate, all 3 rounds. **Every pair ping targeted the destination's
private IP** (Decision 28's rule for same-VPC/same-region pairs), not the
public internet path.

Raw data, unfiltered (including one isolated 18ms spike in round 2's
`a2->a` pair, kept as measured, not treated as an outlier) is in
`thesis/results/v8/aws-sa-az-rtt-raw/`, with its own README covering the
AZ-ID/AZ-name distinction, instance type, and round timestamps.

**Result -- stable across all 3 rounds:**

| Pair | RTT (median, ms) | Pattern |
|---|---|---|
| same AZ (`a<->a2`) | ~0.2 | floor -- effectively no network hop |
| `*<->c` | ~1.1 | cross-AZ |
| `*<->b` | ~1.4-1.8 | cross-AZ |

**Proposal (not yet decided): the lowest scenario is a client co-located
in the same zone as the server**, labeled by its own measured RTT
(~0.2ms, per the AZ-ID same-zone pair above) rather than treated as a
bare "0ms" placeholder with no real measurement behind it -- consistent
with Decision 30's rule that every scenario is labeled by what was
actually measured.

**Caveat, before this label is adopted: this RTT was measured over the
private IP, not the path a real client actually uses.** A real client in
Phase 4 reaches the server over its public IP / the real network path
(NAT, routing out and back in) -- the private-IP figure here is a
same-VPC floor, not necessarily identical to what the public path adds.
The region-control proposal (client co-located with each of the 3 server
regions, to check server region isn't a confound -- reported separately,
not yet itself a numbered decision here) is the natural place to also
measure this same pair over the **public** IP path, before the lowest
scenario's final RTT label is fixed. Not done yet -- proposed only, and
not to be run without the author present.
