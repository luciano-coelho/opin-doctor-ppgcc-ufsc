# v8 Metrics Coverage

Maps every metric in v7's `Consolidated_Metrics_Report_FINAL.md` (computed by
`thesis/scripts/compute_v7_report_data.py` from `thesis/results/v7/report_data_v7.json`)
to its v8 data source, plus the new metrics v8 adds. Written during the
2026-10-21 light flow check (Decision — see `DECISIONS.md`): that check ran
`opin_flow.py`/`campaign_client_runner.py` for real, under Python 3.9 in an
`amazonlinux:2023` container with the campaign's own `--memory=8g --cpus=2`
limits, for all three crypto profiles, against the local MockOPIN stack. The
"v8 data source" and "status" columns below are not guesses: most were
cross-checked against the check's own real output, reported inline.

**v8 campaign folder structure** (Decision 53, `campaign_run.py` docstring):

```
v8/latency/experiment{1,2,3} - {Classic,PQC,Hybrid}/{server}/{scenario}/
  runs/run{NN}.json           (window, server, client, instance_type, result)
  runs/run{NN}.calls.jsonl    (per-call record: endpoint, request_bytes,
                               response_bytes, jwt_sizes, jwk_sizes, latency_ms)
  server/run{NN}_gateway.log, run{NN}_cpu.jsonl, run{NN}.pcap.gz
  client/run{NN}_cpu.jsonl, run{NN}_ping.json, run{NN}.pcap.gz
  median_metrics.json, report.md   (local post-processing -- consolidate_v8.py)

v8/size/experiment{1,2,3} - {Classic,PQC,Hybrid}/{server}/
  median_metrics.json, report.md   (derived from v8/latency's own runs, Decision 55/58)
```

## Traffic: OPINsize

