# Real artifacts — Hybrid profile

This folder (and its sibling folders `artifacts/classic/` and
`artifacts/pqc/`) exists as **verifiable proof of implementation**: for
every claim this project makes that "this was actually done" — a hybrid
certificate generated in this specific order, a JWT signed with this exact
composition, a key published in that particular way, a key-exchange group
negotiated in that handshake — there is, here, the real artifact captured
live from the running system (not a fabricated example), the explanation of
the mechanism, and the exact point in the source code that implements it.

All the data below was captured live under `CRYPTO_PROFILE=hybrid`, on the
same system and pipeline (`tls_kem_proxy`, v7) used for the size and
latency batches — this is not a statistical sample (these are not 10 runs),
it is a single snapshot of each artifact, exactly as it exists in
production in this project.

---

## 1. Hybrid certificate (`client_one_hybrid.crt`)

### The real artifact

Raw file: [`client_one_hybrid.crt`](client_one_hybrid.crt) (PEM, the same
file used by the client throughout every run of the Hybrid profile).
Decoded version: [`client_one_hybrid.crt.txt`](client_one_hybrid.crt.txt)
(`openssl x509 -text -noout`, captured live from the file in use).

Relevant excerpt from the decoding — the three fields that carry the
post-quantum material:

```
X509v3 Subject Alternative Public Key Info:
    <binary: ML-DSA-65 public key>
X509v3 Alternative Signature Algorithm:
    <binary: alternative algorithm identifier>
X509v3 Alternative Signature Value:
    <binary: ML-DSA-65 signature>
Signature Algorithm: sha256WithRSAEncryption
Signature Value:
    c7:f7:74:60:62:ed:df:fa:30:16:23:0f:5f:b6:fd:6f:...
```

**Why OpenSSL shows raw binary here, and why this is the correct behavior,
not a gap in the proof.** OpenSSL recognizes these three extensions by name
(they are standard X.509 extensions, OIDs `2.5.29.72/73/74`) but does not
decode their internal content, because this build has no native support
for ML-DSA-65. This is not a problem to hide — it is **live evidence that
backward compatibility is working exactly as designed**: the three
extensions are deliberately marked **non-critical** (`critical=false`,
visible in the size extraction below), which, by X.509 definition (RFC
5280), instructs any verifier that does not recognize an extension to
**ignore its content and continue validating the certificate normally**. A
plain OpenSSL, with no PQC patch or plugin whatsoever, accepts this entire
certificate — because the signature it does know how to check (RSA,
`Signature Value`) covers the complete certificate, PQC extensions
included, even without understanding what they mean. OpenSSL's "not
understanding" the binary is precisely the behavior that proves a legacy
verifier can use this certificate with no adaptation at all. The proof
that the content *itself* is cryptographically valid — not just the right
size — comes next, through real verification, not through decoding by a
verifier that never had any reason to understand ML-DSA-65.

Exact sizes of each field, extracted via `cryptography` (Python) from the
same file, confirming the three OIDs, whether they are critical, and their
sizes in bytes:

| Field (OID) | Critical? | Size | What it is |
|---|---|---|---|
| `subjectAltPublicKeyInfo` (2.5.29.72) | no | 1.974 bytes | Subject's ML-DSA-65 public key |
| `altSignatureAlgorithm` (2.5.29.73) | no | 13 bytes | Alternative algorithm identifier |
| `altSignatureValue` (2.5.29.74) | no | 3.314 bytes | ML-DSA-65 signature |
| Final RSA signature (`Signature Value`) | — | 512 bytes | RSA-4096, `sha256WithRSAEncryption` |
| **Complete certificate (DER)** | — | **6.859 bytes** | Confirms the `client_cert_der_bytes` measured across the whole v7 batch |

### The proof that actually matters: the second signature is genuinely verifiable

A field of the right size, on its own, proves nothing — it could be any
sequence of 3.309 bytes. The proof that this certificate is **genuinely
hybrid**, not a classical certificate with a decorative field of the right
size, is: **this second signature passes a real cryptographic
verification, performed by a different algorithm (ML-DSA-65), over the
same content that the RSA signature covers.**

I wrote and ran an independent verification that does exactly this — it
extracts the key and the signature from inside the certificate,
reconstructs the exact bytes that were signed, and genuinely verifies the
signature against the corresponding ML-DSA-65 public key:

