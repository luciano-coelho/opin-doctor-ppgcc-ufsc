# Experiment 3 (Hybrid, Strong Nesting) — Architecture Decisions

Log of non-obvious technical decisions made while implementing the
hybrid (PS256 + ML-DSA-65 via Strong Nesting) signature scheme described
in `ARCHITECTURE.md` (this same directory -- translated to English/
Markdown from the original `Arquitetura_Tecnica_Experimento3_Strong_
Nesting.docx`, which has been removed), with the reasoning behind each.
Follows the same format as
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
signature scheme per `ARCHITECTURE.md`.

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

## 5. Etapa 5: hybrid JWKS -- publishing the composed key under a single kid on both AS and RS

**RS side needed no new code.** `ResponseSigningService.loadHybridSigner()`
(Etapa 3) already builds `hybridPk = classicPk || pqcPk` and a `hybridKid`
derived from it, and already returns them from `publicJwk()` as
`{kty: "HYBRID", alg: "MLDSA65-RSA2048-PSS-SHA256", use: "sig",
kid: hybridKid, pk_hybrid: base64url(hybridPk)}` -- exactly Etapa 5's
requirement. `JwksController`'s `/jwks` route already calls
`responseSigningService.getPublicJwk()` unconditionally, for any active
profile. So the RS's `/jwks` was already publishing the correct
composed key the moment Etapa 3 landed; Etapa 5 only needed to confirm
and test this, not write anything new.

**AS side needed a new `/jwks` override**, for the same reason Etapa 2
needed response interception: oidc-provider is kept completely unaware
of hybrid mode (`internalSigningKey` is hybrid.json's classic half
only, see Decision 2), so its own `/jwks` route would publish only that
RSA key -- never the composed `pk_hybrid` a relying party actually needs
to verify a Strong Nesting signature. `utils/opin/configuration.js`
already had a `publishedJwksOverride` mechanism from Experiment 2 (a
route registered in `express.js` before `provider.callback()`, which
Express matches first and which therefore shadows oidc-provider's own
`/jwks`) -- previously used only as an opt-in Conformance Suite decoy in
pqc mode (`JWKS_SHADOW=1`, publishing a classical key nothing actually
signs with, purely to get a Nimbus-based validator past a `kty: AKP`
crash it can't handle; see Decision 6/7 in
`thesis/results/v2/experiment2 - PQC/DECISIONS.md`). Etapa 5 adds a
second, unconditional branch to this same mechanism for hybrid mode:
publishes `{kty: "HYBRID", use: "sig", alg: "MLDSA65-RSA2048-PSS-SHA256",
kid: HYBRID_KID, pk_hybrid: base64url(HYBRID_PK_BYTES)}` (imported
directly from `hybridSigning.js`, so the signer and the `/jwks`
publisher can never disagree about the key or kid) alongside the same
RSA-OAEP encryption key already published in every other profile
(encryption stays classical regardless of `CRYPTO_PROFILE`; see Decision
2). Unlike the pqc-mode decoy, this override is always on in hybrid mode
and is not a diagnostic workaround -- it is the correct, truthful
publication of the key hybrid mode actually signs with.

**Tested against both live, running services** (`CRYPTO_PROFILE=hybrid`,
`auth`/`mtls`/`mongo_seed`/`mockapi` recreated together): fetched
`/jwks` from the AS (`http://auth:3000/jwks`, and confirmed reachable
through the mTLS gateway at `https://matls-auth.local/jwks`) and from
the RS (`http://mockapi:8080/jwks` -- the `matls-api.local`/`api.local`
gateway aliases returned `Unauthorized`, expected: those routes require
a client mTLS certificate at the gateway layer, unrelated to this
change and not exercised by this test). For each, decomposed the
returned `pk_hybrid` back into its two fixed-size halves (256 bytes
RSA-2048 modulus, 1,952 bytes ML-DSA-65 raw public key), recomputed
`sha256(pk_hybrid)` and confirmed it matches the published `kid`, and
confirmed the classic half matches that participant's own `hybrid.json`
`classicSigningKey.n` byte-for-byte. Also confirmed, as a sanity check,
that the AS's and RS's kids and composed keys are different from each
other (expected -- each `kid` identifies that participant's own key,
not a value shared across participants).

