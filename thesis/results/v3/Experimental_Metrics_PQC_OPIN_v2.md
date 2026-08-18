Experimental Metrics — Comparative Results

Experiment 1 (Classic) versus Experiment 2 (PQC)

Luciano Figueiredo Coelho   |   PPGCC/LabSEC/UFSC

1. Objective

This document presents the comparative results of the thesis's Experiments 1 and 2, organized by the metrics jointly defined in the last advisory meeting. Experiment 1 measured the cost of the OPIN consent flow with classical cryptography (PS256/RSA). Experiment 2 measured the same flow with pure post-quantum cryptography (ML-DSA-65), fully replacing the classical algorithms. The comparison between the two experiments establishes the two reference points for Experiment 3 (hybrid), which is the thesis's central contribution.

The three blocks below organize the metrics by analysis dimension: byte-level traffic cost, per-endpoint latency cost, and OPINsize Equation parameters. A fourth block describes the architectural foundation already built for Experiment 3.

2. Block A — Traffic Cost

Traffic metrics measure the size of the data that flows through the complete consent flow. These are the parameters that feed directly into the OPINsize Equation and that determine the migration's impact on the ecosystem participants' cloud infrastructure cost.

This document presents two different numbers both called "OPINsize," and it is important not to confuse them: the analytical OPINsize (95,232 bytes classic / 264,374 bytes PQC, 2.78x growth, Block C) and the empirical OPINsize per participant (~67,604 bytes classic / ~184,637 bytes PQC, 2.73x growth, table below). The two coexist because they answer different, complementary questions, not because one of them is wrong.

The analytical OPINsize includes the mTLS handshake cost, calculated via an equation (Equation 3.1 from Schardong et al., 2022). It is the figure comparable with the literature and answers the thesis's central question: how much does a complete end-to-end OPIN consent cost?

The empirical OPINsize per participant measures only the bytes that flow at the HTTP application layer — after the TLS tunnel is already established. It is the sum of what each participant (AS, RS, PKI/CRL, Directory) actually moved. It answers the advisor's operational question: how much does it add to each ecosystem participant's cloud bill?

The sum across participants reconciles with the empirical value, not the analytical one, because participants only see the application layer — the mTLS handshake happens one layer below, invisible to them.

3. Block B — Latency Cost

Block A showed that the flow becomes 2.73 times heavier in bytes with PQC. But bigger bytes don't necessarily mean a slower application — that depends on how much time the server spends processing each cryptographic operation.

Block B answers this second question: besides heavier, does the flow also become slower? And how much slower at each specific point in the flow?

To answer precisely, all measurements in this block were taken in the zero-network scenario — all services running on the same machine with no artificial network delay. Any time difference between the two experiments in this scenario is attributable exclusively to the cryptographic algorithm, not to network speed. P50 was used as the reference since it represents the system's median behavior.

Because most of these endpoints only have 2 to 4 samples within a single 0ms run, a single run's P50 is statistically fragile — an early pass over this data showed the effect's direction flipping (PQC appearing faster than classic) on 4 of the 5 endpoints below, purely from single-run sampling noise. To resolve this, the 0ms scenario was independently re-run 5 times per experiment (10 full flow executions total), each a freshly isolated process, and the value reported for every endpoint below is the **median of those 5 runs' P50s** — not a single run's figure. The full 5-round table backing this is at the end of this block.

The combination of the two blocks — heavier and slower — is the complete empirical argument that the PQC migration has a real, measurable cost along two independent dimensions: network infrastructure and processing capacity. This is what underpins the proposal of the hybrid scheme as a gradual transition solution — allowing each participant to migrate at the pace their infrastructure can support.

Latency scales proportionally with the network across all scenarios (0ms, 14ms, 30ms, 140ms, 225ms, 320ms) for both experiments — the absolute processing difference between classic and PQC becomes statistically indistinguishable from network noise at high-latency scenarios, given the limited number of samples per scenario (n=4 for /token). At high-latency scenarios (320ms), PQC's computational overhead is diluted by transmission latency and becomes proportionally smaller.

4. Block C — OPINsize Equation Parameters

This thesis's OPINsize Equation (equivalent to Equation 3.1 from Schardong et al., 2022) calculates the flow's total analytical cost as a function of its measurable parameters. The table below presents the empirical values of each parameter in both experiments.

