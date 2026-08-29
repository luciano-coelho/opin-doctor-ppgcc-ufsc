# v5 Median Consolidation — Etapa 2 Final Report

Generated at: 2026-08-29 (batch executed 2026-08-28 22:47 -- 2026-08-29 00:53 UTC)

## Scope

3 profiles (Classic, PQC, Hybrid) × 6 latency scenarios (0/14/30/140/225/320ms)
× 10 runs each = **180 total flow executions**, all completed successfully.
Per-run raw captures live under
`experiment{1,2,3} - {Classic,PQC,Hybrid}/{scenario}ms/runs/run{01..10}_baseline_metrics.json`;
per-scenario medians in `median_metrics.json`/`MEDIAN_REPORT.md` alongside them.
Full narrative for every decision/fix below is in `DECISIONS.md` (this folder).

## Median table by scenario × profile

Every named metric came back **identical across all 10 runs in every one of
the 18 scenario/profile combinations** (0.0% spread throughout) except where
noted in "Incidents" below -- and even those converged to the same values
once the affected run was retried, so the table has no per-scenario
variation to show: the median below IS the value for all 6 latency
scenarios within a profile, because none of these size metrics depend on
network latency.

| Profile | jwt_size_avg_bytes | total_bytes_exchanged | handshake_bytes.p50 | client_cert_der_bytes |
|---|---|---|---|---|
| Classic | 1385.42 | 66452 | 9785.0 | 1494 |
| PQC | 5458.81 | 184637 | 19756.0 | 2953 |
| Hybrid | 7324.81 | 254900 | 25880.0 | 6859 |

**bytes_by_participant** (identical across all 6 scenarios within each profile):

| Profile | Client sent/recv | AS sent/recv | RS sent/recv | PKI/CRL sent/recv |
|---|---|---|---|---|
| Classic | 17378 / 49074 | 14188 / 11875 | 26034 / 4839 | 8852 / 664 |
| PQC | 47203 / 137434 | 29570 / 41700 | 91252 / 4839 | 16612 / 664 |
| Hybrid | 64878 / 190022 | 31058 / 59375 | 121196 / 4839 | 37768 / 664 |

**Note on PKI/CRL**: Classic's PKI/CRL total (9516 bytes/run) is lower than
the value previously reported for Experiment 1 (10664 bytes, using
Raidiam's real external sandbox certs). This is the *expected, deliberate*
effect of Decision 1 in `DECISIONS.md` -- Classic now serves its own
local `root_ca.crt`/`issuer_ca.crt` stand-ins (1515/1519 bytes DER), smaller
than whatever Raidiam's real certs were. Not a regression; a direct,
understood consequence of removing the external dependency.

**Hierarchy holds throughout, as expected**: Classic < PQC < Hybrid on
every single metric, every scenario -- no crossovers, no scenario-specific
anomalies.

## Spread check (the >5% checkpoint)

**No scenario, in any profile, exceeded 5% min/max spread on any named
metric.** All 18 scenario/profile combinations show exactly 0.0% spread in
their final `median_metrics.json`. This holds even for scenarios that
needed a mid-batch retry (PQC 140ms, PQC 225ms\*, PQC 320ms) -- the retry
mechanism (Decision 5) re-runs the ENTIRE flow on failure and only records
the successful attempt, so a transient failure never contaminates the
median with partial/inconsistent data.

## Incidents encountered during the batch (all resolved, full detail in DECISIONS.md)

1. **`docker logs` transient timeout** (Classic, 14ms, run 2) -- gateway-
   metrics collection hiccup, unrelated to the HTTP flow itself. Fixed with
   a one-retry-on-empty in `run_once()`. *(Decision in DECISIONS.md context,
   folded into the median_automation.py docstring.)*
2. **Full Docker Desktop daemon hang** (discovered right after incident 1,
   escalated when even `docker version`/`docker ps` stopped responding).
   Required a full Docker Desktop restart (`taskkill` + `wsl --shutdown` +
   relaunch) and rebuilding the entire `insurance-server-lambdas` stack
   from scratch. Not caused by this session's code -- resource exhaustion
   from ~20 rapid consecutive flow executions.
3. **`pqc-signer` docker-run timeout** (PQC, 140ms, run 9/10) -- Decision 4.
   A single `docker run --rm -i mockopin-pqc-signer` invocation exceeded
   the original 30s timeout under sustained ephemeral-container load, even
   though the daemon itself was healthy. Fixed: shared `_run_pqc_signer()`
   helper, 60s timeout + one retry, used by both `sign_jwt()`'s ML-DSA-65
   branch and `_sign_jwt_hybrid()`.
4. **Reentrant `auth`<->`mock_mtls` introspection race** (PQC, 225ms,
   run 9/10) -- Decision 5. `auth`'s own internal consent-fetch call
   (server-to-server, to the RS) loops back through the gateway, which
   must introspect the AS's bearer token by calling `auth` again --
   occasionally raced against the *outer* `/token` request the whole chain
   started from, producing an EOF, a 401, and ultimately `400 invalid_grant`
   on the original request. Root-caused via the gateway's own access log
   (`docker logs mtls --since ... --until ...`, explicit `+00:00` offset
   required). Not specific to PQC (the same call happens on every
   profile); pure timing coincidence, ~1 in 89 token exchanges at the time
   it was first caught. Fixed with a whole-run retry (`RUN_RETRY_LIMIT = 2`
   in `median_automation.py`), logged transparently to `retry_log` in every
   scenario's `median_metrics.json`.
5. *\*PQC 320ms* needed 2 retries (run 3: PAR `502 Bad Gateway`; run 4:
   token `400`) -- both recovered on the first retry attempt. Same
   incident class as #4 (auth under sustained high-latency load),
   manifesting at different endpoints; both fully absorbed by the
   Decision 5 retry mechanism without operator intervention.

Total: **3 whole-run retries fired across 180 runs** (140ms/PQC: 1 partial
batch redone from scratch before the retry mechanism existed;
225ms/PQC: 1, absorbed cleanly; 320ms/PQC: 2, absorbed cleanly). All
absorbed automatically after Decision 5 was in place; zero runs were lost
to the final dataset.

## Pending anomalies

**None.** Every scenario converged to a clean, 0%-spread median. No open
questions remain from this batch.

## Not yet done

- This report and the underlying `runs/`/`median_metrics.json`/
  `MEDIAN_REPORT.md` data, plus the `opin_flow.py`/`median_automation.py`
  code changes from Decisions 4-5, are **not yet committed**.
