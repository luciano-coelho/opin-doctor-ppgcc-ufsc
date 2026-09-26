# Real artifacts — PQC profile

Verifiable proof of implementation for the PQC profile, following the same
standard as `artifacts/hybrid/` and `artifacts/classic/`: each artifact
comes with the real capture, the mechanism explanation, and the exact
source-code reference. Here the claim to be proven is twofold: (1) that
the post-quantum material (ML-DSA-65 in the certificate/JWT, MLKEM1024 in
the handshake) is genuine and functional, not just a field of the right
size; and (2) that, where the design is deliberately mixed (the
certificate, Step 3.1 — only the subject's key migrates to PQC, the CA
remains RSA), that mixture is exactly what was decided, not an accidental,
incomplete PQC migration — and where the design is pure for external
traffic (the client-to-gateway TLS handshake), it really is pure, with no
classical component (X25519 or any ECDHE) silently mixed into that traffic
specifically (see the caveat about internal auth→RS traffic in Section 4).

All data below was captured live under `CRYPTO_PROFILE=pqc`, on the same
v7 pipeline (`tls_kem_proxy`, Decision 1) used for the size and latency
batch.

---

## 1. Subject certificate (`client_one_pqc.crt`) — ML-DSA-65 key, RSA issuer

### The real artifact

Raw file: [`client_one_pqc.crt`](client_one_pqc.crt). Decoding via
`openssl x509 -text -noout`:
[`client_one_pqc.crt.txt`](client_one_pqc.crt.txt).

```
Signature Algorithm: sha256WithRSAEncryption
Issuer: CN=ca
Subject: CN=client_one_pqc, ...
Subject Public Key Info:
    Public Key Algorithm: 2.16.840.1.101.3.4.3.18
    Unable to load Public Key
50F50000:error:03000072:digital envelope routines:X509_PUBKEY_get0:decode error:...
...
Signature Algorithm: sha256WithRSAEncryption
```

Two structural observations, both intentional: **the certificate's
signature (issuer) is classical RSA**, not ML-DSA-65 — the certificate is
issued by the same `ca.crt`/`ca.key` CA that signs the Classic certificate
(`artifacts/classic/`); and **OpenSSL recognizes the subject key's OID
(`2.16.840.1.101.3.4.3.18`, ML-DSA-65/FIPS 204) but cannot decode it** —
exactly the same situation (and the same reason) already explained in
`artifacts/hybrid/README.md`, Section 1: the OpenSSL 3.x in this
environment does not have an ML-DSA-65 provider loaded, so it prints the
OID correctly (the ASN.1 structure is parsed) but stops exactly there — it
does not decode the key's contents, and this is expected, not a sign that
the key is invalid or the wrong size.

### The proof that actually matters: the subject's ML-DSA-65 key is real and functional, the issuer is classically verifiable

As with the hybrid certificate, this OpenSSL limitation does not prevent a
real cryptographic proof — it only requires a tool that understands
ML-DSA-65 natively (Go 1.27rc2, `crypto/mldsa`, FIPS 204). The proof here
is the most direct one possible: **sign a fresh challenge with the
subject's private key and verify it against the public key the certificate
itself declares** — if this works, the `SubjectPublicKeyInfo` is genuinely
the other half of the key pair in `client_one_pqc.key`, not just a blob of
the right size:

```
$ docker run --rm -v "<repo>/mock-service-os/certs:/certs" -w /certs golang:1.27-rc-alpine \
    sh -c "go build -o /tmp/certtool . && /tmp/certtool -verify-pqc-cert client_one_pqc"

Subject public key algorithm OID: 2.16.840.1.101.3.4.3.18 (ML-DSA-65, FIPS 204)
SubjectPublicKeyInfo: 1952 bytes, first 16 as hex: 07b8d33d7a261d017ef2f6b70ceac247...
Certificate signature algorithm (issuer signature): SHA256-RSA
Challenge signed with client_one_pqc.key, signature 3309 bytes, first 16 as hex: fc0ab8da913c1c66bc1d712ee3a1b113...
RESULT: verificado -- a assinatura ML-DSA-65 do desafio e valida contra a SubjectPublicKeyInfo de
/certs/client_one_pqc.crt -- o par de chaves ML-DSA-65 do certificado e real e funcional, nao apenas
um campo do tamanho certo. A propria assinatura do certificado (issuer) permanece classica (SHA256-RSA),
por design (Etapa 3.1): so a chave do titular migra para PQC, a CA nao.
```