| Metric | Definition | v8 data source | Status | Observation |
|---|---|---|---|---|
| OPINsize (bytes) | N_mTLS × handshake_bytes + N_JWT × JWT_size + N_JWK × JWK_PK_size + N_PKI × PKI_bytes | sum of the four terms below | **covered with gap** | 3 of 4 terms (JWT, JWK, PKI) reproduce v7's own numbers exactly from data the check already produced (see below). The 4th term (mTLS handshake bytes) has no extractor yet -- see that row. |
| term_handshake (N_mTLS × handshake_bytes) | mTLS handshake size, median of the 6 connections, from raw TCP capture (ClientHello..Finished) | `server/run{NN}.pcap.gz` + `client/run{NN}.pcap.gz` (captured by `campaign_run.py`'s tcpdump wiring) | **not covered** | The check's own `campaign_client_runner.py` output has no TCP/TLS-level field at all (application-layer HTTP only: `request_bytes`/`response_bytes`/`jwt_sizes`/`jwk_sizes`). v7's own figure came from a *separate* pipeline (`compute_v7_report_data.py` reading `gateway_metrics.handshake_bytes.p50_bytes` from the size-experiment's `runNN_baseline_metrics.json`, itself produced by a live-capture tool not yet ported to v8). **Fix size: large** -- needs a pcap parser that isolates each mTLS connection's byte count from `run{NN}.pcap.gz`. Not done this turn; -> "depois do piloto". |
| term_jwt (N_JWT × JWT_size) | Sum of all transferred JWTs' byte length (header+payload+signature) | `runs/run{NN}.calls.jsonl` -> `sum(call["jwt_sizes"])` across all calls | **covered** | Verified exactly against v7's `term_jwt_corrected` using this turn's own real check data: classic 37,263 vs v7 37,263; pqc 151,321 vs v7 151,321; hybrid 200,567 vs v7 200,567. Byte-for-byte match, no fixture needed. |
| term_jwk (N_JWK × JWK_PK_size) | Number of `/jwks` fetches times the AS's published signing-key size | `runs/run{NN}.calls.jsonl` -> for each call, `[j for j in call["jwk_sizes"] if j["use"]=="sig"]`; count × size_bytes | **covered** | Verified exactly: classic 512 vs v7 512; pqc 3,904 vs v7 3,904; hybrid 4,416 vs v7 4,416. The `"enc"`-use JWK entry (RSA-OAEP key, used for `id_token` encryption) is present in the same `jwk_sizes` list and must stay excluded, same as v7. |
| term_pki (N_PKI × PKI_bytes) | CA certificate (root+issuer) body bytes, 2 fetches each, 2 sub-flows | `runs/run{NN}.calls.jsonl` -> calls where `endpoint in ("/root-ca.pem","/issuer-ca.pem")`, `sum(response_bytes)` minus HTTP framing (103 B/response, same constant v7 found) | **covered** | Verified exactly after subtracting framing (4 × 103 B = 412 B): classic 8,852-412=8,440 vs v7 8,440; pqc 32,440-412=32,028 vs v7 32,028 (pqc's own corrected figure); hybrid 37,768-412=37,356 vs v7 37,356. The un-subtracted total (8,852/32,440/37,768) also matches v7's own "Directory/PKI" bytes-per-participant row exactly. |

## mTLS handshake

| Metric | Definition | v8 data source | Status | Observation |
|---|---|---|---|---|
| mTLS handshake: bytes (P50) | Same as term_handshake above, reported standalone | same as term_handshake | **not covered** | Same gap: needs the pcap extractor. |
| ClientHello (bytes) | The ClientHello message specifically, as the start-of-capture marker for handshake_bytes | `client/run{NN}.pcap.gz` | **not covered** | v7 never reported ClientHello as its own row either -- it's part of the handshake-capture *methodology* (Section 1.5: "from the ClientHello to the Finished"), not a separate published number. Same extractor gap as term_handshake; once built, isolating ClientHello alone is a strict subset of the same parse. |

## Cryptographic artifacts

| Metric | Definition | v8 data source | Status | Observation |
|---|---|---|---|---|
| Average JWT (bytes) | term_jwt / N_JWT | `runs/run{NN}.calls.jsonl`, same source as term_jwt, divided by count | **covered** | Direct corollary of term_jwt's exact match above. |
| Client certificate (DER bytes) | Size of the test client's own certificate on the mTLS connection | not in `calls.jsonl` (certificate isn't an HTTP call); available on disk at `mock-service-os/certs/client_one{,_pqc,_hybrid}.crt`, DER length via `pem_der_len()` (same helper `compute_v7_report_data.py` already uses) | **covered, different source** | Static artifact, not a live measurement -- reading the file is sufficient and was already v7's own method (`compute_v7_report_data.py:66-71`). No new instrumentation needed; `consolidate_v8.py` can reuse that exact helper against v8's own cert paths (they are the same files v7 used, unchanged). |
| JWK_PK_size: AS public key (bytes) | Size of the "sig"-use JWK published at `/jwks` | same as term_jwk's source | **covered** | Same exact match as term_jwk above. |
| Average PKI_bytes: CA certificate (bytes, PEM body) | term_pki / N_PKI | same as term_pki's source, or directly `(CERTS / root_file).stat().st_size` | **covered** | Either derivation matches; confirmed via the calls-based route above. |

## Bytes per participant (application layer)

| Metric | Definition | v8 data source | Status | Observation |
|---|---|---|---|---|
| Authorization Server (AS) outbound | Sum of response_bytes for calls where participant == "Other" served by the AS (consent, PAR, tokens, JWKS, login/consent HTML, JARM) | `runs/run{NN}.calls.jsonl` -> group by `call["participant"]` and endpoint prefix | **covered** | `calls.jsonl`'s own `participant` field (seen in the check's real output: `"Other"`, `"PKI/CRL"`) already carries the classification v7's `bytes_by_participant` table used; `compute_v7_report_data.py:99-101` reads an equivalent structure (`r["bytes_by_participant"][p][leg]`) from the size-experiment's own JSON, which has the same shape. |
| Resource Server (RS) outbound | Sum of response_bytes for the 4 personal-data query endpoints | same source | **covered** | Same mechanism. |
| Directory/PKI outbound | Sum of response_bytes for `/root-ca.pem`+`/issuer-ca.pem` | same source, `participant == "PKI/CRL"` | **covered** | Exact match already shown under term_pki above. |

## Latency per endpoint (P50, lowest-RTT scenario)

