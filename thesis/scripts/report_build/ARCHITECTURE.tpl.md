# v7 Architecture — OPIN Flow with Three Cryptographic Profiles and the Extended OPINsize Equation

This document describes, independently, the architecture of the final experiment (v7): the system measured, the three cryptographic profiles, how each primitive acts in the flow, how the metrics are collected, and the size equation (OPINsize) with the extension for CA certificates. The numerical results are in [`CONSOLIDATED_REPORT.md`](CONSOLIDATED_REPORT.md); here, the numbers serve only to illustrate the design.

---

## 1. Purpose and Scope

**Experiment question.** How much does it cost, in bytes transferred and flow time, to migrate the Open Insurance Brasil (OPIN) consent flow from classical cryptography to post-quantum (PQC) and to a hybrid combination?

**What v7 covers**, in a single set of measurements:

- **Level 2 (signatures)**: client certificates, tokens (JWT), published public keys (JWKS), and client authentication (`client_assertion`).
- **Level 1 (key exchange)**: the TLS handshake key exchange, the part exposed to the "harvest now, decrypt later" attack.

**What is left out**: token encryption (JWE with RSA-OAEP), for which there is currently no post-quantum JOSE/COSE standard; dynamic client registration (SSA/DCR); the hash-based audit trail; certificate revocation. Full coverage relative to the security architecture document (SAD) is in `thesis/docs/Cruzamento_SAD_vs_Experimentos.md`.