Full output in
[`verify_pqc_cert_output.txt`](verify_pqc_cert_output.txt). 1.952 bytes is
exactly the size of an ML-DSA-65 public key (FIPS 204, parameter set 65);
3.309 bytes is exactly the size of an ML-DSA-65 signature — both matching
the sizes already seen in the hybrid certificate and in the JWT of Section
2 below, which is itself a cross-check (the same algorithm producing the
same sizes in three independent places in the system).

**The second half of the proof** — that the issuer signature actually
verifies — uses the usual classical tool, since this signature is plain
RSA:

```
$ openssl verify -CAfile ca.crt client_one_pqc.crt
client_one_pqc.crt: OK
```

Full DER: **2.953 bytes** (versus 1.494 for Classic) — the 1.459-byte
difference is essentially the cost of embedding an ML-DSA-65
SubjectPublicKeyInfo (1.952 bytes of key, plus the `AlgorithmIdentifier`/
ASN.1 overhead) in place of an ordinary RSA-4096 key, with no additional
extension — confirming that this certificate is not a "disguised" hybrid:
it has neither `AltSignatureValue` nor `SubjectAltPublicKeyInfo`, just a
different SPKI.

### Mechanism explanation

This is the deliberate design of Step 3.1 (mixing a classical issuer with
a post-quantum subject key is ordinary X.509 — the two fields are
independent): only the subject's identity migrates to PQC, while the CA
remains unchanged and classically verifiable by any pre-existing software.
This differs from the hybrid certificate (`artifacts/hybrid/`), which
preserves the original RSA signature AND adds a second ML-DSA-65 signature
over the same certificate — here there is no second signature: the
subject's key simply IS ML-DSA-65, period, and the CA never needed to
learn how to sign with this algorithm to issue this certificate.

### Code reference

`mock-service-os/certs/main.go`:
- `generateClientCertPQC()`, lines 358–432 — generates the ML-DSA-65 key
  (`mldsa.GenerateKey(mldsa.MLDSA65())`, line 371) and creates the
  certificate signing with the **RSA** `caKey` (`x509.CreateCertificate(...,
  key.Public(), caKey)`, line 411–417) — the public-key parameter is the
  new ML-DSA-65 key, while the signing-key parameter remains the existing
  RSA CA. The function's own comment (lines 358–361) documents this choice
  explicitly.
- `verifyPQCCert()`, added for this artifact (same file) — the
  verification from the Section above: signs a challenge with the private
  key from disk and verifies it against the `SubjectPublicKeyInfo` that
  `x509.ParseCertificate` has already natively decoded (the Go 1.27rc2
  parser recognizes the ML-DSA-65 OID and returns a `*mldsa.PublicKey`
  directly in `cert.PublicKey`).

---

## 2. Real, decoded JWT (RS response, `GET .../premium`) — pure ML-DSA-65

### The real artifact

Full token: [`example_jwt_premium_compact.txt`](example_jwt_premium_compact.txt)
/ [`example_jwt_premium.txt`](example_jwt_premium.txt) (decoded).

**Header:**
```json
{"alg": "ML-DSA-65", "kid": "5226750c-4adb-4d00-be74-c6a38845622d", "typ": "JWT"}
```

**Payload (top-level keys):** `data`, `links`, `meta` — with no embedded
RSA/classical component whatsoever (neither a second signature nor an
extra claim like the `pqc` claim in the hybrid scheme). Total: 5.559
characters; the signature segment alone is 4.412 characters (3.309 bytes
decoded) — most of the token's size is the ML-DSA-65 signature itself.

### The proof that actually matters: the ML-DSA-65 signature genuinely verifies, on its own

```
$ node verify_pqc_jwt.mjs pqc.json example_jwt_premium_compact.txt   # (dentro do container `auth`)

ML-DSA-65 public JWK, derivado de pqc.json via parsing do X.509 SPKI: {"kty":"AKP","alg":"ML-DSA-65",
  "use":"sig","kid":"5226750c-4adb-4d00-be74-c6a38845622d","pub":"nRsKrNTf1cz2CJiG7ZwUiUpu...(truncado)"}
Header: {"alg":"ML-DSA-65","kid":"5226750c-4adb-4d00-be74-c6a38845622d","typ":"JWT"}
Signing input length (bytes): 1146   Signature length (bytes): 3309

VERIFICATION RESULT: {
  "valid": true,
  "reason": "ML-DSA-65 verified",
  "hasClassicComponent": false,
  "payloadTopLevelKeys": ["data", "links", "meta"]
}
```