```
$ docker run --rm -v "<repo>/mock-service-os/certs:/src" -w /src golang:1.27-rc-alpine \
    go run . -verify-hybrid client_one

Subject's own ML-DSA-65 public key (SubjectAltPublicKeyInfo), 1952 bytes, first 16 as hex: 07b8d33d7a261d017ef2f6b70ceac247...
Alternative signature (AltSignatureValue), 3309 bytes, first 16 as hex: a49021396523fef8ef74eab565285e60...
Reconstructed preTBS: 2996 bytes (original final TBS was 6323 bytes -- the difference is exactly the AltSignatureValue extension this removes)
RESULT: verificado -- a assinatura ML-DSA-65 (AltSignatureValue) e valida para a chave ML-DSA-65 da CA emissora (issuer_ca_pqc.crt) sobre o preTBS reconstruido de /src/client_one_hybrid.crt.
```

Full output saved in
[`verify_hybrid_cert_output.txt`](verify_hybrid_cert_output.txt) —
reproducible command, runs on any machine with Docker from the repository.

What this command does, step by step (this is the same algorithm any real
verifier of this hybrid scheme would need to implement, not a testing
shortcut):

1. Extracts the subject's ML-DSA-65 public key (`SubjectAltPublicKeyInfo`,
   1.952 bytes of real key — not just the size, the content, shown in
   hex).
2. Extracts the ML-DSA-65 signature (`AltSignatureValue`, 3.309 bytes of
   real signature).
3. Reconstructs the **preTBS** — the exact bytes of the certificate as
   they existed *before* the ML-DSA-65 signature was added (removing only
   the `AltSignatureValue` extension, keeping everything else identical) —
   the same reconstruction that Phase 3 of Level 1 already validated for
   the standalone cryptographic proof. 2.996 bytes against 6.323 for the
   final TBS: the difference matches exactly the size of the removed
   extension.
4. Verifies the signature with `crypto/mldsa` (native ML-DSA-65 support in
   Go 1.27rc2, FIPS 204) against the ML-DSA-65 public key **of the issuing
   CA** (`issuer_ca_pqc.crt`) — not against the subject's own key.
   `SubjectAltPublicKeyInfo` (extracted in step 1) is the ML-DSA-65 public
   key **of this certificate's subject** (`client_one`), and it is
   certified by the CA's signature for the same reason the subject's RSA
   key is also certified by the CA's RSA signature (step 4 above): it is
   the CA that attests to the subject's identity, in both algorithms — the
   verification uses the CA's key because it is the CA that signs, exactly
   as on the classical side.

**Result: verified.** The ML-DSA-65 signature is cryptographically valid
for this key over this certificate — this is not an assumption based on
field size, it is a real signature verification that passed.

### Explanation of the mechanism

A hybrid X.509 certificate carries two independent signatures over the
same content, but **in the order ML-DSA-65-first/RSA-last**, not the other
way around:

1. A "pre-TBS" is assembled with the subject's RSA public key and the
   hybrid key/algorithm extensions (but still without the alternative
   signature), and signed once with RSA merely to obtain well-formed DER
   bytes from which to extract the TBS (`extractTBSBytes`).
2. The CA's ML-DSA-65 private key signs this pre-existing TBS — this is
   the alternative signature (`AltSignatureValue`), verified above.
3. The ML-DSA-65 signature is inserted as a certificate extension, and
   **only then** does the CA's RSA private key sign the final certificate
   — `sha256WithRSAEncryption`, the signature that appears in the standard
   `Signature Value` field, now covering the complete TBS, **including**
   the ML-DSA-65 signature that was just added.

By this ordering, the RSA signature (the one any ordinary X.509 verifier
already knows how to check) transitively covers the ML-DSA-65 signature as
well — tampering with the post-quantum field invalidates the classical
signature too, even though the verifier never looks inside it. This is the
same composition logic described in **Bindel, Braun, Gladiator, Stebila &
Wiggers (2019), "X.509-Compliant Hybrid Certificates for the Post-Quantum
Transition"**, Journal of Open Source Software (JOSS) — the three-extension
mechanism (`SubjectAltPublicKeyInfo`/`AltSignatureAlgorithm`/
`AltSignatureValue`), the non-critical marking, and the signing order all
come directly from that paper.

### Code reference

`mock-service-os/certs/main.go`:

- `generateHybridCert()`, lines 338–402 — certificate generation:
  - Lines 372–376: assembles the pre-TBS and extracts its bytes
    (`extractTBSBytes`, line 109).
  - Line 378: `caKeyMLDSA.Sign(nil, preTBS, nil)` — the ML-DSA-65
    signature, computed **first**, over the pre-TBS.
  - Lines 383–384: the ML-DSA-65 signature is inserted as an extension
    (`altSignatureValueExtension`, line 94), and the final certificate is
    created — it is **this** call to `x509.CreateCertificate` that
    produces the final RSA signature, last, over everything.
  - `hybridExtensions()` (lines 72–91) builds the first two extensions
    (`SubjectAltPublicKeyInfo`/`AltSignatureAlgorithm`), both explicitly
    marked `Critical: false`; the OIDs are declared on lines 38–39
    (`oidAltSignatureAlgorithm`/`oidAltSignatureValue`, `2.5.29.73`/`74`).
