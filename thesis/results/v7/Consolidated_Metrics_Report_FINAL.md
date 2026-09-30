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
| HTTP requests | 42 | distributed across two sub-flows; includes 14 login/consent interaction requests (redirect hops) found during external review and now tracked (Decision 12) |
| mTLS connections | 6 | three connection pools per sub-flow (AS/API, Directory, and login), each reused by every call in its pool |
| JWTs transferred | 28 | includes 2 JARM tokens per flow, found during external review (Decision 11) |
| JWKS fetches | 2 | one per sub-flow |
| CA certificate fetches | 4 | root and issuer, in each sub-flow |

Since this structure does not change between profiles, every measured difference comes from the cryptography used in each one.

### 1.2. The three profiles

| Profile | Signatures | TLS key exchange |
|---|---|---|
| Classic | RSA (PS256) | ECDHE, single P-384 curve |
| PQC | Pure ML-DSA-65 (NIST FIPS 204) throughout: tokens, subject keys, and every certificate's own issuer signature (client, server, and CA certificates alike) | Pure ML-KEM-1024 (NIST FIPS 203) |
| Hybrid | RSA and ML-DSA-65 combined: certificates with a dual signature in non-critical X.509 extensions; payload extension on the RS's JWTs, on the `client_assertion`, and on the PAR object; Strong Nesting on the `id_token` and on the JARM | SecP384r1MLKEM1024 (P-384 + ML-KEM-1024) |

Three design properties ensure the comparisons are fair:

- **Symmetric chain in the key exchange.** Hybrid combines exactly Classic's curve (P-384) and PQC's parameter (ML-KEM-1024). Hybrid's cost can therefore be read relative to its two components.
- **A single group per profile, with no fallback.** Each profile negotiates only its own key-exchange group; if the server doesn't offer it, the connection fails, instead of silently falling back to another group.
- **Same RSA key size.** In both Classic and Hybrid, the RSA component of the JWT signatures uses a key of the same size; the difference between the two profiles comes only from the post-quantum material.

**On the specific parameters chosen (P-384, ML-KEM-1024, ML-DSA-65).** P-384 and ML-DSA-65 both sit at NIST security category 3 (roughly AES-192-equivalent), so the signature migration is a level-for-level swap. ML-KEM-1024, however, is category 5 (roughly AES-256-equivalent) -- one level above the signature scheme it's paired with in Hybrid, not a matched pair. This is a deliberate asymmetry, not an oversight: a signature forgery requires an active, real-time attack against a still-viable scheme, while a key exchange captured today can be decrypted retroactively the moment a sufficiently large quantum computer exists ("harvest now, decrypt later") -- a risk with no expiration date, which is why deployment guidance for the KEM side of a migration commonly favors the highest available parameter set independent of what the signature scheme uses. "Symmetric," in this report's usage, refers to Hybrid combining Classic's and PQC's own already-established parameters unchanged (not degrading either to accommodate the other), not to the two schemes sharing the same NIST category.

