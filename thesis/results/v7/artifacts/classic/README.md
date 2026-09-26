# Real artifacts — Classic profile

This folder exists as **verifiable proof of implementation**, in the same
spirit as `artifacts/hybrid/` and `artifacts/pqc/`: every "this was done"
claim comes with the real artifact captured live, an explanation of the
underlying mechanism, and the exact point in the source code. For Classic
specifically, the claim that needs proof is the **negative** one: no
post-quantum material exists in any of the four artifacts — and "nothing
exists" is verified with the same rigor that "something exists" is
verified in the other two profiles, not merely assumed by omission.

All data below was captured live under `CRYPTO_PROFILE=classic`, on the
same system and pipeline (`tls_kem_proxy`, v7 Decision 1 — Classic now
also goes through the same Go client, just requesting purely classical
curves) used for the size and latency batch.

---

## 1. Classic certificate (`client_one.crt`)

### The real artifact

Raw file: [`client_one.crt`](client_one.crt). Decoded version:
[`client_one.crt.txt`](client_one.crt.txt) (`openssl x509 -text -noout`).

Full extensions block — **three extensions, none of them hybrid**:

```
X509v3 extensions:
    X509v3 Key Usage: critical
        Digital Signature
    X509v3 Extended Key Usage:
        TLS Web Client Authentication
    X509v3 Subject Alternative Name:
        DNS:auth.local, DNS:matls-auth.local, DNS:api.local, DNS:matls-api.local,
        DNS:directory, DNS:directory.local, DNS:keystore, IP Address:127.0.0.1, IP Address:::1
Signature Algorithm: sha256WithRSAEncryption
```

### The proof that actually matters: confirming the absence, and verifying the one signature that exists

Saying "Classic has no hybrid extensions" by looking at the decoding
above requires trusting that nothing was skipped. The real proof is two
independent checks, both run against the actual file:

**1. Absence confirmed programmatically, not by visual inspection** —
the three hybrid OIDs (`2.5.29.72/73/74`, see `artifacts/hybrid/README.md`,
Section 1) searched for against the certificate's actual extension list:

```
$ python -c "
from cryptography import x509
cert = x509.load_pem_x509_certificate(open('client_one.crt','rb').read())
hybrid_oids = {'2.5.29.72','2.5.29.73','2.5.29.74'}
print('Extensoes:', [e.oid.dotted_string for e in cert.extensions])
print('OIDs hibridos encontrados:', [e.oid.dotted_string for e in cert.extensions if e.oid.dotted_string in hybrid_oids])
"
Extensoes: ['2.5.29.15', '2.5.29.37', '2.5.29.17']
OIDs hibridos encontrados: []
```

Three extensions in total (Key Usage, Extended Key Usage, SAN), zero of
them hybrid — confirmed against the certificate's actual structure, not
merely by its absence from the excerpt chosen for display here.

**2. The one signature that exists genuinely verifies** — an ordinary
X.509 trust chain, verified with `openssl verify`, not assumed:

```
$ openssl verify -CAfile ca.crt client_one.crt
client_one.crt: OK
```

Full output in
[`verify_classic_cert_output.txt`](verify_classic_cert_output.txt). Unlike
the hybrid certificate (Section 1 of `artifacts/hybrid/`), there is no
second signature here to reconstruct and verify separately — only the
RSA one exists, and it passes a genuine, standard chain verification,
with no special tooling.

Full certificate size (DER): **1,494 bytes** — confirms the
`client_cert_der_bytes` measured across the entire v7 batch for this
profile, and is 2,953/6,859 bytes *smaller* than PQC/Hybrid respectively,
exactly the difference that having no embedded ML-DSA-65 material should
produce.

### Mechanism explanation

Classic uses the project's simplest certificate logic: a subject
RSA-4096 key, signed once by the CA (`sha256WithRSAEncryption`), with no
extensions beyond the usual three (Key Usage, Extended Key Usage, SAN).
There is no "pre-TBS" step and no second signature — the certificate is
created in a single call to `x509.CreateCertificate`, not two as in the
hybrid case (Section 1 of `artifacts/hybrid/README.md`). It is the only
one of the three profiles whose generation logic has never needed to
change since v5 — the TLS key exchange that v7 unified (Decision 1) was
already classical here from the start.