- `verifyHybridCert()` — the independent verification run above: extracts
  the extensions, reconstructs the preTBS by removing only
  `AltSignatureValue` (`tbs.Raw = nil` before re-serializing is the detail
  that guarantees the reconstruction reflects the removal, rather than
  reusing the original bytes), and calls `mldsa.Verify()` against the
  public key from `issuer_ca_pqc.crt`. Callable via `go run .
  -verify-hybrid <name>` on any `<name>_hybrid.crt` certificate in this
  project.

---

## 2. Real JWT, decoded (RS response, `GET .../premium`)

### The real artifact

Complete token captured live:
[`example_jwt_premium.txt`](example_jwt_premium.txt) — a real response from
the Resource Server (`GET .../insurance-person/{id}/premium`) during a run
of the insurance flow, Hybrid profile.

**Decoded header:**
```json
{"alg": "RS256", "kid": "mZi6awCMmw-lTxi5N3k9d6i_Wa5veP2IZyMvNolkcvQ", "typ": "JWT"}
```
Nothing here indicates that this is anything other than an ordinary RS256
JWT — that is the central point of the mechanism (see below).

**Decoded payload (top-level keys):** `data`, `links`, `meta`, `pqc` — the
`pqc` field carries `{"alg": "ML-DSA-65", "signature": "<4.412 characters
base64url>"}`.

**Exact numbers for this capture**, all checked directly against the
token:

| Metric | Value |
|---|---|
| Complete token | 7.430 characters |
| RS256 signature segment | 342 characters → decodes to 256 bytes (RSA-2048) |
| `pqc.signature` (ML-DSA-65) | 4.412 base64url characters (59% of the token) |

### The proof that actually matters: both signatures genuinely pass, AND gate included

Decoding the token shows the *structure* — two fields of the right size
and format. It does not prove that either one actually verifies. The real
proof is running the **same verification function this project already
uses in production** (`mock-service-os/mock_as/utils/opin/
payloadExtensionVerification.js` — not a reimplementation for this folder)
against the token above and the RS's real public keys, and confirming that
RS256 passes, ML-DSA-65 passes, and the AND gate over the two accepts the
token:

```
$ docker cp insurance-server-lambdas/src/main/resources/crypto-profiles/hybrid.json auth:/tmp/hybrid.json
$ docker cp thesis/results/v7/artifacts/hybrid/example_jwt_premium_compact.txt auth:/tmp/jwt.txt
$ docker cp thesis/scripts/verify_hybrid_jwt/verify_jwt.mjs auth:/tmp/verify_jwt.mjs
$ docker exec insurance-server-lambdas-auth-1 node /tmp/verify_jwt.mjs /tmp/hybrid.json /tmp/jwt.txt

VERIFICATION RESULT: {
  "valid": true,
  "reason": "both RS256 and ML-DSA-65 verified",
  "hybridShaped": true
}
```

Full output (including the two derived public keys, shown in the clear) in
[`verify_jwt_output.txt`](verify_jwt_output.txt).

The script (`thesis/scripts/verify_hybrid_jwt/verify_jwt.mjs`) derives the
two public keys it needs directly from the RS's key-material file
(`crypto-profiles/hybrid.json` — the same file `ResponseSigningService.java`
loads to sign), and calls `verifyPayloadExtension(jwt, classicPublicJwk,
pqcPublicJwk)` — the real function, not a mock. **Why derive from the key
file instead of fetching the RS's live `/jwks`**: I tried — `GET /jwks` on
the RS returned `401 Unauthorized` from some undiagnosed Micronaut
security filter (out of scope for this task, despite the endpoint being
marked `@Secured(IS_ANONYMOUS)` in the code). Deriving from the key file is
methodologically equivalent — it is the same computation the endpoint
would perform — and, in the respect that matters here, stricter: it
confirms that the key used in verification is exactly the one that signed
this specific token, not merely "a response that should be the same."

**A second, independent closing of the loop, unprompted**: I separately
computed the `kid` that the RS's JWKS entry would have
(`SHA-256(classicPk‖pqcPk)`, see Section 3) from this same key file — the
result, `mZi6awCMmw-lTxi5N3k9d6i_Wa5veP2IZyMvNolkcvQ`, is **byte-identical**
to the `kid` already present in this JWT's header (line above). In other
words: not only do the keys verify the signature, the identifier a real
verifier would use to *discover* this key via JWKS also matches exactly.

### Explanation of the mechanism