**Regression check:** re-ran the same environment in `classic` mode
(`CRYPTO_PROFILE=classic`) and confirmed `/jwks` is unaffected --
`publishedJwksOverride` stays `null` (the new hybrid branch is gated on
`isHybrid`), so oidc-provider's own route serves its normal RSA sig +
enc keys exactly as before. `hybridSigning.js` (which reads
`hybrid.json` and validates key lengths at module load) is now
unconditionally imported by `configuration.js` regardless of active
profile, but `hybrid.json` always exists in the repo (all three
profiles' files coexist), so this import is a no-op in classic/pqc
mode and did not change boot behavior -- confirmed via the `auth`
container's boot log, unchanged from before this change.

## 6. Etapa 6: hybrid mTLS certificates -- a real divergence found and resolved with the user before writing any code

**Divergence found and stopped on, per standing instruction.** Section 7's
prose describes the client/gateway certificate's dual signature as: RSA
signs FIRST over the certificate's content; ML-DSA-65 signs SECOND, over
the certificate's content together with the RSA signature and the
participant's ML-DSA-65 public key -- i.e. Strong Nesting applied
literally to "the certificate" as if it were a JWT payload. But the three
named extensions (SubjectAltPublicKeyInfo, AltSignatureAlgorithm,
AltSignatureValue) are not generic placeholders -- they are the specific,
standard identifiers from the paper Section 7 itself cites for this exact
mechanism (Bindel, Braun, Gladiator, Stebila & Wiggers, "X.509-Compliant
Hybrid Certificates for the Post-Quantum Transition," JOSS 4(40), 1606,
2019 -- also standardized in ITU-T X.509's hybrid-certificate amendment).
That real mechanism signs in the OPPOSITE order: the alt (ML-DSA-65)
signature is computed FIRST, over a "preTBSCertificate" that has the
first two extensions but not yet AltSignatureValue (which doesn't exist
yet); the classical (RSA) signature is computed LAST, over the complete,
final TBSCertificate with all three extensions present. This exists for a
specific, load-bearing security reason: it's what lets an old, PQC-unaware
verifier's ONE signature check (the only one it will ever perform)
cryptographically cover the two PQC extensions too -- nobody can swap out
the PQC material without invalidating the RSA signature that verifier
already checks. Section 7's literal order does not have this property:
under it, AltSignatureValue would sit outside what the RSA signature
covers, and (as testing below confirmed) is not just weaker but actually
incompatible with how `crypto/tls` verifies certificates at all --
Go's TLS stack always re-verifies the RSA signature against
`cert.RawTBSCertificate` exactly as received, so that signature MUST
cover the complete, final TBS (all three extensions) for an ordinary,
unmodified mTLS handshake to keep succeeding.

**Presented to the user before writing any code** (two options, with a
recommendation): follow Section 7's literal prose, or follow the real
Bindel et al. (2019)/ITU-T mechanism. **User chose the real mechanism**,
explicitly accepting the extra implementation cost (two-pass signing) for
fidelity to the cited reference and the tamper-evidence property it
provides, and asked that Section 7's prose be corrected afterward to
describe the real order -- done (see below).

**Minor factual correction to how this etapa was originally framed:**
certificate generation (`certs/main.go`) uses Go 1.27's own standard
library `crypto/mldsa` (confirmed via `go doc`; requires the
`golang:1.27-rc-alpine` image, not the `golang:1.23-alpine` this repo's
`certs/Dockerfile` still specifies for its unused `certmaker` build-only
service -- a stale, pre-existing, never-exercised build path, same
category of finding as Decision 3's RS Dockerfile issue, not touched here
since nothing in the actual pipeline invokes it). BouncyCastle is used
only on the Java RS side (Decision 3/4's JWS signing); it plays no role in
certificate issuance anywhere in this codebase.

**Implementation (`certs/main.go`):** new `generateHybridCert()`, invoked
via a new `-hybrid-name <name>` flag mirroring `-pqc-name`'s pattern.
Reuses existing key material exclusively, no new key generation: the
leaf's classical identity is its existing RSA key (`<name>.key`), its own
alt identity is its existing ML-DSA-65 key (`<name>_pqc.key`, published in
the new SubjectAltPublicKeyInfo extension). The signing side is "the same
local CA, two keypairs" per Section 7's own framing: `ca.crt`/`ca.key`
(RSA, as always) plus `issuer_ca_pqc.crt`/`.key` reused as that CA's alt
keypair -- previously only served as a decorative stand-in for Raidiam's
external sandbox PKI (Decision 11 in the v2 log), now given a real,
functional role for the first time. `issuer_ca_pqc`'s own chain to
`root_ca_pqc` is irrelevant here; only its keypair is reused, exactly
mirroring how the single-level classical `ca.crt` is trusted directly
with no intermediate.

Two real calls to `x509.CreateCertificate` against the same template
(same serial number and validity, computed once and reused, so the two
calls differ only in whether AltSignatureValue is present) -- not a
hand-built TBS. Call 1 (two extensions) exists only to get real,
correctly-encoded preTBSCertificate bytes via a new `extractTBSBytes()`
helper (DER-parses the outer `Certificate` SEQUENCE to pull out the
`tbsCertificate` field); its own RSA signature is discarded. The CA's
ML-DSA-65 key signs those preTBS bytes directly via Go's
`(*mldsa.PrivateKey).Sign(nil, message, nil)` (confirmed via `go doc
crypto/mldsa`: passing a nil/zero-HashFunc `opts` signs the message
directly, the "pure" FIPS 204 mode -- no hashing wrapper needed). Call 2
(three extensions, including the resulting AltSignatureValue) is the real,
final certificate. Generated for `client_one` (the OPIN client) and
`mtls` (the gateway's own server cert) -- Section 8's "cliente e
gateway." `op_hybrid` (the AS's own outbound mTLS identity toward the RS)
was deliberately not generated -- wiring it into `setup_ssm.sh`/the live
environment is full end-to-end integration, Etapa 7's territory, not
needed to prove this etapa's mechanism.

**Cryptographic proof, standalone (before touching the gateway):** a
throwaway Go program reconstructed each generated hybrid cert's
preTBSCertificate by parsing the FINAL (three-extension) cert and
removing AltSignatureValue -- via a `tbsCertificateForSurgery` struct
mirroring RFC 5280's TBSCertificate exactly, treating every field except
Extensions as an opaque passthrough. DER's canonical encoding guarantees
this reconstruction reproduces, byte for byte, whatever preTBS the CA's
ML-DSA-65 key actually signed during generation, regardless of which code
produced it -- confirmed empirically for both `client_one_hybrid.crt` and
`mtls_hybrid.crt`: the primary RSA signature verified via
`leaf.CheckSignatureFrom(ca.crt)` (exactly what an unmodified,
hybrid-unaware verifier already does), the reconstructed preTBS verified
against `issuer_ca_pqc`'s public key via `mldsa.Verify`, and a corrupted
alt signature was correctly rejected (negative control). `openssl x509
-text` and `openssl verify -CAfile ca.crt` also confirmed the backward-
compatibility promise directly: a generic, PQC-unaware tool already knows
the three extensions by their standard OIDs, treats them as ordinary
non-critical fields, and validates the RSA chain successfully.

**Gateway wiring (`mock_mtls/`):** `main.go`'s existing
`CRYPTO_PROFILE`-keyed cert selection gained a `hybrid` case (serves
`mtls_hybrid.crt`/`.key` -- an ordinary RSA cert/key pair as far as
`crypto/tls` itself is concerned; the ML-DSA-65 material rides along
inertly as extensions the handshake itself never inspects). New
`hybridVerification.go` adds the AND gate as a `tls.Config.
VerifyPeerCertificate` callback (only installed when
`CRYPTO_PROFILE=hybrid`, nil otherwise) -- this hook runs, per
`crypto/tls`'s own documentation, only AFTER normal (RSA chain)
verification already passed, so it never duplicates or replaces that
check; it only adds the second, ML-DSA-65 half via the same
reconstruct-preTBS-and-verify logic proven standalone above, gated shut
(reject) if the extension is missing, malformed, or the signature doesn't
verify.

**Tested against the real, running gateway** (`CRYPTO_PROFILE=hybrid`,
`auth`/`mtls`/`mongo_seed`/`mockapi` recreated together): a Go HTTPS
client presenting `client_one_hybrid.crt`/`.key` completed a real TLS 1.3
handshake and received a real `200` response from `/jwks` through the
gateway -- the gateway's own log shows both "AND gate passed (RSA +
ML-DSA-65 both valid)" and the completed-handshake entry. The same client
presenting the plain classical `client_one.crt` (no hybrid extensions) was
rejected by the server with `tls: bad certificate`, and the gateway's log
shows the precise reason: `"client certificate is missing the
AltSignatureValue extension"`. This is a live, on-the-wire proof of the
AND gate, not just an offline byte-level check.

**Not covered by this etapa, deliberately deferred:** `op_hybrid`
(AS-as-client identity) and any change to `setup_ssm.sh`/the live
environment's actual mTLS wiring for the full OPIN flow -- both belong to
Etapa 7 (`opin_flow.py` hybrid mode), which is where the environment
actually needs to run end-to-end with hybrid mTLS on every leg, not just
prove the certificate mechanism works. The client-side (Python)
verification of the GATEWAY's own hybrid server certificate is likewise
deferred to Etapa 7, mirroring how Etapa 4 scoped JWT verification to
standalone functions before any live wiring.

**Documentation fix applied as requested:** Section 7 of the
architecture document (`Arquitetura_Tecnica_Experimento3_Strong_
Nesting.docx` at the time -- since translated to English and converted
to `ARCHITECTURE.md`, see Decision 8) originally described the literal
(incorrect) signing order; its text has been corrected in place (via
`python-docx`, editing the existing paragraphs' runs directly to
preserve formatting) to describe the real order and the
security reason for it, matching what was actually implemented.

## 7. Etapa 7: opin_flow.py hybrid mode -- two real infrastructure bugs found and fixed, plus one pre-existing bug found that is NOT specific to hybrid

**Code changes, minimal by design** (per the architecture doc's own
framing: "reutilizados integralmente... produzem um terceiro conjunto de
valores"). `get_client_cert_paths()` gained a `hybrid` branch pointing at
`client_one_hybrid.crt`/`.key` (Etapa 6) -- an ordinary RSA cert/key pair
as far as this script's TLS stack is concerned. `load_client_signing_key()`
gained a `hybrid` branch that reuses `client_one.jwks`'s plain PS256 key
unchanged, NOT a hybrid-signed one -- mirroring Etapa 2's own documented
limitation (the AS's `requestObjectSigningAlgValues`/
`clientAuthSigningAlgValues` stay PS256-only in hybrid mode) and matching
Section 8's actual scope: only the AS/RS's own issued artifacts need the
hybrid signature; what the client sends isn't part of OPINsize's measured
quantities. Confirmed `pyjwt.decode(..., options={"verify_signature":
False})` (used by both `parse_rs_body()` and the JARM-decoding line in
`_CallbackHandler.do_GET`) does not choke on the unrecognized
`"MLDSA65-RSA2048-PSS-SHA256"` header value -- it never inspects `alg`
when signature verification is skipped, confirmed with a synthetic token
before touching the real environment.

**Bug found and fixed: RS header-size limit.** The very first real
end-to-end attempt failed with `413 Request Entity Too Large` on the
consent-creation POST, despite a 379-byte JSON body. Root cause: the
gateway forwards the client's full mTLS certificate PEM as the
`BANK-TLS-Certificate` header (Open Finance Brasil parity, pre-existing
for every profile). classic's PEM is 2078 bytes, pqc's 4056 -- both under
Netty's default 8192-byte (8KB) per-header limit, which nothing in this
repo overrides. Hybrid's PEM is 9345 bytes (the embedded ~1952-byte
ML-DSA-65 public key and ~3309-byte alt signature inflate it), already
over that default on its own. Presented to the user with two options
(raise the RS's header limit, or stop forwarding the full cert in hybrid
mode); **user chose raising the limit** -- added
`micronaut.server.netty.max-header-size: 32768` to
`insurance-server-lambdas/src/main/resources/application.yml`. Doesn't
affect any measured quantity (JWT/cert/handshake sizes are all measured
independently of this transport-layer limit) -- purely a capacity fix for
a limit that was never a deliberate architectural constraint, just an
unexamined default that nothing before hybrid ever got close to. Required
the same `certmaker`-adjacent Dockerfile workaround as Decision 3
(`insurance-server-lambdas/Dockerfile` is still the same pre-existing,
never-exercised broken build path for `dockerBuild`'s "main" image --
moved aside, let Micronaut generate its own, restored immediately after,
`git status` confirmed clean).

**Bug found and fixed: `op.crt` (the AS's own outbound mTLS identity)
needed a hybrid version too -- not deferrable to a later etapa as Decision
6 had assumed.** After the header-size fix, the flow progressed further
and failed with an oidc-provider `InvalidGrant` on the login/consent
page, traced (via the AS's own debug log, not the swallowed generic error
`InsurerAdapter.getConsent()` throws) to a raw TLS alert:
`SSL alert number 42` (bad_certificate). `InsurerAdapter.getConsent()`/
`updateConsent()` -- the AS's own backend calls to the RS, used to render
and update the login/consent screen -- present `op.crt` as their own mTLS
client identity, loaded from SSM (`setup_ssm.sh`'s
`transport_certificate`/`transport_key`, Decision 10 in the v2 log). Decision
6 assumed this backend leg was optional plumbing deferrable to Etapa 7,
but it turned out to be squarely on Etapa 7's own critical path (there is
no way to complete a real login/consent interaction without it) -- an
incorrect assumption at the time, corrected here rather than in Decision
6 itself, per the standing instruction not to rewrite past decisions.
Since the gateway's hybrid AND gate (Decision 6) rejects any client cert
without the three hybrid extensions once `CRYPTO_PROFILE=hybrid`, `op.crt`
being classical-only made this call fail the instant a real flow exercised
it. Fixed by generating `op_hybrid.crt`/`.key` (`certs/main.go
-hybrid-name op`, reusing `op.crt`/`op_pqc.crt`'s existing keys exactly
like `client_one_hybrid`/`mtls_hybrid` did), mounting it into `localstack`
alongside the existing `client_classic`/`client_pqc` volumes, and adding a
`hybrid` branch to `setup_ssm.sh` selecting it. `localstack`'s init script
reruns on every container start (confirmed via its own log output), so no
code changed in the container image itself -- only the compose volume
list and the shell script.

**Both flows verified complete end-to-end against the real, running
environment, each in its own process** (`CRYPTO_PROFILE=hybrid`, all four
services recreated together after each fix): `run_insurance_flow`
completed all 12 calls with 2xx status, including the full automated
login round-trip (PAR, simulated login/confirm, JARM callback, code
exchange) and the hybrid AND-gated mTLS handshake on every leg (both
`client_one_hybrid` for the OPIN client and `op_hybrid` for the AS's own
backend calls, both logged by the gateway as "AND gate passed").
`run_person_flow` completed all 16 calls with 2xx status, including
`parse_rs_body()` correctly reading claims out of hybrid-signed RS
response bodies to extract `policyId` and drive the remaining
sub-resource calls. 28/28 calls, matching the documented expected total
exactly.

**A third bug found -- real, but confirmed NOT specific to hybrid, and
not something this etapa introduced.** Calling `run_insurance_flow()`
then `run_person_flow()` in the *same Python process* -- exactly what
`main()` itself already does for every real scenario run -- reliably
failed on the second flow with `TimeoutError: No callback received after
simulated login`, reproduced 3/3 times in hybrid mode. A classic-mode
control run of the *identical* two-flows-one-process pattern (same code,
different `CRYPTO_PROFILE`) failed identically on the first attempt --
conclusively ruling out anything hybrid-specific (larger certs, heavier
handshakes, the AND gate) as the cause. This is very likely the same
family as the in-process resource-exhaustion issue already documented
from the Block B latency validation work, but newly observed here in a
shape (two *different* flows back to back, not the same flow repeated N
times) that the existing workaround -- "run the flow once per script
invocation" -- was never actually tested against, since every prior
Etapa's testing (2/3/4 and Block B's own validation) deliberately kept to
one flow call per process specifically to sidestep this. Each flow
individually is fully correct and complete (proven immediately above);
the failure is specific to the *second* HTTPS callback server spun up in
an already-used process, and is apparently profile-independent.

**Investigated and fixed, per the user's explicit choice** (stop the etapa
sequence and fix now rather than deferring or working around it in
`main()`). Root cause narrowed via tracing (a monkey-patched `do_GET` plus
a pre-connect socket probe, same non-invasive pattern used throughout this
project): the bug is **intermittent, not deterministic** -- an identical
run with only tracing added (no fix) passed cleanly on the very next
attempt, ruling out a hard deadlock or permanent resource exhaustion.
The actual mechanism: `simulate_login()`'s `session.post(.../confirm,
allow_redirects=True)` is supposed to follow the full redirect chain all
the way to the local callback server, but a broad
`except requests.exceptions.RequestException: pass` around that call
can't distinguish "reached the local server, then errored while
streaming the response back" (the expected, already-documented harmless
case) from "never reached the local server at all" -- and there was no
retry for the latter, silent-failure case; the code just waited out the
full 600-second poll timeout and gave up.

A separate, real (if secondary) issue was found in the same function
while reading it closely for this: `wait_for_authorization_code()` called
`server.shutdown()` but never `server.server_close()` (the former only
stops the `serve_forever()` loop; only the latter actually releases the
listening socket), and never deleted the temp cert/key files
`_generate_callback_tls_cert()` writes on every call. Neither was
confirmed to be the root cause of the timeout itself (a second server did
successfully rebind the same port in every failing trial, meaning the
first socket was evidently already being reclaimed some other way), but
both are genuine resource leaks independent of the race, fixed alongside
it.

**Fix**: `wait_for_authorization_code()` now retries `simulate_login()`
up to 3 times, each attempt getting a shorter 20-second window (instead
of one attempt getting the full 600 seconds) before giving up and trying
a fresh login from scratch -- safe to retry since `simulate_login()`
always starts a brand new interaction session, not a resume of a
half-finished one. `server.server_close()` and cert/key temp-file cleanup
now happen unconditionally via `try`/`finally`, on both the success and
every failure path.

**Verified with repeated trials, not a single pass** (a single pass would
not distinguish "fixed" from "got lucky," given the bug's own
intermittent nature): the full two-flows-one-process pipeline (matching
`main()` exactly, insurance then person, `compute_metrics()` included)
was run 3/3 times successfully in hybrid mode after the fix, plus one
more clean 28/28-call pass in classic mode as a regression check
confirming the fix doesn't change behavior for the already-working
single-attempt-success case. All four runs produced complete,
2xx-everywhere results.

This bug, its root cause, and its fix are unrelated to hybrid mode, the
Strong Nesting architecture, or anything else specific to Experiment 3 --
it was simply first noticed here because Etapa 7 was the first time this
project called `run_insurance_flow()` and `run_person_flow()` back to
back in one process outside of a real `python opin_flow.py <latency>`
invocation (every prior etapa's testing deliberately called one flow
function per script invocation specifically to avoid a *different*,
already-documented in-process issue -- see the Block B latency
methodology work).

**Known possibility for Experiments 1 and 2, explicitly not a finding of
actual harm.** `main()` -- the same entry point every real classic/pqc
scenario run used -- has always called `run_insurance_flow()` then
`run_person_flow()` in one process, i.e. always run under the exact
precondition this race needs. This bug was never fixed before today
because it was never known to exist before today, and the race is
intermittent, not certain, so it is possible (not confirmed, and not
assumed) that some already-completed Experiment 1/2 scenario run hit this
exact timeout at some point without it being recognized as this specific
issue. This does **not** invalidate the already-collected Experiment 1/2
data: that data has already been through multiple independent validation
passes (data-integrity audits, the 5-round median methodology for
unstable scenarios, cross-checks against raw Conformance Suite logs where
applicable -- see the v2 log and the Block B latency work) that would
plausibly have caught a truncated or incomplete run's downstream symptoms
even without knowing this exact root cause. Recorded here as a known,
disclosed possibility for the historical record, not a retroactive
correctness claim about past runs -- no retroactive investigation of
already-published Experiment 1/2 results was performed or is planned as
part of this etapa. Going forward, `main()`'s existing
two-flows-per-process structure is more resilient to it regardless of
`CRYPTO_PROFILE`.

## 8. Architecture document converted from .docx to Markdown/English, matching the rest of the project's documentation

`Arquitetura_Tecnica_Experimento3_Strong_Nesting.docx` -- the original
architecture document this whole log has referenced throughout -- was a
Word file in Portuguese, unlike every other document in this project
(`DECISIONS.md`, `README.md`, `BASELINE_REPORT.md`,
`EXPERIMENT{N}_REPORT.md`), all plain Markdown in English. Translated
faithfully, section by section, into `ARCHITECTURE.md` in this same
directory; the two embedded diagrams (Figure 1 -- the Strong Nesting
signing/verification activity diagram; Figure 2 -- the hybrid JWKS
composition/publication/discovery diagram) were extracted from the
`.docx`'s media parts as PNGs (`figure-1-strong-nesting-diagram.png`,
`figure-2-hybrid-jwks-diagram.png`) and embedded via ordinary Markdown
image syntax, rather than dropped -- both were inspected after
extraction and confirmed to match their surrounding "how to read this
figure" prose exactly.

Section 7's text in `ARCHITECTURE.md` reflects the corrected signing
order from Decision 6 (ML-DSA-65 first over the incomplete
preTBSCertificate, RSA last over the complete one), not the original,
incorrect literal order the `.docx` shipped with before that fix -- i.e.
this translation captures the document's already-corrected state, not a
second independent correction.

The original `.docx` has been deleted (`git rm`) once the Markdown
version was confirmed complete and accurate; every other reference to it
elsewhere in this log and in code comments (`ResponseSigningService.java`,
`hybridSigning.js`, `hybridVerification.js`, `hybrid_verify.py`) was
updated to point to `ARCHITECTURE.md` instead.
