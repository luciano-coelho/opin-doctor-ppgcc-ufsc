# v3 — Final Measurement Tooling: Experiment 1 Revalidated, Experiment 2 Hosted Here

## Purpose

This is the current and final measurement stage. [`v2`](../v2/README.md)
established that the Conformance Suite cannot act as an mTLS client once a
post-quantum certificate is involved (a structural limitation in the
suite's own compiled code — see `v2/experiment2 - PQC/DECISIONS.md`,
Decisions 6–7), so Experiment 2 could not be driven or measured the way
Experiment 1 was. This stage's goals:

- Build a direct replacement for the Conformance Suite —
  [`thesis/scripts/opin_flow.py`](../../scripts/opin_flow.py) — that talks
  to the Authorization Server and Resource Server itself, reproducing the
  exact same OPIN consent flow the suite's own modules drove in Experiment
  1, so the two experiments stay methodologically comparable.
- **Re-run Experiment 1 (classical) through this new tool**, not just trust
  that it behaves like the Conformance Suite did. This folder's
  `experiment1 - classic/` is that revalidation: six WAN-latency scenarios,
  same modules, same metrics schema as [`v1`](../v1/README.md), collected
  by `opin_flow.py` instead of the suite.
- **Host Experiment 2 (PQC)** once it's run the same way
  (`CRYPTO_PROFILE=pqc`), so that, for the first time in this thesis, both
  experiments are produced by the identical code path and are directly
  comparable — not just theoretically equivalent.

## What's in this folder

```
v3/
├── experiment1 - classic/     Experiment 1 revalidated with opin_flow.py --
│                                same six scenarios, same schema as v1,
│                                see below for what changed and why
└── experiment2 - PQC/         Experiment 2's actual data -- not yet run
                                 (pending: CRYPTO_PROFILE=pqc, same six scenarios)
```

`experiment1 - classic/` mirrors `v1/experiment1 - Classic/`'s output shape
exactly (`{ms}ms/baseline_metrics.json` + `BASELINE_REPORT.md`,
`consolidated.json`, `EXPERIMENT1_REPORT.md` from
[`thesis/scripts/consolidate_experiment.py`](../../scripts/consolidate_experiment.py))
— same fields, same tables, so the two are diffable side by side.

## Timeline

**Building `opin_flow.py`.** Rather than design the call sequence from
first principles, it was validated against Experiment 1's own raw
Conformance Suite export logs (`v1/experiment1 - Classic/0ms/*.json`) —
reading exactly which endpoints the suite called, how many times, in what
order, and with what request bodies, for both modules the suite ran:
`opin-consent-api-status-test-v3` (12 calls: JWKS, PKI root/issuer certs,
client-credentials token, consent creation, three status polls, PAR,
manual login, authorization-code token, two more status polls) and
`person_api_core_test-module_v2.0.0` (16 calls: the same shape through
token exchange, then eight resource calls — `insurance-person` fetched
twice, then `claim`/`policy-info`/`premium` twice each). The Conformance
Suite's `opin-consents_api_preflight_test-module_v3` module (both plans) is
deliberately not reproduced — see `DECISIONS.md`, Decision 8, for why.

Three deliberate, disclosed simplifications from the suite's exact
behavior were needed to make an unattended script possible at all:
- **JARM instead of the hybrid `code id_token` response.** The AS's FAPI
  profile rejects a plain authorization-code response mode outright, and
  the hybrid flow's fragment-based redirect isn't readable without a real
  browser's JavaScript. `response_mode=jwt` (JARM, already enabled on the
  AS) keeps the callback entirely server-side without changing which
  endpoints are called or how many times.
- **An HTTPS, not HTTP, loopback redirect_uri**, with a throwaway
  self-signed certificate `opin_flow.py` generates per run — the AS
  requires every redirect_uri of an implicit-capable client to use `https`,
  checked on every authentication, not just at the authorize step.
- **A shared `requests.Session` per flow**, not a fresh connection per
  call — matching how a real client behaves, and load-bearing at the
  higher latency scenarios: without it, the round-trip cost of a
  fresh TLS handshake on every single call was enough to blow past
  oidc-provider's default 60-second PAR `request_uri` TTL before the flow
  could finish (see Known limitations below).

The manual-login step itself is unchanged from `v1`'s protocol: a real
person opens the printed link once, logs in, leaves the consent screen's
selections at their default (all pre-checked), confirms, and presses ENTER
— `opin_flow.py` never automates this step itself.