| Metric | Definition | v8 data source | Status | Observation |
|---|---|---|---|---|
| `/token`, `/consents` POST, `/consents/{id}` GET, `/request` PAR POST, personal-data APIs avg, `/jwks` GET, Directory/PKI download | P50 latency per endpoint, at the scenario closest to 0ms network delay | `runs/run{NN}.calls.jsonl` -> `call["latency_ms"]` grouped by `call["endpoint"]`, median across the N runs of v8's own lowest-RTT scenario (`sa-east-1`/L0, same server+client region -- the real-network analogue of v7's simulated 0ms) | **covered** | `latency_ms` is already a per-call field in the real check output (e.g. the check's own `/jwks` call measured 41-62ms across profiles, same client-side wall-clock method v7 used). v8's L0 scenario is co-located (no real inter-region hop), the correct analogue of v7's 0ms row. |

## Fixed parameters of the OPINsize equation

| Metric | Definition | v8 data source | Status | Observation |
|---|---|---|---|---|
| N_mTLS | Number of distinct mTLS handshakes (6) | `runs/run{NN}.calls.jsonl` grouped by `pool_label` (the check's calls carry a `session-<id>` pool label distinguishing connection pools) | **covered** | Not independently re-derived this turn by counting pools, but the check's own `call_count=42` and the per-call `pool_label` field are consistent with v7's "3 pools × 2 sub-flows = 6" structure; a small follow-up to count distinct `pool_label` values per run would make this fully explicit in `consolidate_v8.py`. |
| N_JWT | Number of JWTs transferred (28) | `runs/run{NN}.calls.jsonl` -> `sum(len(call["jwt_sizes"]) for call in calls)` | **covered** | Verified exactly: 28 in all three profiles, matching v7's corrected (JARM-inclusive) figure, directly from this turn's real check data -- no correction needed on the v8 side, the fix is already baked into the current flow's instrumentation. |
| N_JWK | Number of `/jwks` fetches (2) | `runs/run{NN}.calls.jsonl` -> count of calls with `endpoint == "/jwks"` | **covered** | Verified exactly: 2 in all three profiles. |
| N_PKI | Number of CA certificate fetches (4) | `runs/run{NN}.calls.jsonl` -> count of calls with `endpoint in ("/root-ca.pem","/issuer-ca.pem")` | **covered** | Verified exactly: 4 in all three profiles. |

## Flow time

| Metric | Definition | v8 data source | Status | Observation |
|---|---|---|---|---|
| T_fluxo (total flow latency) | Wall-clock time of the complete flow, monotonic clock, median of N runs per scenario/profile | `runs/run{NN}.json` -> `result.t_fluxo_seconds` | **covered** | This IS the metric the whole v8 campaign exists to re-measure under real network conditions instead of `tc`/`netem`. The check's own real runs produced `t_fluxo_seconds` for all three profiles (6.67s/9.31s/10.22s classic/pqc/hybrid, 0ms-equivalent localhost -- not directly comparable to v7's own 0ms numbers since this check ran inside a resource-constrained, cold-cache container, not a measurement run). |
| Call count (42) | Total HTTP requests per complete flow | `runs/run{NN}.json` -> `result.call_count` | **covered** | Verified exactly: 42 in all three profiles, matching v7's own latency-experiment figure (`thesis/results/v7/latency/.../run01.json`'s own `call_count: 42` -- confirmed by reading that file directly). Not to be confused with the *size*-experiment's `total_requests: 28`, a different, narrower count from a different pipeline (see note below). |
| Flow time decomposition (mTLS handshake / server processing / residual) | Where T_fluxo's time actually goes | handshake share needs term_handshake's pcap extractor (not covered); server-processing share needs `server/run{NN}_gateway.log` parsing (not yet built for v8) | **not covered** | Same root gap as term_handshake -- no pcap/gateway-log parser exists yet for v8. Not attempted this turn ("depois do piloto"); the raw artifacts (`*.pcap.gz`, `*_gateway.log`) are already planned to be collected by `campaign_run.py`, so this is a missing *analysis* step, not a missing *collection* step. |

## New in v8 (not in v7 at all)