### Code reference

`mock-service-os/certs/main.go`:
- `generateCert()`, lines 647 onward — the function that generated
  `client_one.crt`. Note the structural absence: no call to
  `hybridExtensions()`, no `ExtraExtensions` field with the hybrid OIDs, a
  single call to `x509.CreateCertificate` (not two, as in
  `generateHybridCert()`, lines 338–402, compare directly). The absence of
  post-quantum material is not an option switched off somewhere — it is
  simply code that `generateCert()` never had.

---

## 2. Real JWT, decoded (RS response, `GET .../premium`)

### The real artifact

Full token captured live:
[`example_jwt_premium.txt`](example_jwt_premium.txt).

**Decoded header:**
```json
{"alg": "PS256", "kid": "041486ea-f7b8-4b36-9dfb-fadf2966d0e8", "typ": "JWT"}
```

**Decoded payload (top-level keys):** `data`, `links`, `meta` —
**without** `pqc`. Full token: 1,483 characters (versus 7,430 for the
equivalent Hybrid token — almost the entire difference is the
`pqc.signature` field, 4,412 characters, which simply does not exist
here).

### The proof that actually matters: the signature verifies, and the `pqc` field is genuinely absent

```
$ node thesis/scripts/verify_hybrid_jwt/verify_classic_jwt.mjs \
    insurance-server-lambdas/src/main/resources/crypto-profiles/classic.json \
    thesis/results/v7/artifacts/classic/example_jwt_premium_compact.txt

VERIFICATION RESULT: {
  "valid": true,
  "reason": "PS256 verified",
  "hasPqcClaim": false
}
```

Full output in [`verify_jwt_output.txt`](verify_jwt_output.txt). The
script (`thesis/scripts/verify_hybrid_jwt/verify_classic_jwt.mjs`, written
for this profile) genuinely verifies the PS256 signature (RSA-PSS
padding, Node's native `crypto.verify`, against the public key derived
from `crypto-profiles/classic.json` — the same file that
`ResponseSigningService.java` loads for signing) **and** programmatically
checks that `payload.pqc` does not exist (`hasOwnProperty`, not "I didn't
see it in the JSON I printed") — both of which need to be true for this
to be a genuine classical signature, not a hybrid one with the extra
field manually removed before inspection.

**Note on the key**: the `n` of this RSA key is byte-identical to
`classicSigningKey.n` used in the Hybrid profile — the project reuses the
same RS RSA identity across both profiles (Hybrid only adds ML-DSA-65 on
top, never swaps out the classical base). This confirms that "Classic"
and "the classical half of Hybrid" are, deliberately, the same thing.

### Mechanism explanation

A classic JWT is the simplest thing possible: `ResponseSigningService`
assembles the claims, never calls anything equivalent to
`preparePayload()`'s `pqc` injection (that function is specific to the
hybrid signer, Section 2 of `artifacts/hybrid/README.md`), and signs once
with PS256 (RSA-PSS). There is no JCS canonicalization involved — there
is no second payload content to make reproducible across languages,
because there is no second signature.

### Code reference

`insurance-server-lambdas/src/main/java/com/raidiam/trustframework/
mockinsurance/crypto/ResponseSigningService.java`:
- `loadPs256Signer()`, lines 140–160 — loads `classic.json`, signs with
  `RSASSASigner`/`JWSAlgorithm.PS256` (Nimbus). Compare with
  `loadHybridSigner()` (line 212): here there is no overridden
  `preparePayload()`, so the interface's `default` (line 92, which simply
  returns the claims untouched) is what runs — the absence of the `pqc`
  field is the interface's default behavior, not a special exclusion for
  this profile.
- `thesis/scripts/verify_hybrid_jwt/verify_classic_jwt.mjs` — the
  verification run above.

---

## 3. Real JWKS entry (Authorization Server, `/jwks`)

### The real artifact

Full capture: [`jwks_auth.json`](jwks_auth.json) — real response from
`GET https://auth.local/jwks`, Classic profile:

