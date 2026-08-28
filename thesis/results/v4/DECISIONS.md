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

## 9. Closing the Decision 7 gap: hybridizing client-side signing (client assertion, PAR request object) -- a real header-format asymmetry found and confirmed before writing any code

**Motivation.** The JWT-size investigation prompted by the user's own
sanity check on the Experiment 2 vs. 3 comparison (average JWT size
4123.88 bytes in hybrid vs. 5458.81 in pqc, counter-intuitive at first
glance) traced the gap to composition, not a bug: in pqc mode the client
signs its own client_assertion/PAR request object with ML-DSA-65 too (24
of 26 captured JWTs are algorithm-signed), while in hybrid mode those
same 8 client-originated artifacts stayed on plain PS256 (Decision 7's
documented, deliberate scope limit -- the AS didn't accept a hybrid
client assertion). The user asked to close that gap so hybrid reaches
the same 24/26 hybridized proportion pqc already has, leaving only the
JWE-wrapped id_token out (unavoidable on both profiles, see Decision 2).

**A real, inherent header-format asymmetry, found via research and
confirmed with the user before writing any code.** Every hybrid-signing
path built so far (Etapa 2's AS output, Etapa 3's RS output) has one
thing in common: the party constructing the hybrid artifact is also the
party who holds the private key and therefore can freely choose the
final header's bytes (including the combined `alg` string from Section
5) before computing sigma1 over it. Client-to-AS artifacts break that
assumption: the AS can only *verify* what the client already signed --
it never holds the client's private key, so it can never re-sign
anything. sigma1 is only a valid signature over the *exact* header bytes
the client used to compute it; if the AS's own interception logic
changed the header (e.g. to say the combined hybrid alg, or anything
else) before handing it to oidc-provider for its own PS256 check, sigma1
would no longer verify against that changed header, and the whole
mechanism would collapse.

The only workable construction, confirmed with the user: **the client
signs client_assertion/the PAR request object with an ordinary-looking
header from the start -- `alg: "PS256"`, `kid` set to the client's own
already-registered classical key (the same kid oidc-provider already
knows from `client_one.jwks`/`client_one_pub.jwks`) -- and sigma1 is
computed over exactly that header and payload.** sigma2 chains on top of
`header.payload.sigma1` as usual; the transmitted signature segment is
`base64url(sigma1‖sigma2)`, 3565 raw bytes, same convention as
everywhere else. At the header level this is indistinguishable from an
ordinary classical PS256 assertion -- only the signature segment's
*decoded byte length* (3565, not 256) reveals that it's actually hybrid.
The AS's new inbound interception middleware (active unconditionally
whenever `CRYPTO_PROFILE=hybrid`, mirroring how the outbound
rehybridization middleware is gated) decomposes sigma1/sigma2, verifies
both against the client's own classical and PQC public keys, AND-gates,
and -- only if both pass -- rewrites the signature segment down to just
sigma1 (256 bytes) before oidc-provider's own body-parsing/validation
ever sees it. oidc-provider then performs its completely ordinary,
unmodified PS256 verification of sigma1 against the (untouched) header
and payload, and succeeds exactly as it always has for a classical
client -- it is never told, and never needs to know, that anything
hybrid happened.

This means client-to-AS hybrid artifacts and AS/RS-to-client hybrid
artifacts use the *header* differently on the wire (PS256-shaped vs. the
combined `MLDSA65-RSA2048-PSS-SHA256` alg string) even though both use
the exact same Strong Nesting byte convention underneath
(`sigma1‖sigma2`, sigma1 first). This is a real, deliberate divergence
from Section 5 of `ARCHITECTURE.md` ("the field that identifies the
algorithm now declares the combination") -- noted there directly (see
the addendum at the end of Section 5) rather than silently buried here
only, per the user's explicit request. The asymmetry is inherent to the
direction of trust (who holds the private key), not an implementation
shortcut: there is no construction that lets the AS present a
self-describing combined-alg header to oidc-provider for something only
the client could have signed.

**Implementation.** `thesis/scripts/pqc-signer/sign.mjs` gained a third
input shape: `{jwk: private AKP JWK, message_b64}` (no `signature_b64`)
signs raw bytes directly via `webcrypto.subtle.sign()`, returning
base64 -- needed since opin_flow.py has no native ML-DSA-65 support and
now has to produce sigma2 client-side, not just verify it (Etapa 4's
scope). `opin_flow.py`'s `load_client_signing_key("hybrid")` now returns
a `(classic_key, pqc_jwk)` tuple and the classic kid; a new
`_sign_jwt_hybrid()` builds the PS256-shaped header, gets sigma1 from
pyjwt (parsing its own compact output to recover the raw signature
bytes, rather than reimplementing PS256 signing), and sigma2 from the
new pqc-signer mode, over `header.payload.sigma1`. On the AS,
`utils/opin/hybridVerification.js` gained `truncateIfHybrid()`
(decompose/verify/AND-gate, matching `verifyHybrid()`; on success,
returns the same header+payload with the signature truncated to sigma1
alone) and a new `utils/opin/clientHybridAuth.js` supplies client_one's
own classical and ML-DSA-65 public keys (read from
`client_one_pub.jwks`/`client_one_pqc_pub.jwks`, mounted into the `auth`
container unconditionally -- same always-mounted pattern as
`hybrid.json` -- since oidc-provider's own client registry only ever
holds the classical key, unchanged from classic/pqc mode) and the
inbound `provider.use()` middleware itself: for POST `/token` and POST
`/request`, it reads the raw request body by hand (a small inline
stream-to-string reader, not a new `raw-body` package dependency),
rewrites any hybrid-shaped `client_assertion`/`request` field, and
assigns the result to `ctx.request.body` -- confirmed via research into
oidc-provider 9.5.1's own source
(`lib/shared/selective_body.js`) that consuming the raw stream this way
is exactly the fallback path oidc-provider's own body-parsing already
handles (logging a one-time "already parsed request body detected"
warning, then using `ctx.req.body || ctx.request.body` instead of
re-reading the now-exhausted stream) -- confirmed live in the auth
container's own logs during testing below. Registered before the
existing outbound rehybridization middleware (Decision 2), since it has
to act before `await next()`, not after.