Full output in [`verify_jwt_output.txt`](verify_jwt_output.txt). The
script (`thesis/scripts/verify_hybrid_jwt/verify_pqc_jwt.mjs`, written for
this profile) uses Node 24's native
`webcrypto.subtle.verify({name:'ML-DSA-65'})` API — the same primitive
`payloadExtensionVerification.js` uses for the PQC half of the hybrid
scheme (`artifacts/hybrid/README.md`, Section 2) — over the standard JWS
signing input (`header_b64 + "." + payload_b64`, 1.146 ASCII bytes in this
token), verifying against the public key derived directly from the RS's
key-material file (`crypto-profiles/pqc.json`). Unlike Hybrid, there is no
two-signature "AND gate" here: a single ML-DSA-65 signature covers the
entire token, and that is exactly what the verification confirms
(`hasClassicComponent: false`).

### Mechanism explanation

`ResponseSigningService.sign()` assembles the JWS in the most ordinary way
possible — header + payload + `signingInput = headerB64 + "." +
payloadB64` — and signs that `signingInput` once with
`loadMlDsa65Signer()`. There is no `preparePayload()` override with special
logic (that mechanism exists only in the hybrid signer, for the `pqc`
claim): the interface's `default` returns the claims unchanged, so this is
structurally the simplest JWS among the three profiles — only the header's
algorithm changes.

### Code reference

`insurance-server-lambdas/.../crypto/ResponseSigningService.java`:
- `sign()`, lines 112–126 — assembles `signingInput` and calls
  `signer.signToBase64Url(signingInput)`.
- `loadMlDsa65Signer()`, lines 164–197 — loads `pqc.json`, signs via
  `Signature.getInstance("ML-DSA", "BC")` (BouncyCastle).
- `thesis/scripts/verify_hybrid_jwt/verify_pqc_jwt.mjs` — the verification
  run above.

---

## 3. Real JWKS entry — two distinct PQC identities (AS and RS), the same one that signed

### The real artifact

**From the AS** — full capture: [`jwks_auth.json`](jwks_auth.json), the
real response to `GET https://auth.local/jwks` (PQC profile, via
`tls_kem_proxy`): the signing entry `kty: "AKP"`/`alg: "ML-DSA-65"` (`kid`
`QiYeUNBZXaKsrgR_...`), plus the encryption entry `kty: "RSA"`/`RSA-OAEP`
(unchanged across profiles, as already seen in Classic/Hybrid). This `kid`
is **different** from the `kid` of the JWT in Section 2 — as expected: the
AS and the RS are two services with independent PQC key material (the AS
signs its own artifacts, such as the `id_token`; the RS signs the API
responses this document uses as an example). Publishing this key here does
not close the loop for the JWT in Section 2 — it only confirms that the AS
also publishes its own ML-DSA-65 key in the JWKS format (`kty: "AKP"`)
that IANA/JOSE registers for ML-DSA.

**From the RS** — [`jwks_rs_derived.json`](jwks_rs_derived.json): the
entry the RS's `GET /jwks` would publish, derived from the SAME
key-material file (`pqc.json`) used to verify the JWT in Section 2 (the
live fetch hit a `401`, the same undiagnosed cause already recorded in
`artifacts/hybrid/README.md`, Section 2):

```json
{"kty": "AKP", "alg": "ML-DSA-65", "use": "sig", "kid": "5226750c-4adb-4d00-be74-c6a38845622d", "pub": "nRsKrNTf1cz2CJiG7ZwUiUpu...(truncado)"}
```

### The proof that actually matters: the kid and the key match exactly what signed

Two direct checks, neither of them by visual inspection:

1. **Identical `kid`**: `5226750c-4adb-4d00-be74-c6a38845622d` — the exact
   same value as the header of the JWT verified in Section 2, not a
   format coincidence, a literal UUID value matching byte for byte.
2. **`pub` is the same key that verified**: `jwks_rs_derived.json` and
   `verify_pqc_jwt.mjs` (Section 2) derive the `pub` field from the same
   file (`pqc.json`), with the same extraction code
   (`createPublicKey({key: spkiDer, format:'der', type:'spki'})`) — the
   verification in Section 2 already returned `valid: true` using exactly
   this key; if the key published here were different from the one that
   signed, that verification would have failed, not passed.