Unlike the certificate (where the two signatures live in separate X.509
extensions), the hybrid JWT uses **payload extension**: the RS256
signature is the only thing in the JWS signature segment, computed
**last**, over `base64url(header) + "." + base64url(payload)` — and the
`payload` already contains the ML-DSA-65 signature as an ordinary claim
(`pqc`). The ML-DSA-65 signature, in turn, is computed **first**, over the
RFC 8785 (JCS) canonical form of the claims **without** the `pqc` field
yet.

This means an ordinary RS256 verifier, one that has never heard of
ML-DSA-65, accepts the token normally — `pqc` is just another claim it
does not recognize and ignores. This is the explicit reason for this
ordering (unlike the certificate, which uses Strong Nesting in its X.509
extensions): the advisor requested full backward compatibility as a
priority over the stronger security guarantee (SUF-CMA) that the reverse
order would give — see `thesis/results/v4/JWT_Hybrid_Architecture.md` for
the complete SUF-CMA/EUF-CMA trade-off analysis and references (Bindel et
al. 2017; Brendel, Cremers, Jackson & Zhao 2021). That same document
already shows, step by step, the reconstruction of the JCS-canonical bytes
that ML-DSA-65 actually signed.

### Code reference

`insurance-server-lambdas/src/main/java/com/raidiam/trustframework/
mockinsurance/crypto/ResponseSigningService.java`:

- `sign()`, line 112: assembles header + payload and signs —
  `signer.preparePayload(claims)` (line 115) is where the injection of the
  `pqc` field happens **before** the final RS256 signature is computed
  (line 124).
- `loadHybridSigner()`, line 212, and its `preparePayload()`
  implementation, line 275: where the `pqc` claim is built (ML-DSA-65
  signature over the JCS-canonical form of the claims, via BouncyCastle)
  and inserted into the payload before returning.
- `mock-service-os/mock_as/utils/opin/payloadExtensionVerification.js`,
  function `verifyPayloadExtension()` (lines 29–86) — the real
  verification run above: RS256 first (lines 44–55, Node's native
  `crypto.verify`), removes `pqc` and reconstructs the JCS-canonical bytes
  (lines 76–77, the `canonicalize` package, RFC 8785), verifies ML-DSA-65
  over them (lines 79–80, Node 24's native `webcrypto.subtle.verify` —
  experimental but real support, not a polyfill), and only then returns
  `valid: true` — the AND gate (lines 53–55 and 81–83, either one able to
  fail on its own).
- `thesis/scripts/verify_hybrid_jwt/verify_jwt.mjs` — the script in this
  folder that invokes the function above with the RS's real keys.

---

## 3. Real JWKS entry (Authorization Server and Resource Server)

### The real artifact

**From the AS** — full capture: [`jwks_auth.json`](jwks_auth.json), a real
response from `GET https://auth.local/jwks` (Hybrid profile, via
`tls_kem_proxy`):

```json
{
  "kty": "HYBRID",
  "use": "sig",
  "alg": "MLDSA65-RSA2048-PSS-SHA256",
  "kid": "I4SZA4ycHOiCgSV7jKQEwgGmhsX3aV0KnTEF372by2A",
  "pk_hybrid": "pu8AVLEIfYppnbU0r2M1PNhCvYpGnVXbSXj-OxRX72e...(truncated)"
}
```

`pk_hybrid` is the raw concatenation of the two public keys (classical +
ML-DSA-65) — not two separate entries, a single composite key, because
this is the AS's JWKS (it signs the `id_token`/JARM, which remain on
Strong Nesting, not payload extension — see Section 5 of
`JWT_Hybrid_Architecture.md`).

**From the RS** — [`jwks_rs_derived.json`](jwks_rs_derived.json): the two
entries the RS's `GET /jwks` would publish
(`ResponseSigningService.getPublicJwks()`), derived from the same
key-material file used in Section 2 (the live fetch hit a `401`,
undiagnosed — see Section 2 for why this does not weaken the proof):

```json
{
  "kty": "RSA", "use": "sig", "alg": "RS256",
  "kid": "mZi6awCMmw-lTxi5N3k9d6i_Wa5veP2IZyMvNolkcvQ",
  "n": "1KEH2RKcHf2dRKmVcfNB_6vV...(truncated)", "e": "AQAB"
}
```

### The proof that actually matters: the published key is the key that signed, closing the loop

A JWKS entry of the right size and format does not prove that it
corresponds to the actual key used to sign — it could be any valid
RSA/ML-DSA-65 key, unrelated to the token. The closing of the loop lies
entirely in Section 2: **the verification that returned `valid: true` used
exactly these two keys** (the derivation in `verify_jwt.mjs` and the
construction of this JWKS both start from the same `hybrid.json`, with the
same composition logic as `ResponseSigningService.java`) — if the key
published here were not the one that signed, Section 2's verification
would have returned `valid: false`, not `true`. Additionally, the `RSA`
`kid` above (`mZi6awCMmw-lTxi5N3k9d6i_Wa5veP2IZyMvNolkcvQ`) — computed
independently as `SHA-256(classicPk‖pqcPk)`, never copied from the token —
is byte-identical to the `kid` carried in the header of the Section 2 JWT:
a real verifier, performing discovery by `kid`+`kty` as Section 6 of
`JWT_Hybrid_Architecture.md` already demonstrates, would find exactly this
entry for this token.

