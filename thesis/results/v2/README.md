# v2 — PQC Architecture & Migration Decisions (Experiment 2 preparation)

## Purpose

This was the second stage of the PQC migration thesis work. With the
classical baseline established (see [`thesis/results/v1/README.md`](../v1/README.md)),
this stage defined and implemented the actual architecture needed to
migrate the MockOPIN environment from classical to post-quantum
cryptography (ML-DSA-65), so that Experiment 2 could exist at all. The
goals of this stage were to:

- Design a switching mechanism that lets classical (Experiment 1) and
  post-quantum (Experiment 2) cryptography coexist in the same codebase and
  be re-run at will, without reverting code or maintaining diverging
  branches.
- Migrate each participant in the flow — Authorization Server, Resource
  Server, mTLS gateway — to ML-DSA-65, one at a time, verifying each stage
  empirically before moving to the next.
- Determine whether the OpenID Conformance Suite, the tool that drove all
  of Experiment 1, could still act as the OPIN client once a post-quantum
  certificate was involved — and if not, understand exactly why, in enough
  depth to know whether it was worth working around.

This stage is architecture and infrastructure work, not traffic
measurement — it produced no `baseline_metrics.json` of its own. Its
output is [`DECISIONS.md`](experiment2%20-%20PQC/DECISIONS.md): a
running log of every non-obvious technical decision made while migrating
the environment, with the reasoning, the evidence, and (where relevant)
the exact stack traces behind each one.

## What's in this folder

```
v2/
└── experiment2 - PQC/
    └── DECISIONS.md    the architecture-decision log this stage produced —
                          8 decisions, each with context, the option(s)
                          considered, what was verified, and who confirmed it
```

## Timeline

**2026-08-07 — Etapa 1: Authorization Server migrated to ML-DSA-65, and the
classic/PQC switching architecture.** Moved `mock_as` onto Node 24 / `jose`
v6, which delegates signing to Node's native `node:crypto` (ML-DSA support
landed in Node ≥24.7 / OpenSSL ≥3.5) — issuing ML-DSA-65-signed `id_token`s,
request objects, and client-authentication JWTs, verified via the
discovery document, `/jwks`, and a live sign-and-verify round trip inside
the running container. Hit one hard constraint immediately: `jose` v6's
entire verification API is Promise-based, but oidc-provider's
`extraClientMetadata.validator` hook (used to verify the SSA) *must* be
synchronous — so the SSA's PS256 signature is verified by hand with
`node:crypto.verify()` instead, since the SSA is signed by the Trust
Framework/Directory, not the AS itself, and stays classical regardless of
the AS's own profile.

Before going further, settled the classic/PQC switching question: an env
var, `CRYPTO_PROFILE=classic|pqc`, read once at boot and used to pick which
`mock_as/crypto-profiles/<name>.json` to load (signing algorithm + key
material), rather than branching algorithm logic inline throughout the
code. Two alternatives were considered and rejected: Docker Compose
profiles, and separate git branches per experiment — branches specifically
because any later fix to shared infrastructure (Dockerfiles, compose
files, scripts) would have to be cherry-picked across three diverging
branches instead of applying once. The Go gateway deliberately does **not**
get a `CRYPTO_PROFILE`: TLS negotiates its signature algorithm per
handshake, so once the gateway itself is on a PQC-capable Go toolchain
(Etapa 3, below) it is crypto-agile by construction, with no flag needed.
Verified both directions reproduce their respective experiment's AS
signing key exactly (same JWK thumbprint as Experiment 1's archived data
for `classic`; `id_token_signing_alg_values_supported: ["ML-DSA-65"]` for
`pqc`), switching with a container restart alone — no rebuild, no code
change.

**2026-08-07 — Etapa 2: Resource Server response signing, built from
scratch.** Investigation here found the RS (`insurance-server-lambdas`)
never actually signed its API responses at all — `nimbus-jose-jwt` was
present but only used for an unrelated utility class, and incoming access
tokens were parsed with no signature check. This contradicted the FAPI
Security Profile that Open Insurance Brasil (and therefore this thesis)
requires, so it was built as a genuine feature rather than a "migration"
of something that never existed. Both `CRYPTO_PROFILE` values sign for
real — `classic` with PS256 via Nimbus, `pqc` with ML-DSA-65 hand-rolled
over BouncyCastle 1.79's JCA provider (Nimbus has no ML-DSA support in any
release checked) — specifically so that a later classical-vs-PQC
comparison measures the algorithm as the only variable, not "signed vs.
unsigned." Verified end-to-end through the RS's real runtime path (the
embedded Netty server, not the AWS Lambda deployment emulation some
pre-existing tests use — that emulation path turned out to force JSON
re-encoding regardless of content type, breaking 16 pre-existing tests
that were never exercising the real server; documented as a known,
accepted gap rather than fixed, since MockOPIN's actual docker-compose
runtime never goes through that Lambda path).

