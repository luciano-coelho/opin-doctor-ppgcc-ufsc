# Requirements for the official campaign (960 executions, 8 routes) — a document only, nothing implemented here

Explicit request from Luciano, after Phase B (5th real attempt + offline re-analysis of criterion 2, Decisions 101-104) closed 7/7 PASS. This document **only lists what is missing before the official campaign** — no line of code changes because of it. See `thesis/results/v9/DECISIONS.md` (Decisions 18/58/104) for the origin of each cited finding.

---

## (a) Criterion 2 coverage — route L325 and the client→server direction

**Current state (Decision 85/102):** `criterio2_probe.py` only runs once, hardcoded at `CRITERIO2_PROBE_ROUTE = "L219"` (`dedicated_criteria.py`). It measures exclusively the **server→client** direction (the server sends ≥64KB to the client that connected).

**What is missing:**
1. **Route L325 has never been exercised for criterion 2** — never wired in, a pre-existing gap since Decision 85, never noticed before for lack of evidence that would expose it. L219 (219ms) and L325 (325ms) have sufficiently different RTTs that `cwnd`/pacing behavior could diverge (the first flight's formation depends on `rtt_from_handshake_same_connection`, which scales with the actual RTT).
2. **The client→server direction has never been measured** — the client's OWN flights during the real mTLS handshakes (its `Certificate`+`CertificateVerify`+`Finished`, which for PQC/Hybrid-AND are larger than the server's in some cases) have never gone through the same `initcwnd` test. The pre-registered criterion (Decision 14/24/34) does not explicitly distinguish direction — but today's dedicated method only covers one of the two.

**Concrete risk of not fixing this before the campaign:** the official criterion 2 would continue validating only 1 of 3 routes and 1 of 2 directions — a real `initcwnd` failure in the client→server direction, or specifically on route L325, would go through with no evidence at all, exactly as happened with L0 in criterion 1 before Decision 99 fixed it.

---

## (b) Known gaps from the project's history, with priority

### Finding 10 (Decision 58) — CPU/steal sampler: **open gap, HIGH priority, blocking before the official campaign**

The real v8 monitored `cpu_mem_steal` (noisy-neighbor interference in a shared cloud — other VMs on the same physical host competing for CPU) throughout the entire timed window, via `_PeriodicSampler`/`_cpu_mem_sampler_start_cmd`/`_steal_pct_from_cpu_jsonl`, used in `compute_window_health`. **The v9 pilot (Decisions 90-102) has nothing equivalent, by explicit design** — the pilot tests feasibility, it was never the source of the thesis's official numbers.

**Concrete risk:** the official campaign (960 executions, N=30/cell, hours of real execution) **is** the source of the thesis's official numbers — without the steal sampler, a cell with high noisy-neighbor interference (common on `m7i-flex.large` instances, which are *flex*, i.e., they share capacity by design) would be indistinguishable from a real effect of the cryptographic profile. Any difference between profiles measured without this control is **unreliable** until the sampler exists — this is precisely the kind of "measurement noise vs. real effect" that v8's final report (`Consolidated_Metrics_Report_FINAL.md`, Section 8) already treats with statistical care; v9 does not yet have the input data to do the same.

### Finding 18 (Decision 58) — TCP probe restored: **CLOSED, no longer a gap**

`SSHExecutor._tcp_preflight(route)` already exists and already runs as the first line of `start_block`, once per route, fail-closed. Mentioned here only because it was cited in the same historical finding as the item above — **no action needed**.

---

## (c) What the pilot NEVER exercised on real AWS — with each gap's concrete risk