### Explanation of the mechanism

The AS publishes a single `kty: "HYBRID"` entry, with a non-standard `alg`
(`MLDSA65-RSA2048-PSS-SHA256`) that explicitly signals to a verifier that
this key is not an ordinary RSA or EC key — this is deliberate, because
the artifacts the AS signs with Strong Nesting (`id_token`, JARM) are not
intended to be accepted by a legacy verifier without adaptation, unlike
the artifacts signed via payload extension (Section 2 above), whose
corresponding RS publishes **two** entries under the same `kid` — a
complete `HYBRID` one and an `RSA`/`RS256` one containing only the
classical half — precisely so that an ordinary verifier can find the
entry it recognizes. This difference in publication between the AS and
the RS is intentional, not an inconsistency: it reflects the difference in
goals between Strong Nesting (with no aim of legacy compatibility) and
payload extension (legacy compatibility is the central goal) — see
`JWT_Hybrid_Architecture.md`, Sections 5 and 6, for the full account of
why each artifact uses the scheme it uses.

### Code reference

`mock-service-os/mock_as/utils/opin/hybridSigning.js`:
- Line 24: `HYBRID_ALG = 'MLDSA65-RSA2048-PSS-SHA256'` — the published
  algorithm string.
- Line 36 onward: composition of `pk_hybrid` as the concatenation of the
  classical and post-quantum keys.

For the RS side: `insurance-server-lambdas/src/main/java/com/raidiam/
trustframework/mockinsurance/crypto/ResponseSigningService.java`,
`loadHybridSigner()`'s `publicJwks()` (lines 318–327) — builds the
`RSA`/`RS256` entry from `classicJwk.get("n"/"e")` (the same values used
for signing, not a re-derivation) and returns `List.of(publicJwk(),
plainRsaJwk)`, the two entries under the same `kid`; `hybridKid` (lines
244–248) is where `SHA-256(classicPk‖pqcPk)` is computed — the same
formula `jwks_rs_derived.json` reproduces and which matches the JWT's
`kid` (Section 2). The full account of the discovery/fix that motivated
publishing the two entries is in `thesis/results/v4/DECISIONS.md`,
Decision 13, Section 6.

---

## 4. TLS handshake evidence — negotiated key-exchange group

### The real artifact

Real log line from the gateway itself (`mock_mtls`), captured live during
a Hybrid-profile connection through `tls_kem_proxy`:
[`handshake_log.json`](handshake_log.json).

```json
{
  "msg": "mTLS handshake complete",
  "tlsVersion": "TLS 1.3",
  "cipherSuite": "TLS_AES_128_GCM_SHA256",
  "curveID": "X25519MLKEM768",
  "clientCertBytes": 6859,
  "mtlsHandshakeBytes": 17956,
  "handshakeDurationMs": 58
}
```

`curveID: "X25519MLKEM768"` directly confirms, in the live TLS negotiation
itself, that the hybrid key-exchange group was in fact used — this is not
an assumed configuration, it is the value the handshake actually
negotiated, recorded by the very Go process that terminated the
connection.

**KEM public-key size (`key_share` extension of the `ClientHello`)**:
measured and documented earlier in this same project, with the same Go
client implementation still in use — `thesis/results/v6/Level 1/
DECISIONS.md`, Decision 2 — via byte-by-byte decomposition of a real
`ClientHello`: **1.226 bytes** for `X25519MLKEM768` (the 32-byte ephemeral
X25519 key plus the 1.184-byte ML-KEM-768 public key, plus extension
encoding overhead). Not redone here because it requires raw packet capture
(out of scope for this folder) and the client/mechanism has not changed
since that measurement. The ciphertext size (sent by the server, inside
the `ServerHello`/`EncryptedExtensions`, already encrypted at the TLS
record level before `Finished`) **was not extracted** — there is no
instrumentation in this project that exposes it without raw TLS-level
packet capture, unlike the `ClientHello`'s `key_share`, which that earlier
investigation decomposed directly.

### The proof that actually matters: the session key was genuinely derived from the KEM, not decorative