**History.** v7 replaces v5 (signatures-only migration) and v6 (key exchange measured in isolation, with a different TLS client than v5's). Merging the two levels into a single batch, with a single TLS client for all three profiles, is v7's central decision (`DECISIONS.md`, Decision 1 and 2). The size equation extension is in Decision 7.

---

## 2. System Overview

```
  experiment machine (Docker Desktop, a single host)

  ┌──────────────────────┐   local TLS        ┌──────────────────┐   real mTLS, profile group
  │ opin_flow.py          │  127.0.0.1:8443    │  tls_kem_proxy    │  (ECDHE | MLKEM1024 | X25519MLKEM768)
  │ (test client,         │ ─────────────────► │  (TLS client      │ ─────────────────────────────┐
  │  Python)              │ ◄───────────────── │   in Go)          │                              │
  └──────┬───────────────┘                    └──────────────────┘                              ▼
         │ signs PQC JWTs                                                       ┌───────────────────────────┐
         ▼                                                                     │ mTLS gateway (mock_mtls)  │
  ┌──────────────────────┐                                                     │  Go, port 443             │
  │ pqc-signer            │                                                     │  routes by Host           │
  │ (ephemeral container, │                                                     └───┬────────┬──────────┬───┘
  │  Go, ML-DSA-65)       │                                                         │        │          │
  └──────────────────────┘                                              auth.local  │        │ api.local │ directory
                                                                     ┌─────────────▼┐  ┌────▼───────┐ ┌─▼────────────┐
                                                                     │ AS (auth)    │  │ RS (mockapi)│ │ Directory/PKI│
                                                                     │ Node.js,     │  │ Java,       │ │ (on gateway) │
                                                                     │ oidc-provider│  │ BouncyCastle│ └──────────────┘
                                                                     └──────┬───────┘  └──────┬──────┘
                                                                            │  matls-api.local │
                                                                            └── auth → RS (internal, always classical)
```

**What the table below shows.** The diagram above is the map; the table gives, for each box in it, the role it plays in the flow and the technology it was built in — useful for quickly locating where to look for the code or logs of a specific component.

| Component | Role | Technology |
|---|---|---|
| **`opin_flow.py`** | Test client: runs the complete OPIN flow and measures the time of each run | Python |
| **`tls_kem_proxy`** | TLS client in Go that negotiates the key-exchange groups Python doesn't support; one per run | Go (`crypto/tls`) |
| **`pqc-signer`** | Signs the client-side ML-DSA-65 JWTs; one ephemeral container per signature | Go (`crypto/mldsa`) |
| **mTLS Gateway** (`mock_mtls`) | Terminates mTLS, validates the client certificate, routes by `Host` to AS, RS, and Directory, and logs per-connection metrics | Go |
| **AS** (`auth`) | Authorization server: consent, PAR, tokens, `id_token`, JWKS | Node.js, `oidc-provider` |
| **RS** (`mockapi`) | Resource server: responds to insurance queries with a signed JWT | Java, BouncyCastle |
| **Directory/PKI** | Serves the CA certificates (`root-ca.pem`, `issuer-ca.pem`) | Gateway (`directoryHandler`) |

The active profile is selected by a single variable, `CRYPTO_PROFILE` (`classic`, `pqc`, or `hybrid`), read by all components; the switch is performed by `switch_crypto_profile.py`, which also waits for the environment to settle.

**The internal `auth`→RS connection.** To display the consent screen, the AS queries the RS through the same gateway (`matls-api.local`) with its own fixed, classical transport certificate. Node.js's HTTPS client doesn't negotiate the post-quantum groups, so this single connection is kept classical via a deliberate SNI-based exception in the gateway (Section 5.1). It is not part of the measured flow: it doesn't enter N_mTLS nor any size or handshake metric.

---

## 3. The Measured OPIN Flow

Each run has two sub-flows executed in sequence, for a total of **28 requests**:

**What the table below shows.** Each row is one of the two OPIN sub-flows (obtaining consent for insurance data, then for personal data); the "Requests" column counts how many HTTP/TLS calls that sub-flow makes, and "Steps" lists, in the order they occur, what each of those calls is.

| Sub-flow | Requests | Steps |
|---|---:|---|
| Insurance consents | 12 | `GET /jwks` · `GET root-ca.pem` · `GET issuer-ca.pem` · `POST /token` (client_credentials) · `POST` consent · `GET` consent ×3 · `POST /request` (PAR) · [automated login] · `POST /token` (authorization_code) · `GET` consent ×2 |
| Personal insurance data | 16 | the same first 8 identification and authorization steps (1 consent `GET`) · policy lookup ×2 · claim ×2 · policy information ×2 · premium ×2 |

The login is automated and uses a separate connection pool (as a browser would), which gives **three connection pools per sub-flow** (AS, RS, and login) and, across the two sub-flows, the **6 mTLS connections** that the size equation uses as N_mTLS. Each connection is reused (keep-alive) by all calls in its pool. The flow carries **26 JWTs**, fetches the AS's JWKS **2 times** (once per sub-flow), and downloads **4 CA certificates** (root and issuer, in each sub-flow).

---

## 4. The Three Cryptographic Profiles

### 4.1. Where Each Primitive Acts

**What the table below shows.** Each row is a cryptographic artifact in the flow (a certificate, a token, a published key); the three columns show, side by side, which algorithm or scheme that artifact uses in each profile. This is the central reference for answering "what exactly changes when the profile changes?" for each piece of the system.

| Artifact | Classic | PQC | Hybrid |
|---|---|---|---|
| **TLS key exchange** | Classical ECDHE (P-521, P-384, P-256) | Pure **MLKEM1024** | **X25519MLKEM768** |
| **Client certificate** (mTLS) | RSA-4096, signed by an RSA CA | ML-DSA-65 subject key; CA remains RSA | RSA-4096 + three non-critical X.509 extensions carrying the ML-DSA-65 material, signed twice (RSA and ML-DSA-65) |
| **RS response JWT** | PS256 | ML-DSA-65 | RS256 with payload extension (`pqc`) |
| **AS `id_token` and JARM** | PS256 | ML-DSA-65 | Strong Nesting (σ1‖σ2) |
| **`client_assertion` and PAR object** | PS256 | ML-DSA-65 | RS256 with payload extension (`pqc`) |
| **AS signing public key (JWKS)** | RSA (256 bytes) | `kty: AKP`, ML-DSA-65 (1,952 bytes) | `kty: HYBRID`, composite key (2,208 bytes) |
| **`id_token` encryption** | RSA-OAEP + AES-256-GCM | same (classical) | same (classical) |
| **Access token** | opaque, bound to the client certificate | same | same |

The access token is an opaque, unsigned string: the signature that authenticates the client at that step is the `client_assertion`'s.

Resulting sizes per flow (identical across all latency scenarios): client certificate of {{cert_classic}}, {{cert_pqc}}, and {{cert_hybrid}} bytes; average JWT of {{jwtmean_classic}}, {{jwtmean_pqc}}, and {{jwtmean_hybrid}} bytes; handshake of {{hs_classic}}, {{hs_pqc}}, and {{hs_hybrid}} bytes (Classic, PQC, Hybrid).

### 4.2. Why the Profiles Make Different Choices

**PQC — "post-quantum only" philosophy.** Signature and key exchange with no classical component whatsoever. The only exception is the client certificate, whose issuance by the CA remains RSA (the subject key is ML-DSA-65, but the CA doesn't migrate): this is the deliberate design of migrating the participant's identity first, without requiring the CA to learn to sign with ML-DSA-65.

**Hybrid — "AND gate" philosophy.** Compromising the result requires breaking both algorithms at the same time. Each artifact uses the combination scheme best suited to its role:

**What the table below shows.** The Hybrid profile doesn't use a single way of combining classical and post-quantum — it uses three, each chosen for the type of artifact involved. The table lists the three schemes, where each is applied, how it works internally (the signing order, what goes into each signature), and the security property it guarantees.

| Scheme | Where | How it works | Property |
|---|---|---|---|
| **Doubly-signed X.509 extensions** (Bindel et al., 2019) | Certificates | ML-DSA-65 signs first, over the certificate still without the alternative signature; RSA signs last, over the complete certificate. The extensions (`SubjectAltPublicKeyInfo`, `AltSignatureAlgorithm`, `AltSignatureValue`) are marked non-critical, so a classical verifier ignores them | Compatibility with legacy verifiers |
| **Payload extension** | RS JWT; `client_assertion`; PAR object | ML-DSA-65 signs first, over the canonicalized claims (RFC 8785), and the result becomes the `pqc` claim; RS256 signs last, covering that claim. The header remains a plain `RS256` | A plain RS256 verifier accepts the token by ignoring `pqc` |
| **Strong Nesting** | `id_token`, JARM | σ1 = PS256(message); σ2 = ML-DSA-65(message ‖ σ1); signature = σ1 ‖ σ2 (256 + 3,309 = 3,565 bytes). The header remains `PS256` | A classical signature cannot be recombined with a post-quantum one (SUF-CMA property) |
| **Hybrid key-exchange group** | TLS | `X25519MLKEM768`: the session key is derived from X25519 and ML-KEM-768 together | Confidentiality preserved if only one of the two is broken |

The payload extension partially gives up Strong Nesting's SUF-CMA property in exchange for compatibility with legacy verifiers; the complete reasoning and references are in `thesis/results/v4/JWT_Hybrid_Architecture.md`.

**Classic — the baseline.** Nothing changes relative to what was already the system's standard.

### 4.3. Implementation Proof

For each profile, `artifacts/` provides a real capture of every artifact above (certificate, RS JWT, JWKS entry, handshake evidence, `id_token`, `client_assertion`) with **reproducible cryptographic verification** (for example, the hybrid certificate's ML-DSA-65 signature is reconstructed and verified, and the handshake session key is proven fresh on every connection via key-material export, RFC 5705): [Classic](artifacts/classic/README.md), [PQC](artifacts/pqc/README.md), [Hybrid](artifacts/hybrid/README.md).

---

## 5. Transport Layer

All three profiles were measured under the same TLS client architecture (`tls_kem_proxy`), eliminating confounding variables between them — each profile requests exactly one key-exchange group, with no fallback: if the server doesn't offer it, the connection fails visibly, instead of silently falling back to classical. Full description, issue history, and code references in [`TLS_KEM_Proxy_Architecture.md`](TLS_KEM_Proxy_Architecture.md).

### 5.1. The Gateway Policy and Its Only Exception

The gateway defines the list of accepted groups by `CRYPTO_PROFILE`: classical curves in Classic, only `MLKEM1024` in PQC, only `X25519MLKEM768` in Hybrid (with TLS 1.3 mandatory in the latter two). There is **one exception, deliberate and restricted by SNI**: every connection whose `ServerName` is `matls-api.local` (the internal `auth`→RS call) gets the classical configuration. It was confirmed, connection by connection, that **every** classical handshake observed under PQC/Hybrid has this SNI and that no other connection does (35 applications of the exception, 35 classical handshakes, matching source address in every pair; `DECISIONS.md`, Decision 6).

---

## 6. Signature Layer

### 6.1. Certificates

`mock-service-os/certs/main.go` generates the certificates for each profile. The hybrid certificate reuses Classic's RSA key and adds the ML-DSA-65 material in non-critical extensions; independent verification reconstructs the content that ML-DSA-65 signed (the certificate without the alternative-signature extension) and checks it against the CA key. At the gateway, hybrid client-certificate validation applies the AND gate (both signatures must verify).

### 6.2. Tokens and Published Keys

The RS signs each response according to the profile (`ResponseSigningService`); the AS signs `id_token` and JARM (`oidc-provider` with an external signing key in the hybrid profile, to produce the Strong Nesting without the library recognizing a new algorithm); the client signs `client_assertion` and the PAR object (`opin_flow.py`). The JWKS publish each profile's key (in Hybrid, one composite entry on the AS and, on the RS, two entries under the same `kid`: the composite one and one with just the classical half, so that a common verifier finds the one it recognizes).

### 6.3. The Limit: Encryption

The `id_token` is encrypted (JWE, RSA-OAEP with AES-256-GCM) to the key the client registered, in **all** profiles. There is currently no JOSE/COSE standard for representing an ML-KEM key in a JWE, and the library used doesn't support it. A live-captured `id_token` from the PQC profile shows the result: on the inside, a verified pure ML-DSA-65 signature; on the outside, an RSA-OAEP encryption identical to Classic's.

---

## 7. The OPINsize Equation: The Extension Proposed by This Thesis

The original flow-size equation (equivalent to Eq. 3.1 of Schardong et al., 2022) sums three terms — the cost of the mTLS handshake, of the tokens transferred, and of the published public keys:

```
OPINsize = N_mTLS × handshake_bytes + N_JWT × JWT_size + N_JWK × JWK_PK_size
```

This thesis extends it with a fourth term, for the Certificate Authority certificates that the flow downloads and that were already measured but never entered the sum. From here on, **OPINsize always refers to the extended formula** — the three-term version does not reappear as a result; it only served to justify the extension:

```
OPINsize = N_mTLS × handshake_bytes + N_JWT × JWT_size + N_JWK × JWK_PK_size + N_PKI × PKI_bytes
```

with N_mTLS = {{n_mtls}}, N_JWT = {{n_jwt}}, N_JWK = {{n_jwk}}, and N_PKI = {{n_pki}} ({{n_root}} for the root + {{n_issuer}} for the issuer). `PKI_bytes` is the average size, in bytes, of the two CA certificates served, **in the format they travel in (PEM)**; since root and issuer have slightly different sizes, N_PKI × PKI_bytes is the exact sum of the {{n_pki}} transfers. Each term is a size of cryptographic material, not of HTTP traffic — the JWT size is the token's length, the key's size is the key's size, without headers. With N_PKI = 0 the equation reduces to the original, which preserves comparability with the literature.

### 7.1. Why the PKI Term Is Necessary

The flow downloads two CA certificates (`root-ca.pem`, `issuer-ca.pem`) at the start of each sub-flow, {{n_pki}} transfers per complete run. These certificates **are not handshake** (they travel over HTTP, outside the TLS negotiation), **are not JWT**, and **are not a JWKS key**; none of the three original terms includes them, even though the cost was already measured — the raw files record it under the "PKI/CRL" participant. There is no double-counting with the handshake: the certificates that travel **inside** it (server and client) are counted in the handshake term; the CA ones downloaded over HTTP are distinct transfers.

**Data origin, no new measurement.** The certificate sizes come from the PEM files the gateway serves (`mock-service-os/certs/`) and were validated against the HTTP response volume already recorded in the raw data: the measured volume minus the body of the {{n_pki}} certificates gives an HTTP framing of exactly {{frame_each}} bytes per response, identical across all three profiles — which can only happen if the body served is the file used in the calculation.

**What the table below shows.** For each profile, the size in bytes of the root certificate and the issuer certificate (in PEM format, as they travel), and the sum of the {{n_pki}} downloads that make up the equation's PKI term — the numerical basis for everything discussed in Section 7.2.

{{table:pki_detail}}

### 7.2. Why This Matters Specifically in the Hybrid Scenario

In Hybrid, each CA certificate carries, in addition to the RSA structure, the complete ML-DSA-65 material (public key and alternative signature) in the three extensions: each one takes up about {{root_hybrid}} bytes in PEM, versus {{root_classic}} in Classic and {{root_pqc}} in PQC. In absolute terms:

- Hybrid's PKI term is **{{t_pki_hybrid}} bytes** — **{{hyb_pki_over_jwk}} the JWK public-key term** ({{t_jwk_hybrid}} bytes) and equivalent to {{hyb_pki_over_hs}} of the handshake term ({{t_hs_hybrid}} bytes): larger than one of the equation's other three terms.
- It is **{{pki_ratio_hybrid_classic}} Classic's PKI term** and {{pki_ratio_hybrid_pqc}} PQC's: the growth of the CA material is the portion of the cost most sensitive to the combination scheme chosen, because Hybrid is the only profile whose CA certificates carry both signatures.
- The PKI term doesn't change the order of the profiles nor the dominant weight of the JWTs ({{t_jwt_hybrid}} bytes in Hybrid) — its share of each profile's OPINsize is in Section 7.3.

### 7.3. Numerical Impact

**What the table below shows.** Each row is a term of the extended equation; the profile columns give the value of N (how many times the term occurs in the flow) and the result in bytes of each term, per profile. The **OPINsize** row is the sum of the four terms — the equation's final result — and the following row shows what fraction of that total the PKI term (the new one, from this thesis) represents.

{{table:opin}}

**How to read the ratio table below.** Each row divides one profile's OPINsize by another's, to directly answer "how many times larger/heavier is X relative to Y" — the same kind of ratio used in the size tables of `CONSOLIDATED_REPORT.md`, Section 3.1.

{{table:opin_ratios}}

- The PKI term represents {{share_classic}} of Classic's OPINsize, {{share_pqc}} of PQC's, and {{share_hybrid}} of Hybrid's — in Hybrid, the second-largest component of the sum, behind only the JWT term.
- By OPINsize, Hybrid is {{opin1_ratio_hybrid_pqc}} PQC and {{opin1_ratio_hybrid_classic}} Classic; PQC is {{opin1_ratio_pqc_classic}} Classic.
- PQC has the smallest relative share of the PKI term because, in this prototype, its CA certificates have an ML-DSA-65 subject key but remain signed by an RSA CA (deliberate design of Stage 3.1); in Hybrid, the CA certificates carry both signatures.

### 7.4. Sensitivity and Limits of the Term

- **Certificate format.** PEM (base64 with line breaks) takes up about 36–39% more than DER; PEM is the format that actually travels on the wire. In DER, the term would be (the table below recalculates OPINsize with the PKI term in DER, and shows the percentage variation relative to the official OPINsize in PEM):

{{table:sens_der}}

- **HTTP framing.** Using the measured response volume directly (body + {{frame_each}} bytes per certificate), OPINsize changes by less than 1 percentage point — the table below is the same comparison, now with the PKI term measured by actual HTTP traffic instead of the PEM file size:

{{table:sens}}

- **N_PKI is a property of the implemented flow.** The test client downloads the CA certificates at the start of each sub-flow, with no cache; a real client with caching would pay less. The formula keeps N_PKI explicit to allow other values, the same way as N_JWK.
- **Scope.** OPINsize models the cost of the cryptographic artifacts; it does not include HTTP headers, TLS/TCP/IP overhead, or the total application traffic (`total_bytes_exchanged`), which is a separate metric.

---

## 8. How the Metrics Are Collected

**What the table below shows.** For each metric used in the results, exactly where the value comes from (which component records it) and the measurement mechanism — useful for auditing the origin of any number in this report or in `CONSOLIDATED_REPORT.md`.

| Metric | Where it's measured | How |
|---|---|---|
| `handshake_bytes` | Gateway | A counter on the raw TCP connection (below TLS) sums the bytes read and written; the value is read when the server starts reading the first request, i.e., right after the handshake finishes |
| Negotiated key-exchange group | Gateway | Recorded from the TLS connection state (`curveID`), not from the configuration |
| `client_cert_der_bytes` | Client | DER size of the presented certificate |
| JWT and JWK key | Client | Extracted from responses and requests (token length; public-key size of each JWKS entry) |
| Bytes per participant | Client | Headers + body of each request and response, attributed to Client, "Other" (AS + RS), or PKI/CRL |
| `T_fluxo` | Client | Monotonic clock, from the start to the end of the complete flow; attempts discarded due to known failures don't count |

The gateway logs every connection it sees, including the internal `auth`→RS one; that's why the gateway statistics are filtered by the active profile's client-certificate size, which reliably identifies the test client's connections.

**AS/RS resolution.** Each call's participant is assigned by the URL address, and in v7 the calls for all three profiles go through the local proxy — that's why the AS and RS both showed up as "Other" in the official raw data. Closed with a one-off capture (one run per profile, outside the statistical protocol, same category as `artifacts/`) that uses each call's real `Host` header (never rewritten by the proxy) to reclassify; valid for the 180 runs already collected because size is provably deterministic (0.00% spread). See `DECISIONS.md`, Decision 10, for the complete methodology and for a real environment issue found along the way.

**Remaining limitation.** The gateway records handshake bytes as a read+write sum, with no direction — this breakdown would require instrumenting the gateway and was not done (`CONSOLIDATED_REPORT.md`, Section 3.3).

**Protocol**: 6 latency scenarios × 10 runs × 3 profiles, for size and for latency; one warm-up run discarded per latency scenario; no outlier removal; environment warm-up after every profile switch; "JSON is the source, Markdown is derived" convention. The statistics were recalculated from the raw files in an independent audit before consolidation (`CONSOLIDATED_REPORT.md`, Section 7).

---

## 9. Known Limitations of the Architecture

1. Token encryption remains classical in all three profiles (Section 6.3).
2. The internal `auth`→RS connection remains classical by design (Section 5.1).
3. PQC uses ML-KEM-1024 (NIST category 5) and Hybrid uses ML-KEM-768 (category 3): Go only offers ML-KEM-1024 without a classical component.
4. Hybrid's RSA component is 2,048 bits in the JWTs issued by the AS and RS, for continuity with what had already been measured.
5. The test client's ML-DSA-65 signer uses an ephemeral container per signature, which has its own time cost and affects the T_fluxo of the PQC and Hybrid profiles (`CONSOLIDATED_REPORT.md`, Section 6).
6. Pre-release or experimental-version tooling (Go 1.27 release candidate; Node 24's WebCrypto ML-DSA-65).
7. Not covered: SSA, DCR, hash-based audit trail, and revocation (CRL/OCSP).

---

## References

- Bindel, N., Herath, U., McKague, M., & Stebila, D. (2017). *Transitioning to a Quantum-Resistant Public Key Infrastructure.* PQCrypto 2017 (origin of Strong Nesting and the SUF-CMA property).
- Bindel, N., Braun, J., Gladiator, L., Stebila, D., & Wiggers, T. (2019). *X.509-Compliant Hybrid Certificates for the Post-Quantum Transition.* Journal of Open Source Software, 4(40), 1606.
- Schardong et al. (2022), Eq. 3.1 (original flow-size equation). *Full bibliographic entry to be inserted by the author.*
- NIST FIPS 203 (ML-KEM) and FIPS 204 (ML-DSA).
- IETF TLS WG: `draft-ietf-tls-mlkem` (pure ML-KEM in TLS 1.3) and `draft-ietf-tls-ecdhe-mlkem` (hybrid ECDHE-MLKEM groups, including X25519MLKEM768), still in draft.
- RFC 8446 (TLS 1.3); RFC 5705 (key-material exporters); RFC 8785 (JSON Canonicalization Scheme); RFC 7523 (JWT client authentication).
- Project documents: [`CONSOLIDATED_REPORT.md`](CONSOLIDATED_REPORT.md), [`TLS_KEM_Proxy_Architecture.md`](TLS_KEM_Proxy_Architecture.md), [`DECISIONS.md`](DECISIONS.md), `artifacts/`, `thesis/results/v4/JWT_Hybrid_Architecture.md`, `thesis/docs/Cruzamento_SAD_vs_Experimentos.md`.