**The PQC profile is now post-quantum end-to-end, with no remaining classical component in its certificate chain.** Through v7's original collection, PQC's CA and live-handshake certificates (client_one_pqc.crt, the server certificates, and the root_ca_pqc/issuer_ca_pqc download artifacts) carried an ML-DSA-65 subject key but a classical RSA issuer signature -- flagged by external review as making the profile "not post-quantum end-to-end" (thesis/results/v7/DECISIONS.md). Decision 14 closes this: root_ca_pqc.crt is now self-signed with its own ML-DSA-65 key, issuer_ca_pqc.crt is signed by that same root, and client_one_pqc.crt/mtls_pqc.crt/op_pqc.crt are all signed directly by it too -- every certificate the PQC profile presents, in every direction, is ML-DSA-65 both as a subject key and as an issuer signature. This is a scope revision, not an inconsistency: this thesis's own SAD models the migration in three phases, and PQC pure corresponds to Phase 3, the ecosystem's final state, once every participant has migrated -- by definition, it preserves no classical component anywhere. Backward compatibility is Hybrid's responsibility alone (Phase 2, the transition profile); PQC no longer needs to carry any. Counterintuitively, this makes PQC's certificates and handshake larger than Hybrid's, not smaller: Hybrid reuses Classic's compact RSA structure as a base and appends ML-DSA-65 material as an incremental extension, while PQC's certificates have no compact classical structure left to build on -- the subject key and the issuer signature are both full-size ML-DSA-65 material, with nothing smaller underneath. The profile that carries the least cryptographic diversity ends up carrying the most bytes (Section 2, mTLS handshake and Section 3.5).

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
| OPINsize (bytes) | 76.929 | 322.895 | 350.477 | Total cryptographic-material cost of the complete flow, by this thesis's equation (Section 3): N_mTLS × handshake_bytes + N_JWT × JWT_size + N_JWK × JWK_PK_size + N_PKI × PKI_bytes. PQC is **4.20× Classic** (+319.73%); Hybrid is **4.56× Classic** (+355.59%) and **1.09× PQC** (+8.54%). With the PQC profile's certificate chain now fully post-quantum end-to-end (Decision 14), PQC alone already captures 89.9% of Hybrid's total increase over Classic -- Hybrid's own remaining premium over PQC is small, the cost of also carrying a classical signature for backward compatibility, not of the post-quantum material itself. |
| **mTLS handshake** | | | | |
| mTLS handshake: bytes (P50) | 5.119 | 22.607 | 18.023 | Size of each mTLS handshake, in bytes (P50 of the 6 connections). Classic and Hybrid: over 60 runs per profile (6 scenarios × 10), 0.00% spread. PQC: re-measured with a single live capture after Decision 14 (deterministic metric, same justification as Decision 10) -- superseding the original 60-run figure, which reflected the pre-Decision-14 classically-signed client certificate. PQC is 4.42× Classic (+341.63%); Hybrid is 3.52× Classic (+252.08%) and **0.80× PQC (-20.28%)**. PQC's handshake is now the largest of the three: its client certificate carries a full ML-DSA-65 signature from its issuer with no reuse of any smaller classical structure, while Hybrid's primary certificate stays RSA-sized and only bolts on the post-quantum material as incremental extensions. |
| **Cryptographic artifacts** | | | | |
| Average JWT (bytes) | 1.330,82 | 5.404,32 | 7.163,11 | Average size of the JWTs (header + payload + signature) over the flow's 28 tokens, a number equal across all three profiles. Includes the 2 JARM (FAPI Advanced authorization response) tokens per profile, found during external review and fixed at the source (Decision 11): the flow's automated login/consent simulation issued and transmitted these tokens without routing them through the byte- and JWT-accounting path, so the original 26-token figure undercounted them. PQC is 4.06× Classic (+306.09%); Hybrid is 5.38× Classic (+438.25%) and 1.33× PQC (+32.54%). The ML-DSA-65 signature (3.309 bytes) replaces PS256 (256 bytes) in PQC; in Hybrid, both coexist in the same token, either via payload extension (RS256 + ML-DSA-65) or via Strong Nesting (PS256 + ML-DSA-65), depending on the artifact. This is not an inconsistency: RS256, not PS256, is used specifically for the client-signed payload-extension artifacts (`client_assertion`, the PAR request object) because that scheme's whole point is producing an entirely ordinary classical JWT a legacy, PQC-unaware verifier can check without modification -- RS256 is the more universally-supported classical scheme for that purpose. PS256 remains the algorithm for every AS/RS-issued token (`id_token`, access tokens, RS query responses, the JARM), which use Strong Nesting instead, since those artifacts aren't constrained by a legacy-verifier compatibility requirement. |
| Client certificate (DER bytes) | 1.494 | 5.879 | 6.859 | Size of the test client's certificate, presented on the mTLS connection. PQC is 3.94× Classic (+293.51%); Hybrid is 4.59× Classic (+359.10%) and 1.17× PQC (+16.67%). Since Decision 14, PQC's certificate is signed by a genuinely self-contained ML-DSA-65 CA (root_ca_pqc), not the classical CA -- both its subject key and its issuer signature are now ML-DSA-65, closing the external review's "not end-to-end post-quantum" finding for this artifact. The hybrid certificate reuses Classic's RSA key and adds, in three non-critical X.509 extensions (Bindel et al., 2019), the ML-DSA-65 public key and an alternate ML-DSA-65 signature from the CA; it stays slightly larger than PQC's because it still carries the full RSA structure on top of the post-quantum material, not instead of it. |
| JWK_PK_size: AS public key (bytes) | 256 (RSA-2048) | 1.952 (ML-DSA-65) | 2.208 (composite, `kty: HYBRID`) | Size of the AS's public key published at `/jwks`, used to verify the tokens. PQC is 7.62× Classic (+662.50%); Hybrid is 8.62× Classic (+762.50%) and 1.13× PQC (+13.11%). Since N_JWK is the same (2) across all three profiles, the growth comes only from the key's size; in Hybrid, a composite key carrying the RSA half and the ML-DSA-65 half (256 + 1.952 bytes). |
| Average PKI_bytes: CA certificate (bytes, PEM body) | 2.110 | 8.007 | 9.339 | Average size of the two CA certificates (root and issuer) in the format they're transferred in (PEM), without HTTP framing. PQC is 3.79× Classic (+279.48%); Hybrid is 4.43× Classic (+342.61%) and 1.17× PQC (+16.64%). Since Decision 14, PQC's CA certificates carry a genuine ML-DSA-65 signature -- root_ca_pqc.crt is self-signed, issuer_ca_pqc.crt is signed by root_ca_pqc's own key -- not an RSA one; the remaining gap to Hybrid is the cost of Hybrid's CA certificates carrying both an RSA and an ML-DSA-65 signature, where PQC's carry only the latter. |
| **Bytes per participant** (application layer; each server's outbound, or egress, values) | | | | |
| Authorization Server (AS) | 68.325 | 100.009 | 102.901 | AS outbound volume: consent, PAR, tokens, JWKS, plus the login/consent interaction and the JARM response, found missing from every byte total during external review and corrected here (Decision 12; see also Decision 11 for the related JWT/OPINsize fix). Most of this total is the static login/consent HTML pages the automated interaction exchanges with the AS -- a profile-independent cost -- with only the JARM token and the JWTs already counted elsewhere actually scaling with the crypto scheme. PQC is 1.46× Classic (+46.37%); Hybrid is 1.51× Classic (+50.61%) and 1.03× PQC (+2.89%). The relative growth is far smaller than the RS's specifically because most of this total no longer varies with the profile; before this correction, this row only reflected the AS's signed artifacts and understated its true outbound volume by not counting the login/consent traffic at all. |
| Resource Server (RS) | 26.034 | 91.252 | 121.196 | RS outbound volume (basic-data, claim, policy, and premium queries). PQC is 3.51× Classic (+250.51%); Hybrid is 4.66× Classic (+365.53%) and 1.33× PQC (+32.81%). It's the largest absolute increase among the participants (+95.162 bytes from Classic to Hybrid), because every query response is a JWT signed by the RS. Of the servers' total outbound traffic (AS+RS, corrected per Decision 12), the RS accounts for 27.6% in Classic, 47.7% in PQC, and 54.1% in Hybrid: once the AS's own login/consent and JARM traffic is properly counted, the AS is actually the larger contributor in Classic and PQC, and the two are close to parity in Hybrid -- the earlier "RS weighs most on the cloud egress bill" reading was an artifact of the AS's undercount, not a real property of the flow. |
| Directory/PKI (CA certificates, full HTTP response) | 8.852 | 32.440 | 37.768 | Directory outbound volume when serving the CA certificates: certificate body + 103-byte HTTP framing per response, identical across all three profiles. This constant value confirms, byte for byte, that the body served is exactly the file used in the PKI_bytes calculation. PQC is 3.66× Classic (+266.47%); Hybrid is 4.27× Classic (+326.66%) and 1.16× PQC (+16.42%). |
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
| N_JWT: tokens in the flow | 28 | 28 | 28 | Number of JWTs transferred, including the 2 JARM tokens per flow (Decision 11). Equal across all three profiles. |
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
| handshake_bytes | Size of the mTLS handshake (P50) | 5.119 bytes | 22.607 bytes | 18.023 bytes |
| N_JWT | Number of JWT tokens in the flow | 28 | 28 | 28 |
| JWT_size | Average size of each JWT | 1.330,82 bytes | 5.404,32 bytes | 7.163,11 bytes |
| N_JWK | Number of calls to `/jwks` | 2 | 2 | 2 |
| JWK_PK_size | Size of the AS's public key | 256 bytes | 1.952 bytes | 2.208 bytes |
| N_PKI | Number of CA certificate fetches | 4 | 4 | 4 |
| PKI_bytes | Average size of the CA certificate (PEM) | 2.110 bytes | 8.007 bytes | 9.339 bytes |

### 3.2 Classic scenario calculation

```
OPINsize = (6 × 5.119) + (28 × 1.330,82) + (2 × 256) + (4 × 2.110)
6 × 5.119     = 30.714 bytes
28 × 1.330,82 = 37.263 bytes
2 × 256       =    512 bytes
4 × 2.110     =  8.440 bytes
OPINsize = 30.714 + 37.263 + 512 + 8.440 = 76.929 bytes
```

### 3.3 PQC scenario calculation

```
OPINsize = (6 × 22.607) + (28 × 5.404,32) + (2 × 1.952) + (4 × 8.007)
6 × 22.607     = 135.642 bytes
28 × 5.404,32  = 151.321 bytes
2 × 1.952      =   3.904 bytes
4 × 8.007      =  32.028 bytes
OPINsize = 135.642 + 151.321 + 3.904 + 32.028 = 322.895 bytes
```

### 3.4 Hybrid scenario calculation

```
OPINsize = (6 × 18.023) + (28 × 7.163,11) + (2 × 2.208) + (4 × 9.339)
6 × 18.023     = 108.138 bytes
28 × 7.163,11  = 200.567 bytes
2 × 2.208      =   4.416 bytes
4 × 9.339      =  37.356 bytes
OPINsize = 108.138 + 200.567 + 4.416 + 37.356 = 350.477 bytes
```

### 3.5 Comparison across profiles

| Ratio | OPINsize |
|---|---:|
| PQC / Classic | 4,20× (+319,73%) |
| Hybrid / Classic | 4,56× (+355,59%) |
| Hybrid / PQC | 1,09× (+8,54%) |

Migrating the OPIN consent flow to post-quantum cryptography multiplies the volume of cryptographic material transferred by 4,20 in PQC and by 4,56 in Hybrid: each complete flow goes from 76,9 kB to 322,9 kB and 350,5 kB, respectively. This growth requires no change to the flow's structure: the number of connections, tokens, key fetches, and certificates is the same across all three profiles; only the size of each artifact grows. This is narrower than saying the migration leaves the ecosystem's specifications untouched -- it does not. Carrying this material requires the specification to be extended: new JOSE algorithm identifiers (`ML-DSA-65`, the composite `MLDSA65-RSA2048-PSS-SHA256`), a JWK type the JOSE registry has no entry for (`kty: HYBRID`), and non-critical X.509 extensions to carry a second public key and signature on hybrid certificates. What doesn't change is the flow's call sequence and round-trip count; what does change, and would need standardization work before real adoption, is the wire format of several artifacts. Its byte cost, at least, can be estimated before that work happens.

Most of this cost lies in the jump from Classic, not in the choice between PQC and Hybrid. Of Hybrid's total increase over Classic, 89,9% already shows up in pure PQC. Hybrid's additional guarantee — that it remains secure even if only one of the two algorithms is broken — costs only 8,5% more than PQC, now that PQC's own certificate chain is fully post-quantum (Decision 14): almost the entire byte cost of leaving classical cryptography is already paid by PQC alone, and Hybrid's marginal premium is close to what a second, additive signature scheme should cost, not a sign that Hybrid is a materially heavier profile. This is visible directly at the handshake layer: PQC's own mTLS handshake (22.607 bytes) is now larger than Hybrid's (18.023 bytes), even though Hybrid carries two signature algorithms and PQC carries one. The reason is structural, not a measurement artifact: Hybrid's certificate reuses Classic's RSA structure and adds ML-DSA-65 as an incremental extension, so it inherits RSA's comparatively compact key and signature sizes for half of its material; PQC has no classical structure left to reuse -- every key and every signature in its chain is full-size ML-DSA-65. The profile with the fewest algorithms in play is not necessarily the profile with the fewest bytes.

The PKI term, absent from the original equation, accounts for 10,97% of OPINsize in Classic, 9,92% in PQC, and 10,66% in Hybrid -- comparable across all three now that PQC's own CA certificates are ML-DSA-65-signed. In every profile it outweighs the public-key (JWK) term, which the original equation already included. A migration plan based only on handshake, tokens, and keys underestimates the real cost: the Hybrid/PQC gap widens from 7,65% to 8,54% once the term is included, a small effect now that PQC pays a comparable PKI cost to the other two profiles, rather than the large widening (22,87% → 29,30%) this term produced before PQC's chain was made fully post-quantum. Since the measured flow downloads the CA certificates without caching, these values represent the worst case; the N_PKI parameter allows the estimate to be adjusted to each participant's actual behavior.

## 4. Flow Latency Under Different Network Scenarios

The per-endpoint latencies in Section 2 were measured at the 0 ms scenario, with no emulated network delay, to locate where in the flow the post-quantum processing cost shows up. This section answers a complementary question: how does the complete consent flow (the 42 calls, across the two sub-flows -- see Decision 12) behave under different network conditions?

The six scenarios (0, 14, 30, 140, 225, and 320 ms, emulated with `tc`/`netem` at the gateway) reproduce the latency values measured empirically across five AWS geographic regions by Schardong et al. (2022). The two sections complement each other: Section 2 offers a granular, per-component view; this one, an aggregated view, per network condition.

**This dataset was re-collected under the persistent-signer architecture (Decision 13) and supersedes every earlier version of this section.** The original v7 latency runs measured a Python process spawning a fresh Docker container to perform each ML-DSA-65 signature -- roughly 1.25s of container-startup overhead per signing call, 8 calls per flow, contaminating every PQC/Hybrid measurement by some 6-10s regardless of network condition. That architecture was already fixed in code before this report's first draft, but the latency dataset itself was not re-collected until an external technical review raised the resulting numbers as implausible. It was: see Decision 13 for the full before/after and the corrected statistical conclusions below.

### Total flow latency (T_fluxo, median of 10 runs per scenario and per profile)

| Scenario | Classic | PQC | Hybrid |
|---|---:|---:|---:|
| 0 ms | 2.613,98 ms | 2.710,39 ms | 2.777,12 ms |
| 14 ms | 4.992,25 ms | 4.996,41 ms | 5.545,71 ms |
| 30 ms | 7.930,67 ms | 7.947,35 ms | 8.356,60 ms |
| 140 ms | 27.856,77 ms | 28.188,37 ms | 29.195,10 ms |
| 225 ms | 43.384,19 ms | 43.699,64 ms | 45.056,78 ms |
| 320 ms | 60.852,74 ms | 61.123,44 ms | 63.397,11 ms |

With the container-spawn artifact removed, PQC's own signing/verification overhead sits in the range of a few hundred milliseconds spread across the flow's 8 signing calls, not the several-second gap the earlier, container-spawn-contaminated dataset showed -- that earlier "non-overlapping distributions at every scenario" claim was itself an artifact of that overhead, and is superseded by the results below, not quietly dropped. PQC is higher than Classic at every scenario tested, though the gap is smallest at 14 ms (+4 ms) and 30 ms (+17 ms), a bit larger at 0 ms (+96 ms), and settles at roughly 270-330 ms from 140 ms onward.

Hybrid is reliably slower than PQC at every scenario. Unlike the Classic/PQC comparison, Hybrid's extra cost over PQC (doing both a classical and a post-quantum signature/verification) is statistically significant in all six scenarios (p < 0,001 throughout), and the PQC/Hybrid run ranges stop overlapping from 14 ms onward. The relative gap itself, however, is not monotonic: it starts small at 0 ms (+2,46%), peaks at 14 ms (+10,99%), falls to +5,15% at 30 ms, and then settles in a narrow band of +3,1% to +3,7% from 140 ms through 320 ms. From 140 ms onward, this is consistent with dilution -- a roughly fixed processing cost shrinking against a growing, delay-dominated total. Below 140 ms, the exact magnitude of the gap is more sensitive to scenario-to-scenario timing variation, which is expected: total flow time aggregates 42 sequential network round trips, so small per-call fluctuations compound into a percentage that moves more than the underlying processing cost does. The result that holds robustly across every scenario, and is the one this report relies on, is the ordering itself: Classic < PQC < Hybrid, without exception, at every one of the six network conditions tested.

### Where the flow's time actually goes

This section responds to two of the external review's recommendations: decomposing T_fluxo into its components (Recommendation 3) and explaining the flow's effective round-trip count (Recommendation 4). The decomposition draws entirely on data already collected for other purposes in this report. The round-trip explanation required two further, narrowly targeted live measurements beyond that -- a single-flow capture of the gateway's own access log (all three profiles, 0 ms) and a raw packet capture (Classic, 0 ms and 320 ms) -- both one-off, structural measurements of a deterministic mechanism, not a new statistical sample; neither changes any number already published elsewhere in this report.

**Methodological note.** The breakdown below uses `handshake_ms`/`opin_processing_ms`, fields the gateway records during the *size* batch (`thesis/results/v7/size/`), not the *latency* batch that produced the official T_fluxo table above. Both batches run under the same persistent-signer architecture (Decision 13), so the proportions below are representative -- but they come from a separate set of runs, not the exact executions T_fluxo was measured from. handshake_ms and opin_processing_ms are time metrics, not deterministic like size; the residual above therefore also absorbs any run-to-run timing variation between the two batches, not just genuine client/network/wait time. Treat this as a decomposition of the flow's structure, not a re-derivation of the published T_fluxo values themselves.

| Scenario | Profile | mTLS handshake (6 conn.) | Server processing (42 calls) | Residual (client + network + wait) |
|---|---|---:|---:|---:|
| 0 ms | Classic | 104,04 ms (4,0%) | 459,90 ms (17,6%) | 2.050,04 ms (78,4%) |
| 0 ms | PQC | 70,02 ms (2,6%) | 822,36 ms (30,3%) | 1.818,01 ms (67,1%) |
| 0 ms | Hybrid | 135,00 ms (4,9%) | 1.085,28 ms (39,1%) | 1.556,84 ms (56,1%) |
| 320 ms | Classic | 2.010,54 ms (3,3%) | 26.723,34 ms (43,9%) | 32.118,86 ms (52,8%) |
| 320 ms | PQC | 1.953,54 ms (3,2%) | 27.328,14 ms (44,7%) | 31.841,76 ms (52,1%) |
| 320 ms | Hybrid | 2.005,02 ms (3,2%) | 28.719,60 ms (45,3%) | 32.672,49 ms (51,5%) |

At 0 ms, most of T_fluxo is neither handshake nor server processing -- it's client-side and wait time, consistent with the external review's own suspicion (item 4.1) that a large share of the flow's cost sits outside the servers. At 320 ms, that residual share converges to roughly 52% across all three profiles, once network delay dominates the total.

**Isolated signing cost, for context.** A direct microbenchmark of the exact private-key operation TLS's `CertificateVerify` step performs (Go 1.27rc2's own `crypto` stdlib and `mldsa` package, same environment this project's tooling uses) measured RSA-4096 PSS at 6,624 ms per signature versus ML-DSA-65 at 0,713 ms -- both sub-hundredth-of-a-second, and ML-DSA-65 faster, not slower, than its classical counterpart in this implementation (thesis/results/v2/experiment2 - PQC/DECISIONS.md, Decision 11). This confirms the external review's own expectation that optimized sign/verify operations cost fractions of a millisecond. It also means the "server processing" column above -- tens to hundreds of milliseconds per call in this project's actual Java-based AS/RS -- is not explained by the cost of the cryptographic operation itself; most of it is framework, serialization, and I/O overhead unrelated to which signature scheme is in use. (This benchmark used a different language/library pair -- Go's stdlib, not the AS/RS's own Nimbus/BouncyCastle -- so it is cited as a reference for what an optimized implementation costs, not as a direct measurement of this project's own signing calls.)

