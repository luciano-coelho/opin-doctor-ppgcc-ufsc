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
`latency-discovery/aws-region-discovery-01-single-origin-raw/latency_samples.json`. All 10 instances, their
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
`latency-discovery/aws-region-discovery-03-candidates-raw/`.

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
`latency-discovery/aws-region-discovery-04-candidates-confirm-raw/`.

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

**SUPERSEDED 2026-10-12 (Decision 34) -- the window count/size.** "2-3
time-of-day windows" is replaced by an exact figure: 3 windows of 10 runs
each (30 runs/profile/scenario total). The pcap-per-execution proposal
below is not superseded -- Decision 36/37 carry it forward with more
detail (header-only, port 443, compressed).

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
`thesis/results/v8/latency-discovery/aws-region-discovery-05-sa-az-raw/`,
with its own README covering the
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

## 34. Final Phase 4 execution protocol: 30 runs/profile/scenario, 3 randomized-order daily windows, 0ms/region controls discarded

**SUPERSEDED 2026-10-12 (Decision 40) -- the switch-counting argument was
wrong, corrected there.** This decision's "30 runs, 3 windows of 10,
profile order randomized per window" core design stands. What's
corrected: the claim here (implicitly) that scenario order didn't need
its own registered rule, and Decision 39's settling-time estimate, which
assumed one profile switch per scenario transition -- wrong, a scenario
change needs no switch at all, only a profile change does. Decision 40
registers the actual scenario-rotation rule and redoes the math.

**SUPERSEDED again 2026-10-12 (Decision 53) -- the 0ms-control discard,
reversed.** This decision recorded "0ms control on all three
installations... discarded by the author's decision." That specific
call is reversed in Decision 53: each server's own `L0` (co-located
client, same AZ ID) is now measured after all -- not as the originally
discarded standalone "0ms control" experiment, but because it turned
out to double as both a region control and a same-machine-type control
using real campaign data, at the cost of 2 more instances rather than a
separate dedicated experiment. The region-control *procedure* (client
co-located with each server region, Decision 39) is still discarded,
unchanged -- only the "measure 0ms per installation" half is reversed.

**Decision, author's call.** Supersedes Decision 20's looser "2-3
time-of-day windows" (marked above, not deleted) with an exact design:

- **30 runs per (profile, scenario) pair**, split into **3 windows of 10
  runs**, spread across the day (not back-to-back) -- same guard against
  single-window network-condition artifacts that Decisions 9/10 already
  established for latency discovery, now applied to the real experiment.
- **Profile order randomized independently in each window.** Each window
  runs all 3 profiles as 10-run blocks (to amortize `switch_crypto_profile.py`'s
  settling cost -- Decision 4's 5 discarded flows per switch -- across 10
  real runs instead of paying it per run), but the *order* of the 3
  blocks is re-randomized every window. This guards against time-of-day
  drift being confounded with profile order (e.g., if Classic always ran
  first in a day and conditions degrade as the day goes on, that would
  masquerade as a profile effect).
- **Lab used N=10; the real campaign uses N=30** -- explicit magnitude
  change, registered so the two are never conflated when comparing v7's
  simulated-latency reports against v8's real-latency ones.

**Three-installation design** (confirms Decision 30's table, restated
with the client detail for each cell):

| Server | Scenario(s) | Client |
|---|---|---|
| `sa-east-1` | lowest (co-located) | same zone as the server (Decision 33's proposal) |
| `sa-east-1` | 123ms | `ca-central-1` |
| `sa-east-1` | 219ms | `eu-north-1` |
| `sa-east-1` | 325ms | `ap-southeast-1` |
| `us-east-1` | 14.7ms | `ca-central-1` |
| `ap-northeast-1` | 33.2ms | `ap-northeast-2` |

**Sizes measured once, not per scenario.** Artifact sizes (handshake,
JWT, certificate, JWK, PKI, OPINsize, etc. -- full list in Decision 36)
are a property of the crypto profile/protocol, not of network latency --
measuring them again at every scenario would add six-fold redundant data
for no analytical benefit. Measured **once, in `sa-east-1`, using the
same `Host`/SNI headers as the local lab** -- keeping the same virtual
host identity the size measurements have always used (Decision 6's
SNI-based routing) means these numbers stay comparable to v1-v7's own
size reports, not a new, incomparable baseline.

**Discarded by the author's explicit decision, not a technical
finding:**
- **0ms control on all three installations** (i.e., measuring each
  installation against a same-region client too, beyond the one already
  serving as the lowest scenario) -- discarded.
- **The region-control procedure** proposed earlier (client co-located
  with each of the 3 server regions, to statistically rule out server
  region as a confound) -- discarded.

**Limitation to carry into the thesis's own write-up, not just this
log:** the 14.7ms and 33.2ms scenarios run on **different installations**
than the 4-scenario `sa-east-1` block. Any difference observed between
these two scenarios and the other four cannot be cleanly attributed to
latency alone -- server-region/installation is a confound that was
deliberately left unresolved once the region-control procedure built to
address it was discarded. This should be stated as an explicit limitation
wherever these two scenarios are compared against the `sa-east-1` four,
not silently treated as equivalent data.

## 35. Pilot: 10 runs/profile at the lowest scenario and 325ms, under the definitive protocol

**SUPERSEDED 2026-10-12 (Decision 46) -- scope extended, not reversed.**
This decision's core (10 runs/profile, lowest + 325ms, definitive
protocol, conditional retention rule) stands. Decision 46 adds: public-IP
validation of the lowest scenario's RTT, a with/without-tcpdump overhead
comparison, and a written confirmation that nothing on AWS uses
`tc`/`netem`.

**Decision.** Before the full 30-run campaign, run a **pilot**: 10
runs/profile (not 30) at exactly 2 scenarios -- the lowest (near-0ms,
`sa-east-1` co-located) and 325ms (`sa-east-1`/`ap-southeast-1`) -- the
two extremes of the design. Uses the **definitive protocol** (Decision
34's windowing/randomization rules, Decision 36's full metrics list,
Decision 37's raw-data retention), not a throwaway smoke test.

**Conditional retention rule, registered before the pilot runs (so it
can't be adjusted after seeing the data):**
- **If the protocol doesn't change afterward**, the pilot's 10 runs/profile
  count as **window 1** of those two cells (lowest and 325ms, all 3
  profiles) -- not discarded, not duplicated, not re-run.
- **If the protocol does change** as a result of what the pilot reveals,
  the pilot's data is **not discarded either** -- it moves to a clearly
  separate, labeled folder, kept for the record. Same "never discard,
  always relocate" practice this project already applies to settling
  runs and the abandoned Buenos Aires Terraform (Decision 31).

## 36. Campaign measurement list -- what every run must capture

**Decision, registered as the source of truth for Phase 4's actual
collection code (not yet built).** Every execution captures:

**Core timing.** T_fluxo per execution; per-endpoint latency (P50 and
P95) at every level; T_fluxo decomposition (handshake / server / rest)
from the same batch; isolated sign/verify time measured on-instance;
per-step timing for each call in the flow; protocol deadline margins
(PAR TTL and authorization-code TTL) at each level; failure and retry
rates.

**Sizes and artifacts** (measured once per Decision 34, not per
scenario): handshake size, JWT, certificate, JWK, PKI material, bytes
per participant, OPINsize; JWT and JWK captured **both** in raw form and
in their transmitted form (base64url); the JARM redirect URL's size.

**Counts.** Connections, tokens, lookups ("buscas"); effective round
trips counted directly from the pcap (not assumed from the protocol
spec); packets per flow, broken down by profile and by level;
fragmentation and retransmissions per flow.

**Environment metadata, per execution** (so every run is independently
reproducible/auditable): instance type, image identified **by digest**
(not a mutable tag), git commit, AZ IDs involved, and clock
synchronization state.

**Resource usage.** CPU, steal time, and memory, sampled on **both**
client and server.

**Network quality.** Packet loss, jitter, and one-way delay (requires
synchronized clocks -- not just RTT/2); reference RTT measured **before
and after each block** (not just once at the start), so any drift during
a block's execution is caught, not assumed away.

**Bytes on the wire by direction** (not just a total).

**Settling runs** (the discarded flows from each profile switch) are
captured and stored, but kept **separate** from the counted data -- same
principle as Decision 35's pilot-retention rule and this project's
standing practice since Decision 4.

## 37. Raw data retention: everything needed to recompute without a new collection, pcap volume estimate, LFS/external-storage contingency

**SUPERSEDED 2026-10-12 (Decision 42) -- the pcap capture detail, not
the retention principle.** The "capture everything, recompute without a
new collection" principle and `calls.jsonl`'s existence stand unchanged.
Decision 42 fixes the snaplen at 128 bytes (this decision's "reduced
snaplen" was never a specific number), adds `calls.jsonl`'s exact field
list, SYN/SYN-ACK RTT, clock-sync requirements, and the GRO/GSO offload
check.

**Decision.** Every calculation in the eventual report must be
re-derivable from data committed to the repository, without a new AWS
collection -- same principle v7 already follows (its own
`audit_recompute_from_raw.txt`/`audit_v7_from_raw.py` exist specifically
to prove this). Concretely, per run:
- One JSON per execution (the run's own record, same shape as v7's
  `run{NN}.json`).
- One append-only, per-call record: `calls.jsonl` (one line per HTTP/TLS
  call in the flow, not just the aggregate).
- The gateway's raw log lines for that run (not just derived numbers).
- CPU/steal/memory time series (not just peak/average -- the full
  series, so steal-affected runs can be identified after the fact, per
  Decision 39's "mark, don't discard" rule).
- The reference pings taken before/after each block (Decision 36).
- A **pcap, header-only, port 443 only** (SSH traffic on 22 explicitly
  excluded -- it's orchestration noise, not experiment data), captured
  with a reduced snaplen and written compressed. **Per capture, record
  the kernel's own dropped-packet count** (`tcpdump`'s own summary line,
  or `/proc/net/dev`'s drop counter) -- a silently-dropped packet would
  corrupt the round-trip count derived from this pcap without this check.

**Pcap volume -- estimate only, checked 2026-10-12, not yet measured for
real.** 540 runs in the main campaign (6 scenarios x 3 profiles x 30
runs; the pilot's 60 runs are not necessarily additive -- see Decision
35). Reasoning-based estimate, not measured: PQC/Hybrid's larger
certificate chains mean more TCP segments per handshake -- call it
500-2000 packets/execution including the full HTTP exchange. At roughly
80 bytes/packet with a header-only snaplen, that is ~40-160KB/execution
uncompressed, likely compressing to roughly **15-100KB/execution**.
Scaled to 540 runs: **roughly 20-60MB compressed for the whole
campaign's pcaps** -- already in "a few dozen MB" territory.

**Contingency, per the author's own threshold:** if the real figure (to
be known for certain once the pilot, Decision 35, actually runs) comes
in above a few dozen MB, propose **Git LFS** (if the hosting platform
supports it for this repository) or **external storage with a SHA-256
hash committed in the repo** pointing at the external blob, rather than
committing large binary pcaps directly. **Not decided which of the two**
-- deferred until the pilot gives a real number instead of this
estimate.

## 38. Proposed v8 top-level layout: `size/`, `latency/`, `artifacts/`, `discovery/` -- proposal only, nothing moved

**SUPERSEDED 2026-10-12 (Decision 53) -- a server-level nesting was
missing.** `artifacts/`/`discovery/` are unaffected. `latency/` and
`size/` each need one more level than this proposal had: per-server,
since the campaign now has 3 server installations each with their own
scenario set, not one flat `{scenario}/` level. Decision 53 has the
corrected tree.

**Proposal, mirroring v7's own top-level layout exactly** (same shape
this thesis has used since v5, just applied to real-AWS data instead of
`tc`/`netem`):

```
v8/size/experiment{1,2,3} - {Classic,PQC,Hybrid}/
  runs/run01.json .. runN.json
  median_metrics.json
  report.md

v8/latency/experiment{1,2,3} - {Classic,PQC,Hybrid}/{scenario}/
  runs/
  median_metrics.json
  report.md

v8/artifacts/{classico,pqc,hybrid}/
  README.md
  <files>

v8/discovery/
  (everything already in latency-discovery/, see below)
```

**Scenario folders use fixed internal names -- `L0`, `L14`, `L30`,
`L123`, `L219`, `L325`** -- the same short labels v1-v7 already use
internally, kept **even though the real measured RTT differs slightly**
from the nominal number in the name (`L14` measures 14.7ms, `L30`
measures 33.2ms) -- this keeps v8 cross-referenceable against v1-v7's
own folder names without forcing a rename of a well-established
convention. **The real measured RTT is never silently implied by the
folder name alone** -- it's recorded explicitly in both the run JSON and
the scenario's `README.md`, consistent with Decision 30's "label by what
was actually measured" rule.

**`discovery/` -- proposal only, nothing renamed or moved yet.**
`latency-discovery/` (its current name) would become `v8/discovery/`,
sitting alongside `size/`/`latency/`/`artifacts/` the same way v7's flat
layout has no equivalent discovery folder at all (v7 never needed real
AWS RTT discovery). Everything already inside it -- the 5 numbered raw
folders (Decision 33's rename), `scripts/`, and the 4 `terraform*/`
directories -- would move as a unit, unchanged internally. **Not
executed.** No files have been moved; this is a proposal for the author
to approve or amend.

## 39. Campaign plan (not executed): order, randomization, report format, analysis policy, duration/cost estimate

**SUPERSEDED 2026-10-12 (Decision 47) -- the scenario-order question is
resolved, and the duration estimate was wrong.** The "open question"
below is answered by Decision 40 (fixed rotation across the 3 windows,
not left to the author). The duration estimate's settling-time component
assumed one profile switch per scenario transition; that's wrong (a
scenario change alone never triggers a switch), so Decision 47 redoes it
with a materially smaller settling-time figure. Report format and
analysis-policy content below are not superseded -- Decision 47 restates
them with two additions (packet-loss upper-bound reporting, the
10-client/control-instance count) rather than changing them.

**Scenario order across a day.** Not specified by the author's brief
beyond "profile order randomized per window" -- **this is an open
question flagged for the author** (see the chat report's "dúvidas"
section). Proposed default, pending confirmation: cycle through all 6
scenarios each window in a fixed, non-randomized order (`L0, L14, L30,
L123, L219, L325`), since scenario order doesn't carry the same
time-of-day-confound risk profile order does (different scenarios run on
different installations for `L14`/`L30`, and sequentially on the same
`sa-east-1` server for the other four -- randomizing *that* sequence adds
operational complexity, namely extra crypto-profile switches, for a
confound risk that's already handled by the window-level spread itself).

**Warmup.** Stored, per Decision 36, but always kept in a file separate
from the counted runs -- same convention as v7's `run00_warmup.json`,
never mixed into `runN.json`'s numbering.

**Report format.** JSON is the single source of truth; Markdown
(`report.md`) is always **derived** from it, never hand-edited --
matching v7's own `latency_automation.py` pattern (`summarize()` reads
the JSON runs, `format_report()` renders Markdown from that summary, not
the reverse).

**Analysis policy, descriptive only:** median, quartiles (Q1/Q3), min,
max, and a bootstrap confidence interval. **No execution is ever
removed** from the dataset for any reason. Runs affected by CPU steal
(Decision 36's steal-time series makes this detectable after the fact)
are **flagged**, not dropped -- visible in the report as a marked
subset, with and without them shown side by side, letting the reader see
whether steal time actually moved the result.

**Duration estimate -- labeled estimate, checked 2026-10-12, sourced
from this project's own v7 data** (not a new measurement): v7's
`report.md` files record real median T_fluxo per (profile, scenario) at
comparable *nominal* latencies -- e.g. hybrid/0ms median 3.7s
(`thesis/results/v7/latency/experiment3 - Hybrid/0ms/report.md`),
hybrid/140ms median 29.2s, hybrid/320ms median 63.4s. Using these as a
rough proxy (v8's real network path isn't identical to `tc`/`netem`'s
symmetric injected delay, so this is explicitly an approximation, not a
re-measurement):
- Active run time (540 runs, blended across profiles, estimated ~80% of
  hybrid's cost): roughly **3 hours of pure execution time**.
- Settling overhead (Decision 4's 5-flow switches, ~9 switches/scenario
  across 3 windows x 3 profile-blocks): roughly **1.5 hours**.
- Since `us-east-1` and `ap-northeast-1`'s single scenarios run on
  **independent installations** from `sa-east-1`'s four-scenario chain,
  they proceed in parallel -- the **dominant serial chain is `sa-east-1`'s
  4 scenarios, roughly ~2 hours of active+settling time**.
- Because the 3 windows are deliberately spread across a day (Decision
  34), the **campaign's wall-clock span is about 1 calendar day**, even
  though active execution is only ~2 hours of it -- servers stay up per
  Decision 22's per-installation persistence rule for that full span, not
  just the active minutes.

**Cost estimate -- labeled estimate, checked 2026-10-12, same sources as
Decision 32** (`m7i-flex.large`/`c7i-flex.large` on-demand, EBS, public
IPv4 pricing pages): assuming 3 server instances + up to 5 client
instances (one per distinct client region: `sa-east-1` co-located,
`ca-central-1` -- shared between the 123ms and 14.7ms scenarios, **not
yet decided** whether as one reused instance or two separate ones --
`eu-north-1`, `ap-southeast-1`, `ap-northeast-2`) up for roughly 1 day
(~24h) each: **~192 instance-hours**, at a blended ~$0.10-0.15/hr
(compute + public IPv4) per instance -> **roughly $20-35** for this
specific campaign run. Well under the $200 Free Plan credit even
stacked on top of this project's prior spend (all prior discovery rounds
combined were under $5).

**Marked as depending on the author's decision, not resolved here:**
1. Scenario order across a day (proposed default above, needs
   confirmation).
2. Whether the `ca-central-1` client is one instance reused for both
   123ms and 14.7ms, or two separate instances.
3. Pcap storage mechanism (Git LFS vs. external + hash) -- deferred to
   the pilot's real volume measurement (Decision 37).
4. `discovery/` folder rename/reorg (Decision 38) -- proposed, not
   applied.
5. Instance type for the campaign (`m7i-flex`/`c7i-flex` vs.
   `m6i`/`c6i`) -- Decision 29/32's open question, pending the
   previously-proposed brief launch test (not run, needs the author
   present).
6. Exact pcap snaplen value (previously proposed ~96 bytes, not
   confirmed).
7. Install automation mechanism (user-data vs. live SSH bootstrap,
   proposed earlier, not approved).

## 40. Scenario rotation inside each window's profile blocks; the earlier switch-count argument was wrong

**SUPERSEDED 2026-10-12 (Decision 56) -- the scenario-by-scenario
ordering, not the switch-count correction.** This decision's actual
correction (switches scale with windows x profiles, not with scenario
count -- Decision 47/54's duration math still rests on that) stands
unchanged. What's superseded is the *ordering* of executions within a
profile block: this decision ran scenario A's full 30 (now 10/window)
before moving to scenario B; Decision 56 replaces that with round-robin
(run 1 of every scenario, then run 2 of every scenario, ...) to spread
within-block time drift evenly across scenarios. The 4-item/2-item
rotation PATTERNS registered below (increasing/decreasing/rotated) are
not superseded -- they still decide which scenarios are in a given
window's block and in what order round-robin itself cycles through
them each pass.

**Decision, registered before any run happens.** A window is not "10 runs
of one (profile, scenario) pair" -- it is **3 profile-blocks** (order
randomized, Decision 34), and **inside each profile-block, the
installation's own scenarios are visited in a rotating order specific to
that window.** A crypto-profile switch (Decision 4's 5-flow settling
protocol) happens only when moving from one profile-block to the next --
**never when moving between scenarios within a block**, because which
client/scenario is being measured has nothing to do with the server's
crypto-profile configuration.

**Registered per-window scenario order** (`sa-east-1`'s 4-scenario chain
-- the only installation with more than one scenario to rotate):

| Window | Order | Rule |
|---|---|---|
| 1 | L0, L123, L219, L325 | increasing by RTT |
| 2 | L325, L219, L123, L0 | decreasing by RTT |
| 3 | L219, L325, L0, L123 | rotated (cyclic shift of window 1's order by 2 positions) |

`us-east-1` (L14 only) and `ap-northeast-1` (L30 only) have a single
scenario each -- rotation is moot with one item, noted explicitly so
it's never mistaken for an oversight later.

**The earlier argument was wrong, corrected here.** Decision 34/39
reasoned that randomizing scenario order "would add extra profile
switches," and used that to justify leaving scenario order unregistered.
This design itself disproves that: switch count is driven purely by
(windows x profiles) = 3 x 3 = 9 switches per installation, **regardless
of how many scenarios that installation serves or in what order** --
`sa-east-1`'s 4-scenario chain costs the *same* 9 switches as
`us-east-1`'s or `ap-northeast-1`'s single-scenario chains, not 4x more.
Decision 47 redoes the settling-time estimate with this corrected model
(materially smaller than Decision 39's original figure).

**Profile order's randomization mechanism, registered so it's
reproducible after the fact:** a seeded PRNG draws the order at the start
of each window; both the seed and the resulting order are logged into
that window's own metadata. Unlike the scenario rotation above (a fixed,
pre-registered pattern), profile order is genuinely randomized at
execution time, not pre-committed -- "sorteada" means drawn, not a fixed
rotation.

## 41. Ten-instance campaign topology; scenario labels come from the campaign's own pcap, not the discovery-phase pings

**SUPERSEDED 2026-10-12 (Decision 53) -- topology count and size-sourcing
both changed.** The 10-instance count is now 12 (2 more `L0` clients,
one each for `us-east-1`/`ap-northeast-1`). The "sizes measured once, 10
runs/profile, `sa-east-1` only" rule (Decision 34, restated in the "sizes"
paragraph below) is also superseded: sizes are now derived from the byte
fields already present in **every** latency execution's own JSON --
`sa-east-1`'s data (all 4 of its scenarios pooled) is official, the other
two servers' `L0` data is a complementary cross-machine check -- not a
separate 10-run size-only collection phase. The scenario-label-from-pcap
rule below is unchanged, now applied per server's own `L0` too (Decision
53), not just assumed identical to `sa-east-1`'s.

**Topology, final count: 3 servers + 6 clients + 1 control instance =
10.**

| Server | Scenario | Client | Notes |
|---|---|---|---|
| `sa-east-1` | L0 | same zone, by AZ ID (Decision 33) | co-located |
| `sa-east-1` | L123 | `ca-central-1` (instance A) | |
| `sa-east-1` | L219 | `eu-north-1` | |
| `sa-east-1` | L325 | `ap-southeast-1` | |
| `us-east-1` | L14 | `ca-central-1` (instance B) | **separate** from instance A |
| `ap-northeast-1` | L30 | `ap-northeast-2` | |
| (none -- `sa-east-1`) | n/a | control instance | outside every measured path |

**`ca-central-1` is explicitly duplicated, not shared.** Resolves
Decision 39's open question in favor of **two separate instances** (one
per server it talks to) -- avoids tying one client instance's lifecycle,
security-group rules, and scheduling to two different installations'
campaigns at once, at the cost of one extra always-small, free-tier-type
instance. Simpler to reason about and tear down independently.

**Scenario labels: sourced from the campaign's own pcap, not the
discovery-phase pings.** Every scenario's *final* RTT label (used in the
JSON and README, Decision 38) comes from the **real SYN-to-SYN-ACK RTT
measured in that scenario's own campaign pcap** (Decision 42) -- not
from the earlier discovery-phase ICMP measurements (Decisions 9, 10, 12,
13, 33) that produced 0.2/14.7/33.2/123/219/325ms in the first place.
Each block's own reference ping (Decision 36/47) is a **cross-check**
against the pcap-derived figure -- a drift indicator, not the primary
source. This matters because every figure used so far is ICMP- and (for
the lowest scenario) private-IP-based; Decision 10 already flagged that
ICMP and real TCP/TLS RTT aren't guaranteed identical, and this is where
that caveat finally gets resolved with real data instead of carried
forward as a caveat.

**Sizes: measured once, `sa-east-1`, 10 runs/profile (not 30).** Sizes
are deterministic by this project's own established pattern (v7
Decisions 10-12: 0% spread across 180 runs) -- 10 runs is enough to
confirm that pattern holds here too, 30 would be redundant. Same
`Host`/SNI headers as the local lab (Decision 34). **Any byte-count
difference from the lab's own numbers is a finding to explain, not
assumed away** -- and explicitly, **no claim is made that artifact sizes
are identical across different machines**, because that was never
tested; a difference would be investigated, not dismissed as noise.

**Lab-vs-campaign non-comparability, registered explicitly.** v1-v7's
lab paid its emulated `tc`/`netem` delay **twice** on every proxied call
(v7 DECISIONS.md, Decision 15, "Mechanism 1: doubled delay on proxied
requests" -- confirmed there with real numbers, not a new claim here).
On AWS, calls between containers on the *same* installation (gateway to
AS/RS) are **local** -- no real network hop between them at all, so
there is nothing to pay twice. **v8's T_fluxo totals are therefore not
comparable 1:1 against v7's, even at a matching nominal latency.** The
lab remains the source for two things only: the **size** measurements
above, and the **relative ordering between crypto profiles**
(Classic < PQC < Hybrid, consistent across all of v1-v7) -- not for
absolute T_fluxo magnitudes, which v8 measures fresh.

**Buenos Aires opt-in -- reconfirmed, unchanged.** Per Decision 31: the
opt-in stays in effect on the account, reversible only via an AWS Support
ticket, zero resources currently in the zone. Nothing new to add.

## 42. Pcap capture and clock-synchronization specifics

**Snaplen fixed at 128 bytes** (Decision 37's "reduced snaplen" language
is now a specific number) -- enough for Ethernet+IP+TCP headers plus the
visible start of the TLS record (e.g. `ClientHello`/`ServerHello`'s
first bytes), still far short of carrying any payload.

**SUPERSEDED 2026-10-22 (see this file's own later entry) -- raised to
256 bytes.** 128 was enough for the TLS record header (ClientHello's own
declared SIZE, confirmed exact and unaffected by this change either way)
but NOT enough to reach the ClientHello's own SNI extension (measured at
TLS-payload offset ~97, needing ~101 bytes of payload where 128 only
yields ~62 after real header overhead) -- 256 recovers it exactly.

**Port 443 only; port 22 (the operator's own SSH) is explicitly excluded**
from the capture filter -- SSH is orchestration noise, not experiment
data, and leaving it out also means the operator's own traffic pattern
is never incidentally captured.

**Captured on both the client and the server, written compressed**
(unchanged from Decision 37). **Per capture, the kernel's own
dropped-packet counter is recorded** (`tcpdump`'s own summary line) into
that run's environment-metadata JSON (Decision 36) -- a silent kernel
drop would otherwise corrupt every packet-count-derived metric from that
run without any visible symptom.

**`calls.jsonl`'s exact per-line fields** (one line per call): endpoint,
bytes sent, bytes received, per-step timing, connection identifier, HTTP
status, and whether the call needed a retry.

**SYN-to-SYN-ACK RTT, measured at one capture point** (the server side,
where `tcpdump` already runs) -- this is the figure that resolves each
scenario's final RTT label (Decision 41).

**Jitter and one-way delay require synchronized clocks on both sides --
RTT/2 is not a substitute** (an asymmetric path makes that assumption
unsafe). Mechanism: **Amazon Time Sync**, the NTP service built into the
AWS hypervisor and reachable at the link-local address `169.254.169.123`
on every EC2 instance with no extra configuration -- Amazon Linux 2023
ships `chronyd` already pointed at it by default. Every instance's sync
status is checked, and the **clock state is recorded per execution**
(via `chronyc tracking`'s own offset / last-offset / leap-status fields),
not assumed good just because the service exists.

**GRO/GSO offload risk, flagged, check proposed for the pilot.**
Generic Receive/Segment Offload can merge multiple real wire packets
into fewer packets as seen by the capturing process -- this would
corrupt any packet-*count*-based metric (packets/flow, fragmentation
counts) without necessarily changing byte counts, and would do so
silently. **Proposed for Decision 46's pilot** (not yet done): capture
the same flow once with offload on (the default) and once with it
disabled (`ethtool -K eth0 gro off gso off` on the capturing interface),
compare packet-count and size distribution between the two runs. If they
differ, every packet-count metric in the real campaign needs either
offload disabled during capture, or an explicit note that counts reflect
post-offload packets, not wire packets -- **not yet known which**,
pending that comparison.

## 43. Flex-type criterion revised (steal + performance drop, no 40% threshold); launch-test plan prepared, not executed

**Correction, not a new finding.** Two turns ago, a criterion for "the
flex type is inadequate" was stated **only in chat, never written into
this log** -- checked directly (`grep` across this file) before this
decision was written, confirming it was never actually registered. That
chat-only version used a "CPU sustained above the 40%-baseline threshold
without recovering" clause, which the author asked to drop.

**Revised criterion, registered here for the first time:**
- **Steal time** persistently above a **pre-registered 5% threshold**
  during synthetic load, **or**
- A **clear performance drop under load relative to the type's own idle
  baseline** -- judged against what the launch test itself measures, not
  against AWS's generic "40% baseline" marketing figure (Decision 32),
  which describes a *guaranteed floor*, not a *failure threshold*, and
  was the wrong thing to test against.

**If the launch test passes** (steal below 5% in every region tested, no
clear load-induced drop): **use one instance type uniformly across all
10 instances** (Decision 41) -- not a per-role mix -- consistent with
Decision 45's "same instance type across every installation" mitigation
for the cross-installation confound (Decision 34's registered
limitation).

**Launch-test plan -- prepared, not executed, not applied.** Terraform +
script to launch `m7i-flex.large` and `c7i-flex.large` in every server
region (`sa-east-1`, `us-east-1`, `ap-northeast-1`) and every client
region (`ca-central-1`, `eu-north-1`, `ap-southeast-1`,
`ap-northeast-2`) -- 7 regions x 2 types = 14 instances, up for a few
minutes each under synthetic load (`stress-ng`, a labeled proxy for
`tls_kem_proxy`'s real shape, not the real cryptographic workload
itself), steal/CPU sampled from `/proc/stat` throughout, then destroyed
with direct-API verification. Lives at
`latency-discovery/terraform-flex-launch-test/`. **`terraform plan`'s
output is in the chat report; `apply` is not run -- requires the author
present, same standing rule as every other apply in this project.**

## 44. AWS account findings: public-IP same-region data transfer is billed; credit balance isn't queryable by this project's IAM profile

**Public-IP, same-region data transfer: confirmed, there is a charge.**
AWS's documented behavior: traffic routed over a public or Elastic IP --
even between two resources in the same region, even the same AZ --
leaves the VPC, crosses the public network border, and comes back in,
billed as Data Transfer OUT. The same traffic over a **private** IP in
the same AZ is free. This directly validates Decision 28's choice
(private IP for every `sa-east-1`<->`sa-east-1` pair in the AZ-to-AZ
test) on cost grounds, independent of that decision's original
measurement rationale. The exact per-GB rate (commonly cited around
$0.01/GB per direction) comes from secondary sources corroborating each
other, not from an independently re-fetched AWS pricing table (AWS's own
live tables are JS-rendered and didn't return the number through a
direct fetch, same limitation noted in Decision 32) -- **the existence
of the charge is the well-confirmed part; the exact rate is a
secondary-sourced estimate.**

**Credit balance / validity: attempted directly, not queryable by this
project's restricted IAM profile.** Three API calls tried, from the
actual `mockopin-pqc-experiment` profile this project always uses (never
an admin credential):

| API | Result |
|---|---|
| `freetier:GetFreeTierUsage` | `AccessDeniedException` |
| `ce:GetCostAndUsage` | `AccessDeniedException` |
| `account:GetContactInformation` | `AccessDeniedException` |

Consistent with Decision 11's policy, which grants only `ec2:*` and
`sts:GetCallerIdentity` -- nothing billing-related was ever added, so
this result is expected, not a bug. **Console path for the author to
check directly:** AWS Billing and Cost Management console ->
"Credits" (left-hand nav) for balance and expiration, or the Billing
Dashboard's "Free Tier" card for usage against the plan's allowances.

## 45. Installation design: user-data only, image-pull-by-digest, precompiled proxy proposal, `REMOTE_GATEWAY_HOST`, control instance, security posture

**No `curl | bash`, no live SSH bootstrap -- correction to an earlier,
chat-only proposal.** Every instance's setup runs from **user-data,
versioned in this repository, pinned to a specific commit** -- one
command per region to launch; the user-data script itself is identical
everywhere, only region/role parameters differ. This retracts a prior
proposal (chat-only, never committed to this log) that suggested a live
`curl | bash` SSH bootstrap -- the user-data approach is reproducible
and auditable from the repository alone, the live-bootstrap approach
was not.

**Image strategy, answered: build once, pull by digest.** MockOPIN's
images are built **once**, pushed to a registry, and every server
**pulls by digest** -- not built independently on each of the 3 server
installations, even with locked dependency versions. Reasoning:
independent per-server builds leave room for silent drift (different
regions can resolve base-image/package-mirror CDNs differently) even
with identical lockfiles; pulling one identical digest everywhere
removes that variable by construction. This is also what makes Decision
36's "image identified by digest" metadata requirement actually mean
something, rather than recording a digest that's merely hoped to match
across installations.

**`tls_kem_proxy` as a precompiled binary -- proposed, not
implemented.** Decision 26 already found the proxy's 1000%+ CPU spike
was `go run .`'s fresh compile every invocation, not handshake cost.
Proposal: `go build` the binary once, ship the binary itself (not source
+ `go run`) to every client instance via the same digest-pinned
mechanism as the server images. This removes the compile-cost variable
from the client instance's resource usage entirely -- not just from
T_fluxo's own timing window, which `latency_automation.py` already
protects (Decision 26), but from every CPU/steal sample taken throughout
the run.

**`REMOTE_GATEWAY_HOST` in `opin_flow.py` -- described, not
implemented.** Minimal, additive change: a new environment variable read
once at startup. When set: (a) skip the `set_latency()` call entirely
(there is no local Docker gateway container to `docker exec` into from a
remote client), and (b) use its value as the connection target instead of
`127.0.0.1`. When unset (today's default): behavior is byte-for-byte
identical to the current local-lab path -- nothing already validated
changes. Not implemented this turn.

**Control instance.** Small, free-tier-eligible type, `sa-east-1`,
**outside every measured path** (never a client or server for any
scenario). Holds the campaign's schedule; runs under `tmux` or
`systemd` (survives an SSH disconnect, resumes unattended); each
execution writes its own JSON immediately (no in-memory state a crash
could lose); syncs collected data back at the end. **Goes into the
eventual campaign Terraform** as its own resource -- that Terraform
isn't built this turn; this is the requirement registered for when it
is.

**Exposed server, security posture.** The security group opens only the
*currently active* client's IP, only for that scenario's collection
window -- never a standing allowlist for every client region
simultaneously. No credential and no real OPIN data ever touches any
instance (MockOPIN is synthetic-data-only by design, Decision 8 -- this
restates that specifically for the campaign instances, not a new
finding).

**Teardown verification scope, campaign-wide:** instances, security
groups, key pairs, volumes, Elastic IPs, **and the control instance
specifically** (easy to overlook since it's deliberately outside the
"measured path" framing) -- region by region, direct API check, same
standard as every prior teardown (Decisions 25, 29, 33).

## 46. Pilot, extended: public-IP RTT validation, tcpdump overhead check, written tc/netem confirmation

**Extends Decision 35, doesn't replace it.** Same 10 runs/profile at the
lowest scenario and 325ms, same conditional retention rule. Adds three
things:

1. **Validates the lowest scenario's RTT over the real path** -- public
   IP, TCP -- not ICMP over the private IP, which is what Decision 33's
   0.2ms figure actually measured. Closes the exact gap Decision 33
   flagged as pending before that scenario's label could be trusted.
2. **tcpdump overhead check.** A subset of pilot executions run with
   `tcpdump` active and a subset without, comparing T_fluxo and CPU
   between the two -- quantifies the capture's own overhead before
   trusting that it doesn't bias the full campaign's numbers.
3. **Written confirmation, registered here:** nothing in this AWS
   campaign uses `tc` or `netem` at any layer. Every millisecond of
   latency in v8 is real network RTT; `tcpdump` is a passive observer
   only. Consistent with everything built so far -- no Terraform in this
   project has ever provisioned a `netem` qdisc, and `set_latency()`
   (v1-v7's local lab-only mechanism) is explicitly skipped whenever
   `REMOTE_GATEWAY_HOST` is set (Decision 45).

## 47. Campaign plan, redone: corrected settling-time math, 10-instance cost, packet-loss upper-bound reporting

**SUPERSEDED 2026-10-12 (Decision 55) -- the instance/execution count
changed, duration/cost redone again.** 720 executions (8 scenarios, not
6) and 12 instances (not 10) now. Order/report-format/analysis-policy
content below is NOT superseded -- Decision 55 restates it unchanged,
only the numbers depending on instance/execution count are redone.

**Order, report format, analysis policy -- restated, not changed from
Decision 39**, now citing Decision 40's scenario rotation and Decision
41's 10-instance topology: JSON is the single source of truth, Markdown
is always derived; median/quartiles/min/max/bootstrap CI; no execution
is ever removed; steal-affected runs are flagged and shown with/without,
side by side.

**Packet loss, with an upper bound when zero events are observed.** A
flat "0%" with zero observed loss events overstates precision -- instead,
report an upper confidence bound from the number of packets actually
observed (a rule-of-three-style bound: with `n` packets and zero losses
seen, the true loss rate's upper ~95% bound is roughly `3/n`) -- so a
scenario with few packets and zero losses is reported as "no losses
observed, upper bound ~X%," not as a false "0.00%."

**Duration estimate -- corrected, labeled estimate, checked 2026-10-12,
same v7 sources as Decision 39** (hybrid/0ms 3.7s, hybrid/140ms 29.2s,
hybrid/320ms 63.4s): Decision 40's corrected switch-count model changes
the settling-time component materially --
- Active run time (540 runs, unchanged): ~3 hours.
- Settling, recomputed as (windows x profiles) per installation, **not**
  per scenario: `sa-east-1`'s chain needs 9 switches total (not 36) --
  roughly 21 minutes of settling for its entire 4-scenario chain, not
  the ~60 minutes Decision 39 wrongly estimated. `us-east-1`/
  `ap-northeast-1` each need their own 9 switches too (~4-6 minutes
  each).
- `sa-east-1`'s chain remains the dominant serial path (the other two
  installations run in parallel, independent infrastructure): roughly
  **55 minutes of active runs + ~21 minutes of settling =~ 1.25 hours**,
  down from Decision 39's ~1.9-hour estimate.
- Wall-clock span is still **about 1 calendar day**, unchanged -- the 3
  windows are deliberately spread across the day regardless of how
  little active time they actually need; servers stay up the full span
  per Decision 22's per-installation persistence rule.

**Cost estimate -- corrected for the 10-instance topology (Decision
41), labeled estimate, checked 2026-10-12, same sources as Decision 32/44:**
3 servers + 6 clients + 1 control instance, up roughly 24h each: **~240
instance-hours**, at a blended ~$0.10-0.15/hr (compute + public IPv4) ->
**roughly $25-40** for this specific campaign run. Still an order of
magnitude under the $200 Free Plan credit.

## 48. `latency-discovery/` and its raw-data subfolders: current locations confirmed, nothing to move

**Confirmed by direct listing, not assumed.** `latency-discovery/` keeps
its name and location: `thesis/results/v8/latency-discovery/`. All three
folders asked about are **already inside it** -- none is outside, so no
move and no author confirmation is needed this time:

| Asked-about folder | Current path |
|---|---|
| `aws-region-discovery-raw` | `latency-discovery/aws-region-discovery-01-single-origin-raw/` (renamed, Decision 33's sequence-numbering pass) |
| `aws-region-discovery-mesh-raw` | `latency-discovery/aws-region-discovery-02-full-mesh-raw/` (renamed, same pass) |
| `aws-sa-az-rtt-raw` | `latency-discovery/aws-region-discovery-05-sa-az-raw/` (moved into `latency-discovery/` and renamed in the same pass) |

Decision 38's proposed `v8/discovery/` rename (from `latency-discovery/`)
remains a **proposal only** -- not applied, not superseded, just
restated as still pending the author's approval.

## 49. Campaign control-plane infrastructure: networking, control instance, four scripts, safety timer -- prepared, not applied

**Scope.** `thesis/results/v8/campaign/` -- the actual Phase 4 campaign's
Terraform and orchestration scripts, as distinct from
`latency-discovery/`'s exploratory discovery tests. `terraform plan`:
**39 resources to add** (10 instances + 10 Elastic IPs + 10 security
groups + 8 key pairs + 1 generated SSH key), 0 to change, 0 to destroy,
no errors. **Not applied.**

**Networking.**
- **Elastic IP on all 10 instances.** Confirmed, not assumed: an
  Elastic IP costs the same as a plain auto-assigned public IP while
  in use -- AWS's own announcement (already cited, Decision 44) states
  the $0.005/hr charge applies to "in-use Public IPv4 address
  (including Amazon provided public IPv4 and Elastic IP)," the same
  rate either way. EIPs were chosen over auto-assigned public IPs
  specifically because they're stable across a stop/start (the safety
  timer below can shut an instance down without losing its address),
  which a plain auto-assigned public IP would not survive.
- **Elastic IP quota checked directly** (not assumed): `describe-account-attributes`
  in all 7 regions returned the default limit of 5 EIPs/region, 0 in
  use anywhere. The campaign's peak per-region need is 3 (`sa-east-1`:
  server + L0 client + control) -- comfortably inside the default,
  no quota increase request needed.
- **Each server opens port 443 only to its own clients' /32s, one
  ingress rule per client, created once by Terraform and left in place
  for the whole campaign** -- not toggled per-scenario at runtime. This
  revises Decision 45's earlier "open only during the active scenario's
  window" language (dynamic/temporal) in favor of a static-but-scoped
  design: simpler (no runtime security-group mutation, itself a source
  of risk), and no less restrictive -- each server still only ever
  allows its own clients, never a blanket range or another server's
  clients. The one exception: `sa-east-1`'s L0 client is co-located
  (same AZ ID as the server) and is allowed by its **private** IP, not
  its public one -- Decision 28's existing private-IP-within-sa-east-1
  rule, applied here for the first time to campaign (not discovery)
  infrastructure.
- **SSH on every server/client instance accepts connections only from
  the control instance's own Elastic IP.** The control instance itself
  accepts SSH only from the operator's own /32, discovered fresh at
  apply time (`curl -s https://checkip.amazonaws.com`, same mechanism
  as every prior apply in this project) and passed to Terraform as an
  environment variable (`TF_VAR_operator_ip_cidr`) -- never written to
  any file this repository tracks.

**Control instance.**
- **No AWS credential, no IAM role** -- no `iam_instance_profile` is
  set anywhere in `modules/campaign_instance`, and no access key is
  ever placed in user-data (this project has never done that for any
  instance, campaign or discovery). The control instance has zero AWS
  API access of its own; it cannot `terraform destroy` anything itself.
- **A campaign-exclusive SSH key, generated by Terraform
  (`tls_private_key`), never written to user-data or to this
  repository.** The private half exists only in Terraform state (local,
  gitignored, and now explicitly checked by `scan_secrets.sh` -- see
  below) and briefly in memory during `campaign_up.sh`, which reads it
  via `terraform output -raw campaign_private_key` and `scp`s it onto
  the control instance over a **separate** connection authenticated
  with the **operator's own, pre-existing discovery key** (not this
  one) -- the two keys serve different purposes and are never
  conflated. The local temp copy is `shred`-ed immediately after the
  `scp` (`campaign_up.sh`'s `trap ... EXIT`).
- **Inventory (hosts/IPs/roles) is generated by Terraform**
  (the `inventory` output) and copied to the control instance the same
  way, right after the key.
- **IMDSv2 mandatory** (`metadata_options { http_tokens = "required" }`)
  on every instance, campaign-wide -- the documented AWS baseline
  hardening, applied uniformly even though no instance here carries a
  credential IMDSv2 would otherwise protect.
- **Terraform state is local only, already gitignored** (pre-existing
  `.gitignore` rule, unchanged) -- `scripts/scan_secrets.sh` now also
  explicitly checks that no `*.tfstate*` file is tracked, right now or
  at any point in history (a new check, not inferred from the
  `.gitignore` rule alone, which is a convention `git add -f` could
  bypass).

**Four scripts, plus an example vars file** (`thesis/results/v8/campaign/scripts/`):
- `campaign_up.sh` -- discovers the operator's IP fresh, runs `terraform
  apply` (behind an explicit typed confirmation, not `-auto-approve`
  blindly), distributes the campaign key and inventory to the control
  instance, then verifies SSH connectivity and `chronyc tracking`'s
  sync status on every host, proxied through control -- fails loudly
  (non-zero exit, explicit message) on the first mismatch rather than
  continuing past it.
- `campaign_run.py` -- NOT run locally; `campaign_up.sh` installs it on
  the control instance under `systemd` (`campaign_run.service`, same
  directory). Implements the parameterized window schedule, Decision
  40's fixed per-window scenario rotation, a randomized-per-window
  profile order (seed logged), automatic resume (each run's own JSON is
  its resume marker -- already-written runs are never re-run or
  overwritten), and the three pre-block checks (negotiated
  key-exchange group, image digest, disk space). **Its actual
  per-execution step (`run_one_execution()`) deliberately raises
  `NotImplementedError`** -- it depends on `opin_flow.py`'s
  `REMOTE_GATEWAY_HOST` flag (Decision 45), described but not yet
  added to that script; wiring a call to a flag that doesn't exist
  would be fabricated, not prepared.
- `campaign_pull.sh` -- idempotent (`rsync`, safe to re-run), pulls
  campaign data to the operator's own machine, regenerates a sha256
  manifest on the control instance first, then verifies every pulled
  file against it locally, writing a `.pull-verified` marker only on
  success.
- `campaign_down.sh` -- **refuses to `terraform destroy`** unless
  `campaign_pull.sh`'s `.pull-verified` marker exists (bypassable with
  an explicit `--force`, which prints a loud warning first), then
  verifies the teardown directly via the AWS API, region by region:
  instances, security groups, key pairs, volumes, Elastic IPs, **and
  the control instance specifically** (called out by name in the
  script's own output, not just folded into `sa-east-1`'s generic
  count).
- `campaign.vars.example.sh` -- the tracked template; the real copy
  (`campaign.vars.local.sh`, with real local key paths) is gitignored,
  never committed.

**Safety timer, servers and clients only -- not a teardown.** Each
server/client instance runs a `systemd` timer (installed via
user-data, `modules/campaign_instance`'s `templates/safety_timer.sh.tftpl`)
checking a deadline file every 5 minutes; past it, the instance shuts
itself down. Default 48h, renewable by the orchestrator overwriting the
deadline file. **Documented explicitly, here and in `campaign/README.md`:**
this does not release the instance's Elastic IP (still billed) and does
not run any of `campaign_down.sh`'s verification -- it exists so a
crashed orchestrator doesn't leave a billed instance running forever,
not so the operator can skip `campaign_down.sh`. **The control instance
is exempt** (`self_terminate_hours = 0`) -- it must stay up to run
`campaign_pull.sh`/`campaign_down.sh` against.

**Reproducibility.** Pinned provider versions (`~> 5.0` for `aws`, `~>
4.0` for `tls`); `.terraform.lock.hcl` is tracked (not excluded by
`.gitignore`, confirmed by the same pattern already working for every
prior Terraform root in this project). `campaign/README.md` documents
the four commands and their order. No real OPIN data touches any
instance -- MockOPIN is synthetic-data-only by design (Decision 8),
restated here for the campaign instances specifically.

**Caveats, registered explicitly (not just implied by the design):**
state and the campaign's own SSH key are local-only; the control
instance has no power to destroy anything; collected data sits on the
control instance's disk until a verified pull; the safety timer is a
crash net, not a substitute for verified teardown.

## 50. Image delivery: tarball over SCP from the control instance, not a public registry

**Context.** No instance has an AWS credential or an IAM role (Decision
49) -- images still need to reach the 3 servers somehow, without an
ECR/any AWS-authenticated pull. Two options compared, neither needing an
AWS credential at all (neither is an AWS API call -- one is a plain
HTTPS pull, the other is SSH/SCP):

| | Public registry (Docker Hub/GHCR, pull by digest) | Tarball over SCP from control, sha256-verified |
|---|---|---|
| Needs | an explicit secret-scan of the image before every push | nothing new -- reuses the campaign key + the manifest-verification pattern `campaign_pull.sh` already has |
| Exposure | image layers (dependency versions, build structure) visible to anyone, indefinitely | stays entirely inside this project's own private control plane |
| Simplicity | one pull command per instance | a few more manual hops (build -> scp to control -> scp to each server -> load) |

**Decision: tarball over SCP, recommended and chosen.** This project's
posture has consistently been minimal exposure even where the data
itself is synthetic and harmless (Decision 8) -- Decision 45's
"open only to the active client" server posture and Decision 49's
"SSH only from control" rule both already reflect the same instinct.
A public registry, even verified secret-free, still publishes this
thesis's internal implementation details indefinitely for a 3-server,
~1-day-campaign scale that gets nothing in return for that exposure.

**Mechanism, described -- not yet built (a separate, bounded task):**
1. Build each image once (`docker build --pull --no-cache`), tag by digest.
2. **Secret-scan the built image before any distribution** -- `docker save` it, extract the layers, and run `scan_secrets.sh`'s own 5 patterns (AWS key, PEM header, account ID, operator IP -- reused, not reinvented) against the extracted content.
3. `docker save | gzip`, compute sha256 locally.
4. `scp` the tarball + its sha256 to the control instance, over the operator's own key (the same connection `campaign_up.sh` already opens).
5. From control, `scp` the tarball to each server over the campaign key (the same connection direction `campaign_pull.sh`'s manifest pattern already establishes, just reversed).
6. On each server: verify sha256, `docker load`, then `docker inspect --format='{{.Id}}'` and compare across all 3 servers -- this is the actual "identical everywhere" guarantee Decision 45 wanted from "pull by digest," now concretely checkable.

Not built this turn -- a `deliver_images.sh` implementing this is the natural next piece.

## 51. `REMOTE_GATEWAY_HOST` implemented in `opin_flow.py` and `tls_kem_proxy`; regression-tested live across all 3 profiles

**Two things found by direct inspection, not assumed, before writing any
code:**
1. `opin_flow.py`'s own connection targets (`AUTH_CONNECT_HOST` etc.)
   always point at the **local** `tls_kem_proxy`
   (`127.0.0.1:TLS_KEM_PROXY_PORT`) -- what actually has to change for a
   remote gateway is the **proxy's own** upstream `-target` flag
   (hardcoded `"mtls:443"`, the lab's compose-network alias), not
   `opin_flow.py`'s HTTP target. Decision 45's original description
   ("use its value as the connection target instead of 127.0.0.1") was
   imprecise on this point -- corrected here.
2. **A real gap, not a style issue:** `tls_kem_proxy/main.go` only
   explicitly set the upstream TLS `ServerName` (SNI) for the
   `"classical"` baseline curve (`= "matls-api.local"`); for the 3 real
   profile curves (classic->`secp384r1`, pqc->`mlkem1024`,
   hybrid->`secp384r1mlkem1024`) it left `ServerName` unset, relying on
   Go's "defaults to the dial target" behavior. That default breaks the
   moment `target` isn't literally `"mtls"` -- a real IP gets no SNI at
   all (Go omits SNI for literal IP targets, per the TLS spec), and a
   real hostname would send the wrong one. **Fixed:** `ServerName:
   "mtls"` is now set unconditionally on the base config, with the
   existing `"classical"` branch still overriding it to
   `"matls-api.local"` as before -- identical to today's *implicit*
   value when `target` is `"mtls"` (confirmed by the regression test
   below), and the *same explicit* value regardless of what `target`
   becomes.

**Implemented** (diff only, not committed -- left for the author's review):
- `REMOTE_GATEWAY_HOST` (`opin_flow.py`): read once from the
  environment at import time. Unset -- zero behavior change anywhere.
  Set -- (a) `main()` skips `set_latency()` (prints why, instead of
  calling it -- there is no local gateway container to `docker
  exec`/`tc` into from a remote client), (b) `start_tls_kem_proxy()`
  passes `-target {REMOTE_GATEWAY_HOST}:443` instead of `-target
  mtls:443`. `--network insurance-server-lambdas_default` is left
  unchanged either way -- a custom bridge network still NATs to the
  host's own internet connection unless `--internal` is set, which it
  never is here.
- `tls_kem_proxy/main.go`: the `ServerName: "mtls"` fix above.
- `git diff --stat`: `opin_flow.py` +31/-2 (net), `tls_kem_proxy/main.go`
  +23/-8 (net) lines changed.

**Regression test -- run live against the real local lab stack, not
simulated.** Brought up `docker compose --profile main up` (it was not
running before this test; brought back down afterward). For each of the
3 crypto profiles: ran `opin_flow.py 0` once with the ORIGINAL code
(`git stash`-ed the diff) and once with the EDITED code
(`REMOTE_GATEWAY_HOST` unset in both runs), comparing every byte-relevant
field -- `total_bytes_exchanged`, `total_requests`, JWT size/count
fields, `bytes_by_participant`, and `gateway_metrics.handshake_bytes`
(count/mean/p50/p95/p99).

| Profile | All byte fields identical before vs. after? |
|---|---|
| classic | yes |
| pqc | yes |
| hybrid | yes |

Only the live timing fields (`handshake_ms`, `opin_processing_ms`)
differed slightly between runs -- ordinary run-to-run jitter on a live
local stack, unrelated to and unaffected by this change (nothing in the
diff touches a timing-critical path when the env var is unset). The
ad-hoc result files this test wrote (`thesis/results/v3/experiment2 -
PQC/0ms/`) were reverted to their committed state afterward (`git
restore`) -- not left as spurious diffs.

**Not done this turn, flagged rather than silently claimed:** a direct
packet-capture confirmation that the ClientHello itself is
byte-for-byte identical (same SNI, same size) was **not** independently
run -- no sniffer was invoked. The byte-level equality above (identical
`handshake_bytes` count and percentiles) is consistent with an unchanged
ClientHello, but isn't the same evidence a real pcap would give.
Decision 42's pilot-stage capture is the place that actually closes this
with a real packet trace.

**Not affected, by construction:** the "same Host headers" requirement
is unaffected by this diff -- the proxy never parses HTTP at all
(confirmed by `main.go`'s own package comment), so there is no HTTP
Host-header code path this change could touch even in principle.

## 52. Campaign script revisions: mandatory budget/credit confirmation, no instance-type default, fixed UTC windows, operator-IP-update command, post-teardown cleanup prompt; L0's private-vs-public-IP asymmetry registered as a limitation

**`campaign_up.sh`:**
- **Mandatory confirmation, before apply, that the operator personally
  checked -- in the console, just now, not from memory -- the billing
  budget alert and the Free Plan credit balance/expiration.** Decision
  44 already found the restricted IAM profile can't read either value
  via the API -- this has to be a human gate, and it's enforced as a
  typed confirmation (`checked`), separate from the existing `apply`
  confirmation.
- `terraform/variables.tf`'s `server_client_instance_type` **no longer
  has a default** -- `terraform plan`/`apply`/`destroy` now fail
  outright if it isn't set, confirmed live (`terraform plan` without it:
  `Error: No value for required variable`; with `t3.micro` passed
  explicitly: plans cleanly, still 39 resources). Deliberate: Decision
  43's launch test hasn't resolved this yet, and a silent placeholder
  default risked getting used by accident before it does.
  `campaign_up.sh`/`campaign_down.sh` both now require
  `MOCKOPIN_SERVER_CLIENT_INSTANCE_TYPE` in the vars file.
- **Windows default to fixed UTC clock times, not a relative offset:**
  19:00 UTC (today, or tomorrow if 19:00 has already passed), 03:00 UTC
  the day after that, 11:00 UTC that same day -- registered into
  `campaign_schedule.json` exactly as before, still overridable via
  `MOCKOPIN_WINDOW{1,2,3}_START_UTC`.
- **New `--update-operator-ip` mode**: re-discovers the operator's IP
  and re-applies *only* `module.control.aws_security_group.this`
  (`terraform apply -target=...`) -- for when the operator's IP changes
  between sessions and a full re-apply of all 39 resources isn't needed
  or wanted.
- **Fixed a pre-existing gap while touching this file**:
  `campaign_down.sh` runs `terraform destroy`, which re-evaluates the
  whole configuration the same way `apply` does -- it needs the same
  variable values, not just the AWS profile. It previously exported
  none of them (`operator_ip_cidr`, `operator_ssh_public_key`,
  `server_client_instance_type`), which would have failed non-
  interactively the first time anyone actually ran it. Now exports all
  three (IP re-discovered fresh, same as `campaign_up.sh`).

**`campaign_down.sh`:** after the teardown is verified clean, **proposes
deleting the local Terraform state and cache**, behind an explicit typed
confirmation (`delete`) -- reasoned here, not just coded: once nothing
remains in AWS, the local state and the campaign's own SSH key material
(both already gitignored, never committed, Decision 49) no longer
protect anything real. The campaign's SSH private key itself isn't a
separate file to delete -- it only ever existed in Terraform state and
in the (now-destroyed) control instance's own `~/.ssh/campaign_key`;
deleting the state is what actually removes its only remaining copy.

**Limitation, registered explicitly (not just implied by Decision 41's
topology table):** the lowest-latency scenario's client (`L0`) reaches
its server over the server's **private** IP (co-located, same AZ ID,
Decision 28/33), while every other scenario's client reaches its server
over the server's **public** IP, the only path available cross-region.
This is a structural, not just magnitude, difference between `L0` and
every other scenario: no NAT, no public-internet routing, potentially
different MTU/offload behavior (Decision 42's GRO/GSO check is directly
relevant here too). **`L0`'s results should be read as a different kind
of network path, not simply "the lowest-latency sample" on a continuum
with the other five** -- this should be stated as an explicit limitation
wherever `L0` is compared against the rest, consistent with Decision
34's limitation note for the 14.7ms/33.2ms installations.

## 53. Eight scenarios (L0 per server), 720 executions, repository-mirroring data structure, region+machine control via the three L0s

**Context.** Every server now gets its own `L0` (co-located client, same
AZ ID, Decision 28/41's private-IP rule) in addition to its other
levels: `sa-east-1` -> L0, L123, L219, L325; `us-east-1` -> L0, L14;
`ap-northeast-1` -> L0, L30. 8 scenarios x 3 profiles x 30 runs = **720
executions**. 3 servers + 8 clients + 1 control = **12 instances**.

**Current state, checked directly before redesigning (not assumed):**
`campaign/`'s only existing data-path logic was `campaign_run.py`'s
`run_dir_for()`, writing run JSONs to an ad-hoc
`/home/ec2-user/campaign-data/{installation}/{scenario}/{profile}/
window{NN}/run{NN}.json`, plus window metadata under a nested
`_window_meta/` -- and `campaign_pull.sh` rsynced that whole tree into
`$DEST/data/`, a flat mirror that did **not** match any eventual repo
structure. Every other data type the thesis needs -- `calls.jsonl`, raw
gateway lines, CPU/steal/memory series, reference pings, pcap, warmup --
had **no defined location at all**: `run_one_execution()` was (and
remains) an unimplemented seam, so nothing had ever actually written
any of them.

**Structure adopted, mirrored identically on the control instance, in
`campaign-data-pulled/`, and in the repository itself** (Decision
53 -- `campaign_run.py`/`campaign_pull.sh` updated accordingly, see
their own diffs):

```
v8/latency/experiment{1,2,3} - {Classic,PQC,Hybrid}/{sa-east-1,us-east-1,ap-northeast-1}/{scenario}/
  runs/run{NN}.json            (window, server, client, instance type)
  runs/run{NN}.calls.jsonl     (per-call record, one file per execution)
  run00_warmup_window{NN}.json (separate per block, never mixed into runs/)
  server/run{NN}_gateway.log, run{NN}_cpu.jsonl, run{NN}.pcap.gz
  client/run{NN}_cpu.jsonl, run{NN}_ping.json, run{NN}.pcap.gz
  median_metrics.json, report.md   (local post-processing, not written on the control instance)

v8/latency/_campaign-control/
  schedule.json                       (the schedule this run actually used)
  windows/{server}/window{NN}.json    (seed, profile order, scenario rotation)
  orchestrator.log

v8/size/experiment{1,2,3} - {Classic,PQC,Hybrid}/{sa-east-1,us-east-1,ap-northeast-1}/
  median_metrics.json, report.md
```

`v8/artifacts/` and `latency-discovery/` are unchanged -- **nothing
moved out of either.**

**The hash manifest uses the same relative paths as the repository,
not a separate scheme.** `campaign_run.py` now writes under
`/home/ec2-user/campaign-data/v8/...` (the exact relative layout above);
`campaign_pull.sh` generates its sha256 manifest with `cd campaign-data
&& find v8 ...` (relative paths, e.g. `v8/latency/experiment1 -
Classic/sa-east-1/L0/runs/run01.json`) and rsyncs
`campaign-data/v8/` -> `$DEST/v8/` directly -- `$DEST` is now a literal
mirror of `thesis/results/v8/`, not a translated copy.

**Sizes: derived from every latency execution, not a separate batch.**
Supersedes Decision 34/41's "measured once, 10 runs/profile,
`sa-east-1` only." The byte fields every run already records (Decision
36) are pooled after the fact: `sa-east-1`'s number is **official**
(all 4 of its scenarios' executions pooled -- more samples, and
Decision's own v7 precedent already found 0% spread across profiles'
deterministic byte fields, so pooling across scenarios costs nothing).
`us-east-1`/`ap-northeast-1`'s `L0` data is a **complementary,
cross-machine verification** -- deliberately scoped to just `L0` (not
their other scenario too), keeping the 3-way comparison clean and
symmetric. **Any byte-count difference from `sa-east-1`'s official
number is a finding to explain, not assumed away** -- Decision 41
already flagged that cross-machine size identity was never tested; this
is where it actually gets tested, for the first time, with real data.

**Each `L0`'s RTT label comes from that server's own pcap + reference
ping -- never copied from another server's.** `sa-east-1`'s 0.2ms
(Decision 33) does **not** carry over to `us-east-1`/`ap-northeast-1`'s
`L0` -- each gets its own measured value once the real campaign pcap
exists (Decision 41's "pcap, not discovery ping" rule, applied
per-server now, not assumed identical across servers just because the
co-location mechanism is the same).

**The three `L0`s serve two purposes at once, not just "the lowest
scenario" three times over:** a **region control** (the region-control
*procedure* was discarded, Decision 39, but these three numbers, using
real campaign data instead of a dedicated experiment, let the same
question be asked for free) and a **same-machine-type control**
(confirms -- or doesn't -- that nominally identical instance
type/image behaves identically across 3 physically different hosts).

**Analysis for the 3-way `L0` comparison, fixed before any measurement
(same discipline as every other pre-registered criterion in this
project):** compare the three medians' pairwise differences against
**each one's own internal noise** (IQR or a bootstrap CI) --
**descriptive only, no hypothesis test**, consistent with this
project's standing analysis policy (Decision 47/55). **Nothing is
removed.** A divergence that exceeds a server's own internal noise is
**registered as a limitation**, not explained away or hidden.

**Pcap granularity: per execution by default.** One pcap per run
(client and server sides both), consistent with every other per-run
data type above -- **the author may decide per-block capture instead**
(one pcap covering all 10 runs in a window's block), trading
per-execution isolation for less storage/fewer files; not decided here,
flagged as the author's call.

## 54. Infrastructure for the three `L0`s: 12-instance Terraform, AZ-specific availability, EIP quota, re-estimated duration/cost

**Terraform (`campaign/terraform/`), prepared, not applied.** Two new
client modules, `client_l0_us_east_1` and `client_l0_ap_northeast_1`,
same `campaign_instance` module, same instance type and same image as
every other campaign instance (Decision 53's explicit requirement --
nothing special about these two beyond their subnet). Each co-located
with its server via a new AZ-ID-specific subnet lookup
(`use1-az1`/`apne1-az1`, confirmed live via `describe-availability-
zones`, same mechanism as `sa-east-1`'s `sae1-az1`, Decision 33).
`server_us_east_1`/`server_ap_northeast_1` moved onto these same
AZ-specific subnets (previously the generic default-VPC subnet, which
wasn't guaranteed to share an AZ with anything) and now carry **one more
gateway-ingress rule each**, for their own `L0` client's **private** IP
-- same rule as `sa-east-1`'s `L0`.

**Availability of the candidate instance types, checked in the exact
AZ IDs now used (not just "somewhere in the region," Decision 32's
coarser check):** `describe-instance-type-offerings` with
`location-type=availability-zone-id`, confirmed live --
`m7i-flex.large` and `c7i-flex.large` both available in `sae1-az1`,
`use1-az1`, and `apne1-az1`.

**Elastic IP quota, rechecked with the new 12-instance total:**
`describe-account-attributes` in all 7 regions still returns the
default limit of 5/region, 0 in use. Peak per-region need is now 3
(`sa-east-1`, `us-east-1`, and `ap-northeast-1` each host a server +
its own `L0` client, `us-east-1`/`ap-northeast-1` additionally host
one more scenario's client each -- still 3, not more, since each
region's extra client is a *different* region's worth of capacity, not
stacked onto these three). Comfortably inside the default, no quota
increase needed.

**`terraform plan`: 45 resources to add** (12 instances + 12 Elastic
IPs + 12 security groups + 7 campaign key pairs + 1 operator key pair +
1 generated SSH key), 0 to change, 0 to destroy, no errors. Not
applied.

**Orchestrator (`campaign_run.py`) additions:** every installation's
`L0` is in the scenario rotation now, not just `sa-east-1`'s 4-item
list -- `SCENARIO_ROTATION` is keyed per server. Noted explicitly, not
silently glossed over: `us-east-1`/`ap-northeast-1`'s 2-item scenario
lists only have 2 distinct orderings, so their "window 3: rotated"
repeats window 1's order -- a 3rd, genuinely distinct rotation isn't
possible for a 2-item list, unlike `sa-east-1`'s 4-item one.

**Duration/cost, redone for 720 executions / 12 instances, labeled
estimate, checked 2026-10-12, same v7 sources as Decision 47:**
- `sa-east-1` chain (unchanged, 4 scenarios): ~55min active + ~21min
  settling =~ **1.26h**, still the dominant serial path.
- `us-east-1` (now L0+L14): ~4min active + ~3min settling =~ **7min**.
- `ap-northeast-1` (now L0+L30): ~5.4min active + ~3.5min settling =~
  **9.5min**.
- These three run in parallel (independent installations) -- campaign
  wall-clock span is still **about 1-1.5 calendar days** (the fixed
  windows, Decision 52, span two calendar dates: 19:00 day D through
  ~12:15 day D+1).
- Cost: 12 instances up roughly that span (~24-30h each, generous): **~360
  instance-hours** at the same blended ~$0.10-0.15/hr -> **roughly
  $35-55** for this specific campaign run. Still an order of magnitude
  under the $200 Free Plan credit.

**Nota de correção (2026-10-27, piloto 3 real):** o "45 resources to
add" acima estava desatualizado. `terraform plan` real, full topology,
mostrou **65 to add, 0 to change, 0 to destroy** (confirmado ao vivo,
piloto 3). A diferença exata (20 recursos) são as regras
`aws_vpc_security_group_ingress_rule` (uma por cenário/gateway em cada
servidor + uma de SSH por módulo: 12 SSH + 8 gateway = 20) -- este
parágrafo, escrito em 2026-10-12, contou "12 security groups" como se
cada um fosse um recurso atômico com suas regras embutidas; o código
real desde então (ou já desde então, não verificado) modela cada regra
de ingress como seu próprio recurso Terraform. Nenhum `replace`/
`destroy` -- não é drift de configuração, é estimativa de contagem
nunca recalculada contra o código real. Contagem correta por tipo: 12
`aws_instance` + 12 `aws_eip` + 12 `aws_security_group` + 20
`aws_vpc_security_group_ingress_rule` + 8 `aws_key_pair` + 1
`tls_private_key` = 65. Revisadas as 20 regras uma a uma contra o
código-fonte (`main.tf`, não só o plano, já que vários valores de CIDR
aparecem como "known after apply"): nenhuma usa `0.0.0.0/0`/`::/0`;
`var.operator_ip_cidr` aparece em exatamente um lugar (SSH do módulo
`control`); todo outro módulo usa exclusivamente o IP público do
`control` para SSH; cada servidor só abre a porta 443 para os cenários
daquele próprio servidor, com o L0 colocalizado usando IP privado nos
3 casos. As 45 instance-hours/custo estimados abaixo continuam válidos
(a contagem de INSTÂNCIAS, que domina o custo, não mudou -- só a
contagem de regras de firewall, que não tem custo próprio).

## 55. Remote mode and delivery: image-ID comparison, real image-size/transfer/cost estimates, disk sizing confirmed, Docker-dependency audit, `REMOTE_GATEWAY_HOST` validation, pilot acceptance criterion, safety-timer margin confirmed

**Image comparison: loaded image ID, not a registry digest** (Decision
50's step 6 already specified this -- restated here because there IS no
registry digest in a local-tarball-load design; `docker image inspect
--format='{{.Id}}'` after `docker load` on each of the 3 servers is the
actual comparison). **`--platform linux/amd64` pinned on build/save/
load** -- prevents an accidental ARM-architecture image if ever built
on an ARM host (e.g. Apple Silicon), which would otherwise produce a
different, incompatible image silently.

**Real image sizes, measured directly (not assumed), checked
2026-10-12:** custom-built images needing this project's own tarball
delivery -- `mtls` (gateway) 1.51GB, `auth` 542MB, `mockapi`
(`raidiam-insurance-lambdas`) 607MB, `mongo_seed` 1.3GB -- **~3.96GB per
server**. The 3 **stock** images (`postgres:16` 642MB,
`localstack:4.0` 1.83GB, `mongo:latest` 1.3GB) are **not** part of this
delivery problem at all -- they pull directly from their own public
registries on each server, same as any other deployment, no custom
tarball needed.

**Transfer time -- labeled estimate, bottleneck identified:** ~3-4GB
compressed per server. The bottleneck is almost certainly the
**operator's own upload** to the control instance (step 4 of Decision
50's mechanism) -- AWS-internal legs (control -> each server) are far
faster. Assuming a typical home/office uplink (20-50Mbps): roughly
**10-25 minutes** for that one upload (done once, not per server);
control -> servers redistribution at AWS-internal speed is on the order
of a few minutes per server, in parallel. **Total estimate: roughly
25-40 minutes**, one-time, before the campaign starts.

**Inter-region transfer cost -- labeled estimate, checked 2026-10-12**
(secondary-sourced: AWS's own live pricing pages are JS-rendered,
same limitation noted in Decisions 32/44): inter-region transfer is
commonly cited around **$0.02/GB** for most region pairs (`sa-east-1`'s
specific pairs with `us-east-1`/`ap-northeast-1` aren't one of the
known pricier outliers). 2 inter-region legs (`sa-east-1` -> `us-east-1`,
`sa-east-1` -> `ap-northeast-1`) x ~3.5GB x $0.02/GB =~ **$0.14 total** --
negligible, not a material line item next to the compute estimate above.

**Disk sizing: 30GB confirmed sufficient, with real numbers behind the
claim, not just assumed.** Server footprint: ~3.96GB (custom) + ~3.77GB
(stock) =~ **7.73GB of images**, plus container runtime overhead and
this server's own share of pcap/logs/CPU data (small, KB-to-low-MB
scale per Decision 37/42's own pcap estimate) -- comfortably under 30GB
even with generous overhead margin. Client footprint is far smaller:
`golang:1.27-rc-alpine` (381MB) + the PQC signer image (240MB) =~
**621MB**, plus one scenario's own small data share. **No larger size
proposed -- 30GB stays.**

**Docker-dependency audit, all 5 scripts, every dependency point
classified (run on server via SSH from control / run on client via SSH
from control / dispense):**

| Script | Dependency | Decision |
|---|---|---|
| `opin_flow.py` | `set_latency()` (`docker exec`/`tc`) | **Dispensed** -- already skipped when `REMOTE_GATEWAY_HOST` is set (Decision 51) |
| `opin_flow.py` | `_run_pqc_signer()` (`docker run --rm -i`) | **Client** -- runs wherever `opin_flow.py` itself runs |
| `opin_flow.py` | `start_tls_kem_proxy()`/`stop_tls_kem_proxy()` | **Client** -- same reasoning, it's the proxy opin_flow.py talks to locally |
| `opin_flow.py` | `start_pqc_signer_service()`/`stop_pqc_signer_service()` | **Client** -- persistent signer, same process |
| `baseline_automation.py` | `collect_gateway_metrics()` (`docker logs` on the gateway container) | **Server, via SSH from control** -- the gateway container lives on the server; a client can't reach it directly (Decision 49's SSH-only-from-control rule blocks a client->server SSH entirely) |
| `median_automation.py` | (inherits `collect_gateway_metrics()`'s error handling, no independent dependency) | **Server**, same as above |
| `switch_crypto_profile.py` | `docker compose --profile main ...` (up/down/restart the whole stack) | **Server, via SSH from control** -- manages the server's own stack |
| `switch_crypto_profile.py` | `docker inspect`/`docker start` (container-state checks) | **Server** |
| `switch_crypto_profile.py` | `docker exec ... psql` (Postgres health check) | **Server** |
| `switch_crypto_profile.py` | `docker logs insurance-server-lambdas-mtls-1` (post-recreate readiness poll) | **Server** |

**Architectural finding, not previously registered:** this means the
orchestrator needs **two** SSH relationships per block, not one --
control -> client (triggering `opin_flow.py` executions, same as
already assumed) **and** control -> server (profile switches, gateway
metrics, server-side CPU/steal/pcap). Decision 49's security design
already supports this without any change -- every non-control instance
accepts SSH from control's EIP only, which covers both relationships
identically; this is a clarified **orchestration** design, not an
infrastructure change. **Nothing beyond `set_latency()` itself turned
out to be dispensable** -- every other dependency has a real need in
the remote campaign, just relocated to the correct side.

**`run_one_execution()`, specified again (not implemented):** must call
the lab's own existing functions for T_fluxo -- `time.monotonic()`,
discarded-retry-attempt time excluded from the timed window, a
whole-execution retry marked and recorded (not silently retried),
warmup kept separate (`run_warmup()`) -- i.e. invoke
`latency_automation.py`'s/`opin_flow.py`'s existing, already-correct
machinery (Decision 26) over SSH with `REMOTE_GATEWAY_HOST` set, not
reimplement T_fluxo measurement from scratch. `campaign_run.py`'s own
docstring now states this explicitly.

**`REMOTE_GATEWAY_HOST` validation, implemented (diff, not committed):**
rejects any value containing `"://"` or `":"` (scheme or port -- both
are appended automatically wherever the value is used) with an explicit
`SystemExit` message, and otherwise requires it to parse as a valid IP
(`ipaddress.ip_address()`) or a syntactically valid hostname. Tested
live: a bare host and a bare IP are both accepted unchanged; `
https://54.1.2.3:443` is rejected with the explicit message; unset stays
`None`, no validation triggered, zero behavior change.

**Pilot acceptance criterion, registered (Decision 46's pilot is where
this gets checked):** the ClientHello captured during the pilot must
have **the same size and the same SNI** as the local lab's own
ClientHello for the matching profile. This is the real, concrete
pass/fail check Decision 51's "not independently verified" caveat was
waiting on.

**Safety-timer margin, confirmed against the actual fixed windows
(Decision 52's 19:00/03:00/11:00 UTC defaults):** gaps between
consecutive renewals (at startup, and again right before each window,
`campaign_run.py`'s `renew_safety_timers()`) are at most ~24h (the
startup-to-window-1 wait, worst case) and ~8h between the 3 windows
themselves -- comfortably inside the 48h deadline every renewal sets,
with at least 2x margin in the worst case. Confirmed arithmetically
against the real schedule, not just assumed adequate.

**Plan ordering, updated:** the flex launch test (Decision 43) comes
**before** `deliver_images.sh` (Decision 50) -- no point building image
delivery for an instance type that might fail the launch test. This
item (the 12-instance Terraform, Decision 54) comes **before** the
pilot (Decision 46) -- the pilot needs the real topology, including
both extra `L0` clients, already standing.

**Updated sequence to the first real execution, author's dependencies
marked:**
1. Flex launch test (Decision 43) -- **author present**.
2. 12-instance Terraform apply (Decision 54) -- **author present**,
   budget/credit confirmation (Decision 52).
3. Build `deliver_images.sh` (Decision 50) -- not yet built.
4. Author reviews/approves the `REMOTE_GATEWAY_HOST`/SNI/validation diff
   (Decisions 51/53) -- then commit.
5. Pilot (Decision 46) -- **author present** for its own apply (or
   reuses the standing topology from step 2, if still up) -- validates
   `L0`'s public-IP RTT, the ClientHello size/SNI acceptance criterion
   above, tcpdump overhead, written tc/netem confirmation.
6. Implement `run_one_execution()`/`run_warmup()` for real, using the
   approved `REMOTE_GATEWAY_HOST` path and the Docker-dependency audit's
   server/client split above.
7. First real campaign execution (window 1).

## 56. Round-robin execution within each profile block -- supersedes Decision 40's scenario-by-scenario ordering

**Decision.** Within a profile block, executions alternate across that
server's scenarios one run-index at a time -- run 1 of every scenario in
the block, then run 2 of every scenario, and so on -- instead of
finishing all of one scenario's runs before starting the next.
Implemented in `campaign_run.py`'s `run_window()` (round-robin is now
the outer-loop-is-run-index, inner-loop-is-scenario structure).

**Why:** spreads any time-dependent drift within a block (network
weather, however small, over the block's own span) evenly across every
scenario in it, rather than letting one scenario systematically land in
the block's "early" minutes and another in its "late" minutes, every
single window -- a confound round-robin removes by construction that
scenario-by-scenario ordering could not.

**Each client's proxy stays active for the whole block, not just its
own scenario's turn.** New seams, same "specified, not implemented"
treatment as `run_one_execution()`: `start_block_proxies()` (called once
per block, before round-robin begins) and `stop_block_proxies()` (called
once, in a `finally`, after the block's round-robin loop ends or is
abandoned). Warmup is unaffected in count -- still once per scenario per
block -- just moved earlier, before round-robin starts rather than
interleaved into it.

**Effect on total time: none.** Same number of runs, same number of
profile switches (9/window, Decision 40/54's math unaffected), same
per-run durations -- only the execution ORDER changes. **Effect on
orchestrator complexity: real.** Every scenario's proxy in a block must
now be tracked and health-checked concurrently for the block's whole
duration, instead of one at a time; the run loop itself inverts
(scenario becomes the inner loop). This is a genuine increase in how
much live state the orchestrator holds per block, registered here so
it's not discovered as a surprise during implementation.

## 57. Pcap: one file per execution, bundled per scenario+window for commit, volume re-estimated for 720 executions x 2 sides

**One pcap per execution, both sides** -- unchanged (Decision 42).

**For the commit, bundled per (scenario, window, side) into one file,
preserving one member per execution inside it.** `package_pcaps.sh`
(written, tested against synthetic data, not yet run against real
campaign data) tars `server/run01..10.pcap.gz` into
`server/window01.pcaps.tar` (and the same for `client/`) -- plain `tar`,
deliberately **not** `tar.gz`: each member is already gzip-compressed
(Decision 42), so an extra gzip layer over already-compressed data buys
negligible size reduction for real CPU cost. Originals are removed only
after the bundle is verified readable (`tar -tf`), never before.

**Volume, re-estimated for 720 executions x 2 sides (1,440 pcap files),
labeled estimate, checked 2026-10-12, same reasoning as Decision 37/42:**
at the same per-execution range (~15-100KB compressed, PQC/Hybrid's
larger certificate chains pushing toward the high end) -- **roughly
22-145MB compressed for the whole campaign**, both sides. Wider than
Decision 37's original 540-execution/one-topology figure simply because
the execution count grew (540 -> 720) and this estimate now explicitly
counts both sides instead of being ambiguous about it.

**Git LFS vs. external storage: still deferred to after the pilot**
(unchanged from Decision 37/42) -- the pilot is where a real number
replaces this estimate, and that real number is what should actually
decide between the two, not a projection.

**UPDATED 2026-10-22 (see this file's own later entry) -- snaplen raised
128 -> 256, estimate scaled by the real, measured ratio.** Decision 42's
snaplen is now 256 (`TCPDUMP_SNAPLEN_BYTES`, `campaign_run.py`), not 128
-- a real local capture measured the actual size increase directly
(44,774 -> 66,098 bytes for one connection's own capture, +47.6%), not a
re-derivation from the same "80 bytes/packet" reasoning Decision 37/42
used. Applying that same real ratio to this decision's own 22-145MB
range gives **roughly 32-214MB compressed for the whole campaign, both
sides** -- still "a few dozen to a couple hundred MB" territory, same
conclusion as before (Git LFS is comfortably sufficient; still deferred
to a real pilot number before deciding between LFS and external
storage, unchanged).

## 58. Size reports: reproducible script, derived only, variation across executions and latency levels, retries handled separately

**`compute_v8_size_report.py`, written and tested against synthetic
data (not yet run against real campaign data, since none exists yet).**
Reads every `runN.json` under `v8/latency/` for a given profile,
pools `sa-east-1`'s 4 scenarios for the **official** report, and builds
one **complementary** report each for `us-east-1`/`ap-northeast-1` from
their own `L0` runs only (Decision 53's scoping, restated). **`v8/size/`
is always derived this way -- never hand-edited** -- re-running the
script after any pull recomputes it fresh from whatever runs exist so
far, including a partial campaign.

**Retried executions:** a run JSON with `"retried": true` is excluded
from the primary (clean) statistics and listed separately, flagged --
never silently pooled in with clean runs, never discarded outright.
Tested live with synthetic data: 5 clean + 1 retried run pooled
correctly, the retried one correctly excluded from every stat and named
explicitly in the report.

**Variation reported, both axes required by the author's brief:**
across executions (min/max/stdev within one scenario, pooled across all
of `sa-east-1`'s scenarios too) and across latency levels (median per
scenario, so a `sa-east-1` run can be compared scenario-by-scenario,
not just pooled blind). The report states explicitly that sizes are
*expected* to be latency-independent (v7 Decisions 10-12's 0%-spread
finding) and that any scenario whose median departs from the others by
more than ordinary noise is a finding to investigate, not something the
script resolves on its own.

## 59. `deliver_images.sh` written, not executed

**Written, not run -- no apply, no instance launch.** Implements
Decision 50/55's mechanism concretely: builds/verifies each of the 4
custom images (`mtls`, `auth`, `mockapi`, `mongo_seed` -- the 3 stock
images are explicitly excluded, Decision 55) are `linux/amd64`
(`docker image inspect --format='{{.Os}}/{{.Architecture}}'`, fails
loudly if not); `docker save | gzip`; checks the control instance's
free disk space before sending (fails loudly if insufficient, before
transferring anything); sends via `rsync --partial` when available on
the control instance (resumable by construction), falling back to
100MB split parts with a per-part sha256 (resumable by re-checking which
parts already verify) when `rsync` isn't available; verifies sha256 on
arrival; distributes from control to each of the 3 servers over the
campaign key; `docker load`s on each server; **compares the loaded
image's own ID** (`docker image inspect --format='{{.Id}}'`) across all
3 servers, failing loudly if they differ; **removes the tarball from
the control instance** once distribution succeeds. Not yet run against
real infrastructure.

**Instance type:** `server_client_instance_type` stays without a
default (Decision 52, unchanged) -- still waiting on Decision 43's
launch test, not decided here.

## 60. `run_one_execution()` implemented via an Executor abstraction; regression-tested live against the local stack, all 3 profiles; overlap guard added and tested

**Two pre-existing gaps found by direct inspection before writing any
code (not assumed):**
1. `opin_flow.py`'s own `main()` CLI path already had
   `REMOTE_GATEWAY_HOST` support (Decision 51), but the campaign's
   actual N-run/retry/warmup driver, `latency_automation.py`, calls
   `of.set_latency()` **directly** -- bypassing `opin_flow.py`'s CLI
   entirely, and Decision 51's fix never touched it. Fixed with the
   identical guard (skip `set_latency()` when `REMOTE_GATEWAY_HOST` is
   set), now in both places.
2. `run_once_timed()` computed `call_count` from the flow's raw `calls`
   list, then discarded the list -- there was no way to get the
   per-call records `calls.jsonl` (Decision 36/42) needs. Fixed
   additively: a new `return_calls: bool = False` parameter, threaded
   through `run_once_timed_with_retry()` too. Default `False` keeps
   every existing call site (including `latency_automation.py`'s own
   `main()`) byte-for-byte unaffected; the new code opts in explicitly.

**Architecture: an Executor abstraction, not a single hardcoded path.**
`LocalExecutor` (real, implemented) runs everything in-process --
"server" and "client" both the local machine, exactly like
`switch_crypto_profile.py` already assumes -- calling
`latency_automation.py`'s `run_once_timed_with_retry()` directly, never
reimplementing T_fluxo/retry/warmup logic. `SSHExecutor` (real AWS) is
deliberately left as an unimplemented interface -- Decision 55's
Docker-dependency audit already specifies which side each command
belongs on; wiring real SSH calls now, untested against real
infrastructure, would not be "prepared," it would be fabricated.

**New file, `thesis/scripts/campaign_client_runner.py`:** the thin CLI
an `SSHExecutor` would eventually invoke on a real client instance --
calls `run_once_timed_with_retry(..., return_calls=True)` and prints one
JSON object. Not itself exercised by the local test (`LocalExecutor`
calls the same underlying function in-process instead, which is the
more direct way to validate the function itself without also needing a
subprocess/CLI layer working) -- registered as written, not validated
end-to-end as a subprocess.

**Every artifact Decision 53's tree specifies, written per execution:**
`runs/run{NN}.json`, `runs/run{NN}.calls.jsonl`, `server/run{NN}_gateway.log`
(raw `docker logs --since/--until`, the container's own log text, not
re-parsed), `server/run{NN}_cpu.jsonl` (`docker stats --no-stream`,
before/after), `client/run{NN}_cpu.jsonl`, `client/run{NN}_ping.json`,
and `server/`+`client/run{NN}.pcap.gz` (gzip, matching Decision
42/57's per-execution default). `run_warmup()` writes
`run00_warmup_window{NN}.json` once per scenario per block, reusing
`latency_automation.py`'s own single-warmup-run convention -- **not**
Decision 4's separate 5-flow container-settling (a different,
server-side, profile-switch-time concern this orchestrator doesn't
build yet; flagged explicitly in the code so the two are never
conflated with each other).

**`calls.jsonl`'s fields, honestly scoped to what `do_call()` already
produces** (endpoint, request/response/total bytes, per-call latency,
status, participant) -- Decision 42 originally also wanted an explicit
per-call connection identifier and a per-call retry flag; neither exists
in the lab's current call-dict today, and adding them would mean
touching `do_call()` itself, which "sem reescrevê-las" rules out for
this pass. Registered as a known, honest gap, not fabricated.

**Overlap guard:** one `threading.Lock()` per installation
(`_SERVER_LOCKS`), acquired non-blocking at the start of
`LocalExecutor.run_one_execution()` -- a second concurrent call for the
same server raises `RuntimeError` immediately rather than silently
queuing or corrupting shared state. Today's control flow is fully
sequential (no threading anywhere in `main()`/`run_window()`), so this
is defense-in-depth against a future change (e.g. running
installations' windows concurrently) reintroducing an overlap, not a
fix for an overlap that was actually observed. **Tested directly**: two
threads, one holding the lock for 1.5s, the other attempting
`run_one_execution()` 0.3s later on the same installation -- the second
correctly raised `RuntimeError` every run.

**Regression test -- run live against the real local stack (no AWS),
all 3 profiles, `REMOTE_GATEWAY_HOST=host.docker.internal`** (deliberately
not the lab's own `"mtls"` alias -- `host.docker.internal` is Docker
Desktop's real cross-container-to-host route, the closest thing to "a
genuinely different network path" achievable without actual AWS
infrastructure). For each profile: `start_block_proxies()`, one warmup,
two real executions via `run_one_execution()`, `stop_block_proxies()`.

| Profile | T_fluxo (2 runs) | calls.jsonl byte sum | Matches local-lab baseline (REMOTE_GATEWAY_HOST unset)? |
|---|---|---|---|
| classic | 3.00s, 3.17s | 125,485 (both runs) | yes -- exact match |
| pqc | 2.91s, 2.90s | 275,800 | yes -- exact match |
| hybrid | 3.31s, 4.08s | 331,639 (both runs) | yes -- exact match |

Every profile's byte total is **exactly** identical to the local-lab
baseline captured the same session (plain `opin_flow.py 0`,
`REMOTE_GATEWAY_HOST` unset) -- confirms Decision 51's SNI/target fix
holds under `run_one_execution()`'s new code path too, not just
`opin_flow.py`'s bare CLI. `call_count`, `calls.jsonl`'s line count, and
the summed bytes all agreed internally (42/42, etc.) in every run.

**Tree and manifest, confirmed structurally** (via the test's own file
listing, Decision 53's spec): `runs/run{NN}.json`,
`runs/run{NN}.calls.jsonl`, `run00_warmup_window{NN}.json`,
`server/{_gateway.log,_cpu.jsonl}`, `client/{_cpu.jsonl,_ping.json}` all
present, named, and nested exactly as specified -- `campaign_pull.sh`'s
manifest generation (unchanged, Decision 53) needs no adjustment since
the paths it already walks are these same ones.

**pcap: best-effort, not exercised.** `tcpdump` isn't available in this
project's own Windows+Docker-Desktop dev environment -- the capture
code runs, detects its absence, and skips with a clear message rather
than failing the whole execution. Pcap capture itself is therefore
**written but not validated live** this session; it would need a real
Linux client/server (the pilot, Decision 46, or a real EC2 instance) to
actually exercise.

**Five-rename/doc-reference/lock-file checks, all confirmed clean,
checked directly:**
- All 5 raw-data folder renames show as `rename ... (N%)` in `git show
  --stat` on the commit that made them (confirmed: `0e10332`).
- No document references the 5 old folder names except Decision 48's
  own rename-mapping table (`old name -> new name`), which is supposed
  to name the old ones -- not a stale pointer, the record of the rename
  itself. No other match anywhere in `thesis/results/v8/`.
- `.terraform.lock.hcl` is tracked in all 6 Terraform roots in this
  project (`latency-discovery/terraform`, `terraform-candidates`,
  `terraform-bue-lz-test`, `terraform-sa-az-test`,
  `terraform-flex-launch-test`, `campaign/terraform`) -- confirmed via
  `git ls-files --error-unmatch` on each, individually. **No separate
  commit needed.**

**Retry-exclusion scope, confirmed, not just assumed:**
`compute_v8_size_report.py` (Decision 58) excludes `"retried": true`
runs from its own SIZE statistics only. `latency_automation.py`'s own
`summarize()` (unchanged, reused as-is by every T_fluxo report) performs
**no outlier removal of any kind** -- every run, retried or not, stays
in every T_fluxo statistic, exactly as its own long-standing docstring
already states. The two statistics genuinely use different inclusion
rules, confirmed by reading both functions, not inferred.

**Diff shown in the chat response below. Not committed, not applied --
the local stack this test used was brought up and torn down within this
session (it was not running before), and the scratch test files/
directories it wrote were removed afterward, not left behind.**

## 61. `calls.jsonl` extended: per-call UTC start/end and a connection-pool label, additive; cost measured

**Decision.** `do_call()` (`opin_flow.py`) now also records, per call:
`start_utc`/`end_utc` (real UTC timestamps, for correlating a call
against the gateway's own log timestamps and pcap packet times later)
and `pool_label` (`f"session-{id(session):x}"` -- identifies which
`requests.Session`/connection pool made the call; a stable grouping
key, confirming connection reuse the way `do_call()`'s own docstring
already describes -- **not** a per-call retry flag, which the author
explicitly excluded this round). Additive: every existing field is
unchanged, nothing removed.

**A second call-construction site found and fixed, not just the obvious
one.** `simulate_login()`'s redirect-hop response hook
(`_capture_hop`, builds `login_calls` entries) does **not** go through
`do_call()` at all -- found live, the hard way: the first regression
run crashed with `KeyError: 'pool_label'` on exactly these entries
(indices 8-14, 25-31 in a 42-call run -- the login/interaction/JARM
hops). Fixed the same way: `pool_label` is exact there too (same
session object); `start_utc`/`end_utc` are both stamped at the single
moment the hook fires, same honesty as the pre-existing `latency_ms:
0.0` comment on that same object ("not independently timed, folded
into the top-level call's own latency") -- not a real start/end pair,
registered as such, not quietly presented as one.

**Cost measured, not assumed negligible:** a microbenchmark of the
exact three-line sequence (two `datetime.now(timezone.utc).isoformat()`
calls + one `id()` call) over 100,000 iterations: **~2.97us/call**,
checked 2026-10-13. Against a typical 42-call run's multi-second
T_fluxo, that is **~0.004%** of the measured time -- not a candidate
confound for anything this project measures.

**Regression, run live, all 3 profiles, after the fix:** every
`calls.jsonl` line (all 42/run, both the `do_call()`-sourced and the
hook-sourced ones) now carries all three new fields; `total_bytes`
summed from `calls.jsonl` still matches each profile's local-lab
baseline exactly (classic 125,485; pqc 275,800; hybrid 331,639) --
confirms the new fields are genuinely additive, not just in principle.

## 62. Settling sequence implemented (local part) and tested; negotiated-group check corrected after a real false positive

**Decision -- the full per-block sequence, as specified:** (a) switch
profile on the server, (b) restart the client proxy/signer with the
profile's own curve, (c) check the negotiated group in the gateway's
log, (d) 5 settling executions -- saved separately, each verified,
never silently discarded -- (e) per-scenario warmup, (f) round-robin.
(e)/(f) were already wired (Decisions 53/56); this decision implements
(a)-(d) in `LocalExecutor.start_block_proxies()`.

**(a)/(b): reuses `switch_crypto_profile.py`'s own private helpers
directly** (`_compose`, `_start_if_exited`, `_container_status`,
`_wait_for_mtls_ready`, `_check_psql_checkpoint_health`) -- the exact
same container-recreate/health-check sequence that script already
uses, not a reimplementation. `switch_crypto_profile.py`'s own
`switch()` function is not called wholesale (it runs its own,
discarded, 5-flow settling internally, which would have meant 10
flows total, not 5, if layered under this decision's own 5 saved
ones) -- its constituent pieces are composed directly instead.

**A fourth `set_latency()` gap found and fixed while here, not just
the three already known.** `switch_crypto_profile.py`'s `switch()`
function *also* calls `of.set_latency(0)` unconditionally (line 232) --
a fourth call site Decision 51's original fix never touched (the first
three were `opin_flow.py`'s CLI, `latency_automation.py`'s driver, and
now this one). Not actually reachable from this decision's own code
path (which calls `switch_crypto_profile.py`'s *private helpers*
directly, never its `switch()` function) -- but a real latent
inconsistency if anyone ever runs `switch_crypto_profile.py` standalone
with `REMOTE_GATEWAY_HOST` set. Fixed with the identical guard, for
consistency with the other three.

**(c)/(d): 5 settling runs, saved and verified, not discarded.** Each
saved to `_campaign-control/windows/{installation}/settling_{profile}_run{N}.json`,
"verified" meaning completed without exception and `call_count > 0`
(a run that silently did nothing would not pass). Clock drift (gateway
container's own clock vs. this process's) measured once per block via
`docker exec ... date -u`, saved alongside.

**The negotiated-group check -- corrected after a REAL false positive,
not a theoretical one.** First version: grep the gateway's "mTLS
handshake complete" log lines for `curveID`, require all 5 settling
runs to show the SAME value, abort otherwise. **Running this live for
`classic` aborted immediately** with
`{'CurveP256', 'CurveP384'}` seen as "inconsistent." Investigated
before accepting the abort as correct: re-read Decision 15 (v7) and
confirmed this project's own architecture has TWO coexisting TLS
channels per flow -- the client-facing one (profile-specific: P384 for
classic's `secp384r1`) and the AS->RS internal channel, which is
**always classical regardless of `CRYPTO_PROFILE`** (the
`matls-api.local` SNI carve-out) and free to pick any of its own
`[P521, P384, P256]` list. The gateway's handshake-complete log line
does not carry SNI, so this check cannot currently tell the two
channels apart. **Changed from a hard abort to a WARNING**, with the
real explanation printed, not a raised threshold or a silently
loosened check. Confirmed consistent with the architecture across all
3 profiles, live: classic `{CurveP384, CurveP256}`, pqc
`{MLKEM1024, CurveP256}`, hybrid `{SecP384r1MLKEM1024, CurveP256}` --
the client-facing value is always the profile-correct one; `CurveP256`
(or another classical curve) from the internal channel is the
constant across all three. **Correctly separating the two channels**
would need correlating `curveID` against the OTHER log line (which
does carry SNI, Decision 15) by `remoteAddr` -- not built this session,
registered as a known gap, not silently worked around.

**Regression, all 3 profiles, run live:** settling (5 runs each) +
2 real executions each, byte totals still match baseline exactly
(same table as Decision 60, re-confirmed after this session's `do_call()`
fix). Local stack brought up/down within this session, not left
running.

## 63. tcpdump: aborts the block loudly by default; explicit local flag required to skip; liveness/growth/dropped-packet checks

**Decision -- default behavior changed from Decision 60's best-effort
skip.** `_try_tcpdump()` now: uses an **explicit interface** parameter
(never `"any"`), the existing port-443 filter, and **aborts the block
with `RuntimeError`** if tcpdump isn't installed, exits immediately
after starting, or starts but the output file never grows after a
short grace period -- each of these three failure modes checked
directly, not assumed from "the process is still running." **The old
skip-with-warning behavior now requires `allow_tcpdump_skip=True`,
passed explicitly** -- never the default, never silent -- and the
skip, when it happens, is recorded in the run's own JSON
(`"tcpdump_skipped": {"server": bool, "client": bool}`), not just
printed to a log a reader might not see. On successful capture,
`tcpdump`'s own stderr summary line ("N packets dropped by kernel") is
parsed and saved as `dropped_packets` per side.

**Tested, both branches, live:**
- Without the flag: `_try_tcpdump()` raises `RuntimeError` immediately
  on this environment's missing `tcpdump` -- confirmed.
- With `allow_tcpdump_skip=True` (the local test's explicit choice,
  not a default): skips with the warning, records
  `tcpdump_skipped: {"server": true, "client": true}` in every run's
  result -- confirmed.
- **Not tested: the actual capture, liveness, and growth-check paths**
  -- `tcpdump` genuinely isn't available on this project's own
  Windows+Docker-Desktop dev machine, registered as a real gap, not
  glossed over. Needs a real Linux target (the pilot, or a throwaway
  EC2/container) to exercise.

## 64. Server-side `flock` + single-orchestrator instance lock, both implemented; real Linux test via Docker (not simulated)

**`SingleInstanceLock`** (`fcntl.flock` on `/tmp/mockopin-campaign-run.lock`):
wraps `main()`'s entire run -- a second `campaign_run.py` process
fails loudly on startup if another one already holds the lock. No-op
with a clear warning on a non-Linux host (this project's own Windows
dev machine has no `fcntl` at all) -- registered as a platform
limitation, not hidden.

**`server_flock_wrap()`**: wraps the remote profile-switch command in
`flock -n /tmp/mockopin-server.lock -c '...'` -- a real shell binary
(`util-linux`, present on Amazon Linux 2023 by default), not a Python
mechanism, so it protects the server regardless of which SSH
invocation ends up running the wrapped command (relevant for
`SSHExecutor`, where each execution is its own separate SSH call, not
one long-lived process that could hold an in-memory lock the way
`LocalExecutor`'s `_SERVER_LOCKS` threading.Lock does).

**Tested against REAL Linux `flock` semantics, via Docker (this
project's dev machine is Windows, which has no `fcntl` to test
directly)** -- two processes inside a `python:3.12-alpine` container,
one holding the lock for 3s, the other attempting it 0.5s later:
correctly blocked with `OSError: [Errno 11] Resource temporarily
unavailable` (`EWOULDBLOCK`, exactly what `SingleInstanceLock`/
`server_flock_wrap`'s own `LOCK_NB` + `except OSError` is built to
catch), holder released cleanly after. This validates the real
mechanism's semantics directly, not a simulation of them.

## 65. `campaign_client_runner.py` validated as a real subprocess -- 5 checks, one assumption corrected

**Tested as an actual subprocess (`subprocess.run`/`Popen`), not an
in-process import** (the earlier regression used the latter, which
validates the underlying function but not the CLI/process boundary
itself):

| Check | Result |
|---|---|
| `REMOTE_GATEWAY_HOST` unset | exits nonzero, clear message on stderr -- PASS |
| Missing required `--label` | argparse exits nonzero (code 2) -- PASS |
| Working directory | **assumption corrected, not a failure** (below) |
| Timeout (`subprocess.TimeoutExpired`) | raised correctly, process killed, no hang -- PASS |
| `SIGTERM` mid-run | process exits, stdout never contains a half-written JSON object -- PASS |

**Working-directory assumption corrected, not confirmed as originally
expected.** The test assumed a wrong `cwd` would break `import
latency_automation` with `ModuleNotFoundError`. It didn't: Python
always adds the **running script's own directory** to `sys.path[0]`,
regardless of the process's `cwd` -- confirmed directly, not assumed,
by observing the real failure mode with a deliberately wrong `cwd`
(the script DID start and import correctly; it failed later, on a
plain connection-refused to a gateway that wasn't running, the same
reason every other test without a live stack would fail). **This
means `campaign_client_runner.py` does not actually depend on being
invoked from `thesis/scripts/` as its `cwd`** -- a more robust finding
than assumed going in, not a bug.

**Platform caveat, stated plainly:** `Popen.terminate()` on Windows
calls `TerminateProcess`, not a real `SIGTERM` the target could trap or
handle differently -- this test exercises "the process gets killed
mid-run and prints nothing corrupt," not POSIX `SIGTERM` semantics
specifically. A real signal-handling test needs a Linux target.

## 66. `tls_kem_proxy` as a precompiled binary -- Dockerfile written, not wired into the live path

**`thesis/scripts/tls_kem_proxy/Dockerfile`, multi-stage, written this
turn.** Builder stage: pinned `golang:1.27-rc-alpine` (same digest
`opin_flow.py` already pins), `CGO_ENABLED=0 go build -trimpath` --
`go.mod` declares zero external `require`s (confirmed by reading it,
not assumed), so there is nothing to download even in today's `go run`
path; the multi-stage split still matters because it guarantees the
*runtime* image never contains the Go toolchain or source, only the
compiled binary, no module resolution possible at container start
regardless. Runtime stage: `alpine:3.20`, non-root user, `ENTRYPOINT`
is the binary directly.

**Not wired into `opin_flow.py`'s live `start_tls_kem_proxy()` this
session** -- that still runs `go run .` exactly as today's lab does;
changing it would affect every existing local-lab invocation, a larger
change than this decision's scope. This Dockerfile is what Decision
50/59's `deliver_images.sh` would eventually build and deliver, once
that wiring is made -- registered as the next, separate piece of work,
not done here.

## Item 10 -- lab regression, `latency_automation.py` itself, `REMOTE_GATEWAY_HOST` unset

Run live (not simulated): `CRYPTO_PROFILE=classic python
latency_automation.py 0 --runs 2` with `REMOTE_GATEWAY_HOST` unset --
`"Latency reset on insurance-server-lambdas-mtls-1 (eth0)."` printed
(confirms the `else` branch of Decision 60's guard runs normally,
`set_latency()` unaffected when the var is unset), warmup + 2 runs
completed normally (T_fluxo 2.84-2.92s, consistent with this session's
other classic/0ms measurements), `median_metrics.json`/`report.md`
written in the expected shape. A direct, final `opin_flow.py 0`
cross-check immediately after confirmed `total_bytes_exchanged =
125,485` once more -- unchanged by every edit made this session
(`do_call()`'s new fields, `switch_crypto_profile.py`'s fourth-gap fix,
`latency_automation.py`'s own guard). Ad-hoc result files this check
wrote were reverted (`git restore`) afterward, not left as spurious
diffs; the throwaway `v3/latency/` folder this test needed was removed.

## 67. `campaign_run.py` corrections (window overwrite, block order, SSH quoting, real-mode exit, remote-data coverage, service lifecycle, interface detection, clock drift, periodic sampling), local rehearsal, correlated negotiated-group check, repo-wide audit, precompiled-proxy flag -- all tested live, no AWS touched

Ten corrections to `campaign_run.py` (A), four verification/test items
(B), and the precompiled-binary wiring (C, first half of item 15 --
the commit itself is a separate, later action). Nothing here applies
Terraform or launches an instance.

**A.1 -- window overwrite, real bug, fixed.**
`settling_{profile}_run{i}.json`, `settling_{profile}_meta.json`, and
`gateway_block_{profile}.log` had no window number in their filename --
window 2 of a campaign would have silently overwritten window 1's
settling data. Fixed: `settling_{profile}_window{NN}_run{i}.json`,
`settling_{profile}_window{NN}_meta.json`,
`gateway_block_{profile}_window{NN}.log`. `start_block_proxies()`/
`stop_block_proxies()` both gained a `window` parameter (threaded
through the module-level wrappers and `run_window()`) to make this
possible. **Tested live** (`tests/test_window_no_overwrite.py`): runs
the real `LocalExecutor.start_block_proxies()`/`stop_block_proxies()`
three times with `window=1,2,3` (Docker/compose calls mocked, since
this is about the FILE-NAMING logic, not re-proving Decision 62's
settling protocol) -- 21 files written, all 21 names distinct, all 3
windows represented.

**A.2 -- block order: a REAL bug found while "confirming" it, not just
confirmed.** The order specified is switch profile -> proxies up -> 5
settling runs -> per-scenario warmup -> round-robin. Reading
`run_window()` closely (not just trusting the comment above it) showed
warmup was actually called BEFORE `start_block_proxies()` -- every
scenario's warmup ran against whatever profile the client proxy
happened to still be running from the PREVIOUS block, since the
current block's profile switch and proxy restart hadn't happened yet.
Fixed by moving the per-scenario warmup loop to after
`start_block_proxies()` returns. **Tested live**
(`tests/test_block_order.py`): patches the module-level
`start_block_proxies`/`run_warmup`/`run_one_execution`/
`stop_block_proxies` functions to record call order, runs the real
`run_window()` against a 4-scenario/3-profile window (seed=42) --
confirms, per profile block: `start_block_proxies` -> all of that
block's `run_warmup` calls -> round-robin `run_one_execution` calls ->
`stop_block_proxies`, in that order, every block.

**A.3 -- SSH command construction: `repr()`/nested single quotes
replaced with `shlex.quote`/`shlex.join`, hybrid style.** `
server_flock_wrap()` used `f"...{remote_cmd!r}"` -- `repr()` on a
string containing a single quote (exactly what the old `python3 -c
"...start_tls_kem_proxy('{profile}')"` command had, nested inside an
outer single-quoted SSH command) produces a shell string that doesn't
parse: the embedded `'` terminates the outer quote early. Fixed with
`shlex.quote()`, applied with a hybrid rule -- shell SYNTAX (`&&`,
`$(...)`, env-var-assignment prefixes) is left as literal, correct
shell text (it's SUPPOSED to be interpreted by the remote shell); only
VARIABLE values (profile name, IP, label, paths) go through
`shlex.quote()`. The `python3 -c` command specifically: the inline code
string is built via `json.dumps()` (a valid Python string literal,
safe regardless of embedded quotes) and the whole `["python3", "-c",
code]` list is `shlex.join()`'d, never hand-nested. **Every one of
these commands was validated against a real SSH connection in the
local rehearsal (B.11) -- not just read for correctness.**

**A.4 -- real-mode `NotImplementedError` now aborts with a nonzero exit
code; systemd restart limits; an operator status file.**
`run_window()` used to catch `NotImplementedError` at three points and
`return` cleanly -- in real mode (where `SSHExecutor._run_or_print`
raises it for every action, since live SSH execution is still
deliberately not implemented, Decision 60/62) this made the orchestrator
exit 0 and LOOK like a successful, empty campaign. All three `except
NotImplementedError: print(...); return` blocks removed; the exception
now propagates out of `run_window()`/`main()` to the interpreter's
default uncaught-exception handler (nonzero exit, traceback on stderr).
`--dry-run` is unaffected (`_run_or_print` never raises when
`dry_run=True`). Added `write_status(state, detail)`, writing
`CAMPAIGN_STATUS_FILE` (default `/home/ec2-user/campaign-status.json`)
at `starting`/`running`/`completed`/`aborted` (the last captures the
exception's type, message, and full traceback) -- a best-effort write
that never masks or replaces the real error (write failure only warns,
never raises). `campaign_run.service` gained
`StartLimitIntervalSec=600`/`StartLimitBurst=5` (`[Unit]` section): 5
failures inside any rolling 10 minutes trips systemd's own start-limit,
the unit goes to "failed" and stops restarting on its own --
`systemctl reset-failed` + `systemctl start` is the explicit operator
action needed to try again, instead of a silent infinite restart loop
on a deterministic failure.

**A.5 -- `--dry-run`/`SSHExecutor` now cover the full remote-data
surface.** `run_one_execution()` previously only constructed tcpdump
start/execution/stop commands. Added, all real, previewable commands:
gateway log (`docker logs -t --since 10m ...` on the server), CPU/
steal/memory of each instance (`cat /proc/stat; cat /proc/meminfo` on
both sides), reference ping (client -> server), `chronyc tracking` on
each side, and fetching `calls.jsonl` + the run's own JSON (`cat` over
SSH stdout, for the text artifacts) plus the detected-interface files
(A.7). Live SSH execution of these still raises `NotImplementedError`
in real mode, unchanged (Decision 60/62: no untested SSH call is faked
as working) -- what's new is that `--dry-run` now previews ALL of
these, not just the execution/tcpdump subset.

**A.6 -- process lifecycle: proxy via `docker run -d` (a real service,
not a dying foreground process); tcpdump's PID bug fixed.**
Two fixes, one in `opin_flow.py`, one in `campaign_run.py`:
- `opin_flow.start_tls_kem_proxy()` gained `detached: bool = False`.
  When `True`, swaps `--rm -i` for `-d` (same image, same flags
  otherwise) and returns the container's fixed name (a `str`) instead
  of a `Popen` -- `stop_tls_kem_proxy()` already only needed `docker
  stop <name>` to tear it down (not the Popen handle), so it now
  accepts either. Needed because `SSHExecutor`'s remote client proxy
  is started by a SEPARATE SSH invocation than the one that will later
  stop it -- a foreground `-i` container dies the instant that first
  SSH session closes; `-d` makes its lifecycle independent of any one
  SSH connection, matching `start_pqc_signer_service()`'s own
  long-established `-d` pattern, not a new mechanism.
  `SSHExecutor.start_block_proxies()`/`stop_block_proxies()` updated to
  call it with `detached=True` and to `docker stop`/`docker rm -f` the
  fixed container name directly.
- tcpdump's `sudo tcpdump ... & echo $!` captured **sudo's own PID**,
  not tcpdump's (the backgrounding happened OUTSIDE the sudo'd
  process). Fixed: `sudo setsid sh -c "nohup tcpdump ... & echo \$! >
  pidfile"` -- the backgrounding and `echo $!` both happen INSIDE the
  sudo'd shell now, so `$!` is tcpdump's own PID; `nohup`+`setsid`
  detach it from the SSH session so it survives that session closing;
  stdout/stderr redirected to a log file. **Confirmed live, three
  times, by the rehearsal (B.11)** -- see its own writeup for the two
  FURTHER bugs this specific command's own quoting had, found only by
  actually running it over SSH.

**A.7 -- network interface auto-detected (`/proc/net/route`), not
hardcoded `eth0`.** New `_default_route_interface()` (reads
`/proc/net/route`'s destination-`00000000` row) and, for the SSH path,
an inline shell equivalent (`_iface_detect_sh()`, since none of
`SSHExecutor`'s remote reads are wired to live execution yet) with
`eth0` only as a last-resort fallback if detection itself yields
nothing -- never the primary source of truth. The detected name is
recorded in the run's own JSON (`network_interface: {server, client}`)
instead of assumed. **Confirmed live** on a real Linux container
(correctly detected `eth0`) and via the rehearsal (B.11, same result
against the sshd containers).

**A.8 -- clock-drift field renamed and re-conceived: client-vs-server
via `chronyc tracking`, not container-vs-host.** The old
`clock_drift_seconds` compared the gateway CONTAINER's clock against
this Python process's own clock via `docker exec ... date -u` --
meaningless in the local test (container and host share the same
kernel clock, Docker Desktop's Linux VM; there is nothing to drift)
and not what the real campaign needs anyway (client vs. server, not
container vs. host). Renamed to `client_server_clock_drift_seconds`;
new `_chrony_tracking_offset()` parses `chronyc tracking`'s "System
time" line (this host's own offset from its sync reference) -- the
real quantity is each real instance's own offset, compared against
each other (`client_offset - server_offset`), not one host asking the
other's time over SSH (which has its own RTT confound). In
`LocalExecutor` (single host, no second instance to compare) this
stays `None` with the reason recorded, never a fabricated 0.0; it is
SSHExecutor's real per-instance `chronyc tracking` reads (A.5) that
populate it for real. **`_chrony_tracking_offset()`'s parsing confirmed
against a REAL `chronyd` daemon** (Docker container, `--cap-add=SYS_TIME`):
unsynced ("0.000000000 seconds fast") parsed as `0.0`; synced against a
real NTP pool ("0.434293777 seconds slow") parsed as `-0.4155` (small
discrepancy vs. the raw reading is the clock continuing to drift
between the `chronyc` call and the Python parse, not a parsing bug).

**A.9 -- CPU/memory sampled periodically throughout an execution,
`/proc/meminfo` included.** The old sampler took exactly 3 discrete
snapshots (before/during/after) of `/proc/stat` only. New
`_sample_cpu_mem_steal()` reads `/proc/stat` AND `/proc/meminfo`
(`MemTotal`/`MemFree`/`MemAvailable`) per sample; new `_PeriodicSampler`
runs a background daemon thread sampling once per `interval_seconds`
(default 1.0s) from `start()` to `stop()`, returning every sample, not
3. `run_one_execution()` writes one JSON object per line (jsonl) per
sample instead of one `{before, during, after}` object. **Confirmed
live** on a real Linux container: 5 samples over ~1s at a 0.3s
interval, each with real non-null `cpu`/`mem` values (vs. honest
`None` on this Windows dev machine, where neither `/proc/stat` nor
`/proc/meminfo` exist).

**A.10 -- documented, no code change: what actually guarantees "one
execution at a time."** Two layers, not one: (1) the orchestrator's
own sequential control flow (no threading in `run_window()`'s
round-robin loop -- one execution is started, awaited, and written to
disk before the next begins) and (2) `_SERVER_LOCKS`, an in-memory
per-installation lock, defense-in-depth against a future
concurrent-windows change reintroducing an overlap. The server-side
`flock` (Decision 64) covers ONLY the profile switch -- the one
server-side action that mutates shared state (recreating containers)
and could plausibly race with a stray manual `switch_crypto_profile.py`
invocation or a second orchestrator instance. Individual executions
are NOT flock-wrapped on the server side at all; there is nothing
server-side for a single execution against an already-switched,
already-stable server to race on. Documented in `server_flock_wrap()`'s
own docstring, not a separate note disconnected from the code.

**B.11 -- 3-container local rehearsal (control, server, client, real
`sshd`), implemented and run for real.** `tests/rehearsal_setup.sh`
launches `linuxserver/openssh-server` as "server"/"client" (sudo
enabled, `python3`/`tcpdump`/`chrony`/`iputils` installed, `/home/
ec2-user` symlinked to this image's own `/config` home so the real,
unmodified `/home/ec2-user/...` literal paths this file assumes work
unchanged) plus a plain `python:3.12-alpine` "control" container with
an `openssh-client` and the test keypair; `tests/rehearsal_runner.py`
calls `campaign_run.py`'s REAL, unmodified command-building functions
(`server_flock_wrap`, `SSHExecutor._ssh_cmd`/`_tcpdump_start_cmd`/
`_tcpdump_stop_cmd`/`_env_prefix`, `_iface_detect_sh`) and runs the
result over a real SSH connection -- the one thing `SSHExecutor`
itself still deliberately doesn't do (Decision 60/62). **Found and
fixed three real bugs**, each confirmed by an actual failing-then-
passing SSH round trip, not by inspection: (1) `~/...`-prefixed paths
wrapped in `shlex.quote()` -- quoting a leading `~` defeats the
shell's own tilde expansion, so the remote shell tried to create a
file literally named `~` ("nonexistent directory"); fixed by switching
to the literal `/home/ec2-user` (consistent with this file's other
hardcoded paths) and dropping the quoting on these self-constructed,
safe-by-construction path strings. (2) `$HOME` INSIDE `sudo setsid sh
-c '...'` resolves to ROOT's home, not the invoking user's (`sudo`
resets `HOME` by default) -- same literal-path fix covers it. (3)
`$IFACE` also cannot cross the `sudo` boundary as a variable reference
(plain, unexported local variable in the login shell) -- fixed by
DOUBLE-quoting the inner `sh -c` argument instead of single-quoting
it, so the OUTER (login) shell expands `$IFACE` to the real detected
interface name BEFORE `sudo` runs, while `$!` is escaped (`\$!`) so it
survives to be evaluated by the INNER shell instead. After all three
fixes, all 9 of the rehearsal's checks passed, including reading back
the captured PID's own `/proc/<pid>/comm` as `tcpdump` (not `sudo`/
`setsid`/`sh`) -- A.6's claim, independently confirmed.
**What this rehearsal covers:** every SSH command string
`SSHExecutor`'s real methods construct actually parses and runs on a
real remote shell; A.6's PID fix; A.7's interface auto-detection; A.5's
chronyc/ping/`/proc`-file commands.
**What it does NOT cover (by design, not an oversight):**
`switch_crypto_profile.py`'s real settling sequence and
`campaign_client_runner.py`'s real flow execution (both stand-ins here
-- already covered against the real local stack by Decision 62/65);
real AWS conditions (IAM/security-group-gated SSH, instance boot,
real inter-region latency -- these 3 containers share one Docker
bridge network at ~0ms); `SSHExecutor.live` execution itself, still
`NotImplementedError` by design.

**B.12 -- negotiated-group check: correlated by connection, not a flat
set; now aborts on a real mismatch instead of warning.** New
`verify_negotiated_groups()` (module-level, pure function) parses
`docker logs -t`'s slog-JSON lines and pairs each `"mTLS handshake
complete"` line (has `curveID`, no SNI) with the
`"GetConfigForClient: internal-caller classical carve-out applied"`
line (has SNI, no `curveID`) sharing the SAME `remoteAddr` -- an EXACT
string match (both read off the identical `net.Conn`) within a short
time window (guards only against a reused ephemeral port across two
distinct connections, not against fuzziness in the match itself).
Rule: a handshake WITH a paired carve-out line is the INTERNAL
channel -- its curve must be exactly `CurveP256`, any other value is a
regression of the SNI carve-out itself (v7 Decision 15), not a
settling fluke. A handshake with NO paired carve-out is the
CLIENT-FACING channel -- its curve must match the profile's own
(`CurveP384`/`MLKEM1024`/`SecP384r1MLKEM1024`). A carve-out line with
NO paired handshake is an UNPAIRED FAILURE. This supersedes Decision
62's WARN-only compromise (which was correct given what was known at
the time -- the two channels genuinely weren't separated yet) with the
SNI-correlated check Decision 62 itself said would be needed. Wired
into BOTH the 5-settling-run check (`start_block_proxies()`, now
aborts the block on a real problem) AND, new this turn, the per-
scenario warmup (A.2) -- a mismatch there aborts before any of the
block's real runs are spent on a broken warmup. **Tested**
(`tests/test_negotiated_groups.py`, 5 cases, synthetic log text,
pure-function -- no Docker needed since this validates the
CORRELATION LOGIC, not the settling protocol which Decision 62 already
covers live): happy path for all 3 profiles; a forced WRONG client
curve, all 3 profiles (the test item 12 explicitly asked for); a
forced wrong INTERNAL curve (regression case); an unpaired carve-out;
a carve-out just outside the correlation window. All 5 pass.

**B.13 -- Linux SIGTERM/flock repeated; tcpdump in a `netshoot`
container, all real.** SIGTERM: a real Linux container (not this
Windows dev machine, where `Popen.terminate()` calls `TerminateProcess`,
not a true signal) running `campaign_client_runner.py` against a
black-hole TCP listener standing in for the not-yet-started proxy (so
the real HTTPS connect call is genuinely still in flight, not already
failed) -- confirmed `returncode == -15` (the exact signal number) and
empty stdout (no corrupt partial JSON). flock: repeated (Decision 64
already proved this once) -- same `OSError: [Errno 11] Resource
temporarily unavailable` on the second holder. tcpdump in
`nicolaka/netshoot`: capture on port 443 against REAL outbound traffic
(a loopback `nc` listener doesn't cross `eth0` at all, so the pcap
stayed empty until switched to a real external request) -- pcap grew
0 -> 2080 bytes, 29 real TLS-handshake packets captured, dropped-
packet counter read from tcpdump's own summary line ("0 packets
dropped by kernel"), and a deliberately bad interface
(`-i nonexistent0`) confirmed to fail cleanly (the abort-the-block
case).

**B.14 -- repo-wide audit: `set_latency`/`docker exec`/`docker logs`/
hardcoded `127.0.0.1`/`localhost`/absolute paths/fixed ports.** Six
more `of.set_latency(...)` call sites found unguarded, beyond the four
Decision 51/62 already fixed: `_capture_pqc_artifacts.py`,
`_capture_id_token.py`, `_capture_client_assertion.py`,
`capture_participant_decomposition.py`, `median_automation.py`,
`go_classical_baseline.py` -- all one-off capture/calibration scripts
whose OTHER logic (`run_insurance_flow`/`do_call`) already honors
`REMOTE_GATEWAY_HOST` correctly, making this one unguarded line in
each a real, reachable inconsistency, not a theoretical one. Fixed
with the identical guard pattern used everywhere else. `docker exec`/
`docker logs`/`127.0.0.1`/`localhost` elsewhere in `thesis/scripts/`
(`baseline_automation.py`, `check_plan_modules.py`,
`calibrate_tls_kem_proxy_stub.py`, `opin_flow.py`'s own local-proxy
constants) were reviewed and are intentional, self-contained local-
only tools/constants with no `REMOTE_GATEWAY_HOST`-guarded counterpart
to be inconsistent WITH -- not "bugs," not touched. New regression
guard (`tests/test_no_local_lab_assumptions.py`): scans every `.py`
file under `thesis/scripts/` for `of.set_latency(` with no
`REMOTE_GATEWAY_HOST` string within 8 lines above it; fails loudly on
a new unguarded call site. **Verified it actually catches a
regression**, not just that it passes today: temporarily reverted one
guard (`go_classical_baseline.py`) -- the test failed, naming the exact
file and line; restored, test passes again.

**C.15 (first half) -- precompiled proxy binary wired behind an
explicit flag; `go run .` stays the default.** `opin_flow.start_tls_kem_proxy()`
gained `use_precompiled_binary: bool | None = None` (reads
`TLS_KEM_PROXY_USE_PRECOMPILED=1` from the environment when `None`,
so nothing changes unless explicitly opted in); new
`_ensure_precompiled_tls_kem_proxy_image()` builds Decision 66's
Dockerfile on demand (`docker image inspect` first, so it doesn't
rebuild on every call) into `mockopin/tls_kem_proxy:precompiled`. When
set, the `docker run` drops the `/src` source mount and `go run .`
entirely, running the image's own `ENTRYPOINT` (the binary) with the
same `-listen`/`-target`/`-cert`/`-key`/`-curve` flags. **Regression,
both halves checked separately (conflating them would be wrong -- a
ClientHello's 32-byte Random field and ephemeral key share make
literal byte-equality across separate TLS connections impossible BY
DESIGN, not a bug), both run live, both PASS:**
  - Binary byte-for-byte reproducibility: built twice, independently,
    with `--no-cache`; extracted via `docker create`+`docker cp`;
    compared. **9,463,989 bytes, identical, both builds.**
  - ClientHello size+SNI, `go run .` vs. precompiled, all 3 profiles,
    captured via a plain TCP listener standing in for the upstream
    gateway on the real `insurance-server-lambdas_default` network
    (ClientHello is the first, unencrypted record -- no real mTLS
    server needed): **classic 341 bytes/SNI `mtls` both modes; pqc
    1784 bytes/SNI `mtls` both modes; hybrid 1881 bytes/SNI `mtls`
    both modes** -- size and SNI identical in all 3 cases.
  (`thesis/scripts/tests/test_tls_kem_proxy_precompiled_regression.py`.)
  Base image pinned by digest: unchanged from Decision 66 (same
  `golang:1.27-rc-alpine@sha256:...` the live `go run .` path already
  pins).

## 68. `SSHExecutor`'s real SSH/SCP transport implemented and run end to end against the 3-container rehearsal, all 3 profiles; a second, more serious window-overwrite bug found and fixed (`runs/` itself, not just settling); three more real bugs found live; precompiled proxy validated in the full settling+execution flow; delivery/cleanup items closed

Seven items this turn, in the order asked: (1) `scan_secrets.sh`
re-confirmed before and after Decision 67's two commits, and again now
over the full history; (2) `verify_negotiated_groups()` shown in full,
with the forced-wrong-curve test's live output; (3) a SECOND window-
overwrite bug found and fixed, more serious than Decision 67's own
item A.1; (4) `SSHExecutor`'s real SSH/SCP transport implemented and
the orchestrator run for real against the 3-container rehearsal, all
3 profiles, with the full verification suite requested; (5) the
precompiled proxy validated inside the full settling+execution flow,
not just an isolated ClientHello; (6) the hand-created Docker network
removed, compose's own clean adoption confirmed; (7) an after-pilot
deferred-items list.

**(1) Scanner.** Passed before `04e8137`/`00b7b06` (shown live in that
turn's own transcript) and passes again now, full history, all refs:
`RESULT: PASS -- no secrets, account ID, or author IP found`.

**(2) `verify_negotiated_groups()`, shown in full** (the function
itself is reproduced in full in this turn's own chat response, not
re-pasted here -- `campaign_run.py`'s own module-level function,
~85 lines, correlates by exact `remoteAddr` string match within a
short time window, three outcomes: INTERNAL-channel curve wrong,
CLIENT-FACING-channel curve wrong, UNPAIRED carve-out). Live test
output, all 5 cases (`tests/test_negotiated_groups.py`): happy path
(all 3 profiles), forced wrong CLIENT curve (all 3 profiles --
Decision 15 item 12's own ask), forced wrong INTERNAL curve, unpaired
carve-out, a carve-out just outside the correlation window -- all 5
PASS.

**(3) A second, more serious window-overwrite bug -- `runs/` itself,
not just the settling/meta/gateway-log files Decision 67's A.1 fixed.**
`run_window()`'s round-robin loop used the window-LOCAL run index `i`
(1..`RUNS_PER_WINDOW`) directly as both the argument to
`already_done()`/`run_one_execution()` AND the `runs/run{i:02d}.json`
filename -- window 2's run01..run10 would have silently overwritten
window 1's, exactly the class of bug A.1 fixed for the settling files,
just not caught there because `runs/` itself wasn't in that test's
scope. The file's own docstring says "30 runs/profile/scenario"
(10/window x 3 windows) -- only true with GLOBAL numbering. Fixed:
`global_run_index = (window - 1) * RUNS_PER_WINDOW + i`, used for
`already_done()`, `run_one_execution()`'s `run_index` argument, and
the JSON filename; the window-local index is still recorded inside the
file (`window_local_run_index`) for traceability.
**Tested live** (`tests/test_full_campaign_no_overwrite.py`): runs the
REAL `run_window()` three times (not a narrower slice of it), full
round-robin/warmup/settling/negotiated-group-check path, mocking only
the genuinely remote/slow pieces (docker compose/exec/logs,
`latency_automation`'s own flow execution, tcpdump's absence on this
dev machine) -- confirms, for all 4 scenarios x 3 profiles (12
combinations): exactly 30 distinct `run{NN}.json` files, `run01`'s
content says `window=1`, `run11`'s says `window=2`, `run21`'s says
`window=3` (content-correctness, not just a file-count match), plus
all 63 settling/meta/gateway-log files (3 windows x 3 profiles x 7)
present and distinct. **Reverted the fix, confirmed the test actually
fails** (10 files per combination, not 30, content-check fails too) --
**restored it, confirmed PASS again** -- the same prove-the-regression-
guard-actually-guards discipline used throughout this project.

**(4) `SSHExecutor`'s real SSH/SCP transport -- implemented, and run
for real, not previewed.** `_run_or_print()` now calls
`subprocess.run(["ssh", ...], timeout=SSH_TIMEOUT_SECONDS)` for real
when `dry_run=False`; a nonzero exit or a timeout both raise
`RuntimeError` (A.4's "abort loudly," now exercised for real, not just
designed for it). New `_scp_pull()` (pcaps), `_verify_tcpdump_started()`
(the backgrounded start's own liveness, since a `nohup ... &` inside
`sudo setsid sh -c` can "succeed" at the SSH-exit-code level while the
backgrounded tcpdump itself is actually dead), `_run_tolerant()`
(ping/chronyc -- auxiliary measurements, reclassified below). The
settling sequence (5 runs + the correlated negotiated-group check,
B.12) is now real in `SSHExecutor.start_block_proxies()` too, not just
`LocalExecutor`'s -- using the FIRST scenario's client to generate the
traffic (settling verifies the SERVER's negotiated group, which
doesn't depend on which scenario's client happens to generate it; no
"settling's own" client exists in the real 8-scenario topology). `ssh
-i ~/.ssh/{key}` replaced with the absolute `CAMPAIGN_KEY` (no local
shell to tilde-expand a bare argv element). `main()`/`renew_safety_timers()`
gained `CAMPAIGN_INSTALLATIONS`/`CAMPAIGN_SSH_PORT`/`CAMPAIGN_SSH_KEY_PATH`/
`CAMPAIGN_RUNS_PER_WINDOW`/`CAMPAIGN_WINDOWS_PER_CAMPAIGN` env-var
overrides (same pattern as `CAMPAIGN_STATUS_FILE`) so the rehearsal
runs this SAME, unmodified `main()` against 1 installation/port
2222/a short schedule instead of a parallel reimplementation of it --
the real campaign's own defaults (22, `CAMPAIGN_KEY`, all 3
installations, 10/3) are untouched.

**Four MORE real bugs found live, this turn, running the real
orchestrator against the rehearsal -- none visible from reading the
code:**
  - `sudo kill -0 $(cat pidfile)` -- tcpdump runs as root (`sudo setsid`,
    A.6); a bare, non-sudo `kill -0` existence-check failed with
    "Operation not permitted" even though the process was alive and
    well. Fixed: `sudo kill -0`.
  - Auxiliary data (reference ping, `chronyc tracking`) going through
    the same hard-abort `_run_or_print()` as every core action meant
    `chronyc` failing (chronyd not running on the bare rehearsal
    containers) aborted the WHOLE execution -- wrong, since A.8's own
    clock-drift field already tolerates `None` by design
    (`LocalExecutor`'s own `_chrony_tracking_offset()` returns `None`
    rather than raising). Reclassified via `_run_tolerant()`: core
    actions (profile switch, proxy start, tcpdump start+liveness, the
    execution itself, gateway log/CPU fetch) still abort loudly; ping/
    chronyc now warn and continue.
  - A SECOND process refused by `SingleInstanceLock` (working exactly
    as designed, Decision 64) was overwriting the FIRST, legitimately-
    running instance's status file with its own "aborted: already
    running" -- corrupting the one thing an operator relies on to
    monitor the campaign that's actually in progress. Fixed: moved the
    `write_status("aborted", ...)` try/except INSIDE the
    `with SingleInstanceLock():` block, so a refused second instance
    writes nothing at all; only the process that actually holds the
    lock reports its own outcome.
  - (Documented together with Decision 67's own three rehearsal-found
    bugs in `_tcpdump_start_cmd`'s docstring -- the full real-mode run
    is what exercises the command for real, past what the rehearsal's
    own driver script checked in isolation.)

**Full real-mode verification suite, run against the 3-container
rehearsal (not simulated), 3 profiles:**
  - **Golden path**: 1 window, 2 runs/window, 4 scenarios, 3 profiles
    (`CAMPAIGN_RUNS_PER_WINDOW=2 CAMPAIGN_WINDOWS_PER_CAMPAIGN=1
    CAMPAIGN_INSTALLATIONS=sa-east-1 CAMPAIGN_SSH_PORT=2222`) --
    `campaign-status.json` ends at `"state": "completed"`; settling
    verified the correct curve for all 3 profiles over real SSH
    (`pqc` -> `MLKEM1024`, `hybrid` -> `SecP384r1MLKEM1024`, `classic`
    -> `CurveP384`); 36 files written (24 `run{NN}.json` + 12
    `run00_warmup`), full `server`/`client`/`runs` tree, real `.pcap.gz`
    pulled back via `scp` for every run.
  - **Hash manifest** (`campaign_pull.sh`'s own core logic -- `find |
    xargs sha256sum`, `sha256sum -c` on the pulled copy; `docker cp`
    substituted for `rsync`, not installed on this dev machine, same
    verification semantics): 206 files, `OK: every pulled file matches
    its sha256` -- then ONE byte appended to one file, confirmed the
    check actually fails (`FAILED`, exit 1) -- restored.
  - **Resume after a real kill mid-run**: `SIGKILL -9` sent to the
    orchestrator process after 4 runs committed; restarted -- printed
    `run 01 (window-local 01) already done -- resuming past it` for
    the exact run that was already on disk, completed the remaining
    47 of 48 total runs, reached `"state": "completed"`. Confirmed
    the pre-existing run's `started_at_utc` predates the restart (it
    was never re-executed, not just re-named).
  - **Instance lock**: a second real process attempt while the first
    was running raised `RuntimeError: Another campaign_run.py is
    already running` immediately (real `fcntl.flock`, Linux, not
    simulated) -- and, after the status-file fix above, left the
    first instance's status file untouched.
  - **Abort loudly, wrong curve**: `.client_curve_override` written
    to `CurveP521` on the rehearsal server (read by the rehearsal's
    fake `docker logs` script) -- the WHOLE process aborted with
    `negotiated-group verification FAILED (B.12): CLIENT-FACING
    channel ... negotiated 'CurveP521', expected 'MLKEM1024'`,
    recorded in `campaign-status.json` as `"state": "aborted"`.
  - **Abort loudly, tcpdump unavailable ("sem interface" in the sense
    of "capture can't actually happen")**: the real `tcpdump` binary
    hidden (`mv` to a different name) on the client -- the backgrounded
    start command still exited 0 (the `&` absorbs it), but
    `_verify_tcpdump_started()`'s own follow-up check caught it
    ("No such process") and aborted the whole run with a full
    traceback, recorded in the status file. Binary restored afterward.

**What this real-mode run does NOT cover** (same three items
Decision 67's rehearsal already named, still true): real AWS
conditions (IAM/security-group-gated SSH, instance boot, real inter-
region latency/packet loss -- `SSH_TIMEOUT_SECONDS=30` and the
settling-run timeouts are UNTESTED under real multi-hundred-ms RTT);
`switch_crypto_profile.py`/`campaign_client_runner.py`'s real logic
(stand-ins here, covered against the real local stack separately);
multiple REAL per-scenario client instances (this run's inventory
aliased all 4 of `sa-east-1`'s scenario keys to the SAME one rehearsal
client container -- genuine per-scenario machine isolation was never
exercised).

**(5) Precompiled proxy validated inside the FULL settling+execution
flow**, against the real local docker-compose stack (not just the
isolated ClientHello capture Decision 67 already did) --
`LocalExecutor.start_block_proxies()` (profile switch, 5 settling
runs, correlated negotiated-group check) + one real execution via
`latency_automation.run_once_timed_with_retry()`, classic profile, with
`TLS_KEM_PROXY_USE_PRECOMPILED=1`: settling verified `CurveP384`
correctly, 42 calls, **`total_bytes_exchanged = 125,485`** -- the
EXACT same figure `go run .` produces (confirmed in the same session,
same stack) and the long-standing baseline this project has used
since v1. Two real, pre-existing-and-documented environmental flukes
hit along the way, NOT caused by this change: the psql manual-
CHECKPOINT health check correctly tripped once (`5.36s > 5.0s`
threshold) after a `docker restart`, and one settling run hit a `502
Bad Gateway` on its first HTTP request (both already-known, already-
guarded-against failure modes from Decisions 4/9, not new) --
resolved by restarting the affected container and re-running, exactly
as their own error messages instruct. The local stack was brought up
only for this check and brought back down afterward (`docker compose
--profile main down`), not left running.
(`thesis/scripts/tests/test_precompiled_binary_full_flow.py`.)
**The campaign now uses the precompiled binary by default once wired
into the real deployment** -- i.e., `campaign_up.sh` (not yet built,
Decision 49/59) should set `TLS_KEM_PROXY_USE_PRECOMPILED=1` in the
client instances' environment; `go run .` remains the code's own
default for anyone running these scripts directly without that
variable set (local dev, this rehearsal), per C.15's original design.

**(6) Docker network cleanup.** The `insurance-server-lambdas_default`
network had been created BY HAND in an earlier session (the local
stack wasn't running at the time a test needed that network to
exist) -- confirmed the local stack was stopped, removed the
hand-created network, then brought the stack up fresh: compose created
its own network cleanly this time, with NO "a network with name ...
exists but was not created by compose" warning (confirmed by grepping
the `up` output for `warning`/`network` -- only the unrelated,
pre-existing `cs-builder-run` orphan-container warning remains, a
leftover from a different, unrelated compose service, 2 months old,
not touched). Stack brought back down afterward; `docker compose down`
removed its own network along with it, same as any other compose-
managed resource.

**(7) After-pilot: what's still deferred, not glossed over.**
  - `deliver_images.sh` (Decision 50/59) -- still not built; the
    precompiled proxy image now exists and passes its own regression,
    but nothing yet ships it (or the main stack's images) to a real
    EC2 instance.
  - `pre_block_checks()`'s `image_id` and `negotiated_group` fields
    are still literal "NOT YET AVAILABLE" placeholders (Decision
    50/54's image-ID pre-flight comparison, and Decision 45/51's
    PRE-block negotiated-group check -- distinct from the POST-
    settling check this turn made real).
  - Real AWS launch itself: 12-instance Terraform, the flex-instance
    launch test -- both `plan`-clean, neither applied; author must be
    present (standing instruction).
  - `SSH_TIMEOUT_SECONDS=30` and the settling-run retry timing are
    untested under real inter-region RTT/packet loss -- this
    rehearsal's 3 containers share one Docker bridge network at ~0ms.
  - Genuine per-scenario client machine isolation (8 real scenarios
    across 3 installations, not 4 scenario-keys aliased to one shared
    rehearsal container) -- untested until real instances exist.
  - `rsync` itself was never actually exercised (not installed on this
    dev machine; `docker cp` substituted for the pull-mechanism
    verification) -- worth confirming the OPERATOR's own machine has
    it before relying on `campaign_pull.sh` for real.
  - Systemd units for the client-side proxy/signer (vs. this turn's
    `docker run -d`, which already satisfies "service, not a dying
    foreground process") -- not built; `docker run -d` was judged
    sufficient for A.6's own requirement, but a systemd unit would be
    more restart-robust if ever wanted.
  - Disk sizing at FULL SCALE (720 real executions x real-sized pcaps,
    not this rehearsal's ~50-byte empty ones) -- Decision 54's earlier
    estimate was not re-validated against this turn's code.

## 69. Pre-flight image_id/negotiated_group wired for real; `deliver_images.sh` run for real with real rsync (two more real bugs found and fixed); 4 separate per-scenario client containers confirm real isolation; `ServerAliveInterval` added and the golden path confirmed under real 325ms/2%-loss `netem`, including a genuine SSH-drop-mid-execution abort and clean resume; Terraform `enabled_client_scenarios` added and plan-tested against live AWS credentials (read-only, nothing applied)

Five items this turn, in the order asked, every one run for real rather
than reasoned about: (1) `pre_block_checks()`'s two placeholders wired
and tested, including a real abort-on-mismatch; (2) `deliver_images.sh`
clarified as ALREADY WRITTEN (Decision 67's own "after-pilot" list was
wrong to call it unbuilt) and run for real with real rsync -- send,
interrupt, resume, sha256 match, disk-space check, tarball cleanup --
finding and fixing two more real bugs; (3) the rehearsal rebuilt with 4
genuinely separate client containers, one per `sa-east-1` scenario,
confirming real per-scenario isolation; (4) `ServerAliveInterval`/
`ServerAliveCountMax` added (a real, previously-missing gap), and the
full golden path confirmed passing under real `tc netem` 325ms delay +
2% packet loss, including a live SSH-drop-mid-execution test that
aborted correctly and resumed cleanly afterward; (5) a Terraform
`enabled_client_scenarios` variable, plan-tested in all three requested
scenarios against this project's REAL, live AWS credentials (plan
only -- nothing ever applied, no instance ever launched, consistent
with this turn's own opening instruction).

**(1) Pre-flight checks, wired for real.** `pre_block_checks()` gained
an `executor` parameter. For `SSHExecutor`: `image_id` now really
`docker image inspect`s the server's loaded gateway image
(`insurance-server-lambdas-mtls:latest` -- the one whose ID actually
matters for crypto correctness) and compares it against
`/home/ec2-user/delivered_images_manifest.json` (written by
`deliver_images.sh`, see (2)) -- **a mismatch now ABORTS THE BLOCK**,
confirmed live: with the manifest set to one fake ID and the server's
(fake, rehearsal) image reporting a different one, the whole process
aborted immediately with a clear message naming both IDs, before
spending any run. A matching ID (the normal case) was ALSO confirmed
live, every block, across all 3 profiles. `negotiated_group` now
really calls `verify_negotiated_groups()` against a short recent
gateway-log slice -- but only REPORTS (never aborts here): confirmed
live that it correctly shows the PREVIOUS block's own curve as a
"mismatch" against the upcoming profile's expected one (routine, not a
real problem -- the real, abort-worthy check is `start_block_proxies()`'s
own post-switch settling verification, B.12, which ran correctly right
after, every time). For `LocalExecutor`: both fields report "N/A --
local executor" rather than fabricating a comparison that has nothing
real to compare against.

**(2) `deliver_images.sh` -- clarified, and run for real.** It
ALREADY EXISTS (155 lines, Decision 50/55/57) -- Decision 67's own
after-pilot list was simply wrong to call it "not yet built"; it
builds/verifies each image's platform, saves+gzips, checks disk space
on the control instance BEFORE sending, sends via rsync (falling back
to scp+split-parts if rsync is missing), verifies sha256 on the
control instance, distributes to each server via scp, loads and
compares image IDs across servers, and cleans up the tarball on both
ends. Gained `MOCKOPIN_DELIVER_IMAGES_OVERRIDE`/`MOCKOPIN_CONTROL_IP_OVERRIDE`/
`MOCKOPIN_SSH_PORT` env-var overrides (same pattern as
`campaign_run.py`'s own) so it could be run UNMODIFIED against the
rehearsal instead of a parallel reimplementation; also now WRITES
`delivered_images_manifest.json` after each image's cross-server ID
check succeeds, feeding item 1's own pre-flight check.
**Run for real** (an "operator" container with real Docker via a
mounted host socket + real `rsync`, against the rehearsal's server +
one client standing in as "the real server"), using the actual
`mockopin/tls_kem_proxy:precompiled` image (Decision 67) as the
delivered artifact:
  - Platform/size check, disk-space check, sha256 generation: all
    real, all passed.
  - **Real rsync send**: confirmed via its own progress output (not
    inferred) -- transferred for real over the rehearsal's SSH
    connection, not a stand-in.
  - **Two real bugs found and fixed**, neither visible without running
    the script for real:
    1. `SSH_OPTS` (one shared array) used `-p PORT` for BOTH `ssh` AND
       `scp` -- `-p` is `ssh`'s port flag but `scp`'s own "preserve
       modification times" flag (no argument), so `scp` silently
       tried to open a local file literally named "2222"
       ("stat local '2222': No such file or directory"). This had
       always been latent (port was always the AWS default, 22,
       before this turn introduced a non-default port for testing) --
       invisible until a non-default port was ever actually used.
       Fixed with a SEPARATE `SCP_OPTS` array using `-P` (capital).
    2. `sha256sum "$tarball" > "$tarball.sha256"` (and the same
       pattern for the split-parts fallback) embeds `$tarball`'s full
       LOCAL path (under the operator's own `$WORKDIR`) as the
       filename INSIDE the `.sha256` file. `sha256sum -c` on the
       REMOTE side then tries to open that SAME local-looking absolute
       path, which obviously doesn't exist there (the remote copy
       lives at `~/basename`) -- the verification step would have
       FAILED on every single real transfer, interrupted or not; this
       was never an "interrupted transfer only" bug. Fixed:
       `(cd "$(dirname "$tarball")" && sha256sum "$(basename
       "$tarball")")` -- records just the basename, resolving
       correctly on both ends.
  - After both fixes: full real run completed end to end -- sha256
    verified OK on the control instance, distributed to the stand-in
    server, image-ID comparison OK, manifest written, tarball removed
    on BOTH ends (confirmed by `ls` on each afterward).
  - **Real interrupt + resume**, demonstrated separately with a 20MB
    random-data file (a real image's exact bytes don't matter for
    testing the TRANSPORT mechanism itself) and `rsync --bwlimit=200`
    to make the interruption timing controllable regardless of the
    rehearsal's own (very fast) local network: killed mid-transfer at
    ~2.1MB/20MB (confirmed via the remote partial file's size), resumed
    with a second `rsync --partial` call, **final sha256 identical to
    the original** on both ends.
  - rsync confirmed NOT present on the Amazon Linux 2023 base AMI by
    default (`docker run --rm amazonlinux:2023 command -v rsync` finds
    nothing) -- added to the CONTROL instance's own user-data
    (`templates/install_rsync.sh`, `role == "control"` only; servers
    never need it, they only receive a plain `scp`) rather than just
    relying on the script's already-existing scp+split-parts fallback,
    which stays in place as the safety net either way.

**(3) Isolation -- 4 separate client containers, one per `sa-east-1`
scenario.** Rebuilt the rehearsal with `client_l0`/`client_l123`/
`client_l219`/`client_l325` as 4 genuinely distinct containers (not
one container aliased to all 4 scenario keys, Decision 67's own
simplification) -- `inventory.json` maps each `{scenario}@sa-east-1`
key to its own container. Each client's own `campaign_client_runner.py`
stand-in reports its real `hostname` in its JSON result. **Confirmed
live**: the real golden-path run's `runs/run01.json` for each of the 4
scenarios shows a DISTINCT hostname matching that scenario's own
container ID exactly (`L0`->`3a7e534fd53d`, `L123`->`188150b0e8fa`,
`L219`->`54eafad0612f`, `L325`->`5da26a38ac80`) -- genuine per-scenario
machine isolation, not inferred from the code, read back from the
actual executed data.

**(4) SSH under real latency + packet loss; a real gap found and
fixed; a real mid-execution drop tested.** `ServerAliveInterval=10`/
`ServerAliveCountMax=3` were simply ABSENT from every `ssh`/`scp` call
in `campaign_run.py` before this turn -- without them, a connection
gone quiet under real packet loss could sit unnoticed by the SSH
client far longer than `ConnectTimeout` governs (that option is
initial-handshake-only). Added to `_ssh_cmd()`, `_scp_pull()`, and
`renew_safety_timers()`'s own direct `ssh` call. **Tested under real
degraded conditions**: `tc qdisc add dev eth0 root netem delay 325ms
loss 2%` on the server AND all 4 clients (real `iproute2`, real
kernel-level shaping, not simulated) -- a plain `ssh ... echo hi` that
took ~0.1s unshaped took 4.8s shaped, confirming the impairment was
real. The FULL golden path (4 scenarios x 3 profiles, settling +
warmup + round-robin) **completed successfully end to end under this
shaping** -- `ConnectTimeout=15` was never hit, `ServerAliveInterval`
never produced a false-positive drop, every profile's settling check
still correctly verified its curve.
**SSH-drop-mid-execution, the real test**: disconnected `client_l123`
from the Docker network (`docker network disconnect`) mid-campaign.
The round-robin loop correctly finished every OTHER scenario's
in-flight/pending runs, then hit L123's next execution and
**aborted the whole process** (`tcpdump start (client)`: "Could not
resolve hostname" -- then the `finally` block's own
`stop_block_proxies()` attempt failed the SAME way, chained in the
traceback, which is itself correct: cleanup should try and its own
failure shouldn't be hidden). **Confirmed no `run02.json` was ever
written for L123** -- the interrupted execution was neither marked
done nor duplicated. Reconnected the network, restarted with the
SAME command -- confirmed via the printed "already done -- resuming
past it" messages that every OTHER already-completed run (L0/L123/
L219/L325 run01, L0 run02) was correctly skipped, while L123's run02
was genuinely RE-EXECUTED (a fresh `started_at_utc`, strictly after
the reconnect) -- final state: `"completed"`, exactly 24 run files
(4 scenarios x 2 runs x 3 profiles), no duplicates. Same underlying
mechanism Decision 68 already proved for a `SIGKILL` -- this turn
confirms it holds for a genuine network-level SSH drop too, not just
a killed process.

**(5) Terraform `enabled_client_scenarios` -- added, and plan-tested
against REAL, live AWS credentials this session unexpectedly turned
out to have (confirmed by `terraform plan` successfully reading real
VPC/AMI/subnet data) -- plan only, nothing ever applied, no instance
ever launched, per this turn's own opening instruction and the
project's standing rule that only the author applies/launches.**
Added `var.enabled_client_scenarios` (a set of `"{scenario}@{installation}"`
keys, matching `inventory.json`'s own convention -- finer-grained than
a bare per-installation toggle, needed to reproduce scenario (a)'s
exact "only L0 and L325" subset within a single enabled installation).
Every client/server module gained a `count` gated on this set
(`local.sa_east_1_enabled` etc., derived via `split("@", s)[1]`);
`gateway_ingress_cidrs` and the `inventory` output both use
`compact()`/`merge()` to include ONLY enabled entries, never a null/
placeholder for a disabled one. The control instance is NOT gated --
needed regardless of which installations are active.
  - **(a) sa-east-1 only, clients L0+L325, + control**:
    `enabled_client_scenarios=["L0@sa-east-1","L325@sa-east-1"]` ->
    **21 resources to add**, confirmed to be EXACTLY control + the
    `sa-east-1` server + the 2 named clients (+ the 7 region key pairs,
    ungated by design -- cheap, region-scoped, not scenario-specific).
    The `inventory` output's own keys, read back from the plan JSON:
    `servers: ['sa-east-1']`, `clients: ['L0@sa-east-1', 'L325@sa-east-1']`
    -- exactly right, not just "probably."
  - **(b) all installations** (the default): **45 resources to add**
    -- unchanged from the pre-existing baseline (Decision 54's own
    "45 resources, plan-clean" claim still holds after this refactor).
  - **(c) "second apply of (b) over (a)'s state, confirming nothing
    recreated"** -- done as a STRUCTURAL comparison, not a literal two-
    step apply (which the opening instruction forbids): saved both
    plans (`-out`), exported both as JSON (`terraform show -json`),
    and programmatically compared every resource address appearing in
    BOTH plans. **Result: all 21 overlapping resources have IDENTICAL
    planned configuration between (a) and (b)** -- meaning a real
    second apply of (b) over (a)'s state would see 0 diff on them
    (0 to change, 0 to destroy, 0 replace), only the 24 new addresses
    (the other 2 installations + sa-east-1's L123/L219) would be
    added. 21 + 24 = 45, consistent with (b)'s own total. This is a
    sound proof given the no-apply constraint: Terraform's own
    replace-vs-update decision is a direct function of whether a
    resource's desired config changed, and this shows it didn't, for
    any of the 21 resources (a) and (b) share.
  - Security-group rules and the `inventory` output were already
    confirmed, above, to include ONLY what's enabled -- not a
    separate claim, the SAME evidence.

## 70. Credentials/user-data/scheduled-task audit (one real gap found and fixed: Docker was missing from every instance); `PILOT_RUNBOOK.md` written; `pilot_acceptance.py` written for all 9 acceptance criteria, smoke-tested against synthetic data end to end, one real bug found and fixed in the process (the run JSON has no `"label"` field and no `"duration_seconds"` field); data-retention rule for the pilot's window 1 documented

A no-AWS-mutation turn (`terraform plan` only, confirmed throughout --
no `apply`/`destroy`/instance launch at any point), auditing the
pilot's own readiness and building the two pieces of tooling the pilot
itself depends on to be judged pass/fail. Six items, in the order
asked:

**(1) Credentials and access.** Exactly one AWS profile
(`mockopin-pqc`) exists in `~/.aws/config`/`credentials` in this
session's environment -- no admin credential present, no credential
value printed anywhere (only the profile NAME, per the profile's own
restriction from Decision 44). `terraform plan` run read-only against
the pilot's exact 21-resource scope; nothing from its output (ARNs,
IDs, addresses) was written into any document without first passing
`scan_secrets.sh` (see item 7 below).

**(2) A real, previously-undiscovered gap: Docker was missing from
EVERY instance's user-data.** Amazon Linux 2023's base AMI ships
neither `docker` nor `rsync` (confirmed empirically:
`docker run --rm amazonlinux:2023 sh -c "command -v docker"`/`rsync`
both find nothing) -- yet the only user-data template wired into
`campaign_instance`'s module was role-gated to install `rsync` alone,
on a subset of roles. Had this gone uncaught, the FIRST real pilot
launch would have failed completely (no `docker` to run the gateway
stack, no `docker` group for `ec2-user`, since none of this project's
own SSH commands prefix `docker` with `sudo`). Fixed: the role-gated
`install_rsync_user_data` local was replaced with an unconditional
`install_docker_and_rsync_user_data` (`templates/install_docker_and_rsync.sh`,
new; `templates/install_rsync.sh`, removed) applied to all 12 instance
roles (3 servers, 8 clients, 1 control) via `dnf install -y docker
rsync` + `systemctl enable --now docker` + `usermod -aG docker
ec2-user`. Validated via `terraform validate` (pass) and a real
`terraform plan` against the pilot's exact scope -- confirmed (via
`terraform show`'s plain-text output; `user_data` itself is
represented only as a SHA1 hash in both JSON and plain-text plan
output, a known AWS-provider quirk, not inspectable directly) that
control's `user_data` hash differs from the 3 server/client instances'
shared hash, consistent with the expected self-terminate-component
grouping.

**(3) Scheduled tasks.** `CronList` confirms no persistent recurring
job (`CronCreate`-based) exists from this session. Every
`ScheduleWakeup` call made this session was a one-shot, self-consuming
dynamic wakeup used only to pace long rehearsal waits -- none pending,
none AWS-altering, none capable of running `apply`/`destroy`/launch
without Luciano present.

**(4) `v8/campaign/PILOT_RUNBOOK.md` written.** Covers: preconditions
(flex-launch test done + instance type chosen; Luciano's own billing-
budget/credit check, since the restricted profile can't read either
via the API); a 7-step walkthrough with exact commands and each step's
expected output; a 10-row first-contact-with-AWS verification table
(cloud-init, docker+chrony, Elastic IPs, security-group rules,
control↔server↔client connectivity); 5 explicit Luciano-confirms-before-
proceeding points; 8 abort criteria; a cost-monitoring schedule across
the run; the two outcomes (A: unscoped re-apply adds the other 24
resources without touching the pilot's 21, per Decision 69's own
structural proof; B: `campaign_down.sh`); and a keep-up-vs-teardown
cost/time/risk comparison table with a stated, overridable
recommendation.

**(5) `pilot_acceptance.py` written for all 9 criteria -- and smoke-
tested for real, not just read over.** Computes, from raw pulled data
only: total_bytes_exchanged vs. the local-lab baseline (125,485/
275,800/331,639 bytes); client ClientHello size+SNI vs. the local-lab
baseline (341/1784/1881 bytes, SNI "mtls", Decision 67's own
precompiled-proxy regression figures); negotiated group via
`verify_negotiated_groups()` (reused, not reimplemented); steal% (now
computable at all -- see below) with a <5% pass/fail and max CPU/
memory; RTT from the pcap's own SYN→SYN-ACK timestamps vs. the
reference ping; bootstrap CI width of the per-cell median against a
±5% target, with an execution-count recommendation when it isn't met;
T_fluxo with vs. without tcpdump; pcap/disk volume extrapolated to 720
executions with a Git-LFS-vs-external-storage recommendation; and a
full re-verification of `campaign_pull.sh`'s own sha256 manifest
(independent of its `.pull-verified` marker, not just trusting it).
Required a minimal pure-stdlib pcap reader (classic libpcap format,
`struct`-based Ethernet/IPv4/TCP parsing) since no pcap library is in
`thesis/scripts/requirements.txt` and this project's own standing
style doesn't add one for a single narrow read need.

Two `campaign_run.py` additions were built as direct prerequisites,
both validated live in a throwaway Linux container (not just read over):
a `CAMPAIGN_TCPDUMP_SKIP_RUN_INDICES` env var letting specific global
run indices skip tcpdump entirely (criterion 7's own with/without
comparison group); and a periodic CPU/mem sampler for `SSHExecutor`
(`_cpu_mem_sampler_start_cmd`/`_cpu_mem_sampler_stop_cmd`), replacing
the old single-snapshot `/proc/stat`/`/proc/meminfo` fetch -- steal% is
a DELTA between two readings, uncomputable from one snapshot at all
(only `LocalExecutor`'s own A.9 sampler had this before). Confirmed
live: the sampler starts under the same safe-quoting pattern as the
proxy-start command, captures its OWN pid (not a wrapper's) via
`echo $!`, produces one real JSON sample/second of actual
`/proc/stat`/`/proc/meminfo` content, and `kill` genuinely terminates
it (confirmed via `/proc/<pid>/status` showing `State: Z`, i.e.
successfully killed, not yet reaped by the throwaway container's own
minimal `sleep`-based PID 1 -- a benign test-container artifact, not a
concern on a real systemd-based EC2 instance). Full existing test
suite (`test_negotiated_groups.py`, `test_window_no_overwrite.py`,
`test_full_campaign_no_overwrite.py`, `test_block_order.py`) re-run and
still passes after these additions.

**A real bug in `pilot_acceptance.py` itself, found only by actually
running it, not by reading the code:** the run JSON's own `result`
dict (whatever `campaign_client_runner.py`'s stdout/`run_once_timed()`
produces) has NEITHER a `"label"` key NOR a `"duration_seconds"` key --
the real field is `t_fluxo_seconds`, and the real per-execution label
has to be reconstructed from the `run{NN}.json` filename's own run
index plus the JSON's `"window"` field
(`f"w{window:02d}_run{run_index:02d}"`, matching `SSHExecutor`'s own
file-naming convention for `.pcap.gz`/`_cpu.jsonl`/`_gateway.log`/
`_ping.json`, which is NOT the same string as the `run{NN}.json`
filename itself). Caught by building a small, structurally real
synthetic pilot-data tree (a real gzipped pcap with a real SYN/SYN-ACK
pair and a hand-built ClientHello record, a real gateway-log JSON
line pair, real `/proc/stat`-shaped samples, a real sha256 manifest)
and running `pilot_acceptance.py` against it end to end -- it crashed
immediately on the wrong assumption, was fixed (`load_runs()` now
derives `(path, run, run_index, label)` from the filename+`window`
field, not a nonexistent `result["label"]`), and then ran clean through
all 9 criteria with no crash. The two criteria that reported FAIL
against the synthetic run (ClientHello size, bootstrap CI width) did so
correctly -- the synthetic fixture's ClientHello is a deliberately
undersized hand-built stand-in (64 bytes, not a real TLS ClientHello),
and its 3 synthetic `t_fluxo_seconds` values genuinely have more than
±5% spread. This is a smoke test against synthetic data, not a
validation against real pilot data (none exists yet, by design -- the
pilot hasn't run) -- stated plainly, not implied otherwise.

**(6) Data-retention rule for the pilot's data, documented in
`PILOT_RUNBOOK.md`** (new section, "Dados do piloto — regra de
retenção"): the pilot's 2-cell, 1-window data counts as window 1 of the
full campaign's own cells ONLY if the measurement protocol doesn't
change afterward (concrete examples given of what does and doesn't
count as a protocol change: `campaign_run.py`/`campaign_client_runner.py`
measurement-logic changes, instance-type changes, delivered-image
changes count; acceptance-script-only bug fixes and unrelated-region
documentation changes don't). If it changes, the pilot's data are
MOVED (never discarded) to
`v8/latency/_pilot-superseded-<date>/`, with a `DECISIONS.md` note
explaining why, and window 1 of those 2 cells restarts clean under the
corrected protocol.

**Open questions, honestly stated:** the flex-launch test and instance-
type choice (this runbook's own precondition) are still outstanding --
`MOCKOPIN_SERVER_CLIENT_INSTANCE_TYPE` still has no default, on
purpose. `pilot_acceptance.py` has been smoke-tested against synthetic
data only; it has never seen real pilot data because the pilot has not
been run yet. No AWS resource was created, modified, or destroyed this
turn.

## 71. tcpdump A/B toggle reworked into a one-by-one alternation with its own `tcpdump_enabled` field; per-instance environment recorded at campaign start and the AMI pinned per region (replacing silent `most_recent` re-resolution); real reference ClientHello pcaps captured against the local stack via `netshoot`, values moved into a fixture `pilot_acceptance.py` reads; the REAL LocalExecutor run for real against the REAL local stack, fed through `pilot_acceptance.py`, catching two more real bugs no amount of reading would have found

A no-AWS-mutation turn again (confirmed throughout -- every AMI ID
below came from a read-only `describe-images` call, every Terraform
command was `validate`/`plan`, no `apply`/`destroy`/launch anywhere).
Five items, in the order asked:

**(1) tcpdump A/B toggle reworked.** `TCPDUMP_SKIP_RUN_INDICES` (an
explicit, arbitrary set of global run indices) is gone, replaced by
`CAMPAIGN_TCPDUMP_AB_TEST` (a single on/off env var) +
`_tcpdump_enabled_for_run()`: off (the default) means every execution
captures, unchanged; on means capture alternates ONE BY ONE across
global run indices (odd ON, even OFF, run 1 always ON so the very
first execution of any cell still has a pcap baseline) instead of an
arbitrary subset, so the pilot's own with/without comparison is
interleaved across the whole run rather than confounded by a block of
consecutive skipped runs. `result["tcpdump_skipped"]` (inverted,
SSHExecutor-only) is gone, replaced by `result["tcpdump_enabled"]`
(same polarity, true=captured) on BOTH executors -- LocalExecutor's
own per-side availability-skip detail is kept under a separately-named
`tcpdump_skip_detail`, not lost, just no longer sharing the one field
`pilot_acceptance.py`'s criterion 7 actually reads. A real capture
failure on an ENABLED run still aborts the block exactly as before
(`_verify_tcpdump_started()`'s own abort path is untouched by this
toggle) -- the toggle only ever decides whether capture is ATTEMPTED,
never whether a failed attempt is tolerated. `pilot_acceptance.py`'s
criterion 7 updated to match. Full test suite re-run, still passes.

**(2) AMI pinned per region; per-instance environment recorded at
campaign start.** Investigated how the AMI is resolved today: a
`data "aws_ami" { most_recent = true, owners = ["amazon"], filter {...}
}` block per region, re-resolved FRESH on every single
`plan`/`apply` -- meaning a real multi-day campaign (settling + 3
windows) could silently land on a DIFFERENT AL2023 build on a later
apply than the pilot used (Amazon publishes new builds roughly
monthly), with Terraform showing it as an ordinary-looking instance
replacement, not flagged as an environment change. Fixed: a real
(read-only) `describe-images` query via boto3 against the
`mockopin-pqc` profile, same filters the old data sources used,
against all 7 x86_64 regions + sa-east-1's arm64 (control) --
`terraform/main.tf`'s `data "aws_ami"` blocks removed entirely,
replaced by a `pinned_ami_x86_by_region`/`pinned_ami_arm64_sa_east_1`
locals map holding the IDs that query returned
(2026-10-20T12:5x UTC, recorded in the map's own comments alongside
each AMI's name/kernel). `terraform validate` passes; a real
`terraform plan` against the pilot's exact 21-resource scope confirms
every `ami` attribute now resolves to a static, known-at-plan-time
value (not `(known after apply)`) matching the pinned map exactly, and
the plan is still `21 to add, 0 to change, 0 to destroy` -- the pin
didn't change what gets built, only how deterministically. Pinning the
AMI doesn't, by itself, prove a given real instance actually booted
from it, so `campaign_run.py` gained `record_environment()`: queried
from INSIDE each instance (control included) via its own IMDSv2 (ami-
id/instance-type/availability-zone-id) plus `uname -r`/`docker
--version`/`chronyd -v`/`rsync --version`, written once per instance
at campaign start to `v8/latency/_campaign-control/environment/
<instance>.json` -- the ground-truth audit trail a later check compares
against the pinned map. The remote probe is a self-contained `python3
-c` script (same pattern as the CPU/mem sampler) so its JSON is built
by `json.dumps()`, never hand-concatenated command output. Smoke-
tested standalone on this dev machine (no real IMDS reachable here,
which the script's own try/except correctly reports as an `"ERROR:
..."` string rather than crashing -- `docker --version`/`uname -r`
came back real, `chronyd`/`rpm` correctly reported absent on Windows);
real AMI/IMDS values remain unverified against an actual EC2 instance,
since none was launched this turn. `PILOT_RUNBOOK.md`'s first-contact
table gained a row checking the recorded environment's `ami_id`
against the pinned map.

**(3) Real reference ClientHello pcaps, captured live, not hand-typed.**
Brought up the local lab stack for real (`docker compose --profile
main up -d`, then `switch_crypto_profile.py` for each profile in turn,
all 5 real settling runs passing for all 3 profiles). For each profile,
ran `tcpdump` inside a `nicolaka/netshoot` container sharing the
gateway container's OWN network namespace (`docker run --network
container:insurance-server-lambdas-mtls-1 ...`, same technique as an
earlier turn's B.13), triggered one real `opin_flow.run_insurance_flow()`
call against the real gateway, and extracted the first TLS
ClientHello's size+SNI from the resulting real pcap via
`pilot_acceptance.py`'s own `find_first_clienthello()`. **Result: 341/
1784/1881 bytes, SNI "mtls" for classic/pqc/hybrid respectively --
exactly the figures already in use**, now confirmed by a real capture
this turn rather than carried over from an earlier session's test.
Values (not the pcaps themselves, per this turn's own instruction)
saved to `tests/fixtures/reference_clienthello.json`, with a `_method`
field documenting exactly how they were captured; `pilot_acceptance.py`
now loads `BASELINE_CLIENTHELLO` from that fixture instead of a
hardcoded dict, and criterion 2 prints the loaded values every run.

**(4) The REAL LocalExecutor, run for real, against the REAL local
stack -- fed through `pilot_acceptance.py`, which caught two more real
bugs.** 2 executions per profile (6 total), via the actual, non-mocked
`LocalExecutor` (`allow_tcpdump_skip=True` -- this Windows dev host has
no Linux `tcpdump` at all) -- real `start_block_proxies()` (real
compose profile switch, real 5-settling-run verification, real
negotiated-group check: classic→CurveP384, pqc→MLKEM1024,
hybrid→SecP384r1MLKEM1024, internal always CurveP256, all correct) +
real `run_one_execution()` x2 + real `stop_block_proxies()`, written to
a temp `DATA_ROOT` (never the real `v8/latency/` tree -- this is a
smoke test, not pilot data). Feeding this real output through
`pilot_acceptance.py` caught two more real bugs neither code reading
nor the earlier synthetic-data smoke test had surfaced:
  1. **Label convention mismatch, criteria 1/2/3/5/8 silently N/A on
     real LocalExecutor data.** `load_runs()` always reconstructed the
     execution label as SSHExecutor's own
     `"w{window:02d}_run{run_index:02d}"` -- but LocalExecutor names
     its OWN per-execution files (`.calls.jsonl`/`_cpu.jsonl`/
     `_gateway.log`/`_ping.json`) as the bare `"run{run_index:02d}"`,
     no window prefix, a genuinely different convention between the
     two executors. `load_runs()` now checks which convention is
     actually ON DISK (via `calls.jsonl`, the one file every execution
     always writes) rather than assuming either one; defaults to the
     SSHExecutor form when neither is found, since the real pilot/
     campaign only ever uses SSHExecutor.
  2. **Criterion 4 crashed outright (`KeyError: 'proc_stat_line'`) on
     real LocalExecutor data.** SSHExecutor's CPU/mem sampler writes
     RAW `/proc/stat`/`/proc/meminfo` TEXT; LocalExecutor's own,
     pre-existing `_sample_cpu_mem_steal()` writes ALREADY-PARSED
     dicts under different key names entirely (`"cpu"`/`"mem"`, each
     `None` on a non-Linux host -- confirmed live: both were `null` on
     this Windows machine, which genuinely has no `/proc`). Fixed with
     `_normalize_cpu_mem_sample()`, handling both schemas, skipping
     (not crashing) a sample pair with no usable `/proc` data.
  After both fixes, re-running against the SAME real data: criteria 1
  and 3 **PASS for real** (bytes-exchanged match the baseline exactly
  for all 3 profiles; negotiated groups correct for all 3); criteria 2/
  4/5 correctly report **N/A** (no pcap, no `/proc` -- both genuine,
  reported limitations of this Windows host running LocalExecutor, not
  bugs); criterion 6 **N/A** (2 runs/profile, needs >=3 for a bootstrap
  CI -- expected, this turn only asked for 2); criterion 7 **PASS**
  (correctly reports a without-tcpdump-only group, no crash); criterion
  8 **PASS** (volume measured and extrapolated for real); criterion 9
  **FAILS**, correctly -- it needs a real `campaign_pull.sh` hash
  manifest, which only a real AWS pilot produces, never a local smoke
  test. Every one of these outcomes is now either a real PASS or an
  honestly-labeled, correctly-explained N/A -- nothing silent, nothing
  fabricated. Full existing test suite re-run afterward, still passes.

**(5) Data-retention rule -- not touched this turn.** Already
documented (Decision 70); no change needed or made.

**Open questions, honestly stated:** `record_environment()`'s real
IMDS/docker/chrony/rsync values remain unverified against an actual
EC2 instance -- no instance was launched this turn to check against.
The pinned AMI map will go stale the moment Amazon ships a new AL2023
build; nothing currently alerts on that automatically -- re-pinning is
a deliberate, manual, documented act by design, not something to
automate away. The flex-launch test and instance-type choice are still
outstanding, unchanged from Decision 70.

## 72. Pinned AMI architecture confirmed by direct `describe-images` lookup (not the original filtered query) for every pilot/campaign region; local lab stack torn down; no more self-scheduled reminders without Luciano's explicit ask

A no-AWS-mutation turn again (every check below is a read-only
`describe-images`/`describe-security-groups`-class call; nothing
applied, destroyed, or launched).

**(1) AMI architecture, re-confirmed independently.** Decision 71
pinned each region's AMI from a filtered `describe-images` query
(`architecture=x86_64`), but a filter applied at CAPTURE time doesn't
by itself prove the captured ID is still, or was ever actually, that
architecture to a reader of the Terraform file alone -- so this turn
re-queried each of the 7 pinned IDs directly BY `ImageId` (not through
the original filter) in its own region, reading the `Architecture`/
`VirtualizationType`/`State` fields straight from AWS: all 7
(`sa-east-1`, `us-east-1`, `ap-northeast-1`, `ca-central-1`,
`eu-north-1`, `ap-southeast-1`, `ap-northeast-2` -- covering both the
pilot's 2 regions, `sa-east-1` and `ap-southeast-1` via `L325`, and the
full campaign's remaining 5) came back `x86_64`/`hvm`/`available`.
Control's own pinned AMI (`sa-east-1`, arm64) was checked the same way
and correctly came back `arm64` -- confirming the ONE intentional
exception (Graviton `t4g.micro`, free-tier, control only) is still
exactly that, not an accidental mismatch.

**(2) Self-scheduled reminders.** Per Luciano's own instruction this
turn, no further `ScheduleWakeup`/similar self-pacing calls will be
made unless he explicitly asks for one. The one made last turn (to
wait out the real LocalExecutor run) was a one-shot, self-consuming
wait for a foreground task already in progress, not a standing
reminder -- nothing recurring was ever scheduled, but the standing rule
going forward is stricter than "nothing recurring": no self-scheduling
at all without an explicit ask.

**(3) Local lab stack torn down.** `docker compose --profile main
down` in `insurance-server-lambdas/` -- confirmed via `docker ps -a`
that no `insurance-server-lambdas-{mtls,auth,mockapi,psql,mongodb,
mongo_seed,localstack}-*` container remains (only long-unrelated,
pre-existing `cs-*` containers from months earlier are still listed,
untouched, out of this turn's scope).

**Open questions:** none new this turn -- the open items already
recorded in Decision 70/71 (flex-launch test, instance-type choice,
`record_environment()` unverified against a real EC2 instance) remain
unchanged.

## 73. Flex launch test run for real (14 instances, 7 regions) -- both types pass everywhere; Luciano's choice registered: `m7i-flex.large` for all 11 server/client instances, `t4g.micro` for control; Decision 29's open question answered ONLY for the two free-tier flex types; pilot `terraform plan` shown with the chosen type, not applied

Luciano present, budget alert and credit balance confirmed by him before
anything touched AWS (standing precondition). The launch test itself
(apply, measure, destroy) is covered here in full since it was never
written to this log at the time it ran -- Luciano reviewed the results
in chat first and asked for this Decision afterward, once he'd chosen.

**Method, exactly as fixed by Luciano before the apply, never adjusted
after seeing data:** 14 real instances (`m7i-flex.large` and
`c7i-flex.large`, 7 regions -- the 3 server regions `sa-east-1`/
`us-east-1`/`ap-northeast-1` plus the 4 client regions `ca-central-1`/
`eu-north-1`/`ap-southeast-1`/`ap-northeast-2`), AZ pinned by ID (the 3
server regions to the exact IDs Luciano named -- `sae1-az1`/`use1-az1`/
`apne1-az1`; the 4 client regions to the first AZ ID, per a real
`describe-instance-type-offerings` query, that actually offers BOTH
flex types). Same command on every instance (confirmed both types have
exactly 2 vCPUs first): `stress-ng --cpu 2 --timeout 20s --metrics-brief`.
Per instance: >=3 bursts at the start (the median's dispersion
`(max-min)/median` had to be <=5% or the whole set of >=3 bursts
repeated, capped at 2 repeats -- still >5% after that stays
INCONCLUSIVE, neither pass nor fail), a real wait of >=10 minutes, then
>=3 more bursts. Thresholds, fixed before the apply and never moved:
**steal > 5% in ANY single measurement fails the type in that region;
throughput drop > 10% (median of the start bursts vs. median of the
end-of-wait bursts) fails it; initial dispersion > 5% is inconclusive.**
A 90-minute self-terminate safety net (`shutdown -h +90` +
`instance_initiated_shutdown_behavior = "terminate"` +
`delete_on_termination = true` made explicit) was added to every
instance independent of the orchestrating script actually reaching its
own `terraform destroy` -- never triggered; every instance was torn
down in ~37 minutes, well inside the margin.

**Column-sign correction, registered here because it was reported
backwards in chat before this Decision was written:** the "throughput
drop" figure is `(median_start - median_end) / median_start x 100`.
**Positive is a REAL drop in throughput; negative is an INCREASE**
(the end-of-wait median came back higher than the start -- unremarkable
for a short CPU-bound synthetic load, not evidence of anything wrong).
Reading negative numbers as if they were drops, which is how the first
chat report of this table implicitly read, would have been exactly
backwards.

**Real results (all 14, final, after one single-instance re-run --
see below):**

| Region (AZ ID) | Type | Attempts | Max steal | CPU start/end | Throughput start/end (bogo-ops/s, median) | Drop (+) / Increase (-) | Verdict |
|---|---|---|---|---|---|---|---|
| sa-east-1 (sae1-az1) | m7i-flex.large | 2 | 0.025% | 100.0%/100.0% | 2520.3 / 2527.2 | -0.27% | PASS |
| sa-east-1 (sae1-az1) | c7i-flex.large | 1 | 0.000% | 100.0%/100.0% | 2469.2 / 2464.9 | +0.17% | PASS |
| us-east-1 (use1-az1) | m7i-flex.large | 1 | 0.000% | 100.0%/100.0% | 2589.4 / 2686.4 | **-3.75%** (largest increase) | PASS |
| us-east-1 (use1-az1) | c7i-flex.large | 1 | 0.000% | 100.0%/100.0% | 2602.8 / 2621.9 | -0.73% | PASS |
| ap-northeast-1 (apne1-az1) | m7i-flex.large | 1 | 0.000% | 100.0%/100.0% | 2802.5 / 2793.6 | +0.32% | PASS |
| ap-northeast-1 (apne1-az1) | c7i-flex.large | 1 | 0.000% | 100.0%/100.0% | 2730.2 / 2704.1 | **+0.96%** (largest real drop) | PASS |
| ca-central-1 (cac1-az1) | m7i-flex.large | 1 | 0.000% | 100.0%/100.0% | 2457.5 / 2454.2 | +0.14% | PASS |
| ca-central-1 (cac1-az1) | c7i-flex.large | 1 | 0.000% | 100.0%/100.0% | 2710.9 / 2691.4 | +0.72% | PASS |
| eu-north-1 (eun1-az1) | m7i-flex.large | 1 | 0.000% | 100.0%/100.0% | 2786.5 / 2829.3 | -1.54% | PASS |
| eu-north-1 (eun1-az1) | c7i-flex.large | 2 | 0.000% | 100.0%/100.0% | 2934.2 / 2932.9 | +0.04% | PASS |
| ap-southeast-1 (apse1-az1) | m7i-flex.large | 1 | 0.000% | 100.0%/100.0% | 2679.0 / 2746.2 | -2.51% | PASS |
| ap-southeast-1 (apse1-az1) | c7i-flex.large | 1 | 0.450% (max steal overall) | 100.0%/100.0% | 2459.2 / 2467.2 | -0.33% | PASS |
| ap-northeast-2 (apne2-az2) | m7i-flex.large | 1 | 0.000% | 100.0%/100.0% | 2701.8 / 2743.0 | -1.53% | PASS |
| ap-northeast-2 (apne2-az2) | c7i-flex.large | 2 | 0.000% | 100.0%/100.0% | 2909.4 / 2910.6 | -0.04% | PASS |

**All 14 PASS, no exceptions, both types, every region.** Max steal
overall: 0.450% (less than a tenth of the 5% fail threshold). Largest
REAL drop: **0.96%** (`c7i-flex.large`, `ap-northeast-1`) -- under a
tenth of the 10% fail threshold. Largest INCREASE: **3.75%**
(`m7i-flex.large`, `us-east-1`). **3 of the 14 instances needed one
repeat of the initial measurement** (dispersion > 5% on the first
attempt): `sa-east-1`/`m7i-flex.large`, `eu-north-1`/`c7i-flex.large`,
`ap-northeast-2`/`c7i-flex.large` -- all 3 came back under 5% on the
second attempt, none exhausted the 2-repeat cap, none ended up
INCONCLUSIVE.

**One real infrastructure hiccup, handled, not hidden:** the first
attempt's `eu-north-1`/`m7i-flex.large` pair hit a transient SSH timeout
(unrelated to steal/throughput) and was re-run alone, on the SAME
already-running instance, before teardown -- its real result (PASS) is
what's in the table above.

**Three real bugs found by actually running this, not by reading the
code, all fixed before they cost meaningful time or money:**
1. `aws_instance.availability_zone` takes an AZ NAME
   ("sa-east-1a"), not an AZ ID ("sae1-az1") -- the first real apply
   failed all 14 instances on this. Removed; `subnet_id` (already
   filtered to the right AZ ID via a dedicated `data.aws_subnets`
   lookup) fully determines the AZ on its own.
2. `json.dumps()` is not shell quoting -- using it (instead of
   `shlex.quote()`, this project's own established pattern) to build a
   remote `python3 -c` command made the remote shell see literal `\n`
   two-character sequences instead of real newlines. Caught testing
   against one real instance before running the full 14-instance test.
3. `terraform output -json <name>` (a NAMED output) returns the raw
   value directly -- no `{"value": ...}` wrapper, unlike the no-name
   form. Caught on the very first run attempt, before any instance was
   touched.

**Luciano's choice, registered:** **`m7i-flex.large` for all 11
server/client instances** (both types passed everywhere, so Decision
43's own fallback -- "use one instance type uniformly across every
installation" -- applies cleanly); **`t4g.micro` for the control
instance** (already the Terraform default, free-tier, never runs the
measured workload).

**Memory, confirmed against AWS's own official documentation, not just
the API:** `docs.aws.amazon.com/ec2/latest/instancetypes/gp.html` (general
purpose) lists `m7i-flex.large` at 2 vCPU / **8 GiB** (4:1 memory:vCPU
ratio for the whole M7i-flex family);
`docs.aws.amazon.com/ec2/latest/instancetypes/co.html` (compute
optimized) lists `c7i-flex.large` at 2 vCPU / **4 GiB** (2:1 ratio) --
both match the `describe-instance-types` figures already queried
(8192/4096 MiB). **Compared against the local stack's own measured peak
memory** (server-side containers' combined peak, under real automated
flow execution, all 3 profiles: ~1.03GiB -- `mockapi` 673MiB + `auth`
93MiB + `mongodb` 198MiB + `mtls` 19MiB + `psql` 72MiB; client-side
`tls_kem_proxy` peak 281MiB + `pqc_signer_service_run` 24MiB ~ 305MiB):
**`m7i-flex.large`'s 8GiB leaves ample headroom on EITHER side** -- the
server-side peak uses about 13% of it, the client-side peak about 4%.

**Decision 29's open question -- answered ONLY for the flex types,
registered explicitly so it isn't mistaken for a broader answer.**
Decision 29 asked whether this account's free-tier restriction also
blocks the BIGGER, non-free-tier types Decisions 14/18/21 had
recommended (`m6i.large`, `c6i.xlarge`, `c5.2xlarge`) -- this launch
test never touched any of those three; it only confirms the two
free-tier-eligible flex types (`m7i-flex.large`/`c7i-flex.large`) launch
and perform fine everywhere needed. Decision 29's own question, about
the bigger types, remains exactly as open as it was.

**Cost estimate, instance-hours, for Luciano to compare against the
real bill:** real launch/terminate timestamps (`describe_instances`,
`StateTransitionReason`), not assumed -- all 14 instances ran
17:54:3x-18:31:5x UTC, **2026-10-20**, ~37m9s each. Total: **4.334
instance-hours of `m7i-flex.large` + 4.333 instance-hours of
`c7i-flex.large` = 8.667 instance-hours** across the 14 instances. This
project's own restricted IAM profile cannot reach the AWS Pricing API
(`pricing:DescribeServices` -- `AccessDeniedException`, consistent with
Decision 44's finding that billing-adjacent APIs are denied) and AWS's
own on-demand pricing pages are JS-rendered, same limitation Decision 44
already hit -- so, same as that decision's own precedent, a
secondary-sourced estimate: **us-east-1 on-demand rates of $0.0958/hr
(`m7i-flex.large`) and $0.0848/hr (`c7i-flex.large`)**, per
calculator.holori.com (a third-party pricing aggregator, pages last
updated 2026-09-09 and 2026-09-16 respectively -- not AWS's own
published number, checked here because AWS's own page didn't return a
number directly). Applying these us-east-1 rates uniformly to all 8.667
instance-hours gives **~$0.78** total; 6 of the 7 regions actually used
are typically priced above us-east-1 for compute (commonly 15-40%
higher), so a more realistic order-of-magnitude range is **~$0.80-$1.00
total** for the whole test. Stated as an estimate to compare against the
real bill, not a committed figure.

**Raw results saved, not just reported in chat:**
`v8/latency-discovery/aws-flex-launch-test-raw/flex_launch_test_results.json`
(all 14 instances' full per-burst data -- real UTC timestamps, real
`/proc/stat` deltas, real `stress-ng` output, real AMI ID/AZ ID/kernel/
tool version per instance, scanned for secrets/account identifiers
before being saved) + its own `README.md` explaining the schema and the
sign convention above.

**`MOCKOPIN_SERVER_CLIENT_INSTANCE_TYPE` set in
`campaign.vars.example.sh`** to `m7i-flex.large` -- the Terraform
variable itself (`server_client_instance_type`) KEEPS no default, on
purpose, still (Decision 52): only the example script's own value
changed, so a bare `plan`/`apply` still fails loudly if nobody passes a
value in for that specific run. **Pilot `terraform plan` shown with the
chosen type** (`sa-east-1` only: server + `L0` + `L325` clients +
control) -- `Plan: 21 to add, 0 to change, 0 to destroy`, the same
21-resource scope as every prior pilot plan, now with `m7i-flex.large`
on the 3 workload instances and `t4g.micro` (unchanged) on control.
**Not applied** -- read-only `plan` only, consistent with this turn's
own no-AWS-mutation instruction.

**A second account-ID exposure this session, disclosed the moment it
happened:** the `pricing:DescribeServices` `AccessDeniedException`
above printed this project's full IAM ARN, account ID included, in a
tool-call result -- an AWS-generated error message, not something
requested, but foreseeable (IAM denial messages always include the
full ARN) and should have been anticipated/filtered. Flagged to Luciano
immediately; the value was never written to any file and is not
reproduced here.

**Open questions:** Decision 29's bigger-type question (`m6i.large`/
`c6i.xlarge`/`c5.2xlarge`) remains unresolved -- untouched by this test.
The flex-launch-test Terraform changes (AZ pinning, shutdown safety net,
the `availability_zone` bugfix) were deliberately left uncommitted the
turn the test itself ran ("não commita," that turn's own instruction,
while Luciano was still reviewing results) and are committed THIS turn
instead, now that he's chosen.

## 74. Software-inventory audit, per role -- found and fixed three gaps that would each have failed the real campaign outright on first contact (a Python-3.9 import-time crash on EVERY execution, no delivery mechanism at all for the two client-only crypto images, no delivery mechanism at all for `insurance-server-lambdas`/`thesis/scripts`/`mock-service-os`); two more real-but-survivable gaps (fictional pip-version pins, bare remote command names that may not resolve in a non-login SSH session); an AWS-error redaction filter; pilot `terraform plan` reconfirmed 21/0/0

A no-AWS-mutation turn (every finding below came from a real
`amazonlinux:2023` container -- x86_64 AND arm64 -- or from reading
`campaign_run.py`'s own remote commands literally; nothing applied,
destroyed, or launched). Four items, in the order asked, but the
findings turned out far more serious than a routine audit -- three of
them are the kind of gap that fails 100% of real executions, not a
conditional edge case.

### Item 1 — per-role software inventory

| Role | Needs | How it reaches the instance (before this turn) | How it reaches the instance (now) |
|---|---|---|---|
| **All three** | `docker`, `rsync`, `chrony`(`chronyc`), `tcpdump`, `ping`(iputils), `ss`(iproute), `flock`(util-linux-core), `python3-pip` | `docker`+`rsync` only (Decision 71) -- the other 6 were MISSING from the AL2023 **minimal** AMI (confirmed empirically: a real `amazonlinux:2023` container has only `python3` and `curl` out of the box) and campaign_run.py already calls `chronyc`/`ping`/`flock`/`tcpdump` remotely by bare name, with no install step and no abort-on-missing guard for 4 of those 5 | `templates/install_common_packages.sh` (renamed from `install_docker_and_rsync.sh`), one `dnf install`, all 3 roles, unconditional |
| **Server** | `insurance-server-lambdas/` (`docker-compose.yml` + `participants.json`/`software_statement.json`/`mongod.conf`/`pg_hba.conf`), `mock-service-os/` (`certs/`+`ssa/`+`setup_ssm.sh`), `thesis/scripts/*.py` (for `switch_crypto_profile.py`'s own settling calls, which import `opin_flow.py`) + its pip deps, the 4 custom server docker images | Docker images only, via `deliver_images.sh` -- **nothing ever shipped the compose file, the config files, or the Python source at all**; confirmed by reading `start_block_proxies()`'s own remote command literally: `cd insurance-server-lambdas && ... python3 ../thesis/scripts/switch_crypto_profile.py` -- that directory never existed on a real server | New `deliver_source.sh` (operator → control → every server AND client, same relay `deliver_images.sh` already uses) + `deliver_images.sh` |
| **Client** | `thesis/scripts/*.py` + its pip deps, `mock-service-os/certs/` (own client cert), the precompiled `tls_kem_proxy` image, the `mockopin-pqc-signer` image | Same gap as the server's Python source, PLUS: **neither crypto image had any delivery mechanism to a client, ever** -- `mockopin-pqc-signer` has no auto-build fallback in `opin_flow.py` at all (a missing image just fails `docker run` outright); `mockopin/tls_kem_proxy:precompiled` DOES auto-build on demand, but only when `TLS_KEM_PROXY_USE_PRECOMPILED=1`, which `SSHExecutor` never set -- every real remote pqc/hybrid execution was defaulting to `go run .` against a Go source directory that was never shipped either | `deliver_source.sh` (Python source + certs) + `deliver_images.sh`'s new `CLIENT_IMAGES` list (`mockopin-pqc-signer`, `mockopin/tls_kem_proxy:precompiled`) + `campaign_run.py`'s `_REMOTE_CLIENT_ENV()` now sets `TLS_KEM_PROXY_USE_PRECOMPILED=1` on every remote client invocation |
| **Control** | `python3` (stdlib only -- `campaign_run.py` has no pip dependency), `rsync` (operator→control leg of image/source delivery), `systemd` (runs `campaign_run.py` as a service) | Already covered (Decision 71) | Unchanged |

**Two more real, previously-undocumented bugs found while building the
fix, both corrected:**
- `cd insurance-server-lambdas && ... python3 ../thesis/scripts/switch_crypto_profile.py`
  (server-side) and `python3 campaign_client_runner.py` (client-side, no
  `cd` at all) assumed TWO DIFFERENT directory layouts -- the server's
  own relative path (`../thesis/scripts/`) only resolves correctly if
  `thesis/scripts/` and `insurance-server-lambdas/` are siblings under
  `~`, while the client's bare invocation assumed `campaign_client_runner.py`
  sits directly at `~` -- but `opin_flow.py` (which it imports) computes
  `CERTS_DIR` from ITS OWN file location assuming the real repo's
  nesting (`thesis/scripts/` two levels under the tree root), which
  contradicts a flat `~` layout. Resolved by mirroring the repo's own
  relative nesting under `~` on every instance (`~/thesis/scripts/`,
  `~/insurance-server-lambdas/`, `~/mock-service-os/`) and adding the
  one missing `cd ~/thesis/scripts &&` to all 4 of `campaign_run.py`'s
  own remote client-invocation sites (settling, warmup, the real
  execution, and the detached proxy-start call) -- zero changes to
  `opin_flow.py`'s own path computation, which was already correct for
  this layout.
- `deliver_images.sh`'s per-image distribution loop was hardcoded to
  `inv["servers"]` -- generalized into `deliver_image_set()`,
  parameterized by inventory key, called once for `IMAGES`→`servers`
  and once for the new `CLIENT_IMAGES`→`clients`.

### Item 2 — AL2023's real Python, and the single most severe finding this audit turned up

**Confirmed via AWS's own official documentation**
(`docs.aws.amazon.com/linux/al2023/ug/python.html`): AL2023's
`/usr/bin/python3` is Python **3.9**, for the whole life of the AMI, by
design (newer versions are available side by side, namespaced, but
3.9 is what every bare `python3` invocation this project's own remote
commands use actually gets).

**Then confirmed live, not assumed:** a real `import opin_flow` inside
a real `amazonlinux:2023` container running real Python 3.9.25 crashed
immediately, at MODULE LEVEL, before any function could even be
called:
```
File "opin_flow.py", line 437, in <module>
    _PQC_SIGNER_SERVICE_URL: str | None = None
TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
```
PEP 604's `X | Y` union-type syntax (also used in 3 function
signatures in the same file) is a Python 3.10+ feature -- `opin_flow.py`
has no `from __future__ import annotations`, so Python 3.9 tries to
evaluate `str | None` as a real expression instead of deferring it to
a string, and `str.__or__` doesn't exist yet. **This is the single
worst gap this audit found: it would have failed EVERY real execution
of the real AWS campaign, on every client, for every profile including
classic -- not a conditional failure like the crypto-image gaps above,
a universal one, on first contact.** `campaign_client_runner.py` (run
on every client) imports `opin_flow.py` directly; so does
`switch_crypto_profile.py` (now also run on every server, per item 1
above).

**Fixed with one line** (`from __future__ import annotations`, PEP
563, at the top of `opin_flow.py`, before any other import) --
confirmed live, the SAME real Python 3.9 container, that `import
opin_flow` now succeeds, and that `latency_automation`/
`campaign_client_runner`'s own transitive imports succeed too.
`campaign_run.py` and `pilot_acceptance.py` (control's own scripts, no
`opin_flow` dependency) were ALSO confirmed importable under real
Python 3.9 on BOTH x86_64 and arm64 (control's own architecture) --
neither needed any change; grepping the same union-type pattern across
every other file in scope (`campaign_run.py`, `pilot_acceptance.py`,
`latency_automation.py`, `campaign_client_runner.py`,
`baseline_automation.py`, `switch_crypto_profile.py`) found zero other
occurrences.

**pip dependencies, also confirmed on both architectures:** all 6 of
`thesis/scripts/requirements.txt`'s packages install cleanly (prebuilt
manylinux wheels, no compiler needed) under real Python 3.9 on BOTH
x86_64 and arm64, and `opin_flow`/`latency_automation`/
`campaign_client_runner` all import successfully afterward -- but two
of the six EXACT pinned versions (`requests==2.34.2`, `urllib3==2.7.0`)
**do not exist on the real PyPI** (confirmed by actually trying to
`pip download` each exact pin individually, not assumed from a batch
failure) -- `pip install -r requirements.txt` would have failed
outright on any fresh real client instance. Fixed: all six pins
updated to the latest REAL versions confirmed to both exist and
install together cleanly (`requests==2.32.5`, `PyJWT==2.15.1`,
`cryptography==50.0.2`, `pyOpenSSL==26.4.0`, `urllib3==2.6.3`,
`rfc8785==0.1.4`) -- `pyOpenSSL` kept (it IS real, and `opin_flow.py`'s
own try/except around `urllib3.contrib.pyopenssl` still wants it
available when possible, even though it degrades gracefully without
it).

### Item 3 — AWS error messages, redacted

A real incident this session (an `AccessDeniedException` from a denied
`pricing:DescribeServices` call printed this project's full IAM ARN --
account ID included -- in a tool result) showed that AWS-sourced error
text cannot be trusted to never mention the account ID, even though
nothing asked it to. New `redact_aws_errors.py`: masks any `arn:aws:...`
token and any standalone 12-digit number (AWS account IDs are always
exactly 12 digits), line-buffered so it's safe to pipe a live,
streaming command through without losing real-time visibility. Wired
into every AWS-adjacent command whose error output this project's own
scripts already surface to a human: `campaign_up.sh`'s two
`terraform apply` calls, `campaign_down.sh`'s `terraform destroy` call
and its own boto3 teardown-verification block (wrapped in a
`try`/`except botocore.exceptions.ClientError` that redacts the
exception text before it's ever printed or raised). `pipefail` (already
set in both scripts) means a failing `terraform` call still fails the
script despite now being the first stage of a pipeline.

**A related, not-yet-fully-settled finding:** every bare remote
command this project issues for a tool living in `/usr/sbin`
(`tcpdump`, `ping`, `ss`) or relying on PATH at all (`flock`,
`chronyc`) assumed a non-login `ssh host "cmd"` session sources
`/etc/profile`'s own non-root `pathmunge ... after` addition of
`/usr/sbin`/`/usr/local/sbin` -- confirmed AL2023 DOES add that for a
LOGIN shell, but a plain non-interactive `ssh host "cmd"` (what every
SSH call in this project actually is) is NEITHER interactive NOR a
login shell by default, and this could not be fully confirmed one way
or the other without a real EC2 sshd session to test against (not
available this no-AWS-mutation turn). Hardened anyway, at zero
ongoing cost: every one of `campaign_run.py`'s own bare invocations of
these tools (`server_flock_wrap()`, the tcpdump start command, the
reference-ping and chronyc-tracking calls) now uses the absolute path
(`/usr/bin/flock`, `/usr/sbin/tcpdump`, `/usr/sbin/ping`,
`/usr/bin/chronyc`) instead of trusting PATH -- same fix applied to
`campaign_up.sh`'s own `chronyc tracking` connectivity check. This
remains an OPEN finding in the sense that the underlying PATH question
was never conclusively answered on a real instance -- but the fix
removes any dependency on the answer either way.

### Item 4 — pilot `terraform plan`, reconfirmed

After every change above (`install_common_packages.sh` rename,
`main.tf`'s locals update), `terraform validate` passes and a real
`terraform plan` against the pilot's exact scope (`sa-east-1` only,
`L0`+`L325` clients, control) still shows **`Plan: 21 to add, 0 to
change, 0 to destroy`** -- unchanged from every prior pilot plan this
session. Not applied.

**Open questions, honestly stated:** none of today's fixes have been
run against a real EC2 instance yet -- every confirmation is a real
Python 3.9/pip/dnf test inside a real `amazonlinux:2023` container
(x86_64 and arm64), not a real AWS boot. The PATH question for
non-login SSH sessions (item 3) was hardened around, not resolved.
`deliver_source.sh` has not been rehearsed live (no 3-container
rehearsal this turn, unlike `deliver_images.sh`'s own Decision 67/69
rehearsals) -- its tar/rsync logic was verified by actually building
the real tarball from this real repo and inspecting its contents, not
by a live SSH round trip. The flex-type gap from Decision 73
(`m6i.large`/`c6i.xlarge`/`c5.2xlarge` never tested) remains open.

## 75. Full integrated rehearsal, real `amazonlinux:2023` containers from scratch -- found and fixed three more real gaps (`tar`, `python3-pip`, `docker compose` entirely missing from AL2023's own repos); a DooD-vs-DinD architecture correction found mid-rehearsal; Docker Desktop's own engine crashed under the combined load before the rehearsal reached a clean cycle; readiness-marker/hash-pinned-deps/digest-pinned-images/PILOT_RUNBOOK fixes completed without Docker; remaining rehearsal deferred to after Luciano restarts Docker Desktop

A no-AWS-mutation turn. The integrated rehearsal Luciano asked for
(real `amazonlinux:2023` containers, one per role, nothing
pre-installed, the full real sequence: init script → `deliver_source.sh`
→ `deliver_images.sh` → profile switch → client proxy → settling →
warmup → real executions → `campaign_pull.sh`) got further than any
prior rehearsal this project has run -- real user-data, real source/
image delivery, a real attempted profile switch -- before Docker
Desktop's own engine failed outright and the session had to stop.
Everything found and fixed before that point is real; everything after
is deferred, explicitly, to a fresh cycle once Luciano restarts Docker
Desktop (this turn's own instruction).

**Setup: 3 real containers, nothing pre-installed.** `control` on
**arm64** (`--platform linux/arm64`, QEMU-emulated on this x86_64 dev
machine) -- `openssh-server` installed and ran successfully there,
confirming arm64 itself is not a blocker for anything control needs.
`server`/`client` on x86_64. Real `ec2-user` + real sshd + a freshly
generated keypair on all three -- no stand-in scripts, unlike the
project's own earlier B.11 rehearsal (Alpine-based, fake
`switch_crypto_profile.py`/`campaign_client_runner.py`) -- this turn's
own point was to run the REAL ones.

**Three more real, previously-undiscovered gaps, found by actually
running the real init script in a real container, not by reading it:**
1. **`tar` is missing from the AL2023 minimal AMI.** `deliver_source.sh`'s
   own extraction step (`tar -xzf ~/mockopin-source.tar.gz`) failed
   outright, "tar: command not found", on the very first real attempt.
2. **`python3-pip` is missing too.** `deliver_source.sh`'s own last
   step (`pip3 install --user -r requirements.txt`) would have failed
   the same way immediately after.
3. **`docker compose` (the v2 CLI plugin) does not exist as ANY dnf
   package on AL2023 at all** -- `dnf search compose` returns nothing
   relevant; `dnf install -y docker` installs the engine and CLI, never
   the compose plugin. `switch_crypto_profile.py`'s own `docker compose
   up -d --force-recreate ...` (every real profile switch, every
   settling sequence, on every real server) would have failed on the
   very first attempt with `'compose' is not a docker command` --
   caught live, the first time this rehearsal actually tried to switch
   a profile for real, not by reading the code. **This would have
   failed the entire real campaign outright, unconditionally, on
   literally the first thing it does after booting** -- the same
   severity class as Decision 74's Python-3.9 crash.

All three fixed in `install_common_packages.sh`: `tar`/`python3-pip`
added to the existing `dnf install` line; `docker compose` installed
from the official `docker/compose` GitHub release (`v5.6.0`), pinned
by exact version and sha256 -- **both the x86_64 and aarch64 release
assets were actually downloaded and re-hashed this turn** (not copied
from GitHub's own published `.sha256` file and trusted) to confirm the
pin before it ever shipped: `docker-compose-linux-x86_64` ->
`40343e21ca777173e69cff5dbafeb37c6f81f3b0d57d9e597f036e95eb63e76a`,
`docker-compose-linux-aarch64` ->
`733ec76717ceb59052a9609b9dadfb523b2df8eab57a54212872d10a58078ea2`.
Gated to x86_64 only, confirmed this turn by Luciano: arm64 means
control in this project's topology, and control never runs `docker
compose` (only `switch_crypto_profile.py` does, always on a server) --
installing a binary control will never use would repeat the same
unexamined "install everywhere" habit this file's own Decision 71
rationale otherwise argues FOR being careful about.

**An architecture correction found mid-rehearsal, not assumed:** the
first attempt mounted the HOST's own docker socket into `server`/
`client` ("DooD", Docker-outside-of-Docker) so they could reuse this
project's own already-built images without rebuilding. That works fine
for `deliver_images.sh` (`docker save`/`docker load`, entirely
self-contained image content, no host-path dependency) -- **but
`docker-compose.yml`'s own BIND MOUNTS (`../mock-service-os/certs/...`,
etc.) are resolved by the engine that actually executes them, which
under DooD is the HOST's daemon, against the HOST's OWN filesystem, not
the rehearsal container's.** The real symptom, confirmed live: `cp: -r
not specified; omitting directory '/certs-src/mongo.pem'` inside
`mongodb`'s own entrypoint -- Docker silently creates an empty
directory for a bind-mount source that doesn't exist at the resolved
(host) path, instead of erroring, so every cert/config bind mount
quietly became an empty directory, and `auth`/`mtls`/`mockapi`/
`mongodb` all failed for different downstream reasons (`EISDIR`
reading a JWKS file that was actually a directory; "Could not fetch
ssa_jwk from S3"; `UnknownHostException: psql` because `psql` was never
created at all). **Fixed by switching to real DinD** (`--privileged`
containers, `dockerd` started directly inside each, no shared host
socket) -- bind-mount paths then resolve against the SAME container
that's running `docker compose`, exactly like a real EC2 instance's own
single-machine daemon would. `deliver_source.sh`/`deliver_images.sh`
both re-ran clean against the corrected DinD setup afterward, before
the crash below.

**Docker Desktop's own engine crashed under the combined load, before
a clean cycle was reached.** Observed, in order: `docker stats`/`docker
inspect` against the rehearsal containers started returning `request
returned 500 Internal Server Error` from `dockerDesktopLinuxEngine`;
`docker ps`/`docker version --format` (no container-specific target at
all) then failed the same way; by the time Luciano was consulted, EVERY
Docker API call was failing with 500, not just slow. Restarting Docker
Desktop's own processes (`Docker Desktop.exe`, `com.docker.backend`)
did not bring the engine back within a reasonable wait -- Luciano's own
PC needed a full reboot. **Likely cause, stated as an analysis, not a
proven root cause** (no Docker Desktop diagnostic bundle was captured
before restarting, so this is inference from direct observation, not a
confirmed log entry): two REAL nested `dockerd` instances (server's and
client's own DinD, each independently pulling/loading the full
MockOPIN image set -- `postgres`/`mongo`/`localstack` pulled fresh,
plus 6 custom images `docker load`ed) running concurrently, one
QEMU-emulated arm64 container active at the same time, and several
hundred MB of image tarballs moving through nested SSH/scp hops
(operator→control→server, operator→control→client) -- all sharing ONE
WSL2 VM that also already hosted the host's own pre-existing, unrelated
containers (`componente-siga-cypress`, `siga-core`, etc.). **Resource
limits actually in effect:** no `.wslconfig` override exists on this
machine, so WSL2 used its own default memory/CPU ceiling (no explicit
`MemoryMiB`/`CPUs`/`DiskSizeMiB` keys in Docker Desktop's own
`settings-store.json` either) against this host's real 32GiB of total
physical RAM -- i.e., not an artificially tight limit, genuine
concurrent resource pressure from running two full real Docker
daemons' worth of image storage/compose orchestration simultaneously,
on top of the host's own existing container workload sharing the same
VM. Docker Desktop was restarted (processes killed and relaunched) with
Luciano's explicit confirmation beforehand, since it affects every
other container on this machine, not just the rehearsal's own three.

**Completed without Docker, this turn, per Luciano's own instruction
to keep working on what didn't need it:**
1. **Readiness marker.** `install_common_packages.sh` writes
   `/var/lib/mockopin-ready` (a UTC timestamp) as its own LAST line --
   reachable only if every earlier line succeeded, since `set -euo
   pipefail` is already line 2. `campaign_run.py` gained
   `verify_ready_marker()`, called first thing in `main()` (before
   `record_environment()`/`renew_safety_timers()`, which would
   otherwise fail with a confusing SSH/command-level error against a
   half-booted instance) -- checks the local file for control, SSH for
   every server/client, and aborts loudly, naming every instance
   missing the marker, not just the first one found.
2. **`pip install --require-hashes`.** `thesis/scripts/requirements.txt`
   now carries a real sha256 per wheel for all 6 direct dependencies
   AND their 6 transitive ones (`certifi`, `charset-normalizer`, `idna`,
   `typing-extensions`, `cffi`, `pycparser`) -- 18 hashes total, one set
   captured from a REAL `pip download --platform ... --python-version
   3.9.25 --implementation cp --abi cp39` run for x86_64 and another for
   aarch64 (not guessed from PyPI's web UI). Pure-Python wheels resolve
   to the identical file -- confirmed by actually diffing the hashes,
   not assumed -- on both architectures; `cryptography`/`cffi`/
   `charset-normalizer` compile native code and get a real, different
   hash per architecture, both listed per package.
   `deliver_source.sh`'s own `pip3 install` line now passes
   `--require-hashes`.
3. **Base images pinned by digest** -- every one confirmed via a real,
   live query against Docker Hub's own public registry API (not
   copied from a cached/remembered value): `insurance-server-lambdas/Dockerfile`
   (`gradle:5.3.1-jdk11-slim`, `amazonlinux:2`, both previously
   unpinned, vendored third-party code this project builds but has
   pinned base images for elsewhere already, e.g. `mock_mtls`'s own
   golang pin, for exactly this reproducibility reason);
   `mock-service-os/mock_as/Dockerfile` (`node:24-alpine`, previously
   unpinned -- a real inconsistency, since its sibling `pqc-signer`/
   `tls_kem_proxy` Dockerfiles already pinned the same base image
   family); `mock-service-os/mock_as/mongo-seed/Dockerfile` (bare
   `FROM mongo`, previously unpinned); `thesis/scripts/tls_kem_proxy/Dockerfile`'s
   own runtime stage (`alpine:3.20`, previously unpinned -- only its
   OWN builder stage was already pinned); and
   `insurance-server-lambdas/docker-compose.yml`'s three directly-pulled
   stock images (`postgres:16`, `mongo:latest`, `localstack/localstack:4.0`).
   **Deliberately NOT pinned, scoped out:** `docker-compose.yml`'s
   `cs-server`/`cs-httpd`/`cs-builder` services (`openjdk:17-jdk-slim`,
   `maven:3-openjdk-17`) -- these are the Conformance Suite's own
   profile (`cs`/`build-only`), never created by the real campaign
   (which only ever runs `--profile main`), out of scope for a
   reproducibility concern about the measured experiment itself.
4. **`PILOT_RUNBOOK.md`'s first-contact table gained its own first
   row**, literally first in reading order: `which chronyc tcpdump
   flock ping ss python3 docker` on every instance including control,
   before any of the more specific checks below it -- any single tool
   missing aborts immediately (already covered by the section's own
   pre-existing "any row fails -> abort" rule), with a pointer to check
   `install_common_packages.sh`'s own `cloud-init-output.log` rather
   than guessing why.

**"Depois do piloto" / resume-after-Docker-restart list, in the exact
order Luciano specified:**
- Only server+client in x86_64 DinD this time (control's arm64 is
  already validated -- no need to re-run it under emulation again).
- One DinD container at a time, loading images and cleaning between
  stages, `docker system df` checked before and after each -- avoiding
  this turn's own failure mode (everything running concurrently at
  once).
- Full real sequence: `deliver_source.sh` → `deliver_images.sh` →
  real profile switch on the server → real client proxy start → 5 real
  settling executions → warmup → a few real executions per profile →
  `campaign_pull.sh` with its manifest verified.
- Confirm `opin_flow.py`/`campaign_client_runner.py` run a COMPLETE
  FLOW (not just import, which Decision 74 already confirmed) under
  real Python 3.9.
- Rehearse `deliver_source.sh` the same way `deliver_images.sh` was
  rehearsed (Decision 67/69) -- including a real interruption and
  resume.
- Fix whatever's found, stop after ONE clean cycle -- anything left
  over becomes its own "after the pilot" list, not solved by
  over-running this same rehearsal indefinitely.

**Open questions, honestly stated:** the Docker Desktop crash's root
cause is inference from direct observation (the 500 errors appeared
once DinD+QEMU+transfer concurrency peaked), not a confirmed line in a
captured diagnostic bundle -- no bundle was captured before restarting.
The real profile switch, client proxy, settling runs, warmup, real
executions, and `campaign_pull.sh` were never reached in a clean,
complete cycle this turn -- everything about them remains exactly as
unverified as before this turn, except that the environment that would
run them (user-data, image/source delivery, DinD topology) is now
substantially more likely to work than before this turn's three fixes.

## 76. Heavy local rehearsal abandoned in favor of the AWS pilot itself as the delivery/resume rehearsal; a light, no-DinD flow check run instead -- full real flow confirmed under Python 3.9 for all 3 profiles, 3 of OPINsize's 4 terms reproduced byte-for-byte against v7, one real local-stack bug found and fixed (stale `mongo-data` volume, unrelated to the campaign); `METRICS_COVERAGE.md` and `consolidate_v8.py` written and tested end to end

A no-AWS-mutation, no-AWS-cost turn (this turn's own opening constraint).
Supersedes Decision 75's own "depois do piloto" resume list, specifically
the item "Only server+client in x86_64 DinD this time" -- Luciano's own
instruction this turn was explicit: the DinD/DooD heavy rehearsal is
discarded outright, not resumed. **Reason:** it does not represent the
real target instance (a single real EC2 host, one `dockerd`, no nesting)
and it crashed Docker Desktop once already (Decision 75) under the
combined load of two nested daemons + QEMU emulation + concurrent image
transfer -- repeating it risks the same crash for a rehearsal whose own
fidelity to the real target was already questionable. The real AWS pilot
itself (already planned, already budgeted, Decision 35/46) will BE the
delivery-and-resume rehearsal: a real EC2 instance, no nesting, no
Docker-Desktop-specific DooD path quirks to work around. Everything
`deliver_source.sh`'s resume logic and image delivery still need to prove
moves to the pilot, not to a second local rehearsal.

**What this turn's light check actually did, in place of the heavy
rehearsal:** one `amazonlinux:2023` container, **x86_64** (the real
target instance's own architecture, not control's arm64), real
`--memory=8g --cpus=2` limits (the campaign's own `m7i-flex.large`
sizing, Decision 32), disk nominally limited to Terraform's own 30GB
`gp3` root volume (`campaign_instance/main.tf:104-106`, uniform across
every role -- confirmed by grep, no per-role override exists) via
`--storage-opt size=30G`, though this flag is accepted by the Docker API
(`docker inspect` confirms `StorageOpt=map[size:30G]`) but **not actually
enforced** under this Docker-Desktop/WSL2 setup (`df -h /` inside the
container still showed the full ~1007G host filesystem) -- stated
honestly as a limitation of the check's own environment, not of the real
EC2 target. `install_common_packages.sh` ran for real inside it (dnf
installs succeeded; the systemd-related `docker.service` abort at the
end is the same already-accepted, already-documented container-only
limitation from Decision 75, not a new finding). The real repo was
bind-mounted read-only at Docker Desktop's own
`/run/desktop/mnt/host/c/Users/...` path specifically so `opin_flow.py`'s
own `__file__`-relative path computations are simultaneously valid as
normal container-filesystem reads AND as correct DooD bind-mount sources
for `start_tls_kem_proxy()`'s own subsequent `docker run -v` call, with
no change to `opin_flow.py`'s production code -- confirmed live with a
real file read before trusting it for the real run. `tls_kem_proxy`'s
own hardcoded `--network insurance-server-lambdas_default`/`-p
127.0.0.1:8443:8443` and `pqc_signer_service`'s own missing `--network`
flag were both rewritten, ONLY at the test driver's `subprocess.run`
layer (never in `opin_flow.py` itself), to join the check container's
own network namespace instead (`--network
container:mockopin_flow_check`), stripping the now-incompatible `-p`
flag (`--network container:X` and `-p` conflict -- confirmed live,
real Docker: "conflicting options: port publishing and the container
type network mode"); `REMOTE_GATEWAY_HOST=host.docker.internal` routes
the proxy's own upstream dial to the real `mtls` container published on
the host at `443:443`. This reuses `opin_flow.py`'s own existing,
already-shipped `REMOTE_GATEWAY_HOST` mechanism (Decision 51) exactly as
designed -- no new production code, only test-driver wiring.

**One real bug found and fixed, local-stack-only, unrelated to the
campaign itself:** `mongodb`'s own `mongo-data` Docker volume had been
stamped by a NEWER MongoDB release than the one the now-digest-pinned
`mongo:latest@sha256:...` (Decision 75) actually resolves to --
`featureCompatibilityVersion 8.2`, which that pinned, older binary
refuses to start against ("UPGRADE PROBLEM: ... Expected one of the
following versions: '9.0', '8.3', '8.0'"), which in turn left `auth`
unable to reach Mongo at all and `mtls` unable to fetch its SSA JWK from
`localstack` (itself blocked on `auth`'s own failed-to-seed state). Fixed
by removing the stale local volume and letting `mongo_seed` reseed it
fresh against the pinned image -- a purely local, disposable artifact
(not committed, not AWS, not the campaign's own data), not a code or
pinning defect: the pin itself is correct; the volume simply predated it.
Flagged here because it is exactly the class of problem Decision 75's
own digest-pinning work exists to prevent going forward, caught in the
act of actually running the pinned image for the first time since it was
pinned.

**Full real flow confirmed, all 3 profiles, real Python 3.9, real
container:** `opin_flow.py`'s own `start_tls_kem_proxy()`/
`start_pqc_signer_service()` and `campaign_client_runner.py`'s own
`main()` ran a COMPLETE flow (not merely imported, which Decision 74
already confirmed) for classic, pqc, and hybrid in turn, one profile at
a time via `switch_crypto_profile.py` (reused, not reimplemented) between
each. `call_count` came back exactly 42 in all three profiles, matching
both this turn's own target and `thesis/results/v7/latency/experiment1 -
Classic/0ms/runs/run01.json`'s own `call_count: 42` field directly
(confirmed by reading that file) -- the SAME field v8's own
`campaign_run.py`/`latency_automation.py` pipeline already produces.

**OPINsize's real definition resolved -- it was never actually
ambiguous, only not yet looked up this session:** `OPINsize = N_mTLS x
handshake_bytes + N_JWT x JWT_size + N_JWK x JWK_PK_size + N_PKI x
PKI_bytes` (`Consolidated_Metrics_Report_FINAL.md` Section 3,
`compute_v7_report_data.py:145-168`, with the JARM/PQC-CA corrections
from `apply_jarm_correction.py`/`apply_pqc_ca_postquantum_correction.py`
applied) -- a narrow, four-term equation over cryptographic-artifact
sizes, NOT the sum of every byte `campaign_client_runner.py` reports
across all 42 calls (that larger figure -- 125,065/275,380/331,219 bytes
this turn's own classic/pqc/hybrid runs, close to but not identical to
an unrelated historical baseline from Decision 67's own regression test,
125,485/275,800/331,639, likely normal run-to-run JWT-claim/UUID-length
jitter -- answers a different question and was never meant to match
OPINsize's own 76,929/322,895/350,477 bytes). Confirmed by reading
`thesis/results/v7/report_data_v7.json` directly: `extended_corrected`
(classic, hybrid) / `extended_fully_corrected` (pqc) equal exactly
76,929 / 322,895 / 350,477 bytes -- the user-stated targets, byte for
byte. Three of the four terms are fully reproducible RIGHT NOW from
`campaign_client_runner.py`'s own existing per-call output, confirmed
exactly against v7, real local data, all three profiles, no fixture
involved: `term_jwt` (sum of `calls[].jwt_sizes`) = 37,263 / 151,321 /
200,567, matching v7's own JARM-corrected figures exactly; `term_jwk`
(count of `"sig"`-use `calls[].jwk_sizes` entries times their size) =
512 / 3,904 / 4,416, exact; `term_pki` (sum of the two CA-certificate
calls' `response_bytes`, minus the 103-byte-per-response HTTP framing
v7 already identified) = 8,440 / 32,028 / 37,356, exact. The fourth term,
`term_handshake` (mTLS handshake bytes, median of 6 connections, from
raw TCP/TLS capture), is NOT reproducible from this tool at all -- v7's
own figure came from a separate, live-capture pipeline
(`gateway_metrics.handshake_bytes`) that has no v8 equivalent yet; the
raw `.pcap.gz` per run is already planned to be collected
(`campaign_run.py`'s own Decision 53 layout), so this is a missing
*analysis* step, not a missing *collection* step. The counts N_mTLS=6,
N_JWT=28, N_JWK=2, N_PKI=4 all match this turn's own target exactly
(N_JWT/N_JWK/N_PKI confirmed directly from the real per-call data;
N_mTLS consistent with the data's own `pool_label` grouping, not
independently re-derived this turn). Full detail, including what "28
JWTs" vs the *size* experiment's separate `total_requests=28` field
means (two different numbers, from two different v7 pipelines, that
happen to coincide), is in `thesis/results/v8/METRICS_COVERAGE.md`.

**`METRICS_COVERAGE.md` and `consolidate_v8.py` written and tested end
to end, this turn, not merely planned:** the coverage matrix maps every
metric in v7's own consolidated report to its v8 data source (file +
field), status, and -- for every "not covered"/"covered with
difference" row -- the reason and a proposed fix, exactly as this turn's
own instruction required; the only large, deferred fix is the pcap
handshake-bytes extractor (`term_handshake`, and therefore OPINsize's
own total and the flow-time decomposition), explicitly on the "depois do
piloto" list. `consolidate_v8.py` reads the real `v8/latency/...` tree
(Decision 53's own layout) and writes `consolidated.json` +
`CONSOLIDATED_REPORT.md`, reusing v7's own `pem_der_len()` helper
verbatim rather than reimplementing it, and adding one genuinely new
statistic, a bootstrap confidence interval around the median (v8's own
30-runs-per-cell protocol, Decision 34, has less statistical power than
v7's 60; the bootstrap is v8's response to that, not a v7 carryover).
Tested end to end against this turn's own real check data (reshaped into
the campaign's own `runs/run{NN}.json` + `runs/run{NN}.calls.jsonl`
layout, `tests/fixtures/light_flow_check_2026-10-21/`, real data, clearly
labeled): term_jwt/term_jwk/term_pki reproduce v7's own numbers exactly
for all three profiles; OPINsize's complete-equation arithmetic is
exercised once, for classic only, using one explicitly tagged
`_FIXTURE` value for `term_handshake` (v7's own classic handshake figure,
used only to drive the arithmetic, never claimed as a real v8
measurement) and comes back exactly 76,929, matching v7; pqc/hybrid,
with no fixture supplied, correctly come back `"incomplete_missing_
term_handshake"` with the right partial sum rather than a silently wrong
total. `python3 -m pytest tests/test_consolidate_v8.py` passes.

**"Depois do piloto" additions from this turn:** the pcap-based
handshake-bytes extractor (`term_handshake`, OPINsize's own complete
total, the flow-time decomposition, and `ClientHello` as its own
figure) -- all four blocked on the same missing tool, all four
documented in `METRICS_COVERAGE.md` rather than attempted this turn.
Rehearsing image delivery or `deliver_source.sh`'s own resume behavior
remains explicitly out of scope for this turn's check (per this turn's
own instruction) and stays on Decision 75's existing resume list,
now to be exercised against the real pilot instead of a local
rehearsal, per this decision's own first paragraph.

## 77. Decision 76's "needs a pcap extractor" classification for mTLS handshake bytes was WRONG -- the real source (`server/run{NN}_gateway.log`) was already collected, already pulled, only unparsed; `consolidate_v8.py` and `pilot_acceptance.py` corrected; OPINsize verified complete and within tolerance against v7 using only real data; `mongo:latest`'s pinned digest confirmed newer than whatever produced v7's own original data, no expected effect on bytes

A no-AWS-mutation, no-AWS-cost turn (this turn's own opening constraint),
triggered by Luciano's own read-only investigation request questioning
Decision 76's handshake-bytes gap. The question was well-founded: Decision
76 was wrong, and this entry corrects it on the same axis it was wrong on
(a missing analysis tool, not a missing collection step) rather than
quietly patching the number.

**Investigation, read-only, before anything was changed (Luciano's own
instruction):**
1. `mock-service-os/mock_mtls/main.go`'s `countingConn` (lines 207-229)
   and its `mtlsHandshakeBytes` field (line 680, inside the "mTLS
   handshake complete" `slog.Info` call, line 671) are BOTH still
   present, unchanged since v7. The gateway logs via
   `slog.NewJSONHandler(os.Stdout, ...)` (line 1020) -- one JSON object
   per line, to stdout, which is exactly what `docker logs` reads.
2. `campaign_run.py` already captures this exact log, for every real
   execution, via `docker logs -t --since/--until ...
   insurance-server-lambdas-mtls-1`, into `server/run{NN}_gateway.log`
   -- confirmed at SIX separate call sites (pre-flight checks, settling,
   warmup, and both the SSHExecutor and LocalExecutor real-execution
   paths), not a single narrow case. Collection was never missing.
3. `campaign_pull.sh` pulls `v8/` with `find v8 -type f -print0 \| xargs
   -0 sha256sum` -- no per-file exclusion of any kind, so
   `server/run{NN}_gateway.log` was already in the manifest, already
   hash-verified, the same as every other file under `v8/`. The pull
   side needed no fix either.
4. Neither `consolidate_v8.py` nor `METRICS_COVERAGE.md` considered this
   source -- Decision 76's own `term_handshake()` read a
   `gateway_metrics.handshake_bytes` field from `run{NN}.json`'s own
   `result` dict that does not exist anywhere in this pipeline (that
   shape was copied from v7's SEPARATE size-experiment JSON schema,
   `compute_v7_report_data.py`, without checking whether v8's own
   campaign actually produces an equivalent field under that name --
   it does not, under ANY name, in `run{NN}.json` itself; the real data
   lives in a sibling file, `run{NN}_gateway.log`, that Decision 76
   never opened). This was an honest miss, not a deliberate choice: the
   light flow check that produced Decision 76 ran
   `campaign_client_runner.py` directly, outside `campaign_run.py`'s
   own real-execution path, so no gateway log was ever captured during
   that check in the first place -- there was nothing wrong to notice
   with the tooling actually used that day.
5. The real check data from the 2026-10-21 light flow check
   (`campaign_client_runner.py`'s own JSON) has no gateway-log field at
   all -- confirmed by inspecting its full real key set
   (`generated_at`, `t_fluxo_seconds`, `naive_elapsed_seconds`,
   `wasted_seconds`, `retries`, `whole_run_retries`, `call_count`,
   `calls`). This is expected and consistent with point 4's own
   explanation -- that script was never meant to capture the gateway's
   own log, `campaign_run.py`'s real-execution path is.
6. With the real source actually read (a live `docker logs -t
   insurance-server-lambdas-mtls-1` against the local stack, one
   capture per profile, immediately after a real `switch_crypto_profile.py`
   settling sequence), the mTLS handshake bytes DO match v7 closely:
   classic median 5,179 B (v7: 5,119, +1.17%); pqc median 22,607 B (v7:
   22,607, EXACT); hybrid median 19,017 B (v7: 18,023, +5.52%). PQC's
   exact match is not a coincidence: v7's own Consolidated_Metrics_
   Report_FINAL.md (Section 2) already notes PQC's own handshake figure
   was "re-measured with a single live capture after Decision 14 --
   superseding the original 60-run figure" -- i.e., v7's own PQC number
   is ALSO a single live capture, the same methodology used here, so an
   exact match is the expected outcome, not luck. Classic and Hybrid's
   v7 figures are each the median of an ORIGINAL 60-run batch with
   "0.00% spread" (every one of 60 runs identical) -- this turn's own
   single capture shows real variance even within its own 31-handshake
   sample (classic: 5,112-5,233 B; hybrid: 18,950-19,071 B), so some
   drift against that zero-spread historical median is expected, not a
   sign of a bug; root cause of that variance not investigated further
   this turn (candidate, unconfirmed: TLS 1.3 `NewSessionTicket`
   messages, sent asynchronously shortly after the handshake, falling
   inside `countingConn`'s own counting window depending on timing).

**Decision: the log exists and is already collected (branch 1 of
Luciano's own three-way instruction) -- implement the parser, use it as
the primary source, leave pcap as independent verification only.**
`consolidate_v8.py` gained `client_facing_handshakes()` and a rewritten
`term_handshake()`: both reuse `campaign_run.py`'s own
`_parse_gateway_log_lines()`/`_HANDSHAKE_COMPLETE_MSG`/`_CARVEOUT_MSG`/
`_CLIENT_EXPECTED_CURVE`/`_CORRELATION_WINDOW_SECONDS` directly (imported,
not reimplemented) to separate the CLIENT-FACING channel from the AS's
own internal mTLS calls to the RS -- the same gateway logs BOTH (this
turn's own real capture: 31 client-facing + 35 internal handshakes
across 5 settling runs, 31/5≈6.2 and 35/5=7 per run, consistent with v7's
own "6 client connections + 7 internal connections per flow" structure,
Decision 76's flow-time section). A real curve mismatch among the
client-facing group now raises loudly (same philosophy as
`verify_negotiated_groups()`) rather than being silently averaged in.
`term_handshake()` returns `(6, 6 x median_bytes)` per real single-
execution run -- `len(sizes)` naturally equals 6 once given a properly
`_slice_gateway_log_live()`-scoped single-execution log, exactly as
`campaign_run.py` already produces one.

**A second, independent real bug found in the same investigation, fixed
the same way (real data, not assumption): N_mTLS's planned source
(`calls.jsonl`'s own `pool_label` grouping, Decision 76's own
METRICS_COVERAGE.md row) undercounts.** Checked directly: `pool_label`
gives 4 distinct values where the gateway log gives 6 real TLS
handshakes -- `opin_flow.py`'s own connection pooling reuses one pool
label across more than one underlying handshake. Fixed: N_mTLS is now
read from the gateway-log-derived handshake count (the real,
authoritative source), and `pool_label`'s own count is still computed
and reported, but ONLY as `n_mtls_pool_label_diagnostic` in
`consolidated.json` -- visible, never silently trusted as N_mTLS.

**OPINsize's complete total, all 4 real terms, verified against v7
within a declared tolerance:** classic 77,289 B (v7: 76,929, +0.47%);
pqc 322,895 B (v7: 322,895, EXACT); hybrid 356,441 B (v7: 350,477,
+1.70%). No profile exceeds 2%. `_FIXTURE` is gone entirely from this
turn's own test DATA (`test_consolidate_v8.py` rewritten to use real
`{profile}_gateway.log` captures, one execution's own window each,
sliced from a live capture the same way `_slice_gateway_log_live()`
would, and the test itself now asserts `"_FIXTURE" not in
json.dumps(data)`) -- the string itself still appears in
`pilot_acceptance.py`/`test_consolidate_v8.py`'s own CHECK logic (the
code that looks for it), which is exactly what should contain it, not a
leak; no data file (`*.calls.jsonl`, `*_gateway.log`, `consolidated.json`)
under `thesis/results/v8/` contains it.
`METRICS_COVERAGE.md` updated: OPINsize/term_handshake/mTLS-handshake-
bytes-P50/N_mTLS flipped from "not covered"/wrong-source to "covered",
with the corrected mechanism and the real numbers above; ClientHello as
its own standalone byte figure remains genuinely not covered (the
gateway logs the handshake's TOTAL bytes, no separate per-message
field) -- this one was never a false gap, confirmed by reading
`main.go` for a ClientHello-specific log field and finding none; the
flow-time decomposition's handshake-duration leg is now also knowably
available (`handshakeDurationMs`, same log line as the bytes field) but
not yet parsed by `consolidate_v8.py` (out of this turn's own narrow
scope), while its server-processing leg remains a real, open gap (no
`opin_processing_ms`-equivalent field exists in `main.go`, searched for
directly, not found).

**`pilot_acceptance.py` Criterion 10 added:** fails if, at any profile's
own L0 scenario, the 4 OPINsize terms aren't all present, the complete
OPINsize total isn't within tolerance of v7's own figure, or a
`_FIXTURE`-tagged value appears anywhere in data generated from real
pilot data. **Tolerance: +/-3%, chosen and justified as follows:** this
turn's own three real single-execution measurements against v7 (above)
came in at +0.47%/+0.00%/+1.70% -- 3% is roughly double the largest of
those three, tight enough that a genuine regression (this project's own
history: Decision 11's JARM-count fix moved OPINsize by +1.6%; Decision
14's PQC-CA fix moved it by +19.1%) would still fail loudly, while
ordinary single-execution noise against v7's own 60-run median does
not. Smoke-tested against a real-data tree built the same way
`test_consolidate_v8.py` builds its own (same precedent as Decision 70's
own synthetic-data smoke test for Criteria 1-9): all three profiles
PASS at the stated tolerance.

**Mongo digest (Decision 76's own pinning) confirmed newer than
whatever produced v7's original data; no effect on bytes, as
anticipated.** The pinned `mongo:latest@sha256:dc28ed5a9d0fc616903c3f
463bb1e53b92b49f441721b91926e87d90bf957ce8` resolves to a real,
confirmed MongoDB server v9.0.4 (`mongod --version` run directly against
the container this turn: `"version": "9.0.4"`). This is almost certainly
DIFFERENT from whatever `mongo:latest` resolved to when v7's own data
was collected -- v7 predates any digest pinning, so its own `mongo:latest`
was whatever Docker Hub's moving tag pointed to at THAT time, and
indirect evidence already supports a real difference: the SAME local
`mongo-data` volume this turn's own Decision 76 found stamped with
`featureCompatibilityVersion "8.2"` (rejected by the now-pinned v9.0.4
binary, whose own error message names '9.0'/'8.3'/'8.0' as its only
accepted values, conspicuously NOT '8.2') was created by some EARLIER,
unpinned `mongo:latest` pull -- a version that was NOT 9.0.4, and is
consistent with (though not proof of) that earlier pull being closer to
whatever produced v7's own data. **Expected effect on bytes: none, as
anticipated.** MongoDB in this stack is a backing store for OIDC
client/session/grant records (`mongo_seed`'s own seeded documents,
consumed by the AS) -- it is never serialized byte-for-byte into any
measured HTTP response, JWT, JWK, certificate, or handshake; those are
all produced from certificate/key material on the filesystem and the
AS/RS's own signing code, independent of which MongoDB server version
stores the client registration backing it. This turn's own real,
complete, successful flow runs under classic/pqc/hybrid (this entry's
own OPINsize section above) are themselves live, functional evidence
that v9.0.4 works correctly for this stack's actual use of Mongo, not
just an assumption. The local volume was NOT touched beyond what
Decision 76 already did (recreated once, to resolve the FCV mismatch) --
no further local-only change was made this turn.

**Nothing in this entry touches AWS or the already-closed pilot
plan/campaign infrastructure** -- scope was exactly Luciano's own four
numbered items: investigate, decide (parser, not pcap, not a
collection/pull fix), update the acceptance criterion, and check the
mongo digest.

## 78. Hybrid/Classic handshake-byte drift diagnosed as a real measurement-boundary artifact in `mock_mtls`'s own instrumentation, NOT a cert-chain change (open question, not resolved as a design decision); `opin_processing_ms` source found and wired into `consolidate_v8.py`, already collected/pulled, real "38 vs 42" discrepancy flagged rather than silently resolved; ClientHello SIZE confirmed extractable at the real snaplen=128 (no reassembly needed), SNI confirmed NOT extractable there (minimum snaplen measured, not changed); `pilot_acceptance.py` Criterion 2's own latent bug fixed (it would have failed on every real pilot execution)

A no-AWS-mutation, no-AWS-cost turn (this turn's own opening constraint),
calibrating collection/analysis before any instance launch. Three
read-only investigations plus the fixes each one's own findings allowed
or required -- nothing applied to AWS, nothing in the already-closed
pilot plan touched.

**1. Hybrid +5.52% / Classic +1.17% handshake-byte drift against v7 --
investigated, NOT explained by a cert-chain change, STOPPING here per
this turn's own instruction rather than deciding this myself.** Checked
first, directly: every certificate in both chains is byte-identical to
what v7 documented, confirmed via `pem_der_len()` against the real files
on disk -- `client_one_hybrid.crt` 6,859 B (v7: 6,859), `client_one.crt`
1,494 B (v7: 1,494), `client_one_pqc.crt` 5,879 B (v7: 5,879), and the
server-side `mtls_hybrid.crt`/`mtls.crt`/`mtls_pqc.crt` the same. Neither
Decision 6 nor Decision 14 changed anything here -- Decision 14 was
PQC's own certificate chain specifically, never Hybrid's or Classic's.
Also confirmed structurally, reading the real Go source: both
`mock_mtls/main.go` (`Certificates: []tls.Certificate{{Certificate:
[][]byte{serverBytes}}}`, line ~494) and `tls_kem_proxy/main.go`
(`tls.LoadX509KeyPair`, a single-cert PEM file) send ONE certificate
each in the TLS handshake, never a chain -- root/issuer CA certificates
are never part of the handshake's own byte count at all, confirmed by
the certs' own `pem_der_len()` requiring exactly one `BEGIN CERTIFICATE`
block in each file. So the cert-chain hypothesis is ruled out by direct
evidence, not assumed away.

**What the drift actually is, traced via a real raw packet capture
(tcpdump `-s 0`, tshark decode) of one real Hybrid client-facing
connection, byte for byte:** `mtlsHandshakeBytes` for that exact
connection (confirmed 19,011 from the gateway's own log) equals EXACTLY
the sum of: ClientHello (1,881 B, client->server) + the server's whole
encrypted flight -- ServerHello/EncryptedExtensions/Certificate/
CertificateVerify/Finished bundled (7,240 B, server->client) + a further
2,162 B write from the server IMMEDIATELY after that flight, before the
client's own Finished arrives (structurally consistent with a TLS 1.3
`NewSessionTicket`, which a server may send any time after its own
Finished, not waiting for the client's) + the client's own encrypted
flight -- Certificate/CertificateVerify/Finished (7,240 B,
client->server) + TWO FURTHER client->server reads (260 B + 228 B) that
arrive before `connStateHandshakeLogger` actually reads the counter.
1,881 + 7,240 + 2,162 + 7,240 + 260 + 228 = 19,011, exact. Those last two
reads are NOT part of the TLS handshake at all -- they are (part of) the
connection's FIRST REAL HTTP REQUEST, already arrived and already
counted by the time `info.handshakeBytes` is read at `ConnState ->
StateActive` (`main.go` line ~667), because Go's own HTTP server
transitions a connection to `StateActive` once it starts reading the
first request, which happens strictly after the TLS `Handshake()` call
returns server-side, by which point the client has ALREADY pipelined
its first request's bytes onto the same connection (TLS 1.3 removes the
extra round trip real clients rely on; `opin_flow.py`'s own client does
exactly this). **This measurement-boundary quirk is in `mock_mtls/
main.go` itself, unchanged since v7 -- it would have affected v7's own
original data collection identically, same code, same boundary.** It
explains the WITHIN-run clustering already noted in Decision 77 (5,173/
5,179/5,233-byte groups: different connections' own first request
happens to add a different number of bytes, since each of the flow's 6
connection pools serves a DIFFERENT first call with a different
encrypted-record size) and is the leading, evidence-backed explanation
for the CROSS-run drift against v7's own 60-run median too: a real
difference of up to ~1-2 KB between runs is well within the range a
first-request's own JWT/JWK/JSON payload size difference could produce,
not something a handshake-only artifact of this scale would otherwise
be expected to show. **Not fully closed as a design decision, because
it is not one:** this is a pre-existing measurement artifact, not a
cert/protocol design choice, so it does not fit this turn's own
instruction to register a cert-chain explanation in `DECISIONS.md` --
recorded here as the investigation's real finding instead, pending
Luciano's own call on whether `mock_mtls/main.go`'s handshake-byte
counter should be fixed to stop at the TRUE handshake boundary (a code
change to the gateway itself, same class of change as Decision 14,
genuinely out of this turn's own read-only/no-AWS scope to decide
alone). **Classic, one sentence, same mechanism:** Classic's own smaller
+1.17% drift (60 B) is the identical artifact at a smaller scale --
Classic's own first-request payloads are smaller than Hybrid's (e.g. a
JWKS response of 1,814 B vs. Hybrid's 4,366 B), so less of it leaks into
the handshake-byte count, not a different cause.

**2. `opin_processing_ms` (server-processing leg of the flow-time
decomposition) -- source found, already collected, already pulled,
only unparsed; same root pattern as Decision 77's own handshake-bytes
finding.** `baseline_automation.py`'s `collect_gateway_metrics()`
(`thesis/scripts/baseline_automation.py:364-417`) reads the SAME
gateway log Decision 77 already uses, filtered to a DIFFERENT message
(`"msg":"access log"`, `mock_mtls/main.go:790`, one line per HTTP
REQUEST, not per connection) -- field `opinDurationMs`
(`main.go:768`, `opinRequestEnd.Sub(opinRequestStart).Milliseconds()`).
Real example line, captured this turn against the local stack:
`{"time":"2026-10-22T13:03:33.685466869Z","level":"INFO","msg":"access
log","remoteIP":"172.21.0.6:38698","host":"auth.local","request":"/jwks",
...,"opinDurationMs":1,"mtlsHandshakeStart":...,"mtlsHandshakeDurationMs":20,
...,"mtlsHandshakeBytes":5173,"target":"proxy:http://auth:3000/jwks"}`
-- the SAME line also carries `mtlsHandshakeBytes`/`mtlsHandshakeDurationMs`
for the first request on each connection, confirming "access log" is a
strict superset of what Decision 77's own "mTLS handshake complete"
lines carry. Already collected: `campaign_run.py` writes this exact
file (`server/run{NN}_gateway.log`) for every real execution (same six
call sites Decision 77 already found). Already pulled:
`campaign_pull.sh`'s generic `find v8 -type f` manifest, same as every
other file under `v8/`. No collection or pull-side fix was needed --
`consolidate_v8.py` gained `parse_access_log_entries()`/
`opin_processing_stats()`, reusing `baseline_automation.py`'s own
`latency_stats()` directly (imported, not reimplemented) and the SAME
client-facing-channel filter `term_handshake()` already established
(remoteAddr correlation against the carve-out lines) -- NOT v7's own
`clientCertBytes`-equality filter, a second, equivalent definition of
"client-facing" was deliberately avoided in favor of reusing the one
definition already built. Tested against the real local-flow gateway-
log fixtures already committed (Decision 77): `requests_logged_per_run`
now correctly comes out `[42]` (not 49, which is what it was before
this filter -- 42 client-facing + 7 internal AS-to-RS requests, same
structure Decision 76's flow-time section already named), matching v7's
own real per-run figure read directly from
`thesis/results/v7/size/.../run01_baseline_metrics.json`
(`requests_logged: 42`, `opin_processing_ms.count: 42`, checked across
multiple runs and all three profiles -- always 42, never a different
number). **Open question, not silently resolved:** Luciano's own recall
of "38 requisições registradas por cenário" does not match any real v7
data file actually read this turn (consistently 42, in both
`requests_logged` and `opin_processing_ms.count`, across every run
checked) -- reported as a discrepancy, not forced to fit by inventing a
filter that would produce 38; if there's a specific file/section with
that number, point me to it and I'll reconcile directly, rather than
guess at a second filtering rule with no real basis.

**3. ClientHello via pcap: SIZE confirmed extractable at the real
snaplen=128 (no reassembly ever needed); SNI confirmed NOT extractable
at that snaplen -- snaplen NOT changed, per this turn's own
instruction.** `pilot_acceptance.py`'s existing `find_first_clienthello()`
already reads only the TLS record header's own 2-byte length field
(`payload[3:5]`, `pilot_acceptance.py:290`) -- a field that is ALWAYS
inside the very first TCP segment of the ClientHello, however many real
TCP segments the full record spans on the wire, because the record
necessarily starts at byte 0 of that segment and a TLS record is never
split below its own header. Confirmed with real snaplen=128 captures
(tcpdump against the local stack, one execution per profile, real
`switch_crypto_profile.py` settling runs preceding each): sizes come
back 341 / 1,784 / 1,881 (classic / pqc / hybrid) -- EXACT matches to
the v7 reference fixture, no reassembly logic needed or added. SNI
("mtls"), by contrast, sits at TLS-payload offset ~97 in a real
ClientHello (measured directly: `payload.find(b"mtls") == 97` against a
full, untruncated capture) -- at snaplen=128, only ~62 bytes of TCP
payload actually land in the pcap (128 - 66 bytes of Ethernet/IP/TCP
header overhead, TCP options included, measured directly from a real
captured frame), so SNI is NEVER recoverable at the real campaign
snaplen; confirmed the OTHER direction too, a real snaplen=256 capture
of the same connection class recovers it exactly (`(341, 'mtls')`).
**Minimum snaplen needed: ~168 bytes** (66 bytes of header overhead +
101 bytes of payload to cover "mtls" in full, measured, not estimated);
**recommended with margin: 256** (a round number comfortably above the
measured minimum). **Real, measured cost of 128 -> 256, one real
connection's own capture, same local stack:** 44,774 -> 66,098 bytes,
**+47.6%** -- not extrapolated, the actual before/after file sizes.
**Snaplen NOT changed anywhere in `campaign_run.py`** (both hardcoded
`-s 128` call sites, lines ~1104 and ~1707, untouched) -- this is
Luciano's own call per this turn's own instruction, reported, not
decided.

**A real, latent bug found and fixed in the process: `pilot_acceptance.py`'s
own Criterion 2 would have failed on EVERY real pilot execution,
unconditionally, not flakily.** It gated pass/fail on `sni ==
baseline["sni"]` as well as size -- but SNI is now confirmed never
extractable at the real campaign's own snaplen=128 (point 3 above), so
that equality would never once be true against real pilot data. Fixed:
Criterion 2 now gates ONLY on size (confirmed exact and deterministic,
all three profiles, real local captures) and reports SNI informationally
when present, never failing the criterion on its absence. Smoke-tested
against a real test tree built from this turn's own real snaplen=128
captures (classic/pqc/hybrid, one execution each): all three PASS on
size; SNI correctly comes back `None` and is correctly NOT gated.

**Depois do piloto / open items from this turn:** whether to fix
`mock_mtls/main.go`'s own handshake-byte counting boundary (point 1,
Luciano's own call, a gateway code change); reconciling the "38 vs 42"
requests-logged discrepancy (point 2, needs Luciano's own source or
further digging); whether to bump the real campaign's snaplen to 256 for
SNI verification, given the measured +47.6% cost (point 3, Luciano's own
call, explicitly not decided here).

## 79. Three open questions from Decision 78 closed by Luciano's own call: `main.go`'s handshake boundary stays as-is (documented limitation, not fixed); snaplen raised 128 -> 256 (campaign_run.py, README, volume estimate updated); "38 vs 42" resolved (an old Experiment 3 report, not the final v7). Pcap-based "clean" handshake extraction implemented and tested against real captures, all 3 profiles, alongside the gateway value. `pilot_acceptance.py` Criterion 11 added (gateway-vs-pcap diff per scenario, RTT-dependence signal); Criterion 2's SNI gate restored

A no-AWS-mutation, no-AWS-cost turn (this turn's own opening constraint;
`main.go` explicitly not touched, confirmed -- nothing in `mock_mtls/`
was edited this turn). Luciano made three calls on Decision 78's own
open questions; this entry records them and the work each one required.

**Decision 1: `mock_mtls/main.go`'s handshake-byte counting boundary
(Decision 78, point 1) will NOT be corrected.** Reason, as given: keep
comparability with the already-validated v7 dataset -- v7's own
historical numbers carry the identical boundary artifact (same code,
unchanged since v7), so "fixing" it now would make v8's own gateway-
measured handshake bytes no longer comparable to v7's on the same terms,
trading one kind of comparability problem for another. The artifact
itself (NewSessionTicket plus the first real request's own bytes
leaking into `countingConn`'s counter before `connStateHandshakeLogger`
reads it) is now a documented, understood measurement limitation
(Decision 78), not a mystery -- `METRICS_COVERAGE.md`'s own
term_handshake row already says so. `main.go` was not edited this turn,
confirmed.

**Decision 2: snaplen raised from 128 to 256 bytes, cost accepted as
measured (+47.6% per pcap).** `campaign_run.py` gained a named constant,
`TCPDUMP_SNAPLEN_BYTES = 256` (previously two separate hardcoded `"128"`
literals, one per executor -- both now reference the same constant, so
a future change only needs one edit). Decision 42 (the entry that
originally fixed 128) and Decision 57 (the pcap-volume estimate) both
got their own superseding/updating notes in place, not deleted, per this
file's own convention. Campaign README (`campaign/scripts/../README.md`
-- actually this file: see below) and the volume estimate (Decision 57)
both updated: **32-214MB compressed for the whole campaign, both
sides** (Decision 57's own 22-145MB range at snaplen=128, scaled by the
real, measured +47.6% ratio -- not re-derived from scratch). Still Git
LFS territory, still deferred to a real pilot number before choosing
between LFS and external storage, same conclusion as before the change.

**Decision 3: "38 vs 42" resolved -- not a real discrepancy, a stale
reference.** Luciano's own account: 38 came from an OLD Experiment 3
report (28 requests, a different/earlier count from a different
collection round); the FINAL v7 figure is 42, matching exactly what this
turn's own real data already showed (`requests_logged`/`opin_processing_
ms.count` = 42 in every v7 run file actually read, Decision 78). No
further code change was needed -- `consolidate_v8.py`'s own
`opin_processing_stats()` already produces 42, confirmed correct from
the start; this closes Decision 78's own open question about the
figure, not a new fix.

**Item 2: pcap-based "clean" handshake extraction, implemented and
tested with real local captures, all 3 profiles, reported alongside the
gateway value (not replacing it by default).** A circular import
surfaced while wiring this in (`pilot_acceptance.py` already imports
`consolidate_v8.py` for Criterion 10; `consolidate_v8.py` now needed
pcap-parsing code that lived in `pilot_acceptance.py`) -- resolved by
moving the shared pcap/TCP/TLS primitives (`read_pcap_packets`,
`parse_tcp_packet`, `extract_sni`, `find_first_clienthello`,
`find_syn_synack_rtt`, and the two new functions below) into their own
leaf module, `pcap_utils.py`, imported by both, importing neither.

`parse_tcp_packet_true_len()` (`pcap_utils.py`) reads each segment's
TRUE TCP payload length from the IP header's own Total Length field
(always within the first 20 bytes, so present regardless of snaplen),
rather than from how much of the packet tcpdump actually kept -- this is
what lets `extract_clean_handshake_bytes()` sum real wire bytes per
connection at the real campaign's own snaplen (256), with no need for
full packets.

`extract_clean_handshake_bytes()` (`pcap_utils.py`) implements a simple
4-phase state machine over one connection's own packet sequence --
ClientHello, server flight, client flight, closed -- driven only by
DIRECTION and whether a segment carries real data, never by content
(everything after ServerHello is encrypted, so content-based dissection
isn't available without decrypting, which this turn deliberately did
not do: the user's own instruction said "a partir do pcap", and
SSLKEYLOGFILE-based decryption would be a code change to `tls_kem_
proxy/main.go`, a bigger step than asked for). Verified against a real
raw packet trace, byte for byte, before trusting it: 1,881 (ClientHello)
+ 7,240 (server flight) + 2,162 (server's own extra write, consistent
with a NewSessionTicket) + 7,240 (client flight) = 18,523 -- matching
Decision 78's own hand-traced figure for the exact same real Hybrid
connection exactly. The phase-2-closing rule ("ANY server packet, data
or pure ACK, ends the client's own flight") was chosen over a timing-gap
heuristic after checking: in a real local capture, the client's own
first HTTP request follows its handshake flight within tens of
microseconds, with NO observable gap -- a timing-based rule would not
have worked locally and is not guaranteed to work over a real AWS RTT
either (TCP does not block a write on a prior segment's ACK), so this
rule relies only on DIRECTION, which holds regardless of RTT.

**Real gateway-vs-pcap comparison, all 3 profiles, real matched
pcap+gateway-log captures (same container lifetime, same connections):**

| Profile | Gateway (median) | Pcap-clean (median) | Diff |
|---|---:|---:|---:|
| Classic | 5,179 B | 4,945 B | -4.52% |
| PQC | 22,607 B | 20,296 B | -10.22% |
| Hybrid | 19,017 B | 18,523 B | -2.60% |

The pcap-clean value is **constant** across every one of the 7 real
connections checked per profile (0% spread, confirmed, not assumed --
`test_handshake_gateway_vs_pcap.py`), while the gateway's own value
varies connection to connection (same real finding Decision 78 already
reported) -- direct, repeatable confirmation that the pcap-clean
measurement is the more stable of the two, independent of which
specific first-request happened to leak into the gateway's own count.
PQC's own gap (-10.22%) is the largest of the three and notably tighter
internally (0.4 percentage-point spread across its 7 connections, vs.
2.2pp for classic and 0.6pp for hybrid) -- consistent with PQC's own
first-request payloads being both larger AND more uniform in size than
classic's/hybrid's, though this wasn't traced further this turn.

**`consolidate_v8.py` now reports BOTH values, never picks silently.**
New `term_handshake_pcap()` (reuses `extract_clean_handshake_bytes()`
and the SAME client-facing-channel filter `term_handshake()` already
established -- matched by `(ip, port)`, not a second curve-based rule)
and a new `term_handshake_gateway_vs_pcap_diff` field in the
consolidated output. A new module constant, `HANDSHAKE_SOURCE`
(default `"gateway"`, for comparability with v7, consistent with
Decision 1 above), picks which one feeds OPINsize's own total --
documented as Luciano's own call to flip, informed by Criterion 11
below, not something either script decides automatically.

**Item 3: `pilot_acceptance.py` Criterion 11 added (gateway-vs-pcap
diff per scenario, signals RTT dependence); Criterion 2's SNI gate
restored now that snaplen is 256.** Criterion 11 reports the diff% at
every L0/L325 scenario found, then compares L0 against L325 per
profile: a shift beyond `HANDSHAKE_DIFF_RTT_SHIFT_THRESHOLD_PP` (5
percentage points) signals a real RTT dependence and recommends (does
not itself switch) flipping `HANDSHAKE_SOURCE` to `"pcap"`. **Threshold
justified from this turn's own real, local, same-RTT (L0 only, ~0ms)
measurement:** the diff% already varies by up to 2.2 percentage points
run-to-run from ordinary per-connection noise alone (the table above) --
5pp is more than double the largest of those three spreads, tight
enough to catch a real effect, loose enough not to fire on noise. Not
yet testable end to end against a real RTT difference (no L325 data
exists locally, by construction -- this project's own local lab has no
real network hop to vary); `pilot_acceptance.py` handles this honestly
(prints "L325 data not available yet", returns informational `True`,
never fabricates a comparison), confirmed via a real smoke test
(`test_criterion_11_handshake_rtt.py`) rather than asserted blind.
Criterion 2 (ClientHello size + SNI) is back to gating on both, as it
originally did before Decision 77/78's own temporary size-only fix --
confirmed PASS at the real snaplen=256 with real local captures, all 3
profiles (`test_clienthello_snaplen128.py`, now covering both the
historical 128 case and the current 256 one in the same file).

**Testing, this turn, real data throughout:** `pytest tests/` --
13 tests, all passing, covering: the new pcap-clean extraction and its
gateway-comparison (2 tests), Criterion 11 end to end (1 test), the
restored Criterion 2 SNI gate at snaplen=256 alongside the historical
snaplen=128 case (4 tests), plus everything from Decision 76-78 (6
tests, unaffected, still passing). `pilot_acceptance.py`'s own `main()`
run end to end against a real combined tree (calls/gateway-log/pcap for
all 3 profiles): all 11 criteria execute with no code error; the 2
FAILs that do occur (Criterion 1's own old regression baseline,
Criterion 9's missing real `campaign_pull.sh` cycle) are both expected,
data-level results for ad-hoc local test data, not exceptions.

**Nothing in this entry touches AWS, `main.go`, or the already-closed
pilot plan/campaign infrastructure beyond the three decisions Luciano
explicitly made** (the snaplen constant, and the new/updated acceptance
criteria and documentation that follow from them).

## 80. First real pilot `terraform apply` -- partial failure on the very first attempt, root-caused (not patched blind), fixed in the versioned module, re-applied clean: 21 resources up, server + control + L0 + L325, all verified (SSH, chrony, EIP, IMDSv2, real instance specs)

A real-AWS turn, Luciano present throughout, stopping at every planned
checkpoint plus one unplanned one this entry exists specifically to
record. Pre-flight (credentials, safety timer, IMDSv2, SSH scoping,
secret scanner, budget/credit confirmation) and the pilot's own
`terraform plan` (21 resources, exactly as `PILOT_RUNBOOK.md` expects)
all passed before any apply. Neither `aws` nor `terraform` were
installed on this machine at all -- installed via `winget` this turn
(Chocolatey failed, no admin rights); a dedicated operator SSH keypair
(`~/.ssh/mockopin_pqc_discovery`, outside any versioned folder, no
passphrase set yet -- Luciano's own choice, recommended but not
required) was generated fresh, since no prior "discovery" key existed
on this machine despite the example vars file naming one.

**A real secret-handling incident, disclosed immediately, not
repeated.** An expected `AccessDenied` from `iam:ListAttachedUserPolicies`
(the restricted IAM profile correctly lacks that permission) printed
this project's own full ARN, account ID included, directly in a tool
result -- IAM denial messages always embed the caller's own ARN,
independent of which permission was denied. The value was never
written to any file, never repeated in any later output, and from that
point on every single AWS-touching command in this turn was piped
through `redact_aws_errors.py` (account ID + ARN) with the operator's
own IP additionally stripped via a literal-string `sed` pass before any
output was read. Same root cause and same fix as the earlier incident
this project's own `redact_aws_errors.py` docstring already documents
(a `pricing:DescribeServices` denial, a prior session) -- confirms this
is a real, recurring category (any IAM `AccessDenied` can do this), not
a one-off.

**The first real `campaign_up.sh campaign.vars.local.sh` run (full pilot
apply) failed partway through, with real resources already created and
billing.** `tls_private_key.campaign`, all 8 key pairs, and all of
control + client L0 + client L325 (instance + EIP + security group
each) completed successfully; the apply then failed with `Error:
Provider produced inconsistent final plan ... module.server_sa_east_1
[0].aws_security_group.this ... ingress: length changed from 2 to 3`,
before the server itself was ever created. Diagnosed, not retried
blind: `terraform state list` plus a direct, real `aws ec2 describe-
instances`/`describe-security-groups`/`describe-addresses` sweep of
every region in play confirmed exactly 3 instances existed (control,
client L0, client L325; no server, no orphans anywhere, including the
5 regions that only ever get key pairs) -- the diagnosis was built on
what AWS actually reported back, not inferred from Terraform's own
state alone.

**Root cause 1 (the apply failure): `dynamic "ingress"` blocks inline
on a shared security-group resource, fed by a list whose elements are
each independently unknown on a first/fresh apply.** `server_sa_east_1`'s
own `gateway_ingress_cidrs` was built as `compact([locals ? "${module.
client_X[0].public_or_private_ip}/32" : "", ...])` -- on a first apply,
BOTH enabled entries (client L0's private IP, client L325's public IP)
are unknown until their own modules finish creating. Terraform's plan-
time `toset()` over two independently-unknown values can't rule out
them turning out equal, so it conservatively plans a SMALLER ingress
array; once apply resolves both to real, DISTINCT IPs, the real array
is LARGER than planned, and the AWS provider rejects the mismatch
outright. This is a real, reproducible Terraform/AWS-provider
interaction, not a one-off fluke -- traced to the exact `dynamic`
block, not just the error's own symptom text.

**Root cause 2 (found while re-planning, before touching anything
further): the replan showed `3 to destroy` -- the 3 ALREADY-RUNNING
instances, all three flagged `must be replaced` on `associate_public_ip_
address: true -> false`.** Confirmed directly against real AWS (`aws
ec2 describe-subnets ... MapPublicIpOnLaunch`): `true` on the default
subnet used in every region here. AWS launches every instance with an
auto-assigned public IP regardless of the `false` the Terraform config
requests, so Terraform's own post-apply refresh reads back `true` and
wants to replace the instance to "fix" an attribute AWS was never going
to honor. Confirmed harmless in practice: every pilot instance's own
real `PublicIpAddress`, checked directly, already equals its Elastic IP
(association confirmed via `describe-addresses`), not a leftover
ephemeral address -- the EIP always wins once associated.

**Fix 1, in the versioned module (`modules/campaign_instance/main.tf`),
not just the local state -- reproducibility for anyone else running
this campaign is a thesis requirement, not a nice-to-have.** Moved
`ssh`/`gateway` ingress off the shared `aws_security_group` resource's
own inline `dynamic` blocks onto separate `aws_vpc_security_group_
ingress_rule` resources (AWS provider v5+; one resource per allowed
`/32`, same design Decision 49 already specified -- "uma regra por
cliente"). This alone was NOT sufficient: a real full-campaign plan
(45 resources, fresh regions with no state at all) hit a SECOND, related
error, `Invalid for_each argument ... known only after apply`, because
`for_each` over a SET needs every member known at plan time (the value
IS the key) -- worse than the original `dynamic`-block problem, not
better. Terraform's own error message named the real fix: both
`ssh_ingress_cidrs` and `gateway_ingress_cidrs` became `map(string)`
(previously `list(string)`), keyed by literal, static labels decided
purely by which scenario is enabled (`"control"`, `"operator"`, `"L0"`,
`"L123"`, `"L219"`, `"L325"`, `"L14"`, `"L30"` -- all plan-time-known
booleans, never a module output's own value) via `merge()` of single-
key-or-empty maps. Only each entry's VALUE (the real CIDR) stays
unknown until apply, which `for_each` over a map tolerates fine.
Validated, not assumed: `terraform fmt`/`validate` clean, the existing
13-test Python suite still passing (unaffected, as expected, but
checked), and a REAL full from-scratch 8-scenario campaign plan (47
resources) completing with zero errors, zero destroys, zero replaces.

**Fix 2, same file: `lifecycle { ignore_changes = [associate_public_ip_
address] }` added to the shared instance resource, value left at
`false`** (documents the real intent -- EIP-managed, not auto-assign --
even though the attribute's own declared value no longer drives
anything once ignored). Chosen over flipping the literal to `true`
specifically because `true` would be WRONG if this module is ever
pointed at a non-default VPC with `MapPublicIpOnLaunch=false` --
ignoring the drift is correct regardless of the subnet's own setting,
`true` is only correct for THIS account's current default-VPC
subnets. This is the "works for a clean install by a third party too"
option Luciano's own instruction asked to prefer.

**3 real, pre-existing AWS security-group rules imported into the new
resource addresses before re-applying** (`terraform import`, one per
rule, using each rule's own real `SecurityGroupRuleId` read back from
`aws ec2 describe-security-group-rules`) -- the 3 SSH rules on control/
L0/L325's security groups already existed live (created by the OLD
inline-block code in the first, partial apply); without importing them
first, the new plan would have tried to CREATE a rule identical to one
AWS already has, which `AuthorizeSecurityGroupIngress` rejects as a
duplicate. Caught and fixed before it could surface as a real apply
failure, not discovered the hard way.

**Final pilot plan, with both fixes and the imports in place: `6 to
add, 3 to change, 0 to destroy`.** The "3 to change" are each ONLY
`tags`/`tags_all` being added to the 3 imported rules (the old inline-
block design never tagged individual rules) -- confirmed line by line,
no port/protocol/CIDR/security-group-id change anywhere. Applied for
real: `Apply complete! Resources: 6 added, 3 changed, 0 destroyed` --
exactly as planned, no surprises. A re-plan immediately after returned
`No changes. Your infrastructure matches the configuration.`

**A second, independent, pre-existing bug found and fixed while
completing verification: `campaign_up.sh`'s own `CONTROL_IP` extraction
(line 109) assumed `terraform output -json <name>` wraps its result in
a `{"value": ...}` envelope.** It does not, for a SPECIFICALLY NAMED
output (only the no-argument "dump everything" form wraps each output
that way) -- confirmed live, `KeyError: 'value'`, the very first time
this script's own apply path ever got far enough to reach this line
(every earlier real run failed earlier, at the apply itself). Fixed to
match the SAME defensive pattern the script's own remote-side inventory
parser already used two lines later (`raw["value"] if "value" in raw
else raw`) -- the fix makes the local and remote extraction consistent
with each other, not a new, third convention.

**Full verification, all 4 real pilot instances, every check a real
query, not a formality:**

| Instance | Real type | Real vCPU/Mem | EIP associated | IMDSv2 | Arch | Clock sync (chronyc) | SSH via control |
|---|---|---|---|---|---|---|---|
| Control (sa-east-1) | t4g.micro | 2 vCPU / 1,024 MiB | yes | required | arm64 | N/A (is control) | N/A |
| Server (sa-east-1) | m7i-flex.large | 2 vCPU / 8,192 MiB | yes | required | x86_64 | Stratum 2, -1.1us offset | OK |
| Client L0 (sa-east-1) | m7i-flex.large | 2 vCPU / 8,192 MiB | yes | required | x86_64 | Stratum 2, +0.07us offset | OK |
| Client L325 (ap-southeast-1) | m7i-flex.large | 2 vCPU / 8,192 MiB | yes | required | x86_64 | Stratum 2, +0.36us offset | OK |

Safety timer (48h): confirmed structurally for all 3 non-control
instances (same `templatefile`, same `self_terminate_hours` default,
Decision 49) -- not independently re-verified against each instance's
own `/etc/mockopin-campaign/deadline` file this turn (would need an
extra SSH round trip this entry doesn't claim to have made). AMI
pinning confirmed via the server's own real `ImageId`
(`ami-0c7fb00ead73effc8`) matching `main.tf`'s own `pinned_ami_x86_by_
region["sa-east-1"]`.

**Cost so far:** control + L0 + L325 have been running since the first
(partial) apply, ~22 minutes by the time verification finished; the
server, ~3-4 minutes (created only in the second, fixed apply). At this
project's own ~$0.125/hr/instance blended estimate: on the order of
$0.10-0.15 total so far -- well inside the pilot's own sub-$1 estimate.

**Explicitly NOT done this turn, per Luciano's own scope:** no image
delivery, no execution, no further pilot steps -- those remain gated on
their own stop points from the original pilot runbook prompt.

**Depois do piloto:** consider whether `aws_vpc_security_group_ingress_
rule`'s own static-map-key pattern (this entry) should be documented in
`PILOT_RUNBOOK.md` itself as a known Terraform/AWS-provider interaction,
for whoever next modifies this module; the operator discovery key has
no passphrase yet (Luciano's own choice, revisit if desired).

## 81. Pilot item 1 (ENTREGA) run for real against the live instances -- `deliver_source.sh`/`deliver_images.sh` completed, interrupt+resume rehearsed for real, AMI/package/Python/Docker confirmed on all 4 hosts; 3 real delivery-transport bugs found and fixed (commit `93671aa5a8974efd7918bbeec85ae6d7203cf62a`), none a protocol change under this runbook's own criteria

Real-AWS turn, Luciano present, following `PILOT_RUNBOOK.md`'s own
sequence (Decision 80's 4 instances already up: control + server +
`L0`/`L325` clients, `sa-east-1`). Everything below ran against those
real instances, redacted through `redact_aws_errors.py` throughout; no
account ID, operator IP, or key appeared in any output shown to
Luciano.

**`deliver_source.sh`** ran for real (its own header previously said
"WRITTEN NOW, NOT EXECUTED" -- this is its first real execution):
delivered `thesis/scripts/*.py`, `mock-service-os/{certs,ssa,setup_ssm.sh}`,
and the `insurance-server-lambdas/` config files to control, the
server, and both clients; `pip3 install --require-hashes` succeeded on
all 3 targets under the real AL2023 Python 3.9.25.

**Interrupt + resume rehearsed for real** (this script has no built-in
resume logic, unlike `deliver_images.sh` -- Decision 76 deferred
rehearsing this to the real pilot): a forced `timeout 8s` killed the
script mid-transfer to the third host (`L325`); a full re-run
immediately after completed cleanly (exit 0), idempotent across all 3
hosts (`pip3`'s own "Requirement already satisfied" on every package,
no corruption, no duplicate-install error).

**`deliver_images.sh`** ran for real, 6 images (4 server + 2 client,
~1GB compressed) -- first attempt failed outright:

1. **Local `rsync` missing.** This operator machine (Windows/Git-Bash)
   has no `rsync` binary and no ready winget package for it.
   `have_rsync_on_control()` only ever checked the CONTROL side; the
   actual `rsync -e ssh ...` invocation runs on the OPERATOR's own
   machine for the operator->control leg, so the missing local binary
   caused a hard "command not found" (exit 127) instead of reaching the
   script's own existing split+scp fallback. Fixed: added
   `have_rsync_locally()`, now required alongside
   `have_rsync_on_control()` before rsync is attempted at all.
2. **Split+scp fallback corrupted the reassembled tarball.** With the
   fix above in place, the fallback activated for real for the first
   time -- `cat ...part.*` on the control instance also matched each
   part's own `.sha256` sidecar file (e.g. `...part.aa.sha256` fits
   `...part.*` exactly as well as `...part.aa` does), concatenating
   sidecar text into the binary tarball. Every individual part passed
   its own sha256 check (they were intact on disk); only the pre-
   existing FINAL whole-file sha256 check caught the corruption --
   exactly the defense-in-depth that check exists for. No corrupted
   image ever reached `docker load`. Fixed by narrowing the glob to
   `part.??` (`split`'s own default 2-character suffix width, which a
   6+-character `.sha256` suffix can never satisfy). Cleaned the
   corrupted leftovers off control before retrying.

Also found and fixed, independently of the above: **`terraform output
-json <name>` is not wrapped in `{"value": ...}`** the way the no-
argument form is -- the same bug already fixed in `campaign_up.sh`
(Decision 80) was found, unfixed, in `deliver_source.sh`'s,
`deliver_images.sh`'s, and `campaign_pull.sh`'s own `CONTROL_IP`
extraction lines. Fixed identically in all 3.

After both fixes, `deliver_images.sh` completed clean for all 6 images,
each with matching loaded image ID across every host it was delivered
to (recorded in `delivered_images_manifest.json` on control, per the
script's own existing mechanism, Decision 55).

**AMI/package/Python/Docker confirmed directly on all 4 real
instances** (control, server, `L0`, `L325`): every tool
`install_common_packages.sh` installs (`docker`, `rsync`, `chrony`,
`tcpdump`, `ping`, `ss`, `flock`, `tar`, `pip3`) present on all 4;
`docker compose v5.6.0` present on the 3 `x86_64` hosts and correctly
absent on the `arm64` control instance (by the script's own
architecture gate); Python confirmed `3.9.25` everywhere (matching the
`cp39` wheel tags already seen in `deliver_source.sh`'s own pip
output); Docker `25.0.14` everywhere; `/var/lib/mockopin-ready` present
on all 4. Real AMI IDs recorded via IMDSv2: control
`ami-0518be3fcd9e81858` (`t4g.micro`), server+`L0`
`ami-0c7fb00ead73effc8` (`m7i-flex.large`, `sa-east-1`), `L325`
`ami-012634091f2034c69` (`m7i-flex.large`, physically `ap-southeast-1`
-- the scenario label names the TARGET latency, not the client's own
region).

**Commit, scoped and recorded.** Per Luciano's own condition on this
turn's PONTO DE PARADA 1 approval: `scripts/scan_secrets.sh` run and
passed (clean on tracked + staged + full history) BEFORE committing;
one commit containing ONLY the 3 delivery-script fixes above (no
docs, no data) -- `93671aa5a8974efd7918bbeec85ae6d7203cf62a` -- pushed
to `main`. That hash was then written into the pilot's own data tree on
control, `campaign-data/v8/latency/_campaign-control/environment/
delivery_scripts_commit.json` (alongside the per-instance environment
records `campaign_run.py` writes at campaign start), so the data this
pilot produces carries its own delivery-script provenance without
requiring a `.git` checkout on control.

**Not a protocol change.** Checked against `PILOT_RUNBOOK.md`'s own
"o que conta como mudança de protocolo" list: none of these 3 fixes
touch `campaign_run.py`/`campaign_client_runner.py`, the instance type,
or the content of a delivered Docker image (the glob bug corrupted a
TRANSFER, caught before any corrupted image was ever loaded -- the
images actually running on every host are byte-identical to what was
built locally, confirmed via the per-host image-ID comparison above).
This is squarely "ajuste em script de entrega/infra, não do protocolo
de medição" -- the pilot's window 1 data remains eligible to count
toward the full campaign under the runbook's own retention rule.

README.md's Caveats section updated: local `rsync` is optional (falls
back to split+scp either side is missing it), and that fallback's
reassembly is whole-file sha256-verified before any `docker load`, with
a glob narrow enough to exclude its own sidecar files.

**Next:** Item 2 (EXECUÇÃO DO PILOTO) -- 60 real executions (10/profile
x 3 profiles x 2 scenarios), per PONTO DE PARADA 1's own approval.

## 82. `campaign_run.service` never existed anywhere in the repository, and `campaign_run.py` itself was never delivered to the control instance by any script -- both documented as "already written"/already in place, neither real; fixed by extending `deliver_source.sh`, not worked around with an ad hoc start mechanism (commit `57ebaafc365c72bd3ded74afcc193d243ecac91f`)

Found trying to actually start the pilot's 60 real executions, right
after Decision 81's PONTO DE PARADA 1 was approved: `README.md`/
`PILOT_RUNBOOK.md` both describe `campaign_run.service` as "already
written" and instruct `sudo systemctl edit campaign_run.service` on
control. Checked directly, for real, before trusting it: `systemctl cat
campaign_run.service` on the real control instance returned "No files
found." Grepped the whole repository for the unit file itself -- it
does not exist anywhere, only mentioned in prose (README, runbook,
`campaign_run.py`'s own docstring). Checked every delivery script for
anything that copies `campaign_run.py` (the orchestrator itself, as
opposed to the client-side `thesis/scripts/*.py` files) to control --
none does. `deliver_source.sh`'s own tarball reaches control only to be
RELAYED onward to every server/client; control's own copy was deleted
at the end of that relay, never extracted locally. The entire documented
mechanism for starting the real campaign had never been implemented by
any script, on top of the 3 delivery-transport bugs already found and
fixed this same turn (Decision 81).

**Stopped and reported before fixing this one** (unlike Decision 81's 3
bugs, fixed inline) -- this is the deployment path for the script that
produces the thesis's own real-AWS data, not a transport-layer glob/
envelope bug; Luciano's own call on how to proceed mattered here.
Luciano chose to fix it properly, versioned, delivered through
`deliver_source.sh` (so a future full campaign run goes through the
identical, by-then-tested path), with four explicit conditions:

1. **`Restart=on-failure` with a low budget, justified, not
   `Restart=no` by default.** Confirmed first, by reading the code, that
   `campaign_run.py`'s own resume marker is real and safe: a run's
   `runs/run{NN}.json` (`already_done()`, line ~734) is written ONLY
   after `run_one_execution()` returns successfully (`run_window()`,
   the write happens strictly after the call, never before or
   concurrently) -- a crash mid-execution leaves no file, so a restart
   never mistakes an interrupted run for a completed one, and never
   re-runs a genuinely completed one. `RestartSec=30`,
   `StartLimitIntervalSec=600`, `StartLimitBurst=3`: a transient SSH
   blip recovers on its own; three failures in ten minutes exhausts the
   budget and the unit goes `failed` outright, surfaced on the next
   check rather than looping silently and burning pilot budget
   unattended.
2. **Key permissions, redaction, no AWS credential.** The campaign SSH
   key was already `chmod 600`'d to `ec2-user` by `campaign_up.sh`; the
   unit's own `User=ec2-user` means only that same user's session can
   read it, nothing new needed. The unit sets no `AWS_*` environment
   variable at all -- confirmed `campaign_run.py` never calls an AWS API
   directly (stdlib-only imports: `subprocess`/`json`/`os`/etc., no
   `boto3`), it only ever reaches other instances over SSH. Every
   command used to inspect/install it this turn was piped through
   `redact_aws_errors.py`; no account ID or operator IP appeared in any
   output shown.
3. **Delivered through `deliver_source.sh`, one commit, scanner before
   push, hash recorded afterward.** New file `templates/
   campaign_run.service` (versioned); `deliver_source.sh` extended to
   also extract its own tarball directly onto control (previously
   relay-only) and `sudo cp`+`daemon-reload` the unit there --
   `campaign_run.py` added to the same tarball's file list. Verified
   locally first (clean LF line endings, no CRLF -- this is a systemd
   unit a Linux host parses, checked before shipping it) and that
   `ec2-user` has passwordless sudo on control (confirmed live, not
   assumed) before relying on it. `scripts/scan_secrets.sh` run and
   passed (tracked + staged + full history) before committing; this
   commit contains ONLY `deliver_source.sh`'s extension and the new unit
   file -- `57ebaafc365c72bd3ded74afcc193d243ecac91f` -- pushed to
   `main`. `deliver_source.sh` was then re-run for real so the code
   that actually landed on control matches this exact commit, and
   `_campaign-control/environment/delivery_scripts_commit.json` on
   control was overwritten with this hash (superseding Decision 81's
   `93671aa`, recorded as the now-stale prior value in the same file,
   not silently replaced) -- the hash recorded is the one for the code
   that actually ran, not the first commit found adjacent to it.
   Installed and verified directly (`sudo systemctl cat
   campaign_run.service` on the real instance matches the versioned
   file byte-for-byte; `campaign_run.py` present at
   `~/campaign/scripts/campaign_run.py`, `ast.parse()`-clean).
4. **Documented as a real gap, not quietly patched.** This entry;
   `README.md`'s own incorrect claim ("`campaign_up.sh` installs it")
   corrected in place, explaining what was actually missing and how it
   was found.

**Not a protocol change**, same reasoning as Decision 81: neither commit
touches `campaign_run.py`'s own measurement logic, the instance type, or
delivered image content -- this is exclusively "how the orchestrator
reaches control and gets started," which `PILOT_RUNBOOK.md`'s own
retention rule explicitly excludes from counting as a protocol change.

**Next:** start `campaign_run.service` for real (pilot env overrides:
`CAMPAIGN_RUNS_PER_WINDOW=10`, `CAMPAIGN_WINDOWS_PER_CAMPAIGN=1`,
`CAMPAIGN_INSTALLATIONS=sa-east-1`), proceed with the 60 executions.

## 83. Five more real pre-execution blockers found and fixed in sequence trying to actually start the pilot's 60 executions; a sixth found but NOT fixed (co-located client cannot reach the server via its public IP -- AWS same-VPC-to-public-IP routing); pilot torn down clean before resolving it, no execution data exists to lose

Continuation of Decision 82's own turn, same real pilot instances
(sa-east-1 control/server, `L0`/`L325` clients), same discipline:
stop and report on anything touching the measured system's own
correctness or behavior, fix delivery/infra bugs inline, redact every
output through `redact_aws_errors.py`.

**Found and fixed, in order, each blocking the one before it from ever
being exercised:**

1. **`insurance-server-lambdas/docker-compose.yml`: `mockapi`'s real
   dependency on `psql` was never declared.** `mockapi`'s own
   `DB_URL=jdbc:postgresql://psql:...` connects eagerly at JVM boot, no
   retry -- with no `depends_on`, Compose never started `psql` as a
   side effect of starting `mockapi` on a genuinely fresh instance
   (every local rehearsal before this one ran against an
   already-persistent Docker environment where `psql` happened to
   already be up). Full audit of every service's real host usage vs.
   declared `depends_on` done at Luciano's own request; also fixed
   `cs-server`'s missing `depends_on: mtls` (its "directory" alias,
   profile `cs` only, never exercised by the campaign). Added a
   `pg_isready` healthcheck to `psql` (`service_healthy` needs one).
   Commit `27fc79443a6423dbc15bdfd2ca797caecfe7a2bf`.
2. **`campaign_run.py`: `SCENARIO_ROTATION` ignored the pilot's own
   scoped inventory.** Hardcoded to the full campaign's 4-scenario list
   for `sa-east-1`; the pilot's inventory only has 2 of those 4
   (`MOCKOPIN_ENABLED_CLIENT_SCENARIOS`) -- every IP lookup for the
   missing two raised `KeyError`, on literally every block, before a
   single real execution could run. Also: the "switch profile on
   server" SSH call runs `switch_crypto_profile.py` end to end (up to
   ~1 minute by its own docstring) inside the same 30s
   `SSH_TIMEOUT_SECONDS` every short command shares -- always too
   short, first actually exercised end to end by this same pilot run.
   Commit `ce1e80cda6aea70ca21affbb723f31a7637861d7`.
3. **`tls_kem_proxy`/`mockopin-pqc-signer` never delivered to the
   SERVER.** `switch_crypto_profile.py`'s own internal settling step
   (Decision 4) runs on the server and starts its own local proxy/
   signer there (the script's original single-host design) -- no
   image, no `TLS_KEM_PROXY_USE_PRECOMPILED=1`, defaulted to `go run .`
   against Go source never delivered anywhere ("go.mod file not
   found"). Chosen deliberately (Luciano's own call) over trimming
   `switch_crypto_profile.py`'s documented settling behavior: deliver
   the images to "servers" too (`deliver_images.sh`), matching the
   client-side pattern exactly, rather than changing what that script
   does. Also retroactively committed two `templates/campaign_run.service`
   fixes already deployed live earlier the same turn but never
   tracked (`StartLimitIntervalSec`/`StartLimitBurst` belong in
   `[Unit]`, not `[Service]`; `PYTHONUNBUFFERED=1`, Python fully
   buffers stdout under systemd, hiding real-time progress). Commit
   `51c3ed1bb93754a07b5332ecc1b43b228e483c93`.
4. **`opin_flow.start_tls_kem_proxy()`'s `--network` was
   unconditional.** Always joined `insurance-server-lambdas_default` --
   correct only on the SAME host that ran `docker compose up` for it
   (Docker networks are per-daemon, never shared across machines); a
   real remote CLIENT instance never created that network at all
   ("network insurance-server-lambdas_default not found"). Fixed:
   conditional on `REMOTE_GATEWAY_HOST` (unset keeps the exact original
   join; set omits `--network` entirely, Docker's own default bridge
   already NATs outbound the same way). Commit
   `f8b9dcd11549dace0108412939a082e5ceec3c9a`.
5. **Client proxy start timed out at 30s.** Its own internal readiness
   poll (`_wait_for_tls_kem_proxy_ready_detached()`) is ALSO 30s,
   leaving zero margin for the SSH connection itself once the network
   fix above let this call actually reach that far for the first time.
   Added `PROXY_START_TIMEOUT_SECONDS=90`. Commit
   `cbec787bc8afd9c4cf828cbe8bee25479aa023d2`.

All 8 of this directory's own standalone test scripts re-run clean
after every one of the 5 fixes above.

**Found, diagnosed, and NOT fixed this turn (Luciano's own explicit
pause, the pilot destroyed before resolving it):**

6. **`L0` (every region's own co-located client) cannot reach the
   server via its public IP at all.** Confirmed empirically from the
   real `L0` instance: `/dev/tcp` to the server's public IP hangs
   (times out, RC=124); the SAME test to the server's PRIVATE IP
   succeeds instantly (RC=0). Root cause: same-VPC traffic addressed to
   another instance's public/Elastic IP routes out through the
   Internet Gateway and back -- which rewrites the source to the
   sender's OWN public IP by the time it reaches the destination's
   security group. That security group only ever allowed `L0`'s
   PRIVATE IP (matching `PILOT_RUNBOOK.md`'s own documented intent:
   "one private -- L0's, co-located"), so the traffic is silently
   dropped (a hang, not a refusal). Never caught by step 4's own
   connectivity check, which only ever tests from `L325` (the public
   case), never from a co-located client.
   - **Decided fix (Luciano's own call), written but NOT applied:**
     `campaign_run.py`'s `_server_ip()`/`_REMOTE_CLIENT_ENV()` should
     use the server's PRIVATE ip for a co-located client, public
     otherwise -- not just correctness, avoiding the IGW round-trip
     also matters for `L0` specifically, whose whole point is
     near-zero/co-located latency. The discriminator is an EXPLICIT
     `colocated` literal added to every client's own entry in
     `terraform/outputs.tf`'s `inventory` output (`true` for every
     `L0@*`, `false` for every cross-region scenario) -- not derived by
     comparing region strings. `terraform plan` confirmed this is a
     pure output-value change, zero resources to add/change/destroy
     ("You can apply this plan to save these new output values to the
     Terraform state, without changing any real infrastructure").
   - **`terraform apply` itself was refused by this harness's own
     "Blind Apply" safety classifier**, independent of AWS/Terraform --
     attempted once, denied outright, not worked around. The
     `colocated` field change sits in `outputs.tf` locally, uncommitted
     at the time Luciano called the pause below, now committed as
     explicitly PENDING (not yet applied to real Terraform state, not
     yet validated against real AWS).
   - **`campaign_run.py`'s own consumer-side fix (reading `colocated`
     to pick the IP) was deliberately NOT written** -- Luciano's own
     pause instruction ("não continues nenhuma correção nem execução")
     landed before it was started.
   - **The pre-flight port-443 connectivity check (every client,
     including `L0`, short timeout, explicit failure not a hang) was
     NOT added** to `campaign_up.sh`/`campaign_run.py` or
     `PILOT_RUNBOOK.md` (which still only documents testing from
     `L325`) -- also deferred by the same pause.

**Also fixed, needed to safely tear down:** `campaign_pull.sh` had the
exact same missing-local-`rsync` gap `deliver_images.sh` already found
and worked around earlier the same turn, but with no fallback at all --
found live, needed to succeed before `campaign_down.sh` would destroy
anything. Added the same `scp`-based fallback pattern (not incremental
like rsync, but this script's own data volumes are small enough that
this is a correctness fix, not a performance one).

**Teardown (Luciano present, explicit authorization, mid-session
pause).** Before destroying: `campaign-data` on control audited
directly -- zero `runs/`, zero settling files, zero pcaps, zero gateway
logs anywhere; only control-plane metadata (`_campaign-control/`:
environment records, schedule, one window record) ever existed, because
no block ever got past `start_block_proxies()` for real. `campaign_pull.sh`
(with its own rsync-fallback fix above) ran and sha256-verified that
metadata into `campaign/scripts/pilot-data-pulled/` (local-only, not
part of the versioned `v8/latency/` tree -- there was no real
experiment data to preserve there). `campaign_down.sh` then destroyed
27 resources; direct AWS API verification, region by region, confirmed
zero instances/security groups/key pairs/volumes/Elastic IPs in all 7
regions this project ever touches (`sa-east-1`, `us-east-1`,
`ap-northeast-1`, `ca-central-1`, `eu-north-1`, `ap-southeast-1`,
`ap-northeast-2`) -- not just Terraform's own exit status. Local
Terraform state/key material kept as-is (not deleted -- no explicit
instruction to do so).

**Real cost, this turn's own estimate (Luciano's own Billing-console
check is the authoritative one -- this project's restricted IAM profile
cannot read spend via the API, Decision 44):** instances ran far longer
than the pilot's own original ~1-2h estimate because of how much real
debugging this turn needed -- control/`L0`/`L325` ~9h02m each,
`sa-east-1` server ~8h43m. Using `m7i-flex.large`'s own sourced rate
($0.0958/hr, Decision cost table) for the 3 `m7i-flex.large` instances
and a public, commonly-cited (not independently sourced in this repo)
`t4g.micro` rate (~$0.0084/hr) for control, plus the ~$0.005/hr/public-
IPv4 charge AWS applies regardless of association, for 4 addresses over
~9h: compute ≈ $2.64, public IPv4 ≈ $0.18, **total on the order of
$2.80** -- still small, but a few times the original sub-$1 estimate,
entirely explained by real-time elapsed, not a cost-structure surprise.
**Ask Luciano to confirm against the real Billing console.**

**Not a protocol change**, same reasoning as Decisions 81/82: nothing
above touches `campaign_run.py`'s own measurement logic, the instance
type, or delivered image content. Items 1-5 are delivery/dependency/
timeout fixes; item 6 (not yet applied) only changes which of the
server's two already-existing IP addresses a co-located client is
handed.

**Depois do piloto / ao retomar, em ordem:**
1. Luciano confirms the real cost via the Billing console.
2. `campaign_run.py`'s `colocated`-aware IP selection (item 6 above) --
   write it, matching `_REMOTE_CLIENT_ENV()`'s own existing shape.
3. The pre-flight port-443 connectivity check (every client including
   `L0`) in `campaign_up.sh`/`PILOT_RUNBOOK.md`.
4. `terraform apply` for the `colocated` output field (confirmed
   output-only, zero resource changes) -- needs Luciano's own hands
   (this harness refuses `terraform apply`/`destroy` as a blind
   action), or an interactive apply Luciano runs himself.
5. Re-apply the pilot topology (21 resources, same as Decision 80),
   re-run item 1 (ENTREGA) fresh -- the 7 fixes above are already
   committed, so this should be the first attempt that doesn't re-hit
   any of them.
6. Resume item 2 (EXECUÇÃO DO PILOTO) from the start -- no partial
   pilot data exists to resume from or discard.
7. None of `pilot_acceptance.py`'s 11 criteria have been checked
   against real data yet -- this pilot never produced a single real
   execution.

## 84. Decision 83's own 6th bug (co-located client's public-IP path) fixed and consumer written; a pre-flight connectivity check and a time/cost budget added to the orchestrator itself; a genuinely fresh local bring-up test (no DinD, no AWS) re-confirmed Decision 83's own psql fix end to end -- no-AWS turn, code/tests/docs only

Direct continuation of Decision 83, explicitly scoped to NO AWS this
turn (no apply, no destroy, no resource query) -- code, local tests,
and documentation only.

**1. `colocated` field consumer, written.** `pick_gateway_ip()` (module-
level, so both `SSHExecutor._server_gateway_ip()` and the new
pre-flight check share one real implementation) picks the server's
`private_ip` for a co-located client, `public_ip` otherwise -- fails
loudly (never a silent default) if `colocated` is missing from a
client's inventory entry, or if the IP it calls for isn't present on
the server's own entry. Wired into every place a CLIENT reaches the
server's gateway: `REMOTE_GATEWAY_HOST` (proxy start, settling, warmup,
the real execution itself) AND the client-side reference ping (was
pinging the server's always-public `_server_ip()`, which would have
silently measured a DIFFERENT path than the one a co-located
execution actually just used). `_server_ip()` itself is UNCHANGED --
every place CONTROL reaches the server directly (profile switch,
docker logs, tcpdump, cpu/mem sampling, scp pcap pull) keeps using it,
a separate relationship with its own, already-correct security group
rule.

Audited everything else that depends on the server's address, per
Luciano's own list:
- **pcap filter**: `tcpdump ... port 443` -- no IP in the filter at
  all, and the auto-detected capture interface is the SAME one
  regardless of which of the server's two IPs a connection used (an
  EC2 instance has one ENI; "public IP" is an AWS-level NAT mapping
  onto it, not a separate interface the OS itself ever sees). Confirmed
  address-agnostic, no bug.
- **RTT extraction (SYN->SYN-ACK)**: `pcap_utils.find_syn_synack_rtt()`
  derives the expected reply 4-tuple FROM the observed SYN packet
  itself, never from a hardcoded/assumed IP constant. Confirmed
  address-agnostic, no bug.
- **Terraform security group rules**: confirmed statically in
  `main.tf`'s own `gateway_ingress_cidrs` for all 3 server regions --
  every `"L0"` entry already uses `.private_ip`, every cross-region
  scenario already uses `.public_ip`, with an explicit `# co-located --
  private IP` comment at each one. These were ALREADY correct before
  Decision 83 -- only the CLIENT-side connection code was wrong.
- **Cert/SNI independence from address**: confirmed in `mock_mtls/
  main.go`'s own comments and `tls_kem_proxy/main.go`'s
  `upstreamTLSConfig.ServerName` -- SNI is a fixed, hardcoded string
  (`"mtls"` / `"matls-api.local"`), explicitly set because dialing a
  literal IP omits SNI by default otherwise. Confirmed by design,
  independent of which IP is actually dialed, no bug.

5 new unit tests (`tests/test_server_gateway_ip.py`, fake inventories
only, no Docker/AWS/SSH): co-located client gets the private IP,
remote client gets the public IP, a missing `colocated` field raises,
a missing required IP (private OR public) raises. `tests/
rehearsal_runner.py`'s own fake inventory (a single-Docker-network
setup with no real public/private distinction) updated to the new
schema (`colocated: true`, reusing its one reachable hostname for both
IP fields) so it keeps working under the new requirement.

**2. Pre-flight connectivity check, every client including every
`L0`.** `verify_gateway_connectivity()`, called right after
`verify_ready_marker()` in `main()`, before any settling/execution
work: opens a short-timeout (5s) TCP connection from EVERY client to
the server's gateway on the EXACT IP `pick_gateway_ip()` would hand it,
prints a `client / gateway_ip / result / time` table, aborts loudly
(never hangs) if any client can't reach it. `PILOT_RUNBOOK.md`'s own
step 4 table corrected -- it only ever tested from `L325` (the
public-IP case), the exact gap that let Decision 83's own bug through
undetected until real AWS minutes had already been spent on it.

**3. Time/cost budget, orchestrator-enforced.**
`PILOT_TIME_BUDGET_HOURS` (default 3h -- this pilot's own real turn
ran ~9h against a ~1-2h estimate). Checked once per profile block
(`check_time_budget()`, start of `run_window()`'s own per-profile
loop) against `_CAMPAIGN_START_UTC` (set once, at the top of `main()`
-- a systemd restart correctly resets the clock, since a restarted
run has its own fresh real-time cost from that point). Past budget:
BLOCKS (never exits -- exiting would just re-enter the same wait on
the next systemd restart, burning `campaign_run.service`'s own
restart budget for nothing), logging a reminder every 60s, until the
operator creates `/home/ec2-user/campaign_time_budget_override` on
control. Never destroys anything itself, never silently keeps
spending past the budget unattended either -- the decision stays the
operator's. Registered as a new abort criterion in
`PILOT_RUNBOOK.md`: past budget, tear down and reassess, not debug
with the meter still running.

**4. A genuinely fresh local bring-up test -- no DinD, no AWS --
re-confirmed Decision 83's own `psql`/`depends_on` fix end to end.**
Decision 75/76's own prior conclusion (full DinD/DooD rehearsal
abandoned, trusting the AWS pilot itself as the "fresh instance"
check) is exactly what let 5 of Decision 83's own 7 bugs go
undiscovered until real AWS time was spent on them -- this turn
revisited a LIGHT version of that check instead of accepting the same
gap again. DooD (the real host's own `docker.sock`, mounted into a
`--cpus 2 --memory 8g amazonlinux:2023` driver container, `docker` +
the same pinned `docker compose` binary `install_common_packages.sh`
uses) -- not DinD. Isolated from the operator's own currently-running
real `insurance-server-lambdas` dev stack three ways: a dedicated
compose project name (`mockopin_freshcheck`), the already-built
images re-tagged under that project's own expected names (no rebuild,
no shared state), and a compose override (`ports: !reset []` --
Compose's default list-merge APPENDS, so a bare `ports: []` override
does nothing; `!reset` is the tag that actually clears it) removing
every host port binding, since the real dev stack already held every
one of them. Found and worked around, live, the SAME DooD relative-
bind-mount-path translation gap Decision 75 already documented
(`../mock-service-os/certs/` resolved inside the DRIVER container's
own mount namespace, not the HOST's, so the real cert files appeared
missing to `psql`'s own entrypoint) by mounting the source trees at
IDENTICAL absolute host paths inside the driver, not a synthetic
`/work/...` prefix.

Result: a completely fresh stack (fresh volumes, fresh network, zero
prior state) came up clean on the FIRST attempt once the mount issue
was fixed -- `psql Healthy` before `mockapi` ever started, `mockapi`'s
own log confirming `Startup completed ... Server Running`, no
`UnknownHostException`. A `--force-recreate auth mtls mongo_seed
mockapi` under `CRYPTO_PROFILE=pqc` (the exact command
`switch_crypto_profile.py` itself runs) recreated cleanly too, `psql`/
`mongodb` correctly left untouched (`Running`, not recreated).
`docker system df` before/after: images and containers identical to
the pre-test baseline; the test's own named volumes (`docker volume ls`)
fully gone after `down -v`; a small (+3, ~68MB) volume-count delta
belongs to other, unrelated Docker activity already running on this
shared machine, confirmed by name -- none of it this test's own.

**5/6. Variable/file audit and static validations.** The
variable-dependency audit from Decision 83's own turn (item 1's
`REMOTE_GATEWAY_HOST`/pcap/RTT/SG/cert-SNI check above) supersedes and
extends the systematic one from Decision 81/82 -- no separate new
table needed, the findings are folded into item 1 above.
`terraform fmt -check -diff` and `terraform validate` both pass clean
(no credentials needed for either). All 9 of this directory's own
standalone test scripts pass (the 8 from before, plus the new
`test_server_gateway_ip.py`). `pilot_acceptance.py` run against
`tests/fixtures/light_flow_check_2026-10-21` (the existing local
calibration data, Decision 76) -- runs with no Python exception at
all; reports mostly `N/A` (expected: that fixture has no gateway logs,
pcaps, or CPU samples, by design) and a real `FAIL` only on Criterion
9 (no `.pull-verified` marker there, also expected, it isn't from a
real `campaign_pull.sh` run) -- confirms the script itself has no code
error, not that this fixture should pass the full battery.

**Not a protocol change**, same reasoning as every entry since
Decision 81: nothing here touches what `campaign_run.py` measures or
how. Item 1 only changes which of the server's two already-existing
IPs a co-located client is given; items 2/3 are pre-flight/safety
additions that only ever block or warn, never alter a measurement;
item 4 is a local-only verification exercise, no campaign code
changed as a result of it (it confirmed Decision 83's own fix was
already correct).

**Depois do piloto / ao retomar** (supersedes Decision 83's own list --
step "4. terraform apply for the colocated output field" there is now
OBSOLETE: a fresh `campaign_up.sh` apply creates the whole topology,
`colocated` field included, with no separate manual output-only apply
needed):
1. Luciano confirms the real cost of this turn's own pilot attempt via
   the Billing console (Decision 83).
2. `campaign.vars.local.sh` / operator IP / instance type / budget
   balance confirmed current.
3. `campaign_up.sh` -- fresh apply, 21 resources, `colocated` already
   in the inventory this time.
4. Item 1 (ENTREGA) fresh -- all 7 of Decision 83's own fixes plus
   this entry's own `colocated` consumer are already committed, so
   this should be the first attempt that doesn't re-hit any of them.
5. `verify_gateway_connectivity()`'s own table (step 4 of the runbook,
   now automatic) should show `OK` for every client, including `L0` --
   if it doesn't, stop there, before spending any more real time.
6. Resume item 2 (EXECUÇÃO DO PILOTO) -- no partial pilot data exists
   to resume from or discard.
7. Watch `PILOT_TIME_BUDGET_HOURS` (default 3h) -- past it, the
   orchestrator itself will block and ask, not silently keep going.

## 85. First complete real pilot (60/60 executions) torn down for real, environment snapshot extended before teardown; three real bugs found running `pilot_acceptance.py` against the pilot's own real data already fixed (previous commit); two further real measurement bugs found and fixed this turn (Criterion 1's stale baseline, Criterion 11's pcap handshake-bytes extractor); pcap-based packet-loss measurement added (ICMP is blocked); T_fluxo(PQC)-T_fluxo(Classic) decomposed without concluding

**Pilot run outcome.** The real AWS pilot (Decision 84's resume list)
completed for real this time: 60/60 executions (10 runs x 2 scenarios
[L0, L325] x 3 profiles), real `sa-east-1` server, real co-located and
cross-region clients, no aborts. Real bugs found and fixed DURING that
run (orphaned `verify_gateway_connectivity()` false-aborts, a 30s SSH
timeout killing a genuinely-still-working hybrid/L325 execution) are
already covered by Decisions 83/84's own entries; two further real bugs
found immediately AFTER the run, from the run's own real data, are
already committed separately (`d92e7fa`, before this entry): orphaned
tcpdump/CPU-sampler background processes left running past a timed-out
execution (confirmed live: two process pairs still running hours later
on the L325 client and server, one of them having already corrupted a
real CPU-sample file with a concurrent-write null-byte gap); and
`consolidate_v8.py`'s per-run auxiliary-file lookups using the bare
`run{NN}` stem, which never matched SSHExecutor's real `w{NN}_run{NN}`-
prefixed files -- silently reporting every handshake/JWT/JWK/PKI term as
"missing" for real pilot data until caught.

**Before teardown: data pulled and verified, environment snapshot
extended.** `campaign_pull.sh` + its own sha256 manifest confirmed all
491 files transferred intact (`.pull-verified` present, every hash
matched) -- `pilot_acceptance.py`'s Criterion 9 PASSED against that
freshly-pulled directory, in its own natural `$DEST/v8/...`,
`$DEST/.pull-verified`, `$DEST/campaign-data.sha256` layout. That data
was then moved into the repository's own long-term location
(`thesis/results/v8/latency/...`, matching v1-v7's own convention and
`consolidate_v8.py`'s own usage docstring), with `.pull-verified`/
`campaign-data.sha256` kept alongside it at `thesis/results/v8/` for
the permanent record. Criterion 9 itself is NOT re-run against this
final layout: it assumes `root` is the pull's own ephemeral `$DEST`
(sibling `.pull-verified`/`campaign-data.sha256`/`v8/`), not a
reorganized repo path -- re-running it there reports a structural
path-convention mismatch, not a data-integrity regression (already
ruled out: the move used plain file moves, no content touched, and the
hash manifest's own content is unchanged and committed verbatim).
`_campaign-control/environment/*.json` (written at campaign
start with ami_id/instance_type/az/kernel/docker/chrony/rsync versions
already) was extended, before teardown, with: per-interface MTU (real
NIC `enp39s0`: 9001 on every server/client instance -- jumbo frames;
`docker0`: 1500), CPU model/frequency/core count (`Intel(R) Xeon(R)
Platinum 8488C`, 2400MHz, 2 cores on every instance), Python 3.9.25,
Docker Compose v5.6.0, and each instance's own security-group ingress
rules. The control instance's own SSH rule necessarily names the
operator's real IP (by design -- that rule exists specifically to scope
SSH to the operator) -- recorded as the literal string `"operator
(redacted, never recorded in a file this repo tracks)"`, not the real
CIDR, in the committed JSON. No account ID appears anywhere in these
files either. Re-pulled and re-verified (sha256) after the edit.

**Teardown, verified for real.** `campaign_down.sh` destroyed 27
resources; all 7 regions touched this campaign (`sa-east-1`,
`us-east-1`, `ap-northeast-1`, `ca-central-1`, `eu-north-1`,
`ap-southeast-1`, `ap-northeast-2`) independently confirmed clean via
direct `aws ec2 describe-instances`/`describe-security-groups` calls
(no leftover instance, SG, or EIP tagged `Project=mockopin-pqc-aws`
anywhere). The control instance -- safety-timer-EXEMPT by design,
Decision 49 -- was confirmed destroyed via Terraform's own output
(`module.control.aws_instance.this: Destruction complete after 20s`),
not left to the (inapplicable) automatic shutdown. Real runtime: ~2h57m
(23:01-01:58 UTC) across the 3 server/client instance groups plus
control; estimated real cost **~US$0.93** (3x `m7i-flex.large` @
~$0.0958/h + 1x `t4g.micro` @ ~$0.0084/h + 4x public IPv4 @ ~$0.005/h) --
Luciano's own Billing console check is the authoritative figure (this
account's IAM profile cannot read spend via API, Decision 44).

**Criterion 1 recalibrated: `BASELINE_BYTES` was real, but stale.**
Investigated the hypothesis "420 = 42 requests x 10 bytes" (every real
pilot run of every profile came back exactly 420 bytes below the
hardcoded baseline, byte-for-byte identical across all 60 executions).
Ruled out by direct per-call diffing: a fresh real local-lab execution
run THIS TURN, via the exact same code path (`of.start_tls_kem_proxy()`
+ `campaign_client_runner.py`'s own `la.run_once_timed_with_retry()`),
against the still-running local dev stack (confirmed beforehand:
`CRYPTO_PROFILE=classic` already set on its `mockapi` container, so no
profile switch/recreate was needed), produced **125,065 / 275,380 /
331,219 bytes** (classic/pqc/hybrid) -- matching the real pilot's own
total EXACTLY, 0 byte-level diffs across all 42 calls, even though this
fresh local run used a DIFFERENT `requests` version (2.34.2, this
machine's own venv) than the one pinned for the real campaign (2.32.5,
`requirements.txt`) -- ruling out a library-version explanation too.
Confirmed deterministic across the full dataset: all 60 real executions
(10 runs x 2 scenarios x 3 profiles) land on exactly one of these three
values, zero variance. `BASELINE_BYTES` (125,485/275,800/331,639) was
itself a real capture (Decision 68, same mechanism, same kind of local
run) -- just from an earlier git revision of `opin_flow.py`/
`baseline_automation.py`'s own call-recording path, before it evolved
between Decisions 68 and 76. Recalibrated `BASELINE_BYTES` to
125,065/275,380/331,219 in `pilot_acceptance.py`, documented in the
constant's own comment: a baseline for this criterion must come from a
real run of the CURRENT code (local-lab or real campaign -- now proven
byte-for-byte identical between the two), re-captured whenever
`do_call()`/`_capture_hop()`/`header_bytes()` change, not hand-edited.
Criterion 1: 60/60 PASS.

**Criterion 11's real root cause: the pcap handshake-bytes extractor
undercounted any multi-segment flight, not "the first segment"
literally.** The real pilot showed classic at -4.52% (close to local
calibration's -3.3%/-5.5%) but PQC/hybrid at -92%/-90% (local
calibration: -10%/-2.6%) -- the signal the investigation plan named
explicitly. Root cause, confirmed via a real packet-by-packet trace
(`tshark`-equivalent manual parse, both PQC and Hybrid, real L0
captures): the real campaign's 1500-byte path MTU (vs. the local lab's
effectively-unbounded loopback MTU) splits a PQC/hybrid ClientHello
(ML-KEM/ML-DSA key material) across 2+ TCP segments. The OLD
`extract_clean_handshake_bytes()` state machine advanced its phase on
ANY packet from the other direction -- including a zero-payload ACK --
so segment 2 of the SAME ClientHello (still client->server, real data)
was misread as "the client's own later flight starting", and the very
next packet (a bare ACK from the server, 0 payload) was then misread as
"the server responded, flight over" -- closing the connection's count
at just the ClientHello's own ~1.8KB, before the real ~20KB
ServerHello/Certificate flight (captured right after, confirmed in the
trace) was ever reached. Classic's much smaller ClientHello rarely
needs a second segment, so the bug barely showed there -- which is
exactly why local calibration (small captures, large MTU headroom)
never caught it. Fixed in `pcap_utils.py`'s
`extract_clean_handshake_bytes()`: zero-payload segments are now
skipped entirely (never a phase signal, in either direction), and phase
advances only on a genuine DIRECTION CHANGE between real-data segments
-- so an unbounded run of same-direction segments (however many a large
flight needs) is handled uniformly. Verified against the gateway's own
independent count (`mtlsHandshakeBytes`): **0.00% diff, all 3 profiles,
both scenarios, all 60 real executions, zero variance** -- not merely
"closer", exact. A second, smaller bug found alongside it: L325 (non-
colocated) connections matched 0 of 6 per run, because
`term_handshake_pcap()` matched by the full (ip, port) tuple, and a
cross-region client's own egress is SNAT'd through its Internet Gateway
to its public IP by the time the server's gateway log sees it (private
IP in the client's own pcap, public IP in the gateway log -- confirmed
live, same 6 ephemeral ports, different IP, one real L325 run). Fixed
to match by port alone (SNAT/PAT preserves the source port; confirmed
true in every connection checked; collision risk negligible at this
project's own concurrency). Criterion 11 now reports 0.00% diff for
every profile/scenario including L325, no RTT-dependence shift --
`HANDSHAKE_SOURCE` stays `"gateway"` (no signal to switch it).
`tests/test_handshake_gateway_vs_pcap.py`/
`tests/test_criterion_11_handshake_rtt.py` updated: their own original
expected values (constant pcap size; -4.52%/-10.22%/-2.60% diffs) were
the OLD bug's own output, baked in as if correct -- both rewritten to
assert the real, now-confirmed invariant (pcap matches gateway exactly,
per connection).

**Packet loss, measured from pcap (ICMP is blocked by the real
security groups, confirmed -- every pilot `_ping.json` has
`raw_ping_output: null`).** Added `detect_loss_signals()`
(`pcap_utils.py`): counts, per TCP connection in a client pcap,
retransmissions (a data segment's sequence number already seen, same
direction), out-of-order segments (sequence number below the highest
already seen, same direction), and duplicate-ACK events (3+ consecutive
identical-ack zero-payload segments, counted once per run of 3+, the
classic RFC 5681 fast-retransmit signal) -- reusing the same pcaps
already collected for the handshake-bytes term, no new collection
needed. Wired into `consolidate_v8.py`'s `rtt_and_loss` block
(`pcap_loss_signals`, aggregated across a scenario's own clean runs) and
`CONSOLIDATED_REPORT.md`. When zero loss events are observed, the rule
of three (~95% one-sided upper bound on a true event rate given zero
occurrences in n trials) is reported instead of a bare 0%, so "none
observed" and "impossible" stay visibly distinct. Real result, all 6
profile/scenario cells: 0 retransmissions, 0 out-of-order, a handful of
duplicate-ACK events (4-12 per cell, out of 2,513-4,960 segments) --
observed loss_pct between 0.08% and 0.48%, no scenario hitting the
zero-event/rule-of-three branch. Too small a signal, over only 10
executions/cell, to say anything about L0-vs-L325 or classic-vs-PQC
differences -- reported as-is, not interpreted further.

**Proposed, NOT applied: a Terraform ICMP /32-per-client rule for a
reference ping.** Would mirror the existing
`aws_vpc_security_group_ingress_rule.gateway` pattern exactly (same
`var.gateway_ingress_cidrs` map, same per-client /32 scoping,
`ip_protocol = "icmp"`, `from_port = 8` [echo request], `to_port = -1`
[all codes]) in `modules/campaign_instance/main.tf`. Recommendation:
**not worth adding.** The pcap-based measurement above already works,
needs no new collection step, and adds no new exposed surface on a
public-facing security group (even /32-scoped, ICMP ingress is still
attack surface this project doesn't currently have); the "3/n bytes"
precision ICMP would add (compared to pcap's own TCP-level evidence)
is not worth that tradeoff given pcap already produces a usable,
cross-checked-against-nothing-else-available signal.

**T_fluxo(PQC) - T_fluxo(Classic): reported, not concluded.** Luciano's
own observation confirmed: the gap is ~3.17s at L0 (5.481s - 2.312s) and
~3.19s at L325 (23.288s - 20.103s) -- essentially the same regardless of
~325ms of real added RTT. Decomposition with what this turn's own data
can separate (median values, real pilot data):

| | handshake (6 conns, gateway `handshakeDurationMs`) | server processing (28 reqs, `opinDurationMs`) | remainder (T_fluxo minus both) |
|---|---|---|---|
| classic, L0 | 0.084s | 0.168s | 2.060s |
| pqc, L0 | 0.018s | 0.168s | 5.295s |
| hybrid, L0 | 0.084s | 0.196s | 5.844s |
| classic, L325 | 2.067s | 0.168s | 17.868s |
| pqc, L325 | 2.004s | 0.168s | 21.116s |
| hybrid, L325 | 2.064s | 0.252s | 22.168s |

PQC's own measured handshake-establishment time is NOT larger than
classic's (if anything, slightly smaller by this metric, both L0 and
L325) -- the gateway's `handshakeDurationMs` only times the TLS
negotiation itself, not any of the ML-KEM/ML-DSA computation elsewhere
in the flow. Server-processing time (`opinDurationMs`, RS-side only) is
essentially flat across profiles too. Virtually the entire PQC-vs-
classic gap (~3.2s at L0 AND at L325 alike) lands in "remainder" --
and because that gap does NOT grow with RTT, it is NOT explained by
extra network round trips (which would scale with RTT, the way the
handshake term itself clearly does: ~2s added at L325, ~0s at L0, for
every profile equally). **Current data cannot separate CPU cost from
network cost within "remainder"**: it bundles client-side cryptographic
work (ClientHello construction, certificate/signature verification),
the AS's own JWT/JWS signing and verification (a separate component,
not covered by `opinDurationMs`, which is mock_mtls/RS-only), and
whatever ordinary network round trips the flow always makes -- with no
separate timestamp currently collected for any of those three. A
promising next step for the FULL campaign (not chased further here, on
only 10 executions/cell): `calls.jsonl`'s own per-call `latency_ms`
(already collected, already in `latency_per_endpoint_ms`) could show
whether specific calls' own latency grows with RTT at the same rate in
every profile (consistent with "same round trips, extra CPU on top") or
a different rate (consistent with "extra round trips somewhere in the
PQC/hybrid path") -- not attempted this turn, explicitly flagged as
future work rather than guessed at from an undersized sample.

**What to adjust before the full campaign** (supersedes nothing --
first entry in this list; previous "depois do piloto" lists, Decisions
83/84, are now fully executed):
1. `BASELINE_BYTES`/`pilot_acceptance.py`'s Criterion 1 and `pcap_utils.
   py`'s `extract_clean_handshake_bytes()`/Criterion 11 are now both
   fixed and verified against this pilot's own real data -- no further
   action needed before scaling up, beyond normal regression coverage.
2. Packet-loss reporting (`pcap_loss_signals`) is new and only
   cross-checked against this pilot's own small (10 executions/cell)
   sample -- worth a sanity look once the full campaign's much larger
   sample exists, same reasoning as the T_fluxo decomposition above.
3. The T_fluxo(PQC-classic) decomposition above is explicitly NOT a
   conclusion -- the full campaign's larger N is what could actually
   support separating CPU from network cost (e.g. via per-call latency
   growth across RTT), if that question still matters once real data
   at scale exists.
4. ICMP ingress: decided NOT to add it (see above) -- no action item,
   recorded so it isn't re-litigated from scratch next time.
5. Everything else (colocated routing, pre-flight connectivity,
   time/cost budget, orphaned-process cleanup, consolidate_v8.py's
   window-prefix naming) already ran clean through a full, real,
   60-execution pilot with zero recurrence of any earlier bug -- no
   further changes identified.

## 86. The "-420 bytes = 42 x 10" question resolved by git archaeology, not guessed: the old `BASELINE_BYTES` never matched v7's own real data at all (classic/hybrid: zero gap, confirmed against `report_data_v7.json` directly); PQC's real ~15.8KB gap is v7's own Decision 14 (post-quantum certs), already known, not a v8 regression. Pcap handshake extractor's independence from the gateway confirmed by a full run-by-run reconstruction. CPU-instrumentation evaluated, not implemented. Criterion 9 fixed for the final repo layout. No AWS touched.

**Item 1 -- where the "10 bytes x 42 requests" actually came from.**
Investigated by git archaeology, not assumption, per Luciano's own
instruction to report before recalibrating anything further:

- `BASELINE_BYTES = {"classic": 125_485, "pqc": 275_800, "hybrid":
  331_639}` was introduced bare, with no comment and no citation, in
  `f627e2b` (2026-10-19, the commit that first wrote
  `pilot_acceptance.py`). `git log -S` across the ENTIRE repository
  history (all refs) confirms the string `125_485`/`125,485`/`125485`
  never appears anywhere BEFORE that commit in any form that traces to
  a real measurement file -- the closest prior reference is this
  project's own Decision 61 (2026-10-13 regression note, DECISIONS.md),
  which already asserts "matches... local-lab baseline exactly
  (classic 125,485...)" without citing where that baseline itself came
  from. **It is not v7's own real figure**: `thesis/results/v7/
  report_data_v7.json`'s own `size.classic.total_bytes_corrected`
  field -- the actual, official, thesis-cited number -- is **125065**,
  and `size.hybrid.total_bytes_corrected` is **331219** -- both EXACT
  matches to this turn's own recalibration (previous entry, Decision
  85), zero byte difference, for both profiles.
- Confirmed live, not inferred: extracted `opin_flow.py`/
  `latency_automation.py` at commit `20aa2f3` (2026-09-28 -- the exact
  revision whose own code fed `4035ea6`'s "re-collect v7 latency
  dataset" the very next day, i.e. the real v7-final client code) into
  a throwaway copy, ran it live today against the still-running local
  lab stack, classic profile: **125,065 bytes, 42 calls** -- not
  125,485. The literal v7-final client code, run today, reproduces
  today's number exactly, not the old hardcoded constant. (
  `baseline_automation.py`, which does the actual byte counting, has
  not changed at all since that commit -- confirmed, empty `git diff`.)
  **Conclusion: there is no commit or Decision that introduced a real
  10-bytes-per-request drift for classic/hybrid, because no such drift
  exists against v7's own real data.** The old constant was a
  transcription/measurement artifact from early-to-mid October,
  apparently never reconciled against `report_data_v7.json` itself,
  and this turn's recalibration already corrected it.
- **PQC is different: a real, substantial, ALREADY-DOCUMENTED gap.**
  v7's own `total_bytes_corrected` for pqc is **259552** -- NOT
  275,380 (today's value, confirmed again this turn by running the
  v7-final client code live: identical 275,380). The ~15.8KB
  difference is v7's own **Decision 14** (`thesis/results/v7/
  DECISIONS.md`: "PQC's certificate chain made genuinely post-quantum
  end-to-end", commit `478bda5`, 2026-09-29): `client_one_pqc.crt`/
  `mtls_pqc.crt`/`op_pqc.crt` were reissued to be signed by the
  post-quantum root CA instead of the classical `ca.crt`, closing an
  asymmetry an external review flagged. Confirmed directly: today's
  `client_one_pqc.crt` DER is exactly **5879 bytes**, matching
  `report_data_v7.json`'s own `client_cert_der_corrected: 5879` field
  bit for bit -- that specific field WAS updated by Decision 14's own
  `apply_pqc_ca_postquantum_correction.py`. But `478bda5` landed AFTER
  `4035ea6`'s own latency re-collection that same day (`git merge-base
  --is-ancestor 478bda5 4035ea6` → no) -- so `total_bytes_corrected`
  itself, for pqc, was never refreshed with the new cert's real
  on-wire size; only specific OPINsize-feeding fields were corrected
  analytically. Today's code (and the real AWS pilot) correctly use
  the CURRENT, Decision-14, fully-post-quantum cert -- 275,380 is the
  right, up-to-date figure; v7's own 259,552 is the one that's stale
  for this specific aggregate field. v7's own published report is
  unchanged by this finding (official, closed, per standing project
  policy) -- flagged here as context for v8's own baseline, not a
  request to revisit it.
- **No further `BASELINE_BYTES` change needed**: this turn's
  archaeology CONFIRMS (does not merely re-assert) Decision 85's own
  recalibration for all three profiles.

**Item 2 -- the fixed pcap extractor's independence confirmed, not
adjusted to match.** Reconstructed, by hand, the full directional-run
sequence (every real-data TCP segment, grouped into same-direction
runs, exactly what `extract_clean_handshake_bytes()` computes
internally) for one real classic and one real pqc connection (pilot
L0, run01):

| | run 1 (ClientHello) | run 2 (server flight) | run 3 (client flight) | run 4+ (excluded) |
|---|---|---|---|---|
| classic | 341B, 1 seg | 2469B, 1 seg | 2363B, 3 seg | 1877B @ t+17ms, then the real flow's own HTTP traffic |
| pqc | 1784B, 2 seg | 11272B, 2 seg | 9545B, 8 seg | 4156B @ t+6ms, then a ~493ms gap before the next client data |

Sum of runs 1-3: **5173 (classic) / 22601 (pqc)** -- both match the
gateway's own `mtlsHandshakeBytes` for that SAME connection EXACTLY,
not just in aggregate. This reconstruction never reads the gateway's
own value at any point -- it is built purely from TCP direction and
payload length -- so the 0.00% match is the extractor correctly
measuring the same real quantity the gateway measures, not an
adjustment tuned to agree with it.

**What the extractor actually measures, and the real limit on going
further.** It measures ClientHello through the client's own last
pre-response data run ("client Finished", by direction-boundary
construction) -- run 4 in both examples above is excluded by design.
Whether run 4 specifically IS a NewSessionTicket cannot be determined
from the pcap alone: TLS 1.3 encrypts everything after ServerHello as
opaque ApplicationData (0x17) at the record layer -- ClientHello/
ServerHello are the only messages a passive capture can type by
content; everything else is only distinguishable by DIRECTION, SIZE,
and TIMING, never by decrypting it. Run 4's own signature (a small
server-initiated push arriving a few ms after the client's own flight
ends, before the client sends anything else) is consistent with Go's
default behavior of pushing session tickets proactively -- but this is
an inference from timing, not a certainty, and is reported as such.
Either way, whatever run 4 actually is, it is excluded identically by
direction alone, and the resulting total matches the gateway exactly
in every one of the 60 real executions checked.

**Decision 78's "first-request leakage" is not showing up in this real
data.** That reasoning (gateway's own `countingConn` boundary reads its
counter slightly after the handshake, letting a little of the first
real request's bytes in) predates this turn's own extractor fix, and
was itself based on comparing against the OLD, undercounting pcap
figure -- which this turn's own root-cause finding (Decision 85) shows
was the one that was wrong, not the gateway. With the extractor fixed,
zero leakage of any kind is observable in any of the 60 real
executions (0.00% diff, not merely "within tolerance"). Not re-litigated
further here -- `HANDSHAKE_SOURCE` already stays `"gateway"`
(Decision 85), and this is additional support for that choice, not a
reason to revisit it.

**Item 3 -- client-side CPU instrumentation (signing/verifying/KEM):
evaluated only, NOT implemented, per Luciano's own explicit hold.**

- **Signing (classical + hybrid's outer envelope): cheap to
  instrument, low risk.** `opin_flow.py`'s own `pyjwt.encode(...,
  algorithm="PS256"/"RS256", ...)` calls (two call sites) run
  in-process, in Python -- wrapping each in `time.perf_counter()`
  before/after is a 2-4-line, purely additive change per site, the
  same pattern Decision 61 already used for `start_utc`/`end_utc`
  (measured overhead there: ~2.97us/call, ~0.004% of a typical run's
  T_fluxo -- not a candidate confound). Low risk to v7 comparability:
  purely additive, changes nothing about what is actually sent.
- **PQC signing (ML-DSA-65): instrumenting the CLIENT side only
  measures a round trip, not pure CPU time.** The actual signing runs
  inside a SEPARATE process (`_run_pqc_signer_service()`'s own
  Node.js container, reached over a local HTTP call) -- wrapping that
  `requests.post()` call measures loopback IPC + the signer's own
  processing bundled together, not isolated CPU cost. Getting a clean
  CPU-only number needs the signer service's OWN code instrumented
  (its `server.mjs`) and that measurement returned in its response
  payload -- a small protocol change, not just a client-side wrapper.
  Moderate complexity, low risk (additive, doesn't change what's
  signed).
- **KEM (key exchange): lives in a different process entirely, in Go,
  not Python.** The actual KEM/handshake crypto for pqc/hybrid happens
  inside `tls_kem_proxy`'s own Go binary (`tls_kem_proxy/main.go` --
  NOT `mock_mtls/main.go`, a different file; Luciano's own standing
  "don't touch main.go" instruction is confirmed scoped to the
  gateway's `mock_mtls/main.go` only, but this distinction should be
  confirmed explicitly before any work here, since both files share a
  name). Instrumenting it means new Go code around its own `tls.Dial()`
  call, plus a new way to report that measurement back (a parseable
  log line, mirroring the gateway's own access-log pattern, or a
  side-channel HTTP endpoint). Classic has no KEM step at all (N/A for
  that profile). Moderate-to-higher complexity than the Python-side
  cases; still additive/low risk to comparability if done this way.
- **Verification: does NOT exist in the flow today at all -- not an
  instrumentation question, a prior, separate one.** Every JWT the
  client receives is decoded with `pyjwt.decode(..., options=
  {"verify_signature": False})` (confirmed, both call sites) -- the
  simulated client never cryptographically verifies anything it
  receives, today, in v7 OR v8. Instrumenting "time to verify" requires
  first ADDING real verification to the flow -- a functional change
  that would make the client do MORE work than it does today (and than
  v7 ever did), changing T_fluxo itself, not merely observing it. This
  needs Luciano's own explicit decision before it's even an
  instrumentation question -- flagged, not assumed.
- **Overhead/risk summary:** wrapping an existing call is negligible
  (microseconds, Decision 61's own measured precedent). The real
  tradeoffs are (a) PQC-signing and KEM isolation both need a second
  process's own code touched, not just the Python client, and (b)
  verification isn't instrumentation at all -- it's a methodology
  decision about whether to add new client-side work, which would
  itself change what's being measured. **Waiting on Luciano's own call
  on all three before writing any code.**

**Item 4 -- Criterion 9 fixed for the final repo layout, without
weakening the check.** `criterion_9()` (`pilot_acceptance.py`) assumed
`root` IS campaign_pull.sh's own ephemeral `$DEST` (`.pull-verified`/
`campaign-data.sha256`/`v8/` as direct siblings) -- true right after a
pull, false once that data moves into `thesis/results/v8/latency/`
(Decision 85), where `root` for every OTHER criterion becomes `thesis/
results` (one level above "v8"). Fixed: `criterion_9()` now checks
`root/.pull-verified` first (the original, pre-reorganization case),
falling back to `root/v8/.pull-verified` (the final, committed-repo
case) -- the manifest's own file-path entries (always "v8/latency/...")
are still resolved against `root` either way, not the marker's own
location, so a real hash mismatch is still caught regardless of which
layout is in play. Re-run against `thesis/results` (the real,
committed pilot data): **all 10 applicable criteria now PASS**
(Criterion 7 stays N/A -- no tcpdump-A/B-toggle data in this pilot, as
already documented). Test suite: 13/13 still pass.

**Not a protocol change.** Nothing here touches what `campaign_run.py`
measures or how; `mock_mtls/main.go` was not touched (only read, for
the record of what Decision 14's `caCertPool()` change already does).
No AWS touched this turn.

**Open questions for Luciano:** (1) which of the three CPU-
instrumentation items above, if any, to actually implement, and in
what order; (2) whether "don't touch main.go" extends to `tls_kem_
proxy/main.go` as well as `mock_mtls/main.go`, given KEM instrumentation
would need the former; (3) whether real client-side JWT verification
should ever be added to the simulated flow at all, independent of any
instrumentation question.

## 87. Decision (registered per Luciano's own instruction): the v8 data, measured on real AWS, is the article's data; v7 stays the pre-qualification historical experiment. v8's flow is now COMPLETE end to end -- every signed artifact the client receives is cryptographically verified, in all 3 profiles, through one uniform mechanism; `verify_signature=False` no longer exists anywhere in `opin_flow.py`. No AWS touched.

**Decision, as stated by Luciano, registered verbatim for the record:**
the article's own reported numbers are v8's (real AWS inter-region
latency); v7 remains in the thesis as the historical, pre-qualification
experiment (simulated latency), not superseded, not deleted. Because of
this, v8's own flow had to become genuinely complete before any further
campaign data collection: every signature issued in the flow must be
verified by whoever receives it, for all 3 profiles, with real negative
tests proving a tampered/wrong-key/wrong-algorithm artifact is actually
rejected -- not merely that a correct one passes.

### Item 1 -- every signed artifact in the 42(+2)-call flow

| Artifact | Signs | Should verify | Verified before this turn | Verified now |
|---|---|---|---|---|
| id_token | AS (classic: PS256; pqc: ML-DSA-65; hybrid: Strong Nesting, `idTokenExternalSigningKey.js`) | client | NO (`verify_signature: False`) | YES -- decrypted (JWE, see below) then signature-verified |
| JARM (`response=` callback param) | AS (classic: PS256; pqc: ML-DSA-65; hybrid: Strong Nesting, `rehybridizeJwt()`) | client | NO (`verify_signature: False`) | YES |
| RS-signed responses (consent/person bodies) | RS (classic: PS256; pqc: ML-DSA-65; hybrid: payload extension, `ResponseSigningService.java`) | client | NO (`parse_rs_body()`'s own docstring said so explicitly) | YES |
| client_assertion | client | AS | YES (already, server-side -- `clientHybridAuth.js`) | unchanged -- not this script's own artifact to verify |
| PAR request object | client | AS | YES (already, server-side) | unchanged, same reasoning |
| access_token | AS | n/a | n/a | **not a JWT at all** -- confirmed live, opaque bearer string (e.g. `RFFxgM6ZBGBhWCwtP0GKCf1M-dw4sHtYtI4u2_Xd_vE`), introspected server-side by the gateway on every RS-facing call (`mock_mtls/main.go`'s own 401-on-no/bad-Authorization path, read not touched) -- nothing for the client to cryptographically verify |
| JWKS response (AS's, RS's) | n/a (the key source itself) | n/a | n/a | not itself signed in this project -- the root of trust for everything else above, protected by the mTLS channel it's fetched over |
| root-ca.pem / issuer-ca.pem (PKI/CRL stand-ins) | classic/hybrid: `ca.crt` (common anchor); pqc: `root_ca_pqc.crt` (real 2-level chain) | client | NO | YES -- `verify_ca_chain()`, new |

**id_token's own JWE encryption (RSA-OAEP/A256GCM) is classical in ALL
THREE profiles, including pqc -- confirmed live.** This is NOT a gap
introduced or left open by this turn: it is a pre-existing, deliberate,
already-documented decision (`thesis/results/v2/experiment2 - PQC/
DECISIONS.md`, Decision 4; reaffirmed in `thesis/results/v4/DECISIONS.md`:
"encryption already documented as staying classical across profiles...
decided with the user: out of scope"). Migrating it would mean
decrypting with the AS's key, re-signing, and re-encrypting with the
CLIENT's own public key instead -- a materially bigger change than any
other artifact here, explicitly deferred, not something this turn
revisits. `id_token`'s INNER signature (once decrypted) DOES correctly
follow each profile's own algorithm (`idTokenExternalSigningKey.js`,
Decision 10, closes the gap the v4 entry above still described as open
at the time) -- confirmed live: pqc's decrypted id_token is genuinely
ML-DSA-65-signed, hybrid's is genuinely Strong-Nesting-signed (sigma1||
sigma2, 4754 b64url chars, not an ordinary 342), only its OUTER envelope
stays classical.

JWE encryption of the id_token remains RSA-OAEP in all three profiles,
since post-quantum JWE encryption is not yet standardized (IETF drafts
are in progress); the id_token is carried inside the TLS tunnel of the
respective profile. (Decisions: `thesis/results/v2/experiment2 - PQC/
DECISIONS.md`, Decision 4; `thesis/results/v4/DECISIONS.md`.)

**Verification mechanism -- deliberately the SAME structure in all 3
profiles**, per Luciano's own explicit requirement: every profile's
verification goes through the identical call site (`verify_jwt()`/
`decrypt_and_verify_jwt()` in `opin_flow.py`), the identical call shape
(one JSON HTTP POST to the SAME persistent Node service this project
already used for pqc/hybrid SIGNING -- `thesis/scripts/pqc-signer/`), and
the identical key source (the AS's/RS's own published `/jwks`).
`start_pqc_signer_service()` is now started for classic too (previously
a no-op there) -- classic's PS256 verification COULD run in-process via
pyjwt directly; it is routed through this same service anyway, so a
measured timing difference reflects the algorithm, not the architecture.
`signer_core.mjs` gained: a unified `verify_jwt` dispatch (classic/pqc
single-key via `jose.jwtVerify()`; hybrid auto-detects Strong Nesting vs
payload extension by SIGNATURE LENGTH, not header.alg -- id_token's own
header says plain "PS256" even when genuinely Strong-Nesting-signed,
confirmed live, the same header-looks-ordinary asymmetry already
documented for client_assertion/PAR, Decision 9) and a
`decrypt_and_verify_jwt` dispatch (JWE unwrap via `jose.compactDecrypt()`,
then the same verify path on the inner JWS). The hybrid dual-signature
logic (`verifyStrongNesting()`, `verifyPayloadExtension()`) is DUPLICATED
from `mock-service-os/mock_as/utils/opin/hybridVerification.js`/
`payloadExtensionVerification.js`, not imported -- same precedent as
`thesis/scripts/hybrid_verify.py`'s own existing mirror of the first one
(separately deployed Node packages, no shared import path).

**Real bugs found and fixed while building this, live:** (1) the RS's
own `/jwks` is gated behind the SAME Bearer-token/introspection check as
every other RS-facing call (confirmed: 401 without one) -- not fetchable
before the first access token exists, so it is now fetched once per
sub-flow, right after `cc_access_token`, not at the same point as the
AS's own `/jwks`. (2) `isStrongNestingShaped()`'s first version crashed
(uncaught `TypeError`) on a malformed/wrong-kty `classic_jwk` -- a REAL
case, not hypothetical: a key-confusion negative test hits it directly.
Fixed to fail closed (`{valid:false,...}`), with `handleRequest()`
itself now wrapping both verify paths in try/catch so NO input can ever
crash the service into an uncaught 500 instead of a clean rejection.

**Negative tests, all mandatory cases, real artifacts, real local stack
(`thesis/scripts/tests/test_signature_verification.py`), one process per
profile (`CRYPTO_PROFILE=<profile> python -m pytest ...`):**

| Profile | Tampered signature | Wrong key | Wrong algorithm | Scheme confusion (hybrid only) |
|---|---|---|---|---|
| classic | REJECTED | REJECTED | REJECTED | n/a |
| pqc | REJECTED | REJECTED | REJECTED | n/a |
| hybrid | REJECTED | REJECTED | n/a (dispatches by signature shape, not a declared alg) | REJECTED |

One transient flake observed once during this turn's own testing
(`test_tampered_signature_rejected`, classic, failed once inside a full-
suite run immediately after a profile switch's own settling runs, passed
every other time including immediately re-run alone and re-run as part
of the full suite again) -- consistent with container/proxy startup
timing right after `switch_crypto_profile.py`, not a logic defect
(confirmed: the SAME test, SAME artifacts, passes deterministically once
the stack has settled). Flagged here rather than silently re-run away.

### Item 2 -- migration audit, real traffic, all 3 profiles

| | Classic | PQC | Hybrid |
|---|---|---|---|
| mTLS KEM group (real, negotiated) | secp384r1 | mlkem1024 | secp384r1mlkem1024 |
| mTLS client cert chain | `ca.crt` (RSA) | `root_ca_pqc.crt` (ML-DSA-65, self-signed) -> `client_one_pqc.crt` | `ca.crt` (RSA) + ML-DSA-65 alt-signature extension (`mock_mtls/main.go`, read only) |
| client_assertion / PAR request object | PS256 | ML-DSA-65 | RS256 + payload-extension `pqc` claim (ML-DSA-65) |
| JARM | PS256 | ML-DSA-65 | Strong Nesting (header genuinely `MLDSA65-RSA2048-PSS-SHA256`) |
| RS-signed responses | PS256 | ML-DSA-65 | RS256 + payload-extension `pqc` claim (ML-DSA-65) |
| id_token inner signature | PS256 | ML-DSA-65 | Strong Nesting (header says "PS256", real sig is sigma1\|\|sigma2) |
| id_token outer encryption | RSA-OAEP/A256GCM | **RSA-OAEP/A256GCM (classical)** | RSA-OAEP/A256GCM |
| AS /jwks "sig" entry kty | RSA | AKP | HYBRID (composed, decomposes to RSA+AKP) |
| PKI/CRL stand-in chain | `ca.crt` signs both root-ca.pem/issuer-ca.pem (siblings, NOT a root->issuer chain) | real 2-level: root_ca_pqc self-signed, issuer_ca_pqc signed by it | same as classic (`ca.crt`) |

**Verdict per profile, against Luciano's own stated criterion:**
- **Classic: CONFIRMED.** No post-quantum algorithm anywhere, any
  artifact, any channel -- confirmed by the table above, every row.
- **PQC: CONFIRMED, with ONE documented, pre-existing exception.**
  id_token's own JWE encryption (RSA-OAEP) is classical -- the one
  classical algorithm remaining anywhere in this profile's own traffic,
  already decided out of scope (Decision 4, `thesis/results/v2/
  experiment2 - PQC/DECISIONS.md`; reaffirmed `thesis/results/v4/
  DECISIONS.md`). Every other artifact and channel (mTLS KEM, mTLS
  client cert chain, client_assertion, PAR, JARM, RS responses, id_token's
  own inner signature, PKI/CRL chain) is fully ML-DSA-65/mlkem1024, zero
  classical.
- **Hybrid: CONFIRMED** against its own design (Decision 14 and
  predecessors): every artifact that is supposed to carry BOTH a
  classical and a post-quantum signature does (Strong Nesting for
  id_token/JARM, payload extension for client_assertion/PAR/RS
  responses), confirmed live, both halves independently verified,
  AND-gated. id_token's own JWE encryption is classical here too, by the
  SAME already-documented, profile-independent decision above -- not a
  hybrid-specific gap.

### Item 3 -- local recalibration, all 3 profiles, real runs

| | Classic | PQC | Hybrid |
|---|---|---|---|
| call_count | 44 (was 42) | 44 | 44 |
| total_bytes_exchanged | 126,777 | 281,654 | 339,145 |
| N_JWT | 28 (unchanged) | 28 | 28 |
| N_JWK | 4 (was 2) -- corrected, see Decision 88 | 4 | 4 |
| N_PKI | 4 (unchanged) | 4 | 4 |
| N_mTLS | 6 (unchanged -- no new TLS connections, confirmed architecturally: the new call reuses an existing pool) | 6 | 6 |

**N_JWK correction (Decision 88 supersedes this row):** this entry's own
`6/6/8` was a raw count of every `jwk_sizes` list entry across all calls
(including "enc" keys, and, for hybrid, a since-discovered SECOND "sig"
entry per response) -- not what N_JWK actually means (one "sig" key per
`/jwks` fetch). The correct figure, all 3 profiles, is **4** (2 AS +
2 RS fetches, one counted sig key each) -- see Decision 88 for the full
recomputation and the `term_jwk()` fix this required.

**The +2 calls (one per sub-flow) are the RS's own `/jwks`**, fetched
once each, needed to verify RS-signed responses at all -- not possible
to avoid (that key was never fetched anywhere in the original 42-call
sequence) and not free: +1,712 bytes for classic (2 small RSA JWKS
responses), proportionally similar for pqc/hybrid (their own larger
keys). N_JWT is unaffected (the new calls aren't JWT-bearing). N_JWK
rises because there are now 4 `/jwks` fetches total (2 AS + 2 RS, one
pair per sub-flow) instead of 2, each contributing its own key count --
not a uniform "+4" across profiles, since hybrid's own `/jwks` responses
publish more keys per fetch (the composed HYBRID entry plus a
standards-compatible plain RSA/AKP entry alongside it).

**`BASELINE_BYTES`** (`thesis/results/v8/campaign/scripts/
pilot_acceptance.py`) updated to `{"classic": 126_777, "pqc": 281_654,
"hybrid": 339_145}`, documented in the constant's own comment. No other
`pilot_acceptance.py`/`consolidate_v8.py` criterion hardcodes
`call_count`/`N_JWK` against a fixed expected value (checked directly) --
only this constant needed updating. The REAL AWS pilot data already
committed (`thesis/results/v8/latency/`, Decision 85) was collected with
the PRE-verification opin_flow.py (42 calls) -- it is now stale relative
to this new baseline and would fail Criterion 1 if re-checked; this is
expected, not a regression, and is exactly why the "what to adjust
before the full campaign" list below exists. `consolidate_v8.py`'s own
`term_jwk`/`n_jwk`/OPINsize computation reads these fields generically
from whatever `calls.jsonl` actually contains, so it does not need a
code change for the new counts -- only a future real campaign's own
collected data will reflect them.

**T_fluxo order (Classic < PQC < Hybrid): NOT re-confirmed with new
statistical weight this turn.** Single-execution wall-clock times
captured incidentally while validating the full flow (classic 3.59s,
pqc 2.78s, hybrid 4.05s) do NOT show this order -- but these are ONE
execution each, dominated by this run's own container/connection warm-up
noise (no settling runs preceded these specific timed calls the way a
real campaign's own protocol requires), not a comparable measurement.
Not treated as evidence either way; a real T_fluxo comparison needs the
existing, already-validated campaign protocol (settling runs, N>=10,
warmup discarded), not a one-off call from this turn's own verification
testing.

**Full test suite:** `thesis/results/v8/campaign/scripts/tests/` --
13/13 pass (unaffected by this turn, no campaign-script code touched).
`thesis/scripts/tests/test_signature_verification.py` -- all mandatory
cases pass, all 3 profiles (see table above).

### Item 4 -- verdict

**Fluxo completo: CONFIRMED.** Every signed artifact the client receives
is now verified, in all 3 profiles, through one uniform mechanism;
`verify_signature=False` no longer exists anywhere in `opin_flow.py`;
all mandatory negative tests pass in all 3 profiles.

**Migração total: CONFIRMED for classic and hybrid; CONFIRMED for pqc
with one documented, pre-existing, out-of-scope exception** (id_token's
JWE encryption, RSA-OAEP, Decision 4/thesis/results/v2 and v4) -- no
other classical algorithm remains anywhere in pqc's own traffic.

**What's missing / what to adjust before the next full campaign:**
1. The real AWS pilot data already committed (Decision 85) predates this
   turn's verification wiring (42 calls, old `BASELINE_BYTES`) -- a
   future real campaign run will produce 44-call data under the NEW
   baseline; the two are not directly comparable call-for-call without
   accounting for the 2 new RS `/jwks` fetches per execution.
2. T_fluxo's own Classic<PQC<Hybrid ordering needs re-confirming under
   the new, verification-enabled flow, with the real campaign's own
   protocol (N>=10, settling runs) -- not assumed unchanged just because
   the flow's own shape is similar.
3. The one transient test flake (classic, this turn) is worth a second
   look if it recurs during real campaign execution, where a false
   verification failure would abort a real, paid AWS run -- not treated
   as a blocker here (reproduced zero times out of several additional
   runs), but worth keeping an eye on.

## 88. The negative-test "transient flake" from Decision 87 was a bug in the TEST's own tamper() helper, not a race anywhere in opin_flow.py/signer_core.mjs -- root-caused and fixed, 60/60 repeats clean across all 3 profiles. OPINsize recomputed for the real 44-call flow and corrected a second real bug found along the way (hybrid's `/jwks` now publishes two "sig" entries for one key); V8_OPINSIZE is now Criterion 10's own reference, v7 kept informative. No AWS touched.

**Item 1 -- root cause, not "didn't reproduce".** Ran the full negative-
test battery 20 times per profile (60 runs total), fresh proxy+signer
service each iteration, immediately after each profile switch for the
first iteration in every batch. First pass (the ORIGINAL tamper
helper): classic showed 5/20 iterations with the tampered signature
WRONGLY ACCEPTED (`UNEXPECTED_PASS`) -- a real, reproducible 25% failure
rate, not a one-off. Root cause, confirmed by direct inspection of a
real captured signature: the original `_tamper_signature()` swapped the
signature segment's own LAST BASE64URL CHARACTER (to "A", unless it
already was "A") -- for a 256-byte RSA-2048 signature, that character's
own 6-bit value has its bottom 4 bits as pure, decoder-ignored padding
(256 bytes doesn't divide evenly into base64's 3-byte groups); only its
top 2 bits are real signature bits. Whenever the ORIGINAL character's
6-bit value already had both top bits zero -- any of "A".."P", 16 of 64
possible values, exactly a 25% chance -- replacing it with "A" (value 0)
left those two real bits unchanged, so the "tampered" signature decoded
to the IDENTICAL raw bytes as the original. Confirmed directly: a real
captured signature whose last character happened to be "A" produced a
byte-for-byte identical "tampered" version (`original sig == tampered
sig: True`), which `verify_jwt()` then correctly, legitimately accepted
-- the test's own "must be rejected" assertion was the thing that was
wrong, not the production code. The correlation with a slow
`t_proxy_ready` in the original data was coincidental (different
executions' consent claims differ, so each gets a genuinely different
RSA signature whose own last character varies by chance independently
of how long the proxy took to start) -- confirmed by re-running with the
fix: **0/20 anomalies, all 3 profiles, 60/60 total**, including the
first iteration of every batch, immediately after a fresh profile
switch. No race exists in `opin_flow.py`'s own flow, no health-check
fix was needed there, and none was made -- `_wait_for_pqc_signer_service_
ready()`/`_wait_for_tls_kem_proxy_ready()` were already polling real
readiness (an actual `/healthz`/HTTPS round trip), not a sleep, before
this investigation and remain unchanged.

Fixed `tests/test_signature_verification.py`'s `_tamper_signature()` to
decode the signature to real bytes, XOR the LAST BYTE with `0xFF`, and
re-encode -- immune to this class of bug by construction (flipping
every bit of a byte cannot leave that byte unchanged, regardless of
base64 alignment). Nothing in `opin_flow.py`/`pqc-signer/signer_core.mjs`
changed as a result of this item -- their own logic was correct the
whole time; the earlier investigation's "corrects to a container-
timing race" framing (Decision 87) is superseded by this finding.

**Item 2 -- OPINsize recomputed for the real 44-call flow, all 4 terms,
all 3 profiles.** Real local executions, gateway log properly time-
windowed to the measured run itself (`docker logs --since <run_start>
--until <run_end>` -- an earlier attempt this same turn, without that
windowing, wrongly folded `switch_crypto_profile.py`'s own 5 settling
executions into the same log capture, inflating N_mTLS to 38; not an
OPINsize bug, a capture-script bug, caught before it reached any
committed number):

| | Classic | PQC | Hybrid |
|---|---|---|---|
| N_mTLS / term_handshake | 6 / 31,074 | 6 / 135,642 | 6 / 114,102 |
| N_JWT / term_jwt | 28 / 37,263 | 28 / 151,321 | 28 / 200,567 |
| N_JWK / term_jwk | 4 / 1,024 | 4 / 7,808 | 4 / 8,832 |
| N_PKI / term_pki | 4 / 8,440 | 4 / 32,028 | 4 / 37,356 |
| **OPINsize** | **77,801** | **326,799** | **360,857** |
| vs v7 (informative only) | +1.13% | +1.21% | +2.96% |

term_handshake/term_jwt/term_pki are UNCHANGED from the pre-
verification 42-call flow's own figures (confirmed: identical values) --
none of the new verification code touches the mTLS handshake, the JWT
population, or the PKI/CRL fetches. Only term_jwk moves, by exactly the
2 new RS `/jwks` fetches' own contribution (classic +512, pqc +3,904,
hybrid +4,416) -- each new fetch counts one more "sig" key, same
definition as before, not a per-key size change.

**A second real bug found computing this: `consolidate_v8.py`'s
`term_jwk()` crashed on hybrid's own real data** (`AssertionError: jwk
sig size not constant: {2208, 256}`). Confirmed live: a real hybrid
`/jwks` response now publishes TWO "sig" entries sharing the SAME kid --
the composed `kty: "HYBRID"` entry (`pk_hybrid`, 2208 bytes) and a plain
`kty: "RSA"` duplicate of just its classical half (256 bytes), published
by `ResponseSigningService.java` "so a real, standards-compliant JWKS
consumer doing ordinary kid+alg discovery can find a key that matches
what a payload-extension-signed JWT's header actually says" (that
file's own comment). `term_jwk()`'s original assert assumed exactly one
"sig" entry per response, true for classic/pqc, no longer true for
hybrid. Fixed to take the LARGEST "sig" entry per call instead of
asserting one constant size across ALL calls -- confirmed correct
against v7's own hybrid figure (2 fetches x 2,208 bytes = 4,416, exactly
v7's own `term_jwk`): the composed key is the real signing key, the
smaller plain-RSA entry is a discovery-compatibility shim for the SAME
key, not a second artifact.

**`pilot_acceptance.py`:** new `V8_OPINSIZE = {"classic": 77_801, "pqc":
326_799, "hybrid": 360_857}`, documented in its own comment. Criterion
10 now gates on `V8_OPINSIZE` (±3%, same tolerance, re-justified: the
largest real single-execution deviation measured this turn, hybrid's
own +2.96% against v7, is the closest real data point available for how
far a single execution can drift from a fixed reference, and is itself
within the 3% band) -- `V7_OPINSIZE` is kept and still printed on every
run, informative only, never gating pass/fail from this turn on. Spot-
checked against the real, already-committed AWS pilot data (pre-
verification, 42 calls): still PASSES (77,289/322,895/356,441, each
exactly `V8_OPINSIZE` minus the 2 new JWK-term entries, 0.66-1.22% off
the new reference) -- consistent, not a coincidence.

**Verification time per artifact: instrumented, not yet collected by a
real campaign.** `opin_flow.py` gained `_VERIFICATION_TIMINGS` (module-
level list) + `get_verification_timings()`/`clear_verification_timings()`,
measuring real wall-clock time around the SAME `_run_verifier()` call
every profile's every verification already goes through, labelled by
artifact (`"jarm"`, `"id_token"`, `"rs_response"`). This needed no change
to `mock_mtls/main.go` (verification never happens there -- it is purely
a client-side, post-receipt step) nor to `tls_kem_proxy/main.go` (the
KEM handshake those files own is a different thing from JWT/JWE
signature verification) -- both stayed untouched, confirmed by the diff.
One real execution each (not yet a many-run median, dominated by the
client<->pqc-signer-service HTTP round trip at this scale, not yet a
clean per-algorithm signal): classic jarm=23.6ms id_token=30.1ms
rs_response=16.5ms; pqc 28.0/37.7/22.2ms; hybrid 22.9/15.9/10.6ms. NOT
yet wired into `campaign_client_runner.py`'s own JSON output -- that is
a separate, future change (collecting it for real across a campaign),
out of this turn's own scope; the accumulator exists so that change
doesn't need to re-derive where the data comes from.

`METRICS_COVERAGE.md` updated: OPINsize/N_JWK/call-count rows reflect
the new 44-call figures and explain the N_JWK change; a new row
documents the verification-timing instrumentation and its own real
numbers.

**id_token's own JWE encryption, registered in neutral terms, per
Luciano's own wording, not treated as a pending item or a risk:** JWE
encryption of the id_token remains RSA-OAEP in all three profiles,
since post-quantum JWE encryption is not yet standardized (IETF drafts
are in progress); the id_token is carried inside the TLS tunnel of the
respective profile. (Decisions: `thesis/results/v2/experiment2 - PQC/
DECISIONS.md`, Decision 4; `thesis/results/v4/DECISIONS.md`.) Nothing
implemented for this -- out of scope by the same decisions as before.

**Not a protocol change.** `mock_mtls/main.go`/`tls_kem_proxy/main.go`
untouched (confirmed by diff). No AWS touched this turn.

## 89. Piloto 2 completo na AWS real (60/60 execuções, 44 chamadas, verificação ativa) -- achado de ordem (Hybrid mais rápido que PQC) registrado como observação em investigação, NÃO interpretado; diagnóstico local (sem AWS) separou parte do confundimento; dois bugs reais do orquestrador corrigidos com testes; verificação-timing e Criterion 6/N=30 fechados.

**Piloto 2 rodou real, ponta a ponta.** 27 recursos Terraform criados e
verificados; testes negativos (`tests/test_signature_verification.py`)
passaram contra a AWS real nos 3 perfis, logo após cada troca; 60/60
execuções reais coletadas (10/perfil x 2 cenários, `call_count=44` em
todas); dados puxados e verificados por sha256; bateria de aceitação
10/11 PASS; teardown completo, 27 recursos destruídos, as 7 regiões
confirmadas limpas via `aws ec2 describe-instances`/sg/key-pair/volume/
EIP direto (não só o exit code do `terraform destroy`), incluindo o
controle (sa-east-1). Custo real estimado ~US$1,10 (infraestrutura em
pé ~3h40min) -- Luciano confere o valor exato no Billing console.

**Reorganização de pastas (decisão do Luciano, não minha escolha
unilateral):** piloto 1 e piloto 2 usavam o MESMO caminho
(`thesis/results/v8/latency/experiment{1,2,3}.../sa-east-1/{L0,L325}/`)
-- copiar o piloto 2 para lá teria sobrescrito os arquivos reais do
piloto 1, que o `PILOT_1_NOTE.md` e o runbook dizem explicitamente que
devem ser preservados. Perguntado antes de tocar em qualquer arquivo;
Luciano escolheu pastas próprias para os dois:
`thesis/results/v8/latency-pilot1-no-verification/` (42 chamadas, não
usado no artigo, intocado) e
`thesis/results/v8/latency-pilot2-full-flow/` (44 chamadas,
verificação ativa, dados do artigo) -- `consolidated.json`/
`CONSOLIDATED_REPORT.md` regenerados no novo caminho com o
`consolidate_v8.py` já corrigido desta rodada (números idênticos ao
que já estava gravado; só o schema ganhou o campo novo de verification
timing, ver abaixo).

**O achado (registrado aqui como observação, não como conclusão
causal):** T_fluxo real mostrou Hybrid mais RÁPIDO que PQC, intervalos
de confiança bootstrap (95%) não se sobrepondo em L0: Hybrid mediana
9,030s [8,946, 9,457] vs PQC mediana 10,524s [10,346, 10,822]; em L325
os intervalos quase não se sobrepõem (Hybrid [28,499, 28,819] vs PQC
[28,805, 29,151]). Contraria a ordem esperada Classic < PQC < Hybrid.

**Diagnóstico local (sem AWS), pedido antes de qualquer interpretação
causal -- "não concluas antes de testar todas as hipóteses":**

1. *Efeito de ordem/janela, com os dados reais do piloto 2 em si.*
   `_campaign-control/windows/sa-east-1/window01.json` confirma: UMA
   única janela rodou (não as 3 do protocolo completo), com ordem de
   perfil sorteada (seed=1806032845) e resultado PQC -> Classic ->
   Hybrid -- PQC rodou primeiro (logo após a entrega+assentamento da
   instância recém-criada), Hybrid rodou último. Com uma única janela,
   ordem e identidade do perfil são PERFEITAMENTE confundidos nesta
   amostra: não há como separar estatisticamente "PQC é lento por ser
   PQC" de "PQC é lento por ter rodado primeiro" só com estes dados.
   Dentro de cada bloco de 10, não há tendência de queda clara (run01
   não é sistematicamente o mais lento do seu próprio bloco, exceto
   levemente em classic) -- o assentamento de 5 execuções antes da
   coleta parece ter absorvido o grosso do aquecimento DENTRO de cada
   bloco; o que não dá pra descartar é um efeito de aquecimento da
   INSTÂNCIA como um todo (CPU credit/frequency scaling de uma EC2
   recém-lançada), que afetaria o bloco que roda primeiro
   (PQC) mais que os que rodam depois, independente do algoritmo.

2. *Decomposição por chamadas/servidor/CPU, dados reais do piloto 2.*
   Em L0: soma das 44 `latency_ms` de `calls.jsonl` é pequena e
   PARECIDA entre perfis (classic 469,5ms / pqc 427,6ms / hybrid
   509,4ms mediana) -- ou seja, 90-96% do T_fluxo de cada perfil NÃO
   está nas chamadas HTTP em si, mas num resíduo ("gap" = T_fluxo menos
   soma das chamadas) de 5.034,9 / 10.101,6 / 8.519,8ms
   (classic/pqc/hybrid). `opin_processing_ms` (perna do servidor,
   `consolidate_v8.py`'s `opin_processing_stats()`) é minúsculo e
   igual entre perfis (6,0 / 6,0 / 7,5ms mediana) -- não é o servidor.
   Duração do handshake mTLS também pequena e sem favorecer hybrid
   (14,0 / 3,0 / 14,0ms) -- não é o handshake. CPU do cliente é
   PARECIDA entre pqc e hybrid (22,33% / 21,22% médio) e mais alta que
   classic (16,79%) -- ou seja, o custo de CPU em si não diferencia
   pqc de hybrid; a diferença de ~1,58s no "gap" entre os dois não é
   explicada por nenhuma perna medida (chamadas, servidor, handshake,
   CPU) -- sobra para operações locais de assinatura/verificação via
   o serviço `pqc-signer` (Node.js, chamadas HTTP locais ao
   `signer_core.mjs`, não instrumentadas em `calls.jsonl`) e/ou para o
   efeito de ordem do item 1.

3. *Auditoria de assimetria de arquitetura.* Tabela operação x perfil:
   verificação de CADA artefato assinado recebido (id_token, JARM,
   resposta do RS) passa pelo MESMO serviço `pqc-signer` nos 3 perfis
   (inclusive classic, que não usa `pyjwt.decode()` para isso) -- mas
   hybrid faz o dobro de checagens de assinatura por artefato
   (Strong Nesting: sigma1 clássica + sigma2 ML-DSA-65) contra UMA
   checagem do PQC puro; o lado servidor espelha isso (hybrid compõe
   e publica DUAS entradas "sig" no `/jwks`, Decision 88). Ou seja,
   arquiteturalmente hybrid faz um SUPERCONJUNTO do trabalho
   criptográfico do PQC puro (nunca menos) -- o achado real (hybrid
   mais rápido) é inconsistente com uma explicação pura de "custo de
   algoritmo", e consistente com um confundimento de ordem/posição
   (item 1).

4. *Teste local controlado, ordem ABBA alternada.* `switch_crypto_profile.py`/
   `latency_automation.run_once_timed_with_retry()` reaproveitados
   (sem nenhuma mudança em `opin_flow.py`/`main.go` -- confirmado por
   diff), stack local, padrão Classic/PQC/Hybrid/Hybrid/PQC/Classic
   repetido 5 vezes (30 slots, 2 execuções/slot, troca de container só
   quando o perfil muda de fato -- 60 execuções reais, N=20/perfil; um
   soluço real de infra no meio -- CHECKPOINT do psql em 6,21s,
   limiar 5,0s -- tratado reiniciando o container psql e retomando a
   partir do slot interrompido, sem perder dados já gravados).
   Resultado real, com bootstrap 95% CI:
   - classic: mediana 3,265s, IC [3,112, 3,453]
   - pqc: mediana 2,701s, IC [2,629, 2,826]
   - hybrid: mediana 3,456s, IC [3,148, 3,701]

   Ordem local (sem latência WAN): **PQC < Classic < Hybrid** -- nem a
   ordem esperada da literatura (Classic < PQC < Hybrid) nem a ordem
   real da AWS (Hybrid < PQC) se reproduzem aqui. O que importa para o
   achado: IC de hybrid [3,148, 3,701] e de pqc [2,629, 2,826] NÃO se
   sobrepõem -- com ordem sorteada/alternada e N=20/perfil (bem mais
   poder estatístico que os N=10 da AWS), **hybrid é
   significativamente MAIS LENTO que PQC localmente**, o oposto exato
   do que o piloto 2 mostrou na AWS real.

   Efeito de posição/troca checado diretamente: comparando a primeira
   execução de um slot que trocou de perfil contra a primeira execução
   de um slot encadeado (mesmo perfil do slot anterior, sem troca), não
   há penalidade sistemática de "primeiro depois da troca" em nenhum
   perfil (hybrid até inverteu: slots encadeados vieram mais lentos que
   os que trocaram, n pequeno por célula, provavelmente ruído). Por
   ciclo (1 a 5, cobrindo os ~45 minutos do teste todo) a mediana não
   cai monotonicamente -- 3,396 / 3,080 / 2,881 / 3,157 / 3,361s --
   sem um padrão claro de aquecimento do processo como um todo.

**Conclusão:** o achado real da AWS (hybrid mais rápido que PQC) **não
se sustenta** quando a ordem é controlada/alternada e o N sobe para 20
por perfil -- localmente a relação se INVERTE (hybrid significativamente
mais lento que PQC), batendo com o que a auditoria de arquitetura
(item 3) já apontava: hybrid faz um superconjunto do trabalho
criptográfico do PQC puro (duas verificações de assinatura por
artefato contra uma), nunca deveria ser mais rápido num ambiente sem
confundimento. O teste local também não achou evidência de uma
penalidade simples de "primeiro-depois-da-troca" que explicasse o
achado da AWS por si só. A explicação mais parcimoniosa com as
evidências reunidas: o resultado da AWS é um artefato da JANELA ÚNICA,
NÃO ROTACIONADA, do piloto 2 (PQC sorteado primeiro, Hybrid sorteado
por último, nenhuma repetição com outra ordem) combinado com algum
efeito específico daquele ambiente/execução (ex.: throttling de CPU de
uma instância EC2 recém-lançada ainda não estabilizada durante o
PRIMEIRO bloco de perfil, que por acaso foi o do PQC) -- não uma
propriedade real do algoritmo ML-DSA-65 puro vs. híbrido. Isso é uma
hipótese bem fundamentada pelos dados reunidos, não uma certeza: os
dados reais do piloto continuam sendo os dados reais, e a única forma
de confirmar ou refutar isso de verdade é repetir a medição na AWS com
múltiplas janelas de ordem sorteada independentemente (ver abaixo).

**O que falta confirmar na AWS real:** rodar o piloto 2 (ou a campanha
completa) com as 3 janelas do protocolo original e ordem sorteada
INDEPENDENTEMENTE por janela (já suportado por
`campaign_run.py`'s `profile_order = PROFILES[:]; rng.shuffle(...)`) --
só com múltiplas janelas, cada uma com uma ordem diferente, dá pra
separar estatisticamente ordem de algoritmo nos dados REAIS de rede;
o teste local acima testa se o efeito aparece numa rede sem latência
WAN, não se ele se reproduz com latência real.

**Correções (item 3):**

1. `campaign_run.py`'s `run_window()`: uma instalação sem nenhum
   cenário habilitado no inventário deste run (ex.: piloto escopado só
   para sa-east-1, rodando contra a lista completa de instalações da
   campanha) chamava `sys.exit()` -- abortava o processo inteiro do
   orquestrador, não só aquela instalação. Confirmado real no piloto 2
   (us-east-1, sem cenário habilitado, veio depois de sa-east-1 na
   ordem de iteração) -- inofensivo NESTA execução só porque
   sa-east-1 já tinha terminado as 60 execuções antes da iteração
   chegar em us-east-1; numa campanha com mais de uma instalação
   escopada de forma desigual, teria matado o restante de instalações
   já saudáveis também. Corrigido: agora imprime um aviso e `return`
   (pula só aquela instalação/janela), sem abortar a campanha.
   `tests/test_installation_skip.py` (novo): 3 cenários de inventário
   falso -- piloto só sa-east-1 (confirma us-east-1 pulado sem
   SystemExit e sa-east-1 seguindo normal), campanha completa
   (confirma nenhuma instalação pulada), instalação totalmente ausente
   do inventário (mesmo resultado do caso 1). `test_block_order.py`
   (existente) confirmado ainda passando.

2. `already_done()`/o loop round-robin (`campaign_run.py`, já
   existente, não alterado): confirmado por leitura direta do código
   que `Restart=on-failure` NÃO repete execuções já gravadas -- cada
   `(window, scenario, global_run_index)` é checado contra
   `run{NN}.json` já existente em disco antes de rodar; um restart
   reentra no mesmo loop e só "resume past it" pelas que faltam.
   Comportamento pré-existente, correto, não precisou de correção
   nem de teste novo -- só verificação.

3. Verificação-timing por artefato: `campaign_client_runner.py` agora
   chama `of.clear_verification_timings()` antes de cada execução
   cronometrada e anexa `of.get_verification_timings()` ao resultado
   (`result["verification_timings"]`, lista de `{artifact,
   duration_ms}`) -- os MESMOS timers que `verify_jwt()`/
   `decrypt_and_verify_jwt()` já gravavam, só agora surfaçados.
   `consolidate_v8.py` agrega por artefato (`verification_timings_ms.
   per_artifact`, mediana/min/max/bootstrap CI) e reporta no
   `CONSOLIDATED_REPORT.md`; dados reais do piloto 2 (anteriores a
   esta mudança) corretamente marcados `"missing (run predates
   campaign_client_runner.py wiring)"`, não um zero falso. Overhead do
   cronômetro medido diretamente (`timeit`, 100k repetições): 0,737
   microssegundos por chamada de verificação (dois `time.monotonic()`
   + um `list.append()`) -- com 3-6 verificações por execução, overhead
   total por execução ~2-4 microssegundos, desprezível contra um
   T_fluxo de segundos (menos de 1 parte em 1 milhão). Não altera o que
   T_fluxo mede além deste overhead já existente antes desta mudança
   (a instrumentação em si já rodava dentro da janela cronometrada;
   só a exposição no JSON é nova). Validado localmente, de ponta a
   ponta: uma execução real (classic) produziu `verification_timings`
   com 7 entradas reais (3 `rs_response`, 2 `jarm`, 2 `id_token`); um
   diretório de cenário sintético com 3 execuções, passado por
   `consolidate_profile_scenario()`, produziu medianas/IC bootstrap
   por artefato corretamente (ex.: `id_token` mediana 12,5ms sobre 3
   execuções).

4. Criterion 6 (`pilot_acceptance.py`): limiar de ±5% NÃO alterado.
   Documentado que o piloto usa N=10/célula e a campanha completa usa
   N=30/célula (`RUNS_PER_WINDOW=10` x `WINDOWS_PER_CAMPAIGN=3`).
   Projeção via bootstrap (resample a N=30 a partir dos 10 valores
   reais do piloto 2, 2000 resamples, mesmo método de
   `bootstrap_median_ci()`): a ÚNICA célula que falha hoje em N=10
   (hybrid/L0, largura 5,7% do IC) projeta 3,8% em N=30 -- dentro do
   alvo. Todas as outras células já passam em N=10 e projetam ainda
   mais estreitas em N=30 (ex.: pqc/L0 4,5% -> 2,1%). N=30 deve ser
   suficiente para o alvo de ±5% sem precisar mudar o limiar.

## 90. Contabilidade completa do T_fluxo (novas categorias signing/setup/wait, resíduo caracterizado via cProfile real); ordem balanceada por quadrado latino + aquecimento de instância + posição como covariável; portões de validação (24 execuções) e de aceite da janela 1; campaign_down.sh sem prompt interativo. Sem AWS -- só código, testes locais, docs.

Turno de 4 itens, todos sem tocar AWS, `mock_mtls/main.go` ou
`tls_kem_proxy/main.go` (confirmado por diff ao final de cada item).

### Item 1 — Contabilidade completa do T_fluxo

`opin_flow.py` já tinha `_VERIFICATION_TIMINGS` (turno anterior). Esta
sessão acrescentou duas categorias novas e confirmou uma terceira como
"efetivamente zero por construção":

- **`_SIGNING_TIMINGS`** (novo): `sign_jwt()` agora cronometra a si
  mesmo (um único ponto de wrap cobre os 3 ramos -- PS256 via pyjwt,
  ML-DSA-65 via `_run_pqc_signer()`, hybrid via `_sign_jwt_hybrid()`,
  que por sua vez chama `_run_pqc_signer()` de novo), com um parâmetro
  `artifact` livre (mesma convenção de `verify_jwt()`). `make_client_
  assertion()`/`make_request_object()` passam esse `artifact` adiante;
  os 4 pontos de chamada reais (`/token` client_credentials, PAR
  request_object, PAR assertion, `/token` authorization_code) recebem
  rótulos distintos (`client_assertion:token_cc`,
  `request_object:par`, `client_assertion:par`,
  `client_assertion:token_ac`).
- **`_WAIT_TIMINGS`** (novo): o ÚNICO `time.sleep()` dentro da janela
  medida de T_fluxo é o loop de poll em `wait_for_authorization_code()`
  esperando o callback local -- cronometrado só no caminho de SUCESSO
  (o caminho de retry/descarte já é excluído de T_fluxo via
  `wasted_seconds`, cronometrá-lo de novo aqui seria contar o mesmo
  tempo duas vezes). Todo outro `time.sleep()` do arquivo roda FORA da
  janela medida (dentro de `start_tls_kem_proxy()`/`start_pqc_signer_
  service()`, chamados uma vez por BLOCO, não por execução) ou dentro
  do caminho já descartado.
- **`_SETUP_TIMINGS`** (novo, achado real via profiling, não previsto
  no pedido original): uma primeira validação local (classic, 3
  perfis) mostrou um resíduo (T_fluxo menos a soma de HTTP+signing+
  verification+wait) de **~75% do T_fluxo** -- muito alto para aceitar
  sem investigar. Um `cProfile` real de uma execução local (classic)
  identificou 3 custos reais, específicos, nunca antes instrumentados,
  nenhum deles assinatura/verificação/KEM/chamada HTTP:
  - `load_signing_key` -- construção do objeto de chave RSA a partir
    do JWK de assinatura do cliente (`cryptography`'s own
    `RSAPrivateNumbers.private_key()`), ~0,42s/chamada, 2x/execução
    (uma por sub-fluxo, dentro de `load_client_signing_key()`).
  - `generate_callback_cert` -- geração de um keypair RSA-2048
    descartável para o certificado TLS auto-assinado do callback OIDC
    local (`_generate_callback_tls_cert()`), ~0,26s/chamada,
    2x/execução.
  - `callback_server_teardown` -- `socketserver.serve_forever()` da
    stdlib do Python faz poll via `select()` com `poll_interval=0,5s`
    fixo; `shutdown()` precisa esperar o poll EM CURSO retornar antes
    de parar, pagando até ~0,5s por chamada -- não é código deste
    projeto, é um detalhe da stdlib nunca visto antes porque nunca
    tinha sido cronometrado.
  Nenhum dos três é assinatura, verificação, operação KEM, ou chamada
  HTTP a uma parte do OPIN -- é scaffolding do próprio harness de
  teste (geração de cert/chave local, ciclo de vida do servidor HTTPS
  de callback), por isso ganhou categoria própria em vez de ficar
  escondido dentro do resíduo.

**Resultado após instrumentar `_SETUP_TIMINGS`**: resíduo caiu de ~75%
para **14-24% do T_fluxo**, nos 3 perfis, validado com 3 execuções
reais cada (classic, pqc, hybrid) contra a stack local -- não um
único ponto, uma amostra pequena mas real. Números medianos (segundos,
3 execuções/perfil):

| perfil | T_fluxo | http | signing | verification | wait | setup | resíduo | resíduo % |
|---|---|---|---|---|---|---|---|---|
| classic | 3,22 | 0,57 | 0,07 | 0,11 | ~0 | 1,98 | 0,48 | 14,7% |
| pqc | 2,65 | 0,56 | 0,12 | 0,12 | ~0 | 1,15 | 0,62 | 23,5% |
| hybrid | 3,40 | 0,58 | 0,18 | 0,10 | ~0 | 1,92 | 0,52 | 14,7% |

(mediana de 3 execuções cada; variação execução-a-execução observada
entre 14,5% e 24,1% nas 9 execuções reais -- máquina de desenvolvimento
com ~20 outros containers Docker não relacionados rodando
concorrentemente, ruído de fundo real, não um bug.)

**Resíduo remanescente (14-24%), explicado, não instrumentado
separadamente**: o mesmo `cProfile` confirmou que custo de SSL/TLS
(`load_verify_locations`, `connect()`, `load_cert_chain`,
`enum_certificates`) já está DENTRO do intervalo medido de cada
chamada HTTP (`do_call()`'s own `start`/`end` em volta de
`session.request()`) -- não é um gap adicional, é por isso que
`http_calls_seconds` já é maior do que RTTs puros de loopback
sugeririam. O que resta de fato não-instrumentado é: (a) o handshake
mTLS/KEM em si, que acontece dentro de `tls_kem_proxy`/`mock_mtls`
(Go, off-limits este turno) sem ponto de instrumentação do lado
cliente possível sem tocar `main.go`; (b) overhead geral de
interpretador Python/JSON/dict ao longo de ~230 mil chamadas de função
por execução; (c) o ruído de fundo da máquina já citado. Nenhum desses
é uma categoria que valha inventar sem dados reais -- reportado como
resíduo caracterizado, não um número misterioso.

**Overhead dos próprios cronômetros** (`timeit`, 200k repetições de
`time.monotonic()` + montar dict + `list.append()`): 0,397
microssegundos/chamada. Uma execução real tem ~23 desses eventos (8
signing + 7 verification + 2 wait + ~6 setup) -> overhead total
~0,009ms/execução, **~0,0003% de um T_fluxo de ~3s** -- não altera o
que é medido de forma perceptível.

**Erro de ambiente encontrado e corrigido no caminho** (não é um bug
deste turno, é um achado operacional): a validação local inicial para
o perfil `pqc` falhou com `ValueError: Unknown key type:
2.16.840.1.101.3.4.3.18` (o OID do ML-DSA-65) dentro de
`_verify_cert_signed_by_mldsa65()`. Investigado e confirmado: o
`python` do PATH deste shell é o Python de sistema
(`C:\Python313\python.exe`, `cryptography==46.0.3`, sem suporte a
ML-DSA), não o `.venv` do projeto (`thesis/scripts/.venv`,
`cryptography==50.0.0`, pinado em `requirements.txt` como `50.0.2`).
Confirmado reproduzindo o MESMO erro contra o código ORIGINAL (não
modificado), via `git stash` -- não é uma regressão desta sessão.
Corrigido daqui em diante usando `.venv/Scripts/python.exe`
explicitamente para toda validação local (classic/pqc/hybrid, todas
as 3 reconfirmadas limpas depois da correção).

`consolidate_v8.py`: novos blocos `signing_timings_ms`, `setup_timings_
ms`, `wait_timings_ms`, `phase_accounting` (todos seguindo o mesmo
padrão `status`/`runs_with_data`/estatística agregada de
`verification_timings_ms`, incluindo `"missing (run predates ...)"`
para dados anteriores a este turno, nunca um zero falso). Validado
contra os 11 testes existentes (`test_consolidate_v8.py`, continua
passando sem alteração) e contra uma verificação sintética própria
(3 execuções reais repetidas num diretório de cenário temporário,
confirma que o dado sai por execução E que mediana/IC saem por
célula). `METRICS_COVERAGE.md` atualizado com a linha nova e os
números reais acima.

### Item 2 — Ordem balanceada (quadrado latino) + aquecimento de instância

`run_window()` sorteava `profile_order` de forma independente por
janela (`rng.shuffle`) -- exatamente o que confundiu identidade de
perfil com posição/janela no piloto 2 real (Decision 89: a única
janela real sorteou PQC primeiro e Hybrid por último). Substituído por
`build_latin_square_profile_orders(seed)`: UMA semente para a campanha
toda (não mais uma por janela) sorteia uma permutação-base dos 3
perfis e uma direção de rotação (+1/-1); as 3 janelas são a base e suas
2 rotações cíclicas nessa direção -- um quadrado latino circulante, que
garante de graça a restrição de coluna (cada posição também vê cada
perfil exatamente uma vez) sem rejection sampling. 6 bases x 2 direções
= 12 quadrados possíveis, o total exato de quadrados latinos 3x3 --
todos alcançáveis pela semente. `campaign_up.sh` agora grava
`latin_square_seed` (uma chave) em vez de `window_seeds` (uma por
janela) no `campaign_schedule.json`.

`profile_position_in_window` (0/1/2, `enumerate(profile_order)`) agora
é gravado em todo `run{NN}.json` real, junto do `window` que já
existia -- a covariável que faltava para separar efeito de ordem de
efeito real sem precisar do teste ABBA local inteiro de novo.
`consolidate_v8.py` agrega isso em `t_fluxo_by_window_position.series`
por célula, pronto para a análise usar sem reler cada `run{NN}.json`
manualmente.

**Aquecimento de instância** (`run_instance_warmup()`, novo): uma vez
por instalação, antes do PRIMEIRO bloco da campanha inteira -- 180s
(3 minutos) de fluxos descartáveis (perfil classic) via o mesmo
`run_warmup()` já existente, gravados em
`_campaign-control/instance_warmup/`, nunca na árvore real de dados.
180s não foi escolhido depois de ver resultado nenhum: é uma margem de
50% sobre os ~2 minutos que a Decision 4 (`switch_crypto_profile.py`)
já tinha medido para o fechamento da janela de *settling* de uma
RECRIAÇÃO DE CONTAINER (perturbação mais leve que o boot de uma
instância EC2 nova de verdade, que ainda tem disco EBS frio, cache de
página do SO frio, caches de JIT/interpretador frios).

Testes novos (`tests/test_latin_square_order.py`, 6 casos): o quadrado
é de fato um quadrado latino (linha E coluna, 200 sementes diferentes),
determinístico por semente, não degenerado a uma única ordem, rejeita
`len(PROFILES) != WINDOWS_PER_CAMPAIGN`; `run_instance_warmup()` roda
pelo tempo configurado e depois desliga os proxies, grava fora da
árvore real, pula instalação sem cenário disponível no inventário
(mesma filosofia "pula, não aborta" do item 3 de turnos anteriores).

### Item 3 — Portões de validação e de aceite da janela 1

`run_validation_stage()` (novo): 1 execução por perfil em cada um dos 8
cenários da campanha completa (4 sa-east-1 + 2 us-east-1 + 2
ap-northeast-1 = 8; x 3 perfis = 24 execuções), ANTES da janela 1,
gravadas em `_campaign-control/validation_stage/`, nunca na árvore
real. Depois de escritas, bloqueia em
`wait_for_operator_gate("validation_stage")`. `wait_for_operator_gate()`
(novo) espera indefinidamente (sem timeout, de propósito) um arquivo
marcador (`_campaign-control/gates/<nome>.approved`) que SÓ o operador
cria, depois de puxar a amostra via `campaign_pull.sh` e rodar
`pilot_acceptance.py` contra ela fora da instância -- o orquestrador
em si não tem acesso a pcaps/dados já puxados para rodar isso ele
mesmo (só roda NA instância de controle). Mesmo mecanismo reaplicado
depois da janela 1 inteira completar (`wait_for_operator_gate(
"window1_acceptance")`), antes da janela 2 começar -- aceite completo
sobre o dataset real, não só a amostra de 24.

Testado com inventários falsos (`tests/test_validation_gate.py`, 5
casos): inventário de campanha completa roda exatamente 24 execuções e
chama o portão 1 vez; inventário de piloto (só sa-east-1) roda 6 (3
perfis x 2 cenários), pulando as outras 2 instalações sem abortar;
instalação totalmente ausente do inventário não roda nenhuma execução
mas ainda chega ao portão; o portão retorna na hora se o marcador já
existe, e bloqueia de fato até o marcador aparecer (thread separada
criando o arquivo depois de um delay, confirmado por tempo decorrido).

`PILOT_RUNBOOK.md`: nova seção "Portões da campanha completa" com os 3
passos (aquecimento, validação, aceite da janela 1), o que o operador
precisa fazer em cada um, estimativa rotulada de tempo por etapa
(mesma metodologia das Decisions 47/54/55, não um número exato), e o
critério de aborto específico (se `pilot_acceptance.py` reportar
`OVERALL: FAIL` contra a amostra ou contra a janela 1, o operador NÃO
cria o marcador -- investiga e corrige primeiro).

### Item 4 — `campaign_down.sh` sem prompt interativo

O prompt final (`read -r -p ...`, perguntando se apaga o state/chave
local) foi substituído por um comportamento padrão não-interativo:
sem a flag `--delete-local-state`, o script MANTÉM o state/chave local
(o lado seguro -- ambos já são local-only, no `.gitignore`, nunca
commitados, Decision 49, então manter não custa nada) e reporta
exatamente quais arquivos permanecem e onde. Com `--delete-local-state`,
remove e reporta exatamente o que removeu. Lógica extraída para uma
função nomeada (`report_and_handle_local_state()`) especificamente para
ser testável sem terraform/AWS: `tests/test_campaign_down_local_state.sh`
extrai essa função real do arquivo (não duplica a lógica) e a testa
contra diretórios falsos -- mantém por padrão, remove só com a flag,
não erra com diretório vazio em nenhum dos dois modos, e (o ponto
central do bug original) retorna imediatamente com stdin redirecionado
de `/dev/null`, em vez de bloquear ou falhar com "Inappropriate ioctl
for device".

**O que ficou da execução anterior** (teardown real do piloto 2,
turno anterior, antes desta correção existir): `terraform.tfstate`
(0 recursos -- destroy real já tinha funcionado), `terraform.tfstate.
backup`, `.terraform/`, `.terraform.lock.hcl`, todos em
`thesis/results/v8/campaign/terraform/`, local-only, no `.gitignore`.
Deixados como estão (comportamento padrão, nenhuma ação tomada agora)
-- Luciano pode rodar `rm -rf thesis/results/v8/campaign/terraform/
{.terraform,.terraform.lock.hcl,terraform.tfstate,terraform.tfstate.backup}`
manualmente se quiser limpá-los, ou deixar para a próxima campanha
(Terraform recria o que precisar).

### Fechamento

`scan_secrets.sh` passou antes do commit. Dois commits separados
(código, docs) -- nenhum dado de piloto neste turno, nenhuma chamada
AWS. Testes: 27 (`pytest tests/`) + 10 (`test_campaign_down_local_state.sh`)
+ 6 (`test_latin_square_order.py`, incluído nos 27) + 5
(`test_validation_gate.py`, incluído nos 27) -- todos passando.

## 91. Atestado de perfis (Classic/PQC/Hybrid), medido em execução real contra a stack local, sem AWS -- grupo TLS/versão/algoritmo de assinatura/JWT/JWKS/verificação/hash de config/teste negativo, com quantificação em bytes do custo real da extensão ML-DSA inerte do Hybrid; achado de imagem Docker única; nenhuma FALHA sem explicação concreta -- piloto 3 e campanha NÃO bloqueados

`thesis/results/v8/PROFILE_ATTESTATION.md` (novo). Metodologia: uma
execução real por perfil contra a stack local (sem AWS -- nada aqui
precisava), com captura real de pacotes (sidecar `nicolaka/netshoot`
rodando `tcpdump`/`tshark` no MESMO namespace de rede do container
`insurance-server-lambdas-mtls-1`, via `--network container:...` --
pacotes reais, não sintéticos) cruzada contra o log estruturado real do
próprio gateway (`curveID`/`tlsVersion`/`cipherSuite`/
`mtlsHandshakeBytes`/`clientCertBytes`) e contra os arquivos de
certificado puxados DO CONTAINER RODANDO (`docker exec ... cat
certs/...`, não da cópia local do repo). Commit medido:
`ba63354f56a4b0860ec1c138cc65339cd01c08dd`; hashes de
`opin_flow.py`/`mock_mtls/main.go`/`tls_kem_proxy/main.go`/
`signer_core.mjs` registrados no próprio atestado.

**Achados principais, todos PASSA depois da correção de redação abaixo**:
- Grupo TLS negociado: Classic `CurveP384`/grupo IANA 24; PQC
  `MLKEM1024`/grupo 514; Hybrid `SecP384r1MLKEM1024`/grupo 4589 --
  confirmado por DUAS fontes reais independentes (pcap via `tshark` e
  log do gateway), concordando exatamente nos 3 perfis. TLS 1.3 e
  cipher `TLS_AES_128_GCM_SHA256` em todos.
- Certificado X.509 (handshake): PKCS1v1.5/SHA-256 nos três perfis
  (Classic e Hybrid, RSA-4096; PQC, ML-DSA-65). Nenhuma cadeia de 3
  níveis existe -- é sempre folha->raiz direto (2 níveis); os arquivos
  `root-ca.pem`/`issuer-ca.pem` servidos pelo Directory mock são
  SEPARADOS da cadeia real do handshake mTLS, não fazem parte dela.
- JWT/JWKS: PS256 (Classic), ML-DSA-65 (PQC), e no Hybrid dois
  algoritmos reais distintos (`RS256` para artefatos emitidos pelo
  cliente -- payload-extension, Decision 13; `MLDSA65-RSA2048-PSS-
  SHA256` para artefatos emitidos pelo AS -- Strong Nesting, Decision
  9) -- confirmado em JWTs reais capturados e em `/jwks` reais buscados
  ao vivo. O `/jwks` do RS do Hybrid publica 2 entradas `sig`
  (composta + cópia RS256, Decision 88, reconfirmado ao vivo); o do AS
  publica só 1.
- Verificação: 7 eventos reais de verificação por execução (das 44
  chamadas, 7 carregam artefato assinado verificável), 21/21 sem
  exceção nas 3 execuções reais desta sessão.
- Hashes vs v7: certificados de servidor e de cliente de Classic/Hybrid
  idênticos à v7. O certificado de CLIENTE PQC mudou (commit `478bda5`,
  depois do fechamento oficial da v7) -- motivo real e já documentado
  (fecha uma assimetria: a cadeia PQC da v7 tinha assinatura de CA
  ainda clássica/RSA apesar da chave ser ML-DSA-65; agora é ML-DSA-65
  ponta a ponta). `docker-compose.yml` também mudou (commit `27fc794`)
  -- só ordem de boot, confirmado sem efeito no que é medido.
- Teste negativo: os 3 perfis, como cliente, falharam o handshake real
  contra um servidor de outro perfil -- `tls_kem_proxy`'s own log:
  `remote error: tls: handshake failure`, alerta TLS real, não um
  timeout de rede genérico.

**Correção de redação (pedido explícito, mesma rodada)**: a primeira
versão deste atestado marcou FALHA em 2 linhas por uma formulação de
expectativa que conflava camadas -- corrigido tanto no atestado quanto
em `thesis/README.md`'s própria tabela de perfis (coluna única
"Signatures" dividida em "X.509 certificate signature" e "JWT
signature", e a célula do PQC que dizia "certificates issued by an RSA
CA" -- verdadeira antes do commit `478bda5`, falsa agora -- corrigida
para refletir a cadeia ML-DSA-65 ponta a ponta atual). A regra, agora
explícita nos dois lugares: PS256 é o algoritmo do JWT, não do
certificado (que usa PKCS1v1.5 nos 3 perfis); no Hybrid, a troca de
chaves TLS é híbrida, a autenticação do handshake (certificado) é RSA
puro, e a assinatura dupla (Strong Nesting) vale só na camada JWT -- a
extensão ML-DSA no certificado é inerte no handshake, lida mas nunca
usada pelo `crypto/tls` (confirmado lendo `mock_mtls/main.go`, não
alterado).

**Quantificação em bytes (seção 7 do atestado)**:
- O que a extensão ML-DSA soma ao termo de handshake do Hybrid: as 3
  extensões X.509 custom (`2.5.29.72/73/74`) somam exatamente 5.301
  bytes POR CERTIFICADO (medido via DER real, `mtls_hybrid.crt` e
  `client_one_hybrid.crt` -- idêntico nos dois). Como mTLS transmite
  os dois certificados (servidor + cliente) em cada um dos 6
  handshakes client-facing do fluxo, isso soma **10.602 bytes/handshake
  só da extensão** -- **76,6%** do delta real medido entre Classic e
  Hybrid nos próprios `mtlsHandshakeBytes` do gateway nesta sessão
  (5.112 B vs 18.950 B, delta 13.838 B). O restante (3.236 B) vem do
  key share SecP384r1MLKEM1024 em si (maior que P-384 puro) mais 128 B
  de overhead estrutural não-ML-DSA. Conclusão: a maior parte do custo
  extra de bytes do handshake Hybrid é a extensão inerte, não a troca
  de chaves PQC.
- Efeito da correção do certificado de cliente PQC no OPINsize vs v7 --
  **RESOLVIDO COM MEDIÇÃO** (turno seguinte, 2026-10-27, terceira
  rodada; a "tensão em aberto" registrada antes foi investigada a
  fundo, não deixada por hipótese). Montado localmente, lado a lado, o
  certificado ANTIGO (`478bda5^`, via `git show`, chaves privadas
  reutilizadas sem alteração -- confirmado nunca terem mudado) e o
  NOVO (atual) para os 3 arquivos PQC live-handshake do servidor
  (trocados dentro do volume bind-mount real do `mtls` --
  **achado novo**: `insurance-server-lambdas/docker-compose.yml` monta
  `../mock-service-os/certs/:/app/certs/` do host, os certificados NÃO
  estão embutidos na imagem) e o arquivo do cliente no host, com
  `mtls` reiniciado entre trocas; tudo restaurado via `git checkout` ao
  final, `git status` confirmado limpo. O cliente ATUAL rejeita a
  cadeia antiga por desenho (`verify_ca_chain()` corretamente barra uma
  raiz PQC não auto-assinada em ML-DSA-65 -- confirma, ao vivo, que o
  código de hoje já não voltaria à cadeia antiga); bytes reais do
  handshake antigo foram medidos via um script externo read-only
  chamando `do_call()` diretamente (5 conexões reais), sem passar pela
  checagem de cadeia (lógica do cliente, não requisito do protocolo).
  Medido ao vivo: antigo `clientCertBytes`=2.953 B, `mtlsHandshakeBytes`
  mediana=16.749 B (9 conexões); novo `clientCertBytes`=5.879 B,
  mediana=22.607 B (40 conexões) -- ambos batendo exatamente ou quase
  exatamente com os valores históricos da Decision 14 da v7 (2.953/
  5.879 idêntico; 16.605/22.607, a mediana nova idêntica, a antiga
  0,9% diferente por ruído de amostra pequena). A própria Decision 14
  da v7 (dado bruto, não inferência) já documentava que seu valor
  oficial (322.895 B) é o PÓS-fix, corrigido analiticamente em
  `report_data_v7.json` antes mesmo da v7 citar esse número como
  referência. Reconciliação exata: `delta_handshake (6.002 B) x N_mTLS
  (6) + delta_PKI (3.957 B) x N_PKI (4) = 36.012 + 15.828 = 51.840 B =
  322.895 - 271.055` -- fecha exato. O resíduo de +3.904 B entre
  322.895 (v7) e `V8_OPINSIZE` (326.799) não tem nada a ver com o
  certificado (os dois lados já usam o mesmo, o novo) -- é exatamente
  a adição do `/jwks` do RS no fluxo de 44 chamadas, já documentada em
  `METRICS_COVERAGE.md` antes desta investigação começar (mesmo valor,
  byte a byte: 322.895 + 3.904 = 326.799, fecha exato também.
  **Conclusão (forma "a"): v7 e v8 SÃO comparáveis quanto ao
  certificado PQC.** Nada a declarar ao orientador como viés -- o fix
  já estava corretamente embutido na própria referência da v7 antes
  desta tese citá-la.

**Imagem Docker única**: confirmado via `docker inspect` com os 3
perfis testados na mesma sessão -- `insurance-server-lambdas-mtls`
(`sha256:6f8cbcfb45fb...`) é A MESMA imagem nos 3 perfis; o que muda é
só `CRYPTO_PROFILE` (env var) + os arquivos de certificado que o
binário Go carrega em tempo de execução. Não existem "3 imagens, uma
por perfil".

**Decisão implementada no turno seguinte (2026-10-27, antes do piloto 3,
para não contar como intervenção durante a janela)**: `campaign_run.py`'s
`run_window()` agora grava `gateway_image_id` (novo
`get_gateway_image_digest()`, reusa o MESMO comando `docker image
inspect -f '{{.Id}}'` que `pre_block_checks()` já rodava por bloco, só
que também surfaçado a nível de janela) em `window{NN}.json`, e
`code_hash` (novo `CODE_HASH`, sha256 de `opin_flow.py` +
`campaign_client_runner.py` + `campaign_run.py`, computado uma vez por
processo) em todo `run{NN}.json` (inclusive os da `run_validation_stage()`).
Testado localmente: `get_gateway_image_digest()` contra o Docker real
desta máquina retornou `sha256:6f8cbcfb45fb...` -- o MESMO hash já
confirmado na atestação de perfis acima, a mesma imagem única. 7 testes
novos (`tests/test_image_and_code_hash.py`), incluindo um que edita um
arquivo de verdade e confirma que `CODE_HASH` muda. 34 testes
`pytest` + 10 `bash` no total, todos passando.

**Conclusão**: nenhuma FALHA sem explicação concreta -- piloto 3 e a
campanha NÃO estão bloqueados por este atestado. A tensão da seção 7b
foi resolvida com medição real (terceira rodada, acima) -- v7 e v8 são
comparáveis quanto ao certificado PQC, sem resíduo sem explicação.

## 92. Plano de análise do piloto 3 -- registrado ANTES de olhar qualquer dado real (pedido explícito, item 8 do prompt do piloto 3)

Escopo do piloto 3 (ensaio geral da campanha completa, topologia cheia,
tamanho/janelas do piloto): os 3 servidores (`sa-east-1`, `us-east-1`,
`ap-northeast-1`), os 8 cenários (4+2+2, a lista completa, não a
sub-lista `L0`/`L325` dos pilotos 1/2), 3 perfis, **10 execuções por
perfil/cenário, 1 janela** (não 3) -- `CAMPAIGN_WINDOWS_PER_CAMPAIGN=1`,
sem `MOCKOPIN_ENABLED_CLIENT_SCENARIOS` definido (topologia completa).
Total: 3 x 8 x 10 = **240 execuções reais**, contra as 60 dos pilotos
1/2 (`sa-east-1` só) e as 720 da campanha completa (3 janelas x 240).
45 recursos Terraform (12 instâncias + 12 EIPs + 12 security groups + 7
key pairs de campanha + 1 key pair de operador + 1 chave SSH gerada --
mesma contagem já confirmada ao vivo na Decision 54), 12 instâncias
`m7i-flex.large` (tipo já escolhido e validado nos pilotos 1/2,
reaproveitado, não re-escolhido sem motivo).

**Plano de análise, decidido agora, sem ver nenhum número do piloto 3**:
- Estatística central: mediana por célula (perfil x cenário x servidor),
  a mesma convenção de v1-v7 e dos pilotos 1/2 -- nunca média.
- Incerteza: IC 95% via bootstrap (mesma `bootstrap_median_ci()` já
  usada em `consolidate_v8.py`), reportado ao lado de cada mediana, não
  substituindo-a.
- Covariável: posição do perfil na janela (`profile_position_in_window`,
  item 2 da Decision 90) entra na análise de qualquer inversão de
  latência observada -- junto com decomposição por fase do fluxo
  (`phase_accounting`, Decision 90), tempos por artefato
  (`verification_timings`/`signing_timings`), `steal` máximo, perda de
  pacotes (pcap) e o efeito de instância fria (`run_instance_warmup()`,
  item 2 da Decision 90). Uma inversão Classic/PQC/Hybrid em latência só
  é aceita como explicada se pelo menos uma dessas evidências, medida
  (não hipótese), sustentar a explicação -- "ruído" não é uma categoria
  válida de explicação neste piloto.
- Inversões SEM explicação concreta ficam marcadas **ABERTO** no
  critério de aceite 4 -- não PASSA, não FALHA.
- Nenhum run é removido da amostra por julgamento. Um run só é
  descartado com motivo técnico registrado (ex.: retry de PAR TTL já
  excluído por desenho, falha de verificação de assinatura que abortou
  o fluxo, divergência de grupo negociado) -- cada descarte é contado e
  listado, nunca silenciosamente ausente do denominador.
- Ordem esperada em bytes (OPINsize v8, ±3%): Classic (77.801) < PQC
  (326.799) < Hybrid (360.857) -- critério de aceite 1/4, não column
  aberta a interpretação.

Este parágrafo é o compromisso prévio (pre-registration, mesmo
princípio já usado para o descarte do warmup run nos pilotos
anteriores) -- a análise real do piloto 3, quando os dados chegarem,
segue exatamente isto, não um método escolhido depois de ver o
resultado.

**Addendum (2026-10-28, checagem de cobertura Schardong -- ver Decision
94): três acréscimos ao plano de análise, pedidos explicitamente,
mantendo mediana e bootstrap como estão:**
- **Resumo da distribuição por combinação** (perfil x cenário x
  servidor): mínimo, Q1, Q3, p95, máximo e um histograma de 10 bins --
  `stats_block()` em `consolidate_v8.py` agora inclui isso em TODA
  métrica que já passa por ele (não só T_fluxo), não um cálculo
  separado e paralelo.
- **Shapiro-Wilk**, para registrar a não normalidade (nunca para
  decidir PASS/FAIL de nada) -- mesma regra da Decision 92 original:
  só evidência medida e concreta assenta uma inversão, nunca um teste
  estatístico isolado.
- **Mann-Whitney (postos) entre perfis**, por célula servidor/cenário,
  sobre as amostras reais de T_fluxo -- diz apenas se as distribuições
  são estatisticamente distinguíveis, nunca por si só a causa de uma
  inversão.

Shapiro-Wilk e Mann-Whitney usam `scipy.stats` -- único lugar deste
pipeline de análise que depende de algo fora da stdlib (nunca instalado
em nenhuma instância EC2; `thesis/scripts/requirements.txt`, que É o
runtime real do campo/cliente, não foi tocado). Decisão registrada
explicitamente porque este projeto tem um estilo documentado de evitar
dependência nova para uma necessidade estreita (`pcap_utils.py`, próprio
docstring) -- reimplementar Shapiro-Wilk à mão (algoritmo Royston 1995,
AS R94, com coeficientes tabulados) para uma tese é um risco maior do
que declarar essa dependência: um teste de normalidade silenciosamente
errado é pior do que uma dependência nova e explícita. Mann-Whitney
poderia ser escrito à mão com segurança, mas ficou na mesma biblioteca
para não ter um teste artesanal ao lado de um Shapiro-Wilk de
biblioteca. Degrada honestamente (`"status": "scipy not installed"`)
se `scipy` não estiver disponível no ambiente local de análise, nunca
quebra o `consolidate_v8.py`.

## 93. Incidente real: `campaign_up.sh` destruiu 38 recursos reais (8 instâncias) por uma variável de escopo de piloto antiga esquecida em `campaign.vars.local.sh` -- causa raiz corrigida, duas salvaguardas novas no script, nada perdido além de tempo/dinheiro

**Linha do tempo (UTC, horários dos arquivos de log salvos -- não timestamps
exatos de evento da AWS/Terraform, que não ficaram registrados
separadamente; aproximação honesta, não um número preciso):**

- **~2026-10-28T01:01:40Z** -- `terraform plan` (leitura, topologia
  completa) confirmado: 65 a adicionar, 0 a mudar, 0 a destruir.
- **2026-10-28T01:08:48Z** -- `terraform apply` **aprovado por
  Luciano** (presente, confirmado nesta conversa) iniciado, direto,
  variáveis explícitas, sem `MOCKOPIN_ENABLED_CLIENT_SCENARIOS`.
- **~2026-10-28T01:09:43Z** -- apply aprovado concluído: **"Apply
  complete! Resources: 65 added, 0 changed, 0 destroyed."** 12
  instâncias reais no ar, nas 7 regiões.
- **(entre ~01:09:43 e ~01:11:28Z)** -- SEGUNDO apply, NÃO revisado
  antes de rodar: `./campaign_up.sh campaign.vars.local.sh`, reaproveitando
  o script (em vez do `terraform apply` direto já aprovado) para copiar
  chave/inventário/cronograma e verificar SSH/relógio. Esse script faz
  seu PRÓPRIO `terraform apply -auto-approve` internamente -- e
  `campaign.vars.local.sh` ainda tinha `MOCKOPIN_ENABLED_CLIENT_SCENARIOS=
  "L0@sa-east-1 L325@sa-east-1"` (resquício dos pilotos 1/2), nunca
  limpo. O apply rodou com a topologia ESCOPADA, destruindo tudo que
  não estava nesse subconjunto.
- **~2026-10-28T01:11:28Z** -- saída do script interrompida (erro
  `python3` não encontrado no PATH deste shell, dentro do pipe de
  redação) -- mas o `terraform apply` destrutivo já tinha rodado e
  concluído antes disso (confirmado abaixo, não assumido).

**O que foi destruído de verdade (confirmado por 2 fontes independentes --
`terraform state list` local E `aws ec2 describe-instances` real, 7
regiões, sem ID de conta/ARN em nenhuma chamada) -- 38 recursos, todos
das instalações `us-east-1`, `ap-northeast-1`, e dos 4 clientes remotos
que não co-localizam com `sa-east-1`:**
- 8x `aws_instance`, 8x `aws_eip`, 8x `aws_security_group` (módulos
  `server_us_east_1`, `server_ap_northeast_1`, `client_l0_us_east_1`,
  `client_l0_ap_northeast_1`, `client_ca_central_1_a`,
  `client_ca_central_1_b`, `client_eu_north_1`, `client_ap_northeast_2`).
- 14x `aws_vpc_security_group_ingress_rule` (as regras SSH desses 8
  módulos + as regras de gateway `L0`/`L14`/`L30` de
  `server_us_east_1`/`server_ap_northeast_1` + as regras de gateway
  `L123`/`L219` de `server_sa_east_1`, que FICOU de pé mas perdeu essas
  2 regras específicas).
- Sobrevivente real, confirmado via `aws ec2 describe-instances` (sem
  conta/ARN): `sa-east-1` (controle + servidor + `L0`) e
  `ap-southeast-1` (`L325`) -- exatamente a topologia escopada dos
  pilotos 1/2, igual ao valor esquecido na variável.

**Causa raiz, confirmada por leitura direta (não suposição):**
`campaign.vars.local.sh` (local, gitignored, nunca commitado) linha 16
tinha `export MOCKOPIN_ENABLED_CLIENT_SCENARIOS="L0@sa-east-1
L325@sa-east-1"` -- escrito no turno dos pilotos 1/2, nunca removido
depois. Chamadas à AWS feitas para confirmar o estado real (todas
leitura, nenhuma escreveu nada, nenhuma imprimiu ID de conta/ARN):
`aws sts get-caller-identity` (antes do apply aprovado), `aws ec2
describe-instances` nas 7 regiões (depois do incidente, para confirmar
o que sobrou de verdade), `terraform state list`/leitura local do
`.tfstate` (sem chamada à AWS, só arquivo local).

**Corrigido:**
1. `campaign.vars.local.sh`: linha removida, substituída por um
   comentário explicando o incidente -- deixado SEM a variável é o
   padrão seguro (topologia completa, o default do próprio Terraform).
2. Procurado e não encontrado nenhum outro valor de piloto antigo: nenhuma
   outra variável `MOCKOPIN_*` setada no ambiente deste shell, nenhum
   `*.tfvars` em lugar nenhum do diretório `terraform/`,
   `campaign.vars.example.sh` só tem a mesma linha como exemplo
   COMENTADO (nunca executado).
3. `campaign_up.sh`: duas salvaguardas novas, nenhuma muda o que é
   medido (puramente infraestrutura/segurança):
   - Antes de QUALQUER `apply`, roda `terraform plan` primeiro, imprime
     as variáveis efetivas (sem a IP do operador, sem o conteúdo da
     chave) e o resumo add/change/destroy, e **ABORTA se houver
     qualquer destroy** (um replace conta como destroy+add, já cobre
     os dois) -- a não ser que `--allow-destructive` seja passado
     explicitamente.
   - Aborta também se `MOCKOPIN_ENABLED_CLIENT_SCENARIOS` for um
     subconjunto estrito dos 8 cenários completos, sem a mesma flag --
     exatamente a condição que causou este incidente.
   - `python3`/`python` locais trocados por `PYTHON_BIN`, resolvido em
     tempo de execução checando se o candidato REALMENTE RODA (não só
     se `command -v` o encontra -- o stub da Microsoft Store do
     `python` "existe" no PATH deste Windows sem funcionar, foi
     exatamente isso que mascarou o erro original).
   - A linha que imprimia o IP do operador em texto puro (regra padrão
     já violada antes deste incidente, achada ao investigar) também
     corrigida -- nunca mais impressa.
4. **Testado em modo plan, de verdade, sem nenhum apply** (duas vezes):
   (a) config limpa -- mostrou as variáveis corretas (topologia
   completa), rodou o plan real (38 a adicionar, 0 destruir), seguiu
   até o prompt de orçamento e abortou lá (entrada não-confirmatória
   dada de propósito); (b) `MOCKOPIN_ENABLED_CLIENT_SCENARIOS` setada de
   propósito para o valor escopado, sem a flag -- abortou IMEDIATAMENTE,
   antes de rodar qualquer `terraform plan`, com a mensagem explicando
   exatamente por quê.

**Plano de restauração (preparado, NÃO aplicado -- esperando autorização
explícita de Luciano para o comando exato, conforme pedido):**
`terraform plan` real, config limpa: **38 a adicionar, 0 a mudar, 0 a
destruir** -- 8 `aws_instance` + 8 `aws_eip` + 8 `aws_security_group` +
14 `aws_vpc_security_group_ingress_rule`, distribuídos: `us-east-1` (2
instâncias) + `ap-northeast-1` (2) + `ca-central-1` (2) + `eu-north-1`
(1) + `ap-northeast-2` (1) = 8 instâncias novas, mais 2 regras de
gateway devolvidas a `server_sa_east_1` (que nunca perdeu suas próprias
instâncias). Estado atual real: 4 instâncias; depois deste plano: 12 --
bate exato com o que é esperado.

**Relógio e custo:** o custo real já incorrido com o incidente (apply
aprovado + apply destrutivo + o tempo de investigação) soma ao teto de
US$8 do piloto 3 -- não é descontado. O relógio de 6h, por outro lado,
**recomeça do zero no momento do novo apply (quando autorizado)** --
nenhuma medição chegou a começar; nada do que o relógio de 6h protege
(uma janela de medição em andamento) foi sequer iniciado.

**Atualizado:** `thesis/results/v8/campaign/scripts/campaign_up.sh`
(salvaguardas), `campaign.vars.local.sh` (variável removida, não
commitado -- gitignored), `PILOT_RUNBOOK.md` (regra nova: scripts que
chamam apply/destroy nunca rodam sem o plano e as variáveis efetivas
serem vistos primeiro).

**Restauração aplicada (2026-10-28), com plano salvo em arquivo, não
recalculado -- novo procedimento padrão a partir de agora:**
`terraform plan -out=tfplan` (variáveis explícitas, config limpa),
resumo real conferido ANTES de qualquer apply (**38 a adicionar, 0 a
mudar, 0 a destruir**, IP do operador mascarado na saída -- nenhuma
ocorrência apareceu neste plano específico, já que o módulo `control`
não mudava), depois `terraform apply tfplan` (o MESMO plano, sem
recalcular, sem `-auto-approve` -- a aprovação já está no arquivo
revisado). Toda saída (plan e apply) passou por `redact_aws_errors.py`
mais um segundo filtro que mascara o IP literal do operador (capturado
uma vez em variável de ambiente, nunca impresso). `tfplan` apagado
imediatamente após o apply confirmado; `scan_secrets.sh` rodado de novo
e confirmou PASS (nunca foi commitado) -- `.gitignore` também corrigido
nesse meio tempo: o padrão antigo `*.tfplan` nunca cobria o nome
literal `tfplan` sem extensão que `-out=tfplan` realmente grava (lacuna
real, achada ao verificar, não assumida corrigida).

**Resultado: `Apply complete! Resources: 38 added, 0 changed, 0
destroyed.`** Confirmado por leitura real na AWS (`describe-instances`,
as 7 regiões, sem conta/ARN): **exatamente 12 instâncias**
`pending`/`running` -- sa-east-1:3, us-east-1:2, ap-northeast-1:2,
ca-central-1:2, eu-north-1:1, ap-southeast-1:1, ap-northeast-2:1.
Topologia completa restaurada.

**Início do novo relógio de 6h**: `tfplan` foi salvo em
`2026-10-28T01:24:28Z` (horário do arquivo -- a linha de log com o
horário exato de início do `apply` em si não chegou a ser capturada
nesta rodada, um detalhe de como a saída em segundo plano foi
redirecionada, não algo intencional; reportado com essa imprecisão
honesta em vez de uma hora falsamente precisa). O apply concluiu até
`2026-10-28T01:26:05Z` (horário do arquivo de saída). **Usando o lado
mais cedo e mais conservador da janela, `2026-10-28T01:24:28Z` é o
início oficial do relógio de 6h do piloto 3** -- nenhuma medição tinha
começado antes disso.

**Procedimento adotado daqui em diante para todo apply de campanha**:
sempre via plano salvo em arquivo (`terraform plan -out=<arquivo>`,
resumo revisado por um humano, só então `terraform apply <arquivo>`
sem recalcular) -- nunca mais `terraform apply` recalculando na hora.
Registrado também em `PILOT_RUNBOOK.md`.

**Pausa e teardown final (2026-10-28), por decisão de Luciano, com ele
presente -- mesmo padrão de plano salvo:**
`terraform plan -destroy -out=tfdestroy` (mesmas variáveis do apply),
resumo conferido ANTES de aplicar (**0 a adicionar, 0 a mudar, 65 a
destruir** -- bate exato com a topologia em pé: 8 `aws_instance`, 8
`aws_eip`, 8 `aws_security_group`, 11 `aws_vpc_security_group_ingress_
rule` no controle/servidores, 8 `aws_key_pair` incluindo a do operador,
1 `tls_private_key`), IP do operador/ID de conta/ARN mascarados na saída
salva. `terraform apply "tfdestroy"` (o mesmo plano, sem recalcular) --
**"Apply complete! Resources: 0 added, 0 changed, 65 destroyed."**
(início 2026-10-28T02:44:40Z, fim 2026-10-28T02:45:26Z). `tfdestroy`
apagado logo depois; lacuna real encontrada no `.gitignore` (mesmo
padrão do incidente original -- `tfplan`/`tfplan.*` nunca cobriam o
nome literal `tfdestroy`) corrigida antes do commit, embora o arquivo
já não tivesse sido staged/commitado em nenhum momento (confirmado por
`git status`/`git log`). `scan_secrets.sh` rodado de novo: PASS.

Verificação final, região por região, via `aws ec2
describe-instances`/`describe-addresses`/`describe-security-groups`/
`describe-key-pairs`/`describe-volumes` (leitura direta, sem ID de
conta/ARN em nenhuma chamada) -- **as 7 regiões (`sa-east-1`,
`us-east-1`, `ap-northeast-1`, `ca-central-1`, `eu-north-1`,
`ap-southeast-1`, `ap-northeast-2`) confirmadas com ZERO instâncias, EIPs,
security groups, key pairs (incluindo a do operador, nome
`mockopin-pqc-campaign-operator`, verificada à parte por usar um nome
diferente das demais) e volumes.** Nenhum dado local nem o repositório
foram apagados.

**Relógio e custo desta pausa:** o relógio de 6h havia recomeçado no
apply de restauração (~2026-10-28T01:24-01:26Z, aproximado por
timestamp de arquivo, mesma ressalva de honestidade já usada acima --
não um evento separadamente registrado) e foi encerrado pela pausa em
2026-10-28T02:45:26Z -- **~1h19-21min usados dos 6h permitidos, bem
abaixo do limite.** Custo real estimado usando a referência do próprio
Luciano (~US$1,15/h para a topologia completa de 12 instâncias) sobre o
período em que havia instâncias reais em pé (2026-10-28T01:09:43Z a
02:44:40Z, ~1h35min, com uma janela intermediária de ~13min em
capacidade reduzida por causa do incidente) -- **estimativa ~US$1,80,
bem abaixo do teto de US$8 do piloto 3.** Luciano confirma o valor
exato no console de Billing.

**Ponto de retomada (registrado também em `PILOT_RUNBOOK.md`):** apply
e restauração validados, entrega (etapa 5) validada, pré-flight SSH e
TCP/443 validados (8/8 clientes, 0 falhas). Falta: confirmar o
handshake TLS do ponto de vista do cliente remoto real nos 3 perfis
(tentativa única, perfil hybrid, deu 404 -- diagnosticado como
limitação do script de teste, não da pilha real, mas NÃO corrigido nem
reconfirmado ainda), o portão de validação (24 execuções) e a janela de
medição 1. Infraestrutura totalmente derrubada ao final desta rodada;
retomar exige um novo apply completo (plano salvo), com Luciano
presente.

## 94. Checagem de cobertura contra o artigo do Schardong (CANS 2022) -- um gap real encontrado e corrigido (fração do handshake sobre T_fluxo), um gap real encontrado e NUNCA antes implementado (jitter), estatística do plano de análise (Decision 92) implementada no `consolidate_v8.py`. Sem AWS, sem alterar código de medição.

**Pedido:** confirmar em `METRICS_COVERAGE.md` que v8 cobre o que
Schardong et al. mediram -- bytes na rede, T_fluxo em latência baixa e
alta, e a fração do tempo de handshake TLS sobre o tempo total, por
perfil e cenário; acrescentar ao plano de análise (Decision 92) resumo
de distribuição/Shapiro-Wilk/Mann-Whitney; confirmar que jitter e perda
continuam calculados do pcap.

**Bytes na rede:** já cobertos (OPINsize e os 4 termos, Decision
77/78/85/88) -- nada a fazer.

**T_fluxo em latência baixa e alta, por perfil/cenário:** já coberto
estruturalmente -- `consolidate_profile_scenario()` roda por célula
perfil x servidor x cenário, e cada cenário (`L0`.."L325") É uma RTT
real diferente, medida (não assumida) em `thesis/results/v8/latency-
discovery/`. Nenhuma mudança de código necessária, só esta confirmação
explícita.

**Fração do handshake TLS sobre T_fluxo: NÃO estava calculada --
corrigida.** `handshakeDurationMs` já era logado pelo gateway (mesma
linha `"mTLS handshake complete"` de `mtlsHandshakeBytes`,
`mock_mtls/main.go:675`) e já era puxado (`server/run{NN}_gateway.log`,
mesmo arquivo de sempre) -- só nunca tinha sido agregado, mesmo padrão
exato do próprio `term_handshake` (Decision -- corrigido em 2026-10-22).
`consolidate_v8.py` ganhou `handshake_duration_stats()` (mediana por
run, pareada 1:1 com o T_fluxo daquele MESMO run) e dois campos novos
por célula: `mtls_handshake_duration_ms` e
`mtls_handshake_fraction_of_t_fluxo_pct`. Testado contra fixture real
(pcap+gateway log casados, `test_handshake_gateway_vs_pcap.py`'s própria
fixture): mediana real do handshake 19,5/18,0/20,0 ms
(classic/pqc/hybrid); fração real medida contra dados do piloto 1
(`L0`, co-localizado): ~0,61% do T_fluxo -- número pequeno esperado
num cenário de baixa latência onde T_fluxo é dominado por chamadas
HTTP/assinatura, não pela rede; a fração deve crescer nos cenários de
alta latência (`L325` etc.), ainda não medido contra dado real de alta
latência fora do piloto 1/2 (que só têm `L0`/`L325`, mas sem este campo
no histórico -- será populado a partir do piloto 3 em diante).

**Jitter: NUNCA esteve implementado -- achado real, não assumido
corrigido.** Busca em `pcap_utils.py`/`consolidate_v8.py` não encontrou
nenhuma função de jitter em lugar nenhum -- a única ocorrência da
palavra era um comentário sobre variação RUN-A-RUN, não jitter de rede.
Implementado agora, do MESMO pcap já capturado para os termos de
bytes/perda do handshake, sem nova coleta: `find_all_syn_synack_rtts()`
(generaliza `find_syn_synack_rtt()` para retornar o RTT de TODAS as
conexões reais do pcap, não só a primeira -- o primeiro elemento
confirmado idêntico à função original, testado) e
`rtt_jitter_seconds()` (diferença média absoluta entre RTTs
consecutivos -- mesma definição que a RFC 3550 S6.4.1 usa para jitter
de RTP, adaptada a handshakes TCP já que este projeto não captura
tráfego RTP). Novo campo `rtt_and_loss.rtt_jitter_ms` por célula.
Testado contra os pcaps reais do piloto 1 (`L0`): 6 conexões reais
casadas, jitter mediano real ~0,12ms; e contra a fixture `s256`
casada (14 conexões reais por execução, jitter sub-milissegundo em
todos os 3 perfis).

**Estatística do plano de análise (Decision 92 addendum, ver acima):**
`stats_block()` ganhou quartis/p95/histograma/Shapiro-Wilk (toda
métrica, não só T_fluxo); nova função `add_cross_profile_t_fluxo_
comparisons()` roda Mann-Whitney par a par entre os perfis presentes em
cada célula servidor/cenário, usando as amostras reais (`t_fluxo_raw_
seconds`, campo novo por célula) -- resultado em `consolidated.json`
no campo de topo `cross_profile_t_fluxo_comparisons`. Único novo campo
que também precisou mudar o nível de agregação: Mann-Whitney compara
amostras de perfis DIFERENTES na mesma célula, então não cabia dentro
de `consolidate_profile_scenario()` (que só vê um perfil por vez) --
roda uma vez, depois que `build_consolidated()` já montou os 3 perfis.

**Testado, não só revisado:** `handshake_duration_stats()`/jitter
contra as fixtures reais já existentes (pcap+gateway log casados) e
contra os pcaps reais do piloto 1; `percentile()`/`histogram_buckets()`/
`shapiro_wilk()`/`mann_whitney_u()`/`add_cross_profile_t_fluxo_
comparisons()` com testes unitários novos
(`tests/test_schardong_coverage.py`, 15 casos, todos passando); suíte
completa de `thesis/results/v8/campaign/scripts/tests/` re-executada
(49/49 passando, incluindo os 34 testes pré-existentes, nenhuma
regressão); `consolidate_v8.py` reexecutado ponta a ponta contra o dado
real do piloto 1 completo (não um fixture sintético) -- confirma os
números acima e que nada quebrou no pipeline existente. Um caso real de
borda encontrado e corrigido durante esse teste: `term_pki` tem
variância zero entre runs (mesmo nº de bytes sempre) -- `scipy.stats.
shapiro` degrada para `statistic=1.0`/`p=1.0` com um aviso "range zero"
nesse caso; `shapiro_wilk()` agora detecta variância zero antes de
chamar o scipy e reporta `"status": "degenerate (zero variance...)"`
em vez de um "normal" tecnicamente verdadeiro mas sem sentido.

**Nada do código de medição foi alterado** (`opin_flow.py`,
`campaign_run.py`'s captura, `mock_mtls/main.go`) -- só
`consolidate_v8.py`/`pcap_utils.py` (pós-processamento, roda localmente
sobre dados já coletados) e `METRICS_COVERAGE.md`/`DECISIONS.md`. Sem
AWS tocado.

## 95. Correção da fração do handshake sobre T_fluxo (Decision 94): deve ser a SOMA dos N_mTLS handshakes do fluxo, não a mediana de uma única conexão -- achado pelo próprio Luciano, corrigido no mesmo dia, antes de qualquer uso real; valores recalculados. Jitter: definição registrada em uma linha. scipy fixado em 1.16.0 no README. Sem alterar código de medição.

**Causa raiz do erro:** `handshake_duration_stats()` (Decision 94)
calculava a MEDIANA das durações das 6 conexões client-facing de um run
e usava esse valor único no numerador da fração -- Schardong et al.
definem a fração como o tempo total gasto em TODOS os handshakes do
fluxo (soma), dividido pelo T_fluxo, não o tempo de uma única conexão.
Isso subestimava a fração em ~6x (N_mTLS=6).

**Corrigido:** nova função `handshake_duration_sum_ms()` (mesma fonte,
mesmo filtro client-facing, soma em vez de mediana). A fração
(`mtls_handshake_fraction_of_t_fluxo_pct`) agora usa a soma; a mediana
por conexão (`mtls_handshake_duration_ms`) continua existindo, mas
só como figura informativa separada, nunca mais usada na fração --
novo campo `mtls_handshake_duration_sum_ms` registra a soma
explicitamente. Testado contra a fixture real já usada pela Decision
94 (`test_handshake_gateway_vs_pcap.py`'s própria fixture, pcap+log
casados): soma real por run 117/102/119 ms (classic/pqc/hybrid, 6
conexões reais cada) -- novo teste de regressão
(`test_handshake_duration_sum_ms_real_fixture`,
`tests/test_schardong_coverage.py`), confirma soma > mediana (a
distinção que esta correção depende de existir de fato nos dados reais,
não só em teoria).

**Valores recalculados contra o piloto 1 (dado real, não fixture
sintética):**

| Perfil | L0 (co-localizado) | L325 |
|---|---|---|
| Classic | 3,76% | 10,26% |
| PQC | 0,37% | 8,59% |
| Hybrid | 1,43% | 8,44% |

A versão anterior (mediana de 1 conexão) reportava algo da ordem de
0,6% para `L0` em todos os perfis -- pequeno demais para mostrar
qualquer diferença real entre cenários. Com a soma, a fração cresce
claramente de `L0` para `L325` em todos os 3 perfis, como esperado (o
RTT de rede de cada uma das 6 conexões cresce com o cenário; o tempo de
HTTP/assinatura do lado do cliente não escala do mesmo jeito) -- o
padrão que a versão com mediana era pequena demais para evidenciar.

**Jitter, definição em uma linha (pedido explícito):** jitter = média
das diferenças absolutas entre RTTs consecutivos (SYN->SYN-ACK) das
conexões reais de um mesmo run, mesma definição que a RFC 3550 §6.4.1
usa para jitter de RTP, adaptada aqui a handshakes TCP (não há tráfego
RTP neste projeto). Perda continua vindo do pcap real
(`detect_loss_signals()`/`pcap_loss_summary()`), não alterado.

**scipy fixado:** `thesis/results/v8/campaign/README.md` agora pede
`pip install scipy==1.16.0` (a versão real contra a qual este pipeline
foi testado), não mais uma instalação sem versão.

**Testado, não só revisado:** suíte completa de
`thesis/results/v8/campaign/scripts/tests/` re-executada (50/50
passando, incluindo o novo teste de regressão da soma);
`consolidate_v8.py` reexecutado ponta a ponta contra o piloto 1
completo, novos números conferidos acima diretamente do
`consolidated.json` gerado, não estimados.

**Nada do código de medição foi alterado** -- só
`consolidate_v8.py`/`pcap_utils.py` (que não captura nada, só
reprocessa dados já coletados), `METRICS_COVERAGE.md`,
`DECISIONS.md` e o README. Sem AWS tocado. Sem apply/destroy nesta
etapa -- a retomada do piloto 3 (parte 2 do pedido) segue em paradas
separadas, abaixo.

## 96. Retomada do piloto 3: apply de plano salvo (65/0/0, início 2026-10-28T21:30:57Z), entrega de imagens/código, pré-flight TCP/handshake nos 3 perfis corrigido (achava 404 por falta de Host header, não por certificado), estágio de validação (24/24 execuções reais, ordem Classic<Hybrid<PQC em T_fluxo em todos os 8 cenários) -- dois bugs reais de orquestração encontrados e corrigidos, registrados aqui, não escondidos

**Apply:** `terraform apply tfplan` (plano salvo, sem recalcular) -- **65
added, 0 changed, 0 destroyed**, início 2026-10-28T21:30:57Z, fim
21:31:39Z. `tfplan` apagado, scanner confirmou nunca commitado. 12/12
instâncias confirmadas nas 7 regiões via `aws ec2 describe-instances`
(minha primeira tentativa usou a tag `Project=mockopin-pqc`, errada --
a real é `mockopin-pqc-aws` -- corrigida antes de reportar, não depois).

**Bug real #1 (achado, não assumido): `terraform apply` direto pula o
que `campaign_up.sh` faria depois do seu próprio apply.** `deliver_
images.sh` falhou na primeira tentativa (`FileNotFoundError:
/home/ec2-user/inventory.json`) porque a chave de campanha
(`~/.ssh/campaign_key`) e o `inventory.json` nunca foram copiados para
o control novo -- `campaign_up.sh` faz essa cópia como parte do seu
próprio fluxo pós-apply; aplicar o plano salvo diretamente (Decision 93)
pula essa parte. Corrigido copiando os dois arquivos manualmente
(`terraform output -raw campaign_private_key` + `terraform output -json
inventory`, via scp com a chave do operador). `campaign_schedule.json`
tinha a mesma lacuna (nunca escrito) -- gerado com a mesma convenção
padrão de `campaign_up.sh` (janela 1 às 19:00 UTC do dia seguinte) e
copiado também. Nenhum desses arquivos é segredo (chave de campanha
gerada pelo Terraform, não a do operador) nem afeta o que é medido --
só infraestrutura de entrega. Reentregue com sucesso depois: imagens
(RC=0, ~18min, 6/6, IDs idênticos nos 3 servidores) e código-fonte
(RC=0, cryptography-50.0.2 confirmada em todos os hosts).

**Pré-flight TCP/443 (8 clientes, 20 amostras, 3 perfis):** 0/20 falhas
na primeira tentativa, EM TODOS os 8 clientes -- achado real: a
checagem de TCP rodou ANTES de qualquer gateway subir (`deliver_
images.sh` só carrega as imagens Docker, nunca inicia o
`docker-compose`; é `switch_crypto_profile.py` que chama
`_start_if_exited()`). Refeita depois do primeiro switch de perfil
(gateways já de pé): **20/20 amostras, 0 falhas, nos 8 clientes**,
medianas batendo com o esperado (L0 0,14-0,18ms; L123 122,9ms; L14
15,4ms; L219 219,9ms; L30 32,3ms; L325 330,3ms).

**Handshake TLS, corrigido o 404 do piloto anterior:** diagnosticado
(não suposto) lendo `opin_flow.py`'s `do_call()` -- o 404 anterior era
por FALTA do header `Host: auth.local` no script de teste ad hoc, NÃO
por falta de certificado de cliente (confirmado lendo `get_local_leg_
cert_paths()`'s própria docstring: o proxy local nunca pede certificado
nessa perna, a identidade mTLS real é toda estabelecida do lado do
proxy). Corrigido no script de teste (v3): **24/24 verificações reais
(8 clientes x 3 perfis) -- todas `ok: true, status: 200`**, com corpo
JWKS real e correto por perfil (RSA/AKP/HYBRID).

**Bug real #2 (achado na primeira execução real de `run_validation_
stage()`, nunca tinha rodado contra AWS real antes): `FileNotFoundError`
no primeiro write de `calls.jsonl`.** `run_validation_stage()` criava
só o diretório pai de cada cenário, nunca as subpastas `runs/`/`server/`/
`client/` que `run_one_execution()` escreve -- `run_window()` (o
caminho real da campanha) já faz esse mkdir (linha ~2468); a função de
validação, escrita e testada só localmente/dry-run antes de hoje, nunca
tinha essa linha. Corrigido espelhando exatamente o mkdir de
`run_window()`. Testado: suíte completa (50/50) sem regressão; depois,
real: 24/24 execuções completas sem erro.

**Estágio de validação, 24/24 execuções reais, call_count=44 em todas,
nenhuma com retry:**

| Cenário | Classic (s) | Hybrid (s) | PQC (s) | Ordem esperada? |
|---|---|---|---|---|
| L0@sa-east-1 | 5,96 | 10,01 | 11,33 | sim |
| L123@sa-east-1 | 12,51 | 16,08 | 17,12 | sim |
| L219@sa-east-1 | 18,18 | 22,27 | 23,17 | sim |
| L325@sa-east-1 | 24,28 | 28,83 | 29,44 | sim |
| L0@us-east-1 | 6,07 | 9,93 | 10,71 | sim |
| L14@us-east-1 | 6,66 | 10,09 | 11,59 | sim |
| L0@ap-northeast-1 | 5,73 | 9,65 | 10,97 | sim |
| L30@ap-northeast-1 | 7,05 | 11,30 | 12,60 | sim |

**Ordem Classic < Hybrid < PQC confirmada em 8/8 cenários** -- ao
contrário da inversão Hybrid-mais-rápido-que-PQC observada no piloto 2
(Decision 89, amostra única também). N=1 por célula aqui (amostra de
fumaça, não os 10 runs/perfil/cenário reais) -- não conclusivo
estatisticamente, mas um sinal direto, não interpretado além disso.

**Parado aqui, como instruído: processo real (`campaign_run.py`, PID
17600 no control) confirmado sentado em `wait_for_operator_gate(
"validation_stage")`, aguardando o marcador do operador -- 24/24
`run01.json` reais confirmados em disco, nenhum erro, a janela de
medição NÃO foi iniciada.** Nenhum marcador foi criado por mim.

**Relógio e custo:** apply em 21:30:57Z; validação completa por volta
de 2026-10-29T00:1x:xxZ (log parou de crescer logo após o 24º ping,
processo confirmado ocioso em `ps aux`, não travado) -- aproximadamente
2h40min dos 6h usados, bem abaixo de 80%. Custo estimado seguindo a
mesma referência já usada (~US$1,15/h para a topologia de 12
instâncias): ~US$3,05, dentro do teto de US$8.

**Atualizado:** `campaign_run.py` (dois bugs reais corrigidos, ver
acima), `thesis/results/v8/campaign/scripts/tests/` sem regressão
(50/50). Nenhum código de MEDIÇÃO alterado (`opin_flow.py`, `mock_
mtls/main.go`, `tls_kem_proxy/main.go`) -- só o orquestrador
(infraestrutura de execução) e o script de diagnóstico local.

## 97. Decomposição real de T_fluxo (L0/L325, dado do portão de validação, sem coleta nova) -- verificação custa o MESMO (~490ms) nos 3 perfis, muito acima do benchmark nativo (<1ms): artefato de implementação do despachante de assinatura/verificação, não do algoritmo; a inversão Hybrid<PQC é um resíduo extra específico de PQC, reproduzido em 2/2 cenários

**Dados usados:** os 6 `run01.json` reais do portão de validação
(classic/pqc/hybrid x L0/L325, sa-east-1) -- `phase_accounting`,
`verification_timings` (7/execução), `signing_timings` (8/execução), já
coletados; `server/w00_run01_gateway.log` para bytes/duração de
handshake (`consolidate_v8.py`'s `term_handshake()`/`handshake_
duration_sum_ms()`, reusados, não reimplementados). Nenhuma coleta nova,
nenhum código alterado.

### 1. Decomposição da diferença de T_fluxo

`checksum` = soma dos termos decompostos (handshake+assinatura+
verificação+setup+rede+resíduo); pequena diferença para `total` é o
`explicit_wait_seconds` (sempre ~0) e arredondamento.

| L0 | Total | Handshake (bytes) | Handshake (tempo) | Assinatura | Verificação | Setup | Rede (http_calls) | Resíduo |
|---|---|---|---|---|---|---|---|---|
| PQC−Classic | +5,369s | +104.568 B | −0,068s | **+3,923s** | −0,032s | −0,515s | −0,000s | **+1,993s** |
| Hybrid−Classic | +4,054s | +83.028 B | +0,000s | **+3,929s** | +0,035s | −0,012s | +0,080s | +0,022s |
| Hybrid−PQC | **−1,315s** | −21.540 B | +0,068s | +0,006s | +0,067s | +0,503s | +0,080s | **−1,971s** |

| L325 | Total | Handshake (bytes) | Handshake (tempo) | Assinatura | Verificação | Setup | Rede (http_calls) | Resíduo |
|---|---|---|---|---|---|---|---|---|
| PQC−Classic | +5,159s | +104.568 B | −0,079s | **+3,690s** | +0,061s | −0,429s | +0,121s | **+1,716s** |
| Hybrid−Classic | +4,555s | +83.028 B | −0,011s | **+3,753s** | +0,168s | +0,000s | +0,957s | −0,324s |
| Hybrid−PQC | **−0,604s** | −21.540 B | +0,068s | +0,063s | +0,106s | +0,429s | +0,836s | **−2,039s** |

**Leitura:** PQC−Classic e Hybrid−Classic são dominados quase
inteiramente por ASSINATURA (73-97% do delta), não por handshake, rede
ou verificação (todos ~0 nos dois casos). O handshake em BYTES cresce
exatamente como esperado (Classic<Hybrid<PQC, igual ao OPINsize), mas o
handshake em TEMPO não acompanha -- nos dois cenários o tempo de
handshake é estatisticamente igual entre perfis (diferenças de
±10-80ms, sem padrão), porque o TEMPO do handshake é dominado pelo RTT
de rede (6 round-trips fixos por conexão), não pelo tamanho do payload
dentro do MTU -- a diferença de bytes não se traduz em diferença de
tempo de handshake nesta escala.

### 2. Como cada verificação é implementada

**TODAS as verificações, nos 3 perfis** (`opin_flow.py`'s `verify_jwt()`/
`decrypt_and_verify_jwt()`), passam pelo MESMO despachante:
`_run_verifier()` -> `thesis/scripts/pqc-signer/signer_core.mjs`'s
`verify_jwt` dispatch, em **JavaScript/Node.js**, via `server.mjs` (um
serviço HTTP de vida longa, iniciado uma vez por bloco perfil/instalação
-- `start_pqc_signer_service()`) OU, se esse serviço não estiver de pé,
um `docker run --rm -i` NOVO por chamada (fallback em `_run_verifier()`,
linha 630). Isso é deliberado mesmo para Classic (que poderia verificar
PS256 com `pyjwt` localmente) -- "para que uma diferença de tempo medida
reflita o algoritmo, não 'Python em processo' vs 'processo separado'"
(docstring de `start_pqc_signer_service()`).

**Assinatura é diferente por perfil:** Classic assina PS256 via
`pyjwt.encode()` **em processo, Python puro**, sem tocar o despachante.
PQC/Hybrid assinam a parte ML-DSA-65 via `_run_pqc_signer()`, o MESMO
despachante Node.js/HTTP-ou-docker-por-chamada da verificação.

**Medido (média, 7-8 chamadas/execução, L0):**

| Operação | Classic | PQC | Hybrid | Benchmark nativo (Go, assinatura) |
|---|---|---|---|---|
| Assinatura (ms/op) | 2,3ms (pyjwt, em processo) | 492,7ms (despachante) | 493,4ms (despachante) | RSA-4096: 6,624ms / ML-DSA-65: 0,713ms |
| Verificação (ms/op) | 492,5ms (despachante) | 487,9ms (despachante) | 497,4ms (despachante) | (sem benchmark nativo de verificação registrado) |

**A verificação custa o MESMO (~488-497ms) nos 3 perfis, independente
do algoritmo** -- Classic verifica RSA e paga o mesmo preço que PQC
verificando ML-DSA-65. Isso por si só já é evidência direta de que o
custo medido não é da operação criptográfica (que o benchmark nativo
mostra ser sub-milissegundo para os dois algoritmos): é do MECANISMO de
despacho. Mesma conclusão para assinatura PQC/Hybrid: ~493ms, ~690x o
benchmark nativo ML-DSA-65 (0,713ms) -- e ~215x mais lento que a própria
assinatura Classic em processo (2,3ms), que por sua vez já é compatível
com a ordem de grandeza do benchmark nativo RSA-4096 (6,624ms,
PS256/RSA-pyjwt sendo razoavelmente mais rápido, esperado por ser uma
chave/implementação diferente mas do mesmo algoritmo).

### 3. Conclusão: **(b) artefato de implementação do despachante, não diferença real de algoritmo**

Mesma classe de problema já documentada e corrigida nesta tese para o
assinador da v7 (um `docker run --rm -i` novo por chamada custando
~0,79s/spawn, ~94% do delta PQC/Híbrido medido então) -- aqui o custo
medido (~450-550ms/chamada) está na MESMA ordem de grandeza daquele
problema antigo, não na ordem de grandeza que o "serviço persistente"
(`server.mjs`, já implementado para corrigir exatamente isso) deveria
produzir (uma chamada HTTP local + JSON pequeno + operação
sub-milissegundo deveria custar poucos ms, não ~500ms). Duas hipóteses
concretas, não aplicadas, propostas para verificação:
1. **O serviço persistente pode não estar realmente em uso nestas
   execuções reais da AWS** (regressão silenciosa para o fallback
   `docker run --rm -i` por chamada, mesmo padrão do bug antigo) --
   diagnóstico: logar explicitamente, em `_run_verifier()`/`_run_pqc_
   signer()`, qual dos dois caminhos foi usado em cada chamada
   (`_PQC_SIGNER_SERVICE_URL is not None` ou não), sem mudar o
   comportamento. Custo: ~15min de código + teste local, sem AWS.
2. **Se o serviço persistente estiver mesmo em uso**, o custo de
   ~450-550ms está dentro do próprio `server.mjs`/do round-trip HTTP
   local -- precisa de profiling direto do servidor Node (tempo de
   parse/dispatch/resposta) para achar o que, dentro dele, custa ~500ms
   a mais que a operação criptográfica em si. Custo: variável, depende
   do que o profiling achar; não estimável sem medir.
Nenhuma das duas foi aplicada -- proposta registrada, aguardando decisão
de Luciano sobre qual investigar primeiro.

### 4. Por que Hybrid ficou mais rápido que PQC (mesma decomposição)

Assinatura, verificação e handshake são **estatisticamente iguais**
entre PQC e Hybrid nos dois cenários (deltas de ±0,01-0,10s, ruído, não
um padrão) -- ou seja, usar ML-DSA-65 dentro do esquema Hybrid custa o
MESMO que usá-lo sozinho no PQC. **A inversão Hybrid<PQC é inteiramente
explicada pelo RESÍDUO**: PQC carrega um resíduo extra de +1,99s (L0) e
+1,72s (L325) sobre o Classic que o Hybrid NÃO carrega (resíduo do
Hybrid fica a ±0,3s do Classic, nos dois cenários) -- reproduzido em
2/2 cenários reais, não um evento isolado. Esse resíduo não está
atribuído a nenhuma fase nomeada (`phase_accounting`'s própria definição
de "resíduo": o que sobra depois de http/assinatura/verificação/setup/
espera) -- não root-causado ainda a uma linha de código específica;
hipótese mais provável, dado que Hybrid faz TRABALHO ADICIONAL (duas
assinaturas: ML-DSA bruta + RSA do JWT externo) e ainda assim NÃO
carrega esse resíduo, é que a causa é específica de algo no caminho
PQC-apenas (ex.: conversão/formatação de chave bruta ML-DSA-65 só para
esse modo), não do algoritmo ML-DSA-65 em si. **N=1 por célula aqui
(amostra do portão de validação, não os 10 runs/perfil/cenário reais)
-- o padrão é consistente nos 2 cenários testados, mas não é
estatisticamente conclusivo; seria resolvido com certeza pela janela de
medição real (N=10).**

## 98. Intervenção (correção de artefato de implementação, não do algoritmo medido) -- serviço persistente de assinatura/verificação nunca era iniciado no caminho real da campanha (SSHExecutor); corrigido, código entregue, as 24 execuções do portão de validação invalidadas e serão refeitas

**Confirmação em 15 minutos, por código E por evidência ao vivo (pedido
explícito, item 1):** `SSHExecutor.start_block_proxies()` só chamava
`opin_flow.start_tls_kem_proxy()`, NUNCA `opin_flow.start_pqc_signer_
service()` -- confirmado lendo o código (`campaign_run.py`, a versão de
`start_block_proxies()` da classe `LocalExecutor` chama os dois; a
versão da `SSHExecutor`, usada de verdade na campanha real, só chamava
um). Confirmado também ao vivo: `docker ps -a --filter
name=pqc_signer_service_run` num cliente real (L0@sa-east-1, usado nos
3 perfis durante as 24 execuções) não mostrou NENHUM container com esse
nome, vivo ou morto -- o serviço persistente nunca existiu em nenhuma
das 24 execuções do portão de validação, em nenhum perfil.

**Hora UTC:** confirmação e correção entre 2026-10-29T00:3xZ e
2026-10-29T00:53:31Z (este registro). **Commit:** `2cf7374` (código:
`thesis/scripts/opin_flow.py`, `thesis/results/v8/campaign/scripts/
campaign_run.py`). **Motivo:** achado real durante a análise de
decomposição (Decision 97) -- verificação custando o mesmo (~490ms) nos
3 perfis, muito acima do benchmark nativo, apontou para um artefato do
despachante, não do algoritmo; confirmado como descrito acima.
**Execuções afetadas:** as 24 execuções do portão de validação
(sa-east-1/us-east-1/ap-northeast-1, 3 perfis, N=1/célula) -- **todas
invalidadas** (mediram o custo do `docker run` por chamada, não o
algoritmo) e serão refeitas com o código corrigido antes de qualquer
liberação do portão. Nenhuma janela de medição real (N=10) chegou a
rodar -- nada além da amostra de validação é afetado.

**Correção aplicada (item 2):**
- `opin_flow.py`: `_run_pqc_signer()`/`_run_verifier()` não têm mais
  recuo silencioso para `docker run --rm -i` por chamada -- se
  `start_pqc_signer_service()` não foi chamado no processo, a chamada
  levanta `PqcSignerServiceNotStarted` imediatamente, com mensagem clara.
  As funções one-shot (`_run_pqc_signer_oneshot()`/`_run_verifier_
  oneshot()`) continuam existindo, só não são mais alcançadas por
  acidente. Cada entrada de `signing_timings`/`verification_timings`
  passa a gravar `dispatch` ("in_process_pyjwt" para PS256,
  "persistent_service" para ML-DSA-65 puro, "persistent_service+in_
  process_pyjwt" para hybrid).
- `campaign_run.py`: `SSHExecutor.start_block_proxies()` agora também
  inicia `start_pqc_signer_service()` em cada cliente, no MESMO comando
  remoto que já inicia o proxy TLS, ANTES de qualquer execução (inclusive
  o aquecimento, que já reusa `start_block_proxies()`/`stop_block_
  proxies()` -- um único ponto de correção cobre aquecimento, portão de
  validação e janelas reais). `start_pqc_signer_service()` já bloqueia
  até `/healthz` responder (`_wait_for_pqc_signer_service_ready()`,
  código pré-existente, não alterado) -- isso É a validação pedida no
  item 2 ("o aquecimento valida isso"): um serviço que não sobe a tempo
  aborta o bloco na hora, antes de qualquer fluxo real rodar.
  `stop_block_proxies()` derruba o serviço junto com o proxy.

**Isto é correção de artefato de implementação, não mudança do
algoritmo medido:** mesmas chaves, mesmos algoritmos (PS256/ML-DSA-65),
mesmo formato de wire, mesma lógica de verificação dentro de
`signer_core.mjs`. Muda só COMO o cliente invoca esse código (processo
persistente de verdade, em vez de um novo container por chamada) --
exatamente a mesma classe de correção já registrada para o assinador da
v7.

**Testado antes de entregar:** `PqcSignerServiceNotStarted` confirmada
sendo levantada localmente (`_run_pqc_signer('{}')`/`_run_verifier('{}')`
sem serviço ativo); suíte completa de
`thesis/results/v8/campaign/scripts/tests/` re-executada (50/50,
nenhuma regressão -- nenhum teste dependia da string exata do comando
remoto antigo). Entregue a 3 servidores + 8 clientes
(`deliver_source.sh`, RC=0) antes de qualquer nova execução.

