# Final Comparative Table — Classic | PQC | Hybrid (v5)

This file consolidates the comparative table across the three profiles (Classic, pure PQC, Hybrid)
against v5's definitive data — median of 10 executions per scenario, 180 total
executions (3 profiles × 6 scenarios × 10), 0% spread on every size metric in every
scenario. Source: `thesis/results/v5/experiment{1,2,3} - {Classic,PQC,Hybrid}/*/median_metrics.json`
and `CONSOLIDATED_REPORT.md`. No value in this file was carried over from `v3`/`v4` —
every value was either recalculated or re-measured from v5 (see Decision 6 in `DECISIONS.md`
for the one value that needed a pipeline fix before it could be measured at all).

Every size metric is identical across the 6 latency scenarios (0/14/30/140/225/320ms)
within each profile — payload size does not depend on network latency, only response
time does (see Decision 12 in `thesis/results/v4/DECISIONS.md`). The values below
hold for any of the 6 scenarios.

---

## Aggregation Methodology

Every value in this document goes through up to two layers of statistical aggregation,
applied by distinct code paths (`baseline_automation.py` for the intra-run layer,
`median_automation.py` for the cross-run layer) — not always the same process in both
layers, and not always both. This section documents exactly which process applies
to each metric, at each layer, to eliminate any ambiguity about "median of what."

**Layer 1 — intra-run**: within a single execution of the flow (28 HTTP calls),
some metrics result from an aggregation over multiple samples collected within that
same run (e.g., ~6 physical mTLS connections, 26 JWTs). Others have no such layer — they
are already a closed total per run, or a constant that never varies.

**Layer 2 — cross-run**: `median_automation.py` runs the flow 10 times per scenario and
computes the **median** of the 10 values already produced by Layer 1 (or, when there is
no Layer 1, the median of the 10 raw per-run values) — it never pools individual samples
from multiple runs into a single calculation. See `thesis/results/v5/DECISIONS.md` and
`median_automation.py::summarize()`/`NAMED_SCALAR_METRICS`.

| Metric | Layer 1 (intra-run) | Layer 2 (cross-run) | Final N in the median |
|---|---|---|---|
| mTLS_handshake_bytes (P50) | **Median** of ~6 byte samples per physical connection (deduplicated by `remoteIP:port`, outliers >3× the median removed iteratively — `filter_handshake_outliers`) | **Median** of the 10 already-computed P50s | 10 numbers (each already a median of ~6) |
| Average JWT | **Mean** (not median) of the 26 JWT sizes captured in the run | **Median** of the 10 already-computed means | 10 numbers (each already a mean of 26) |
| total_bytes_exchanged | **Sum** of `request_bytes+response_bytes` across the run's 28 calls (not a central-tendency statistic, it's a total) | **Median** of the 10 sums | 10 numbers (each already a sum of 28) |
| bytes_by_participant (Client/AS/RS/PKI-CRL, sent/received) | **Sum** per participant/direction, over the calls routed to it within that run | **Median** of the 10 sums, separately per participant×direction | 10 numbers per table cell |
| Client certificate (DER bytes) | None — a static property of the certificate file (`client_cert_der_bytes(profile)`), identical on every call | Median of 10 identical values (trivial) | 10 numbers, all equal — not a real aggregation, a constant reconfirmed 10× |
| JWK_PK_size | **No layer of the 180-run pipeline** | **None** — never goes through `median_automation.py` at all | 0 — value obtained outside the batch, via live/static verification (Decision 6), not via a median across runs |

**Asymmetry not to be assumed by mistake — average JWT.** Unlike `mTLS_handshake_bytes`,
Average JWT's Layer 1 is a **mean**, not a median: `jwt_size_avg_bytes` is
`statistics.mean()` over the 26 JWT sizes of one run. Only Layer 2 (across the 10
runs) uses a median. Both metrics go through "two aggregation layers," but with
different statistical processes at each layer — not every metric is a "median of medians."

**JWK_PK_size is not a statistic of the 180-run batch.** It is a
cryptographic constant — the fixed byte size of the ML-DSA-65 public key (1,952) or of
the RSA+ML-DSA-65 concatenation (2,208) — confirmed by direct decoding of the key
material (live via `/jwks`, or statically via `crypto-profiles/{pqc,hybrid}.json`), not
computed from samples collected during the runs (Decision 6). Unlike every other
row in this table, none of the 180 runs mathematically contributes to this number —
they only confirm, indirectly, that the key published at `/jwks` did not change size
during the batch (which indeed it would not, since the key is fixed per profile).

---

## Traffic — OPINsize

**Validated formula**: `OPINsize = N_mTLS × handshake_bytes(P50) + N_JWT × Average_JWT + N_JWK × JWK_PK_size`

| Metric | Classic | PQC | Hybrid | Note |
|---|---|---|---|---|
| OPINsize (bytes) | 95,242.92 | 264,369.06 | 350,141.06 | Calculation: 6×9,785.0 + 26×1,385.42 + 2×256 (Classic); 6×19,756.0 + 26×5,458.81 + 2×1,952 (PQC); 6×25,880.0 + 26×7,324.81 + 2×2,208 (Hybrid). Under hybrid, the total flow cost is 350,141.06 bytes — 32.44% above pure PQC and 3.68× above classic. All three terms of the equation grow simultaneously under hybrid: the handshake carries the full RSA structure plus the three post-quantum extensions; each of the 26 JWTs carries a composite signature (σ1‖σ2, Strong Nesting, for AS-issued artifacts) or the `pqc` payload extension (for client-signed ones, Decision 13); and the published public key is the concatenation of both keys. The equation itself has no PKI/CRL term — the Classic profile's local-certificate fix (Decision 1) does not affect this value directly. |