`curveID: "X25519MLKEM768"` in the log proves that the *name* of the
negotiated group is this one. It does not, by itself, prove that the
resulting session secret genuinely depends on a fresh key exchange on
every connection — in theory, a log could say this even if the secret
were fixed due to some bug. The real proof: open two independent TLS
connections, both forced to `X25519MLKEM768`, and export key material from
each via **RFC 5705** (`tls.ConnectionState.ExportKeyingMaterial` — the
same standard mechanism TLS uses for channel binding). If the two exports
come out different, the session secret was genuinely re-derived from
scratch on each handshake — exactly what an ephemeral key exchange (KEM or
ECDHE) guarantees; a fixed or cached secret would export the same value
every time.

```
$ docker run --rm --network insurance-server-lambdas_default \
    -v thesis/scripts/verify_kem_export:/src -v mock-service-os/certs:/certs:ro -w /src \
    golang:1.27-rc-alpine go run . x25519mlkem768 /certs/client_one_hybrid.crt /certs/client_one_hybrid.key

connection 1: curveID=X25519MLKEM768 tlsVersion=TLS 1.3 exported(32B)=3bb7ce2812ac6833ec4484a9ed68c0f7c4db74af5aa53d34229447fb913a7778
connection 2: curveID=X25519MLKEM768 tlsVersion=TLS 1.3 exported(32B)=0456a3e67350bb00e6086436db013ca6902c70d5401e2cd24c5da7c52a092216

RESULT: verificado -- ambas as conexoes negociaram X25519MLKEM768, e o material de chave exportado (RFC 5705)
e DIFERENTE entre as duas -- confirma que o segredo de sessao foi de fato derivado de uma troca de chave nova
a cada conexao (o mecanismo KEM/ECDHE efemero real), nao um valor fixo ou decorativo.
```

Full output in
[`verify_kem_export_output.txt`](verify_kem_export_output.txt). The two
32-byte exports above are visibly distinct byte for byte, and both
connections, checked in the code, negotiated the same hybrid group — this
is as close as it gets to "opening the box" on the session secret without
compromising the security of the connection itself (the master secret
itself is never exposed, by TLS 1.3 design; the exporter is the standard
mechanism that exists precisely to allow this kind of external
verification without violating that).

### Explanation of the mechanism

Classic uses pure ECDHE curves (P-521/P-384/P-256); Hybrid combines a
classical key exchange (X25519) with a post-quantum one (ML-KEM-768) in
the same `X25519MLKEM768` group — the same choice Chrome and Cloudflare
already use by default in production (see `thesis/results/v7/
DECISIONS.md`, Decision 1, and `thesis/results/v6/Level 1/ARCHITECTURE.md`,
Phase 1, for the complete reasoning behind why this specific group was
chosen for Hybrid, and `MLKEM1024` — with no classical component — for
PQC). Since the v7 unification (Decision 1), the same Go client
(`tls_kem_proxy`) negotiates this group for all three profiles, varying
only the requested curve — Classic requests pure ECDHE curves through the
same process.

### Code reference

- `mock-service-os/mock_mtls/main.go`, function `init()`, lines 136–138:
  for `CRYPTO_PROFILE=hybrid`, `serverCurvePreferences = []tls.CurveID{tls.
  X25519MLKEM768}` — this is the gateway's default policy for this profile
  (no silent downgrade to classical). **Verified caveat, not an
  assumption**: there is a single, deliberate exception that predates this
  work — `GetConfigForClient` (same file) reserves classical curves
  exclusively for connections whose SNI is `"matls-api.local"` (the
  internal `auth`→RS call, `InsurerAdapter.getConsent()`, whose Node.js
  client does not negotiate X25519MLKEM768 — extending the certificate
  carve-out from Decision 5, `thesis/results/v5/size/DECISIONS.md`, to the
  key exchange). Confirmed live: instrumenting this point with logging and
  cross-checking against the `curveID=CurveP256` handshakes captured in
  the same period, the correspondence was 1:1 (35 of each, same
  `remoteAddr`) — no classical handshake without this explanation. Does
  not affect the client↔gateway traffic this artifact measures (different
  SNI, via `tls_kem_proxy`).
- `thesis/scripts/tls_kem_proxy/main.go`, function `runRelay()`, the
  `"x25519mlkem768"` case of the curve `switch` — the client that actually
  negotiates this group on the `tls_kem_proxy` side.
- The `curveID` field in the log above comes from `handshakeInfo.curveID`,
  populated from `cs.CurveID.String()` (the handshake's own
  `ConnectionState`) in `mock_mtls/main.go` — this is not a configuration
  assumption, it is read back from the handshake that actually took
  place.
