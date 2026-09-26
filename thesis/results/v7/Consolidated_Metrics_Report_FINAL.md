# Consolidated Experimental Metrics Report: final version

**Post-quantum migration of the OPIN ecosystem: Classic, pure PQC, and Hybrid**
Luciano Figueiredo Coelho | PPGCC/LabSEC/UFSC

## 1. Objective and context

### 1.1. What was measured

This document consolidates the final results of the cost measurement, in bytes transferred and in flow time, of migrating the Open Insurance Brasil (OPIN) consent flow to post-quantum cryptography (PQC) and to a hybrid combination.

The measurement target is a complete OPIN flow, executed by a test client against a prototype authorization server (AS), a resource server (RS), and an mTLS gateway. The flow covers consent, authorization request (PAR), automated login, code-for-token exchange, and resource queries.

Each complete execution has the following structure, identical across all three profiles:

| Element | Quantity | Detail |
|---|---:|---|
| HTTP requests | 28 | distributed across two sub-flows |
| mTLS connections | 6 | three connection pools per sub-flow (AS/API, Directory, and login), each reused by every call in its pool |
| JWTs transferred | 26 | |
| JWKS fetches | 2 | one per sub-flow |
| CA certificate fetches | 4 | root and issuer, in each sub-flow |

Since this structure does not change between profiles, every measured difference comes from the cryptography used in each one.

### 1.2. The three profiles

| Profile | Signatures | TLS key exchange |
|---|---|---|
| Classic | RSA (PS256) | ECDHE, single P-384 curve |
| PQC | Pure ML-DSA-65 (NIST FIPS 204) on tokens and subject keys; certificates issued by a CA with an RSA signature | Pure ML-KEM-1024 (NIST FIPS 203) |
| Hybrid | RSA and ML-DSA-65 combined: certificates with a dual signature in non-critical X.509 extensions; payload extension on the RS's JWTs, on the `client_assertion`, and on the PAR object; Strong Nesting on the `id_token` and on the JARM | SecP384r1MLKEM1024 (P-384 + ML-KEM-1024) |

Three design properties ensure the comparisons are fair:

- **Symmetric chain in the key exchange.** Hybrid combines exactly Classic's curve (P-384) and PQC's parameter (ML-KEM-1024). Hybrid's cost can therefore be read relative to its two components.
- **A single group per profile, with no fallback.** Each profile negotiates only its own key-exchange group; if the server doesn't offer it, the connection fails, instead of silently falling back to another group.
- **Same RSA key size.** In both Classic and Hybrid, the RSA component of the JWT signatures uses a key of the same size; the difference between the two profiles comes only from the post-quantum material.

Across all profiles, `id_token` encryption (RSA-OAEP with AES-256-GCM) remains classical, since there is no post-quantum JOSE encryption standard.

Every number in this document originates from `thesis/results/v7/report_data_v7.json`, independently recomputed from the raw files (`thesis/scripts/audit_v7_from_raw.py`).

### 1.3. Implementation control

All three profiles use the same TLS client implementation; only the requested key-exchange group changes. Post-quantum signatures on the client side are performed by a process persistent for the duration of one run, not by a new process for every signature. This ensures the difference between profiles is not contaminated by a change of implementation.

### 1.4. Environment

- **Machine:** a single computer, Docker Desktop on Windows 11.
- **Software:** Go 1.27 (release-candidate version), Node.js 24, and BouncyCastle.
- **Emulated latency:** `tc`/`netem` applied only to the gateway's outbound traffic, with no packet loss or delay jitter. Since every response packet leaves the gateway, each scenario's value is added once per round trip.

The environment is a lab setup and does not reproduce a real long-distance network.

### 1.5. Collection protocol

- **Design:** 6 latency scenarios (0, 14, 30, 140, 225, and 320 ms) × 10 runs × 3 profiles, for size and for latency.
- **Warm-up:** after every profile switch, the environment is only released for measurement once it has settled (containers up, gateway accepting connections, and a stable database). Each latency scenario additionally has one discarded warm-up run.
- **Time (T_fluxo):** time of the complete flow, measured with a monotonic clock on the client, with no outlier removal.
- **Size:**
  - `handshake_bytes` is measured at the gateway, on the raw TCP connection (read + write, from the ClientHello to the Finished), as the median of the 6 connections of each run. The negotiated group is recorded from the actual connection state, not from the configuration.
  - JWTs and JWK keys are measured by the length of the token and of the key, without headers.
  - Bytes per participant are counted at the application layer (HTTP headers + body).
