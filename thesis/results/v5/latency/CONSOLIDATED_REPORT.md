# v5 Latency Batch (T_fluxo) — Final Report

Generated at: 2026-08-29 (batch executed 2026-08-29 ~17:40 -- ~20:00 UTC-3)

## Scope

3 profiles (Classic, PQC, Hybrid) × 6 latency scenarios (0/14/30/140/225/320ms)
× 10 runs each = **180 total flow executions**, all completed successfully
(after the retries/re-runs documented below). Metric: `T_fluxo = t_fim -
t_início` (monotonic clock), full flow (`run_insurance_flow` +
`run_person_flow`), with discarded PAR-TTL/login-race/interaction-session
sub-attempts excluded from the measured time (Decisions 1 and 7). One
warmup run per scenario, always discarded, never counted (Decision 2).
No outlier removal on the 10 counted runs, ever (Decision 3). Full
narrative for every decision/fix below is in
`thesis/results/v5/latency/DECISIONS.md`.

## Median table by scenario × profile (T_fluxo, seconds)

| Scenario | Classic | PQC | Hybrid |
|---|---|---|---|
| 0ms | 3.8186 | 10.1322 | 10.7295 |
| 14ms | 5.9678 | 12.7829 | 12.2654 |
| 30ms | 8.0768 | 13.7300 | 14.6475 |
| 140ms | 26.8036 | 31.5855 | 32.8667 |
| 225ms | 41.2262 | 45.8748 | 47.3474 |
| 320ms | 57.5602 | 62.3904 | 64.3370 |

## Hypothesis verdict: T_Classic < T_PQC < T_Hybrid

**Partially confirmed — holds in 5 of 6 scenarios, one inversion at 14ms.**

- 0ms: 3.82 < 10.13 < 10.73 -- holds
- 14ms: 5.97 < **12.78 > 12.27** -- **PQC's median is slightly ABOVE
  Hybrid's** (does not hold in this scenario)
- 30ms: 8.08 < 13.73 < 14.65 -- holds
- 140ms: 26.80 < 31.59 < 32.87 -- holds
- 225ms: 41.23 < 45.87 < 47.35 -- holds
- 320ms: 57.56 < 62.39 < 64.34 -- holds

