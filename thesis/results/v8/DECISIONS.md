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
