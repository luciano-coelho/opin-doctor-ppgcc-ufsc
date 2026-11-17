> **Translation note.** This is an English translation of the pre-registration
> document originally committed in Portuguese at commit `62f57326`
> (2026-11-16T14:34:09-03:00) and subsequently amended ("Emenda 1") at commit
> `f688242e` (2026-11-16T15:00:03-03:00 = 2026-11-16T18:00:03Z). The original
> Portuguese text of both the pre-registration and Emenda 1 remains unchanged
> in the git history at those commits — this translation does not replace or
> supersede the registered original for pre-registration purposes.

# Degrau 2 — pre-registration of the supplementary fine-grained-timer latency campaign

Luciano Figueiredo Coelho | PPGCC/LabSEC/UFSC. SUPPLEMENTARY phase, authorized separately from the already-published official report (`Consolidated_Metrics_Report_FINAL.md`, **untouched in this phase**) and from the exploratory "Degrau 1" investigation (`thesis/results/v9/analise_origem/RELATORIO_ORIGEM.md`, also untouched). Data in a separate directory — remote: `~/campaign-data/v9/degrau2`; local: `thesis/results/v9/degrau2/`. **This document is committed BEFORE any analysis runs or any new data is collected** — no number below comes from Degrau 2 data (all `a`/`b`/`c` values cited come from Degrau 1, already published, never recomputed here before data collection).

**Explicitly out of scope:** the Control profile (`hibrido-v8`) is NOT included in this supplementary campaign. No AWS action in this Stage 0 (everything below is local). Stage 1 (real AWS actions) only begins with explicit authorization and confirmed user presence, **sub-stage by sub-stage** — confirmed presence today is not a blanket authorization for all future sub-stages.

## Motivation

Degrau 1 confirmed, by reading the code (`latency_automation.run_once_timed()`), that the library already internally computes a FINE-GRAINED T_fluxo (`t_fluxo_seconds`) and a per-phase decomposition (`phase_accounting`: HTTP calls, signing, verification, explicit wait, setup, internal residual) — but these fields are discarded by `orchestrator.py` before being persisted. The entire Degrau 1 investigation (H1-H4, items 1-10) worked only with the ORCHESTRATOR's T_fluxo ("wall-clock": `end_utc - start_utc`, which includes the full SSH call + Python cold-start + key warm-up). Degrau 2 persists both fields (an additive change, Stage 0, item 2) and runs a new, small campaign to actually separate the two — with RTT(control,client) actually MEASURED (not externally approximated, as in Degrau 1) via `probe_overhead.py`.

## Fixed seeds (registered BEFORE any data collection)

- **Round 1:** seed `20261117`.
- **Round 2:** seed `20261118`.
- Used for: drawing the profile order per route and per round (recorded in the manifest, the same convention as Degrau 1/the official campaign), and any statistical bootstrap performed in Stage 2 (Hodges-Lehmann, 95% CI, `numpy.random.default_rng`, 10.000 resamples — the same convention as all of Degrau 1).

## Exact tests (declared now, never chosen after seeing the data)