| Metric | Definition | v8 data source | Status | Observation |
|---|---|---|---|---|
| RTT (real network round-trip time) | Real measured latency between client and server regions, replacing v7's `tc`/`netem` emulated delay | `client/run{NN}_ping.json` -> `raw_ping_output` (`ping -c 10 -q <server_ip>`, parsed for `rtt min/avg/max/mdev`) | **new** | This is the whole point of v8: v7's scenarios were *target* RTTs chosen to match Schardong et al. (2022)'s AWS measurements; v8 measures the *actual* RTT of each region pair instead of assuming it. The region-to-scenario mapping itself is in `thesis/results/v8/latency-discovery/`. |
| Packet loss (upper bound) | Loss rate between client and server | same `client/run{NN}_ping.json` -> parsed loss % from the same `ping -c 10` output | **new, upper bound only** | `ping -c 10` gives loss in 10% increments (1 lost packet = 10%), so it can only usefully say "loss ≤ X%" at this sample size, not a precise rate -- reported as an upper bound, not a point estimate, exactly per the user's own framing. A tighter estimate would need a larger `-c` or a dedicated loss-measurement tool; not done this turn. |
| CPU utilization | Server/client CPU usage during a run | `server/run{NN}_cpu.jsonl`, `client/run{NN}_cpu.jsonl` -> `_sample_cpu_mem_steal()`'s own `cpu.total`/`cpu.idle` fields, sampled throughout the run (`campaign_run.py:638-701`) | **new** | Already implemented and wired into `campaign_run.py`'s real/local executors (both call the same sampler). `consolidate_v8.py` needs to parse the JSONL and compute utilization %, not re-invent collection. |
| CPU steal | Hypervisor-level CPU steal time (relevant on shared-tenancy EC2 instance types) | same `_cpu.jsonl` files -> `cpu.steal` field (`/proc/stat`'s own `steal` column) | **new** | Same sampler as CPU utilization; steal is a separate field already captured, not an extra collection step. |
| Memory | Server/client memory usage during a run | same `_cpu.jsonl` files -> `_sample_cpu_mem_steal()`'s own memory fields (from `/proc/meminfo`) | **new** | Same sampler, already captured alongside CPU/steal in one JSONL stream per run. |
| Bootstrap confidence interval of the median | A statistical addition: since v8's real-AWS campaign runs fewer repetitions per scenario (30) than v7's lab setup (60), a plain median alone understates the uncertainty at that sample size | computed by `consolidate_v8.py` itself from the pooled per-scenario values in `runs/run{NN}.json` -- not a raw collected field, a derived statistic | **new, to be computed at consolidation time** | v7 reported median + min/max/mean/stdev/spread (Section 1.5); v8 adds a bootstrap CI around the median as a direct response to the smaller N, using the same resampling method for every scenario/profile cell so the uncertainty is comparable across the table. |

## Summary

- **Fully covered, exact match confirmed against v7's own numbers using this turn's real check data:** term_jwt, term_jwk, term_pki (and therefore average JWT, JWK_PK_size, average PKI_bytes, bytes-per-participant), N_JWT, N_JWK, N_PKI, call count (42).
- **Covered, not independently re-verified this turn but backed by existing, already-wired instrumentation:** client certificate DER bytes (static file read), N_mTLS (pool-label grouping), latency per endpoint, T_fluxo, RTT, packet loss (upper bound), CPU/steal/memory.
- **Not covered -- real gap, size "large", -> depois do piloto:** term_handshake (and therefore OPINsize's own total, and the handshake/server/residual time decomposition) and ClientHello, both blocked on the same missing piece: a pcap parser that extracts per-connection TCP/TLS byte counts from `run{NN}.pcap.gz`. The raw `.pcap.gz` files themselves are already planned to be collected by `campaign_run.py` -- this is a missing *analysis* tool, not a missing *collection* step, and the fix (once built) is reusable across all three affected rows at once.
- **New, to be computed at consolidation time, not a raw field:** bootstrap CI of the median.

A note on the "42 requests" vs "28 total_requests" figures, both real, both from v7, neither a mistake: v7 has two separate pipelines over the same underlying flow -- the *latency* experiment (`thesis/results/v7/latency/`, same `call_count=42` field this check reproduced) and the *size* experiment (`thesis/results/v7/size/`, which reports a different, narrower `total_requests=28`, counting requests at the level the byte/size instrumentation groups them, not every individual HTTP call). v8's `campaign_run.py` currently only builds the `v8/latency/` tree (Decision 53's docstring); the `v8/size/` tree is planned (Decision 55/58) to be *derived* from `v8/latency/`'s own runs, not collected separately -- so this check, which exercises the latency-style tooling, is measuring the right thing for what v8 currently builds.