## mTLS Handshake

| Metric | Classic | PQC | Hybrid | Note |
|---|---|---|---|---|
| mTLS_handshake_bytes — P50 | 9,785.0 | 19,756.0 | 25,880.0 | Under hybrid, the handshake is 2.64× classic and 1.31× PQC. Stable (0% spread) across the 6 scenarios and the 10 runs of each scenario — the certificate presented during the handshake (`mtls_hybrid.crt`) carries both the RSA signature and the three non-critical X.509 extensions with the full ML-DSA-65 material (dual nested combiner, Bindel et al. 2019), increasing the size of the TLS negotiation's `Certificate` message beyond what either scheme alone would require. |

## Cryptographic Artifacts

| Metric | Classic | PQC | Hybrid | Note |
|---|---|---|---|---|
| Average JWT (bytes) | 1,385.42 | 5,458.81 | 7,324.81 | Under hybrid, the average is 34.18% above pure PQC and 5.29× classic. All 26 JWTs in the flow carry hybrid material — those issued by the AS (id_token, JARM, access/consent tokens) use Strong Nesting (σ1‖σ2, one full RSA signature followed by one full ML-DSA-65 signature); those signed by the client (client assertion, PAR request object) use the `pqc` payload extension over an ordinary RS256 JWT (Decision 13, `thesis/results/v4/DECISIONS.md`) — heavier than a lone ML-DSA-65 signature in both cases, since they carry both signatures at once rather than just one. |
| Client certificate (DER bytes) | 1,494 | 2,953 | 6,859 | Under hybrid, the certificate is 4.59× classic and 2.32× PQC — it carries the original RSA structure plus the three non-critical X.509 extensions with the full post-quantum material simultaneously (the same architecture as the handshake certificate above, since it's the same dual nested combiner mechanism applied to the client's identity). Value re-measured directly from the `client_cert_der_bytes` field in v5's raw data (identical, 0% spread, across the 180 runs) — not inherited from v3/v4. It coincides with the number reported before precisely because it's a structural constant of the certificate (same key pair, same X.509 extension, not subject to measurement noise), not because of reuse. |
| JWK_PK_size — AS signing public key | 256 (RSA-2048) | 1,952 (ML-DSA-65) | 2,208 (256+1,952) | Under hybrid, the key published at `/jwks` is the byte-for-byte concatenation of the two public keys under a single `kid` (`kty: "HYBRID"`, `pk_hybrid` field) — 2,208 bytes, 8.63× classic. This value was not available in v5's raw data until this round: `extract_jwk_sizes()` only recognized `kty` RSA/EC and silently dropped the `AKP` (PQC) and `HYBRID` keys, fixed and re-measured live against the same key material used throughout the 180-run batch (Decision 6). |

## Bytes by Participant

| Metric | Classic | PQC | Hybrid | Note |
|---|---|---|---|---|
| Authorization Server — AS (sent+received) | 26,063 | 71,270 | 90,433 | Under hybrid, the AS moves 90,433 bytes — 26.89% above pure PQC. Every token issued by the AS (id_token, JARM, access tokens) carries a full Strong Nesting signature; the difference over pure PQC reflects the cost of attaching a whole RSA signature to every artifact that already carried ML-DSA-65 alone. |
| Data Server — RS (sent+received) | 30,873 | 96,091 | 126,035 | Under hybrid, the RS moves 126,035 bytes — 31.16% above pure PQC, same cause as the AS: every response signed by the RS (protected resources) carries the full composite signature, not just the post-quantum half. |
| PKI/CRL (sent+received) | 9,516 | 17,276 | 38,432 | Under hybrid, PKI/CRL is 4.04× classic and 2.22× PQC — the hybrid `root-ca.pem`/`issuer-ca.pem` carry the same dual nested combiner as the handshake/client certificates above (full RSA plus three ML-DSA-65 extensions), the largest of the three profiles because it represents two files (root+issuer), each with the full hybrid structure. Classic's value (9,516) is lower than what was historically reported (10,664, using Raidiam's real sandbox) — the expected effect of Decision 1 (v5): Classic now uses local `root_ca.crt`/`issuer_ca.crt` (1,515/1,519 bytes DER), smaller than the real external certificates that used to be fetched. |
| Client — total flow traffic | 66,452 | 184,637 | 254,900 | Equal to the scenario's `total_bytes_exchanged` — the sum of everything the client sent and received across the flow's 28 HTTP calls. Under hybrid, 38.05% above pure PQC and 3.84× classic, reflecting the accumulation of every item above (larger handshakes, larger JWTs, larger PKI/CRL). Identical (0% spread) across the 10 runs of each of the 6 latency scenarios. |

## Fixed Parameters of the Equation

Confirmed from v5's raw data (`jwt_count`, `gateway_metrics.handshake_bytes.count`
in each profile's `runs/run01_baseline_metrics.json`) before assuming the already-expected values.

| Metric | Classic | PQC | Hybrid |
|---|---|---|---|
| N_mTLS | 6 | 6 | 6 |
| N_JWT | 26 | 26 | 26 |
| N_JWK | 2 | 2 | 2 |

---
