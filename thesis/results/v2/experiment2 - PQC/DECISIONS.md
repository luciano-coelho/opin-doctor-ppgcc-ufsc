# Experiment 2 (PQC migration) — Architecture Decisions

Log of non-obvious technical decisions made during the classical -> PQC migration
of the MockOPIN environment, with the reasoning behind each. Experiment 2 replaces
classical algorithms entirely (no parallelism/hybrid — that's Experiment 3).

## 1. AS software_statement validation: bypass jose for the sync validator hook

**Context:** `mock_as/utils/opin/configuration.js` verifies the SSA JWT inside
oidc-provider's `extraClientMetadata.validator` hook. This hook **must be
synchronous** — confirmed in oidc-provider's current docs: "async validators or
functions returning Promise shall be rejected during runtime." This is a hard
constraint of the hook itself, unrelated to the oidc-provider version.

**Problem:** jose v6's entire verification API is Promise-based (`jwtVerify` and
everything built on it) — there is no synchronous verify path, and hasn't been
since jose v3. So `jose`'s v6 API cannot be used inside this specific hook,
regardless of which JWA algorithm is involved.

**Decision:** for this one call site only, verify the SSA's ML-DSA-65 signature
manually and synchronously with `node:crypto.verify()` (a synchronous method,
and per Node PR nodejs/node#59259 it supports `'ml-dsa-65'` `KeyObject`s natively
from Node >=24.7 / OpenSSL >=3.5) — selecting the signing key by `kid` from the
SSA's JWS header, building the `KeyObject` via
`crypto.createPublicKey({ key: jwk, format: 'jwk' })`, and validating `iss` /
`maxTokenAge` / `typ` claims by hand (the checks `jwtVerify` would otherwise do).
`ssaJwks` has no other consumer in `mock_as`, confirmed via grep, so this doesn't
leave a half-migrated jose v2 dependency anywhere else.

**Confirmed by:** user, 2026-08-07 ("Sim, segue com o workaround").

## 2. Go gateway (mock_mtls): use Go 1.27 pre-release for ML-DSA-65 mTLS support

**Context:** native ML-DSA support in `crypto/x509`/`crypto/tls` only lands in
Go 1.27 (`crypto/mldsa` package + `MLDSA44`/`MLDSA65`/`MLDSA87` `SignatureScheme`
values). As of 2026-08-07, Go 1.27 is **not yet released** (go.dev/doc/go1.27
still marked "not yet released... expected in August 2026"; RC1 shipped June
2026). `liboqs-go` was ruled out separately — no supported path for X.509
certificate generation/verification, only raw signing primitives (the OQS
ecosystem solves X.509 via `oqs-provider` + OpenSSL, not Go bindings).

**Decision:** accept the Go 1.27 pre-release (RC or later) for the gateway,
rather than treating this as an unmigrated/documented limitation. Rationale
(user, 2026-08-07): this is a thesis environment, not production — what matters
is that the exact toolchain version used is documented, not that it's GA.

**Action:** the exact Go version (module `go` directive + `go version` output at
build time) used for `mock-service-os/mock_mtls` will be recorded here once
Etapa 3 is implemented.

**Still open:** whether the OpenID Conformance Suite (the mTLS *client* in every
test flow) can present an ML-DSA-65 client certificate at all — its outbound
HTTP/TLS client lives inside a pre-built external `.jar`
(`fapi.conformance.version`, from Raidiam's Maven repo, already documented as
"not editable" in `thesis/patches/README.md`) running on Java 17, whose default
JSSE provider has no ML-DSA support. Not yet investigated whether forcing
BouncyCastle's `BCJSSE` provider as the JVM-wide default TLS provider (via
`Security.insertProviderAt`, no jar edits needed) is sufficient — deferred until
Etapa 3.

## 3. Classic <-> PQC switching: CRYPTO_PROFILE env var + versioned config files

**Context:** the user needs to be able to re-run Experiment 1 (classical) at any
time, including after Experiments 2 and 3 are implemented, without manually
reverting code. Three options were on the table: an env var read at runtime, a
set of Docker Compose profiles, or separate git branches per experiment.

**Decision (user, 2026-08-07):** env var, but implemented as a *single*
config-loading indirection rather than algorithm branches scattered through the
code. `CRYPTO_PROFILE=classic|pqc` (default `classic`) is read once at boot in
`mock_as/utils/opin/configuration.js` and picks which
`mock_as/crypto-profiles/<name>.json` to load — each file holds that profile's
`signingAlgs` (array, so Experiment 3's hybrid can later hold more than one
value) and the AS's own signing `signingKey` JWK. `enabledJWA`, `clientDefaults`,
and the DCR per-client overrides all read from the loaded profile instead of a
hardcoded literal. Docker Compose passes it through as
`CRYPTO_PROFILE=${CRYPTO_PROFILE:-classic}` on the `auth` service. Git branches
were rejected for the reason the user identified: any fix to shared infra
(Dockerfile, docker-compose, scripts) would need cherry-picking across 3
diverging branches.

**Scope boundary:** the Go gateway (`mock_mtls`) does **not** get a
`CRYPTO_PROFILE` — TLS negotiates signature algorithms per-handshake, so once
it's rebuilt on Go 1.27 (see Decision 2) it validates both a classical and an
ML-DSA-65 `client_one` certificate in the same binary with no flag needed, as
long as both certs exist and both issuing CAs are trusted. Confirmed by the user
explicitly.