Closing the loop here is more direct than in Hybrid (Section 3 of
`artifacts/hybrid/`): there is no composite hash
(`SHA-256(classicPk‖pqcPk)`) to recompute — the `kid` is copied verbatim
from `pqc.json`, and it is the same on both sides (signing and
publication) by construction.

### Mechanism explanation

`loadMlDsa65Signer()` uses the SAME `kid` variable (read once from
`pqc.json`) both to sign (`kid()`, used in the JWT header) and to publish
(`publicJwk()`, used in the JWKS) — there are no two independent places
that could diverge; it is literally the same string reference inside the
same `JwsSigner` object.

### Code reference

`insurance-server-lambdas/.../crypto/ResponseSigningService.java`:
- Line 166: `String kid = (String) json.get("kid")` — read once from
  `pqc.json`.
- Line 180: `public String kid() { return kid; }` — used in the JWT header
  (via `sign()`, line 119).
- Lines 189–196: `publicJwk()` — uses the SAME `kid` variable (line 193)
  when assembling the JWKS entry.
- `thesis/scripts/verify_hybrid_jwt/derive_pqc_jwks.mjs` — derives
  `jwks_rs_derived.json` above.

---

## 4. TLS handshake evidence — pure MLKEM1024 on external traffic, with a deliberate, documented internal exception

### The real artifact

Real gateway log line, PQC profile, via `tls_kem_proxy`:
[`handshake_log.json`](handshake_log.json).

```json
{
  "msg": "mTLS handshake complete",
  "tlsVersion": "TLS 1.3",
  "cipherSuite": "TLS_AES_128_GCM_SHA256",
  "curveID": "MLKEM1024",
  "clientCertBytes": 2953,
  "mtlsHandshakeBytes": 16669,
  "handshakeDurationMs": 56
}
```

`clientCertBytes: 2953` matches exactly the DER of the certificate from
Section 1 (2.953 bytes) — confirming that this log line corresponds to the
real connection that presented `client_one_pqc.crt`.

### The proof that actually matters: confirming that NO classical component entered the negotiated group, and that the session is fresh

```
$ docker run --rm --network insurance-server-lambdas_default \
    -v thesis/scripts/verify_kem_export:/src -v mock-service-os/certs:/certs:ro -w /src \
    golang:1.27-rc-alpine go run . mlkem1024 /certs/client_one_pqc.crt /certs/client_one_pqc.key

connection 1: curveID=MLKEM1024 tlsVersion=TLS 1.3 exported(32B)=d2d7b3bd7714b426b128d2c0500ae2b1b965f4e3387dd84234cdf7228a6ed529
connection 2: curveID=MLKEM1024 tlsVersion=TLS 1.3 exported(32B)=a1101913ec7b0234d386503186a9bd68a73c612803ad236743cfdfc4e654dc16

RESULT: verificado -- ambas as conexoes negociaram MLKEM1024 (grupo=mlkem1024), e o material de chave
exportado (RFC 5705) e DIFERENTE entre as duas -- confirma que o segredo de sessao foi de fato derivado
de uma troca de chave nova a cada conexao, nao um valor fixo ou decorativo.
```

Full output in
[`verify_kem_export_output.txt`](verify_kem_export_output.txt). The same
tool used for Hybrid and Classic runs here with the `mlkem1024` argument:
it requires the negotiated `curveID` to be EXACTLY `"MLKEM1024"` on both
connections — if the handshake had negotiated `X25519MLKEM768` (the
classical+PQC hybrid group of the Hybrid profile) or any purely classical
curve, the program would have ended in `RESULT: FAIL`, not succeeded.
`MLKEM1024`, unlike `X25519MLKEM768`, has NO ECDHE component mixed into
the group's name itself (defined in the Internet-Draft
`draft-ietf-tls-mlkem`, IETF TLS WG, not yet published as an RFC) — it is
not a "hybrid with half PQC," it is the pure KEM. The key-material export
(RFC 5705) additionally confirms that the session secret is genuinely new
for each connection, via an ephemeral KEM, not a fixed value.

### Mechanism explanation