| # | Not exercised | Concrete risk (not a generic "untested") |
|---|---|---|
| 1 | **Multiple time windows (settling/drift)** | The real v8 uses 3 windows (w01/w02/w03) and already found 10/72 cells with a statistically significant downward trend even after K=5 warm-up executions (Mann-Kendall, `Consolidated_Metrics_Report_FINAL.md` Section 8). The pilot ran **a single window, no formal warm-up, N=5/cell** — if the official campaign also has settling drift (e.g., TLS session-resumption connection cache, kernel buffers adjusting, DNS cache), **this would never be detected** with the current design, and the N=30 executions of each cell could be mixing a transient "warm-up" effect with the profile's real effect. |
| 2 | **Resume after interruption** | No checkpoint/resume exists in `orchestrator.py run_pilot` — it is an in-memory `for route: for profile: for run` loop, which only writes the 3 final files (`manifest.json`/`piloto_combined.log`/`piloto_calls.json`) at the END of everything (confirmed by directly reading the code, Decision 102). **If the official 960-execution campaign drops midway (SSH connection, safety self-shutdown, instance failure) after, say, 700 real executions, those 700 are LOST — nothing is saved incrementally.** This nearly happened in this very round (Step 10, Decision 101, SSH dropped during the smoke gate) — it only caused no loss because it was the smoke gate (12 executions), not the real campaign. |
| 3 | **Routes/regions beyond the 3 piloted** | The pilot used sa-east-1 (L0/L219/L325, control+server+1 client). **The official campaign needs 8 real routes** (Decision 21: `sa-east-1` L0/L123/L219/L325, `us-east-1` L0/L14, `ap-northeast-1` L0/L30) — **`us-east-1` and `ap-northeast-1` were never touched by this round at ANY point.** Concrete risk: any region-specific problem (different EC2 quota, AMI unavailable, higher control→client SSH latency, regional IAM policy, Security Group behaving differently) would only show up during the official campaign, with no prior rehearsal in those 2 regions. |
| 4 | **Real N=30 scale** | The pilot uses N=5/profile/route (60 executions total). The official campaign uses N=30/profile/route (960 executions total) — **16x more executions**. Concrete risks never exercised at this scale: (i) the accumulated size of `piloto_calls.json` — already reached **10,9MB with only 60 real executions** (Decision 101) — at 960 executions, by linear extrapolation, that would be **~175MB**, a single JSON file that `consolidate_v9_pilot.py`/`evaluate_criteria.py` need to load entirely into memory; (ii) SSH throttling already observed once in this very round **after only 60 executions** (Decision 94, "transient server throttling right after Step 11") — at 960 executions, with no mitigation tested at real scale beyond the simple retry already applied, the risk of recurring throttling is unknown; (iii) disk space for the 12→96 dedicated captures (4 profiles × 8 routes, with up to 3 attempts each per Decision 99) was never sized nor tested. |
| 5 | **Hours-long stability** | The complete pilot (Step 0 to Step 15) took a little over 4,5h in this round, with the real measurement phase (Step 11) taking ~1h03min for 60 executions+12 captures. The official campaign, with 960 executions (16x) and 96 dedicated captures (8x), projected linearly, would take **orders of magnitude longer** (see the cost/duration section below) — **it was never tested whether the fleet, the containers, or the SSH sessions remain healthy for that long.** Concrete risks: log rotation not configured anywhere (the backend containers — `auth`/`mongo_seed`/`mockapi` — can accumulate logs without limit, Decision 96 already showed `mockapi-1` alone generating 363KB of log in ONE pilot execution); the safety self-shutdown `systemd` timers (Decision 101/102, `safety_timer.sh.tftpl`) would need to be manually extended multiple times, as happened in this very round — without automation, this is a real operational risk of the fleet going down mid-campaign over many hours with nobody monitoring. |

---

## Executive summary (for quick reference, does not replace reading the 5 lines above)

| Item | Priority | Blocking before the official campaign? |
|---|---|---|
| (a) Criterion 2: L325 + client→server direction | Medium — affects only 1 of the 7 criteria | Advisable, not necessarily blocking |
| (b) Finding 10, CPU/steal sampler | **HIGH** | **Yes, by Decision 58's own record** — without it, the differences between profiles measured by the official campaign are not statistically reliable |
| (c.1) Multiple windows/drift | Medium-High | Affects the statistical validity of the N=30, not the execution itself |
| (c.2) Resume after interruption | **HIGH** | Direct operational risk of losing many hours of work |
| (c.3) Routes `us-east-1`/`ap-northeast-1` never touched | **HIGH** | Operational risk of the campaign failing in a never-rehearsed region |
| (c.4) N=30/960-execution scale | Medium-High | Throttling/memory/disk risks known at smaller scale, never sized for the real scale |
| (c.5) Hours-long stability | Medium | Operational risk, mitigable with manual monitoring as in this round |

No scope decision is made here — that is up to Luciano.

---

## Additional official-campaign parameters, set by Luciano on 2026-11-09 (post-pilot)

These parameters are **only for the future official campaign and the reduced multi-region rehearsal** — never retroactive to the data already collected/preserved from this round (`piloto-real-aws-2026-11-09-v2`), which remains untouched. None of them was exercised in this round, so they are recorded here as requirements/parameters declared for the next cycle, not as an Amendment to the pilot's already-closed pre-registration (Decision 104):

1. **New AWS account, US$100 budget.** The official campaign and the reduced multi-region rehearsal will run in an AWS account separate from the one used for the pilot's 5 attempts — nothing is reused from the old account (SSH keys, EIPs, security groups, Terraform state); only code and the Docker images already verified by content (Decisions 61/68/101/103) carry over to the new account.
2. **Official windows, at most 30 minutes of interval between one and the next** — much tighter than the ~2,78h of `setup_overhead` observed in this round between Steps 0-10. Never exercised: this pilot ran in a single continuous window, with no planned interval between sub-blocks.
3. **Official campaign structure:** 4 profiles × 8 routes × N=30 = 960 executions, split into **3 windows of N=10** (not 1 of N=30 nor 30 of N=1), keeping **Hybrid-v8 as the control profile**.
4. **Reduced multi-region rehearsal, redefined:** 4 profiles × 8 routes × N=2 = 64 executions, on the new account, with the SAME pacing/window discipline as the official campaign (item 2), with the explicit goal of **zero manual intervention needed during the real official campaign** — i.e., this rehearsal must expose in advance any problem that would require a live fix.