With Experiment 1's real parameters (constant N_mTLS of 6 connections and handshake P50 of 9,785 bytes, both identical across all 6 scenarios): classic OPINsize = 6 × 9,785 + 26 × 1,385 + 2 × 256 = 58,710 + 36,010 + 512 = 95,232 bytes.

With Experiment 2's real parameters (constant N_mTLS of 6 connections across all scenarios): PQC OPINsize = 6 × 19,756 + 26 × 5,459 + 2 × 1,952 = 118,536 + 141,934 + 3,904 = 264,374 bytes.

Analytical growth: 264,374 / 95,232 = 2.78x. This is the overhead of the pure PQC migration as measured by the analytical equation, using the experiments' empirical parameters.

**Note — the N_mTLS correction revealed that the previous analytical value was distorted, and it now converges with the empirical one.** Until this update, classic N_mTLS was measured as an average (~9 to 16 connections, average ≈ 11) because `opin_flow.py` opened a real operating-system browser for the manual login step, and that browser attempted its own mTLS connections against the gateway — attempts that were never actually part of the consent flow itself, and whose success or failure depended on non-deterministic race conditions in the browser (see DECISIONS.md, Decision 13). After fully automating the login (removing the browser and the manual wait), N_mTLS dropped to a constant value of 6 connections in both experiments, and the classic side's handshake_bytes P50 also stabilized at 9,785 bytes across all 6 scenarios — no longer needing the average excluding the 0ms scenario, as the previous version of this document did. The net effect is that the classic analytical OPINsize dropped from 151,120 to 95,232 bytes, and analytical growth rose from 1.75x to 2.78x — much closer to the empirical growth already recorded in Block A (2.73x). This convergence between two independent measurement methods, the analytical equation (which includes the mTLS handshake cost) and the empirical per-participant sum (which measures only the application layer), is evidence of internal consistency: the old figure (1.75x) was distorted by browser noise, the new one (2.78x) is not.

5. Architectural Foundation for Experiment 3

Experiment 3 does not start from scratch — it reuses all the infrastructure already validated in Experiments 1 and 2. The same automation script, the same Go mTLS gateway, and the same PQC certificates we already know how to generate, including the local simulation of the CA certificate chain. None of this needs to be rebuilt — it needs to be extended.

The central difference lies in the signing logic. In Experiments 1 and 2, the Authorization Server and the Resource Server each choose a single algorithm at a time, controlled by a configuration variable — either PS256 or ML-DSA-65. In Experiment 3, every JWT needs to carry both signatures simultaneously, and the certificate used in the mTLS handshake also needs to present both signatures at the same time, not one or the other.

This means the cryptographic-profile architecture needs to evolve: instead of selecting a single profile, the system needs to combine two. A new hybrid profile would activate this dual-signing logic in the AS and the RS, and the client's and gateway's certificates would need to be generated with both simultaneous signatures.

The metrics to be collected in Experiment 3 are exactly the same ones already defined and validated in Experiments 1 and 2: OPINsize, mTLS handshake size, average JWT size, bytes per participant, and per-endpoint latency. No new metric needs to be created — the same collection and analysis pipeline that already produced this document's results will be fully reused, now over the new hybrid architecture.

6. Methodological Notes

Experiments 1 and 2 were both run with the same automation script (opin_flow.py), covering 28 HTTP calls across the two test plans (consents_v3 and person_v2) in 6 latency scenarios each (0ms, 14ms, 30ms, 140ms, 225ms, and 320ms via tc/netem on the gateway container). All modules finished with a PASSED result across all 12 scenarios.

mTLS handshake metrics were filtered by client_cert_bytes to isolate the automation script's traffic from the Authorization Server's internal traffic, which uses a separate, always-classical transport certificate.

The preflight modules were excluded because they always finish with a FAILED result due to their dependency on Raidiam's real Directory, unavailable in a local environment.

The Resource Server (Data Server) only reads CRYPTO_PROFILE at boot — every profile switch between experiments required recreating the auth, mtls, mongo_seed, and mockapi containers simultaneously to guarantee full environment synchronization. This is documented in thesis/results/v3/DECISIONS.md.