`CRYPTO_PROFILE=pqc` makes `mock_mtls`'s `init()` override
`serverCurvePreferences` to contain only `tls.MLKEM1024` — no classical
curve appears in the server's default preference list. The
`tls_kem_proxy` (v7 Decision 1) requests exactly this group on the client
side via `-curve mlkem1024`, using Go 1.27rc2's native support for
MLKEM1024 (which Python's TLS/OpenSSL stack, used by the rest of
`opin_flow.py`, still does not negotiate — hence the proxy's existence).

**A verified caveat, not an assumption**: this restriction is not
absolute for 100% of the traffic that touches this gateway — there is an
internal exception, deliberate and pre-existing to this work, for exactly
one call: `GetConfigForClient` (`mock_mtls/main.go`) intercepts every
connection's `ClientHelloInfo` and, when `hello.ServerName ==
"matls-api.local"`, returns a separate `tls.Config` with
`CurvePreferences` fixed to classical curves — this is the route
`auth`'s `InsurerAdapter.getConsent()` uses to check consent with the RS
(Node does not negotiate MLKEM1024/X25519MLKEM768), extending the same
classical-certificate carve-out already recorded in Decision 5
(`thesis/results/v5/size/DECISIONS.md`) to the key-exchange dimension as
well. **Confirmed live**, not assumed: I instrumented
`GetConfigForClient` with a log (`slog.Info`, printing `hello.ServerName` +
`remoteAddr`) and cross-checked, connection by connection, against the
`"mTLS handshake complete"` lines from the same period — **the 35
applications of the carve-out and the 35 captured `curveID=CurveP256`
handshakes match 1:1, same `remoteAddr`, with no classical handshake left
unaccounted for**. In other words: under `CRYPTO_PROFILE=pqc`/`hybrid`,
the ONLY source of classical key exchange on this gateway is this internal
route, specifically tied to that SNI — not a policy-enforcement failure,
and not something that affects the client↔gateway traffic this artifact
measures (a different SNI, `AUTH_CONNECT_HOST`/`API_CONNECT_HOST` via
`tls_kem_proxy`, never `matls-api.local` directly).

### Code reference

- `mock-service-os/mock_mtls/main.go`, line ~114: `init()` overriding
  `serverCurvePreferences` to `[]tls.CurveID{tls.MLKEM1024}` under
  `CRYPTO_PROFILE=pqc`.
- `thesis/scripts/opin_flow.py`: `TLS_KEM_PROXY_CURVE_BY_PROFILE = {"pqc":
  "mlkem1024", ...}` — maps the profile to the proxy's `-curve` argument.
- `thesis/scripts/tls_kem_proxy/main.go`, the `"mlkem1024"` case of the
  curve `switch`.
- `thesis/scripts/verify_kem_export/main.go` — the tool used above, here
  invoked with `mlkem1024`.
- `mock-service-os/mock_mtls/main.go`, `GetConfigForClient` — the internal
  SNI-based exception documented in the caveat above, with the code
  comment updated to make it explicit alongside the "no silent fallback"
  policy it carves an exception into.

---

## 5. Real, decoded `id_token` — pure ML-DSA-65 signature, message encryption still classical, confirmed impossible to migrate today

### The real artifact

Captured live from the `id_token` field of a real `POST /token` response
(full flow, PQC profile): [`id_token_raw.txt`](id_token_raw.txt) — a
5-segment JWE, not a 3-segment JWS (unlike the artifacts in Sections
1–4):

```
$ node decrypt_and_verify_id_token.mjs pqc id_token_raw.txt   # (dentro do container `auth`)

id_token: 7246 chars, 5 segments (JWE compact serialization)
JWE protected header: {"alg":"RSA-OAEP","enc":"A256GCM","cty":"JWT","kid":"83e830ad-...","iss":"https://auth.local","aud":"client_one"}
Decrypted inner JWS: 4753 chars, 3 segments
Inner JWS header: {"alg":"ML-DSA-65","kid":"QiYeUNBZXaKsrgR_BfvZfQJHxyPo9mez54AgoBeB9VU"}
Inner JWS payload (decoded, complete): {
  "sub": "usuario1@seguradoramodelo.com.br",
  "acr": "urn:brasil:openinsurance:loa3",
  "nonce": "Vq3qV-2HxtFs",
  "aud": "client_one",
  "exp": 1789354547,
  "iat": 1789350947,
  "iss": "https://auth.local"
}
Inner JWS signature length (bytes): 3309
VERIFICATION RESULT: {"valid": true, "reason": "ML-DSA-65 verified"}
```

Full output in
[`verify_id_token_output.txt`](verify_id_token_output.txt).

### The proof that actually matters: the inner signature is genuinely pure ML-DSA-65; the outer cipher remains RSA-OAEP, and neither fact should be softened

**The part that migrated, genuinely migrated**: the inner signature of
the `id_token`, once the JWE is decrypted, is pure ML-DSA-65 (3.309 bytes,
verified via `webcrypto.subtle.verify`) — with no RSA component mixed in,
exactly like the JWT in Section 2 and the certificate in Section 1 of this
same profile.

**The part that did not migrate, and cannot migrate today, is the JWE's
encryption**: `alg: "RSA-OAEP"` — the same one that appears in Classic and
Hybrid, without exception. This is not a gap specific to this prototype
under PQC — it is a real limit of the state of the art: there is currently
no JOSE/COSE standard for post-quantum (ML-KEM) encryption of tokens; the
draft that existed was withdrawn from the IETF working group, and
libraries such as `jose` have no support for it at all. **This is the
most direct and concrete evidence of this finding in the entire
`artifacts/` folder**: an `id_token` genuinely PQC from the neck down
(signature), yet still entirely classical in the layer that wraps it
(encryption) — not by this project's design choice, but because there is
no available alternative to choose. See
`thesis/docs/Cruzamento_SAD_vs_Experimentos.md` for the complete survey of
this point against the SAD.

### Mechanism explanation

Just as in Classic, `oidc-provider` assembles and signs the `id_token`
internally and encrypts it (RSA-OAEP + AES-256-GCM) before the response
leaves the process. Under `CRYPTO_PROFILE=pqc`, `internalSigningAlgs`/
`internalSigningKey` point to the profile's ML-DSA-65 key (`pqc.json`'s
`signingKey`, `kty: "AKP"`) — and, unlike Hybrid (Section 5 of that
profile's README), **it needs no `ExternalSigningKey` mechanism at all**:
this environment's `jose`/`oidc-provider` already recognizes
`"ML-DSA-65"` as a valid signing algorithm natively (the same native Node
24 support already used in Section 2 of this folder and of the `hybrid/`
folder) — only the combination of TWO algorithms into a single `alg`
string (Hybrid's case) requires the workaround.

The encryption public key used here is the one `client_one_pqc.jwks`
registers (a `kid` different from Classic/Hybrid — each profile has its
own encryption key registered for the client, confirmed by comparing the
`kid`s of the three `id_token`s captured in this folder).

### Code reference

- `mock-service-os/mock_as/utils/opin/configuration.js`, line 43:
  `internalSigningAlgs = isHybrid ? ['PS256'] : cryptoProfile.signingAlgs`
  — for `pqc`, resolves to `['ML-DSA-65']`, read from `pqc.json`.
- `mock-service-os/mock_as/utils/opin/configuration.js`, line 330:
  `idTokenEncryptionAlgValues: ['RSA-OAEP']` — the same classical
  encryption, for any profile.
- `mock-service-os/certs/client_one_pqc.jwks`: the client's RSA-OAEP key
  pair for this profile (`use: "enc"`).
- `thesis/scripts/verify_hybrid_jwt/decrypt_and_verify_id_token.mjs` — the
  verification run above.

---

## 6. Real `client_assertion` — pure ML-DSA-65 authenticating the client

### Why this artifact exists

SAD step 8 ("Access token") is not signed — the `access_token` captured
live is an opaque string, with no JWT structure
(`certificateBoundAccessTokens: true`, with no `formats.AccessToken`
configured). The real ML-DSA-65 signature that authenticates the PQC
client when requesting a token lives in the `client_assertion`, not in the
`access_token` itself — see
`thesis/docs/Cruzamento_SAD_vs_Experimentos.md` for the complete
correction of this classification.

### The real artifact

Captured live from the body of a real `POST /token` request (PQC
profile): [`client_assertion_raw.txt`](client_assertion_raw.txt).

```
$ node verify_client_assertion.mjs pqc client_assertion_raw.txt   # (dentro do container `auth`)

Header: {"kid":"fbHr8nZT_Z048MGn6p25MDa8YVLmp-teybDNaQK-ADI","alg":"ML-DSA-65"}
Payload (decoded, complete): {
  "sub": "client_one",
  "aud": "https://matls-auth.local/token",
  "iss": "client_one",
  "exp": 1789351810,
  "iat": 1789351750,
  "jti": "Sf-H8rQ8kWgZ973VkKZuIUq9"
}
Signature length (bytes): 3309
VERIFICATION RESULT: {"valid": true, "reason": "ML-DSA-65 verified"}
```

Full output in
[`verify_client_assertion_output.txt`](verify_client_assertion_output.txt).
Pure ML-DSA-65 signature (3.309 bytes, the same size already seen in
Sections 2 and 5 of this profile), with no RSA component — the PQC client
authenticates with the same algorithm that signs everything else in this
profile.

### The proof that actually matters

Real ML-DSA-65 verification (`webcrypto.subtle.verify`) against the
public key published in `client_one_pqc_pub.jwks` — `valid: true`. Same
structure as Classic's `client_assertion` (Section 6 of that README), only
the algorithm changes — the `_run_pqc_signer()` Docker helper signs
exactly as it signs any other PQC payload in this project (Section 2).

### Mechanism explanation

`sign_jwt()`'s `alg == "ML-DSA-65"` branch (`thesis/scripts/opin_flow.py`)
serializes the private key + header + claims and invokes
`_run_pqc_signer()` — the same ephemeral Docker container used for any
client-side ML-DSA-65 signature in this project.

### Code reference

- `thesis/scripts/opin_flow.py`, `sign_jwt()`, `alg == "ML-DSA-65"` branch
  (lines 581–584); `_run_pqc_signer()` (line 386).
- `mock-service-os/certs/client_one_pqc_pub.jwks` — public key used in the
  verification.
- `thesis/scripts/verify_hybrid_jwt/verify_client_assertion.mjs` — the
  verification run above.

---

## Methodological note: how this batch was collected, and a real reproducibility threat it revealed

Capturing a real PQC flow live exposed a problem that initially seemed
specific to this capture script, but **was not**: Python's TLS stack
(`opin_flow.py`) tries to locally load the `client_one_pqc.crt/.key` key
pair even on the Python→`tls_kem_proxy` leg (which never requires a client
certificate — see `tls_kem_proxy/main.go`, the local listener does not set
`ClientAuth`), and this host's default OpenSSL 3.0 cannot parse a native
ML-DSA-65 key (`EE_KEY_TOO_SMALL`/`X509_LIB`, confirmed in isolation, with
no network activity involved at all). The real leg that authenticates with
the gateway (Go→gateway, inside `tls_kem_proxy`) uses native Go 1.27rc2
and works without issue — it is only the local, cosmetic leg that fails to
load the file.

**A direct test confirmed this is not a peculiarity of the capture
script**: running `median_automation.run_once("pqc", 0)`, calling
`opin_flow.run_insurance_flow()`/`run_person_flow()` **with no
modification whatsoever** — the exact same code path that generated this
v7's already-committed PQC data (2026-09-12) — failed on this machine, now,
with the same `EE_KEY_TOO_SMALL`, at the same call (`do_call()` →
`session.request(cert=cert, ...)`). In other words: **the official
measurement pipeline is also broken on this machine at the time this
artifact was written**, not just the auxiliary capture tool. The cause is
an external environment change (OpenSSL/Windows, not precisely
determined) between 2026-09-12 and 2026-09-13 — the certificate/key files
in the repository did not change (confirmed via `git status`/timestamps).

This failure was fixed in `opin_flow.py` (see Decision 5,
`thesis/results/v7/DECISIONS.md`): the local Python→`tls_kem_proxy` leg
stops presenting any client certificate under the `pqc`/`hybrid` profiles,
since that presentation never had any real effect (the local listener
never requires it) — it is purely cosmetic, and removing it restores
reproducibility without altering any already-measured data. After the
fix, the same test (`median_automation.run_once("pqc", 0)`, official
pipeline unchanged apart from this removal) was re-run successfully.

The capture script used to generate this README's examples
(`thesis/scripts/_capture_pqc_artifacts.py`, disposable) used, before the
fix above existed, an equivalent workaround for that same cosmetic leg
only — substituting the local certificate with `client_one.crt` (RSA,
loadable) after `tls_kem_proxy` had already been started with the real PQC
certificate, so the real authentication against the gateway used
`client_one_pqc.crt/.key` completely unchanged. With the `opin_flow.py`
fix already applied, this capture-script workaround became redundant
(`opin_flow.py` itself no longer presents a certificate there), but it was
left in the file since removing it was not necessary.

The already-committed size/latency batch data (2026-09-12) remains valid
and was not re-collected — the fix documented here exists only to ensure
that a future PQC collection on this machine will work again.