**Verified:** rebuilt the `auth` image once, then flipped between
`CRYPTO_PROFILE=classic` and `=pqc` via container restart only (no rebuild, no
code change). `classic` reproduces Experiment 1's AS signing key exactly — the
published `/jwks` `kid` (`xQLs45xYyJr1omHs4qnB2rhes9qNFHIHQ5YPQKVJliM`) matches
the one recorded from the actual Experiment 1 data collection, since the JWK
thumbprint is deterministic over the same key material. `pqc` reproduces
Experiment 2's Etapa 1 result (`id_token_signing_alg_values_supported:
['ML-DSA-65']`).

**Note:** `mock_as`'s SSA verification (`verifySsaJwt`) is intentionally *not*
profile-driven — it always expects PS256, regardless of `CRYPTO_PROFILE` — since
it verifies a document signed by a different actor (the Trust
Framework/Directory), not the AS's own key. See Decision 1.

## 4. RS response signing (Etapa 2): built from scratch, both modes sign for real

**Context:** initial Etapa 2 investigation found the RS (`insurance-server-lambdas`)
never actually signed Consents/Person API responses or did any JWE encryption --
`nimbus-jose-jwt` was only used for an unrelated `Pair` utility class, and
incoming access tokens were parsed via Nimbus's `PlainObject` (`alg: none`,
no signature check at all). This contradicted the Etapa 2 brief's premise
("RS assina respostas com PS256"). The user confirmed (2026-08-07, citing the
Open Finance Brasil FAPI Security Profile, which requires JWS response
signing on sensitive APIs) that MockOPIN's RS was simply missing a real
requirement, and to build it -- not just "migrate" something that never
existed.

**Decision:** both `CRYPTO_PROFILE` values sign for real (`classic` -> PS256
via Nimbus, `pqc` -> ML-DSA-65 hand-rolled over BouncyCastle 1.79's JCA
provider, since Nimbus has no ML-DSA support in any release through 11.0
[2026-06-18] -- same gap as Decision 1). Rationale (user, 2026-08-07): with
`classic` a no-op, an Experiment 1 -> 2 byte/latency comparison would
conflate "gained a signature" with "the signature is PQC" -- signing both
ways isolates the algorithm as the only variable.

**User's explicit methodological note (2026-08-07):** Experiment 1 will be
*rerun* after this change, so the classical baseline captures RS response
signing (PS256) from the start. There are not two baselines to reconcile --
the pre-Etapa-2 unsigned RS responses were never a "baseline," just the
pre-existing gap this decision closes.

**Implementation:** `ResponseSigningService` (new `crypto` package) loads
`classic.json` (a real RSA-2048/PS256 JWK, parsed via Nimbus's own
`RSAKey.parse`) or `pqc.json` (`kty: AKP`, PKCS8/X.509 DER blobs -- BC's own
native encodings, not the raw AKP `pub`/`priv` fields `mock_as`'s Node side
uses, since the RS's key never needs to leave the JVM) at boot, same
env-var/`@Value` pattern as `mock_as`. `ResponseSigningFilter` (new
`HttpServerFilter`, mirrors the existing `IdempotencyFilter`'s
response-interception idiom) wraps any `@SignedResponse`-annotated
controller method's 2xx JSON body as a compact JWS. `JwksController`
publishes the active key at `GET /jwks` (the RS never had one before either).
Applied to all non-204 Consents + Person endpoints.

**Empirically verified end-to-end** through the real `mockapi` Netty HTTP
server (the actual runtime path `docker-compose`/the thesis experiments use --
see the Lambda-adapter caveat below): `GET /open-insurance/consents/v3/consents/{id}`
against a real seeded consent returned `200`, `Content-Type: application/jwt`,
with a well-formed JWS in both profiles. For `pqc`, independently verified
the signature with Node's native `crypto.verify()` against the published
`/jwks` key -- valid, and the raw signature was exactly 3309 bytes (FIPS 204),
cross-confirming BouncyCastle's and Node/OpenSSL's ML-DSA-65 implementations
agree, the same figure Decision 1's AS work already established. Also
confirmed `crypto/x509`-style DER round-tripping (BC `KeyPairGenerator` ->
PKCS8/X.509 `getEncoded()` -> `KeyFactory.generatePrivate/generatePublic` ->
sign/verify) works before wiring it into the service, via a standalone
`docker run eclipse-temurin:17-jdk` + bcprov/bcutil-jdk18on:1.79 harness.

**Known limitation, not fixed:** the 16 pre-existing `PersonControllerSpec`/
`ConsentControllerSpec` Gradle tests now fail. Root cause isolated: every
test in both specs drives requests through
`io.micronaut.function.aws.proxy.payload1.ApiGatewayProxyRequestEventFunction`
(the AWS Lambda deployment emulation path), whose response-body encoding
step unconditionally tries to JSON-encode the body regardless of the
filter-set `Content-Type` or runtime body type (`String` and `byte[]` both
fail identically with `Error encoding object [...] to JSON`) -- it resolves
its writer some other way than the real embedded-Netty-server path does, and
that path was never exercised by this discovery. This only affects the AWS
Lambda deployment target, which MockOPIN's docker-compose thesis environment
doesn't use (`mainClassName` is a plain `Micronaut.run` `Application`, not a
Lambda handler) -- not fixed because it's out of scope for the environment
this thesis actually runs against, and because signing responses at all was
already a from-scratch addition the Lambda path was never designed around.

## 5. mTLS certificates (Etapa 3): Go 1.27rc2 confirmed sufficient, no gateway code changes needed

**Context:** Decision 2 accepted Go 1.27 pre-release for the gateway on the
premise that native ML-DSA support would land in `crypto/x509`/`crypto/tls`.
That premise is now verified against the real RC, not just the draft release
notes.

**Toolchain used:** `go1.27rc2`, via the official `golang:1.27-rc-alpine` /
`golang:1.27-rc` Docker Hub images (pushed 2026-08-05). `go.mod` for both
`mock-service-os/certs` (the cert-generation tool) and `mock-service-os/mock_mtls`
(the gateway) now declare `go 1.27rc2`.

**3.1 -- client_one_pqc.crt/.key:** added a `-pqc-client-only` flag to
`mock-service-os/certs/main.go` that *loads* the existing `ca.crt`/`ca.key`
from disk (via a new `loadCACert`) instead of the tool's normal behavior of
generating a fresh CA + all certs from scratch -- regenerating the CA would
have invalidated every other cert in the environment (mongo, postgres, op,
mtls, client_one/two), all signed by the same CA. Verified before and after
via MD5 that `ca.crt`/`ca.key`/`client_one.crt`/`client_one.key` are
byte-identical to what they were before this ran. The new
`generateClientCertPQC` generates an ML-DSA-65 keypair
(`mldsa.GenerateKey(mldsa.MLDSA65())`) and signs it with the *existing* RSA
CA key -- a classical issuer signature over a post-quantum subject public key
is ordinary, valid X.509 (the two fields are independent), and matches the
Etapa 3.1 brief: only the client's own key moves to PQC, not the CA.
Independently re-verified with a standalone Go 1.27 program: the generated
cert chains to `ca.crt` (`Verify` succeeds), and the key parses back as
`*mldsa.PrivateKey` via `x509.ParsePKCS8PrivateKey`.

**3.2 -- gateway:** turned out to need *zero* functional code changes beyond
the Go version bump. `tlsConfiguration()` never restricted TLS 1.3 signature
schemes explicitly, so Go 1.27's newly-added `tls.MLDSA65` scheme and
`crypto/mldsa`-aware `crypto/x509` chain verification are just part of the
stdlib defaults `ClientAuth: tls.VerifyClientCertIfGiven` already used. Since
`client_one_pqc.crt` is signed by the same CA already in `ClientCAs`
(`caCertPool()`), no config change was needed there either.

**3.4 -- validated with a real handshake**, not just unit-level primitives:
a standalone Go 1.27 client (loading `client_one_pqc.crt`/`.key`, run on the
`insurance-server-lambdas_default` docker network so it resolves `api.local`
the same way a real client would) completed a full TLS 1.3 handshake against
the rebuilt gateway and received an HTTP response (401, correct -- no access
token was sent; unrelated to the certificate). The gateway's own
`countingConn`/handshake-logging instrumentation (built for Experiment 1)
picked it up with zero changes needed: `"tlsVersion":"TLS 1.3"`,
`"clientCertBytes":2953`, `"mtlsHandshakeBytes":10880` -- meaning Experiment
2's mTLS handshake-size data collection is already wired up for free once a
real PQC-capable client drives traffic through it.

*Aside, unrelated to PQC:* the gateway's own server certificate
(`mtls.crt`) has no `ExtKeyUsageServerAuth`, only `ExtKeyUsageClientAuth`
(true of every cert `certs/main.go` issues, including its own). A strict Go
`http.Client` verifying the server cert rejects this
(`x509: certificate specifies an incompatible key usage`); had to set
`InsecureSkipVerify` on the *test client's* server-side verification to
isolate and test the client-certificate path in question. Pre-existing, not
something Experiment 2 touched, and apparently never hit by the Conformance
Suite's own client (or that path also isn't strict about it) -- noted here
so it isn't mistaken for a PQC-related regression if someone else hits it.

**3.3 -- Conformance Suite config templates:** `thesis/config/config_template_consents_v3.json`
and `config_template_person_v2.json`'s `mtls.cert`/`mtls.key` now hold
`client_one_pqc.crt`/`.key` (read and written by a small Node script directly
from the source files -- after a near-miss manually retyping the base64 by
hand and garbling it, verified byte-for-byte identical to the source files
before treating this as done). `mtls.ca` and `client.jwks` (the client's own
request/assertion-signing key, unrelated to the transport cert) are
untouched.

**Still open, not resolved here -- same item flagged in Decision 2:**
whether the Conformance Suite can actually *drive* this end-to-end. Confirmed
`cs-server` runs on plain `eclipse-temurin:17-jdk` (stock OpenJDK 17, no
PQC-capable TLS provider) -- consistent with every other maturity signal
found in this migration (Nimbus: roadmap-only; Go: RC2, days-old Docker
tags). Did not attempt forcing BouncyCastle's `BCJSSE` as the JVM-wide
default provider or a full CS rebuild (~15-20 min/cycle per
`thesis/patches/README.md`, against a pre-built external jar with no
available source) -- this is a distinct, potentially substantial piece of
work from the gateway/cert work above (which is complete and independently
verified without needing the CS at all), not a quick add-on. Deferred as an
explicit follow-up decision rather than absorbed into this session's Etapa 3
scope.

## 6. Conformance Suite cannot drive Experiment 2 (pqc) end-to-end -- definitive, not worked around

**Context:** resolving Decision 5's "still open" item. With `CRYPTO_PROFILE=pqc`
on `auth`+`mockapi` and `client_one_pqc.crt`/`.key` wired into
`config_template_consents_v3.json` (Decision 5, Etapa 3.3), ran
`opin-consent-api-status-test-v3` against the real `cs-server` (via its
`/api/plan` + `/api/runner` HTTP API, same pattern as
`thesis/scripts/baseline_automation.py`). Test reached `INTERRUPTED`/`FAILED`
in 5 seconds -- before ever reaching the `WAITING` (manual browser login)
state, i.e. before attempting any call that would need the client's mTLS
certificate at all.

**Root cause, exact:** not a TLS/mTLS problem. The gateway logs show the
handshake to `auth.local` for `/.well-known/openid-configuration` and
`/jwks` completed fine (TLS 1.3, no client cert needed -- those are public
discovery endpoints). The failure is in the CS's own
`net.openid.conformance.condition.client.ValidateServerJWKs` condition,
which runs unconditionally early (right after fetching discovery + JWKS,
for every test module, regardless of what happens later in the flow) and
uses **Nimbus JOSE+JWT** -- the same library confirmed PQC-blind in Decision
1 and Decision 4 -- to parse each key the AS's `/jwks` returns:

```
java.text.ParseException: Unsupported key type "kty" parameter: AKP
  at com.nimbusds.jose.jwk.JWK.parse
  at net.openid.conformance.condition.client.AbstractValidateJWKs.parseJWKWithNimbus
  at net.openid.conformance.condition.client.AbstractValidateJWKs.checkJWKs (forEach over jwksObject's "keys" array)
  at net.openid.conformance.condition.client.ValidateServerJWKs.evaluate
```

**Considered and ruled out: publishing both PS256 and ML-DSA-65 keys in the
AS's JWKS**, so the CS would validate the RSA key and the AS would still
sign with ML-DSA-65. Not viable, confirmed two ways:
- *Source (public, `openid-certification/conformance-suite` on GitHub,
  mirroring `gitlab.com/openid/conformance-suite`):* `checkJWKs` iterates
  `jwksObject.getAsJsonArray("keys").forEach(...)` and calls
  `parseJWKWithNimbus` with no per-key try/catch -- the first unparseable
  key in the array throws and aborts the whole check, regardless of
  position or of any other valid key present.
- *Empirically, today:* the AS's `pqc`-profile JWKS **already** has two keys
  -- the ML-DSA-65 signing key (`kty: AKP`) and the (never-migrated,
  Decision 4) RSA-OAEP encryption key (`kty: RSA`, perfectly Nimbus-parseable)
  -- and `ValidateServerJWKs` still fails outright. A mixed JWKS is not a
  hypothetical -- it's the current state, and it already doesn't help.

**Decision (user, 2026-08-08):** accept this as a **definitive** limitation,
not to be worked around via config or partial JWKS. The Conformance Suite
cannot be used to drive or collect metrics for Experiment 2 in pure-PQC mode
-- its own core validation logic depends on a library (Nimbus) with no
ML-DSA support, in code we don't control (the vendored
`fapi.conformance.version` jar, no available source, per
`thesis/patches/README.md`). Patching/rebuilding the CS's own Nimbus
dependency was considered and explicitly rejected as disproportionate to
this thesis's scope.

**Consequence:** Experiment 2's measurement strategy changes. Instead of the
Conformance Suite, a direct Python script will call the AS's and RS's APIs
with ML-DSA-65 directly, measuring the JWTs/JWS returned, payload sizes, and
latencies -- without depending on the CS's JWKS validation at all. (Etapas
3.1-3.4's gateway/certificate work stays valid and independently verified --
see Decision 5 -- this only rules out the CS as the *driver* for Experiment
2 traffic.)

## 7. Two workarounds attempted and pushed as far as they'd go -- three-layer investigation, definitive result

**Context:** before accepting Decision 6, tried two further, deeper
workarounds to see whether the Conformance Suite could be made to drive
Experiment 2 (pqc) end-to-end after all, each tested empirically against the
real `opin-consent-api-status-test-v3` module (via the same
`/api/plan`+`/api/runner` pattern `baseline_automation.py` uses) rather than
reasoned about abstractly. Both are **kept in the codebase, not reverted** --
they're real, working infrastructure that got the CS measurably further, and
document exactly where the wall is.

### Layer 1 -- Nimbus can't parse `kty: AKP` (Decision 6's finding)

`net.openid.conformance.condition.client.ValidateServerJWKs` uses Nimbus
JOSE+JWT to parse every key in the AS's `/jwks`, unconditionally, for every
test module, before anything mTLS-related happens.

**Workaround implemented:** `mock_as/utils/opin/configuration.js` (pqc mode
only) now builds `publishedJwksOverride` -- the *classic* RSA signing key's
public projection (borrowed from `crypto-profiles/classic.json`, no private
fields) plus the real RSA-OAEP encryption key -- and `express.js` registers
`app.get('/jwks', ...)` serving it, positioned *before*
`app.use(provider.callback())` so Express's route matching shadows
oidc-provider's own `/jwks` handler. The AS's real signing keystore
(`cryptoProfile.signingKey`, the ML-DSA-65 key, used via `enabledJWA`) is
completely untouched -- tokens are still actually signed with ML-DSA-65; only
the published discovery document is a decoy. Verified: `/jwks` publishes
`kid: xQLs45xYyJr1omHs4qnB2rhes9qNFHIHQ5YPQKVJliM` (the exact same kid as
Experiment 1's real classical AS key -- same key, same JWK thumbprint), while
`/.well-known/openid-configuration` still correctly advertises
`id_token_signing_alg_values_supported: ["ML-DSA-65"]`.

**Result:** `ValidateServerJWKs` now passes, and the test advances through
~20 further conditions (server JWKS validity/kid/key-length checks, client
JWKS validity, mTLS certificate header parsing) before hitting Layer 2.

### Layer 2 -- `java.security.cert` can't decode the ML-DSA-65 SubjectPublicKeyInfo

With Layer 1 fixed, the test reached
`net.openid.conformance.condition.client.ValidateMTLSCertificatesAsX509.validateMTLSKey`,
which threw `NullPointerException: Cannot invoke
"java.security.PublicKey.getAlgorithm()" because "publicKey" is null`. Root
cause: Java 17's default `java.security.cert.CertificateFactory` doesn't
recognize ML-DSA's SubjectPublicKeyInfo AlgorithmIdentifier OID
(`2.16.840.1.101.3.4.3.18`) and silently returns a null `PublicKey` instead
of throwing -- and the CS's own condition code has no null check before
calling `.getAlgorithm()` on it. A latent bug in the CS's own code, exposed
by an algorithm its JVM doesn't recognize -- not something fixable from our
side by configuration.

**Workaround implemented (experimental, kept as-is):**
`insurance-server-lambdas/conformance-suite/extra-libs/` now holds
`bcprov-jdk18on-1.79.jar`, `bcutil-jdk18on-1.79.jar`, and `bc.security` (one
line: `security.provider.20=org.bouncycastle.jce.provider.BouncyCastleProvider`).
`docker-compose.yml`'s `cs-server` service mounts that directory and its
`command` was changed from `-jar /server/fapi-test-suite.jar` to `-cp
/server/fapi-test-suite.jar:/extra-libs/bcprov-jdk18on-1.79.jar:/extra-libs/bcutil-jdk18on-1.79.jar
org.springframework.boot.loader.JarLauncher` (the jar's own `Main-Class`,
extracted from its manifest -- `-jar` ignores any `-cp` addition, using only
the jar's internal manifest Class-Path, so reaching a addable classpath
required launching the Spring Boot loader class directly instead) plus
`-Djava.security.properties=/extra-libs/bc.security` (no leading `=`:
additive to the JVM's default provider list, not a replacement -- placed
*before* `-cp`/the class name, since like `-jar`, anything after the class
name is a program arg to Spring Boot, not a JVM option, and would silently
do nothing there). No jar was modified or rebuilt.

**Result:** the NPE is gone -- BouncyCastle's registered ML-DSA algorithm
support lets `CertificateFactory` correctly decode the public key this time.
The test advances to Layer 3.

### Layer 3 -- hardcoded RSA assumption in the CS's own compiled code, not fixable by provider registration

```
ValidateMTLSCertificatesAsX509: "The private key format does not support. You need to provide a private key which is RSA or EC"
OpinInsertMtlsCa: Error creating HTTP client
  at sun.security.rsa.RSAPrivateCrtKeyImpl.parseKeyBits
  at sun.security.rsa.RSAKeyFactory.generatePrivate
  at net.openid.conformance.condition.util.AbstractMtlsStrategy.generatePrivateKeyFromDER
  at net.openid.conformance.condition.util.DefaultMtlsStrategy.process
  at net.openid.conformance.condition.util.MtlsKeystoreBuilder.configureMtls
```

`AbstractMtlsStrategy.generatePrivateKeyFromDER` calls
`sun.security.rsa.RSAKeyFactory`/`RSAPrivateCrtKeyImpl` **by name**, directly
-- it never goes through the algorithm-agnostic `KeyFactory.getInstance(alg,
provider)` lookup that would let a registered provider (BouncyCastle or
otherwise, BCJSSE included) intervene. The code has already decided the key
is RSA before any provider gets a chance to be asked. This is a hardcoded
assumption baked into the CS's compiled logic, not a configuration or
provider-availability gap -- no JVM flag or registered `Provider` can change
which class a hardcoded call site invokes.

**Conclusion (user, 2026-08-08):** the Conformance Suite cannot act as an
mTLS client with an ML-DSA-65 certificate, full stop -- a structural
limitation in its compiled source, not our configuration, our JVM setup, or
missing algorithm support in the crypto libraries available to it (BC 1.79
has ML-DSA; the CS's own code just never asks it). Fixing this would require
patching and recompiling the CS from source, which was already ruled out in
Decision 6 as disproportionate to this thesis's scope. Layers 1 and 2's
workarounds are kept in the repository (not reverted) as working,
documented infrastructure -- they're each individually correct and useful
evidence of exactly where the real wall is, even though the combination
doesn't clear Layer 3.

**Experiment 2 measurement strategy (final):** a Python script that
simulates the flow directly against the AS and RS (bypassing the
Conformance Suite as the traffic driver entirely), reproducing the same
call sequence the CS's test modules make, to preserve methodological
equivalence with Experiment 1's data collection.

## 8. opin_flow.py scope: excludes both plans' preflight modules

**Context:** `thesis/scripts/opin_flow.py` (Decision 7's replacement
measurement strategy) replicates the real HTTP call sequences from
Experiment 1's raw logs. Each of the two plans Experiment 1 ran
(`baseline_automation.py`'s `PLANS`) has two modules: a preflight module and
the module that actually drives a consent (`opin-consent-api-status-test-v3`
for the Insurance consents plan, `person_api_core_test-module_v2.0.0` for
the person plan). `opin_flow.py` replicates only the latter two.

**What was excluded:** the `opin-consents_api_preflight_test-module_v3`
modules from both plans.

**Reason:** they depend on Raidiam's real Directory, unavailable in a local
environment. They ended with a `FAILED` result in every scenario of
Experiment 1 for that reason (confirmed via `baseline_automation.py`'s own
module_results and its docstring, which already documented this as
expected/known, not a bug).

**Why they don't contribute to the results:** since they always failed
before completing, the data they generate doesn't represent a real
consent flow and isn't comparable across algorithms. Including them would
contaminate the metrics with error traffic.

**Consequence for `opin_flow.py`'s per-scenario totals:** 28 HTTP calls
(12 from the insurance-consents flow + 16 from the person flow), instead
of the 37 raw log entries a full Experiment-1-style run produces across
both plans' preflight+main modules combined.

## 9. mockapi (RS) must be recreated on every CRYPTO_PROFILE switch, not just auth/mtls/mongo_seed

**Context:** `ResponseSigningService`
(`insurance-server-lambdas/src/main/java/com/raidiam/trustframework/mockinsurance/crypto/ResponseSigningService.java`)
signs every Consents/Person API response body as a compact JWS (PS256 or
ML-DSA-65, chosen by `mockinsurance.crypto-profile`, itself mapped from the
`CRYPTO_PROFILE` env var in `application.yml`). This mirrors the same
externalized-profile switch already used on the AS (Decision 3).

**The bug:** unlike the AS's `configuration.js`, which re-reads
`CRYPTO_PROFILE` per request via `cryptoProfile.signingAlgs`,
`ResponseSigningService.init()` is a Micronaut `@PostConstruct` -- it picks
the signer **once, at JVM boot**, and never again. Throughout this
session's data collection, switching `CRYPTO_PROFILE` between scenarios was
done with `docker-compose --profile main up -d --force-recreate auth mtls
mongo_seed` -- a list assembled before `mockapi`'s own dependency on
`CRYPTO_PROFILE` was noticed, since the docker-compose service definition
looks identical in shape to `psql`/`mongodb`'s static config. `mockapi` was
never included, so it kept running -- and kept signing -- with whatever
profile was active the last time it happened to be created (a bare
`docker-compose up -d` with no explicit service list, which recreates
every service whose resolved config changed).

**Symptom that surfaced it:** a `thesis/scripts/opin_flow.py` Experiment 2
(pqc) run's total bytes exchanged and JWT sizes for the RS-facing calls
(`/insurance-person`, `/claim`, `/policy-info`, `/premium`) varied by
scenario in a way uncorrelated with latency -- e.g. one 14ms run measured
~178KB/scenario with ~5-7KB JWTs, while 0/30/140/225/320ms measured
~113KB/scenario with ~1-3KB JWTs, collected under the same nominal
`CRYPTO_PROFILE=pqc`. Root-caused by dumping raw response bodies
(`Content-Type: application/jwt`) for both patterns: both are a single,
well-formed 3-part compact JWS, no wrapper/array/nesting -- the only
difference is the `alg`/`kid` in the header and, consequently, the
signature length (ML-DSA-65's 3309-byte raw signature -> 4412 base64url
chars, vs. PS256's 256-byte RSA signature -> 342 chars; the ~4076-byte
gap observed between the two patterns matches this difference almost
exactly, plus a few bytes for the `alg` string itself). Confirmed
definitively via `mockapi`'s own boot log line (`Response signing
profile: <profile> (alg: ..., kid: ...)`), which is emitted once per
container lifetime and doesn't change afterward regardless of what
`auth`/`mtls`/the client are doing.

**Consequence:** any already-collected scenario file where `mockapi` had
silently drifted from the experiment's intended `CRYPTO_PROFILE` has
RS-attributed bytes/JWT sizes reflecting the wrong algorithm -- not a
one-off, not tied to any particular latency value, and not auditable after
the fact (container recreation discards the old instance's logs, so which
scenarios were actually affected can't be reconstructed retroactively).
This is why all 12 scenarios (both experiments) were re-collected after
this decision, rather than only the scenario(s) where the symptom had been
directly observed.

**Fix:** `mockapi` is now included in the `--force-recreate` list on every
profile switch, alongside `auth mtls mongo_seed`:

```
CRYPTO_PROFILE=<classic|pqc> docker-compose --profile main up -d --force-recreate auth mtls mongo_seed mockapi
```

Both `docker-compose.yml` environment blocks (`mockapi`'s and `auth`'s)
now carry a comment to this effect. The procedure additionally confirms
`mockapi`'s own "Response signing profile: ..." boot log line before
starting a scenario, rather than trusting the env var alone.

## 10. AS transport certificate and gateway server certificate migrated to ML-DSA-65 (pure substitution, not the CA)

**Context:** two remaining classical-only components in Experiment 2 (pqc)
were identified: the AS's own transport certificate (used by
`InsurerAdapter` for its outbound AS->RS backend calls -- rendering the
consent screen, updating consent status) and the gateway's own TLS server
certificate (what `mock_mtls` presents to every connecting client). Both
were static, non-`CRYPTO_PROFILE`-aware files (`op.crt`/`op.key`,
`mtls.crt`/`mtls.key`) before this decision, meaning Experiment 2 was
measuring a client that had migrated to PQC talking to infrastructure that
partly hadn't.

**Explicitly out of scope: `root-ca.pem`/`issuer-ca.pem`.** These are not
generated by this project's local CA (`mock-service-os/certs/ca.crt`) --
`thesis/scripts/opin_flow.py`'s `fetch_server_keys_and_ca()` fetches them
from Raidiam's real, public sandbox PKI
(`https://crl.sandbox.pki.opinbrasil.com.br`), infrastructure this thesis
does not control and cannot migrate. Standing up a local server to
impersonate that hostname was considered and rejected: it would stop the
PKI/CRL metric from representing a genuine ecosystem dependency and turn
it into a simulation of our own making. This is documented as a
methodological limitation -- the CA-root migration depends on Raidiam
updating their sandbox, which is exactly the kind of institutional
dependency this thesis's transition framework is meant to identify, not
resolve. `PKI/CRL` bytes are therefore expected to (and do) stay stable
across Experiment 1/2, unaffected by this decision.

**Feasibility validated before implementing** (two isolated tests, not
assumed from Decision 5's client-cert-verification precedent, which is a
different code path): (1) Go 1.27rc2's `crypto/tls` presenting its own
ML-DSA-65 **server** certificate and completing a full TLS 1.3 handshake
-- confirmed via a throwaway `tls.Listen`/`tls.Dial` program in the same
process; (2) a real Node.js 24 TLS **client** presenting an ML-DSA-65
**client** certificate (`client_one_pqc.crt`) against a Go 1.27 server
requiring client auth, in two separate Docker containers on the same
network -- confirmed on both sides independently (Node: handshake
succeeded; Go: `PublicKeyAlgorithm=ML-DSA`, matching `client_one_pqc`'s
subject).

**Implementation:**
- `mock-service-os/certs/main.go` gained a generalized `-pqc-name <name>`
  flag (replacing the need for a new one-off flag per cert, like the
  existing `-pqc-client-only`): generates `<name>.crt`/`.key` as an
  ML-DSA-65 subject key signed by the existing (RSA) local CA -- same
  mixed-issuer pattern as Decision 1's `client_one_pqc`, the CA itself
  untouched. Used to generate `op_pqc.crt`/`.key` (AS transport) and
  `mtls_pqc.crt`/`.key` (gateway server).
- `insurance-server-lambdas/docker-compose.yml`'s `localstack` service now
  mounts both cert pairs (`client_classic.{crt,key}` /
  `client_pqc.{crt,key}`, aliased from `op.*`/`op_pqc.*`) and passes
  `CRYPTO_PROFILE`; `mock-service-os/setup_ssm.sh` picks which pair to
  push as `/local/op_fapi_client_config/transport_certificate`/
  `transport_key`, mirroring the `mongo-seed`/`start.sh` pattern from
  Decision 3.
- `mock-service-os/mock_mtls/main.go` reads `CRYPTO_PROFILE` at startup
  (`init()`) and switches `serverCertFilePath`/`serverKeyFilePath` between
  `certs/mtls.crt`/`.key` and `certs/mtls_pqc.crt`/`.key` -- the whole
  `mock-service-os/certs/` directory is already bind-mounted into the
  container, so no new volume was needed, only a rebuild
  (`docker-compose build mtls`) to pick up the code change.

**Verified end-to-end**, not just via boot logs: for the AS transport
cert, drove a real flow and inspected the gateway's own access log --
the AS's outbound calls to `matls-api.local` (rendering/updating consent)
carried `clientCertBytes=2937`, `op_pqc.crt`'s exact DER length, distinct
from both the classical `op.crt` (1478) and `client_one_pqc.crt` (2953).
For the gateway server cert, connected directly with `pyOpenSSL` (the same
TLS stack `opin_flow.py` uses) and inspected the presented server
certificate: DER length 2941 (`mtls_pqc.crt`'s exact length), `Subject:
CN=mtls_pqc`, TLS 1.3. Both reverted correctly to their classical
counterparts when switched back to `CRYPTO_PROFILE=classic` (no
regression).

**Effect on Experiment 2 data:** all 6 scenarios were re-collected.
`mTLS_handshake_bytes` P50 moved from 15500 (one ML-DSA-65 cert in the
handshake -- the client's) to 19756 bytes (two -- client and server both
ML-DSA-65 now), perfectly constant across all 6 latency scenarios.
`total_bytes_exchanged`, `JWT_size`, and the AS/RS participant byte totals
are unchanged, as expected: the migrated certificates operate at the TLS
layer, not the HTTP application layer these figures measure.

## 11. Infrastructure certificate migration complete for Experiment 2 -- larger handshake, faster handshake, and why that's not a contradiction

**What was done:** Decision 10's two remaining classical-only components
-- the AS's internal transport certificate (`op.crt` -> `op_pqc.crt`) and
the mTLS gateway's own server certificate (`mtls.crt` -> `mtls_pqc.crt`)
-- were migrated to ML-DSA-65, both gated behind `CRYPTO_PROFILE` the
same way `client_one`'s certificate already was. This completes the PQC
migration for every certificate under this thesis's control.
`root-ca.pem`/`issuer-ca.pem` remain classical: they are Raidiam's real
public sandbox PKI (`crl.sandbox.pki.opinbrasil.com.br`), not generated
by this project's local CA, and migrating them is outside this thesis's
control -- documented in Decision 10 as a methodological limitation, not
revisited here.

**Why:** to complete the PQC migration across the whole certificate chain
this thesis controls, matching the scope of what Schardong et al. (2022)
measured against the full TLS certificate chain, not just the client leaf
certificate.

**Unexpected finding: the handshake got bigger in bytes but faster in
time.** `mTLS_handshake_bytes` P50 grew from 15500 to 19756 bytes (+27%,
Decision 10), exactly as expected from adding a second ML-DSA-65
certificate to the handshake. What was not expected: `handshake_ms` P50
*dropped*, from the classical baseline's ~18-25ms range down to ~7-9ms.

**Root cause, confirmed by direct benchmark:** signature *size* and
signing *computational cost* are independent properties of an algorithm.
RSA-4096 (the classical `mtls.crt`'s key size) is expensive to sign with
-- large-modulus modular exponentiation -- while ML-DSA-65's
lattice-based signing is comparatively cheap, despite producing a much
larger signature. Benchmarked the exact private-key operation TLS's
`CertificateVerify` step performs (RSA-PSS/SHA-256 vs `mldsa.Sign()`,
same Go 1.27rc2 environment):

| Algorithm | Time per sign operation |
|---|---|
| RSA-4096 PSS | 6.624 ms |
| ML-DSA-65 | 0.713 ms |
| **Ratio** | **RSA-4096 is 9.29x slower** |

Replacing the gateway's RSA-4096 server certificate with an ML-DSA-65 one
removes a ~6.6ms-per-handshake cost and replaces it with a ~0.7ms one --
more than accounting for the observed ~10-15ms drop in `handshake_ms`,
even though the handshake now carries ~4.3KB more data on the wire.

**Validation:** three consecutive runs of the 0ms scenario, no container
restarts between them (to rule out warm-up effects as a variable).
`handshake_ms` P50 across the three runs: 9.0ms / 8.0ms / 7.0ms -- a
2ms spread, within the ±3ms tolerance set before running the test.
`handshake_bytes` P50 was identical (19756 bytes) in all three runs,
confirming the effect is isolated to timing, not size.

**Impact on the OPINsize equation (Section 4, Decision 9's `N_mTLS`
methodology):** with `mTLS_handshake_bytes` updated to 19756 (from
15500), OPINsize PQC = 6 x 19756 + 26 x 5459 + 2 x 1952 = 118536 +
141934 + 3904 = **264374 bytes** (was 238838). The classical side is
unaffected (its own certificates were already fully classical and are
untouched by this decision) at 151120 bytes. Analytical growth:
264374 / 151120 = **1.75x** (was 1.58x).

## 12. root-ca.pem/issuer-ca.pem given local ML-DSA-65 stand-ins for Experiment 2 -- a simulation, not a migration of Raidiam's PKI

**Context:** Decision 10 left `root-ca.pem`/`issuer-ca.pem` classical,
reasoning that they're Raidiam's real external sandbox PKI
(`crl.sandbox.pki.opinbrasil.com.br`), not this project's own
infrastructure, and that faking them locally would turn a genuine
ecosystem dependency into a simulation of our own making. Before
revisiting that, re-verified by reading the current source directly (not
from this document): `mock_mtls/main.go`'s `caCertPool()` builds the
gateway's mTLS trust store from exactly one file, the local
`certs/ca.crt` -- `root-ca.pem`/`issuer-ca.pem` never appear anywhere in
the gateway's Go code. In `opin_flow.py`'s
`fetch_server_keys_and_ca()`, the HTTP response for both files is bound
to `resp` and never read again -- `do_call()` only measures byte counts,
scans for JWT-shaped substrings, and (only for paths ending `jwks`)
parses JWK sizes; none of that touches these two calls' content as an
X.509 structure. Contrast with every other call in the same flow
(`/token`, `POST /consents`, `/request`, ...), which all call
`resp.raise_for_status()` and extract real data from the response on the
very next line. Confirmed empirically too: removing the two calls would
drop `total_requests` from 28 to 26 and remove the `PKI/CRL` participant
category, nothing else in the flow (mTLS handshake, authentication,
token issuance, resource calls) depends on their content in any way.

**Decision:** given (a)-(c) above are unambiguous from the code itself,
`root-ca.pem`/`issuer-ca.pem` are now given local ML-DSA-65 stand-ins for
`CRYPTO_PROFILE=pqc`, completing the certificate chain measurement for
Experiment 2. This reverses Decision 10's scope call for these two files
specifically -- deliberately, not by oversight -- on the basis that the
earlier code-reading confirmed there's no functional risk to doing so.

**(a) This is a local simulation for cost-measurement purposes, not a
real migration of Raidiam's PKI.** `root_ca_pqc.crt`/`issuer_ca_pqc.crt`
(`mock-service-os/certs/`) are ML-DSA-65 leaf certificates signed by this
project's own local CA (same `-pqc-name` mechanism as `op_pqc`/`mtls_pqc`,
Decision 10) -- they carry no cryptographic relationship to Raidiam's
actual root/issuer CAs. They exist purely so `opin_flow.py`'s PKI/CRL
byte measurement reflects PQC-sized certificate downloads when
`CRYPTO_PROFILE=pqc`, matching the rest of Experiment 2's "what would the
whole flow cost under full PQC" framing.

**(b) In production, this migration would depend on Raidiam updating
their real sandbox infrastructure.** Nothing here changes that. This
decision does not claim the simulated files are interchangeable with a
real PQC-migrated Raidiam PKI in any deployment sense -- it only asserts
that, for this thesis's cost-measurement purposes, serving
locally-generated files with the same byte-size characteristics as a
real PQC-migrated PKI would have is sufficient, because (per the code
reading above) nothing in the measured flow inspects their cryptographic
validity.

**(c) The decision was made only after confirming, from the code, that
no other part of the flow depends on these files' real content** -- see
the `caCertPool()`/`fetch_server_keys_and_ca()` reading above. This is
what makes the simulation safe: it cannot silently invalidate any
already-collected metric, because nothing besides the PKI/CRL byte count
itself was ever coupled to these two files.

**Implementation:**
- `mock-service-os/certs/root_ca_pqc.{crt,key}` /
  `issuer_ca_pqc.{crt,key}` generated via `main.go -pqc-name
  root_ca_pqc` / `-pqc-name issuer_ca_pqc` (Decision 10's mechanism,
  unchanged).
- `mock_mtls/main.go`'s `directoryHandler()` (the same mux that already
  mocks the OPIN Directory participant locally) gained two new routes,
  `/root-ca.pem` and `/issuer-ca.pem`, serving these files' raw bytes
  with `Content-Type: application/x-pem-file`. Reachable at
  `https://directory/root-ca.pem` (the `directory` hostname is already
  in the local hosts file and already served by this same gateway
  process on port 443) -- no new container, no new port, no DNS/hosts-file
  changes.
- `opin_flow.py`'s `fetch_server_keys_and_ca()` now takes `crypto_profile`
  and picks the host per call: `directory` when `pqc`, the real
  `crl.sandbox.pki.opinbrasil.com.br` when `classic` -- Experiment 1 is
  completely unaffected, byte-for-byte, by this decision.
- Deliberately **not** done: no Windows-hosts-file editing, no Docker
  network alias for the real hostname. An early draft of this decision
  proposed intercepting `crl.sandbox.pki.opinbrasil.com.br` itself via
  the OS hosts file, gated on `CRYPTO_PROFILE`, but `opin_flow.py` runs
  on the Windows host (confirmed: `auth.local`/`api.local`/`directory`
  already resolve through `C:\Windows\System32\drivers\etc\hosts` to the
  gateway's published port, not through Docker-internal network
  aliases) -- editing the *system* hosts file would need admin
  privileges and leaves state outside the repository that persists
  across reboots and could silently affect unrelated future use of the
  real Raidiam hostname on the same machine. Redirecting the URL inside
  `opin_flow.py` achieves the identical measured outcome without any of
  that risk, and is fully reversible with a code diff.

## 13. Login interaction fully automated -- removes the real browser, makes N_mTLS deterministic in both experiments

**Context:** `opin_flow.py`'s `wait_for_authorization_code()` used to call
`webbrowser.open(auth_url)` and then block on `input()`, waiting for a
human to complete the login/consent screens in a real system browser
(Edge) before pressing ENTER. A separate investigation into why
`N_mTLS` (the gateway's `handshake_bytes.count`) was perfectly constant
at 6 across all 6 PQC latency scenarios, but varied between 9 and 16
across the 6 classic scenarios, traced the entire discrepancy to this
real browser: every `webbrowser.open()` call made Edge attempt its own,
independent mTLS connection(s) to `auth.local`, entirely outside
`opin_flow.py`'s own `requests.Session()` traffic. In PQC, every one of
these attempts failed identically at the TLS layer -- gateway logs
showed `"http: TLS handshake error ...: tls: peer doesn't support any
of the certificate's signature algorithms"` on every attempt, because
Windows' native TLS stack (Schannel, which Edge uses) has no ML-DSA-65
support -- so the real browser could never contribute a connection,
making `N_mTLS` deterministic by hard incompatibility. In classic, Edge
could negotiate the classical certificate's signature algorithm fine,
so some of its several parallel/speculative connection attempts
occasionally won a race and completed a full handshake (contributing
extra `favicon.ico`/`styles.css`/`scripts.js`/image requests visible in
the gateway's raw access log under the same client certificate), while
others failed (`"remote error: tls: unknown certificate"`/`EOF`) --
producing the observed 9-16 variability from genuine, timing-dependent
browser networking non-determinism, not from anything `opin_flow.py`
itself does.

**Decision:** remove the real browser and the manual `input()` entirely.
`wait_for_authorization_code()` no longer opens anything or blocks on
stdin -- it drives the login/consent forms directly over HTTP via a new
`simulate_login()` function, ported unchanged in logic from the scratch
driver scripts' `simulate_login()` (which had already been validated
across all 12 of this thesis's official scenario runs to date, driving
the exact same forms from outside the process). This was verified safe
before making the change, not assumed: `mock_as`'s login
(`views/login.ejs`, `utils/opin/routes.js`'s
`POST /interaction/:uid/login`) and consent-confirm
(`POST /interaction/:uid/confirm`) routes are plain HTML `<form>` POSTs
read via `req.body.login`/`req.body.password`, with no CSRF token field
anywhere in the templates and no CSRF middleware anywhere in `mock_as/`
(confirmed by grepping the whole tree for `csrf`/`xsrf`: zero matches).
The only state that needs to carry across requests is the `oidc-provider`
session cookie set on the first `GET /auth`, which a plain
`requests.Session()` already handles automatically.

**Implementation:**
- `simulate_login(auth_url, cert)` (new function, `opin_flow.py`): opens
  its own `requests.Session()` (deliberately separate from the flow's
  shared session, preserving the same connection-pool shape already
  validated under PQC -- see below), follows the `GET /auth?...`
  redirect chain to the interaction page, `POST`s
  `{login, password}` (fixed mock credentials,
  `usuario1@seguradoramodelo.com.br` / `P@ssword01`) to
  `/interaction/{uid}/login`, extracts every hidden
  `<input name="{scope}-accounts" value="{resourceId}">` field from the
  consent page via the same `HIDDEN_ACCOUNTS_RE` regex already validated
  in the driver scripts (an empty confirm body skips resource selection
  entirely, which silently breaks every person-flow resource call
  downstream), and `POST`s them to `/interaction/{uid}/confirm`.
- `wait_for_authorization_code()` starts the same local HTTPS callback
  listener as before (still needed to capture the JARM `response` JWT),
  calls `simulate_login()` instead of `webbrowser.open()`/`input()`, then
  polls `server.captured_params` exactly as before.
- `import webbrowser` removed; `import re` added for the regex.
- These login/confirm HTTP calls are deliberately **not** added to
  `calls`/`do_call()` -- matching how the real browser's requests were
  never part of `total_requests` either. This keeps `total_requests=28`
  and every `calls`-derived metric (`bytes_by_participant`,
  `total_bytes_exchanged`, `jwt_*`) numerically comparable to every
  previously-collected scenario; only the gateway-side metrics
  (`gateway_metrics.*`, sourced from the gateway's own raw access log,
  not from `calls`) change, because they were the ones polluted by the
  browser in the first place.
- `simulate_login()` uses its own `Session`, not the flow's shared one --
  this reproduces, deliberately, the same "AS pool / RS pool / login-pool"
  three-connections-per-flow structure already established (and already
  the source of PQC's stable `N_mTLS=6`) rather than introducing a new
  connection-pooling shape only in classic.

**Effect on the data -- re-ran all 12 scenarios (6 classic + 6 PQC) from
scratch, fully automated, zero manual interaction:**

| Scenario | Classic `N_mTLS` (old, browser-driven) | Classic `N_mTLS` (new, automated) | PQC `N_mTLS` (old) | PQC `N_mTLS` (new) |
|---|---|---|---|---|
| 0ms | 10 | **6** | 6 | **6** |
| 14ms | 9 | **6** | 6 | **6** |
| 30ms | 10 | **6** | 6 | **6** |
| 140ms | 16 | **6** | 6 | **6** |
| 225ms | 10 | **6** | 6 | **6** |
| 320ms | 10 | **6** | 6 | **6** |

`N_mTLS` is now perfectly constant at 6 in *both* experiments, across
all 12 scenarios -- fully comparable between classic and PQC for the
first time, with the confounding real-browser variable eliminated
rather than merely explained. `total_requests` stayed at 28 in every
scenario, `requests_logged` (gateway-side, includes the login/consent
sub-requests) settled at 38 in every scenario in both experiments (was
38 already in PQC; was up to 58 in classic when the browser occasionally
won its connection race). Confirmed unaffected, spot-checked against
the pre-automation committed data for the 0ms scenario of both
experiments: `jwt_count`, `jwt_size_avg_bytes`, `jwt_size_max_bytes`,
and `bytes_by_participant` are identical in PQC, and identical in
classic except for a 6-byte difference in `PKI/CRL` bytes (10000 vs
10006) -- expected run-to-run jitter from Raidiam's real external
sandbox endpoint (`crl.sandbox.pki.opinbrasil.com.br`, hit unchanged by
classic per Decision 12), not a regression. `total_bytes_exchanged` is
byte-for-byte identical across all 6 PQC scenarios (184637, matching
the already-committed value) and within a handful of bytes across all 6
classic scenarios (67600-67606), consistent with that same external-PKI
jitter.

**Follow-up -- consolidation and OPINsize equation recomputed:**
`consolidated.json`/`EXPERIMENT{1,2}_REPORT.md` were regenerated against
these 12 new scenario files. With N_mTLS now deterministic on both
sides, the classical `mTLS_handshake_bytes` P50 also turned out to be
perfectly stable across all 6 scenarios (9785 bytes, was 10.381-10.511
before, no longer needing the old methodology's "average, excluding
0ms" workaround). Recomputing the OPINsize equation with the classical
side's actual N_mTLS=6 (instead of the old scenario-average ~11) drops
OPINsize classical from 151.120 to 95.232 bytes -- 6 x 9785 + 26 x 1385
+ 2 x 256 = 58.710 + 36.010 + 512 = 95.232. OPINsize PQC is unchanged
(264.374 bytes, since PQC's N_mTLS was already 6). Analytical growth
moves from 1,75x to **2,78x**, which now closely matches the empirical
growth already measured in Bloco A (2,73x, ~67.604 -> ~184.637 bytes)
-- two independent measurement methods (the analytical equation,
which includes mTLS handshake cost, and the empirical per-participant
sum, which only covers the HTTP application layer) converging is strong
internal-consistency evidence that the old 1,75x figure was the
distorted one, not the new 2,78x. `Metricas_Experimentais_PQC_OPIN_v2.md`
was updated throughout (Bloco A intro, Bloco C equation and parameter
table, plus two other table cells that still cited the old 10.381-byte
figure) to reflect this.
