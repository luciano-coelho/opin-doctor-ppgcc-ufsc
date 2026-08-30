# Latency Batch (T_fluxo) — Methodology Decisions

## 1. T_fluxo excludes discarded PAR-TTL/login-race retry time -- same principle already applied to bytes

**Context.** The size batch (`thesis/results/v5/median_automation.py`) already
established the precedent for discarded retry attempts: a PAR call that
expired before login completed (TTL race) is never added to `calls`, so it
never contributes to `total_bytes_exchanged`/`bytes_by_participant` --
it's measurement-environment noise (an artifact of this local
environment's 60s PAR TTL and injected latency), not a real cost of the
flow itself. The latency batch needs the equivalent decision for *time*:
should a discarded attempt's wall-clock duration count toward T_fluxo?

**Decision**: no. `T_fluxo = t_fim - t_início`, both `time.monotonic()`
(never `time.time()`, which can jump forward or backward under NTP
adjustment -- irrelevant for a short single-process measurement, but the
correct default regardless), **minus** any time spent on a discarded
PAR-TTL or login-race attempt within that same run.

**Implementation**: `opin_flow.py`'s `wait_for_authorization_code()` and
`create_and_authorize_consent()` both gained an optional `timing` dict
parameter (`None` by default -- zero behavior change for every existing
caller that doesn't pass it, including the size batch). When given, each
function adds to `timing["wasted_seconds"]` the wall-clock duration of any
attempt it discards:
- `wait_for_authorization_code()`'s own pre-existing internal retry (the
  "no callback received" race, `max_attempts=3`): each failed attempt's
  duration (up to `attempt_timeout_seconds=20s`) is added.
- `create_and_authorize_consent()`'s PAR retry loop (the `request_uri`
  TTL race): each failed attempt's duration is added -- **with explicit
  double-counting avoidance**, since a failed PAR attempt's span already
  includes any nested login-race retries `wait_for_authorization_code()`
  recorded on its own. The PAR-level code snapshots
  `timing["wasted_seconds"]` before calling `wait_for_authorization_code()`
  and only adds the *remainder* of the failed attempt's span not already
  accounted for by nested retries.

`latency_automation.py`'s `run_once_timed()` then computes
`T_fluxo = naive_elapsed_seconds - timing["wasted_seconds"]`.

**Verified** via the same deliberate-reproduction technique used for the
original PAR retry fix: monkeypatched `simulate_login()` to sleep 65s
before its first call (forcing the first `request_uri` to expire before
login), ran a live Classic/0ms flow. Result: `naive_elapsed=68.73s`,
`wasted_seconds=65.49s` (matches the forced delay almost exactly),
`T_fluxo=3.24s` -- consistent with an undelayed control run's `T_fluxo`
(2.89s, no retry, `wasted_seconds=0.0`, same scenario). Confirms the
exclusion recovers the flow's real cost regardless of how much wall-clock
time a discarded attempt wasted.

## 2. One unconditional "warmup" run per profile, always discarded, never a post-hoc outlier judgment

**Decision**: `latency_automation.py` always runs one extra execution
immediately before the 10 counted runs of a scenario, labeled `warmup`,
written to its own `run00_warmup.json`, and reported separately in
`report.md` -- never fed into `median_metrics.json`'s statistics.

**Why pre-committed, not post-hoc**: the batch's own methodological stance
(agreed before any data was collected) rules out deciding, after looking
at the 10 values, whether run 1 "looks like" a cold start and should be
discarded -- that is exactly the kind of after-the-fact judgment call that
risks fitting the data to convenience. Taking one unconditional,
always-discarded warmup run sidesteps the question entirely: it costs one
extra run per scenario (18 extra runs total across the batch) and removes
any need to ever inspect the 10 counted values before deciding what
counts as data.

## 3. No outlier removal on the 10 counted runs, ever