```json
{
  "keys": [
    {"kty": "RSA", "use": "sig", "kid": "xQLs45xYyJr1omHs4qnB2rhes9qNFHIHQ5YPQKVJliM", "alg": "PS256", "e": "AQAB", "n": "pu8AVLEIfYppnbU0r2M1PNhCvYpGnVXbSXj...(truncado)"},
    {"kty": "RSA", "use": "enc", "kid": "AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k", "alg": "RSA-OAEP", "e": "AQAB", "n": "gbulO7BqCAKwVy3ZqrR033OM1Mp...(truncado)"}
  ]
}
```

Two ordinary `kty: "RSA"` entries — one for signing (PS256), one for
encryption (RSA-OAEP, for the `id_token`'s JWE). No `kty: "HYBRID"`, no
`pk_hybrid` field, no non-standard `alg`.

### The proof that actually matters: this is a JWKS that any standard JOSE library already understands

Unlike the other two profiles, there is nothing exotic here to close the
loop with a special verification — **the very fact that this JWKS has
exactly the shape that `jose`/any standard library expects, with no
adaptation, is the proof**. The `n` of the signing entry above is
byte-identical to the beginning of the AS's `pk_hybrid` in the Hybrid
profile (`artifacts/hybrid/README.md`, Section 3) — confirming that the
same AS RSA key is reused between Classic and Hybrid, exactly as on the
RS side (Section 2 above).

### Mechanism explanation

The AS, in classic mode, never invokes any hybrid composition logic — it
publishes the two RSA keys (signing and encryption) that have always
existed in the project, since before any post-quantum work began. It is
not a "hybrid with half removed" — it is the original code, untouched.

### Code reference

The AS's classic JWKS publication path is the same one used since v1 of
this project (before any PQC/Hybrid profile existed) —
`mock-service-os/mock_as/utils/opin/configuration.js` selects which key
set to publish based on `CRYPTO_PROFILE`; for `"classic"`, neither
`hybridSigning.js` nor `payloadExtensionVerification.js` is even imported
along the execution path.

---

## 4. TLS handshake evidence — no post-quantum key-exchange group

### The real artifact

Real gateway log line, Classic profile, via `tls_kem_proxy`:
[`handshake_log.json`](handshake_log.json).

```json
{
  "msg": "mTLS handshake complete",
  "tlsVersion": "TLS 1.3",
  "cipherSuite": "TLS_AES_128_GCM_SHA256",
  "curveID": "CurveP256",
  "clientCertBytes": 1494,
  "mtlsHandshakeBytes": 5052,
  "handshakeDurationMs": 17
}
```

`curveID: "CurveP256"` — a purely classical elliptic curve, with no KEM
component. (The server's preference lists P521/P384/P256 in that order —
the Go client negotiated P256, not necessarily the first on the list;
TLS 1.3 lets the final choice also depend on the client's preference, and
this changes nothing about what this artifact needs to prove.)

### The proof that actually matters: confirming programmatically that NO group with a KEM component was negotiated, and that the session is still fresh

```
$ docker run --rm --network insurance-server-lambdas_default \
    -v thesis/scripts/verify_kem_export:/src -v mock-service-os/certs:/certs:ro -w /src \
    golang:1.27-rc-alpine go run . classic /certs/client_one.crt /certs/client_one.key

connection 1: curveID=CurveP256 tlsVersion=TLS 1.3 exported(32B)=11f8dee31e3ef962310c1ce7b2947012d13a64a8cc3dd0a4d10515dd2d513134
connection 2: curveID=CurveP256 tlsVersion=TLS 1.3 exported(32B)=6bb68d296426bc17d6a750bd8762a3d299648ed57793c4d2125dfbd9793957df

RESULT: verificado -- ambas as conexoes negociaram CurveP256 (grupo=classic), e o material de chave exportado
(RFC 5705) e DIFERENTE entre as duas -- confirma que o segredo de sessao foi de fato derivado de uma troca de
chave nova a cada conexao, nao um valor fixo ou decorativo.
```

Full output in
[`verify_kem_export_output.txt`](verify_kem_export_output.txt). The same
tool used for Hybrid and PQC runs here with `-group classic`: it
internally checks that the negotiated `curveID` is on the list of purely
classical curves (`CurveP256`/`CurveP384`/`CurveP521`) — had any group
with "MLKEM" in its name appeared, the program would have ended in
`RESULT: FAIL`, not successfully. The key-material export (RFC 5705)
confirms, as in the other two profiles, that the session secret is
genuinely new for each connection — here, via pure ephemeral ECDHE, not a
KEM.

### Mechanism explanation

Before v7 (Decision 1), Classic never went through `tls_kem_proxy` — it
connected directly to the gateway, and `mock_mtls`'s
`serverCurvePreferences` (the package's default value, never overridden
for this profile) was already purely classical. v7 routed Classic through
the same Go client that PQC/Hybrid use, but this did not change the
requirement on the server side — `CRYPTO_PROFILE=classic` never activates
any `init()` branch that swaps `serverCurvePreferences`, so the server
keeps offering only classical curves, and `tls_kem_proxy` (invoked with
`-curve classic`, v7 Decision 1) requests exactly that on the client
side.

### Code reference

- `mock-service-os/mock_mtls/main.go`, lines 88–89:
  `serverCurvePreferences = []tls.CurveID{tls.CurveP521, tls.CurveP384,
  tls.CurveP256}` — the package's default value, never overridden by
  `init()` for `CRYPTO_PROFILE=classic` (compare with lines 114/137, where
  `init()` overrides this value specifically for `"pqc"`/`"hybrid"`).
- `thesis/scripts/tls_kem_proxy/main.go`, the `"classic"` case of the
  curve `switch` (see `thesis/results/v7/DECISIONS.md`, Decision 1, for
  why this case does not need the SNI trick the legacy `"classical"` case
  uses).
- `thesis/scripts/verify_kem_export/main.go` — the same tool as in
  Sections 4 of `artifacts/hybrid/` and `artifacts/pqc/`, invoked here
  with `classic`.

---

## 5. Real `id_token`, decoded — signature migrated, message-level encryption still classical due to a real limitation

### The real artifact

Captured live from the `id_token` field of a real `POST /token` response
(full flow, Classic profile): [`id_token_raw.txt`](id_token_raw.txt).

Unlike the artifacts in Sections 1–4 (all 3-segment JWS), this one is a
**5-segment JWE** — the `id_token` is not only signed, it is also
**encrypted**:

```
$ node decrypt_and_verify_id_token.mjs classic id_token_raw.txt   # (dentro do container `auth`)

id_token: 1812 chars, 5 segments (JWE compact serialization)
JWE protected header: {"alg":"RSA-OAEP","enc":"A256GCM","cty":"JWT","kid":"92297d36-...","iss":"https://auth.local","aud":"client_one"}
Decrypted inner JWS: 678 chars, 3 segments
Inner JWS header: {"alg":"PS256","kid":"xQLs45xYyJr1omHs4qnB2rhes9qNFHIHQ5YPQKVJliM"}
Inner JWS payload (decoded, complete): {
  "sub": "usuario1@seguradoramodelo.com.br",
  "acr": "urn:brasil:openinsurance:loa3",
  "nonce": "CTtar5YUNixk",
  "aud": "client_one",
  "exp": 1789354423,
  "iat": 1789350823,
  "iss": "https://auth.local"
}
Inner JWS signature length (bytes): 256
VERIFICATION RESULT: {"valid": true, "reason": "PS256 verified"}
```

Full output in
[`verify_id_token_output.txt`](verify_id_token_output.txt).

### The proof that actually matters: the inner signature genuinely verifies; the outer encryption is classical RSA-OAEP, and this needs to be said without hedging

**Two layers, two different proofs.** The inner layer (the signature) is
genuinely verified: once the JWE is decrypted, the PS256 signature over
`header.payload` confirms valid against the AS's public key
(`client_one.jwks`'s pair corresponding to the decryption private key —
the AS signs with its own signing key, PS256/RSA, and encrypts for the
encryption public key that the CLIENT registered). This layer is migrated
and measured exactly like the other artifacts in this folder.

The outer layer (the encryption, `alg: "RSA-OAEP"`) is **classical in all
three profiles, without exception** — including PQC (Section 5 of that
profile's README). This is not a gap in this prototype: no JOSE/COSE
standard for post-quantum encryption exists today (the draft that did
exist was withdrawn from the IETF working group) — `thesis/docs/
Cruzamento_SAD_vs_Experimentos.md` documents this finding in more detail.
Capturing this artifact here, in Classic, serves as an honest baseline:
here the classical encryption is exactly what is expected (nothing
changed), and it is the same mechanism that appears, with no available
alternative, in the other two profiles.

### Mechanism explanation

The `id_token` is built and signed entirely inside `oidc-provider`'s
internal code (`lib/models/id_token.js`), then immediately encrypted
(RSA-OAEP + AES-256-GCM, compact JWE) before the HTTP response leaves the
process — there is no hook between signing and encryption in
`oidc-provider` 9.5.1. Encryption is always **for the encryption public
key that the client registered** (here, `client_one.jwks`'s `use: "enc"`
entry), not for a key of the AS's own — this is how `id_token`
confidentiality works in OIDC: the AS encrypts for whoever will read it
(the client), not for itself.

### Code reference

- `mock-service-os/mock_as/utils/opin/configuration.js`, line 330:
  `idTokenEncryptionAlgValues: ['RSA-OAEP']` — the only `id_token`
  encryption algorithm enabled, in any profile.
- `mock-service-os/mock_as/mongo-seed/init_clients.json`: client
  registration with `id_token_encrypted_response_alg: "RSA-OAEP"`.
- `mock-service-os/certs/client_one.jwks`: the client's RSA-OAEP key pair
  (`use: "enc"`) used for decryption above.
- `thesis/scripts/verify_hybrid_jwt/decrypt_and_verify_id_token.mjs` —
  the verification run above.

---

## 6. Real `client_assertion` — the signature that actually authenticates the client (not the access_token)

### Why this artifact exists

`thesis/docs/Cruzamento_SAD_vs_Experimentos.md` originally classified SAD
step 8 ("Access token") as covered by "hybrid signature, measured" —
inaccurate: the `access_token` captured live is an opaque 43-character
string (`certificateBoundAccessTokens: true`, with no
`formats.AccessToken` configured — `oidc-provider`'s default), **with no
signature at all**. The real signature that authenticates the client at
this step is the `client_assertion` (`private_key_jwt`) — the JWT that
the client itself signs to authenticate at `POST /token`. This artifact
closes that cataloging gap for the Classic profile.

### The real artifact

Captured live from the body of a real `POST /token` request (Classic
profile): [`client_assertion_raw.txt`](client_assertion_raw.txt).

```
$ node verify_client_assertion.mjs classic client_assertion_raw.txt   # (dentro do container `auth`)

Header: {"alg":"PS256","kid":"c0d35890-1f2a-4ed5-bf9f-856d10ccd093","typ":"JWT"}
Payload (decoded, complete): {
  "sub": "client_one",
  "aud": "https://matls-auth.local/token",
  "iss": "client_one",
  "exp": 1789352024,
  "iat": 1789351964,
  "jti": "LduoZgIao5GTDrGr90owD6r1"
}
Signature length (bytes): 512
VERIFICATION RESULT: {"valid": true, "reason": "PS256 verified"}
```

Full output in [`verify_client_assertion_output.txt`](verify_client_assertion_output.txt).
A 512-byte signature confirms `client_one`'s own RSA-4096 key (not an
ordinary RSA-2048) — the same key already used for the mTLS certificate
(Section 1) and the JWKS (Section 3), reused here for signing artifacts
the client issues.

### The proof that actually matters

A genuine PS256 verification against the public key published in
`client_one_pub.jwks` (the same key pair as the certificate in Section 1)
— `valid: true`. Nothing exotic here: it is the standard OIDC/FAPI
`private_key_jwt` mechanism, with no extra layer — the point of this
artifact is precisely to contrast with Hybrid (Section 6 of that
README), where the same structural position carries a real
payload-extension signature.

### Mechanism explanation

`opin_flow.py`'s `make_client_assertion()` assembles the standard claims
of a `private_key_jwt` (RFC 7523) and signs via `sign_jwt()`, which for
`alg == "PS256"` delegates directly to `pyjwt.encode()` — with no
additional logic, the simplest path of the three profiles.

### Code reference

- `thesis/scripts/opin_flow.py`, `make_client_assertion()` (line 629) and
  `sign_jwt()` (line 578), `alg == "PS256"` branch (lines 579-580).
- `mock-service-os/certs/client_one_pub.jwks` — the public key used in
  the verification.
- `thesis/scripts/verify_hybrid_jwt/verify_client_assertion.mjs` — the
  verification run above.