**A real bug found and fixed during first live testing.**
`hybridVerification.js`'s `verifyHybrid()`/`truncateIfHybrid()` had
`CLASSIC_SIG_BYTES` hardcoded to 256 -- correct for every prior caller
(the AS's own hybrid.json key, RSA-2048), but wrong for `client_one`,
whose signing key is the same RSA-**4096** key already used for its mTLS
certificate, not a fresh 2048-bit key minted for JWS. The bug surfaced
immediately and unambiguously as `signature verification failed` at
oidc-provider's own layer (not this project's code): a decoded combined
signature of 3821 bytes (512 + 3309) was being split at byte 256 instead
of 512, so sigma1 was reconstructed wrong and never verified --
`truncateIfHybrid()` correctly refused to touch the field, and
oidc-provider then rejected the still-3821-byte "PS256" signature it
was never going to accept at that length. Diagnosed by running
`verifyHybrid()` directly inside the running `auth` container against a
captured real client assertion (same `docker cp` + `docker exec`
diagnostic pattern used throughout this project) and comparing the
observed combined length against what 256+3309 vs. 512+3309 would each
predict. **Fixed** by deriving the classical signature length from the
actual key's own RSA modulus (`Buffer.from(classicPublicJwk.n,
'base64url').length`) instead of a hardcoded constant -- correct
regardless of which RSA key size ends up calling this function.

**Tested against the real, running environment**
(`CRYPTO_PROFILE=hybrid`, all four services recreated together after the
fix): a full `run_insurance_flow` + `run_person_flow` pass completed all
28 calls successfully, including the client's own hybrid-signed
`client_assertion` (sent to `/token`, both grants) and PAR `request`
object being accepted by the AS on every occurrence. Of the 26 captured
JWTs, **24 are now genuinely hybrid-signed** -- the 16 AS/RS-issued
artifacts (unchanged from before this etapa, `MLDSA65-RSA2048-PSS-SHA256`
header, 3565-byte signature) plus the **8 client-signed ones** (PS256
header as designed, but a 3821-byte decoded signature -- 512 bytes of
RSA-4096 sigma1 plus 3309 bytes of ML-DSA-65 sigma2 -- confirming Strong
Nesting is genuinely in effect even though the header alone can't show
it). Only the 2 JWE-wrapped `id_token`s remain outside hybrid signing,
exactly as Decision 2 already documents and as Section 5's addendum
above now states explicitly. Average JWT size at 0ms: **5481.42 bytes**,
up from 4123.88 before this etapa and now *above* pqc's own 5458.81 --
matching the proportion (24/26 hybridized, only the id_token held out)
that pqc and classic already have, closing the composition gap the
user's own sanity check on the Experiment 2/3 comparison had surfaced.
This closes the Decision 7 gap: the AS now accepts a properly
Strong-Nested hybrid client assertion.

**All 6 latency scenarios re-run with this fix**
(`thesis/results/v4/experiment3 - Hybrid/`, environment fully recreated
before each run, same protocol as the original Etapa 9 pass): 28/28
calls and 26/26 JWTs at every scenario, no PAR/request_uri retries
needed even at 140/225/320ms. The 26 raw JWT sizes are byte-for-byte
identical across all six scenarios (confirmed by direct list
comparison, not just the rounded average) -- latency has no effect on
artifact sizes, exactly as expected, and the fix is not scenario-
dependent. Average JWT size: **5481.42 bytes at every one of the 6
scenarios** (was 4123.88 before this etapa) -- now consistently *above*
pqc's 5458.81, the 24/26 hybridized proportion the user asked to match.
`consolidated.json` and `EXPERIMENT3_REPORT.md` regenerated from the new
per-scenario data.

## 10. Closing the last gap: hybridizing the id_token itself, via oidc-provider's `ExternalSigningKey` hook

**Motivation.** A user-driven investigation into a different anomaly (the
"AS bytes" participant total being lower in hybrid than pqc, despite
hybrid winning on every other metric) traced entirely to the `id_token`:
in both profiles it's the one artifact the outbound rehybridization
middleware (Decision 2) never reaches, because it's built and signed
entirely inside oidc-provider's own internal code, then immediately
JWE-encrypted, before the HTTP response the middleware inspects even
exists. In pqc mode this doesn't matter -- oidc-provider is configured to
sign it with real ML-DSA-65 natively. In hybrid mode it stayed plain
PS256, the one remaining non-hybridized AS-issued artifact. The user
asked to resolve this properly rather than accept it as permanent,
explicitly ruling nothing out until both a native-hook path and a
decrypt/re-sign/re-encrypt path were investigated.

**Path B (decrypt existing JWE, re-sign inner JWT, re-encrypt) --
investigated and confirmed structurally impossible, not merely
expensive.** Captured a live id_token and tried decrypting it with the
AS's own registered encryption key (`AS_ENC_JWK`) -- failed. Traced the
JWE header's `kid` to `client_one`'s *own* registered encryption key
(`client_one_pub.jwks`'s `use: enc` entry, matching kid exactly) and
confirmed decryption succeeds only with that key -- standard OIDC
behavior (id_token encryption always targets the RP's own public key so
only the RP can decrypt it), which this mock correctly implements.
`client_one`'s private half of that key exists only in
`client_one.jwks`, held by the Python/client side (`thesis/scripts/`),
never mounted into the `auth` container. For the AS to decrypt what it
just encrypted, it would need the client's private key -- which is not
an engineering inconvenience to work around, it's the exact thing id_token
encryption exists to prevent. No party legitimately holds both halves
needed (the AS's own signing keys AND the client's decryption key)
without breaking the security model. Path B was correctly ruled out.

**Path A (native hook) -- researched, verified, and implemented.**
Researched oidc-provider 9.5.1's actual source (downloaded the exact
pinned tarball from the npm registry, matching `package-lock.json`'s
integrity hash) rather than relying on documentation alone. Confirmed in
`lib/models/id_token.js`: signing (`JWT.sign()`) and encryption
(`JWT.encrypt()`) are two sequential calls in the same method with
nothing application-controlled between them -- no event, no hook. But
oidc-provider does expose a first-class, non-experimental-in-spirit
(though technically flagged `experimental-01` for acknowledgement)
mechanism for exactly this: `features.externalSigningSupport` +
`ExternalSigningKey`, both genuine public exports of the `oidc-provider`
package's own entry point (`lib/index.js`). A `jwks.keys` entry that's an
`ExternalSigningKey` instance causes oidc-provider to hand its own real
JWS signing input (`base64url(header) + "." + base64url(payload)`,
byte-for-byte) to that instance's `sign(data)` method and use whatever
bytes come back as the signature, unvalidated -- exactly the primitive
needed to substitute Strong Nesting's `sigma1||sigma2` in place of a
single PS256 signature, before oidc-provider proceeds to encrypt
whatever `sign()` returned.

**Confirmed constraint (expected, not a surprise):** the id_token's
header `alg` still has to say `"PS256"` -- oidc-provider validates the
client's `id_token_signed_response_alg` against its own kty/alg table
*before* ever calling into `ExternalSigningKey`, and doesn't recognize
the combined alg string. Same asymmetry already accepted for
client_assertion/the PAR request object (Decision 9), now extended to a
third artifact: header looks ordinary, only the signature's decoded
length (3565 bytes) reveals Strong Nesting is in use. Documented as an
addendum to Section 5 of `ARCHITECTURE.md` when Decision 9 was written;
no further doc change needed since it's the same rule, not a new one.

**Verified collision risk, per the user's explicit request, before
writing any implementation code.** Confirmed in `id_token.js`:
`keystore.selectForSign({ alg, use: 'sig' })` is called with no `kid` for
*both* `use: 'idtoken'` and `use: 'authorization'` (JARM) -- and both
resolve to the identical alg string in hybrid mode
(`idTokenSigningAlgValues`/`authorizationSigningAlgValues` are both
`internalSigningAlgs`). There is no documented way to scope a second
PS256-capable signing key to only one of them. Rather than relying on
undocumented array-order/stable-sort tie-breaking, the fix **replaces**
`internalSigningKey`'s plain-JWK entry in `jwks.keys` with the new
`HybridIdTokenSigningKey` (an `ExternalSigningKey` subclass) entirely in
hybrid mode, leaving exactly one PS256-capable signing key candidate --
nothing left to disambiguate. Also confirmed this is safe even in the
worst case: if it *were* also selected for JARM, the existing outbound
middleware (Decision 2) unconditionally rebuilds JARM's header and
signature from scratch regardless of what arrives, discarding whatever
came before -- so JARM would still end up correctly hybrid-signed under
the combined alg header either way, just with one redundant (thrown-away)
signing pass. Not a correctness risk in either branch.

**Implementation:** `hybridSigning.js` gained `signStrongNesting(message)`
(the shared sigma1||sigma2 primitive, extracted out of `rehybridizeJwt()`
so there's exactly one implementation instead of two) and
`CLASSIC_PUBLIC_JWK`/`CLASSIC_KID` (a real RFC 7638 JWK thumbprint via
jose's `calculateJwkThumbprint`, not an ad-hoc hash, even though nothing
external depends on this exact value now that there's only one signing
key). New `idTokenExternalSigningKey.js` defines
`HybridIdTokenSigningKey extends ExternalSigningKey`: `keyObject()`
returns the classic RSA public key (so oidc-provider can still export a
normal-looking public JWK for it if ever asked), `sign(data)` calls
`signStrongNesting(Buffer.from(data))`. `configuration.js` enables
`features.externalSigningSupport` (gated to hybrid mode, `ack:
'experimental-01'` to cleanly acknowledge the flag) and swaps
`internalSigningKey` for `new HybridIdTokenSigningKey()` in `jwks.keys`,
hybrid mode only.

**Tested against the real, running environment**, capturing both the
`id_token` and the JARM from the same live flow to check for the
collision in both directions at once: JARM's header is still
`{alg: "MLDSA65-RSA2048-PSS-SHA256", kid: HYBRID_KID}` with a 3565-byte
signature -- unchanged, no regression. The id_token, decrypted with
`client_one`'s own real private encryption key (confirming Path B's
finding empirically from the other side: this key genuinely works, it
just can never live on the AS), has header `{alg: "PS256", kid:
CLASSIC_KID}` and a **3565-byte decoded signature** -- and, going beyond
a length check (Etapa 2's `CompactSign` bug is exactly why length alone
was never trusted again in this project), `hybridVerification.js`'s
`verifyHybrid()` cryptographically confirms **both sigma1 and sigma2
independently verify** against the AS's real classic and PQC public
keys: `{valid: true, reason: 'both sigma1 and sigma2 verified'}`.

This closes the last remaining non-hybridized AS-issued artifact.

**All 6 latency scenarios re-run** (`thesis/results/v4/experiment3 -
Hybrid/`, environment fully recreated before each run): 28/28 calls,
26/26 JWTs at every scenario. The 26 raw JWT sizes are byte-for-byte
identical across all six scenarios. **The two 1812-byte JWE entries
(the id_token, previously the only non-hybridized artifact) are gone,
replaced by two 7695-byte entries** -- confirmed via a live labeled
capture that all 24 visibly-3-segment JWTs are hybrid-signed (16
AS/RS-issued at 3565 bytes, 8 client-signed at 3821 bytes, Decision 9)
and, via decrypt + `verifyHybrid()`, that the 2 JWE-wrapped id_tokens are
now hybrid-signed internally too -- **26/26, not 24/26**. Average JWT
size: **5933.96 bytes at every one of the 6 scenarios** (up from 5481.42
before this decision). `N_mTLS` (6) and `mTLS_handshake_bytes` P50
(24991.0) are unchanged from before this decision, exactly as
expected -- id_token signing doesn't touch the mTLS transport layer at
all. `client_cert_bytes` isolation (6859 vs. `op_hybrid`'s 6842)
reconfirmed intact across the cumulative gateway logs from all these
runs. `/jwks` reconfirmed still correctly publishing the 2208-byte
`pk_hybrid` (Decision 5, untouched by this change -- separate mechanism
from the internal signing keystore this decision modifies).

**OPINsize recomputed**: 6×24991.0 + 26×5933.96 + 2×2208 = 149946 +
154282.96 + 4416 = **308644.96 bytes** -- up from 296878.92 before this
decision, a delta of 11766.04 bytes. That delta reconciles exactly: the
id_token's own size grew by 7695−1812 = 5883 bytes, and it's issued
twice per full run (once per flow) -- 5883×2 = 11766, matching the
OPINsize delta almost exactly (the few remaining cents are the id_token
now also being 2 of the 26 entries feeding the `jwt_size_avg_bytes`
term, not a separate effect). Final growth: **+16.75% over pqc**
(264374 bytes), **3.24x over classic** (95232 bytes) --
`consolidated.json`/`EXPERIMENT3_REPORT.md` regenerated from this final
data, confirmed no stale values remain (grepped for the two prior
average figures, 4123.88 and 5481.42 -- neither appears anywhere in the
final files).

**Regression check, all prior etapas**: JARM re-verified from a live
capture in the same test run that captured the id_token -- still
`{alg: "MLDSA65-RSA2048-PSS-SHA256", kid: HYBRID_KID}` with a 3565-byte
signature, unchanged (confirms the collision risk investigated above
never actually manifests as a problem in practice, whether or not it
technically occurs). Etapa 5 (`/jwks`) reconfirmed live. Etapa 6 (mTLS
certificates) is a separate Go implementation never touched by this
change. Decision 9 (client-side hybrid signing) reconfirmed working --
every one of the 6 scenario runs required the AS to accept a hybrid
client_assertion/PAR request object to complete at all.

**A separate, real finding surfaced during these re-runs, investigated
but not fixed (out of scope for this decision, pre-existing and
unrelated to id_token signing).** The very first 30ms attempt failed
with `InvalidGrant` from `InsurerAdapter.getConsent()`, traced (via the
AS's own debug log, not the swallowed generic error) to an actual `401
Unauthorized` from the RS -- not a TLS/certificate problem this time
(ruled out: no SSL alert in the log, unlike Decision 7's earlier
op_hybrid finding). A clean retry of the identical scenario succeeded
immediately, so it's intermittent, not systematic -- confirmed by all 6
scenarios (including a second attempt at 30ms) completing cleanly
afterward. While investigating, found what looks like a real, pre-existing,
unrelated bug in `InsurerAdapter.getToken()`
(`mock-service-os/mock_as/utils/opin/adapter.js`): `this.nodeCash.set(hash,
this.token, 2000)` caches `this.token` (a property that is never set
anywhere in the class) instead of the local `token` variable the
function just obtained -- meaning the internal AS-to-RS token cache
silently never has a hit, and every `getConsent`/`updateConsent` call
does a full fresh internal OAuth exchange instead of reusing one for up
to 2 seconds as the code clearly intends. This bug predates every etapa
in this document (no session in this log ever touched `adapter.js`) and
is not proven to be the 401's root cause -- id_token signing, the actual
subject of this decision, plays no role in this specific call path
either (`getConsent` happens during consent-status polling, before
login, and never touches an id_token). Recorded here as a disclosed,
unresolved observation rather than investigated further or silently
patched, per the standing instruction to report before fixing anything
not explicitly asked for.

## 11. Closing the last symmetry gap: `root-ca.pem`/`issuer-ca.pem` given hybrid stand-ins too

**Context.** Decision 12 in `thesis/results/v2/experiment2 - PQC/DECISIONS.md`
gave `root-ca.pem`/`issuer-ca.pem` local ML-DSA-65 stand-ins for
`CRYPTO_PROFILE=pqc` (`root_ca_pqc.crt`/`issuer_ca_pqc.crt`, pure
ML-DSA-65 leaf certs, no RSA counterpart), served by
`mock_mtls`'s `directoryHandler()` at `https://directory/root-ca.pem`/
`/issuer-ca.pem`. Hybrid mode was never given an equivalent -- `opin_flow.py`'s
`ca_host` selector only branched on `crypto_profile == "pqc"`, so hybrid
silently fell into the `else` branch and hit the real, external, classical
Raidiam sandbox (`crl.sandbox.pki.opinbrasil.com.br`), breaking the
symmetry every other artifact in this experiment already has.

