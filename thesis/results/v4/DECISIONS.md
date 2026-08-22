# Experiment 3 (Hybrid, Strong Nesting) — Architecture Decisions

Log of non-obvious technical decisions made while implementing the
hybrid (PS256 + ML-DSA-65 via Strong Nesting) signature scheme described
in `Arquitetura_Tecnica_Experimento3_Strong_Nesting.docx` (this same
directory), with the reasoning behind each. Follows the same format as
`thesis/results/v2/experiment2 - PQC/DECISIONS.md` (Experiments 1/2's
decisions log) — cross-references to decisions in that file are given by
number and full path, since the two logs are chronologically continuous
but kept in separate files for this document's own section of the work.

## 1. Local CA expired mid-thesis -- regenerated with 5-year validity, every cert re-signed reusing its existing key

**Context:** starting Experiment 3 work (hybrid signing), `auth` failed to
connect to MongoDB with `certificate has expired`. Root cause: the local
CA (`mock-service-os/certs/ca.crt`) was generated with a hardcoded 1-year
validity and expired 2026-08-21 -- one day before this investigation.
This CA signs every certificate in the environment (mongo, postgres,
`client_one`/`_pqc`, `op`/`_pqc`, `mtls`/`_pqc`, `root_ca_pqc`,
`issuer_ca_pqc`), so its expiry broke TLS everywhere, not just
Experiment 3 -- Experiments 1 and 2 would fail to re-run too. Recorded
here (rather than in the Experiments 1/2 log) because it was found and
fixed as part of starting this section's work, even though its impact
was environment-wide, not Experiment-3-specific.

**Decision:** regenerate the CA (fresh key, 5-year validity this time)
and re-sign every existing leaf certificate against it, reusing each
leaf's private key unchanged. Not reusing the keys was never on the
table: `client_cert_der_bytes()` and every already-committed byte-size
figure in this thesis (1,494/2,953/etc.) depend on the exact DER
encoding of these certs, which depends on the key.

**Implementation:** `certs/main.go` gained a `-resign-all` flag
(`resignEverything`, `resignRSACert`, `resignMLDSACert`) that generates
the new CA and re-signs `mtls`/`op`/`client_one`/`client_two` (RSA) and
`mtls_pqc`/`op_pqc`/`client_one_pqc`/`root_ca_pqc`/`issuer_ca_pqc`
(ML-DSA-65), loading each existing key from disk rather than generating
a new one. `mongo.pem`/`mongo.crt`/`postgres.crt` aren't this tool's
format (different SANs, 2048-bit not 4096-bit keys, no generator script
found in the repo) -- re-signed separately with openssl, same
reuse-the-key principle.