- Exact two-sided Mann-Whitney U (`scipy.stats.mannwhitneyu`, `method="exact"`) for comparisons between 2 groups (n=15 per group in this campaign, not n=10 as in the official campaign).
- Holm correction over each hypothesis's test family (D1: 3 tests/installation; D3/D4: per cell, families separate from D1).
- Hodges-Lehmann (median of the paired differences) with a 95% CI via bootstrap (the corresponding round's seed, 10.000 resamples).
- No new test introduced after seeing Degrau 2's real data.

## The 5 hypotheses

### D1 — is the heterogeneity between installations (Degrau 1's H4) an artifact of the orchestrator?

**Numerical prediction:** in the WALL-CLOCK T_fluxo (Degrau 1, Classic, L0), the 3 installations differed by up to ~145% from one another (sa-east-1 median 2.357,9ms vs. ap-northeast-1 median 5.786,2ms). If this heterogeneity is, wholly or mostly, an artifact of the orchestration overhead (SSH+cold-start, which Degrau 1's Item 5b already estimated as dependent on the control-client RTT), the FINE-GRAINED T_fluxo (`t_fluxo_seconds`) medians of the 3 installations should fall **within ~10-15% of one another** (the order of magnitude left over after removing ~1,8s+ of fixed overhead plus each one's `b×RTT_cc` term).

**Exact test:** exact two-sided Mann-Whitney, 3 pairs (sa-east-1×us-east-1, sa-east-1×ap-northeast-1, us-east-1×ap-northeast-1), Classic profile, L0 routes, FINE-GRAINED T_fluxo, n=15 per group per round (tested separately in each round AND on the 2 rounds' pooled data, n=30). Holm over the 3 pairs.

**Decision criterion:** **REFUTED** (H4 was mostly a measurement artifact) if all 3 pairs lose significance (Holm p ≥ 0,05) AND the medians fall within ~15% of one another. **SUPPORTED** (the real heterogeneity persists, it is not just an artifact) if at least 1 of the 3 pairs remains significant (Holm p < 0,05) with a median difference >15%. **What I will say if the data support neither extreme:** an explicit report of the real p-values and median differences, without forcing either label — "partially explained" only if the difference reduction is clear (e.g., from ~145% to <50%) but significance persists.

### D2 — does the overhead (wall-clock − fine-grained) follow Degrau 1's Item 5b regression?

**Model (already estimated in Degrau 1, never refit here before seeing new data):** `predicted_overhead_ms = a + b × RTT(control,client)_ms`, with `a ≈ 1.807,3ms` (published 95% CI `[1.553,7; 1.924,9]`) and `b ≈ 13,17` (published 95% CI `[12,20; 15,29]`), both from `RELATORIO_ORIGEM.md`, Item 5b.

**RTT(control,client) used:** REAL, measured by `probe_overhead.py` (median of 30 new TCP connections to port 22, Stage 1) for `L0-us-east-1`/`L0-ap-northeast-1` — for the first time with no external approximation. For `L0-sa-east-1` and `L123`, the real value is already known from Degrau 1 (control and server of these routes co-located in `sa-east-1`): `0,129ms` and `122,642ms` respectively — but they will be RECONFIRMED by the same `probe_overhead.py` in this campaign, never just reused without checking.

**Numerical prediction (formula declared now; the exact value finalized in a purely mechanical way once `probe_overhead.py` runs — this is not adjusting the hypothesis after seeing results, it is computing the same formula with the real measured RTT instead of the approximated one):**
- `L0-sa-east-1`: `1.807,3 + 13,17×0,129 ≈ 1.809,0ms`
- `L123`: `1.807,3 + 13,17×122,642 ≈ 3.422,3ms`
- `L0-us-east-1`/`L0-ap-northeast-1`: `1.807,3 + 13,17×RTT_cc_measured` (RTT_cc to be determined by `probe_overhead.py`).

**Decision criterion:** **SUPPORTED** if the observed median overhead (median wall-clock T_fluxo − median fine-grained T_fluxo) in each of the 4 cells falls within the model's 95% CI (using the already-published extremes of `a`/`b`'s CI: `[a_lo+b_lo×RTT; a_hi+b_hi×RTT]`) OR within ±30% of the central point — whichever is more permissive — in at least 3 of the 4 cells. **REFUTED** if 3 or more cells fall outside both criteria. **INCONCLUSIVE** in between (exactly 2 of 4 inside, 2 outside).

### D3 — do the Classic<PQC<Hybrid order and the L0-sa-east-1 inversion persist in the fine-grained T_fluxo?

**Numerical prediction:** in the official report (wall-clock T_fluxo), the order is `Classic<PQC<Hybrid` on `L123`/`L0-us-east-1`/`L0-ap-northeast-1` and `PQC<Classic<Hybrid` (inversion) on `L0-sa-east-1`. Since the orchestration overhead is mostly common across profiles (Degrau 1, the impact item — except for the small RSA-key bias, 26-45ms, already shown unable to flip any sign), the prediction is that **the SAME order will persist in the fine-grained T_fluxo across the 4 cells**, since the cause of the order (real signing/verification work, Degrau 1 item 6) happens INSIDE the fine-grained T_fluxo, not outside it.

**Exact test:** direct comparison of the per-profile fine-grained T_fluxo medians, across the 4 cells, the same order convention as the official report (Section 4.2).

**Decision criterion:** **SUPPORTED** if the order persists in ≥3 of the 4 cells. **REFUTED** if it diverges in ≥3 of the 4 cells. **INCONCLUSIVE** if exactly 2 of 4 persist.

### D4 — where does the difference BETWEEN PROFILES reside in the fine-grained T_fluxo?

**Numerical prediction:** based on the code reading already done in Degrau 1 (item 6: PQC signs via a network dispatch to the Node `pqc-signer` service; Hybrid does both; verification routed through the same service in all 3 profiles), the prediction is that **Δ(signing_seconds + verification_seconds) between PQC/Hybrid and Classic will account for ≥60% of Δ(fine-grained T_fluxo)** in each of the 4 cells, with **Δ(http_calls_seconds) <20%**.

**Exact test:** direct decomposition of `phase_accounting` (`http_calls_seconds`, `signing_seconds`, `verification_seconds`, `explicit_wait_seconds`, `setup_seconds`, `residual_seconds`), medians per profile/cell, Δ computed by subtraction (never by median of per-execution differences — the same precision convention used in Degrau 1).

**Decision criterion:** **SUPPORTED** if the prediction (≥60% signing+verification, <20% http_calls) is confirmed in ≥3 of the 4 cells (for the 2 pairs PQC-Classic and Hybrid-PQC, 8 comparisons total — "≥3 of 4" read per cell, considering that cell's 2 pairs together). **REFUTED** if the largest fraction is in another component (e.g., `residual_seconds` or `setup_seconds`) in ≥3 of the 4 cells. **What I will say if the decomposition points to the library's internal `residual_seconds`:** I will honestly report this as a NEW, unforeseen finding (the internal residual, which the code itself documents as "the TLS-KEM-proxy hop and the mTLS/KEM handshake" — a mechanism already discussed in Degrau 1, item 5b, `c`≈19,40), without forcing it to confirm D4 as formulated.

### D5 — does the fine-grained T_fluxo on L123 grow with the real RTT at the magnitude `c`≈19,40 predicts?

**Numerical prediction:** `Δfine_residual(L123 − L0-sa-east-1, Classic) / real_RTT(L123, measured by probe_overhead.py or reconfirmed from Degrau 1 ≈122,642ms) ≈ c ≈ 19,40` — the same tolerance range as Degrau 1/H3 (half to double: **9,70 to 38,80**).

**Exact test:** `fine_residual = t_fluxo_seconds − sum(latency_ms of the actual HTTP calls)` (the same decomposition as Degrau 1, but over the FINE-GRAINED T_fluxo instead of the wall-clock one), median per cell, Classic profile, ratio `Δfine_residual / real_RTT`.

**Decision criterion:** **SUPPORTED** if the ratio falls within `[9,70; 38,80]`. **REFUTED** if it falls outside this range — no "inconclusive" category (the same convention as the original H3, to keep the criterion symmetric and not inflate intermediate categories).

## Summary of predictions (single table, for quick checking in Stage 2)

| Hypothesis | Numerical prediction | SUPPORTED criterion | REFUTED criterion |
|---|---|---|---|
| D1 | Fine-grained medians of the 3 installations within ~10-15% of each other (vs. ~145% wall-clock) | All 3 pairs lose significance (Holm) AND median diff. <15% | ≥1 pair retains significance AND median diff. >15% |
| D2 | `a+b×RTT_cc` per cell (see values above) | ≥3/4 cells within the CI/±30% | ≥3/4 cells outside |
| D3 | Same Classic/PQC/Hybrid order as wall-clock, including the L0-sa-east-1 inversion | Order persists in ≥3/4 cells | Order diverges in ≥3/4 cells |
| D4 | signing+verification ≥60% of Δfine; http_calls <20% | confirmed in ≥3/4 cells | largest fraction in another component in ≥3/4 cells |
| D5 | Δfine_residual/RTT ratio between 9,70 and 38,80 | within the range | outside the range |

## Reproducibility

No warm-up data (5 per cell, discarded) will be read in the Stage 2 analyses — the same rule as Degrau 1. Stage 0 scripts (`probe_overhead.py`, the `lscpu`/CPU-info collection script) described in the Stage 0 report, never touching the existing measurement scripts beyond the already-described additive change (Stage 0, item 2). Every number in Stages 1-2 will come from a script, never typed by hand.

---

## Amendment 1 — criteria corrections, made BEFORE any real Degrau 2 data is analyzed

**Real order of events (verified truth, not assumed by default) — 3 real timestamps, UTC:**
1. **Commit of this Amendment 1:** `2026-11-16T18:00:03Z` (commit `f688242e3dc6a7a3dc0e7c4d11df1e90074de95a`, confirmed via `git log --format=%aI` after the commit — a literal value recorded in this follow-up note, not in the same commit it describes, for a structural reason: a commit's timestamp only exists after it is created).
2. **First REAL AWS action of Block 1 (`start-instances`):** **HAS NOT HAPPENED EVEN ONCE SO FAR.** The only attempt was BLOCKED by the session's safety classifier before any call reached AWS (no effect, no instance started) — there is no real timestamp for this event because it never occurred. Before that, only one READ action (`describe-instances`, confirming the 8 Instance IDs and that all were `stopped`) was executed successfully.
3. **First real output from `probe_overhead.py`:** **DOES NOT EXIST.** Confirmed now, explicitly, before writing the rest of this amendment: a search of the entire Degrau 2 directory and for any file newer than `probe_overhead.py` with that name across the whole project — the only result is the source script itself and a bytecode-cache `.pyc` (generated by the Stage 0 `py_compile` syntax check, never a real run) — **zero real probe data exists anywhere**.

**Integrity conclusion, confirmed with real verification (not by default):** since neither event 2 nor event 3 happened, **this amendment was necessarily written without looking at any real Degrau 2 number** — not because I abstained from looking, but because **those numbers simply do not exist yet**. Block 1 is stuck at sub-stage 1 (`start-instances`, blocked), it never reached sub-stages 2-5 (deadline, preflight, CPU info, `probe_overhead.py`) — **Block 1 is NOT completed, nor nearly completed.**

### D1 correction (the original version had the criterion inverted)

**New criterion, by statistical equivalence (replaces D1's original criterion above):**
- **SUPPORTED** (the heterogeneity is mostly a measurement artifact) if, across the 3 installation pairs, the Hodges-Lehmann difference's 95% bootstrap CI falls **entirely WITHIN** ±15% of the smaller median of that pair's two groups.
- **REFUTED** if **any** of the 3 CIs falls **entirely OUTSIDE** ±15%.
- **PARTIAL**, otherwise (e.g., a CI crosses the ±15% boundary without falling entirely inside nor entirely outside) — reporting the p-value, median difference, and CI of each of the 3 pairs without forcing a binary label.

### D2 correction (conceptual error: `a` already includes work that now appears inside the fine-grained value itself)

**Problem identified:** Degrau 1's `predicted_overhead = a + b×RTT` model was fit over the WALL-CLOCK T_fluxo's RESIDUAL (wall-clock − sum of the calls) — a residual which, in this campaign, now that the fine-grained T_fluxo is separately measured, **is no longer the best dependent variable**: part of what `a` captured in Degrau 1 (internal library work — signing, verification, setup, internal handshake residual) is now KNOWN and resides inside the fine-grained T_fluxo itself, not in the orchestration overhead.

**New test (replaces D2's original test):** regression of the observed MEDIAN overhead (`median wall-clock T_fluxo − median fine-grained T_fluxo`, per cell) against the REAL RTT(control,client) measured by `probe_overhead.py`, across the 4 cells (n=4 points — the same statistical fragility already declared in Degrau 1 for fits with few points, explicitly reported).

**Decision criterion:** **SUPPORTED** if the regression's slope falls within `[12,2; 15,3]` **AND** the intercept falls within `[0; 1.925]`ms (a range based on the `a`/`b` CI already published in Degrau 1, Item 5b). **REFUTED** if either one falls outside its respective range.

**D2b (new, additional):** a SEPARATE regression using only `probe_overhead.py`'s "pure SSH" time (the `ssh_handshake_ms` field, not the total wall-clock-minus-fine overhead) against the real measured RTT(control,client), across the same 4 cells. Report this regression's slope and compare it to `b≈13,17` — **explicitly stated now:** the ABSOLUTE LEVEL of the pure SSH time **is not predicted by any earlier model** (neither Degrau 1 nor D2 above) — only the SLOPE (ms of pure SSH per ms of RTT) is comparable to `b`, never this specific regression's intercept's absolute value.

### Addition to D3 — per-pair tests, in each cell

In addition to the already-planned aggregated order comparison, **D3 gains**: an exact two-sided Mann-Whitney test per PAIR (Classic×PQC, PQC×Hybrid) in EACH of the 4 cells (8 tests total), with Holm correction over these 8 tests — reporting the direction (which profile has the larger median) and significance of each pair individually, not just the already-declared aggregated order.

**New prediction, declared now (before seeing the data):** the PQC−Classic difference on `L0-sa-east-1` (fine-grained T_fluxo) should be around `-69 + [26;45]`ms (i.e., incorporating the RSA-bias range already known from Degrau 1 — Classic pays ~26-45ms that PQC does not pay, and in this cell's WALL-CLOCK T_fluxo the observed difference was -69ms) — resulting in a predicted range of approximately `[-43; -24]`ms. **The stated expectation is that this specific pair will NOT be statistically significant** (Holm p ≥ 0,05), consistent with what was already seen in Degrau 1 for this same pair in the wall-clock T_fluxo (Holm p=0,2176, not significant).

### Splitting D4 into D4a/D4b

**D4a** (restricted to the 3 L0 cells — `L0-sa-east-1`, `L0-us-east-1`, `L0-ap-northeast-1`): the same already-declared criterion (signing+verification ≥60% of Δfine; `http_calls` <20%), applied to the 2 pairs (PQC-Classic, Hybrid-PQC) in each of the 3 L0 cells. **Decision criterion:** a cell "confirms" D4a if BOTH pairs in that cell satisfy both thresholds. **SUPPORTED** if ≥2 of the 3 L0 cells confirm. **REFUTED** if 0 or 1 confirm.

**D4b** (new — tests the effect of real RTT, not the profile effect): the INCREMENT in Δfine (per profile pair) going from `L0-sa-east-1` to `L123` (same `sa-east-1` installation, different real RTT) — i.e., `Δfine(L123) − Δfine(L0-sa-east-1)`, computed separately for the PQC-Classic pair and for the Hybrid-PQC pair (2 comparisons). **Prediction:** this increment should be **≥60%** in `residual_seconds + http_calls` combined (mechanisms that could scale with real RTT: the library's internal residual — the TLS-KEM-proxy handshake — and the HTTP calls themselves) **AND <40%** in signing+verification combined (cryptographic primitives, whose cost should not depend on RTT). **Decision criterion:** **SUPPORTED** if BOTH of the 2 comparisons (PQC-Classic and Hybrid-PQC) confirm the prediction. **REFUTED** if NEITHER confirms. **PARTIAL** if only 1 of the 2 confirms.

### Reformulation of D5 (removes the symmetric `[9,70; 38,80]` range)

**New criteria (fully replace D5's original criterion):**
- **SUPPORTED** (interpretation: "the SSH component explains the `b` coefficient") if the `Δfine_residual/RTT` ratio falls within `[13,6; 26]`.
- **ALTERNATIVE** (interpretation: "compatible with `b+c`≈32,6 combined, without separating out a pure-SSH component") if it falls within `(26; 42,4]`.
- **NEW FINDING** (not forced into either category above) if it falls outside `[13,6; 42,4]` in any direction — the real numbers are always reported, whichever range they fall into.

### General two-round rule (new, applied to ALL 5 hypotheses)

**Before pooling** round 1's data (seed `20261117`) and round 2's data (seed `20261118`) for any of the D1-D5 analyses: run an exact two-sided Mann-Whitney between round 1 and round 2, **per cell AND per relevant metric** (fine-grained T_fluxo; each `phase_accounting` component: `http_calls_seconds`, `signing_seconds`, `verification_seconds`, `explicit_wait_seconds`, `setup_seconds`, `residual_seconds`). Holm correction over this test family (4 cells × 7 metrics = 28 tests).

**If the Holm-adjusted p-value is <0,05 on any of these comparisons:** **do NOT pool** the two rounds for that specific cell/metric — analyze the two rounds SEPARATELY only for that combination, and **explicitly report this as a real divergence between rounds** (never hide it, never assume it is noise without the test having confirmed there is no difference).

## Summary of predictions — UPDATED by Amendment 1

| Hypothesis | Criterion (post-Amendment 1) |
|---|---|
| D1 | SUPPORTED/REFUTED/PARTIAL by CI equivalence at ±15% (see text) |
| D2 | slope within `[12,2;15,3]` AND intercept within `[0;1.925]`ms, regression of the observed overhead vs. real RTT |
| D2b | only the pure-SSH slope is comparable to `b`; the absolute level is not predicted by any model |
| D3 | + per-pair Mann-Whitney in each cell (8 tests, Holm); prediction for `L0-sa-east-1` PQC-Classic ≈`[-43;-24]`ms, not significant |
| D4a | 3 L0 cells only; ≥2/3 confirm (both pairs) = SUPPORTED |
| D4b | increment L0-sa→L123; SUPPORTED if both pairs confirm, REFUTED if neither, PARTIAL if 1 |
| D5 | SUPPORTED `[13,6;26]` / ALTERNATIVE `(26;42,4]` / NEW FINDING outside `[13,6;42,4]` |
| Two-round rule | Mann-Whitney round1×round2 per cell/metric, Holm; do NOT pool where Holm p<0,05 |
