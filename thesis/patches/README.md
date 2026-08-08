# Patches — Conformance Suite

`insurance-server-lambdas/conformance-suite/` is cloned on demand (`make setup-cs`) from `gitlab.com/raidiam-conformance/open-insurance/open-insurance-brasil`, and is gitignored by this project (`insurance-server-lambdas/.gitignore`). Because of that, the modified versions of these files are preserved here — without this, the patches would silently disappear on every fresh clone.

## How to apply

After running `make setup-cs` (clones `conformance-suite/`), copy these files to the equivalent paths inside the cloned folder, overwriting the originals:

| File here | Destination in `insurance-server-lambdas/conformance-suite/` |
|---|---|
| `testmodule-support/OpinSetDirectoryInfo.java` | `src/main/java/net/openid/conformance/opin/testmodule/support/OpinSetDirectoryInfo.java` |
| `testmodule-support/CheckOpinDirectoryApiBase.java` | `src/main/java/net/openid/conformance/opin/testmodule/support/CheckOpinDirectoryApiBase.java` |
| `testmodule-support/CheckOpinDirectoryDiscoveryUrl.java` | `src/main/java/net/openid/conformance/opin/testmodule/support/CheckOpinDirectoryDiscoveryUrl.java` |
| `testmodule-support/OpinCallDirectoryParticipantsEndpoint.java` | `src/main/java/net/openid/conformance/opin/testmodule/support/OpinCallDirectoryParticipantsEndpoint.java` |
| `server-dev/Dockerfile` | `server-dev/Dockerfile` (fixes a malformed line break + a discontinued base image) |
| `httpd/Dockerfile-static` | `httpd/Dockerfile-static` (fixes the discontinued `debian:buster` base image) |

After copying, rebuild the jar (`make setup-cs` again — build phase, ~15-20min) and recreate the container: `docker-compose up -d --force-recreate cs-server` inside `insurance-server-lambdas/`.

## `extra-libs/` — not copied in, mounted directly

Unlike the Java patches above, `extra-libs/` (`bcprov-jdk18on-1.79.jar`,
`bcutil-jdk18on-1.79.jar`, `bc.security`) doesn't need to be copied into the
cloned `conformance-suite/` or compiled in — it's runtime-only, and
`insurance-server-lambdas/docker-compose.yml`'s `cs-server` service mounts
this folder directly (`../thesis/patches/conformance-suite/extra-libs/:/extra-libs/:ro`)
and adds `-Djava.security.properties=/extra-libs/bc.security` plus a
classpath addition to `cs-server`'s `command`. It registers BouncyCastle as
an extra `java.security.Provider` in the suite's JVM, needed for Experiment
2 (pqc) -- see `thesis/results/experiment2 - PQC/DECISIONS.md`, Decision 7,
for what this fixes (an NPE decoding an ML-DSA-65 certificate's public key)
and what it doesn't (the suite's own mTLS HTTP client code hardcodes RSA by
name a step later, which no provider registration can work around).

## Why the Java patches exist

By default, the suite validates against (and in one case, calls directly) Raidiam's real Directory (`*.sandbox.directory.opinbrasil.com.br`), with URLs **hardcoded** in source code — not configurable via JSON. Running fully offline/local, this fails with a TLS error (`unknown_ca`) or with the message "Testing for Brazil certification must be done using the Brazil directory". The patches:

1. **`OpinSetDirectoryInfo`** — now uses `directory.discoveryUrl`/`apibase`/`keystore` from the config instead of Raidiam's hardcoded URLs.
2. **`CheckOpinDirectoryApiBase`** / **`CheckOpinDirectoryDiscoveryUrl`** — now accept `https://directory/` as a valid URL, in addition to Raidiam's.
3. **`OpinCallDirectoryParticipantsEndpoint`** — builds the `/participants` URL from the config's `directory.apibase` instead of a hardcoded one.

See `../README.md` for the full context of how these patches fit into the baseline collection.