**Investigation, before implementing anything:**
1. **How the PQC stand-ins were built**: complete replacement, not
   coexistence -- confirmed by reading Decision 12 directly.
   `root_ca_pqc`/`issuer_ca_pqc` are pure ML-DSA-65 leaf certs (`certs/main.go
   -pqc-name`), signed by the classical local CA, with no RSA key of their
   own. There was nothing classical to reuse for hybrid; two brand-new RSA-4096
   keys had to be generated first (`root_ca.key`/`issuer_ca.key`, PKCS8, via
   `openssl genpkey` -- run only after the user explicitly authorized local
   key generation).
2. **Confirmed the silent-classical-fallback exactly as suspected**:
   `opin_flow.py:706`, `ca_host = "directory" if crypto_profile == "pqc" else
   "crl.sandbox.pki.opinbrasil.com.br"` -- hybrid fell through to the real
   external host with no warning.

**Implementation**, mirroring Section 7's dual nested combiner exactly (same
mechanism as `client_one_hybrid`/`mtls_hybrid`/`op_hybrid`):
- `certs/main.go -hybrid-name root_ca` / `-hybrid-name issuer_ca` (via
  `docker run golang:1.27-rc-alpine`, same cached image already used for
  every other hybrid cert): reuses the newly-generated `root_ca.key`/
  `issuer_ca.key` (RSA-4096) as each subject's classical identity and the
  already-existing `root_ca_pqc.key`/`issuer_ca_pqc.key` (ML-DSA-65) as each
  subject's alt identity, signed by the local CA's RSA key (`ca.key`) plus
  its ML-DSA-65 alt key (`issuer_ca_pqc.key`, the same reuse convention every
  other hybrid cert already uses). Output: `root_ca_hybrid.crt`/`.key`,
  `issuer_ca_hybrid.crt`/`.key`.