**Decision**: `median_metrics.json`'s median/min/max/mean/stdev are always
computed over all 10 raw `T_fluxo` values, with no filtering step of any
kind (contrast the *size* batch's gateway-side `handshake_bytes`, which
does filter connection-level outliers before computing its own P50 --
that filter targets a different, already-documented artifact, TCP
keep-alive connections replaying a cached handshake value, not a general
license to discard latency samples that don't fit expectations). Any run
that needed a retry is marked in `runs_with_retries` and narrated in
`report.md`'s Anomalias section, but its (already retry-time-excluded)
`T_fluxo` still counts fully toward the median like every other run.

## 4. Containers are not recreated between the 10 runs of one scenario

**Decision**: unlike the size batch (which had no timing concern),
`latency_automation.py` assumes the backend stack is already running and
never touches the containers itself. Reconciliation
(`docker-compose ... up -d --force-recreate mtls auth mockapi` +
`mongo_seed`) happens once per `CRYPTO_PROFILE` switch, driven externally,
exactly as already established for the size batch's own container
reconciliation sequence (`thesis/results/v5/DECISIONS.md`, Decision 2) --
not once per run. Re-creating containers between runs would itself
introduce cold-start variance into the very measurement this batch exists
to take cleanly.

## 5. File convention: JSON is raw data, MD is always-regenerable prose

**Decision**: `run00_warmup.json`/`run{01..10}.json`/`median_metrics.json`
contain only numbers, timestamps, and structured retry records -- never a
sentence of interpretation. `report.md` is entirely derived from those
JSONs by `write_report()`/`summarize()` and can be regenerated at any time
without rerunning a single flow execution, by re-reading the same JSON
files. This mirrors the size batch's own `median_metrics.json`/
`MEDIAN_REPORT.md` split.

## 6. Cross-check against the size batch's flow -- confirms same N_mTLS/N_JWT/N_JWK

**Context.** Before trusting T_fluxo as measuring "the same flow" the size
batch already validated, the exact call sequence needed reconfirming: same
`run_insurance_flow`/`run_person_flow` functions, unmodified except for
the additive, default-`None` `timing` parameter (zero behavior change for
every other caller, including `median_automation.py` itself, which never
passes `timing`).

**Verified** (pilot, Classic/0ms): `call_count` per run = 28 (13 + 16, +
1 for the shared PAR call under the older docstring's count, matches
`total_requests` in the size batch's own `baseline_metrics.json`) in
every one of the 10 counted runs plus the warmup. `N_JWT`/`N_JWK` are
derivable client-side (from each call's own `jwt_sizes`/`jwk_sizes`
fields, populated identically to the size batch since it's the same
`do_call()`), confirmed at 26/2 respectively. `N_mTLS` (physical TCP/TLS
connections) requires the gateway's own access log
(`ba.collect_gateway_metrics()`), which this batch does not otherwise
need or call (T_fluxo is measured purely client-side) -- checked once,
during the pilot only, against a fresh gateway-log fetch: 6, matching the
size batch exactly. Not re-checked for every one of the other 17
scenario/profile combinations, since the flow code itself does not change
between them.

## 7. A third, unconfirmed-root-cause race -- "interaction session id cookie not found" -- treated defensively with the same retry pattern

**Context.** Classic, 320ms, run 3/10 of the full latency batch failed with
`RuntimeError: No consent/confirm page reached`, body a plain re-rendered
login page. `auth`'s own log for that moment showed the real underlying
error: `SessionNotFound: "interaction session id cookie not found"`.
Distinct from both retries already handled (PAR `request_uri` TTL;
"no callback received") -- oidc-provider's own interaction-session cookie
was not recognized on a subsequent request. Occurred once in ~194 flow
executions across this session's work so far (180 from the size batch,
14 from the latency batch before this failure).

**Investigation.** `ttl.Interaction` in `mock_as/utils/opin/configuration.js`
is 600 seconds -- found, in passing, to be mislabeled in its own comment
as "1 hour" (600s = 10 minutes; a pre-existing, unrelated documentation
slip, not touched further here) -- far longer than a single flow's
25-60s duration even at 320ms, so plain TTL expiry does not explain the
failure. Wrote an instrumented `simulate_login()` (scratch) logging the
actual `Set-Cookie` received on `GET /auth` and the `Cookie` header
actually sent on the subsequent `POST /login`, and ran it 7 times at
320ms deliberately trying to reproduce the race: **all 7 succeeded**, and
in every one the `_interaction` cookie (path-scoped to
`/interaction/{uid}`) was sent and received consistently, matching UIDs
throughout. The race did not reproduce, and the root cause remains
**unconfirmed** -- unlike `RequestUriExpiredError`, which was confirmed
via deliberate reproduction before this project ever wrote a fix for it.

**Decision, made explicitly without a confirmed root cause**: add
`InteractionSessionLostError`, raised from `simulate_login()` wherever the
response body contains `SessionNotFound` or `interaction session id
cookie not found` (checked at all three of its existing
"did we reach the expected page" checkpoints, since it isn't known which
one actually surfaces it). Propagates out of
`wait_for_authorization_code()` unchanged (retrying with the same
`auth_url` can't help an already-unrecognized session), caught by
`create_and_authorize_consent()`'s PAR retry loop alongside
`RequestUriExpiredError`, same wasted-time exclusion logic, distinguished
in `timing["retries"]` as `step: "interaction_session_lost"` rather than
`"par_ttl"` so the two are never conflated in `report.md`'s Anomalias
section.

**Verified** (deliberate forced-failure test, since the race itself
couldn't be reproduced naturally): first `simulate_login()` call raises
`InteractionSessionLostError` immediately; flow completes on the second
PAR attempt; `wasted_seconds=0.564` correctly excluded from `T_fluxo`.
Classic/320ms was then re-run from scratch with this fix in place.

**Honesty note for the thesis text**: this is the one retry mechanism in
the whole v5 batch (size or latency) adopted without a confirmed root
cause -- recorded here as exactly that, not dressed up as a solved
mystery. If it recurs with enough frequency to reproduce deliberately,
the investigation should resume from the cookie-transport evidence above
(which at least rules out simple Set-Cookie/Cookie mismatches).

## 8. PQC/Hybrid's higher T_fluxo spread is real signing-architecture cost, not measurement noise -- confirmed quantitatively, no exclusion applied

**Context.** PQC, 14ms, run 7/10 came back with `spread_pct=68.26%`
(individual values 11.47-19.29s), no retries recorded on any of the 10
runs -- a real wall-clock spread with no exception/retry event behind it,
unlike every other case this batch had stopped for so far. Checkpoint
triggered (user-set threshold: stop and report above ~60-70%).

**Investigation.** Instrumented `_run_pqc_signer()` (scratch, not a
permanent code change) to log each individual `docker run --rm -i
mockopin-pqc-signer` invocation's wall-clock duration, then ran 8 full
PQC/14ms flows (`run_insurance_flow` + `run_person_flow`, 8 signer calls
each -- one per client-signed JWT across both plans). Result:

| Run | T_fluxo (naive) | Σ signer time | Rest of flow |
|---|---|---|---|
| 1 | 13.27s | 8.49s | 4.78s |
| 2 (slowest) | 16.39s | 11.33s | 5.06s |
| 3 | 13.87s | 9.16s | 4.71s |
| 4 | 11.19s | 6.36s | 4.84s |
| 5 | 10.84s | 6.20s | 4.65s |
| 6 | 11.01s | 6.26s | 4.75s |
| 7 | 10.85s | 6.18s | 4.67s |
| 8 | 10.83s | 6.23s | 4.60s |

The non-signer portion of the flow ("rest of flow") is essentially
constant across all 8 runs (4.60-5.06s) -- **effectively all of the
variance in T_fluxo traces to the sum of the 8 `docker run` invocations**.
This is not one call spiking: in the three slower runs (1, 2, 3), every
one of the 8 individual signer calls came back uniformly slower (e.g. run
2: 1.08-1.95s each) than in the five faster runs (e.g. run 5: 0.66-0.95s
each) -- consistent with a general Docker Desktop scheduling/contention
effect during that whole run's wall-clock window, not a single misbehaving
container.

**Decision, per explicit user instruction**: this is real cost of the
PQC/Hybrid signing architecture (Decision 4, `thesis/results/v5/
DECISIONS.md` -- a fresh ephemeral container per ML-DSA-65 signature, no
long-lived signer process), not measurement-environment noise like the
PAR-TTL/login-race/interaction-session retries above. **No time is
excluded from T_fluxo for this** -- doing so would misrepresent PQC's and
Hybrid's real, architecture-driven cost relative to Classic (which signs
in-process via `pyjwt`, no subprocess spawn at all, and has shown
consistently low spread: 0.33-35.4% across all 6 Classic scenarios so
far, with the two higher values both explained by OS/network jitter at
low injected latency, not signer overhead Classic doesn't have).

**Going forward**: PQC and Hybrid are expected to show higher spread than
Classic on the same scenario, as a legitimate consequence of this
architecture -- this is not, by itself, treated as an anomaly requiring a
stop-and-report. A spread is only flagged going forward if it deviates
materially from the pattern characterized here (roughly 4.6-5.1s
non-signer baseline plus 8 signer calls each normally landing well under
~2s), e.g. a signer call individually approaching the 60s timeout, a
sudden change in call count, or a spread far exceeding what 8 uniformly-
slower-but-still-sub-2s calls could produce.

PQC/14ms was re-run from scratch for its official 10 values after this
investigation.

**Addendum -- Hybrid/14ms decomposed too, after the official batch found
an inversion there (T_PQC=12.78s > T_Hybrid=12.27s, see
CONSOLIDATED_REPORT.md).** Same instrumentation, 8 ad-hoc flows: signer
time 5.00-5.72s, non-signer flow cost 5.46-5.85s -- confirms directly
that Hybrid's non-signer cost is genuinely higher than PQC's (~5.5-5.85s
vs ~4.6-5.1s here), a real architectural difference consistent with
Hybrid costing more everywhere else in the table. It does **not** confirm
what caused the specific inversion in the official 10-run data: these are
separate ad-hoc runs taken after the fact, not instrumented captures of
the exact 20 official runs (10 PQC + 10 Hybrid) that produced the
12.78s/12.27s medians -- `latency_automation.py` does not log per-call
signer timing for official runs. Notably, PQC's signer calls (measured
earlier) were slower on average than Hybrid's (measured later) in these
two decompositions -- the opposite of what "PQC's mechanism is
inherently slower" would predict, supporting time-varying host
contention over a per-profile explanation, but still an inference rather
than a proof tied to the specific inversion. Reported with this
distinction intact rather than overstated -- see CONSOLIDATED_REPORT.md's
hypothesis section for the full framing.

## 9. The Decision-5 reentrant race recurs in the latency batch, at a new call site -- whole-run retry added to `latency_automation.py`

**Context.** PQC, 30ms, run 9/10 crashed the entire script (unhandled
exception, no whole-run safety net existed in `latency_automation.py`).
Error body:

```
InvalidGrant: invalid_grant
    at InsurerAdapter.getConsent (adapter.js:53:13)
```

Identical function and error shape to Decision 5 in `thesis/results/v5/
DECISIONS.md` (the reentrant `auth`<->`mock_mtls` introspection race: the
AS's own internal consent-fetch call loops back through the gateway,
which must introspect the AS's bearer token by calling `auth` again,
occasionally racing against whatever else `auth`'s single Node process is
mid-flight handling). The only difference from the original occurrence:
this time it surfaced during `simulate_login()`'s interaction/confirm
page rendering, not the final `/token` exchange -- confirming
`InsurerAdapter.getConsent()` is called from more than one place in
oidc-provider's interaction flow, all sharing the same vulnerability.
Same mechanism, new call site -- not a new mystery.

**Decision**: `latency_automation.py` gained the same whole-run retry
`median_automation.py` already has (Decision 5), as
`run_once_timed_with_retry()` / `RUN_RETRY_LIMIT = 2`. Distinct from the
PAR-TTL/login-race/interaction-session-lost retries (Decisions 1 and 7),
which exclude only a wasted sub-interval from an otherwise-successful
run: a whole-run failure here happens before there is any T_fluxo worth
keeping, so the entire attempt (both its time and its (nonexistent, since
it failed) data) is discarded and retried completely from scratch. A
second consecutive failure on the same run still stops the batch
(`SystemExit`) rather than retrying further. Every whole-run retry is
recorded in `median_metrics.json`'s `whole_run_retries` and narrated in
`report.md`'s Anomalias section, clearly distinguished from the
sub-interval retries above.

**Verified**: unit test (`run_once_timed_with_retry`, forced first-attempt
failure) confirms recovery on the second attempt and the retry logged
correctly. PQC/30ms was re-run from scratch with this fix in place.

## 10. An unexplained ~77.5s stall in one run -- no exception, no retry fired, entire scenario re-run rather than removing the one outlier

**Context.** Hybrid, 140ms, run 2/10 came back at `t_fluxo=111.19s`
against a tight cluster of ~32.2-33.3s for the other 9 runs -- 245.42%
spread, far beyond every checkpoint threshold discussed so far.
`retries=[]` and `whole_run_retries=[]`: no exception of any kind fired
during this run, ruling out every retry mechanism built so far (Decisions
1, 7, 9) -- those all react to something raising an exception; this run
completed as a full, ordinary success, just extremely slowly.

**Investigation.** `mock_mtls`'s own access log for run 2's execution
window shows a **77.5-second gap with zero gateway activity of any
kind** -- last entry `22:36:52.79` (`GET /auth/{uid}`, part of the person
plan's login step), next entry `22:38:10.06`. This falls inside
`wait_for_authorization_code()`'s local poll on `server.captured_params`
(checking a local Python variable in a `while` loop with `time.sleep(0.5)`,
generating no HTTP traffic at all, hence invisible to the gateway's own
log) -- the callback eventually arrived and the run succeeded, just ~77s
later than every other run's callback. Docker itself was confirmed
healthy immediately after (`docker version` responded normally), and
`auth`'s own log shows no errors in the same window. Root cause not
confirmed -- plausibly the same broad class of host/Docker Desktop
infrastructure flakiness already seen multiple times this session (the
full daemon hang that needed a restart, the `docker logs` timeout), this
time manifesting as a stall inside a plain local wait loop rather than an
explicit network call, which is why nothing here could have caught it as
an exception: a hang that resolves on its own before any of this batch's
timeouts trip isn't distinguishable, from the code's point of view, from
a genuinely slow-but-legitimate callback.

**Decision, per explicit user instruction**: honor Decision 3's own "no
outlier removal, ever" rule to its logical conclusion -- discarding just
run 2 while keeping the other 9 would be exactly the selective, after-
the-fact data curation that rule exists to prevent. The entire 10-run set
is discarded together and the scenario is re-run from scratch as a fresh,
complete batch of 10. If the stall recurs, it stops being a one-off and
warrants deeper investigation (e.g., OS-level network/event logs during
the exact gap window) before accepting any more data for this scenario.

Hybrid/140ms was re-run from scratch after this decision.
