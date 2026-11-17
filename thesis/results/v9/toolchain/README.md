# v9 Phase 1, T2: reproducible Go toolchain

Local, in-container build of Go from the official source code, at a
pinned tag, to serve as the base for the `crypto/tls` fork that
Hybrid-AND (D2/D3) requires. No AWS here; nothing is published outside
this repository.

## Chosen version: go1.27.3

v8 used `go1.27rc2` (release candidate). For v9, the final version
chosen is **go1.27.3** (released 2026-10-19), neither the rc2 nor the
plain 1.27.0, for the three reasons recorded in the `Dockerfile`'s
header and in the corresponding Decision in `DECISIONS.md`:

1. rc2 was never promoted to stable; v9 begins a more sensitive
   mechanism (forking `crypto/tls` itself), with no reason to start
   from a pre-release base.
2. go1.27.3 includes a `crypto/x509` security fix that rc2 does not
   have, and the AND mechanism depends directly on that package's
   chain verification (two independent chains).
3. It is the same version against which Luciano's external reference
   patch (outside this repository) has already been validated -- using
   the same one here eliminates any version drift between that
   validation and the rebuild done inside this container.

Commit of the `go1.27.3` tag, verified in this session against
`go.googlesource.com/go`: `2aae1000ea1d4b28923b96db28acf4e3b99d6aff`. The
`Dockerfile` fails the build if the clone resolves to a different commit.

## What the Dockerfile does

1. Uses `golang:1.27.3-alpine` (pinned by digest) **only** as the
   bootstrap compiler (`GOROOT_BOOTSTRAP`).
2. Clones `go.googlesource.com/go` fresh, at tag `go1.27.3`, and confirms
   the commit against the value above.
3. Applies `patches/and.patch` via `git apply`, if the file is not
   empty. At this stage (T2) the file is deliberately empty -- the
   goal here is to prove the build+test pipeline works end to end
   BEFORE any fork code exists. T3 replaces this file with the real
   patch (~220 lines across 6 files + `dual.go`) and uses this same
   Dockerfile, unmodified, to apply and test it.
4. Runs `./make.bash` to build the toolchain from the source
   (patched or not).
5. Runs the `crypto/tls` package's test suite, unmodified
   (`go test -count=1 -v ./...` inside `src/crypto/tls`), against the
   freshly built toolchain.
6. Writes `/build_metadata.json` inside the image with the Go version,
   the commit, the two base-image digests, and the SHA-256 of the
   applied patch (or the explicit mark that none was applied).

## How to run

```
cd thesis/results/v9/toolchain
docker build -t mockopin-v9-toolchain .
docker run --rm mockopin-v9-toolchain cat /crypto_tls_test_output.txt
docker run --rm mockopin-v9-toolchain cat /build_metadata.json
```

## Expected result (T2, empty patch)

The `crypto/tls` suite should pass in full, with the exception of
any test that depends on real internet access (a pre-existing
property of that suite, not something introduced by this build). The
real result of this round is recorded in the T2 Decision in v9's
`DECISIONS.md`, along with the exact PASS/FAIL/SKIP count.

## T3, completed and reviewed: real patch applied and tested

`patches/and.patch` contains the real AND mechanism: `dual.go` (321
lines) + changes to 6 existing files (`common.go`, `conn.go`,
`handshake_client.go`, `handshake_client_tls13.go`,
`handshake_messages.go`, `handshake_server_tls13.go`, 543 lines in
total outside `dual.go`/tests, plus a 5-line registration in
`tls_test.go`) + `dual_test.go` (903 lines, 23 tests). Patch SHA-256:
`65f7ef4e50f5fd6025e9ab048cb4dd360a1455b3708702d648a93bd5c510cb2c`.

**Real bug found and fixed in the Dockerfile itself, before the
first result:** the first version of this step did `cd src &&
git apply ... && cd ..`, and reported success (exit 0) while
"Skipping" (`Skipped patch`) every file in the patch, without applying
anything -- `git apply` resolves the patch's paths against the ROOT of
the git repository, not against the shell's current directory. Fixed
with `git apply --directory=src/crypto/tls`. **Hardened afterward**:
the step now counts how many files `and.patch` itself touches (via
`grep -c '^diff --git'`) and explicitly fails the build (`exit 1`) if
`git status` does not show exactly that number of changed files in
`src/crypto/tls` -- confirmed in an isolated diagnostic container that,
by deliberately reintroducing the old bug, the check now detects the
divergence (9 expected vs. 0 real) instead of letting it pass.

**Real result, full `crypto/tls` suite (original + the 23 AND
tests), against the go1.27.3 toolchain rebuilt from the real patch,
via the complete pipeline (clone -> verify commit -> hardened
`git apply` -> `make.bash` -> test):** `ok crypto/tls
58.248s` -- **237 PASS, 0 FAIL, 0 SKIP** at the level of
named tests (214 from the original suite, unchanged, + 23 from AND).
Also counting the internal subcells of `TestBogoSuite` (the
BoringSSL conformance suite, embedded and offline): 2.991 PASS, 0 FAIL,
2.278 SKIP -- the skips are all internal to that conformance matrix
(BoGo's own decisions about which cases apply to
this build), unrelated to the network; `TestVerifyHostname`,
`TestRealResumption`, and `TestBogoSuite` itself (top level)
pass, confirming real network availability inside the container. Wire-size
measurement (`TestDualWireSizeMeasurement`): classical-only
Certificate message 814 B vs. dual (classical+ML-DSA-65) 6.355 B (+680,7%);
classical-only CertificateVerify signature field 256 B vs. dual
3.567 B (+1.293,4%); isolated PQ chain 5.533 B.

Full detail, including the side-by-side impostor test (strict/
non-strict pair), the decision on session resumption and
HelloRetryRequest, the per-file table, and the decision on the patch's
size (543 lines outside `dual.go`/tests, above the ~400 expected,
kept as is by Luciano's decision): Decisions 6 and 7 in v9's
`DECISIONS.md`.