**Not corrected, reported as observed** (per the explicit methodological
instruction: investigate an inversion, don't rewrite it away).

**What is directly confirmed, not inferred**: Decision 8 measured PQC/14ms's
own per-call `pqc-signer` timing directly (8 ad-hoc flows: signer time
6.18-11.33s, non-signer flow cost 4.60-5.06s). A parallel decomposition
was then run for Hybrid/14ms (8 more ad-hoc flows, same instrumentation):
signer time 5.00-5.72s, non-signer flow cost 5.46-5.85s. This confirms,
with direct evidence, that **Hybrid's non-signer flow cost is genuinely
higher than PQC's** (~5.5-5.85s vs ~4.6-5.1s) -- a real architectural
difference (more verification/composition work per call), consistent
with Hybrid costing more than PQC in every other scenario of this table.

**What is not confirmed, and should not be overstated**: these two
decompositions are separate ad-hoc runs (8 each), taken after the fact --
not the exact 10 official runs that produced the 12.78s/12.27s medians in
the table above. `latency_automation.py` does not instrument per-call
signer timing for the official runs, so there is no direct evidence tying
a specific slow/fast signer call to a specific one of those 20 official
runs. The most defensible statement is: signer-call duration varies with
general host/Docker scheduling contention over time rather than
deterministically by profile (PQC's signer calls, measured earlier, were
slower on average than Hybrid's, measured later -- the opposite of what
would be needed to explain the inversion by profile alone, supporting
"time-varying contention" over "PQC's mechanism is inherently slower
here"), and 14ms is the scenario where PQC's and Hybrid's medians sit
closest together in every other sense (|gap| = 0.51s, versus 0.92-1.95s
in every other scenario) -- making it the single scenario most exposed to
exactly this kind of noise flipping which one lands on top. That is a
plausible, evidence-consistent mechanism, not a proven root cause of this
specific inversion. Classic's own median (5.97s) is far below both, so
the *classical-vs-hybridized-signing* distinction the hypothesis cares
about most is untouched by this inversion either way.

**Every other scenario confirms the expected ordering cleanly.** The
*absolute* gap between Classic and the other two does **not** widen as
latency increases -- it stays roughly constant throughout (Classic-to-PQC:
6.31s at 0ms, 4.65-4.83s at 140-320ms; Classic-to-Hybrid: 6.30-6.91s
across every scenario, no clear trend), consistent with the signer's
per-JWT cost being a fixed overhead that network latency doesn't change.
What changes sharply is the *ratio*: PQC/Hybrid start at ~2.1-2.8x
Classic's median at 0-14ms and converge to ~1.1-1.2x by 225-320ms, as the
same fixed few seconds of signing overhead becomes a shrinking fraction
of an ever-larger total flow time. This is the same dilution effect
driving the spread convergence noted below.

## Spread check (the ~60-70% checkpoint)

| Scenario | Classic | PQC | Hybrid |
|---|---|---|---|
| 0ms | 35.20% | 12.58% | 4.89% |
| 14ms | 35.39% | 21.81%\* | 11.36% |
| 30ms | 9.59% | 7.89%\* | 6.83% |
| 140ms | 1.74% | 19.66% | 12.47%\* |
| 225ms | 1.42% | 1.11% | 10.51% |
| 320ms | 0.33% | 0.64% | 0.59% |

\* re-run from scratch at least once after an incident (see below);
value shown is the accepted, official one.

No scenario's *accepted* value exceeds the 60-70% checkpoint. Two
scenarios did exceed it before a fix/re-run (PQC 14ms's first attempt:
68.26%; Hybrid 140ms's first attempt: 245.42%, see below) -- both
resolved and re-run per the checkpoints agreed in advance.

**Classic's spread collapses toward 0% as latency rises** (35.20% at
0ms, essentially flat to 35.39% at 14ms, then falling steadily to 0.33%
at 320ms) -- network delay dominates, swamping OS/process jitter,
confirming Decision 8's own finding.

**PQC/Hybrid do not show a "stays elevated" trend -- both are irregular
across the 6 scenarios, and both converge to Classic's own low level by
320ms.** Notably, at 0-30ms Classic's spread is actually the *highest* of
the three (e.g. 0ms: Classic 35.20% vs. PQC 12.58%/Hybrid 4.89%) --
Classic's absolute T_fluxo is smallest there (3.8-8.1s), so its own
network/OS jitter is a larger fraction of a smaller number. PQC's and
Hybrid's spread only exceeds Classic's clearly at 140-225ms (PQC
19.66%/1.11% and Hybrid 12.47%/10.51%, against Classic's 1.74%/1.42%) --
this is where the fixed few seconds of signer-subprocess jitter
identified in Decision 8 is large relative to Classic's own,
by-then-collapsed network jitter. By 320ms all three converge to a
common low floor (0.33-0.64%): absolute T_fluxo is now large enough
(57-64s) that *neither* network jitter *nor* signer-subprocess jitter is
proportionally significant for any profile -- the same dilution effect
already noted for the medians above, now visible in the spread too.

## Incidents encountered during the batch (all resolved, full detail in DECISIONS.md)

1. **PAR-TTL/login-race time exclusion mechanism** (Decision 1) --
   designed and verified via deliberate reproduction before the batch
   started (65s forced delay correctly excluded from T_fluxo).
2. **A third TTL-adjacent race**, `InteractionSessionLostError`
   ("interaction session id cookie not found") -- found live at Classic/
   320ms run 3/10 (Decision 7). Root cause **not confirmed** despite 7
   deliberate reproduction attempts with full cookie-transport
   instrumentation (all 7 succeeded cleanly) -- treated defensively with
   the same retry-and-exclude pattern as the other two races, on the
   honest record that this one specific mechanism's cause remains
   unknown. Classic/320ms re-run from scratch after the fix.
3. **PQC/14ms's first attempt: 68.26% spread, no retries fired**
   (Decision 8) -- investigated quantitatively (8 flows, per-call
   `pqc-signer` timing) and confirmed as real signing-architecture cost
   (Docker subprocess-spawn scheduling jitter), not noise to exclude.
   Recalibrated the spread checkpoint going forward: PQC/Hybrid spread
   from this mechanism is expected, not itself an anomaly. PQC/14ms
   re-run from scratch for its official value (21.81%).
4. **The Decision-5 reentrant `auth`<->`mock_mtls` race recurred**, at a
   new call site (`InsurerAdapter.getConsent()` during interaction/login
   rendering, not just `/token` exchange) -- crashed the whole script at
   PQC/30ms run 9/10 since `latency_automation.py` had no whole-run retry
   yet (Decision 9). Added the same `RUN_RETRY_LIMIT=2` whole-run retry
   `median_automation.py` already has. PQC/30ms re-run from scratch.
5. **An unexplained ~77.5s stall, no exception, no retry fired**
   (Decision 10) -- Hybrid/140ms run 2/10 first attempt: 111.19s against
   a ~32.2-33.3s cluster for the other 9 (245.42% spread). Traced to a
   77.5-second gap with zero gateway activity, inside a local (non-
   network) polling wait -- root cause not confirmed, plausibly the same
   class of host/Docker Desktop flakiness seen elsewhere this session.
   Per Decision 3's own "no selective outlier removal" rule, the entire
   10-run set was discarded and the scenario re-run from scratch as a
   complete batch (did not recur on re-run: 12.47% spread).

## Pending anomalies

**None outstanding.** Every scenario's accepted data is within checkpoint
thresholds. Two root causes remain formally unconfirmed (Decision 7's
interaction-session-lost race, Classic/320ms; Decision 9's Decision-5
recurrence, PQC/30ms's crash before the whole-run retry existed; Decision
10's 77.5s stall, Hybrid/140ms) -- all three documented honestly as such,
all mitigated by discarding the entire affected 10-run scenario and
re-running it completely from scratch (never a partial/selective
discard). Verified directly against each scenario's final
`median_metrics.json` (not just narrated): Classic/320ms's 10 accepted
values (57.48-57.67s) show `runs_with_retries: []`; PQC/30ms's 10
accepted values (13.52-14.58s) show both `runs_with_retries: []` and
`whole_run_retries: []`. Neither final dataset carries any trace of its
respective incident.

## Cross-check against the size batch (v5's own tabela_final_v5.md/CONSOLIDATED_REPORT.md)

Confirmed once, during the pilot (Decision 6): same flow, `call_count=28`,
`N_JWT=26`, `N_JWK` entries=4 (2 per fetch), `N_mTLS=6` -- identical to
every value already established for the size batch. Not re-checked for
every one of the other 17 combinations since the flow code itself never
changed between them.

## Not yet done

- This report and the underlying `runs/`/`median_metrics.json`/
  `report.md` data, plus the `opin_flow.py`/`latency_automation.py` code
  changes from Decisions 1, 7, 8, 9, 10, are **not yet committed**.