- Standalone cryptographic proof before wiring anything in (same "reconstruct
  preTBS, verify both halves, corrupt-signature negative control" method
  Decision 6 used) -- reused `mock_mtls/hybridVerification.go`'s own
  `reconstructPreTBS`/AND-gate logic verbatim in a throwaway Go program
  rather than re-deriving it, since that's the actual, already-proven
  production verifier. Both certs: RSA chain verified via
  `CheckSignatureFrom(ca.crt)`, ML-DSA-65 alt signature verified against the
  reconstructed preTBS, corrupted-signature negative control correctly
  rejected.
- `mock_mtls/main.go`: `rootCaPqcFilePath`/`issuerCaPqcFilePath` stayed a
  `const`, unchanged -- `issuerCaPqcFilePath` has a second, unrelated use
  (`hybridVerification.go` reads it for the CA's own ML-DSA-65 public key,
  the client-certificate AND gate's verification key, which must stay the
  pure-ML-DSA-65 cert in every profile regardless of what `/issuer-ca.pem`
  itself serves). New `rootCaServeFilePath`/`issuerCaServeFilePath` vars,
  profile-keyed in `init()` exactly like `serverCertFilePath` already is,
  govern only what the two HTTP routes serve. Deliberately kept as two
  separate variable sets so the AND gate's key source and the served content
  could never accidentally couple.
- `opin_flow.py`: `ca_host` now checks `crypto_profile in ("pqc", "hybrid")`.

**Validated end-to-end**: `/root-ca.pem`/`/issuer-ca.pem` fetched live,
byte-for-byte identical to the on-disk `root_ca_hybrid.crt`/
`issuer_ca_hybrid.crt`. A full live flow (both `run_insurance_flow`/
`run_person_flow`) completed with no errors. The client-certificate AND
gate (unrelated to this fix, but on the same code path) reconfirmed
unaffected via a fresh JARM capture and a fresh 26/26 cryptographic
re-verification of every JWT (see the sabatina below).

**PKI/CRL result**: 19216 bytes per flow fetch (9606 root-ca.pem + 9610
issuer-ca.pem) x 2 flows = **38432 bytes per scenario**, stable across all 6
re-run latency scenarios. Isolated via an A/B test (rerunning the identical
flow with `ca_host` monkeypatched back to the old real-external value,
live, in the same container): only the `PKI/CRL` participant total changed
(38432 -> 10664, matching classic's own range almost exactly, as expected
since both now fetch the real external files) -- `AS`/`RS` totals were
**identical in both configurations**, proving they are NOT caused by this
change (see the sabatina below for what they actually are). Hierarchy now
matches every other metric in this experiment: classic (10664-10670) < pqc
(17276) < **hybrid (38432)**.