- **Statistics:** each cell reports the median of 10 runs, with minimum, maximum, mean, standard deviation, and spread (maximum minus minimum, divided by the minimum). Differences between profiles were assessed with the exact rank test, in a purely descriptive way, because each profile's runs were collected in sequential blocks and are not independent samples.
- **Traceability:** the raw data for every run is preserved, and every statistic was recomputed from it in an independent audit before consolidation.

---

## 2. Consolidated Metrics Table

| Metric | Classic | PQC | Hybrid | Note: meaning, decisions, and findings |
|---|---:|---:|---:|---|
| **Traffic: OPINsize** | | | | |
| OPINsize (bytes) | 75.687 | 261.663 | 340.355 | Total cryptographic-material cost of the complete flow, by this thesis's equation (Section 3): N_mTLS × handshake_bytes + N_JWT × JWT_size + N_JWK × JWK_PK_size + N_PKI × PKI_bytes. PQC is **3.46× Classic** (+245.72%); Hybrid is **4.50× Classic** (+349.69%) and **1.30× PQC** (+30.07%). Since the flow's structure is the same across all three profiles (N parameters at the end of this table), all of the growth comes from the size of the cryptographic artifacts. Hybrid sits above PQC on every size metric because its signed artifacts carry both signatures and its key exchange combines both mechanisms. |
| **mTLS handshake** | | | | |
| mTLS handshake: bytes (P50) | 5.119 | 16.605 | 18.023 | Size of each mTLS handshake, in bytes (P50 of the 6 connections), over 60 runs per profile (6 scenarios × 10). Spread of 0.00%: the value is deterministic. The number of handshakes is the same (6) across all three profiles; the variation comes only from the size of each one. PQC is 3.24× Classic (+224.38%); Hybrid is 3.52× Classic (+252.08%) and 1.09× PQC (+8.54%). Hybrid adds only 1.418 bytes per handshake over PQC, even though its client certificate is 3.906 bytes larger: in transport, the extra cost of hybrid protection is marginal. |
| **Cryptographic artifacts** | | | | |
| Average JWT (bytes) | 1.385,42 | 5.458,81 | 7.324,81 | Average size of the JWTs (header + payload + signature) over the flow's 26 tokens, a number equal across all three profiles. PQC is 3.94× Classic (+294.02%); Hybrid is 5.29× Classic (+428.71%) and 1.34× PQC (+34.18%). The ML-DSA-65 signature (3.309 bytes) replaces PS256 (256 bytes) in PQC; in Hybrid, both coexist in the same token, either via payload extension (RS256 + ML-DSA-65) or via Strong Nesting (PS256 + ML-DSA-65), depending on the artifact. |
| Client certificate (DER bytes) | 1.494 | 2.953 | 6.859 | Size of the test client's certificate, presented on the mTLS connection. PQC is 1.98× Classic (+97.66%); Hybrid is 4.59× Classic (+359.10%) and 2.32× PQC (+132.27%). In PQC, only the subject's key changes (ML-DSA-65); the CA still signs with RSA. The hybrid certificate reuses Classic's RSA key and adds, in three non-critical X.509 extensions (Bindel et al., 2019), the ML-DSA-65 public key and an alternate ML-DSA-65 signature from the CA. That's why it exceeds the sum of the two isolated certificates (4.447 bytes): it carries an ML-DSA-65 signature from the CA (3.309 bytes) that doesn't exist in the PQC certificate. |
| JWK_PK_size: AS public key (bytes) | 256 (RSA-2048) | 1.952 (ML-DSA-65) | 2.208 (composite, `kty: HYBRID`) | Size of the AS's public key published at `/jwks`, used to verify the tokens. PQC is 7.62× Classic (+662.50%); Hybrid is 8.62× Classic (+762.50%) and 1.13× PQC (+13.11%). Since N_JWK is the same (2) across all three profiles, the growth comes only from the key's size; in Hybrid, a composite key carrying the RSA half and the ML-DSA-65 half (256 + 1.952 bytes). |
| Average PKI_bytes: CA certificate (bytes, PEM body) | 2.110 | 4.050 | 9.339 | Average size of the two CA certificates (root and issuer) in the format they're transferred in (PEM), without HTTP framing. PQC is 1.92× Classic (+91.94%); Hybrid is 4.43× Classic (+342.61%) and 2.31× PQC (+130.59%). Same pattern as the client certificate: in PQC, the CA certificates have an ML-DSA-65 key but an RSA signature; in Hybrid, they carry both signatures. |
| **Bytes per participant** (application layer; each server's outbound, or egress, values) | | | | |
| Authorization Server (AS) | 14.188 | 29.570 | 31.058 | AS outbound volume (consent, PAR, tokens, JWKS). PQC is 2.08× Classic (+108.42%); Hybrid is 2.19× Classic (+118.90%) and 1.05× PQC (+5.03%). The relative growth is smaller than the RS's because the AS issues few JWTs in the flow. Hybrid's small increase over PQC is consistent with the composition of its artifacts: `id_token`, JARM, and the published key essentially add the RSA part (256 bytes each) to the ML-DSA-65 material. |
| Resource Server (RS) | 26.034 | 91.252 | 121.196 | RS outbound volume (basic-data, claim, policy, and premium queries). PQC is 3.51× Classic (+250.51%); Hybrid is 4.66× Classic (+365.53%) and 1.33× PQC (+32.81%). It's the largest absolute increase among the participants (+95.162 bytes from Classic to Hybrid), because every query response is a JWT signed by the RS. Of the servers' total outbound traffic, the RS accounts for 53.1% in Classic, 66.4% in PQC, and 63.8% in Hybrid: it's the participant that weighs most on the cloud egress bill. |
| Directory/PKI (CA certificates, full HTTP response) | 8.852 | 16.612 | 37.768 | Directory outbound volume when serving the CA certificates: certificate body + 103-byte HTTP framing per response, identical across all three profiles. This constant value confirms, byte for byte, that the body served is exactly the file used in the PKI_bytes calculation. PQC is 1.88× Classic (+87.66%); Hybrid is 4.27× Classic (+326.66%) and 2.27× PQC (+127.35%). |
| **Latency per endpoint** (P50, 0 ms scenario, no emulated network delay) | | | | Locates where in the flow the post-quantum processing cost shows up. |
| `/token` (POST) | 21,99 ms | 46,28 ms | 54,08 ms | Endpoint that authenticates the client by verifying the signed `client_assertion`. PQC +24,29 ms (+110,46%) over Classic; Hybrid +32,09 ms (+145,93%) over Classic and +7,80 ms (+16,85%) over PQC. |
| `/consents` (POST) | 29,63 ms | 53,92 ms | 65,15 ms | Consent creation; the RS assembles and signs the response before returning it. PQC +24,29 ms (+81,98%); Hybrid +35,52 ms (+119,88%) over Classic and +11,23 ms (+20,83%) over PQC. |
| `/consents/{id}` (GET) | 14,11 ms | 27,04 ms | 31,73 ms | Consent-status queries, tracking the transition through to `AUTHORISED`; each response is signed by the RS. PQC +12,93 ms (+91,64%); Hybrid +17,62 ms (+124,88%) over Classic and +4,69 ms (+17,34%) over PQC. |
| `/request` (PAR, POST) | 9,55 ms | 19,27 ms | 21,51 ms | Submission of the authorization object signed by the client. PQC +9,72 ms (+101,78%); Hybrid +11,96 ms (+125,24%) over Classic and +2,24 ms (+11,62%) over PQC. |
| Personal-data APIs (average of 4 endpoints: basic data, claim, policy, premium) | 17,41 ms | 33,43 ms | 34,82 ms | Average latency of the four queries in the personal-data sub-flow, each response signed by the RS. PQC +16,02 ms (+92%) over Classic; Hybrid +17,41 ms (+100%) over Classic and +1,39 ms (+4,2%) over PQC. In PQC, the increase ranges from +9,98 ms (`policy-info`) to +22,44 ms (`claim`) across the endpoints. |
| `/jwks` (GET) | 26,00 ms | 21,05 ms | 27,31 ms | Reading the public keys, with no signing or verification at the endpoint. The differences (PQC −4,95 ms; Hybrid +1,31 ms over Classic) have no consistent direction and sit at the level of measurement noise. |
| Directory/PKI (CA certificate download) | 11,81 ms | 10,50 ms | 13,76 ms | Reading a static file. Same pattern as `/jwks`: no consistent direction (PQC −1,31 ms; Hybrid +1,95 ms over Classic), within the noise. Together with `/jwks`, this shows that the extra cost concentrates on endpoints that perform signing or verification, not on delivering larger keys or certificates. |
| **Fixed parameters of the OPINsize equation** | | | | |
| N_mTLS: distinct handshakes | 6 | 6 | 6 | Number of mTLS connections in the flow (three connection pools per sub-flow × 2 sub-flows). Equal across all three profiles: the growth in communication cost doesn't come from more connections, but from the size of each one. |
| N_JWT: tokens in the flow | 26 | 26 | 26 | Number of JWTs transferred. Equal across all three profiles. |
| N_JWK: `/jwks` fetches | 2 | 2 | 2 | Number of queries to the AS's public keys, one per sub-flow. Equal across all three profiles. |
| N_PKI: CA certificate fetches | 4 | 4 | 4 | New term from this thesis: number of CA certificate downloads (root and issuer, in each of the 2 sub-flows). Equal across all three profiles. Being explicit in the equation lets the estimate be adjusted to each participant's caching policy. |

## 3. The OPINsize Equation

The original flow-size equation (equivalent to Eq. 3.1 of Schardong et al., 2022) sums three terms — the cost of the mTLS handshake, of the tokens transferred, and of the published public keys. This thesis extends it with a fourth term, for the Certificate Authority certificates that the flow downloads and that were already measured but never entered the sum.

```
OPINsize = N_mTLS × handshake_bytes + N_JWT × JWT_size + N_JWK × JWK_PK_size + N_PKI × PKI_bytes
```

### 3.1 Equation variables

| Variable | Description | Classic | PQC | Hybrid |
|---|---|---:|---:|---:|
| N_mTLS | Number of distinct mTLS handshakes in the flow | 6 | 6 | 6 |
| handshake_bytes | Size of the mTLS handshake (P50) | 5.119 bytes | 16.605 bytes | 18.023 bytes |
| N_JWT | Number of JWT tokens in the flow | 26 | 26 | 26 |
| JWT_size | Average size of each JWT | 1.385,42 bytes | 5.458,81 bytes | 7.324,81 bytes |
| N_JWK | Number of calls to `/jwks` | 2 | 2 | 2 |
| JWK_PK_size | Size of the AS's public key | 256 bytes | 1.952 bytes | 2.208 bytes |
| N_PKI | Number of CA certificate fetches | 4 | 4 | 4 |
| PKI_bytes | Average size of the CA certificate (PEM) | 2.110 bytes | 4.050 bytes | 9.339 bytes |

### 3.2 Classic scenario calculation

```
OPINsize = (6 × 5.119) + (26 × 1.385,42) + (2 × 256) + (4 × 2.110)
6 × 5.119     = 30.714 bytes
26 × 1.385,42 = 36.021 bytes
2 × 256       =    512 bytes
4 × 2.110     =  8.440 bytes
OPINsize = 30.714 + 36.021 + 512 + 8.440 = 75.687 bytes
```

### 3.3 PQC scenario calculation

```
OPINsize = (6 × 16.605) + (26 × 5.458,81) + (2 × 1.952) + (4 × 4.050)
6 × 16.605     =  99.630 bytes
26 × 5.458,81  = 141.929 bytes
2 × 1.952      =   3.904 bytes
4 × 4.050      =  16.200 bytes
OPINsize = 99.630 + 141.929 + 3.904 + 16.200 = 261.663 bytes
```

### 3.4 Hybrid scenario calculation

```
OPINsize = (6 × 18.023) + (26 × 7.324,81) + (2 × 2.208) + (4 × 9.339)
6 × 18.023     = 108.138 bytes
26 × 7.324,81  = 190.445 bytes
2 × 2.208      =   4.416 bytes
4 × 9.339      =  37.356 bytes
OPINsize = 108.138 + 190.445 + 4.416 + 37.356 = 340.355 bytes
```

### 3.5 Comparison across profiles

| Ratio | OPINsize |
|---|---:|
| PQC / Classic | 3,46× (+245,72%) |
| Hybrid / Classic | 4,50× (+349,69%) |
| Hybrid / PQC | 1,30× (+30,07%) |

Migrating the OPIN consent flow to post-quantum cryptography multiplies the volume of cryptographic material transferred by 3,46 in PQC and by 4,50 in Hybrid: each complete flow goes from 75,7 kB to 261,7 kB and 340,4 kB, respectively. This growth requires no change to the flow. The number of connections, tokens, key fetches, and certificates is the same across all three profiles; only the size of each artifact grows. The migration, therefore, swaps out the cryptographic pieces without altering the ecosystem's specifications, and its byte cost can be estimated before adoption.

Most of this cost lies in the jump from Classic, not in the choice between PQC and Hybrid. Of Hybrid's total increase over Classic, 70% already shows up in pure PQC. Hybrid's additional guarantee — that it remains secure even if only one of the two algorithms is broken — costs 30% more than PQC. This supports Hybrid as a viable transition path.

The PKI term, absent from the original equation, accounts for 11,15% of OPINsize in Classic, 6,19% in PQC, and 10,98% in Hybrid. In every profile it outweighs the public-key (JWK) term, which the original equation already included. A migration plan based only on handshake, tokens, and keys underestimates the real cost, and the error is largest precisely in the hybrid profile, where the gap to PQC rises from 23,44% to 30,07% once the term is included. Since the measured flow downloads the CA certificates without caching, these values represent the worst case; the N_PKI parameter allows the estimate to be adjusted to each participant's actual behavior.

## 4. Flow Latency Under Different Network Scenarios

The per-endpoint latencies in Section 2 were measured at the 0 ms scenario, with no emulated network delay, to locate where in the flow the post-quantum processing cost shows up. This section answers a complementary question: how does the complete consent flow (the 28 calls, across the two sub-flows) behave under different network conditions?

The six scenarios (0, 14, 30, 140, 225, and 320 ms, emulated with `tc`/`netem` at the gateway) reproduce the latency values measured empirically across five AWS geographic regions by Schardong et al. (2022). The two sections complement each other: Section 2 offers a granular, per-component view; this one, an aggregated view, per network condition.

### Total flow latency (T_fluxo, median of 10 runs per scenario and per profile)

| Scenario | Classic | PQC | Hybrid | Δ PQC−Classic | Δ Hybrid−Classic | Δ Hybrid−PQC |
|---|---:|---:|---:|---:|---:|---:|
| 0 ms | 2.891,26 ms | 9.586,39 ms | 10.269,73 ms | +6.695,14 ms (+231,56%) | +7.378,47 ms (+255,20%) | +683,34 ms (+7,13%) |
| 14 ms | 4.693,21 ms | 11.152,92 ms | 12.275,20 ms | +6.459,71 ms (+137,64%) | +7.581,99 ms (+161,55%) | +1.122,28 ms (+10,06%) |
| 30 ms | 7.176,65 ms | 13.345,81 ms | 14.492,22 ms | +6.169,17 ms (+85,96%) | +7.315,57 ms (+101,94%) | +1.146,40 ms (+8,59%) |
| 140 ms | 24.859,26 ms | 30.107,49 ms | 32.358,19 ms | +5.248,23 ms (+21,11%) | +7.498,93 ms (+30,17%) | +2.250,70 ms (+7,48%) |
| 225 ms | 38.481,78 ms | 44.327,57 ms | 46.416,61 ms | +5.845,79 ms (+15,19%) | +7.934,83 ms (+20,62%) | +2.089,04 ms (+4,71%) |
| 320 ms | 53.669,58 ms | 59.569,22 ms | 61.437,57 ms | +5.899,64 ms (+10,99%) | +7.767,99 ms (+14,47%) | +1.868,35 ms (+3,14%) |

**The post-quantum cost is fixed per flow and does not grow with the network.** The absolute difference from Classic stays practically constant across all scenarios: between 5,2 and 6,7 s in PQC and between 7,3 and 7,9 s in Hybrid, from 0 to 320 ms. Larger handshakes and tokens, therefore, do not generate additional network round trips: the migration's cost is in processing, not in transport.

**The consequence is a dilution of the relative cost.** With 28 calls, each subject to the same delay, the total time comes to be dominated by network round trips as latency grows. A fixed cost weighs less and less on an ever-larger total: PQC goes from 3,32× Classic at 0 ms to 1,11× at 320 ms, and Hybrid, from 3,55× to 1,14×.

**The order among the profiles holds under every condition.** In all six scenarios, the medians follow the order Classic < PQC < Hybrid. Between Classic and PQC, the distributions don't overlap: no PQC run is faster than the slowest Classic run. Hybrid's increase over PQC ranges from 3,1% to 10,1%, which confirms, in time as well, that hybrid protection costs little beyond the post-quantum migration itself.

## References

- Bindel, N., Herath, U., McKague, M., & Stebila, D. (2017). *Transitioning to a Quantum-Resistant Public Key Infrastructure.* PQCrypto 2017.
- Bindel, N., Braun, J., Gladiator, L., Stebila, D., & Wiggers, T. (2019). *X.509-Compliant Hybrid Certificates for the Post-Quantum Transition.* Journal of Open Source Software, 4(40), 1606.
- Schardong et al. (2022), Eq. 3.1 (original flow-size equation).
- NIST FIPS 203 (ML-KEM) and FIPS 204 (ML-DSA).
