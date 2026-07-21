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

## Why these patches exist

By default, the suite validates against (and in one case, calls directly) Raidiam's real Directory (`*.sandbox.directory.opinbrasil.com.br`), with URLs **hardcoded** in source code — not configurable via JSON. Running fully offline/local, this fails with a TLS error (`unknown_ca`) or with the message "Testing for Brazil certification must be done using the Brazil directory". The patches:

1. **`OpinSetDirectoryInfo`** — now uses `directory.discoveryUrl`/`apibase`/`keystore` from the config instead of Raidiam's hardcoded URLs.
2. **`CheckOpinDirectoryApiBase`** / **`CheckOpinDirectoryDiscoveryUrl`** — now accept `https://directory/` as a valid URL, in addition to Raidiam's.
3. **`OpinCallDirectoryParticipantsEndpoint`** — builds the `/participants` URL from the config's `directory.apibase` instead of a hardcoded one.

See `../README.md` for the full context of how these patches fit into the baseline collection.