| Metric | Classic (Exp 1) | Pure PQC (Exp 2) | Growth | What this means |
|---|---|---|---|---|
| Total OPINsize (bytes) | ~67,604 | ~184,637 | 2.73x | The complete OPIN consent flow becomes 2.73 times heavier with pure PQC. This is the cost of fully replacing the classical algorithms with ML-DSA-65, including the PKI/CRL certificate chain now simulated locally (Decision 12). Experiment 3 (hybrid) is estimated to exceed this value — by running PS256 and ML-DSA-65 in parallel, each JWT would accumulate both signatures simultaneously, potentially making the hybrid flow heavier than pure PQC. The experiment will confirm or correct this estimate. |
| mTLS Handshake — P50 (bytes) | 9,785 | 19,756 | +102% | Before any data exchange, participants need to establish a secure connection. This authentication process costs 102% more in bytes with PQC — both the client and the server (gateway) present ML-DSA-65 certificates, each contributing a larger signature than the RSA equivalent. The digital certificate the client presents to identify itself grew from 1,494 bytes (classic) to 2,953 bytes (ML-DSA-65). |
| Average JWT (bytes) | 1,385 | 5,459 | 3.94x | Every security token that flows through the flow has three parts: the header (identifies the algorithm), the payload (data such as the consent identifier, permissions, and validity), and the digital signature. With the migration to ML-DSA-65, only the signature changes — from 342 bytes (RSA-2048, the Authorization Server's and Data Server's keys) to 4,412 bytes (ML-DSA-65). The header and payload stay practically the same. The result is that the full token grows from 1,385 to 5,459 bytes — 3.94 times larger. |
| Authorization Server bytes — AS | 26,063 | 71,270 | 2.73x | The Authorization Server grows 2.73x — every token it issues now uses ML-DSA-65. The growth reflects the full migration of the flow's authorization tokens to the new algorithm. |
| Data Server bytes — RS (Resource Server) | 30,873 | 96,091 | 3.11x | The Data Server is the participant most impacted in absolute volume — it grows 3.11x and accumulates +65,218 additional bytes. The Consents and Person APIs are called multiple times in the flow, and every response is now signed with ML-DSA-65, accumulating the overhead with each call. |
| PKI/CRL bytes | 10,668 | 17,276 | +61.9% | The Certificate Authority certificates (root-ca.pem/issuer-ca.pem) are now locally simulated with ML-DSA-65 to complete the certificate chain for comparison with the literature (Decision 12 in DECISIONS.md). This is a local simulation for cost-measurement purposes — in production, this migration would depend on Raidiam updating their real PKI, external infrastructure outside this thesis's control. |

