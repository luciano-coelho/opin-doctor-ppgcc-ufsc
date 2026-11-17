# Degrau 2, Stage 2 — results of the 5 hypotheses (D1-D5)

Luciano Figueiredo Coelho | PPGCC/LabSEC/UFSC. **Draft for review — do not treat as final/published.** Follows `PLANO_DEGRAU2.md` + Amendment 1 in full, without changing criteria, tests, seeds, or aggregation rules. Every number comes from `scripts/etapa2_analise_d1_d5.py`, reading directly from `campaign_data/round{1,2}/runs_raw/*.json` and `hardware_probe/probe_overhead_result.json` — no value typed by hand. Full output (every number, including those not cited here): `ETAPA2_RESULTADOS.json`.

## Two-round rule (applied before any analysis)

Exact two-sided Mann-Whitney, Round 1 (seed `20261117`) × Round 2 (seed `20261118`), per route × metric (`t_fluxo_fino_seconds` + the 6 `phase_accounting` components = 7 metrics × 4 routes = 28 tests), Holm over the 28. **None of the 28 comparisons had an adjusted p <0,05 — the two rounds could be pooled in every analysis below**, with no real divergence to report.

**Explicit methodological choice (not literally covered by the plan's text, decided BEFORE seeing the p-values):** "cell" in this rule = route (4, not 12), pooling the 3 profiles within each route (n=45/round) — the only reading consistent with the fixed "4 cells × 7 metrics = 28 tests" number already written in the plan. This does not affect any downstream decision criterion, since all 28 comparisons came back non-significant.

## D1 — is the heterogeneity between installations an artifact of the orchestrator?

| Pair | Median A (ms) | Median B (ms) | HL diff (ms) | 95% bootstrap CI (ms) | ±15% band (ms) | Within the band? |
|---|---|---|---|---|---|---|
| sa×us | 1808,4 | 1828,3 | -14,3 | [-37,9; 12,5] | ±271,3 | Yes |
| sa×ap | 1808,4 | 1879,7 | -70,2 | [-96,3; -44,0] | ±271,3 | Yes |
| us×ap | 1828,3 | 1879,7 | -56,6 | [-83,3; -30,8] | ±274,3 | Yes |

**Verdict: SUPPORTED** (the WALL-CLOCK T_fluxo's heterogeneity is mostly a measurement artifact) — all 3 CIs fall entirely within ±15% of the pair's smaller median, exactly Amendment 1's criterion. Note that 2 of the 3 pairs are statistically significant even after Holm (sa×ap and us×ap, Holm p=0,0014) — the difference is real and detectable, but small in relative magnitude (≤70ms, within the pre-registered ~271-274ms tolerance band). The third pair (sa×us) is not significant (Holm p=0,321). These p-values are purely descriptive (the plan's general testing convention) — D1's SUPPORTED/REFUTED/PARTIAL decision uses exclusively Amendment 1's CI-vs-band criterion, never a p-value. **Process finding:** the first version of this script had the SUPPORTED/REFUTED labels inverted relative to Amendment 1's literal definition — fixed before this report was written, cited here for transparency.

## D2 — does the overhead (wall-clock − fine-grained) follow Degrau 1's Item 5b regression?

| Route | Observed overhead (ms) | Real RTT (ms) |
|---|---|---|
| L0-sa-east-1 | 456,1 | 2,25 |
| L0-us-east-1 | 2106,4 | 113,40 |
| L0-ap-northeast-1 | 4438,2 | 259,11 |
| L123 | 2290,7 | 124,50 |

Regression (4 points): slope = **15,53 ms/ms**, intercept = **384,67 ms**.

**Verdict: REFUTED.** The intercept (384,67ms) is within the `[0;1.925]`ms range, but the slope (15,53) falls **outside** `[12,2;15,3]` by a small margin (0,23). By the criterion's construction ("REFUTED if either one falls outside"), it only takes one of the two to fail. With only 4 points, this is the same statistical fragility already stated in the pre-registration — the conclusion is sensitive to a single point.

## D2b — "pure SSH" regression vs. real RTT (additional, no SUPPORTED/REFUTED criterion)

Slope = **11,77** ms of pure SSH per ms of RTT (vs. Degrau 1's `b≈13,17` — the same order of magnitude, never comparable at the absolute level). Intercept = 230,18ms (not predicted by any earlier model, as already stated in Amendment 1).

## D3 — do the Classic/PQC/Hybrid order and the L0-sa-east-1 inversion persist in the fine-grained T_fluxo?

| Route | Observed order (fine-grained) | Official order (wall-clock) | Persists? |
|---|---|---|---|
| L0-sa-east-1 | Classic < PQC < Hybrid | PQC < Classic < Hybrid | **No** |
| L0-us-east-1 | Classic < PQC < Hybrid | Classic < PQC < Hybrid | Yes |
| L0-ap-northeast-1 | Classic < PQC < Hybrid | Classic < PQC < Hybrid | Yes |
| L123 | Classic < PQC < Hybrid | Classic < PQC < Hybrid | Yes |

**Verdict: SUPPORTED** (persists in 3/4 routes). **The L0-sa-east-1 inversion does NOT persist in the fine-grained T_fluxo** — in the wall-clock value, PQC was faster than Classic on that installation (a difference attributed to Classic's 26-45ms RSA-key bias, Degrau 1); in the fine-grained value, Classic is once again (slightly) faster than PQC, but the difference (7,8ms) is small and **not significant** (Holm p=0,546), consistent with Amendment 1's specific prediction.

**Specific prediction for L0-sa-east-1 (PQC−Classic, the same convention as Amendment 1):** observed **+7,8ms**, outside the predicted `[-43;-24]`ms range, but **not significant as predicted** (Holm p=0,546 ≥0,05). The non-significance matched the prediction; the magnitude and sign did not (Amendment 1 predicted PQC cheaper than Classic by ~24-43ms; the observed value is PQC very slightly more expensive, 7,8ms, within noise).

Per-pair tests (8, Holm): all Classic×PQC pairs are non-significant (Holm p between 0,09 and 0,55); all PQC×Hybrid pairs are significant (Holm p <0,012, most <0,0001) — Hybrid is consistently more expensive than PQC across all 4 routes.

## D4a — is Δ(PQC/Hybrid vs. Classic) in the fine-grained T_fluxo dominated by signing+verification?

**Methodological note (post-audit):** the plan defines the fraction as component ÷ Δ(fine-grained T_fluxo) (a scalar). Since Δfine is small in several cells (there is cancellation between components of opposite signs), this literal fraction produces values >100% or with sign oscillation — reported below exactly as they come out, without rounding into `[0%,100%]`.

| Route | PQC−Classic: sign+verif / http_calls (Δfine, ms) | Hybrid−PQC: sign+verif / http_calls (Δfine, ms) | Confirms (both pairs)? |
|---|---|---|---|
| L0-sa-east-1 | 332,3% / -300,5% (7,8) | 8,1% / 65,3% (102,6) | No |
| L0-us-east-1 | 86,0% / 76,2% (27,4) | 6,9% / 39,2% (84,1) | No |
| L0-ap-northeast-1 | 176,0% / -23,8% (14,9) | 4,7% / 52,8% (157,8) | No |

**Verdict: REFUTED** (0/3 routes confirm both pairs — on no route does the PQC−Classic pair simultaneously reach sign+verif≥60% AND http_calls<20%, because of the second threshold; L0-us-east-1 and L0-ap-northeast-1 easily reach the signing+verification threshold, but fail `http_calls<20%`). **Honest finding, not forced into the original hypothesis:** the numerical instability itself (fractions >100%, signs flipping) is a result in itself — it appears because Δfine is small and the individual components (signing positive, http_calls sometimes negative) nearly cancel out, not because the calculation is wrong. The Hybrid−PQC pair is never dominated by signing+verification (always <9%) — it is concentrated in `http_calls_seconds` (39-65%) and the residual (see `ETAPA2_RESULTADOS.json`), consistent with Degrau 1's reading that Hybrid's extra cost is more tied to the handshake/TLS-KEM-proxy and extra round-trips than to the signing/verification itself.

## D4b — is the increment in Δfine going from L0-sa-east-1 to L123 dominated by residual+HTTP?

| Pair | Total increment (ms) | residual+http | signing+verif | Confirms? |
|---|---|---|---|---|
| Classic→PQC | 16,7 | 59,5% | 6,6% | No (by 0,5 percentage point) |
| PQC→Hybrid | -30,7 | 78,0% | 5,6% | **Yes** |

**Verdict: PARTIAL** (1/2 pairs confirm). The PQC→Hybrid pair clearly confirms the prediction. The Classic→PQC pair is only 0,5 percentage points away from the 60% threshold (59,5%) — it technically REFUTES this sub-test by the exact criterion, but the direction and order of magnitude match the prediction; the signing+verification fraction (6,6%) is well within the expected `<40%` limit.

## D5 — ratio of Δfine_residual/real RTT on L123 vs. L0-sa-east-1

Median fine-grained residual: L0-sa-east-1 = 1388,7ms; L123 = 3599,6ms. Δ = 2210,9ms. Real RTT for L123 = 124,50ms. **Ratio = 17,76**.

**Verdict: SUPPORTED** (within `[13,6;26]`) — compatible with the reading that the SSH component explains Degrau 1's `b` coefficient.

## Summary

| Hypothesis | Verdict |
|---|---|
| D1 | SUPPORTED |
| D2 | REFUTED (by a small margin on the slope) |
| D2b | descriptive (slope 11,77 vs. b≈13,17) |
| D3 | SUPPORTED (the L0-sa inversion does NOT persist in the fine-grained value) |
| D4a | REFUTED |
| D4b | PARTIAL |
| D5 | SUPPORTED |

## Pre-registered × exploratory separation

All the verdicts above follow exactly the criteria/tests/seeds of `PLANO_DEGRAU2.md` + Amendment 1, with no change after seeing the data. The following observations are **exploratory** (not part of any pre-registered criterion, they only describe the pattern found in the already-computed numbers): the negative direction of `http_calls_seconds` in D4a for 2 of the 3 L0 routes; the concentration of the Hybrid−PQC cost in `http_calls_seconds`+`residual_seconds`; the fact that 2/3 of D1's pairs are statistically significant despite SUPPORTED.

## Corrections made after independent audit (before this report was treated as final)

An independent audit (a separate agent, which never read any key file) found, and I fixed:

1. **[High]** D4a/D4b were using an undeclared denominator (the sum of the absolute magnitudes of the 6 components) instead of the plan's literal denominator (Δfine/the increment itself). Fixed — it now uses the literal denominator, with the resulting numerical instability (fractions >100%, signs flipping when Δfine is small) explicitly reported in the tables above, never hidden.
2. **[Medium]** D3's prediction for L0-sa-east-1 had a sign error (it negated PQC−Classic before comparing it against a range already defined for PQC−Classic). Fixed — no effect on the verdict because the magnitude already fell outside the range under both signs, but the reported value is now correct.
3. **[Low]** Two of D2's booleans (`slope_in_range`/`intercept_in_range`) were serializing as the string `"True"`/`"False"` in the JSON due to an unconverted `numpy.bool_` — fixed to a native `bool`; it never affected the verdict itself (computed before serialization).
4. **[Low, latent]** D4a/D4b never checked the two-round rule before pooling — no real effect in this round (no divergence exists), but a guard was added that fails loudly if this changes in a future round, instead of silently pooling.
5. Also added: Holm correction over D1's 3 descriptive p-values (the plan's general convention, never used in D1's decision) and an explicit note on the bootstrap seed used when a D1 pair is pooled (Round 1, `20261117` — the plan does not literally cover the pooled case).

None of these corrections changed the 6 final verdicts (D1 SUPPORTED, D2 REFUTED, D3 SUPPORTED, D4a REFUTED, D4b PARTIAL, D5 SUPPORTED) — they changed supporting numbers and, in D4a/D4b, the exact magnitude of the reported fractions.

## Operational finding unrelated to the hypotheses

12/12 dedicated captures failed in Round 2 (vs. 2/12 in Round 1) — the same already-accepted error category ("incomplete decryption", never "size mismatch"), but at a much higher rate, suggesting a systemic cause tied to Round 2's window. It does not affect any number used in the D1-D5 analyses above (an orthogonal field). Full detail: `DECISIONS.md`, Decision 214.