**Sabatina finding, disclosed and isolated, not silently absorbed: `AS`/`RS`
bytes-by-participant and `mTLS_handshake_bytes` P50 shifted from their
previously-committed values, for a reason unrelated to this decision.**
Re-running the 6 scenarios in the freshly rebuilt environment gave `AS
=78231` (was 78311, -80), `RS=102075` (was 102235, -160), and
`mTLS_handshake_bytes` P50 `=25880.0` (was 24991.0). The A/B test above
proves the `AS`/`RS` shift is independent of this decision's own change
(both configurations gave the identical 78231/102075). Raw gateway log
inspection traced the handshake-bytes shift to the same, already-documented
measurement caveat `connStateHandshakeLogger`'s own comment names directly:
`mtlsHandshakeBytes` "may also include a few early application-data bytes
if the client pipelined its first request into the same TCP read/TLS
record as the handshake's tail end" -- confirmed empirically, the raw
per-connection samples for `client_one_hybrid` (clientCertBytes=6859) show
several distinct values within a single run (25820/26075/25880), not one
constant, so which one lands on the P50 is sensitive to exactly this kind
of pipelining variance. This project's own environment-recreation protocol
fully rebuilds the container on every re-run round; nothing in `git diff`
touches TLS handshake logic, `go.sum` is unchanged (no dependency drift),
and the `golang:1.27-rc-alpine` image used for cert generation is the same
cached digest as every prior round -- ruling out a code or toolchain
regression. This is the same class of run-to-run noise already documented
for `total_bytes_exchanged` (a handful of bytes across scenarios) and
`PKI/CRL` pre-fix, just larger in this instance. Recomputed OPINsize with
the new P50: `6x25880.0 + 26x5933.96 + 2x2208 = 313978.96` bytes -- note the
OPINsize equation itself has no `PKI/CRL`/`AS`/`RS`/`Client` term, so this
decision's own fix has **zero direct effect on OPINsize**; the entire
+5334.0 byte delta from the previously-committed 308644.96 traces to the
unrelated handshake-bytes noise above, not to anything this decision
touched.

## 12. Total flow latency across the 6 scenarios, all three experiments: single-run methodology replaced with a 5-run median, and a real (not noise) explanation for the 0ms direction reversal

**Context.** A review of `thesis/results/v3/Experimental_Metrics_PQC_OPIN_v2.md`'s
"Total flow latency across all 6 network scenarios" table (classic vs. pure
PQC only -- Experiment 3/hybrid never had an equivalent) noticed the
classic/PQC delta oscillating without a consistent direction across the
6 latency scenarios (+14% at 0ms, -7% at 14ms, +1% at 30ms, -0.4% at 140ms,
+11% at 225ms, +6% at 320ms) -- not the pattern expected if PQC's larger
byte volume (already established via the OPINsize equation) were the
dominant driver of its cost.

**Methodology, confirmed from the document itself, not assumed:**
`Experimental_Metrics_PQC_OPIN_v2.md` line 101 states plainly that only the
**0ms** scenario used a 5-independent-run median (matching Decision 14's own
per-endpoint methodology in the same document); the other 5 scenarios
(14/30/140/225/320ms) were each a **single run**, reconstructed from
`consolidated.json`'s `mean_ms x count` per endpoint. The document's own
prose (line 103) already flagged this as a limitation: with a single run per
non-zero scenario, the observed deltas "are within the range of run-to-run
noise... should not be read as a stable trend."

**Re-measured all 3 experiments, all 6 scenarios, 5 independent runs each
(90 total flow executions)**, following Decision 14's exact protocol: each
run its own subprocess (never looped in one process -- Decision 14's
"Problem 2", in-process resource exhaustion), containers recreated once per
profile before its run series, one throwaway warmup run for pqc and hybrid
specifically (both drive ML-DSA-65 signing through BouncyCastle on the RS
side, both pay the same first-request JVM/provider cold-start cost Decision
14 first isolated for pqc; hybrid was not separately confirmed to have this
issue before, but the very first flow after every container recreation in
this round showed the same signature -- an outlier roughly 3-5x every other
run in that series -- so the same warmup treatment was applied). classic's
0ms and 14ms series each had one first-run-after-recreation outlier too
(4656.83ms and 6843.34ms respectively, against a otherwise-tight
800-1100ms/2370-2730ms spread) -- not replaced, since in both cases the
outlier landed at the max of its 5-run set and the median (which depends
only on the middle value) is completely unaffected either way, the same
reasoning already used in the existing 5-round table's own run-1
substitution note. Two isolated failures (hybrid 320ms run 4, pqc 320ms
run 5) hit the already-documented PAR `request_uri` 60s-TTL limit at high
injected latency (`EXPERIMENT3_REPORT.md`'s own "Known limitations"
section) -- retried once, succeeded, no impact on the reported median.

**Median-of-5 total flow latency (ms), all three experiments:**

| Scenario | Classic | PQC | Hybrid | Delta (PQC-Classic) |
|---|---|---|---|---|
| 0ms | 983.55 | 931.17 | 1074.60 | -52.38 (-5.3%) |
| 14ms | 2660.92 | 3102.83 | 2255.06 | +441.91 (+16.6%) |
| 30ms | 3965.06 | 4643.60 | 4022.77 | +678.54 (+17.1%) |
| 140ms | 14443.27 | 15944.92 | 16347.11 | +1501.65 (+10.4%) |
| 225ms | 23594.30 | 24993.51 | 26022.48 | +1399.21 (+5.9%) |
| 320ms | 32729.39 | 35379.01 | 36662.44 | +2649.62 (+8.1%) |

With the median in place of a single run, the classic/PQC delta stops
oscillating: PQC is consistently slower from 14ms through 320ms (5 of 6
scenarios), with the gap growing in absolute terms as the number of
round trips (and therefore accumulated signing/verification calls) grows --
exactly the pattern expected if cryptographic cost, not sampling noise,
is the dominant driver at non-zero latency. Hybrid tracks the same
direction as PQC at every non-zero scenario, consistently above both.

**The 0ms reversal (PQC 5.3% *faster* than classic) is real and has a
specific, identified cause -- not sampling noise, and not a reversal of
which algorithm costs more to compute.** Per-call breakdown (3 confirmatory
runs per profile, cold-start-affected first runs excluded from the
decomposition below) isolates the two `root-ca.pem`/`issuer-ca.pem` calls
from everything else:

| Portion | Classic | PQC | Hybrid |
|---|---|---|---|
| PKI (`root-ca.pem`+`issuer-ca.pem`, both flows) | ~258ms | ~48ms | ~56ms |
| Everything else (the signing/verification-bearing calls) | ~597ms | ~1104ms | ~1475ms |