**2026-08-08 — Etapa 3: mTLS certificates and the Go gateway.** Native
ML-DSA support in `crypto/x509`/`crypto/tls` only exists starting in Go
1.27, which was not yet officially released — the decision was to accept
the pre-release (`go1.27rc2`, available as an official `golang:1.27-rc`
Docker Hub image within days of being needed) since this is thesis
research, not production, and what matters is that the exact toolchain
version is documented. Generated `client_one_pqc.crt`/`.key` by *loading*
the existing CA rather than regenerating it (regenerating would have
invalidated every other certificate in the environment) — an ML-DSA-65
keypair signed by the same classical CA key, which is ordinary, valid
X.509 (issuer and subject key algorithms are independent). The gateway
itself needed **zero** functional code changes beyond the Go version bump:
its TLS config never restricted signature schemes explicitly, so Go
1.27's new `crypto/mldsa`-aware chain verification just applied. Verified
with a real TLS 1.3 handshake against the rebuilt gateway, picked up
automatically by the handshake instrumentation built in v1 with no changes
needed (`clientCertBytes: 2953`, `mtlsHandshakeBytes: 10880` — both far
above the classical baseline's ~1.5KB/~11KB, exactly the growth this
thesis is measuring for).

**2026-08-08 — The Conformance Suite cannot drive Experiment 2, and why.**
With every participant migrated, the same `opin-consent-api-status-test-v3`
module that passed reproducibly in every scenario of Experiment 1 was run
again against `CRYPTO_PROFILE=pqc`. It failed in 5 seconds, before ever
reaching the point of needing the client's mTLS certificate at all. Root
cause: `ValidateServerJWKs`, a condition the suite runs unconditionally
early for every module, parses the AS's `/jwks` with Nimbus — the same
library confirmed PQC-blind in Etapa 1 and Etapa 2 — and Nimbus throws on
the ML-DSA-65 key's `kty: AKP`, aborting the whole check before anything
mTLS-related is attempted. A workaround publishing both a classical and a
PQC key side by side in the same JWKS was considered and ruled out, both
from reading the suite's public source (it iterates keys with no per-key
error handling — the first unparseable key aborts everything, position
and other valid keys irrelevant) and by testing it directly against the
already-mixed JWKS the `pqc` profile produces.

Two further, deeper workarounds were then tried and pushed as far as they
would go, specifically to establish *where* the real wall was rather than
stop at the first failure:
- **Layer 1** — a route in `mock_as` that shadows oidc-provider's own
  `/jwks` handler with a decoy publishing only the classical key (the AS's
  real signing keystore, still ML-DSA-65, is untouched — only the
  published discovery document is a decoy). This got `ValidateServerJWKs`
  to pass and the suite advanced through roughly 20 further conditions.
- **Layer 2** — the suite then hit a `NullPointerException` in
  `ValidateMTLSCertificatesAsX509`: Java 17's default certificate factory
  doesn't recognize ML-DSA's `SubjectPublicKeyInfo` OID and silently
  returns a null public key instead of throwing, which the suite's own
  code doesn't null-check. Registering BouncyCastle as an extra
  `java.security.Provider` in the suite's JVM — via a classpath addition
  and an additive `java.security.properties` file, mounted at runtime with
  no changes to the suite's own jar — fixed the decode and cleared the NPE.
- **Layer 3** — the suite's mTLS client code
  (`AbstractMtlsStrategy.generatePrivateKeyFromDER`) then turned out to
  call `sun.security.rsa.RSAKeyFactory` **by class name**, directly, never
  through the algorithm-agnostic `KeyFactory.getInstance(alg, provider)`
  lookup that would let any registered provider — BouncyCastle or
  otherwise — intervene. This is a hardcoded assumption baked into the
  suite's own compiled logic, not a configuration or missing-algorithm
  gap, and there is no way to clear it without patching and recompiling
  the Conformance Suite from source.

**Final decision:** the Conformance Suite cannot act as an mTLS client
with a post-quantum certificate, full stop, and patching/recompiling it
was explicitly ruled out as disproportionate to this thesis's scope. Both
workarounds (Layers 1 and 2) are kept in the repository, not reverted —
they are real, working infrastructure that measurably advanced the
diagnosis, and they document exactly where the true limitation sits.
Experiment 2's measurement strategy changed as a direct result: a Python
script calling the AS and RS directly, reproducing the same call sequence
the suite's own modules made, replaces the Conformance Suite as the
traffic generator from this point on.

## Known limitations (carried forward, not fixed)

- **The Conformance Suite cannot drive PQC traffic**, for the three
  structural reasons above. Layer 3 specifically is not fixable without
  patching and recompiling the suite's own source, which was ruled out of
  scope.
- **The RS's AWS Lambda deployment-emulation test path** re-encodes
  response bodies as JSON regardless of content type, breaking 16
  pre-existing tests that exercise only that path. Not fixed, since
  MockOPIN's actual runtime (this thesis's environment) never uses it.

## Relationship to later stages

This stage's central finding — that the Conformance Suite cannot be the
traffic generator once PQC is involved — is why
[`thesis/scripts/opin_flow.py`](../../scripts/opin_flow.py) exists: a
direct Python client reproducing the same OPIN consent flow the suite's
own modules drove in Experiment 1, validated against Experiment 1's raw
logs call-for-call. Its actual six-latency-scenario runs, using the
`CRYPTO_PROFILE`/certificate/RS-signing architecture defined in this
stage, live in `thesis/results/v3/`. An eighth decision, covering exactly
which of the Conformance Suite's original modules `opin_flow.py` does and
doesn't reproduce, was later appended to this stage's `DECISIONS.md` once
that tooling existed.
