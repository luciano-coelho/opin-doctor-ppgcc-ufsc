# sa-east-1 intra-region AZ-to-AZ RTT (Decision 30/31/32+)

Measured RTT between `sa-east-1`'s 3 Availability Zones, without Buenos
Aires (abandoned, Decision 31 -- Free Tier blocker). Built to inform the
proposed "lowest" scenario: client co-located in the same zone as the
server.

## Topology

4 nodes, all in `sa-east-1`:

| Node | AZ ID | Role |
|---|---|---|
| `sa-east-1-a` | `sae1-az1` | SSH jump host (only node reachable from the operator) |
| `sa-east-1-a2` | `sae1-az1` | same zone as `a` -- the same-AZ sanity-floor pair |
| `sa-east-1-b` | `sae1-az2` | cross-AZ |
| `sa-east-1-c` | `sae1-az3` | cross-AZ |

**AZ IDs, not AZ names.** `sae1-az1/2/3` are AWS's stable,
account-independent zone identifiers. AZ *names* (`sa-east-1a/b/c`) are
account-specific aliases -- AWS randomizes which physical zone maps to
which name per account, specifically so no customer can infer another
customer's physical zone layout from the name alone. The mapping used to
pick the Terraform subnets in this test was by AZ ID; this account's own
AZ *name* for each of these AZ IDs is not recorded here since it isn't
portable or meaningful outside this account.

**Instance type:** `t4g.micro` (all 4 nodes) -- same discovery-standard
type used throughout this project, confirmed free-tier-eligible on this
account (Decision 29).

**IP used for the ping target:** the destination's **private** IP in
every pair (Decision 28's rule for same-VPC/same-region pairs). This
measures the RTT of the intra-region path only -- it does **not**
include whatever a real client, connecting over the public internet,
would add on top (NAT, routing out and back in). That public-path RTT is
a separate, not-yet-done measurement -- see `DECISIONS.md` for the
proposal to measure it as part of the region-control procedure before
the lowest scenario is actually labeled.

## Sampling

3 rounds, ~1h apart, 20 ICMP pings per directed pair per round, both
directions (12 directed pairs/round: 4 origins x 3 destinations).
100% response rate every round (20/20 samples, no pair ever came back
empty).

Round start times (UTC):
- Round 1: 2026-10-12T14:45:36Z
- Round 2: 2026-10-12T15:46:37Z
- Round 3: 2026-10-12T16:47:39Z

## Data

`latency_sa_az_samples.json` -- raw output of
`latency-discovery/scripts/discover_sa_az.py`, **unfiltered**: every
individual ping sample is kept as measured, including one isolated 18ms
spike in round 2's `sa-east-1-a2->sa-east-1-a` pair (likely a one-off
scheduling/network blip -- that pair's median for the same round is
0.206ms, consistent with its other rounds; the spike was not removed or
treated as an outlier).

No account identifiers or operator IP are present in this file -- only
ephemeral AWS-assigned public/private IPs of instances that have since
been destroyed and verified torn down (instances, security groups, key
pairs, EBS volumes, and Elastic IPs all confirmed absent afterward via a
direct AWS API check, not just Terraform's own exit status).

## Result summary

| Pair | RTT ~ | Pattern |
|---|---|---|
| same AZ (`a<->a2`) | ~0.2ms | floor -- effectively no network hop |
| `*<->c` | ~1.1ms | cross-AZ |
| `*<->b` | ~1.4-1.8ms | cross-AZ |

Stable across all 3 rounds. Full matrix (median/min/max per pair per
round) is in `DECISIONS.md`.