| Endpoint | Classic P50 (0ms network, median of 5 runs) | PQC P50 (0ms network, median of 5 runs) | Computational overhead | What this means |
|---|---|---|---|---|
| /token (POST) | 26.54ms | 52.48ms | +25.94ms (+98%) | /token is the endpoint where the client proves its identity to the server. To do this, it creates a special token called a client assertion. The server receives this token, verifies the signature, and, if everything checks out, returns the access token. With PS256, creating and verifying this signature takes about 26.54ms. With ML-DSA-65, the same process takes 52.48ms — essentially double. Across the 5 independent runs backing this figure, PQC was slower than classic in every single one, with no overlap between the two runs' ranges (classic: 24.72–32.05ms; PQC: 41.94–62.98ms) — the most statistically solid result in this table. |
| /open-insurance/consents/v3/consents (POST) | 72.49ms | 89.47ms | +16.98ms (+23%) | When the script creates a consent by POSTing to /consents, the Data Server needs to respond confirming the consent was created. With PQC, this response comes signed with ML-DSA-65 — the server spends time computing the signature, and then still needs to transmit a larger JWT than before. With PS256 this takes 72.49ms. With ML-DSA-65 it takes 89.47ms. **Statistical note:** this endpoint has only n=2 samples per run (one call per flow), and the two experiments' 5-run ranges overlap (classic: 59.37–101.12ms; PQC: 76.08–149.18ms) — the median still points to PQC being slower, but less decisively than /token. This endpoint is also the one that produced the two extreme JVM/BouncyCastle cold-start outliers documented in DECISIONS.md (Decision 14) — excluded here since those reflect a one-time initialization cost after container recreation, not the algorithm's steady-state cost. |
| /open-insurance/consents/v3/consents (GET) | 17.24ms | 34.23ms | +16.99ms (+99%) | After creating the consent, the script queries its status several times to check whether it is AWAITING_AUTHORISATION and later AUTHORISED. Each query is a GET on the same /consents/{id} endpoint, combined across both flows' distinct consent URNs (6 samples total per run: 5 from one consent + 1 from another). With PS256 this query takes 17.24ms. With ML-DSA-65 it takes 34.23ms — almost exactly double. Across the 5 runs, PQC was slower in every one, with no overlap between ranges (classic: 15.28–22.75ms; PQC: 28.73–55.20ms). |
| /open-insurance/insurance-person/v2/... | 24.14ms | 41.41ms | +17.27ms (+72%) | The person flow calls four personal-data APIs — insurance-person, claim, policy-info, and premium — each returning real policy, claim, and premium data for the insured party, reported here as the average of the four endpoints' own P50s. With PQC, each response is signed with ML-DSA-65. With PS256 the average response across the four endpoints is 24.14ms. With ML-DSA-65 it is 41.41ms. **Statistical note:** the two experiments' 5-run ranges overlap somewhat (classic: 19.62–46.38ms, with one run showing an outlier at 46.38ms; PQC: 34.56–45.26ms, a tighter spread), but the median direction (PQC slower) holds in 4 of the 5 run-to-run comparisons. |
| /jwks (GET) | 45.09ms | 37.40ms | -7.69ms (-17%) | The /jwks endpoint is where the client fetches the server's public key to verify the tokens it receives. It is a simple read operation — the server performs no cryptographic computation, it just returns the already-stored public key. Unlike every other endpoint in this table, /jwks shows PQC as slightly *faster*, but the two experiments' 5-run ranges overlap substantially (classic: 37.70–57.64ms; PQC: 31.84–45.56ms) — consistent with there being no signing or verification operation on this endpoint, so its response time is expected to be practically equivalent between algorithms rather than showing a real, reproducible direction either way. What does not change between reruns is the response size: the RSA-2048 public key is 256 bytes, while the ML-DSA-65 key is 1,952 bytes (value from the FIPS 204 specification — methodological limitation: the pipeline's JWK parser does not recognize the AKP key type, so this key does not appear in the directly measured results). |

**Total flow latency across all 6 network scenarios:**

Rather than a single endpoint, this table sums the latency of all 28 HTTP calls in the complete consent flow (both the insurance and person test plans combined) per scenario — the same total-cost framing Bloco A already uses for bytes, applied here to time.

| Latency scenario | Classic total | PQC total | Delta |
|---|---|---|---|
| 0ms | 847.57ms | 964.09ms | +116.52ms (+14%) |
| 14ms | 3,348.04ms | 3,128.44ms | -219.60ms (-7%) |
| 30ms | 4,721.97ms | 4,770.93ms | +48.96ms (+1%) |
| 140ms | 16,792.05ms | 16,716.76ms | -75.29ms (-0.4%) |
| 225ms | 24,016.83ms | 26,759.78ms | +2,742.95ms (+11%) |
| 320ms | 34,239.04ms | 36,421.63ms | +2,182.59ms (+6%) |

For 14ms–320ms, each total is reconstructed exactly (not approximated) from `consolidated.json`'s existing per-endpoint `count`/`mean_ms` fields — since `mean × count` recovers the exact summed latency across every one of that scenario's 28 calls, no raw per-call log was needed, and each of these five scenarios is already a single stable run with no sign of the instability described below. The 0ms total, by contrast, needed the same 5-independent-run median treatment as the endpoint table above: an isolated 0ms endpoint showed run-to-run instability, and the full-flow sum turned out to have it too — see the validation data immediately below.

Once network latency is injected, the classic/PQC gap stops following a consistent pattern (-7% at 14ms, roughly flat at 30ms/140ms, back up to +6–11% at 225ms/320ms) rather than shrinking monotonically — with only a single run per non-zero scenario, these deltas are within the range of run-to-run noise already observed in the 0ms series (up to a few hundred percent on a single flaky run) and should not be read as a stable trend across latency, only the 0ms row (backed by 5 runs each) supports a real directional claim: PQC's total flow cost is measurably higher without network latency in the picture.

**Total flow latency, 5-round validation data (0ms scenario, ms per run):**

| Run | Classic total | PQC total |
|---|---|---|
| 1 | 1,981.46 | 1,056.79 |
| 2 | 846.91 | 979.65 |
| 3 | 847.57 | 950.68 |
| 4 | 1,214.59 | 964.09 |
| 5 | 837.62 | 861.47 |
| **Median** | **847.57** | **964.09** |

PQC's 5 runs were clean on the first attempt. Classic's first attempt at run 1 produced an outlier (4,990.35ms, roughly 5x every other run) immediately after a container recreation that had needed two retries for an unrelated localstack SSM-parameter startup race — discarded and replaced with a fresh run (1,981.46ms) per the same run-replacement protocol used elsewhere in this document; the median (847.57ms) is unchanged by this substitution either way, since it depends only on the three consistently tight middle values (837.62/846.91/847.57ms), not on whichever number lands in the highest slot.

**5-round validation data (0ms scenario, P50 in ms per run):**

| Run | Classic /token | Classic /consents POST | Classic /consents GET | Classic person avg | Classic /jwks | PQC /token | PQC /consents POST | PQC /consents GET | PQC person avg | PQC /jwks |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 24.72 | 59.37 | 15.65 | 19.62 | 45.09 | 62.98 | 149.18 | 55.20 | 45.26 | 37.40 |
| 2 | 28.20 | 97.20 | 20.73 | 21.38 | 47.25 | 52.48 | 89.47 | 39.87 | 34.56 | 45.56 |
| 3 | 26.54 | 67.50 | 15.28 | 46.38 | 42.33 | 41.94 | 76.08 | 30.33 | 39.70 | 42.06 |
| 4 | 26.31 | 72.49 | 17.24 | 26.95 | 37.70 | 57.33 | 94.44 | 34.23 | 41.41 | 31.84 |
| 5 | 32.05 | 101.12 | 22.75 | 24.14 | 57.64 | 45.20 | 78.04 | 28.73 | 41.67 | 35.23 |
| **Median** | **26.54** | **72.49** | **17.24** | **24.14** | **45.09** | **52.48** | **89.47** | **34.23** | **41.41** | **37.40** |

Each run is a fully independent execution of both flows (insurance and person), each spawned as its own isolated process against a freshly warmed environment (containers recreated once per experiment before the 5-run series, not once per run — see DECISIONS.md, Decision 14, for why one throwaway warmup run was needed before the PQC series specifically). The reported table value is the median of the 5 per-run P50s, not a single run's own P50.

| Parameter | Classic (Exp 1) | Pure PQC (Exp 2) | Growth | What this means for the OPINsize equation |
|---|---|---|---|---|
| N_mTLS — number of distinct handshakes | 6 (constant across all scenarios) | 6 (constant across all scenarios) | Stable | The number of connections does not change with the algorithm — only the cost of each one does. With the login now fully automated (Decision 13 in DECISIONS.md, which eliminated the real browser the script opened for the manual login step), the value is perfectly constant in both experiments; the ~9 to 16 variation previously measured on the classic side came from that browser's non-deterministic connection attempts, not from the consent flow being measured. |
| mTLS_handshake_bytes — handshake size, P50 | 9,785 bytes (constant across all scenarios) | 19,756 bytes (all scenarios) | +102% | Parameter that grows with the client's and gateway's ML-DSA-65 certificates (Experiment 2 complete). Perfectly stable in both experiments now that the login is fully automated — evidence that handshake size is deterministic for both algorithms, not just PQC. |
| N_JWT — number of tokens in the flow | 26 | 26 | Stable | The number of tokens does not change with the algorithm — only the size of each one does. Fixed parameter in the equation for both experiments. |
| JWT_size — average JWT size | 1,385 bytes | 5,459 bytes | 3.94x | Same data already explained in the traffic-cost table (Average JWT, earlier in this document) — repeated here because it is one of the parameters that feeds directly into the analytical OPINsize equation. |
| JWK_PK_size — AS public key size | 256 bytes (RSA-2048) | 1,952 bytes (ML-DSA-65) | 7.63x | Public key that the Authorization Server publishes so other participants can verify the tokens it signs. Grew 7.63x with the migration to ML-DSA-65 — reflects the structurally larger size of post-quantum keys as defined by the FIPS 204 standard. |
| N_JWK — number of calls to /jwks | 2 | 2 | Stable | The script queries the /jwks endpoint 2 times during the flow, to fetch the public keys it needs. This number is fixed — it does not change with the cryptographic algorithm used. |