**Two bugs found and fixed while verifying byte-for-byte fidelity against
the previously-committed certs (DER length comparison, not just "does it
boot"):**
- **Missing `AuthorityKeyIdentifier` on RSA certs, unexpectedly present
  on ML-DSA-65 certs.** `x509.CreateCertificate`'s `parent` argument
  needs `PublicKey`/`SubjectKeyId` populated on the Go struct (not just
  present in `parent`'s encoded DER) to emit an AKI extension on the
  child. The original RSA certs (`mtls`/`op`/`client_one`/`client_two`)
  were all issued in one `main()` run passing the *raw, unparsed*
  `generateCACert()` template as parent -- so they never had this
  extension. The ML-DSA-65 certs were each issued later via
  `-pqc-name`, which calls `loadCACert()` -- `x509.ParseCertificate` on
  `ca.crt` from disk, a fully populated struct -- so they did. Matching
  each original exactly meant deliberately reproducing this asymmetry
  (`rawCACert` as parent for the RSA group, a freshly re-parsed
  `parsedCACert` for the ML-DSA-65 group), not "fixing" it into
  consistency.
- **`org_id` format mismatch.** The original RSA certs all shared one
  `-org_id` value with a non-default `OPIBR-<uuid>` format (43 chars);
  the resign's default `uuid.NewString()` (36 chars) shifted the
  Subject field's DER length. Extracted the exact original string from
  the committed certs and hardcoded it (`originalRSAOrgID`) for the RSA
  group. The ML-DSA-65 certs each originally got their own independent
  random `org_id` (one per `-pqc-name` invocation) -- fine to use a
  fresh random one again, since only the *length* (a bare UUID) needed
  to match, not the specific value.

**Verified before treating this as done:** all 11 certificates' DER
byte length matches the previously-committed cert exactly; public key
fingerprints (RSA) and raw key bytes (ML-DSA-65, never touched since no
`.key` file was written) confirmed identical; full chain validation
against the new CA passes for every leaf. Environment confirmed booting
clean in `classic`, `pqc`, and `hybrid` afterward.

## 2. Etapas 1-2: hybrid crypto-profile files, and Strong Nesting signing via response interception (oidc-provider can't produce the composite alg natively)

**Context:** implementing the hybrid (PS256 + ML-DSA-65 Strong Nesting)
signature scheme per `Arquitetura_Tecnica_Experimento3_Strong_Nesting.docx`.

**Etapa 1 -- `crypto-profiles/hybrid.json`, both AS and RS.** Neither
`classic.json` nor `pqc.json` was designed to carry two keys at once, so
the format was extended rather than reused as-is: AS's `hybrid.json` is
`{signingAlgs: ["MLDSA65-RSA2048-PSS-SHA256"], classicSigningKey: {...},
pqcSigningKey: {...}}`; RS's (whose `classic.json`/`pqc.json` are the
bare JWK/key-blob itself, no wrapper) is
`{alg: "...", classicSigningKey: {...}, pqcSigningKey: {...}}`. Both
embed the exact same key material already in `classic.json`/`pqc.json`
-- confirmed programmatically (JSON equality) before treating Etapa 1 as
done. Confirmed with the user: RS's `ResponseSigningService` could
technically reuse its two existing hardcoded loaders
(`loadPs256Signer()`/`loadMlDsa65Signer()`) directly instead of reading
`hybrid.json`, but the user opted for `hybrid.json` as the single source
of truth per profile regardless, for audit consistency with the
classic/pqc convention (one file holds everything one profile needs).

**Etapa 2 -- AS signing, via response interception, not native
configuration.** Confirmed before writing any code: `jose`
(`6.2.8`, oidc-provider's own signing dependency) only supports a fixed
set of real JOSE algorithm identifiers -- `MLDSA65-RSA2048-PSS-SHA256`
isn't one and never will be, so no `enabledJWA`/`jwks` configuration of
oidc-provider can make it produce or accept this alg internally. The
implementation therefore never tells oidc-provider about hybrid mode at
all: in hybrid mode it's configured exactly like classic internally
(`internalSigningAlgs = ['PS256']`, `internalSigningKey =
hybrid.json's classicSigningKey`) and produces a completely normal,
valid PS256 artifact. A new `provider.use()` middleware
(`express.js`, using the new `utils/opin/hybridSigning.js`) runs after
oidc-provider's own handling completes, finds every plain PS256 compact
JWS in the response (JSON body fields, recursively, or a redirect's
query-string params) and replaces it: builds the real header (`alg:
"MLDSA65-RSA2048-PSS-SHA256"`, `kid: HYBRID_KID`), discards
oidc-provider's PS256 signature (it was computed over the old header,
a different byte string), and redoes Strong Nesting from scratch --
`sigma1 = PS256_sign(newHeader.payload)`,
`sigma2 = ML-DSA-65_sign(message || sigma1)` (raw byte concatenation,
confirmed with the user as the fixed convention for Etapas 2/3/6, not
base64-encoded), final signature `base64url(sigma1 || sigma2)`.
`HYBRID_KID` is `sha256(classicPk_bytes || pqcPk_bytes)` -- 256 + 1,952
raw bytes, confirmed against both JWKs before use -- computed once so
the signer and Etapa 5's `/jwks` publisher can never disagree about
which kid a given signature was made under. ML-DSA-65 signing runs
in-process via native WebCrypto (Node has native ML-DSA-65 since 24.7,
already used for the AS's own pqc-profile signing) -- no Docker
round-trip to `pqc-signer` needed for this component (that tool's
Docker helper exists only for `opin_flow.py`, which lacks any native
ML-DSA-65 support; corrected after initially conflating the two when
proposing this decision). See Decision 4 for a correction to the exact
signing call used here.

**Verified against a real, running AS** (not a synthetic unit test):
ran `opin_flow.py`'s real `run_insurance_flow("classic")` against
`CRYPTO_PROFILE=hybrid` on the AS (RS temporarily left on `classic`,
since Etapa 3 -- RS hybrid signing -- doesn't exist yet; confirmed this
is the only thing blocking a full-hybrid run, not a bug: RS's
`ResponseSigningService.init()` correctly throws
`IllegalStateException: Unknown mockinsurance.crypto-profile 'hybrid'`
when actually exercised). The JARM authorization response (the artifact
carrying the authorization code) came back with header `{"alg":
"MLDSA65-RSA2048-PSS-SHA256", "kid": "<HYBRID_KID>"}` and a signature
exactly 3,565 bytes long -- 256 (PS256/RSA-2048) + 3,309 (ML-DSA-65),
matching FIPS 204's raw signature size exactly. Full flow (PAR ->
automated login -> confirm -> token exchange) completed successfully,
12/12 calls. (This structural verification held up, but the signature's
actual cryptographic validity did not -- see Decision 4.)

**Bug fixed along the way:** the response-scanning middleware crashed
(`TypeError: Invalid URL`) on relative `Location` redirects (e.g. the
plain `/interaction/{uid}` hop before any login has happened, which
never carries a JWT) -- `new URL()` requires an absolute URL. Fixed by
only attempting the query-string scan when the redirect already looks
absolute (`scheme://...`).

**Known limitation, deliberately deferred, not a bug:** `id_token` is
JWE-encrypted (`alg: RSA-OAEP, enc: A256GCM`, 5 segments) -- a
pre-existing `mock_as` configuration unrelated to `CRYPTO_PROFILE`
(encryption already documented as staying classical across profiles in
`thesis/results/v2/experiment2 - PQC/DECISIONS.md`). The interception
middleware's compact-JWS detector correctly does not match a 5-segment
JWE and leaves it untouched -- meaning `id_token`'s *inner* signature is
not currently hybridized (only the outer JWE, which was already
RSA-OAEP-encrypted before this work, wraps it). Hybridizing it would
require decrypting the JWE (AS's own private key), re-signing the inner
JWT, and re-encrypting with the *client's* public encryption key (not
the AS's) -- a materially bigger change than the JARM/response-body
case. Decided with the user: out of scope for now. The JARM response
(the artifact that actually carries the authorization code and drives
the rest of the flow) is fully hybridized and verified; `id_token`'s
content is unaffected by CRYPTO_PROFILE either way (its claims, not its
signature, are what the flow actually consumes downstream).

## 3. Etapa 3: RS hybrid signing, and a pre-existing broken build path found and fixed along the way

**Etapa 3 -- RS Strong Nesting.** Unlike the AS,
`ResponseSigningService.sign()` already builds the JWS header and
signing input itself before delegating to a `JwsSigner` (see `sign()`),
so there was no library alg-name validation to work around: the new
`case "hybrid" -> loadHybridSigner()` branch produces a header saying
`MLDSA65-RSA2048-PSS-SHA256` from the start, no intercept-and-replace
step needed (that was specifically an AS/oidc-provider problem -- see
Decision 2). `loadHybridSigner()` loads both keys from the RS's own
`crypto-profiles/hybrid.json` (Etapa 1), computes
`sigma1 = PS256_sign(signingInput)` via the same Nimbus `RSASSASigner`
`loadPs256Signer()` already uses, `sigma2 =
ML-DSA-65_sign(signingInput || sigma1)` via the same BouncyCastle
`Signature.getInstance("ML-DSA", "BC")` `loadMlDsa65Signer()` already
uses, and returns `base64url(sigma1 || sigma2)` -- byte concatenation,
matching the AS's fixed convention exactly. The hybrid kid is
`sha256(classicPk || pqcPk)`, computed independently from the RS's own
two keys (correctly a different value from the AS's hybrid kid -- it
identifies this participant's composed public key, not something
shared across participants). One subtlety caught before it could
silently produce a kid that would never match `mock_as`'s: the classic
public key bytes must come from the JWK's own `"n"` field
(`Base64.getUrlDecoder().decode(...)`), not
`rsaKey.toRSAPublicKey().getModulus().toByteArray()` -- `BigInteger`'s
two's-complement encoding prepends a zero byte whenever the modulus's
high bit is set (true for nearly every real RSA-2048 key), silently
producing 257 bytes instead of 256.

**Verified against the real, running RS**: ran `opin_flow.py`'s real
`run_insurance_flow("classic")` (AS and RS both `hybrid`, client still
`classic` -- Etapa 7 pending) and inspected every RS response. All 6
(`POST /consents`, 5x `GET /consents/{id}`) came back with `alg:
"MLDSA65-RSA2048-PSS-SHA256"`, one consistent `kid` across all of them
(same signing key throughout, as expected), and a signature exactly
3,565 bytes long every time -- 256 (PS256/RSA-2048) + 3,309 (ML-DSA-65).
Full flow, 12/12 calls, no errors. Unlike the AS's Decision 2, this
signature turned out to be genuinely cryptographically valid from the
start -- see Decision 4.

**Pre-existing infrastructure problem found and fixed, unrelated to the
hybrid architecture itself:** building the RS's Docker image
(`./gradlew dockerBuild`) failed before any of the above could be
tested. Root cause: the repository's root `Dockerfile` -- a GraalVM
20.3.0/Java 11 native-image pipeline targeting AWS Lambda's custom
runtime (`bootstrap`/`function.zip`), present unchanged since this
repo's very first commit -- is picked up by the Micronaut Gradle
plugin as an override for the plain `dockerBuild` ("main", JVM/Netty)
image task too, not just the Lambda-native one. That Dockerfile's
builder stage (`gradle:5.3.1-jdk11-slim`) cannot load this project's
`build.gradle` at all (`Failed to apply plugin ... Shadow ... supports
Gradle 8.0+ only`; the project's own `gradle-wrapper.properties`
specifies Gradle 8.10) -- meaning `dockerBuild` was never actually
buildable via this checked-in file, for as long as it's existed in this
repo's history. The currently-deployed `raidiam-insurance-lambdas:latest`
image (confirmed via `docker history`: `eclipse-temurin:17-jre` base,
plain `ENTRYPOINT ["java","-jar",...]`, layered-JAR `COPY`s -- the
Micronaut plugin's own default JVM image shape) must have been built by
some other, no-longer-reproducible process before this repository's
current state, never through this Dockerfile. Fixed by temporarily
renaming `Dockerfile` -> `Dockerfile.lambda-native.bak` (not deleting --
it's still needed for actual Lambda packaging, entirely out of this
thesis's scope) so the Micronaut plugin falls back to auto-generating
its own Dockerfile for the "main" image, confirmed to reproduce the
exact same `eclipse-temurin:17-jre` layered-JAR shape as the
already-running image; renamed back to `Dockerfile` immediately after
the build succeeded. This has no bearing on the hybrid architecture or
any experiment's data -- it only affects how the RS's Docker image gets
rebuilt locally, something no prior decision in this thesis needed to
do (Experiments 1/2 never modified RS Java code, only mounted
`crypto-profiles/*.json` and cert files).

## 4. Etapa 4: hybrid verification, and a real signing bug in Etapa 2 that nothing had caught until now

**Scope, confirmed with the user before writing any code:** implement
the Strong Nesting verification routine (decompose sigma1/sigma2, verify
each half, AND-gate) as a pure, standalone, tested function on both
sides -- not wired into either the AS's live request pipeline or
`opin_flow.py`'s flow control. Two reasons, both confirmed rather than
assumed: (a) on the AS side, verifying an *incoming* hybrid-signed
`client_assertion`/request object would mean intercepting and rewriting
the raw Koa/Node request stream before oidc-provider parses it -- a
materially riskier piece of engineering than the signing side's
after-the-fact `ctx.body` replacement (Decision 2), and not yet
testable end-to-end regardless, since no real caller sends a
hybrid-signed client assertion until Etapa 7 exists; (b) on the client
side, `opin_flow.py` doesn't cryptographically verify *any* profile's
signature today (`parse_rs_body()` always calls `pyjwt.decode(...,
verify_signature=False)`) -- there is no existing "point that verifies
signature" to extend for hybrid without also changing classic/pqc
behavior, which is out of scope.

**AS side:** `mock_as/utils/opin/hybridVerification.js`,
`verifyHybrid(compactJwt, classicPublicJwk, pqcPublicJwk)`. ML-DSA-65
verification (sigma2) goes through Node's native WebCrypto
(`webcrypto.subtle.verify({name: 'ML-DSA-65'}, ...)`) directly, not
jose's `CompactVerify` -- jose's JWS-shaped API recomputes its own
signing input from a header/payload it parses, with no entry point for
"verify this signature against this exact byte string" (which is
exactly what verifying sigma2 over `message || sigma1` requires). The
public key import still goes through jose's `importJWK()` (proven
already, used by the signing side) rather than a hand-rolled
`webcrypto.subtle.importKey()` -- the latter imports without error but
produces a key that silently never verifies, confirmed empirically
while debugging the failure below.

**Client side:** `thesis/scripts/hybrid_verify.py`,
`verify_hybrid(compact_jwt, classic_public_jwk, pqc_public_jwk)`. PS256
verification uses `cryptography`'s native RSA-PSS support directly (no
external help needed, unlike signing where a Docker helper was only
ever needed for the ML-DSA-65 half). ML-DSA-65 verification (sigma2)
reuses `pqc-signer` (the same Docker image `opin_flow.py` already uses
for pqc-mode client signing), extended with a second stdin-driven mode:
alongside the existing `{jwk, headers, claims}` -> compact-JWT-signing
shape, a new `{jwk, message_b64, signature_b64}` shape does a raw
`webcrypto.subtle.verify()` and prints `"true"`/`"false"` -- deliberately
not `CompactVerify`-based, for the identical reason as the AS side.

**Bug found and fixed: Etapa 2's AS-side ML-DSA-65 *signing* was
producing signatures over the wrong bytes, undetected until this
verification routine existed to catch it.**
`hybridSigning.js`'s `signMlDsaRaw()` used jose's `CompactSign(message)`
to get at sigma2's raw bytes -- but `CompactSign` treats its argument as
a JWS *payload*, internally signing
`base64url(header) + "." + base64url(payload)`, not the `message` bytes
handed to it directly. This silently violated the "sign the raw
`message || sigma1` bytes" convention Etapa 2 was supposed to implement
(and that the user explicitly confirmed as a byte-for-byte convention
across Etapas 2/3/6). It went undetected through all of Etapa 2 and 3's
own testing because ML-DSA-65 signatures are fixed-length (3,309 bytes)
regardless of what's actually signed -- every structural check (header
`alg`, `kid`, total signature length 3,565 bytes) passed even though
sigma2 itself was cryptographically meaningless. The RS/Java side never
had this bug: `ResponseSigningService.loadHybridSigner()` calls
`Signature.getInstance("ML-DSA", "BC")` directly on the raw
`messagePlusSigma1` byte array, with no JWS-shaped library in the way --
confirmed by this same Etapa 4 testing, which verified a real, live RS
response successfully on the first attempt with no fix needed.

**Fixed** by replacing `CompactSign` with a direct
`webcrypto.subtle.sign({name: 'ML-DSA-65'}, pqcPrivateKey, message)`
call in `signMlDsaRaw()` -- the private-key import (`importJWK`) was
already correct and unchanged, only the actual signing call moved off
jose's JWS abstraction. Re-verified after the fix: a synthetic
happy-path signature now verifies correctly and both single-byte
corruption tests (sigma1, sigma2) correctly reject; a **live** JARM
response captured from a real `opin_flow.py` run against the running
(rebuilt) AS was independently verified valid by `hybridVerification.js`
-- the first genuine cryptographic proof, not just a structural one,
that Etapa 2's signing produces a real, checkable Strong Nesting
signature. `auth`'s Docker image was rebuilt and the running container
recreated with the fix before this re-verification.

**Also re-verified (no bug, already correct):** a live RS response,
captured the same way, verified valid on the first attempt against
`thesis/scripts/hybrid_verify.py` -- confirming Etapa 3's Java
implementation was cryptographically sound from the start.

**Both sides tested, happy path + two independent failure paths** (a
single flipped byte inside sigma1's range, and inside sigma2's range),
against both a synthetic test signature and a live-captured real one:
accept only when both halves are genuinely valid, reject on either
corruption. Not wired into any live request-handling path on either
side, per the scope agreed above.