**Concrete risk of none of these 4 parameters having been exercised yet:** the new account means absolutely nothing operational (EC2 quotas, IAM permissions, VPC/subnets, AMI availability in the region, Security Group behavior) has been tested there — the entire "already worked once" history of this round (Decisions 61-104) applies only to the old account. The 30-minute discipline between windows is tighter than ANY real interval ever observed in this project (the `setup_overhead` of 2,78h alone already exceeds it) — if image delivery/provenance verification between windows does not fit within 30 min, the official campaign may not be able to meet its own window discipline.

---

## Cost/duration estimate — 4 scenarios, with the arithmetic (never a bare number)

**Real rates, derived directly from this Phase B's data (Decisions 101/102), never isolated catalog estimates:**
- `avg_s_por_execucao` = 3309,2s / 60 real executions = **55,15s/execution** (pooled L0+L219+L325)
- `avg_s_por_captura` = 651s / 12 real captures (including Amendment 99's retries) = **54,23s/capture**
- `setup_overhead` (Steps 0-10: apply→smoke gate) = observed **~2,78h** in this round (fixed, does not scale with N — but DOES scale with the number of instances/images to deliver, see caveat below)
- `collect_teardown` (Steps 12-15) = observed **~0,75h**
- Cost rate: `(n_flex × $0,0958 + $0,0084 + n_eips × $0,005)` USD/h, where `n_flex` = server + clients (1 per route), `n_eips` = `n_flex` + control

| Scenario | Executions | Captures | Instances (flex/clients) | Total time | Total cost |
|---|---|---|---|---|---|
| **(a) Full official campaign** (8 routes × 4 profiles × N=30, 3 windows of N=10, new account) | 960 | 32 (4×8) | 9 flex (server+8 clients) | base 2,78+14,71+0,48+0,75=18,72h + 2 intervals between the 3 windows × up to 0,5h = **~19,72h** | 0,9206 USD/h × 19,72h = **~US$18,15** |
| **(b) The pilot's 3 routes, N=30** (4×3×30) | 360 | 12 (4×3) | 4 flex (server+3 clients) | 2,78+5,52+0,18+0,75 = **~9,2h** | 0,4166 USD/h × 9,2h = **~US$3,84** |
| **(c) Reduced multi-region rehearsal** (8 routes × 4 profiles × N=2, same window discipline, new account) | 64 | 32 (4×8) | 9 flex (server+8 clients) | base 2,78+0,98+0,48+0,75=4,99h + window interval(s) (see note 4) = **~5,0h to ~5,5h** | 0,9206 USD/h × 5,0–5,5h = **~US$4,60 to US$5,06** |
| **(d) Short window rehearsal** (3 routes × 4 profiles × N=1) | 12 | 12 (4×3) | 4 flex (server+3 clients) | 2,78+0,18+0,18+0,75 = **~3,9h** | 0,4166 USD/h × 3,9h = **~US$1,62** |

**Comparison against the new account's US$100 budget (scenarios (a) and (c)):**
- (a) official campaign: **~US$18,15 computed vs. a US$100 ceiling** — a margin of ~US$81,85 (≈5,5× the computed cost) to absorb the new account's from-scratch setup (IAM, VPC, quotas, retries) and any underestimate from the caveats below.
- (c) reduced multi-region rehearsal: **~US$4,60–5,06 computed vs. a US$100 ceiling** — a margin of ~US$95 (≈20×), meaning the US$100 ceiling is not this rehearsal's limiting factor; what limits it is the real time for manually setting up the new account, not exercised/measured here.

**Explicit caveats on the arithmetic above (never hidden):**
1. `setup_overhead` was observed with **5 instances** (1 server + 3 clients + control), **on the old account, already configured** (VPC/IAM/quotas already existing from previous rounds). Scenarios (a)/(c) use **10 instances** (8 clients) **on a brand-new AWS account** (the "New AWS account" item above) — both the larger number of hosts and the absence of any prior account configuration likely make `setup_overhead` LARGER than the 2,78h observed, by an unknown factor — **not measured, treated here as the same value for simplicity, a known and explicit underestimate** for (a) and (c).
2. `avg_s_por_execucao`/`avg_s_por_captura` are LINEAR extrapolations from a sample of 60 executions/12 captures — section (c.4) of the document above already records that SSH throttling ALREADY appeared once at this small scale (Decision 94); at 960 real executions, the time per execution may not be constant.
3. None of these 4 scenarios includes the CPU/steal sampler (finding 10, not yet implemented) nor any of the gaps in section (c) above — these are EXECUTION time/cost estimates, not of statistical validity.
4. For (a), the interval between the 3 windows (the "Official windows" item above) was added here as **2 intervals × up to 30 minutes each** (the maximum allowed, treated as a conservative ceiling — it may be shorter in practice). For (c), the split of N=2/cell into windows was not specified by Luciano (the "3 windows of N=10" structure is defined for N=30; there is no obvious equivalent split for N=2) — which is why (c)'s interval is presented as a range (0 to 1 interval of up to 30min, depending on whether the rehearsal runs as a single pass or as 2 sub-windows of N=1), not a single number.

No scope recommendation is made here — the numbers above are for Luciano to decide on.
