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