**Reorganizing results and generalizing consolidation.** As this tooling
came together, `thesis/results/` was reorganized into the versioned `v1`/
`v2`/`v3` layout this README lives in, and `opin_flow.py` gained a
`RESULTS_VERSION` env var (default `v3`) so a future reorganization
wouldn't require another code change. `consolidate_experiment1.py` (`v1`'s
own, folder-specific) was generalized into
[`consolidate_experiment.py`](../../scripts/consolidate_experiment.py),
driven by `RESULTS_VERSION`/`EXPERIMENT_NUMBER`, so both experiments reuse
one script instead of each getting a copy.

**Two real bugs found and fixed during the first full six-scenario run.**
The first attempt at all six scenarios completed without errors but
produced OPINsize figures noticeably smaller than `v1`'s, which didn't
survive a "why did this number change" check:
- The insurance flow's two post-login consent-status checks were sending
  the authorization-code token, which the RS rejected with `401`
  (silently — nothing in that loop checked the response status). Comparing
  against `v1`'s raw log showed the suite reusing the *original*
  client-credentials token for consent-status checks both before and after
  login; `opin_flow.py` now does the same.
- The person flow's `claim`/`policy-info`/`premium` calls were failing
  with `400 Bad Request, consent does not cover this person` — a scan of
  the RS's Java source (`ConsentService`/`PersonService`) showed the
  consent-screen's hidden form fields (`person-accounts` and siblings,
  pre-checked by default in `mock_as/views/interaction.ejs`) are what tell
  the RS which resources a consent actually covers; a real browser
  submitting the screen as-is includes them automatically, but the
  scripted login simulation used to validate `opin_flow.py` end-to-end
  (outside the committed tool itself) had been posting an empty
  confirmation, so the RS never linked any resource to the consent. Fixed
  in that simulation, not in `opin_flow.py`, which was never the source of
  the bug.

**A measurement bug in `compute_metrics()` itself, not `opin_flow.py`.**
Once `opin_flow.py` started reusing connections (above), mTLS handshake
percentiles — computed by `baseline_automation.py`'s `compute_metrics()`,
shared by every experiment since `v1` — turned out to be sampled once per
*HTTP request* rather than once per *physical TCP connection*. That was
invisible in `v1` (the suite rarely reused a connection, so request count
and connection count were nearly the same) but skewed the percentiles
under `opin_flow.py`'s connection reuse, weighting them toward whichever
connection happened to carry the most requests. Confirmed on a live
capture: 64 access-log entries over only 19 distinct connections, naive
per-request P50 of 9529 bytes vs. a true per-connection P50 of 11455
bytes. Fixed with `dedupe_handshake_samples_by_connection()`, applied
before the existing outlier filter — a correction that benefits any future
experiment reusing `compute_metrics()`, not just this one.

## Known limitations

- **PAR `request_uri` TTL at 225ms/320ms.** oidc-provider's default 60-second
  TTL for pushed authorization requests (not overridden anywhere in this
  environment) is tight once round-trip cost compounds across the calls
  between PAR and login completion at the two highest latency scenarios —
  both occasionally needed a retry (`invalid_request_uri: expired`) during
  data collection, more often than `v1` ever needed at 320ms. This is an
  artifact of the environment's security TTL interacting with injected
  latency, not a cryptography- or algorithm-related finding; the data kept
  in this folder is from the run that completed successfully for each
  scenario.
- **mTLS handshake byte counts carry some inherent measurement noise**
  even after the per-connection dedup above: the gateway's byte counter can
  include a few bytes of the first pipelined HTTP request if it arrives in
  the same TCP read as the handshake's tail end (documented in
  `mock_mtls/main.go` itself). With only ~20–25 connections per scenario,
  this occasionally shifts a scenario's P50 to a neighboring value (e.g.
  320ms showing 10913 bytes against every other scenario's 11455) — sampling
  variance in a known, bounded noise source, not a systematic latency
  effect.

## Relationship to other stages

`v1` remains the historical record of the Conformance-Suite-driven
classical baseline and is not superseded by the `experiment1 - classic/`
data here — the two are meant to be compared, not one replacing the other,
as a check that switching tools didn't change what's being measured. One
expected difference when doing that comparison: `v1` records
`person_api_core_test-module_v2.0.0` failing in all six scenarios on a
mock schema issue unrelated to this thesis (see `v1/README.md`); that
module passes in all six scenarios here, because `opin_flow.py` never
exercises the field the suite's own module validated and failed on — not
because the underlying mock data issue was fixed. `v2` explains why this
tool had to exist at all. Once Experiment 2's data is collected into
`experiment2 - PQC/` the same way, this folder becomes the thesis's
primary source for the classical-vs-PQC comparison every earlier stage was
built toward.