The "everything else" row is unambiguous and matches every prior
per-endpoint finding in this thesis (Decision 14's own table): RSA-2048/
4096 < ML-DSA-65 < RSA+ML-DSA-65 -- classic cheapest, hybrid most
expensive, no reversal. The reversal comes entirely from the PKI row:
classic's `root-ca.pem`/`issuer-ca.pem` calls still hit Raidiam's real,
external sandbox (`crl.sandbox.pki.opinbrasil.com.br`, Decision 10/12's
deliberate choice to treat this as genuine ecosystem infrastructure, not
something to fake locally), while pqc's and (as of Decision 11) hybrid's
own calls hit the local `directory` stand-in inside the same Docker
network. A single `root-ca.pem` fetch was observed varying between 76ms
and 680ms across otherwise-identical classic runs -- real, uncontrolled
internet latency to an external host, entirely independent of the
`tc/netem`-injected scenario latency (these two calls never traverse the
gateway container that latency is injected on). At 0ms, this fixed,
classic-only ~200ms-plus tax is large enough relative to the ~900-1100ms
total to flip the net comparison; at every other scenario, the same fixed
tax is a rounding error against totals in the 2,000-36,000ms range, so the
real (and consistently-directioned) cryptographic cost delta dominates
instead unopposed. This also means classic's own 0ms measurement carries
an irreducible noise source no amount of additional runs removes: live
internet conditions to a real external server, not present anywhere else
in this local, fully-Dockerized experiment.

**Not implemented, and not needed**: no code change resulted from this
decision -- it is a measurement/reporting decision only. The existing
`Experimental_Metrics_PQC_OPIN_v2.md` (Experiments 1/2, an earlier phase of
this thesis) is left untouched per instruction; this decision's 3-column
table (adding hybrid) is the one to cite going forward for total flow
latency across all three experiments.

## 13. Migrating the JWT hybrid signature from Strong Nesting to a payload-extension scheme -- a deliberate security-property tradeoff, proposed by the advisor

**Context and motivation.** Every hybrid JWT in this project has, since Etapa 2,
used Strong Nesting (Bindel et al., 2017): sigma1 = classical_sign(message),
sigma2 = ML-DSA-65_sign(message‖sigma1), signature = base64url(sigma1‖sigma2)
-- ML-DSA-65 *last*, over a message that already includes the classical
signature. This gives SUF-CMA (strong unforgeability): nobody can produce a
second valid signature over the same message, even with the first signature
in hand. The advisor proposed the opposite composition: extend the *payload*
with a `pqc` claim carrying the ML-DSA-65 signature, computed FIRST over the
claims alone, then let the classical algorithm sign LAST, over the whole
JWS input (header + payload, the payload already carrying `pqc`) -- the same
ordering principle Etapa 6's hybrid X.509 certificates already use (PQC
first over a preTBS, RSA last over the complete TBS), now applied to JWTs.
The header reverts to an ordinary `{"alg": "RS256", "typ": "JWT"}` (RS256,
not PS256 -- a deliberate part of this scheme, chosen for maximal
legacy-verifier compatibility) -- no custom alg string, no interception of
oidc-provider's own signing step needed for artifacts using this scheme,
since the token it produces is byte-for-byte an ordinary, valid RS256 JWT;
`pqc` is just an extra, ignorable claim to a verifier that's never heard of
it. This is a deliberate trade: **SUF-CMA gives way to EUF-CMA** (existential
unforgeability -- nobody can forge a *new* message's signature, but a
second signature over the *same already-signed* message is not excluded by
the primitive alone). Accepted because none of this project's consents ever
circulate with their classical and PQC signatures detached from one
another for an attacker to recombine -- the practical recombination risk
SUF-CMA defends against does not apply to how OPIN actually moves these
artifacts. References backing this analysis: Bindel, Herath, McKague &
Stebila (2017, PQCrypto, the Strong Nesting composition itself and its
SUF-CMA proof); Bindel, Braun, Gladiator, Stebila & Wiggers (2019, JOSS,
the X.509 hybrid-extension mechanism this JWT scheme mirrors); Brendel,
Cremers, Jackson & Zhao (2021, IEEE S&P, "The Provable Security of
Ed25519" -- SUF-CMA vs. EUF-CMA in practice, and why protocol-level context
often makes the weaker property sufficient); Bhargavan et al. (formal
protocol analyses that assume SUF-CMA as a base building block, the
standard this project is deliberately relaxing); and the F1000Research
review on strong-unforgeability signature schemes (survey grounding for
why this distinction is a recognized, named tradeoff in the literature,
not an ad hoc justification).

**Investigation before writing any code -- two real technical obstacles
found, reported, and resolved with the user before implementing anything:**