**Explaining the round-trip count.** Dividing each scenario's T_fluxo increase by its emulated delay -- the external review's own method -- implies roughly 129-159 round trips using the original (pre-Decision-13) latency data, or 170-182 using the corrected data; the documented flow makes 42 real HTTP requests (Decision 12). Two mechanisms, both verified directly (application-layer logs, then raw packet capture), account for this:

*Doubled delay on proxied requests.* `tc`/`netem` delays *every* outbound packet from the gateway's network interface, not just responses to the client -- this includes the gateway's own internal proxy calls to the AS/RS backends. A proxied request therefore pays the emulated delay twice (once forwarding to the backend, once returning to the client), not once. Confirmed quantitatively: `opin_processing_ms`'s increase from 0 ms to 320 ms, divided across the flow's 42 requests, averages 625-658 ms per request across the three profiles, matching 2×320 ms (640 ms) within 2-3%.

*A real, previously uncounted internal channel.* The AS backend makes its own mTLS calls back through the same gateway to validate consent with the RS (`InsurerAdapter.getConsent()`, already noted in `mock_mtls/main.go`'s own comments) -- traffic invisible to the client-side request count entirely, using its own connections and its own classical curve, independent of `CRYPTO_PROFILE`. A live capture of the gateway's own access log during one full flow (all three profiles, 0 ms) found this channel adds 7 further requests and 7 further connections, identical in every profile -- confirmed via the gateway's own `requests_logged` counter, not inferred.

*mTLS handshake establishment costs two round trips, not one -- a structural finding, not specific to this review.* Raw packet capture (tcpdump, one full flow per scenario at 0 ms and 320 ms, Classic) traced all 7 client-facing connections and found an identical pattern in every one: the TCP three-way handshake completes one delay unit in (SYN at t=0, SYN-ACK at t=0.320s), and the TLS 1.3 handshake's server flight (ServerHello, Certificate, Finished) arrives a full second delay unit later (t≈0.641-0.646s) -- only after that does the client send its first application request, immediately and without further wait. Establishing one mutually-authenticated mTLS connection under this architecture therefore costs two round-trip-equivalent delay units, not the one this report's earlier models assumed. This is a property of the TCP+TLS 1.3 handshake sequence itself, not an artifact of this specific test environment, and is stated here as a general finding about mutually-authenticated TLS 1.3 connection costs under added latency, independent of the external review that prompted looking for it.

Recomputing the mechanical estimate with both corrections (42 requests, 38 proxied at 2 units and 4 served directly at 1 unit; 7 handshakes at 2 units each; plus the internal channel's own 7 proxied requests and 7 handshakes on the same terms) gives 94 + 28 = **122 delay-equivalent units** per flow. Against the external review's own most conservative estimate (129, from the 14 ms scenario), this is a 94.6% match. The review's own method produced different figures at different scenarios from the same underlying approach (129, 143, and 159 at 14, 30, and 320 ms respectively) -- a spread of 23% across scenarios that never claimed to measure a scenario-dependent quantity, which points to inherent imprecision in a method that infers a structural count from a noisy timing ratio, not to additional structure this report failed to find. This is reported as a structural mechanism fully identified and quantified, matched with 94.6% precision against the review's most conservative figure -- not as a claim that every unit of every scenario's estimate has been individually traced.

**A related observation on TCP fragmentation (external review item 4.4), not a resolution of it.** The same packet captures show that even Classic's modest response sizes (e.g., the ~2.95 kB JWKS response) arrive fragmented across 2-3 TCP segments rather than one. This is consistent with the review's own concern that larger handshakes and tokens could exceed an initial TCP congestion window and cost additional round trips -- worth flagging as a promising direction for the review's own Recommendation 5 (bandwidth/MTU-limited re-testing). It is not evidence that this happens under PQC or Hybrid's larger payloads specifically, nor under a bandwidth-constrained link: neither was tested in this capture, which used only Classic at full emulated bandwidth. Recorded here as a lead for future work, not as this item's resolution.

## References

- Bindel, N., Herath, U., McKague, M., & Stebila, D. (2017). *Transitioning to a Quantum-Resistant Public Key Infrastructure.* PQCrypto 2017.
- Bindel, N., Braun, J., Gladiator, L., Stebila, D., & Wiggers, T. (2019). *X.509-Compliant Hybrid Certificates for the Post-Quantum Transition.* Journal of Open Source Software, 4(40), 1606.
- Schardong et al. (2022), Eq. 3.1 (original flow-size equation).
- NIST FIPS 203 (ML-KEM) and FIPS 204 (ML-DSA).