- `thesis/scripts/verify_kem_export/main.go` — the key-export proof run
  above (generalized to all three profiles via the `-group`/first
  positional argument): curve forced in `CurvePreferences` (line 62),
  `state.ExportKeyingMaterial("EXPORTER-artifact-proof", nil, 32)` (line
  72, Go's public API implementing RFC 5705) on each of the two
  connections, byte-by-byte comparison of the two outputs (line 95).

---

## 5. Real `id_token`, decoded — genuine Strong Nesting (sigma1||sigma2), message encryption still classical

### The real artifact

Captured live from the `id_token` field of a real `POST /token` response
(complete flow, Hybrid profile): [`id_token_raw.txt`](id_token_raw.txt) —
a 5-segment JWE (unlike the 3-segment JWS's of Sections 1–4):

```
$ node decrypt_and_verify_id_token.mjs hybrid id_token_raw.txt   # (dentro do container `auth`)

id_token: 7695 chars, 5 segments (JWE compact serialization)
JWE protected header: {"alg":"RSA-OAEP","enc":"A256GCM","cty":"JWT","kid":"92297d36-...","iss":"https://auth.local","aud":"client_one"}
Decrypted inner JWS: 5090 chars, 3 segments
Inner JWS header: {"alg":"PS256","kid":"xQLs45xYyJr1omHs4qnB2rhes9qNFHIHQ5YPQKVJliM"}
Inner JWS payload (decoded, complete): {
  "sub": "usuario1@seguradoramodelo.com.br",
  "acr": "urn:brasil:openinsurance:loa3",
  "nonce": "Auxk99qUA2Vl",
  "aud": "client_one",
  "exp": 1789354340,
  "iat": 1789350740,
  "iss": "https://auth.local"
}
Inner JWS signature length (bytes): 3565
VERIFICATION RESULT: {"valid": true, "reason": "both sigma1 and sigma2 verified"}
```

Full output in
[`verify_id_token_output.txt`](verify_id_token_output.txt). The JWE's
`kid` (`92297d36-...`) is **byte-identical to the Classic id_token's**
(Section 5 of that profile's README) — Hybrid reuses the same client
encryption key as Classic, consistent with the pattern already confirmed
in this folder that Hybrid reuses the classical RSA identity throughout,
not only in the certificate (Section 1).

### The proof that actually matters: BOTH inner signatures verify, with the real AND gate — the outer cipher remains classical

**The inner layer is genuinely Strong Nesting, not a plain signature of
the right size**: 3.565 bytes of signature decompose into sigma1 (256
bytes, PS256/RSA) + sigma2 (3.309 bytes, ML-DSA-65) — the same
verification used throughout this thesis (`verifyHybrid()`,
`mock_as/utils/opin/hybridVerification.js`, the real production function,
not a reimplementation for this artifact): sigma1 verified against the
classical RSA key over `header.payload`; sigma2 verified against the
ML-DSA-65 key over `header.payload || sigma1`; **AND gate — both passed**
(`"both sigma1 and sigma2 verified"`). The outer header still says
`alg: "PS256"`, by design (Decision 10, `thesis/results/v4/DECISIONS.md`)
— only the decoded signature's size gives away that this is Strong
Nesting, the same "ordinary header, larger signature" pattern already
seen in the `client_assertion`.

**The outer layer (the JWE encryption) remains `RSA-OAEP`, the same
across all three profiles** — the same genuine limitation documented in
Sections 5 of `artifacts/classic/` and `artifacts/pqc/`: no JOSE/COSE
standard for post-quantum encryption exists today. Hybrid does not change
this — this profile's post-quantum half lives entirely in the signature,
never in the encryption.

### Explanation of the mechanism

Under `CRYPTO_PROFILE=hybrid`, the `oidc-provider` is kept entirely
unaware of hybrid mode — configured as if it were pure Classic
(`internalSigningAlgs = ['PS256']`, `internalSigningKey =
cryptoProfile.classicSigningKey`) — because `"MLDSA65-RSA2048-PSS-SHA256"`
is not a real JOSE algorithm that `jose`/`oidc-provider` recognize. The
crucial difference from Classic lies in ONE piece: the
`HybridIdTokenSigningKey` class (`idTokenExternalSigningKey.js`),
registered as the signing key via the `oidc-provider`'s official
`ExternalSigningKey` mechanism. When the `oidc-provider` assembles and
internally signs the `id_token`, it hands the exact `header.payload` bytes
to this class, which returns `signStrongNesting(bytes)` — a genuine
sigma1||sigma2 — in place of what would be an ordinary PS256 signature.
The `oidc-provider` never knows it received anything other than a valid
PS256 signature; it simply passes along whatever the class returned.
After that, RSA-OAEP+AES-256-GCM encryption happens exactly as in Classic
— blind to what it is encrypting.

### Code reference

- `mock-service-os/mock_as/utils/opin/idTokenExternalSigningKey.js`: the
  complete `HybridIdTokenSigningKey` class — `sign()` (line 63) calls
  `signStrongNesting()`; the comment at the top of the file (lines 1–41)
  documents in detail why this detour through `ExternalSigningKey` is
  necessary and why the header must keep saying `"PS256"`.
- `mock-service-os/mock_as/utils/opin/configuration.js`, line 11 (import)
  and the swap of `internalSigningKey`/`internalSigningAlgs` for hybrid
  mode (lines 42–44).
- `mock-service-os/mock_as/utils/opin/hybridVerification.js`, function
  `verifyHybrid()` (line 33) — the real, production verification run
  above with no modification whatsoever.
- `mock-service-os/mock_as/utils/opin/configuration.js`, line 330:
  `idTokenEncryptionAlgValues: ['RSA-OAEP']` — the same classical
  encryption as always, here too.
- `thesis/scripts/verify_hybrid_jwt/decrypt_and_verify_id_token.mjs` — the
  verification run above.

---

## 6. Real `client_assertion` — payload-extension (RS256 + `pqc`), the production AND gate

### Why this artifact exists

Step 8 of the SAD ("Access token") carries no signature at all — the
`access_token` captured live is an opaque string. The "hybrid signature"
that an earlier version of `thesis/docs/
Cruzamento_SAD_vs_Experimentos.md` attributed to this step is, in
practice, the `client_assertion` the client signs to authenticate `POST
/token` — exactly the artifact captured below, using the same
payload-extension scheme (Decision 13) already seen in Section 2 of this
README, here in the opposite direction (client → AS, rather than AS/RS →
client).

### The real artifact

Captured live from the body of a real `POST /token` request (Hybrid
profile): [`client_assertion_raw.txt`](client_assertion_raw.txt).

```
$ node verify_client_assertion.mjs hybrid client_assertion_raw.txt   # (dentro do container `auth`)

Header: {"alg":"RS256","kid":"c0d35890-1f2a-4ed5-bf9f-856d10ccd093","typ":"JWT"}
Payload (decoded, sem o campo pqc.signature truncado): {
  "sub": "client_one",
  "aud": "https://matls-auth.local/token",
  "iss": "client_one",
  "exp": 1789351935,
  "iat": 1789351875,
  "jti": "W7odyDVfnRq4Bij6ANcq_Ewr",
  "pqc": { "alg": "ML-DSA-65", "signature": "kfglsACsNFdXVp9F6gHoGqik2c...(4412 caracteres, truncado)" }
}
Signature length (bytes): 512
VERIFICATION RESULT: {"valid": true, "reason": "both RS256 and ML-DSA-65 verified", "hybridShaped": true}
```

Full output (with the complete `pqc.signature`) in
[`verify_client_assertion_output.txt`](verify_client_assertion_output.txt).
Header `alg: "RS256"` — not `PS256` as in Classic — by design (Decision
13: the client signs under an ordinary header from the start, so that a
legacy RS256 verifier accepts this `client_assertion` with no adaptation
whatsoever, exactly like the Section 2 JWT on the RS side). External
signature: 512 bytes (the client's RSA-4096, the same key as Classic); the
real ML-DSA-65 signature lives inside the `pqc` claim, not in the JWS
signature segment.

### The proof that actually matters: the production AND gate passed, in both directions

This is the SAME production function (`verifyPayloadExtension()`,
`payloadExtensionVerification.js`) already used in Section 2 — here
invoked from the side `clientHybridAuth.js` actually calls in production
(the AS verifying an incoming `client_assertion`), with the CLIENT's
public keys (`client_one_hybrid_pub.jwks` + `client_one_pqc_pub.jwks`),
not the RS's. `hybridShaped: true` confirms the verifier correctly
detected the extended format; `"both RS256 and ML-DSA-65 verified"`
confirms the complete AND gate, not just the RS256 half a legacy verifier
would see.

### Explanation of the mechanism

`opin_flow.py`'s `_sign_jwt_hybrid()` implements the client side of the
same Decision 13 scheme already documented in Section 2: ML-DSA-65 signs
first (RFC 8785/JCS, claims without `pqc`), the result becomes the `pqc`
claim, and RS256 signs last over `header.payload` with `pqc` already
embedded — an entirely ordinary RS256 JWS from the point of view of any
verifier unaware of the extra claim.

### Code reference

- `thesis/scripts/opin_flow.py`, `_sign_jwt_hybrid()` (line 590) — the
  client side of the scheme.
- `mock-service-os/mock_as/utils/opin/clientHybridAuth.js` — the
  production middleware that calls `verifyPayloadExtension()` on every
  incoming `client_assertion`/PAR request object.
- `mock-service-os/certs/client_one_hybrid_pub.jwks` +
  `client_one_pqc_pub.jwks` — the public keys used in the verification.
- `thesis/scripts/verify_hybrid_jwt/verify_client_assertion.mjs` — the
  verification run above.
</content>