1. **JSON has no canonical serialization.** Verifying `payload.pqc.signature`
   requires removing `pqc` from the received payload and RE-SERIALIZING the
   remainder to reproduce the exact bytes ML-DSA-65 signed -- unlike DER
   (used for the X.509 case this mirrors), plain JSON has no single
   canonical encoding, so Node's `JSON.stringify`, Java's Jackson, and
   Python's `json.dumps` are not guaranteed to reproduce each other's
   byte-for-byte output. **Resolved: adopt RFC 8785 (JSON Canonicalization
   Scheme, JCS) formally**, implemented identically on all three sides via
   established reference libraries (not hand-rolled, to avoid exactly the
   kind of subtle cross-language divergence this problem is about):
   `canonicalize` (npm, Node/AS), `io.github.erdtman:java-json-canonicalization`
   (Maven, the JCS spec author's own reference implementation, Java/RS),
   `rfc8785` (PyPI, Python/client). ML-DSA-65 signs the JCS-canonical bytes
   of the claims WITHOUT `pqc`; the JWT payload segment itself does NOT
   need to be JCS (it's transmitted verbatim and RS256 covers it exactly
   as produced, no reconstruction needed there) -- JCS is only load-bearing
   for the one step that has to be reproduced independently.

2. **id_token and JARM have no public extension point to inject `pqc`
   before oidc-provider's native signing pass.** Traced directly in
   oidc-provider 9.5.1's own source (downloaded via `npm pack`, same
   method as Decision 10's investigation): both id_token and JARM are
   built through the exact same internal `IdToken` class
   (`lib/models/id_token.js`; `lib/response_modes/jwt.js`'s JARM handler
   literally does `new IdToken({}, {ctx}); token.extra = payload;
   token.issue(...)`) via a `payload()` method and a `set()` method that
   are never exposed through any documented configuration hook --
   `extraTokenClaims` (already used elsewhere in this codebase) only
   applies to opaque/JWT-formatted *access tokens*, a different code path
   entirely. Decision 10's `ExternalSigningKey` mechanism does not help
   here either: its `sign(data)` hook receives `data` already fully
   serialized (`base64url(header) + "." + base64url(payload)`) -- there is
   no way to modify the payload from inside it, only to supply alternate
   signature bytes over what's already fixed. The only remaining path
   would be monkey-patching `IdToken.prototype.payload` at boot --
   depending on undocumented library internals rather than a supported
   extension point. **Decided with the user: do not do this.** id_token
   and JARM stay on Strong Nesting exactly as Decision 10 left them,
   completely untouched by this decision -- an explicit, justified scope
   exception, not a gap: the fragility a prototype-patch would introduce
   (breaking silently on any future oidc-provider upgrade that
   restructures this internal class) is disproportionate to the benefit
   of migrating two artifacts whose current mechanism already works
   correctly and needs nothing from this decision.

**Implementation, on every artifact WITHOUT this blocker** (RS-issued
Consents/Person responses, client_assertion, the PAR request object --
`tokens do AS` beyond id_token/JARM turned out not to exist as a distinct
category in this codebase: nothing else was ever routed through
`hybridSigning.js`'s outbound `rehybridizeJwt`/`rehybridizeInPlace`
middleware in practice, confirmed by tracing every caller):

- **RS** (`ResponseSigningService.java`): `sign()`'s signature changed from
  `sign(byte[] jsonPayload)` to `sign(Object body)` -- the RS needs the
  claims as a mutable structure to inject `pqc` before final
  serialization, not pre-serialized bytes. A new `JwsSigner.preparePayload`
  hook (default no-op, so classic/pqc signers are untouched) lets the
  hybrid signer do this; `signToBase64Url` for hybrid is now a single,
  ordinary RS256 signature (`JWSAlgorithm.RS256`, not `PS256`) -- Strong
  Nesting's sigma1/sigma2 combination logic is gone entirely from this
  path. `alg()` now returns `"RS256"`.
- **Client** (`opin_flow.py`'s `_sign_jwt_hybrid`): builds `claims`, signs
  `rfc8785.dumps(claims)` with ML-DSA-65 via the pqc-signer docker helper's
  raw-sign mode, embeds the result as `claims["pqc"]`, then
  `pyjwt.encode(..., algorithm="RS256", ...)` as the final step.
- **AS verification** (new `payloadExtensionVerification.js`, alongside --
  not replacing -- `hybridSigning.js`/`hybridVerification.js`, which stay
  exactly as they are for id_token/JARM): verifies RS256 first over the
  received header+payload, then extracts `payload.pqc.signature`, removes
  `pqc`, JCS-canonicalizes the remainder, and verifies ML-DSA-65 against
  that. `clientHybridAuth.js` (Decision 9's inbound middleware) now calls
  this instead of `truncateIfHybrid` -- and, unlike Decision 9, **no
  longer needs to rewrite the request body at all**: a payload-extension
  token is already an entirely ordinary, valid RS256 JWT the instant it
  arrives, so oidc-provider's own native verification already accepts it
  unmodified. The middleware's only remaining job is the one check
  oidc-provider cannot perform on its own -- if `pqc` is present but its
  ML-DSA-65 signature fails, reject the request outright (HTTP 400)
  before oidc-provider ever sees it, since its own RS256-only check would
  otherwise still accept a token whose PQC half was invalid or absent,
  silently downgrading the AND gate to an OR gate. `truncateIfHybrid`/
  `verifyHybrid` in `hybridVerification.js` have no remaining callers
  anywhere in this codebase after this change -- left in place (not
  deleted) since id_token verification conceptually still relies on the
  same primitive being available/correct, but flagged here as dead code
  from this decision's own perspective.

**Two real, un-anticipated fixes found only by running a real flow, not
by reading the code in isolation:**

- `configuration.js`'s `internalSigningAlgs` (`['PS256']` for hybrid) fed
  BOTH the id_token/JARM config keys (`idTokenSigningAlgValues`,
  `authorizationSigningAlgValues`, correctly still PS256) AND the
  client-auth config keys (`clientAuthSigningAlgValues`,
  `requestObjectSigningAlgValues`, plus the `request_object_signing_alg`/
  `request_object_signed_response_alg` client-metadata defaults) from the
  same constant. Under the new scheme the client signs with RS256, not
  PS256 -- reusing `internalSigningAlgs` there would have oidc-provider
  reject every client_assertion/PAR object outright, before
  `clientHybridAuth.js` even runs. Fixed by splitting off a new
  `clientSigningAlgs` constant (`['RS256']` for hybrid) and repointing
  exactly the client-facing config keys at it, leaving id_token/JARM's own
  keys on the original `internalSigningAlgs`/PS256.
- `client_one_pub.jwks`'s registered signing key still carries
  `"alg": "PS256"` (this file is shared with classic mode, where that's
  still correct -- `certs/main.go`'s `generateJWKS()` always sets it that
  way regardless of profile, so patching the source file directly would
  silently revert on the next regeneration). oidc-provider's own
  `keystore.js` (`selectForDSA`, confirmed by reading the downloaded
  source directly) only enforces an alg match when the candidate JWK
  itself carries an `alg` field -- so the fix is to strip `alg` from
  client_one's registered *signing* key specifically at MongoDB-seed time
  (`mongo-seed/start.sh`, hybrid-mode-only `jq` transformation, right
  after the existing profile-conditional JWKS-selection block), making the
  same physical RSA key a valid candidate for either PS256 (classic) or
  RS256 (hybrid) without weakening the match (`kid`+`kty`+`use` still
  fully scope it) and without touching the shared source file at all.

**Validated end-to-end, live, before any scenario re-run:** a full flow
(both `run_insurance_flow`/`run_person_flow`) completed 28/28 calls with no
errors on the first attempt after wiring everything together. Classifying
all 26 captured JWTs by header alg and presence of a `pqc` claim: 2 JWE
(id_token, unaffected), 16 RS-issued + 8 client-issued all `alg: "RS256"`
with `pqc` present -- exactly the expected split, nothing left on the old
combined-alg header outside id_token. Full independent cryptographic
re-verification (fresh keys derived from each participant's own key
material, not reusing any earlier session's trusted constants, same
discipline as every prior sabatina in this document), reusing the actual
production `payloadExtensionVerification.js` as a library: **26/26 valid**
-- 16 against the RS's own key, 8 against client_one's, both via the new
scheme; the 2 id_tokens still valid via the unchanged, original
`verifyHybrid` (Strong Nesting). JARM re-verified from a fresh, independent
live capture: still `{alg: "MLDSA65-RSA2048-PSS-SHA256", kid: HYBRID_KID}`,
AND-gate valid, byte-for-byte the same shape as before this decision --
confirming the id_token/JARM exception holds in practice, not just on
paper. Negative-control coverage: the 3-identity verification loop
(AS/RS/client_one) itself constitutes 52 implicit negative controls across
the 26 tokens -- every token was rejected by the two non-matching
identities and accepted only by the correct one, exercising the actual
rejection path (not just the accept path) for both `RS256` and
`ML-DSA-65` verification without needing a separately fabricated tampered
token.

**Regression check on the two mechanisms this decision's Java refactor
could plausibly have disturbed even though neither is in its stated
scope** (`ResponseSigningService.sign()`'s signature changed for every
profile, not just hybrid): re-ran classic and pqc 0ms fresh, live, and
diffed the resulting `jwt_sizes_bytes` list against the already-committed
`thesis/results/v3` baselines for both -- **byte-for-byte identical in
both profiles** (classic: avg 1385.42, 26/26 sizes match exactly; pqc: avg
5458.81, 26/26 sizes match exactly). The `sign(Object body) ->
objectMapper.convertValue(..., Map.class) -> preparePayload (no-op for
classic/pqc) -> writeValueAsBytes` round trip is confirmed lossless for
both untouched profiles.

**Re-ran all 6 latency scenarios (hybrid)**, all completed cleanly with no
retries needed this time (unlike Decision 11's round, which hit the
already-documented PAR TTL issue twice). Every metric perfectly stable
across all 6 scenarios (0/14/30/140/225/320ms):

| Metric | Before (Strong Nesting) | After (payload extension) |
|---|---|---|
| JWT average | 5933.96 bytes | **7324.81 bytes** |
| AS bytes | 78231 | 90433 |
| RS bytes | 102075 | 126035 |
| PKI/CRL | 38432 (unchanged, untouched by this decision) | 38432 |
| mTLS handshake P50 | 25880.0 (unchanged, untouched) | 25880.0 |
| `client_cert_bytes` isolation | 6859/6842/0 | 6859/6842/0, unchanged |

**The JWT-size growth is expected and precisely explained, not a
regression:** the ML-DSA-65 signature now gets base64url-encoded TWICE --
once as the `pqc.signature` claim's own string value, then again as part
of the whole payload's own base64url encoding for the JWS -- versus Strong
Nesting's single base64url pass over the raw combined signature bytes.
3309 raw ML-DSA-65 signature bytes -> 4412 base64url characters after one
encoding pass -> ~5883 characters' worth of additional encoding overhead
once that string is itself re-encoded as part of the payload. This is the
literal, inherent cost of "retrocompatibility over efficiency" the advisor's
scheme deliberately accepts, not an implementation inefficiency to fix.
**OPINsize recomputed**: `6x25880.0 + 26x7324.81 + 2x2208 = 350141.06`
bytes -- delta from the previous 313978.96 is +36162.10, which reconciles
exactly with the per-JWT delta (7324.81-5933.96=1390.85) times 26 JWTs
(36162.10) -- the entire OPINsize change traces to this one, fully
explained mechanism, nothing else moved.

**A claim in this decision's own first "validated end-to-end" pass turned
out to be wrong -- caught by the user asking a pointed follow-up question,
not by anything in the original testing.** The original legacy-verifier
check imported each classical public key by hand
(`importJWK({kty:'RSA', n, e, alg:'RS256'}, 'RS256')`), with `alg`
hardcoded by the test itself -- it proved only that *if* a verifier already
knows out-of-band that the token is RS256, `jose` accepts it; it never
exercised real `kid`-based JWKS discovery, the thing an actual
"legacy-compatible" claim depends on. Corrected the test to use
`jose.createLocalJWKSet` against each JWKS exactly as published/registered,
with no manual override, and got the opposite result:

- `client_one_pub.jwks`'s registered signing key still had `"alg": "PS256"`
  while the token header said `"RS256"` -- **REJECTED**,
  `ERR_JWKS_NO_MATCHING_KEY`.
- The RS's real, live `/jwks` only ever published the composed
  `kty: "HYBRID"` entry -- no plain RSA key for a standard library's RS256
  path to find at all -- **REJECTED**, `ERR_JWKS_NO_MATCHING_KEY`.

So the scheme's central promise -- "an ordinary verifier accepts this
without adaptation" -- held only for this project's *own* verification
(`clientHybridAuth.js`/`payloadExtensionVerification.js`, which read key
material directly from known files, never through `kid`+`alg` JWKS
discovery), not for a real external relying party doing standard discovery.
That gap is now closed, not deferred:

- **RS `/jwks`**: `ResponseSigningService`'s `JwsSigner` interface gained a
  `publicJwks()` method (defaulting to a singleton list wrapping the
  existing `publicJwk()`, so classic/pqc are untouched) that the hybrid
  signer overrides to publish TWO entries -- the original composed
  `kty: "HYBRID"` key unchanged, plus a new plain `kty: "RSA"`,
  `alg: "RS256"` entry under the *same* `kid` (the one every
  payload-extension token's header actually carries), built from the exact
  `n`/`e` `signToBase64Url` already signs with. `JwksController` now
  returns `getPublicJwks()`.
- **Client**: a new, committed file, `client_one_hybrid_pub.jwks` --
  byte-identical to `client_one_pub.jwks` except `"alg": "PS256"` ->
  `"alg": "RS256"` on the signing key -- mirrors the existing
  `client_one_pqc_pub.jwks` pattern exactly (same `kid`/`n`/`e`, only the
  published `alg` differs). `client_one_pub.jwks` itself is untouched
  (still correct for classic mode, which still signs PS256).
  `mongo-seed/start.sh`'s existing profile-conditional `CLIENT_ONE_JWKS`
  selection gained an `elif hybrid` branch pointing at this file, replacing
  the earlier, cruder fix (a `jq`-based `del(.alg)` at seed time, stripping
  the field rather than correcting it) with a properly-labeled key.
  `clientHybridAuth.js` now reads this same file too (functionally
  identical either way, since it never inspected `alg`, but keeping every
  reader pointed at the one file that's actually correct to publish).

**Re-tested with the fix in place, same corrected methodology, both now
pass:**

- `client_one_hybrid_pub.jwks` (the file actually registered for hybrid
  mode now): registered `alg: "RS256"` matches the token header ->
  `jose.createLocalJWKSet` **ACCEPTED**.
- The RS's live `/jwks`, fetched fresh: now `[{kty:"HYBRID",...},
  {kty:"RSA", alg:"RS256", kid: <same>}]` -> `jose.createLocalJWKSet`
  **ACCEPTED**.

Confirmed this follow-up changes no measured byte content: a fresh 0ms
run's `jwt_sizes_bytes` (avg 7324.81) matches the already-committed
post-payload-extension baseline exactly, byte-for-byte -- neither the RS's
extra JWKS entry nor the client's re-labeled one touches anything actually
signed or transmitted in the measured flow, only what gets published/
registered as metadata. The already-collected 6-scenario data from this
decision's earlier pass therefore did not need re-collection. Full sabatina
re-run regardless (client_cert_bytes isolation, JARM live re-verification,
26/26 cryptographic re-verification, classic/pqc `/jwks` shape spot-check
-- classic still publishes its original single `{kty:"RSA", alg:"PS256"}`
entry, unaffected by the `publicJwks()` refactor) -- all clean.

**Still deliberately deferred, genuinely not needed for the point above:**
the AS's own `/jwks` still publishes only the single composed
`kty: "HYBRID"` key, unchanged -- no fix applied there, because no
AS-issued artifact currently uses the payload-extension scheme (id_token/
JARM are the only AS-issued hybrid artifacts, and Decision 13 leaves both
on Strong Nesting entirely). If a future decision ever adds a
payload-extension AS-issued artifact, it would need the same
`publicJwks()`-style fix `configuration.js`'s own `/jwks` override
currently lacks. The broader question of whether the composed single-entry
publication still makes sense at all, now that the two signatures verify
independently of each other, remains open -- this decision only closed the
concrete, demonstrated discovery failure, not the general design question.
