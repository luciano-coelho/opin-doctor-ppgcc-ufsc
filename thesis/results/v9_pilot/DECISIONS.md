# Decisions — v9 (Hybrid-AND, two-certificate TLS authentication, phase 1 local)

## 1. T1, reconnaissance: facts A, B, E, and F confirmed in the current code; fact D does not reproduce in the official v8 data (clarified later, see note); fact C is left for Decision 2 (direct reading of the SAD)

**Fact A, confirmed.** `mock-service-os/mock_mtls/hybridVerification.go`,
`hybridVerifyPeerCertificateFunc()`/`verifyHybridClientCert()`: the
ML-DSA-65 signature verified in Hybrid-v8 is only the CA's signature
over the preTBS of the CLIENT's certificate (proof that the CA signed
that content, never a proof of possession of the ML-DSA key by the
party connecting). The actual proof of possession during the TLS
handshake is RSA only (`CertificateVerify`). The SERVER's certificate
never undergoes an equivalent check on the client side.

**Fact B, confirmed on both points.** `thesis/scripts/tls_kem_proxy/
main.go:212`: `InsecureSkipVerify: true` in `upstreamTLSConfig`, for all
three v8 profiles, varying only the curve. `mock-service-os/certs/main.go`:
every certificate generation uses `ExtKeyUsageClientAuth`, including the
certificates used as the SERVER certificate (`mtls_pqc`,
`mtls_hybrid`); no occurrence of `ServerAuth` anywhere in the file.

**Fact D, investigated, clarified by Luciano (see his message).**
I recalculated from the official data of the 720 runs
(`consolidated_combined.json`) and confirmed that `term_handshake_pcap`
matches `term_handshake` (gateway) exactly across the three profiles, 0%
difference -- in other words, the current pcap extractor
(`pcap_utils.py`, `extract_clean_handshake_bytes()`), even after the fix
from Decision 85 of v8, does NOT exclude the first HTTP request in
practice, because its phase 3 consumes the entire segment in the same
direction without being able to distinguish, without a keylog, where
the TLS 1.3 `Finished` ends (both come out as the same encrypted 0x17
record on the wire). Luciano confirmed that the values 4.945/22.373/
18.783 B came from a recalculation of his, done outside this
repository, using a TCP segment boundary heuristic (first
client->server segment that begins with 0x17 after the client's flight),
valid in ~97-99,7% of connections but it is an ESTIMATE, not official
data. The official figures remain those from the gateway (5.179/22.607/
19.017 B). Adjustment recorded for T6(d): byte counting INSIDE the
process (net.Conn that sums bytes in both directions, closes the count
when `tls.Conn.Handshake()` returns, in the client proxy and in the
gateway), giving the exact boundary without depending on pcap; keylog +
full pcap remain as an independent cross-validation.

**Fact E, confirmed, and it explains fact D.** Without SSLKEYLOGFILE, no
handshake message after the ServerHello is distinguishable in the pcap,
by construction of TLS 1.3 (everything is encrypted as the same record
type externally). Snaplen 256 confirmed in `campaign_run.py`
(`TCPDUMP_SNAPLEN_BYTES`).

**Fact F, confirmed, already documented honestly in the current v8 final
report.** Handshake residue above expected: Section 6 of
`Consolidated_Metrics_Report_FINAL.md`, "not attributed," investigated
without an isolated cause identified with confidence. Residue of ~14% of
T_flow in the reference cell (240,1/260,3/253,9 ms, Classical/PQC/Hybrid):
same section, with the Hybrid "HTTP calls" phase being the largest of
the three (410,7 ms), "partly residual, not fully attributed." Item
T6(f) of this plan tackles this point directly (server time per call).

**Luciano's Decisions D1-D6 and the AND mechanism specification**: no
contradiction with the current code. No patch or `dual.go` file exists
in this repository yet -- confirmed by search, nothing to reconcile, T3
implements it from scratch per the specification received.

**Scope confirmed for the next tasks, no blocker:** `certs/
main.go` (1.333 lines, generic functions reused by name) will
need a new function for Hybrid-AND (two independent chains) in T4;
`mock_mtls/main.go` currently has a fixed `ClientAuth`
(`VerifyClientCertIfGiven`) for all profiles, which will become
profile-dependent in T5 (`RequireAndVerifyClientCert` only for
Hybrid-AND, D3). There is no Go installed locally in this environment,
but Docker (29.9.1) is available and working, no blocker for T2.

No action on AWS, no terraform touched, no commit prior to this one.

## 2. Fact C: direct reading of the SAD (local `docs/`, not version-controlled), confirming 7 points requested by Luciano

**File read:** `thesis/docs/SAD - Luciano Coelho - PPGCC (1) (2).pdf`.
SHA-256: `fac336b95c9a803cb11ad50079b969146f54e7daf1ba9e4182a91500aaa55184`.
36 pages. Environment without `poppler-utils`, hence no visual
rendering of the pages available in this session -- reading done via
text extraction (`pypdf`), not from a page image. Recorded here as an
explicit limitation of the method, not hidden: if something diverges
from a visual/OCR reading, what is written on the page governs, not
this note.

**Critical finding, outside the original request, that needs a decision
from Luciano before any further action:** this same PDF (and a second
one, `thesis/docs/Parecer tecnico ... .pdf`) are ALREADY version-controlled
in git, present in the current tree of `main` and of `origin/main`
(public/shared push), since commits `e88e3734` (2026-09-11) and
`478bda51` (2026-09-29) respectively -- contrary to Luciano's premise
that `docs/` is a local, non-version-controlled folder. Reported in
chat before any other action; no git action (history rewrite, force
push) was taken without his confirmation.

**Point 1, confirmed.** Page 11 (printed "10"), Figure 1, step 3:
"Primitive: RSA (IFP), Parameter: RSA-2048". Repeated in Table 1
(page 17, printed "16"), step 3: "RSA-2048 — Shor — Institutional
identity authenticity".

**Point 2, confirmed with one wording caveat.** BRCAC (step 4a):
page 11, "Primitive: RSA (IFP) · ECDHE (ECDLP), Parameter: RSA-2048" —
exactly the primitive combination of an `ECDHE-RSA`, but the document
never literally uses that cipher suite name. As for TLS 1.3: page 12
(printed "11") describes the data-exchange channel in general as
"TLS 1.2/1.3" (Rescorla, 2018), not only "TLS 1.3"; Figure 2
(page 19, printed "18"), on the row for step 9/HNDL, uses "TLS 1.3"
in isolation. In other words: RSA-2048+ECDHE confirmed for the BRCAC;
"TLS 1.3" does appear, but alongside "TLS 1.2/1.3" elsewhere in the
same document, not as the only version cited.

**Point 3, confirmed, with a distinction worth recording.** PS256
(RSA-PSS+SHA-256) for SSA (step 5), OIDC consent (step 7), and the
FAPI access token (step 8): page 14 (printed "13"), "mandates
RSA-PSS with SHA-256, referred to as PS256, as the signing primitive for
access tokens, identity tokens, and request objects"; also confirmed
in Figure 1/Table 1 per step. RSA-OAEP: same page 14, "RSA-OAEP
performs key encapsulation in JWE envelopes" — but this is specifically
about the data exchange (step 9), not a generic statement that SSA/FAPI/
OIDC use RSA-OAEP in their own signature payloads (which use PS256,
not RSA-OAEP). Both algorithms are in the document, at different steps
of the flow.

**Point 4, confirmed.** Table 1 (page 17, printed "16"), "Quantum
exposure mapping by OPIN operational step": Shor at steps 3, 4a, 4b, 5,
6, 7, 8, 9; Grover at step 10. Urgency levels: Section 3.1 (page 29,
printed "28"), "THREE-TIER MIGRATION URGENCY TAXONOMY" — Level 1
(ECDHE/RSA-OAEP, HNDL, irreversible), Level 2 (signatures, PS256,
institutional-authentication dimension of the BRCAC), Level 3 (SHA-256,
Grover).

**Point 5, NOT FOUND in the SAD -- dropped per Luciano's instruction.**
I searched for "Double-Lock"/"Double Lock" across all 36 pages
(full text extraction, automated search): zero occurrences. Confirmed
by Luciano: that expression comes from other material (slides), which
will NOT be used in v9 -- do not cite or investigate it further. The
single, primary source for v9 is this 36-page written SAD. The model
that actually exists in the document, under that name, is the "Phased
Hybrid Transition Model" (Section 3.2, page 30, printed "29").

**Consolidated citation, by supported statement (requested by Luciano) --
PDF page and printed page (the printed page is always one unit behind
the PDF page, because of the 2 unnumbered cover pages):**

- **RSA-2048 baseline**: Figure 1 (PDF 11, printed 10), step 3,
  "Primitive: RSA (IFP), Parameter: RSA-2048"; Table 1 (PDF 17,
  printed 16), same step; and the sentence from PDF 14 (printed 13) -- "The
  FAPI profile additionally requires certificate-based mutual
  authentication for all API interactions, binding each channel to the
  RSA-2048 public key of the communicating institution" -- FAPI binds
  each channel to the institution's RSA-2048 public key. All three
  support the same statement: OPIN's normative baseline is RSA-2048,
  never RSA-4096, at every step with a classical dependency.
- **Hybrid signature**: Section 2.2 (PDF 26-27, printed 25-26) --
  "a hybrid signature concatenates the classical signature, such as
  PS256, with the post-quantum signature, such as MLDSA, over the same
  content" -- concatenates the classical signature (PS256) with the
  post-quantum one (ML-DSA) over the SAME content. This sentence
  directly supports the design of the AND mechanism's dual
  `CertificateVerify` (two signatures over the same transcript value,
  same context) and feeds into the AND's own decision record
  (Decision 4 below).
- **Transition model**: Section 3.2 (PDF 30, printed 29), "PHASED
  HYBRID TRANSITION MODEL" -- three sequential phases (inventory with
  no algorithm change; simultaneous hybrid operation at levels 1 and 2;
  PQC-only consolidation). Supports the backward-compatibility model
  recorded in Decision 5.

**SAD already in origin/main**: left as is, per Luciano's explicit
instruction -- no git action taken because of this in this session,
nor now.

**Point 6, confirmed.** Section 3.3 (page 30, printed "29"),
"NORMATIVE EXTENSION REQUIREMENTS": among the six normative gaps
listed, "restriction of the OPIN Technical Controls (Open Insurance
Brasil, 2022) to classical algorithms". References (page 34, printed
"33"): "OPEN INSURANCE BRASIL. Controles Tecnicos de Seguranca da
Informacao, Versao 3.2. [S.l.:s.n.], 2022." — version "3.2" confirmed
exactly.

**Point 7, confirmed by exhaustive search.** "4096" does not appear a
single time across the 36 pages (automated search on the full extracted
text). Every RSA parameter cited in the document, at every step, is
RSA-2048.

**Decision made based on this reading:** do not version-control this
PDF again (it has already been version-controlled since
2026-09-11/2026-09-29, by a decision predating Luciano's current
request to the contrary -- the decision on what to do about it awaits
his confirmation, not reverted unilaterally here). No new copy of the
PDF was created; this Decision is the only place where the content was
cited.

**Question posed to Luciano about the already-version-controlled PDF
finding:** he chose "nothing for now" -- no git action taken on this in
this session, neither on history nor on the current state. Recorded
here so it is not lost; the decision on how to handle it is his,
whenever he wants.

## 3. T2, reproducible Go toolchain: go1.27.3 chosen and justified, build from official source successful, crypto/tls suite 100% green (214 PASS, 0 FAIL, 0 SKIP)

**Version chosen: go1.27.3** (not go1.27rc2, which v8 used, nor plain
go1.27.0). Three reasons, in order of weight:
1. rc2 is a release candidate, never promoted to stable -- v9 is
   starting a more sensitive mechanism (a fork of `crypto/tls` itself),
   with no reason to start from a pre-release base when the final
   release exists.
2. go1.27.3 (released 2026-10-19, confirmed via search) includes a
   security fix in `crypto/x509` that rc2 does not have -- relevant
   because the AND mechanism depends directly on that package's chain
   verification.
3. It is the same version that Luciano's external reference patch has
   already been validated against, outside this repository -- it
   eliminates version drift between that validation and the
   reconstruction done here.

**Commit of the `go1.27.3` tag**, resolved via `git ls-remote --tags
https://go.googlesource.com/go go1.27.3` in this session:
`2aae1000ea1d4b28923b96db28acf4e3b99d6aff`. The `Dockerfile`
(`thesis/results/v9/toolchain/Dockerfile`) fails the build if the clone
resolves to a different commit.

**Base images, pinned by digest** (`docker pull`, resolved in this
session): `golang:1.27.3-alpine@sha256:
d200d2dd76b03a99b52651fd1325aff7dcd35422c35c01bac56571b0507f3deb`
(used only as a bootstrap compiler) and `alpine:3.24@sha256:
be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a`
(builder image).

**Pipeline**: clones `go.googlesource.com/go` fresh at the `go1.27.3`
tag (does not reuse the `/usr/local/go/src` from the bootstrap image,
so that the commit actually compiled can be verified against the
public tag); applies `patches/and.patch` via `git apply` if the file is
not empty (empty at this stage -- no fork code exists yet, on purpose,
this is the proof that the pipeline works before T3 writes the real
patch); runs `./make.bash`; runs the `crypto/tls` package test suite,
unmodified.

**Real bug found and fixed in the Dockerfile itself in this session,
before the final result:** the first version did `go test | tee
file; echo "exit_code=$?"` -- `$?` after a pipe captures `tee`'s exit
code, not `go test`'s, so a failing test would NOT fail the build.
Fixed to `bash -o pipefail -c "go test |
tee file"`, which propagates `go test`'s real exit code.
Necessary before T3, where real test failures need to be detected.

**Result, full `crypto/tls` suite, unmodified, against the
freshly-compiled go1.27.3 toolchain:** `ok crypto/tls 48.969s` -- **214
PASS, 0 FAIL, 0 SKIP**. The container had real network access during
the build/test, so this result does not distinguish "the suite has no
test that needs internet" from "it needed it and the network was
available" -- recorded as an observation, not as a claim of
network-isolated testing.

Committed artifacts: `thesis/results/v9/toolchain/Dockerfile`,
`README.md`, `patches/and.patch` (empty, T3 placeholder),
`build_metadata.json`, `crypto_tls_test_summary.txt`.

**go1.27.3 approved by Luciano as the final v9 version** (confirmed
explicitly in his response to this Decision's report). Nothing to
revise here.

## 4. Scope added by Luciano after the Fact C/T2 report (SAD, Section 3.4): stack divergence, TLS 1.3 limitation, interoperability matrix

**a) Declared stack divergence.** The SAD (Section 3.4, "EXPERIMENTAL
VALIDATION", PDF 31/printed 30) foresees the experimental environment
with "reference implementations of MLKEM and MLDSA made available by NIST...
integrated with open-source cryptographic libraries with support for
hybrid operations, namely OpenSSL and liboqs". v9 (like the entire
v1-v8 series before it) uses Go 1.27.3 with native ML-DSA-65 and
ML-KEM-1024 from `crypto/tls`/`crypto/x509`/`crypto/mldsa` in the
stdlib itself, without OpenSSL or liboqs. Justification recorded: (1)
this is the SAME stack that the whole project has used for PQC/Hybrid
since v6 (Level 1) -- switching to OpenSSL+liboqs now would invalidate
comparability with v6-v8; (2) the AND mechanism requires a fork of
`crypto/tls` itself (ClientHello, CertificateRequest, Certificate
message, dual `CertificateVerify`) -- this is only feasible with access
to the TLS stack's source code, which the Go stdlib offers directly
and which OpenSSL (a C library, binary API) would not offer without an
equivalent, more expensive fork of OpenSSL itself; (3) Go 1.27 already
has native and tested ML-DSA-65/ML-KEM-1024 (confirmed in T2),
eliminating the external liboqs dependency that the SAD anticipated
when it was written (before these APIs existed in the Go stdlib). A
real divergence from what the SAD proposed, recorded here, not hidden.

**b) Declared limitation: TLS 1.3 only, not TLS 1.2/1.3.** The SAD
cites OPIN's data channel as "TLS 1.2/1.3" (PDF 12/printed 11). The AND
mechanism, per the specification received from Luciano itself, only
works in TLS 1.3 (the `signature_algorithms`/`CertificateRequest`
extended with code 0xFE65 and the design of the dual
`CertificateVerify` have no defined equivalent in TLS 1.2, and the
specification's "known gaps" list this explicitly: "no explicit TLS 1.2
rejection -- use is TLS 1.3 minimum"). Recorded as an explicit
limitation of the Hybrid-AND measured in v9: it covers only the TLS 1.3
subset of what the SAD describes for the OPIN channel, not the TLS 1.2
that the SAD also allows.

**c) Interoperability matrix -- checking what already exists before
implementing.** I searched `Consolidated_Metrics_Report_FINAL.md` and
v8's `DECISIONS.md` for any cross-profile interoperability measurement
(client of one profile against server of another). The only existing
finding is **PQC against a generic OpenSSL client**
(`thesis/results/v8/artifacts/pqc/openssl_interop_diagnosis.md`,
Section 2 of the final report) -- a configuration diagnosis (missing
the `-sigalgs` flag), not a matrix among the project's OWN profiles. v8
never tested a Classical client against a PQC server, or any other
cross combination: by design, the client (`tls_kem_proxy`) and the
server (`mock_mtls`) always use the SAME `CRYPTO_PROFILE` in every
official run. **Confirmed to Luciano: there is no cross-profile
interoperability matrix in any v8 data or report** -- this is
genuinely new scope for v9, implemented in T3/T4 as a local functional
test (not part of the official performance results), covering
Classical, PQC, Hybrid-v8, Hybrid-AND-non-strict and Hybrid-AND-strict,
per client x server pair, with success/failure, reason,
`DualAuthenticated` (indicates downgrade), and the "effective AND
protection: yes/no" column.

## 5. Strict mode and backward compatibility

**Strict is a per-pair policy, not a global protocol.** The mechanism
(client offers 0xFE65 alongside the classical schemes; server chooses
the dual pair if it has a PQ chain available) supports both
`Dual.Require=true` (strict) and `Dual.Require=false` (non-strict) --
T3's patch keeps both configurations, with no automatic fallback built
INTO the officially measured Hybrid-AND profile (which always runs
strict, per D3). The experiment measures only that profile, where
every participant is Hybrid-AND, so the strict mode does not distort
the official metric -- it would only show up if the experiment tested
a mixed pair, which the interoperability matrix (Decision 4c) does
deliberately, outside the official results.

**Proposed transition model, aligned with the SAD (Sections 3.2 and
3.4, via Decision 2):** non-strict for a pair not yet migrated (the
connection is marked as lacking AND protection, via
`DualAuthenticated=false`); strict for a migrated pair; until strict
becomes the ecosystem's general rule. Logic similar to HSTS (trust on
first use / enforce once confirmed). **The trustworthy source for
"this pair has already migrated" (for example, a field in the OPIN
Participant Directory) is NOT implemented in v9** -- recorded here as
future work and a dependency on OPIN's own governance, without
claiming that the real Directory already has that field today (it does
not, per what the SAD describes).

**A classical participant against a strict server is rejected by
design** -- which is exactly what the impostor test (below) and the
interoperability matrix demonstrate. The operational alternative (a
separate, non-strict endpoint to accept classical participants during
the transition) is equivalent to non-strict AT THAT SPECIFIC endpoint,
and must be described as such, never as "the strict server accepting
classical."

**Impostor test (evidence for why strict mode is mandatory) -- result
in Decision 6 (T3).**

## 6. T3, containerized AND patch: implemented from scratch per the specification, 18 tests (15 items from the original request, 3 with two scenarios each, 18 scenarios in total), full crypto/tls suite (232 PASS, 0 FAIL, 0 SKIP), actually applied via git apply in the T2 pipeline

**What was implemented**, in `thesis/results/v9/toolchain/patches/and.patch` (SHA-256
`cc61d6dec9c774b358d48ff528e8d46bd178ccb71d78e01fbd22bef324fffb95`):

- `dual.go` (304 lines, new): `DualConfig` (`Certificates`,
  `RootCAs`, `ClientCAs`, `Require`), the private code `0xFE65`, the
  dual signing/verification functions (`signDualMessage`/
  `verifyDualMessage`, no short-circuit -- both halves are always
  verified, the combined result only at the end), the independent
  validation of the peer's PQ chain (`verifyDualPeerChain`: own root,
  EKU, hostname when applicable, category -- ML-DSA only, ML-DSA-65
  leaf), the "classical chain without ML-DSA" check
  (`verifyClassicalHalfIsClassical`), and identity comparison by SAN
  set (`sameDualIdentity`).
- Changes to 6 existing files, 529 lines in total (outside
  `dual.go` and the tests -- above the ~400 that Luciano marked as the
  stopping point; I asked, he confirmed proceeding as is, see note
  below): `common.go` (+30, `Dual` field in `Config`, `Clone()`, 3 new
  fields in `ConnectionState`), `conn.go` (+10, internal `Conn`
  fields + population in `connectionStateLocked`), `handshake_client.go`
  (+17, offer of the dual code in the ClientHello, prohibition of
  `InsecureSkipVerify` with `Dual`), `handshake_client_tls13.go` (+172,
  verification of the server's PQ chain and of the dual
  `CertificateVerify` on the client, sending the certificate+dual
  signature when the server requests it),
  `handshake_messages.go` (+157, the parser/serializer for the 3
  zero-byte delimiter in the Certificate message), `handshake_server_tls13.go`
  (+138, selection of the dual certificate on the server,
  `CertificateRequest` with the dual code, verification of the
  client's pair). `tls_test.go` (+5, registration of the `Dual` field
  in `TestCloneNonFuncFields`, required by that existing test itself).
- `dual_test.go` (718 lines, new): 18 tests -- the 15 items from the
  original request (counted by semicolon), 3 of them with two
  scenarios each, giving the 18 scenarios covered (see Decision 7,
  item 3, and Luciano's confirmation in Decision 8: "15 items, 18
  scenarios" is the correct count, "17" discarded). Exact names of the
  3 requested by Luciano, used literally:
  `TestDualQuantumAdversaryHoldingOnlyRSAKey`,
  `TestSingleChainRSAAdversaryStillAuthenticates`,
  `TestDualNonStrictAllowsDowngrade`.

**Patch-size decision, asked and confirmed by Luciano.**
529 lines outside `dual.go`/tests exceeds the ~400 he marked as an
explicit stopping point. I asked before proceeding; he confirmed
"proceed as is" -- the excess comes from needing the full logic on
both sides (client sends and verifies, server sends and verifies),
with real security validation (independent chains, SAN, no
short-circuit), not from loose or needlessly duplicated code.

**Impostor test, the two results side by side (the direct evidence for
why strict mode is mandatory):**

| Test | Adversary | Verifying pair | Result |
|---|---|---|---|
| `TestDualQuantumAdversaryHoldingOnlyRSAKey` | Has the legitimate pair's RSA key, does NOT have the ML-DSA key (presents the legitimate, public PQ certificate, but signs with a different ML-DSA key, for lack of the real one) | Strict AND server (`Dual.Require=true`) | **Rejected** -- classical ok, post-quantum fake, server refuses the pair |
| `TestSingleChainRSAAdversaryStillAuthenticates` | The SAME adversary (RSA key only, single chain, nothing post-quantum) | Common classical server, mTLS without `Dual` (Hybrid-v8 format: ML-DSA only as the CA's signature, never verified in the handshake) | **Authenticates normally** -- there is no PQ key possession proof to fail, because it is never requested |

This table demonstrates exactly the gap that motivated v9 (fact A of
Decision 1): the same adversary, with the same stolen key, is rejected
by the AND mechanism and accepted by Hybrid-v8.

**Real bug found and fixed in T2's own `Dockerfile`, before the final
result.** The first attempt to apply the real patch
(`cd src && git apply /tmp/and.patch && cd ..`) reported success (exit
0) but "Skipped" (`Skipped patch`) every file, applying nothing --
`git apply` resolves the patch's paths against the ROOT of the cloned
git repository, not against the shell's current directory, and the
patch was generated with paths relative to `crypto/tls` (`a/common.go`),
not to `src/crypto/tls` (the clone's real root). Fixed with
`git apply --directory=src/crypto/tls`, the option that prefixes each
patch path -- confirmed in an isolated diagnostic container before
touching the real Dockerfile.

**Two other real bugs found and fixed during the implementation
itself, not in the Dockerfile:**
1. `net.Pipe()` in the tests caused a transport deadlock whenever the
   client aborted the read in the middle of the server's first flight
   (exactly the case for the negative tests) -- replaced with
   `localPipe(t)` (real TCP on loopback, the same mechanism that the
   `crypto/tls` suite itself already uses for full handshakes).
2. Go's own `getClientCertificate()`, unmodified, filters the client's
   classical certificate by the same signature algorithm list the
   server announced in the `CertificateRequest` -- in strict mode that
   list is only `0xFE65`, which does not match any real classical
   algorithm, causing the client to send no certificate at all even
   though it has one available. Fixed by using a common classical
   algorithm list solely for certificate SELECTION, not for the
   signature scheme choice (which remains the dual code).

**Final result, full `crypto/tls` suite (original + the 18 new
tests), against the go1.27.3 toolchain rebuilt from the real patch,
through T2's complete pipeline (clone -> verify commit ->
`git apply` -> `make.bash` -> test):** `ok crypto/tls 55.306s` --
**232 PASS, 0 FAIL, 0 SKIP** (214 from the original suite, unchanged, +
18 new). Wire-size measurement (`TestDualWireSizeMeasurement`,
real data from this run): classical-only Certificate message 814 B vs.
dual (classical+ML-DSA-65) 6.355 B (+680,7%); classical-only
CertificateVerify signature field 256 B vs. dual 3.567 B (+1.293,4%);
standalone PQ chain 5.533 B.

Updated artifacts: `thesis/results/v9/toolchain/Dockerfile`,
`README.md`, `build_metadata.json`, `crypto_tls_test_summary.txt`,
`patches/and.patch` (now with the real content, no longer empty).

## 7. Response to 6 points requested after the T3 report: full impostor pair, SKIPS explained, exact count of the 23 tests, pipeline hardened against the git apply bug, session resumption and HelloRetryRequest tested, documentation per file

**1. Impostor pair, single classical chain, strict vs. non-strict,
side by side.** The previous report compared the adversary (RSA key
only) against a strict AND server and against a common classical
server (without any `Dual`) -- useful for the interoperability
matrix, but not the exact pair requested. Two new tests added, with
the SAME client configuration (single classical chain, no `Dual`) in
both:

| Test | Server | Result |
|---|---|---|
| `TestDualImpostorSingleChainVsStrict` | Strict AND (`Dual.Require=true`) | **Rejected** |
| `TestDualImpostorSingleChainVsNonStrict` | Non-strict AND (`Dual.Require=false`) | **Accepted**, `DualAuthenticated=false` confirmed in the test (`cs.DualAuthenticated` checked explicitly, not just the absence of an error) |

The tests `TestDualStrictServerVsLegacyClient` and
`TestDualNonStrictAllowsDowngrade` (from the previous round) already
covered these same two result transitions, but under different
thematic names, without it being explicit that it is the SAME client
in both cases -- the two new tests make this comparison self-contained
and named for the exact pair requested.

**2. SKIPS, explained precisely.** The "0 SKIP" figure from the
previous report counted only the TOP-LEVEL tests (`^--- SKIP`, no
indentation) -- correct at that level, but incomplete: there are
2.278 real SKIPS, all internal SUBCELLS of ONE top-level test,
`TestBogoSuite` (BoringSSL's embedded conformance suite,
`bogo_shim_test.go`). Confirmed at line 658-659 of that file: each
subcell skips when the BoGo runner's OWN internal result is `"SKIP"`
(`result.Actual == "SKIP"` -> `t.SkipNow()`)
-- a decision made by BoGo itself about which test cases apply to
this specific build (for example, protocol features outside this
configuration's scope), never due to lack of network. `TestVerifyHostname`,
`TestRealResumption`, and the top-level `TestBogoSuite` (which
aggregates the subcells) all appear as **PASS**, not SKIP -- confirming
that the container DOES have real internet access (the Dockerfile's
own `apk add`/`git clone` already requires network, and they pass).
Exact command run, with no alteration whatsoever: `go test -count=1 -v ./...`, from
`/go-src/src/crypto/tls`, inside the container built by this folder's
`Dockerfile` -- no test excluded, no `-short` flag
or build tag restricting the set.

**3. Exact count, the 23 tests in `dual_test.go`, name by name,
reconciling "15 items" with "17 mandatory".** Correction of an
inaccuracy in the previous report: I said "17 mandatory + 1 contrast
test," which was wrong. Re-checking the original request point by
point, counting by semicolon (which is how the request itself was
written), there are exactly **15 top-level items**, not
17. The word "17" used earlier (by Luciano, when clearing T3, and by
me, when accepting the label without re-checking) does not match a
literal count of the semicolons -- and this is the reconciliation
requested:

Of the 15 items, **3 of them explicitly name TWO scenarios each**,
with the word "and" connecting the two within the same item (not two
items separated by a semicolon):
- item 6: "PQ chain from an untrusted CA, **on the server and on the
  client**"
- item 12: "QUANTUM ADVERSARY holding the RSA key... **and the same
  adversary against a single RSA chain**"
- item 14: "**round trip and malformed delimiters** of the Certificate
  message"

15 items + 3 extra scenarios (one per duplicated item) = **18 concrete
scenarios**, neither 15 nor 17 -- and T3's 18 tests cover these 18
scenarios exactly, one by one, table below. No leftover contrast test:
what the previous report called "1 contrast test"
(`TestSingleChainRSAAdversaryStillAuthenticates`) is in fact the
SECOND half explicitly requested by item 12, not an extra. If "17"
was meant to count only 2 of the 3 duplicated items as a pair (and
treat the third as a single combined test), the table below makes
clear which interpretation was actually implemented (all 3 as pairs,
18 in total) for Luciano to confirm or correct.

| # | Item from the original request | Test(s) |
|---|---|---|
| 1 | full strict mTLS | `TestDualStrictFullMTLS` |
| 2 | server only | `TestDualServerOnly` |
| 3 | strict client x legacy server (fails) | `TestDualStrictClientVsLegacyServer` |
| 4 | strict server x legacy client (fails) | `TestDualStrictServerVsLegacyClient` |
| 5 | client without PQ chain (fails) | `TestDualClientMissingPQChain` |
| 6 | PQ chain from an untrusted CA, on the server and on the client | `TestDualServerPQChainUntrustedByClient`, `TestDualClientPQChainUntrustedByServer` |
| 7 | untrusted classical chain | `TestDualClassicalChainUntrusted` |
| 8 | wrong hostname in the PQ chain | `TestDualWrongHostnameInPQChain` |
| 9 | divergent client identities | `TestDualClientDivergentIdentities` |
| 10 | second signature tampered | `TestDualTamperedSecondSignature` |
| 11 | first tampered | `TestDualTamperedFirstSignature` |
| 12 | quantum adversary (RSA only) vs. strict, AND the same adversary with a single chain vs. common classical | `TestDualQuantumAdversaryHoldingOnlyRSAKey`, `TestSingleChainRSAAdversaryStillAuthenticates` |
| 13 | non-strict accepts fallback (documented downgrade) | `TestDualNonStrictAllowsDowngrade` |
| 14 | Certificate message round trip, AND malformed delimiters | `TestDualCertificateMessageRoundTrip`, `TestDualCertificateMessageMalformedDelimiter` |
| 15 | size measurement | `TestDualWireSizeMeasurement` |

5 more from this round (items 1 and 5 of this request):

| Item from this request | Test(s) |
|---|---|
| 1: impostor, single chain, strict vs. non-strict | `TestDualImpostorSingleChainVsStrict`, `TestDualImpostorSingleChainVsNonStrict` |
| 5a: session resumption | `TestDualStrictModeDisablesSessionTickets`, `TestDualResumedSessionDoesNotCarryDualAuthentication` |
| 5b: HelloRetryRequest with the hybrid group | `TestDualHandshakeAcrossHelloRetryRequest` |

**Total: 23 test functions, all passing** (confirmed in the full suite
via the real pipeline, below). None of them is "a contrast test" in
the sense of being left over from the request -- the previous
report's phrasing was imprecise and is corrected here.

**4. Pipeline hardened against the `git apply` bug.** The patch
application step now counts how many files `and.patch` ITSELF touches
(`grep -c '^diff --git' /tmp/and.patch`, not a fixed number in the
Dockerfile -- stays correct if the patch changes) and compares it
against how many files `git status --porcelain` actually finds changed
in `src/crypto/tls` after `git apply`. A mismatch = explicit `exit 1`,
with a message naming the original bug. Validated in an isolated
diagnostic container, outside the real pipeline: deliberately
reintroducing the old invocation (`cd src && git apply
... && cd ..`, without `--directory`), the check now reports "and.patch
touches 9 files; git status reports 0 changed" and correctly
identifies the mismatch -- confirmed that this specific bug can no
longer pass silently.

**5. Patch gaps: tested or recorded.**

a) **Session resumption -- decided and tested, not left as an open
gap.** TLS 1.3 resumption skips Certificate/
CertificateVerify entirely, so a resumed connection would inherit the
dual authentication of the original connection WITHOUT re-verifying
either chain -- undermining exactly the guarantee that `Require=true`
exists to make absolute. Decision: strict connections NEVER issue a
session ticket (`shouldSendSessionTickets`, `handshake_server_tls13.go`) --
there is nothing to resume. Tested in `TestDualStrictModeDisablesSessionTickets`
(two consecutive connections with the same `ClientSessionCache`; the
second never resumes). Non-strict connections keep issuing tickets as
before, but a resumed connection NEVER reports `DualAuthenticated=true`
(this field is never restored from session state, unlike
`PeerCertificates`/`VerifiedChains`, which Go itself already restores
with no change of mine) -- tested directly in
`TestDualResumedSessionDoesNotCarryDualAuthentication` (confirms
`DidResume=true` AND `DualAuthenticated=false` on the same resumed
connection, not merely assumed).

b) **HelloRetryRequest with the hybrid group -- tested, passes.**
`TestDualHandshakeAcrossHelloRetryRequest` forces a real group
retry: `curvePreferences()` (`common.go`) always orders the allowed
groups in a fixed global order (hybrids before classical,
`curvePreferenceOrder()` in `defaults.go`), ignoring the order given in
`Config.CurvePreferences` -- so simply placing the hybrid group first
in the client's list does not force a retry (it would already be
first anyway). The real way to force it: client allows
`X25519MLKEM768` (ranked first in the fixed list, receives the initial
key share) AND `SecP384r1MLKEM1024` (declared only, no initial key
share); server only accepts `SecP384r1MLKEM1024`; the client's initial
key share is unusable, the server responds with a HelloRetryRequest
specifically requesting `SecP384r1MLKEM1024`, and the dual handshake
completes correctly after that -- confirmed (`cs.HelloRetryRequest`,
`cs.DualAuthenticated`, `cs.CurveID` all checked in the test).

c) **Recorded as a gap still open, with no code change**
(in `dual.go`'s header, updated): the client's
`VerifyConnection`/`VerifyPeerCertificate` callbacks still see only
the classical chain (`c.peerCertificates`), exactly as in stock Go,
and run BEFORE the PQ chain validation; no support for
`CompressedCertificate` (RFC 8879) or Exported Authenticators (RFC
9261); no `RelatedCertificate` (RFC 9440); the mechanism is TLS 1.3
only, with no explicit rejection of the dual code under TLS 1.2 (it
simply is never offered or accepted below 1.3, with the same
practical effect).

**6. Documentation: 543 lines vs. ~400 expected, per-file table,
the three fixes.**

The total rose from 529 to **543 lines outside `dual.go`/tests**
(the session-ticket guard from item 5a added 14 lines to
`handshake_server_tls13.go`). Luciano's decision to proceed as is
(Decision 6) remains valid -- the increase is for the same reason
(real security logic, not loose code).

| File | Lines | What it does |
|---|---:|---|
| `common.go` | +30 | `Dual *DualConfig` field in `Config`; `Dual.clone()` in `Config.Clone()`; 3 new fields in `ConnectionState` (`DualAuthenticated`, `DualPeerCertificates`, `DualVerifiedChains`) |
| `conn.go` | +10 | 3 internal fields in `Conn` (mirror the ones in `ConnectionState`); population in `connectionStateLocked` |
| `handshake_client.go` | +17 | Offer of the dual code `0xFE65` in the `ClientHello` (only it in strict mode); prohibition of `InsecureSkipVerify` with `Dual` configured |
| `handshake_client_tls13.go` | +172 | Client: independently validates the server's PQ chain; verifies the dual `CertificateVerify` (both signatures, no short-circuit); when asked for a certificate (mTLS), selects the classical certificate using a common classical algorithm list (not the strict server's dual-only list) and sends both certificates + dual signature when the server asks |
| `handshake_messages.go` | +157 | Serialization/parsing of the Certificate message with the 3 zero-byte delimiter; rejects a first, last, or repeated delimiter; behavior identical to the original parser when there is no delimiter |
| `handshake_server_tls13.go` | +152 | Server: chooses the dual certificate when the client offers the code and a PQ chain is configured; `Require` closes the handshake if the client does not offer it; `CertificateRequest` also offers the dual code for mTLS; verifies the client's pair (PQ chain + SAN identity) and the dual `CertificateVerify`; suppresses the session ticket in strict mode |
| `tls_test.go` | +5 | Registers the `Dual` field in `TestCloneNonFuncFields` (an existing test, not modified by this patch, but which requires every new `Config` field to be covered) |

**The three real bugs found during the implementation,
summarized:**
1. `git apply` resolves paths against the root of the cloned git
repository, not against the shell's current directory -- it reported
success while skipping every file. Fixed with `--directory=src/crypto/tls`;
hardened in item 4 above to never pass silently again.
2. `net.Pipe()` in the tests causes a transport deadlock whenever the
client aborts the read in the middle of the server's first flight (the
case for every negative test) -- replaced with `localPipe(t)` (real
TCP on loopback, the same mechanism the `crypto/tls` suite itself
already uses for full handshakes).
3. Go's own `getClientCertificate()`, unmodified, filters the client's
classical certificate by the same signature algorithm list the server
announced -- in strict mode that list is only
`0xFE65`, which does not match any real classical algorithm, causing
the client to send no certificate at all even though it has one
available. Fixed by using a common classical algorithm list solely for
certificate SELECTION, not for the signature scheme choice (which
remains the dual code).

**Result of this round, full `crypto/tls` suite (original +
the 23 AND tests), complete and hardened pipeline (clone -> verify
commit -> `git apply` with file-count check ->
`make.bash` -> test):** `ok crypto/tls 69.728s`. At the level of
NAMED tests: **237 PASS, 0 FAIL, 0 SKIP** (214 original + 23 AND).
Counting the internal subcells of `TestBogoSuite` as well: 2.991 PASS,
0 FAIL, 2.278 SKIP (all internal to that conformance matrix, detailed
in item 2). SHA-256 of this round's patch:
`093338402cce147920a4f63d2a2b8947f0fc8f275bae36f33a0dd8badeaad572`
-- **superseded by Decision 8** (the HelloRetryRequest test was
strengthened and fixed there, changing `dual_test.go` and hence the
patch's SHA-256; the final, valid numbers are in Decision 8).

Updated artifacts: `thesis/results/v9/toolchain/Dockerfile`,
`README.md`, `build_metadata.json`, `crypto_tls_test_summary.txt`,
`patches/and.patch`, `dual.go` (known-gaps header updated).

No action on AWS. No new tag.

## 8. Response to 3 points requested after the previous round's report: 15/17/18 reconciliation (see Decision 7, item 3, already corrected above), HelloRetryRequest with explicit initial and final groups, and recording the per-profile group restriction for T5/T6

**1. Count 15 vs. 17 vs. 18.** See the correction made directly in
Decision 7, item 3 (rewritten, not duplicated here): counting by
semicolon, the original request has 15 top-level items, of which 3
(items 6, 12, and 14) name TWO scenarios each within the same item,
totaling **18 concrete scenarios** -- not 15, nor 17.
T3's 18 tests cover these 18 scenarios one by one (table in Decision
7). If "17" intended to treat one of the three duplicated items as a
single combined test, I need Luciano to say which one -- as
implemented, all three were treated as pairs, giving 18.

**2. HelloRetryRequest -- explicit initial and final group.**
`TestDualHandshakeAcrossHelloRetryRequest` (`dual_test.go`) already
forced and verified the retry correctly in the previous round (the
test passed), but did not make the two groups visible in the test's
own log -- fixed. The test now names the two roles explicitly
(`initialShareGroup`, `retryTargetGroup`) and logs explicitly via
`t.Logf`:

- **First ClientHello**: key share sent for `X25519MLKEM768`
  (this group ranks first in `curvePreferenceOrder()`, so it receives
  the client's initial key share, even though it is listed after
  `SecP384r1MLKEM1024` in `Config.CurvePreferences`).
- **HelloRetryRequest**: the server (which only accepts `SecP384r1MLKEM1024`)
  cannot use that initial key share, and responds by specifically
  requesting `SecP384r1MLKEM1024` -- a group the client had already
  declared support for, just without an initial key share.
- **Final negotiated group**: `SecP384r1MLKEM1024`, confirmed via
  `ConnectionState.CurveID` on BOTH sides (client and server,
  `cs.CurveID`/`ss.CurveID`), not only one side -- and via
  `ConnectionState.HelloRetryRequest=true` on both sides as well,
  confirming that the retry actually happened (not a direct match by
  coincidence).

**Finding while strengthening the test, not a patch bug:** the first
strengthened version checked `DualAuthenticated` on BOTH sides, but
the original test only configured dual identity on the SERVER side
(without mTLS) -- and `ss.DualAuthenticated` (server) correctly came
out `false`, because the server never requested nor verified any
client certificate, dual or otherwise. It is not a bug:
`DualAuthenticated` describes whether THIS side verified the OTHER
side's pair, not a symmetric flag for the whole connection. Fixed by
elevating the test to full mutual mTLS (like
`TestDualStrictFullMTLS`), where both ends actually authenticate each
other -- only then should both sides report `true`, and they do.

Real result, full suite after this change: `ok crypto/tls`,
`TestDualHandshakeAcrossHelloRetryRequest` passes (mutual mTLS, group
retry included), real log from the run:
`first ClientHello key share: X25519MLKEM768; server's only accepted
group (HelloRetryRequest target): SecP384r1MLKEM1024; negotiated group
after retry: client=SecP384r1MLKEM1024 server=SecP384r1MLKEM1024`.

**3. Per-profile KEX group restriction, recorded for T5/T6
(not implemented now -- it concerns the real campaign code, outside
the scope of T3/the `crypto/tls` fork).** Confirmed in `curvePreferences()`
(`common.go`, Decision 7 item 5b): the order given in `Config.CurvePreferences`
is ignored; only which groups are ALLOWED matters, priority is
always `curvePreferenceOrder()`'s fixed global order. Direct
consequence for the real campaign (T5/T6, not for this patch's unit
tests): **each profile needs to restrict `CurvePreferences` to
EXACTLY one group**, with no extras, or the group actually negotiated
might not be the one the profile intends to measure:
- Classical: `CurveP384` only.
- PQC: `MLKEM1024` only.
- Hybrid and Hybrid-AND: `SecP384r1MLKEM1024` only.

This is already exactly what `mock_mtls/main.go` does today in v8
(confirmed in T1, Decision 1 of this folder: `serverCurvePreferences`
fixed to a single entry per profile, no multiple lists) -- the
requirement here is to NOT regress this in T5/T6 when integrating the
AND mechanism (never introduce `X25519MLKEM768` or any other extra
group into the REAL client/gateway configurations, even though an
isolated unit test, such as the HelloRetryRequest one above, needs an
extra group on purpose, solely to force the retry in the lab).

**Recorded as a mandatory T5/T6 requirement (pending implementation,
not of this Decision):** every measured run must read
`ConnectionState.CurveID` right after the handshake and **fail the run
explicitly** (not just log a warning) if the negotiated group is not
exactly the one expected for that profile -- the same "fail explicitly,
never pass silently" logic already applied to the pipeline's own
`git apply` (Decision 7, item 4), now extended to the KEX group of
every real measured connection.

**Finding while strengthening the HelloRetryRequest test with both
sides checked (not just the client): not a patch bug.** The first
strengthened version (item 2 above) checked `DualAuthenticated` on
both sides, but the original test only configured dual identity on
the SERVER, without mTLS -- `ss.DualAuthenticated` (server) correctly
came out `false`, because the server never requested nor verified any
client certificate. `DualAuthenticated` describes whether THIS side
verified the OTHER side's pair, not a symmetric flag for the whole
connection -- correct behavior, not a bug. Fixed by elevating the test
to full mutual mTLS (like `TestDualStrictFullMTLS`), where both ends
actually authenticate each other; only then do both sides report
`true`, confirmed.

**Final result of this round of adjustments, full `crypto/tls` suite
(original + the 23 AND tests), complete and hardened pipeline:**
`ok crypto/tls 58.248s`. At the level of NAMED tests:
**237 PASS, 0 FAIL, 0 SKIP** (214 original + 23 AND, including
`TestDualHandshakeAcrossHelloRetryRequest` now in mutual mTLS).
Counting the `TestBogoSuite` subcells as well: 2.991 PASS, 0 FAIL,
2.278 SKIP (same explanation as item 2). Final patch SHA-256:
`65f7ef4e50f5fd6025e9ab048cb4dd360a1455b3708702d648a93bd5c510cb2c`
(`dual.go` 321 lines, the 6 existing files 543 lines outside
`dual.go`/tests -- unchanged this time --, `dual_test.go` 903
lines/23 tests, `tls_test.go` +5).

Updated artifacts: `thesis/results/v9/toolchain/patches/and.patch`
(final SHA-256 above), `build_metadata.json`, `crypto_tls_test_summary.txt`,
`README.md`.

**Confirmed by Luciano: "15 items, 18 scenarios" is the correct and
final count.** "17" was his own imprecise count, now discarded --
use "15 items, 18 scenarios" in every future report and document about
T3, never "17" again.

No action on AWS. No new tag.

## 9. T4, new certificates: Classical and Hybrid-v8 at RSA-2048, Hybrid-AND with two independent chains (RSA-2048 + ML-DSA-65, same SAN identity), PQC reused from v8 unchanged -- all validated by Go's standard verifier, no InsecureSkipVerify

**Scope decision, not asked beforehand, recorded here for Luciano to
confirm or correct:** the original T4 request cites
`certs/main.go` (the REAL production certificate generator,
`mock-service-os/certs/main.go`, used by the already-published and
tagged v7/v8). I chose **NOT to touch that file** and instead build a
new, isolated generator at `thesis/results/v9/certs/` -- following the
same principle already applied to v9 as a whole ("additive, never
overwrites the official v8"): any edit to `certs/main.go` would risk
affecting, even by mistake, the RSA-4096 certificates that v8 already
measures and publishes. The real integration with the gateway/client
(deciding whether this new generator comes to live inside
`certs/main.go` or stays separate) is left for T5, which is explicitly
about integration. If Luciano wanted `certs/main.go` edited already, I
am flagging this before any wiring happens in T5.

**What was generated and where:**
`thesis/results/v9/certs/main.go` (a self-contained Go program, stdlib
only -- without `github.com/google/uuid`/`go-oidc`, which the real
generator uses only for JWKS/extra Subject fields, outside T4's scope)
generates and validates the 4 profiles, writing each certificate and
key to `thesis/results/v9/certs/certs/`:

| Profile | Chain(s) | Files |
|---|---|---|
| Classical | 1 RSA-2048 CA -> server leaf + client leaf, RSA-2048 | `classico_ca`, `classico_server`, `classico_client` |
| Hybrid-v8 | 1 RSA-2048 CA (primary) + 1 ML-DSA-65 CA (signs only the AltSignatureValue) -> RSA-2048 leaves with the 3 hybrid X.509 extensions (Bindel et al. 2019), same mechanism as v8, now RSA-2048 instead of RSA-4096 | `hibrido_v8_ca` (RSA), `hibrido_v8_ca_mldsa` (alt), `hibrido_v8_server`, `hibrido_v8_client` |
| Hybrid-AND | 2 FULLY independent chains: 1 RSA-2048 CA -> RSA-2048 leaves; 1 ML-DSA-65 CA (genuinely self-signed) -> ML-DSA-65 leaves. Same SAN identity in both, different end keys, no CA shared with Hybrid-v8 | `hibrido_and_rsa_ca/server/client`, `hibrido_and_mldsa_ca/server/client` |
| PQC | Reused from v8 **with no change at all** -- read-only copy (only the `.crt` files, no key) of `mock-service-os/certs/{root_ca_pqc,issuer_ca_pqc,mtls_pqc,client_one_pqc}.crt` into `thesis/results/v9/certs/v8_pqc/`, loaded and revalidated, never regenerated | (no new files; read-only copies in `v8_pqc/`) |

**SAN used**: server leaves carry `mtls` (the literal SNI that
`thesis/scripts/tls_kem_proxy` dials by default today) plus the same
hostname list that `mock-service-os/certs/main.go` already uses
(`auth.local`, `matls-auth.local`, `api.local`, `matls-api.local`,
`directory`, `directory.local`, `keystore`) and the IPs
`127.0.0.1`/`::1`; client leaves carry their own, stable identity,
`opin-client-one`, the same in both Hybrid-AND chains (the mechanism's
requirement).

**EKU**: every server certificate with `ExtKeyUsageServerAuth`, every
client certificate with `ExtKeyUsageClientAuth` -- confirmed by the
validation ITSELF below (which fails if the EKU does not match), not
just by what the template requests.

**Validation, every chain, with Go's `x509.Certificate.Verify()`,
with `InsecureSkipVerify` nowhere at all** (that flag belongs to
`crypto/tls`, at the connection level -- it does not even exist in an
isolated x509 call like this one, which by itself already rules out
the most common way for a validation to "pass" without really checking
anything):

```
=== Classico (RSA-2048) ===
OK   Classico/server: verified (root trusted, EKU=serverAuth, DNSName="mtls")
OK   Classico/client: verified (root trusted, EKU=clientAuth, DNSName="")

=== Hibrido-v8 (RSA-2048 + assinatura dupla X.509 ML-DSA-65) ===
OK   Hibrido-v8/server (RSA half): verified (EKU=serverAuth, DNSName="mtls")
OK   Hibrido-v8/client (RSA half): verified (EKU=clientAuth, DNSName="")
OK   Hibrido-v8/server: AltSignatureValue (ML-DSA-65 half) independently re-verified
OK   Hibrido-v8/client: AltSignatureValue (ML-DSA-65 half) independently re-verified

=== Hibrido-AND (duas cadeias independentes) ===
OK   Hibrido-AND/server (cadeia RSA): verified (EKU=serverAuth, DNSName="mtls")
OK   Hibrido-AND/client (cadeia RSA): verified (EKU=clientAuth, DNSName="")
OK   Hibrido-AND/server (cadeia ML-DSA-65): verified (EKU=serverAuth, DNSName="mtls")
OK   Hibrido-AND/client (cadeia ML-DSA-65): verified (EKU=clientAuth, DNSName="")
OK   Hibrido-AND/server: as duas cadeias declaram a MESMA identidade SAN
OK   Hibrido-AND/client: as duas cadeias declaram a MESMA identidade SAN

=== PQC (reaproveitado da v8, sem mudanca) ===
OK   PQC/server (v8, inalterado, EKU real=ClientAuth): verified (EKU=clientAuth)
OK   PQC/client (v8, inalterado): verified (EKU=clientAuth)
```

Full real output in `thesis/results/v9/certs/validation_report.txt`.

**Finding while validating the PQC profile, not a bug in this
generator: it independently reconfirms fact B from T1.** The first
attempt validated
`mtls_pqc.crt` (v8's real SERVER certificate) requiring
`EKU=ServerAuth`, and Go's own verifier refused it: "certificate
specifies an incompatible key usage". This is not a bug -- it is
exactly fact B already confirmed in T1 by reading the code
(`mock-service-os/certs/main.go` only generates `ExtKeyUsageClientAuth`,
on EVERY certificate, including server ones), now reconfirmed by Go's
own strict verifier, from an independent angle (not a code read, a
real validation). Fixed in the script: the validation
of `mtls_pqc.crt` uses `ClientAuth`, the REAL EKU the file has, not
what it "should" have -- T4 requires the correct ServerAuth for the
NEW certificates (Classical, Hybrid-v8, Hybrid-AND), not for the
PQC one, which intentionally stays as it is in v8, known limitation
included.

**Sizes (DER bytes, real data from this round):**

| Profile | Certificate | Bytes |
|---|---|---:|
| Classical | CA | 749 |
| Classical | server | 900 |
| Classical | client | 787 |
| Hybrid-v8 | CA (RSA) | 753 |
| Hybrid-v8 | CA (ML-DSA-65, alt) | 5.494 |
| Hybrid-v8 | server | 6.242 |
| Hybrid-v8 | client | 6.131 |
| Hybrid-AND | CA (RSA) | 763 |
| Hybrid-AND | CA (ML-DSA-65) | 5.496 |
| Hybrid-AND | server (RSA chain) | 914 |
| Hybrid-AND | client (RSA chain) | 801 |
| Hybrid-AND | server (ML-DSA-65 chain) | 5.647 |
| Hybrid-AND | client (ML-DSA-65 chain) | 5.534 |
| PQC (v8) | root | 5.867 |
| PQC (v8) | issuer | 5.877 |
| PQC (v8) | server | 5.867 |
| PQC (v8) | client | 5.879 |

**Total per profile** (sum of the chains listed, CA+server+client):
Classical 2.436 B; Hybrid-v8 18.620 B; Hybrid-AND 19.155 B; PQC (v8)
23.490 B.

**Note on the committed private keys.** `thesis/results/v9/certs/certs/*.key`
are private keys of test certificates, generated from scratch solely
for this local validation, with no real protection -- committed under
the SAME convention that `mock-service-os/certs/*.key` has already
followed since v1 (confirmed: `ca.key`, `client_one.key`, `client_one_pqc.key`, etc. are
already version-controlled in git). No official v8 key was touched; the
only v8 keys referenced here (PQC) were not copied, only the public
`.crt` files (with no key at all) in `v8_pqc/`, for validation, never
to sign anything.

Artifacts created: `thesis/results/v9/certs/{go.mod,main.go,Dockerfile,
validation_report.txt}`, `thesis/results/v9/certs/certs/` (26
files, 13 .crt/.key pairs), `thesis/results/v9/certs/v8_pqc/` (4
read-only copies, .crt only, from official v8).

No action on AWS. No new tag.

## 10. Response to the 5 points requested before T5: PQC reissued with the correct EKU, size comparability explained, per-handshake table, parameterizable SAN, confirmation on committed keys

**1. PQC reissued, no longer reused from v8.** The real certificate
`mtls_pqc.crt` is NO LONGER used as v9's PQC profile -- confirmed that
v9's client verifies the server in every profile, with no
`InsecureSkipVerify`, and Go would refuse that file (EKU=ClientAuth
only). Generated from scratch: `pqc_ca` (self-signed ML-DSA-65 CA) -> `pqc_server`
(EKU=ServerAuth) and `pqc_client` (EKU=ClientAuth), using the SAME
`generateMLDSACA`/`generateMLDSALeaf` functions already used for the
Hybrid-AND's ML-DSA-65 chain (the same template, not a separate copy).

**EKU confirmed, leaf by leaf, all profiles, no exception**
(real output from this round):

| Profile | Leaf | EKU |
|---|---|---|
| Classical | server | `serverAuth` |
| Classical | client | `clientAuth` |
| Hybrid-v8 | server | `serverAuth` |
| Hybrid-v8 | client | `clientAuth` |
| Hybrid-AND | server (RSA) | `serverAuth` |
| Hybrid-AND | client (RSA) | `clientAuth` |
| Hybrid-AND | server (ML-DSA-65) | `serverAuth` |
| Hybrid-AND | client (ML-DSA-65) | `clientAuth` |
| PQC (v9) | server | `serverAuth` |
| PQC (v9) | client | `clientAuth` |

All 10 leaves validated with `x509.Certificate.Verify()`, the required
EKU matching the expected one, `DNSName="mtls"` on the server ones
(a real hostname check, not an empty one).

**2. Size comparability, explained and fixed.** The original question
(why v8's PQC totals 23.490 B against ~16,7 KB for Hybrid-AND's
ML-DSA-65 side) was comparing chains of DIFFERENT formats:
real v8 has 2 CA levels (`root_ca_pqc` -> `issuer_ca_pqc` ->
leaf, 4 certificates) and 3 extra fields in each leaf's DN
(`organizationID`, `LDAP-UID`, `X500-UID`); Hybrid-AND (and now the
reissued PQC) has 1 level (CA signs the leaf directly, 3
certificates) and a DN with only `CommonName`. PQC reissued with the
SAME template as Hybrid-AND (request made, fulfilled) -- now the two
ML-DSA-65 chains are directly comparable, and the remaining difference
is minimal, just from variable-length ASN.1 encoding (serial number,
timestamps):

| | PQC (v9) | Hybrid-AND (ML-DSA-65) |
|---|---:|---:|
| CA | 5.468 B | 5.496 B |
| server | 5.619 B | 5.647 B |
| client | 5.506 B | 5.534 B |

**Recorded for the equivalence checklist (T8) and here:** v9's PQC
(16.593 B total) is structurally DIFFERENT from v8's real PQC
(23.490 B) -- not because of ML-DSA-65 (the public key and signature
have a FIXED size, identical in both), but because of 1 fewer CA
level and 3 fewer DN fields. This is a deliberate divergence of this
phase (T4, simplification for local comparability), not an error --
if v9's real campaign (T5/T8) needs the same 2-level format that v8
used (for example, to compare OPINsize per term directly with v8),
this needs to be decided explicitly before the official collection,
recorded here as pending.

**3. Per-handshake table -- what actually travels over the wire**
(leaf/leaves + intermediates, WITHOUT the root -- the root never
travels on the network, it only needs to be in each side's local trust
pool):

| Profile | Chain sent by the server | Bytes | Chain sent by the client | Bytes |
|---|---|---:|---|---:|
| Classical | leaf only | 900 | leaf only | 787 |
| Hybrid-v8 | 1 leaf (with the 3 hybrid X.509 extensions) | 6.242 | 1 leaf (same) | 6.131 |
| Hybrid-AND | RSA leaf + ML-DSA-65 leaf (both, by the mechanism) | 6.561 | RSA leaf + ML-DSA-65 leaf | 6.335 |
| PQC (v9) | leaf only | 5.619 | leaf only | 5.506 |

No profile in this round uses its own intermediate (all are 1
level); if a real profile comes to use 2 levels (as v8 did for
PQC), the intermediate adds to this same table as well -- the formula
is "every leaf between the final leaf and the root, root exclusive."

**4. SAN as a parameter, no longer fixed in the code.** `main.go` now
accepts `-server-dns`, `-server-ips`, `-client-dns` (comma-separated
lists) and `-out` (output directory); with no flag, it uses loopback
(`127.0.0.1`/`::1`) and the same local hostnames as always -- the same
default as before, now explicit and swappable, not hardcoded.

**How this fits into the deploy flow (recorded for T5/T8, not
implemented now):** in the pilot and in the real campaign, the
certificates must be issued AT DEPLOY TIME, after the infrastructure
(Terraform) knows the fleet's real addresses -- never before, never
version-controlled. Proposed flow: the deploy script (T5) resolves
the real IPs/hostnames of the newly created instances, calls this
generator (or whatever it evolves into) with `-server-ips=<real IPs>`
and `-server-dns=<real hostnames, if any>`, and the resulting
`.crt`/`.key` files stay ONLY on the instance's disk/in the session's
local scratch space -- never committed, for the same reason the
operator's IP, the ARN, and the account ID are never committed today
(a rule already in force since v8). T8 (equivalence checklist with
v8) must confirm that this flow was followed before any official
collection.

**5. Private keys -- Decision 9's commit happened; THIS round's was
blocked by the environment's own automatic security classifier, and I
accepted the block instead of forcing it.** Confirmed: yes, there was
a prior commit (hash `4f179778`, Decision 9) with 13 test `.crt`/`.key`
pairs. When attempting to commit this round (16 pairs, after the PQC
reissue), this environment's "Credential Leakage" classifier refused
the action twice, even with a commit message explaining the context.
Decision made: **I did not force the key commit**. Instead, I
restored the `.crt`/`.key` files for the profiles that had not changed
in substance (Classical, Hybrid-v8, Hybrid-AND -- only the random key
material had changed, from running the generator again, not the
structure) to what was already committed in Decision 9, and left the
3 NEW PQC keys (`pqc_ca.key`, `pqc_server.key`,
`pqc_client.key`) **out of the commit, only on this session's local
disk, not version-controlled**. The corresponding public `.crt` files
(with no key at all) went in normally.

**This reinforces, through a channel independent of my own judgment,
exactly the caution that point 5 was asking for:** a separate,
automatic classifier agreed that this is a sensitive enough pattern to
require explicit confirmation, not assumed. The "explicit permission"
I had documented earlier (the precedent of `mock-service-os/certs/
*.key` since v1) was not enough for the classifier this time
-- recorded here as a signal in favor of NOT version-controlling any
test key from here on in v9, not just in the real campaign, barring
an explicit decision to the contrary from Luciano. **For the real
campaign (T5/T8), no change: keys are NEVER generated before deploy
and NEVER committed** -- each instance generates/receives its own key
on the spot.

**Question for Luciano:** do the 3 new PQC keys stay local only
(as they are now), or does he want me to try committing them anyway
(he can adjust the Bash permission for that, outside this session)?
Until this is decided, the `pqc_*.key` keys exist only on this
session's disk, never committed.

Updated and COMMITTED artifacts: `thesis/results/v9/certs/main.go`
(PQC reissued, parameterizable SAN, new tables in the report),
`validation_report.txt`, DECISIONS.md, and the 3 new public PQC
`.crt` files (`pqc_ca.crt`, `pqc_server.crt`, `pqc_client.crt`). The
`.crt`/`.key` files of the other 3 profiles went back to Decision 9's
state (unchanged).
**NOT committed**: `pqc_ca.key`, `pqc_server.key`, `pqc_client.key`
(local only, see above).

No action on AWS. No new tag.

## 11. Response to the following round (private keys never version-controlled, generation at run time, non-comparability of PQC v9 vs v8 certificate size): removal of the local history of Decision 9's 13 keys, permanent .gitignore policy, Makefile for ephemeral generation, recorded for T8

**Luciano's decision, summarized:** never version-control a private
key in v9 (test or otherwise), never adjust the Bash permission to
work around the security classifier; answer before acting whether
Decision 9's commit passed through the scanner and whether the
`v9/fase1-local` branch was pushed to the remote; if it was not
pushed, remove the keys from that branch's LOCAL history (without
touching any tag or v8's history) and confirm with `git log` and
`git grep`; if it had been pushed, do not rewrite history, just stop
version-controlling keys from now on; from now on, `.gitignore` for
private `*.key`/`*.pem` in v9, only public `.crt` may be
version-controlled (and only if the scanner allows it), and local/T5
tests must generate the certificate at run time via the generator (a
Makefile or script target), never a pre-committed file; record in
DECISIONS.md and in the T8 checklist that v9's PQC chain (1-level CA,
DN with only CommonName) differs structurally from v8's real PQC
(2-level CA, 3 extra DN fields), so v9's certificate sizes are not
comparable to v8's, only among themselves.

**1. Did Decision 9's commit pass through the scanner before being
made?**
Yes. Commit `4f179778` (Decision 9, 13 test `.crt`/`.key` pairs)
was created after this environment's own secret scanner ran over the
diff and did not block it -- not because the content was safe (these
were real private keys, test ones, but real), but because at the time
of Decision 9 this round's rule ("a private key is never
version-controlled") had not yet been established. The classifier
that blocked was the one from THIS round's commit attempt (Decision
10, 16 pairs, after the PQC reissue) -- that one did refuse the
action twice, which was respected with no workaround (already
recorded in Decision 10, item 5). In other words: Decision 9 already
had a key committed before any block existed; the "never
version-control a key" rule is new as of this round, not retroactive
by itself -- hence the history removal below.

**2. Was the `v9/fase1-local` branch pushed to the remote?** No.
Confirmed by `git rev-parse --abbrev-ref --symbolic-full-name
v9/fase1-local@{upstream}` (no upstream configured) and by `git
ls-remote --heads origin v9/fase1-local` (empty output -- the branch
does not exist in `origin`). Since there is no shared history at
risk, removing the LOCAL history is safe: no collaborator or remote
clone can already have these keys.

**3. Local history removal, procedure and verification.**
A local safety branch was created (`backup-v9-before-key-removal`,
never pushed anywhere) before any rewrite, then deleted once the
verification below confirmed success. Executed:

```
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch <13 .key paths from Decision 9>' \
  -- 08e3118e..v9/fase1-local
```

This rewrote exactly the 2 commits in the range that carried a key
(commits before `08e3118e`, every tag, and v8/main's history were all
outside the range, hence untouched). Resulting new hashes:
`af144177` (was Decision 9) and `c9e071ed` (was Decision
10). `refs/original/refs/heads/v9/fase1-local` (`filter-branch`'s own
automatic backup) was removed after the verification. An attempt at
`git reflog expire --all --expire-unreachable=now` + `git
gc --prune=now` (to purge the now-unreachable objects from the local
database) was blocked by this environment's security classifier as
"irreversible local destruction" -- respected with no workaround, for
the same reason as Decision 10, item 5. The two verification criteria
that Luciano explicitly requested do not depend on that step and were
confirmed clean even without it:

```
git log --oneline -3 v9/fase1-local
  -> c9e071ed, af144177, 08e3118e (no commit with a key above these)

git grep -l "BEGIN.*PRIVATE KEY" v9/fase1-local -- "thesis/results/v9/*"
  -> (empty)

git log --all --oneline -- "thesis/results/v9/certs/certs/pqc_*.key"
  -> (empty, no commit on any branch/tag references these paths)
```

The old key blob objects may still exist loose in the local database
(unreachable by any ref) until a normal Git `gc` routine eventually
collects them -- this exposes nothing in a normal `git log`/`git grep`/
`git show <ref>`, which is exactly what was requested as the criterion,
and it does not affect anything that gets pushed to the remote (a
`push` never sends an unreachable object). Transparent record, not
hidden: if Luciano wants to force this final cleanup, it needs to be
done outside this session (a permission adjustment that he himself
decides to make, not me).

**4. `.gitignore` policy and generation at run time.**
Created:
- `thesis/results/v9/.gitignore` (`*.key`, `*.pem` -- applies to all
  of v9, any future subfolder, not just `certs/`).
- `thesis/results/v9/certs/certs/.gitignore` (`*.crt`, `*.key`,
  `*.pem` -- only affects NEW files; the 16 public `.crt` files
  already committed in Decision 9/10 remain tracked normally, as the
  historical record of T4's validation).
- `thesis/results/v9/certs/.gitignore` (`/generated/` -- see below).

Created `thesis/results/v9/certs/Makefile` with a `certs` target:
builds the generator's Docker image (the same `Dockerfile` from T4,
now with `ARG SERVER_DNS`/`SERVER_IPS`/`CLIENT_DNS` passed through as
flags to `main.go`), creates an ephemeral container, copies `/app/certs`
and `/report.txt` to the local `./generated/`, removes the container.
The `clean` target removes `./generated/`. Tested end to end twice
in this round:

- The first attempt used `OUT := certs` (the same name as the
  historical `certs/certs/` directory) -- real bug found: since this destination
  already existed, `docker cp` nested the new content one level deeper
  (`certs/certs/certs/`) instead of replacing it. The 16 historical
  `.crt` files were NOT overwritten (luck from `docker cp`'s merge
  semantics, not by design), but the result was confusing and fragile.
- Fixed: `OUT := generated` (its own name, never collides with the
  historical record) and a `rm -rf $(OUT)` before every `docker
  create`, guaranteeing the destination never pre-exists. Tested
  again: flat structure, `generated/validation_report.txt` and the 32
  files (16 profiles x `.crt`+`.key`) land exactly in `generated/`,
  with no nesting. `git status` confirms `generated/` is fully
  ignored (covered by `thesis/results/v9/certs/.gitignore`); `git diff
  --stat -- certs/certs` confirms T4's historical record with no
  alteration. `make clean` removes `generated/` entirely.

From now on: local tests and T5 use `make certs` (or the equivalent
`docker build`/`run`) to generate a disposable certificate and key on
every run -- never a fixed, version-controlled file. In the real
campaign (T5/T8), the same generator receives `-server-dns`/
`-server-ips` with the fleet's real addresses, resolved at deploy
time, never before -- the key never leaves the disk of the instance/
session that generated it.

**5. Size non-comparability: PQC v9 vs. v8's real PQC,
recorded for T8.** v9's PQC chain (generated by this folder's
`main.go`) uses a 1-level CA and a DN containing only `CommonName`.
v8's real PQC chain (`mtls_pqc.crt`/`client_one_pqc.crt`, used in the
official campaign) uses a 2-level CA (root + intermediate) and a DN
with 3 additional fields (Organization, Country, etc., see Decision
10, size-comparison section). The size difference between the two
(already quantified in Decision 10) comes entirely from this
structural template difference -- chain depth and DN fields -- not
from any cryptographic difference in ML-DSA-65 itself, which is
identical in both cases. **Recorded for T8's equivalence checklist:**
v9's certificate sizes are NOT comparable to v8's, profile by profile;
they are comparable only AMONG v9's own 4 profiles (Classical,
Hybrid-v8, Hybrid-AND, PQC), which share the same CA/DN template from
this generation. Any PQC-vs-classical size overhead comparison the
thesis presents must use v9's 4 profiles against each other, never v9
against v8 directly.

Artifacts from this round: `thesis/results/v9/.gitignore` (new),
`thesis/results/v9/certs/.gitignore` (new), `thesis/results/v9/certs/
certs/.gitignore` (new), `thesis/results/v9/certs/Makefile` (new),
`thesis/results/v9/certs/Dockerfile` (edited -- SAN `ARG`/flags),
DECISIONS.md (this section). No new key on disk at the end of this
round (the 3 PQC keys from Decision 10, which were never committed,
were removed from disk; any key used in a local test from now on is
generated and discarded by `make certs`/`make clean`).

No action on AWS. No new tag.

## 12. T5, integration: fork of the gateway/proxy inside v9 (without touching the production mock_mtls/tls_kem_proxy), 4 profiles run end to end in containers, single group and DualAuthenticated confirmed on both sides

**Cleanup requested before T5 (refs/original):** `git for-each-ref
refs/original` returned empty -- the only backup ref that Decision
11's `filter-branch` created
(`refs/original/refs/heads/v9/fase1-local`) had already been deleted
in that same previous round, right before the final verification.
Nothing to remove in this round; no classifier involved.

**T5 scope decision (asked of Luciano before writing any code):**
mock-service-os/mock_mtls/main.go and
thesis/scripts/tls_kem_proxy/main.go are the PRODUCTION files that
v7/v8's already-frozen data depend on. Editing these files directly
(removing InsecureSkipVerify, switching ClientAuth to
RequireAndVerifyClientCert on all profiles) would change the behavior
of code shared behind frozen results. Luciano chose: **fork inside
thesis/results/v9/, reusing the same architecture, without touching
the production files** -- and requested, for each copied file, the
v8 origin commit and a readable diff, for T8's equivalence checklist.

**Files created, with origin commit:**

- `thesis/results/v9/integration/gateway/main.go` + `hybridVerification.go`
  -- fork of `mock-service-os/mock_mtls/main.go` (commit
  `478bda51815d8bf60ebd23fb83f592270aa04377`) and
  `mock-service-os/mock_mtls/hybridVerification.go` (commit
  `7c722f6347b48a8d6a100b9197b7dc99f9146be5`).
- `thesis/results/v9/integration/proxy/main.go` -- fork of
  `thesis/scripts/tls_kem_proxy/main.go` (commit
  `a304d6980422e6a264d990302fd319b4862693ee`).

**Readable diff against the origin, gateway (mock_mtls):**

| What | Original | Fork (v9/integration/gateway) | Why |
|---|---|---|---|
| `ClientAuth` | `tls.VerifyClientCertIfGiven` (optional) on all profiles | `tls.RequireAndVerifyClientCert` on all profiles | Explicit T5 requirement |
| `InsecureSkipVerify` | `true` in `tlsConfiguration()` itself (server side verifies nothing beyond the basic handshake) | removed | Does not apply to this field on the server side the same way as on the client, but the field was removed because this fork never internally bridges TLS-over-TLS the way the original did for the matls-api.local call |
| Profiles | 3: classic, pqc, hybrid | 4: classico, pqc, hibrido-v8 (equivalent to the original "hybrid"), hibrido-and (new) | v9 scope |
| `GetConfigForClient`/`internalCallerConfig` (SNI carve-out for matls-api.local, for the Node reentrant call) | present | removed | This harness has no real auth/mockapi making that call; nothing for the carve-out to apply to |
| HTTP routing (reverse proxy to auth/api, SSA, token introspection, participants.json) | present, dependent on the real Node stack | removed, replaced by a single `/` handler that returns `{profile, curve, dualAuthenticated, tlsVersion, peerCertCount}` | Outside T5's scope (TLS, not OPIN business logic); the full 44-call flow is left for T8 |
| Cert/key loading | manual PEM decode + `x509.ParsePKCS8PrivateKey` | `tls.LoadX509KeyPair` | Simplification -- the same pattern `tls_kem_proxy` itself already uses on the client side, including for the ML-DSA-65 key |
| CA pool | manual loop decoding PEM blocks | `x509.CertPool.AppendCertsFromPEM` | Simplification, no behavior change |
| Per-connection metrics (`handshakeInfo`, `countingConn`, `connStateHandshakeLogger`) | present | removed | T6 measures; T5 only proves the connection closes successfully |
| `hybridVerifyPeerCertificateFunc` | no parameter, reads `CRYPTO_PROFILE` and a package constant (`issuerCaPqcFilePath`) | receives the ML-DSA-65 CA path as an argument | The harness already decides the profile in `main.go`; the cryptographic logic (`verifyHybridClientCert`, `reconstructPreTBS`) is identical, byte for byte |
| AND mechanism (Dual) | does not exist (predates the mechanism) | new hibrido-and profile: `tls.Config.Dual` with the two independent chains, `Require: true`, `SessionTicketsDisabled: true` | v9's own subject |

**Readable diff against the origin, proxy (tls_kem_proxy):**

| What | Original | Fork (v9/integration/proxy) | Why |
|---|---|---|---|
| `InsecureSkipVerify` | `true` | removed, `RootCAs` set per profile | Explicit T5 requirement: client verifies the server in all profiles |
| `ServerName` | fixed to `"mtls"` | kept, same logic/comment | No change |
| Relay mode (TLS-over-TLS tunnel to the Python `opin_flow.py`) | present (`-listen`, `-stub`) | removed -- this harness has no Python component to relay to | T5 tests only the Go side; reintegrating the local listener with the real `opin_flow.py` is left for T6/T8 |
| Request | raw bidirectional tunnel (`io.Copy`) | one real HTTP call (`http.Client` with `TLSClientConfig`) per run, against the gateway's `/` | Proves handshake + full request/response, not just the tunnel |
| Profiles/curves | 4 old names (secp384r1/mlkem1024/secp384r1mlkem1024/classic/classical/x25519mlkem768) | 4 v9 names (classico/pqc/hibrido-v8/hibrido-and), each with exactly 1 group | Aligned with v9's naming; `classical`/`x25519mlkem768` (historical v6/v7 carve-outs) do not apply here |
| Negotiated-group check | none (only logs) | compares `ConnectionState.CurveID` against the profile's expected group and fails explicitly (`log.Fatalf`) if it does not match | Explicit T5 requirement |
| `DualAuthenticated` check | does not exist | for hibrido-and, fails explicitly if `false` | Explicit T5 requirement |
| AND mechanism (Dual) | does not exist | new hibrido-and profile: `tls.Config.Dual` with the two independent chains, `Require: true` | v9's own subject |

**Execution, 4 profiles, end to end in containers (no AWS, no bind
mount -- certificates enter the images via `COPY`, copied before the
build by `run_t5.sh` from `../certs/generated/`, never
mounted):**

```
classico:    curve=CurveP384            status=200  dualAuthenticated=false (nao aplicavel)
pqc:         curve=MLKEM1024            status=200  dualAuthenticated=false (nao aplicavel)
hibrido-v8:  curve=SecP384r1MLKEM1024   status=200  dualAuthenticated=false (nao aplicavel; AND gate X.509 do client cert passou, log do gateway confirma)
hibrido-and: curve=SecP384r1MLKEM1024   status=200  dualAuthenticated=true  (confirmado nos DOIS lados: log do proxy E do gateway)
```

All 4 profiles negotiated exactly the configured group (checked and
enforced via `ConnectionState.CurveID` on both sides, not just
configured as a preference); no fallback, no silent downgrade.
Hybrid-AND confirmed `DualAuthenticated=true` on both the client and
the server, on the same connection -- the dual proof of possession
(RSA-PSS-SHA256 AND ML-DSA-65, neither optional) that v8 did not have.
Hybrid-v8 kept using only the X.509 gate (`AltSignatureValue`
extensions), without TLS Dual -- as decided, unaltered.
Session tickets explicitly disabled (`SessionTicketsDisabled:
true`) on both sides of hibrido-and, in addition to the automatic
suppression the AND patch already performs server-side when
`Dual.Require` is true (see Decision 6).

One recurring, harmless, and expected log line: `http: TLS
handshake error from ...: EOF`, once per profile -- it comes from
`run_t5.sh`'s own readiness probe (`nc -z mtls 443`, which opens and
closes the TCP connection without doing any TLS handshake), not from
the real measured connection that comes immediately after and always
succeeded.

**Outside this round's scope, recorded for T8:** the full flow of 44
HTTP calls / 6 mTLS connections / 28 JWTs / 4 /jwks / 4
CA fetches (same as v8's) was not reproduced here -- this harness
proves the TLS layer (handshake, mutual verification, single group,
AND gate), not the OPIN business logic (which depends on the real
Node stack: auth, mockapi, oidc-provider). T8's equivalence checklist
must separately confirm that the full business flow runs over this
same TLS mechanism before any official measurement (T6).

New artifacts: `thesis/results/v9/integration/{gateway,proxy}/*.go`,
`go.mod`, `Dockerfile`; `run_t5.sh`, `Makefile`, `.gitignore`.
No key, no certificate committed (generated and discarded on every
run via `make certs`/`make clean`, copied into the build context and
removed at the end of `run_t5.sh`). `mock-service-os/
mock_mtls` and `thesis/scripts/tls_kem_proxy` remain untouched.

No action on AWS. No new tag.

## 13. Two adjustments requested before T6: session tickets turned off on all FOUR profiles (not just Hybrid-AND), and an explanation of why the full flow (44 HTTP / 6 mTLS / 28 JWT / 4 jwks / 4 CA) did not run in T5

**1. TICKETS, on all four profiles.** `gateway/main.go` and
`proxy/main.go` gained an explicit `ticketsDisabled` parameter
(`TICKETS_DISABLED` on the gateway, `-tickets-disabled` on the proxy,
default `true` on both) that sets
`tls.Config.SessionTicketsDisabled` -- previously set only on
Hybrid-AND's `Dual`, now on EVERY `tls.Config` that
`buildServerTLSConfig`/`buildClientTLSConfig` produce.

**What v8 (and v7, same code) actually did -- confirmed, not
assumed:** `grep -rn SessionTicket mock-service-os/mock_mtls/*.go
thesis/scripts/tls_kem_proxy/*.go` returns no occurrence at all --
no v7/v8 `tls.Config` ever sets `SessionTicketsDisabled`,
so tickets remain ON (Go's zero-value default) in ALL three
v8 profiles, always. And the ticket bytes DID enter the gateway's
counter: `thesis/results/v8/DECISIONS.md`, Decision 78, had already
tracked this byte for byte via a real capture (tcpdump) of a real
Hybrid connection -- `mtlsHandshakeBytes` contained the `ClientHello`
+ the server's complete flight + **2.162 B consistent with a
`NewSessionTicket`** + the client's flight + the start of the first
HTTP request, all summed because `connStateHandshakeLogger` reads the
cumulative counter at `ConnState -> StateActive`, which only fires
after ALL of that traffic has already passed through the connection.
Decision 79 (same file) records that Luciano decided **NOT to fix**
this measurement limit in v8, to preserve comparability with v7
(which has carried the same artifact forever, same code). In other
words: v7/v8's historical `mtlsHandshakeBytes` figures include the
ticket(s) plus a piece of the first request -- a number deliberately
left "dirty" for historical comparability, not an unknown bug.

**Why v9 diverges from this, deliberately, recorded here for T8's
equivalence checklist:** v9 is not trying to reproduce v7/v8's
historical figures byte for byte -- it is comparing Hybrid-AND
against v9's own other 3 profiles. If tickets stayed on in 3 profiles
and never in Hybrid-AND (the only profile whose own protocol logic
structurally prevents them, see T6 below), the comparison would be
biased in Hybrid-AND's favor for a reason that has nothing to do with
the AND mechanism itself. Turning them off in all four levels the
field. **Explicit v9 divergence from v7/v8:** v9 measures the
handshake WITHOUT tickets by default; v7/v8 always measured WITH
tickets (and with the ticket partially contaminating the counter).
The two figures are not directly comparable to each other for this
additional reason (added to the certificate non-comparability already
recorded in Decision 11) -- only among v9's 4 profiles, among
themselves.

**Quantification of the effect, requested for T6 (diagnostic mode,
tickets turned back on solely to measure):** done, see Decision 14
below -- it includes a new, unforeseen structural finding: Hybrid-AND
NEVER emits a ticket, regardless of this parameter, for a different
reason (a design decision from T3 itself, not from this adjustment).

**2. FULL LOCAL FLOW -- why it did not run in T5, what is missing, how
v8 runs it, feasibility.**

**Why T5 did not run the full flow:** T5 was designed and approved
(Decision 12) with a deliberately restricted scope -- prove that the
TLS MECHANISM (handshake, mutual verification, single group, the AND
gate) works across the 4 profiles, without rebuilding the OPIN
business logic. The T5/T6 harness
(`thesis/results/v9/integration/{gateway,proxy}`) is a deliberately
reduced fork: the gateway's HTTP handler is a single fixed endpoint
that returns `{profile, curve, dualAuthenticated,
tlsVersion}` -- there is no reverse proxy to auth/api, no SSA
signing, no token introspection, no `/jwks`/`/root-ca.pem`/
`/issuer-ca.pem` serving real content, and the proxy makes ONE manual
HTTP call per run, not a persistent tunnel that the real
`opin_flow.py` could use.

**How v8 actually runs the full flow (`mock-service-os/
docker-compose.yml` + `insurance-server-lambdas/docker-compose.yml`),
service by service:**
- `mtls` (the real gateway, `mock_mtls`) -- reverse proxy to auth/api,
  serves `/root-ca.pem`/`/issuer-ca.pem`/`/jwks`, signs the SSA.
  Exposes
  `matls-auth.local`/`auth.local`/`api.local`/`matls-api.local`/
  `directory` as network aliases.
- `auth` (`mock_as`, Node.js, oidc-provider) -- issues the JWTs, makes
  the reentrant `InsurerAdapter.getConsent()` call back to the
  gateway via SNI `matls-api.local`.
- `mongo1`/`mongo_seed` -- oidc-provider state (sessions,
  clients, grants).
- `localstack` -- emulates SSM Parameter Store and S3 LOCALLY (a
  local Docker container, never touches real AWS -- without
  violating the "no AWS" rule), serves the SSA's private key
  (`SSA_JWK_URL`) and the config parameters that `auth`/`mtls` read
  at boot.
- `insurance-server-lambdas` (a separate stack, `API_GATEWAY_URI`) --
  the RS/insurer-side API that the gateway proxies via
  `api.local`/`matls-api.local`.
- `thesis/scripts/opin_flow.py` + `thesis/scripts/tls_kem_proxy` (relay
  mode, not stub) -- the real client: `tls_kem_proxy` terminates a
  local TLS connection (throwaway, self-signed) on one side and opens
  ONE real mTLS connection per connection on the other, relaying raw
  bytes -- this is what lets Python talk to a gateway that requires
  ML-KEM groups that Python's OpenSSL cannot negotiate.

**What is concretely missing to run v9's 4 profiles (including
Hybrid-AND) end to end locally, with the same counts (44/6/
28/4/4):**
1. Restore to the gateway fork (`thesis/results/v9/integration/
   gateway`) the business layer T5 removed for scope reasons: reverse
   proxy to auth/api, SSA signing (needs the `jwx` dependency back),
   `/jwks`/`/root-ca.pem`/`/issuer-ca.pem`,
   token introspection -- OR point these handlers at the real
   `mock_as`/`insurance-server-lambdas` (neither needs a change, they
   are agnostic to the TLS profile).
2. Extend the proxy fork with a persistent RELAY MODE (like the real
   `tls_kem_proxy` has, which T5 removed for scope reasons -- see
   Decision 12), including the 4th profile (hibrido-and) that the
   real `tls_kem_proxy` does not have.
3. Bring up `auth`/`mongo1`/`mongo_seed`/`localstack`/
   `insurance-server-lambdas` alongside it (no change to any of them --
   they are agnostic to the TLS mechanism, they only speak plain HTTP
   to the gateway).
4. Point `opin_flow.py` at this gateway/proxy instead of the real ones
   (there is precedent: the `REMOTE_GATEWAY_HOST` flag designed in
   v8's AWS experiment plan solves exactly this kind of redirection,
   reusable here).
5. Confirm the counts (44 HTTP / 6 mTLS / 28 JWT / 4 jwks / 4 CA)
   via the SAME instrumentation T6 has already built (Decision 14),
   now measuring the full flow, not an isolated connection.

**Feasibility: YES, no fundamental technical obstacle found.**
None of the missing components depends on an external network, real
AWS, or anything that does not exist in this repository today -- it
is integration engineering (items 1-4 above), not research or new
design. Outside the already approved scope of T5 (Decision 12) and
this instrumentation round (T6); recorded here as a **mandatory T7
criterion**, as requested, before any AWS pilot.

Same rules: no action on AWS, no commit before the scanner, report in
chat.

## 14. T6, instrumentation: decrypted keylog+pcap cross-checked against in-process counting at the exact Handshake() boundary, CPU microbenchmarks, tickets quantified (structural finding: Hybrid-AND in STRICT MODE never emits a ticket -- non-strict mode not tested, would emit normally), initcwnd/RTT analysis for distant routes

**Architecture, to avoid a bind mount (does not work in this
environment -- Decision 11):** `thesis/results/v9/integration/measure/`
builds ONE container that holds the gateway, proxy, tcpdump, AND
tshark together; the gateway and proxy talk over loopback (127.0.0.1)
INSIDE this same container, writing the TLS keylog to the same local
filesystem that tshark later reads -- no file crosses a container
boundary, no bind mount anywhere. `measure.sh` orchestrates: tcpdump
in the background -> gateway in the background -> proxy in the
foreground (one connection) -> stop the capture -> decrypt with
tshark using the keylog -> print everything.
`thesis/results/v9/integration/bench/` is a separate container, no
network, CPU only.

**Byte count at the exact `Handshake()` boundary:** `gateway/
main.go` and `proxy/main.go` abandoned T5's `http.Server`/`http.Client`
(which hide the `Handshake()` call inside `net/http` itself) in favor
of an explicit `Accept()`/`tls.Server()`/`tls.Client()` loop: a
`countingConn` wrapper under `tls.Conn` takes a snapshot of the
counters immediately before and after the `Handshake()` call, and a
second window ("post-handshake") covers exactly what is written/read
between `Handshake()`'s return and the manual HTTP response this
harness writes by hand (never `net/http` -- see the
`serveOneResponse` comment). For v9, this replaces the heuristic
estimate of 4.945/22.373/18.783 that Luciano identified as not
reproducible from the repository's code -- the numbers below ARE
reproducible, by running `bash thesis/results/v9/integration/run_t6.sh`.

**Cross-validation, confirmed across the 4 profiles:** the number the
process counts (`handshakeBytesIn`/`handshakeBytesOut`) matches, byte
for byte, the sum of the TLS records that tshark decrypts via the
keylog (for example, Classical: ClientHello 341B + server flight
(ServerHello+EncryptedExtensions+CertificateRequest+Certificate+
CertificateVerify+Finished) 1.640B + client flight
(Certificate+CertificateVerify+Finished) 1.172B = exactly the
`handshakeBytesOut=1640`/`handshakeBytesIn=1513` -- `341+1172=1513` --
that the gateway recorded). The raw byte sum of the entire pcap
(independent of decryption) also matches the handshake + post-handshake
window summed, across the 4 profiles. Three independent sources
(in-process counter, decrypted tshark, raw pcap sum)
agree exactly -- no estimate, three measurements.

**Result per profile, normal mode (tickets off, N=1 run
each -- proof of instrumentation, not yet a statistical campaign;
repetition with a larger N is pilot/T7 work):**

| Profile | Negotiated group | DualAuthenticated | Server flight (B) | Client flight (B) | Post-handshake in/out (B) |
|---|---|---|---|---|---|
| Classical | CurveP384 | false (n/a) | 1.640 | 1.513 | 71 / 203 |
| PQC | MLKEM1024 | false (n/a) | 10.878 | 10.728 | 71 / 198 |
| Hybrid-v8 | SecP384r1MLKEM1024 | false (n/a; client cert X.509 gate passed) | 8.552 | 8.397 | 71 / 215 |
| Hybrid-AND | SecP384r1MLKEM1024 | **true**, confirmed on both sides | 12.177 | 11.902 | 71 / 215 |

All 4: negotiated group matches exactly what was expected, `status=200`
on the single HTTP request, no failure.

**Tickets, diagnostic mode (turned back on solely to measure;
technical finding along the way -- recorded because it changed the
test's design):** the first attempt, with `SessionTicketsDisabled=false`
on both sides, measured a ZERO delta on every profile -- a bug in the
instrumentation ITSELF, not in the mechanism: this toolchain's
`handshake_client.go` (line ~376) only has the client announce
`psk_key_exchange_modes` (the signal the server's
`shouldSendSessionTickets()` requires, RFC 8446 4.2.9) when
`Config.ClientSessionCache` is NOT nil -- the harness never set that.
Fixed (`proxy/main.go`, `buildClientTLSConfig`): when
`ticketsDisabled=false`, it sets `ClientSessionCache =
tls.NewLRUClientSessionCache(4)`. After the fix:

| Profile | Server flight WITHOUT ticket (B) | Server flight WITH ticket (B) | Ticket overhead (B) |
|---|---|---|---|
| Classical | 1.640 | 3.331 | **1.691** |
| PQC | 10.878 | 22.007 | **11.129** |
| Hybrid-v8 | 8.552 | 15.591 | **7.039** |
| Hybrid-AND | 12.177 | 12.177 | **0** |

Confirmed symmetrically on the client side: the SAME number of bytes
shows up in the proxy's post-handshake window (e.g., Classical
203->1.894, delta 1.691) instead of in the handshake window -- because
the CLIENT's `Handshake()` returns before opportunistically reading
the `NewSessionTicket` the server has already written (confirmed by
reading `handshake_server_tls13.go`: the server sends the ticket
SYNCHRONOUSLY, inside its own `Handshake()`, right after processing
the client's `Certificate`/`CertificateVerify` -- but the client does
not need to finish READING that ticket to consider its own handshake
complete). In other words: the same ticket can land on one side or
the other of the boundary depending on WHO measures and WHEN --
exactly why the original request (measuring both windows, on both
sides) was not redundant.

**Structural finding, CORRECTED after Luciano's review -- the
original wording ("never emits a ticket, under any mode") was
imprecise and contradicted what T3 itself had already documented
(non-strict mode emits a ticket normally). Reconciled here, by reading
the code again instead of trusting memory:** the ticket suppression
in `dual.go`'s
`shouldSendSessionTickets()` is gated ONLY by `Dual.Require`:

```go
if hs.c.config.Dual != nil && hs.c.config.Dual.Require {
    return false
}
```

In other words: with **`Dual.Require = true` (strict mode)**, no
ticket is ever emitted -- confirmed, this part of the original
wording was
correct. With **`Dual.Require = false` (non-strict mode)**, that `if`
is never entered, and the ticket is emitted normally, subject to the
same RFC 8446 gate as the other 3 profiles
(`ClientSessionCache`/`pskModeDHE`) --
exactly as T3 had already recorded ("non-strict connections keep
issuing tickets as before", `dual.go`/Decision 6 comment). **"Under
any mode" was wrong** -- it should have been "in strict mode." The
T5/T6 harness only tests `Dual.Require = true` for Hybrid-AND
(and the mechanism's specification requires this -- Decision 5,
strict mode is the only one that makes sense for v9 to prove the dual
proof-of-possession guarantee), which is why the two tests (normal and
diagnostic) gave the same result:
it is not that non-strict mode is also immune, it is that it was
never exercised here.

**Correction of the conclusion:** Hybrid-AND is immune to the
inflation artifact **specifically in strict mode**
(`Dual.Require=true`), the only mode v9 uses and measures -- the
reason is the same: resuming a session via PSK would skip the ENTIRE
Certificate/
CertificateVerify exchange that proves possession of both keys, which
would void the mechanism's central guarantee, so the patch turns off
the ticket unconditionally in this mode. In non-strict mode (not used
by v9), Hybrid-AND would behave like the other 3 profiles: vulnerable
to the same artifact if an operator turned tickets back on. v9's other
3 profiles (and v7/v8's 3) remain vulnerable to the artifact
regardless of mode, because they have no notion of `Dual` at all.
This also explains why the ticket's
size scales with the profile (1.691B Classical -> 7.039B Hybrid-v8 ->
11.129B PQC): Go's ticket embeds the verified PEER's certificate
chain, so that a resumed session still has
`ConnectionState.PeerCertificates` populated without needing to
re-send the certificates -- so a client with a large certificate
(PQC, Hybrid-v8) produces a large ticket, in the same proportion.

**Gateway per-stage timings, additional finding about the limit of
the measurement boundary (transparency, does not invalidate the table
above):**
`gateway/main.go` gained `requestDurationUs` (time only for the step
of serving the HTTP response, separate from `handshakeDurationUs`).
While measuring this, a second form of the SAME type of artifact that
v8's Decision 78 had already documented (bytes from a following stage
entering the previous stage's count) showed up -- just at a different
layer: with the client sending its HTTP request with NO delay right
after its own `Handshake()` returns, the server's `Read()` that
consumes the handshake's last message (the client's `Finished`)
occasionally already finds, in the socket buffer, the HTTP request
bytes that arrived stuck right behind it (loopback, near-zero
latency) -- and counts them as "handshake" (`handshakeBytesIn` rose
from 1.513 to 1.584 in that round, exactly the 71 B of the request
that "leaked" to the inside of the boundary; `postHandshakeBytesIn`
correspondingly dropped to 0). **This does NOT invalidate the table
published above** -- that round was obtained with a 100ms pause
before sending (originally introduced for the ticket diagnostic,
still active when that table was generated) and confirmed TRIPLY
(process counter = decrypted tshark = raw pcap sum, the three
agreeing exactly) -- but it confirms that the measurement boundary,
even at the `Handshake()` level, is not immune to this effect when
the peer sends data immediately, with no pause at all. **Recorded
for T7:** the real campaign must keep cross-checking the process
counter against pcap/tshark per run (already part of this pipeline),
not rely on the counter alone when the real latency between handshake
and first request is very low (e.g., the 0ms scenario).

Times measured, same round (normal mode, without the diagnostic
pause, hence without the ticket bias): `requestDurationUs` --
Classical 30us, PQC 63us, Hybrid-v8 43us, Hybrid-AND 115us (the step
of serving ONE minimal HTTP response, not yet comparable to v7/v8's
real `opin_processing_ms`, which serves larger JSON payloads --
Hybrid-AND is expected to tend to be the slowest here too in the real
campaign, for having two chains to consider in the ConnState checks,
not because of this specific number).

**CPU microbenchmarks per operation (4 primitives, N=2000 each,
except RSA/ML-DSA-65 keygen N=100 since they are much slower;
`thesis/results/v9/integration/bench`, keys generated on the spot,
same type/parameter as the real profiles -- the specific key does
not affect CPU cost):**

| Operation | ns/op | ops/s |
|---|---|---|
| RSA-2048 keygen | 61.518.062 | 16 |
| RSA-2048 sign (PSS-SHA256) | 830.087 | 1.205 |
| RSA-2048 verify (PSS-SHA256) | 27.887 | 35.859 |
| ML-DSA-65 keygen | 270.874 | 3.692 |
| ML-DSA-65 sign | 537.322 | 1.861 |
| ML-DSA-65 verify | 152.369 | 6.563 |
| ECDH P-384 keygen | 112.387 | 8.898 |
| ECDH P-384 compute (KEX) | 550.225 | 1.817 |
| ML-KEM-1024 keygen | 112.890 | 8.858 |
| ML-KEM-1024 encapsulate | 77.896 | 12.838 |
| ML-KEM-1024 decapsulate | 126.740 | 7.890 |

KEX cost per profile, summing the operations the handshake actually
executes: Classical = 1x keygen + 1x ECDH P-384 compute (~663 us);
PQC = 1x keygen + 1x encapsulate + 1x decapsulate ML-KEM-1024 (~317
us); Hybrid/Hybrid-AND = sum of the two lines above, since the hybrid
group's combiner concatenates the two secrets (~980 us).
Signature/verification cost per profile: Classical uses RSA-2048 (1
sign + 1 verify on the certificate pair = ~858 us); PQC/Hybrid-AND
(ML-DSA-65 chain) use ML-DSA-65 (1 sign + 1 verify = ~690 us, FASTER
than RSA-2048 despite the larger certificate); Hybrid-v8 sums RSA
(main signature) + ML-DSA-65 (alt X.509 signature, verified only
during chain validation, not as a network operation). Hybrid-AND pays
the full RSA cost AND the full ML-DSA-65 cost, structurally IN
PARALLEL (two independent chains) -- CPU cost is the sum of both, not
hybridized.

**initcwnd / extra-RTT analysis for distant routes (desk calculation,
local Phase 1 -- there is no real AWS route yet to measure; uses the
REAL sizes measured above, not T4's certificate table):**
formula: `extra RTTs = max(0, ceil(flight_bytes / cwnd_bytes) - 1)`,
`cwnd_bytes = initcwnd_segments x MSS`, MSS=1460B (standard Ethernet).

| Profile | Server flight (B) | initcwnd=10 (14.600B, current Linux default) | initcwnd=3 (4.380B, legacy pre-2011) |
|---|---|---|---|
| Classical | 1.640 | 0 extra RTT | 0 extra RTT |
| PQC | 10.878 | 0 extra RTT | **2 extra RTTs** |
| Hybrid-v8 | 8.552 | 0 extra RTT | **1 extra RTT** |
| Hybrid-AND | 12.177 | 0 extra RTT | **2 extra RTTs** |

**Conclusion:** with the `initcwnd=10` that is the default on any
reasonably current Linux kernel (since 2011, RFC 6928) -- what is
expected of any modern EC2 instance --, NONE of the 4 profiles needs
an extra RTT due to an initial-congestion-window limit, at ANY of the
latency tiers already used in this thesis (14/30/140/225/320ms) --
Hybrid-AND's extra cost (almost 2x Hybrid-v8, for carrying two
complete chains) still fits inside the first flight at any RTT. Only
under a legacy `initcwnd` (3 segments, pre-2011) would PQC and
Hybrid-AND pay extra RTTs -- **recorded for T7: empirically confirm
the pilot EC2 instances' real `initcwnd` before assuming 0 extra
RTTs**, not decided here for lack of a real route to measure. This
analysis does not cover packet loss/retransmission (a phenomenon
dependent on a real route, not reproducible on local loopback).

**Artifacts:** `thesis/results/v9/integration/gateway/main.go` and
`proxy/main.go` rewritten (counting at the `Handshake()` boundary,
keylog, parameterized tickets); `measure/{Dockerfile,measure.sh,
.gitignore-covered certs}`; `bench/{main.go,go.mod,Dockerfile}`;
`run_t6.sh` (replaces `run_t5.sh` as the reference script --
`run_t5.sh` keeps working, kept for compatibility, but
`run_t6.sh` is what now proves both the integration and the
instrumentation). No key, no certificate, no pcap or
keylog committed -- everything generated and discarded on every run
(`t6_out/` and `measure/certs/` gitignored).

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 15. Clarifications requested after T6: per-TLS-message table (4 profiles), per-stage timings, implication of initcwnd for v8's residue

**Point 1 (tickets)** reconciled directly in Decision 14 above
(corrected text, not a new section): the immunity is only in strict
mode (`Dual.Require=true`), the only one v9 uses.

**Point 2: size per TLS message, per profile, per direction,
measured in the same round (normal, tickets off).**
`measure.sh` gained a second tshark query
(`-Y tls.handshake -e tls.handshake.type -e tls.handshake.length`),
decrypted by the same keylog -- size of each message = 4 handshake
header bytes + the declared length (`tls.handshake.length`).
Confirmed against the isolated ClientHello (the only number with no
grouping ambiguity): Classical 332+4=336, real frame 341 (336 +
5B of TLS record header -- a single record, no CCS, no AEAD tag,
because the ClientHello is never encrypted). The rest arrive already
encrypted; the number below is the size of the MESSAGE inside the
record, not the entire encrypted record.

| Message | Classical | PQC | Hybrid-v8 | Hybrid-AND |
|---|---|---|---|---|
| ClientHello | 336 | 1.779 | 1.876 | 1.858 |
| ServerHello | 187 | 1.658 | 1.755 | 1.755 |
| EncryptedExtensions | 10 | 10 | 10 | 10 |
| CertificateRequest | 109 | 104 | 111 | 98 |
| Certificate (server) | 913 | 5.632 | 6.255 | 6.582 |
| CertificateVerify (server) | 264 | 3.317 | 264 | 3.575 |
| Finished (server) | 36 | 36 | 36 | 36 |
| Certificate (client) | 800 | 5.519 | 6.144 | 6.356 |
| CertificateVerify (client) | 264 | 3.317 | 264 | 3.575 |
| Finished (client) | 36 | 36 | 36 | 36 |
| **Sum, client->server direction** (client's CH+Cert+CV+Fin) | 1.436 | 10.651 | 8.320 | 11.825 |
| **Sum, server->client direction** (server's SH+EE+CR+Cert+CV+Fin) | 1.519 | 10.757 | 8.431 | 12.056 |
| **Total measured at the Handshake() boundary, already excluding the 1st HTTP request -- client->server** | **1.513** | **10.728** | **8.397** | **11.902** |
| **Total measured at the Handshake() boundary, already excluding the 1st HTTP request -- server->client** | **1.640** | **10.878** | **8.552** | **12.177** |
| Record-layer overhead (measured - sum of messages) | 77 / 121 | 77 / 121 | 77 / 121 | 77 / 121 |

The record-layer overhead (5B TLS 1.3 record headers + inner type
byte + 16B AEAD tag per encrypted record, plus the compatibility
ChangeCipherSpec record) comes out to **exactly
77B in the client->server direction and 121B in the server->client
direction, across the 4 profiles, with no exception** -- this makes
sense: the NUMBER of messages per flight is identical across the 4
profiles (always 1 ClientHello; always the server's
SH+EE+CR+Cert+CV+Fin; always the client's Cert+CV+Fin), only the
CONTENT varies, and the record overhead depends on how many records
there are, not on each one's size. This consistency is itself an
additional confirmation (a fourth one, besides the three already
reported in Decision 14) that the measurement is correct equally
across the 4 profiles, not just by coincidence in one of them.

**Point 3: gateway timings per stage, per profile (same round,
normal mode, without the diagnostic-pause bias).**

| Profile | `handshakeDurationUs` | `requestDurationUs` |
|---|---|---|
| Classical | 4.752 | 30 |
| PQC | 2.813 | 63 |
| Hybrid-v8 | 5.402 | 43 |
| Hybrid-AND | 8.734 | 115 |

N=1 per profile -- proof that the instrumentation measures the right
stage (handshake isolated from the request, no contamination from the
ticket diagnostic pause, see Decision 14), not yet a statistical
campaign (that is a larger N, pilot/T7 work). Hybrid-AND is slower
than the other 3 both in the handshake (more bytes to generate/
verify: two complete chains) and in the response-serving step (more
`ConnState` work considering two certificate sets) -- expected
direction, exact magnitude only with more samples.

**Point 4: what initcwnd=10 implies for v8's unattributed residue
(handshake time above expectations that the thesis had not yet
explained), and which component measured by T6 can explain it.**

With `initcwnd=10` covering the entire flight of any of the 4
profiles in ONE window (Decision 14), the hypothesis that the residue
came from an extra RTT due to a congestion-window overflow is
**ruled out for the latency tiers already used in this thesis
(14-320ms)** -- no flight, not even Hybrid-AND's (12.177B), comes
close to the 14.600B limit. This shifts the explanation to two
components that T6 now measures for the first time, separately, and
that v7/v8 never isolated:

1. **Cost of generating/transmitting the session ticket.** v7/v8
   always ran with tickets ON (Decision 13) -- every handshake paid
   the cost of ENCRYPTING and sending a ticket that embeds the peer's
   certificate chain (Decision 14), **1.691 to 11.129B extra, depending
   on the profile**, never accounted for as a separate line in any
   previous report. This cost (AEAD encryption of a blob of a few KB,
   plus the corresponding network write) is a direct candidate for
   part of the residue -- especially in the PQC/Hybrid profiles, where
   the ticket is larger because the client's certificate is larger.
2. **CPU cost of the primitives themselves (signing, verifying, KEX),
   now measured in isolation by `bench`** (Decision 14): this had
   never been isolated as a fraction of the total handshake time in
   v7/v8 -- it was implicitly inside the total time, never decomposed.

**Not decided here, recorded for T7/the pilot:** confirming whether
the sum (ticket cost, when on + measured CPU cost) actually accounts
for v8's historical residue would require reprocessing v8's raw data
(outside this round's scope, which is v9's local Phase 1) -- what this
round delivers is the TWO pieces that were missing for that
reckoning, not the reckoning closed out.

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 16. T7, DRAFT of the pre-pilot acceptance criteria -- for Luciano's review, not executed, no tag created

**Status of this draft: proposal, not approved.** None of these
criteria is to be taken as closed merely for being listed here --
each one gets its own status (CLOSED, with the evidence that closes
it; or PENDING, with what is missing). The `v9-prereg` tag only goes
out after Luciano's explicit approval of this draft, and only after
ALL the criteria below are CLOSED (or explicitly waived by him).

**(a) Full local flow, with v8's counts, zero errors.**
Criterion: the 4 profiles (Classical, PQC, Hybrid-v8, Hybrid-AND) run
locally against the real stack (`mock_as`, `insurance-server-lambdas`,
`localstack`, `mongo`, unaltered), producing exactly 44
HTTP calls, 6 mTLS connections, 28 JWTs, 4 `/jwks` fetches, 4 CA
fetches per run, confirmed by T6's instrumentation (not by
manual counting), zero errors. **Status: CLOSED, after T6b (Decision
17) and the requested reconciliation (Decision 18) -- the 5 numbers
confirmed exact across the 4 profiles: 44 HTTP calls, 6 client-facing
mTLS connections (after excluding the proxy's readiness probe, which
was never part of the measured flow), 28 JWTs, 4 `/jwks`, 4 CA
fetches, 0 errors -- against the real stack (`mock_as`/
`insurance-server-lambdas` untouched).**

**(b) v8's five validity gaps, one by one, with the test that closes
each one:**

| # | v8's gap | v9's fix | Test that closes it | Status |
|---|---|---|---|---|
| 1 | Classical/Hybrid used RSA-4096 (atypical; real-world practice is RSA-2048) | Classical/Hybrid-v8 reissued at RSA-2048 (T4, Decision 9/10) | `certs/main.go`'s `validateChain`+EKU table confirms RSA-2048; `bench` (Decision 14) measures the new key's real cost (830us/signature) against the 6,624ms/signature for RSA-4096 already documented in v8 (Decision 99/`98678` of `v8/DECISIONS.md`) -- order of magnitude consistent with the key-size ratio | **CLOSED** (issuance + measured cost; no formal regression test preventing accidental reintroduction of RSA-4096) |
| 2 | The client (`tls_kem_proxy`) never verified the server (`InsecureSkipVerify: true`) | v9's proxy sets `RootCAs` per profile, with no `InsecureSkipVerify`, on all 4 profiles (Decision 12) | T5/T6: every connection SUCCEEDED with the gateway's real certificate -- proves the verification is present and does not reject the correct case, but does NOT prove it would reject a wrong certificate | **PARTIAL -- missing negative test** (gateway with an untrusted/wrong certificate, confirm the proxy REFUSES the connection, across the 4 profiles) |
| 3 | The server (`mock_mtls`) had an OPTIONAL client certificate (`tls.VerifyClientCertIfGiven`) | v9's gateway uses `tls.RequireAndVerifyClientCert` on all 4 profiles (Decision 12) | T5/T6: every connection with a valid client certificate SUCCEEDED -- same gap as item 2, proves the happy path, not the rejection | **PARTIAL -- missing negative test** (connection WITHOUT a client certificate, or with an invalid one, confirm the gateway REFUSES, across the 4 profiles -- Hybrid-AND already has this covered by T3/`dual_test.go`'s 18 scenarios, the other 3 profiles do not) |
| 4 | Handshake counter contaminated by the first HTTP request (and, in v8, by tickets -- Decision 78/79 of `v8/DECISIONS.md`) | Counting at the exact `Handshake()` boundary, tickets off by default (Decision 13/14) | Triple cross-validation (process counter = decrypted tshark = raw pcap sum), across the 4 profiles (Decision 14); consistent record overhead (77B/121B) across the 4 profiles (Decision 15) | **CLOSED** |
| 5 | Per-message size and time residue never measured/isolated | Per-message table (Decision 15) + CPU microbenchmarks + quantified ticket cost (Decision 14) | Per-message table cross-checked against the measured total, 4 profiles (Decision 15); ticket cost and CPU cost are now numbers, not unknowns | **PARTIAL -- the pieces exist, v8's historical residue reckoning was not redone with them** (Decision 15, last paragraph) |

**DATED NOTE (2026-11-09, after the real Phase B completed, explicit
decision from Luciano -- the original text of the table above kept
intact, never rewritten): gaps #2 and #3 (status "PARTIAL -- missing
negative test") are CLOSED by explicit decision.** The fix (already
present since this Decision 18) was applied and exercised on the
happy path across the 4 profiles -- confirmed with 100% real data from
Phase B (Decision 101, 60/60 runs, 0 errors, the gateway's correct
certificate in all of them). **Rejection (the negative test) is
explicitly declared OUT OF SCOPE** -- no longer a remaining gap, by
explicit decision, not by omission. See Decision 103 (b) and
Decision 104 for consolidated evidence.

**(c) CurveID and DualAuthenticated checked on every measured
connection.**
Criterion: every run of the real campaign reads
`ConnectionState.CurveID` and fails explicitly if it does not match
the profile's expected group; every Hybrid-AND run reads
`DualAuthenticated` on both sides and fails explicitly if `false`.
**Status: CLOSED**, reconfirmed by T6b
(Decision 17) with the real business layer and `opin_flow.py`, not
just the isolated harness: across the 4 profiles, every client-facing
connection negotiated exactly the expected group; in Hybrid-AND,
`DualAuthenticated
= true` in 100% of the 7 client-facing connections measured (confirmed
by the gateway's own log).

**(d) Interoperability matrix executed.** Decision 4 of this same
folder (`DECISIONS.md`) already recorded the gap (TLS 1.3-only stack
divergence, interoperability matrix not covered) as pending since
T1/T2. **Status: PENDING, not started in this round** -- needs scope
definition (which external client/server pairs, if any, enter the
matrix) before it can be estimated or executed.

**(e) AWS pilot reproduces the per-message sizes measured locally
(tolerance to be defined) and the instances' real initcwnd.**
Criterion: the first real collection on AWS (outside this Phase 1)
measures the same per-message sizes from Decision 15 (within a
tolerance Luciano defines -- suggestion: 0B tolerance on the message
sizes themselves, which are deterministic by algorithm/certificate,
not by the network; tolerance only on time, not on size) and confirms
via `ss --info`/`ip route`/equivalent which `initcwnd` the real
instances use, closing out Decision 14's assumption (initcwnd=10
assumed, not measured). **Status: PENDING -- depends on AWS, outside
this Phase 1's scope by definition.**

**(f) Closing the residue: at least 90% of the inter-profile latency
difference attributed to measured components, the rest explained or
declared.** Criterion: for each pair of profiles (e.g.,
PQC-minus-Classical), the sum of the already measured components
(KEX, sign/verify, extra bytes x RTT, ticket if on) must cover >=90%
of the total time difference observed between the two profiles; the
remaining residue (<=10%) must be named (even if not eliminated) or
explicitly declared unexplained. **Status: PENDING --
this round's Decision 14/15 deliver the components (KEX, CPU, ticket,
initcwnd) but the closing reckoning itself (the 90%) can only be done
with real end-to-end per-profile latency data, which require T6b
(full flow) or the pilot -- there is not yet a "latency per profile"
number in v9 to compare against.**

**(g) Pilots designed to stress the distant routes.**
Criterion: the pilot's design (AWS regions, number of runs,
order) deliberately includes the higher latency tiers (225ms,
320ms) with enough repetitions to distinguish Hybrid-AND's cost from
the other 3 profiles with statistical significance, not just passively
replicate the tiers already used in v7/v8. **Status: PENDING
-- depends on the AWS pilot plan (outside this Phase 1), but Decision
14 already provides a concrete number to calibrate this design:
Hybrid-AND totals ~12.177B (server) + ~11.902B (client) per
handshake, almost 2x Hybrid-v8 -- the pilot's design should
guarantee enough N for this difference to be detectable at the
slowest tier too, not just the fastest.**

**(h) Equivalence checklist with v8 -- deliberate divergences listed
explicitly, not hidden:**

| Deliberate divergence | Decision that records it |
|---|---|
| Classical/Hybrid-v8 at RSA-2048, not RSA-4096 | Decision 9/10 (T4), item (b)#1 above |
| Session tickets off by default on all 4 profiles (v7/v8: always on) | Decision 13 |
| v9's PQC chain is 1 level, DN with only CommonName (real v8: 2 levels, 3 extra DN fields) -- sizes NOT comparable between v9 and v8, only among v9's 4 profiles | Decision 11 |
| Full mutual verification on all 4 profiles (client verifies server, server requires client certificate) -- v7/v8 had both gaps (item (b)#2 and #3 above) | Decision 12 |
| The T5/T6 harness is a fork at `thesis/results/v9/integration/`, never the production files `mock-service-os/mock_mtls`/`thesis/scripts/tls_kem_proxy` that v7/v8 use | Decision 12 |
| Byte counting at the exact `Handshake()` boundary, not at `ConnState -> StateActive` (v7/v8 deliberately kept the old limit, for comparability with v7 -- Decision 78/79 of `v8/DECISIONS.md`) | Decision 14 |
| `thesis/scripts/opin_flow.py` edited (the only production file touched anywhere in v9) -- additive and opt-in (`V9_HARNESS`), the same pattern as the `REMOTE_GATEWAY_HOST` already existing in the same file; zero behavior change when off | Decision 17 |
| No endpoint waives the client certificate in v9 (uniform RequireAndVerifyClientCert, on all 4 profiles) -- real v8 uses VerifyClientCertIfGiven globally, but no call from the historical opin_flow.py was ever served without a certificate (confirmed by measuring it), so this policy divergence was never actually exercised in practice | Decision 18 |

**No tag created. No action on AWS. Stop at the end of this draft,
as requested -- awaiting Luciano's explicit approval before any
`v9-prereg`.**

## 17. T6b, full local flow: the 4 profiles ran end to end against the real stack (mock_as and insurance-server-lambdas untouched), 44 HTTP calls and 0 errors on all 4, with three real bugs found and fixed along the way; mTLS connection-count divergence reported, not forced to match

**Risk checked before writing any business-logic code:**
`client_one` uses `token_endpoint_auth_method: "private_key_jwt"`
(`init_clients.json`) -- the client assertion's signature is verified
by the AS against a REGISTERED JWKS (`mongo_seed`), a credential
ENTIRELY SEPARATE from the mTLS certificate that carries the
connection. Confirmed by reading `thesis/scripts/opin_flow.py`'s
`load_client_signing_key()` and `mock-service-os/mock_as/mongo-seed/
start.sh`: both already fall back to the real classical setup
(`client_one.jwks`/`client_one_pub.jwks`, RSA-4096, PS256) for
ANY profile that is not literally `"pqc"` or `"hybrid"` --
`"hibrido-and"` falls into this fallback for free, needing no change
to `mongo_seed` nor to `opin_flow.py`'s signing. This confirmed that
no change would be needed in `mock_as` or
`insurance-server-lambdas` -- the mTLS mechanism swap (v9) is
completely orthogonal to client authentication at the token endpoint
(which uses another key, another protocol).

**Real empirical baseline, BEFORE any change, against the 100%
original stack:** real `mtls` restarted (`docker compose up mtls`),
the original `opin_flow.py` run with no modification whatsoever --
`run_insurance_flow('classic')` + `run_person_flow('classic')`:
**20 + 24 = 44 HTTP calls, 0 errors.** Confirms exactly the
already-established number (`v8/DECISIONS.md`, Decisions 89/9064/10719)
and serves as a control: any divergence that appears later is from MY
harness, not from the real stack.

**Architecture (see `thesis/results/v9/integration/`):**
- `gateway/business.go` + `business_server.go` (new): restore the
  business layer of `mock_mtls/main.go` (reverse proxy to
  `auth:3000`/`mockapi:8080`, token introspection,
  `/root-ca.pem`/`/issuer-ca.pem`) to v9's fork, WITHOUT SSA (confirmed
  by directly reading `opin_flow.py`: neither flow calls
  `.../softwarestatements/.../assertion` -- `client_one` is
  pre-registered, it does not go through DCR) and without
  `/participants`/
  `/application.jwks`/`/.well-known` (also confirmed as not called).
  The explicit handshake (`tls.Server`+`Handshake()`) still checks
  CurveID/DualAuthenticated per connection (criterion (c) of T7's
  draft), then hands the already-authenticated connection to a shared
  `http.Server` via a custom listener, to support keep-alive
  (the real flow reuses each mTLS connection across several HTTP
  calls, which the T5/T6 "measure" mode, one response per connection,
  does not support).
  Mode selected via `HTTP_MODE=business` (new), with `measure` as the
  default -- `run_t5.sh`/`run_t6.sh` keep working with no
  change.
- `proxy/relay.go` (new): persistent relay mode (the counterpart to
  T5/T6's single-request "measure" mode) -- listens locally with an
  ephemeral self-signed certificate (the same mechanism as the real
  `tls_kem_proxy`), opens one real mTLS connection per accepted local
  connection, using `buildClientTLSConfig` (the SAME code from T5/T6,
  covering the 4 profiles including Hybrid-AND, which the real
  `tls_kem_proxy` does not have). Enabled by `-listen`.
- `thesis/scripts/opin_flow.py` (EDITED -- the only production file
  touched in this round, additively): `_USE_TLS_KEM_PROXY` gained
  `"hibrido-and"`; a new env var `V9_HARNESS` (off by default, same
  precedent as `REMOTE_GATEWAY_HOST` in the same file) makes
  `start_tls_kem_proxy()` launch v9's relay proxy instead of the real
  `tls_kem_proxy`, for all 4 profiles -- necessary even for
  classic/pqc/hybrid, because the real `tls_kem_proxy` only knows how
  to present the REAL production certificates, which v9's gateway
  (its own CAs, Decision 9/10/11) will never trust. No other line
  changed --
  confirmed that `load_client_signing_key`, the call count, and the
  entire flow logic remain identical.

**Integration with the real stack:** the real `mtls` container was
stopped (`docker stop`, never removed); a `v9-mtls` container (my
image, `business` mode) joined the SAME
`insurance-server-lambdas_default` with the SAME network aliases
(`--network-alias mtls
matls-auth.local auth.local matls-api.local api.local directory`) --
`auth`/`mockapi`/`mongodb`/`psql`/`localstack` stayed up,
unaltered, exactly as they were. v9's certificates and the
REAL ones from `mock-service-os/certs/` entered via bind mount
(`docker run -v`, confirmed working normally in this environment with
`MSYS_NO_PATHCONV=1` -- the earlier conclusion that a bind mount "does
not work in this environment" was itself an artifact of Git Bash's
path mangling, not a real limitation of Docker Desktop;
recorded here to correct that earlier understanding).

**Three real bugs found and fixed along the way, each found by
actually running it, not foreseen statically:**

1. **DNS round-robin between the real `mtls` and the new `v9-mtls`.**
   An intermittent error ("certificate is valid for ..., not mtls") on
   the first attempt -- cause: the REAL `mtls` container was still
   running (I had restarted it to measure the baseline and forgot to
   stop it), and both (real `mtls` + `v9-mtls`) had the `mtls` alias
   registered on the same network at the same time -- Docker's
   embedded DNS alternated between the two. Fixed by stopping the
   real `mtls` before continuing.

2. **`internalCallerConfig` with `ClientCAs` fixed to `ca.crt`,
   diverging from the original.** Under `pqc`, the reentrant call to
   `InsurerAdapter.getConsent()` (via SNI `matls-api.local`) failed
   with
   `certificate signed by unknown authority` -- `setup_ssm.sh`
   publishes
   `op_pqc.crt` (signed by `root_ca_pqc`, NOT by `ca.crt`) as the AS's
   transport certificate under this profile. The ORIGINAL `mock_mtls/
   main.go` does not have this problem because its
   `internalCallerConfig := *cfg` INHERITS the `ClientCAs` from the
   main config (which `caCertPool()` already extends to trust
   `root_ca_pqc.crt` under `CRYPTO_PROFILE=pqc`) -- I had fixed a
   separate pool, with only `ca.crt`, diverging on this detail. Fixed:
   the pool now also trusts `root_ca_pqc.crt` when the profile is
   `pqc` (`business_server.go`'s `attachInternalCallerCarveOut`).

3. **`VerifyPeerCertificate` unintentionally inherited into the
   carve-out.**
   Under `hybrid`, the same reentrant call failed with `ML-DSA-65 alt
   signature verification failed` -- Hybrid-v8's AND X.509 gate
   (which verifies the alternative signature against v9's OWN ML-DSA
   CA, `hibrido_v8_ca_mldsa.crt`) was being inherited by
   `internalCfg` via `cfg.Clone()`, but `op_hybrid.crt` (the AS's real
   certificate under this profile) has its alternative signature made
   by the REAL production ML-DSA CA, a completely different key.
   The internal caller was never part of any profile's v9-specific
   identity scheme. Fixed: explicit `internalCfg.
   VerifyPeerCertificate = nil` in the carve-out.

**Final result, the 4 profiles, `auth`/`mongo_seed`/`mockapi`
recreated with the corresponding `CRYPTO_PROFILE` before each test
(classic/pqc/
hybrid; hibrido-and runs with the backend on classic, on purpose -- see
below), `insurance-server-lambdas` and `mock_as` never edited:**

| Profile | HTTP calls (insurance+person) | Errors | Group (client connections) | DualAuthenticated |
|---|---|---|---|---|
| Classical | 20+24=44 | 0 | CurveP384, 7/7 | n/a (false, expected) |
| PQC | 20+24=44 | 0 | MLKEM1024, 7/7 | n/a (false, expected) |
| Hybrid-v8 | 20+24=44 | 0 | SecP384r1MLKEM1024, 7/7 | n/a (false, expected -- X.509 gate confirmed passing in the logs) |
| Hybrid-AND | 20+24=44 | 0 | SecP384r1MLKEM1024, 7/7 | **true, 7/7 client connections** |

All 44 calls returned success (no Python exception, no
`raise_for_status()` firing) across the 4 profiles. On ALL client
connections (SNI `mtls`) of the 4 profiles, the negotiated group
matched exactly what was expected for the profile; in Hybrid-AND
specifically, `DualAuthenticated
= true` in 100% of these connections (confirmed by the gateway's own
log, not inferred).

**Why the backend stays on `classic` for Hybrid-AND:** the AND
mechanism belongs entirely to the transport layer (dual proof of
possession in the TLS handshake) -- it changes nothing about how the
AS signs JWTs or how the RS signs responses. Leaving `auth`/`mockapi`
on `classic` for this profile is a deliberate choice, not an
omission: there is no (nor should there be a) "CRYPTO_PROFILE=hibrido-and"
in the real `mock_as`/
`insurance-server-lambdas`, because nothing there needs to know that
the AND mechanism is in use.

**Count divergence reported here (7 client-facing mTLS connections,
not 6) -- RECONCILED in Decision 18, after additional instrumentation
requested by Luciano: it is not a real divergence.** The seventh
connection is the proxy's own readiness probe
(`_wait_for_tls_kem_proxy_ready()`), which runs once per call to
`start_tls_kem_proxy()` and never serves any real HTTP request --
excluding it, exactly 6 client-facing connections remain, matching
exactly v7/v8's historical number. The `cert=None` hypothesis recorded
below (already tested, see Decision 18) was WRONG: this specific
connection also presents a client certificate normally
(`requests`'s `merge_setting()` does not turn off the session's
certificate when `cert=None` is passed explicitly).

**Internal connections (SNI `matls-api.local`):** also 7 per run,
across all profiles -- symmetric to the 7 client-facing ones, likely
the same structural cause (the same number of "AS-to-RS flows" as
client-facing flows, 1:1, consistent with
`InsurerAdapter.getConsent()` firing once per consent authorization).

**JWTs (28) and /jwks (4): extracted and confirmed in Decision 18**,
across the 4 profiles, with no divergence whatsoever.

**Container state at the end of this round:** `v9-mtls` removed;
real `mtls` STOPPED (not removed, `docker start
insurance-server-lambdas-mtls-1` brings it back); `auth`/`mongo_seed`/
`mockapi` recreated back on `CRYPTO_PROFILE=classic` (the default);
`localstack`/`mongodb`/`psql` keep running, unaltered.
`thesis/results/v9/certs/generated/` and `thesis/results/v9/integration/
{gateway,proxy}/certs/` remain on this session's local disk (not
committed, gitignored) -- removed before this round's commit.

New/edited artifacts: `thesis/results/v9/integration/gateway/
{business.go,business_server.go}` (new), `main.go` (edited --
`HTTP_MODE` dispatch); `thesis/results/v9/integration/proxy/
relay.go` (new), `main.go` (edited -- `-listen` flag);
`thesis/scripts/opin_flow.py` (edited, additively -- see above).

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 18. Closing out the points requested about T6b: the seventh connection identified (and it is not what the cert=None hypothesis suggested -- premise corrected), 28 JWTs/4 jwks/4 CA confirmed across the 4 profiles with no divergence, exact opin_flow.py diff with empirical proof of equivalence when V9_HARNESS is off

**1. The seventh mTLS connection, precisely identified.** I
instrumented `gateway/business.go`/`business_server.go` to log, per
connection, `remoteAddr` (the client's ephemeral port -- uniquely
identifies WHICH TCP connection served each request) together with
`clientCert` (the CommonName of the presented certificate, or
`"none"`) and
`handshakeBytesIn/Out`; and cross-checked this against the HTTP access
log, which now also carries the same `remoteAddr`. Full round,
Classical profile, complete list below (the same structure repeats
across the other 3 profiles, confirmed by sampling).

**Complete list of TLS connections from one run (insurance+person
combined), type and handshake bytes:**

| # | remoteAddr | SNI | Type | ClientCert | handshakeBytesIn/Out | What it served |
|---|---|---|---|---|---|---|
| 1 | :39996 | mtls | mTLS (cert required and presented) | classico_client | 1513/1640 | **nothing** -- see finding below |
| 2 | :40006 | mtls | mTLS | classico_client | 1513/1640 | /jwks(AS), /token, /jwks(RS), POST consents, GET consents x2, /request |
| 3 | :40020 | mtls | mTLS | classico_client | 1513/1640 | /root-ca.pem, /issuer-ca.pem |
| 4 | :56390 | mtls | mTLS | classico_client | 1513/1640 | /auth, /interaction x3, /auth/{id} |
| 5 | :56394 | mtls | mTLS | classico_client | 1513/1640 | /jwks(AS), /token, /jwks(RS), POST consents, GET consents, /request, /token(ac), 8x insurance-person |
| 6 | :56402 | mtls | mTLS | classico_client | 1513/1640 | /root-ca.pem, /issuer-ca.pem |
| 7 | :56414 | mtls | mTLS | classico_client | 1513/1640 | /auth, /interaction x4, /auth/{id} |
| -- | 7x :43xxx | matls-api.local | mTLS (internal, AS->RS) | op | 4307/2530 | `InsurerAdapter.getConsent()`, 3x insurance + 4x person |

**Finding: connection #1 (`:39996`) serves NO HTTP request at all --
it is the proxy's own readiness probe
(`_wait_for_tls_kem_proxy_ready()`, `opin_flow.py` line ~1179), which
makes a plain `GET /`, with no Host header recognizable by any
`ServeMux` pattern, getting a 404 from Go's default handler -- which
in my code never goes through `loggingMiddleware` (only the
registered patterns, "auth.local/" etc., go through it), which is why
this connection opens (and shows up in the CONNECTION log) but never
appears in the ACCESS log.** This function is CALLED BY ME TOO inside
the `V9_HARNESS` branch (same shared function, `opin_flow.py` line
1114) -- it is not a bug introduced by v9, it is the SAME mechanism
the real `tls_kem_proxy` always had, exercised once per call to
`start_tls_kem_proxy()`, which both my test script and
`switch_crypto_profile.py` call once per combined run (the two flow
calls share the same proxy, started once before both).

**Excluding this probe, exactly 6 client-facing connections remain
(#2 through #7) -- v7/v8's historical number, matching exactly.** And
the 7 internal connections (`matls-api.local`) also match exactly
against what Decision 77 of `v8/DECISIONS.md` had already found
independently
("7 internal AS-to-RS requests", same number, same category).
**Conclusion: there is no real count divergence. The "7" I reported
earlier was adding the readiness probe (which is not part of the
measured flow) to the 6 real connections -- an artifact of MY own
test script (which calls `start_tls_kem_proxy()` without the care an
official collection would take to exclude this connection from the
measurement window), not of the mechanism itself.** Recorded for
T7/T8: an official collection needs to start counting handshakes
AFTER `_wait_for_tls_kem_proxy_ready()` returns, not before -- this is
probably already how `switch_crypto_profile.py` operates in
practice (the probe happens during the profile's SETUP, outside the
window of any measured run), but this was not confirmed here.

**The `cert=None` hypothesis was wrong -- premise corrected, not
confirmed.** Connection #3 (`:40020`), which specifically serves
`/root-ca.pem`/`/issuer-ca.pem` (the call that uses `cert=None`),
**has
`clientCert=classico_client`** -- a REAL client certificate was
presented and verified, exactly like all the others. Reason:
`requests.Session.request(..., cert=None)` does not turn off the
session's certificate -- the library itself (`merge_setting()`)
treats an explicitly `None` argument as "no override," falling back
to
`session.cert` (which `run_insurance_flow`/`run_person_flow` already
set once, at the start, for every call in that session).
`cert=None` on these specific calls never had the effect of turning
off the certificate -- it is only documentation/intent in the source
code, not real runtime behavior.

**Carve-out: NO endpoint that waives the client certificate exists in
v9 today -- correction of the question's premise, not a description
of something already implemented.** Confirmed by the table above:
the 7 client-facing connections (including the ones serving
`/root-ca.pem`/
`/issuer-ca.pem`) have `ClientAuth: tls.RequireAndVerifyClientCert`
WITH NO EXCEPTION, the same main profile config, across the 4
profiles, with no difference -- this is precisely the decision
already made and recorded in Decision 12 (closing v8's validity gap
#3, `VerifyClientCertIfGiven`,
for ALL endpoints, not just some). If real v8 actually accepted a
connection without a client certificate in some case (possible, given
that it uses `VerifyClientCertIfGiven` globally), this was never
exercised by this specific flow (`opin_flow.py` always sends a
certificate, because of `session.cert` + the `merge_setting()`
behavior explained above) -- so there is, in this investigation's
real data, no historical v7/v8 call that was ever served without a
client certificate. **I did not create any new carve-out**, because
the data showed no need for one -- if Luciano wants v9 to deliberately
reproduce an "optional server certificate" behavior for some specific
endpoint (reopening gap #3 just there), that is a new scope decision,
not a bug fix.

**Final classification for the metrics:** across the 4 profiles, 100%
of the 6 real client-facing connections (excluding the probe) ARE
mTLS with a client certificate -- zero server-only connections. **v8's
"6 mTLS connections" corresponds 1:1 to v9's "6 connections with a
client certificate"** -- there is no second category to split into,
because no server-only connection exists in the measured data.

**2. Remaining counts: 28 JWTs, 4 /jwks, 4 CA fetches -- extracted
and confirmed across the 4 profiles, ZERO divergence.** Extracted
directly from the `calls1`/`calls2` that `run_insurance_flow`/`run_person_flow`
return (`jwts` and `endpoint` fields, not inferred by heuristic):

| Profile | HTTP calls | JWTs | /jwks | CA (root+issuer) | Errors |
|---|---|---|---|---|---|
| Classical | 44 | 28 | 4 | 4 | 0 |
| PQC | 44 | 28 | 4 | 4 | 0 |
| Hybrid-v8 | 44 | 28 | 4 | 4 | 0 |
| Hybrid-AND | 44 | 28 | 4 | 4 | 0 |

All 4 profiles produce exactly the same numbers because the call
sequence is entirely defined by the flow logic
(`opin_flow.py`), which does not vary by profile -- only the TLS
mechanism (certificate/group/AND) varies, never the HTTP sequence.
This matches exactly Luciano's original 5 numbers (44/6/28/4/4 --
with 6 being the number of client-facing connections, already
reconciled in point
1). **No count divergence remains.**

**3. `opin_flow.py`: exact diff (already committed in `1763a64e`,
reproduced here in full) and proof of equivalence with `V9_HARNESS`
off.**

```diff
--- a/thesis/scripts/opin_flow.py
+++ b/thesis/scripts/opin_flow.py
@@ -235,9 +235,35 @@ DIRECTORY_HOST = "directory"
 _CRYPTO_PROFILE_FOR_ROUTING = os.environ.get("CRYPTO_PROFILE", "classic")
-_USE_TLS_KEM_PROXY = _CRYPTO_PROFILE_FOR_ROUTING in ("classic", "pqc", "hybrid")
+_USE_TLS_KEM_PROXY = _CRYPTO_PROFILE_FOR_ROUTING in ("classic", "pqc", "hybrid", "hibrido-and")
 TLS_KEM_PROXY_PORT = int(os.environ.get("TLS_KEM_PROXY_PORT", "8443"))

+V9_HARNESS = os.environ.get("V9_HARNESS") == "1"
+V9_PROFILE_NAME = {"classic": "classico", "pqc": "pqc", "hybrid": "hibrido-v8", "hibrido-and": "hibrido-and"}
+V9_CERTS_DIR = BASE_DIR / "thesis" / "results" / "v9" / "certs" / "generated"
+V9_PROXY_IMAGE = "mockopin-v9-proxy"
+
 # (comentarios omitidos aqui por espaco -- integrais no commit 1763a64e)
@@ -1046,7 +1072,7 @@ def start_tls_kem_proxy(...):
-    if crypto_profile not in TLS_KEM_PROXY_CURVE_BY_PROFILE:
+    if crypto_profile not in TLS_KEM_PROXY_CURVE_BY_PROFILE and crypto_profile != "hibrido-and":
         return None
     subprocess.run(["docker", "rm", "-f", TLS_KEM_PROXY_CONTAINER_NAME], ...)
-    crt_path, key_path = get_client_cert_paths(crypto_profile)
-    curve = os.environ.get(...) or TLS_KEM_PROXY_CURVE_BY_PROFILE[crypto_profile]
     proxy_target = f"{REMOTE_GATEWAY_HOST}:443" if REMOTE_GATEWAY_HOST else "mtls:443"
     run_mode_flags = ["-d"] if detached else ["--rm", "-i"]
+    if V9_HARNESS:
+        # ... lanca o proxy da v9 em vez do tls_kem_proxy real (bloco
+        # completo no commit) ...
+        return proc_ou_nome
+    crt_path, key_path = get_client_cert_paths(crypto_profile)
+    curve = os.environ.get(...) or TLS_KEM_PROXY_CURVE_BY_PROFILE[crypto_profile]
     # resto da funcao ORIGINAL, inalterado, a partir daqui
```

**Why a file-hash proof does not apply (the file really changed), and
what proof I used instead:** `opin_flow.py` DID change --
it has new lines. The real question is whether the BEHAVIOR, with
`V9_HARNESS` off (the default state), is identical to before the
edit. Proof by ARGUMENT about the diff: (a) the condition
`crypto_profile not in TLS_KEM_PROXY_CURVE_BY_PROFILE` is identical
for the 3 profiles that already existed (`classic`/`pqc`/`hybrid`
were already in the dict, so `and crypto_profile != "hibrido-and"`
never changes the result for them); (b) the `if V9_HARNESS:` block is
skipped entirely when the env var is not `"1"` (the default), falling
straight into the SAME two lines
(`crt_path, key_path = ...` / `curve = ...`) that existed before,
byte for byte, just shifted in position; (c) no other function in the
file was touched.

**Proof by REAL EXECUTION, stronger than a text hash -- runs the
code, not just reads it:** I restarted the REAL `mtls` (`docker compose up
mtls`), confirmed from the container's own log
(`clientCertBytes=1494`, `mtlsHandshakeBytes=5173` -- the REAL numbers
for the RSA-4096 production certificate, not any v9 certificate) that
it was the real gateway responding, and ran `run_insurance_flow`/
`run_person_flow('classic')` with `V9_HARNESS` explicitly
NOT set (`unset V9_HARNESS`, confirmed `of.V9_HARNESS == False`
in the Python process itself). Result: **44 calls, 28 JWTs, 4
jwks, 4 CA, 0 errors** -- identical to the baseline measured BEFORE
any edit in this session (Decision 17) and identical to v7/v8's
historical number. No `tls_kem_proxy_run` container with v9's image
existed during this run (confirmed by `docker ps` during the test).

**Decision: the change stays where it is** (`thesis/scripts/opin_flow.py`,
commit `1763a64e`) -- the proof above (diff logic + identical real
execution) establishes equivalence when off; moving it to a copy
in `v9/integration/` would require duplicating ~1.900 lines of flow
logic just to isolate 4 genuinely new lines, which Luciano himself
implicitly ruled out by accepting the additive edit as the approach
(previous round) -- but the final decision is his; if he still prefers
to revert and move it, let me know and I will undo it.

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 19. Probe correction (confirmed no loophole), internal carve-out documented, negative tests across the 4 profiles (16 scenarios, all correct), 5x5 interoperability matrix executed -- critical finding: the AND mechanism only protects in strict mode, confirmed at the pure TLS layer

**1. The readiness probe ALWAYS presents a client certificate -- there
is no loophole.** `_wait_for_tls_kem_proxy_ready()` does
`requests.get(url, timeout=1, verify=False)` -- a module-level call
with NO `cert=` at all, no Session, hence NO certificate on the LOCAL
leg (Python -> my proxy's local listener, which never requires one).
But my relay proxy (`relay.go`) builds `buildClientTLSConfig` ONCE, at
the start of the process, and uses THIS SAME config, with the
profile's real certificate, for EVERY accepted local connection --
including the probe's. Confirmed directly in the log: the probe's
connection (`:39996` in Decision 18's round) shows up with
`clientCert="classico_client"`, a REAL certificate, verified by the
gateway's `RequireAndVerifyClientCert` like any other. There is no
loophole because the two-hop architecture (local leg with no
certificate, real leg always with the process's fixed certificate) is
exactly what the real `tls_kem_proxy` always did too -- no change
from v9 on this.

**Confirmed that the probe does NOT enter any measured counter.**
Bytes: the probe never reaches `loggingMiddleware` (a 404 from the
`ServeMux`'s default handler, which this middleware does not wrap),
so it never generates an ACCESS log line -- only the CONNECTION line
(which I added solely for this diagnostic; the normal `measure`/T6
mode does not log connections by default, it only uses the counter
for handshake_bytes, which is by itself irrelevant here because this
connection was never part of any official measurement). Connections:
confirmed by the structure of the
the real `switch_crypto_profile.py` -- the proxy is started ONCE per
PROFILE SWITCH (not per run), and the probe runs at that moment,
BEFORE any of the N measured runs of that profile start;
the measured runs reuse the SAME, already-probed proxy. **Real v8
also excluded the probe from the "6" -- not via an explicit filter,
but structurally: the probe never happens INSIDE the window of a
measured run, it happens exactly once, at the profile switch, before
the first run.** It was MY ad-hoc test script (which calls
`start_tls_kem_proxy()` on every call, simulating "every run is a
profile switch") that reintroduced the probe inside the window I was
measuring -- an artifact of MY own test method, not of the real
mechanism, already closed out in Decision 18.

**2. Internal carve-out (`matls-api.local`), documented:**

| Aspect | Value |
|---|---|
| Authentication used | Pure classical TLS (CurvePreferences `[P521, P384, P256]`, `CurveP256` negotiated in the tests) -- never the hybrid/PQC group of the main profile |
| Server certificate (my gateway) | ALWAYS the real `mock-service-os/certs/mtls.crt`/`.key` -- fixed, does not depend on v9's profile |
| Expected client certificate (auth) | `op.crt` (classic/hibrido-and) / `op_pqc.crt` (pqc) / `op_hybrid.crt` (hybrid) -- whatever `setup_ssm.sh` publishes for that real BACKEND `CRYPTO_PROFILE`, not v9's TLS profile |
| `ClientCAs` | always the real `ca.crt`; **plus** `root_ca_pqc.crt` when the profile is `pqc` (Decision 17, bug #2) -- the only variation across profiles |
| `VerifyPeerCertificate` | always `nil` (Decision 17, bug #3) -- never the main profile's AND/hybrid gate |
| Same across the 4 profiles? | The CODE that builds the carve-out is identical across all 4 (`attachInternalCallerCarveOut`, a single function, always called); the CA pool's CONTENT varies only under `pqc`, mirroring what the real backend publishes under that `CRYPTO_PROFILE` -- not a divergence among v9's 4 profiles, but the carve-out faithfully following what the real AS presents |
| Does it enter any measured counter? | Yes, as its OWN category ("internal connections", SNI `matls-api.local`) -- never added to the client-facing connections. 7 per combined run, across the 4 profiles, matching exactly v8's Decision 77 ("7 internal AS-to-RS requests") |

**3. Negative tests, 4 profiles, 16 scenarios -- ALL correct (no
improper acceptance):**

Built in `thesis/results/v9/integration/negtest/` (new),
run against v9's REAL gateway/proxy binaries (not just the
`dual_test.go` suite). Methodological finding along the way, fixed
before trusting any result: a `Handshake()` that returns success on
the CLIENT side is not enough -- TLS 1.3 lets the client finish before
the server confirms its certificate, the SAME asymmetry that
`dual_test.go`'s `dualHandshakePipe` had already documented and
worked around in this same session (T3). Without an extra read after
`Handshake()`, the first 3 profiles reported `UNEXPECTED_SUCCESS` on
`no-client-cert`/`untrusted-client-ca` -- WRONG, the server rejects
both, just that the alert arrives later. Fixed (extra read,
2s deadline); final, clean result:

| Scenario | Classical | PQC | Hybrid-v8 | Hybrid-AND |
|---|---|---|---|---|
| (i) no client certificate | REJECTED (`certificate required`) | REJECTED (`certificate required`) | REJECTED (`certificate required`) | REJECTED (`handshake failure`) |
| (ii) client certificate from an untrusted CA | REJECTED (`certificate required`\*) | REJECTED (`certificate required`\*) | REJECTED (`certificate required`\*) | REJECTED (`certificate required`\*) |
| (iii-a) server certificate from an untrusted CA | REJECTED (`signed by unknown authority`) | REJECTED (`signed by unknown authority`) | REJECTED (`signed by unknown authority`) | REJECTED (`signed by unknown authority`) |
| (iii-b) server certificate with the wrong SAN | REJECTED (`certificate is valid for [...], not not-a-real-san.invalid`) | REJECTED (same) | REJECTED (same) | REJECTED (same) |
| (iv) Hybrid-AND, single RSA chain, STRICT mode | -- | -- | -- | REJECTED (`handshake failure`) |

\* The error reported for an untrusted CA certificate arrives as the
same `certificate_required` alert as scenario (i) in this
implementation -- Go's chain verification runs BEFORE the client's
`Handshake()` returns, so the observed alert is of the same class; the
rejection itself is real and confirmed (the client never
authenticates), only the alert text does not distinguish "no
certificate" from "wrong CA certificate" in these cases -- behavior
of `crypto/tls` itself, not a bug in this implementation.

**4. Interoperability matrix, 5x5 (+1 critical row), executed now,
locally -- long format, with the requested "effective AND protection"
column:**

| Client | Server | Success/Failure | Reason | Downgrade (DualAuthenticated) | Effective AND protection |
|---|---|---|---|---|---|
| Classical | Classical | SUCCESS | correct group/cert (CurveP384) | n/a | n/a (does not involve AND) |
| Classical | PQC | FAILURE | incompatible group (handshake failure) | no (never authenticated) | n/a |
| Classical | Hybrid-v8 | FAILURE | incompatible group (handshake failure) | no | n/a |
| Classical | Hybrid-AND strict | FAILURE | no Dual, server requires it (handshake failure) | no | **YES -- blocked a client with no PQ material** |
| Classical | Hybrid-AND non-strict | FAILURE | incompatible group, never even gets to test the Dual (handshake failure) | no | not applicable (failed for another reason first) |
| PQC | Classical | FAILURE | incompatible group (handshake failure) | no | n/a |
| PQC | PQC | SUCCESS | correct group/cert (MLKEM1024) | n/a | n/a |
| PQC | Hybrid-v8 | FAILURE | incompatible group (handshake failure) | no | n/a |
| PQC | Hybrid-AND strict | FAILURE | no Dual, server requires it (handshake failure) | no | **YES** |
| PQC | Hybrid-AND non-strict | FAILURE | incompatible group (handshake failure) | no | not applicable |
| Hybrid-v8 | Classical | FAILURE | incompatible group (handshake failure) | no | n/a |
| Hybrid-v8 | PQC | FAILURE | incompatible group (handshake failure) | no | n/a |
| Hybrid-v8 | Hybrid-v8 | SUCCESS | correct group/cert (SecP384r1MLKEM1024) | n/a | n/a (its own X.509 gate, not the TLS Dual) |
| Hybrid-v8 | Hybrid-AND strict | FAILURE | no Dual, server requires it (handshake failure) | no | **YES** |
| Hybrid-v8 | Hybrid-AND non-strict | FAILURE | group matches, but Hybrid-v8's classical CA is not trusted by Hybrid-AND (`signed by unknown authority`) | no | **YES, but via classical chain verification, not specifically by the Dual mechanism** (see note) |
| Hybrid-AND strict | Classical | FAILURE | incompatible group (handshake failure) | no | n/a |
| Hybrid-AND strict | PQC | FAILURE | incompatible group (handshake failure) | no | n/a |
| Hybrid-AND strict | Hybrid-v8 | FAILURE | group matches, but Hybrid-AND's ML-DSA CA does not exist in Hybrid-v8 (handshake failure) | no | n/a (not a test of the AND mechanism, it's chain incompatibility) |
| Hybrid-AND strict | Hybrid-AND strict | SUCCESS | both chains valid | **no -- `DualAuthenticated=true`, no downgrade** | **YES -- real dual proof of possession** |
| Hybrid-AND strict | Hybrid-AND non-strict | SUCCESS | both chains valid (client offered Dual, server accepted even without requiring it) | **no -- `DualAuthenticated=true`** | **YES -- non-strict did not make anything WORSE here, it just would not have STOPPED a weaker client** |
| Hybrid-AND non-strict | Classical | FAILURE | incompatible group (handshake failure) | no | n/a |
| Hybrid-AND non-strict | PQC | FAILURE | incompatible group (handshake failure) | no | n/a |
| Hybrid-AND non-strict | Hybrid-v8 | FAILURE | incompatible classical CA (`signed by unknown authority`) | no | n/a |
| Hybrid-AND non-strict | Hybrid-AND strict | SUCCESS | both chains valid | **no -- `DualAuthenticated=true`** | **YES** |
| Hybrid-AND non-strict | Hybrid-AND non-strict | SUCCESS | both chains valid | **no -- `DualAuthenticated=true`** | **YES, but by coincidence -- the client OFFERED the Dual even without needing to** |
| **RSA-only (attacker), no Dual** | Hybrid-AND strict | FAILURE | server requires Dual, client does not offer it (handshake failure) | no (never authenticated) | **YES -- blocked** |
| **RSA-only (attacker), no Dual** | **Hybrid-AND non-strict** | **SUCCESS (at the TLS layer)** | **server does not require Dual -- accepts the isolated classical chain** | **YES -- authenticated with `DualAuthenticated=false`, WITHOUT proving ML-DSA-65 possession** | **NO -- vulnerable, see critical finding below** |

**Critical finding, extra row (was not part of the original 5x5
matrix, added because it is exactly what "effective AND protection"
needs to answer): an attacker with ONLY the RSA key (no PQ material
at all, `Dual=nil` on the client) was ACCEPTED, at the pure TLS layer,
by the NON-STRICT Hybrid-AND server.** Confirmed directly, with no
interpretation needed: the client's own `Handshake()` returned
success --
`curve=SecP384r1MLKEM1024 dualAuthenticated=false` -- a full, valid
TLS authentication, WITHOUT ever proving possession of the ML-DSA-65
key.
**This is, literally, the same vulnerability that v8's real Hybrid
has and that this entire project exists to close** -- only now
reproduced and confirmed live inside the Dual mechanism itself, in
the mode that leaves it off. The connection just did NOT end up being
served because MY test gateway (`measure` mode) has a second check,
at the APPLICATION layer (not the TLS protocol), that closes any
`hibrido-and` connection with `DualAuthenticated=false`
regardless of the configured `Require` -- an extra defense I wrote
for the test harness, NOT a property of the Dual mechanism itself. A
real deployment that configured `Dual.Require=false` without this
additional check would be genuinely vulnerable. **This definitively
confirms, now measured (not just argued), why strict mode is
mandatory -- it is not a design preference, it is the only
configuration in which the dual-proof-of-possession guarantee
actually exists in the protocol.**

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 20. Revised T7: items (e)/(f)/(g) with concrete, pre-registerable numbers -- Hybrid-AND's size factor corrected (1,4x Hybrid-v8, +11% over PQC, not "almost 2x" as I had written). DRAFT, not approved, no tag created.

**(e) Pilot tolerance for reproducing the per-message sizes --
calculated, not assumed.** I regenerated the certificates with SANs
of the real size an AWS instance would have (EC2 public/private DNS,
`sa-east-1`, e.g., `ec2-18-230-105-42.sa-east-1.compute.amazonaws.com`/
`ip-10-0-1-134.sa-east-1.compute.internal`, plus 5 internal names
following the same pattern as the current default, just longer) and
measured the REAL difference against Decision 14/15's loopback
baseline, across the 4 profiles:

| Profile | Certificate (loopback) | Certificate (realistic AWS SAN) | Delta |
|---|---|---|---|
| Classical | 1.640 B | 1.876 B | **+236 B** |
| PQC | 10.878 B | 11.114 B | **+236 B** |
| Hybrid-v8 | 8.552 B | 8.786 B | **+234 B** |
| Hybrid-AND | 12.177 B | 12.649 B | **+472 B** (2x the single-chain delta -- both chains carry the same SAN) |

Confirmed that ServerHello/EncryptedExtensions/CertificateVerify/
Finished came out at EXACTLY the same size in both rounds -- these
four never carry any name. **Correction after Luciano's review:
"0B outside the Certificate" was wrong for the ClientHello -- it
carries the SNI, and my proxy currently fixes `ServerName: "mtls"` (4
characters) REGARDLESS of the real destination (the same convention
the real `tls_kem_proxy` already uses, on purpose, to keep the lab's
ClientHello comparable -- see the original comment in
`tls_kem_proxy/main.go`). In a real campaign, the SNI would carry the
server's real name, not "mtls".**

**ClientHello, calculated with a name of length equivalent to the
real one:**

| Name (example) | Length | Delta vs. `"mtls"` (4 ch.) |
|---|---|---|
| EC2 private DNS (`ip-10-0-1-134.sa-east-1.compute.internal`) | 40 ch. | **+36 B** |
| EC2 public DNS (`ec2-18-230-105-42.sa-east-1.compute.amazonaws.com`) | 49 ch. | **+45 B** |

The SNI extension has only ONE variable-size field (the hostname
itself); the rest of the extension (type, lengths) is fixed, so the
delta in the ClientHello is exactly `len(real_name) - 4`, with no need
to reconstruct the entire message to confirm it. A campaign inside the
same VPC typically uses the PRIVATE DNS between instances -- **central
estimate: +36 B**; **proposed tolerance: ±15 B** (covers the variation
among AWS region codes of different length, e.g. `sa-east-1`
(9 ch.) vs `ap-southeast-2` (14 ch.), plus 1-3 extra digits per IP
octet embedded in the name -- it does NOT cover the difference between
private and public DNS, which is structural, not noise: **if the real
campaign uses PUBLIC DNS instead of private, the central estimate
changes to +45B, it is not just a matter of tolerance** -- recorded
for Luciano to decide which DNS the real campaign will use, before
the pilot.

**New deployment-dependent field found, verified in Go's source code:
`CertificateRequest` carries
`certificate_authorities` (list of Subject DN for each CA in
`ClientCAs`, `handshake_server_tls13.go:862`,
`certReq.certificateAuthorities = c.config.ClientCAs.Subjects()`) --
structurally deployment-dependent (it could vary if the CA's name
changed per environment). **For v9 specifically, 0B of tolerance
STILL holds here** because the generator (`certs/main.go`) uses a
FIXED `CommonName` for the CA ("classico_ca" etc.), hardcoded in the
code, not parameterized by `-server-dns`/`-server-ips` nor by
environment -- confirmed by reading the generator, not assumed. If
the CA ever comes to have a deployment-dependent name (e.g.,
including the region), this field would need tolerance too; today it
does not.

**No other field found with a deployment dependency.** SAN IPs
(present both in the certificate and in principle relevant here) do
NOT contribute additional variability: an IP SAN is encoded as a
FIXED-size OCTET STRING per address family (4B IPv4, 16B
IPv6), never as text -- swapping `127.0.0.1`/`::1` (1 IPv4 + 1 IPv6)
for 2 real IPv4 addresses was already INCLUDED in my earlier
measurement of the `Certificate` delta (+236/+234/+472B), it is not a
separate term.

**Final tolerance table, per message:**

| Message | Deployment-dependent? | Tolerance |
|---|---|---|
| ClientHello | Yes (SNI) | **±15 B** around +36B (private DNS) -- recalculate the central estimate if the campaign uses public DNS |
| ServerHello | No | 0 B |
| EncryptedExtensions | No | 0 B |
| CertificateRequest | Structurally yes, in practice no (CA with a fixed name in v9's generator) | 0 B |
| Certificate (server) | Yes (SAN) | **±50 B** around the measured delta (+236/+234/+472B per profile) |
| CertificateVerify | No | 0 B |
| Finished | No | 0 B |
| Certificate (client) | No (the client's identity is fixed, "opin-client-one", not tied to the physical deployment) | 0 B |

**(f) Residue formula, with the components, each one's origin, and
the guard for routes with a small Δ:**

```
route_residue = (Δ_observed_latency - Σ Δ_measured_components) / Δ_observed_latency
```

**Criterion, with the requested guard:**

```
valid if: |residue_absolute| <= max(0.10 * |Δ_observed|, half_width_CI95(Δ_observed))
```

Without the guard, a route where the observed Δ between two profiles
is small (e.g., 0ms, where the Classical-PQC difference might be just
a few ms) would turn the 10% relative criterion into an absurdly
tight threshold (10% of a small number is an even smaller number,
smaller than the measurement noise itself) -- rejecting as "high
residue" a route where there actually is not enough data to tell
residue apart from noise. The guard accepts the route even with
`|residue| > 10%` IF that absolute residue is smaller than the
measurement's own statistical uncertainty -- that is, smaller than
what the natural noise of the 30 runs would already explain by
itself.

**Confidence-interval method: percentile bootstrap, B=10.000
resamplings, over each profile/route's 30 runs.** For each
route: (1) compute `Δ_observed` = difference of the means (or
medians, to be decided based on the real distribution's shape -- this
thesis has already documented bimodality in at least one real
incident, Decision 98/99 of v8, so the mean-vs-median choice is not
trivial and must be decided by looking at the real data before the
pilot, not assumed here);
(2) resample with replacement the 30 runs of EACH profile, B=10.000
times, recomputing `Δ` on each resampling; (3) `half_width_CI95`
= (97,5th percentile - 2,5th percentile of the 10.000 resamplings) / 2.
Bootstrap (non-parametric) chosen specifically because of this
already-documented bimodality -- a CI based on assumed normality
would be the wrong method for a distribution that the thesis itself
has already shown is not normal in some cases.

| Component (Δ between profiles) | Origin/decision that measures it |
|---|---|
| Δ handshake bytes x transmission time (not extra RTT -- Decision 14 already rules out extra RTT under initcwnd=10) | Decision 14/15 (per-message table, real bytes per profile) |
| Δ signing/verification CPU (RSA-2048, ML-DSA-65) | `bench` (Decision 14) |
| Δ KEX CPU (ECDH P-384, ML-KEM-1024) | `bench` (Decision 14) |
| Δ session ticket cost, IF on (does not apply to v9's default, tickets off -- Decision 13) | Decision 14 (diagnostic mode) |
| Δ HTTP processing time per call (durationMs from the access log) | T6b (Decision 17/18), the gateway's `access log` |
| Δ fixed network time for the full flow (RTT x number of REAL round trips in the flow, not just the handshake -- 44 calls, not 1) | TO BE MEASURED in the pilot -- does not exist locally yet, the full flow only runs at 0ms |

**Not closed out here:** the first 2 groups (handshake+CPU) have a
local number; the last one (full-flow network, 44 real calls) only
exists with real latency, it requires the pilot. The formula and the
criterion are pre-registered; the reckoning itself cannot be closed
out in local Phase 1.

**(g) Pilot and official campaign, explicitly separated, with N,
routes, and estimated time for each -- and the corrected size
factor:**

**Size-factor correction** (my earlier draft said "almost 2x
Hybrid-v8" -- WRONG). Using the real total measured per handshake
(server+client, Decision 14, loopback baseline): Hybrid-v8 =
8.552+8.397 = **16.949 B**; PQC = 10.878+10.728 = **21.606 B**;
Hybrid-AND = 12.177+11.902 = **24.079 B**. Hybrid-AND / Hybrid-v8 =
24.079/16.949 = **1,42x** (≈1,4x, not ≈2x); Hybrid-AND / PQC =
24.079/21.606 = **1,1145** (**+11,45%**, ≈+11%). All three numbers
match exactly what Luciano had already calculated independently.

**Official campaign, CORRECTED in Decision 21 -- "6 routes" was
wrong.** Real v8 uses **8 routes** (not 6: `sa-east-1` L0/L123/L219/
L325, `us-east-1` L0/L14, `ap-northeast-1` L0/L30 -- see Decision 21,
point 2, for the full reconciliation). 4 profiles x **8 routes** x
N=30 = **960 combined runs -- exactly Luciano's number**,
not the 720 I had calculated with the wrong route list.

**Pilot, SMALLER, aimed at validation/calibration, not statistical
power, routes corrected to use v8's REAL names:**

| Item | Pilot | Official campaign |
|---|---|---|
| Profiles | 4 (Classical, PQC, Hybrid-v8, Hybrid-AND **strict**) | the same 4 |
| Routes | **3**: `sa-east-1/L0` (control), `sa-east-1/L219` (middle), `sa-east-1/L325` (the most distant across all of v8) | the full **8** |
| N per profile/route | **5** | 30 |
| Combined runs | 4 x 3 x 5 = **60** | 4 x 8 x 30 = **960** |

**What the pilot needs to prove, explicitly, before authorizing the
campaign (each one is a go/no-go criterion, not just a collection):**
1. **Per-message sizes** meet item (e)'s tolerance -- needs
   1 full capture (pcap+keylog) per profile per route, not all 5
   runs instrumented that way (3 routes x 4 profiles = 12
   captures, reusing Decision 14's mechanism).
2. **Real initcwnd** of the instances confirmed (`ss --info` or
   equivalent) -- once per instance TYPE used (server,
   client), not per run.
3. **Distant routes work with no error** -- 0 errors across the 5
   runs of each profile on the `sa-east-1/L325` route specifically
   (325ms, the most demanding across all of v8).
4. **Counts (44/6/28/4/4) reproduce outside localhost**, under real
   network, not just under local `tc`/`netem`.
5. **Zero errors across the 60 runs** -- go/no-go criterion for the
   official campaign; any error needs to be diagnosed and
   fixed before authorizing the full 960 runs.

**Pilot's estimated time (estimate, not measured -- deliberately wide
range):** each combined run (insurance+person, 44 HTTP calls) locally,
with no real network latency, takes a few seconds;
at 325ms of real RTT (`sa-east-1/L325`), a rough estimate (44 calls x ~1 RTT
each of pure latency, plus 6 handshakes x ~2 RTT each) adds up to
something like +15-20s of network latency alone per run
on that route -- **10-30s
per run**, depending on the route, variance not measured. 60 runs
at that range: **10-30 minutes of pure execution**. Plus real
overhead, historically relevant in this thesis (client profile/region
switch, settling runs, possibly creating/destroying the client's EC2
instance per route if not pre-created): 4 profiles x 3 routes = 12
configuration switches, each historically taking minutes
(the real `switch_crypto_profile.py`: ~1-2min of settling alone, not
counting Terraform if the instance needs to be recreated) -- **+30-60
minutes of
overhead**. **Estimated total: ~1 to 1,5 hours**, wide range because
none of this has been measured yet (and that is exactly what the
pilot measures, not something knowable without running it).

**The official campaign's N=30: anchored in precedent, not a new
power calculation** (no change this round) -- keeps the same caveat
already recorded: a formal power calculation using v7/v8's real
per-route variance is an additional step not done here, if Luciano
wants it before locking in N=30 for Hybrid-AND specifically.

**Design to stress the distant routes, official campaign:**
repeat the 4 profiles across ALL 8 routes (not just the slowest) with
N=30, so that the residue (item f, with the CI95 guard) can be
calculated route by route -- a residue that grows with the route
would be the signal that an RTT-dependent component is missing from
item (f)'s list.

---

**Full, revised T7, for Luciano's approval -- no tag
created:**

**(a)** Full flow, v8's counts, zero errors -- **CLOSED**
(Decision 17/18: 44/6/28/4/4, 0 errors, 4 profiles).

**(b)** v8's five validity gaps:
1. RSA-4096->2048 -- **CLOSED**
2. Client did not verify the server -- **CLOSED** (Decision 19, negative
   tests (iii-a)/(iii-b), 4 profiles)
3. Server with optional client certificate -- **CLOSED**
   (Decision 19, negative tests (i)/(ii), 4 profiles, and (iv) for
   Hybrid-AND specifically)
4. Contaminated counter -- **CLOSED**
5. Per-message size and residue -- **PARTIAL**: per-message size
   closed (Decision 15, now with the tolerance calculated in item (e)
   above); residue formula and criterion pre-registered (item (f)
   above), the reckoning itself pending the pilot

**(c)** CurveID/DualAuthenticated -- **CLOSED**.

**(d)** Interoperability matrix -- **CLOSED**, two distinct matrices,
not conflated: "measurement configuration" (Decision 19,
5x5 + the RSA-only attacker's critical row, group/CA restricted per
profile as T5 always used) and "interoperability configuration"
(Decision 21, shared CA + all groups, answers the SAD §3.4 metric --
confirms that a migrated classical party DOES communicate when the
configuration allows it, and that the RSA-only attacker's downgrade
also persists under shared trust).

**(e)** Pilot reproduces local sizes + real initcwnd -- tolerance
PER MESSAGE now defined and calculated (not assumed): ±15B on the
ClientHello (SNI, around the expected +36B with private DNS), 0B on
ServerHello/EncryptedExtensions/CertificateRequest/CertificateVerify/
Finished/client-Certificate, ±50B on the server's Certificate (SAN)
-- **PENDING execution**, depends on AWS.

**(f)** 90% of the residue attributed -- formula with the CI95 guard
(bootstrap, B=10.000, over the 30 runs) for routes with small Δ,
pre-registered above -- **PENDING execution**, depends on real
latency/full flow with real RTT.

**(g)** Pilots designed for distant routes -- **CLOSED** (routes
reconciled, Decision 21): pilot (60 runs, 4 profiles x 3 real v8
routes, including `sa-east-1/L325` the most distant, x N=5,
~1-1,5h estimated) SEPARATE from the official campaign (960 runs, 4
profiles x **8 real v8 routes** x N=30 -- "960" confirmed exact,
"6 routes" was my own error, corrected); corrected size factor
(1,4x/+11%); **7 go/no-go criteria** with an explicit numerical
threshold (5 original + full instrumentation + latency sanity,
Decision
21, point 4, revised this round) and a post-tag amendment policy
recorded -- execution itself **PENDING**, depends on AWS.

**(h)** Equivalence checklist -- **kept**, plus the entries from
Decisions 17-19 (opin_flow.py edited additively; no optional-certificate
carve-out in v9; internal carve-out documented).

**No `v9-prereg` tag created. Awaiting Luciano's explicit approval.**

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 21. Interoperability matrix v2 (configuration separated from measurement), v8's 8 real routes reconciled (960 confirmed, 6 was wrong), client SAN confirmed fixed, 5 pilot criteria with a numerical threshold

**1. Matrix v2, "interoperability configuration" -- shared CA
(RSA-2048 and ML-DSA-65, one of each, used by ALL 6 modes),
all 3 KEX groups offered on both sides, never used for
measurement (only for this test).** Built from scratch in
`thesis/results/v9/integration/interop/` (new, single process,
certificates generated in memory, nothing on disk). Methodological
finding along the way: the first version had both the server AND the
client read with the SAME 2s deadline after the handshake -- a race
(whoever closed first decided the result), which made even
strict-against-strict (which has to succeed) fail by luck half the
time. Fixed by having the server WRITE a confirmation byte instead of
reading -- no race, identical result across 3 repeated rounds.

| Client | Server | Result | Reason | Server->client auth | Client->server auth | DualAuthenticated | Effective AND protection |
|---|---|---|---|---|---|---|---|
| Classical | Classical | SUCCESS | group=SecP384r1MLKEM1024 | RSA | RSA | false | no |
| Classical | PQC | SUCCESS | group=SecP384r1MLKEM1024 | ML-DSA | RSA | false | no |
| Classical | Hybrid-v8 | FAILURE | `bad certificate` -- missing AltSignatureValue | -- | -- | -- | -- |
| Classical | Hybrid-AND strict | FAILURE | `handshake failure` -- no Dual | -- | -- | -- | -- |
| Classical | Hybrid-AND non-strict | SUCCESS | group=SecP384r1MLKEM1024, Dual not used | RSA | RSA | false | no |
| PQC | Classical | SUCCESS | group=SecP384r1MLKEM1024 | RSA | ML-DSA | false | no |
| PQC | PQC | SUCCESS | group=SecP384r1MLKEM1024 | ML-DSA | ML-DSA | false | no |
| PQC | Hybrid-v8 | FAILURE | `bad certificate` -- missing AltSignatureValue | -- | -- | -- | -- |
| PQC | Hybrid-AND strict | FAILURE | `handshake failure` -- no Dual | -- | -- | -- | -- |
| PQC | Hybrid-AND non-strict | SUCCESS | group=SecP384r1MLKEM1024, Dual not used | RSA | ML-DSA | false | no |
| Hybrid-v8 | Classical | SUCCESS | group=SecP384r1MLKEM1024; X.509 gate present but NOT verified (Classical has no VerifyPeerCertificate) | RSA | RSA+altML-DSA (X.509, not verified here) | false | no |
| Hybrid-v8 | PQC | SUCCESS | same, PQC also does not verify the gate | ML-DSA | RSA+altML-DSA (X.509, not verified here) | false | no |
| Hybrid-v8 | Hybrid-v8 | SUCCESS | X.509 gate VERIFIED (the Hybrid-v8 server always verifies it) | RSA+altML-DSA (X.509, not verified by the client -- see note) | RSA+altML-DSA (X.509, verified) | false | no |
| Hybrid-v8 | Hybrid-AND strict | FAILURE | `handshake failure` -- the X.509 gate is not the TLS Dual, the server never sees a Dual offer | -- | -- | -- | -- |
| Hybrid-v8 | Hybrid-AND non-strict | SUCCESS | group=SecP384r1MLKEM1024, Dual not used, X.509 gate NOT verified (this server has no VerifyPeerCertificate) | RSA | RSA+altML-DSA (X.509, not verified here) | false | no |
| Hybrid-AND strict | Classical | FAILURE | `handshake failure` -- server without Dual, strict client requires it | -- | -- | -- | -- |
| Hybrid-AND strict | PQC | FAILURE | `handshake failure` | -- | -- | -- | -- |
| Hybrid-AND strict | Hybrid-v8 | FAILURE | `handshake failure` -- the X.509 gate is not the TLS Dual | -- | -- | -- | -- |
| Hybrid-AND strict | Hybrid-AND strict | **SUCCESS** | both chains valid | **dual (RSA+ML-DSA)** | **dual (RSA+ML-DSA)** | **true** | **YES** |
| Hybrid-AND strict | Hybrid-AND non-strict | **SUCCESS** | both chains valid | **dual (RSA+ML-DSA)** | **dual (RSA+ML-DSA)** | **true** | **YES** |
| Hybrid-AND non-strict | Classical | SUCCESS | group=SecP384r1MLKEM1024, Dual not used (peer has no Dual) | RSA | RSA | false | no |
| Hybrid-AND non-strict | PQC | SUCCESS | group=SecP384r1MLKEM1024, Dual not used | ML-DSA | RSA | false | no |
| Hybrid-AND non-strict | Hybrid-v8 | FAILURE | `bad certificate` -- missing AltSignatureValue (the AND's pure classical certificate does not satisfy Hybrid-v8's X.509 gate) | -- | -- | -- | -- |
| Hybrid-AND non-strict | Hybrid-AND strict | **SUCCESS** | both chains valid | **dual (RSA+ML-DSA)** | **dual (RSA+ML-DSA)** | **true** | **YES** |
| Hybrid-AND non-strict | Hybrid-AND non-strict | **SUCCESS** | both chains valid (both offered, neither required) | **dual (RSA+ML-DSA)** | **dual (RSA+ML-DSA)** | **true** | **YES** |
| **RSA-only (impostor)** | **Hybrid-AND strict** | **FAILURE** | `handshake failure` -- server requires Dual, impostor does not offer it | -- | -- | -- | -- |
| **RSA-only (impostor)** | **Hybrid-AND non-strict** | **SUCCESS** | group negotiated, but WITHOUT Dual | RSA | **RSA (classical only)** | **false** | **NO -- downgrade confirmed again, under shared trust** |

**Explicitly requested records:**

1. **Every client in this configuration offered every signature
   scheme, including ML-DSA-65** -- no config in this matrix (either
   before or now) explicitly sets `Config.SignatureSchemes`, in any
   mode; this toolchain's Go announces the complete DEFAULT list in
   the ClientHello's `signature_algorithms`, which already includes
   ML-DSA-65 natively (confirmed indirectly: the PQC/Hybrid-v8/Hybrid-AND
   profiles only work because this signature is in the default, it
   never needed an explicit opt-in in either harness). The Dual
   scheme (`0xFE65`) is the ONLY one that ONLY appears when
   `Config.Dual` is actually configured -- that one really is an
   opt-in, not the default.
2. **Hybrid-v8's server X.509 gate refuses any client without
   `AltSignatureValue`, ALWAYS, regardless of who the client is** --
   confirmed in the 2 rows `Classical -> Hybrid-v8` and `PQC ->
   Hybrid-v8`, both `FAILURE`, the exact same error (`bad certificate --
   missing AltSignatureValue`), even though Classical and PQC are
   completely different identities (RSA vs. pure ML-DSA) -- the gate
   does not distinguish WHO is missing the extension, only that it is
   missing.
   **Additional finding, not requested but relevant:** this gate is
   ASYMMETRIC -- only the Hybrid-v8 SERVER verifies it (via
   `VerifyPeerCertificate`); no CLIENT in this matrix, including
   Hybrid-v8 itself acting as a client, verifies the alternative
   signature on the server side. A "fake" Hybrid-v8 server (valid
   RSA, no AltSignatureValue) would fool a Hybrid-v8 client without
   being detected -- recorded here, not fixed (outside this round's
   request).

**Positive finding from SAD §3.4 (classical and migrated clients DO
COMMUNICATE, when the configuration allows it):** Classical<->PQC
succeeds in both directions -- each side presents its own certificate
type (RSA or ML-DSA), verified by the other side's SHARED trust pool.
Hybrid-v8 interoperates with ALL other 4 modes except strict
Hybrid-AND (its own X.509 gate is an INDEPENDENT protection from the
TLS Dual -- it rejects pure Classical/PQC the same way the Dual would,
but through a different mechanism, not interoperable with the Dual).

**2. v8's routes, reconciled -- "6" was wrong, that was the simulated
v7 (`tc`/`netem`), not the real v8.** Real v8 uses **8 routes**
(not 6), confirmed directly in `v8/DECISIONS.md`: `sa-east-1` -> L0,
L123, L219, L325 (4 levels); `us-east-1` -> L0, L14 (2); `ap-
northeast-1` -> L0, L30 (2). **8 routes x 3 profiles x 30 N = 720
runs (real v8).** v9, with its 4th profile: **8 routes x 4 profiles x
30 N = 960 -- exactly Luciano's number, now reconciled.**
Fixed: v9's official campaign uses the SAME 8 routes as v8, not 6
generic ones.

**Pilot, routes adjusted to include v8's most distant one:**
`sa-east-1/L0` (control, co-located), `sa-east-1/L219` (middle), **`sa-
east-1/L325`** (the most distant across all of v8, 325ms -- the one
the request explicitly demanded). Kept within the SAME client region
(`sa-east-1`) to isolate only the distance variable, not also the
region variable -- the official campaign is what covers all 3
regions.
Pilot: **4 profiles x 3 routes x N=5 = 60 runs** (unchanged in
number, only the routes changed from generic to real).

**3. Client certificate SAN -- confirmed fixed, not parameterized by
deployment, by convention (not by technical impossibility).**
`certs/main.go` DOES have a `-client-dns` flag (default
`"opin-client-one"`) -- TECHNICALLY parameterizable, just like
`-server-dns`. But the generator's own comment documents the intent:
`"identity, not network hostname"` -- in other words, by design,
the client's SAN represents a stable LOGICAL IDENTITY (the OPIN
participant "client one"), not a physical network address, and
should NOT vary depending on which EC2 instance runs the client in
each route/region of the pilot or the campaign. Also confirmed that
the client certificate never receives `IPAddresses` (this field is
only set for `ExtKeyUsageServerAuth`, never for `ClientAuth`, in the
generator functions). **The 0B tolerance on the client's Certificate
remains correct**, under the current convention -- explicitly
recorded that this is a DESIGN CHOICE, not a structural guarantee: if
the real deployment ever comes to use a different `-client-dns` per
instance, this tolerance would need to be revisited.

**4. The pilot's 7 go/no-go criteria (5 original + 2 new ones
requested this round), with an explicit numerical threshold (without
that, none of them is a criterion, only an intention). ANY failure of
ANY of the 7 blocks authorization of the 960-run campaign:**

| # | Criterion | Numerical threshold |
|---|---|---|
| 1 | Per-message sizes within tolerance (Decision 20, item e) | **100%** of captures (4 profiles x 3 routes = 12 captures) within ±15B on the ClientHello and ±50B on the server's Certificate; 0B on the remaining messages |
| 2 | Real initcwnd confirmed | **>= 10 segments** (what Decision 14 assumed without measuring); if lower, the extra-RTT analysis needs to be redone before authorizing the campaign |
| 3 | Zero errors on the most distant route | **0 errors in 20/20 runs** (4 profiles x N=5) on the `sa-east-1/L325` route specifically |
| 4 | Counts match exactly under real network | **44 HTTP calls, 6 client-facing mTLS connections, 28 JWTs, 4 /jwks, 4 CA -- exact (0 tolerance) in 60/60 runs** |
| 5 | Zero overall errors | **0 errors in 60/60 combined runs** |
| 6 | Full instrumentation, across all 60/60 | **keylog + capture + per-message sizes successfully extracted in 100% of the 60 runs** (not just the 12 captures of criterion 1 -- here it is every pilot run); **`ConnectionState.CurveID` (profile's expected group) and `DualAuthenticated` (Hybrid-AND) assertions passing in 60/60, 0 failures** |
| 7 | Per-route latency sanity | **measured RTT of each of the pilot's 3 routes within ±10% of nominal** (e.g., `sa-east-1/L325` nominal 325ms -> acceptable 292,5-357,5ms); a route outside this range invalidates the measurements of THAT route specifically, not the others |

**Criterion amendment, after the `v9-prereg` tag: requires a new,
dated decision, with a reason -- never an edit to the original text.**
Any change to one of the 7 criteria above (threshold, method, route,
N) AFTER the tag exists requires a new numbered entry in this same
file (`DECISIONS.md`), with explicit date and reason, leaving the
original text of the 7 criteria intact, visible, never overwritten --
the history of WHICH criterion was in force WHEN needs to stay
traceable, even if a criterion is revised later.

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 22. T8 (local part), full equivalence checklist with v8; PKI procedure fixed (single issuance, distribution via scp); destruction procedure fixed (Resource Groups Tagging API + auto-shutdown); 7-criteria evaluator written and tested (3 real bugs found and fixed); Go binary SHA-256; Hybrid-v8 limitation recorded

**1. T8, full equivalence checklist with v8.** I looked up
`v8/DECISIONS.md` directly for each item (did not rely on memory --
the "6 routes" error of the previous round was exactly that).

| Item | v8 (real) | v9 (Phase 1 / planned) | Status |
|---|---|---|---|
| Instance types | `t4g.micro` (control, arm64); `m7i-flex.large` (server and clients, x86_64, 2 vCPU/8GiB) -- confirmed directly in v8's real `terraform.tfstate.backup` (`server_client_instance_type`=`m7i-flex.large` on 11 instances, `control_instance_type`=`t4g.micro` on 1), not just in DECISIONS.md prose | the SAME types (config literals, do not depend on AWS to be specified) | **SAME, by decision -- verifiable and verified NOW** (the type is a config string; only the exact ID of the resolved AMI remains NOT VERIFIABLE WITHOUT AWS, own row below) |
| Regions and routes | 8 real routes: `sa-east-1` L0/L123/L219/L325, `us-east-1` L0/L14, `ap-northeast-1` L0/L30 -- REAL latency from geographic distance, not simulated | the SAME 8 routes (Decision 21) | **SAME**, by decision |
| How L0/L219/L325 are produced | L0 = client co-located in the SAME region/AZ as the server (minimal but non-zero real network latency); the others = client on an instance actually deployed in ANOTHER region/distance, real IP-path latency, never `tc`/`netem` | identical, same logic (reuses v8's infrastructure) | **SAME**, by decision -- **NOT VERIFIABLE WITHOUT AWS** whether the RTT actually comes out at the nominal values (that is the pilot's criterion 7) |
| AMI | Amazon Linux 2023 (AL2023), specific AMI resolved via `data "aws_ami"` (`al2023-ami-*-kernel-*`, `most_recent=true`) -- real IDs have already become stale (the AMI changes over time) | same source (`data "aws_ami"`, same filter) | **SAME by construction** (same resolution mechanism); the exact ID will be different, by design (`most_recent`) -- **NOT VERIFIABLE WITHOUT AWS** which exact ID comes out in the pilot |
| OS and kernel | AL2023; the exact kernel version (`uname -r`) was NEVER pinned in text in `v8/DECISIONS.md` -- only captured as metadata, never compared to an expected value | same practice (capture, do not pin) | **NOT VERIFIABLE WITHOUT AWS** -- not even v8 has a fixed value to compare against, so "same" here means "same AMI/family," not "same kernel number byte for byte" |
| Go | `golang:1.27-rc` (release candidate) | `go1.27.3`, compiled from source, commit verified (`2aae1000...`) | **DELIBERATE DIVERGENCE**, already recorded (Decision 3): 1.27.3 is stable, has a security fix in `crypto/x509` that 1.27rc2 does not have, and is the version the AND patch has already been validated against |
| Node.js | `node:24-alpine` (Node 24), pinned in `mock_as`'s real Dockerfile | the SAME -- T6b reuses `mock_as` with no alteration at all | **SAME**, confirmed (no backend Dockerfile was touched) |
| MongoDB | `mongo:latest@sha256:dc28ed...` | the SAME -- T6b reuses the real `mongodb` with no alteration | **SAME**, confirmed |
| initcwnd | never measured in v8 (v9's own Decision 14 assumes 10, without measuring) | same assumption, now a formal pilot criterion (#2) | **NOT VERIFIABLE WITHOUT AWS** -- becomes an item on the pilot's checklist |
| Congestion control algorithm (cubic/bbr) | never checked anywhere, not even in v8 | same | **NOT VERIFIABLE WITHOUT AWS** -- **NEW item on the pilot's checklist**, did not exist before |
| Slow start after idle (RFC 2861) | never checked | same | **NOT VERIFIABLE WITHOUT AWS** -- **NEW item on the pilot's checklist**, relevant because the pilot has gaps between runs (settling, profile switch) |
| MTU | REAL: NIC with jumbo frames (9001) on the instances, but the real PATH MTU (internet/VPC between regions) is 1500 -- this already caused a real bug in v8 (large PQC/Hybrid certificates fragmented across multiple TCP segments, the pcap had to be reassembled) | same infrastructure, SAME RISK expected | **NOT VERIFIABLE WITHOUT AWS**, but **ALREADY KNOWN RISK, recorded for the pilot**: criterion 1's capture (per-message sizes) needs to correctly reassemble large certificates (PQC 5.632B, Hybrid-AND 6.582B) fragmented by a 1500B path MTU -- do not assume 1 segment = 1 message |
| Run order/randomization | profile RANDOMIZED per window (3 windows/day); ROUTE fixed, round-robin, never random, within each window | **TO BE DECIDED**: the pilot is small (60 runs, probably 1 window) -- proposal: profile randomized per run (`random.shuffle`), route in fixed order (L0, L219, L325), replicating v8 on the part that matters (route never random) | **DIVERGENCE BY SCALE, not by design** -- v8 randomizes BETWEEN windows (several per day); the pilot probably only has one |
| Warm-up | 5 runs discarded per profile switch (`SETTLING_WARMUP_RUNS = 5`, `switch_crypto_profile.py`) | the SAME number, reusing the same constant | **SAME**, confirmed in the source, not just recalled |
| Clock synchronization | REAL, verified: Amazon Time Sync (kernel NTP), `chronyc tracking`, measured offsets <1µs, Stratum 2 on every instance | same infrastructure (Amazon Time Sync comes built-in on any AWS instance) -- **NOT YET CONFIRMED FOR V9 SPECIFICALLY** | **NOT VERIFIABLE WITHOUT AWS** -- **NEW item on the pilot's checklist** (confirm `chronyc tracking` on every instance, expected to match v8's pattern since it uses the same infrastructure) |
| Number of runs | 30/profile/route (720 total, 3 profiles x 8 routes) | 30/profile/route too (960 total, 4 profiles x 8 routes); the pilot uses N=5 | **SAME N per cell**; higher total only because of the 4th profile (Decision 21, reconciled) |
| Flow counts | 44 HTTP / 6 client-facing mTLS / 28 JWTs / 4 jwks / 4 CA, per run | the SAME 5 numbers, confirmed across the 4 profiles (Decision 17/18) | **SAME**, empirically verified, not assumed |
| HTTP body and header sizes | defined by the real `mock_as`/`mockapi` | the SAME -- T6b never alters the backend, only the TLS layer | **SAME by construction, NOT compared byte for byte this round** -- honestly recorded as a gap: I did NOT run a byte-for-byte comparison of HTTP bodies/headers between an old v8 run and a new v9 one; the theoretical expectation (same backend, same code) is strong, but it is not the same thing as having measured it |
| JWT algorithms per profile | Classic=PS256 (RSA), PQC=ML-DSA-65, Hybrid=PS256 on the client-to-AS side (see `sign_jwt()`'s docstring) | the SAME for the 3 equivalent profiles (real backend, unaltered); Hybrid-AND uses PS256 (runs with the backend on "classic" on purpose, Decision 17) | **SAME** on the 3 original profiles; **DELIBERATE DIVERGENCE, new profile** for Hybrid-AND (no counterpart exists in v8) |
| Key sizes | Classic/Hybrid RSA-4096; PQC/Hybrid ML-DSA-65 | Classical/Hybrid-v8 RSA-2048 (gap #1, Decision 9/10); PQC/Hybrid-AND ML-DSA-65 (same level) | **DELIBERATE DIVERGENCE**, already recorded |
| Measurement method | `ConnState -> StateActive`, contaminated by the ticket + the start of the 1st request (v8's Decision 78/79, accepted for comparability with v7) | exact `Handshake()` boundary, tickets off by default (Decision 13/14) | **DELIBERATE DIVERGENCE**, already recorded |
| Safety auto-shutdown | REAL, already implemented: systemd timer (`safety_timer.sh.tftpl`), checks a deadline file every 5min, auto-shuts-down (does not destroy) after 48h by default, renewable | reuse the SAME Terraform module, smaller N (see point 3 below) | **SAME mechanism, DELIBERATE DIVERGENCE in N** (48h is excessive for a ~1-1,5h pilot) |

**Items that remain on the pilot's checklist** (not locally
assessable, need real AWS): exact instance types, exact AMI, real RTT
per route, initcwnd, congestion algorithm, slow start after idle,
clock synchronization, and the MTU=1500 fragmentation risk in
criterion 1's capture.

**2. PKI procedure, fixed -- ONE issuance, not one per instance.**

The earlier version was wrong: "each instance generates its own PKI"
would produce DIFFERENT CAs on each side, breaking mutual verification
(exactly the type of error that this same folder's Decision 17 had
already fixed in the local harness -- it should not have come back in
the pilot's procedure). Fixed:

1. The server comes up first, Terraform resolves its real address
   (IP/DNS). Only AFTER that, **a single call** to the generator
   (`certs/main.go`, the same binary already existing, no change)
   with `-server-dns=<real hostname>` `-server-ips=<real IP>`
   `-client-dns=opin-client-one`, run on the OPERATOR's machine
   (inside this session, local scratch) or on an ephemeral control
   instance -- never directly on the server/client instances,
   because neither of the two knows the OTHER's address at its own
   boot time. This call produces, all at once: 1 CA + 1 server +
   1 client PER profile (4 profiles), all with the SAME server/client
   identity, signed by CAs SHARED between both sides -- exactly what
   was missing fixed.
2. **Distribution, via `scp` over the operator's SAME SSH channel**
   (already in use since v8 -- `MOCKOPIN_OPERATOR_SSH_PRIVATE_KEY_FILE`,
   control IP never printed): the server receives the 4 SERVER
   certificates+keys + the public CAs (to validate the clients); the
   client receives the 4 CLIENT certificates+keys + the SAME public
   CAs (to validate the server). `scp`, not SSM Parameter Store --
   simpler, does not put a private key into yet another system (SSM
   would store the key as a SecureString, but it is an extra system
   with its own attack surface; `scp` over a channel that already
   exists adds nothing new to protect).
3. **Cleanup:** the operator's LOCAL copy (this session's scratch) is
   deleted immediately after successful-delivery is confirmed on both
   instances (checksum or simply re-reading the remote file). Each
   instance's copy is deleted at the end of that instance's use -- for
   the client, at the end of its last run before switching
   route/region (or being destroyed); for the server, at the end of
   the entire pilot. No key is ever logged in clear text at any point
   (neither in the `scp` transport, which is encrypted by nature, nor
   in any shell log).

**3. Destruction procedure, fixed -- verification by TAG, not just by
resource type, plus auto-shutdown with a defined N.**

- **Verification by tag, single API call:** `aws resourcegroupstaggingapi
  get-resources --tag-filters Key=Project,Values=mockopin-pqc-v9`
  before AND after every destroy -- covers EVERYTHING that accepts a
  tag in a single call (instances, EBS volumes, network interfaces,
  security groups, key pairs, elastic IPs), unlike real v8, which
  checked type by type (`describe-instances`/
  `describe-security-groups`/`describe-key-pairs`/`describe-volumes`)
  and never specifically checked network interfaces (confirmed by
  searching `v8/DECISIONS.md` -- no hit for
  `describe-network-interfaces` nor for this tagging API). Expected
  **empty** after every destroy; any non-empty result blocks closing
  the session.
- **Auto-shutdown, reusing v8's REAL module** (not reinvented --
  `modules/campaign_instance/templates/
  safety_timer.sh.tftpl`, already tested, already in production
  there): same mechanism (systemd timer, checks a deadline file
  every 5min),
  **N = 4 hours** for the pilot (not v8's default 48h, which is meant
  for a multi-day CAMPAIGN) -- generous margin over the pilot's
  1-1,5h estimate (Decision 20), but short enough to not leave
  anything running all night if the session drops. Auto-shuts-down
  (does not destroy) -- the tag verification above is what confirms
  real destruction, the timer is just the safety net against
  forgetting.

**4. Evaluator for the 7 criteria -- written and tested against real
local data, 3 real bugs found and fixed along the way.**

`thesis/results/v9/integration/evaluate_criteria.py` (new) -- reads
the artifacts that `run_t6.sh` and a T6b round already produce (no
new format invented) and computes criteria 1, 4, 5, and 6 (the ones
Luciano confirmed are locally assessable); 2, 3, and 7 have the logic
written but return `None` (no data) until real pilot artifacts exist.

**Three real bugs found while testing against a real `run_t6.sh` run
+ a real T6b round (not invented data):**
1. The per-profile block slicing stopped at the first `==` it found
   (including ones inside the block itself, like "==
   gateway" or "== tshark: records..."), never reaching the
   per-message size section. Fixed: the slice now runs until the NEXT
   `== Profile:`, not until any `==`.
2. The error check (`FATAL:`) was capturing the `Dockerfile`'s OWN
   text (`echo "FATAL: ..." >&2; exit 1; }`), which Docker reprints
   as a normal part of the build log even on a successful build --
   reporting a false positive on a round that actually passed. Fixed:
   only a `FATAL:` line that does NOT have shell syntax
   (`>&2`/`exit 1`) next to it counts as a real error.
3. The `Certificate` message size was being summed counting the
   SERVER's and the CLIENT's together (both have the same TLS type,
   11) -- nearly doubling the number. Fixed: only count the
   `Certificate` from the frame that ALSO contains `ServerHello`
   (type 2), which is unambiguously the server's flight.

**Result, running against a real local-harness execution (4
profiles, `run_t6.sh` + a real T6b round for the Classical profile):**

```
criterio 1 (tamanhos por mensagem): PASS
criterio 2 (initcwnd real): N/A (sem dados -- precisa do piloto)
criterio 3 (zero erros na rota mais distante): N/A (sem dados -- precisa do piloto)
criterio 4 (contagens do fluxo): PASS
criterio 5 (zero erros): PASS
criterio 6 (instrumentacao completa + asserções): PASS
criterio 7 (sanidade de latencia por rota): N/A (sem dados -- precisa do piloto)
```

**5. Go binary -- SHA-256 computed, reproducibility confirmed.**

```
gateway: fa4c9c32412abab4533bb40e8a45524c149be59e7d10888b00a1895bc0dc4871
proxy:   a4f901a94253aa6bafaf0579518f9487405e3358218db5a9e635d13d55c1d6e9
```

Confirmed reproducible: a full rebuild with `--no-cache` (identical
source, identical toolchain) produced the SAME `gateway` hash,
byte for byte, not just "similar." **Procedure proposed for the
pilot:** build it ONCE (in this session or on an ephemeral control
instance), compute the SHA-256, `scp` the binary (not the source
code, do not rebuild on each instance) to the server and the client
together with a `.sha256` file, and each instance runs `sha256sum -c`
at boot before using the binary -- fails that instance's deploy if
the hash does not match, instead of unknowingly running a potentially
different binary.

**6. Hybrid-v8, limitation recorded -- kept as is, for fidelity to
v8.** Explicitly confirmed (Decision 21, extra finding, now formalized
as a documented profile limitation): **no client in this matrix --
including Hybrid-v8 itself acting as a client -- verifies the
SERVER certificate's alternative signature (`AltSignatureValue`);
only the server verifies the client's.** This is faithful to real
v8's behavior, not a gap introduced by v9: the real `tls_kem_proxy`
uses `InsecureSkipVerify: true` (performs NO server chain verification
at all, neither the classical nor the alternative one); v9 is already
stricter than that (always verifies the server's classical RSA chain,
Decision 12), it just does not extend that verification to the
alternative X.509 gate. **Measurement implication, recorded:** the
CLIENT's CPU cost in the Hybrid-v8 profile (bench, Decision 14)
UNDERESTIMATES the real cost of a client that actually verified the
server's alternative signature -- this operation (1 extra ML-DSA-65
verification per connection) is never exercised on the client side,
neither in v8 nor in v9. **Decision: kept as is**, for fidelity to
v8 -- recorded here so that whoever reads Hybrid-v8's CPU numbers
knows the client side specifically has this downward bias, it is not
a "complete" number.

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 23. Six fixes to T8/the procedure/the evaluator -- local PKI copy deleted only at the pilot's end, run order switched to per-profile blocks (replicating real v8), MongoDB/Node verified by real digest (not by label), criterion 1 confirmed at message level + MSS/MTU/snaplen in the pilot, auto-shutdown fixed to terminate, HTTP sizes compared byte for byte in a real round

**1. PKI, operator's local copy -- fixed: now deleted only at the END
of the pilot, not after the first confirmed delivery.**

The earlier version (Decision 22, item 2.3) was wrong for the same
reason Luciano himself pointed out: the pilot has **3 clients**
(L0, L219, L325), not 1 -- and all 3 exist and operate
**simultaneously** during the pilot (see point 2 below: a profile
block needs all 3 routes available at the same time for the
round-robin). Deleting the local copy after "delivery confirmation"
sounds safe, but does not clearly define delivery to WHICH of the 3
clients -- and if a client needs to be replaced mid-pilot (crash,
instance recreated), reissuing the PKI from scratch would swap the
CA, invalidating the trust already established with the server and
with the other 2 clients still standing. **Fixed:** the operator's
local copy (this session's scratch) is retained until the entire
pilot closes -- it is only deleted after the LAST destroy (server +
3 clients) is confirmed. Each instance's own copy keeps being deleted
at the end of THAT instance's use (same as Decision 22 already said --
that did not change, only the OPERATOR's copy).

**2. Run order -- fixed to randomization by profile BLOCK, fixed
route round-robin inside the block, replicating real v8.**

Decision 22's proposal ("profile randomized per run") was
wrong: every profile switch requires restarting the
`gateway`/`proxy` (new TLS config -- curve group, CA, Dual), and that
restart's readiness probe (the same one that caused the "7th
connection," Decision 18) would fall INSIDE the measured window if
the profile changed on every run. Checked how real v8 ordered it
(`switch_crypto_profile.py`
is the campaign's real orchestrator, looked up directly, not from
memory): **profile drawn once PER WINDOW** (real v8 has 3
windows/day, each with its own drawn order); **inside a window,
the ROUTE is never drawn** -- fixed round-robin (`L0, L14,
L30, ...`, always the same literal order), repeated run after run.
In other words: v8 switches profile (restarts the gateway) ONCE, does
the warm-up (5 discards, `SETTLING_WARMUP_RUNS`), and only THEN walks
through the routes in a fixed round-robin, several times, before
switching to the next drawn profile.

**Adopted for the v9 pilot, with the same logic:** since the pilot
probably fits in a single window (Decision 20), the order of the 4
profiles is drawn **once, for the entire pilot**; inside each
profile block, the round-robin walks through the pilot's 3 routes
(`L0,
L219, L325`, fixed order) **N=5 times each** = 15 runs per
profile, 60 in total. The `gateway`/`proxy` only restarts on a block
SWITCH (4 times in total, not 60) -- each restart's readiness probe
stays outside the measured window, exactly as intended.
**Direct consequence for point 1:** since the round-robin needs all
3 routes (3 client instances) available at the same time during the
ENTIRE profile block, the 3 clients need to be up and already have
the PKI delivered BEFORE the first block starts -- reinforcing why
the operator's copy cannot be deleted right after the "first"
delivery.

**3. MongoDB and Node.js -- fixed: verified by real digest, not by a
matching label on both ends.**

Decision 22 marked "SAME, confirmed" just because the label
`mongo:latest`/`node:24-alpine` appeared on both ends -- exactly the
error Luciano pointed out. I re-verified directly at the source, by
digest:

| Image | Where it is pinned | Real digest | Real version confirmed (`--version` inside the container) |
|---|---|---|---|
| MongoDB (insurance-server-lambdas) | `insurance-server-lambdas/docker-compose.yml:324` | `sha256:dc28ed5a9d0fc616903c3f463bb1e53b92b49f441721b91926e87d90bf957ce8` (note: an earlier transcription of mine, only in working notes, had a 1-digit error in this hash -- `f469bb` instead of the real `f463bb`; it never made it into this file, but recorded here so it doesn't repeat) | `db version v9.0.4`, `gitVersion 64ade602b836c9adeffba7fa038c887ffab56196`, `openSSLVersion OpenSSL 3.5.5` |
| Node (mock_as) | `mock-service-os/mock_as/Dockerfile:1` | `sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f` | `v24.22.0` |

Both files (`insurance-server-lambdas/docker-compose.yml` and
`mock-service-os/mock_as/Dockerfile`) **were never touched by any v9
commit** (confirmed via `git log -- <file>`, the latest commit on
each predates v9's existence) -- T6b reuses both with NO ALTERATION,
so v8 (real campaign) and v9 (local T6b, and the pilot later)
literally run the SAME file, SAME digest. This is why **"SAME" is
correct** here -- but now confirmed by digest + real running
version, not assumed from the label.

**Illustration of why the label alone is unsafe** (found along the
way, recorded as context, not as a v8-vs-v9 divergence): there is a
THIRD `node:24-alpine` image in the repo,
`thesis/scripts/pqc-signer/Dockerfile:12`, pinned by a DIFFERENT
digest
(`sha256:d32cdf619f63fe0471182d08996dd516c6275bb5fd31ae06e55a570bd9e1ad43`),
which resolves to a genuinely different REAL version (`v24.19.0`, not
`v24.22.0`)
-- the same literal label `node:24-alpine`, pinned at different
times, points to genuinely different Node builds. This file was also
never touched by v9 (last commit
`055ffa81`/`388e874c`, both pre-v9) -- so it is also "same" v8 x v9
by construction, it only serves as concrete proof that checking by
digest was necessary, not perfectionism.

**4. Criterion 1 and MTU -- confirmed at message level (not packet);
real MSS/path MTU and the initcwnd x MSS check added to the pilot;
the pilot's snaplen cannot reuse real v8's 256.**

Confirmed by reading `measure/measure.sh` directly (lines 52-55): the
section `evaluate_criteria.py` uses for criterion 1 comes from
`tshark -r
"$PCAP" -o "tls.keylog_file: $KEYLOG" -Y tls.handshake -T fields -e
tls.handshake.type -e tls.handshake.length` -- `tls.handshake.length`
is the length field DECLARED INSIDE the TLS message itself
(after decryption and TCP reassembly done by tshark via the
keylog), not the size of a packet/frame. The packet size
(`tcp.len`) only appears in a SEPARATE section, explicitly labeled
"cross-check" (line 57-58), never used by criterion 1. This confirms
what Decision 20 had already assumed, now read in the source, not
recalled.

The local capture (`measure.sh` line 19) already uses `tcpdump -i lo -s 0`
(full snaplen, no truncation) -- but v8's REAL campaign uses
`TCPDUMP_SNAPLEN_BYTES` = **256**, confirmed in
`v8/campaign/scripts/campaign_run.py` (lines 1686/2464) and in
`v8/campaign/README.md` itself ("Pcap capture: snaplen 256, handshake
measured two ways", v8's Decision 79) -- sufficient there because the
only use of the pcap in v8 was confirming SNI visibility/tolerance in
the ClientHello (near the start of the record). **This is NOT
sufficient for v9's pilot:** the `Certificate` messages of the
PQC/Hybrid-AND profiles measure 5.632B/6.582B (Decision 15/20) -- a
snaplen of
256 would truncate the message content irrecoverably (bytes lost, not
just deferred), breaking tshark's reassembly well before the record
ends. **Recorded in the pilot's procedure: the capture uses
`tcpdump -s 0` (or a snaplen explicitly larger than the largest
expected message, with margin), never real v8 campaign's conventional
256.**

**New pilot items, added to the checklist:**
- Record the real MSS and the real path MTU on each of the pilot's 3
  routes (e.g., `tracepath <destination>` from each client instance
  to the server, or `ip route get`/`ss --info` after a real
  connection for the negotiated MSS).
- Verify that the server's FIRST flight (ServerHello +
  EncryptedExtensions + CertificateRequest + Certificate +
  CertificateVerify + Finished, Decision 15) fits within
  `initcwnd x MSS` -- if it does not fit, criterion 2 (real initcwnd)
  and the very assumption of "no extra RTT in the handshake"
  (Decision 14/22) need to be revisited before accepting the pilot's
  numbers.

**5. Auto-shutdown -- confirmed/fixed: `terminate`, not just
`stop`.**

Confirmed directly in the real module
(`v8/campaign/terraform/modules/campaign_instance/main.tf`): the
`resource "aws_instance" "this"` NEVER sets
`instance_initiated_shutdown_behavior` -- it stays at AWS's default,
which is `"stop"` (confirmed by absence: no hit for
`shutdown_behavior` in this file). This means that v8's real
`safety_timer.sh.tftpl`, when it fires a `shutdown` inside the guest
after the deadline, only STOPS the instance -- it continues to exist
(and can be billed for EBS/elastic IP) until someone actually
destroys it. **For v9's pilot, deliberate divergence, recorded: the
Terraform module (when written, reusing `campaign_instance` as a
base) explicitly sets
`instance_initiated_shutdown_behavior = "terminate"`** -- the safety
auto-shutdown (Decision 22, N=4h) really TERMINATES the instance,
not just stops it, reducing the residual-cost window should the
session drop without manual teardown.

**6. HTTP body/header sizes -- compared byte for byte in a real
round, no longer "by construction" without measuring.**

Decision 22 (the "HTTP body and header sizes" item) had honestly
recorded the gap: the comparison had never been run.
Ran it now: I used v8's real data already collected at
`thesis/results/v8/janela1/experiment1 - Classic/sa-east-1/L0/runs/
w01_run01.calls.jsonl` (44 calls, Classical profile, route L0) as a
reference, and brought up a fresh v9 T6b round (this session's
`gateway`/`proxy` containers, `classico` profile, against the SAME
real backend `auth`/`mockapi`/`mongodb`/`localstack` that was already
up, unaltered) via a minimal driver that calls
`run_insurance_flow`/`run_person_flow` from `opin_flow.py` itself
directly (same production code, no new flag) and dumps the resulting
44 calls. I compared them pairwise, in the same order (same sequence
of endpoints in both rounds, confirming identical count and order
again):

- **`request_bytes` (body + headers of each REQUEST): 44/44
  identical, byte for byte, no exception.**
- **`response_bytes`: 14/44 identical byte for byte** (endpoints with
  deterministic content -- initial JWKS, CA, token issuance,
  `/auth`, `/request`, login/consent-redirect confirmations).
- **30/44 differ by exactly 1 byte**, always in the same pattern:
  confined to the endpoints whose response body embeds (a) `mock_as`'s
  own JWKS, derived from an EPHEMERAL RSA-2048 key generated at
  run time (the big-integer serialization
  of the `n` modulus can legitimately vary ±1 byte between two
  distinct key generations, depending on the high bits of the
  randomly drawn modulus --
  this is expected per-run key noise, not a bug), or (b)
  business data randomly generated by `insurance-server-lambdas`
  itself (claim/premium values) on every
  run -- a generator that was never altered by v9 (confirmed via
  `git log`). This same noise source (±1 byte, sometimes more in
  monetary values) exists running v8 twice in a row against
  itself, it is not a v8-vs-v9 divergence. **Honest caveat:** I did
  not open the raw body of each response byte by byte to pinpoint the
  exact character that differs in each of the 30 cases -- the pattern
  (a difference of exactly 1 byte, confined to endpoints with content
  known to be random per run, zero difference everywhere else)
  is strong evidence, not a case-by-case byte-level proof.

**Result recorded in the checklist (corrects the "HTTP body and
header sizes" row of Decision 22):** from "SAME by construction,
NOT compared" to **"SAME, now measured: requests 44/44 exact;
responses 14/44 exact and 30/44 with ±1 byte of known random noise
(ephemeral key/mock data), the same pattern expected within v8 itself
run-to-run"**.

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 24. Correction to the explanation of Decision 23's item 6 (the "random noise" hypothesis was WRONG -- real cause identified and proven: a calendar artifact in the RS's Date header); capture separated from timed measurement, with a scheme for the pilot and the campaign; per-block collection with a hash; terminate reconfirmed; estimated cost of the pilot and the official campaign with margin

**1. HTTP SIZES -- Decision 23's explanation was wrong. Proof by
replay, not accepted on hypothesis.**

Luciano asked for exactly the proof that was missing: compare
`w01_run01` with `w01_run02` from v8 ITSELF (same execution window,
same container boot). Result: **0/44 calls differ between the two
real v8 runs.** This directly refutes Decision 23's "random
per-run noise" hypothesis (ephemeral key regenerated on every run,
random mock data) -- if it were genuine per-run noise, it would show
up WITHIN v8 itself too, run to run, and it does not.

Additional investigation, isolating the real variable:
1. I brought up the REAL `mtls` (unaltered) + the REAL `tls_kem_proxy`
   (precompiled image) in this session, and ran the SAME
   `opin_flow.py` (production code, no new flag) against them, today --
   44 calls captured (`v8real`).
2. I compared `v8real` (today) against v9 (today, this session's
   containers): **0/44 differ.** v8 and v9 are byte-identical TODAY,
   across all 44 calls.
3. I compared `v8real` (today) against the archived file `w01_run01`
   (2026-10-30): **18/44 differ, each by exactly 1 byte** --
   all and ONLY the calls served by the Resource Server
   (`mockapi`/`insurance-server-lambdas`, Java/Micronaut): the RS's
   `/jwks`, `/consents` (POST and GET), `/insurance-person/*`. No
   call to the AS (`mock_as`/oidc-provider, Node) appears in this
   list.

**Root cause, identified and confirmed, not assumed:** I captured the
raw body of the RS's `/jwks` response (the call with an Authorization
Bearer, index 4) -- 455 bytes, EXACTLY, matching the real static key
(`insurance-server-lambdas/src/main/resources/crypto-profiles/
classic.json`, committed, never regenerated, `kid` identical to the
archived one: `041486ea-f7b8-4b36-9dfb-fadf2966d0e8`). A fixed, 100%
deterministic body -- the 1-byte difference can only be in the
header. The `Date` header captured today (November 7th):
`"Sat, 7 Nov 2026
13:15:02 GMT"` -- **no leading zero on the day** (15 characters before
the year). The RS's (Java/Micronaut) HTTP `Date` formatter does NOT
zero-pad single-digit days (1-9), unlike the AS (Node/
oidc-provider), which always zero-pads (`"Sat, 07 Nov 2026..."`,
confirmed in call idx0, which IS from the AS and NEVER appears in the
differences list). The archived file was recorded on 2026-10-30 --
**day 30, two digits, with no such ambiguity.** Today is day 7 -- one
digit, 1 byte shorter in the `Date` header, exactly on every call
that goes through the RS.

**This is NOT noise: it is a DETERMINISTIC artifact, explained and
tied to the CALENDAR of the day the comparison is made**, not to v8
vs. v9 (confirmed: v8real-today vs. v9-today = 0/44 differences) and
not to run-to-run variation (confirmed: v8 run01 vs. run02 = 0/44).
It reappears whenever one side of the comparison was captured on a
1-digit day (1-9 of any month) and the other side on a 2-digit day --
and disappears (stays 0/44) when both sides have the same digit count
in the day, as happened in both "today vs. today" tests above.
**Corrects Decision 23: the "ephemeral key"/"random mock data"
explanation was WRONG (no key is ephemeral here -- both ends, AS and
RS, load static, committed keys) -- the real cause is the RS's
`Date` header formatting.** T8's checklist result corrected once
more: HTTP body and header sizes
**SAME between v8 and v9, confirmed by double measurement
(today-vs-today,
0/44 differences); the only source of difference found is a calendar
artifact in the RS itself (unrelated to v8-vs-v9), which self-corrects
outside the 1-9 day-of-month window.**

**2. TERMINATE AND ARTIFACTS -- per-block collection added to the
procedure, with integrity verification before proceeding.**

Correct: with `instance_initiated_shutdown_behavior = "terminate"`
(Decision 23, item 5), the root EBS volume is deleted along with the
instance on destroy -- any artifact that only existed on the
instance's disk is lost if the teardown fires before collection.
Added to the procedure: at the END of EACH of the 4 profile blocks
(not just at the end of the whole pilot), the operator copies that
block's artifacts (gateway/proxy logs, pcap+keylog from that block's
captures, `calls.jsonl` from the 15 runs) to the operator's machine
via `scp`, computes the SHA-256 of each received file and checks it
against the hash computed ON the instance before deleting the remote
original -- it only moves on to the next block
(or to the destroy, on the last block) after the integrity
confirmation.
**The auto-shutdown (N=4h, Decision 23) remains just the safety net
against a dropped session -- per-block collection is the primary
mechanism, it does not depend on the timer.**

**3. CAPTURE vs. LATENCY -- scheme defined: capture kept separate
from the timed runs, both in the pilot and in the official campaign.**

**Which runs carry a capture:** the 12 from criterion 1 (4 profiles x 3
routes, Decision 20/21) -- ONE full capture (`tcpdump -s 0` +
keylog) per profile x route cell, not the entire 15 runs of that
block. All 60 pilot runs continue to be ALL timed
(criterion 5/6/7 require this); the capture runs on a DEDICATED,
additional run, outside the statistical count of the 15 per
block -- replicating exactly the pattern v7 already used (v7's
Decision 15: a packet captured by a `--rm` observer, OUTSIDE the
statistical batch, "the size batch and the latency batch are
different sets of runs").

**Perturbation measured locally (N=5 with vs. without capture,
Classical profile, same machine):** I ran v9's `gateway`+`proxy`
inside the SAME container (no local network traversal, same as
`measure.sh`) 5 times WITH `tcpdump -s 0`+keylog (as the real
`measure.sh` does) and 5
times WITHOUT any capture, extracting the `handshakeDurationUs` that
the `proxy` itself reports. **Without capture:** 7436, 6326, 12795, 10719,
6089 µs (mean 8673). **With capture:** 4320, 4744, 6183, 7064, 4636 µs
(mean 5389). **Honest result: the sample WITH capture came out
SMALLER, not larger** -- the opposite of what a real perturbation
would cause. I conclude that, at this scale (microseconds, local
loopback, N=5), the environment's background variance (Docker
scheduling, container boot) completely dominates any real cost of
the capture --
**this local test is inconclusive, it does not prove the capture is
harmless, only that the effect (if any) is below the background
noise measured here.** Honestly recorded: the real test needs to be
redone in the pilot, on a route with REAL network latency (where the
handshake takes tens to hundreds of ms, not 5-13), N=5 with vs.
without capture, same route and profile -- only there is the result
conclusive.

**Scheme proposed for the official campaign (960 runs):** capture
runs ONLY on the 12 dedicated runs (4 profiles x 8 routes... no,
3 of the 8 routes are enough for the criterion -- but if Luciano
wants all 8 routes captured, that's 32 dedicated captures, 4 profiles
x 8
routes), each OUTSIDE the 30 statistical runs of that
cell -- never the same run counted twice. The 30 statistical runs per
cell (960 in total) NEVER carry `tcpdump`/keylog
turned on, exactly as v7 separated the "size batch" from the "latency
batch." This guarantees that the official latency number never
includes the cost (measured or not) of running the capture.

**4. AUTO-SHUTDOWN -- reconfirmed.** `terminate`, not `stop`
(Decision 23, item 5, no change -- reconfirmed here because of
item 2 above, which depends on this semantics).

**5. COST -- estimated by arithmetic, with declared sources and
dates, with no AWS call at all.**

**Source and date of each unit price** (all already cited in
`v8/DECISIONS.md`, never re-obtained via API -- this project has no
billing permission, v8's Decision 44):
| Item | Price | Source | Date cited in v8/DECISIONS.md |
|---|---|---|---|
| `m7i-flex.large` (server and clients) | US$0,0958/h | calculator.holori.com (aggregator, us-east-1) | 2026-10-?? (v8's Decision ~98, line 4774) |
| `t4g.micro` (control) | US$0,0084/h | commonly cited public source | same decision |
| Public IP (each) | US$0,005/h, charged even when idle | official AWS announcement (Public IP Insights) | cited in v8's Decision 44 |
| EBS gp3 (30GB) | US$0,08/GB-month | aws.amazon.com/ebs/pricing | cited in v8's Decision ~98 |
| Cross-region transfer | ~US$0,02/GB | secondary source, not the official API | v8's Decision 32/44 |

**Real anchor, not estimated: what v8 actually cost.** Recorded
directly in `v8/DECISIONS.md`, Decision 117 (2026-10-31): fleet
up since 2026-10-30T21:08:56Z, **22.45 total fleet-hours**,
**estimated total cost ≈ US$29,34**, confirmed at the final destroy (65
resources destroyed, 7 regions, verified via the real AWS API). This
is v8's full REAL campaign: 3 profiles x 8 routes x 30 = 720
runs.

**v9's pilot (60 runs, 1 server + 3 clients + 1 control,
~5 instances up for the entire pilot):** using the corrected run
order (Decision 23, item 2 -- only 4 profile switches, not 12), the
estimated total time drops from ~1-1,5h (Decision 20) to something
like **30-60 minutes of measured window**, plus setup margin
(PKI distribution, settling) and teardown -- **~1,5-2h of fleet up**,
a round, conservative number. Cost: 4x `m7i-flex.large`
(server+3 clients) + 1x `t4g.micro` (control) + 5x public IP, 2h:
- Compute: (4 x 0,0958 + 1 x 0,0084) x 2h ≈ US$0,783
- Public IP: 5 x 0,005 x 2h ≈ US$0,05
- EBS (5 x 30GB, gp3, pro-rated for 2h): ≈ US$0,033
- Cross-region transfer: negligible at this scale (real v8 measured
  ~US$0,14 for the ENTIRE 720-run campaign) ≈ US$0,02
- **Subtotal: ≈ US$0,89. With a 30% margin: ≈ US$1,15.**

This matches a real precedent already recorded in `v8/DECISIONS.md`
(several pilot attempts of similar scale/duration really cost
US$0,93, US$1,10, and US$1,80) -- the estimate is not
fanciful, it reproduces the same order of magnitude that real v8 has
already measured. **Fits within US$27,72 with a large margin (uses
~4-7% of the ceiling).**

**v9's official campaign (960 runs, 4 profiles x 8 routes x 30 --
33% more runs than real v8, same 8 routes/regions, same instance
types):** scaling v8's real anchor (US$29,34 / 22,45h
for 720 runs = 3 profiles) linearly per profile (US$9,78 and
7,48h of fleet-time per profile, from real v8): **4 profiles -> ≈ 29,9h
of fleet-time, ≈ US$39,12 before margin.** **With a 30% margin: ≈ US$50,86.**
**DOES NOT fit within US$27,72** -- the full official campaign, at
this estimate, lands between 1,4x (no margin) and 1,8x (with margin)
above that value. If US$27,72 is the intended ceiling only for the
PILOT, the pilot fits with a large margin (item above); if it is the
intended ceiling for the entire OFFICIAL CAMPAIGN, the estimate here
indicates it does not fit, and the decision (reduce N, reduce routes,
raise the ceiling, or accept the overrun) is Luciano's -- not assumed
here.

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 25. Instance types reconciled (m7i-flex.large/t4g.micro confirmed in the real tfstate, not the old plan's t3.xlarge/t3.medium); cross-arch amd64+arm64 Go build with a reproducible hash per architecture; control instance's role explained and kept; the Date artifact recorded as a limitation with a day-boundary treatment; regional price sensitivity and the price sources made explicit

**1. TYPES AND ARCHITECTURE -- reconciled against v8's real tfstate,
not against the old plan.**

The "t3.xlarge"/"t3.medium" that Luciano read comes from a **draft
plan that predates any real research into v8** (the phase plan
recorded at the start of this session, before Decision 22 actually
researched v8) -- it was never written into v9's `DECISIONS.md`; v9's
`DECISIONS.md` (Decision 22 onward) has always used
`m7i-flex.large`/`t4g.micro`. I reconfirmed this now directly against
the most concrete artifact possible, not prose:
`thesis/results/v8/campaign/
terraform/terraform.tfstate.backup` (the REAL, post-apply STATE, not
the plan) -- `grep instance_type` shows **11 instances with
`"instance_type": "m7i-flex.large"`** (servers and clients, all
x86_64) and **1 with `"instance_type": "t4g.micro"`** (control,
arm64), matching exactly `variables.tf`
(`server_client_instance_type`, no default -- requires an explicit
choice; `control_instance_type`, default `"t4g.micro"`,
commented as "free-tier-eligible, small -- the control instance
never runs the real workload"). **Fixed the "Instance types" row from
T8 (Decision 22):** from "NOT VERIFIABLE WITHOUT AWS" to
**"SAME, by decision -- verifiable and verified NOW"**, because the
TYPE is a configuration string, it does not depend on AWS to be
specified; only the exact ID of the resolved AMI (its own row,
`most_recent=true`) still depends on a real resolution.

**Cross-architecture build, each with a reproducible hash, tested
now:** I built `gateway` for the fixed toolchain (go1.27.3, the same
`mockopin-v9-toolchain` image) with `GOARCH=amd64` and with
`GOARCH=arm64` separately, and REBUILT both from scratch (new
container, same source, same toolchain) to confirm reproducibility:

```
amd64: 94bd9cadf87cc665b6fda5114b10cc3ddc771432436d0973b1cacc1630ee6537  (idêntico nas duas builds)
arm64: 458009d2a77544f7919989ce70368b6e583b997e6b74df3e12326d93c342d78a  (idêntico nas duas builds)
```

Two hashes DIFFERENT from each other (expected -- different machine
code), each one stable/reproducible on its own architecture (expected
-- confirms that build reproducibility (Decision 22, item 5) holds
for both architectures, not just amd64). **Real usage:**
`gateway`/`proxy` run on the SERVER and on the 3 CLIENTS, all
`m7i-flex.large` (amd64) -- this is the source-hash pair that needs
to be checked (`sha256sum -c`) on EACH of these 4 instances before
using the binary. **The CONTROL instance (arm64) does not run
`gateway`/`proxy` in the current design** (it only orchestrates via
SSH, Section 2 below) -- the arm64 build is prepared anyway, by
explicit request and as a precaution (lets the control instance run
a connectivity self-test with the SAME binary, independent of the
real x86 path, if Luciano wants that extra diagnostic before each
block) -- but, honestly, it is not used by today's measured flow.
**Hash checking is always architecture-aware**: each
instance checks against the hash of ITS OWN architecture (amd64 on
the 4 `m7i-flex.large`, arm64 on the control if it ever runs the
binary), never crossed -- comparing an amd64 hash against an arm64
binary would always fail, by design (they are different files).

**Burstable-CPU risk (`t4g.micro`) -- assessed, low impact on the
measured/captured path, but monitoring proposed as a precaution.**
`t4g.micro` is in the T family (Graviton2, burstable): low baseline
performance, with a CPU credit that accumulates while idle and
depletes under sustained load -- under exhaustion, the instance is
throttled below baseline. `m7i-flex.large` (the server and the 3
clients -- where the timed HTTP flow and the `tcpdump -s 0`/keylog
ACTUALLY run) is in the M "Flex" family: higher baseline, WITHOUT the
credit mechanism that depletes -- it does not suffer the same risk.
**Conclusion: the instance that runs the risk of credit-based
throttling is EXACTLY the one that runs neither the timed flow nor
the capture** (control only does SSH/
orchestration) -- the risk does not directly contaminate the measured
data.
**But it could delay the round-robin cadence** (Decision 23, item 2)
if the control gets slow under credit exhaustion, creating time gaps
between runs (not bias in the numbers, which are self-contained
client-side, only a possible delay/window larger than planned).
**Monitoring proposed, added to the procedure:** before and after
EACH profile block (4 times in the pilot), running `ethtool -S` does
not apply here -- the real mechanism is `aws cloudwatch get-metric-
statistics --metric-name CPUCreditBalance` (outside this session's
reach, "no AWS") OR, from inside the instance itself, checking
`/proc/stat`/perceived load before/after as a cheap proxy; the formal
item remains part of the pilot's procedure (not executable without
AWS now), with the criterion: the control's credit balance must not
reach zero during the pilot -- if it does, document the observed
cadence delay, do not discard the data (which remains valid, only
potentially more spread out in time).

**2. CONTROL -- role explained (same as real v8), kept in the
procedure.**

I looked up the exact role directly in `v8/DECISIONS.md`, Decision 49
("Campaign control-plane infrastructure"), instead of assuming it.
**What the control instance DOES in real v8, and will do identically
in v9:** it is the ORCHESTRATOR -- it runs the campaign script
(equivalent to the real
`campaign_run.py`) under `systemd`, holds the campaign's exclusive
SSH key (generated by Terraform, never written into the repository)
and uses THAT key to connect to the server and the clients, never the
other way around; it is what decides the ORDER (drawn profile,
route round-robin -- exactly the mechanism Decision 23, item 2,
depends on something orchestrating) and fires each run via SSH.
**What the control instance does NOT do, confirmed in the same
decision:** it has no AWS credential or role of its own
(`iam_instance_profile` never set -- it cannot run
`terraform destroy` or any AWS call by itself);
it does not run the measured HTTP flow nor the capture (that's on the
server/
clients). Inbound SSH on the server/clients only accepts connections
from the CONTROL's own elastic IP (never directly from the operator)
-- the operator only talks to the control, and the control talks to
everything else.
**Decision: kept in v9's procedure, identical in role** -- without
it, there is no one to fire the round-robin across the 3 clients in
the right order nor anyone to hold/relay the campaign key; it is also
where the PKI's operational copy can be mirrored (besides the
operator's copy, Decision 23 item 1) if Luciano wants a second copy
inside the campaign's network.

**3. DATE -- recorded as a known limitation in the checklist, with a
proposed day-boundary treatment.**

Added to the T8 checklist (Decision 22) and to the pilot's
limitations: **the RS's (`mockapi`/Java/Micronaut) responses have
exactly 1 byte less in the `Date` header on any run that falls on
days 1
through 9 of any month** (no leading zero on the day -- Decision 24).
This is **purely a calendar matter**, not a v8-vs-v9 matter, not a
run-to-run matter -- confirmed in both directions (Decision 24).
**Treatment
adopted:** (a) the real date of each run is already recorded
(`start_utc`/`end_utc`, per call, always logged -- no change
needed) -- any 1-byte discrepancy is retroactively explainable just
by checking that date, never mysterious;
(b) criterion 1's tolerance (Decision 20, ±50B on the Certificate)
already generously absorbs this ±1B on the TLS messages -- it is not
a risk to criterion 1 itself (which measures TLS, not the RS's HTTP
body); the risk is only for a future comparison of HTTP BODY SIZE
between runs on days with a different digit count, which needs to
know about this caveat so as not to confuse it with a real
regression.

**CAN the official campaign cross this boundary?** Yes, realistically
-- the fleet-time estimate (Decision 24, item 5) is ~29,9h continuous,
but real v8 ran across MULTIPLE windows over >1 calendar day
(boot 2026-10-30T21:08, destroy 2026-10-31T19:36 -- almost 23h of
wall-clock time, not just active fleet-time) -- a similar pattern in
v9 could easily cross from a 2-digit day into a 1-digit one (e.g.,
day 30/31 into day 1) or vice versa. **How to handle it:**
there is no need to PREVENT the crossing (item (a) above already
makes it traceable) -- but, as a simple, zero-cost precaution,
**recorded
as a scheduling recommendation**: avoid starting the official campaign
less than ~2 days before a 9->10 or 30/31->1 turnover, when the
estimated duration is close to 24h+, simply to keep ALL 960
runs on the same side of the boundary and eliminate this variable
entirely instead of just explaining it afterward. If the crossing
happens anyway (e.g., real duration longer than estimated), item (a)
guarantees nothing is left unexplained.

**4. COST -- regional sensitivity added; the source of the prices
(third-party aggregator, not AWS's official table) made explicit; the
campaign's estimate (anchored in v8's real spend) already reflects
the real regional mix, the pilot's (bottom-up) needed the
adjustment.**

**Source, explicit:** all unit prices used in Decision 24
come from **third-party aggregators** (`calculator.holori.com`,
`instances.vantage.sh`, both cited and linked inside
`v8/DECISIONS.md` itself) -- **none comes from AWS's official pricing
table** (this project's IAM has no permission to read `pricing:*`,
v8's Decision 44, nor does it authorize any AWS call in this
session).
**Needs to be re-checked manually (AWS Pricing Calculator or
Billing Console) before any real campaign `apply`** -- this is not a
price guarantee, it is an order-of-magnitude estimate.

**Regional sensitivity, added:** `v8/DECISIONS.md` itself
(line ~1502) already records the caveat "assumes up to ~1,5x in
pricier regions (`sa-east-1`, `ap-northeast-*`), not independently
confirmed" about the cited `m7i-flex.large` rate
(US$0,0958/h is `us-east-1`'s rate). **This matters more for the
PILOT than for the campaign:** given the real route structure
(Decision
21 -- `sa-east-1` hosts L0/L123/L219/L325, the 4 "distance" profile
routes inside the SAME region), **the pilot's 3 clients
(L0/L219/L325) PLUS the server PLUS the control are ALL in
`sa-east-1`** -- none in the base region (`us-east-1`) used for
price sourcing. Recalculating the pilot with the 1,5x multiplier
(conservative, the top of the range v8 already recorded) on compute:
- Compute: (4 x 0,0958x1,5 + 1 x 0,0084x1,5) x 2h ≈ US$1,17 (before:
  US$0,78 with no regional adjustment)
- Adjusted subtotal: ≈ US$1,27. **With a 30% margin: ≈ US$1,65.**
  Still **fits within US$27,72 with a large margin** (~6% of the
  ceiling).

**For the official campaign, the regional adjustment is NOT needed in
the same way:** Decision 24's estimate (≈US$39,12 before margin, 4
profiles x 8 routes) was anchored in **v8's already-recorded REAL
spend**
(US$29,34/22,45h, v8's Decision 117) -- this number comes from real
AWS billing, across the 7 real regions v8 actually used, so the real
regional price mix is ALREADY baked into it by construction, with no
need for a synthetic multiplier on top. **It holds:
≈US$39,12 before margin, ≈US$50,86 with 30%, DOES NOT fit within
US$27,72**
-- no change to this conclusion from this item, only the origin of
the number is made more explicit (real anchor vs. bottom-up
estimate).

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 26. REAL ERROR corrected -- the pilot's topology had the 3 clients in the same region as the server, which would not actually produce L219/L325; v8's 8 routes tabulated with source; topology/cost/vCPU quotas redone for the 3 real regions; tag verification extended to all pilot regions; operator-control-instances path for PKI/binary/collection described

**1. ROUTES AND REGIONS -- real error admitted: the previous round
placed L0/L219/L325 all in `sa-east-1`, which contradicts the T8
checklist itself (which says these routes come from REAL geographic
distance, not `tc`/`netem`) -- 3 instances in the SAME region would
never actually produce ~219ms/~325ms. Fixed, by looking directly at
`v8/DECISIONS.md` (lines 1996-2001 and 1801-1805, Decision 53/lines
8553-8554 and 9973 for the real measured values), not from memory:**

| Server region | Scenario | Client region | Nominal RTT | Real measured RTT (v8) | How it is produced |
|---|---|---|---|---|---|
| `sa-east-1` | L0 | `sa-east-1` (same AZ, private IP) | 0ms | ~0,14-0,18ms | real co-location |
| `sa-east-1` | L123 | `ca-central-1` (instance A) | 123ms | ~122,9ms | real geographic distance |
| `sa-east-1` | **L219** | **`eu-north-1`** | 219ms | ~219,9ms | real geographic distance |
| `sa-east-1` | **L325** | **`ap-southeast-1`** | 325ms | ~330,3ms | real geographic distance |
| `us-east-1` | L0 | `us-east-1` (same AZ) | 0ms | ~0,14-0,18ms | real co-location |
| `us-east-1` | L14 | `ca-central-1` (instance B, SEPARATE from A) | 14ms | ~15,4ms | real geographic distance |
| `ap-northeast-1` | L0 | `ap-northeast-1` (same AZ) | 0ms | ~0,14-0,18ms | real co-location |
| `ap-northeast-1` | L30 | `ap-northeast-2` | 30ms | ~32,3ms | real geographic distance |

8 routes, 3 servers (`sa-east-1`/`us-east-1`/`ap-northeast-1`), 3
profiles x 30 = 720 runs (v8's Decision 53, line 2663). **The pilot's
3 routes (L0/L219/L325, Decision 20/21) are the 3 first rows marked
above, ALL under the same `sa-east-1` server** --
`L0` co-located, `L219` with a real client in `eu-north-1`, `L325`
with a real client in `ap-southeast-1`. **Pilot topology
fixed: server in `sa-east-1`; L0 client in `sa-east-1`
(same AZ); L219 client in `eu-north-1`; L325 client in
`ap-southeast-1`; control in `sa-east-1`** (alongside the server,
same pattern as real v8) -- **4 AWS regions involved in the pilot,
not 1.**

**Topology, cost, and vCPU quotas redone:**

| Region | Instances | vCPU (m7i-flex.large=2, t4g.micro=2) |
|---|---|---|
| `sa-east-1` | 1 server + 1 L0 client + 1 control | 6 vCPU |
| `eu-north-1` | 1 L219 client | 2 vCPU |
| `ap-southeast-1` | 1 L325 client | 2 vCPU |

**Per-region vCPU quota -- NOT VERIFIED (requires AWS), but demand is
small.** Real v8 only checked the EIP quota (Decision 49), never the
vCPU quota explicitly -- no direct precedent to cite here. Proposed
as a pilot pre-flight item (before the apply): `aws service-quotas get-service-quota --service-code ec2
--quota-code L-1216C47A` (Running On-Demand Standard (A,C,D,H,I,M,R,
T,Z) instances) across the 3 regions -- the pilot's demand (6/2/2
vCPU) is small enough to probably fit within a new account's default
(typically 5-32), but this is an expectation, not a verification.

**Pilot cost, recalculated with the real regions (no longer
"everything in sa-east-1"):** there is no `m7i-flex.large` rate
sourced per region in `v8/DECISIONS.md` -- the only real regional
table there is for `c5.2xlarge` (line 1196-1201: `sa-east-1` ~$0,49/h,
`ca-central-1`/`eu-north-1` ~$0,37/h, `ap-southeast-1` ~$0,43/h),
a DIFFERENT instance family. I use this table only as a PROXY for the
regional ratio (not as a direct rate) over the
`m7i-flex.large` us-east-1 base ($0,0958/h, Decision 24): `sa-east-1`
≈1,32x ≈US$0,1265/h; `eu-north-1` ≈1,0x ≈US$0,0958/h (stays close to
the base); `ap-southeast-1` ≈1,16x ≈US$0,1111/h -- **explicitly not
confirmed for `m7i-flex.large` specifically, only a ratio borrowed
from another family, the same limitation already recorded in
Decision 25.** `t4g.micro` kept at the base rate (no separate
regional adjustment, negligible impact on the total either way). 2h
of fleet-time:
- `sa-east-1` (1 server + 1 L0 + 1 control): (2x0,1265 + 1x0,0084)
  x2h ≈ US$0,523
- `eu-north-1` (1 L219 client): 0,0958x2h ≈ US$0,192
- `ap-southeast-1` (1 L325 client): 0,1111x2h ≈ US$0,222
- Public IP: 5x US$0,005x2h = US$0,05
- EBS (5x30GB gp3, pro-rated for 2h): ≈US$0,033
- Cross-region transfer (2 real legs, `sa-east-1<->eu-north-1`
  and `sa-east-1<->ap-southeast-1`, the pilot's small scale):
  negligible, ≈US$0,02 (real v8 measured only ~US$0,14 for the
  ENTIRE 720-run campaign)
- **Subtotal: ≈ US$1,04. With a 30% margin: ≈ US$1,35.** Still
  **fits within US$27,72 with a large margin** (~5% of the
  ceiling) -- the topology fix changes the number (from ≈US$1,27/1,65
  to ≈US$1,04/1,35),
  but does not change the conclusion.

The OFFICIAL CAMPAIGN's estimate (Decision 24/25, ≈US$39,12/US$50,86,
DOES NOT fit within US$27,72) does not change from this item -- it
remains anchored in v8's REAL spend across the REAL regions, not in
a synthetic topology.

**DATED NOTE (2026-11-07, independent review, item D.10b -- added
later, original text intact):** Decision 25 (item 4,
"REGIONAL SENSITIVITY") computed the pilot's cost assuming "the
pilot's 3 clients (L0/L219/L325) PLUS the server PLUS the control are
ALL in `sa-east-1`" -- exactly the topology that THIS decision (26)
found to be a real error and fixed above (L219 in
`eu-north-1`, L325 in `ap-southeast-1`). **Decision 25 is, on this
point, SUPERSEDED BY this Decision (26)**: the cost recalculation
with the correct topology is already done in item 1 above
(≈US$1,04/1,35 instead
of ≈US$1,27/1,65) -- no number from Decision 25 remains in use
after this. The rest of Decision 25 (instance types, cross-architecture
build, control's role, the Date artifact) is not
affected by this point and remains valid. This same note formally
marks this item 1 as an AMENDMENT to Decision 25 (explicit request
from the independent review, item D.10b -- the topology fix was
already done, only the formal "superseded by" label was missing,
instead of just "REAL ERROR" in the title).

**2. TAGS ACROSS ALL REGIONS -- fixed, `resourcegroupstaggingapi` is
regional by nature.**

Correct -- this API does not aggregate across regions, each call only
sees the region of the endpoint used. **Fixed in the procedure: the
check before AND after every destroy runs across the pilot's 3
regions
(`sa-east-1`, `eu-north-1`, `ap-southeast-1`), one call per
region, expecting empty in all 3** -- not just in the control's
region.
**Additionally, a single time at the end of the entire pilot (not per
block):** runs the same check across ALL regions enabled
on the account (`aws account list-regions` or the fixed region list
v8 already used, 7-8 known regions), as a safety net against
any resource accidentally created in an unplanned region --
the same logic as real v8's final teardown (Decision 117, "confirmed
via the real AWS API across the 7 regions").

**3. SSH AND PKI -- full operator-control-instances path described,
private key never leaves the control instance without being deleted,
control destroyed at the end.**

Looked up directly in v8's Decision 49 (real two-key architecture) and
applied to v9's PKI/binary/collection flow:

- **Inbound path:** the operator connects DIRECTLY to the control
  (the control's elastic IP only accepts SSH from the operator's /32,
  Decision 49).
  The operator does NOT reach the server/clients directly -- each of
  them only accepts SSH from the control's OWN elastic IP (never from
  the operator). The control is the only intermediate hop to both
  sides.
- **PKI delivery:** the operator `scp`s each client's (L0/L219/L325)
  certificate/key + the public CA + the server's certificate/key,
  from the operator's machine to the control, using the OPERATOR's
  key (the same inbound connection). The control, using the
  campaign's EXCLUSIVE key (generated by Terraform, never committed --
  same mechanism as Decision 49), `scp`s each piece to its right
  destination (the server receives its own material + the public
  CAs; each client receives ITS OWN certificate/key + the same public
  CAs).
- **Binary delivery:** same path -- the operator `scp`s the
  `gateway`/`proxy` (plus the `.sha256`) to the control, the control
  `scp`s it to each destination instance (amd64 for the
  server+3 clients); each instance runs `sha256sum -c` before using
  it.
- **Per-block artifact collection:** reversed direction -- each
  instance (server/clients) `scp`s its own block artifacts to the
  control (campaign key), the control `scp`s them to the
  operator (operator's key); SHA-256 checked on each leg before
  deleting the remote original, exactly as Decision 24, item 2,
  already proposed (now with the 2-hop path made explicit, not
  implicit).
- **No private key is logged or persisted beyond what's necessary on
  the control:** each client's/server's private key only exists on
  the control's disk between the inbound `scp` and the outbound `scp`
  to the final destination -- deleted (`shred`) immediately after
  delivery is confirmed successful at that destination (the same
  `trap ... EXIT` pattern Decision 49 already uses for the campaign's
  SSH key, applied here too to the mTLS client/server keys). No
  `scp`/`cat`/`cp` command involving key material is printed with the
  key in clear text in any shell log -- only the filename, never the
  content.
- **The control IS destroyed at the end of the pilot**, together with
  the server and the 3 clients -- confirmed in the destruction list
  (item 1 above, the tag check covers the control's region too).
  **The OPERATOR's copy (outside any AWS instance) is the ONLY one
  that persists until the end of the entire pilot** (Decision 23,
  item 1) -- the copy inside the control is always ephemeral
  (deleted after every successful relay), never the "long" copy that
  item 1 describes.

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 27. Server address (EIP allocated before the instance, used in the SAN) and security group defined; read-only pre-flight with exact commands; abort procedure described; pre-registration check for push/tag -- real finding (a false positive from my own command, fixed) that there is no private key in the v9 branch's history

**1. SERVER ADDRESS -- elastic IP, allocated BEFORE the instance;
used directly in the SAN; security groups defined.**

**Elastic (EIP), not DNS.** v9's own certificate generator
(`certs/main.go`, `-server-ips` flag) was already designed for this:
"in the real campaign, the fleet's IPs resolved at deploy time" (the
flag's comment, line 474). An Elastic IP can be ALLOCATED (`aws_eip`,
without the `instance` attribute) even before the instance exists --
it solves the ordering problem (the server's address is needed to
generate the server's cert, but the instance only comes up
afterward) without needing DNS (hosted zone, propagation, TTL --
extra infrastructure this project has never used anywhere).
**Sequence:** 1) Terraform allocates the server's EIP (not yet
associated) -- the resulting address is an output; 2) this output
feeds the PKI generator's SINGLE call (Decision 22/23,
`-server-ips=<server's EIP>`), producing the server's certificate
with this exact IP as the SAN; 3) the server instance comes up; 4)
the EIP is associated to it. **The server's SAN uses the IP, not a
DNS name** -- IPs in a SAN are fixed-width OCTET STRINGs (Decision
20, 4B IPv4), so they add no size variability depending on the real
IP, unlike a DNS name.

**Server security group, defined:**
- Port 443: 3 inbound rules, one per client -- L0 via its PRIVATE IP
  (co-located in the same region/AZ, same pattern as real v8,
  Decision 49), L219 and L325 via their respective public ELASTIC IP
  (different regions, no peering/VPN between regions in this
  infrastructure -- only the public one reaches). Same pattern as
  real v8: "one ingress rule per client, created once by Terraform."
- Port 22: ONE rule, only the CONTROL's elastic IP -- never the
  operator directly (Decision 26, item 3).
- **No IP is version-controlled in any file.** The addresses
  (server's EIP, the 3 clients' EIPs, the control's EIP) only exist
  as RESOLVED values in `terraform.tfstate` (local, gitignored --
  same policy real v8 already uses, Decision 49) and as variables
  computed within Terraform itself (`aws_eip.*.public_ip`,
  referenced by another resource, never copied into a
  version-controlled `.tf` literal). The SG rules reference these
  computed values directly -- Terraform's own dependency ordering
  resolves it (EIP allocated -> SG rule references the resulting IP
  -> both in the same apply, no manual round-trip).

**2. PRE-FLIGHT -- read-only, exact commands, Luciano's go/no-go
point before the first apply.**

None of these were executed in this session ("no AWS" still holds) --
these are the EXACT commands that would run, with an explicit
decision point after seeing each one's result:

```
# 1. Credential identity and permissions (NEVER print the
#    literal result in chat -- account ID/ARN, permanent rule)
aws sts get-caller-identity
aws iam list-attached-user-policies --user-name <IAM username, redacted in a dated note -- see Decision 44, item F.15>

# 2. vCPU quota (Running On-Demand Standard (A,C,D,H,I,M,R,T,Z)),
#    one call per pilot region
aws service-quotas get-service-quota --service-code ec2 \
  --quota-code L-1216C47A --region sa-east-1
aws service-quotas get-service-quota --service-code ec2 \
  --quota-code L-1216C47A --region eu-north-1
aws service-quotas get-service-quota --service-code ec2 \
  --quota-code L-1216C47A --region ap-southeast-1

# 3. Instance-type availability, per region
aws ec2 describe-instance-type-offerings --location-type region \
  --filters Name=instance-type,Values=m7i-flex.large,t4g.micro \
  --region sa-east-1
aws ec2 describe-instance-type-offerings --location-type region \
  --filters Name=instance-type,Values=m7i-flex.large \
  --region eu-north-1
aws ec2 describe-instance-type-offerings --location-type region \
  --filters Name=instance-type,Values=m7i-flex.large \
  --region ap-southeast-1

# 4. Latest AMI per region (x86_64 in all 3; arm64 only in
#    sa-east-1, where the control host runs)
aws ec2 describe-images --owners amazon \
  --filters "Name=name,Values=al2023-ami-*-kernel-*-x86_64" \
             "Name=state,Values=available" \
  --query 'Images | sort_by(@,&CreationDate)[-1].[ImageId,Name]' \
  --region sa-east-1
# (repeat for eu-north-1 and ap-southeast-1, only --region changes;
#  repeat with -arm64 instead of -x86_64, only for sa-east-1)

# 5. Budget alert already in place
aws budgets describe-budgets --account-id "$(aws sts get-caller-identity --query Account --output text)"
```

**Go/no-go point: Luciano reviews each command's output and
authorizes (or not) the first `apply` -- none of them is executed
without this authorization, and no result with an account ID/ARN/IP
is pasted into the chat (the same rule as always, only the go/no-go
verdict per item).**

**3. ABORT -- procedure if a safety criterion fails mid-pilot.**

**Triggers:** a creation error (`apply` fails partially), an instance
that does not come up (healthcheck/SSH never becomes ready), loss of
connection to the control.

**Destruction order, from most external to most central:** 1) the 3
clients (L0/L219/L325) first -- smallest radius, nothing depends on
them;
2) the server next; 3) **the control LAST** -- it needs to be
working to relay any emergency collection and to confirm the state of
the others before it is destroyed itself. **Explicit exception: if
the TRIGGER is exactly "loss of connection to the control"**
(control unreachable), the order above cannot be executed normally
(no SSH, neither to the control nor through it) --
but this does NOT block the destruction: `terraform destroy` operates
via the AWS API, never via SSH to the instances, so destroying ALL
(the 3 clients + server + control, in the same call) remains possible
even with the control unreachable.

**Tag verification:** run across the pilot's 3 regions
(`sa-east-1`/`eu-north-1`/`ap-southeast-1`) after an emergency
destroy, same as the normal teardown (Decision 26, item 2) --
expected empty in all 3, regardless of the abort's reason.

**Already-collected artifacts:** kept, never discarded -- they are
already safe on the operator's machine (2-hop relay, Decision 26,
item
3). **Only the data from the BLOCK in progress at the moment of
failure**
(the incomplete run, or anything that only existed on the instance
that failed and was never relayed) is explicitly marked as "aborted
run, not part of the dataset" and excluded from the statistical
analysis -- recorded, not silently deleted (the same "report the
divergence, don't just discard it" policy this project has used
since v1).

**4. PRE-REGISTRATION -- prepared, NOT sent. A real finding along the
way: a false positive from my own command, fixed and re-verified.**

**Finding and fix, honestly recorded.** My first attempt to sweep
"the branch's entire reachable history" used
`git log --all -p main..v9/fase1-local` -- the `--all` flag OVERRIDES
the intended range (it makes git traverse ALL of the repository's
refs, including `remotes/upstream/*`, which has nothing to do with
the v9 branch), and it found real `-----BEGIN PRIVATE KEY-----`
blocks. Investigating FURTHER instead of accepting the result: I
located the exact commit (`74487e99`), confirmed it is a 2025-08-21
commit, author `luiky-raidiam` (Raidiam team, upstream), reachable
only via `remotes/upstream/feat/update-mockopin-4` -- NEVER actually
an ancestor of `main` or of `v9/fase1-local`. **I redid the sweep
without `--all`, with the correct range:**

```
git log -p main..v9/fase1-local -- .
  -> 24 commits (matches `git log --oneline main..v9/fase1-local`)
  -> 0 occurrences of any private-key PEM header
     (RSA/EC/DSA/OPENSSH/ENCRYPTED/PGP, all tested)
  -> 0 .key/.pem/.p12/.pfx files touched by any of the 24 commits
  -> the only "BEGIN...PRIVATE KEY" found is PROSE text (an earlier
     commit message from this same project, citing the `git grep`
     command used in a past verification -- not a real key)
  -> the only IP found: 127.0.0.1 (loopback, 18 occurrences, local
     harness usage, never a real public IP)
  -> 0 occurrences of arn:aws, AKIA[access key], or a 12-digit
     number in account-ID format
```

**Honest note about `mock-service-os/certs/*.key`:** these files
(test mTLS certificates, localhost-only) ARE version-controlled in
the repository -- but this is a pre-existing convention, documented
in the root `README.md` itself (`--key ./mock-service-os/certs/client_one.key`,
line 233+), present across the ENTIRE repository including `main`,
not introduced by any v9 commit (confirmed: none of v9's 24
commits touches any `.key` file). They are not real credentials, they
have no relation to the real pilot's PKI (that one is generated at
run time, never committed -- a separate rule, already validated every
round of this project). Mentioned here for transparency, not as a
blocker -- the criterion Luciano asked for ("private key in the v9
branch's REACHABLE history") is about what v9's 24 commits
introduce, and these commits confirmedly do NOT touch this type of
file.

**Scanner on the 24 commits:** each of this session's 24 commits was
preceded by a manual diff review before the `git commit` (a practice
followed every round, recorded in each round's chat report) --
reconfirmed now, retroactively, by the sweep above over the full
range, not just commit by commit.

**Prepared for push, NOT sent:**
```
git push origin v9/fase1-local
git push origin v9-prereg
```
**Neither was executed.** Awaiting Luciano's explicit confirmation --
"don't send anything without my explicit confirmation" still holds
to the letter.

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 28. AMENDMENT 1 TO CRITERION 1 (T7, post-`v9-prereg` tag) -- server SAN fixed -- L0 reaches it over a PRIVATE IP, L219/L325 over the EIP (confirmed in real v8, Decision 52/53); option (a) chosen, two IPs in the SAN; Certificate tolerance recalculated with an ARITHMETIC delta (-12B, later corrected by a real measurement in Decision 29) and evaluate_criteria.py updated

**Formal amendment label, per Decision 21's policy
("Criterion amendment, after the `v9-prereg` tag: requires a new,
dated decision, with a reason -- never an edit to the original
text"):**
- **What changed:** the baseline for the server's `Certificate`
  message used by criterion 1 (Decision 20/21, ±50B tolerance), inside
  `evaluate_criteria.py`'s `CERTIFICATE_BASELINE`. OLD values
  (loopback default, published in Decision 15/20/21): Classical
  913B, PQC 5.632B, Hybrid-v8 6.255B, Hybrid-AND 6.582B. NEW
  values, proposed in this amendment (ARITHMETIC estimate, see body
  below): 901B/5.620B/6.243B/6.570B.
- **Reason:** the server's SAN needs TWO real IPv4 addresses
  (private IP + EIP) instead of the loopback pair (IPv4+IPv6) used in
  the local tests so far -- discovered while designing the server's
  real address for the pilot (see this decision's body).
- **Date:** 2026-11-07.
- **The published `v9-prereg` tag remains intact** -- this amendment
  does not rewrite the original text of the 7 criteria (Decision 21),
  it only records a PARAMETER change inside the evaluator that
  implements criterion 1, in a new, dated entry, exactly as the
  policy requires.
- **Note added later (see Decision 29): the "NEW" values
  above, computed by DER arithmetic, did NOT match the real
  measurement done with the harness -- Decision 29 is a SECOND
  amendment (Amendment 2) that corrects these numbers to the
  measured values.** The text below (the original arithmetic
  reasoning) remains intact, not rewritten, per the same policy --
  only marked here as superseded.

**How real v8 had L0 reach the server -- looked up directly, not
assumed.** `v8/DECISIONS.md`, Decision 52 (title: "L0's
private-vs-public-IP asymmetry registered as a limitation"), line
2644-2656: **explicitly confirmed** -- "the lowest-latency
scenario's client (L0) reaches its server over the server's PRIVATE
IP (co-located, same AZ ID)... every OTHER scenario's client reaches
its server over the server's PUBLIC IP, the only path available
cross-region." Recorded by v8 itself as a structural limitation (not
just a difference in magnitude): "no NAT, no
public-internet routing, potentially different MTU/offload
behavior." Also confirmed in `campaign_run.py:456`:
`ip_field = "private_ip" if client["colocated"] else "public_ip"`
-- L0 is the only one `colocated=True`.

**Choice: option (a) -- fix the server's private IP and include
BOTH IPs in the SAN, do not move L0 to the EIP.** Moving L0 to the
EIP (option b) would destroy exactly the property that makes L0 a
useful scenario (zero NAT, zero public-internet routing, a truly
co-located path) -- v8 NEVER did this, and v9 has no reason to
diverge here. **Since v9 requires strict server verification by the
client (T5, Decision 12 -- no `InsecureSkipVerify`, a deliberate
divergence from real v8, which uses `InsecureSkipVerify:true` in
`tls_kem_proxy`), the server's certificate MUST answer to both
addresses**, unlike v8 (which could ignore this requirement because
it never really verified the server). `-server-ips`
(Decision 22/27) now lists BOTH: the server's private IP (for
L0) + the server's EIP (for L219 and L325).

**Certificate tolerance recalculated, exact delta, not
approximated.** The IP SAN goes from the local-development default
(`127.0.0.1,::1` -- 1x IPv4 + 1x IPv6) to 2x real IPv4. IPs in a SAN
are FIXED-width `OCTET STRING`s (Decision 20): IPv4 = 2B of
tag+length + 4B of content = 6B per entry; IPv6 = 2B+16B = 18B
per entry.
- Before (loopback): 1x IPv4 (6B) + 1x IPv6 (18B) = **24B**
- After (pilot): 2x IPv4 (6B+6B) = **12B**
- **Delta: -12B**, exact -- it depends only on the COUNT and TYPE of
  the addresses (2 IPv4), never on the exact VALUE AWS assigns (the
  same logic that already applies to any IP SAN, Decision 20) -- so
  it can be computed and fixed NOW, before deployment, without
  waiting for the real IP to exist.

**Certificate baseline, updated (was the loopback default, -12B):**
| Profile | Before (loopback) | After (pilot, final SAN) |
|---|---|---|
| Classical | 913B | **901B** |
| PQC | 5.632B | **5.620B** |
| Hybrid-v8 | 6.255B | **6.243B** |
| Hybrid-AND | 6.582B | **6.570B** |

Tolerance (±50B, Decision 20) kept unchanged -- it continues to
cover genuine uncertainty (not this delta, which is now known and
already baked into the baseline itself). `evaluate_criteria.py`'s
`CERTIFICATE_BASELINE` updated to the 4 values above, with a
comment explaining the -12B's origin -- the same logic holds for
ANY future real deployment, not just this specific pilot (the delta
is deployment-independent, it depends only on the address COUNT in
the SAN, fixed at 2 by an architecture decision, not by IP luck).

**DATED NOTE (2026-11-07, added later -- see Decision 30):
the justification above assumes, without verifying, that the client
validates the server by the SAN's IP address. Confirmed later
(Decision 30) that this is NOT the case: the real verification is by
DNS NAME (`cert.VerifyHostname
("mtls")`, against `DNSNames`, never against `IPAddresses`) -- the
IPs added to the SAN in this decision are harmless and are already
calibrated in the measured baseline (Decision 29), but they are NOT
what the proxy actually checks to authenticate the server. In this
architecture, the server's identity is the NAME issued by the
experiment's CA
(`mtls`), not the address. Original text above kept intact, not
rewritten -- this note only adds what was missing.**

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 29. AMENDMENT 2 TO CRITERION 1 (T7, post-`v9-prereg` tag) -- Amendment 1's arithmetic (Decision 28) did not match the real measurement; confirmed that the loopback baseline's SAN had IPs (not a DNS name like "localhost"); MEASURED values adopted; extra finding explained (Hybrid-AND doubles the delta for having 2 server leaf certificates)

**Formal amendment label:**
- **What changed:** the same `CERTIFICATE_BASELINE` that Decision 28
  (Amendment 1) had already changed -- now to the MEASURED values,
  not that amendment's arithmetic estimate. Amendment 1's values
  (arithmetic, SUPERSEDED): 901B/5.620B/6.243B/6.570B. **This
  amendment's values (measured, ADOPTED):** **899B/5.618B/6.241B/6.554B.**
- **Reason:** I actually measured instead of trusting the arithmetic
  (explicit request from Luciano) -- the arithmetic was wrong.
- **Date:** 2026-11-07 (same day as Amendment 1).
- **The `v9-prereg` tag remains intact**, same reason as Amendment 1.

**1. Confirmed: the loopback baseline's SAN (Decision 15/20/21)
had ONLY IPs in the part that changed, not a name like "localhost".**
Confirmed by reading `certs/Makefile` directly: `SERVER_DNS ?=
mtls,auth.local,...,keystore` (8 names, fixed, used both in the
loopback case and in the pilot -- Host-header routing, not real DNS)
and
`SERVER_IPS ?= 127.0.0.1,::1` (only this changed). The 8 DNS names
ARE the SAME in both scenarios -- the only variable between loopback
and the pilot is exactly the IP list, confirming that the isolated
comparison (only the IP's effect) is valid.

**2. Measured, not calculated -- two certificate builds, same
pipeline, same day.** I generated the server certificates twice with
`make certs` (`thesis/results/v9/certs`), varying ONLY
`SERVER_IPS`: (a) default (`127.0.0.1,::1`) and (b) two
DOCUMENTATION ranges, NEVER real addresses -- `203.0.113.10`
(TEST-NET-3, RFC 5737) and `10.0.0.10` (RFC 1918) -- confirmed in the
SAN generated via
`openssl x509 -noout -ext subjectAltName`: `DNS:mtls,...,DNS:keystore,
IP Address:203.0.113.10, IP Address:10.0.0.10`. I ran the SAME
`measure.sh` (4 profiles, tickets off) for each of the two
certificate sets, extracting the isolated `Certificate` message size
(the frame that ALSO contains ServerHello, the same rule as
criterion 1) both ways:

| Profile | (a) Loopback, measured NOW | (b) Doc-range, measured NOW | Measured delta | Old baseline (Decision 15) |
|---|---|---|---|---|
| Classical | 913B | 899B | **-14B** | 913B |
| PQC | 5.632B | 5.618B | **-14B** | 5.632B |
| Hybrid-v8 | 6.255B | 6.241B | **-14B** | 6.255B |
| Hybrid-AND | 6.582B | 6.554B | **-28B** | 6.582B |

**The "Loopback, measured NOW" column matches EXACTLY the old,
published baseline (913/5.632/6.255/6.582)** -- this confirms that
the measurement pipeline has had no drift since Decision 15; the
comparison is direct and trustworthy, not contaminated by another
change.

**3. Arithmetic's divergence, partially explained (not a
mystery).** Amendment 1 predicted -12B (2 IPv4 GeneralNames of 6B
each replacing 1 IPv4 6B + 1 IPv6 18B); the measurement gave **-14B**
for the 3 single-certificate profiles. The extra 2B were not
decomposed byte by byte -- the most likely hypothesis, not
individually confirmed, is a boundary effect in DER length
encoding (a size field at some nested level -- the SAN
extension, the OCTET STRING wrapping it, or the
`Extensions SEQUENCE` itself -- switches from short form to long
form, or vice versa, near the 128-byte content threshold, depending
on the total size; this width change of the size field itself is
NEVER purely additive in DER). **This does not invalidate the result
-- exactly why measuring instead of trusting the arithmetic
matters.**

**4. Extra finding, CONFIRMED in the code (not just a hypothesis):
Hybrid-AND doubles the delta because it has TWO server leaf
certificates, not one.** `certs/main.go`, lines 525-538: Hybrid-AND
generates `andRSAServer` AND `andMLDSAServer` as two SEPARATE SERVER
LEAFS (not a single one with an extra extension) -- with an explicit
check in the generator itself, `sameSANs(andRSAServer, andMLDSAServer)`,
guaranteeing that BOTH declare the SAME SAN. This is why the SAN
effect (-14B) applies TWICE in this specific profile -- 2 x
(-14B) = -28B, matching exactly the measured value. It is not an
anomaly, it is a direct and already confirmed consequence of this
profile's dual-certification architecture.

**FINAL baseline, adopted (measured, not arithmetic) -- replaces
Decision 28 (Amendment 1):**
```python
CERTIFICATE_BASELINE = {"classico": 899, "pqc": 5618, "hibrido-v8": 6241, "hibrido-and": 6554}
```
`evaluate_criteria.py` updated with these values and a comment
pointing to this decision (29), no longer to Decision 28 --
Amendment 1 remains recorded as history (its reasoning and its
numbers were not deleted, Decision 28 remains intact), but the
evaluator uses this amendment's numbers.

**DATED NOTE (2026-11-07, added later -- see Decision 30):
the measured values above remain correct and continue to be what the
evaluator uses -- the server's Certificate REALLY has that
size, byte for byte confirmed by measurement. What needs a note
is the original MOTIVATION: this decision treated the SAN's IPs as
necessary for "strict server verification by the client"
(T5). Confirmed later (Decision 30) that the real verification uses
the DNS NAME (`cert.VerifyHostname("mtls")`), never the SAN's IPs --
so the IPs are harmless and correctly measured, but they are not,
in this architecture, the mechanism that actually authenticates the
server.
Original text kept intact.**

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 30. AMENDMENT 3 TO CRITERION 1 (T7, post-`v9-prereg` tag) -- the ClientHello's SNI is FIXED ("mtls", hardcoded in the proxy, never depends on `-target`'s real address); server verification is by the SAN's DNS name, never by IP; tolerance fixed from ±15B to 0B, confirmed by local measurement; evaluator updated and tested

**Formal amendment label:**
- **What changed:** `CLIENTHELLO_TOLERANCE_B` (Decision 20/21, item e)
  from **±15B** to **0B**; `CLIENTHELLO_BASELINE` now exists and is
  actually checked in the evaluator (before, the constant existed
  but was never used in the code).
- **Reason:** the original assumption ("SNI ~+36B expected with
  private DNS") was never checked against the proxy's real code --
  direct reading shows the SNI is a FIXED string, not the deployment
  hostname.
- **Date:** 2026-11-07 (same day as Amendments 1 and 2).
- **The `v9-prereg` tag remains intact**, same reason as the earlier
  amendments -- Decision 20/21's original text (which assumed the
  +36B) was not rewritten, only superseded by this new entry.

**1. Read the proxy's and the client's code -- the SNI is FIXED,
never depends on `-target`'s address.** `proxy/main.go`,
`singleChainClientConfig` (line 269) and `dualClientConfig` (line
299): **`ServerName: "mtls"`, hardcoded in both `tls.Config`
constructors** -- used both in the single-test mode and in the
`-listen` mode (persistent relay, `proxy/relay.go` line 33, the SAME
`buildClientTLSConfig` called from there, confirmed by reading the
code). The `-target` (dial address, `tls.Dial("tcp", target, cfg)`,
`relay.go` line 63) is used ONLY for the TCP dial -- it is never read
back into the `ServerName` field. **In the pilot, the proxy dials the
server by IP (EIP or private IP), but sends `ServerName: "mtls"` as
the SNI anyway -- exactly the same string the local loopback already
uses.**

**2. The server's certificate verification is by the SAN's DNS NAME,
never by IP.** Default, documented behavior of Go's
`crypto/tls`/`crypto/x509`: hostname verification calls
`cert.VerifyHostname(c.config.ServerName)`; inside it, if the
argument does NOT parse as a valid IP (`net.ParseIP` fails), the
comparison is made against `Certificate.DNSNames`, NEVER against
`Certificate.IPAddresses`. Since `"mtls"` is not a valid IP, the
verification ALWAYS matches against the SAN's `mtls` DNS entry
(present since the default `SERVER_DNS`, Decision 22/27) -- **the
IPs that Decision 28/29 added to the SAN (private IP + EIP) never
enter this specific verification, in this architecture** (they would
still be correct to have -- a certificate with more SANs is not a
problem -- they are just not what the proxy actually checks to
validate the server).

**3. The pilot's expected ClientHello size = EXACTLY the loopback
one -- confirmed by measurement, not just by reading the code.**
I reused Decision 29's TWO real measurement rounds (same
`measure.sh` pipeline, same day) -- one with loopback-SAN certs,
the other with documentation-range SAN (`203.0.113.10`/`10.0.0.10`)
-- and compared the ClientHello frame (type `1`, always alone in
its own frame, never shared with another message type, across the 4
profiles): **IDENTICAL size in both rounds, byte for byte, across
the 4
profiles** -- expected, because the ClientHello is entirely
generated by the CLIENT before the server sends anything, it never
depends on the server's certificate (SAN or any other field). This
directly confirms, by measurement and not just by reading the code,
that there is NO source of variability in this message between
loopback and the pilot.

| Profile | Measured ClientHello (loopback, today) | Measured ClientHello (doc-range SAN, today) | Difference |
|---|---|---|---|
| Classical | 336B | 336B | 0B |
| PQC | 1.779B | 1.779B | 0B |
| Hybrid-v8 | 1.876B | 1.876B | 0B |
| Hybrid-AND | 1.858B | 1.858B | 0B |

**4. Tolerance fixed to 0B; evaluator updated and TESTED against
real data, not just edited.** `evaluate_criteria.py`:
`CLIENTHELLO_BASELINE = {"classico": 336, "pqc": 1779, "hibrido-v8":
1876, "hibrido-and": 1858}`, `CLIENTHELLO_TOLERANCE_B = 0`. The
ClientHello extraction (frame with `types == ["1"]`, `+4B` header,
same convention as the Certificate) was ACTUALLY WIRED IN
to `criterion_1_message_sizes()` -- before, the constant
`CLIENTHELLO_TOLERANCE_B` existed but was never checked in the code,
only documented. Tested by running the script against a synthetic
log built from this same session's REAL data (Decision 29's loopback
measurements): **PASS across the 4 profiles, Certificate and
ClientHello together**, full output reproduced (not summarized):
`classico`/`pqc`/`hibrido-v8`/`hibrido-and` all with
`certificate_ok: true` and `clienthello_ok: true`.

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 31. AMENDMENT 4 TO CRITERION 1 (T7, post-`v9-prereg` tag) -- full audit of evaluate_criteria.py (criteria 1-7), mutation testing per message/count/error; real finding -- ServerHello/EncryptedExtensions/CertificateRequest/CertificateVerify/Finished/client-Certificate were NEVER checked (only documented); fixed, wired in, tested

**Formal amendment label:**
- **What changed:** `ZERO_TOLERANCE_MESSAGES` (Decision 20/21) existed
  as a constant but NEVER controlled any real comparison in the
  code -- the same class of bug Amendment 3 already found for the
  ClientHello, now confirmed for the other 5 handshake messages
  PLUS the CLIENT's Certificate (never extracted). Fixed:
  `HANDSHAKE_MESSAGE_BASELINE` (8 fields per profile, measured) is
  now actually extracted and checked inside `criterion_1_message_sizes()`.
- **Reason:** audit requested by Luciano, after Amendment 3 had
  already found the same bug pattern once.
- **Date:** 2026-11-07 (same day as Amendments 1, 2, and 3).
- **The `v9-prereg` tag remains intact** -- Decision 20/21's
  original text (which already listed these 5 messages as "0B
  tolerance") was not rewritten; this amendment only fixes the
  IMPLEMENTATION that was missing, not the criterion's definition.

**1. Full audit, criterion by criterion, message by
message -- where (if anywhere) each value is actually
compared in the code:**

| Criterion | Item | Where it is checked (line/function) | Mutation test |
|---|---|---|---|
| 1 | ClientHello | `criterion_1_message_sizes`, `ch_ok` (already fixed in Amendment 3) | FAIL with +1B (tolerance 0) -- **detected** |
| 1 | ServerHello | **was NOT checked before this amendment** -- now `other_messages["ServerHello"]` | FAIL with +1B -- **detected** (after the fix) |
| 1 | EncryptedExtensions | **was NOT checked** -- now `other_messages["EncryptedExtensions"]` | FAIL with +1B -- **detected** |
| 1 | CertificateRequest | **was NOT checked** -- now `other_messages["CertificateRequest"]` | FAIL with +1B -- **detected** |
| 1 | Certificate (server) | `criterion_1_message_sizes`, `cert_ok` (already existed, Decision 20/28/29) | FAIL with +51B (tolerance 50) -- **detected**; PASS with exactly +50B (inclusive threshold, `abs(...)<=tolerance`) -- **confirmed** |
| 1 | Certificate (client) | **was NOT checked, nor extracted** -- now `other_messages["Certificate_cliente"]` | FAIL with +1B -- **detected** |
| 1 | CertificateVerify (server) | **was NOT checked** -- now `other_messages["CertificateVerify_servidor"]` | FAIL with +1B -- **detected** |
| 1 | CertificateVerify (client) | **was NOT checked** -- now `other_messages["CertificateVerify_cliente"]` | FAIL with +1B -- **detected** |
| 1 | Finished (server) | **was NOT checked** -- now `other_messages["Finished_servidor"]` | FAIL with +1B -- **detected** |
| 1 | Finished (client) | **was NOT checked** -- now `other_messages["Finished_cliente"]` | FAIL with +1B -- **detected** |
| 4 | HTTP count (44) | `criterion_4_counts`, `ok = actual == expected` | FAIL with 43 and with 45 -- **detected both ways** |
| 4 | JWT count (28) | same | FAIL with 27 and with 29 -- **detected** |
| 4 | /jwks count (4) | same | FAIL with 3 and with 5 -- **detected** |
| 4 | CA count (4) | same | FAIL with 3 and with 5 -- **detected** |
| 5 | real error (`"ok":false...error`) | `criterion_5_zero_errors`, regex + `errors_found` list | FAIL when a real error is injected -- **detected** |
| 5 | Dockerfile false positive (`FATAL` with `>&2`/`exit 1`) | same function, explicit filter (Decision 22) | PASS even with the Dockerfile line present -- **confirmed, no false positive** |
| 5 | real FATAL (no shell syntax) | same function | FAIL -- **detected** |
| 6 | CurveID per profile | `criterion_6_instrumentation`, `curve_ok` | FAIL with the wrong curve on the Classical profile -- **detected** |
| 6 | DualAuthenticated (Hybrid-AND) | same function, `dual_ok` | FAIL with `dualAuthenticated:false` on Hybrid-AND -- **detected** |
| 6 | Decrypted keylog evidence | same function, `has_keylog_evidence` | FAIL without the evidence line in the log -- **detected** |
| 2 | real initcwnd | `criterion_2_initcwnd` -- **stub, unconditionally returns `None`, NEVER reads the argument** | Mutation does not apply -- confirmed that `pass=None` does not change with ANY input content (tested with `None` and with arbitrary text) -- **behavior documented since Decision 22, not a bug, the real logic only exists after the pilot** |
| 3 | zero errors on the distant route | `criterion_3_distant_route` -- same stub pattern | same -- does not apply, same reason |
| 7 | latency sanity (RTT) | `criterion_7_latency_sanity` -- same stub pattern | same -- "RTT one step above the threshold" has no effect at all because there is NO threshold coded yet (only the logic for the 5 local criteria exists; 2/3/7 are placeholders until the pilot, by design, Decision 22) |

**2. Mutation test actually executed (not just described) --
the script runs against the real `evaluate_criteria.py` module, not a
reimplementation.** Baseline (with no mutation): criteria 1, 4, 5,
6 all PASS. Each of the 11 mutations for criterion 1 (10 messages +
1 exact-threshold test), 8 for criterion 4, 3 for criterion 5, 3 for
criterion 6 -- **26 mutations in total, all with the
expected result** (FAIL when it should fail, PASS when it should
pass at the exact threshold or in the Dockerfile's benign case).

**3. Fix applied.** `evaluate_criteria.py`:
`HANDSHAKE_MESSAGE_BASELINE` (8 fields x 4 profiles, measured now,
same `measure.sh` round, same `+4B` header convention),
`HANDSHAKE_MESSAGE_TOLERANCE_B = 0`, wired into
`criterion_1_message_sizes()` via positional extraction of EVERY line
from the "size PER MESSAGE" section (not just the Certificate line) --
both the SERVER's flight (frame with ServerHello, type `2`) and the
CLIENT's flight (frame with Certificate but WITHOUT ServerHello).
`ZERO_TOLERANCE_MESSAGES` kept in the file (old name, backward
compatibility), but the comment makes explicit that it no longer
controls anything -- `HANDSHAKE_MESSAGE_BASELINE` is the source of
truth now.

**Measured values, the 8 fields x 4 profiles (measure.sh, today, same
round as Amendment 3):**
| Profile | ServerHello | EncryptedExtensions | CertificateRequest | Certificate_cliente | CertificateVerify_servidor | CertificateVerify_cliente | Finished_servidor | Finished_cliente |
|---|---|---|---|---|---|---|---|---|
| Classical | 187 | 10 | 109 | 800 | 264 | 264 | 36 | 36 |
| PQC | 1.658 | 10 | 104 | 5.519 | 3.317 | 3.317 | 36 | 36 |
| Hybrid-v8 | 1.755 | 10 | 111 | 6.144 | 264 | 264 | 36 | 36 |
| Hybrid-AND | 1.755 | 10 | 98 | 6.356 | 3.575 | 3.575 | 36 | 36 |

Confirmed by measurement (not assumed) that none of these vary
between Decision 29/30's two SAN rounds (loopback vs. documentation)
-- only the SERVER's Certificate varies, exactly as already
established.
`Finished` is always 36B (32B of HMAC + 4B of header) regardless of
profile/side -- structural to TLS 1.3 (the `Finished`'s fixed size,
not a coincidence).

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 32. AMENDMENT 5 TO CRITERION 7 (T7, post-`v9-prereg` tag) -- L0's nominal is 0ms, ±10% is an empty/undefined range; an absolute floor (<1ms) adopted for L0; L219/L325 keep ±10% of nominal; evaluator updated

**Formal amendment label:**
- **What changed:** criterion 7 (Decision 20/21/24: "RTT measured
  for each route within ±10% of nominal") now has TWO different
  methods depending on the route: L0 uses an ABSOLUTE FLOOR (RTT <
  1ms), L219/L325 keep ±10% of nominal (219ms/325ms).
- **Reason:** L0 has a nominal of 0ms -- ±10% of 0 is 0, a
  zero-width range that NO real RTT (not even the ~0,14-0,18ms real
  v8 measured in this same co-located scenario) could ever satisfy.
  The criterion, as originally written, would ALWAYS fail L0, by
  mathematical construction, never because of a real route failure.
- **Date:** 2026-11-07 (same day as Amendments 1-4).
- **The `v9-prereg` tag remains intact** -- Decision 20/21/24's
  original text (±10% of nominal, no exception for L0) was not
  rewritten, only superseded by this new entry.

**Floor adopted:** L0's RTT < **1ms** -- gives a comfortable margin
over what real v8 already measured in this exact scenario
(0,14-0,18ms, v8's Decision
52/53) without opening the door to a route that actually traversed
a real network (anything >=1ms would already be suspect of not
being genuinely co-located). L219/L325 keep ±10% of the route's
NOMINAL (219ms/325ms) -- NOT of the value v8 measured (219,9ms/330,3ms),
which is only context confirming the nominal is realistic, never the
tolerance's own target.

`evaluate_criteria.py`: `NOMINAL_RTT_MS = {"L0": 0, "L219": 219,
"L325": 325}`, `L0_RTT_ABSOLUTE_FLOOR_MS = 1.0`,
`RTT_TOLERANCE_FRACTION = 0.10`, function `_rtt_ok(route, measured_ms)`
applying the right method per route. Tested with v8's own real
values (0,16/219,9/330,3) -- PASS across the 3 routes (see Decision 33
for the exact-threshold tests).

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 33. FAIL-CLOSED EVALUATOR -- no criterion ever returns `pass: None` again; criteria 2, 3, and 7 ACTUALLY IMPLEMENTED (no longer stubs); real mutation tests for all 3 (thresholds, above and below) plus a global test (empty directory/missing data -> all 7 criteria fail)

**1. Fail-closed principle, applied across the 7 criteria.** Before this
decision, "no data" resulted in `pass: None` (criteria 2, 3, 7
always; criterion 4 when `--calls-json` was missing) -- a state the
final report could mistakenly treat as "not relevant" instead of
"not authorized". Fixed: **missing data, file not found, or invalid
format now always result in `pass:
False`**, across ALL 7 criteria. `main()`'s status map
(`{"True":"PASS","False":"FAIL"}`) had the `"None"` branch removed on
purpose -- if some criterion ever returns `None` again, the script
breaks loudly and visibly (`KeyError`), instead of silently printing
"N/A".

**2. Criteria 2, 3, and 7 -- actually implemented, no longer
stubs.**

- **Criterion 2 (initcwnd >= 10):** `ip route show` only shows
  initcwnd when there is an explicit route override -- the kernel's
  effective value does not show up there by default. Method adopted:
  criterion 1's dedicated CAPTURE (Decision 24) already serves as a
  base -- count how many TCP SEGMENTS the SERVER sends (source port
  443) BEFORE the client's first ACK acknowledging those bytes; the
  system configuration (`sysctl`) is read as a CROSS-CHECK reference,
  never as the primary source. **Limitation explicitly recorded:**
  on local loopback the MSS is large enough to never actually
  segment -- this criterion structurally CANNOT be exercised against
  real local data, only against the pilot's real capture on a route
  with RTT > 0. The function `criterion_2_initcwnd(aws_dir)` reads
  `<aws_dir>/criterio2_initcwnd.json` (`{"server_segments_before_
  client_ack": N, "sysctl_reference": {...}}`), produced by this pcap
  analysis outside this function (the same trust pattern criterion 4
  already has with `--calls-json` -- the evaluator checks a result,
  it does not reimplement packet extraction).
- **Criterion 3 (0 errors, 20/20 at L325):** `criterion_3_
  distant_route(aws_dir)` reads `<aws_dir>/criterio3_l325_execucoes.json`
  (`{"execucoes": [{"profile", "route", "ok"}, ...]}`) and checks: 20
  EXACT entries, all `route=="L325"`, 4 distinct profiles x 5 each
  (`L325_PROFILES`/`L325_N_PER_PROFILE`), 0 with `ok=false`.
- **Criterion 7 (per-route RTT):** `criterion_7_latency_sanity(aws_dir)`
  reads `<aws_dir>/criterio7_rtt_por_rota.json` (`{"L0":{"rtt_ms":...},
  "L219":{...}, "L325":{...}}`, produced by `ping -c 20 <address>`,
  mean, explicitly defined method) and applies `_rtt_ok()` (Decision
  32) per route.

**3. Real mutation tests, run against the module (not
reimplemented), threshold by threshold:**

| Criterion | Mutation | Expected | Result |
|---|---|---|---|
| 2 | segments = 10 (exact threshold) | PASS | **PASS** |
| 2 | segments = 9 (1 below) | FAIL | **FAIL** |
| 2 | segments = 11 (1 above) | PASS | **PASS** |
| 3 | 20/20, 0 errors (baseline) | PASS | **PASS** |
| 3 | 1 error among the 20 | FAIL | **FAIL** |
| 3 | 19 runs (1 missing) | FAIL | **FAIL** |
| 3 | wrong route (L219 instead of L325) | FAIL | **FAIL** |
| 7 | L0 = 0,999ms (below the floor) | PASS | **PASS** |
| 7 | L0 = 1,0ms (at the floor, exclusive) | FAIL | **FAIL** |
| 7 | L219 = 197,1ms (exact lower bound, nominal-10%) | PASS | **PASS** |
| 7 | L219 = 197,0ms (1 step below) | FAIL | **FAIL** |
| 7 | L219 = 240,9ms (exact upper bound) | PASS | **PASS** |
| 7 | L219 = 241,0ms (1 step above) | FAIL | **FAIL** |
| 7 | L325 = 292,5ms (exact lower bound) | PASS | **PASS** |
| 7 | L325 = 292,4ms (1 step below) | FAIL | **FAIL** |
| 7 | L325 = 357,5ms (exact upper bound) | PASS | **PASS** |
| 7 | L325 = 357,6ms (1 step above) | FAIL | **FAIL** |
| 7 | baseline with v8's REAL values (0,16/219,9/330,3) | PASS | **PASS** |

**16 mutations, all with the expected result** -- confirms the
EXACT thresholds (inclusive on both ends) and v8's real values
passing comfortably within the adopted ranges.

**4. Global test: empty directory / missing data -> all 7 criteria
must fail.** Run with `log_text=""`, `calls_json=None`,
`aws_dir=<freshly created empty directory>` against the 7 criteria
directly: **all 7 gave `pass: False`**, confirmed one by one (not
assumed). Also reconfirmed via `main()` (real pipeline, empty log,
no `--calls-json`, no `--aws-dir`): criteria 2/3/4/7 FAIL
as expected; 1/5/6 remain PASS when there is real, valid data in the
log (confirmed in a second round, a real log from a fresh
`measure.sh` run) -- fail-closed did not break the criteria that
already worked.

**DATED NOTE (2026-11-07, independent review, item D.10e -- added
later, original text intact):** the fail-closed PRINCIPLE of this
decision (no criterion returns `pass: None`)
remains valid and was not touched afterward. But the measurement
METHOD this decision adopted for criterion 2 (counting segments
within a normal TLS handshake) **is SUPERSEDED BY Decision 34**
(Amendment 6 -- the method was wrong by construction, a normal
handshake never saturates the cwnd) and the method for criterion 7
(RTT via `ping`/ICMP) **is
SUPERSEDED BY Decision 35** (Amendment 7 -- the pilot's security
group would never open ICMP, replaced by a TCP/443 probe + pcap's
SYN/SYN-ACK). The mutation table numbers above (the "segments = 10"
row) were also redone under the new method, they are no longer in
force -- see Decision 34.

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 34. AMENDMENT 6 TO CRITERION 2 (T7, post-`v9-prereg` tag) -- Decision 33's method was wrong by construction (a TLS handshake never saturates the cwnd); a dedicated test adopted (>=64KB on a new connection, bytes/MSS, ss -ti cross-check, ethtool -k offloads recorded); evaluator, mutations, and synthetic data updated

**Formal amendment label:**
- **What changed:** criterion 2's METHOD (not the threshold, which
  remains >=10 segments) -- from "count segments within a normal TLS
  handshake" to a DEDICATED test (>=64KB on a new connection,
  `bytes_before_ACK / MSS`, with `ss -ti` and `ethtool -k` as
  mandatory cross-check evidence).
- **Reason:** the earlier method measured the wrong size -- the
  server's first flight (1,6-12KB across the 4 profiles) is SMALLER
  than 10xMSS (~14,5KB at MSS~1448B), so the server is ALWAYS limited
  by lack of data, never by the cwnd -- counting segments there would
  never prove initcwnd, it would only prove "how many segments fit in
  the handshake." Also, TSO/GSO on the sending side can aggregate
  multiple real segments into a single "super-packet" as seen by the
  capture, inflating or confusing the count.
- **Date:** 2026-11-07 (same day as Amendments 1-5).
- **The `v9-prereg` tag remains intact** -- the original threshold
  (Decision 14/24, >=10 segments) did not change and was not
  rewritten; only the measurement METHOD was fixed.

**Method adopted:** a NEW connection (outside the 60 statistical
runs, the same logic of separating capture from the timed
measurement, Decision 24), the server sends **>=64KB** (far more than
any reasonable initcwnd would cover) -- `bytes sent BEFORE the
client's first ACK / MSS` (MSS read from the SAME connection's SYN
OPTIONS, never assumed) gives the number of segments the initial cwnd
allowed. **Two confirmation channels, both mandatory:** (1)
`ss -ti` right after the connection, the `cwnd` field reported by the
kernel itself; (2) `ethtool -k` (`tso`/`gso`/`gro` state) -- if TSO or
GSO is on, the bytes/MSS count's result becomes suspect (the capture
might be seeing aggregated super-packets, not real wire segments) and
the criterion FAILS for this specific reason, even if the raw numbers
seemed to match.

`evaluate_criteria.py`: `criterion_2_initcwnd(aws_dir)` rewritten,
reads `<aws_dir>/criterio2_initcwnd.json` (`bytes_sent_total`,
`bytes_sent_before_first_client_ack`, `mss_bytes`, `ss_ti_cwnd`,
`offloads`). `INITCWND_MIN_BYTES_SENT = 64*1024` (precondition: the
test itself needs to have sent enough data, otherwise the result
proves nothing -- the same class of error that motivated the fix).

**7 mutations tested, all with the expected result:**
| Mutation | Expected | Result |
|---|---|---|
| baseline (65536B, 14480B before the ACK = exactly 10,0 segments at MSS 1448, ss confirms 10, offloads off) | PASS | **PASS** |
| computed segments = 9,99 (1 step below) | FAIL | **FAIL** |
| `ss -ti` says cwnd=9 (cross-check fails even with segments=10) | FAIL | **FAIL** |
| total sent = 32KB (< 64KB, invalid test) | FAIL | **FAIL** |
| TSO on | FAIL | **FAIL** |
| GSO on | FAIL | **FAIL** |
| no `--aws-dir` | FAIL | **FAIL** |

**DATED NOTE (2026-11-07, independent review, item D.10e -- added
later, original text intact):** the two "TSO on"/"GSO on" rows above
(FAIL solely for an offload being on, regardless of the bytes/MSS x
`ss -ti` agreement) **are SUPERSEDED BY Decision
37** (Amendment 9) -- failing whenever TSO/GSO is on would make the
criterion unreachable on real AWS (GSO comes on by default); the
offload became just recorded EVIDENCE, never a reason to FAIL by
itself, with the decision instead coming from the agreement between
bytes/MSS and `ss -ti`.
The rest of this decision's method (dedicated >=64KB test, bytes/MSS,
`ss -ti` cross-check) remains in force, only these two rows changed.

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 35. AMENDMENT 7 TO CRITERION 7 (T7, post-`v9-prereg` tag) -- ping (ICMP) would NEVER pass through the pilot's security group (only 443/22 open); researched how real v8 measured RTT in an EQUALLY restricted campaign -- a TCP/443 probe, not ICMP; adopted TWO TCP channels (dedicated probe + real pcap's SYN/SYN-ACK) with cross-confirmation; no new SG rule needed

**Formal amendment label:**
- **What changed:** criterion 7's METHOD -- from "RTT measured" (no
  explicit method) to two specific TCP channels, with a requirement
  that they agree with each other, not just each independently
  falling within range.
- **Reason:** the pilot's security group (Decision 27) only opens
  443 and 22 -- ping (ICMP) would always fail, without a new rule.
  Instead of opening a port just for this, I researched how real v8
  solved the SAME problem (its real campaign also restricted the SG
  to 443/22 per client, v8's Decision 49).
- **Date:** 2026-11-07 (same day as Amendments 1-6).
- **The `v9-prereg` tag remains intact** -- the acceptance range
  (nominal ±10%, with L0's floor from Amendment 5) did not change,
  only the METHOD of obtaining the number changed.

**Researched directly in `v8/DECISIONS.md`, not assumed:** line
8546-8554, **"Pre-flight TCP/443 (8 clients, 20 samples, 3
profiles)"** -- a TCP CONNECTION probe on port 443 (not ICMP), whose
medians (L0 0,14-0,18ms, L123 122,9ms, L14 15,4ms, L219 219,9ms,
L30 32,3ms, L325 330,3ms) are exactly the numbers this
project already cited as "what v8 measured" -- now with the method's
source confirmed, not just the number. Real v8 also has a SECOND
method, used in the post-campaign analysis (line 9970-9971): RTT =
median of the SYN->SYN-ACK from the actually measured TLS connections
themselves, straight from the pcap -- zero extra port or connection.

**Method adopted for v9, both together:**
1. `rtt_ms_probe`: a TCP connection probe on port 443 (the same
   "Pre-flight TCP/443" method as real v8), N samples, median.
2. `rtt_ms_pcap`: SYN->SYN-ACK extracted directly from the dedicated
   capture (criterion 1/2) of the real TLS connections -- zero cost,
   the data already exists.
Both need to pass the acceptance range (Amendment 5) **AND**
agree with each other (`_rtt_consistent`, Δ <= max(1ms, 10% of the
larger) --
a real cross-check, not two loose numbers that happen to each pass
their own range).

**The pilot's procedure: NO new security group rule is
needed** -- both methods use already-open ports/connections
(443). Explicitly recorded: if Luciano wants ping as a
THIRD channel (not required by this criterion), it would need a new
ICMP echo request/reply rule, client by client, against the
server -- NOT included in the procedure, since it is not necessary.

**6 mutations tested, all with the expected result** (including
v8's own real values as the baseline):
| Mutation | Expected | Result |
|---|---|---|
| baseline (v8's real values, probe+pcap consistent) | PASS | **PASS** |
| L0 both well below the 1ms floor | PASS | **PASS** |
| L0: probe ok, pcap at/above the threshold (1,2ms) | FAIL | **FAIL** |
| L219: probe=200 pcap=238 (both within their individual range, but diverge >10% from each other) | FAIL (inconsistency) | **FAIL** |
| L325 missing from the file | FAIL | **FAIL** |
| no `--aws-dir` | FAIL | **FAIL** |

**DATED NOTE (2026-11-07, independent review, item D.10e -- added
later, original text intact):** the agreement threshold used above
(`Δ <= max(1ms, 10% of the larger)`) was a FIRST number, with no
explicit numerical justification per route --
**it is SUPERSEDED BY Decision 38** (Amendment 10), which defines the
real, per-route-differentiated threshold (absolute 0,5ms for L0, 5%
of NOMINAL for L219/L325, not "10% of the larger measured value").
The TWO channels (TCP/443 probe + pcap's SYN/SYN-ACK) and the
decision that no new SG rule is needed remain in force, untouched by
this change.

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 36. AMENDMENT 8 TO CRITERION 4 (T7, post-`v9-prereg` tag) -- the "6 client-facing mTLS connections" count (44/6/28/4/4, Decision 17/18) had never been wired into the evaluator; added by counting the gateway's real "connection OK", excluding the internal carve-out; the dedicated TCP/443 probe (Decision 35) is EXCLUDED BY CONSTRUCTION (never completes a handshake, never produces this line)

**Formal amendment label:**
- **What changed:** `criterion_4_counts` gained a fifth field
  (`mtls`, expected =6) and a second parameter (`log_text`) -- before
  it only checked http/jwts/jwks/ca.
- **Reason:** while auditing Luciano's request about probe pollution,
  I confirmed that "6 client-facing mTLS connections" (the full
  44/6/28/4/4 count that Decision 17/18 verified MANUALLY) had never
  been wired into this automatic evaluator -- a real gap,
  found along the way, beyond what was asked.
- **Date:** 2026-11-07 (same day as Amendments 1-7).
- **The `v9-prereg` tag remains intact.**

**Method:** counts the `"gateway: PROFILE connection OK
remoteAddr=... sni=\"...\" ..."` lines that `business_server.go`
(line 103,
`acceptBusinessConn`) actually writes -- each one is a COMPLETE,
successful TLS handshake. **Explicitly excluded:** the internal
carve-out (`sni="matls-api.local"`, `internalCallerSNI`) --
auth calling back to the RS, not one of the "6" client-facing ones
(same logic as Decision 18/19). **Excluded BY CONSTRUCTION, with no
special filter:** the dedicated TCP/443 probe (Decision 35, for
criterion 7) NEVER completes the TLS handshake (closes the connection
before sending the `ClientHello`, or never sends anything) --
`tlsConn.Handshake()`
returns an error and the real code writes `"gateway: PROFILE: handshake
failed: ..."` (PLAIN TEXT, line 75 of `business_server.go`), never
the `"connection OK"` line this count looks for. **Just counting real
successes already excludes the probe's failed attempt, with no need
to recognize the probe specifically.**

**5 mutations tested:**
| Mutation | Expected | Result |
|---|---|---|
| baseline: 6 client-facing "connection OK" + 1 internal + 1 failed probe | PASS (mtls=6) | **PASS** |
| 5 "connection OK" (1 missing) | FAIL | **FAIL** |
| 7 "connection OK" (one extra) | FAIL | **FAIL** |
| only the failed probe line in the log, no real connection | FAIL (no improper PASS) | **FAIL** |
| 6 "connection OK" + 5 failed probe attempts | PASS (does not inflate the count) | **PASS** |

## 37. AMENDMENT 9 TO CRITERION 2 (T7, post-`v9-prereg` tag) -- failing for TSO/GSO being on would make the criterion unreachable (GSO comes on by default on AWS); fixed -- offloads are always RECORDED as evidence, never fail by themselves; the decision comes from the AGREEMENT between bytes/MSS and `ss -ti` cwnd, with a defined maximum difference (2 segments); instance offloads are NEVER altered (equivalence with real v8)

**Formal amendment label:**
- **What changed:** Decision 34 had `offload_risk` (TSO or GSO
  on) directly fail the criterion. Fixed: `ethtool -k`
  is always REQUIRED in the file (must be recorded), but its
  CONTENT never decides pass/fail anymore -- the decision now comes
  from the AGREEMENT between the two independent channels
  (`segments_computed` via bytes/MSS, and `ss_ti_cwnd`), with an
  EXPLICIT maximum acceptable difference: **`INITCWND_MAX_DIFF_
  SEGMENTS = 2`** (justified: absorbs a small timing offset in the
  `ss -ti` snapshot -- if one or two initial ACKs have already
  arrived before the snapshot, the cwnd may have already grown one
  slow-start step beyond the pure initcwnd -- without being so wide
  that it fails to detect a real disagreement between the two
  methods).
- **Reason:** failing solely because TSO/GSO is on would make the
  criterion practically unreachable -- **GSO is usually on by
  DEFAULT on the kernel of the EC2 instances** used here, and
  counting bytes sent before the ACK divided by the negotiated MSS
  is INDEPENDENT of how many "super-packets" the NIC decided to make
  along the way (the byte count and the MSS are the same, offload on
  or not). Also, turning the offloads off just for this test would
  diverge from real v8, which never touched this -- **kept: the
  pilot instances' offloads are NOT altered**, by deliberate
  equivalence with v8.
- **Date:** 2026-11-07 (same day as Amendments 1-8).
- **The `v9-prereg` tag remains intact** -- the >=10-segment
  threshold (Decision 14/24) did not change; only the decision method
  (now by agreement, not by offload blocking) was fixed.

**4 mutations tested:**
| Mutation | Expected | Result |
|---|---|---|
| TSO=on, GSO=on, segments=10,0, `ss`=10 (agree) | PASS (offload no longer blocks) | **PASS** |
| segments=10,0, `ss`=12 (difference=2, exact limit) | PASS | **PASS** |
| segments=10,0, `ss`=13 (difference=3, 1 step beyond) | FAIL | **FAIL** |
| `offloads` field missing from the file (must be recorded, even though it doesn't decide) | FAIL | **FAIL** |

## 38. AMENDMENT 10 TO CRITERION 7 (T7, post-`v9-prereg` tag) -- maximum acceptable difference between the TCP/443 probe and the pcap's SYN/SYN-ACK, explicitly defined: absolute (0,5ms) for L0, percentage (5% of nominal) for L219/L325

**Formal amendment label:**
- **What changed:** `_rtt_consistent()` (Decision 35) had no
  explicit, per-route number -- fixed with
  `RTT_CONSISTENCY_ABS_MS = {"L0": 0.5}` and
  `RTT_CONSISTENCY_FRACTION = 0.05`.
- **Reason:** Luciano correctly pointed out that the agreement
  requirement existed with no defined number.
- **Date:** 2026-11-07 (same day as Amendments 1-9).
- **The `v9-prereg` tag remains intact.**

**Justification of the numbers:** **L0 uses an ABSOLUTE difference
(0,5ms)**
-- a percentage makes no sense with a nominal of 0 (the same
structural reason as Amendment 5); 0,5ms gives a generous margin over
the expected precision of the two methods themselves at this scale
(real v8 measured 0,14-
0,18ms, a spread of ONLY 0,04ms between samples of the SAME method --
0,5ms covers this with room to spare). **L219/L325 use a PERCENTAGE
difference
(5% of the route's NOMINAL)** -- deliberately STRICTER than the
criterion's own acceptance range (±10%, Decision 20/24):
agreement between two methods measuring the SAME physical quantity
needs to be tighter than "within the acceptable range," otherwise the
cross-check adds no rigor at all over the individual criterion
(L219: 219ms x5% = 10,95ms; L325: 325ms x5% = 16,25ms).

**6 mutations tested, exact threshold and 1 step beyond, across the 3 routes:**
| Mutation | Expected | Result |
|---|---|---|
| L0 difference = exactly 0,5ms (limit) | PASS | **PASS** |
| L0 difference = 0,51ms (1 step beyond) | FAIL | **FAIL** |
| L219 difference = exactly 10,95ms (5% of nominal) | PASS | **PASS** |
| L219 difference = 10,96ms (1 step beyond) | FAIL | **FAIL** |
| L325 difference = exactly 16,25ms (5% of nominal) | PASS | **PASS** |
| L325 difference = 16,26ms (1 step beyond) | FAIL | **FAIL** |

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 39. INDEPENDENT REVIEW OF HEAD 23ee2ceb -- 4 real bugs confirmed and fixed in the AND patch (strict mode did not abort without dual authentication; Dual* fields leaked without DualAuthenticated; a misconfigured server fell back to RSA; sameDualIdentity was vacuously true with no SAN); 4 new tests (27 in total, full suite green); amd64/arm64 binaries rebuilt, hashes and build_metadata.json updated

**Context.** An independent review of commit `23ee2ceb` (the HEAD at
the time) found 4 real bugs in the AND mechanism (`dual.go`,
`handshake_client_tls13.go`, `handshake_server_tls13.go`) -- handled
here with evidence (code read, test written and RUN against the
real module, not just described), fixing what was confirmed. Since
this changes the binaries' hash, it was done first, before any other
item in this round.

**1. Strict mode did not enforce AND on acceptance -- CONFIRMED and
fixed.** Reading `readServerCertificate` (client) and
`readClientCertificate` (server): the `else` branch (classical
CertificateVerify) never checked `c.config.Dual.Require` -- a peer
that negotiated/offered dual but signed classically would be
accepted as classically authenticated, `DualAuthenticated=false`,
**with no error at all**, even with `Require=true` promising this
was impossible.
**Fixed:** at the end of both functions (after both branches had a
chance to set `dualAuthenticated`), `Require &&
!dualAuthenticated` sends an alert (`alertHandshakeFailure`) and
aborts
the handshake.

**Real, not hypothetical, test hook.** Added
`testingOnlyForceSingleChainCertificateVerify` (`dual.go`, package
var, the same pattern Go upstream itself already uses --
`testingOnlySupportedSignatureAlgorithms`, confirmed by reading
`common.go`) -- forces THIS side to sign with isolated
RSA-PSS-SHA256, single chain, even when dual was negotiated, working
around normal algorithm negotiation (which would fail for an
UNrelated reason against a strict peer whose offered list is only
`[0xFE65]`) by hardcoding
`PSSWithSHA256` directly at both signing points (client and server).
**2 new tests, for both roles, PASSED:**
- `TestDualStrictClientRejectsServerThatIgnoresTheOffer`: a
  dual-capable (NON-strict) server hooked to sign single-chain;
  strict client -- handshake fails, `DualAuthenticated=false`.
- `TestDualStrictServerRejectsClientThatIgnoresTheOffer`: symmetric,
  a dual-capable client hooked; strict server -- handshake fails.

**2. `DualPeerCertificates`/`DualVerifiedChains` leaked without
`DualAuthenticated` -- CONFIRMED and fixed.** These fields were set
as soon as the PQ chain was structurally/cryptographically valid
(inside `if len(certMsg.dualPQCertificate) > 0`), BEFORE knowing
whether the `CertificateVerify` actually used the dual scheme -- a
caller inspecting `ConnectionState` could see these fields populated
even when `DualAuthenticated=false` (valid chain, but key possession
never proven). **Fixed:** moved inside the
`certVerify.signatureAlgorithm == dualSignatureScheme` branch,
together with
`c.dualAuthenticated = true`, on both sides -- the local
values (`dualPeerCerts`/`dualVerifiedChain`) keep being computed in
their original place (they still need to exist for
`verifyDualMessage` to use), only the EXPORTED `ConnectionState`
fields moved.
No dedicated new test (not explicitly requested) -- a low-risk,
mechanical change, confirmed by inspection and by the full suite
remaining green.

**3. A server with `Require=true` and empty `Dual.Certificates` fell
back to
RSA -- CONFIRMED and fixed.** `len(c.config.Dual.Certificates) > 0`
guarded the dual branch; without it, the code fell straight through
to classical selection, with NO warning that the server's own
configuration could never satisfy `Require=true`. **Fixed:** an
explicit check at the start of `pickCertificate` -- `Require=true`
with empty
`Certificates` is a configuration error (`alertInternalError`), not a
silent fallback. **New test, PASSED:**
`TestDualServerRequireWithEmptyCertificatesIsConfigError`.

**4. `sameDualIdentity` was vacuously true with no SAN -- CONFIRMED,
fixed, and the FIRST fix broke real tests (honestly recorded, not
hidden).** Two empty SAN lists compare as equal (`len(a)==len(b)==0`)
-- an attacker could pair a classical certificate and a PQ one with
NO SAN AT ALL, of completely different identities, and pass as "same
identity."

**Real error along the way:** the first version of this fix
REJECTED outright any pair with no SAN under `Require=true` --
running the full suite, this BROKE `TestDualStrictFullMTLS` and
`TestDualHandshakeAcrossHelloRetryRequest`, two tests that ALREADY
EXISTED and had always been green until now: this project's CLIENT
certificates are, by its own convention, deliberately SAN-less
(identified by
`Subject.CommonName`, not by SAN) -- a legitimate pattern already in
use,
not a gap. Fixing this by rejecting everything would have fixed one
bug by introducing another.

**Final fix, tested and green:** `sameDualIdentity` now, when
NEITHER leaf has any SAN at all, falls back to comparing
`Subject.CommonName` (non-empty on both sides, and equal) instead of
vacuously accepting. This keeps `TestDualStrictFullMTLS` passing (the
client's classical/PQ pair legitimately uses the SAME CommonName,
"and-client") and rejects a pair of DIFFERENT identities that
also have no SAN. **New test, with DELIBERATELY DIFFERENT
CommonNames (simulating the real attacker, not the legitimate
case), PASSED:** `TestDualClientSANlessIdentityRejectedWhenRequired`.

**5. Full suite re-run, binaries rebuilt.** Toolchain
rebuilt from scratch (fresh go1.27.3 clone, new patch applied,
`make.bash`, full `crypto/tls` suite): **`ok crypto/tls 153.090s`**
-- 0 FAIL, including the 23 original AND tests + the 4 new ones (27
in total) + the entire Go upstream suite. `gateway`/`proxy`
rebuilt for `linux/amd64` AND `linux/arm64` with the fixed toolchain,
reproducibility reconfirmed (rebuild from scratch, same hash):
```
gateway amd64: d1aa962d01788e053c0cc4efd4f146f5a55c654026d758661023a106cac8d588
gateway arm64: 1afd6f51a03af905e677e5f4bb1122bddb9da1e0768776a903bac06b5241ab24
proxy   amd64: 819f21de28c9942f3b22f886d71f5e60374107110c18b4e40e7a9e5352212f11
proxy   arm64: f23877763b1ceaf129b5b2f292ec16c281f07f66c8b4c7b2df6f6719db41f738
```
**Supersede the hashes from Decision 22** (`gateway fa4c9c32...`,
`proxy
a4f901a9...`, amd64 only, pre-fix) -- those binaries had
bug #1 (strict mode did not enforce AND), **must never be used in
the pilot.** `toolchain/build_metadata.json` updated
(new `and_patch_sha256`, new `built_at_utc`).

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 40. INDEPENDENT REVIEW, SECTION B -- evaluator rewritten: criterion 4 isolates EACH run's window (readiness probe no longer pollutes the count), criteria 1/6 require the pilot's real cardinality (12 captures / 60 runs) in pilot mode, criterion 3 fixes a type bug (the `"false"` string counted as success), criterion 7 validates numeric/non-negative/minimum samples, criterion 2 requires route/instance/profile, `ZERO_TOLERANCE_MESSAGES` removed, fail-closed decorator across all 7 functions

**1. Criterion 4 (item B.6) -- the readiness probe was polluting the
count, CONFIRMED and fixed.** The readiness probe (one per profile
BLOCK SWITCH, Decision 23) completes a real mTLS handshake (the proxy
always dials upstream with its real certificate, Decision 18) --
counting "connection OK" across the ENTIRE log (as Decision
36 did) adds the probe together with the block's 15 runs, never
matching exactly 6 per run. **Fixed:** the evaluator now
requires explicit per-run markers in the pilot's combined log
-- `== EXECUCAO INICIO perfil=X rota=Y run=N ==` ... `== EXECUCAO
FIM ... ==` -- and counts "connection OK" ONLY within that specific
run's window (`_execucao_window`). The probe, which runs BEFORE
the first INICIO marker of each block, falls structurally outside
any window -- **excluded by construction, confirmed by
test** (synthetic log with a probe + 2 runs of 6 connections
each: both runs read exactly `mtls=6`, the probe never
entered the count).

`criterion_4_counts` changed signature: it now takes a LIST of
runs (`[{"profile","route","run","insurance":[...],
"person":[...]}, ...]`), evaluating all **60/60**, not a single
`calls_json`. `--calls-json` on the CLI now expects this list.

**2. Criteria 1 and 6 (item B.7) -- real cardinality required in
pilot mode.** Criterion 1 requires the 12 captures (4 profiles x 3
routes) -- with `--aws-dir`, it reads `<aws_dir>/criterio1_capturas/
<profile>_<route>.log` for the 12 combinations and FAILS if any is
missing (tested: 11/12 present -> FAIL, with the missing capture
explicitly named). Criterion 6 reconciles with Decision 24's TEXT
("CurveID and DualAuthenticated across 60/60 runs, 0
failures") -- with `--aws-dir`, it reads `<aws_dir>/criterio6_execucoes.json`
(a list of 60) and requires all 60, each with `keylog_evidence=true`
too. Without `--aws-dir`, both keep their earlier local
behavior (development use, with an explicit note that this alone is
not enough for the real criterion).

**3. Criterion 3 -- real type bug, CONFIRMED and fixed.**
`not e.get("ok")` is `False` for ANY non-empty string, including
the literal text string `"false"` -- a malformed JSON with `"ok":
"false"` (instead of the boolean `false`) would silently pass as
"no error." **Fixed:** `e.get("ok") is not True` now
counts as an error -- tested (an entry with the literal `"ok": "false"`
now gives FAIL, correctly detected; the real boolean `true`
still passes).

**4. Criterion 7 -- type/sign/sample-count validation added.**
RTT must be NUMERIC, NON-NEGATIVE (bool explicitly excluded
-- `bool` is a subclass of `int` in Python, `isinstance(True, int)` is
`True`), and the probe's sample count (`n_samples_probe`) must
be >= `RTT_MIN_SAMPLES = 20` (the same N real v8's "Pre-flight
TCP/443" used). **4 mutations tested:** negative RTT -> FAIL; RTT
non-numeric (string) -> FAIL; N=19 (1 below) -> FAIL; N=20 (exact
threshold) -> PASS.

**5. Criterion 2 -- route/instance/profile identification required
(item B.8).** The JSON now needs `route`, `instance_type`,
`profile` (validated against `PILOT_ROUTES`/`PROFILES_ALL`) --
without this, an isolated initcwnd result cannot be traced back to
where it was measured. Tested: with all 3 fields -> PASS; without
`route` -> FAIL.

**6. `ZERO_TOLERANCE_MESSAGES` removed** (not edited, REMOVED --
explicit request "remove it if it's unused"), confirmed to no
longer control anything since Amendment 4.

**7. Fail-closed extended to ALL 7 functions via a decorator.**
`_safe_criterion(N, name)` wraps each function -- any unforeseen
exception (a wrong type not covered by an explicit check, an
out-of-range index) now turns into `pass: False` with the exception
recorded in the note, NEVER a traceback bubbling up to the caller.
**Tested with 4 deliberately malformed inputs** (log_text
as an integer, a list turned into a string, an object's JSON turned
into a list, a run missing expected fields) -- all 4 gave FAIL,
none crashed.

**This round's test suite: every mutation ran against the
REAL module** (`evaluate_criteria.py` imported, not
reimplemented), covering the 7 items above -- 20 assertions, all
passed.

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 41. INDEPENDENT REVIEW, SECTION C -- the 3 data producers for criteria 2, 3, and 7 (described only so far) actually written and tested locally, end to end with the evaluator

`thesis/results/v9/integration/producers/` (new):

**1. `criterio2_probe.py`.** Event order exactly as requested
(item C.9): `tcpdump -s 0` comes up first; accepts the test
connection; takes the `ss -ti` snapshot IMMEDIATELY, BEFORE sending
any byte (after that the cwnd would already grow via slow-start);
sends 70KB (>64KB required); stops the capture; extracts the MSS
(from the server's SYN-ACK options) and bytes before the client's
first ACK via `tshark`; always records `ethtool -k` (tso/gso/gro).
**Tested end to end, for real, in a container with
`tcpdump`/`tshark`/`ss`/`ethtool`
installed:** ran against a test connection on loopback,
produced valid JSON with `ss_ti_cwnd=10` (read from a real `ss -ti`,
not simulated) and `offloads={"tso":"on","gso":"on","gro":"on"}`
(confirmed: TSO/GSO comes ON by default even in a generic
container -- empirically corroborating Amendment 9's reason for not
failing because of it). `bytes_sent_before_first_client_ack` came out
`null`
in this test -- **empirically confirms, not just in theory, the
already-recorded limitation**: on loopback (and with GSO on) the
entire payload shows up as a single segment in the capture before
any real ACK, exactly the visibility effect that motivates needing a
real pilot route for this number to mean anything.

**2. `criterio3_collector.py`.** Only aggregates -- reads a directory
of per-run JSONs (`{"profile","route","ok"}`, the same format the
orchestrator already produces) and filters for `route=="L325"`.
**Tested
end to end:** 20 L325 files + 3 L219 files (noise, to confirm
the filter) -> `criterio3_collector.py` -> the real
`criterion_3_distant_route()`
-> **PASS, 20 runs** (the 3 L219 ones correctly ignored).

**3. `criterio7_rtt.py`.** Two subcommands for the two channels:
`probe`
(a real TCP connection, N samples, median -- **tested for real**:
20 real connections against a test listener, median 0,819ms,
`n_samples=20`) and `pcap` (SYN->SYN-ACK via `tshark` on an existing
capture); `combine` merges both per route into the final format.
**Tested end to end, across the 3 routes:** `combine` x3 (L0/L219/L325,
with v8's real values as synthetic input) ->
the real `criterion_7_latency_sanity()` -> **PASS**.

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 42. INDEPENDENT REVIEW, SECTION D -- formal amendments recorded (criterion 6 vs. Decision 24, Decision 26's topology, the evaluator's interpretive choices); Certificate tolerance reduced from ±50B to ±4B (fixed SAN, measured baseline); "superseded by" notes marked on Decisions 25, 33, 34, and 35

**(a) Criterion 6 vs. Decision 24 -- AMENDMENT 11 TO CRITERION 6,
formalized now (the work itself was already done in Decision 40,
item 2, just without the formal amendment label).** Decision 24
(T7's table) defines criterion 6 as "keylog + capture + per-message
sizes successfully extracted in 100% of the 60 runs...
`ConnectionState.CurveID`... and `DualAuthenticated`... assertions
passing in 60/60, 0 failures." Decision 40 already reconciled
`criterion_6_instrumentation`
with that exact text: in pilot mode (`--aws-dir`), it reads
`criterio6_execucoes.json` (a list of 60) and requires all 60 present,
EACH
with `keylog_evidence=true`. **Nothing changes in the code here** --
only the formal label: this is Amendment 11, dated 2026-11-07, reason
"explicit request from the independent review to record as a
numbered amendment what had already been fixed in prose in Decision
40".

**(b) Decision 26's topology -- already recorded as a dated note
in Decision 25 itself, above** (see the DATED NOTE added to
Decision 25 in this same commit): Decision 26 is marked as the
amendment that fixes Decision 25 on that specific point, with the
formal "superseded by" label, no longer just the title "REAL ERROR
corrected."

**(c) The evaluator's interpretive choices -- documented,
confirmed or contested with evidence, not accepted on argument
alone:**

- **N=5 runs per profile in criterion 3 -- CONTESTED: this is not an
  interpretive choice by the evaluator.** `L325_N_PER_PROFILE = 5`
  (`evaluate_criteria.py`, line 529) implements, literally, what
  Luciano himself requested ("0 errors in 20/20 runs (4 profiles x
  N=5) at sa-east-1/L325", a request that predates this review) --
  the evaluator did not invent this number, it only encoded it.
  Recorded here so it does not go unanswered, but with no code
  change.
- **The FATAL heuristic (criterion 5) -- CONFIRMED as a real
  interpretive choice, with a documented limitation.**
  `criterion_5_zero_errors` excludes lines containing `"FATAL:"` IF
  they ALSO contain `>&2` or `exit 1` on the same line -- reason: the
  Dockerfile echoes its own source command
  (`echo "FATAL: ..." >&2; exit 1; }`) in the build log even on a
  successful build, and the first version of this evaluator confused
  this echoed line with a real failure (found live, Decision 22).
  **Honest limitation, not hidden:** a real FATAL message that
  happens to contain the substrings `>&2` or `exit 1` on the
  SAME line (e.g., a stack trace citing this shell snippet)
  would be incorrectly excluded -- low probability (no real error
  message from this project's actual stack has this format,
  confirmed by the real logs already seen in T6/T6b), but not zero.
  No code change proposed now (the heuristic works on the
  real data already seen); recorded as a known limitation, not
  as a bug.
- **Reading of criterion 6 -- see item (a) above.**

**(d) Certificate tolerance -- reduced from ±50B to ±4B, a fixed SAN
and a measured baseline make the old margin unjustifiable.**
`CERTIFICATE_TOLERANCE_B` (evaluate_criteria.py, line ~80) changed from
`50` to `4`. **Reason:** the ±50B margin was only justified when the
server's SAN itself was uncertain (Amendment 1, Decision 28) -- today
the
SAN is FIXED (Decision 29/30) and the baseline is MEASURED, not
estimated. The
only legitimate source of variability left is the certificate's
serial number ASN.1 integer (up to ±2B per server leaf certificate
from sign-padding; Hybrid-AND has 2 server leaf certificates,
Decision 29, doubling it to ±4B in the worst case). **Tested
against the real module** (not simulated, 7 mutations with
`_message_sizes_for_profile` called directly, `classico` profile,
baseline 899B):

| Delta over the baseline | Expected | Result |
|---|---|---|
| +0B (exact baseline) | PASS | **PASS** |
| +4B (exact upper limit) | PASS | **PASS** |
| -4B (exact lower limit) | PASS | **PASS** |
| +5B (1B above the new limit) | FAIL | **FAIL** |
| -5B (1B below the new limit) | FAIL | **FAIL** |
| -6B (hypothetical SAN with 1 fewer IP) | FAIL | **FAIL** |
| -14B (Decision 29's real regression -- EIP missing from the SAN) | FAIL | **FAIL** |

**Confirms the reason for the change:** with the old tolerance
(±50B), the real -14B regression (or -28B on Hybrid-AND) would have
passed silently -- with ±4B, it correctly fails. None of the 4
MEASURED baseline values (899/5618/6241/6554) needed to change.

**"Superseded by" notes marked this round (each decision's original
text intact, a note added at the end of each one):**
Decision 25 (superseded by Decision 26, regional cost item), Decision
33 (superseded by Decisions 34 and 35, criteria 2 and 7's method), Decision
34 (superseded by Decision 37, offload gating), Decision 35 (superseded
by Decision 38, RTT agreement threshold).

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 43. INDEPENDENT REVIEW, SECTION E -- control's SSH contested with real v8 evidence (no rule fix needed, explicit requirement added to the procedure to prevent regression); final cleanup check extended to 5 calls per region, same as v8's real teardown; certificate generator's NotBefore backdated 1h

**1. SSH FROM THE CONTROL TO THE CO-LOCATED SERVER/L0 (item E.11) --
CONTESTED WITH EVIDENCE: the current rule (Decision 26/27, the
control's elastic IP) already works by construction, as long as v9's
future orchestrator ALWAYS dials each target by its PUBLIC IP --
this requirement is now explicitly added to the procedure, to never
regress.**

The review's concern (the control and the server/L0 share the
SAME VPC/region -- a TCP connection's real origin there could be
the control's PRIVATE IP, which a `/32` EIP rule would never match)
is a LEGITIMATE concern in the abstract -- but it has a concrete
EMPIRICAL answer, found in v8's own real history, not assumed:
`v8/DECISIONS.md`, Decision 83, finding #6 (a real incident,
not fixed in time, the pilot destroyed before it was resolved). This
incident confirms, by a direct test on a real instance
(`/dev/tcp` to the server's public IP: timeout RC=124; to the
PRIVATE IP: success RC=0), AWS's exact mechanics for
SAME-VPC traffic addressed to another instance's public/Elastic IP:
**"routes out through the Internet Gateway and back -- which
rewrites the source to the sender's OWN public IP by the time it
reaches the destination's security group."** In other words: when
one instance dials ANOTHER instance of the SAME VPC via its PUBLIC
IP, the packet goes out and comes back through the IGW, and the
origin the destination VPC SEES is the dialer's OWN PUBLIC IP --
never the private IP.

**Applied to the control -> server/L0 SSH:** `v8/campaign/scripts/
campaign_run.py` (`SSHExecutor._server_ip`/`_client_ip`, lines
1476-1474) uses `public_ip` ALWAYS, including for the server/client
co-located in the control's own region -- never the private IP,
even when available. And the real SG rule (`terraform/main.tf`,
line 285/419, `ssh_ingress_cidrs = {"control" = "${module.control.
public_ip}/32"}`) requires exactly this public IP as the origin. By
the mechanism confirmed in incident 83 (same VPC + public-IP
addressing = the observed origin is the sender's public IP), **both
ends are CONSISTENT by construction**: the control dials via the
public IP, the rule expects the public IP, they match -- which is
why NO failed-SSH incident between the control and the co-located
server/L0 was ever recorded in all of `v8/DECISIONS.md` (only the
GATEWAY/443 data path, Decision 83 item 6, had this problem -- and
exactly because THERE the SG rule expected the PRIVATE IP by design,
v8's Decision
28/41, while the code dialed via the public one by mistake --
an INTENT-vs-CODE mismatch, not a network impossibility). SSH never
had this ambiguity of intent: neither v9's Decision
26/27 nor real v8's pattern ever proposed using the control's
PRIVATE IP for SSH.

**Decision: v9's SG rule (Decision 26/27, the control's EIP) stays
UNCHANGED** -- it is not the bug the review suspected. **But a new,
explicit requirement enters the procedure, to NEVER regress into the
same mismatch as incident 83:** when v9's real orchestrator is
written (it does not exist yet -- "no AWS" still holds), its
functions equivalent to `_server_ip`/`_client_ip` MUST
use each target's PUBLIC/Elastic IP for SSH, ALWAYS, including for
the server and the L0 client co-located with the control --
NEVER the private IP for this specific purpose (SSH), even though the
private IP is correctly used ELSEWHERE, as the L0 client's
GATEWAY/443 traffic already does, by design, Decision 27 item 1).
This is exactly the class of bug incident 83 documented --
not SSH, but the SAME networking mechanism -- so the requirement is
recorded here BEFORE any real code exists, not after an identical
incident repeats.

**2. FINAL CLEANUP (item E.12) -- check extended to 5
calls per region, same as real v8's proven teardown;
real orphaned-EIP risk identified in the auto-shutdown safety net,
mitigated by detection rather than new automation.**

**Extended check, confirmed against a real precedent:** real v8's
final teardown (`v8/DECISIONS.md`, line 8325-8334) used
exactly `aws ec2 describe-instances`/`describe-addresses`/
`describe-security-groups`/`describe-key-pairs`/`describe-volumes`,
one call each per region, across the 7 regions -- not just the tag
API. **The same pattern adopted for v9's procedure:** the final
check (Decision 26, item 2, today only `resourcegroupstaggingapi`)
now runs the SAME 5 calls, across the pilot's 3 regions
(`sa-east-1`/`eu-north-1`/`ap-southeast-1`), both on the normal
teardown
and on the emergency abort (Decision 27, item 3) -- expected empty
across the 5 calls x 3 regions.

**Real orphaned-EIP risk -- identified, not on the path the review
cited.** The explicit ABORT procedure (Decision 27, item
3) already uses `terraform destroy`, which destroys the `aws_eip`
resource
TOGETHER with the instance -- this path NEVER leaves an orphaned EIP.
**The real risk is elsewhere: the time-based
auto-shutdown safety net** (`self_terminate_hours`, Decision 23 item
5, "auto-shutdown fixed to terminate") -- this mechanism runs
INSIDE the instance itself and can only terminate ITSELF (via
IMDS/systemd), never release its OWN EIP (that is an account-level
call, `release-address`, outside the reach of an instance terminating
itself without a dedicated IAM role for that). **If this
auto-shutdown fires with no `terraform destroy` following** (e.g.,
the operator unavailable, the instance terminated by the safety net
but
no one runs the destroy afterward), the corresponding EIP stays
allocated and
billing US$0,005/h indefinitely, per EIP. **Mitigation chosen,
deliberately WITHOUT giving self-terminate a new permission to
release its own EIP** (against this project's least-privilege
principle -- adding this permission just for this rare case does not
outweigh the risk of a compromised instance being able to call
`release-address` on its own): the 5-call check from the item
above, run MANDATORILY after ANY pilot session
(success, abort, OR auto-shutdown), `describe-addresses` always
catches any EIP with no associated instance, across the 3 regions --
an explicit finding turns into a manual release
(`aws ec2 release-address`), it never slips by unnoticed.

**3. CERTIFICATES, NotBefore backdated (item E.13) -- done and
tested against the real toolchain.**

`certs/main.go`: a new function `certNotBefore()` (`time.Now().Add(-1 *
time.Hour)`), replacing the 5 occurrences of `NotBefore:
time.Now()` across the 4 profiles (CA and leaf, RSA and ML-DSA-65) --
absorbs clock skew between the machine generating the certificates
and the pilot's real instances (if the instance's clock is a few
minutes AHEAD relative to this machine, a certificate without this
margin would look "not yet valid" on the first connection).
`NotAfter` kept anchored to the real `time.Now()` (not backdated) --
backdating it would only needlessly shorten validity, the problem is
only at the window's LOWER bound. **Tested for real, not just
compiled:** a build inside the real container (`mockopin-v9-toolchain`)
succeeded, and a full `go run .` generating the 4 profiles with the
program's own internal validation (`x509.Certificate.Verify`, with no
`InsecureSkipVerify`) passing for all chains -- confirms that
a NotBefore 1h in the past breaks no verification (the verifier
only requires `NotBefore <= now <= NotAfter`, and "now" remains well
after "now - 1h").

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 44. INDEPENDENT REVIEW, SECTION F -- the matls-api.local SNI carve-out's limitation declared explicitly (confirmed in the code: `Dual = nil`); IAM username removed from DECISIONS.md (dated note); no other account identifier found in v9's version-controlled files

**1. THE `matls-api.local` SNI CARVE-OUT -- LIMITATION declared
explicitly, confirmed DIRECTLY in the code, not by argument.**

`gateway/business_server.go`, `attachInternalCallerCarveOut` (line
146-203): when the ClientHello arrives with SNI `matls-api.local`
(the reentrant AS->RS call that uses REAL production certificates,
not v9's 4 profiles), the config the gateway uses for this
connection explicitly has:
```go
internalCfg.Dual = nil // the internal caller never presents a dual cert
```
**This confirms, in the code itself, the limitation the review asked
to have declared: the claim "the gateway only accepts dual
certificate pairs" (the AND mechanism, Decision 6/19) HOLDS ONLY FOR
THE MAIN SNI
(`mtls`) -- NEVER for the internal SNI `matls-api.local`, which uses
a config WITHOUT Dual, accepting a single classical certificate (the
real production `op.crt`/`op_hybrid.crt`), under ANY profile,
including under Hybrid-AND.** This is a deliberate and
JUSTIFIED design decision (the internal caller was never part of v9's
specific AND mechanism -- Decision 17 already documented this in the
context of the "ML-DSA-65 alt signature verification failed" error),
not a bug --
but it is a condition that needs to be EXPLICIT anywhere that
describes the AND mechanism as universal, so as not to suggest a
broader security guarantee than what the code actually provides.
**Recorded here as the explicit declaration requested; no earlier
place in this `DECISIONS.md` was found stating the unqualified
version** (searched for "only accepts"/"dual pairs"/
"gateway.*AND" -- the 7 internal connections per run have always been
treated, in Decision 19, as their OWN category, separate from the
client-facing ones, never described as covered by the AND mechanism)
-- but the declaration is recorded here, explicitly and on its own,
so that any future reading (including the thesis itself) does not
need to infer this just by reading the code.

**2. IAM USERNAME -- removed from v9's `DECISIONS.md`, dated
note, without rewriting the rest of the text.**

`DECISIONS.md`, Decision 27's pre-flight command block (line
~3882): the call `aws iam list-attached-user-policies --user-name
<literal value>` had this project's IAM username written out in
full. **Edited now** to `<IAM username, redacted in a dated
note -- see Decision 44, item F.15>` -- the COMMAND itself (which
call to run, and why) remains documented identically, only the
literal name was replaced. This is a targeted edit of a single
value, not a rewrite of that decision's reasoning or conclusion.

**Sweep confirming the scope -- only this one occurrence across all
of `thesis/results/v9/`, before the edit above:**
```
git grep -n "<IAM username>" -- thesis/results/v9
  -> 1 occurrence (the line edited above)
git grep -niE "arn:aws|AKIA[0-9A-Z]{16}|[0-9]{12}" -- thesis/results/v9
  -> 0 occurrences of a real ARN/access key/account ID (the only
     matching line is prose describing the "arn:aws" PATTERN
     searched for by an earlier sweep, Decision 27 -- not a real
     value)
```
**Honest scope note, not hidden, without repeating the value
here:** the same IAM username appears, extensively, across three
v8 files (`DECISIONS.md`, `README.md`, two `variables.tf`) --
**this independent review was scoped to HEAD `23ee2ceb` and to
v9's commits** (explicit request: "independent review of HEAD
23ee2ceb"), so these v8 files (closed, from a previous, already
concluded session) **were not touched** -- scrubbing that name there
too would mean rewriting the history of an
already-closed deliverable, a much larger scope than what was asked
here, and it remains a separate decision for Luciano, not assumed on
my own.

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 45. Two points requested after the independent review's push -- (1) confirmed, directly in v8's real module, that NO auto-shutdown path releases the EIP (neither `stop` nor `terminate`), and fixed in the procedure: auto-shutdown now always requires a full teardown afterward; (2) confirmed that the CommonName fallback only fires when BOTH leaves are SAN-less, with a direct test (`TestSameDualIdentitySANFallback`) proving this even in the asymmetric case, plus a new guard in the certificate generator that fails loudly if any SAN comes out empty -- binaries and toolchain rebuilt, full suite green

**1. EIP and auto-shutdown -- CONFIRMED: neither path releases the
Elastic IP, neither before nor after the `stop`/
`terminate` divergence between v8 and v9. Fixed in the procedure,
not in the mechanism.**

Read directly in the real module
(`v8/campaign/terraform/modules/campaign_instance/main.tf`, lines
92-99, and `templates/safety_timer.sh.tftpl`) -- v8 itself already
documents this in its code, in its own words:
```
# Renewable safety timer -- Decision 49. [...] This is a safety net,
# not a teardown substitute: it does not release the Elastic IP and
# does not replace campaign_down.sh's own verified teardown
```
and the script itself, when it fires, logs: `"...shutting down (Decision
49 -- this does not release the Elastic IP, does not substitute for
campaign_down.sh)"`. **Confirms in writing, at the source, exactly
what Decision 43 (item E.12) had already concluded by inference:
releasing the EIP ALWAYS depends on destroying the
`aws_eip` resource itself (`terraform destroy`, or a manual
`release-address`) --
never on any side effect of stopping or terminating the
instance.** This holds BOTH for v8's real `shutdown -h now` (which
results in `stop`, since it does not set `instance_initiated_shutdown_behavior`)
AND for the `terminate` v9 decided to use (Decision 23 item 5,
Decision 24 item 4) -- the difference between the two only changes
the instance's fate (stopped vs. destroyed), never the EIP's fate,
which is a SEPARATE Terraform resource (`aws_eip`) in both cases.

**Fix adopted, procedural (not new automation -- the same
least-privilege choice as Decision 43):** the procedure now treats
"auto-shutdown fired" as a mandatory teardown TRIGGER,
never as a teardown in itself. Explicit rule added: **whenever the
routine check finds an instance that should be running but is no
longer (`describe-instances` without it, or an unexpected state), the
MANDATORY next action before considering the session closed is a
full `terraform destroy` of that deployment** --
even if the instance has already disappeared on its own, `terraform
destroy` of an `aws_eip` does not depend on the associated instance
still existing (the real call is `ec2:ReleaseAddress` by the
allocation ID, stored in the state, not by the instance). The 5-call
check (Decision 43, item 2) is what detects this, across the 3
regions, after ANY session -- success, abort, or auto-shutdown
fired, with no distinction.

**2. CommonName fallback -- CONFIRMED in the code, PROVEN with a
direct test and a mutant, and reinforced with a new guard in the
certificate generator.**

**(a) Confirmed in the code:** `sameDualIdentity`
(`toolchain/dual.go`) only falls back to CommonName when
`!leafHasAnySAN(classicalLeaf) && !leafHasAnySAN(pqLeaf)` -- BOTH
need to be SAN-less. If either has a SAN, it falls into the
normal SAN-set comparison (DNS/email/IP), which correctly never
matches an empty set against a non-empty one.

**(b) Proven with a direct test, not just by reading the code:**
`TestSameDualIdentitySANFallback`, new, in `dual_test.go`, calls
`sameDualIdentity` directly (no handshake) with 4 pairs: both
SAN-less + same CommonName (should match), both SAN-less + different
CommonName (should not match), **the asymmetric case -- one leaf
with a real SAN, the other without, the SAME CommonName on both
(should not match, in either argument order)**, and both with the
SAME real SAN (should
match, the real format of the 4 profiles). **Mutant tested to prove
the test actually catches the bug:** I swapped `&&` for `||` in the
guard
(`dual.go`, line 319) in an isolated copy, run against the real,
rebuilt BINARY (not a mock) -- the test **FAILED exactly on the two
asymmetric-case assertions** (`got a match` where it should be
`no match`), confirming the test actually depends on the `&&` being
correct. With the original `&&`: **PASS**, full suite re-run:
**`ok crypto/tls 87.619s`, 0 FAIL** (the 23 earlier AND tests + the 4
from
Decision 39 + this new one + the entire Go upstream suite).

**(c) Confirmed that v9's 4 profiles ALWAYS generate leaves with a
SAN -- not by assumption, by real inspection of the generated
certificate.**
`certs/main.go`: all 12 leaf-generation calls (4 profiles x
server/client, with Hybrid-AND counting its 2 leaves per role)
pass `serverSANs`/`clientSANs`, never `nil` nor a literal empty
list. I ran the real generator (`go run .`, rebuilt toolchain) and
inspected the SAN of each of the 10 resulting real leaf
certificates (via a minimal Go inspector, `x509.ParseCertificate` +
reading `DNSNames`/`IPAddresses`):
```
classico_server:        DNSNames=[mtls auth.local ... keystore] IPAddresses=[127.0.0.1 ::1]   totalSAN=10
classico_client:        DNSNames=[opin-client-one]                                             totalSAN=1
hibrido_v8_server:      (identico ao classico_server)                                          totalSAN=10
hibrido_v8_client:      (identico ao classico_client)                                          totalSAN=1
hibrido_and_rsa_server: (identico ao classico_server)                                          totalSAN=10
hibrido_and_rsa_client: (identico ao classico_client)                                          totalSAN=1
hibrido_and_mldsa_server: (identico ao classico_server)                                        totalSAN=10
hibrido_and_mldsa_client: (identico ao classico_client)                                        totalSAN=1
pqc_server:             (identico ao classico_server)                                          totalSAN=10
pqc_client:             (identico ao classico_client)                                          totalSAN=1
```
**The 10 real leaf certificates (the 4 profiles, server and client)
have a SAN -- none empty.** This confirms that, in this project's
real practice, the CommonName fallback is NEVER exercised by the 4
profiles -- it exists only to cover the legitimate but different case
of the pure AND MECHANISM's CLIENT certificates used in Go's own
tests (`dual_test.go`, which deliberately uses SAN-less certificates
to exercise this path), not for the real certificates this project
generates.

**(d) Reinforced with a new guard, so this guarantee never depends
only on "nobody passing an empty flag by mistake":** `certs/main.go`
now fails loudly (`fatalf`) if `-server-dns` or `-client-dns`
results in zero names after parsing -- tested (`-client-dns=`
empty -> `fatalf` with an explicit message, `exit status 1`, no
SAN-less certificate generated silently) and confirmed that normal
generation keeps working identically (the 10 certificates
above, generated AFTER the guard was in place).

**Binaries and toolchain:** `and.patch` regenerated (rebuilt
pristine/fixed from scratch, the same method as Decision 39 --
reverse-apply, edit, new diff, applies clean onto a fresh pristine
copy, the resulting tree byte-for-byte identical to the intent, 9
files, confirmed),
new SHA-256 `1865eb2a99f0cc6029495a77f0d1a73b9da705a405b46fc051743fae25b4eb4b`,
`build_metadata.json` updated. `gateway`/`proxy` rebuilt for
`amd64`+`arm64` with the updated toolchain, reproducibility
reconfirmed (rebuild from scratch, identical hash across both
rounds, each architecture):
```
gateway amd64: cefddbeef31efacdc9dcb20dcb72b970938c3ab07d3a18b6e6ed40ac89b895c3
gateway arm64: c6a5f880b628aa87857e9e233d3efd18e439641902b68b02f480bbbe4de20d08
proxy   amd64: 273169d27148bc1c2b9cdf9d0f3bf259f8e9b9d8935e202feada06b257fc3c08
proxy   arm64: 455e4a9178fda970c5a3f4d6eedb5ee398e6db52b1c2659c87878da8fc7f8bc5
```
**Supersede the hashes from Decision 39** (which in turn superseded
Decision 22's) -- the old binaries never had `TestSameDualIdentitySANFallback`
nor the generator guard; they must not be used in the pilot.

Same rules: no action on AWS, no commit before the scanner,
report in chat.

## 46/47. Pilot infrastructure written and tested locally -- multi-region Terraform (a copy of v8's real module, 1 new additive variable), the orchestrator for the 60 runs with a simulation mode, PKI relay, per-block collection with SHA-256, cleanup+EIP+drift detection, go/no-go pre-flight -- 38 automated tests (aws/ssh/terraform stubbed, no real call), at least one mutation per script; no deviation from the v9-prereg pre-registration

**Decision 46 (Terraform, `thesis/results/v9/terraform/`).** A
VERBATIM copy of the real `v8/campaign/terraform/modules/
campaign_instance` module (not referenced by a relative path on
purpose -- v8 is an already-closed session, never edited by this
session; copying avoids any change, even an additive one, to its
already-closed files). **THE ONLY code difference across the whole
module:** the new `instance_initiated_shutdown_behavior` variable
(default `null`
= the same implicit behavior real v8 always had, never set there) +
the line connecting it to `aws_instance` -- necessary because
Decision 23 item 5 decided v9's pilot uses `terminate`
(real v8 never sets this attribute, staying at AWS's default
"stop"). The `Project` tag changed from `mockopin-pqc-aws` (v8) to
`mockopin-pqc-v9-piloto` -- the pilot's OWN identifier, so
`cleanup.py` can never confuse (or, worse, affect) v8's real
resources if they ever coexist in the same account.

**Exact topology from Decisions 26/27/43/45:** server+L0+control in
`sa-east-1` (L0 in the SAME AZ ID as the server), L219 in `eu-north-1`,
L325 in `ap-southeast-1`; `m7i-flex.large` server/clients,
`t4g.micro` control; `terminate` auto-shutdown with N=4h
(server/clients, never the control); the gateway (443) only for the
3
clients (L0 via PRIVATE IP, L219/L325 via PUBLIC IP); SSH only from
the control's EIP (server/clients) or the operator's (control). AMIs
PINNED, reusing the SAME real IDs already used and version-controlled
by v8 (public, non-sensitive -- any account in the same region sees
the same ID).

**Validated, with no AWS:** `terraform fmt -recursive` (clean) and
`terraform validate` (`Success!`) -- `terraform init -backend=false`
only downloads the PROVIDERS from the public registry, no AWS call,
no credential. No `plan`/`apply` attempted.

**Decision 47 (orchestrator + 4 scripts + tests, `thesis/results/
v9/campaign/`).** A single CLI boundary (`scripts/cli.py`) through
which EVERY script talks to `aws`/`ssh`/`scp`/`terraform` -- the
tests replace exactly this boundary (`cli._run`, or the
`run_aws`/`run_aws_json`/`run_ssh`/`run_scp`/`run_terraform`
functions
individually), never a real call. `redact()` is imported
directly from v8's real file (`redact_aws_errors.py`), never
duplicated.

**1. Orchestrator (`orchestrator.py`), a REDUCED equivalent of the
real `campaign_run.py`** (without the multi-day campaign machinery --
windows, Latin square, cost/time budget, chronyc -- that a 1-block/2h
pilot never needs). Two Executors, the same SSHExecutor/LocalExecutor
pattern as real v8:
- `SSHExecutor`: dials every target via its PUBLIC IP (Decision
  43/45),
  never tested against real AWS.
- `LocalExecutor`: **SYNTHETIC simulation, does not bring up the real
  Docker stack** -- generates HTTP counts (44/28/4/4), per-profile
  CurveID/
  DualAuthenticated, and message sizes using the MEASURED
  BASELINES `evaluate_criteria.py` already uses (imported,
  never reinvented). **Honest limitation, explicitly recorded
  here:** proves the ORCHESTRATION logic (cardinality, order,
  markers, the format the evaluator accepts) -- it does NOT exercise
  any real network/cryptography, only AWS can confirm that (see the
  readiness table in chat).

Run order (Decision 23 item 2, profile blocks replicating real
v8): for EACH route, ONE `random.Random(seed)` draws the order of
the 4 profile blocks (seed always recorded in the manifest,
reproducible).
`== EXECUCAO INICIO/FIM ==` markers exactly in the format the
REAL `evaluate_criteria.py` regex expects (tested against it, not
assumed). The readiness probe is emitted OUTSIDE any window,
by construction.

**Tested end to end against the REAL evaluator** (`--mode simulate`,
fixed seed): 60 runs, 12 captures, criteria 1/4/5/6 (the ones the
orchestrator actually produces) **genuine PASS** -- not just "did
not
break"; criteria 2/3/7 (produced by the OTHER dedicated
producers, Decision 41, outside the orchestrator's scope) **FAIL
fail-closed**, as expected, no exception.

**2. PKI relay (`pki_relay.py`)** -- 2 hops exactly as
Decision 26 item 3 describes: operator `scp`s to the control
(operator's key) -> control `scp`s to the final destination
(campaign's EXCLUSIVE key) -> `shred -u` on the control, ONLY after
the final `scp` succeeds (order guaranteed by `&&`, tested with a
mutant). No key content appears in any argv (tested).

**3. Per-block collection with SHA-256 (`collect_artifacts.py`)**,
the equivalent of the real `campaign_pull.sh`, but PER PROFILE (4
blocks, not
a single pull at the end) -- a manifest regenerated on the control,
pulled, checked again locally with native Python (`hashlib`, does not
depend on the `sha256sum` binary existing on the operator's machine).
`.pull-verified` only written after the check passes -- never
before (tested with corruption and with a missing file, both
detected).

**4. Cleanup + EIP + drift (`cleanup.py`)**, the equivalent of the
real `campaign_down.sh` (the SAME 5 calls -- instances/addresses/
security-groups/key-pairs/volumes, 3 regions) with two additions
real v8 did not have, explicitly requested (Decision 43/45):
- **Auto-shutdown drift detection:** counts instances
  running BEFORE the destroy: fewer than the expected 5 (control+
  server+3 clients) becomes an explicit warning that auto-shutdown
  has already fired on one of them -- it never blocks the destroy
  (which remains mandatory: only it releases the `aws_eip`, Decision
  45).
- **Orphaned-EIP release:** the final check identifies any
  Elastic IP with no associated instance; with `--release-eips`, it
  really
  releases it (`ec2:ReleaseAddress`); without the flag, it only
  reports (the same
  "detection before new automation" policy as Decision 43).
`.pull-verified` required before destroying (the same safety latch
as the real `campaign_down.sh`), with `--force` to explicitly
override it.

**5. Go/no-go pre-flight (`preflight.py`)**, the SAME exact commands
already described in prose in Decision 27 item 2, now executable:
credential identity, vCPU quota (3 regions), instance-type
availability (3 regions), AMI resolution (3 regions),
budget alert. **Account ID: used internally ONLY to build
`--account-id` for the budgets call (the API's own requirement) --
NEVER returned nor logged**, with a redundant safety net
(`assert` inside `run_preflight` that fails loudly if any real ARN
ever escaped) -- tested with a mutant that simulates exactly this
leak.

**Real finding along the way, fixed:** `cli.run_aws()` was adding
`--output json` even when the caller had already requested `--output text`
(the Account ID case via `--query Account --output text`) -- two
`--output` flags in the same call would make the real CLI obey only
the last one, silently ignoring the caller's. Fixed: it only adds
`--output json` if the caller requested NONE.

**Tests, all without a real network/credential:** 38 automated tests
(`pytest`), covering the 5 scripts + the CLI boundary, ALL with
`aws`/`ssh`/`scp`/`terraform` stubbed (never a real call) --
**at least one mutation per script**, each confirmed to
fail the corresponding real test (not just existing): order
with no shuffle (orchestrator), shred before the scp (relay), hash
check turned off (collection), `clean=True` ignoring a running
instance (cleanup), `go` aggregated via `any()` instead of `all()`
(pre-flight).

**No deviation from the `v9-prereg` pre-registration this round** --
no threshold, baseline, or go/no-go criterion was touched; all this
decision's work is pilot EXECUTION infrastructure (Terraform,
orchestration, data logistics), never the already-frozen measurement
METHOD. If this ever changes in a future round, the corresponding
formal amendment will be recorded separately, as always.

Same rules: no action on AWS, no commit before the scanner,
report in chat. No push without explicit authorization.

## 48. AMENDMENT 12 TO THE v9-prereg PRE-REGISTRATION -- a smoke gate (12 runs, 1 per profile x route, never counted in the 60) added to the pilot's procedure, running only in real SSH mode, right after the apply/PKI relay and before the timed block; two real findings that make the earlier readiness table optimistic, recorded with evidence

**Reason for the amendment:** the `v9-prereg` pre-registration fixed
the 7 criteria and their thresholds, but never provided for a quick
validation gate against the REAL infrastructure before committing the
60 official runs to it. Without this, an infrastructure problem
(wrong SG, stale binary, badly relayed PKI) would only show up AFTER
all 60
runs, wasting the time/cost of an entire route. Decision 23
already established the precedent of "capture kept separate from the
timed measurement" (the 12 dedicated captures for criterion 1, which
also never count in the 60) -- this amendment extends the SAME
principle to a new smoke check, before any real run
starts.

**What formally changes:** `orchestrator.py` gains
`run_smoke_gate()` -- runs `N=1` run per (profile, route), 12 in
total, ALWAYS in its OWN output directory (never reused
by the real 60), with an explicit `manifest["smoke"] = true`.
Abort criterion: **any of the 12 failing (exception, HTTP count
outside 44/28/4/4, or any other single-run check) is
reason to abort the entire pilot and run `cleanup.py` (destroy +
the 5-call check), never proceed to the 60.** Nothing in the
pre-registration of the 60 runs/7 criteria changes -- the smoke gate
is NOT an eighth criterion, it is an operational gate BEFORE them.
Tested: `test_porta_de_fumaca_tem_cardinalidade_12_nunca_60`,
`test_porta_de_fumaca_passa_com_dados_bons`,
`test_porta_de_fumaca_aborta_se_qualquer_execucao_falhar` (mutant:
one of the 12 with a wrong HTTP count, `smoke_ok` turns False and
identifies exactly which profile/route) and its own inverse mutant
(`smoke_ok` computed only from cardinality, ignoring failures --
correctly failed by the earlier test).

**Two real findings that make the previous round's readiness table
OPTIMISTIC for Terraform and for the orchestrator -- recorded
here with evidence, not by argument:**

**(a) `aws_eip.this` (Terraform module, `main.tf` line 192) fixes
`instance = aws_instance.this.id`** -- this forces Terraform to
create
the instance BEFORE (or in the same apply as) the EIP, never allowing
an isolated `terraform apply -target=aws_eip.server` to discover the
address BEFORE the instance comes up. **This contradicts, to the
letter,
the 4-step sequence Decision 27 item 1 requires** ("1) Terraform
allocates the server's EIP (not yet associated) -- the resulting
address
is an output; 2) this output feeds the PKI generator's SINGLE call
...; 3) the server instance comes up; 4) the EIP is associated to
it").
The module copied from v8 never needed this sequence (real v8 does
not
use an IP in the certificate's SAN) -- copying it verbatim brought
this gap
along. **NOT FIXED this round** (the request was for evidence, not
more code) -- it needs an `aws_eip` without the `instance` attribute
+
a separate `aws_eip_association` before any real apply.

**(b) `SSHExecutor.run_execution`/`dedicated_capture`/
`readiness_probe` (`orchestrator.py`) has the remote command as a
SKETCH, never confirmed against the real `opin_flow.py`.** Reading
the
real file now: `opin_flow.py main()` (line 2433+) REQUIRES a
PRE-EXISTING `experimentN*` directory (raises `SystemExit` if it
cannot
find one, line 2493-2497), expects flags like `--latency-ms`, and
writes
the result (`baseline_metrics.json`, schema `plan_alias`/`module`/
`status`, NOT `{"insurance":[...], "person":[...]}`) **to a FILE,
never to stdout** -- the current command (`CRYPTO_PROFILE=...
REMOTE_GATEWAY_HOST=... V9_HARNESS=1 python3 opin_flow.py`, expecting
`json.loads(proc.stdout)`) **would really fail against a real
instance**, both for lacking the experiment directory and for the
wrong channel (empty stdout, real data in the file). **The only path
already proven and trustworthy is `--mode simulate`** (LocalExecutor,
tested end to end against the real evaluator, Decision 47) -- the
`--mode ssh` mode needs to be rewritten (the real remote command:
run
`opin_flow.py` with the right arguments inside an already-prepared
`experimentN*`, then `cat` the resulting `baseline_metrics.json` and
adapt the parsing) before any real run, including before the
smoke gate itself.

**Practical consequence:** this amendment's smoke gate, as
written, is only actually executable AFTER finding (b) above is
fixed -- documented here exactly so this dependency does not
stay implicit.

Same rules: no action on AWS, no commit before the scanner,
report in chat. No push without explicit authorization.

## 49. Four points requested after Decision 48's finding (b) -- `--mode ssh` fixed and genuinely proven (local shim, real stack, 5 classico + hibrido-v8 runs passing the probe, a NEW, real finding along the way: pqc/hibrido-and get stuck on a library gap, not an orchestrator one); EIP recorded as a non-problem (decorative SAN, DNS-based verification); the smoke gate fixed to pause, never to destroy on its own; cleanup confirmed to cover the control, residual risk listed

**1. `--mode ssh` fixed -- reusing v8's REAL invocation,
genuinely proven against the local stack (shim), not assumed.**

Read directly in the real `campaign_run.py` (`SSHExecutor.run_one_execution`/
`start_block_proxies`/`stop_block_proxies`, v8's 720 real runs,
zero errors) and in the real `campaign_client_runner.py` (`thesis/scripts/`,
generic, never v8-specific -- it only calls
`latency_automation.run_once_timed_with_retry()`): the correct remote
command is `campaign_client_runner.py --label <X>`, never `opin_flow.py`
directly (which requires a pre-existing `experimentN*` directory and
writes
the result to a FILE -- Decision 48's finding, now fixed).
`SSHExecutor` (`orchestrator.py`) rewritten:
- **Profile name translation -- real finding, confirmed by reading
  `opin_flow.py` (`V9_PROFILE_NAME`, line ~263):** the GATEWAY and the
  evaluator use v9's display names ("classico"/"hibrido-v8");
  the CLIENT (`CRYPTO_PROFILE`, which `_CRYPTO_PROFILE_FOR_ROUTING`
  reads)
  only recognizes v8's old names ("classic"/"hybrid") -- "pqc"
  and "hibrido-and" are the same on both sides. Using the wrong name
  on the
  client side would make `_USE_TLS_KEM_PROXY` come out false and the
  flow
  run without the proxy, against the wrong target -- never exercised
  before
  this round, found LIVE, not assumed.
- **Per-block lifecycle** (`start_block`/`stop_block`, new):
  literally reuses v8's real command to bring up/tear down
  `tls_kem_proxy_run`/`pqc_signer_service_run` (`of.start_tls_kem_proxy(
  ..., detached=True)`/`of.start_pqc_signer_service(...)`, then
  `docker stop`+`docker rm -f` for both fixed names.
- **Real readiness probe** (`readiness_probe`): 1 real settling
  run (same `SETTLING_RUNS` pattern as v8), never
  counted, with the "connection OK" line extracted from the gateway's
  REAL log (not invented).
- **Real mTLS/CurveID/DualAuthenticated count**: regex over the
  gateway's real log (`gateway: PROFILE connection OK
  remoteAddr=... sni="..." curve=... dualAuthenticated=...`), excluding
  the internal carve-out (`matls-api.local`) -- no longer a fixed
  number
  per profile.

**Proven with a real SHIM, not a stub -- `cli.enable_local_
shell_shim()` (new, `cli.py`): the SAME `remote_cmd` that would go
over SSH
runs in a LOCAL shell, against v9's real local Docker stack (the real
`insurance-server-lambdas` backend + v9's real gateway/proxy/signer,
never mocked).**

**Result 1 -- a block of 5 runs (classico/L0), 100% real:**
```
criterio4: as 5 execucoes, cada uma {"http":44,"jwts":28,"jwks":4,"ca":4,"mtls":6}, "ok":true
criterio5 (zero erros): pass=true, errors_found=[]
```
**The 5 numbers match EXACTLY the already-measured real numbers
(Decision
17/18), across all 5 runs, individually** -- this proves that the
fixed invocation produces data identical to what a real campaign
would produce, not just "doesn't break."

**Result 2 -- smoke gate (12 runs, 4 profiles x 3 routes):
PARTIAL, and it found a real problem -- exactly what it exists
for.** `classico` and `hibrido-v8` passed the readiness probe
for real (a real mTLS handshake, the AND gate confirmed for
hibrido-v8, real
JWKS/CA/token). **`pqc` (and, for the same reason, `hibrido-and`,
which also uses an ML-DSA-65 CA) got stuck on a NEW error, never seen
before
this round:**
```
ValueError: Unknown key type: 2.16.840.1.101.3.4.3.18
  opin_flow.py:917, _verify_cert_signed_by_mldsa65():
    pqc_jwk = {... "pub": _b64url_encode(issuer_cert.public_key().public_bytes_raw())}
```
OID `2.16.840.1.101.3.4.3.18` is ML-DSA-65 (FIPS 204) -- the
`cryptography` Python library installed on this machine (confirmed:
version
46.0.3, recent) does not recognize this key type when calling
`.public_key()` on a real ML-DSA-65 certificate (v9's PQC/
Hybrid-AND CAs, Decision 9/10). **This is NOT a bug in the
orchestrator
nor in v9's gateway/proxy** -- it is a limitation of the CLIENT's
Python library on this specific development machine, found only
because the smoke gate actually tested against real cryptographic
material instead of synthetic. **Honestly recorded, not hidden nor
worked around:** the pilot's real instance (Amazon Linux 2023, fresh
pip) might have a different version -- this can only be confirmed by
running it there, which is exactly why the smoke gate exists before
the 60 official runs.

**Two extra operational findings, found live while assembling this
shim (documented, not hidden):** (a) switching ONLY the GATEWAY's
profile was never enough -- `auth` runs with its OWN `CRYPTO_PROFILE`
(real log: "Crypto profile: classic (signingAlgs: PS256)"), which
needs to be switched TOO (`docker compose up -d --force-recreate
auth mongo_seed mockapi`, the same real command as
`switch_crypto_profile.py`, except for excluding "mtls") -- without
this,
`/token` fails with 401 for any profile different from what `auth`
was already running. (b) `mockapi` (Java/Micronaut, Hibernate) really
takes ~30s to come up after a `--force-recreate` -- without
waiting for it specifically, the first real call hangs with a 502
Bad Gateway. Both ONLY apply to this validation's LOCAL backend
profile-switching mechanism (`local_shim_bridge_join=True`) -- for a
real remote pilot, the server runs a fixed profile for the entire
block, decided BEFORE the block starts (Decision 23), it does not
switch on every call.

**New tests (`test_orchestrator.py`), all stubbed, no real
call:** profile-name translation (+mutant), `start_block`
switching the gateway and bringing up proxy/signer (+mutant via
`stop_block`), extracting curve/dualAuthenticated from the real log
(+mutant that does not filter the internal carve-out) -- 48 tests in
total now, all green.

**2. EIP -- recorded as a NON-PROBLEM, Terraform untouched.**

Decision 48 (finding a) pointed out that `aws_eip.this` (module,
line
192) fixes `instance = aws_instance.this.id`, preventing the isolated
`apply
-target` that Decision 27 item 1's literal sequence describes.
**Re-examined: this is not a real problem, for three facts already
confirmed in the code itself, never assumed:**

- **The IP in the SAN is decorative.** Decision 30 (already
  recorded):
  `proxy/main.go`/`proxy/relay.go` fix `ServerName: "mtls"` --
  `cert.VerifyHostname("mtls")` compares against `DNSNames`, NEVER
  against `IPAddresses` (`crypto/x509`, Go std -- "mtls" is not a
  valid IP, so the verifier never looks at the IP list). **The exact
  value of the IP in the SAN is never checked by anyone, anywhere in
  this
  architecture** -- it only contributes to the certificate's SIZE
  (Decision
  28/29), never to the decision to accept/reject the connection.
- **The inventory and the clients ALWAYS dial the EIP.** Confirmed in
  the code (`SSHExecutor._client_ip`, `orchestrator.py`): it returns
  `self.inventory["clients"][route]["public_ip"]` with no exception,
  for
  EVERY route -- never the private one, not even for the co-located
  L0 (Decision
  43/45). The only place that uses the PRIVATE IP is
  `_server_gateway_ip`,
  and only for the data traffic (443) of the proxy INSIDE the
  co-located L0 client -- never for SSH, never for the inventory
  itself.
- **The gateway waits for the relay's certificates before accepting
  traffic.** Confirmed in the code (`gateway/main.go`, lines ~259-266):
  each profile `case` calls `singleChainServerConfig`/builds the dual
  config by reading the certificate files from disk AT THAT MOMENT --
  if
  missing, `log.Fatalf` ends the process, it never comes up
  partially.
  **This closes the real sequence:** `terraform apply` creates the
  instance+EIP
  TOGETHER (a single apply, confirmed -- `aws_eip.this` depends on
  `aws_instance.this.id`); `terraform output` reads the EIP, already
  stable;
  the certificate is generated with this EIP in the SAN (decorative,
  but generated
  the right way regardless); the PKI RELAY
  (Decision 26 item 3) delivers certificate+binary to the ALREADY
  EXISTING instance;
  ONLY THEN does the operator start the gateway, which only comes up
  if
  the certificates are already in place. **There is never a window
  where the
  gateway accepts traffic with a wrong or missing certificate** -- the
  startup `log.Fatalf` prevents this by construction.

**Conclusion: the Terraform stays as it is.** The 4-step sequence
from Decision 27 item 1 (isolated EIP, then instance) described a
precaution that the real architecture (DNS-based verification, a
gateway that never comes up without a certificate) already makes
unnecessary -- kept here as a dated note, NOT rewriting Decision 27's
original text.

**3. Smoke gate -- fixed to PAUSE, never to destroy on its own
(Amendment 12 revised).**

Decision 48 recorded "any of the 12 failing... is reason
to abort the entire pilot and destroy" -- **ambiguous text, fixed
here via a dated note (not rewritten): the ORCHESTRATOR NEVER
destroys anything on its own, on NO code path** (confirmed:
neither `orchestrator.py` nor `run_smoke_gate` call `cleanup.py` or
`terraform destroy` anywhere -- Decision 48's phrasing described
the operational procedure's INTENT, never a real automatic action).
`orchestrator.py --smoke`, on a failure, now explicitly prints:
```
*** PORTA DE FUMACA REPROVADA -- PAUSADO. ***
Nao executado: nenhum destroy automatico. Decisao do Luciano:
  (a) corrigir e repetir --smoke dentro da janela de 4h, ou
  (b) mandar destruir (cleanup.py).
```
and exits with code 1 -- never more than that. **The destroy at the
END of the pilot (after the 60 official runs) remains mandatory, with
no
exception** (Decision 43/45/48); **the time-based auto-shutdown (4h)
remains a trigger for a full teardown** (Decision 45/49 item 4
below) -- neither changes here, only the behavior IN THE MIDDLE of
the smoke gate.

**4. Cleanup covers the control instance -- confirmed; residual
risk listed.**

Confirmed in the code (`cleanup.py`, `verify_region`): filtering is
by `tag:Project={PROJECT_TAG}` in EACH region, with no `Role`
exception
-- the control (Role=campaign-control, sa-east-1) is counted together
with the server/clients in the 5 calls, and `terraform destroy`
destroys ALL
resources in the state, control included, regardless of any
auto-shutdown (the control never has one, Decision 26 item 3 -- it
needs to stay alive to orchestrate the entire pilot).

**Residual risk, explicitly recorded (not mitigated this
round -- the request was only to list it, not to fix it):** since the
control
is DELIBERATELY exempt from auto-shutdown, it is the ONLY pilot
resource with no automatic safety net at all. If the session is
abandoned with no one running `cleanup.py` (the operator's machine
freezes,
the network drops, the session is forgotten), the control (and its
EIP) keep running
INDEFINITELY, billing, with no mechanism stopping them on their
own -- unlike the server/clients, which the 4h auto-shutdown always
reaches even in this scenario. **Not fixed on purpose**
(the request was to list, not mitigate) -- if Luciano wants, the
simplest mitigation would be a MUCH longer auto-shutdown just for the
control (e.g., 24h, well above any real pilot), as a last-resort
safety net, never as a substitute for `cleanup.py`.

**Items still optimistic, explicitly reported:**
- The `--mode ssh` mode is now real and tested for `classico`/
  `hibrido-v8` -- but `pqc`/`hibrido-and` NEVER completed a real
  run on this machine (library gap, item 1
  above). Only the pilot's real instance confirms whether this
  repeats
  there.
- The *remote* GATEWAY's profile-switching mechanism (not this
  validation's local shortcut) still does not exist -- Decision 48
  already
  recorded this, it still holds.
- `dedicated_capture` (criterion 1's 12 captures) remains outside the
  `SSHExecutor`'s scope -- never tested this round nor in the
  previous one.

Same rules: no action on AWS, no commit before the scanner,
report in chat. No push without explicit authorization.

## 50. Full diagnosis of the "Unknown key type" (not a code bug -- it was the wrong Python interpreter); 3 of the 4 profiles (classico/pqc/hibrido-v8) proven end to end via the ssh shim, with the exact real numbers; hibrido-and found a NEW, distinct gap (alg mismatch at /token), honestly recorded, unresolved; Python package versions aligned with the pinned requirements.txt; the control gains a 5h safety auto-shutdown with terminate

**1. Diagnosis of "Unknown key type: 2.16.840.1.101.3.4.3.18" --
NOT a bug, neither v8's nor v9's. It was the wrong Python
interpreter.**

**Exact point of the call:** `thesis/scripts/opin_flow.py:917`, inside
`_verify_cert_signed_by_mldsa65`:
```python
pqc_jwk = {"kty": "AKP", "alg": "ML-DSA-65", "pub": _b64url_encode(issuer_cert.public_key().public_bytes_raw())}
```
`issuer_cert.public_key()` is what actually triggers the `cryptography`
library's OID->key-type dispatch -- and what raised the
`ValueError` when the real CA certificate (ML-DSA-65, OID
2.16.840.1.101.3.4.3.18/FIPS 204) was not recognized.

**Did it exist in v8 or was it introduced in v9?** Pre-existing, from
v8 ITSELF: `git log -S "_verify_cert_signed_by_mldsa65"` points to commit
`a9924fab9` (2026-10-25, "feat(v8): opin_flow.py now verifies every
signed artifact it receives..."). **It never changed in v9.** Real v8
ran this 720 times with no error because the PYTHON ENVIRONMENT was
the right one --
never because the code was different.

**Real root cause, confirmed: I was calling the client with the WRONG
Python.** `thesis/scripts/requirements.txt` pins
`cryptography==50.0.2` (hash-pinned, with its own justification in
the header: **"Pinned to the exact versions validated for the pqc
CRYPTO_PROFILE... presenting an ML-DSA-65 client certificate requires
routing TLS through cryptography's bundled OpenSSL"**) -- and there
is a dedicated venv at `thesis/scripts/.venv/` exactly for this
(`README.md`, "Virtual environment" section). **I had run against
`/c/Python313/python` (this machine's system Python, never
managed by this project), which had `cryptography==46.0.3`** --
a version with no X.509 support for ML-DSA. Confirmed directly:
```
.venv\Scripts\python.exe -c "from cryptography import x509; ...
  cert.public_key()"
-> <class '...MLDSA65PublicKey'>, 1952 bytes -- EXACTLY what the
   real function's own docstring already said ("confirmed live,
   returns exactly the 1952 raw bytes").
```
**No code fix needed -- no rerouting to Go/gateway/proxy.** The
already-existing design (the function's own docstring, never read
carefully before this round) ALREADY delegates signature
VERIFICATION to `pqc-signer` (Go) -- `cryptography` is
used only to EXTRACT the certificate's raw public-key bytes,
which the correct version does with no problem. The fix was to use
the correct
interpreter (`thesis/scripts/.venv/Scripts/python.exe`), never
the system Python -- `cli.py`/the validation script updated
for this.

**2. Smoke gate + blocks of 5, via the real shim -- 3 of the 4
profiles with TOTAL and IDENTICAL success; the 4th found a NEW,
distinct, unresolved problem.**

**classico, pqc, and hibrido-v8 -- a block of 5 runs each, 100%
real, THE SAME EXACT 3 numbers across the 3 profiles, across all 15
runs (5x3) individually:**
```
criterio4: {"http":44,"jwts":28,"jwks":4,"ca":4,"mtls":6} -- "ok":true, em TODAS as 15
criterio5 (zero erros): pass=true, errors_found=[] -- nos 3 perfis
```
Proves that item 1's fix, plus the profile-name translation and
the block lifecycle already fixed in Decision 49, produce data
IDENTICAL to what was historically measured (Decision 17/18), across
the 3 profiles that completed.

**hibrido-and -- a NEW finding, DIFFERENT from the "Unknown key
type," honestly unresolved this round.** Even with the backend on
the right profile (`hybrid`, see fix below) and a clean restart of
the entire stack, `/token` fails with `401`:
```
auth: path=/token method=POST error={"error":"invalid_client",
  "error_description":"client authentication failed"} detail=alg mismatch
```
**Partial finding, honestly recorded:** `opin_flow.py`'s
`load_client_signing_key()` (line ~586-607) only has explicit
branches for `"pqc"` and `"hybrid"` -- `"hibrido-and"` falls into the
`else` (classical PS256 signing with `client_one.jwks`'s real key),
which **by construction returns the SAME alg/kid the "hybrid"
branch itself uses for the `client_assertion`** (the function's
docstring confirms: "hybrid... kid is the CLASSIC key's kid... alg:
'PS256'"). **This means hibrido-and's specific "alg mismatch" cause
is NOT confirmed this round** -- it could be something else (e.g.,
the "hibrido_and_rsa_client" TLS cert interacting with some
cross-identity check between the TLS layer and the JWT layer that
this diagnostic did not have time to isolate). **Not hidden, not
worked around:** it remains recorded as an open gap, it needs a
dedicated round to isolate.

**Extra operational findings, found live, fixed:**
- **A BACKEND profile map, separate from the CLIENT map** (real
  finding): `auth`/`mongo_seed`/`mockapi` (`mock-service-os/mock_as`)
  only
  know `crypto-profiles/{classic,pqc,hybrid}.json` -- there is NO
  `hibrido-and.json`. Hybrid-AND never had its own JWT scheme
  (it only adds dual TLS authentication) -- also confirmed in the
  gateway's internal carve-
  out (Decision 44, it only uses `op_hybrid.crt`, never a
  separate file). New `BACKEND_CRYPTO_PROFILE_ENV` (orchestrator.py):
  maps hibrido-and -> "hybrid" for the backend switch, never
  "hibrido-and" (which made `configuration.js` hang trying to read a
  non-existent file).
- **Backend readiness wait**, needed for any profile
  switch (not just hibrido-and): `auth` (fast, ~3-20s) AND `mockapi`
  (Java/Micronaut, really ~30s) -- without waiting for both, the
  first
  call hits 401 (auth still booting) or 502 (mockapi still
  booting).

**This round's net result: 9 of the 12 smoke-gate runs genuinely
completed (classico/pqc/hibrido-v8 x L0, with real numbers identical
to what was already measured), not all 12 -- the original request
was 4 profiles, 3 arrived.**

**3. Python package versions -- compared and aligned.**

`install_common_packages.sh` (Terraform module, Decision 46) only
installs `python3-pip` (the TOOL) via `dnf` -- the real
dependencies (`cryptography`, `PyJWT`, `requests`, `pyOpenSSL`, ...)
are
installed AFTERWARD, by `deliver_source.sh` (`pip3 install --user -r
requirements.txt`, outside this round's scope -- a separate, already
existing script). `thesis/scripts/requirements.txt` pins versions
with a
HASH (`pip install --require-hashes`), explicitly generated via
`pip download --platform ... --python-version 3.9.25` for BOTH
real fleet architectures (x86_64 server/clients, aarch64
control) -- never for Windows (my dev environment).

**Real difference found, fixed:** my local venv
(`thesis/scripts/.venv/`) had OLD/DIFFERENT versions from the
current pin -- `cryptography==50.0.0` (pin: `50.0.2`), `PyJWT==2.13.0`
(pin: `2.15.1`), `requests==2.34.2` (pin: `2.32.5`, NEWER than the
pin, not older). **Fixed:** reinstalled to match
EXACTLY the version numbers from `requirements.txt` (the hash
itself cannot be checked on Windows -- the pinned hashes are for
Linux cp39 wheels, this machine downloads a Windows cp311/abi3 wheel,
a DIFFERENT binary artifact by construction, never an
integrity problem). Reconfirmed afterward: ML-DSA-65 parsing keeps
working with the pin's exact versions.
```
cryptography 50.0.2, pyjwt 2.15.1, requests 2.32.5, pyOpenSSL 26.4.0
ML-DSA parse OK: MLDSA65PublicKey
```
**No change to `requirements.txt` was needed** -- it was
already correct; only this machine's local venv had fallen out of
date relative to it.

**4. Control instance -- a 5h safety auto-shutdown, with terminate,
recorded.**

`thesis/results/v9/terraform/main.tf`, `control` module:
`self_terminate_hours = 5` (before: `0`, exempt) +
`instance_initiated_shutdown_behavior = "terminate"` (before: not
set, AWS default "stop"). **Reason:** closes the residual risk
Decision 49 item 4 listed (the control was the ONLY pilot resource
with no automatic safety net at all). **5h, not a
smaller number:** the real pilot lasts ~2h -- 5h gives a generous
margin (2,5x) without ever firing in a normal session, even with
delay; the RENEWABLE deadline mechanism
(`safety_timer.sh.tftpl`, already copied verbatim from
v8, Decision 46) lets the orchestrator renew the deadline if it needs
more time, same as any other pilot instance -- 5h is only the
LAST-RESORT floor for an ABANDONED session, never a normal
operational limit. **Replaces nothing:** the final destroy after the
60 runs remains mandatory (Decision 43/45/48/49), and the release
of EIPs by `cleanup.py` remains mandatory -- this auto-shutdown
only adds ONE MORE safety net specifically for the control,
same as the server/clients already had since Decision 23. `terraform
fmt`/`validate` confirmed clean after the change.

**Items still optimistic, explicitly reported:**
- **Hybrid-AND still does not work end to end** in this
  local validation -- a NEW finding (alg mismatch, item 2), root
  cause not isolated. It cannot be claimed that the 4 profiles work
  until this is
  resolved in a future, dedicated round.
- The full smoke gate (12/12) was never reached -- 9/12.
- The BACKEND profile-switching mechanism (auth/mongo_seed/mockapi)
  used in this validation (`docker compose --force-recreate`) is only
  for
  the LOCAL environment -- for the real remote pilot, the server runs
  ONE fixed profile for the entire block from deploy time (Decision
  23), it never
  switches in real time -- this switching mechanism never needs to
  exist
  there, only here.
- `dedicated_capture` (criterion 1) remains outside the tested scope.

Same rules: no action on AWS, no commit before the scanner,
report in chat. No push without explicit authorization.

## 51. Hybrid-AND fixed (root cause confirmed with evidence, not hypothesis) -- the smoke gate closes 12/12, all 4 profiles; pre-flight gains a permanent lock against the interpreter error; criterion 1's dedicated captures -- isolation/hash/reading validated locally, the network capture itself remains pending, honestly reported

**1. Hybrid-AND, "alg mismatch" at `/token` -- AMENDMENT 13
(implementation bug, never changed the pre-registered design).**

**(a) Reproduced, exact evidence:**
```
auth (backend): path=/token method=POST
  error={"error":"invalid_client","error_description":"client authentication failed"}
  detail=alg mismatch
```
**Who raises it:** the BACKEND (`auth`), inside the
`oidc-provider` library (not this project's code) --
`node_modules/oidc-provider/lib/shared/jwt_client_auth.js:15-17`:
```js
if (ctx.oidc.client.clientAuthSigningAlg) {
  if (header.alg !== ctx.oidc.client.clientAuthSigningAlg) {
    throw new InvalidClientAuth('alg mismatch');
  }
}
```
**Expected alg:** `RS256` (`client_one_hybrid_pub.jwks`, `client_one`'s
registered key under the backend's "hybrid" profile --
confirmed by reading the file: `"alg": "RS256"`). **Received alg:**
`PS256` -- captured LIVE, not assumed, by decoding the real JWT
`opin_flow.py` builds:
```
CRYPTO_PROFILE=hibrido-and -> load_client_signing_key() alg='PS256'
JWT HEADER DE VERDADE ENVIADO: {'alg': 'PS256', 'kid': '...', 'typ': 'JWT'}
```

**(b) Side by side, hibrido-v8 (passes) vs. hibrido-and (was
failing), `thesis/scripts/opin_flow.py`:**

| | hibrido-v8 (`CRYPTO_PROFILE=hybrid`) | hibrido-and (`CRYPTO_PROFILE=hibrido-and`, BEFORE the fix) |
|---|---|---|
| `load_client_signing_key()` | `elif crypto_profile == "hybrid":` (line 595) -- matches | falls into `else` (line 602) -- generic, NEVER matches "hibrido-and" |
| Signing key | `(classic_key, pqc_jwk)` -- RSA from `client_one.jwks` + ML-DSA from `client_one_pqc.jwks` | only the RSA from `client_one.jwks` (no ML-DSA) |
| `alg` returned | `"hybrid"` | `"PS256"` |
| `sign_jwt()` dispatches to | `_sign_jwt_hybrid()` -- external RS256 + embedded `"pqc"` claim (ML-DSA over RFC 8785) | `pyjwt.encode(..., algorithm="PS256")` directly -- no `"pqc"` claim |
| Real header sent | `{"alg": "RS256", ...}` | `{"alg": "PS256", ...}` |
| What the validator (`auth`) expects | `RS256` (`client_one_hybrid_pub.jwks`) | `RS256` (the SAME file -- the backend was already on the right profile) |
| Result | matches -- PASSES | does not match -- `alg mismatch` |

**(c) Client/backend profile mismatch hypothesis -- ruled out
with evidence, confirmed BEFORE the call:**
```
gateway (v9-mtls), log real: "profile=hibrido-and listening on :443" <- confirmado
auth (backend), log real:    "Crypto profile: hybrid (signingAlgs: MLDSA65-RSA2048-PSS-SHA256)" <- confirmado
```
Both sides were on the RIGHT pair (`BACKEND_CRYPTO_PROFILE_ENV`
maps hibrido-and -> hybrid for the backend, Decision 50) -- the
`force-
recreate` did NOT leave any hybrid/diverging state. The cause was
never
an inconsistent environment -- it was a missing `elif` in the
CLIENT.

**(d) Fix, only after the evidence -- an implementation bug, not a
change to the pre-registered design.** `thesis/scripts/opin_flow.py`,
`load_client_signing_key()`:
```diff
-        elif crypto_profile == "hybrid":
+        elif crypto_profile in ("hybrid", "hibrido-and"):
+            # Decisao 51: "hibrido-and" cai aqui tambem -- o
+            # mecanismo AND so acrescenta autenticacao TLS por DOIS
+            # certificados; nunca teve esquema de JWT proprio.
```
**No other line changed.** Verified that NO other point that
distinguishes "hybrid" (`get_client_cert_paths`, the
`get_local_leg_cert_
paths`-equivalent, `TLS_KEM_PROXY_CURVE_BY_PROFILE`) is on the
causal path of this specific error -- the dual mTLS (AND) handshake
ALREADY worked (`dualAuthenticated=true`, confirmed in the logs,
before and
after this fix), only the OAuth client_assertion was wrong.
**This never touches the 7 criteria, baselines, or tolerances of
the `v9-prereg` pre-registration** -- it is only a fix to the test
CLIENT
(`opin_flow.py`, a file shared across v4-v9, edited
additively, the same convention as always), never touching the
measurement design. Confirmed with Luciano that this waives prior
consultation (item (d) of the request: "if it's merely an
implementation bug, record it as a numbered Amendment").

**(e) Acceptance criterion -- MET, with no rounding:**
```
hibrido-and, bloco de 5 execucoes reais: as 5 deram
  {"http":44,"jwts":28,"jwks":4,"ca":4,"mtls":6}, "ok":true -- as 5
criterio5 (zero erros): pass=true, errors_found=[]

PORTA DE FUMACA: 12/12 -- "smoke_ok": true, "smoke_failures": []
  route_orders confirma os 4 perfis x 3 rotas, todos passando:
  L0:   hibrido-v8, classico, pqc, hibrido-and
  L219: classico, hibrido-and, hibrido-v8, pqc
  L325: hibrido-and, hibrido-v8, classico, pqc
avaliador real sobre as 12: todas as rows "ok":true, criterio5 pass=true
```

**2. Permanent lock against the interpreter error -- preflight.py.**

`check_client_python_environment(python_exe, requirements_path,
mldsa_cert_path)` (new): runs a probe in the SAME interpreter the
orchestrator will use -- prints the executable's path and the 3
versions (`cryptography`/`PyJWT`/`requests`), fails if any
diverges from `requirements.txt`'s pin, and PARSES a real
ML-DSA-65 certificate (`mock-service-os/certs/root_ca_pqc.crt`),
requiring exactly 1952 bytes of public key. Default: the project's
own venv (`thesis/scripts/.venv/Scripts/python.exe`) -- never the
system Python. Wired into `run_preflight()`, fails `go` if it fails.

**Proven, both sides, with REAL interpreters (not stubbed --
`test_ambiente_python_correto_aprova`/`test_ambiente_python_errado_
reprova`):**
```
=== venv do projeto ===
"ok": true, "versions": {"cryptography":"50.0.2","PyJWT":"2.15.1","requests":"2.32.5"},
"mldsa_public_key_bytes": 1952, "mismatches": []

=== Python de sistema (C:\Python313\python.exe) ===
"ok": false, "versions": {"cryptography":"46.0.3","PyJWT":"2.10.1","requests":"2.32.3"},
"mismatches": [
  "cryptography: instalado 46.0.3, requirements.txt pede 50.0.2",
  "PyJWT: instalado 2.10.1, requirements.txt pede 2.15.1",
  "requests: instalado 2.32.3, requirements.txt pede 2.32.5",
  "parse de ML-DSA-65 falhou ou tamanho errado: ValueError: Unknown key type: 2.16.840.1.101.3.4.3.18"
]
```
**Reproduces, to the letter, Decision 50's real error** -- now
caught by the pre-flight, never silently again.

**3. Criterion 1's dedicated captures -- locally validated what
could be, an honest pending item for what could not.**

**Validated locally:**
- **Structural isolation:** `test_capturas_dedicadas_rodam_fora_de_
  qualquer_janela_cronometrada` -- the 12 captures ONLY run after
  the entire block loop (never between an INICIO and FIM marker),
  never entering `execucoes_calls`/`criterio6_rows`. A mutant (a
  simulated capture INSIDE a window) proves the test would catch the
  contamination if it existed.
- **Artifact naming and hashing:** the 12 files come out as exact
  `{profile}_{route}.log`; a stable SHA-256 hash (same profile,
  different routes -> same hash, confirmed -- the TLS message size
  does not depend on the route).
- **Reading by the real evaluator:** `criterion_1_message_sizes(aws_dir=...)`
  reads the 12 files correctly, a **genuine PASS** (not just "doesn't
  break").

**Pending for AWS (or for a future dedicated local round, outside
this one's time budget):** the NETWORK CAPTURE itself, inside
`SSHExecutor.
dedicated_capture`, remains a placeholder (`cat /tmp/criterio1_...`,
Decision 49) -- never actually implemented. Found this round, while
trying: the real TLS traffic between the proxy and the gateway
happens on Docker's BRIDGE network (between containers), never on
loopback --
capturing this requires identifying the bridge's correct interface
(or running tcpdump INSIDE one of the containers), new complexity
that did not fit in this round's time. Honestly recorded, not hidden.

**Tests:** 57 (before: 48) -- 9 new (`check_client_python_
environment` + 2 mutants, `_parse_pinned_versions`, isolation of the
12 captures + mutant, naming/hash/reading of the 12 captures, profile
translation for hibrido-and already covered by Decision
49/50's existing tests).

Same rules: no action on AWS, no commit before the scanner,
report in chat. No push without explicit authorization.
## 52. Four items before the pilot's date: the pre-registration confirmed preserved (AND is only a TLS layer, by design), two real negative tests prove the AND gate, 0xFE65 confirmed on the wire, a grep audit finds and fixes 2 real bugs (dead in the pilot, alive on other paths), criterion 1's network capture actually implemented with a real pcap per profile

Response to the 4 requested items. No AWS, no push, the
`v9/fase1-local` branch untouched regarding `v9-prereg`/`main`.

**1. Does Amendment 13 preserve the pre-registered design? YES --
literal citation.**

From the `DECISIONS.md` frozen at `v9-prereg` (Decision 17, T6b,
section "Why the backend stays on `classic` for Hybrid-AND"):

> "the AND mechanism belongs entirely to the transport layer (dual
> proof of possession in the TLS handshake) -- it changes nothing
> about how the AS signs JWTs or how the RS signs responses. Leaving
> `auth`/`mockapi` on `classic` for this profile is a deliberate
> choice, not an omission: there is no (nor should there be a)
> "CRYPTO_PROFILE=hibrido-and" in the real `mock_as`/
> `insurance-server-lambdas`, because nothing there needs to know
> that the AND mechanism is in use."

And from Decision 4c (same file, the mechanism's origin): the AND
mechanism "only works in TLS 1.3 (the `signature_algorithms`/`CertificateRequest`
extended with code 0xFE65 and the design of the dual `CertificateVerify`)"
-- no mention of JWT/application signing in either source. Decision 1
(D3): "strict mode" is defined as
`RequireAndVerifyClientCert` on the server -- again, purely TLS.

**Conclusion: the pre-registration NEVER required AND at the JWT
layer -- it explicitly requires it ONLY at the TLS layer.** Amendment
13 (which made `hibrido-and` sign the JWT exactly like
`hibrido-v8`/"hybrid", RS256 + an embedded `pqc` claim) is the fix the
pre-registration itself PROVIDED FOR, not a deviation from it.
Also confirmed on the orchestrator's side
(`orchestrator.py`, line ~193): `BACKEND_CRYPTO_PROFILE_ENV["hibrido-
and"] = "hybrid"`, with the same reasoning documented there. The two
profiles, after Amendment 13, differ EXACTLY as pre-registered:
identical in everything (JWT, JWKS, backend) except the TLS layer,
where
`hibrido-and` requires the dual pair (`Dual.Require=true`) and
`hibrido-v8`
offers no Dual at all. **I did not stop nor consult -- the request's
premise (the pre-registration requiring AND at the JWT layer) is
false, confirmed by direct citation.**

**2. Proof that Hybrid-AND really enforces the AND mechanism.**

*(a) Negative handshake test, the dual pair intact, one half invalid
at a time.* Added `and-bad-classical`/`and-bad-pqc` to
`thesis/results/v9/integration/negtest/main.go` (`tryANDBadClassical`/
`tryANDBadPQC`, reusing the already existing
`attackerRSACert()`/`attackerMLDSACert()`)
-- unlike the already existing `and-single-chain` (which OMITS the
entire Dual), these keep `cfg.Dual` set with
`Require=true` and only swap ONE of the two chains for an attacker's,
unrelated to the real CAs. Run against the real `v9-mtls`,
`CRYPTO_PROFILE=hibrido-and`:

```
DEBUG raw-handshake-succeeded curve=SecP384r1MLKEM1024 dualAuthenticated=true tlsVersion=TLS 1.3
RESULT scenario=and-bad-classical profile=hibrido-and outcome=REJECTED error="handshake reported success but a server-side rejection followed: remote error: tls: certificate required"

DEBUG raw-handshake-succeeded curve=SecP384r1MLKEM1024 dualAuthenticated=true tlsVersion=TLS 1.3
RESULT scenario=and-bad-pqc profile=hibrido-and outcome=REJECTED error="handshake reported success but a server-side rejection followed: remote error: tls: bad certificate"
```

Both REJECTED -- the dual pair with an attacker's half never
passes, confirming the gate requires BOTH chains valid and matching
the same identity, not just "some classical chain present."

*(b) Evidence from the real handshake -- 0xFE65 on the wire + the
observed flight vs. expected.* Captured locally (the gateway
container's OWN network namespace, never loopback -- the same
capture point as item
4 below), decrypted with the gateway's real keylog, via tshark:

ClientHello + CertificateRequest, `sig_hash_alg` field (the list of
offered/accepted `SignatureScheme`s):
- **Hybrid-AND:** `0xfe65,0x0904,0x0905,...` -- 0xFE65 present, FIRST in the list, on both sides (the client's ClientHello AND the server's CertificateRequest).
- **Hybrid-v8 / PQC / Classical:** 0xFE65 ABSENT in all three captures -- confirmed by a direct grep on tshark's output, zero occurrences.

`DualAuthenticated` (the gateway's real log, same connection):
```
hibrido-v8:  curve=SecP384r1MLKEM1024 dualAuthenticated=false clientCert="hibrido_v8_client"    handshakeBytesIn=8425  handshakeBytesOut=8552
hibrido-and: curve=SecP384r1MLKEM1024 dualAuthenticated=true  clientCert="hibrido_and_rsa_client" handshakeBytesIn=11924 handshakeBytesOut=12177
```

| Profile | Expected bytes (in/out) | Observed bytes (in/out) | Deviation |
|---|---|---|---|
| Hybrid-v8 | 8.397 / 8.552 | 8.425 / 8.552 | **+28B** on `in`, 0 on `out` |
| Hybrid-AND | 11.902 / 12.177 | 11.924 / 12.177 | **+22B** on `in`, 0 on `out` |

`handshakeBytesOut` (the SERVER's flight, which never changes
depending on the client used) matches EXACTLY on both profiles.
`handshakeBytesIn` (the CLIENT's flight) deviates +22/+28B on both --
same order of magnitude, same sign, on both profiles, which points to
a common METHODOLOGICAL cause (the trigger connection used here was
the `negtest -scenario
matrix` harness, which builds its `tls.Config` by hand in Go, not the
pilot's real `opin_flow.py`/proxy client -- small default TLS
extension differences between the two stacks, not a problem with the
AND mechanism itself).
Honestly recorded: the deviation is small (<0,3%), consistent across
the
two profiles, and never changes the conclusion (AND present, 0xFE65
negotiated,
flight ~1,4x larger than Hybrid-v8 as expected) -- but it is real,
not
hidden.

*(c) Neither proof failed -- Hybrid-AND is NOT degraded to v8.*
0xFE65 present, `DualAuthenticated=true`, both negative tests
rejected, a flight ~1,4x larger exactly where expected.

**3. Audit of the bug class -- full grep, table + 2 real fixes.**

Scope: client (`opin_flow.py`), orchestrator (`orchestrator.py`),
evaluator (`evaluate_criteria.py`), gateway/proxy (Go), backend
(`mock_as`/`mongo-seed`). v8 (frozen, 3 profiles, with no concept of
`hibrido-and`) excluded from scope by construction.

| File:line | What it decides | hibrido-and |
|---|---|---|
| `opin_flow.py:242` `_USE_TLS_KEM_PROXY` | whether to use the proxy | explicit in the tuple -- OK |
| `opin_flow.py:263` `V9_PROFILE_NAME` | translation to display name | explicit key -- OK |
| `opin_flow.py:406` `get_client_cert_paths` | which cert/key the client loads | **fell into `else` -> CLASSICAL cert. FIXED** (Decision 52): `elif` now includes `hibrido-and`, same cert as "hybrid" |
| `opin_flow.py:422` `get_local_leg_cert_paths` | the local leg's cosmetic cert | **fell into the default (which called the already-wrong function above). FIXED**: added to the tuple, same placeholder as "hybrid" |
| `opin_flow.py:595` `load_client_signing_key` | JWT alg/claim | fixed in Decision 51 (Amendment 13) -- confirmed still correct |
| `opin_flow.py:874` `load_client_encryption_key` | id_token's "enc" key | falls into `else` -> `client_one.jwks`, **correct by design** (same explicit doc: "pqc/hybrid still use classic_one's own plain-RSA enc key" -- hibrido-and inherits the same reason, RSA only at this layer) -- justified, no code fix |
| `opin_flow.py:971` `verify_ca_chain` | which CA to validate root/issuer-ca.pem against | falls into `else` -> `ca.crt`, **correct by design** (explicit doc: "classic/hybrid... both signed directly by this project's own real mTLS trust anchor") -- justified |
| `opin_flow.py:1004` `TLS_KEM_PROXY_CURVE_BY_PROFILE` | legacy proxy's curve (only the path WITHOUT V9_HARNESS) | no key -- if reached, immediate `KeyError` (a loud failure, never a silent wrong answer); a dead path in the real pilot (V9_HARNESS=1 always, skips this whole dict) -- **justified, not a silent failure** |
| `opin_flow.py:1090` legacy proxy's early-return guard | whether to skip the proxy entirely | `and crypto_profile != "hibrido-and"` explicit -- OK |
| `opin_flow.py:1416` `dispatch` (signing telemetry) | log label | keyed by `alg` (always "hybrid" for hibrido-and, by Decision 51's construction) -- OK, never "unknown" in practice |
| `orchestrator.py` `PROFILES`/`CLIENT_CRYPTO_PROFILE_ENV`/`BACKEND_CRYPTO_PROFILE_ENV` | client/backend translation | all 4 keys explicit -- OK |
| `evaluate_criteria.py` `EXPECTED_CURVE`/`CERTIFICATE_BASELINE`/`CLIENTHELLO_BASELINE`/`HANDSHAKE_MESSAGE_BASELINE` | expected curve/baselines | all 4 keys explicit -- OK |
| `gateway/main.go:33,259` `expectedCurve`/switch | expected curve, which TLS config to build | explicit `case "hibrido-and"` -- OK |
| `gateway/main.go:150`, `business_server.go:107` | requires `DualAuthenticated` | explicit `profile == "hibrido-and"` -- OK |
| `business_server.go:186` | widens the internal caller's CA pool for pqc | `else` covers hibrido-and, **correct** (same treatment as hibrido-v8, which also does not need the widening -- both use the same real internal-caller `op_hybrid.crt`) |
| `business_server.go:233` `realCAFilesForProfile` | which CA pair to serve at /root-ca.pem | `default` covers classico+hibrido-and, **justified in the code's own comment** (opin_flow only distinguishes pqc vs. the rest) |
| `proxy/main.go:223` `buildClientTLSConfig` | which TLS config the proxy loads | explicit `case "hibrido-and"`, `default` is fail-closed (`error`) -- OK, this was already the right pattern |
| `mock_as/configuration.js:25`, `mongo-seed/start.sh` | which `crypto-profiles/*.json`/JWKS the backend loads | `hibrido-and` NEVER reaches here (translated to "hybrid" earlier, by design -- Decision 17) -- N/A, not a gap in this file |

**Diff of the 2 fixes** (`thesis/scripts/opin_flow.py`):
```diff
-    elif crypto_profile == "hybrid":
+    elif crypto_profile in ("hybrid", "hibrido-and"):
         crt, key = CERTS_DIR / "client_one_hybrid.crt", CERTS_DIR / "client_one_hybrid.key"
...
-    if crypto_profile in ("pqc", "hybrid"):
+    if crypto_profile in ("pqc", "hybrid", "hibrido-and"):
         return get_client_cert_paths("classic")
```
Neither is exercised by the real pilot today (`V9_HARNESS=1`
skips both functions entirely -- the Go proxy loads the AND cert
natively, `proxy/main.go`'s `dualClientConfig`, already correct and
fail-closed). Fixed anyway, as a genuine fix and not just a
consequence -- they could be reached by any future use of
`opin_flow.py` outside V9_HARNESS (manual diagnostics, v8-style
direct execution). 4 new, pure tests, no Docker: `thesis/scripts/
tests/test_profile_cert_dispatch.py`.

**4. Criterion 1's network capture -- actually implemented, a real pcap per profile.**

**Capture point defined:** the SERVER's PRIMARY interface (never
loopback) -- even in the co-located L0 scenario, the client always
dials
the server's real PRIVATE IP (`_server_gateway_ip`, Decision
49/Amendment
13), never 127.0.0.1, so all client-facing mTLS traffic crosses this
real interface. `SSHExecutor._primary_iface` discovers it via `ip -o
-4 route show to default` (never hardcoded -- it varies between
`ens5`/`eth0` across EC2 families). Decryption via `KEYLOG_PATH`, read
from the gateway container's own
filesystem (`docker exec cat`) after the
capture. Extraction via tshark, reusing the `mockopin-v9-
measure` image already built for T6 (pcap reading only, no new
capture inside the container).

**Real bug found and fixed along the way:** `KEYLOG_PATH` was only
read in `main()` -- `runBusinessMode` (the ONLY mode the real pilot
uses, `HTTP_MODE=business`) passed a hardcoded `nil` for
`KeyLogWriter`,
silently never writing anything. Fixed in `business_server.go`
(also reads `KEYLOG_PATH` inside `runBusinessMode`) -- a pure
implementation
fix (instrumentation wiring), it never changed any
handshake/network behavior, it never needed an amendment.

`SSHExecutor.dedicated_capture` rewritten (replaces Decision 49's
placeholder): discovers the interface, starts `tcpdump` in the
background on
the server, triggers ONE real settling run on the client (the same
isolation guarantee as `readiness_probe` -- it never enters
criteria 4/6's counts), stops tcpdump, reads the container's keylog,
runs tshark, returns the block in the SAME format `measure.sh`/the
evaluator already use. 7 new tests (`test_orchestrator.py`): the
interface
never loopback, kill by PID, start->trigger->kill order, keylog+tshark
via `mockopin-v9-measure`, parsing accepted by the real evaluator
(`hibrido-v8` baselines matching exactly), a loud failure if the
interface comes back empty + a mutant.

**LOCAL (not AWS) validation, real, not simulated:** a script at
`thesis/results/v9/campaign/local_validation_criterio1/` (gitignored,
never committed -- pcap/keylog are TLS session secrets). For each
of the 4 profiles: brings up `v9-mtls` with `KEYLOG_PATH`, captures on
the PRIMARY interface of the container's OWN network namespace
(`eth0`, never
loopback -- via a `--net container:v9-mtls` sidecar), triggers a
real, successful connection (`negtest -scenario matrix`), extracts
with tshark.
**One real pcap per profile, decrypted, with the flight extracted:**

| Profile | ClientHello | Certificate (server) | Total observed flight | 0xFE65? |
|---|---|---|---|---|
| Classical | 332B | 909B | ~1,4KB | no |
| PQC | 1.803B | 5.628B | ~8,4KB | no |
| Hybrid-v8 | 1.900B | 6.251B | ~8,5KB | no |
| Hybrid-AND | 1.876B | 6.578B | ~12,1KB | **yes** |

Matches the expected order of magnitude (AND larger than v8, v8/PQC
larger
than Classical) across all 4. **What is left only for AWS to
confirm:** the
real interface (`ens5` or equivalent, not Docker bridge's `eth0`),
the traffic
crossing TWO real instances (not two containers on the same
host), and the pilot's exact byte tolerance (SAN with a real EIP,
Decision 29) -- the capture's MECHANICS (correct point, decryption,
extraction, the format the evaluator accepts) are validated locally
with
real, not simulated, data.

**Tests:** 68 in total across the two packages touched this round --
64 in `thesis/results/v9/campaign/tests/` (57 before + 7 new for
`dedicated_capture`), plus 4 new, isolated ones in `thesis/scripts/
tests/test_profile_cert_dispatch.py`. All passing.

**This round's local commit** (no push): branch `v9/fase1-local`,
files touched -- `thesis/results/v9/integration/negtest/main.go`
(`and-bad-classical`/`and-bad-pqc` scenarios), `thesis/results/v9/
integration/gateway/business_server.go` (the KEYLOG_PATH fix),
`thesis/scripts/opin_flow.py` (2 fixes from item 3), `thesis/
results/v9/campaign/scripts/orchestrator.py` (real `dedicated_capture`
+ `KEYLOG_PATH` in `start_block`), `thesis/results/v9/campaign/
tests/test_orchestrator.py` (+7), `thesis/scripts/tests/
test_profile_cert_dispatch.py` (new, +4), `thesis/results/v9/
.gitignore` (+1 line, local validation folder).

No item this round required an amendment to the pre-registration --
item 1 confirmed that the pre-registration already provided for
exactly what was implemented, and items 2-4 were implementation
proof/fixes, never a design change. I continue to not authorize any
push nor any AWS resources.

## 53. Five points before the pilot's date: the amendment criterion clarified and Amendment 14 recorded (3 fixes from Decision 52 should never have been left out); KEYLOG_PATH confirmed off across every timed window with a real test; a correction to a wrong claim from Decision 52 (get_local_leg_cert_paths was never "dead"); capture preflight + per-profile proof in the smoke gate; the root cause of the +22/28B deviation isolated in the ClientHello

Response to the 5 requested points. No AWS, no push, branch
`v9/fase1-local`.

**1. Amendment criterion -- the 3 missing fixes become Amendment 14.**

There are TWO distinct criteria in this project, never conflated
before this round:

a) **The criterion of the pre-registration ITSELF** (`v9-prereg`,
final section, cited literally): "Criterion amendment, after the
`v9-prereg` tag:
requires a new, dated decision, with a reason... Any change to one
of the 7
criteria above (threshold, method, route, N) AFTER the tag exists
needs a new numbered entry". **This criterion is strict:**
it only protects the TEXT of the 7 go/no-go criteria (Decision 21),
never
any line of the project's code.

b) **Luciano's operational instruction for this implementation
phase**, explicitly given in Decision 51 and CONFIRMED right there:
"Confirmed with Luciano that this waives prior consultation
(item (d) of the request: 'if it's merely an implementation bug,
record it
as a numbered Amendment')." Decision 51 itself is explicit that the
alg-mismatch fix did NOT touch any of the 7 criteria ("This never
touches the 7 criteria, baselines, or tolerances of the
v9-prereg pre-registration"), but it was recorded as Amendment 13
anyway -- because of criterion (b), never (a).

**Conclusion: criterion (b) is what actually governs this project
during implementation rounds, and it does NOT support a difference
between
Amendment 13 and this round's 3 fixes -- by that SAME rule, all 3 are
"implementation bugs" and should have been Amendments too.**
Recording now:

**Amendment 14 (dated 2026-11-07, retroactive to this same session --
covers the 3 fixes from commit `ec37ec2c`, Decision 52):**

| # | Fix | File | Reason | Effect on measurements |
|---|---|---|---|---|
| 14.1 | `get_client_cert_paths("hibrido-and")` now returns the hybrid cert, not the classical one | `thesis/scripts/opin_flow.py` | hibrido-and fully reuses hybrid's app identity (Decision 17) -- the generic `else` should never have caught this profile | **NONE** -- confirmed with a test (item 3 below): this function is only reachable from the NON-V9_HARNESS branch of `start_tls_kem_proxy`, never executed by the real pilot (V9_HARNESS=1 always) |
| 14.2 | `get_local_leg_cert_paths("hibrido-and")` added to the tuple, keeps the classical placeholder (does not inherit 14.1's effect) | `thesis/scripts/opin_flow.py` | same reason "hybrid" was already in the tuple (connection-pool separation, never ML-DSA) | **NONE on bytes/counts** -- this function's cert is cosmetic (never verified by the local listener, confirmed in its own docstring), BUT the function ITSELF runs on every real run (fix to a wrong claim from Decision 52 -- see item 3) |
| 14.3 | `KEYLOG_PATH` now also read in `runBusinessMode` (Go gateway) | `thesis/results/v9/integration/gateway/business_server.go` | the only mode the pilot uses (`HTTP_MODE=business`) never read the env var -- hardcoded `nil` | **NONE on handshake/network** -- it only turns a session-key file's WRITING on/off; it never participates in any accept/reject decision nor in any byte on the network |

None of the 3 changed any threshold/method/route/N of the 7 criteria
(confirmed, item (a) above also remains intact) nor any MEASURED
pilot behavior (confirmed in the "effect" column -- 2 of them are
dead or cosmetic, the third is just instrumentation OFF by
default, see item 2 below).

**2. KEYLOG_PATH and the Go gateway.**

**(a) Off across every timed window, proven with a test.**
Real finding this round (not a hypothesis): Decision 52's first
version turned on `KEYLOG_PATH` in EVERY `start_block` -- that is, in
EVERY timed run, not just during `dedicated_capture`. This
would have introduced extra I/O per handshake (writing a session key
to disk) in all 60 real runs, never present before
this round -- a real MEASUREMENT effect, not just a theoretical one.
**Fixed:** `_launch_gateway(profile, keylog=False)` (a new method,
factored out of `start_block`) is the ONLY place that decides the
flag --
`start_block` always calls with `keylog=False` (never turns it on);
ONLY
`dedicated_capture` calls with `keylog=True`, restarting the SAME
container ONLY when it is about to capture. Guarantee: the
environment variable
(`-e KEYLOG_PATH=...`) is set only on the second call to
`_launch_gateway`, never the first. New tests (`test_orchestrator.py`):
`test_start_block_nunca_liga_keylog_path` (green), `test_run_execution_
nunca_menciona_keylog` (green), `test_dedicated_capture_liga_keylog_
so_na_propria_reinicializacao` (confirms BOTH calls exist and
differ), `test_mutante_keylog_sempre_ligado_e_pego` (a mutant that
reproduces THIS round's ORIGINAL bug -- confirms the tests above
actually depend on the fix).

**(b) The gateway restart happens outside any timed window, it never
alters already-measured data.** Structural, not just by convention:
`run_pilot` runs the entire block loop (the 60 runs +
`stop_block` for each block) FIRST; ONLY THEN, in a SEPARATE
loop (`if not skip_dedicated_captures: for profile... dedicated_
capture(...)`), do the dedicated captures run. `dedicated_capture`
now calls `self.start_block(profile, route)` (rebuilds the
right backend/proxy/signer for this capture's PROFILE -- a real
finding: without this, the gateway that would be running at that
point would be the one from the
LAST block in the grid, not necessarily the right profile) and only
THEN `_launch_gateway(..., keylog=True)`. Both restarts
happen inside this second loop, which only starts after ALL
data from the 60 runs has already been written to disk
(`piloto_calls.
json`/`criterio6_execucoes.json`) -- restarting the container after
that
can NEVER alter already-persisted data. `dedicated_capture`
ends with `self.stop_block(...)`, symmetric cleanup.

**(c) The gateway binary's hash/identity -- there is NO pre-
registered hash to compare against, but there IS a pre-registered
MECHANISM to guarantee integrity, and it remains correct.** Searched
across the entire frozen
`v9-prereg`: no literal hash for any `gateway` build was
registered at any earlier point -- there is no "old hash" to compare
against a "new" one. What DOES EXIST, pre-registered
(the PKI/binary/collection delivery section): **"Binary delivery:
same path -- the operator `scp`s the `gateway`/`proxy` (plus the
`.sha256`) to the control, the control `scp`s it to each
destination instance... each instance runs `sha256sum -c` before
using it."** This
mechanism ALWAYS recomputes the hash from the binary that will
actually be used (never reuses an old value) -- my
`KEYLOG_PATH` fix changes the compiled binary (any source
change changes it), and the pre-registered mechanism correctly
captures this
by construction, with no extra action needed from me. **Honest,
separate finding:** the current `SSHExecutor`
(`orchestrator.py`) NEVER implemented this `scp`+
`sha256sum -c` mechanism for the gateway -- it assumes a Docker
image already
built on the instance (`docker run ... mockopin-v9-gateway`), with
no hash check at all. A PRE-EXISTING gap (not caused by this
round), recorded here for completeness, not fixed now (it requires
deciding BETWEEN the pre-registered binary+sha256 mechanism OR
formalizing build-by-Docker-image as the real method -- a design
decision, not an implementation bug, outside this round's scope).

**3. Test for the "dead in the pilot" claim -- it is a real fix to
Decision 52.**

`thesis/scripts/tests/test_profile_cert_dispatch.py`, 3 new tests:

- `test_get_client_cert_paths_nunca_chamada_sob_v9_harness` --
  **GREEN.** Proves `get_client_cert_paths` is genuinely dead
  under `V9_HARNESS=1` (only reachable from the non-harness branch
  of
  `start_tls_kem_proxy`, which the real pilot never executes).
- `test_experimento_descartavel_get_client_cert_paths_E_chamada_sem_
  v9_harness` -- **RED, on purpose (the disposable experiment
  requested).** The SAME assertion, now without `V9_HARNESS` -- it
  fails,
  confirming the green test above is not vacuous (the function is
  not
  "dead" in general, only within the right branch).
- `test_get_local_leg_cert_paths_e_live_sob_v9_harness_correcao_da_
  decisao_52` -- **finding: Decision 52 was wrong.** It claimed
  that BOTH functions were dead under `V9_HARNESS=1`. False for
  `get_local_leg_cert_paths`: `run_insurance_flow()`/`run_person_
  flow()` call this function with NO `V9_HARNESS` guard at all,
  so it runs on EVERY real run, harness on or not.
  Confirmed by actually running `run_insurance_flow("hibrido-and")`
  for real
  (network blocked on purpose right after, just to isolate
  what matters) -- `get_local_leg_cert_paths` was called BEFORE
  any network attempt. **Decision 52's correction recorded
  here, not hidden:** fix 14.2 was never "dead" -- it is
  cosmetic (its cert is never verified by the local listener), but
  it
  really runs. Amendment 14's table (item 1 above) already reflects
  this correction.

**4. Capture in AWS's topology -- preflight + proof in the smoke gate.**

**(a) New preflight**, `thesis/results/v9/campaign/scripts/
preflight.py`: `check_capture_prerequisites(host)` -- 1 SSH call
combining 5 probes (`tcpdump` on the PATH, `sudo -n true` to confirm
passwordless sudo -- required by `dedicated_capture`'s real
`tcpdump`,
the same convention as real v8's `campaign_run.py` cited in
Decision 46/Terraform itself; the `mockopin-v9-measure` image present
via
`docker image inspect`; `/tmp` writable; the primary interface via
`ip
-o -4 route show to default`, never `lo`). `run_capture_preflight
(hosts)` aggregates several hosts, fail-closed (`go` only `True` if
ALL
pass). **How the image gets to the instance, honestly
documented:** built from synced source code
(the same convention as EVERY other `docker build` in this project,
never
downloaded from a registry) -- the check only confirms final
PRESENCE, not the
origin; the sync+build step does not yet exist in the real
deploy (a separate gap, outside this round, the same family as the
finding in
item 2c).

**(b) The smoke gate gains the proof.** `run_smoke_gate` now: (1)
calls
`executor.capture_ready_check()` FIRST -- `LocalExecutor` always
`go=True` (no real infrastructure to check), `SSHExecutor` really
calls
`preflight.run_capture_preflight([self._server_ip()], ...)`; (2)
ONLY THEN do the 12 runs run (now with
`skip_dedicated_captures=True` explicit -- fixing a divergence
that already existed between `run_pilot`'s docstring, which said
the smoke gate skipped this part, and the code, which never actually
skipped it); (3) after the 12, it runs `dedicated_capture` ONCE per
PROFILE (4, never 12) on a representative route, writing to
`smoke_capture_proof/` (never `criterio1_capturas/`), validating each
block with the REAL evaluator (`ec._message_sizes_for_profile`).
`smoke_ok` now requires all 3 things: 12/12 runs, 0 failures, AND
`capture_proof_ok`.

**(c) Fail-closed, a clear message, before any run --
tested.** `test_porta_de_fumaca_aborta_antes_de_qualquer_execucao_
se_prerequisito_de_captura_faltar`: with `capture_ready_check()`
failing, `aborted_before_execution=True`, `total_execucoes=0`,
no run file is written, the message names exactly
what is missing (e.g., "tcpdump not found in PATH"). A mutant
(`test_mutante_porta_de_fumaca_ignora_capture_preflight_e_pego`)
confirms the gate is load-bearing -- without it, the 12 runs
would run even with `tcpdump` missing.

**Summary diff** (`preflight.py`): +90 lines (`_CAPTURE_PROBE_
SCRIPT`, `check_capture_prerequisites`, `run_capture_preflight`,
never touching `run_preflight` nor any existing check).
**Summary diff** (`orchestrator.py`): `_launch_gateway` factored out
of
`start_block` (item 2), a new `capture_ready_check` on both
Executors, `dedicated_capture` (SSHExecutor) gains `start_block`+
`_launch_gateway(keylog=True)`+`stop_block` at the start/end, `run_
smoke_gate` rewritten (preflight + capture proof, item 4).

**What only AWS confirms (unchanged since Decision 52, recorded
again for completeness):** the REAL interface (`ens5` or equivalent,
not the local Docker bridge's `eth0`), the traffic crossing TWO
real EC2 instances, the pilot's exact byte tolerance
(SAN with a real EIP), and now also: whether `mockopin-v9-measure`
actually
builds/arrives on each instance (the sync mechanism still
not implemented, item 4a).

**5. The handshakeBytesIn deviation (+22/+28B) -- cause isolated, not just assumed.**

Captured again, now looking at EACH message individually (not
just the aggregate) against the REAL baselines from
`evaluate_criteria.py`
(`HANDSHAKE_MESSAGE_BASELINE`/`CLIENTHELLO_BASELINE`), for the
Hybrid-v8 profile:

| Message (client) | Observed (raw) | Baseline (raw) | Deviation |
|---|---|---|---|
| ClientHello | **1900** | **1872** | **+28B** |
| Certificate_cliente | 6140 | 6140 | 0 |
| CertificateVerify_cliente | 260 | 260 | 0 |
| Finished_cliente | 32 | 32 | 0 |

**The deviation is 100% concentrated in the ClientHello -- every
other message matched EXACTLY, 0B difference.** Cause isolated in
the code,
not assumed: `thesis/results/v9/integration/negtest/main.go`'s
`baseConfig()` (used to trigger this local validation's connection,
via `-scenario matrix`) sets `MinVersion: tls.VersionTLS12` for
ALL profiles, generically -- while `proxy/main.go`'s
`singleChainClientConfig()` (the pilot's REAL client) receives
`minVersion` PER PROFILE, and `hibrido-v8`/`pqc` are called with
`tls.VersionTLS13` explicitly (only `classico` uses `TLS12`). A
`ClientHello` that declares TLS 1.2 support HAS to announce the
list
of legacy cipher suites and additional signature_algorithms valid
for 1.2 -- exactly what inflates the `ClientHello` by ~22-28B,
varying per profile according to that extra list's exact content.
**It is not NewSessionTicket (that is post-handshake, never
counted in
`handshakeBytesIn/Out`, which closes the snapshot right after
`Handshake()` returns) nor TLS 1.3 record overhead (confirmed
record by record: each AEAD record has 17B of overhead -- 1B
content-type + 16B tag -- IDENTICAL on both sides, already baked
into
both numbers, never the cause of the DIFFERENCE between them).**

**Conclusion: this deviation is an artifact of the VALIDATION METHOD
(negtest
used as the connection trigger for this local capture), never a
property of the pilot's real client** (`opin_flow.py`/proxy, which
pins `MinVersion` correctly per profile) -- it should not appear
in a measurement made with the real client.

**Pre-registered tolerance for `handshakeBytesIn/Out` -- DOES NOT
EXIST, explicitly declared.** What the pre-registration defines
(Decision 20/29/30) is tolerance for criterion 1 (sizes PER
MESSAGE, via tshark): today, **0B for the ClientHello, ±4B for the
Certificate, 0B for the rest** -- but this measures a DIFFERENT
quantity (the `tls.handshake.length` field of each decrypted
message), not the aggregate counter `handshakeBytesIn/Out` the
gateway itself logs (RAW bytes on the TCP connection, including
record/AEAD overhead). No tolerance was pre-registered
for this second number specifically.

**Proposal, not applied retroactively:** adopt the SAME 0B tolerance
criterion_1 already uses for the ClientHello (the only message where
some deviation historically appeared), propagated to the aggregate --
in other words, `handshakeBytesIn/Out` measured with the pilot's REAL
CLIENT should match EXACTLY (0B) against the historical values
(8.397/8.552, 11.902/12.177), since every individual message is
already required
to be within 0B/±4B and the aggregate is just their sum plus
fixed protocol overhead (identical across runs). Proposal recorded
here for
Luciano to decide -- NOT applied to any existing criterion this
round, and the real measurement (when done with the real client, not
negtest) needs to be redone before declaring this tolerance
met or not.

**Tests:** 88 in total across the packages touched this round -- 81
in `thesis/results/v9/campaign/tests/` (68 before + 13 new: 4
KEYLOG_PATH, 8 capture preflight, 5 smoke gate/capture -- the exact
count
is in the test names above, some cover more than one
point), plus 7 in `thesis/scripts/tests/test_profile_cert_dispatch.py`
(4 before + 3 new from item 3). All passing.

**Local commit** (no push), branch `v9/fase1-local`: files
touched -- `thesis/results/v9/campaign/scripts/preflight.py` (new:
`check_capture_prerequisites`/`run_capture_preflight`), `thesis/
results/v9/campaign/scripts/orchestrator.py` (`_launch_gateway`,
`capture_ready_check` on both Executors, `dedicated_capture`
restructured, `run_smoke_gate` rewritten), `thesis/results/v9/
campaign/tests/test_orchestrator.py` (+17), `thesis/results/v9/
campaign/tests/test_preflight.py` (+8), `thesis/scripts/tests/
test_profile_cert_dispatch.py` (+3, docstring fixed).

Amendment 14 recorded (item 1). No other item required an amendment --
item 2 was an implementation fix (instrumentation OFF by
default, never affecting measurement), item 3 confirmed and fixed
a claim from Decision 52 (never changed the design), item 4 added a
check/proof (additive, never changed an existing criterion), item 5
is diagnosis + a proposal NOT applied. I continue to not authorize
push nor AWS resources.

## 54. Four points before the pilot's date: scp+sha256sum -c verification of the gateway binary implemented and tested (tampered aborts, correct passes), the byte-deviation hypothesis CLOSED (0B across 480 real connections, 4 profiles), a tolerance proposed from measured variance, a self-contained readiness dossier (7 criteria, Luciano's prerequisites, cost/emergency, residual risks, runbook)

Response to the 4 requested points. No AWS, no push, branch
`v9/fase1-local`.

**1. Gateway binary verification in the real SSHExecutor -- implemented.**

A mechanism ALREADY PRE-REGISTERED (`v9-prereg`, "Binary delivery"
section:
"the operator `scp`s the `gateway`/`proxy`... each instance runs
`sha256sum -c` before using it"), never implemented before this
round (an honest gap from Decision 53, item 2c) -- now implemented in
`SSHExecutor`:

- `_local_gateway_binary_info()`: extracts `/gateway` from the
  ALREADY built local Docker image (`docker create`+`docker cp`, the
  same pattern as
  `certs/Makefile`), computes a real sha256, runs `go version -m`
  via `mockopin-v9-toolchain` (static reading, never executing the
  binary) and reads `/build_metadata.json`, which the toolchain
  ITSELF already records (`go_tag`, `go_commit`, the AND patch's
  hash) -- confirmed
  by actually running it this session: `go1.27.3`, path
  `mockopin-v9-gateway`, `CGO_ENABLED=0 GOARCH=amd64 GOOS=linux`.
- `_verify_gateway_binary(profile, route)`: `scp`s the binary to the
  server, writes the `.sha256` remotely, runs `sha256sum -c` THERE
  -- raises `RuntimeError` BEFORE `_launch_gateway` runs if it
  diverges.
- `_verify_running_gateway_binary(verification)`: closes the full
  loop -- after the container comes up, it checks that the binary
  INSIDE it (`docker exec ... sha256sum /gateway`) matches the
  SAME hash verified in transit (otherwise the transit
  verification would prove little, the Docker image could have been
  built from a different binary).
- `start_block` calls both, in this order, BEFORE any
  run. `dedicated_capture` re-checks the container (not the
  transport, which does not change) after restarting with
  `KEYLOG_PATH`.
- Each block's manifest (`run_pilot`/`run_smoke_gate`) gains
  `gateway_binary_verifications`: one entry per block, with sha256,
  `go_version_m`, `go_build_version`, toolchain metadata, and both
  verification results (transport + running container).

**Test with a tampered binary -- aborts BEFORE any run
(confirmed):**
```
test_start_block_aborta_antes_de_qualquer_execucao_se_binario_adulterado_no_transporte -- PASS
  RuntimeError("sha256sum -c FAILED in transport...") raised
  BEFORE any "docker run -d --name v9-mtls" or
  "start_tls_kem_proxy" shows up in the calls -- confirmed
  explicitly (assert not any(...)).
test_start_block_aborta_se_binario_do_container_rodando_diverge -- PASS
  same guarantee for the second loop (container already running
  with a binary that differs from the one verified).
```
**Test with the correct binary -- passes:**
```
test_start_block_verifica_binario_correto_e_passa -- PASS
  gateway_binary_verifications[0] = {transfer_sha256sum_c_ok: true,
  running_container_sha256_ok: true, go_build_version: "go1.27.3",
  toolchain_build_metadata: {...}} -- e a execucao prossegue
  normalmente (proxy/signer sobem).
```
A mutant (`test_mutante_start_block_ignora_resultado_da_verificacao_e_pego`)
confirms both abort tests genuinely depend on the exception
being propagated, they do not pass by accident.

**2. The byte-deviation hypothesis -- CLOSED, 0B across the 4 profiles.**

Root cause (Decision 53): `negtest`'s `baseConfig()` used
`MinVersion: tls.VersionTLS12` generically for all profiles,
while the real client (`proxy/main.go`) pins `MinVersion` per
profile (`TLS13` for pqc/hibrido-v8/hibrido-and). Fixed in
`negtest/main.go` (`minVersionForProfile`, a new map, the same
logic as the already-existing
`expectedCurve`) -- I repeated the local capture for all 4
profiles, with a real keylog, real pcap:

| Profile | Observed handshakeBytesIn | historical value cited | Δ | Observed handshakeBytesOut | historical value cited | Δ |
|---|---|---|---|---|---|---|
| Classical | 1.513 | (never cited before) | -- | 1.640 | (never cited before) | -- |
| PQC | 10.728 | (never cited before) | -- | 10.878 | (never cited before) | -- |
| Hybrid-v8 | **8.397** | 8.397 | **0** | **8.552** | 8.552 | **0** |
| Hybrid-AND | **11.902** | 11.902 | **0** | **12.177** | 12.177 | **0** |

**The hypothesis is proven: 0B of deviation on both profiles
Luciano cited with a historical value.** The raw ClientHello also
matches
exactly against `CLIENTHELLO_BASELINE` across the 4 profiles (e.g.,
hibrido-v8
1.872 observed vs. 1.872 expected). Classical/PQC never had a
historical value cited before this round -- the numbers above are
recorded as the FIRST real reference for both in v9.

**3. Tolerance derived from measured variance -- 480 real samples, 0B of variance.**

Measured with the pilot's REAL CLIENT (`SSHExecutor.run_execution`,
the exact same invocation as `campaign_client_runner.py`, via a
local shim
-- a disposable script, never committed), N=20 runs per profile,
6 client-facing connections per run = **120 samples per profile,
480 in total**:

| Profile | N samples | min (in/out) | max (in/out) | deviation |
|---|---|---|---|---|
| Classical | 120 | 1.513 / 1.640 | 1.513 / 1.640 | **0B** |
| PQC | 120 | 10.728 / 10.878 | 10.728 / 10.878 | **0B** |
| Hybrid-v8 | 120 | 8.397 / 8.552 | 8.397 / 8.552 | **0B** |
| Hybrid-AND | 120 | 11.902 / 12.177 | 11.902 / 12.177 | **0B** |

**Zero variance across ALL 480 samples, across the 4 profiles.** The
local
environment (Docker containers on the same host) is fully
deterministic for this measure.

**Possible sources of variance, separated by where they CAN differ on AWS:**

| Source | Can it differ on AWS? | Why |
|---|---|---|
| Certificate SAN (real private IP/EIP vs. loopback) | **YES** | Already measured and compensated (Decision 28/29): -14B (single-leaf-certificate profiles) or -28B (Hybrid-AND, 2 leaves) -- a FIXED, known difference, not random |
| Certificate's ASN.1 serial number (1-byte padding if the most significant byte has the high bit set) | **YES, but limited** | Varies by certificate BUILD (`make certs`), never by run -- ±2B per leaf, ±4B for Hybrid-AND (2 leaves); this is ALREADY the basis for criterion 1's `CERTIFICATE_TOLERANCE_B=4B` |
| SNI ("mtls", fixed) | **NO** | Confirmed by Decision 30: byte for byte identical regardless of the real target -- never depends on the destination's IP/DNS |
| Session tickets (`TICKETS_DISABLED`) | **NO, if the config is the same** | Always `true` in every launch of this project -- if it ever diverged, it would add `NewSessionTicket` to handshakeBytesOut (never tested here because it has always been off) |
| Client's minimum TLS version (`MinVersion`) | **NO, if the binary is the same** | The EXACT cause of the deviation closed in item 2 -- controlled by item 1's binary verification |
| TLS 1.3 random fields (32B Random, key_share) | **NO** | FIXED size by specification -- only the CONTENT is random, never the length |

**Proposed tolerance** (for Luciano's approval, NOT applied to
no existing criterion this round): **0B for `handshakeBytesOut`
across the 3 single-certificate profiles, ±4B for Hybrid-AND's
`handshakeBytesIn` (2 leaf certificates, doubling the serial
number's margin) --
and, when measured in an environment with a SAN different from
loopback (real AWS), add the FIXED, already-measured offset
(-14B/-28B) to the baseline before applying this same tolerance,
never treating that offset as "unknown variance".** Justification:
480 real local samples gave 0B of variance; the ONLY legitimate
source of variance left (serial number) is the same one criterion 1
already tolerates for individual messages. Proposal recorded, not
applied -- needs Luciano's approval before it applies to any
criterion.

**4. Readiness dossier -- a self-contained document.**

`thesis/results/v9/campaign/PILOT_READINESS.md` (new, committed) --
covers the 5 requested points (a-e): a table of the 7 criteria with
their real status (none 100% closed without AWS, by design -- the
mechanics of all of them are implemented and tested where the
measure is local), the
AWS prerequisites that are Luciano's (per-region quotas, a key
pair, a PROPOSED least-privilege IAM policy -- never created on
AWS --, a budget alert with a suggested value), a cost ceiling
(~US$1,15 with margin, anchored in v8's real measured cost) and the
exact emergency-stop command (`cleanup.py --release-eips
--force`, what it destroys and what could be left billing), 7
residual risks with mitigation or an explicit decision pending from
Luciano, and
confirmation that the runbook (apply -> PKI -> capture preflight ->
smoke gate -> 60 runs -> collection -> cleanup) fits within the
3-4h window with 3 explicit pause/decision points, always Luciano's,
never automatic.

**Tests:** 92 in total across the packages touched -- 85 in
`thesis/results/v9/campaign/tests/` (81 before + 4 new for
the binary verification), plus 7 (unchanged) in `thesis/scripts/
tests/test_profile_cert_dispatch.py`. All passing.

**Local commit** (no push), branch `v9/fase1-local`: `thesis/
results/v9/campaign/scripts/orchestrator.py` (`_local_gateway_binary_
info`, `_verify_gateway_binary`, `_verify_running_gateway_binary`,
wired into `start_block`/`dedicated_capture`, the manifest), `thesis/
results/v9/campaign/tests/test_orchestrator.py` (+4, fakes
extended for local `docker` calls), `thesis/results/v9/
integration/negtest/main.go` (`minVersionForProfile`, closes
item 2's hypothesis), `thesis/results/v9/campaign/PILOT_READINESS.md`
(new).

No item this round required an amendment to the pre-registration --
item 1 implements a mechanism ALREADY pre-registered (never changed
the design), item 2 is a fix+confirmation of an already-isolated
cause, item 3 is measurement + a proposal explicitly NOT applied,
item 4 is documentation. I continue to not authorize push nor AWS
resources. The pilot's date is left for after this report, at
Luciano's discretion.

## 55. Three corrections to Decision 54 (source of the Classical/PQC baseline, asymmetric tolerance, 480 samples from a single build) and six deliverables: PINS.json + fail-closed verification in the SSHExecutor, delivery via docker save/load (never building on the instance), the derived tolerance validated across 20 real rebuilds (0B in all), a restricted IAM policy + dry-run check, an emergency stop independent of Terraform, PILOT_READINESS.md rewritten

Response to the 3 corrections + 6 requested points. No AWS, no push,
branch `v9/fase1-local`, `v9-prereg`/`main` untouched.

**Corrections accepted, confirmed with citation/evidence:**
(i) Classical (1.640/1.513) and PQC (10.878/10.728) were ALREADY in
the pre-registration -- Decision 14 (T6), `DECISIONS.md` lines
1511-1519 and
1750-1751. Decision 54's claim "never cited before" was
wrong -- fixed, now cited in `PILOT_READINESS.md`, section b.
(ii) Decision 54's tolerance was asymmetric with no justification --
fixed by item 3 below's derived mechanism, which treats the 4
profiles and the 2 directions uniformly (no longer a special rule
just for Hybrid-AND).
(iii) The 480 samples came from a SINGLE certificate build --
fixed with 20 real rebuilds, 4 SAN variants, item 3 below.

**1. Binary and image pins -- implemented and tested.**

**Reproducibility, genuinely tested (not assumed):** the gateway
built 2x from scratch (`--no-cache`), with explicit
`-trimpath`+`GOARCH=amd64`
(added to the 3 Dockerfiles) -- the binary's sha256 is
**identical** across both builds (`a08ba8e3...`). The proxy tested
the same way, same result (`86f1ef60...`). **The Docker Image ID is
NOT
reproducible** across independent builds -- confirmed: the SAME
binary produced 2 different Image IDs (`74eb54fa...` vs
`ce797b5e...` in a first test without trimpath; `184ddeb6...` vs
`71105be1...` with trimpath) -- layer metadata varies, content
does not. This is why `PINS.json` (new, version-controlled,
`thesis/results/v9/campaign/PINS.json`) pins the BINARY's sha256
(reproducible, can be checked against a future rebuild) and the
Image ID of ONE SPECIFIC built image (only valid together with item
2's save/load delivery -- never together with a local rebuild).
It also records `go version -m` (text + the output's sha256) and
the toolchain's build metadata (`go_tag`, `go_commit`,
`and_patch_sha256`, already recorded by `mockopin-v9-toolchain`
ITSELF
in `/build_metadata.json`).

`_local_gateway_binary_info()` (SSHExecutor) now checks the
freshly-extracted sha256 against `PINS.json["images"]["gateway"]["binary_
sha256"]` -- fail-closed, raises BEFORE `_launch_gateway` runs if it
diverges. `load_pins()` never writes the file, only reads -- altering
`PINS.json` requires an explicit numbered Amendment (a `_policy`
field inside the file itself documents this).

**Tests:** `test_pin_divergente_aborta_antes_de_qualquer_execucao`
(wrong hash -- aborts, no `docker run`/proxy comes up),
`test_pin_correto_passa` (right hash -- passes, `pin_matched: true` in
the manifest), `test_campanha_oficial_com_os_pins_do_piloto_passa` (a
SECOND `SSHExecutor` instance, a profile/route outside the pilot's
grid -- `load_pins()` is a pure function of the file, it never
depends on
"being the pilot," it passes the same way).

**2. Image delivery -- docker save/load, never building on the instance.**

`SSHExecutor._deliver_image(image_key, host)`: `docker save <image>
| ssh <host> docker load`, followed by `docker image inspect --format
'{{.Id}}'` on the destination, compared against `PINS.json`.
Fail-closed,
called in `start_block` (gateway, server; proxy, client) and
`dedicated_capture` (measure, server) -- BEFORE any
verification/run.

**Each instance's architecture, confirmed in the code (no control
script --
`pki_relay.py`/`collect_artifacts.py`/`cleanup.py` --
calls `docker` anywhere):**
| Instance | Type | Architecture | Runs gateway/proxy/measure? |
|---|---|---|---|
| Control | t4g.micro | **ARM64** | **No** -- confirmed, no image reaches it |
| Server | m7i-flex.large | x86_64 | gateway + measure |
| Clients (3) | m7i-flex.large | x86_64 | proxy |

`check_capture_prerequisites` fixed to require `mockopin-v9-measure`'s
EXACT Image ID (not just its presence) -- `expected_measure_
image_id`, read from `PINS.json` by `run_capture_preflight`. Tested
(`test_imagem_measure_com_id_errado_reprova`/`..._com_id_certo_
passa`). **11 new tests in total** across items 1 and 2.

**3. Derived tolerance -- validated across 20 real rebuilds, 0B in all.**

`evaluate_criteria.expected_handshake_bytes(profile, certs_dir)`:
the MEASURED baseline (Decision 14, the table in section b above) +
(the sum of the DEPLOYED certificates' DER sizes minus the sum of
the BASELINE certificates), per direction. `CERT_FILES_BY_PROFILE`/
`BASELINE_CERT_DER_SIZES` (new) -- the DER sizes of the build that
produced the baseline, really measured on this session's real files,
confirming Decision 9 (`DECISIONS.md` lines 896-901:
server RSA 914, ML-DSA 5.647; client RSA 801, ML-DSA 5.534).

**Validation: `make certs` run 20 times**, 4 SAN variants (5
builds each) -- loopback (default), private IP (10.0.1.50), an
EIP-type public IP
(203.0.113.50), an additional DNS name -- covering the 4 profiles,
the gateway REBUILT and MEASURED for real on every rebuild (never
simulated):

| Build | Variant | Profile | Predicted (in/out) | Measured (in/out) | Deviation |
|---|---|---|---|---|---|
| 1-5 | loopback | 4 profiles + classico | exact baseline | exact baseline | **0/0** |
| 6-10 | ip_privado | 4 profiles + classico | e.g.: classico 1513/1620 | 1513/1620 | **0/0** |
| 11-15 | ip_publico_eip | 4 profiles + classico | e.g.: classico 1513/1620 | 1513/1620 | **0/0** |
| 16-20 | nome_dns | 4 profiles + classico | e.g.: classico 1513/1673 | 1513/1673 | **0/0** |

**20/20 builds, 0B of deviation in ALL of them -- no exception.**
Concrete example (build 6, classico, loopback->private IP): the
server certificate drops from 900B to 880B DER (a shorter SAN) --
predicted
`out=1620`, measured `out=1620`.

**Final rule, proposed pre-pilot, NOT applied retroactively:**
the pre-registered thresholds remain criterion 1's official gate
(0B ClientHello, ±4B Certificate, 0B the rest -- Decision 20/29/30,
untouched). `expected_handshake_bytes` enters as a DIAGNOSTIC --
implemented (`orchestrator._bytes_diagnostic_for_profile`, called
by the smoke gate): a deviation != 0 marks `bytes_diagnostic_needs_
decision=True` in the manifest, **PAUSES and asks for Luciano's
decision**,
same as the smoke gate -- it never aborts nor is silently ignored,
never
blocks `smoke_ok` on its own (tested, including a mutant).

**4. IAM -- complete action list, restricted policy, dry-run check.**

A complete table of the EC2 actions Terraform performs (plan/apply/
destroy) for `main.tf`'s resources -- `PILOT_READINESS.md`, section
e. Restricted policy rewritten: `aws:RequestedRegion` (the 3
regions)
on EVERY statement; `aws:RequestTag`/`ec2:CreateAction` on the 4
CREATE actions (they do not support `aws:ResourceTag`, which does
not exist yet);
`aws:ResourceTag` on the MODIFY/DESTROY actions (`Terminate
Instances`, `ReleaseAddress`, `DeleteKeyPair`, etc.).

`thesis/results/v9/campaign/scripts/iam_dryrun_check.py` (new): each
mutable action with `--dry-run`, per region -- authorized
(`DryRunOperation`) vs. denied (`UnauthorizedOperation`), never
really creating
anything. Actions that need a real resource (`Terminate
Instances`/`ModifyInstanceAttribute`/`ReleaseAddress`/`DeleteKeyPair`/
`RevokeSecurityGroupIngress`) are left explicitly "not tested" with
no
real ID passed -- never faked as PASS. **7 tests, fully mocked --
this process never ran the script against AWS, only wrote and
tested it.** Luciano runs it for real.

**5. State-independent emergency stop -- `emergency_stop.py`, new.**

By the `Project=mockopin-pqc-v9-piloto` tag, directly via the API,
across the 3
regions -- each destructive action checks the tag (via a filtered
`describe-*`) IMMEDIATELY before acting, never on a loose ID.
Order: instances (terminate, wait up to 2min) -> EIPs (disassociate,
release) -> security groups (only after the instances) -> key pairs.
Dry mode (default, without `--execute`) never calls any mutable
action
-- explicitly tested. **6 tests, fully mocked.**

**Worst-case cost, with only the auto-shutdown (no additional
action):** compute capped at ~US$1,575 (4h clients/server +
5h control, confirmed `terminate` really ends the
compute); EBS disappears along with it (delete_on_termination is the
default, never overridden). **The 5 EIPs are NEVER released by the
auto-shutdown**
(Decision 45, reconfirmed) -- US$0,025/hour INDEFINITELY, ≈US$18
over a forgotten month. Exactly the scenario layer 2
(`emergency_stop.py`) covers even without Terraform.

**6. `PILOT_READINESS.md` rewritten** with the 4 cited baselines
(section b), items 1-5 above (sections c-f), risk 1/2 marked
RESOLVED, risk 6/7 updated with the real mechanism, the budget
alert reclassified as a billing-delayed notification
(never an automatic brake -- the suggestion revised to US$3), and a
final short list of what is still pending on Luciano's side.

**Tests:** 115 in total across the packages touched -- 108 in
`thesis/results/v9/campaign/tests/` (91 before + 4 PINS/image
delivery + 2 wrong/right Image ID + 7 IAM dry-run + 6 emergency stop +
4 bytes diagnostic -- some cover more than one point, the exact
count is in the test names), plus 7 (unchanged) in
`thesis/scripts/tests/`. All passing.

**Local commit** (no push), branch `v9/fase1-local`: `thesis/
results/v9/campaign/PINS.json` (new), `thesis/results/v9/campaign/
scripts/orchestrator.py` (`load_pins`, `_deliver_image`, `_bytes_
diagnostic_for_profile`, wiring), `thesis/results/v9/campaign/
scripts/preflight.py` (Image ID in `check_capture_prerequisites`),
`thesis/results/v9/campaign/scripts/iam_dryrun_check.py` (new),
`thesis/results/v9/campaign/scripts/emergency_stop.py` (new),
`thesis/results/v9/integration/evaluate_criteria.py` (`expected_
handshake_bytes`), `thesis/results/v9/integration/{gateway,proxy,
measure}/Dockerfile` (`-trimpath`+`GOARCH=amd64`), `thesis/results/
v9/campaign/PILOT_READINESS.md` (rewritten), plus the 5 new/extended
test files.

No item required an amendment to the pre-registration -- items 1-2
implement an already pre-registered mechanism + an additive one
(never changing the design), item 3 is a diagnostic explicitly NOT
applied to the official gate, items 4-5 are new documentation/
tooling, never touching the 7 criteria. I continue to not authorize
push nor AWS resources. The pilot's date is left for after this
report.

## 56. Three reduced points: PINS.json printed + 2 answers about the build machine and the measure pin; the SAN technique (real IP + preserved ::1) zeroes the deviation against the BASELINE (not just against the predicted value) across 20 real rebuilds, 80/80 combinations; a 15-minute infrastructure rehearsal procedure (never executed)

No AWS, no push, branch `v9/fase1-local`, `v9-prereg`/`main`
untouched. Local commit.

**1. PINS.json and the 2 answers.** Content printed in full in the
chat (not repeated here). **(a)** The orchestrator and the build run
on the operator's machine (this environment today; on the pilot's
day, Luciano's machine) -- NEVER on an AWS instance (confirmed,
Decision 55, item
2). The binary's hash should reproduce there too (the tested
reproducibility only proves the build is deterministic INSIDE
containers
with a base/toolchain pinned by digest/tag -- the host's
architecture (Windows/Mac/Linux) never enters the final binary,
GOOS/GOARCH are
explicitly fixed), but this has NEVER been tested on a second
real physical machine -- honestly recorded, not assumed. **(b)**
For `measure`, only the Image ID is pinned (`binary_sha256`/`go_version_m`
stay `null` in PINS.json) -- the image only packages capture
tooling (tcpdump/tshark) plus internal copies of gateway/proxy/bench
used
ONLY by T6's standalone measurement harness, never by the real
pilot,
so there is no single, dedicated binary that makes sense to hash.

**2. SAN and the Certificate gate -- a feasible technique, validated against the real BASELINE.**

Finding: `make certs SERVER_IPS="<real IP>,::1"` (keeping the COMMA
and
`::1`, only swapping the IPv4 VALUE) preserves the SAME SAN entry
count/type
as the baseline (`127.0.0.1,::1`) -- an IPv4
entry always takes 4 bytes, an IPv6 one always 16 bytes in ASN.1 DER,
REGARDLESS of the value. Confirmed by running `make certs` 20 times
(10
private-style IPs, 10 public-EIP-style, a different value on each
build), measuring each certificate's real DER against
`BASELINE_CERT_DER_SIZES`:

```
all_zero: True, n_builds: 20, n_rows: 80, nonzero rows: 0
```

**80/80 combinations (20 builds x 4 profiles), ZERO delta against
the BASELINE -- not just against its own prediction -- in both
directions.**

**Alternative tried and discarded:** DNS-name padding (adding a
name of calculated length to compensate for the `::1` that would be
removed). Tested with 15, 17, and 18 characters -- deviations
of -2B, +1B, and +3B respectively (per server leaf; doubled on
Hybrid-AND) -- it does NOT scale linearly with the name's length
(a boundary effect in the extension-length ASN.1 encoding, never
calibrated to an exact 0B in 3 attempts). The IP+`::1` technique
is simpler, exact by construction (does not depend on calibrating
any length) and provenly 0B -- preferred, without reservation.

**No Amendment needed** -- the technique is feasible (confirmed, not
the opposite) and changes no code in this project, only the VALUE of
`SERVER_IPS` passed to `make certs` on the pilot's day (an
operational choice, documented in `PILOT_READINESS.md`, section d).

**3. Infrastructure rehearsal procedure -- 15 minutes, never executed.**

`thesis/results/v9/campaign/INFRA_REHEARSAL.md` (new): uses the SAME
credentials/profile as v8 (`mockopin-pqc`). 6 steps -- a real
`terraform
apply` with `self_terminate_hours=1` (reduced just for the
rehearsal);
checking the 5 instances via `describe-instances` per region;
`docker save`/`load` with the Image ID checked against `PINS.json`
(no `docker run`, no mTLS connection, no profile activated);
`emergency_stop.py` in dry mode (confirms empty action lists);
`emergency_stop.py --execute` on the rehearsal's own resources;
a final check (12 `describe-*` calls, 4 types x 3 regions,
all empty) + `terraform destroy`. Each step has an exact command,
expected output, and an explicit abort criterion. Estimated cost:
≈US$0,14 (15-20min real), ≈US$0,28 at double the time, ≈US$0,56 if
the
1h self_terminate fires due to some error in the manual cleanup.

**Tests:** no change -- no new code this round (item 2 is
just an operational discovery, item 3 is documentation). 108 in
`thesis/results/v9/campaign/tests/` + 7 in `thesis/scripts/tests/`,
unchanged, all passing.

**Local commit** (no push): `thesis/results/v9/campaign/
PILOT_READINESS.md` (section d gains item 2's finding),
`thesis/results/v9/campaign/INFRA_REHEARSAL.md` (new).

No item required an amendment to the pre-registration. I continue
to not authorize push nor AWS resources.

## 57. Rehearsal-procedure fix: linear order (0-8), terraform plan with a derived count of 28 resources, Docker readiness + port checked against the SG, negtest delivered to the client (never pinned, with a reason), a real handshake script tested on loopback (4/4 PASS), a real finding -- no aws_key_pair had a tag (not even in v8) -- fixed in main.tf, cleanup.py becomes the main teardown (more capable than real v8), emergency_stop only as a fallback

No AWS, no push, branch `v9/fase1-local`. Local commit.

**1-3 (order/count/readiness):** `INFRA_REHEARSAL.md` rewritten in
strictly linear order (0 to 8, no "numbered X but runs between Y and
Z"). Step 1 gains a `terraform plan` with the resource count
DERIVED from reading `main.tf`/`modules/campaign_instance/main.tf`
line
by line (never assumed): `tls_private_key`(1) + `aws_key_pair`(4) +
`aws_security_group`(5) + `ingress.ssh`(5) + `ingress.gateway`(3,
server only) + `aws_instance`(5) + `aws_eip`(5) = **28**. Step 2
gains a
wait for `docker info` ready across the 5 instances (20-attempt
limit) and checks the port used (443, gateway; 22, SSH) against
the real `aws_vpc_security_group_ingress_rule` rules in `main.tf`.

**4 (delivery + negtest pin):** Step 3 delivers `mockopin-v9-negtest`
to the L0 client (`docker save`/`load`), in addition to the gateway
to the server.
**`negtest` is NEVER pinned in PINS.json, for a confirmed reason:**
a grep
in `orchestrator.py`/`preflight.py` finds NO reference to
`negtest` at all -- no real pilot code uses it, only manual
validation/
this rehearsal. Pinning an artifact that no production path loads
would protect nothing.

**5 (real handshake script, tested before delivery):**
`thesis/results/v9/campaign/scripts/rehearsal_handshake.sh` (new) --
for real, for each of the 4 profiles: removes the previous gateway,
brings it up with the right `CRYPTO_PROFILE`, waits for it to be
ready (30 attempts),
dials with `negtest -scenario matrix`, extracts the "connection OK"
line
with `grep` (never `tail -1`), compares `handshakeBytesIn/Out`
against
`BASELINE_HANDSHAKE_BYTES` (Decision 14). **Tested locally on
loopback before being delivered -- actually run this session:**
```
RESULTADO FINAL: PASS -- 4/4 perfis, delta 0B nos dois sentidos
```
The gateway image HAS a shell (`sh`, confirmed by really running
`docker run --entrypoint sh mockopin-v9-gateway -c "echo shell-ok"`)
-- the step that reads the certificate via `cat` inside the
container remains valid, no switch to `docker create`+`cp`
was needed.

**6 (cleanup.py vs. v8, main teardown swapped):** Compared
line by line against real v8's `v8/campaign/scripts/campaign_down.sh`.
**The 5 verification checks are structurally IDENTICAL** (the same
TYPE of per-resource filter -- tag for instances/volumes/EIPs,
NAME
pattern for security groups/key pairs -- confirmed in both
files, only the constant changed: `mockopin-pqc-campaign*` ->
`mockopin-pqc-v9-piloto*`). **But there is a real logic change:**
`cleanup.py` has 2 capabilities v8 NEVER had -- auto-shutdown
drift detection BEFORE the destroy, and ACTIVE release of
orphaned EIPs (`--release-eips`); real v8 only FAILS and requires
manual intervention if an EIP is left over, never releases it on
its own.
**This is why the procedure's main teardown now is `cleanup.py
--release-eips --force`** (more capable, tested against v8's
proven pattern on the 5 central checks), with `emergency_stop.py
--execute` ONLY as a fallback if `cleanup.py` reports `all_clean:
false` -- `emergency_stop.py` in dry mode keeps running BEFORE
any teardown, as a diagnostic.

**Real finding along the way (fixed):** NO `aws_key_pair` had
`tags` -- not here, not in the original v8 (confirmed in both
`main.tf` files). This made `emergency_stop.py` (which filters by
tag)
never find any key pair, even though the 4 really existed --
`cleanup.py` never had this problem (it uses a NAME pattern for key
pairs, same as v8, never tag). Fixed in `thesis/results/v9/
terraform/main.tf`: additive tags on the 4 `aws_key_pair` resources
(never changing
`key_name`/`public_key`) -- `terraform validate` confirms the syntax
(no AWS call).

**Tests:** no change to testable Python code beyond what already
passed -- 108 in `thesis/results/v9/campaign/tests/` + 7 in
`thesis/scripts/tests/`, unchanged, all passing. The new
`rehearsal_handshake.sh` is a shell script, tested by a real
run (shown above), not by pytest.

**Local commit** (no push): `thesis/results/v9/campaign/
INFRA_REHEARSAL.md` (rewritten), `thesis/results/v9/campaign/
scripts/rehearsal_handshake.sh` (new), `thesis/results/v9/terraform/
main.tf` (additive tags on the key pairs).

No item required an amendment to the pre-registration -- the
procedure fix is documentation/a validation script, the key-pair tag
is additive (never changes any resource's name/key/behavior), the
main-teardown swap is an operational choice based on evidence
(cleanup.py being more capable than v8), never a criterion change.
I continue to not authorize push nor AWS resources.

## 58. v9 vs. v8 infrastructure comparison (a read-only round, no code change) reveals a real finding -- `start_block` never delivered `mockopin-pqc-signer` to the client (finding 19), nor `thesis/scripts/*.py`/`mock-service-os/certs`/`certs/generated` to any instance (the same bug class v8 had already fixed); fixed via the already-existing mechanism (PINS.json + `_deliver_image`, a new `deliver_source.py` via a 2-hop relay); the pure TCP probe restored (finding 18); a CPU/steal sampler recorded as a known gap before the official campaign (finding 10, not implemented); cleanup.py already redacted AWS errors (no gap); an additional, unfixed finding -- the server/clients' SG only accepts SSH from the control's EIP, never from the operator, so `orchestrator.py` only really works when run from the control

No AWS, no push, branch `v9/fase1-local`. Local commit.

**Context:** a purely read-only v9-vs-v8 comparison (changing
nothing, "just the diff and the classification") found, along the
way, a real
finding (19): `start_block` calls `of.start_pqc_signer_service()` on
the remote client, for ALL 4 profiles, with NO
`V9_HARNESS` branch at all (unlike `start_tls_kem_proxy`, which has
one) --
and no code in this package ever delivered `mockopin-pqc-signer`
to the client. The same bug class real v8 found and fixed
in `deliver_images.sh` (`CLIENT_IMAGES` never reached the client,
"this would have failed the very FIRST profile switch / first
execution of the real campaign"). This round's request: a table of
the entire remote path's dependencies, a fix via the already-existing
mechanism, pinning the new images via an amendment, tests that catch
the
regression, and three related items (findings 18/10, error
redaction in cleanup.py).

**1 (dependency table + fix for finding 19):** reading
`orchestrator.py`/`opin_flow.py`/`cli.py` line by line (never
assumed), `SSHExecutor`'s remote path depends on:

| Remote command | Image/file/certificate | Delivered BEFORE this round | Pin/verification |
|---|---|---|---|
| `_launch_gateway` (`docker run ... mockopin-v9-gateway`) | `gateway` image | `_deliver_image` (save/load) | PINS.json, Image ID + binary sha256 |
| `_launch_gateway` (`-v .../mock-service-os/certs:/real-certs:ro`) | `mock-service-os/certs` | **NEVER delivered** -- the `$(pwd)/../../...` path only made sense in the local shim | none -- fixed this round |
| `of.start_tls_kem_proxy` (`docker run ... mockopin-v9-proxy`) | `proxy` image | `_deliver_image` (save/load) | PINS.json, Image ID |
| `of.start_tls_kem_proxy` (V9_HARNESS, `-v V9_CERTS_DIR:/certs:ro`) | `thesis/results/v9/certs/generated` | **NEVER delivered** | none -- fixed this round |
| `of.start_pqc_signer_service` (`docker run ... mockopin-pqc-signer`) | `pqc-signer` image | **NEVER delivered -- finding 19** | none before; PINS.json + `_deliver_image` now |
| `python3 campaign_client_runner.py`/`opin_flow.py` (import) | `thesis/scripts/*.py` (+`requirements.txt`) | **NEVER delivered** | none -- fixed this round |
| `dedicated_capture` (`docker run ... mockopin-v9-measure`) | `measure` image | `_deliver_image` (save/load) | PINS.json, Image ID |
| `rehearsal_handshake.sh` (outside the orchestrator) | `negtest` image | save/load, only in the rehearsal | no pin, for the reason recorded in Decision 57 (no production code uses it) |
| none (local-only, T6) | `bench`/`interop`/`certs`(Go)/`gateway-check` | n/a | outside the remote path's scope -- only `run_t6.sh`/local validation |
| none (it is an ENDPOINT, not an artifact) | `/jwks` | served by the `auth`/`mockapi` containers (docker-compose, `insurance-server-lambdas`) | a SEPARATE gap, already documented in `start_block`'s own docstring ("needs a v9-aware version... this does NOT exist yet") -- outside this round's request |

Fixed via the already-existing mechanism (no new mechanism): `pqc-signer`
pinned in `PINS.json` (Image ID only, no dedicated binary to hash --
`server.mjs`, Node, the same pattern as `measure`) and `start_block`
now
calls `self._deliver_image("pqc-signer", self._client_ip(route))`
before `python3 -c "...start_pqc_signer_service..."`, the same
relative
position (after the proxy, before the trigger). `thesis/scripts/*.py`/
`mock-service-os/certs`/`thesis/results/v9/certs/generated` gain a
new script, `deliver_source.py` (`thesis/results/v9/campaign/
scripts/`), the same 2-hop relay `pki_relay.py` already uses
(operator -> control -> destination, the campaign key on the second hop)
-- the reason for the relay, not an aesthetic choice: the server's
and each client's Security Group only accepts SSH from the control's
OWN EIP
(`main.tf`, `ssh_ingress_cidrs = {"control": ...}`), never the
operator's. `COMMON_FILES` (scripts + mock-service-os/certs) goes to
the server and every client; `CLIENT_ONLY_FILES` (certs/generated)
only to the
clients (confirmed by reading `opin_flow.py`: `V9_CERTS_DIR` is only
mounted
inside `start_tls_kem_proxy`, which only runs on the client). A local
tarball via `tarfile` (not depending on a `tar` in the operator's
PATH),
~200KB (common) / ~270KB (client), measured this session against the
real repo.

**Additional finding, recorded, NOT fixed this round:** the same
reading of the Security Group confirms the OPERATOR never reaches
the server/clients directly on a real AWS -- only the control
reaches them.
`orchestrator.py` (SSHExecutor), therefore, only really works when
run from inside the CONTROL (the same real pattern as `campaign_run.py`/
`campaign_run.service` in v8), never from the operator's laptop.
`deliver_source.py` delivers the files over the right path, but WHO
triggers `orchestrator.py --mode ssh` still needs to be running
from inside the control -- this does not change this round (the
request was
image/file/certificate delivery, not where the process runs).
Recorded here and in `INFRA_REHEARSAL.md` (Step 3) so it never stays
hidden.

**Related fix:** `_launch_gateway` mounted `/real-certs` from
`$(pwd)/../../mock-service-os/certs` -- a path that only makes
sense in the LOCAL validation via `local_shim_bridge_join=True` (where
`cwd` is forced to the real repository by the shim); on a real
remote instance, `$(pwd)` resolves to the SSH login directory
(`/home/ec2-user`), never to the repo's layout. Fixed to
`~/mock-service-os/certs` for the real remote case (where `deliver_
source.py` now really delivers, and where `opin_flow.py`'s own
`CERTS_DIR = BASE_DIR/"mock-service-os"/"certs"`, with `BASE_DIR =
SCRIPTS_DIR.parent.parent`, already assumed with no code change at
all)
-- the old path remains, unchanged, only when
`local_shim_bridge_join=True`.

**Tests (finding 19):** `_assert_every_used_image_was_delivered_first`
-- a "simulated executor that logs commands and images," generic,
checks that every image with a USE marker (`docker run
-d --name v9-mtls`/`--entrypoint tshark mockopin-v9-measure`/
`start_tls_kem_proxy`/`start_pqc_signer_service`) had a delivery
(`docker save <image> | ssh ... docker load`) at an index BEFORE it
in the same call list.
`test_toda_imagem_usada_no_caminho_remoto_foi_entregue_antes`
exercises
`dedicated_capture` (which calls `start_block` internally) and checks
the 4 real images; `test_mutante_pqc_signer_nao_entregue_e_pego`
reproduces the ORIGINAL bug (`_deliver_image` skipping "pqc-signer")
and
confirms the test above fails with that mutation -- this is the test
that would have caught finding 19 had it existed before this round.

**2 (finding 18, pure TCP probe restored):** the (existing)
`readiness_probe` already runs from inside the CLIENT and already
proves real
reachability (a complete TLS handshake does not happen without TCP
working) --
but only AFTER `start_block` has already delivered the image,
verified the
binary, and brought up 3 containers, an expensive cost to discover a
wrong SG. The real v8 `preflight_tcp.py` did this SAME check (pure
TCP,
`/dev/tcp`, triggered from the CLIENT -- never from the control, for
a literal reason v8 already recorded: "checking from control directly
would test a different network path") once per scenario, BEFORE
anything expensive. Restored as `SSHExecutor._tcp_preflight(route)`,
called as the FIRST line of `start_block` -- once per ROUTE
(not per block/profile, memoized in `self._tcp_preflight_done`),
fail-closed (aborts BEFORE any image delivery if the client
cannot reach `{gateway_ip}:443` via pure TCP). 4 new tests
(`test_tcp_preflight_roda_do_cliente_antes_de_qualquer_entrega`/
`test_tcp_preflight_aborta_antes_de_qualquer_entrega_se_sem_alcance`/
`test_tcp_preflight_roda_so_uma_vez_por_rota`).

**3 (AWS error redaction in cleanup.py):** checked, this is not a
gap -- `cli.run_terraform`/`cli.run_aws`/`cli.run_aws_json` (the
ONLY boundary in this package for any real terraform/aws
command) already call `redact_aws_errors.redact` (reused
directly from v8's real file, never duplicated) on `stdout`/`stderr`
before returning or raising -- `cleanup.py` never needed its own
call because all output passing through it already comes redacted
at the boundary. No code change made here -- documented in the
`INFRA_REHEARSAL.md`, Step 8, so it does not look like an ignored
gap.

**4 (finding 10, CPU/steal sampler -- known gap, NOT
implemented):** real v8 monitored `cpu_mem_steal` (shared-cloud
neighbor noise) throughout the entire real timed window
(`_PeriodicSampler`/`_cpu_mem_sampler_start_cmd`/
`_steal_pct_from_cpu_jsonl`, used in `compute_window_health`) -- v9's
pilot (60 runs, never the source of the thesis's official numbers)
has nothing equivalent, by design (the pilot tests
feasibility, not publishable statistical collection). **Recorded here
as a known gap that needs to be resolved BEFORE a real official
campaign** (not before the pilot) -- not implemented this round,
by explicit request.

**5 (INFRA_REHEARSAL.md):** rewritten with 11 steps (0-10, linear
order preserved) -- a new Step 3 (`deliver_source.py`, with the
honest section about the SG only accepting SSH from the control),
Step 4 now delivers
the 4 real images (gateway/proxy/pqc-signer/negtest, no longer 2)
with
a per-image/region timing table to fill in during the real
rehearsal, a new Step 5
(`orchestrator.py --exercise-start-stop`, 1 profile at L0, not
counted in the 60/12 -- confirms the 3 real containers coming
up/down
via SSHExecutor's REAL PATH, distinct from Step 6's direct
gateway+negtest handshake). Estimated cost adjusted to ~25 min
(~US$0,17).

**Tests:** 123 in `thesis/results/v9/campaign/tests/` (108 before
this round + 15 new: 9 in `test_orchestrator.py` -- image
dependency/mutant, 3 for the TCP probe, 2 for the `/real-certs` path,
2 for
`exercise_start_stop` -- + 6 in `test_deliver_source.py`, new),
all passing.

**Local commit** (no push): `thesis/results/v9/campaign/PINS.json`
(the `pqc-signer` entry), `thesis/results/v9/campaign/scripts/
orchestrator.py` (pqc-signer delivery, `_tcp_preflight`, fix to the
`/real-certs` mount, `exercise_start_stop`),
`thesis/results/v9/campaign/scripts/deliver_source.py` (new),
`thesis/results/v9/campaign/tests/test_orchestrator.py` (15 new tests
in total across both files), `thesis/results/v9/campaign/
tests/test_deliver_source.py` (new), `thesis/results/v9/campaign/
INFRA_REHEARSAL.md` (rewritten).

Every fix this round is additive (no new delivery mechanism, just
the same path -- PINS.json + `_deliver_image`, a 2-hop
relay -- applied to the dependencies that were missing) -- none
requires
an amendment to the pre-registration. The SG/where-the-orchestrator-
runs finding remains recorded as a real, unresolved risk, for
Luciano's decision. I continue to not authorize push nor AWS
resources.

## 59. Decision 58's Security Group finding (the operator never reaches the server/clients, only the control) decided to be BLOCKING, not future work -- resolved with v8's real model: image delivery restored via 2 real hops (docker save into a FILE on the operator, scp to the control with a disk-space check, docker load on the host via ssh from the control, never local docker on the control), orchestrator.py really delivered to the control and run from there, the campaign SSH key delivered to the control (an additional gap found and fixed), INFRA_REHEARSAL.md rewritten with every step labeled by machine

No AWS, no push, branch `v9/fase1-local`. Local commit.

**Context:** Decision 58 recorded, as an additional, unfixed finding,
that the server's/clients' Security Group only accepts SSH
from the control's OWN EIP (`main.tf`, `ssh_ingress_cidrs =
{"control": ...}`) -- the operator never reaches these hosts
directly
on real AWS. Luciano decided this is NOT future work: it blocks
the pilot, and it is resolved this round with v8's real model
(`campaign_run.py` runs from the control; `deliver_images.sh` does
`docker
save` into a file, not a pipe).

**Contradictions found and fixed, by reading the code directly
(never assumed):**
- Decision 56, answer (a): "the orchestrator and the build run on
  the operator's machine... NEVER on an AWS instance" -- WRONG for
  "the orchestrator." Only the BUILD stays on the operator; the real
  execution
  of `SSHExecutor` (which talks to the server/clients) only works
  from inside the CONTROL.
- `PILOT_READINESS.md`: "control... never invokes docker" -- the
  STATEMENT itself was correct (and remains correct), but the list
  of scripts that "run on the control" was wrong -- `pki_relay.py`/
  `collect_artifacts.py`/`cleanup.py` run on the OPERATOR (talking to
  the
  control via SSH, or not even that); only `orchestrator.py` now
  really runs THERE. Fixed ("Each instance's architecture" section).

**1. A single execution-model table** (explicit request) -- where
each step runs, SSH path, Docker dependency:

| Step | Where it runs | SSH path | Depends on Docker on the executing machine? |
|---|---|---|---|
| Building the images (`docker build`) | Operator | n/a (local) | Yes |
| `docker save` (produces `.tar`) | Operator (`deliver_images.py`) | n/a (local) | Yes |
| Sending the `.tar` to the control | Operator -> Control (`deliver_images.py`) | scp/ssh operator->control (allowed) | No |
| `docker load` on the hosts | Control -> Host (`orchestrator._deliver_image`, 2nd hop) | scp of the local `.tar` on the control -> host; ssh host "docker load" (allowed) | No on the control; yes on the HOST |
| Image ID check | Control (reads via ssh host "docker image inspect", compares in Python) | ssh control->host | No (string comparison) |
| `pki_relay.py` (certs + `deliver_campaign_key`, new) | Operator -> Control -> Host (2 hops) | 1st: operator->control (operator key); 2nd: control->host (campaign key) | No |
| `deliver_source.py` (server/client) | Operator -> Control -> Host (2 hops) | same | No |
| `deliver_source.py --to-control` (new) | Operator -> Control (1 hop) | operator->control | No |
| `deliver_images.py` (new) | Operator -> Control (1 hop) | operator->control (+LOCAL docker on the operator) | Yes (on the operator) |
| `orchestrator.py` (real SSHExecutor) | **CONTROL** (delivered by `deliver_to_control`, invoked via `ssh control "python3 orchestrator.py ..."`) | control->host (start_block/stop_block/run_execution/etc) | No -- never calls docker locally (tested) |
| `dedicated_capture` | Control (inside the same `orchestrator.py` process) | control->host (tcpdump/tshark run on the HOST via ssh) | No on the control; yes on the host |
| `collect_artifacts.py` | Operator (pulls directly from the control) | operator->control | No |
| `cleanup.py` | Operator | No SSH -- only the direct AWS API + local terraform | No |
| `emergency_stop.py`/`iam_dryrun_check.py` | Operator | No SSH -- only the AWS API | No |

**2. Image delivery model restored (real v8), 2 hops:**
`deliver_images.py` (new) runs on the OPERATOR -- `docker save <image>
> <image>.tar`, sha256, a disk-space check on the CONTROL
(a real `df` -- a 30GB `gp3` volume, confirmed in `main.tf`, huge
margin for the ~140MB total measured this session: gateway ~10MB,
proxy
~9MB, pqc-signer ~59MB, measure ~58MB), scp to the control
(`~/images/`), `sha256sum -c` there. For the gateway, it also
extracts the
binary (`docker create`+`cp`) and checks its sha256 against
PINS.json
HERE (never on the control -- reproducing exactly Decision 54's
`_local_gateway_
binary_info`, just now on the right machine).
`orchestrator.SSHExecutor._deliver_image`/`_verify_gateway_binary`
rewritten: never again `docker save | ssh ... docker load` (which
required
Docker on the control); now only `Path.is_file()` (a LOCAL read of
what
`deliver_images.py` has already staged) + scp/ssh to the HOST --
fail-closed if
the `.tar`/binary is not staged ("run deliver_images.py
first").

**3. `orchestrator.py` delivered to the control, and that is where it runs from:**
`deliver_source.deliver_to_control()` (new) -- a SINGLE hop
(operator
-> control, never relayed further): `orchestrator.py`/
`cli.py`/`preflight.py`/`rehearsal_handshake.sh`/`PINS.json`/
`evaluate_criteria.py` + `inventory.json` (generated by `terraform
output`, copied separately -- never a repository file).

**Additional finding, fixed:** `pki_relay.py`/`deliver_source.
relay_and_extract`/`orchestrator.py` ALL assumed `~/.ssh/
campaign_key` was already present on the control for the second hop
-- no script ever delivered it. `pki_relay.deliver_campaign_key()` (new)
closes the gap -- the same real pattern as v8's `campaign_up.sh`, a
SINGLE
hop, chmod 600, a local temporary file always removed (`with
TemporaryDirectory`), content never printed anywhere.

**4. `INFRA_REHEARSAL.md` rewritten** -- 14 steps (0-13), EVERY step
labeled **[OPERATOR]** or **[CONTROL]**, checked one by one against
`main.tf`'s real `ssh_ingress_cidrs`/`gateway_ingress_cidrs` (a table
in Step 1). A new Step 3 (campaign-key delivery). Step 8
(`--exercise-start-stop`) and Step 9 (`rehearsal_handshake.sh`) now
triggered from inside the CONTROL, never from the operator's
laptop --
`negtest` (not pinned, reason already recorded in Decision 57)
delivered
via an equivalent manual 2nd hop, documented in full in the
step itself.

**5. Tests:** `_assert_every_used_image_was_delivered_first`
updated for the new delivery marker (`"<image>.tar ec2-user@"`,
no longer `"docker save <image>"`). New ones, proving the delivery
via the staged `.tar` is the ONLY path: `test_deliver_image_nunca_
invoca_docker_localmente` (no `argv[0]=="docker"` in start_block/
dedicated_capture), `test_deliver_image_nunca_faz_docker_save_pipe_ssh`
(reproduces and forbids the old pattern), `test_deliver_image_falha_alto_
se_tar_nao_esta_estagiado` (fail-closed, zero scp/ssh calls if the
`.tar` is missing). Plus: `test_deliver_images.py` (6, new, binary
extraction + pin check + space check + 1-hop relay),
`test_deliver_to_control_*` (4, new, in `test_deliver_source.py`),
`test_deliver_campaign_key_*` (3, new, in `test_pki_relay.py`).

**Tests:** 139 in `thesis/results/v9/campaign/tests/` (123 before
this round + 16 new), all passing.

**Local commit** (no push): `thesis/results/v9/campaign/scripts/
orchestrator.py` (`_deliver_image`/`_verify_gateway_binary`
rewritten, `_local_gateway_binary_info` removed),
`thesis/results/v9/campaign/scripts/deliver_images.py` (new),
`thesis/results/v9/campaign/scripts/deliver_source.py`
(`CONTROL_FILES`/`deliver_to_control`), `thesis/results/v9/campaign/
scripts/pki_relay.py` (`deliver_campaign_key`), `thesis/results/v9/
campaign/tests/{test_orchestrator.py, test_deliver_images.py (new),
test_deliver_source.py, test_pki_relay.py}`, `thesis/results/v9/
campaign/INFRA_REHEARSAL.md` (rewritten), `thesis/results/v9/
campaign/PILOT_READINESS.md` (fix to Decision 56(a) + an
architecture table).

No fix this round changes any pre-registered criterion -- it is a
fix to a real operational blocker (image/code/key delivery), never a
change to the pilot's design. I continue to not authorize push nor
AWS resources.

## 60. Five small fixes to Decision 59's procedure/scripts, plus 1 additional finding of the same class: inventory.json generated and verified right after the apply (no longer duplicated in Step 5); the handshake dials the SAME address the real route uses (L0 is colocated, dials the server's PRIVATE IP, not the EIP -- a real finding, it was wrong); the Docker-readiness loop fails loudly, naming the host at fault; image delivery (2nd hop) now measures and reports time/size/Image ID per host, with an abort criterion for slowness (>10min); a new step checks orchestrator.py's python3/dependencies on the control before the remote exercise; additional finding -- negtest's 2nd-hop addresses and the manual docker ps checks were also hardcoded, the same error class

No AWS, no push, branch `v9/fase1-local`. Local commit.

**Context:** Decision 59 was accepted on the execution table/model;
five small adjustments requested in the procedure and the scripts
it calls, plus an additional finding if I found "one more similar
divergence."

**1 (inventory.json moved earlier and verified):** the procedure's
Step 2
now generates `/tmp/inventory.json` right after `describe-instances`
(no longer inside Step 5) -- with a real assertion checking that
the format matches what the 3 scripts read: `inventory["server"]
["public_ip"/"private_ip"]`, `inventory["clients"][route]["public_ip"
/"private_ip"/"colocated"]`, `inventory["control"]["public_ip"]`.
Confirmed by reading `deliver_source.py`/`pki_relay.py`/`orchestrator.py`
line by line: all 3 expect the ALREADY-UNWRAPPED dict (`raw["value"]`
extracted before saving) -- `terraform output -json <name>`, for a
NAMED output, always wraps it in `{"sensitive":..., "value":...}`.
Variables (`$CONTROL_IP`/`$SERVER_IP`/`$L0_IP`/`$L219_IP`/`$L325_IP`)
exported once, reused by the rest of the procedure -- no address
typed by hand from Step 2 onward.

**2 (real finding -- the handshake was dialing the wrong address):**
the earlier procedure set `GATEWAY_HOST` to the server's EIP,
unconditionally
-- but `outputs.tf` confirms L0 is `colocated: true` (same AZ ID
as the server), and `orchestrator._server_gateway_ip` dials the
server's PRIVATE IP
for a co-located client, never the EIP (Decision 27 item
1). Fixed: Step 10 now computes `GATEWAY_HOST_L0` ON THE
CONTROL ITSELF, reading the local copy of `inventory.json`
(delivered in Step
6) and reproducing the SAME `_server_gateway_ip` logic
(`private_ip`
if `colocated`, else `public_ip`) -- no longer a fixed value.

**3 (Docker readiness fails loudly):** Step 4's loop, which runs
FROM
THE CONTROL to the server/clients, now accumulates the hosts that
never
got ready (`FAILED="$FAILED $IP"`) and, if the list is not
empty, prints the message with the addresses and exits with `exit
1` --
before, the loop just silently moved on.

**4 (time/Image ID per delivery + abort criterion):**
`SSHExecutor._deliver_image` (orchestrator.py) now measures the
real time for the 2nd hop (`time.monotonic()`, scp+load+inspect) and
records
`elapsed_seconds`/`tar_bytes`/`slow` (`slow` = above
`DELIVERY_SLOW_THRESHOLD_SECONDS = 600`, just a REPORTING threshold
-- it
never aborts on its own) in `image_delivery_verifications`,
alongside the already-compared Image ID. The procedure's Step 9 now
prints
this listing per image/host and documents the abort criterion
("any delivery with elapsed_seconds > 600").

**5 (new step -- orchestrator.py's dependencies on the control):**
found by reading `cli.py`/`preflight.py`/`evaluate_criteria.py` line
by line: none imports a third-party package, only the standard
library
-- and all 3 are imported at the TOP of `orchestrator.py`, outside
any function, so `python3 orchestrator.py --help` alone already
proves the entire import chain (if any failed, `--help`
would never print anything). A new Step 8, before the remote
exercise:
`python3 --version` + `python3 orchestrator.py --help` on the
CONTROL. Since there is no pip package required, the only real
cause of
failure would be `python3` missing/broken on Amazon Linux 2023 ARM64
--
`install_common_packages.sh` already installs `python3-pip` (pulls
`python3`
as a dependency) on every instance, control included; if it is
missing
anyway, the procedure documents `sudo dnf install -y python3`, never
`pip install` (there is no third-party dependency to install).

**Additional finding (request: "if you find one more similar
divergence"):** while fixing item 2, I found the SAME error class in
the `negtest` delivery's manual 2nd hop (Step 10) and in
Step 9's manual `docker ps` checks -- both had the server/client
addresses HARDCODED in the procedure's text, instead of read from
the inventory. Fixed together: `negtest`'s 2nd hop now computes
`SERVER_IP`/`L0_IP`/`GATEWAY_HOST_L0` INSIDE the block that runs on
the control (the same local copy of `inventory.json`), and Step 9's
`docker ps` checks use the `$SERVER_IP`/`$L0_IP` exported in Step
2.

**Tests:** `test_deliver_image_registra_tempo_e_tamanho_do_2o_salto`/
`test_mutante_entrega_lenta_e_marcada_slow` (2, new, in
`test_orchestrator.py`) -- 141 in `thesis/results/v9/campaign/tests/`
(139 before this round + 2 new), all passing. Items 1/2/3/5
are PROCEDURE/documentation fixes (no new Python code beyond
item 4) -- no additional automated test for them, but the
3 format assertions (item 1) and the `colocated` logic (item 2)
are reused from code ALREADY tested (`orchestrator._server_
gateway_ip`, `outputs.tf`), never invented in the procedure.

**Local commit** (no push): `thesis/results/v9/campaign/scripts/
orchestrator.py` (`DELIVERY_SLOW_THRESHOLD_SECONDS`, timing in
`_deliver_image`), `thesis/results/v9/campaign/tests/
test_orchestrator.py` (2 new tests), `thesis/results/v9/campaign/
INFRA_REHEARSAL.md` (rewritten, 15 steps).

No fix this round changes any pre-registered criterion -- these
are address/robustness/reporting fixes to the rehearsal procedure,
never a change to the pilot's design. I continue to not authorize
push nor AWS resources.

## 61. Amendment -- the gateway's Image ID in PINS.json re-pinned (the original image no longer exists locally; the binary/certificates/base layer confirmed identical by content, never rebuilt). Luciano authorizes real execution on AWS from this Decision onward (present remotely, absent during the run itself) -- push becomes permitted only on v9/fase1-local

**Authorization:** Luciano authorized autonomous execution on AWS
(the `mockopin-pqc` account and profile, a US$5 cost ceiling, limited
retries, the fleet never idle, mandatory stops at specific criteria)
and
push to `v9/fase1-local` (never main/the `v9-prereg` tag), confirmed
explicitly after I stopped at the earlier pre-flight and asked back.
Branch `v9/fase1-local`.

**Context (resuming from the earlier PARADA.md):** this session's
pre-flight
found a local `mockopin-v9-gateway:latest` with Image ID
`fadd40fc9bf98d018a0cda2c364e1d546ac8b51db80613bac96dee5690bc9d28`,
diverging from the one pinned in PINS.json
(`625acc6b8838725265e2f66a52feaa00d87cac513713836d2bb7cc4af816f9ff`).
Luciano asked, before authorizing any re-pin: search for the
original image by digest; if it does not exist, an Amendment
conditioned on 4 proofs.

**Search for the original image:** `docker image inspect sha256:625acc
6b8838...` -- `[]`/"No such image". `docker images -a --no-trunc` --
does not appear, neither tagged nor dangling. **Confirmed: it no
longer exists
locally.**

**The 4 required proofs, all done by reading/comparing
content -- NO rebuild, NO `make certs`:**

**(a) Binary sha256 identical to the pinned one.** Extracted again
(`docker create`+`docker cp` from the current image) -- `a08ba8e31c4e6bdc
865cd32164413169390eca6766359105d10ed0e7557ff47f`, IDENTICAL to the
`binary_sha256` already in PINS.json. `go version -m` also identical
(same text, same build flags).

**(b) Image content, file by file, against expectations.**
`docker history --no-trunc` shows only 2 layers added on top of the
base: `COPY /gateway /gateway` (11.6MB) and `COPY certs /certs`
(193kB)
-- exactly what the `Dockerfile` declares, nothing more. The BASE
layer
(`sha256:75c137aedfb2760f88629236cb7b797630aed0c3d91d626d1d1bb694878
fc2ba`) is IDENTICAL, byte for byte (the same layer digest), to a fresh
`docker
pull` of `alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a
09c5aaaf51968b89368a3c0371ea2c9a` -- the exact digest the
`Dockerfile`
pins on the `FROM` line. I listed ALL of the image's files with
sha256
(`find / -xdev -type f | xargs sha256sum`, inside a real
container) -- 33 files in `/certs`, the `/gateway` binary, and the
rest is the
standard content of the Alpine 3.24 minirootfs (busybox, apk,
openssl,
etc.) -- nothing beyond what the Dockerfile copies.
`ENTRYPOINT ["/gateway"]`
and `EXPOSE 443` are the ONLY runtime instructions, no extra CMD
nor ENV. **No executable or runtime configuration diverges.**

**(c) Embedded certificates -- SAN and DER size against the
baselines.** 10 certificates (5 server + 5 client, one pair per
profile:
`classico`/`pqc`/`hibrido_v8`/`hibrido_and_rsa`/`hibrido_and_mldsa`).
Every SERVER certificate has the SAN `DNS:mtls,...,IP Address:127.0.0.1,
IP Address:0:0:0:0:0:0:0:1` -- exactly the `<IP>,::1` format
Decision 56
proved zeroes the byte deviation against the baseline (the IPv4's
VALUE
never affects the DER size, as Decision 56 already confirmed). Each
certificate's DER size, extracted from inside the image (`openssl
x509
-outform DER`), compared against `evaluate_criteria.BASELINE_CERT_
DER_SIZES`:

| Profile | Measured client DER | baseline "in" | Measured server DER | baseline "out" |
|---|---|---|---|---|
| classico | 787 | 787 | 900 | 900 |
| pqc | 5506 | 5506 | 5619 | 5619 |
| hibrido-v8 | 6131 | 6131 | 6242 | 6242 |
| hibrido-and (rsa+mldsa summed) | 801+5534=6335 | 6335 | 914+5647=6561 | 6561 |

**0B of deviation against the baseline, across the 4 profiles, in
both directions** --
identical to what Decision 56 had already proven across 20 rebuilds,
now confirmed also in the REAL image that goes into the pilot.

**(d) PINS.json diff.** Only the gateway's `image_id` field changed,
plus a new `note` field explaining the re-pin; `binary_sha256`/
`go_version_m_sha256`/`go_version_m_text` unchanged (already
confirmed
identical in item a):
```diff
-      "image_id": "sha256:625acc6b8838725265e2f66a52feaa00d87cac513713836d2bb7cc4af816f9ff"
+      "image_id": "sha256:fadd40fc9bf98d018a0cda2c364e1d546ac8b51db80613bac96dee5690bc9d28",
+      "note": "Decisao 61 (Emenda): Image ID re-pinado -- a imagem original (625acc6b8838...) nao existe mais localmente [...]"
```

**Image immutably tagged:** `docker tag mockopin-v9-gateway:latest
mockopin-v9-gateway:pinned` -- this tag is never overwritten again;
no
`docker build`/`make certs` runs again on this host before the pilot
finishes (Luciano's rule, recorded here so it is not forgotten).

**Item 2 of Luciano's request -- vCPU quotas, confirmed via v8's
historical record (no longer blocking, becomes documentation):**
v8's real `thesis/results/v8/campaign/terraform/main.tf` (the real
file used in
the v8 campaign) declares, across v9's pilot's 3 regions, EXACTLY the
same instance count/types the v9 pilot needs: `sa-east-1` --
`control`(t4g.micro)+`server_sa_east_1`(m7i-flex.large)+`client_l0`
(m7i-flex.large) = 3 instances/6 vCPU; `eu-north-1` --
`client_eu_north_1`(m7i-flex.large) = 1/2 vCPU; `ap-southeast-1` --
`client_ap_southeast_1`(m7i-flex.large) = 1/2 vCPU (confirmed
`m7i-flex.large`/`t4g.micro` = 2 vCPU each via `aws ec2 describe-
instance-types`, a real, read-only call). REAL execution evidence
(not just config): v8's Decision 73 ("Flex launch test run for real,
14
instances, 7 regions") -- `m7i-flex.large` AND `c7i-flex.large`
really ran, simultaneously, in sa-east-1/eu-north-1/
ap-southeast-1 (among others), 2026-10-20, confirmed via real
`describe-instances`/`StateTransitionReason`, not assumed.
**This directly proves >=4 simultaneous vCPU in sa-east-1 and >=2 in
eu-north-1/ap-southeast-1 have already worked** -- it covers with
direct evidence
the `eu-north-1`/`ap-southeast-1` minimum (2 each), but does NOT
directly prove the 6 vCPU the v9 pilot needs in `sa-east-1`
simultaneously (Decision 73's real test only ran 2 instances per
region, not 3) -- the full campaign's real config (3 instances in
sa-east-1) was never confirmed here by a single direct citation of
an apply with all 3 together. **The real apply attempt itself, with
rule 7(c) (tear down and stop on `VcpuLimitExceeded`), is the
final backstop -- exactly as Luciano himself designed it.**

**Service Quotas permission (a finding from the earlier
pre-flight):** remains denied
(`servicequotas:GetServiceQuota`) -- no longer blocking, per
Luciano's explicit instruction; recorded here, not
hidden.

**Tests:** 141/141, unchanged -- no Python code change
in this Decision, only `PINS.json` (data, not code).

**Commit and PUSH** (now authorized, only on `v9/fase1-local`):
`thesis/results/v9/campaign/PINS.json` (the gateway's Image ID
re-pinned), `thesis/results/v9/DECISIONS.md` (this Decision).

From here on, execution follows the runbook (Phase A --
infrastructure rehearsal; Phase B -- the 60-run pilot; Phase C --
consolidation) under the exact limits Luciano set, without asking
for confirmation at every step -- only at stops the limits
themselves require.

## 62. Real finding during Phase A's real execution (a real apply, 5 instances up) -- `deliver_campaign_key` wrote the key with CRLF (Windows line breaks), rejected by the destination's real ssh/scp ("invalid format"); fixed to write in binary, with no newline translation at all

Nothing outside the authorized scope. Branch `v9/fase1-local`, commit
and
push (Luciano's rule 5 -- every fix gets a Decision + a commit).

**Finding, live, at the rehearsal's real Step 4 (checking Docker
readiness on the 4 hosts via a relay through the control):** the 4 SSH
attempts from the control to the real hosts failed with `Load key "/home/ec2-user/
.ssh/campaign_key": invalid format` / `Permission denied`. The key
HAD already been delivered successfully in Step 3 (`deliver_campaign_key`,
no error reported) -- the problem was the file's CONTENT, not the
delivery itself.

**Root cause:** `Path.write_text(pem, encoding="utf-8")`, in TEXT
mode, on Windows Python, translates every `\n` to the OS's default
newline
(`\r\n`) before writing -- an SSH key with CRLF in the middle is
invalid for the real OpenSSH key parser (confirmed live, not
assumed). Never showed up in the tests because the tests stub all of
`cli._run`
-- none of them really write the file and then try to use it
with a real `ssh`/`scp` afterward.

**Fixed:** `deliver_campaign_key` now normalizes (`\r\n` -> `\n`,
in case any comes from some pipe beforehand) and writes with
`Path.write_bytes`
(binary, never `write_text`) -- exact bytes, no newline
translation possible. 2 new tests
(`test_deliver_campaign_key_grava_bytes_sem_cr`, confirms `b"\r\n"`
absent from the file captured before `TemporaryDirectory` removes
it).

**Retry 1/3 for this problem** (Luciano's rule 3) -- re-running
Step 3 (key delivery) and Step 4 (Docker readiness) again, with
the fix.

**Tests:** 142/142 (140 before + 2 new), all passing.

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
scripts/pki_relay.py` (fix), `thesis/results/v9/campaign/tests/
test_pki_relay.py` (2 new tests), `thesis/results/v9/DECISIONS.md`
(this Decision).

## 63. Second real finding in the same real Phase A -- `deliver_images.py` used `sh -c "docker save ... > <windows-path>"`, which corrupts the redirection with a backslash path; fixed to `docker save -o <path>` (pure argv, no shell in between)

Branch `v9/fase1-local`, commit and push. Retry 2/3 for the same
"Windows path problem" (the same family as Decision 62's finding, but
in a different file/command -- counted as a new problem for rule 3,
not a repeat of the same one).

**Finding, live, at Step 7 (`deliver_images.py`):** `docker save`
returned `returncode=0` (success) but the `.tar` never existed at
the expected path -- a `FileNotFoundError` on the `tar_path.stat()`
call
right after. Cause: `cli._run(["sh", "-c", f"docker save
{image} > {tar_path}"])` with `tar_path` a WINDOWS path
(`C:\Users\...\gateway.tar`) interpolated INSIDE a shell
string -- the backslashes break the redirection parsing
for the real `sh` (git-bash), which accepts the command (exit 0) but
never
writes to the right place.

**Fixed:** `docker save` has its OWN `-o <file>` flag --
switched to `cli._run(["docker", "save", "-o", str(tar_path),
docker_image])`, pure argv (a list), no shell interpreting the
path. Also added an explicit check
(`tar_path.is_file()`) after `docker save` -- never again trusting
just the `returncode`, even when it says success.

**Confirmed locally before trying again on AWS** (never just
in the tests, which stub all of `cli._run` and would not have caught
this):
`save_image_tarball("gateway", ...)` really run,
a 10.441.728-byte `gateway.tar` created at the right path.

**Tests:** `test_deliver_images.py`'s fake updated for the new
argv format (`docker save -o <path> <image>`, no longer `sh -c`)
-- 142/142, unchanged in count (only the fake changed, no new test).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
scripts/deliver_images.py` (fix), `thesis/results/v9/campaign/tests/
test_deliver_images.py` (fake updated), `thesis/results/v9/
DECISIONS.md` (this Decision).

## 64. Third real finding, same CRLF family (Decisions 62/63), found via a preventive audit after the second one -- deliver_images.py wrote the .sha256 and gateway_binary_info.json with write_text (Windows), corrupting the sha256sum -c verification on the real control

Branch `v9/fase1-local`, commit and push. Retry 3/3 for the "Windows
path/encoding problem" (rule 3 -- on the 3rd, if it persists, the
rule says to tear down and stop; I decided to audit the ENTIRE rest
of the package for this pattern BEFORE spending this 3rd attempt, so
as not to hit it again at an unverified 4th spot).

**Finding, live, resuming Step 7 after Decision 63's fix:**
`docker save -o` now created the right `.tar`, but `sha256sum -c`
still failed: `sha256sum: 'gateway.tar'$'\r': No such file or
directory`. The same root cause as Decisions 62/63 -- `sha_path.
write_text(f"{sha256}  {tar_path.name}\n")` writes `\r\n` on
Windows; the `\r` sticks to the file NAME when the real
(Linux) `sha256sum` parses the line on the control.

**Preventive audit (before spending the 3rd/last retry):**
`grep -rn "write_text(" thesis/results/v9/campaign/scripts/*.py` --
9 occurrences. Classified:
- `cli.py` (`_LocalShellShim`): only manual LOCAL validation, never
  exercised by the real pilot (`orchestrator.py --mode ssh` never
  turns the shim on) -- no risk here.
- `collect_artifacts.py` (`.pull-verified`): written on the
  OPERATOR, only its EXISTENCE is checked afterward (`cleanup.py`),
  never the content --
  no risk.
- `orchestrator.py` (manifest/logs/criterio6/captures): written
  INSIDE the `orchestrator.py` process, which runs on the CONTROL
  (Linux, Decision 59) -- `write_text` there never translates to
  CRLF (only
  Windows does that) -- no risk.
- `deliver_images.py` (`.sha256`, `gateway_binary_info.json`): BOTH
  written on the OPERATOR (Windows) and then READ by a real
  Linux process (`sha256sum`/`json.loads` on the control) --
  **real risk, both fixed**.

**Fixed:** both `write_text` calls in `deliver_images.py` swapped
for `write_bytes` with an explicit `\n`, the same pattern as
Decisions
62/63.

**Tests:** 2 new
(`test_deliver_images_sha_path_nunca_tem_cr`/`test_deliver_images_
gateway_info_json_nunca_tem_cr`) -- 144/144 (142 before + 2 new),
all passing.

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
scripts/deliver_images.py` (2 fixes), `thesis/results/v9/campaign/
tests/test_deliver_images.py` (2 new tests), `thesis/results/v9/
DECISIONS.md` (this Decision).

## 65. Two real findings at Step 8 (checking dependencies on the control, exactly the step designed to catch this) -- redact_aws_errors.py never delivered to the control (cli.py depends on it via a relative sys.path), and orchestrator.py/evaluate_criteria.py use the `|` union syntax (PEP 604) that breaks on the control's real Python 3.9

Branch `v9/fase1-local`, commit and push. A new "problem" for rule 3
(0/3 retries used on it so far).

**Finding 1 -- `redact_aws_errors.py` missing:** `python3 orchestrator.py
--help` on the control broke at `import cli`, which broke at
`ModuleNotFoundError: No module named 'redact_aws_errors'`.
`cli.py` imports that module via a relative `sys.path` (`Path(__file__).
resolve().parents[3] / "v8" / "campaign" / "scripts"`, a finding from
Decision 59 that assumes the entire repository) -- but `deliver_to_
control` (Decision 59) never included this v8 file in the list of
what it delivers to the control. Fixed: `CONTROL_FILES`
(`deliver_source.py`)
gains `thesis/results/v8/campaign/scripts/redact_aws_errors.py`.

**Finding 2 -- the control's real Python 3.9, incompatible syntax:**
the control (AL2023, confirmed `python3 --version` = 3.9.25) does not
have
`list[str] | None` (`|` union between types, PEP 604 -- only from
3.10 onward). `orchestrator.py` (2 occurrences) and
`evaluate_criteria.py` (1
occurrence) use this syntax in function annotations -- evaluated at
the function's DEFINITION, which would break the entire module as
soon as
the first finding was fixed and the import reached that point.
Fixed with `from
__future__ import annotations` (defers every annotation to a
string, never
evaluated at runtime -- confirmed, no `get_type_hints`/dataclass
in any of the 4 files the control runs, zero behavior
change) in both files.

**Why both only showed up now:** no automated test
runs `orchestrator.py` under the control's real Python (the tests
run on the operator's machine, Python 3.13) -- exactly why
Decision 60 asked for this Step 8 as a new procedure item.
It worked: it caught both BEFORE any timed run.

**Tests:** 144/144, unchanged (syntax/import, nothing the fakes
test specifically -- `from __future__ import annotations` is
transparent to the existing tests).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
scripts/deliver_source.py` (`CONTROL_FILES` +1), `thesis/results/v9/
campaign/scripts/orchestrator.py` (`from __future__ import
annotations`), `thesis/results/v9/integration/evaluate_criteria.py`
(same), `thesis/results/v9/DECISIONS.md` (this Decision).

## 66. Real finding at Step 9 (--exercise-start-stop) -- `_tcp_preflight` always failed on the FIRST block of any route, because it checked port 443 before the gateway existed; fixed to distinguish "connection refused" (network OK, the app just hasn't come up yet -- expected) from a real timeout (the only case that still fails)

Branch `v9/fase1-local`, commit and push.

**Finding, live, resuming Step 9:** `_tcp_preflight` aborted
with "client did not reach ...:443" -- real output: `bash: connect:
Connection refused`. Investigating: real v8 had `mtls` as a
PERSISTENT docker-compose service (never recreated by
`switch_crypto_profile.py`), so port 443 was always up
whenever `preflight_tcp.py` (the original) ran. v9's `_launch_
gateway` does `docker rm -f`+`docker run` on every profile switch --
`_tcp_preflight`, being `start_block`'s FIRST step on
purpose, runs BEFORE the gateway has ever come up on the first
block of any route (or in an isolated exercise like `--exercise-
start-stop`) -- "connection refused" is exactly what is expected at
that
moment, never a symptom of a wrong Security Group.

**Missing distinction:** a "connection refused" (a fast RST)
PROVES the packet reached the server's kernel and was
rejected only because nothing is listening yet -- POSITIVE evidence
that
the Security Group let the traffic through. Only a real TIMEOUT
(no response, the packet silently dropped) is real evidence
of a wrong SG/VPC.

**Fixed:** the remote command now distinguishes the 3 cases
(the real `timeout`'s `$?`: `0`=OK, `124`=TIMEOUT, anything
else=REFUSED) --
`ok = outcome in ("OK", "REFUSED")`, only `TIMEOUT` aborts.
`tcp_preflight_results` gains the `outcome` field (besides `ok`), so
the audit shows which of the 3 actually happened.

**Tests:** `test_tcp_preflight_aborta_se_timeout_de_verdade`
(renamed/fixed -- simulates an explicit TIMEOUT, no longer a generic
"FAIL") + `test_tcp_preflight_passa_com_connection_refused` (new
-- proves REFUSED passes and lets the entire block proceed) -- 145
in total (144 before + 1 new).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
scripts/orchestrator.py` (`_tcp_preflight` fixed),
`thesis/results/v9/campaign/tests/test_orchestrator.py` (2 tests),
`thesis/results/v9/DECISIONS.md` (this Decision).

## 67. Real STOP in Phase A, Step 9 -- the post-docker-load Image ID diverges between the operator's Docker version (29.9.1) and the real server's (25.0.16), even with the binary/certificates confirmed byte-identical; the pre-registered Image ID verification mechanism (Decision 55) does not survive this version difference -- stopped per rules 6/7(e), the fleet torn down and confirmed clean

Branch `v9/fase1-local`, commit and push. Fleet torn down
(`cleanup.py --release-eips --force`, `all_clean: true`) and
confirmed clean via 12 independent `describe-*` calls, all
empty, across the 3 regions. See `thesis/results/v9/piloto/PARADA.md`
for the full account (test/evidence/options for Luciano to decide
on).

**What actually ran before this stop:** a real apply (28
resources), Steps 0-8 of the rehearsal completed -- each fixed
at least once live (Decisions 62-66, all committed/pushed).
Step 9 (`--exercise-start-stop`) did deliver the gateway's `.tar`
over 2 real hops, verified by sha256 at both transport points -- and
it only FAILED on the POST-load Image ID check.

**Finding, investigated only by reading (no rebuild, no
change to PINS.json):** the `/gateway` binary inside the real
container, on the server, has an sha256 identical to the pinned
one -- correct
content, confirmed. The Image ID (`docker image inspect .Id`), after
`docker load`, however, diverges from the pinned one. Root cause: the
OPERATOR's machine runs Docker 29.9.1; the real server (Amazon Linux
2023,
`dnf install docker` package) runs Docker 25.0.16 -- the SAME `.tar`,
loaded by both versions, produces two different Image IDs. This
scenario had NEVER been tested across different Docker versions
before this real execution (`docker load`'s determinism,
established in Decisions 54/55/58/59, had only been confirmed UNTIL
NOW
within the SAME Docker installation).

**Why this is a stop, not a fix:** fixing this
(changing what is verified, or pinning the host's Docker version)
alters a PRE-REGISTERED verification mechanism (Decision 55) --
Luciano's rule 6 ("changing... pre-registered criteria: STOP and
report") and rule 7(e) ("doubt about whether a fix changes what
is being measured"). Honestly recorded as a real finding, never
worked around on my own.

**Risk for the official campaign, not just the pilot:** any real
EC2 instance tends to run an older Docker (a distribution package)
than the operator's (Docker Desktop) -- this problem should repeat
in any real delivery by Image ID, it is not specific to this
instance/execution.

**3 options recorded in PARADA.md, none applied:** (1) switch
the fail-closed criterion to the binary's/`.tar`'s sha256 (already
proven stable across versions) and demote Image ID to a diagnostic;
(2) pin the SAME Docker version on the host as on the operator
(`install_common_
packages.sh` would pin a version, not a generic `dnf install -y
docker`); (3) another path.

**Tests:** no code change in this Decision (only investigation and
documentation) -- 145/145, unchanged.

**Real cost of this execution (apply + ~9 steps + destroy, 3
regions,
~25-30min of fleet-time):** well under US$1, far below the US$5
ceiling. No "same problem" exceeded 1 retry.

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/piloto/
PARADA.md` (rewritten with the real finding), `thesis/results/v9/
piloto/estado.json`, `thesis/results/v9/piloto/ensaio_infra/logs/*`
(real apply/cleanup/final-check/diagnostic logs, redacted),
`thesis/results/v9/DECISIONS.md` (this Decision).

No Phase B attempted -- Phase A did not close out green. Awaiting
Luciano's decision on the Image ID verification mechanism
before any new attempt.

## 68. Amendment -- the delivery-verification mechanism switched from Image ID to content (tar sha256 + RootFS.Layers + Config subset + the binary's sha256 inside the container), confirmed stable across Docker versions by a local test with docker:25-dind; no pre-registered criterion nor what is measured changes

Branch `v9/fase1-local`, commit and push. Luciano's decision, a
direct response to Decision 67's finding: "nothing else is decided,
proceed like this"
+ the prompt's detailed item-1 instruction.

**Reason.** Decision 67 stopped the real Phase A because the
gateway's Image ID
(`.Id`), after a `docker load` on the real server, diverged from
the one
pinned in PINS.json -- even with the binary inside the container
byte-identical to the pin. The root cause (the operator's Docker
29.9.1 vs.
the real server's 25.0.16) is structural: any real EC2 instance
tends to
run an older Docker (a distribution package) than the
operator's, so the Image ID fail-closed mechanism pre-registered
in Decision 55 would never survive a real execution, on any
future attempt.

**Local investigation, no AWS, before any change.** I brought up a
`docker:25-dind` (resolved to Docker 25.0.5, the same version family
as the real AMI, 25.0.16) alongside the operator's Docker (29.9.1).
For
each of the 4 pinned images, I did a `docker load` of the SAME
`.tar`
on both daemons and compared `docker image inspect`:

- `.RootFS.Layers` (the content-addressable layer digest list):
  IDENTICAL across both versions, on the 4 images.
- `.Config` (the Entrypoint/Cmd/Env/ExposedPorts subset): IDENTICAL
  across both versions, on the 4 images.
- `.Id` (the final Image ID): DIVERGES between the two versions,
  reproducing
  exactly what was seen live on the real server (Decision 67).
- For gateway/proxy: the binary's sha256 INSIDE the container loaded
  on the DinD matched exactly the one pinned in PINS.json in both
  cases.
- `docker save` of the same local image id (never rebuilt), two
  independent invocations: the same file sha256 both times
  (proving the `.tar` itself is reproducible, not just the binary
  inside
  it).

Conclusion: layers and config ARE stable across Docker versions for
a byte-identical `.tar`; only the Image ID is not. This applies the
first
branch of Luciano's item 1 (pin by `.tar` sha256 + RootFS.Layers +
Config subset; Image ID drops to informative).

**New mechanism, in this order (every abort happens BEFORE any
real execution on the image):**
1. The sha256 of the freshly-built local `.tar` is checked against
   the pinned
   `tar_sha256` (`deliver_images.py`, 1st hop,
   operator->control) -- if the local image was rebuilt, it aborts
   here, it never gets to scp.
2. The sha256 of the `.tar` staged on the control is checked against
   the same
   `tar_sha256` (`orchestrator._deliver_image`, before the 2nd hop).
3. After `docker load` on the host (server/client), `RootFS.Layers`
   is checked against the pinned `rootfs_layers`.
4. `Config` (Entrypoint/Cmd/Env/ExposedPorts) is checked against
   the pinned `config_subset`.
5. For gateway/proxy (which have their own Go binary): the sha256 of
   the binary
   INSIDE the container loaded on the host (never of the isolated
   `.tar`)
   is checked against the pinned `binary_sha256` -- the same content
   guarantee Decision 55 already required, just now verified
   after the real `docker load` on the host, not only on the `.tar`.

The Image ID (`.Id`) keeps being read and recorded in PINS.json, but
**only as an informative field** -- never compared, never a reason
for an abort.

**PINS.json diff (schema, per image; 4 images, the same change in
all of them):**
```
- "image_id": "sha256:...",                    # unico campo de identidade, fail-closed
+ "tar_sha256": "<sha256 do .tar>",             # NOVO -- fail-closed, 2 saltos
+ "rootfs_layers": ["sha256:...", ...],         # NOVO -- fail-closed, pos docker load no host
+ "config_subset": {                             # NOVO -- fail-closed, pos docker load no host
+     "Entrypoint": [...], "Cmd": ..., "Env": [...], "ExposedPorts": ...
+ },
+ "image_id": "sha256:...",                     # MANTIDO, agora so informativo
+ "image_id_note": "Informativo apenas -- NUNCA verificado (Decisao 68, ver _image_identity_note)."
```
Plus a new top-level field, `_image_identity_note`,
explaining the finding and the new verification order. The gateway
re-pinned
in Decision 61 already had `binary_sha256`/`binary_path_in_image`
unchanged -- this Amendment only adds the 3 content fields above,
it never touches the binary/certificates/sha256 already pinned.

**Explicit declaration (Luciano's rule 6/7e):** this Amendment
alters
ONLY the mechanism for verifying that the delivered image is the
expected one
(an infrastructure integrity check). None of the 7
pre-registered criteria nor their thresholds change; no measurement
(latency, bytes, any pilot metric) depends on the Image ID or
comes to depend on any of the new fields -- they only decide
whether the run CAN start, never what is measured during it. No
binary, certificate, or runtime configuration was altered or
rebuilt for this Decision.

**Code:** `orchestrator._deliver_image` rewritten (reads `tar_sha256`/
`rootfs_layers`/`config_subset`/`binary_path_in_image`/
`binary_sha256` from PINS.json; aborts on the `.tar`'s sha256 BEFORE
any scp; after `docker load`, checks layers/config/binary
and only then decides `ok`). `deliver_images.py` gains the same
`tar_sha256` check on the 1st hop. `preflight.check_capture_prerequisites`/
`run_capture_preflight` swap the `measure` image's Image ID check
for `RootFS.Layers`+the `Config` subset.

**Tests (mutants requested by Luciano, all new or rewritten):**
a tampered local tar fails BEFORE any scp; a tampered layer
fails; tampered config fails; a binary tampered inside the
container fails (only the image with the swapped binary, the others
pass); the correct case passes with `layers_ok=config_ok=binary_ok=true`
across the 3 images with a verifiable binary/content. 151/151 after
this round (145 before + 6 new/rewritten, minus 1 obsolete Image ID
test removed).

**Documentation:** `PILOT_READINESS.md` (the pins section rewritten +
a new "Image ID -- Decision 68" subsection) and `INFRA_REHEARSAL.md`
(Steps 7 and 9 updated, expected output shows the new fields)
updated to reflect the new mechanism.

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
PINS.json`, `thesis/results/v9/campaign/scripts/orchestrator.py`,
`thesis/results/v9/campaign/scripts/deliver_images.py`,
`thesis/results/v9/campaign/scripts/preflight.py`,
`thesis/results/v9/campaign/tests/test_orchestrator.py`,
`thesis/results/v9/campaign/tests/test_deliver_images.py`,
`thesis/results/v9/campaign/tests/test_preflight.py`,
`thesis/results/v9/campaign/PILOT_READINESS.md`,
`thesis/results/v9/campaign/INFRA_REHEARSAL.md`,
`thesis/results/v9/DECISIONS.md` (this Decision).

## 69. Full CRLF/Windows-path sweep across the remote path; .gitattributes gains `*.tftpl`; a new test (`test_no_crlf_sweep.py`) really sweeps, on disk, every file that travels to Linux (`deliver_source.py`'s lists + terraform templates + the campaign package) -- no new finding beyond the ones already fixed in Decisions 62/64

Branch `v9/fase1-local`, commit and push. Item 2 of the same prompt
from Luciano that originated Decision 68.

**Manual sweep, before the test:** reviewed every terraform
`.sh`/`.tftpl` script (`safety_timer.sh.tftpl`, user_data),
every script delivered via `deliver_source.py`
(`COMMON_FILES`/`CLIENT_ONLY_FILES`/`CONTROL_FILES`) and the entire
`campaign/scripts`+`campaign/tests` package, looking for: CRLF, a
backslash path, `~` expansion on the wrong side (operator instead of
remote), and SSH key permission. No new finding -- every
remaining `~` expansion is done by a REMOTE shell (never local) or
is an `scp` destination resolved on the server; no backslash path
reaches a command that runs on the Linux side. The 2 real CRLF
points (CRLF in `pki_relay`/Decision 62 and in
`deliver_images.py`/Decision 64) had already been fixed earlier in
this same real
Phase A -- this sweep only confirms there is no third one.

**`.gitattributes` (repo root):** already had `eol=lf` for
`*.sh`/`*.py`/`*.json`/`*.key`/`*.pem`/`*.crt` and others -- only
`*.tftpl` was missing. Added the line `*.tftpl text eol=lf`.

**New test, `thesis/results/v9/campaign/tests/
test_no_crlf_sweep.py`:** really sweeps on disk (never just trusting
`.gitattributes`, which only normalizes what is committed, never
what
is generated at runtime), every `.sh`/`.tftpl`/`.py`/`.json`
extension
inside: `deliver_source.py`'s 3 lists (the single source of
truth, imported directly -- never duplicated, so it never goes
stale), the terraform templates, and the `campaign/
scripts`+`campaign/tests` package. Fails if any file contains `\r`.
The first run found 5 files with CRLF -- investigated, none
belongs to the remote path (`thesis/scripts/audit_v7_from_raw.py`,
`compute_v7_report_data.py`, `generate_v8_final_report.py`,
`render_v8_final_report.py`, `report_build/build_v7_reports.py` --
LOCAL v7/v8 final-report generators, never delivered to any
instance, confirmed by grep: no reference to them in
`thesis/results/v9`). Sweep restricted to the remote path's real
scope (above); final result: 0 findings.

**Tests:** 154/154 (151 before + 3 new in this file: the main
sweep test, a sanity test confirming the sweep really finds files,
and a mutant test confirming the `\r` detection works).

**Declaration:** no pre-registered criterion nor what is measured
changes -- this is only an infrastructure safety net (file format),
same as Decision 68.

**Commit and push** (`v9/fase1-local`): `.gitattributes`,
`thesis/results/v9/campaign/tests/test_no_crlf_sweep.py`,
`thesis/results/v9/DECISIONS.md` (this Decision).

With this, items 1 and 2 of Luciano's prompt are complete. Moving on
to item 3: a green test suite -> Phase A from scratch (a new fleet,
steps 0 to 14, `self_terminate_hours=1`) -> if it closes out green,
Phase B
with no request for confirmation.

## 70. Real finding, live, resuming the real Phase A (a new fleet, Step 9) -- `_launch_gateway` unconditionally used `--network insurance-server-lambdas_default` (only exists in the LOCAL validation via the shim), stuck the container at "Created" (never "Up") on a real EC2 server; neither `docker run -d` nor the "listening on" wait loop checked the exit code, so the real error only showed up 2 steps later, with no clue to the cause

Branch `v9/fase1-local`, commit and push. Real resumption of Phase A
(item
3 of Luciano's earlier prompt), a new fleet (`terraform apply
-var="self_terminate_hours=1"`, 28 resources, 5 instances, 3
regions) -- the account confirmed clean (12 `describe-*` calls, 3
regions, all empty) before the apply.

**Finding, live, at Step 9 (`--exercise-start-stop`):**
`_verify_running_gateway_binary` aborted with `"Error response from
daemon: container ... is not running"`. Investigated via `docker ps -a`
on the real server (2nd hop, via the control): the `v9-mtls`
container
was in `Created` status (never `Up`) -- `docker run -d` never
actually
started the container.

**Root cause:** `_launch_gateway` always used `--network
insurance-server-lambdas_default` + 6 `--network-alias` (designed
for
internal Docker DNS resolution by OTHER containers in the local
`insurance-server-lambdas` stack, which only comes up when
`local_shim_bridge_
join=True`). On a real EC2 server (`local_shim_bridge_join=False`,
the case for every real remote pilot), this network NEVER exists --
`docker run` was failing (network not found), but neither that call
nor
the "listening on" wait loop below it (`cli.run_ssh(...)`
with no `.returncode` check) was checking for the error -- the
problem only
showed up 2 steps later, in `_verify_running_gateway_binary`, with
no
clue to the real cause. This same gap had already been honestly
recorded in `start_block`'s docstring since Decision 49
("For a real remote pilot, this script needs a v9-aware version...
this does NOT exist yet") -- a known, deferred gap, that only
actually manifested in this resumption.

**Why this is a safe fix, never a STOP:** the real client
(`_server_gateway_ip`) always dials the HOST's IP on port 443, never
a Docker alias -- the network/aliases never had any effect on
what is measured (real TLS handshake bytes/latency), they only
decided whether
OTHER local containers (auth/mockapi, which do not even exist in the
remote pilot) could resolve "mtls" via Docker DNS. Swapping this for
the only real requirement of the remote case (publishing the port on
the host) does not touch PINS.json, any pinned binary/certificate,
nor any
of the 7 pre-registered criteria.

**Fixed, in `orchestrator.py._launch_gateway`:** `network_flags`
is now conditional on `local_shim_bridge_join` -- `True` keeps the
old
network/aliases (local validation, where other compose containers
need to resolve the alias); `False` (the real remote case) switches
to using `-p 443:443`. `docker run -d` now has its `.returncode`
checked, aborting immediately with the real output if it fails. The
"listening on" wait loop now also checks whether it was found
("FOUND" in stdout) before proceeding -- if it never finds it within
30s,
it aborts with the container's real status (`docker ps -a`) in the
message, instead of letting the error show up 2 steps later with no
context.

**Tests:** 2 new (`test_launch_gateway_aborta_se_docker_run_falha`,
`test_launch_gateway_aborta_se_container_nunca_fica_pronto`) + the 2
existing `_launch_gateway` tests (real remote case / local
validation) gained new assertions checking the correct
`network_flags`
in each mode. 156 tests in total.

**Validated live, resuming Step 9 on the SAME real fleet** (after
redeploying the fixed `orchestrator.py` to the control via
`deliver_source.py --to-control`): `start_block_ok: true` -- the
gateway
comes up, logs "listening on", `_verify_running_gateway_binary`
confirms
`running_container_sha256_ok: true`.

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
scripts/orchestrator.py`, `thesis/results/v9/campaign/tests/
test_orchestrator.py`, `thesis/results/v9/DECISIONS.md` (this
Decision).

## 71. Second real finding, same Phase A resumption, Step 9 (after Decision 70) -- `deliver_source.py` never installed `thesis/scripts/requirements.txt` on the real client (a step the original v8 had, lost in the Python rewrite); `opin_flow.py` broke with `ModuleNotFoundError: No module named 'jwt'` on the first real `start_block`

Branch `v9/fase1-local`, commit and push. The same real fleet from
Decision
70 (no new instance needed to come up).

**Finding, live, resuming Step 9 (after fixing Decision
70):** `start_block` did get the gateway up successfully, but
failed at "bringing up proxy/signer" on the L0 client, with the real
traceback:
`File ".../opin_flow.py", line 131 -- import jwt as pyjwt --
ModuleNotFoundError: No module named 'jwt'`.

**Root cause:** `install_common_packages.sh` (the already existing
Terraform template) has a comment citing that v8's REAL
`deliver_source.sh` did, as its OWN last step, `pip3 install --user -r
requirements.txt` on the destination -- this package's Python
rewrite
(`deliver_source.py`, Decision 58) delivered the `requirements.
txt` FILE (it is in `COMMON_FILES`) but never installed it anywhere.
Masked throughout this entire round (including Decision 67) because
the
only existing Python-environment check
(`preflight.check_client_python_environment`) tests the OPERATOR's
OWN `.venv` (`_VENV_PYTHON_DEFAULT`, a Windows path), never the
remote client -- it only showed up live at the first real
`start_block`
that implicitly got far enough to bring up the proxy/signer on the
client (earlier
steps, Decisions 62-67, never got that far).

**Why this is a safe fix, never a STOP:** installing
hash-PINNED Python dependencies (`requirements.txt` already requires
`--require-hashes`, a decision predating this round) on the client
does not
alter any pinned binary/certificate, nor PINS.json, nor any
of the 7 pre-registered criteria -- it is only the environment
prerequisite
for `opin_flow.py` to run.

**Fixed:** `deliver_source.py` gains `install_client_requirements()`
(runs `pip3 install --user --require-hashes -r ~/thesis/scripts/
requirements.txt` on the client, relayed through the control with
the
CAMPAIGN key, the same 2-hop pattern as the rest of the file) --
called
INSIDE `deliver_source()`'s client loop, never for the server
(which never executes this code). The per-client report gains
`"requirements_installed": true`.

**Tests:** 2 new
(`test_deliver_source_instala_requirements_so_nos_clientes`,
`test_deliver_source_aborta_se_pip_install_falha_no_cliente`). 158
tests in total.

**Validated live, resuming Step 9 on the SAME real fleet** (after
`deliver_source.py --inventory-json ...` redeployed the 3 clients
with
the new pip install): Step 9 closed out **completely green**
-- `start_block_ok: true`, `stop_block_ok: true`,
`gateway_binary_verifications[0].pin_matched: true` and
`running_container_sha256_ok: true`, all 3 `image_delivery_
verifications` (gateway/proxy/pqc-signer) with `ok/layers_ok/
config_ok/binary_ok` all `true`, `tcp_preflight_results[0].ok:
true`. The first time this round (and in this package's history)
that
Step 9 closes out end to end in a real AWS execution.

**Cumulative cost of this resumption:** a new fleet, ~25min of
life so far (apply + steps 0-9 + the 2 fixes above), well under
US$1,
far below the US$5 ceiling.

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
scripts/deliver_source.py`, `thesis/results/v9/campaign/tests/
test_deliver_source.py`, `thesis/results/v9/DECISIONS.md` (this
Decision).

Moving on to Steps 10-14 of the procedure (same fleet, no
reapplying).

## 72. Third real finding, same Phase A resumption, Step 10 -- `rehearsal_handshake.sh` had the same `CERTS_DIR`/`REAL_CERTS_DIR` defaults relative to the script (only making sense when run LOCALLY), breaking with "No such file or directory" when run from the real control; fixed to use the real path when `CLIENT_SSH`/`GATEWAY_SSH` are set -- validated live on a new fleet together with Decisions 73/74 (see below), after 2 additional findings at the SAME step

Branch `v9/fase1-local`, commit and push. The same real fleet from
Decisions
70/71 (no new instance needed to come up for this specific
finding).

**Finding, live, at Step 10 (real per-profile handshake):**
`rehearsal_handshake.sh`, triggered from the control, aborted at the
first useful line with `rehearsal_handshake.sh: line 23: cd:
./../../certs/generated: No such file or directory`.

**Root cause:** `CERTS_DIR`/`REAL_CERTS_DIR` had the SAME default
relative to the script itself (`$(dirname "$0")/../../...`) that
`orchestrator._launch_gateway.real_certs_mount` had BEFORE
Decision 58 -- it only makes sense when the script runs in the real
repository
(the operator's laptop). The copy `deliver_source.py` delivers to
the CONTROL (`CONTROL_FILES`) never has `certs/generated` on its
side
(`CLIENT_ONLY_FILES` only delivers that to the CLIENT) -- and even if
it did, the `-v $CERTS_DIR:/certs:ro` mount needs to exist on the
HOST
that actually runs the `docker run` (client/server, via `on_client`/
`on_gateway`), never on the control, which only triggers the command
via SSH.
The same bug class, exactly the same reasoning already fixed in
`_launch_gateway` (Decision 58) -- just that this shell script never
had received the same treatment.

**Why this is a safe fix, never a STOP:** the certificate mount
path does not alter any pinned binary/certificate nor
any of the 7 pre-registered criteria -- the SAME certificates
(delivered by `deliver_source.py`) just start being read from the
right place (the real client/server) instead of a place that never
existed
(the control).

**Fixed, in `rehearsal_handshake.sh`:** `CERTS_DIR`/`REAL_CERTS_DIR`
now only fall back to the old default (relative to the script) when
`CLIENT_SSH`/`GATEWAY_SSH` are EMPTY (local mode); when set
(real remote mode), they use the real path `deliver_source.py`
actually delivers -- an ABSOLUTE path (`/home/ec2-user/...`), not
`~`; see
Decision 73 for the exact reason behind that choice (an additional
finding, in the SAME
resumption, before the live validation closed out).

**Infrastructure note (not a code bug, recorded here for
transparency):** before I could redeliver and re-test this
fix live, the 3 `sa-east-1` instances (control/server/
L0) simultaneously became unreachable on ports 22 AND 443
from the operator's machine, for ~8 straight minutes (several
attempts, including a pure TCP test via `/dev/tcp`, with no
response at all -- a real timeout, never "connection refused"). It
was not
a code or configuration problem: `aws ec2 describe-
instance-status` confirmed the 3 instances with `instance: ok` and
`system: ok` (healthy at the hypervisor level); the AWS API
calls (HTTPS) kept working perfectly the entire time; the
control's Security Group confirmed unchanged and correct (rule
22/tcp exactly for the operator's CIDR, same as at apply time); the
operator's public IP confirmed unchanged; port 22 to a NON-
AWS host (github.com) worked normally at the same instant.
Conclusion:
a transient network-routing problem between the operator's machine
and
specifically these 3 instances (`sa-east-1` region), never
diagnosable nor fixable by this package -- with no SSM available
as an alternative (`ssm:DescribeInstanceInformation` denied by the
real IAM policy, the same already-known limitation as other read
calls). The "fleet never idle" rule (>15min stuck) applied:
after ~8min with no recovery, the fleet torn down (`cleanup.py --tf-dir
../../terraform --release-eips --force`, `all_clean: true`,
`destroy_rc: 0`, no drift) and confirmed clean via the 12 independent
`describe-*` calls (instances/EIPs/security-groups/key-
pairs, 3 regions), all empty.

**Tests:** no new automated test (a shell script with no associated
pytest suite in this package, the same situation as every other
`.sh` script) -- 158 tests unchanged. **Live validation**:
this fix, by itself, was still not enough (an additional real finding
at the same Step 10, see Decision 73) -- it only closed out as a real
**PASS** after that, on the new fleet (see Decision 73/74).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
scripts/rehearsal_handshake.sh`, `thesis/results/v9/DECISIONS.md`
(this Decision).

Reapplying a new fleet (`self_terminate_hours=1`) to resume
Phase A from Step 0, the account already confirmed clean above.

## 73. Fourth real finding, resuming Phase A on a new fleet, STILL at Step 10 -- Decision 72's fix (path) was not enough: `~` inside `-v "$VAR:..."` never expands (double quotes suppress tilde expansion), Docker failed with "invalid local volume name"; and, once resolved, `rehearsal_handshake.sh` also unconditionally used `--network insurance-server-lambdas_default` for the gateway (the SAME root cause already fixed in `_launch_gateway`, Decision 70, never replicated here) -- both fixed, with Decision 72's fix validated live at the same step

Branch `v9/fase1-local`, commit and push. A NEW fleet (reapplied
after
Decision 72's infrastructure note -- a real apply, 28 resources, 5
instances, 3 regions, the account confirmed clean before the apply).

**Finding 1, live, resuming Step 10 on the new fleet:** with
Decision 72's fix delivered, the gateway's `docker run -d` failed
with
`docker: Error response from daemon: create ~/mock-service-os/certs:
"~/mock-service-os/certs" includes invalid characters for a local
volume name... If you intended to pass a host directory, use
absolute path.` Decision 72's `~` never actually got expanded:
inside double quotes (the quotes in `-v \"$REAL_CERTS_DIR:...\"`
already
existed in the script, protecting LOCAL Windows paths with
spaces), the REMOTE shell also never expands tilde -- Docker
received the
LITERAL tilde and treated it as a named volume name, not a path.
Unlike `_launch_gateway` (Decision 58), which uses the SAME `~`
WITHOUT
outer quotes (`-v {real_certs_mount}:/real-certs:ro`, expanding
normally) -- this shell script has the quoting quirk that Python
does
not have.

**Fixed (Finding 1):** `CERTS_DIR`/`REAL_CERTS_DIR`, in remote
mode, now use the real ABSOLUTE path (`/home/ec2-user/...`
-- the fixed login user on every instance in this project, confirmed
at every other point that does SSH here), never `~` -- eliminating
the
quoting ambiguity entirely, nothing needs to be expanded.

**Finding 2, live, in the SAME resumption, after resolving Finding
1:**
the gateway's `docker run -d` failed again, now with `docker:
Error response from daemon: network insurance-server-lambdas_default
not found.` -- the SAME root cause Decision 70 had already
fixed in `orchestrator._launch_gateway` (the Docker network/aliases
only exist in the local validation stack via compose) -- just that
`rehearsal_handshake.sh` has the SAME duplicated logic, which never
received
the same treatment, because it is a separate script that never
shares
code with `orchestrator.py`.

**Why both are safe fixes, never a STOP:** neither
touches a pinned binary/certificate, PINS.json, or any of the 7
pre-registered criteria -- only how the gateway/client in this
MECHANISM-PROOF step (never one of the official 60/12 runs)
reach each other over the real network.

**Fixed (Finding 2):** new variables `GATEWAY_NETWORK_FLAGS`/
`CLIENT_NETWORK_FLAGS`, conditional on `GATEWAY_SSH`/`CLIENT_SSH`
being set -- remote mode: the gateway uses `-p 443:443` (the client
dials `GATEWAY_HOST`, a real IP, never a Docker alias); the negtest
client needs no Docker network at all (`CLIENT_NETWORK_FLAGS=""`
-- the host's default network is enough to reach any external IP).
Local mode keeps the old network/aliases, unchanged.

**Tests:** no new test (same situation as Decision 72) -- 158
unchanged.

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
scripts/rehearsal_handshake.sh`, `thesis/results/v9/DECISIONS.md`
(this Decision).

## 74. Fifth real finding, STILL the same resumption, STILL Step 10 (Findings 1/2 from Decision 73 resolved) -- this script's gateway `docker run -d` failed with "port is already allocated" on port 443: the `v9-mtls` container from `orchestrator.py`, left up on purpose by the earlier Step 9 (`stop_block` never removes it), was already occupying the same host port via `-p 443:443` (Decision 70) -- fixed by defensively removing it before bringing up this script's container, only in remote mode

Branch `v9/fase1-local`, commit and push. The same new fleet from
Decision
73.

**Finding, live:** with Findings 1/2 from Decision 73 fixed,
the gateway's (`v9-mtls-ensaio`) `docker run -d` failed with `docker:
Error response from daemon: driver failed programming external
connectivity on endpoint v9-mtls-ensaio (...): Bind for 0.0.0.0:443
failed: port is already allocated.`

**Root cause:** Step 9 (`--exercise-start-stop`, run BEFORE
Step 10 in the same procedure) brings up `orchestrator.py`'s gateway
(a fixed name, `v9-mtls`, `-p 443:443` in remote mode since Decision
70)
and `stop_block` NEVER removes it on purpose (it stays running for
manual inspection/reuse by the next block) -- when Step 10 runs
afterward, on the SAME server instance, this script's container
(`v9-mtls-ensaio`, a DIFFERENT name) competes for the SAME port 443
on
the same host against the still-alive `v9-mtls`.

**Why this is a safe fix, never a STOP:** it is only operational
sequencing between two steps of the SAME rehearsal procedure (never
one
of the official 60/12 runs) -- it touches no pre-registered
criterion nor PINS.json.

**Fixed:** in remote mode (`GATEWAY_SSH` set), before bringing up
its own container, `rehearsal_handshake.sh` now also defensively
removes `v9-mtls` (a known, fixed name, from `orchestrator.py`)
-- never in local mode, where neither it nor the port conflict
exist.

**Tests:** no new test -- 158 unchanged.

**Validated live, end to end, after the 3 findings (Decisions
72/73/74) fixed:** `rehearsal_handshake.sh` closed out with
`RESULTADO FINAL: PASS -- 4/4 perfis, delta 0B nos dois sentidos`
for the 4 profiles (classico/pqc/hibrido-v8/hibrido-and), each one
really restarting the gateway -- the first time, in this
package's history, that Step 10 closes out end to end in a real
execution on
AWS.

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
scripts/rehearsal_handshake.sh`, `thesis/results/v9/DECISIONS.md`
(this Decision).

Moving on to Steps 11-14 of the procedure (same fleet, no
reapplying).

## 75. Amendment -- the real SAN (SERVER_IPS="<real EIP>,::1") dropped for the pilot, never applied; confirmed by content that the delivered certificates (certs/generated, mock-service-os/certs) are the same ones already embedded in the pinned images

Luciano's decision, in response to the Phase A resumption's report:
the real-SAN technique (PILOT_READINESS.md, section d/j-6) is
dropped for the pilot -- no image rebuild, no `make
certs`. The pilot uses the certificates exactly as they are,
embedded
in the pinned images. Before proceeding, a content-based proof (never
by assumption) was required that the certificates REALLY
delivered to the instances this round (certs/generated, mock-
service-os/certs) are the same ones embedded -- a read-only
investigation, with no rebuild, no AWS call.

**(a) certs/generated (disk) == certificates embedded in the pinned
images.** Extracted the 16 files (`.crt`, 5 per profile + each
profile's CA) from inside
`mockopin-v9-gateway:pinned` (`docker run
--entrypoint cat`) and compared by sha256 against
`thesis/results/v9/certs/generated/`: 16/16 identical byte for byte.
`mockopin-v9-proxy:latest` confirmed with the same 5 server
certificates as the gateway (identical sha256). No file
rebuilt for this check.

**(b) mock-service-os/certs -- internal consistency.** Nothing in
this directory is embedded in any image by design
(`business_server.go`: REAL_CERTS_DIR is always MOUNTED, never
copied into an image) -- the check possible here is chain
consistency, not comparison against a baked-in one. `ca.crt`
is the single trust anchor; `root_ca.crt`, `issuer_ca.crt`,
`op.crt`, `mtls.crt`, `client_one.crt`, `client_two.crt` verify
OK against `ca.crt` (`openssl verify -CAfile ca.crt`). The
directory has had no change since 2026-09-29, predating this entire
campaign.

**(c) why the real SAN was never necessary.** Every embedded server
certificate's SAN is `DNS:mtls, IP Address:127.0.0.1, IP
Address:0:0:0:0:0:0:0:1` -- loopback, never the real EIP; the
"<IP>" in Luciano's phrasing is always this generic placeholder,
never the pilot's public IP. `negtest/main.go.baseConfig()` fixes
`ServerName:
"mtls"` -- the client's hostname check always matches
against that fixed label (present in every certificate's SAN),
never against the dialed IP. This is why Step 10 (Decisions
72/73/74)
closed out with a 0B delta on a real network without the SAN
containing the EIP: neither the hostname check nor byte parity
(Decision 56: the IPv4's VALUE in the SAN never affects the DER
size) depends on it.
Rebuilding the image to change the SAN would never have had an
effect on
either of the two mechanisms that actually matter -- the proposal
correctly dropped.

**Why this is an Amendment, never a STOP:** no file was
altered by this investigation (only reading/comparing); no
pre-registered criterion changes; the pilot keeps using exactly the
the same certificates that were already there, with no mechanism
change at all.

**Tests:** none new (read-only investigation, not code).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/DECISIONS.md`
(this Decision).

## 76. The smoke gate (run_smoke_gate) never breaks on the control again: bytes diagnostic switched to stdlib, certs/generated delivered to the control, any exception in the diagnostic only marks needs_decision

Luciano's decision, item 2 of the same request: `run_smoke_gate`
runs from the CONTROL (Decision 59 -- SSHExecutor only really works
from there) and the bytes diagnostic
(`_bytes_diagnostic_for_profile` -> `ec.expected_handshake_bytes` ->
`ec._cert_der_size`) had, until now, depended on two assumptions
never
true there: the `cryptography` library installed, and
`certs/generated` present on disk. Without both, the diagnostic
(only that, never the official gate) would break the entire smoke
gate with
`ModuleNotFoundError`/`FileNotFoundError` before even reaching the
criteria that actually decide.

**Fixed, two independent points:**

1. `evaluate_criteria.py._cert_der_size` switched from
   `cryptography.x509.load_pem_x509_certificate(...).public_bytes
   (Encoding.DER)` to `ssl.PEM_cert_to_DER_cert(pem_text)` (stdlib
   -- a PEM is just DER in base64, decoding it never reserializes,
   the same size byte for byte; the test
   `test_bytes_diagnostic_zero_desvio_com_certs_reais_e_log_real`,
   which already exercised this entire path with real certs,
   keeps passing unchanged, proving the equivalence).
2. `deliver_source.py.CONTROL_FILES` gains
   `thesis/results/v9/certs/generated` (the same directory
   convention `CLIENT_ONLY_FILES` already used for the clients) --
   now the control receives the real certificates before
   any smoke gate runs.
3. `orchestrator.py.run_smoke_gate`: the loop that builds
   `bytes_diagnostic_rows` now wraps each call to
   `_bytes_diagnostic_for_profile` in a try/except -- any
   residual exception (in case points 1/2 above are not enough for
   some
   unforeseen reason) produces `{"ok": False, "note": "<exception>"}`
   for
   that profile, which automatically sets
   `bytes_diagnostic_needs_decision = True` via the already
   existing formula (`any(not r["ok"] ...)`) -- it never propagates
   and breaks the
   function. `smoke_ok` keeps being computed ONLY from
   `total_execucoes`/`failures`/`capture_proof_ok` (unchanged
   formula) -- the diagnostic never enters that reckoning, with or
   without an
   exception.

**Why this is a safe fix:** no pre-registered criterion
changes; the bytes diagnostic was always only that, a diagnostic
(Decision 55, item 3) -- never criterion 1's official gate.

**Tests, including Luciano's explicit request ("an error in the
diagnostic pauses and does not alter smoke_ok; the correct
diagnostic with a 0 delta passes"):**
`test_bytes_diagnostic_excecao_pausa_mas_nunca_quebra_o_smoke_gate`
(new) -- forces `_bytes_diagnostic_for_profile` to raise a
`FileNotFoundError` for the `pqc` profile, checks `run_smoke_gate`
NEVER propagates it (if it did, the test would not even reach the
asserts),
that that profile's row comes out `ok: False` with the exception in
the
`note`, that `bytes_diagnostic_needs_decision` comes out `True`, and
that
`smoke_ok` remains `True` (official criteria intact). The
pre-existing tests `test_bytes_diagnostic_zero_desvio_com_certs_reais_e
_log_real`/`test_porta_de_fumaca_sinaliza_decisao_pendente_sem_
bloquear_smoke_ok_quando_desvio_detectado` keep covering the
correct path (a 0 delta passes; a deviation detected with no
exception
also only pauses, never breaks). `test_control_files_inclui_certs_
generated` + `test_deliver_to_control_tarball_inclui_certs_
generated` (new) cover item 2. 161 tests in total (158 + 3
new: 1 in test_orchestrator.py, 2 in test_deliver_source.py).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/integration/
evaluate_criteria.py`, `thesis/results/v9/campaign/scripts/
{orchestrator.py,deliver_source.py}`,
`thesis/results/v9/campaign/tests/{test_orchestrator.py,
test_deliver_source.py}`, `thesis/results/v9/DECISIONS.md` (this
Decision).

## 77. Operator public-IP pre-check against the SSH ingress rule (check_operator_ip.py) -- added after Decision 72's real 8-minute block, root cause never confirmable retroactively

Luciano's decision, item 5 of the same request: investigate whether
the real
8-minute block (port 22/443, Decision 72, "infrastructure
note") could be explained by a change in the operator's public IP
NOT reflected in the control's SSH ingress rule
(`module.control.aws_vpc_security_group_ingress_rule.ssh["operator"]`,
`terraform/main.tf:131`, `ssh_ingress_cidrs =
{"operator": var.operator_ip_cidr}` -- a DIFFERENT rule from the
control->server/clients one, which uses the control's EIP and was
already
correct by design).

**Investigated, honestly, as far as possible:** the rule covers ONLY
port 22 (there is no rule giving the operator direct
access to port 443 on any instance -- any
unreachability of 443 observed from the operator would never be
evidence of a down rule, but of a port that was NEVER opened
to it by design). The IP is captured once per `terraform
apply` (the `TF_VAR_operator_ip_cidr` environment variable, never
persisted to a file) and never checked again afterward -- the
scratch script that generated that value (`env.sh`) always
recomputes it on the spot, never recording the historical value that
was
in force at the exact moment of the incident. Honest conclusion: it
is not possible to retroactively reconstruct
what the operator's IP was at the moment of the real block -- the
mechanism (a single capture, never re-checked) is
plausible, but NEVER proven to be the root cause of that specific
incident.

**Why the pre-check goes in anyway:** cheap safety,
regardless of proving that specific cause -- an 8-minute block cost
an entire fleet (teardown+reapply). Re-checking the IP before each
phase costs an HTTP call and, in the rare case of a change, a
`terraform apply -target` scoped to ONE resource.

**Implemented:** `check_operator_ip.py` (new,
`thesis/results/v9/campaign/scripts/`), run by the OPERATOR (never
by the control) before each phase that depends on SSH working.
`ensure_operator_ip_current(tf_dir)`: reads the current IP
(`curl https://checkip.amazonaws.com`, via `cli._run`, the same
test boundary as the entire package), reads the `cidr_ipv4`
currently recorded
in the state (`terraform show -json`, via `cli.run_terraform`,
locating
`module.control.aws_vpc_security_group_ingress_rule.ssh["operator"]`
in the `child_modules` tree); if they match, does nothing
(`{"changed": False}`); if they differ, reapplies ONLY that rule
(`terraform apply -auto-approve
-target='module.control.aws_vpc_security_group_ingress_rule.ssh
["operator"]' -var="operator_ip_cidr=<new>/32"`, never a full
fleet apply) and fails loudly (`RuntimeError`) if the reapply
itself fails -- never proceeding with a phase with a possibly
stale rule.

**Tests (new, `test_check_operator_ip.py`, cli._run/cli.run_
terraform stubbed, no real call):** reading the current IP
(success/loud failure if curl fails); reading the state's cidr
(success/loud failure if `terraform show` fails or the resource does
not exist in the state); `ensure_operator_ip_current` does not
reapply when
the IP matches (checks no `apply` call is fired);
reapplies when the IP differs (checks the exact `-target`/`-var` in
the real command); fails loudly if the reapply fails. 8 new tests.

**169 tests in total** (161 from Decision 76 + 8 here -- the final
number confirmed by running the entire suite after this Decision).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
scripts/check_operator_ip.py`,
`thesis/results/v9/campaign/tests/test_check_operator_ip.py`,
`thesis/results/v9/DECISIONS.md` (this Decision).

## 78. collect_artifacts.py rewritten for run_pilot's real FLAT structure -- the earlier version assumed a per-profile directory that never really existed

Luciano's decision, item 3 of the same request: the earlier
resumption's code research (before Decision 75) had already found
that
`collect_artifacts.py` expected a
`<remote_base_dir>/<profile>/` + per-profile `<profile>.sha256`
structure, but
`orchestrator.py.run_pilot` ALWAYS wrote to a single FLAT
directory (`piloto_combined.log`, `piloto_calls.json`, `criterio6_
execucoes.json`, `manifest.json`, `criterio1_capturas/*.log`, all
together, never split by profile) -- this function would never have
worked against the pilot's real output, only against the old
tests' wrong premise.

**Fixed:** `collect_block()` (per profile) removed; `collect_
pilot_data(control_ip, key_path, remote_dir, local_dir)` (new)
regenerates the sha256 manifest on the control over the ENTIRE
DIRECTORY
(`find . -type f | xargs sha256sum`, the same call as always, just
without
the `/<profile>` suffix), pulls everything with a single `scp -r`
step, and
checks the manifest again locally -- EXACTLY the same
guarantee as always (no change to the verification logic itself,
only to what it points at). CLI: `--remote-dir` (was
`--remote-base-dir`
+ `--profiles`) -- the same `--out` already passed to `orchestrator.py
run_pilot`/`run_smoke_gate`.

**Why this is a safe fix:** it does not touch `run_pilot`/`run_smoke_
gate` (Luciano's explicit request) nor any
pre-registered criterion -- it only fixes the COLLECTION side to
point to the format that has always really existed.

**Tests:** the entire `test_collect_artifacts.py` rewritten --
fixture `_setup_fake_remote` now builds a FLAT fake remote directory
(with
a `criterio1_capturas/` subdirectory, like the real one, but never
one per profile), the same 4 cases as always (correct hash, a
corrupted file detected, a missing file detected, the
verification-disabled mutant caught by both the corruption/missing
tests).
169 tests in total (unchanged -- 4 tests replacing 4 tests).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
scripts/collect_artifacts.py`,
`thesis/results/v9/campaign/tests/test_collect_artifacts.py`,
`thesis/results/v9/DECISIONS.md` (this Decision).

## 79. consolidate_v9_pilot.py (new) -- final consolidation in v8's structural pattern (a json source + an md report, a clean directory); the full data path proven locally BEFORE touching AWS again, as Luciano requested (item 4)

Luciano's decision, item 4 of the same request: before touching AWS
again, run locally (a local executor, minimum N) the FULL data
path -- `run_pilot`, collection, manifest, evaluation of the 7
criteria, consolidation -- and prove the consolidated result comes
out coherent.

**Consolidation written:** `consolidate_v9_pilot.py` (new,
`thesis/results/v9/campaign/scripts/`). Reuses `evaluate_
criteria.py` in-process (the SAME 7 calls `main()` already makes,
never reimplemented), and writes the source+derived PAIR in the same
STRUCTURAL pattern `consolidate_v8.py` already uses (a source JSON +
a derived Markdown, in a clean final directory, separate from
the campaign scratch) -- not the SAME calculations: v8 is a
continuous, multi-week, 3-region campaign with distributional
statistics
(median/bootstrap CI across many runs); v9's pilot is a
single pass/fail sanity check, already fully resolved
by `evaluate_criteria.py`'s pre-registered thresholds -- no
genuine additional statistic to inherit from there, only the form.
Writes, under `--out-dir`: `raw/` (an intact copy of the already
collected and
verified directory from `collect_artifacts.py`, never moved),
`criteria_evaluation.json` (the 7 criteria's raw output),
`RELATORIO_PILOTO.md` (a pass/fail table + failure notes).

**Full data path, proven LIVE, locally (`--mode
simulate`, LocalExecutor, seed 20261108, the full official grid --
never reduced):** `orchestrator.py --mode simulate --out
/tmp/v9_local_dry_run_piloto` closed out 60/60 runs + 12/12
captures; `consolidate_v9_pilot.py --collected-dir
/tmp/v9_local_dry_run_piloto --out-dir thesis/results/v9/piloto/
dados_oficiais/validacao-local-fase-b --run-label validacao-local-
fase-b` consolidated and came out **coherent**: criteria 1/4/5/6
(the ones locally assessable, PILOT_READINESS.md) closed out as a
real PASS
over real local data; criteria 2/3/7 (AWS-only) failed with a
clear "file missing" note, never breaking nor passing by
omission -- exactly the expected fail-closed behavior (Decision
33), never an inflated result. Evidence archived at
`thesis/results/v9/piloto/dados_oficiais/validacao-local-fase-b/`.

**Real finding, not a bug from this request -- a pre-existing gap,
never closed before this investigation:** `thesis/results/v9/integration/
producers/{criterio2_probe,criterio3_collector,criterio7_rtt}.py`
(the 3 dedicated files criteria 2/3/7 read from `--aws-dir`)
were NEVER wired into `orchestrator.py`/`deliver_source.py`/`PILOT_
READINESS.md` -- confirmed by a grep across the entire repository,
zero references outside themselves and `evaluate_criteria.py`.
Investigated
(read-only, with no file change):
- **criterio2_probe.py** runs on the SERVER, opens a listener on a
  NEW port (never 443/22, the only ones open today in the Security
  Group) -- it would need a new ingress rule, never
  authorized by any Decision so far.
- **criterio3_collector.py** is a purely local aggregator, but
  expects a JSON file PER RUN (`{"profile","route","ok"}`)
  that nothing in the real pipeline ever produces -- `run_pilot`
  only writes
  ONE combined `piloto_calls.json`, a different format, with no
  `"ok"` field; it would need a new adapter, never written.
- **criterio7_rtt.py** (`probe`) runs from any CLIENT against the
  already-open port 443 (no SG gap); (`pcap`) needs the `.pcap` from
  a dedicated capture (these, `_launch_gateway` already writes to
  `/tmp`
  on the server, never copied anywhere) + `tshark`
  available there (only confirmed inside the `mockopin-v9-
  measure` image, never on the bare host).

None of the 3 has an automated test (confirmed by grep -- no
file in `campaign/tests/` imports any of the three).

**Why this pilot continues WITHOUT wiring them now:** item 6 of
Luciano's same request enumerates Phase B's exact sequence -- apply,
PKI/
delivery, capture preflight, the smoke gate, the 60 runs, the 12
captures, collection, cleanup, consolidation, final check -- and that
list NEVER mentions criterion 2/3/7's dedicated producers.
Really wiring them would require opening a new ingress port on a
real AWS account (an infrastructure change outside the requested
scope),
writing an adapter never requested, and relying on tests never
written -- all of this within the SAME session that is about to run
real AWS, exactly the kind of change "doubt about whether it alters
what
is measured" (rule 7(e)) that this authorization asks to be handled
with
extra caution. It remains recorded here as a KNOWN,
pre-existing gap (never hidden) -- this round's pilot fully closes
out
criteria 1/4/5/6 (the only ones `run_pilot`/`run_
smoke_gate`/`collect_artifacts.py` actually feed) and honestly
reports
2/3/7 as lacking evidence, never as a PASS by omission. The decision
to wire them (and open the new port) remains pending on Luciano.

**Tests:** `test_consolidate_v9_pilot.py` (new, 4 tests) -- uses the
REAL output from `run_pilot(LocalExecutor(), ...)` as a fixture
(never
hand-built fake data): the 7 calls are reused in the right
order; criteria 2/3/7 fail with a clear note without breaking;
`raw/`+`criteria_evaluation.json`+`RELATORIO_PILOTO.md` come out
correct; it fails loudly if `piloto_combined.log` is missing;
the overall result correctly reflects that 1/4/5/6 pass and 2/3/7
do not.
173 tests in total (169 + 4).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
scripts/consolidate_v9_pilot.py`,
`thesis/results/v9/campaign/tests/test_consolidate_v9_pilot.py`,
`thesis/results/v9/piloto/dados_oficiais/validacao-local-fase-b/`
(evidence), `thesis/results/v9/DECISIONS.md` (this Decision).

## 80. PILOT_RUNBOOK.md (new) -- Phase B's complete procedure, at the same level of detail as INFRA_REHEARSAL.md, covering exactly the sequence from item 6 of Luciano's request

Luciano's decision, second part of item 4: write Phase B's procedure
(sequence, commands, which machine runs each step, expected output,
abort criterion), at the same level of detail as
`INFRA_REHEARSAL.md`, and follow it.

**Written:** `thesis/results/v9/campaign/PILOT_RUNBOOK.md` -- 16
steps (0-15), the same [OPERATOR]/[CONTROL] convention as the
infrastructure procedure, covering exactly the sequence Luciano
enumerated in item 6 (apply self_terminate_hours=4, PKI/delivery,
capture preflight, the smoke gate, the 60 runs, the 12 captures,
collection, cleanup, consolidation, a final check) plus two
new steps from this same round: the operator-IP pre-check (Decision
77, marked 🔁 at the points where it must be repeated -- after the
apply and
before the two longest blocks, Steps 10/11) and delivering
`certs/generated` to the control (Decision 76, Step 7). It explicitly
documents, in the header, the known gap in criteria 2/3/7
(Decision 79) -- never hidden, never treated as if it were
resolved.

**Why it is safe to follow this procedure:** each step reuses
already existing, tested scripts (`deliver_source.py`, `deliver_
images.py`, `pki_relay.py`, `orchestrator.py`, `collect_artifacts.py`,
`consolidate_v9_pilot.py`, `cleanup.py`, `emergency_stop.py`) --
no new command invented just for the procedure; the Terraform
resource count (28) is identical to the infrastructure rehearsal,
only the
`self_terminate_hours` parameter changes (1h -> 4h).

**Tests:** none new (a document, not code).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
PILOT_RUNBOOK.md`, `thesis/results/v9/DECISIONS.md` (this Decision).

## 81. Real finding, live, running Phase B for real (Step 10, the first time run_smoke_gate runs against a real fleet) -- capture_ready_check() always failed on a new fleet, for lacking an image it never delivered itself

Branch `v9/fase1-local`. A real apply (`self_terminate_hours=4`, 28
resources), Steps 0-9 of `PILOT_RUNBOOK.md` all green (a new fleet,
the operator's IP checked by Decision 77 live for the first time --
`{"ok": true, "changed": false}`; 4 images delivered and sha256
checked; `certs/generated` confirmed reaching the control for
the first time, Decision 76). Step 10 (the smoke gate) ran and
FAILED **before any run**:

```
"capture_preflight": {"go": false, "checks": [{"host": "<servidor>",
  "missing": ["imagem docker mockopin-v9-measure ausente (entregue
  por docker save/load, Decisao 55 item 2 -- nunca docker build na
  instancia)"]}]}
```

**Root cause:** `preflight.run_capture_preflight` (called by
`SSHExecutor.capture_ready_check()`, Decision 53/4c) only READS
whether
`mockopin-v9-measure` already exists on the server (`docker image
inspect`)
-- never delivers it. `dedicated_capture()` (Decision 55, item 2)
delivers
that image, but only LAZILY, the first time IT runs -- and
`dedicated_capture` only runs AFTER the smoke gate passes (inside
`run_smoke_gate` itself, in the 4 `smoke_capture_proof`). On a new
fleet,
nothing had ever delivered `measure` before this point --
`capture_ready_check()` always failed, for lacking an image
that it never tries to deliver itself. Never caught before because
`run_smoke_gate`/`capture_ready_check` had NEVER run against a
real fleet in this history -- `INFRA_REHEARSAL.md` only exercises
`--exercise-start-stop`/`rehearsal_handshake.sh`, neither of which
touches capture.

**Why this is a safe fix, never a STOP (this authorization's rule
7(a) does not apply -- this is a code bug, never a
pre-registered criterion failing with already-correct code):**
`_deliver_image` is idempotent (sha256 checked at both hops,
Decision 68) and it is exactly the same mechanism `dedicated_capture`
already uses for this SAME image -- it only moves the delivery up to
preflight time instead of waiting for the first real use. No
pre-registered criterion changes, no measurement is affected.

**Fixed:** `SSHExecutor.capture_ready_check()` now calls
`self._deliver_image("measure", self._server_ip())` BEFORE running
`preflight.run_capture_preflight(...)` -- preflight becomes
self-sufficient (guarantees what it checks), never merely passive.

**Tests (new):**
`test_capture_ready_check_entrega_measure_antes_de_rodar_o_probe`
(checks the exact ORDER: delivery before the probe, with the right
host) +
`test_mutante_capture_ready_check_nunca_entrega_measure_e_pego`
(a mutant reverting to the old behavior, confirming the real
test depended on the delivery). 175 tests in total (173 + 2).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
scripts/orchestrator.py`,
`thesis/results/v9/campaign/tests/test_orchestrator.py`,
`thesis/results/v9/DECISIONS.md` (this Decision).

Redelivering `orchestrator.py` to the control (same fleet, no
reapplying) and repeating Step 10.

## 82. Real STOP in Phase B, Step 10 (resumed) -- the gateway's business layer (HTTP_MODE=business) never had, anywhere in this v9 package, a delivery path for the real AS/API backend to any instance -- every real run that needs JWKS fails with DNS unresolved

**Result of Step 10 reapplied (after Decision 81's fix):** the
capture preflight passed; the 12 runs started; the readiness
probe (`readiness_probe`, which triggers the FULL REAL flow
via `campaign_client_runner.py`/`opin_flow.py` -- JWKS, AS, RS, never
just the mTLS handshake) failed for `hibrido-v8`/`L0` on both
internal attempts of
`latency_automation.run_once_timed_with_retry`:

```
RuntimeError: readiness_probe hibrido-v8/L0: execucao de settling falhou:
settling_hibrido-v8_L0 failed on both attempts -- stopping (not retrying
further; this is no longer the known rare race, treat as a new failure).
Last error: Expecting value: line 1 column 1 (char 0)
```

**Root cause, confirmed by reading the gateway's real log on the
server (never assumed):**

```
2026/11/08 19:31:00 http: proxy error: dial tcp: lookup auth on 172.31.0.2:53: no such host
2026/11/08 19:31:00 INFO access log ... host=auth.local request=/jwks method=GET status=502 ...
```

The mTLS handshake itself always passes ("connection OK", 3x in the
first few seconds) -- what fails is the BUSINESS layer
(`HTTP_MODE=business`, `business.go`, reinstated by Decision 17 "to
run the real end-to-end flow of 44 HTTP calls"): every
call to `auth.local/*` is a real reverse proxy to
`AUTH_URI` (default `http://auth:3000`, `business.go` line 40) --
"auth" is a hostname that ONLY exists as a Docker network alias in
the LOCAL validation (`insurance-server-lambdas_default`, the same
network
Decision 70 had already identified as exclusive to local
validation). On a real EC2 instance, "auth" never resolves (the
VPC's DNS resolver returns NXDOMAIN) -- NO call that needs JWKS (or
`api.local`/`matls-api.local`, a proxy to `API_GATEWAY_URI`)
would ever work in a real run, not just this one.

**Why this was never caught before:** `INFRA_REHEARSAL.md`
(`--exercise-start-stop`) never calls `readiness_probe`/
`run_execution` -- only `start_block`/`stop_block`. `rehearsal_
handshake.sh` (Step 10 of that procedure) tests ONLY the mTLS
handshake
(negtest), never the business HTTP flow. This Phase B Step 10
(the smoke gate, which calls `run_pilot`->`readiness_probe`->
`campaign_client_runner.py`->`opin_flow.py`, the REAL business flow)
is, confirmed by searching this entire project's history, THE
FIRST TIME any real business HTTP call runs against
a real EC2 instance.

**Confirmed, by reading `thesis/results/v8/campaign/scripts/
deliver_images.sh`:** v8 had ALREADY solved this EXACT problem for
its
campaign -- it delivers 4 SERVER images
(`insurance-server-lambdas-mtls`,
`insurance-server-lambdas-auth`, `raidiam-insurance-lambdas` [the
API],
`insurance-server-lambdas-mongo_seed`) to each real server, via the
SAME 2-hop relay. v9 never ported this mechanism -- `PINS.json`/
`deliver_images.py` only deliver gateway/proxy/pqc-signer/measure,
never auth/mockapi/mongo_seed. These images also do NOT exist today
locally (`docker images` lists no `insurance-server-
lambdas-*`) -- they would need to be (re)built (`docker-compose
build`
inside `mock-service-os/`) before any delivery.

**Why this is a STOP, never a fix-and-retry (this authorization's
rule
6/7(e)):** it is not a 1-2 line bug like Decisions 70-74/81 -- it
requires: (1) (re)building 3-4 entire Docker images never built
before this round; (2) a NEW delivery mechanism
(`deliver_images.py`/`PINS.json` never knew about them);
(3) orchestrating this backend's containers on the server alongside
the
gateway (`_launch_gateway`/`start_block` bring up nothing today
beyond
gateway/proxy/pqc-signer); (4) deciding the correct `AUTH_URI`/`API_GATEWAY_
URI` for this new arrangement. Any of these changes
DIRECTLY alters what is executed during a real measurement --
exactly the "doubt about whether the fix alters what is measured"
that
rule 7(e) asks to be handled with a stop, never with an attempt
within
the same session.

**Action taken, following rule 6 (fleet never idle):** no
new attempt within this fleet -- immediate teardown (`emergency_
stop.py` dry mode confirmed the expected 5 instances/5 EIPs/3 SGs/4
key pairs;
`cleanup.py --tf-dir ../../terraform --profile mockopin-pqc
--release-eips --force` reported `"all_clean": true`, zero drift);
an independent final check (12 `describe-*` calls, 3 regions)
confirmed empty.

**Decisions pending from Luciano (none taken on my own):**
1. Port v8's auth/mockapi/mongo_seed backend to v9 (rebuild
   the images, a new delivery mechanism, a new orchestration step
   on the server) -- the most complete path, but the most expensive
   in time.
2. Decide whether v9's pilot can/should measure only the mTLS layer
   (without the full business flow) -- it would require changing
   `opin_flow.py`/
   `campaign_client_runner.py` to skip JWKS/AS/RS in that mode, which
   changes what is measured (criteria 4/6 depend on the full flow,
   40/44 HTTP calls) -- probably not feasible without re-registering
   criteria.
3. Some third option Luciano prefers (e.g., a minimal AS/API
   stub, simpler than porting all of v8, if he judges that
   this does not materially alter what is measured).

**Tests:** none new (an infrastructure/architecture finding, never
a code bug fixable with this package's existing tests --
no Python function needs to change until Luciano decides the
path).

**Cost of this attempt:** fleet alive for approximately 25-30
minutes (real apply ~19:1x UTC, teardown confirmed ~19:3x UTC) --
well within the US$5 ceiling, adding to Phase A's spend (~US$0,55).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/DECISIONS.md`
(this Decision), evidence in `thesis/results/v9/piloto/
ensaio_fase_b_real/`.

## 83. Amendment -- v8's business backend (auth/mockapi/mongo_seed + psql/localstack/mongodb) genuinely ported to v9's pilot, closing Decision 82's real gap

Luciano's decision, item 1 of the post-Decision-82 request: port
what v8
already did -- extra server images, the Docker network with
aliases, the bring-up order, the health checks and the shutdown,
using the same v8 Dockerfiles/sources, delivered via the same
2-hop mechanism, with the backend coming up BEFORE the gateway with
a real readiness probe, included in stop/dedicated capture/cleanup,
and
a CPU/memory comparison against v8.

**Key finding, investigated before writing any new line:**
`orchestrator.py.start_block` ALREADY HAD the entire mechanism
written
(Decision 49) -- `docker compose --profile main up -d --force-
recreate auth mongo_seed mockapi` + the SAME real health checks
(curl `/jwks` for `auth`, grep `"Startup completed"` in `mockapi`'s
log) -- but GATED by `if self.local_shim_bridge_join:`,
never running in the real remote case (`start_
block`'s own docstring already recorded this as an "honest
limitation... a separate gap
for this round"). The fix was NEVER rewriting the orchestration from
scratch -- it was unlocking the `if`, choosing the right `cd` per
mode (the same
convention already used for `real_certs_mount`, Decision 58), and
delivering the
images/files that were missing.

**Images -- 6 NEW entries in PINS.json (none existing
changed), the same content-based identity scheme (Decision 68):**
`psql`/`localstack`/`mongodb` are STOCK images, pinned by the
EXACT digest `insurance-server-lambdas/docker-compose.yml` already
fixes -- never rebuilt, only verified. `auth`/`mongo_seed`
REBUILT this round from the CURRENT source (`mock-service-
os/mock_as` and `mock_as/mongo-seed`, `docker compose --profile main
build`, 2026-11-08) -- confirmed by `git log` that these
directories' working tree was clean (no pending commit) at build
time. **`mockapi` (`raidiam-insurance-lambdas`), an honest
exception:** an EXISTING image (created 2026-09-24), NEVER rebuilt.
`insurance-server-lambdas/Dockerfile` changed on 2026-10-21, but
only pinning digests of the SAME base images (gradle:5.3.1-jdk11-slim/
amazonlinux:2) -- `git log` confirms zero change to `src/`/`build.
gradle` since 2026-09-24. Also, this image's REAL `Entrypoint`
(`java -jar /home/app/application.jar`) never matches what
this Dockerfile would produce (GraalVM native-image, `/home/
application/server`) -- proof that this image was never built
by it; the documented build process (`./gradlew optimizedDocker
Build`) is broken today (the Shadow plugin requires Gradle 8+, the
project's
wrapper pinned to an incompatible version, thesis/results/v4/
DECISIONS.md). Kept as it was, with the divergence explicitly
recorded -- never hidden, never rebuilt "to pretend it matches."
The decision to really unblock the build remains pending on
Luciano.

**Delivery (the same mechanism as always, nothing new):**
`deliver_images.py.BACKEND_IMAGE_KEYS` (new, 6 keys) adds to the
existing `ALL_IMAGE_KEYS` -- the first hop (operator -> control)
identical. Second hop: `SSHExecutor._deliver_backend_images()`
(new) calls `_deliver_image` (Decision 68, unchanged) for each one,
TO THE SERVER, with an idempotency guard (`self._backend_
delivered`) -- never redelivering ~6GB per block, only once per
fleet
(the backend images never change binary per profile, only the
CONTENT `docker compose` itself seeds). `deliver_source.py`
gains `SERVER_ONLY_FILES` (new) -- `docker-compose.yml` +
`pg_hba.conf`/`mongod.conf`/`participants.json`/`software_statement.
json`/`setup_ssm.sh`/`ssa/*.json` -- delivered ONLY to the server
(never
clients), never the build source (the images already arrive
pinned).

**Orchestration (`start_block`, unlocked):** the backend comes up
BEFORE the
gateway, with `CRYPTO_PROFILE` translated (`BACKEND_CRYPTO_PROFILE_ENV`,
Decision 49, unchanged) and the SAME 2 real health checks as always
(curl `/jwks` for `auth`; grep `"Startup completed"` for `mockapi`,
which really takes ~30s). A NEW fail-closed (it never existed
before, not even in the local case): if `docker compose up` fails,
it raises
a `RuntimeError` BEFORE the gateway tries to come up -- the earlier
code simply ignored the `returncode`. `_launch_gateway`: the
`insurance-server-lambdas_default` network + the aliases (`auth.local`/
`matls-api.local`/etc.) are now used in BOTH modes (before, only
local) -- in the real remote case, the gateway ALSO publishes
`-p 443:443`
(neither is mutually exclusive in Docker). `stop_block`:
now also stops (never `down` -- never tears down the network the
gateway uses) the backend, freeing up CPU/memory between blocks (the
next `start_block`, for any profile, always does `--force-
recreate` again). `dedicated_capture` already calls `start_block`
first -- it gets the backend for free, with no change of its own.

**CPU/memory (Luciano's explicit request, item 1):**
`SSHExecutor._sample_cpu_mem(host)` (new) -- the SAME format
`campaign_run.py._sample_cpu_mem_steal()` already uses (`/proc/stat`'s
`cpu` line + `/proc/meminfo`, never `docker stats`, for the same
reason
as always: `steal` is only visible at the HOST level). One sample
before and
one after each backend bring-up, accumulated in `self.cpu_mem_
samples`, included in `manifest.json` (`run_pilot`) -- the real
comparison against v8 is left for consolidation/the final report,
after
the pilot really runs.

**Tests (new, 10 + extending the `_fake_pins`/`_FAKE_*` fixtures
for the 6 new keys across ALL existing delivery tests):**
`_deliver_backend_images` delivers the 6 and is idempotent (+ a
mutant that
removes the guard and is caught); `start_block` brings up the
backend BEFORE the
gateway with the 2 real health checks, uses the correctly
translated `CRYPTO_PROFILE`, and aborts BEFORE the gateway if the
compose fails;
`stop_block` also stops the backend, never with `down`; `_sample_cpu_
mem` reads `/proc/stat`+`/proc/meminfo` and never breaks if SSH
fails;
`start_block` records the 2 samples (before/after). Pre-existing
tests
updated to reflect the new real delivery count/order (the
gateway is no longer the FIRST image delivered -- the
backend comes first) and the network now present in both modes. 186
tests in total (175 + 11: 10 new + 1 rewritten from `==3` to
`== {the original 3} | {the backend's 6}`).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
PINS.json`, `thesis/results/v9/campaign/scripts/
{orchestrator.py,deliver_images.py,deliver_source.py}`,
`thesis/results/v9/campaign/tests/{test_orchestrator.py,
test_deliver_source.py}`, `thesis/results/v9/DECISIONS.md` (this
Decision).

## 84. DEPENDENCY_MAP.md (item 2) + local validation in a CLEAN environment (item 3) -- a real finding in the validation itself, fixed before touching AWS

**Item 2:** `thesis/results/v9/campaign/DEPENDENCY_MAP.md` (new) --
a complete hostname/port/volume/env/file/image table for
the gateway, proxy, pqc-signer, and the business backend (Decision
83),
stating where each one resolves and who provides it on a real AWS.
Conclusion:
no dependency listed is "local only" -- the last one that was
(AUTH_URI/API_GATEWAY_URI) was fixed by Decision 83 itself.

**Item 3: local validation in a CLEAN environment, a real finding.**
Tested
WITHOUT depending on this machine's development environment: an
ISOLATED
directory (`/tmp/v9_clean_validation/`) with ONLY what
`deliver_source.py`
actually delivers (`SERVER_ONLY_FILES` + `mock-service-os/certs`),
no build source present, a compose project with its OWN name
(`-p v9cleantest`, never the default name that would collide with
this machine's development containers).

**Real finding, live, in the validation itself:** the 1st attempt,
with
`-p v9cleantest` but WITHOUT re-tagging the pre-built images for
the name this project expected (`v9cleantest-auth`/`v9cleantest-
mongo_seed`), made `docker compose up` try to BUILD (never
reuse the already-loaded pinned image) -- `additional privileges
requested: pass "--allow=fs.read=..\mock-service-os"`, because the
build context (`mock_as/`) does not exist in the isolated directory.
**This proves, live, why the real mechanism (no `-p`, Decision
83) works:** on the real server, `docker load` preserves the
EXACT name (`insurance-server-lambdas-auth:latest`) and `docker
compose`
(default project = directory name, also `insurance-server-
lambdas`) finds this image ALREADY PRESENT under the expected name
-- it never tries to build. Confirmed by temporarily re-tagging the
pinned images to the name project `v9cleantest` expected
(`docker tag`, never `docker build`/`docker prune` -- the
original tags remained intact, only the temporary ones removed at
the end): the 2nd attempt created the 6 containers with no build
attempt at all, both real health checks passed (`curl /jwks` -> a
real
JWKS returned; `docker logs mockapi | grep "Startup completed"` ->
found on the 4th attempt), and v9's gateway (`mockopin-v9-gateway`),
joined to the same isolated network with the same aliases as always,
came up
and correctly rejected (mTLS enforced, never a bug) a connection
with no client certificate.

**Why not the full 60 runs via the real SSHExecutor:** the local
validation mechanism already existing for the entire package
(`local_shim_bridge_join=True`, Decision 49, already extensive test
coverage) depends on the DEFAULT network/container name
(`insurance-
server-lambdas_default`), which deliberately collides with this
machine's
development environment -- running the official 60 runs
against a FULLY isolated environment would require rewriting this
shim
for an isolated compose project, just for this test, never reused --
disproportionate to what remains to be proven (the backend's
delivery+start MECHANISM, the part never before exercised, is
already proven live
above). The table's static check (item 2) + the real run on an
isolated network with no inherited environment (above) cover item
3's
request in this decision, with the honest reason recorded -- never
hidden.

**Cleanup:** the `v9cleantest` project's containers/network/volumes
removed (`docker compose down -v`, only this test's resources,
never `docker prune`); the temporary tags removed (`docker rmi`
reported only "Untagged", never "Deleted" -- the original pinned
images remained intact, confirmed by the same ID before/
after); this machine's development containers, temporarily stopped
just to free up the conflicting host ports
during the test, restarted at the end.

**Tests:** none new (manual infrastructure/
environment validation, never testable by pytest -- it needs real
Docker).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
DEPENDENCY_MAP.md`, `thesis/results/v9/DECISIONS.md` (this
Decision).

## 85. The 3 dedicated producers for criteria 2/3/7 wired into the real pipeline and the consolidator -- Decision 79's gap closed

Luciano's decision, item 4 of the same post-Decision-82 request:
wire
`criterio2_probe.py`/`criterio3_collector.py`/`criterio7_rtt.py`
into the
real pipeline and the consolidator, with tests and mutants, so the
consolidated result produces real values for the 7 criteria, never
"no
evidence."

**Real findings, fixed in the producers themselves (never
reinvented):** neither `criterio2_probe.py` nor `criterio7_rtt.py`
had any way to run -- both call `tshark` bare, but the real server
NEVER has that binary on the host's PATH (only inside
`mockopin-v9-measure`, the SAME pinned image `dedicated_capture`
already uses for criterion 1). Fixed in both: `tshark` now runs via
`docker run --rm -v /tmp:/tmp:ro --entrypoint tshark mockopin-v9-
measure ...` -- never rebuilding nor changing the image. In
`criterio7_rtt.py`, the RTT math (median of SYN->SYN-ACK) was
factored into a new pure function (`rtt_from_syn_synack_times`),
reused
both by the local path (bare tshark, if it ever exists) and
by the real path (tshark via docker) -- never duplicated.

**Criterion 2 (real initcwnd) -- a new port:** the pilot's SG only
opened
443/22 -- criterio2_probe.py needs a DEDICATED port for
the test listener. `thesis/results/v9/terraform/modules/campaign_
instance/main.tf` gains `aws_vpc_security_group_ingress_rule.
criterio2_probe` (port 9876, the SAME `gateway_ingress_cidrs` port
443 already uses -- never broader) -- 3 new resources (one per
client), terraform rises from 28 to 31 total resources.

**Criterion 3 (zero errors at L325) -- an adapter that reuses the
evaluator:** `criterio3_collector.py` expects a JSON file per
run (`{"profile","route","ok"}`) that nothing in the real pipeline
produces -- `run_pilot` only writes ONE combined `piloto_calls.json`,
with no `"ok"` field. Instead of inventing a new error detector, the
adapter (`dedicated_criteria.build_criterio3`) calls
`evaluate_criteria.criterion_4_counts` (already written, already
tested --
compares each run's real HTTP/mTLS counts against the
expected) and reuses the `ok` IT already computes per run, filtering
only to `route == "L325"`. `criterio3_collector.py` gains `collect_l325_
execucoes()` (factored out of `main()`, never duplicated) to become
importable.

**Criterion 7 (per-route RTT) -- both channels:** the `probe`
channel
(a real TCP connection, from the CLIENT against the already-open
port 443 -- no
new port) + the `pcap` channel (reuses the dedicated pcaps
`_launch_gateway`/`dedicated_capture` ALREADY write to `/tmp/criterio1_
<profile>_<route>.pcap` on the server -- no new capture, any
profile proves the channel, SYN/SYN-ACK never depends on the
cryptographic profile).

**Orchestration -- `dedicated_criteria.py` (new), runs FROM THE
CONTROL** (the same convention as `orchestrator.py` -- only the
control reaches the
server/clients, Decision 59): `run_all(executor, collected_dir,
out_dir)` calls the 3, in order (criterion 3 first, it never depends
on
the network; then 2 and 7, which need the fleet alive), writing the
3
new files in the SAME directory `run_pilot --out` already used --
a single `collect_artifacts.py` run afterward brings everything
together. Its own CLI
(`--inventory-json`/`--ssh-key`/`--dir`), delivered to the control
via
`CONTROL_FILES` (a new item, together with `deliver_images.py` -- a
real finding, never delivered before: `orchestrator.py` has imported
`deliver_
images` since Decision 83 for `BACKEND_IMAGE_KEYS`, but it had never
been added to `CONTROL_FILES` -- `python3 orchestrator.py --help`
would break on the real control with `ModuleNotFoundError`, never
caught
before because the tests import both modules in the SAME local
Python process). `criterio2_probe.py` delivered only to the SERVER
(`SERVER_ONLY_FILES`); `criterio7_rtt.py` delivered to BOTH (`COMMON_
FILES` -- runs on both sides).

**Consolidator:** no change needed -- `consolidate_v9_
pilot.py`/`evaluate_criteria.py` already call the 7 criteria
unconditionally against `--aws-dir`; once the 3 files exist
in the collected directory, criteria 2/3/7 become
genuinely evaluated, no longer "no evidence" by design.

**`PILOT_RUNBOOK.md` updated:** resource count 28->31; a new
Step 11.5 (dedicated producers, between the real pilot and the
collection);
Step 13 updated -- the 7 criteria now have a real expected
result, never "no evidence" by design (if that happens, it is
a sign Step 11.5 failed, not a normal result).

**Tests (new, with explicitly requested mutants):**
`test_producers.py` (7 tests -- both producers' `_tshark_argv`
runs via docker, never bare, with a mutant that reverts it;
`rtt_from_syn_
synack_times` correctly computes the median, never breaks on empty,
with a
mean-vs-median mutant; `collect_l325_execucoes` filters the right
route); `test_dedicated_criteria.py` (7 tests -- `build_criterio3`
really reuses `criterion_4_counts` and filters L325, with a mutant
that
forgets the filter; `run_criterio2` brings up the probe, triggers
the right client, fails loudly if the file never appears, with a
mutant that never waits; `run_criterio7` runs the probe on the right
client and the pcap on the
right server, fails loudly if no dedicated pcap exists). 199
tests in total (186 + 13: 7 producers + 7 dedicated_criteria - 1
already counted).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/terraform/
modules/campaign_instance/main.tf`,
`thesis/results/v9/integration/producers/{criterio2_probe,
criterio3_collector,criterio7_rtt}.py`,
`thesis/results/v9/campaign/scripts/
{dedicated_criteria.py (new),deliver_source.py}`,
`thesis/results/v9/campaign/tests/
{test_producers.py (new),test_dedicated_criteria.py (new)}`,
`thesis/results/v9/campaign/PILOT_RUNBOOK.md`,
`thesis/results/v9/DECISIONS.md` (this Decision).

## 86. Real finding, live, running Phase B again (Step 8) -- scp's fixed timeout (140s) never designed for the backend's images, timed out delivering localstack.tar (1.8GB)

Branch `v9/fase1-local`. A new fleet applied (31 resources, `self_
terminate_hours=4`), Steps 0-7 all green (the operator's IP
checked, the key delivered, Docker ready on the 5 instances,
`deliver_
source.py` confirmed the new files from Decisions 83/85 arriving
correctly, `dedicated_criteria.py`/`orchestrator.py` confirmed
really importing on the control -- see note below). Step 8
(`deliver_images.py`, now with 10 images -- the 4 original + the 6
from the backend) failed delivering `localstack.tar` (1.8GB):

```
subprocess.TimeoutExpired: Command [... 'scp' ... 'localstack.tar' ...]
timed out after 140 seconds
```

**Root cause:** `cli.run_scp`'s timeout (`connect_timeout=20` default
-> a total process timeout of 140s) had been measured and calibrated only
against the 4 original images (~140MB total, Decision 59/68) -- never
designed for the backend's 6 images (Decision 83), some of ~1.8GB.
The real bandwidth was GOOD (`psql.tar`, 642MB, completed within the
same 140s limit BEFORE `localstack.tar` -- >4.5MB/s measured
live) -- the problem was never the network, it was the fixed timeout never
scaling with the file's real size.

**Fixed:** `deliver_images.py` gains `_scp_timeout_for_bytes`
(new) -- it computes the `connect_timeout` (which `cli.run_scp` already uses as
the base for the process's total timeout) PROPORTIONAL to the `.tar`'s real
size, with a conservative floor of 24Mbps (well below the real
bandwidth
observed, never the usual fixed one). Passed explicitly in the
`cli.run_scp` call for the main tar (never for the `.sha256`,
tiny).

**Why this is a safe fix, never a STOP:** it does not touch any
identity/content verification (sha256/layers/config remain
exactly as Decision 68 defined them) -- it only gives enough time
for the
real scp to finish before the process thinks it has hung. No
pre-registered criterion changes.

**Tests (new):** `test_scp_timeout_for_bytes_escala_com_tamanho_
real` (+ a mutant reverting to the fixed value, caught) + `test_deliver_images_
usa_timeout_proporcional_no_scp_do_tar` (checks the exact
`ConnectTimeout=N` in scp's real argv). 202 tests in total (199 + 3).

**State of the control at the time of the finding (never needed
manual cleanup -- scp overwrites the destination):** `gateway`/`proxy`/`pqc-
signer`/`measure`/`psql` already delivered and verified (sha256 OK);
`localstack.tar` partial (470MB of ~1.8GB) -- will be overwritten by
the redelivery. Control's disk with 28GB free, a huge margin.

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
scripts/deliver_images.py`,
`thesis/results/v9/campaign/tests/test_deliver_images.py`,
`thesis/results/v9/DECISIONS.md` (this Decision).

Redelivering the remaining images (the same fleet, without reapplying).

## 87. Real finding, live, running Phase B again (Step 10) -- stock images (psql/localstack/mongodb) should never have gone through the save/load-by-name mechanism

Branch `v9/fase1-local`. After Decision 86's finding (fixed,
remaining images delivered, sha256_ok:true for the 5), Step 10
(the smoke gate) failed again, now inside `start_block`:

```
RuntimeError: _deliver_image(psql, <servidor>): identidade nao
confere (layers_ok=False, config_ok=False, binary_ok=True) --
abortando ANTES de qualquer execucao
```

**Investigated live, never assumed:** reproduced locally in a
CLEAN
`docker:25-dind` (a new container, never used before): `docker
save postgres@sha256:ca0bd...` (a reference ONLY by digest, never
tagged by name) + `docker load` on the dind -> `docker images
--digests` shows `<none> <none> <none>` -- NO nameable reference
survives save/load, only the loose Image ID ("Loaded image
ID: sha256:..."). `docker image inspect postgres@sha256:...` on the
dind returns `Error response from daemon: No such image` -- exactly the
`actual_layers=None`/`config=None` (the command failed, never a
real content mismatch) that produces `layers_ok=False,
config_ok=False` without crashing the process.

**Root cause:** `psql`/`localstack`/`mongodb` (Decision 83) are
STOCK images, referenced in PINS.json ONLY by digest
(`postgres@sha256:...` etc, to match exactly what
`docker-compose.yml` already pins) -- but the delivery/
verification mechanism BY NAME (`_deliver_image`, Decision 68)
requires a
nameable reference surviving `docker load`, which NEVER
happens for a digest-only image, confirmed live above.

**Fix -- never re-tag and force it, the design reconsidered
(simpler, more correct):** `psql`/`localstack`/`mongodb` LEAVE
the 2-hop mechanism entirely -- removed from `PINS.json`
(they never needed a pin of their OWN: the exact digest is already
fixed
INSIDE `docker-compose.yml`, the correct source of truth) and from
`deliver_images.py.BACKEND_IMAGE_KEYS` (now only `auth`/`mongo_seed`/
`mockapi` -- EXACTLY the 3 CUSTOM images Luciano explicitly
requested, "extra server images (auth, mockapi,
mongo_seed)"). `docker compose up` itself already resolves the 3
STOCK ones correctly -- pulling directly from the public registry
(egress
SG open, confirmed in `main.tf`), the same exact digest the
compose.yml already fixes, deterministic content either way (pull
or load). No pinned CUSTOM image was touched -- `auth`/`mongo_
seed`/`mockapi` were already delivered and verified (sha256_ok: true)
on the same fleet, and never needed redelivery.

**Collateral finding, fixed in the same step:** editing
this fix itself (a Python script writing PINS.json in text mode on
Windows) reintroduced CRLF into the file -- caught immediately by
`test_no_crlf_sweep.py` (Decision 69) before any commit,
fixed by writing in binary mode.

**Why this is a safe fix, never a STOP:** it simplifies the
design (3 images delivered over 2 hops, never 6), never touches
any content verification of the CUSTOM images, and the pin for the 3
STOCK ones still exists -- just in the right place (`docker-compose.
yml`, where it always was, never duplicated in PINS.json). No
pre-registered criterion changes.

**Tests:** the entire suite runs unchanged (`test_orchestrator.py`
computes `BACKEND_IMAGE_KEYS` dynamically, never hardcoded -- the
tests adapt automatically to the smaller list). 202 tests in
total (unchanged).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
PINS.json`, `thesis/results/v9/campaign/scripts/
{orchestrator.py,deliver_images.py}`,
`thesis/results/v9/campaign/DEPENDENCY_MAP.md`,
`thesis/results/v9/DECISIONS.md` (this Decision).

Redelivering only the CODE (orchestrator.py/deliver_images.py/PINS.json
-- the CUSTOM images are already on the control, verified) and repeating
Step 10.

## 88. Real finding, live, running Phase B again (Step 10, still) -- mongo_seed/mockapi's Env in PINS.json was TRUNCATED (a transcription error of this very session, never a system bug)

Branch `v9/fase1-local`. With Decision 87 fixed, Step 10 failed
again, now on `mongo_seed`:

```
RuntimeError: _deliver_image(mongo_seed, <servidor>): identidade nao
confere (layers_ok=True, config_ok=False, binary_ok=True) --
abortando ANTES de qualquer execucao
```

**Investigated live, never assumed:** `layers_ok=True` (the
image's content arrived correctly -- this is not a bug in the
delivery mechanism,
Decision 68, which keeps working). `docker image inspect
insurance-server-lambdas-mongo_seed --format '{{json .Config}}'`
run directly on the real server returns an `Env` with 10 entries
(`JSYAML_VERSION`/`JSYAML_CHECKSUM`/`MONGO_REPO`/`HOME`/
`GLIBC_TUNABLES` among them) -- the `Env` pinned in `PINS.json`
(Decision 83) only had 5, missing exactly those 5. Also checked
`mockapi`: pinned with 3 entries, the real image has 6 (missing `LANG`/
`LANGUAGE`/`LC_ALL`). `auth` checked -- that one was correct (3 of
3, never truncated).

**Root cause:** a TRANSCRIPTION error of this very session, writing
`PINS.json` in Decision 83 -- each image's complete `Env` had
already
been captured correctly in local files (`docker image
inspect ... --format '{{json .Config}}'`, saved before writing
the PINS.json), but, when transcribing into JSON, the
`mongo_seed`/`mockapi` lists were shortened by mistake (never a
problem with Docker, the network, or the identity mechanism itself --
`auth`, transcribed correctly, never failed).

**Fixed:** `PINS.json.images.{mongo_seed,mockapi}.config_subset.
Env` rewritten with the COMPLETE list, copied directly from the
inspection files already saved locally (never retyped) --
`mongo_seed` 5->10 entries, `mockapi` 3->6 entries.

**Why this is a safe fix, never a STOP:** the images' real CONTENT
never changed -- only the PIN was wrong (a subset of what the
real image always had). Fixing the pin to match the REAL image
is exactly the function of an Amendment (Decision 55, item 1) -- it
never
loosens the verification, only makes it EXACT rather than incomplete.

**Tests:** the entire suite runs unchanged (no test fixture
hardcodes these specific Env values). 202 tests in total
(unchanged).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
PINS.json`, `thesis/results/v9/DECISIONS.md` (this Decision).

Redelivering only the CODE (PINS.json fixed -- no image
needs redelivery, the real content never changed) and repeating
Step 10.

## 89. Real finding, live, running Phase B again (Step 10, the backend comes up end-to-end for the first time) -- setup_ssm.sh lost its executable bit on the remote path, only on Windows

Branch `v9/fase1-local`. With Decision 88 fixed, Step 10 advanced
MUCH further -- the 4 backend images came up, `localstack` was
skipped by compose successfully (confirming Decision 87 live), but
`auth` never came up: `Container insurance-server-lambdas-localstack-1
Error dependency localstack failed to start: dependency failed to
start: container insurance-server-lambdas-localstack-1 is
unhealthy`.

**Investigated live, never assumed:** `docker logs insurance-
server-lambdas-localstack-1` on the real server shows the exact cause:

```
PermissionError: [Errno 13] Permission denied:
'/etc/localstack/init/ready.d/init-aws.sh'
```

**Root cause:** that path is `mock-service-os/setup_ssm.sh`
MOUNTED (`docker-compose.yml`, `localstack` service) -- `localstack`
runs that script DIRECTLY via `subprocess.call` (never `sh script.
sh`), requiring the file's own executable bit. `git ls-files -s`
confirms git tracks that file as `100755` (executable)
-- but `deliver_source.py.build_tarball` uses `tar.add(src,
arcname=rel)` WITHOUT a filter, which uses the LOCAL file's
`os.stat()` (Windows, where the operator runs) for the tar's Unix
mode -- and Windows NEVER preserves the 755 bit git tracks at
checkout. The tarball
delivered to the server always had that script WITHOUT the +x, even
though it
comes from a repository where it was always marked executable.

**Why this was never caught before:** no other `.sh` delivered over
this path needs its own +x bit -- `rehearsal_handshake.sh`
is always invoked as `bash rehearsal_handshake.sh` (the bit never
matters, `bash` reads the content regardless of
execute permission). `setup_ssm.sh` is the FIRST `.sh` file
delivered over
this path that needs to be executable on its own (`localstack`
calls it directly) -- and it only started being delivered in this
same round
(Decision 83/85, `SERVER_ONLY_FILES`).

**Fixed:** `deliver_source.py.build_tarball` gains `_fix_
permissions_filter` (new, passed as `filter=` to `tar.add()`)
-- forces 0o755 for any `.sh` and directories, 0o644 for everything
else,
NEVER trusting what the local OS (Windows) reported.

**Why this is a safe fix, never a STOP:** it touches no file
content, only the Unix permission in the tar -- it makes the delivery
CORRECT (what git always intended), never a behavior
change beyond fixing a transport bug.

**Tests (new, with mutant):** `test_build_tarball_forca_bit_
executavel_em_arquivos_sh` + `test_build_tarball_arquivo_nao_sh_
fica_so_leitura` + `test_mutante_tarball_sem_filtro_de_permissao_e_
pego` (deliberately clears the local +x, confirming that WITHOUT the
filter the
tar loses the bit, and that the real `build_tarball` always forces
it). 205
tests in total (202 + 3).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
scripts/deliver_source.py`,
`thesis/results/v9/campaign/tests/test_deliver_source.py`,
`thesis/results/v9/DECISIONS.md` (this Decision).

Redelivering `deliver_source.py` (Step 6, server+clients -- the
fixed `setup_ssm.sh` only arrives this way) and repeating Step 10.

## 90. Real STOP in Phase B, Step 10 -- the business backend comes up end-to-end for the FIRST time (12/12 runs, 0 failures), but the capture proof fails on all 4 profiles -- a real finding over a real network, never exercised before, rule 7(e) applied

**Result, after Decisions 81/87/88/89 (real findings, all
fixed live, each one validated): Step 10 advanced further than
in ANY previous attempt this round.** `smoke_capture_proof`
confirms, reading the real `manifest.json` directly from the control (the
SSH connection hung without closing after the command finished -- the same
"empty heredoc" symptom already recorded earlier in this session, never a problem
with the pilot ITSELF -- the real result was read directly from the file on the
control, never assumed):

- `capture_preflight.go: true`
- **12/12 smoke-gate runs, ZERO failures** (`smoke_
  failures: []`) -- the FIRST time in this package's history that the
  real business backend (auth/mockapi/mongo_seed + psql/
  localstack/mongodb) comes up, serves a real JWKS/token, and sustains
  12 real runs via `campaign_client_runner.py`/`opin_flow.py`
  with zero failures -- **the complete delivery of item 1 of Luciano's
  request is proven, live, on a real AWS.**
- `bytes_diagnostic_needs_decision: false` (a diagnostic, Decision 76,
  never the official gate -- it passed clean).
- `capture_proof_ok: false` -- the 4 MECHANISM-PROOF tests
  (Decision 53, item 4b -- 1 dedicated capture per profile, never one
  of the 12 official criterion-1 ones) failed, all 4 with `ok: false`.

**Investigated live, never assumed:** the 4 capture logs
(`smoke_capture_proof/*.log`, archived here) show REAL decryption
working -- the "PER-MESSAGE size" shows concrete,
plausible values, never empty or corrupted. The cause of `ok: false` is
that EACH log contains the SAME group of messages REPEATED 6 times
(always with the SAME bytes on each repetition -- never diverging
values among themselves), with the "server CertificateVerify+Finished"
group (tshark types 15,20) appearing on a SEPARATE line from the
"ServerHello+EncryptedExtensions+CertificateRequest+
Certificate" group (types 2,8,13,11) -- `_message_sizes_for_profile`
(evaluate_criteria.py) only attributes 15/20 as "from the server" when
they appear on THE SAME line as 2+11; when tshark reports them on
SEPARATE frames (due to different TCP fragmentation/coalescing on a
real network vs. local), those two fields are never filled in, and
the criterion fails due to a missing field, never a wrong byte.

**Why this is a STOP, never a fix-and-retry:** this
classification (`_message_sizes_for_profile`) is the SAME function that
decides the OFFICIAL criterion 1 (the most-cited pre-registration
criterion)
-- never just the smoke gate's mechanism proof. This is the
FIRST TIME, in this project's entire history, that this
classification runs against a REAL network capture (all prior
validation was local/loopback, where TCP coalescing is always
different). Fixing this classification logic, under time
pressure, on a live fleet, WITHOUT fully understanding whether the
frame grouping varies per run (network timing/jitter) or
is deterministic for the real environment -- is exactly the "doubt about
whether the fix changes what is being measured" that rule 7(e) of
this authorization calls for handling with a stop, never with an
attempt
within the same session. Unlike Decisions 81/87/88/89 (infrastructure/
transport/transcription bugs, always with a single root cause,
obviously safe to fix), this finding touches the MEASUREMENT
MECHANISM itself.

**Decision taken:** STOP here. The business backend (this round's
central request) is proven working end-to-end --
that is a real, significant result, not a defeat. The
tshark message classification under a real network needs
Luciano's decision before any change: it touches the official
criterion 1.

**Action taken, following rule 6 (fleet never idle):** `emergency_
stop.py` in dry mode confirmed the expected 5 instances/5 EIPs/3 SGs/4 key pairs;
`cleanup.py --tf-dir ../../terraform --profile mockopin-pqc
--release-eips --force` reported `"all_clean": true`, zero drift;
a final independent check (12 `describe-*` calls, 3 regions)
confirmed empty.

**Decisions pending from Luciano:**
1. Does the per-line classification in `_message_sizes_for_profile` need
   to group by TIME WINDOW (not just exact line), or does tshark
   need an option forcing TLS record reassembly before
   analysis (`-o tls.desegment_ssl_records: TRUE`, possibly already
   on by default -- needs confirming), or is this an
   expected/tolerable behavior that just needs a classification fallback
   (summing 15/20 from ANY line in the block, not only the one with 2+11)?
2. The 6 repeated groups per capture -- are they 6 real
   connections (why 6, if each capture should have only 1 settling
   run?) or is it the SAME handshake being reported across multiple
   windows by tshark? It needs deeper investigation (perhaps
   with the raw pcap, not just the already-extracted text) before any
   fix.
3. Given that the business backend is already proven (item 1 complete),
   Luciano decides whether he wants: (a) to investigate/fix the
   classification before any new real-pilot attempt, or (b) to accept
   running the full pilot even with the smoke gate's mechanism proof
   failing (never recommended -- the same classification
   decides the official criterion 1), or (c) another approach.

**Tests:** none new (a measurement finding under a real network, never
testable locally the same way -- it would need an equivalent real
capture, which exists only in this archived evidence).

**Cost of this attempt:** fleet alive for approximately 1h25
(apply ~20:32 UTC, teardown ~21:53 UTC) -- the LARGEST window of a
single attempt this round, but still well within the US$5 ceiling
(estimate ~US$1,20 for this attempt alone, ~US$2,45 accumulated with
Phase A and the previous Phase B attempt).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/DECISIONS.md`
(this Decision), evidence in `thesis/results/v9/piloto/
ensaio_fase_b_real_v2/`.

## 91. Amendment -- a PARSING bug in criterion 1's measurement mechanism (NEVER a change to the criterion, the thresholds, or the baselines), answering Decision 90's 3 pending decisions

**Item 1 of Luciano's request -- confirmed by data, without AWS, before any fix:**

1. **Cause of the fragmentation:** `_message_sizes_for_profile` classified
   each message by the CO-OCCURRENCE of types on the same tshark line
   ("server" = a line with ServerHello(2) AND Certificate(11) together),
   never by WHO ACTUALLY SENT the message. Under a real network, the
   server's flight sometimes arrives in TWO separate socket
   writes (CertificateVerify+Finished on a line without 2/11) -- the
   same TLS mechanism as always, just with packet grouping
   different from loopback (real RTT/congestion window
   never present on loopback). The old heuristic simply
   never tested that possibility.
2. **The "6 repeated groups" per capture hypothesis:** CONFIRMED, and
   it is not a new assumption -- it is an invariant OF THIS PROJECT,
   documented in `thesis/scripts/opin_flow.py`
   (`get_local_leg_cert_paths`, a v7 Decision from 2026-09-14): a
   full run of the business flow (`opin_flow.py`) opens
   exactly 6 real client-facing mTLS connections per run
   ("restores exactly 6 'upstream handshake complete' lines per
   full flow", confirmed against v7 data from 2026-09-12). The 6
   repeated groups, byte-for-byte identical, in Decision 90's real
   logs (`smoke_capture_proof_*.log`, 1 `dedicated_capture` =
   1 complete run of `campaign_client_runner.py`) ARE those 6
   connections -- never the same handshake reported across different
   windows by tshark.
   - **Honest limitation:** this attempt's RAW .pcap was never
     pulled from the ephemeral host to the operator before Decision
     90's teardown -- only the "PER-MESSAGE size" section (text
     ALREADY derived by `dedicated_capture` itself) survived, now
     archived
     at `piloto/tentativas/ensaio_fase_b_real_v2/` (`conta_como_
     dado: false`, at Luciano's request). It was not possible to count `tcp.
     stream` in this specific attempt's raw pcap because it never
     existed locally -- item 2's confirmation above comes from the
     project's CODE
     (a primary source, never a guess) and, below, from
     a NEW, local capture with a real raw pcap. Fixed going
     forward: the next real attempt archives the raw pcap too (see
     item 4).

**Item 2 of Luciano's request -- fixing `_message_sizes_for_profile`, constraints (a)-(f):**

- **(a) Thresholds/baselines untouched:** `CERTIFICATE_BASELINE`,
  `CLIENTHELLO_BASELINE`, `HANDSHAKE_MESSAGE_BASELINE` and the
  tolerances (0B/±4B/0B) -- not a single line changed.
- **(b) TLS messages reassembled per connection:** a new function
  `_message_sizes_stream_aware` (evaluate_criteria.py) classifies
  each message by the `tcp.srcport` of whoever sent it (the
  ClientHello's srcport = client; anything else = server), grouping by
  `tcp.stream` -- messages from the SAME side on different lines/frames
  of the SAME stream are merged before building the per-type dict,
  fragmentation stops mattering. `dedicated_capture` (orchestrator.py)
  now EXPLICITLY turns on TCP/TLS desegmentation (`-o tcp.desegment_
  tcp_streams/tls.desegment_ssl_records/tls.desegment_ssl_application_
  data: TRUE`) and extracts `tcp.stream`/`tcp.srcport`/`tcp.len` in
  addition to
  `tls.handshake.type/length` (a new format: 7 columns, `frame, stream,
  srcport, tcp.len, types, sizes, sni` -- the 7th field, the
  ClientHello's SNI, is an ADDITIONAL finding, see below). The LEGACY
  path (3
  columns, local measure.sh/synthetic fixture, never fragmented on
  loopback) stays untouched, byte for byte, for regression testing (item e).
- **(c) 6 connections, divergence reported:** each capture groups the
  valid streams (where a ClientHello was found) in chronological order; the
  first is the official measured value, the others must be IDENTICAL
  -- any divergence goes into `stream_divergences` (never
  ignored) and fails `ok`.
- **(d) Mandatory consistency:** raw TCP bytes per direction (the sum
  of `tcp.len` from the start of the stream to the LAST frame with a message of
  handshake) must close EXACTLY with the `handshakeBytesIn`/
  `handshakeBytesOut` the REAL GATEWAY logged for that connection
  (`countingConn`, `business_server.go`) -- now extracted by
  `_handshake_bytes_all` (orchestrator.py, a time window around the
  `_gateway_logs` around when the capture was triggered) and compared by
  `_parse_gateway_handshake_bytes` (evaluate_criteria.py). If it does
  not close
  -- or the section is missing (fail-closed) -- the stream FAILS, never passes.
  **Confirmed empirically, not just by formula:** against the 4
  real reference captures (pqc/hibrido-v8/hibrido-and/classico,
  `local_validation_criterio1_v2/`, Decision 84) and against a NEW,
  local capture of 6 real connections (below), the raw TCP bytes
  close byte for byte with the gateway log in the 4+6 cases.
- **(e) Regression:** `test_evaluate_criteria.py` (NEW, 13 tests)
  confirms the legacy path and the new one produce an IDENTICAL result
  on the classico reference capture (the only one of the 4 whose
  reference capture never fragments); honestly documents that pqc/
  hibrido-v8/hibrido-and ALREADY fragmented in these same LOCAL
  reference captures (it never needed AWS to happen) and that the
  legacy path ALREADY got them wrong (certificate_bytes/ServerHello/
  CertificateVerify_servidor/Finished_servidor = None) -- the new
  path gets all 3 right. Synthetic fixtures cover: a flight fragmented
  across
  2 lines: a mutant of the legacy format against the SAME fragmentation
  (blind, confirming the real bug); 6 identical streams vs. a mutant
  with
  the 6th connection diverging; consistency closing vs. a mutant with
  handshakeBytesIn/Out tampered with; a missing consistency section
  (fail-closed); a stream without a ClientHello (fail-closed).
- **(f) Never adjust to pass:** a dedicated test
  (`test_item_f_totais_fecham_mas_mensagem_individual_diverge_
  continua_fail`) confirms that, even with (c)/(d) OK, a single
  message outside the baseline still FAILS -- the fix NEVER
  loosens the official criterion 1.

**ADDITIONAL finding, while validating locally (item 4 of the
request, "run locally... to confirm 4/4 profiles" BEFORE bringing up the fleet):**
bringing up the real stack locally (the backend via `docker compose`,
the gateway
`mockopin-v9-gateway`, proxy+pqc-signer via `opin_flow.start_tls_kem_
proxy`/`start_pqc_signer_service`) and running ONE real, complete
run of the business flow (`campaign_client_runner.py`, the classico
profile, `call_count: 44`) with tcpdump+tshark capturing the gateway's
primary interface (the same pattern as `capture_one_profile.sh`,
Decision
84, but with the real business flow instead of the 1-connection
`negtest`): the real capture showed **exactly 6 `sni="mtls"`
connections
(client-facing, confirming item 2 above with real data) PLUS 7
connections
from the internal auth carve-out (`sni="matls-api.local"`, Decision
17/18/36, already excluded from criterion 4's count) -- both cross
the SAME captured port 443/interface.** Without a filter, those 7
connections would contaminate `n_streams`/`stream_divergences` with
a
completely different TLS negotiation (CurveP256, a different certificate).
Fixed BEFORE any real attempt: `dedicated_capture` now also
extracts `tls.handshake.extensions_server_name` (the ClientHello's
SNI, 7th column); `_message_sizes_stream_aware` excludes any
stream whose ClientHello SNI differs from `"mtls"`, reported in
`ignored_streams` (never an error, never a divergence -- just a
known carve-out, outside the scope of the "6"). This capture's 6 real
`mtls` connections were byte-for-byte identical to each other
(`stream_divergences: []`) and closed exactly against
`handshakeBytesIn=1513`/`handshakeBytesOut=1640` from the real
gateway in all 6
(`consistency`, 6/6 `ok: true`) -- `certificate_ok: false` only for
the
same reason ALREADY documented (Decision 28/29, a SAN with 2 IPs in
this
local deployment, +14B over the baseline, in ALL 4 profiles,
including this capture). Evidence (derived text, never the raw .pcap/
keylog) in `thesis/results/v9/piloto/dados_oficiais/
validacao-local-decisao-91/`.

**Honest limitation of this local validation:** only classico ran the
REAL, complete business flow -- pqc/hibrido-v8/hibrido-and failed
in this operator's own LOCAL Python with `ValueError: Unknown key
type: 2.16.840.1.101.3.4.3.18` (a JWT signature with a PQC/
ML-DSA certificate via off-the-shelf `pyjwt`/`cryptography`), the
SAME class of
limitation the project ALREADY documents (`opin_flow.get_local_leg_cert_
paths`) and the reason Decision 84 uses `negtest -scenario
matrix` (a single connection) instead of the real business flow to
validate
these 3 profiles locally -- never a bug in this Amendment, never
fixed here (out of scope: it is about JWT signing, not TLS
message size). The classification/consistency logic itself
has NO profile-specific branch whatsoever -- it is identical for any
profile -- and has already been confirmed byte for byte against real
captures of
pqc/hibrido-v8/hibrido-and (1 connection each, Decision 84) in the
automated tests.

**Tests:** `test_evaluate_criteria.py` (NEW, 13 tests, regression +
mutants) + 2 tests/fixtures in `test_orchestrator.py` updated
for the new format (`_TSHARK_FAKE_OUTPUT`, `test_dedicated_capture_
extrai_tamanhos_que_o_avaliador_aceita`) -- 218 tests in total, all
green.

**Requested organization (item 1):** `piloto/ensaio_fase_b_real/` and
`piloto/ensaio_fase_b_real_v2/` moved to `piloto/tentativas/`
(`git mv`, history preserved), each `IDENTIDADE.json` with an explicit
`conta_como_dado: false` -- evidence of STOPPED attempts,
never one of the 7 official criteria.

**Decision:** with the cause confirmed by data, the fix restricted to
parsing (never the criterion), the regression and mutants green, and
local confirmation (4/4 profiles -- 1 via a real business flow + 3 via
a single-connection reference capture, Decision 84), the suite runs
green and
Phase B can be run again (item 4 of the request), following the
stop rules from item 7 of the original prompt.

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/integration/
evaluate_criteria.py`, `thesis/results/v9/campaign/scripts/
orchestrator.py`, `thesis/results/v9/integration/measure/measure.sh`,
`thesis/results/v9/campaign/tests/test_evaluate_criteria.py` (new),
`thesis/results/v9/campaign/tests/test_orchestrator.py`,
`thesis/results/v9/piloto/README.md`, `thesis/results/v9/piloto/
tentativas/` (reorganization), `thesis/results/v9/piloto/dados_oficiais/
validacao-local-decisao-91/` (new evidence), this Decision.

## 92. Real STOP in Phase B, Step 10 (3rd attempt) -- Decision 91 works PERFECTLY against a real network on all 4 profiles; a new stop on `certificate_bytes`, a finding that touches the pre-registered `CERTIFICATE_BASELINE`

**A real fleet applied** (31 resources, `terraform apply -var="self_terminate_hours=4"`), Steps 0-9 green. **A real finding, live, before Step 10 (runbook corrected):** `deliver_images.py` without an explicit `--images` uses `ALL_IMAGE_KEYS` (gateway/proxy/pqc-signer/measure -- a misleading name, it never includes the backend) -- `PILOT_RUNBOOK.md` never had a step calling `--images auth mongo_seed mockapi` (`BACKEND_IMAGE_KEYS`, Decision 83), a gap that has existed since that Decision and was never noticed because no attempt had gotten this far without stopping earlier. `start_block` (called inside Step 10) broke with `RuntimeError: auth.tar nao encontrado`. Fixed: `deliver_images.py --images auth mongo_seed mockapi` run (3/3 `sha256_ok: true`), **`PILOT_RUNBOOK.md` gains Step 8b** documenting this permanently.

**Step 10, part 1: complete success.** `smoke_ok` required all 12 runs without a failure (`smoke_failures: []`, confirmed) -- the SSH connection never closed locally after the command finished (the SAME "empty heredoc" symptom already recorded in this session and in earlier sessions, never a problem with the pilot itself) -- confirmed by reading `manifest.json` directly from the control over a new connection, never assumed.

**Step 10, part 2: Decision 91 proven, for the first time, against a real network, on all 4 profiles.** Reading the 4 `smoke_capture_proof/` logs (text already in the new 7-column format, with `sni`) directly from the control and really running `ec._message_sizes_for_profile` against them:

| Profile | n_streams | divergence among the 6 | consistency (6/6) | other messages (0B tolerance) | certificate_bytes vs baseline |
|---|---|---|---|---|---|
| classico | 6 | none | closes | all OK | 913 vs 899 (+14B) |
| pqc | 6 | none | closes | all OK | 5632 vs 5618 (+14B) |
| hibrido-v8 | 6 | none | closes | all OK | 6255 vs 6241 (+14B) |
| hibrido-and | 6 | none | closes | all OK | 6582 vs 6554 (+28B) |

In ALL 4 profiles: exactly 6 real client-facing mTLS connections
(`sni="mtls"`), ZERO stream errors, ZERO divergence among them
(confirming item (c) of Decision 91 against a real network for the
first
time), consistency (d) closing EXACTLY (raw TCP bytes ==
the real gateway's handshakeBytesIn/Out, across the 6 connections, in
all 4 profiles) and
EVERY message that is NOT the server's Certificate matching the
official baseline EXACTLY (0B tolerance) -- including
`CertificateVerify_servidor`/`Finished_servidor`, exactly the 2
fields Decision 90 could never fill in under real
fragmentation. **The measurement mechanism's fix worked perfectly.**

**The sole cause of `capture_proof_ok: false`:** `certificate_bytes`
consistently **+14B** above the baseline (classico/pqc/hibrido-v8,
1 server leaf each) or **+28B** (hibrido-and, 2 server
leaves -- the margin doubles, exactly as Decision 29 already predicted
for that profile). **Investigated by content, not assumed:**
Decision 75 (earlier in this same extended session) had already
investigated this EXACT question and explicitly decided that the
pilot uses the certificates as they already are, embedded in the
pinned images
(`mockopin-v9-gateway:pinned`/`:proxy`), WITHOUT any image
rebuild -- confirmed again now: the `sha256sum` of the
`classico_server.crt` freshly generated by `make certs` (default,
`SERVER_IPS=127.0.0.1,::1`) matches byte for byte the same file
extracted from inside `mockopin-v9-gateway:pinned`
(`29c720c0...` == `29c720c0...`). This certificate's DER measures 900
bytes; the TLS 1.3 framing formula (`1(context)+3(certificate_
list)+3(cert)+DER+2(extensions)`) predicts exactly 909B of content
(+4B header = 913B message) -- matching EXACTLY the
measured value, in all 4 profiles. **`CERTIFICATE_BASELINE` (899 for
classico, and
the equivalents for the other 3) does not match the certificate that
REALLY is embedded in the pinned images and that Decision 75 already
confirmed is correct for the pilot -- a pre-existing calibration
mismatch, never a bug of this session, just NEVER exposed before
because this is the first time the capture proof reaches this point
in full.**

**Collateral finding, fixed live BEFORE any real run could
use the wrong result (it never reached contaminating any measurement):**
while investigating the cause above, this operator mistakenly
tried to regenerate `certs/generated` with the fleet's REAL
`SERVER_IPS` (the same IPs used in Decision 91's local validation) --
exactly the
technique Decision 75 had already explicitly ruled out for the
pilot. Reverted immediately (default `make certs`, without
`SERVER_IPS`) and reconfirmed by sha256 against the pinned image BEFORE
delivering again to the 5 hosts -- the smoke gate that produced
this Decision's numbers had already finished with the CORRECT
certificates
by that point (the wrong attempt only happened AFTERWARD, while
investigating the result), so no real measurement was affected.

**Why this is a STOP, never a fix-and-retry:**
`CERTIFICATE_BASELINE`/`CERTIFICATE_TOLERANCE_B` are the OFFICIAL,
PRE-REGISTERED thresholds of criterion 1 (Decision 20/28/29/30/31) --
changing any of them is changing the criterion itself, exactly what
rule 7(e) of this authorization forbids doing without Luciano's
decision. The
code (measurement, classification, consistency) is verified correct
-- every OTHER field matches exactly, across the 4 profiles, including
against the gateway's REAL handshakeBytesIn/Out. The failure is
entirely the
NUMBER 899/5618/6241/6554 not matching the certificate Decision 75
already decided is CORRECT for the pilot -- rule 7(a) of this
authorization ("a pre-registered criterion fails with the code already
verified correct") applies directly.

**Action taken, following rule 6 (fleet never idle):**
`emergency_stop.py` in dry mode confirmed the expected 5 instances/5 EIPs/3 SGs/4
key pairs (no drift); `cleanup.py --tf-dir ../../terraform
--profile mockopin-pqc --release-eips --force` reported
`"all_clean": true`; a final independent check (12 `describe-*`
calls, 3 regions) confirmed empty (instances show up as
`terminated`, never `running`).

**Honest limitation of this evidence (a sequencing error):** the 4
raw `.log` files from `smoke_capture_proof/` were only remembered
AFTER `cleanup.py` had already terminated the instances -- with them
terminated (never just stopped), the files became unrecoverable.
The exact values (read and computed live, directly from the control,
while the fleet was still up) are recorded in
`thesis/results/v9/piloto/tentativas/ensaio_fase_b_real_v3/
resultados_porta_de_fumaca.json` -- never reconstructed from memory
after the fact. A process fix for the next attempt: archive ALL
evidence before any teardown call, never after.

**Decisions pending from Luciano:**
1. Do `CERTIFICATE_BASELINE`/`CERTIFICATE_TOLERANCE_B` (and the 3
   analogous values for the other profiles) need recalibrating to the
   certificate REALLY embedded in the pinned images (899→913,
   5618→5632, 6241→6255, 6554→6582 -- all +14B, except hibrido-and
   +28B), with a formal Amendment recording the before/after and the cause
   (a SAN with 2 IP addresses, `127.0.0.1,::1`, in the server's
   certificate -- never the IP value itself, Decision 75, item c)? Or
2. were the baselines always supposed to be these (913/5632/6255/6582)
   and it was the ORIGINAL NUMBER (899/5618/6241/6554) that was never
   updated after some historical change in certificate generation
   (it needs investigating WHEN/HOW 899 was originally measured,
   against which certificate)? Or
3. another approach -- for instance, if the IP SAN's presence in the
   server certificate is itself dispensable (Decision 75, item c,
   already showed NO real check depends on it -- neither
   hostname nor the handshake), would it be simpler to remove those 2
   entries from the certificate (regenerating the pinned image, with a
   formal re-pin Amendment, Decision 61) than to change the baselines?

**Cost of this attempt:** fleet alive for approximately 1h (apply
~03:06 UTC, teardown ~04:03 UTC) -- well within the US$5 ceiling
(estimate ~US$0,50 for this attempt alone, ~US$2,95 accumulated with the
Phase A and the 2 previous Phase B attempts).

**Tests:** none new (a baseline-calibration finding against a
real certificate, never testable locally the same way -- Decision
91 already has 13 tests covering the MECHANISM, which this Decision
confirms works; the baseline number itself is not testable without
Luciano's decision on which value to use).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
PILOT_RUNBOOK.md` (Step 8b), `thesis/results/v9/piloto/tentativas/
ensaio_fase_b_real_v3/` (new evidence), `thesis/results/v9/piloto/
README.md`/`estado.json`, this Decision.

## 93. Amendment -- `CERTIFICATE_BASELINE` recalibrated by DERIVATION from the real DER (Luciano's option 2), full investigation before any fix: Decision 75 had already reversed Decision 28/29's premise, and `CERTIFICATE_BASELINE` was never rechecked against that reversal

**Investigation, without AWS, item 1 of the request (five parts, none assumed):**

**(a) Each embedded certificate's real DER vs `BASELINE_CERT_DER_SIZES`.**
Measured directly (`ssl.PEM_cert_to_DER_cert`) against `certs/generated/`
(confirmed by sha256 == the same one embedded in `mockopin-v9-gateway:
pinned`, Decision 92): classico out=900/in=787; pqc out=5619/in=5506;
hibrido-v8 out=6242/in=6131; hibrido-and out=914+5647/in=801+5534 --
**the four match `BASELINE_CERT_DER_SIZES` EXACTLY, with no
divergence.** This table was never the problem.

**(b) History via `git log -S` + `DECISIONS.md`.** `BASELINE_CERT_
DER_SIZES` was introduced in `8a14254b` (Decision 55) with the SAME
900/5619/6242/914+5647 as today -- it never changed since. 
`CERTIFICATE_BASELINE` changed exactly once, in `107f592c` (Decisions
28/29): the diff literally shows a REMOVED comment reading
`"Baseline recalculado: 913-12=901, 5632-12=5620, 6255-12=6243,
6582-12=6570"` -- in other words, **913/5632/6255/6582 (the SAME
values the real AWS measurement, Decision 92, found) were already
Decision 28's starting point**, which SUBTRACTED an arithmetic
estimate of -12B (later corrected to -14B/-28B measured in Decision
29) assuming the pilot would swap the loopback SAN for one with two
real IPs (private+EIP). Decision 75 (resumed in this same extended
session) investigated that EXACT premise and explicitly overturned it:
"the real-SAN technique... is ruled out for the pilot -- no image
rebuild"; confirmed by sha256 that the embedded certificate is the
loopback one (127.0.0.1,::1); and concluded "why this is an Amendment,
never a STOP: no pre-registered criterion changes" -- but never
rechecked `CERTIFICATE_BASELINE` against that reversal. The number
stayed anchored to a SAN swap that Decision 75 itself proved never
happens.

**(c) Sum of per-message baselines vs `BASELINE_HANDSHAKE_BYTES`,
residual, a single inconsistent entry.** For each profile/direction:
`out_sum = ServerHello+EncryptedExtensions+CertificateRequest+
Certificate+CertificateVerify_server+Finished_server`; `in_sum =
ClientHello+Certificate_client+CertificateVerify_client+Finished_
client`. **Before the fix** (899/5618/6241/6554): the `out` residual =
135/135/135/149 (NOT constant -- hibrido-and diverges from the other
3 exactly because of the Certificate's extra leaf) and the `in`
residual =
77/77/77/77 (already constant, the client side never had a problem).
**After the fix** (913/5632/6255/6582): the `out` residual =
121/121/121/121 (constant across the 4) and the `in` residual stays 77/77/77/77.
**The ONLY inconsistent entry, on both sides, was the SERVER's
Certificate -- confirmed by exact arithmetic, no other table row
(ServerHello/EncryptedExtensions/CertificateRequest/
CertificateVerify/Finished, in both directions, nor the client's
Certificate_cliente) needs a fix.** (The leftover 121B/77B residual is
TLS 1.3 record framing/AEAD tag/ChangeCipherSpec -- never part of the
"+4B per message" convention these tables use, never an
inconsistency.)

**(d) The Certificate value derived by the formula, 4 profiles, 2
directions (includes the CLIENT's Certificate in mTLS).** RFC 8446,
section 4.4.2: `message = 4(handshake header) + 1(certificate_
request_context, always empty) + 3(certificate_list length) +
per leaf [3(cert length) + DER + 2(extensions length) +
the real extension)]`. For 1 leaf: `message = DER+13` --
tested against the 3 single-leaf profiles, matching EXACTLY in both
directions (classico: server 900+13=913, client 787+13=800 -- this
LATTER one was already the value used in `HANDSHAKE_MESSAGE_BASELINE`,
it never changed; pqc: 5619+13=5632 / 5506+13=5519 [already correct];
hibrido-v8: 6242+13=6255 / 6131+13=6144 [already correct]). Hibrido-AND
(2 leaves, server AND client): the formula generalizes to `8 +
sum_per_leaf(DER_i+5+extension_i)` -- confirmed by content (tshark's
`Certificates Length` field, never the ML-DSA leaf's ASN.1 sub-parsing,
which tshark itself gets wrong with "BER Error"/"Vector length...
malformed") that the ML-DSA leaf carries 3B of REAL extension per
`CertificateEntry` that the RSA leaf does not have -- confirmed in 2
INDEPENDENT real captures (local, Decision 84; real AWS, Decision 92):
server
914+5647+21=6582 (matches Decision 92's real measurement); client
801+5534+21=6356 (matches the `Certificate_cliente` that `HANDSHAKE_
MESSAGE_BASELINE` already used, never changed). **The 4 profiles, both
directions: the formula EXACTLY reproduces both the already-correct
values (ClientHello, Certificate_cliente, all other messages) and
the single wrong value (the server's Certificate) -- no second
inconsistency found.**

**(e) Why old local validations passed with 899.** They never
passed against a real certificate -- Decision 79 ("the complete data
path proven locally") used `LocalExecutor`/`_dedicated_
capture_block`, which FABRICATES message sizes DIRECTLY from the
baseline dictionaries themselves (`HANDSHAKE_MESSAGE_BASELINE`/
`CERTIFICATE_BASELINE`) -- circular by construction, never an
independent measurement against a real certificate file. Decision 90
was the FIRST time `certificate_ok` was evaluated against a real
network capture (and it stopped before reaching that specific
comparison, due to a different parsing bug); Decision 92 was the
FIRST time the comparison actually ran -- and that is exactly
when the inconsistency appeared.

**Luciano's hypothesis: CONFIRMED on all 5 points.** The residual
shows EXACTLY one inconsistent entry (never more than one, never
another message); the value derived by the formula from the real DER
matches EXACTLY the one measured on AWS (Decision 92) across the 4 profiles.

**Fix (item 2 of the request, option 2 -- by DERIVATION, never copying):**
`CERTIFICATE_BASELINE` stops being a literal constant and becomes
CALCULATED, at import time, by `_tls13_certificate_message_
size(leaf_der_sizes, extra_extension_bytes)` (new, `evaluate_
criteria.py`) from `BASELINE_CERT_DER_SIZES` (which was already
correct, never touched) -- the formula and the verifying `assert`
(the Hibrido-AND individual DER sum == the total `BASELINE_CERT_DER_
SIZES` already held) are RECORDED in the code itself, never only in
the commit.
`CERTIFICATE_TOLERANCE_B` stays ±4B (Decision 42, still valid: the only
legitimate source of variability is the serial number's ASN.1
padding).
No other constant touched. `BASELINE_CERT_DER_SIZES` was only
MOVED to before `CERTIFICATE_BASELINE` in the file (it needs to exist
first, being computed at import time) -- identical content.

**This is a FORMAL DEVIATION from the `v9-prereg` pre-registration**
(criterion 1's numeric threshold changes, 899/5618/6241/6554 ->
913/5632/6255/6582, even though the logic and the ±4B tolerance stay
the same) -- **to be reported in the thesis as such**, with this
Decision and the evidence from Decisions 75/90/92 attached: the root
cause was never a measurement or implementation error, it was Decision
28/29 having been built on a premise (a SAN with real IPs) that
Decision 75, later, ruled out without propagating the reversal to the
number that depended on it.

**Tests:** `test_evaluate_criteria.py` gains 5 new tests --
the formula reproduces the derived baseline (1 and 2 leaves), a
mutant that omits the ML-DSA leaf's real extension (errs by exactly
3B), a constant residual across the 4 profiles (proving no other
entry needs a fix), a mutant with the old `CERTIFICATE_BASELINE`
(proving the residual was NOT constant before). The 3 reference
captures
(pqc/hibrido-v8/hibrido-and, Decision 91) gain a new assertion:
`certificate_ok`/`ok` now `True`. 223 tests in total, all green.

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/integration/
evaluate_criteria.py`, `thesis/results/v9/campaign/tests/test_
evaluate_criteria.py`, this Decision.

## 94. The fourth real attempt at Phase B -- four real findings fixed live in sequence at Step 11.5 (the dedicated producers for criteria 2/3/7), none of them touching what is measured

**A real fleet applied** (31 resources), Steps 0-10 green -- `smoke_ok:
true`, `capture_proof_ok: true` on all 4 profiles (Decision 93
confirmed again against the real network). Step 11 (60 runs + 12
captures): green,
`total_execucoes: 60`, zero failures. **Step 11.5
(`dedicated_criteria.py`, the producers for criteria 2/3/7, Decision 85)
-- the FIRST time this script runs against the complete real pilot
-- found 4 real findings in sequence, each investigated by
content (never assumed) before fixing:**

1. **The SSH session bringing up `criterio2_probe.py` never returned
   (a 50s timeout), even with the process already really running on
   the server (confirmed by `ps aux`/log, repeatedly).** Five
   fix attempts by command SYNTAX (an explicit `< /dev/null`,
   `stdin=subprocess.DEVNULL` in `cli._run`, `setsid`, the
   `sh -c '...& echo $!'` pattern `_launch_gateway` already uses for
   tcpdump, `ssh -f`) -- NONE changed anything. The real cause,
   confirmed manually: TRANSIENT throttling on the server right after
   Step
   11 (60 runs, many SSH connections in quick succession) -- the
   SAME simple command as always returned in ~1,3s after only about
   15s of waiting. Fixed with a simple retry (3 attempts, 15s
   intervals) in `run_criterio2`, never changing the launch
   mechanism. `cli._run` gained `stdin=subprocess.DEVNULL` for
   defensive hygiene (never the cause or the fix for this
   specific finding, honestly documented in the code).
2. **`ethtool` missing on the real AMI (Amazon Linux 2023) -- it brought
   down the ENTIRE script** with a `FileNotFoundError`, even though
   this field
   (Decision 37) never decides criterion 2's result.
   `ethtool_offloads` gains a `try/except` -- an explicit
   `"indisponivel"`, never a silent None, never again bringing down the script.
3. **`tcpdump` without `sudo` in `criterio2_probe.py` -- it failed with
   "CAP_NET_RAW may be required", SILENTLY** (the `Popen` never
   checked the return code) -- confirmed by running `tcpdump` manually
   as `ec2-user` on the real server. No pcap was written,
   `mss_bytes`/`bytes_sent_before_first_client_ack` stayed `None`
   with no visible error. Fixed with `sudo` (the same fix
   `dedicated_capture`/`_launch_gateway` already use for criterion 1's
   real tcpdump).
4. **A real logic bug in `extract_mss_and_bytes_before_ack`**,
   confirmed by content against the real pcap: the function used the
   client's FIRST ACK (`ack_out[0]`) to compute how many bytes the
   server sent before it -- but that FIRST ACK is the one that CLOSES
   the
   3-way handshake (`ack_num == first_seq`, acknowledging only the
   SYN, never any data byte), making
   `bytes_sent_before_first_client_ack`
   be ALWAYS `None` by construction, NEVER reflecting what the function
   actually tried to measure. The function's own docstring already
   described the
   CORRECT behavior ("ack_num > the server data's initial seq") --
   the code never implemented that condition. Fixed:
   it skips any ACK that acknowledges <= `first_seq`, using the first
   one that
   actually acknowledges real data (verified against real pcap numbers:
   2896 bytes, not `None`).

**Additional finding, even before Step 11.5 (fixed BEFORE
any real run could use the wrong result):** `PILOT_RUNBOOK.md`
never had a step delivering the 3 business-backend images
(`auth`/`mongo_seed`/`mockapi`, Decision 83) via `deliver_images.py
--images` -- `deliver_images.py` without an explicit `--images` uses
`ALL_IMAGE_KEYS` (a misleading name, it never includes the backend).
`start_block`
(inside Step 10) broke with `auth.tar nao encontrado` on this round's
first
attempt. Fixed with a new Step 8b in the runbook.

**Why none of these is a STOP:** the 4 findings from Step 11.5 and the
Step 8b finding are all INFRASTRUCTURE/TRANSPORT/PARSING LOGIC
bugs in a dedicated producer -- none touches `CERTIFICATE_
BASELINE` nor any other pre-registered threshold, none changes what
criteria 2/3/7 actually measure (it only fixes the measuring
MECHANISM). The same class as Decisions 81/86/87/88/89 (real
infrastructure findings, fixed live, never a STOP).

**Tests:** `test_dedicated_criteria.py` gains 3 tests (retry with
backoff, fails loudly after 3 attempts, a mutant without retry); `test_
producers.py` gains 6 (ethtool missing + mutant + normal case, sudo
on tcpdump + mutant, ack-skip with real pcap data + mutant).
233 tests in total, all green.

**Estimated accumulated cost:** ~US$3,50 (ceiling US$8, raised by
Luciano this round so as not to trigger the 80% alarm midway through
the pilot).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/campaign/
scripts/{dedicated_criteria,cli}.py`, `thesis/results/v9/integration/
producers/criterio2_probe.py`, `thesis/results/v9/campaign/tests/
{test_dedicated_criteria,test_producers}.py`, `thesis/results/v9/
campaign/PILOT_RUNBOOK.md` (Step 8b), this Decision.

## 95. Phase B complete, end-to-end, for the first time in this package's history -- 60/60 runs, 12/12 captures, the 7 criteria evaluated with 100% real data; 3 NEW findings (never seen before, never testable locally) found in the results, none fixed live (they would be changes to the measurement METHOD, not infrastructure)

**Steps 12-15, all green:** `collect_artifacts.py` (19 files
verified by sha256 manifest, pulled to the operator BEFORE
any teardown -- a lesson applied after a
sequencing error in Decision 92); `consolidate_v9_pilot.py` (generated
`RELATORIO_PILOTO.md`+`criteria_evaluation.json` in `thesis/results/
v9/piloto/dados_oficiais/piloto-real-aws-2026-11-09/`); `emergency_
stop.py` dry (5/5/3/4 expected resources, no drift); `cleanup.py
--release-eips --force` (`all_clean: true`); a final independent
check (12 `describe-*` calls, 3 regions, all empty).

**Overall result: 4/7 PASS (criteria 3/4/5/6), 3/7 FAIL (criteria
1/2/7) -- the FIRST time the 7 criteria are evaluated against
100% real data, end-to-end, in this history. The 3 FAILs are NEW and
REAL findings, never seen before because no previous attempt had
gotten this far -- none is an infrastructure/transport bug
(the class Decisions 81/86/87/88/89/94 already resolved live); the 3
touch the measurement METHOD itself, requiring Luciano's decision
before any fix (rule 7(e)).**

**Criterion 1 (per-message sizes) -- FAIL.** Classico/pqc/hibrido-
v8/hibrido-and: L219 and L325 PASS on all 4 (confirming Decision 91/93
working perfectly against a real network, again, now in the 12
OFFICIAL captures, not just in the smoke gate's mechanism proof).
**L0 fails on all 4 profiles, always the SAME way:** of each L0
capture's 6 mTLS connections, ONLY the ClientHello and ServerHello
decrypt (183B, always correct) -- EncryptedExtensions/CertificateRequest/Certificate/
CertificateVerify/Finished never appear, in ANY subsequent frame,
across the 6 connections, in the 4 profiles -- confirmed that the raw
packets DO EXIST in the pcap (real tcp.len>0, never missing frames),
only the TLS dissector never decrypts them. Hypothesis (never confirmed
byte for
byte, needs deeper investigation): L0 is the ONLY near-zero-RTT
route -- the 6 connections complete so fast that the keylog
(`/tmp/v9_keylog.txt`, written by the Go gateway) may not be
fully flushed to disk by the time `dedicated_capture`
does `docker exec cat` on it, moments later -- L219/L325 (real RTT)
naturally give the process more time to flush between secrets.

**Criterion 2 (real initcwnd) -- FAIL.** `segments_computed ≈ 0,32`
(2896B / 8961B MSS) vs `ss_ti_cwnd = 10` -- the two sources
disagree a LOT (diff ≈ 9,7 >> the tolerance of 2). Investigated: the extracted
`mss_
bytes` comes from the server's SYN-ACK (8961B, the NIC's LOCAL
jumbo-frame capacity, `pmtu:9001` confirmed in `ss -ti` itself), but
the
EFFECTIVE MSS of the real connection (`ss -ti` shows `mss:1448`, the
value the
KERNEL actually uses) is much smaller -- PMTU discovery reduces it to
~1500 on
the public cross-region path. Even recalculating with 1448 (2
segments), it still diverges from the kernel-reported cwnd=10 -- `ss -ti`
also shows `pacing_rate 1,05Mbps`: TCP PACING (BBR/fq, the default on
modern Linux kernels) deliberately caps the sending rate
INDEPENDENTLY of the available cwnd, so "bytes sent before the
first ACK" may never reflect the configured cwnd on a
REAL connection with pacing on -- one channel may be measuring the cwnd
(kernel configuration) and the other the pacing rate (sending
policy), never the same quantity. Never tested against a real kernel/NIC
before this attempt.

**Criterion 7 (per-route latency sanity) -- FAIL on L219/L325
(L0 PASSES).** `rtt_ms_pcap` comes out at ~0,06-0,10ms on the 3
routes, way below
the nominal value (0/219/325ms) for L219/L325 -- it only matches for
L0 (which
coincidentally is ALSO ~0). Investigated: the `pcap` channel extracts
the
delta between the SYN frame arriving and the SYN-ACK frame leaving,
both
captured on the SAME SERVER interface (`dedicated_capture`,
Decision 52) -- that only measures the server's PROCESSING TIME
(SYN->SYN-ACK on the same host), NEVER the real network RTT (which
would need BOTH propagation legs, client->server AND
server->client, invisible in a capture taken only on the server).
A design never exercised against a route with real RTT >0 before
this attempt -- L0 "passed" by coincidence (real RTT and processing
time are both tiny).

**Why these 3 are STOPs, never fix-and-retries:** all three
touch the measurement METHOD/mechanism of criteria 1/2/7 (never just
infrastructure/transport) -- changing any of them CHANGES what is
measured, exactly what rule 7(e) of this authorization calls for
handling with a stop. Criteria 3 (zero errors, L325), 4 (flow
counts), 5 (zero errors) and 6 (instrumentation+assertions) PASS with
100%
real data, without reservation.

**Decisions pending from Luciano:**
1. Criterion 1 -- investigate the real cause of the L0 decryption gap
   (it needs this attempt's raw pcap + raw keylogs, already
   discarded by the teardown -- the next attempt should archive
   them before any `cleanup.py`) and decide whether to widen the
   window before `docker exec cat keylog` in `dedicated_capture`, or
   another
   approach.
2. Criterion 2 -- decide whether `mss_bytes` should come from the
   EFFECTIVE MSS
   (`ss -ti`) instead of the SYN-ACK, and/or whether pacing needs to
   enter the
   agreement formula between the 2 channels (or a different
   tolerance), or whether the criterion's method needs revising.
3. Criterion 7 -- the `pcap` channel needs capture ON BOTH SIDES
   (client AND server) to measure real RTT, or it needs to be
   redesigned/dropped as an independent channel of this criterion.

**Complete evidence** (the consolidated report + the 19 collected
files, the 12
OFFICIAL captures, `piloto_calls.json` from the 60 real runs) in
`thesis/results/v9/piloto/dados_oficiais/piloto-real-aws-2026-11-09/`.

**Estimated final accumulated cost:** ~US$4,20 (ceiling US$8).

**Tests:** none new (3 measurement-METHOD findings against real
infrastructure/kernel/network, none reproducible locally the
same way -- it would need equivalent real pcaps/keylogs, which
are archived as this Decision's evidence, never reconstructed).

**Commit and push** (`v9/fase1-local`): `thesis/results/v9/piloto/
dados_oficiais/piloto-real-aws-2026-11-09/` (complete result),
`thesis/results/v9/piloto/README.md`/`estado.json`, this Decision.

## 96. A NEW fail-closed rule for teardown -- destroy only after the raw data is collected and VERIFIED by sha256 (12 pcaps, 12 keylogs, flight data, logs from every instance and container, artifacts from the 60 runs); a real finding: PILOT_RUNBOOK.md had `--force` as the MAIN command, never exercising the gate that already existed in code

**Luciano's request**, in response to the Phase B report (Decision 95):
a new, fail-closed rule for teardown -- it may only run after the
raw data is collected and verified by sha256; if the collection
fails, the fleet is NOT torn down (except for the cost/
safety limit, rule 7, in which case the report must say exactly
what was lost); test the block with a mutant.

**Real finding, while auditing PILOT_RUNBOOK.md itself:** the gate
(`cleanup.py full_cleanup`, `pull_verified_marker`) had already existed
in
code since early in this round -- but the actual runbook (Step 14)
ALWAYS commanded `--force` as the MAIN teardown command, NEVER
`--pull-verified-marker`. The gate had never actually been exercised
in
ANY real attempt this session (Decisions 90-95 all used
`--force`). Fixed:

1. **cleanup.py full_cleanup:** `force=True` now REQUIRES `reason`
   (a non-empty string) -- EXPLICITLY reserved for the cost/
   safety exception (rule 7), never a bypass out of convenience/
   habit. `reason`/`forced` are included in the result (auditable, never
   a silent bypass). The CLI gains `--reason`.
2. **PILOT_RUNBOOK.md, Step 14:** the main command now uses
   `--pull-verified-marker /tmp/v9_piloto_coletado/.pull-verified`
   (the SAME marker Step 12/collect_artifacts.py already writes
   AFTER fully hashing the directory) -- `--force --reason`
   is documented ONLY as rule 7's fallback.
3. **Missing raw evidence in what the manifest already hashes** (the
   real reason the gate never made a difference, even if exercised:
   the critical raw data was never in the directory it verifies):
   - orchestrator.py dedicated_capture: besides the already-extracted
     text block (which already existed), it now also brings the RAW
     PCAP and KEYLOG from
     EVERY attempt (success or failure, see Decision 99) to the
     LOCAL capturas_dir (the control) -- previously these only lived
     in /tmp
     on the SERVER, destroyed by teardown, never part of what
     collect_artifacts.py verifies.
   - dedicated_criteria.py run_criterio2: also brings the raw pcap
     from the dedicated initcwnd test (criterio2_probe.pcap),
     previously only the JSON.
   - dedicated_criteria.py collect_full_logs (NEW): the FULL log (no
     time window) of the server's 4 containers
     (gateway/auth/mongo_seed/mockapi) -- previously, only a WINDOW of
     the gateway (_gateway_logs, used within a specific
     run) was preserved; the other 3 NEVER had any log
     saved at all. Plus lightweight diagnostics (dmesg, best-effort,
     never
     fail-closed) from each instance in the fleet.
   All of these write INSIDE the SAME out_dir/--dir that
   collect_artifacts.py already hashes completely (find . -type f)
   -- becoming evidence covered by the EXISTING sha256 manifest, by
   construction, never a second, parallel verification system.

**Tests (a mutant explicitly requested):** test_cleanup.py gains 5
tests (force without reason fails loudly, an empty reason fails
loudly, an explicit reason proceeds and is reported, without force it
never reports `forced`,
a MUTANT reproducing the OLD behavior -- `--force` alone
sufficed, exactly as PILOT_RUNBOOK.md used it -- confirming the
real gap this Amendment closes). test_dedicated_criteria.py
gains 4 (the criterion-2 pcap pull + a mutant without the pull,
collect_full_logs brings all 4 containers + a mutant that only brought
the gateway). test_orchestrator.py gains 1 (preserves the pcap/keylog
from
EVERY attempt, including failures, in capturas_dir).

Same rules: no action on AWS, no commit before the scanner,
report in the chat.

## 97. RTT-pcap Amendment to criterion 7 -- the pcap channel measured the server's LOCAL PROCESSING time (SYN arriving -> SYN-ACK leaving, both on the SAME interface), never real network RTT; fixed to SYN-ACK leaving -> the ACK closing the handshake coming back (the same capture, zero new endpoint, zero new SG rule); validated with ground truth (Decision 100)

**Formal amendment label:**
- **What changed:** criterion 7's `rtt_ms_pcap` channel's METHOD --
  from "the client's SYN arriving -> the server's SYN-ACK leaving" to
  "the server's SYN-ACK leaving -> the client's first ACK (which
  closes the
  3-way handshake, Decision 94 already confirmed it never
  acknowledges data) arriving back". The acceptance band (nominal
  +-10%, the L0
  floor from Amendment 5) and the second channel (rtt_ms_probe,
  TCP/443) do not
  change.
- **Reason:** a real finding from Decision 95 -- the old method
  measures two
  events on the SAME server interface, with NO network
  propagation between them -- it is local processing time (confirmed
  by
  theory AND by ground truth, Decision 100: 0,024ms measured in a
  test with a REAL, configured 50ms RTT). The new method covers the
  outbound
  (server->client) AND return (client->server) legs completely in
  the SAME
  server-only capture -- genuinely real RTT, without needing
  capture on the client.
- **Date:** 2026-11-09.
- **Pairing by tcp.stream** (never by list order/index --
  streams can interleave under a real network, Decision 91).
- **The criterion's tolerance (+-10%, the L0 floor) reviewed and
  CONFIRMED
  adequate** -- the 1ms absolute floor for L0 (Decision 32, Amendment 5)
  already correctly handles the sub-millisecond case Luciano
  mentioned; no change needed there, no STOP.

criterio7_rtt.py: pcap_syn_synack_rtt/rtt_from_syn_synack_times
replaced with pcap_synack_ack_rtt/rtt_from_synack_ack_times/
pair_synack_ack_by_stream (explicit pairing by stream).
evaluate_criteria.py: criterion 7's docstring updated, no
threshold/data-format change.

**Validated with ground truth (Decision 100):** RTT configured at
5/50/200ms via tc netem (the correct topology -- delay only on the
client,
egress+ingress via ifb, never on the server) -- both channels (the
real probe + the new pcap one) matched the configuration within
+-2% across the 3
values; the OLD method, measured against the SAME real packets,
showed exactly the theorized symptom (0,024ms at a configured 50ms).

**Tests:** test_producers.py gains 3 (pairing by stream,
a mutant "old method measures only local processing", median robust
to outliers with the new signature). test_dedicated_criteria.py
unchanged (the JSON interface -- rtt_ms_pcap/n_samples_pcap --
preserved, only the internal implementation changed).

Same rules: no action on AWS, no commit before the scanner,
report in the chat.

## 98. Effective-MSS Amendment to criterion 2 -- mss_bytes came from the MSS ANNOUNCED in the SYN-ACK (the NIC's LOCAL jumbo-frame capacity, Decision 34), never the real path's EFFECTIVE MSS; fixed to require AGREEMENT between ss -ti and the pcap's largest real payload, otherwise FAIL; a formal deviation from pre-registration (Decision 34), declared for the thesis; validated with ground truth (Decision 100)

**Formal amendment label, a DECLARED deviation from pre-registration:**
- **What changed:** criterion 2's METHOD for obtaining `mss_bytes` --
  from
  "MSS from the server's SYN-ACK options" (Decision 34 said "read
  from the
  SYN options of the same connection, never assumed" -- the code
  implemented that by literally reading the SYN-ACK option, which is
  exactly the NIC's LOCAL capacity, never the real effective one) to
  mandatory AGREEMENT between TWO channels of the EFFECTIVE MSS: (1)
  ss -ti, the kernel's own mss field; (2) the LARGEST real payload
  (tcp.len) the server actually put on the wire, straight from the
  pcap.
  The threshold (INITCWND_MIN_SEGMENTS=10) does not change.
- **Reason:** the real AWS run (Decision 95) measured mss_bytes=8961
  (announced in the SYN-ACK, the instance's LOCAL jumbo-frame
  capacity)
  but the real EFFECTIVE MSS (ss -ti) was 1448 -- reduced by PMTU
  discovery on the real cross-region path. Using the announced value
  inflated
  segments_computed's denominator by ~6x, making the criterion
  fail for a MEASUREMENT reason, never because of the real
  initcwnd.
- **Date:** 2026-11-09.
- **Explicitly declared as a deviation from pre-registration**
  (Decision
  34 defined the MSS by the "SYN's options" without specifying which
  side of the
  connection nor distinguishing announced-vs-effective -- the literal
  implementation followed the SYN-ACK) -- to be reported in the
  thesis's methodology.

**Method adopted:** criterio2_probe.py gains ss_ti_snapshot with an
mss
field (besides the already-existing cwnd); extract_mss_and_bytes_
before_ack also returns mss_pcap_max_payload (the largest tcp.len
among the server's data segments), a new helper function
effective_mss(ss_ti_mss, mss_pcap_max_payload) -- if they agree (diff
0B) it uses the value, mss_channels_agree=True; if they disagree =>
mss_bytes=None, mss_channels_agree=False. The MSS announced in the
SYN-ACK is still recorded (mss_synack_announced_bytes), ONLY as a
diagnostic -- it never enters the calculation. evaluate_criteria.py's
criterion_2_initcwnd requires mss_channels_agree is True BEFORE
any segment calculation -- missing/False fails for that specific
reason.

**Validated with ground truth (Decision 100):** MTU 1500 (ethtool
TSO/GSO/GRO off) -- ss_ti_mss=1448, mss_pcap_max_payload=1448,
they agree; MTU 9001 (jumbo) -- ss_ti_mss=8949,
mss_pcap_max_payload=8949, they agree -- in BOTH cases the
SYN-ACK's announced value (1460/8961) is SLIGHTLY different from the
effective one (overhead from TCP options such as timestamp),
reinforcing why it
should never be used directly. GSO on (an incidental finding, before
turning the offloads off for the main test) inflated
mss_pcap_max_payload into a "superpacket" (21720B) -- the mandatory
agreement correctly FAILED on that case, never accidentally
accepting it.

**Additional finding, not requested but relevant (see Decision 100):**
in
BOTH MTU tests (a configured RTT=40ms), segments_computed
came out well below ss_ti_cwnd=10 -- TCP pacing (an observed
pacing_rate, 5,75-35,4Mbps) throttles sending independently of the
cwnd,
reproducing, in a controlled and repeatable way, the SAME phenomenon
Decision
95 already found against the real AWS (pending decision #2) --
strengthening that analysis: it is not a fluke of the real network,
it is a
generic pacing effect on any new connection (slow-start).

**Tests:** test_producers.py gains 6 (mss alongside cwnd in the
snapshot, effective_mss agreeing/disagreeing, a mutant "would use the
announced value by default"). test_evaluate_criteria.py gains 4
(criterion_2_initcwnd passes when they agree, fails when
mss_channels_agree=False/missing, a mutant replicating the
OLD logic that would incorrectly accept an ACCIDENTAL agreement
between
segments_computed with the wrong MSS and ss_ti_cwnd).

Same rules: no action on AWS, no commit before the scanner,
report in the chat.

## 99. Capture-robustness Amendment to criterion 1 -- dedicated_capture checks for IMMEDIATE and COMPLETE decryption (6 mTLS streams, the server's Certificate decrypted) before accepting a capture, RETRYING (up to 3x) ONLY when the failure mode is incomplete decryption, NEVER for a size divergence; preserves the pcap+keylog from EVERY attempt (success or failure)

**Luciano's request (item 3):** stop guessing the cause of the L0
decryption gap (Decision 95) -- make the capture ROBUST: before
finishing, check for immediate and complete decryption; if missing,
redo it (only
when the failure mode is incomplete decryption, never a size
divergence), up to 3x, logging each attempt; preserve the pcap and keylog
from all of them, including the ones that failed.

**Mechanism:** evaluate_criteria.py gains capture_decryption_
complete(raw_lines, expected_streams=6) -- it factors the per-stream
classification out (_classify_streams, extracted from
_message_sizes_stream_
aware without changing its behavior, confirmed byte for byte by the
entire suite passing) and checks that the expected_streams (6,
N_mTLS, Decision 91) real client-facing connections have the
SERVER's
Certificate decrypted (tls.handshake.type==11 readable) -- it NEVER
decides size/divergence, only WHETHER the capture decrypted enough
to be evaluated.

orchestrator.py's dedicated_capture is rewritten with a loop of UP TO
MAX_CAPTURE_ATTEMPTS=3 attempts: each uses its OWN pcap/keylog/log
(numbered _tentativaN), triggers a NEW connection, extracts via
tshark, checks capture_decryption_complete --
it only accepts and exits the loop when n_handshake_rows > 0 and
complete;
otherwise, it tries again (an extra 2s sleep, instead of 1s, before
the
docker exec cat of the keylog -- giving more time for the disk
flush,
Decision 95's hypothesis, but NEVER the only fix -- the retry covers
the case where it is still not enough). If all 3 attempts fail,
it raises with the complete log of each one (attempts_log) -- NEVER
masking, NEVER reporting an incomplete capture as if it were
complete.
The WINNING attempt is copied on the server to the name WITHOUT a
suffix
(criterio1_<profile>_<route>.pcap/.txt) -- run_criterio7
(dedicated_criteria.py) keeps finding the pcap by the same name, no
change.

**Preservation (item 0, Decision 96):** _preserve_capture_attempt
brings the pcap+keylog from EVERY attempt (success or failure) to the
local capturas_dir (capturas_brutas/), PLUS the winner under the
clean name -- no attempt is silently discarded.

**A size divergence never triggers a retry** (Luciano's explicit
requirement): the retry is only triggered by capture_decryption_complete() ==
False -- a capture that decrypted everything but diverges from the
baseline
(_message_sizes_stream_aware) is accepted and reported as is, never
retried.

**Tests:** test_evaluate_criteria.py gains 4 (capture_decryption_
complete with 6 complete streams, with a partial-L0 case reproducing
Decision 95's real symptom, with fewer than 6 streams, a mutant that
ignores a missing Certificate). test_orchestrator.py gains 4 (retries
when the 1st attempt is incomplete and the 2nd complete, fails after
the 3
attempts with decryption always incomplete, preserves the pcap/keylog
of
EVERY attempt including failures, a mutant "would accept a partial
capture
without checking decryption"), plus the shared fixture _TSHARK_FAKE_
OUTPUT updated to 6 streams (the real N_mTLS) instead of 1.

Same rules: no action on AWS, no commit before the scanner,
report in the chat.

## 100. LOCAL validation (without AWS) of Amendments 97/98 with GROUND TRUTH -- tc netem on real Docker containers (RTT 5/50/200ms, MTU 1500/9001), against the REAL producers (criterio2_probe.py/criterio7_rtt.py), with no modification nor monkeypatching

**Luciano's request (item 4):** validate the fixes locally with
ground truth -- tc netem on containers (--cap-add NET_ADMIN),
a configured RTT (5/50/200ms) and MTU/MSS (1500/9001), proving that
RTT and
initcwnd measured by BOTH channels match the configured values
within tolerance; mutants (wrong channel, SYN-ACK's MSS).

**Topology (a real finding, fixed live, documented in
campaign/tc_netem_ground_truth/IDENTIDADE.json):** the first
attempt (a symmetric 25/25ms delay on the EGRESS of both sides)
correctly measured the total RTT via ping, but the pcap SYN->SYN-
ACK channel showed 25ms (not ~0) -- investigated: tcpdump captures
EGRESS packets AFTER netem's delay has been applied, so a delay on
the SERVER's EGRESS contaminates the "SYN-ACK leaving" event itself
with an
artificial LOCAL delay that a real network never has (propagation
happens only ON THE WIRE, never as a local queue observable by the
sender itself). Fixed: delay ONLY on the CLIENT side -- egress
(outbound)
+ ingress via ifb (tc filter ... action mirred egress redirect dev
ifb0) -- correctly reproducing "zero local overhead, propagation
only on the wire", the SAME premise criterion 7's new method
assumes.

**Real results (criterion 7, RTT):** configured RTT 5ms -> the
probe channel 5,233ms / the NEW pcap channel 5,186ms. Configured RTT
50ms ->
the probe channel 50,353ms / the NEW pcap channel 50,564ms / the OLD
pcap channel
(the same pcap) 0,024ms. Configured RTT 200ms -> the probe channel
200,408ms
/ the NEW pcap channel 200,218ms.

Both real channels matched the configuration within +-2% across the 3
values (well within the criterion's +-10%); the OLD method, measured
against the SAME real packets captured at 50ms, confirms the
theorized symptom (local processing time, not RTT).

**Real results (criterion 2, effective MSS):** MTU 1500 -> ss -ti
mss=1448, the largest real payload (pcap)=1448, the announced
SYN-ACK=1460,
they agree=yes. MTU 9001 -> ss -ti mss=8949, the largest real payload
(pcap)=8949, the announced SYN-ACK=8961, they agree=yes.

Both effective-MSS channels agree EXACTLY across the two MTUs
tested; the one announced in the SYN-ACK always differs slightly
(overhead from
TCP options such as timestamp) -- it should never be used directly,
confirming Amendment 98. GSO on (an incidental finding before
turning the offloads off) inflated the pcap channel into a
"superpacket"
(21720B) -- the mandatory agreement correctly FAILED on that
case, never accidentally accepting it.

**Additional finding (not requested, reported for relevance):** in
both
MTU tests (RTT=40ms), segments_computed came out well below
ss_ti_cwnd=10 because of TCP pacing -- reproducing, in a
controlled, repeatable way, the SAME phenomenon Decision 95 reported
as
pending decision #2 against the real AWS (strengthening that
analysis, not
resolving it -- the pending decision remains with Luciano).

**No producer was altered for this test** -- it runs the SAME
criterio2_probe.py/criterio7_rtt.py that goes to AWS, with no
network monkeypatching whatsoever (only real containers/tc). The
containers,
networks and Docker images used were all REMOVED after the collection
(no persistent resource, no real IP, no credential).
Evidence (the real JSON from each run + an IDENTIDADE.json with the
complete method) in thesis/results/v9/campaign/tc_netem_ground_truth/.

Same rules: no action on AWS, no commit before the scanner,
report in the chat.

## 101. The fifth real attempt at Phase B -- the first with Amendments 96-99 really exercised on AWS: 6/7 PASS (criteria 1 and 7, the Amendments' direct targets, now PASS for the first time), only criterion 2 still FAILS, for the reason ALREADY known (pacing, never again the MSS bug). Teardown for the FIRST TIME really using the fail-closed gate (--pull-verified-marker, never --force)

**Context:** after Amendments 96-100 (previous Decisions), Luciano
authorized running all of Phase B again, without asking for
confirmation, to exercise criteria 1/2/7's fixes against the real AWS
for the
first time. Full autonomy maintained throughout the run
(this round's standard guardrails: regions sa-east-1/eu-north-1/
ap-southeast-1, the `mockopin-pqc-v9-piloto` tag, cost and time
monitored in real time).

**Real infrastructure findings, fixed live (none touches
what is measured):**

1. **The `mockopin-v9-measure` image mistakenly destroyed in this
   very
   session** (removed during the tc netem local validation cleanup
   in Decision 100, without noticing it was the SAME image the
   real pilot used) -- `deliver_images.py` correctly aborted (the
   `.tar`'s sha256
   did not match `PINS.json`, fail-closed working as
   designed). Fixed by rebuilding the image from the SAME Dockerfile
   (`docker build -f measure/Dockerfile .`) and **re-pinning ONLY the
   `measure` entry in
   `PINS.json`** (`tar_sha256`, the `rootfs_layers[3]` layer that
   changed -- only the copy timestamp metadata of
   `measure.sh`, never content --, and the informational `image_id`)
   --
   `config_subset` and the other 5 layers come out IDENTICAL,
   confirming
   nothing functional changed. Gateway/proxy/pqc-signer NEVER touched.
   This image is only capture tooling (tcpdump+tshark), never the
   system under test -- re-pinning the tar never affects any
   pre-registered criterion.
2. **Step 10 (the smoke gate): the SSH connection dropped** ("Connection
   reset by peer") mid-run -- the remote process (without
   `nohup`) died along with the session. Investigated live (including
   an independent investigation, evidence preserved at
   `piloto/tentativas/investigacao_passo10_2026-11-09/`, `conta_como_
   dado: false`, confirming via `docker ps` with real timestamps on
   the server that the process was genuinely progressing, never
   stuck, before the connection dropped). Fixed by relaunching with
   `nohup ... & disown`, immune to subsequent SSH drops -- used
   from here on for ALL long steps (Step 11, 11.5).
   **Additional finding, not fixed in code (documented for a
   future decision):** no SSH call in this pipeline uses
   `ConnectTimeout`/`ServerAliveInterval`/`ServerAliveCountMax`, and
   no runbook step has a time budget -- a real hang (vs. a hang) is
   indistinguishable from a genuine hang
   without manual investigation like this one. Recorded as a
   future improvement, never applied this round (no change mid-way
   through
   an ongoing real run).
3. **The safety auto-shutdown window (4h, Decision 23) turned out
   too short for this attempt's real scope** -- the smoke gate
   alone (12 runs) took ~45 min, leaving only ~1h13 for
   the 60 runs + 12 captures (with retry) + collection + consolidation +
   teardown. Fixed live, deliberately, WHILE actively supervised
   (never a "silent" extension -- Luciano present and
   confirming each step): `/etc/mockopin-campaign/deadline`
   rewritten on all 5 instances, twice, ending at
   server+3 clients = `2026-11-09T18:30:00Z`, control =
   `2026-11-09T19:30:00Z` (>=60min after the hosts, Luciano's
   explicit request -- the final collection goes through the
   control, which needs
   to survive longer than the hosts it still collects from). The
   real mechanism (a `systemd` timer, `shutdown -h now`, never
   releasing the
   EIP by itself) was read directly from the Terraform template
   (`safety_timer.sh.tftpl`) before acting -- it would NEVER be
   "renewed
   by the orchestrator" as an old comment in `variables.tf`
   suggested (`orchestrator.py` never implemented that -- a real
   finding, a
   pre-existing gap, never fixed this round because it is out of
   scope for Amendments 96-100).
4. **`collect_artifacts.py --remote-dir ~/campaign-data/v9/piloto`
   failed twice** with `cd: ... No such file or directory`,
   showing a LOCAL operator path (`/c/Users/.../campaign-
   data/...`) -- the `~` was expanded by the operator's OWN git-bash
   before reaching the script, never passed literally for the
   control to expand on its side (a pitfall already documented in
   this
   project). `MSYS_NO_PATHCONV=1` does NOT fix this (it only affects
   conversion
   of an absolute-path pattern, never bash's `~` expansion, which
   is a different mechanism). Fixed by putting `--remote-dir` in
   single quotes. Never a bug in `collect_artifacts.py` -- an
   operator invocation error, fixed on the spot, without changing the script.

**Cost/time monitored in real time throughout the run**
(Luciano present, direct, repeated checks via `describe-
instances`/process state/real file counts -- never
static estimates): projections recalculated at each real milestone
(the 1st
L0 block, the 1st L219 block, the 1st L325 block) -- all stayed within
the new thresholds (US$8 = alert, US$10 = pause-and-ask, never again
an automatic destroy for cost/slowness, a rule Luciano updated
this round, replacing the old 80%-never-triggers-mid-
pilot rule). Neither threshold was reached -- the final cost
~US$6,13 (US$4,20 from previous attempts + ~US$1,93 from this one),
the US$10 ceiling never threatened.

**Step 11 complete, real data confirmed in `piloto_calls.json`
(10,9MB, all 60 complete runs):** `total_execucoes: 60`,
`expected_total: 60`, **0 failed HTTP calls across the 60 runs**
(L0=20, L219=20, L325=20, confirmed by direct count). Median latency
per call, per route: L0=10,3ms, L219=235,6ms,
L325=341,9ms -- physically consistent with each route's nominal RTT
(0/219/325ms) + processing overhead, no anomalous route.

**The 7 criteria, this attempt's real values (consolidated in
`thesis/results/v9/piloto/dados_oficiais/piloto-real-aws-2026-11-09-
v2/`):**

| # | Criterion | Result | Note |
|---|---|---|---|
| 1 | Per-message sizes | **PASS** | across the 12 captures, including ALL the L0 ones (Decision 95's persistent gap) -- `n_streams=6`, 0 stream errors, 0 divergences, consistency `ok:true` in each capture's 6 connections, Certificate matching exactly the baselines derived in Decision 93 (913/5632/6255/6582) |
| 2 | Real initcwnd | FAIL | `mss_channels_agree: true` (Amendment 98 confirmed correct -- both effective-MSS channels really agree) -- but `segments_computed=2,0` vs. the threshold of 10, because of the SAME pacing already reported in Decision 95 (pending decision #2, still Luciano's) -- NEVER again the SYN-ACK-announced-MSS bug |
| 3 | Zero errors on the most distant route | **PASS** | 20/20 on L325, 0 errors |
| 4 | Flow counts | **PASS** | |
| 5 | Zero errors | **PASS** | 0/60 |
| 6 | Complete instrumentation + assertions | **PASS** | |
| 7 | Per-route latency sanity | **PASS** | Amendment 97 confirmed correct -- L0 probe=0,148ms/pcap=0,098ms; L219 probe=219,889ms/pcap=220,048ms (Δ0,159ms); L325 probe=330,196ms/pcap=330,859ms (Δ0,663ms) -- both channels genuinely agree, never just each one passing alone |

**Result: 6/7 PASS** (up from 4/7 in Decision 95) -- the TWO
criteria that were the direct target of Amendments 97 (criterion 7)
and 99
(criterion 1) now PASS for the first time. The sole FAIL (criterion
2) is the SAME finding already reported and pending Luciano's
decision --
not a new finding, and Amendment 98 is CONFIRMED correct (the
effective MSS now measures correctly; pacing is a separate METHOD
problem,
still undecided).

**Step 12 (collection): 92 files verified by sha256** (vs. 19 in
Decision 95) -- including, for the first time, the RAW pcaps/keylogs
from
every capture attempt (`capturas_brutas/`, confirming Amendment
99's retry really worked: `classico/L0` needed 3
attempts before decrypting completely and being accepted;
`classico/L219`
decrypted completely on the 1st attempt), `criterio2_probe.pcap`, and
`full_container_logs/` with the server's 4 containers (gateway/
auth/mongo_seed/mockapi) + lightweight per-instance diagnostics --
everything Decision 96 (the new fail-closed rule) asked for.

**Step 14 (teardown): FIRST TIME really using the fail-closed
gate.** `cleanup.py --pull-verified-marker /tmp/v9_piloto_
coletado/.pull-verified` (never `--force`) -- `"forced": false,
"reason": null`, `"all_clean": true` across the 3 regions. In previous
attempts (Decisions 90-95), the runbook always used `--force`,
never exercising the gate that had already existed in code since
Decision 96
-- this is the FIRST time teardown went through the real path,
without a bypass.

**Step 15 (independent verification): confirmed clean.** The 5
instances show up in `describe-instances` with `State.Name=
terminated` (normal AWS metadata retention, never a billed
resource) -- `describe-addresses`/`describe-security-groups`/
`describe-key-pairs` empty across the 3 regions, confirming
`cleanup.py`.

**This attempt's final cost:** ~US$1,93 (4,64h of fleet, 5
instances + 5 EIPs) -- total accumulated ~US$6,13, within the new
alert ceiling (US$8) and well below the pause ceiling (US$10).

**Evidence:** `thesis/results/v9/piloto/dados_oficiais/piloto-real-
aws-2026-11-09-v2/` (RELATORIO_PILOTO.md + criteria_evaluation.json +
raw/, 92 files verified by sha256, including the 60 real runs and the
raw captures from every retry attempt);
`thesis/results/v9/piloto/tentativas/investigacao_passo10_2026-11-
09/` (the investigation of finding 2 above, `conta_como_dado: false`).
The
previous result (`piloto-real-aws-2026-11-09/`, Decision 95, 4/7
PASS) remains intact as history -- never overwritten.

**Pending decision from Luciano, the sole remaining one:** criterion
2 --
should `segments_computed` use a different window/metric that does
not suffer
from pacing throttling, or does the method need revising? (the same
question as Decision 95, now reconfirmed with the MSS fixed --
never again a question of incorrect MSS).

**DATED NOTE (2026-11-09, same day, a correction after direct
investigation of the real pcap -- the original text above kept
intact, never
rewritten): the "TCP pacing" explanation above and from earlier
Decisions (94/95/100) for low `segments_computed` IS
SUPERSEDED BY Decision 102** -- reconstructing the pcap's real
timeline (frame by frame, microsecond timestamps) proved the 10
segments of the 1st flight go out ~9us apart from each other, ~1000x
FASTER than the reported `pacing_rate` would require -- NO
pacing signature in the real packets. The real cause was a
counting bug (`extract_mss_and_bytes_before_ack` stopped at the
FIRST
ACK packet seen, but under real RTT the client never sends just 1 ACK,
it sends SEVERAL arriving in a tight cluster -- the first covered
only 2 of the 10
real segments). Fixed in Decision 102 -- `segments_computed`
re-analyzed from the SAME preserved pcap comes out 10,0, matching
exactly
`ss_ti_cwnd=10`. **Criterion 2 PASSES** -- the "pending decision"
above
is RESOLVED, no longer an open question for Luciano.

Same rules: no action on AWS, no commit before the scanner,
report in the chat.

## 102. Window-robustness Amendment to criterion 2 -- a real finding investigated by content (never assumption): segments_computed=2,0 was NOT TCP pacing (Decision 101 reported it wrong) -- it was a counting bug by ACK number, never by send timestamp. Fixed, validated with real ground truth (initcwnd 4/10/20, with and without fq), re-analyzed OFFLINE from the SAME preserved pcap -- criterion 2 PASSES. Phase B: 7/7 PASS

**Investigation, at Luciano's explicit request: prove or disprove
pacing from the packets' real timeline, never by assumption.**
The complete timeline (microsecond timestamps,
tshark) of this round's real pcap (criterio2_probe.pcap, L219,
classico, already preserved by Decision 96) was reconstructed:

- The server's SYN-ACK leaves at t=.245875; the client's handshake
  ACK
  arrives at t=.465820 -- real RTT = 219,945ms (matching `ss -ti`:
  219,99ms).
- **The 1st flight's 10 segments leave between t=.484441 and
  t=.484522 --
  81us end to end, ~9us between consecutive segments.** The
  reported `pacing_rate` (1,05Mbps) would require ~11ms of distance
  between 1448B segments -- **~1000x slower** than what was
  observed. NO pacing signature in the real packets.
- The 1st flight has EXACTLY 10 segments (14.480B) -- matching exactly
  `ss_ti_cwnd=10` (a snapshot taken BEFORE any sending) and the
  2nd flight (20 segments, slow-start doubling from 10 to 20,
  starting at t=.704672).
- The server had 71.680B to send (5x more than 1 window of
  14.480B) -- never limited by a lack of data.
- The client sends 5 ACK packets arriving in a tight CLUSTER
  (t=.704618-.704619, acks 2897/5793/8689/11585/14481) -- the
  FIRST of these (2897) covers only the first 2 segments of the
  real flight of 10.

**Root cause confirmed:** `extract_mss_and_bytes_before_ack`
(Decision 94) stopped at the FIRST ACK packet it saw with `ack_num >
first_seq` -- under real RTT, the client never sends just 1 ACK, it
sends
SEVERAL arriving almost together, and the method only counted what
THAT
FIRST one covered (2 of 10 segments = 2896B), never the complete
flight. Decision
101 attributed this to TCP pacing -- **WRONG**, corrected by
the dated note in Decision 101 above.

**Branch, as requested:** the real `ss -ti`, taken BEFORE
any sending, reports `cwnd:10` -- NEVER less than 10. This is NOT
a host/kernel configuration finding (not a STOP) -- it is a
METHOD bug, fixed below.

**Fixed method (`criterio2_probe.py`):** `extract_bytes_sent_
within_rtt_window` counts the SERVER's data bytes by SEND
TIMESTAMP (never by ACK number), within the window `[the time
of the 1st data segment, +1 RTT]`. The RTT comes from an INDEPENDENT
measurement, on the SAME connection (`rtt_from_handshake_same_connection`:
the server's SYN-ACK LEAVING -> the client's handshake ACK ARRIVING
back --
the SAME method as criterion 7's RTT-pcap Amendment, Decision 97) --
never
derived from the behavior of DATA ACKs, which is exactly what
caused the bug. Robust to clustered ACKs and to a delayed/lost ACK,
because it never looks at the data ACKs to decide HOW MUCH was sent,
only HOW LONG to count. The field renamed from `bytes_sent_before_first_
client_ack` to `bytes_sent_within_first_rtt_window` (an explicit
deviation, never a name that lies about what it measures) -- a new field
`rtt_ms_used_for_window` recorded for auditing.
`evaluate_criteria.criterion_2_initcwnd` updated for the new field
name.

**Validated with ground truth BEFORE touching any real data**
(Luciano's explicit request) -- a real `ip route ... initcwnd N`
on the server (not assumed), N=4/10/20, the same tc
netem topology from Decision 100, against the real
`criterio2_probe.py`, with
no modification:

| Configuration | `ss_ti_cwnd` | `bytes_sent_within_first_rtt_window` | `segments_computed` |
|---|---|---|---|
| N=4, without fq | 4 | 5.792 | **4,0** |
| N=10, without fq | 10 | 14.480 | **10,0** |
| N=20, without fq | 20 | 28.960 | **20,0** |
| N=10, **fq (real pacing) on**, confirmed by `tc qdisc show` | 10 | 14.480 | **10,0** |

Both channels matched the real configuration EXACTLY in all 4 cases,
including
with real pacing active -- proving the method is NOT biased
toward always reporting 10. A mutant (a response of only 2,048B,
smaller than 1
window at cwnd=10): the method correctly reports 2,048B (never
pretends it is window-limited when it is genuinely limited by data).
Evidence in `campaign/tc_netem_ground_truth/evidencia_initcwnd/`.

**OFFLINE re-analysis of the real, already-preserved pcap (NEVER a
new
AWS round, exactly as requested) -- only AFTER the validation
above passed:** `criterio2_probe.pcap` (L219, classico, Decision 96)
re-analyzed by the fixed, validated method:

```
mss_pcap_max_payload = 1448 (mss_channels_agree=true, unchanged)
rtt_ms_used_for_window = 219,945
bytes_sent_within_first_rtt_window = 14.480
segments_computed = 10,0 (== ss_ti_cwnd, agree=true)
```

`thesis/results/v9/piloto/dados_oficiais/piloto-real-aws-2026-11-09-
v2/raw/criterio2_initcwnd.json` updated with the re-analyzed fields
(the ORIGINAL value, from the old, buggy method, kept
fully in `criterio2_initcwnd_original_bug_decisao_95_101.
json`, never deleted -- complete auditability). `criteria_evaluation.
json`/`RELATORIO_PILOTO.md` regenerated by `consolidate_v9_pilot.py`
against the SAME `raw/` (no new raw data).

**Phase B's final result, 5th attempt, re-analyzed: 7/7 PASS.**
The first time in this package's history with all 7 criteria passing
over 100% real AWS data.

**An honest method limitation, explicitly recorded (Luciano's
request, NEVER scope creep to resolve now):** `criterio2_probe.py`
only runs on the L219 route (`CRITERIO2_PROBE_ROUTE`, Decision 85 --
L0
excluded by design, RTT~0 makes the method meaningless; L325 was
NEVER
wired up, a pre-existing gap, never noticed before for lack of
evidence exposing it). The probe only measures the server->
client DIRECTION (the server sending data to the client that
connected) --
NEVER the client->server direction, which is relevant for the
CLIENT's OWN flights during the real mTLS handshakes (e.g., the
client's
Certificate, Finished). The pre-registered criterion (Decision
14/24/34)
does not explicitly specify route nor direction -- this is a real
COVERAGE GAP, declared here, never hidden, never resolved
this round.

**Tests:** `test_producers.py` gains 5 (MSS separate from the old
bug, the handshake's RTT matches the real one, a 1-RTT window counts
the complete
real flight -- 14.480B never 2.896B --, a mutant "counts by ACK
number"
reproducing the old bug, a mutant "wrong window" too short/long
errs the wrong way), using this pcap's REAL data as the fixture
(never
purely synthetic). `test_evaluate_criteria.py` updated for the new
field name. 263 tests in total, all green.

**A process finding, fixed live:** `consolidate_v9_pilot.py`
does `shutil.rmtree(dest_raw)` BEFORE `shutil.copytree(collected_
dir, dest_raw)` -- passing `--collected-dir`/`--out-dir` pointing to
the
SAME `raw/` (a real error this session) deletes the source before
copying
from it, `FileNotFoundError`. Recovered immediately via `git
checkout` (Decision 101's commit already had everything versioned)
--
no data genuinely lost, confirmed by `git status` before and
after. Fixed by reapplying the re-analysis to a STAGING copy outside
the
destination tree. Never a bug in `consolidate_v9_pilot.py` itself
(the script always assumed source != destination) -- an invocation
error,
recorded here to never repeat.

Same rules: no action on AWS, no commit before the scanner,
report in the chat.

## 103. Final consolidation of Phase B (Luciano's request): a static check for RSA-2048/no InsecureSkipVerify/no VerifyClientCertIfGiven in the current code; the final status of v8's 5 gaps; an honest re-analysis of v8's historical ~14% T_fluxo residual (Fact F); a consolidated list of methodological deviations for the thesis's methodology section

**(a) Static check, CURRENT code (not just as of the T4 date),
direct `grep`, never assumed:**
- `rsa.GenerateKey(rand.Reader, 2048)` -- **9 occurrences** across
  all the v9 Go code (`certs/main.go` x3, `integration/bench/main.go`,
  `integration/interop/main.go` x3, `integration/negtest/main.go`
  x2), **none with `4096`** -- the ONLY occurrence of the number
  `4096`
  in any `.go` file in v9 is an unrelated byte buffer
  (`integration/proxy/main.go:188`, `make([]byte, 4096)`) plus a
  comment confirming the absence. **CONFIRMED: RSA-2048 across
  the entire codebase, never RSA-4096.**
- `InsecureSkipVerify` -- **zero functional occurrences** in all of
  `integration/*.go` -- the ONLY line containing the string is a
  COMMENT (`proxy/main.go:216`) explicitly documenting that it
  was REMOVED. **CONFIRMED: absent.**
- `VerifyClientCertIfGiven` -- **zero occurrences**, anywhere.
  **CONFIRMED: absent.**
- `RequireAndVerifyClientCert` -- present in `gateway/main.go` (2x,
  both real TLS listeners) and `interop/run.go` -- **CONFIRMED: the
  correct, secure configuration is in use.**

**(b) v8's 5 gaps (Decision 18), FINAL status after the real Phase
B:**

| # | Gap | FINAL status | Numeric evidence |
|---|---|---|---|
| 1 | RSA-4096 (atypical) | **CLOSED, reconfirmed** | the static check (a) above, current code -- 9/9 `rsa.GenerateKey` with 2048, 0 with 4096 |
| 2 | The client never verified the server (`InsecureSkipVerify`) | **CLOSED (Luciano's explicit decision, 2026-11-09): the fix applied and exercised on the happy path across the 4 profiles; rejection out of scope.** Phase B's 60 real runs (Decision 101) confirm 0 errors with the gateway's CORRECT certificate, across the 4 profiles. | 60/60 real runs, 0 errors (Decision 101); `negtest/main.go` exists in the repository, never exercised against the real pilot -- rejection out of scope, by explicit decision, never a remaining gap |
| 3 | The server with an OPTIONAL client certificate (`VerifyClientCertIfGiven`) | **CLOSED (Luciano's explicit decision, 2026-11-09): the fix applied and exercised on the happy path across the 4 profiles; rejection out of scope.** | the same evidence as item 2 -- `RequireAndVerifyClientCert` confirmed in use (check (a)); Hibrido-AND already has the rejection path covered by T3's/`dual_test.go`'s 18 scenarios, the other 3 profiles do not -- rejection out of scope, by explicit decision |
| 4 | A contaminated handshake counter | **CLOSED** (already was, reconfirmed by Phase B: `raw_in==gateway_in`/`raw_out==gateway_out` consistency EXACT across the 12 official captures, Decision 101/criterion 1) | 12/12 captures, 100% byte-for-byte consistency |
| 5 | Per-message size and the time residual never measured/isolated | **PARTIAL, advanced but not closed** -- per-message size: **CLOSED** (12/12 real captures, Decision 101, criterion 1 PASS); the TIME residual: see item (c) below -- the RTT-extra-per-initcwnd hypothesis is now RULED OUT with confirmed real data (not just assumed), but v8's ~14% T_fluxo residual (the "HTTP calls" phase, Fact F) still has NO isolated cause, the SAME conclusion as v8's final report | see (c) |

**(c) An honest re-analysis of v8's historical residual (~14% of
T_fluxo,
Fact F, `v8/Consolidated_Metrics_Report_FINAL.md` Section 6) with
v9's real
components -- NEVER a forced attribution:**

v8's real numbers (sa-east-1/L0, the near-zero-RTT reference route):
HTTP calls 361,9/335,4/410,7ms; Signing 16,2/26,9/44,7ms;
Verification 25,1/26,3/28,2ms; Setup/teardown (fixed) 1.071,2/1.095,2/
1.071,6ms; **Residual 240,1/260,3/253,9ms = 13,8%/15,0%/14,0% of
T_fluxo** (Classico/PQC/Hibrido). v8's own report already
investigated this (a complete timeline of a real high-RTT run)
and concluded "more consistent with client-side sequencing
(the 6 connections are neither kept continuously busy nor run in
parallel) than with extra network RTTs within a SINGLE
connection's handshake" -- **not attributed with confidence**.

**Tested with v9's real components:**
1. **The RTT-extra-per-initcwnd hypothesis: NOW RULED OUT with
   confirmed REAL data, not just assumed.** Decision 14's formula
   (`extra RTTs = max(0, ceil(flight_bytes/cwnd_bytes)-1)`) already
   showed 0 extra RTTs for the 4 profiles with an assumed
   `initcwnd=10` --
   Decision 102 now empirically CONFIRMS (a real `ss -ti` + a real
   pcap, not an assumption) that the pilot's real instances genuinely
   have `initcwnd=10`. **Conclusion: 0ms of the 240-260ms residual
   can
   come from this mechanism, for NONE of the 4 profiles, on NONE of the
   pilot's routes** -- reinforcing (not re-proving for v8 literally,
   these are
   different instances, but removing the same class of doubt v8
   had) v8's own report's conclusion that the residual
   does NOT originate from extra network RTT.
2. **v9's CPU microbenchmarks (Decision 14) are ORDERS OF
   MAGNITUDE smaller than v8's "signing"/"verification" PHASES --
   finding that the two tables are NOT the same quantity, they cannot be
   added directly.** The cost of PURE RSA-2048 signing+verification
   (just the cryptographic operation, N=2000): ~858us (0,858ms) --
   against
   the 16,2ms (Classico) v8's "signing" PHASE reports, ~19x larger.
   This means v8's "signing" PHASE **never measured just the
   pure cryptographic operation** -- it includes Go's `crypto/tls`
   overhead, buffer
   I/O, or a wider measurement boundary than the isolated
   operation. **Honest conclusion: v9's CPU components
   CANNOT be arithmetically added to v8's residual to
   "explain" a fraction of it -- the two tables measure
   different quantities, a direct-sum attempt would produce a
   meaningless number.**
3. **Ticket cost: NEVER applies to this residual.** v9 runs
   with `TICKETS_DISABLED=true` (confirmed in the pilot's real
   environment,
   Decision 101/the gateway's env) -- v9's residual, if there were one,
   would NEVER
   include ticket cost. The historical v8 may or may not have had
   tickets contributing to ITS original residual -- **a real
   asymmetry
   between the two setups, declared here, never hidden.**

**Final, honest conclusion, NEVER forced:** v9's real
components do not attribute v8's historical ~14% residual to a
specific new cause -- they remain the SAME conclusion as v8's final
report
("not attributed", client-side sequencing, not network).
What v9 ADDS that is real: the RTT-extra-per-initcwnd hypothesis
is now ruled out with empirical confirmation (not assumption), and the
scale incompatibility between v9's CPU microbenchmarks and
v8's time phases is explicitly documented (preventing an
invalid arithmetic sum a hasty reader might attempt). Gap #5 remains
**PARTIAL, not CLOSED** -- kept honest, never
forcibly closed.

**(d) a CONSOLIDATED list of this Phase B's methodological
deviations, for
the thesis's methodology section (cross-referenced, none hidden):**

| Decision | Deviation | Reason | Declared for the thesis? |
|---|---|---|---|
| 61 | The `gateway`'s Image ID in `PINS.json` re-pinned (the original image no longer exists locally) | binary/certificates/base layer confirmed identical by CONTENT (never rebuilt) -- only the Image ID (already known to be non-reproducible across Docker versions, Decision 68) changed | Yes -- never affects what is measured, only the image's identity verification |
| 75 | A SAN with a real IP (`SERVER_IPS`) ruled out, never applied to the pilot | the delivered certificates confirmed identical to the ones already embedded in the pinned images | Yes |
| 91 | Criterion 1's message classification method (by direction/stream, never by co-occurrence on the same line) | a real network fragments the server's flight across more than one tshark line -- loopback never showed this | Yes -- a MECHANISM fix, never of the criterion/thresholds |
| 93 | `CERTIFICATE_BASELINE` recalibrated by DERIVATION (an RFC 8446 formula from the real DER) instead of the old value | Decision 75 (the same session) had reversed the premise that motivated the old value, without rechecking the baseline | **Yes, a formal pre-registration deviation, explicitly declared** |
| 97 | Criterion 7's pcap channel measures SYN-ACK leaving -> ACK coming back (never SYN arriving -> SYN-ACK leaving) | the old method only measured the server's local processing time, never real network RTT | Yes -- a MECHANISM fix, never of the threshold (±10%, the L0 floor) |
| 98 | Criterion 2's effective MSS comes from the `ss -ti`/largest real pcap payload agreement (never from the MSS announced in the SYN-ACK) | the SYN-ACK announces the NIC's LOCAL capacity (jumbo), never the MSS actually used on the real path (PMTU discovery) | **Yes, a formal pre-registration deviation (Decision 34), explicitly declared** |
| 99 | Criterion 1 retries the capture (up to 3x) when decryption comes out incomplete | a real L0 finding (Decision 95) -- the keylog might not be fully flushed to disk | Yes -- it never retries for a SIZE divergence, only for incomplete decryption |
| 102 | `bytes_sent_within_first_rtt_window` counts by send timestamp within 1 RTT (never by ACK packet number) | the old method (Decision 94) still disagreed under real RTT with clustered ACKs -- confirmed by pcap content, never pacing as Decision 101 mistakenly reported | Yes -- a METHOD Amendment, validated with ground truth before applying it to real data |

Same rules: no action on AWS, no commit before the scanner,
report in the chat.

## 104. A FORMAL AMENDMENT to the `v9-prereg` pre-registration -- the official, complete list of every method deviation/adjustment made during the entire pilot (Decisions 61/75/91/93/97/98/99/102), with what changed, the reason, and whether it is a formal pre-registration deviation or just a mechanism fix; the `v9-ferramentas-congeladas` tag created at the current commit -- the official campaign runs with the tools EXACTLY as frozen at this tag

**Luciano's explicit request.** This is the official, FORMAL
AMENDMENT
that closes out the deviation record for this entire pilot round --
never an informal list. No item below rewrites the
original text of Decisions 1-100 (all remain intact, visible,
never overwritten) -- this Amendment only CONSOLIDATES, in a single
official table, what was already scattered Decision by Decision,
explicitly declaring which item is a FORMAL pre-registration
deviation (it needs
to be in the thesis's methodology section) and which is just a
MEASUREMENT-MECHANISM fix (never changing what is measured, nor
needing to go
into the limitations/methodology section as a deviation, only as an
implementation note).

**Official, complete table, Decisions 61 through 102 (all of this
round's Phase B):**

| Decision | What changed | Reason | A FORMAL pre-registration deviation? |
|---|---|---|---|
| 61 | The `gateway`'s Image ID in `PINS.json` re-pinned (the original image no longer exists locally) | binary/certificates/base layer confirmed identical by CONTENT (never rebuilt) -- only the Image ID (already known to be non-reproducible across Docker versions, Decision 68) changed | **NO** -- only image-verification metadata, never what is measured |
| 75 | A SAN with a real IP (`SERVER_IPS`) ruled out, never applied to the pilot | the delivered certificates confirmed identical to the ones already embedded in the pinned images | **NO** -- a design decision reversed BEFORE any real measurement used it |
| 91 | Criterion 1's message classification method (by direction/stream, never by co-occurrence on the same line) | a real network fragments the server's flight across more than one tshark line -- loopback never showed this | **NO** -- a MECHANISM fix (a parsing bug), never of the criterion/thresholds/baselines |
| 93 | `CERTIFICATE_BASELINE` recalibrated by DERIVATION (an RFC 8446 formula from the real DER) instead of the old value (913/5632/6255/6582, previously 899/5618/6241/6554) | Decision 75 (the same session) had reversed the premise that motivated the old value, without rechecking the baseline | **YES -- a formal deviation, explicitly declared** (the original pre-registration had a wrong number, never the calculation method itself) |
| 97 | Criterion 7's pcap channel measures SYN-ACK leaving -> ACK coming back (never SYN arriving -> SYN-ACK leaving) | the old method (Decision 35) only measured the server's local processing time, never real network RTT | **NO** -- a MECHANISM fix, the threshold (±10%, the L0 floor, Decision 32) and the pre-registration's TWO channels (probe+pcap, Decision 35) remain exactly the same |
| 98 | Criterion 2's effective MSS comes from the `ss -ti`/largest real pcap payload agreement (never from the MSS announced in the SYN-ACK) | the SYN-ACK announces the NIC's LOCAL capacity (jumbo), never the MSS actually used on the real path (PMTU discovery) | **YES -- a formal deviation, explicitly declared** (Decision 34 said "MSS read from the SYN's options", without distinguishing announced-vs-effective -- the literal reading used the SYN-ACK) |
| 99 | Criterion 1 retries the capture (up to 3x) when decryption comes out incomplete, preserving the pcap/keylog from every attempt | a real L0 finding (Decision 95) -- the keylog might not be fully flushed to disk | **NO** -- it never retries for a SIZE divergence (only for incomplete decryption), it never changes the criterion nor the baselines |
| 102 | `bytes_sent_within_first_rtt_window` counts by send timestamp within 1 RTT (never by ACK packet number) | the old method (Decision 94) still disagreed under real RTT with clustered ACKs | **NO** -- a MECHANISM fix (a counting bug), the threshold (>=10 segments, Decision 14/24) and the pre-registered method (a dedicated test >=64KB, two channels, Decision 34) remain the same |

**Summary: 2 FORMAL pre-registration deviations across the entire
round**
(Decisions 93 and 98 -- both already declared individually in their
own Decisions, now consolidated here for the thesis's methodology
section) -- **6 MECHANISM fixes** (61, 75, 91, 97, 99, 102),
none of which changes what is measured, the thresholds, or the
pre-registration's baselines.

**Tool-freeze tag: `v9-ferramentas-congeladas`**,
created at this branch's (`v9/fase1-local`) current commit -- **the
official campaign (960 runs, 8 routes) runs with the measurement
code EXACTLY as frozen at this tag, no further method
change without a new, numbered Amendment.** No action on
`main`/`v9-prereg` -- both remain untouched, exactly as
the original authorization requires.

Same rules: no action on AWS, no commit before the scanner,
report in the chat.

---

## Decision 105 -- BLOCK B (offline, preserved old data, without AWS): real extraction of hibrido-and's dual signature + an encoding-bug finding in the experimental stack

Luciano's request (BLOCK B, item 1/2/3): extract, from the handshake's REAL Certificate message (never from the source code), the two certificates involved in hibrido-and's dual signature, with proof that both were validated; and replace the inference by `openssl asn1parse` of the pqc profile's ML-DSA certificate with a direct tool reading.

**Real finding 1 -- the `tshark --export-objects x509af` exporter is insufficient:** when extracting certificates from the 12 official pcap+keylog pairs (`raw/criterio1_capturas/`), the exporter correctly reassembled the RSA certificates for classico/hibrido-v8/pqc, but for hibrido-and it produced, besides the 2 expected RSA certificates, 11-12 unnamed 23-24 byte objects (`(null).cer`) -- fragments, never valid certificates (`openssl` cannot decode them). Investigated thoroughly (never dismissed as "noise"): hibrido-and's real Certificate message (confirmed via `tshark -x` with the keylog, reading the "Decrypted TLS" block tshark prints, and manually parsing the RFC 8446 Section 4.4.2 structure in Python) contains **TWO real CertificateEntry items in the SAME message**: an RSA-2048 one (serial 10 server/11 client, `CN=hibrido_and_rsa_{server,client}`) and an ML-DSA-65 one (serial 12 server/13 client, `CN=hibrido_and_mldsa_{server,client}`) -- with **3 zero-padding bytes the RFC does not anticipate between the two entries** (a real encoding bug in this profile's experimental stack, not a parsing error in this project -- confirmed reproducible across the 3 routes, server and client, 12 identical occurrences).

**Proof the extraction matches the real material:** the 2 ML-DSA certificates extracted from the pcap (server and client) have a sha256 IDENTICAL, byte for byte, to the real `.crt` files on disk (`certs/generated/hibrido_and_mldsa_{server,client}.crt`, the real PKI used in deployment, never the source code) -- 4/4 checks `identical: true` (RSA+ML-DSA, server+client).

**Real finding 2 -- proof that both were validated:** `raw/full_container_logs/v9-mtls.log` shows 6/6 of hibrido-and's real connections (excluding the unrelated internal channel `clientCert="op"`) with `dualAuthenticated=true` and real `handshakeBytesIn`/`handshakeBytesOut` (e.g., 11902/12177 bytes) -- consistent with the additional volume of the ML-DSA certificate (~5,5KB) over hibrido-v8's RSA-only volume (~8,4KB total). The TLS stack (Go `crypto/tls`) only reaches "connection OK" after processing the entire Certificate message (both entries) without error -- an honest limitation recorded: the INFO-level log does not distinguish "I verified RSA" from "I verified ML-DSA" as separate lines; the available evidence is the aggregate result, never a per-certificate trace.

**Real finding 3 -- replacing `openssl asn1parse`:** a minimal, generic DER parser was written in Python (`read_der_len`/`read_der_tlv`/`der_oid_to_str`/`parse_der_certificate_generic`, in `build_consolidated_report_v9.py`) that reads the OID and the byte sizes of the public key and the signature DIRECTLY from the ASN.1 structure (`SubjectPublicKeyInfo`/`signatureValue`), without depending on any library having NATIVE support for the algorithm (the available `cryptography` 46.x library and `openssl` 3.2.4 cannot load an ML-DSA key) and without cross-validating against JWKS (Decision 103's method, now replaced as the primary source -- agreement with the real JWKS remains as secondary corroboration, never the primary evidence). Confirmed: ML-DSA-65 (OID 2.16.840.1.101.3.4.3.18) in both pqc AND hibrido-and's PQC component, a raw public key of 1952 bytes, a raw signature of 3309 bytes -- EXACTLY the same in both profiles (an automated check FAILS LOUDLY, never just logging, if this diverges).

**Never a pre-registration deviation** -- this is an evidence-EXTRACTION technique for a descriptive report, never one of the pilot's 7 pre-registered criteria/thresholds/methods. No new data collected, no image rebuilt, no action on AWS -- only a deeper reading of the SAME already-preserved pcap+keylog (`piloto-real-aws-2026-11-09-v2/raw/`) and of the SAME already-preserved log file, cross-checked against real PKI files on disk (never source code, never committed -- `certs/generated/` is not tracked by git).

**Dated correction (2026-11-09, same day, Luciano's request via the coordinator):** the paragraph above ("Real finding 1") calls the 3 zero bytes between the two CertificateEntry items "a real encoding bug in the experimental stack" -- **that is WRONG**. We went straight to the patch's source code (`toolchain/patches/and.patch`, the `marshalDualCertificate` function, lines ~1889-1928) and confirmed: it is an **intentional delimiter of the AND mechanism**, explicitly documented in the patch's own comment -- "a 3-zero-byte delimiter entry carrying NO extensions field at all" -- used by `unmarshalDualAwareCertificate` (the same patch, ~line 1960) to separate the classical chain from the post-quantum chain within the SAME `certificate_list`: any entry with zero-length `cert_data` is recognized as the delimiter (never a real certificate, which never has zero bytes), explicitly rejecting a repeated or edge-positioned delimiter. **An implementation feature, not a bug.**

Also confirmed, at Luciano's explicit request, that `CERTIFICATE_BASELINE["hibrido-and"]` (6582, Decision 93/98, `integration/evaluate_criteria.py` line 145) **ALREADY accounts for these 3 bytes correctly** -- the formula uses `_tls13_certificate_message_size([914, 5647], extra_extension_bytes=[0, 3])`, whose result (6582) matches EXACTLY the real value measured in 2 independent captures (Decision 84 local, Decision 92 AWS) and in this very round (`Certificates Length: 6574`, `tls.handshake.length: 6578`, a decrypted buffer of 6582 bytes -- all confirmed this session). A precision note (never a numeric discrepancy, only the source code's prose explanation): the comment on lines 140-143 of `evaluate_criteria.py` attributes the 3 bytes to "a REAL extension of the ML-DSA leaf" -- reading the patch, they are actually the delimiter's 3 bytes (its OWN `CertificateEntry`, zero bytes of `cert_data`, no extensions field at all), which sits BEFORE the ML-DSA leaf, not INSIDE it. The TOTAL byte sum is identical under both readings (919 RSA + 3 delimiter + 5652 ML-DSA = 6574 = 919 RSA + 5655 "ML-DSA with extra_extension_bytes=3") -- so the baseline number (6582) remains correct and needs no fix at all; only the code comment's explanatory sentence attributes those 3 bytes to the wrong structural element. Reported here as requested (never fixed without authorization) -- if Luciano wants, the comment on `evaluate_criteria.py` lines 140-143 can be adjusted in a future session to cite the delimiter instead of "the ML-DSA leaf's extension", without changing any number.

**The 14-byte difference between hibrido-and's RSA DER (914B) and classico's (900B), a concrete cause identified (never assumed):** comparing the two real certificates extracted this session, field by field -- an identical SAN on both (the same 10 entries, same order, same bytes), an identical public-key size (270B DER, 2048 bits), an identical signature size (256B), no Alt-Signature/Catalyst extension (Bindel et al.) present in EITHER one (hibrido-and's RSA leaf is a pure X.509 certificate, with no extension beyond KeyUsage/EKU/AKI/SAN, the same 4 classico has) -- the ONLY real difference is the length of the CN strings: `CN=classico_server` (15 characters) vs. `CN=hibrido_and_rsa_server` (22 characters, +7 bytes) in the Subject, and `CN=classico_ca` (11 characters) vs. `CN=hibrido_and_rsa_ca` (18 characters, +7 bytes) in the Issuer. +7B +7B = **+14B, exact**, closing the complete difference with no residual. It is not a different CA chain (depth 1 in both, a direct root CA), not the serial (both fit in 1 INTEGER byte, serial 2 and serial 10), not validity (the same UTCTime format in both).

## Decision 106 -- A new official-campaign parameter: a maximum 30-minute interval between windows (declared as a deviation)

Luciano set (via the coordinator, 2026-11-09, after Decision 104) that the future official campaign (960 runs, a new AWS account) runs in **3 windows of N=10**, with **at most a 30-minute interval between one window and the next**. This is **a NEW parameter, never before specified** in any prior Decision in this package -- the real pilot (`piloto-real-aws-2026-11-09-v2`) ran in a single continuous window, with no planned interval between sub-blocks, and no prior Decision (1-104) defined an interval discipline between windows for the official campaign.

**Declared deviation:** this is NEITHER a mechanism fix NOR an Amendment to the PILOT's pre-registration (which already closed 7/7 PASS and remains untouched, along with the `v9-ferramentas-congeladas` tag -- neither is touched by this Decision). It is a NEW parameter for the OFFICIAL CAMPAIGN's method, which has not yet run -- recorded here, as is customary in this project, to be included in the thesis's methodology before the real run. Documented in `campaign/REQUISITOS_CAMPANHA_OFICIAL.md` (section "Additional official-campaign parameters, set by Luciano on 2026-11-09") and reflected in scenario (a)'s cost/duration estimate (18,72h base + 2 intervals x up to 30min = ~19,72h, ~US$18,15 -- arithmetic already shown, confirmed with no correction needed: the earlier number ALREADY summed the 30-min intervals, never the pilot's observed ~3h of setup overhead, which is a different thing -- infrastructure setup, not an interval between measurement windows).

No action on AWS, no change to the `v9-ferramentas-congeladas` tag (it stays exactly where it is) -- a purely documentary Decision.

## Decision 107 -- BLOCK A: generalizing the orchestrator/tools to N servers (the official campaign, 3 servers/8 routes), never rewriting the pilot's already-validated logic

Luciano decided (via the coordinator, 2026-11-09, after BLOCK A reported that the pilot's real orchestrator (`orchestrator.py`) assumes a SINGLE server throughout its code -- `_server_ip()`, `_server_gateway_ip(route)`, `_gateway_logs()`, `_launch_gateway()`, `_deliver_backend_images()`, `dedicated_criteria.collect_full_logs()`/`run_criterio2()`, `deliver_source.py`, `pki_relay.py` -- and that the official campaign's real topology (7 regions, **3 servers** in sa-east-1/us-east-1/ap-northeast-1, 8 routes, per the real Terraform in `terraform_campanha_oficial/`, a finding already recorded in `outputs.tf`'s own comment) would never run without adaptation): **ADAPT** the orchestrator to generalize to N servers, never rewrite the pilot's already-validated logic (7/7 PASS, Decisions 96-103). Five rules applied, in this order:

**1. The `v9-ferramentas-congeladas` tag was never touched.** Confirmed in this Decision: `git rev-parse v9-ferramentas-congeladas` still points to the SAME commit (`eca35772ccc38aed69ffe1d02745ca0ad9952d83`) as when it was created -- no tag command run this round. All the generalization below was done by editing the `v9/fase1-local` branch's current working state, never moving nor recreating the tag it freezes.

**2. A complete inventory of single-server assumptions, BEFORE changing anything** (findings, not assumption -- each item read directly in the code):
- `orchestrator.py`: `_server_ip()`, `_server_gateway_ip(route)`, `_gateway_logs()`, `_verify_gateway_binary`, `_verify_running_gateway_binary`, `_deliver_backend_images()`, `_launch_gateway()`, `start_block`/`stop_block` (the inventory mutated via a fixed `self.inventory["server"][...]`), `readiness_probe`/`run_execution`/`dedicated_capture` (likewise), `capture_ready_check()` (it only tested `[self._server_ip()]`, never all servers).
- `dedicated_criteria.py`: `collect_full_logs()` (only one `server_ip`, never per-server), `run_criterio2()` (no direction parameter -- only server->client, never client->server; no label support, preventing reuse on L325/other routes simultaneously).
- `cleanup.py`, `emergency_stop.py`, `iam_dryrun_check.py`, `preflight.py`: an independent, HARDCODED region list in each of the 4 files -- a risk of divergence among them and between them and the real Terraform (the highest-risk finding, Finding #4, Luciano's condition 2).
- `deliver_source.py`: a fixed `inventory["server"]["public_ip"]` -- it would only deliver `SERVER_ONLY_FILES` to the first/only server, never to the campaign's other 2.
- `pki_relay.py` (`main()`): the same pattern, `targets` built with a single fixed `"server"` target.
- Terraform (`terraform/modules/campaign_instance/main.tf`): the `Project` tag hardcoded to the PILOT's value in 6 places -- a real bug found and fixed BEFORE any apply (see below), not listed as an orchestrator finding but from the same inventory.
The complete list reported to Luciano (via the coordinator) as a checkpoint before any implementation, as rule 5 below itself authorized.

**3. Proof of compatibility (the 1-server/3-route pilot identical byte for byte).** Created `campaign/tests/_orchestrator_pre_generalization_baseline.py`: a LITERAL snapshot (`git show HEAD:...`) of `orchestrator.py` at the commit immediately before any generalization edit -- a frozen fixture, never edited afterward. A new test, `campaign/tests/test_pilot_regression_n_servidores.py`, loads that baseline via `importlib.util.spec_from_file_location` under a distinct module name, runs both versions (the baseline and the current one) against the SAME pilot inventory, and compares literally: `_server_ip()`, `_server_gateway_ip()` (3 routes), `_client_ip()` (3 routes), and the list of SSH commands captured from `_gateway_logs()` -- 5 tests, an IDENTICAL result between the two versions, proof by a real diff, never by visual code inspection. The pre-existing complete suite (263 tests) remains 100% green, with no assertion change needed in ~95% of the file (only 2 tests needed a signature/assertion adjustment for a legitimate API change -- `_backend_delivered` from `False` to `set()`, `_launch_gateway` gaining `route=None` -- never for a behavior regression).

**An approved design (region-suffixed labels + a ROUTE_SERVER map):** created `campaign/scripts/campaign_topology.py` as the single source of truth for the campaign's topology -- `CAMPAIGN_REGIONS` (7), `CAMPAIGN_SERVERS` (3), `CAMPAIGN_ROUTE_SERVER` (a route->server dict, 8 entries: `L0-sa-east-1`/`L123`/`L219`/`L325` -> sa-east-1, `L0-us-east-1`/`L14` -> us-east-1, `L0-ap-northeast-1`/`L30` -> ap-northeast-1 -- only the 3 `L0` routes need a region suffix to become unique; `L123`/`L219`/`L325`/`L14`/`L30` were already globally unique and stay as they were, with no change to any existing file/dict that indexes them by that name). `orchestrator.py` gained `route_server=None` in `__init__` and a single new indirection point, `_server_key(route=None)`: it returns `self.inventory["server"]` (the pilot, the old behavior untouched) when `route_server is None`, or `self.inventory["servers"][self.route_server[route]]` (the campaign) when configured. ALL the rest of the file that used to read `self.inventory["server"]` directly now reads through `_server_key`/`_server_ip(route)`/`_server_gateway_ip(route)` -- no duplicated logic, a single source of truth for "which server answers for this route."

**Condition 2 (a single source for regions, Finding #4, the highest risk):** `campaign_topology.regions_from_terraform()` extracts via regex the real regions declared in `terraform_campanha_oficial/providers.tf`; a dedicated test, `test_campaign_regions_bate_com_terraform_real` (in `test_campaign_topology.py`), automatically FAILS if `CAMPAIGN_REGIONS` (the Python constant) and the real Terraform regions ever diverge -- never again a silent misalignment. `cleanup.py`, `emergency_stop.py`, `iam_dryrun_check.py`, `preflight.py` now consume `campaign_topology.CAMPAIGN_REGIONS` (a `--campaign` flag/`regions=` parameter, default `None` preserves the pilot's old behavior unchanged). `cleanup.py` gained `CAMPAIGN_EXPECTED_RUNNING_INSTANCES = 1 + len(CAMPAIGN_SERVERS) + len(CAMPAIGN_ROUTES)` (= 12), threaded through `count_running_instances_all_regions`/`check_self_terminate_drift`/`full_cleanup`.

**Condition 3 (a label-to-scenario equivalence table):** `CAMPAIGN_SCENARIO_TABLE` in `campaign_topology.py` -- a list of dicts, one row per route, with `rota`/`servidor`/`regiao_cliente`/`nominal_rtt_ms`/`colocalizado`, covering the campaign's 8 routes. This is the official route<->scenario equivalence table for use in the thesis; recomputable by script (never a hand-typed number), a source derived from the same `CAMPAIGN_ROUTE_SERVER`/`CAMPAIGN_NOMINAL_RTT_MS` the rest of the code uses (never a second, parallel source that could diverge).

**Condition 4 (finding 10, complete logs, criterion 2 per server including L325 and the client->server direction):**
- A CPU/mem-steal sampler: `_cpu_steal_sampler_start`/`_cpu_steal_sampler_stop_and_collect`/`_steal_pct_from_cpu_jsonl` in `orchestrator.py` -- a faithful port of the mechanism ALREADY PROVEN in the real v8 (`campaign_run.py`: a Python loop backgrounded via SSH, `nohup ... & echo $! > pid_path`, one JSON line per second from `/proc/stat`+`/proc/meminfo`, steal% computed as the CUMULATIVE DELTA between the first and last line, never an average nor a since-boot ratio). Gated entirely on `self.route_server is not None` -- zero effect, zero new call, on the pilot's path.
- `dedicated_criteria.collect_full_logs()`: generalized to collect logs from ALL servers in campaign mode (previously, only one); the report key includes the server's label when there is more than one, preserving the old (unlabeled) key in the pilot.
- `dedicated_criteria.run_criterio2()`: gained `direction` (`"server-to-client"`, the default -- reproducing the pilot byte for byte -- or `"client-to-server"`, new) and `label` (`None` preserves the pilot's old fixed remote/local paths; any label produces separate `*_{label}.*` paths). A new `run_criterio2_campaign()` covers the 5 non-L0 routes (the 3 `L0` ones are co-located, nominal RTT zero, out of criterion 2's scope) x the 2 directions, including **L325 explicitly** (one of the two gaps that had been documented as out of scope, now closed in code) -- per-combination failures are captured individually (`{"ok": bool, ...}`), never aborting the rest.
- The infrastructure missing to enable the client->server direction (the OTHER gap, also now closed): the pilot's/campaign's Security Group only opened port 9876 on the SERVERS (for the client to initiate the test connection) -- never on the clients. A new `criterio2_reverse_ingress_cidrs` variable (default `{}`, no effect on the pilot) and a new `aws_vpc_security_group_ingress_rule.criterio2_probe_reverse` resource in `terraform/modules/campaign_instance/main.tf`, applicable only to `role == "client"`. Wired into the 5 non-L0 client modules in `terraform_campanha_oficial/main.tf` (`client_ca_central_1_a`/`_b`, `client_eu_north_1`, `client_ap_southeast_1`, `client_ap_northeast_2`), each scoped to the `/32` of the specific server it serves (never a broader CIDR).
- `deliver_source.py`/`pki_relay.py`: generalized in the same pattern (a plural `inventory["servers"]`, a dict per region-server, iterating and delivering/relaying to EACH one; the singular `inventory["server"]`, the pilot, preserves the old path -- the same target name "server", the same "server.crt"/"server.key" file pair -- identical byte for byte).

**A real bug found and fixed before any real apply (a finding of this round, not of the original inventory):** `terraform/modules/campaign_instance/main.tf` had the `Project` tag hardcoded to the PILOT's value (`"mockopin-pqc-v9-piloto"`) in 6 places -- the official campaign, reusing this module without modification, would have tagged EVERY resource with the WRONG tag, never matching the new account's least-privilege IAM policy's `aws:RequestTag/Project`/`ec2:ResourceTag/Project` condition (RunInstances/AllocateAddress/etc. would be denied by a correct policy reacting to a wrong tag). Fixed via a new `project_tag` variable (default = the old literal -- the pilot never passes this value, the pilot's plan demonstrably untouched via a real `terraform validate`/`plan`) + `terraform_campanha_oficial/` passing `project_tag = var.project_tag` (default `"mockopin-pqc-campanha-oficial"`) explicitly in all 12 modules.

**Real validation, not just a code read:**
- The complete Python test suite (`campaign/tests/`): **285 passed** (263 original + 19 new ones from finding-10/topology/regression/campaign + 3 new ones from this latest deliver_source/pki_relay round), 0 failures, confirmed by running it right now in this Decision.
- `terraform validate` in `terraform/` (the pilot): Success, the pilot's config unaffected by the shared module's generalization.
- `terraform validate` in `terraform_campanha_oficial/`: Success.
- A REAL `terraform plan` against the new account (`mockopin-pqc-campanha`), with plan-only variables (never used in a real apply): **78 resources to add, 0 to change, 0 to destroy, 0 errors** -- the previous 73 + 5 new `aws_vpc_security_group_ingress_rule.criterio2_probe_reverse` (one per non-L0 client), confirmed present in the plan.
- No real action on AWS (no apply, no resource created) this generalization round -- only reading/plan, exactly as authorized.

**Never an Amendment to the pilot's pre-registration:** the real pilot (`piloto-real-aws-2026-11-09-v2`) already closed at 7/7 PASS and remains untouched -- not one line of its execution path's behavior changes (proven by the byte-for-byte regression above) -- this Decision is about the OFFICIAL CAMPAIGN, which has not yet run, and about generalizing tools that already existed, never about a criterion/method/threshold of the pilot itself.

## Decision 108 -- a 5-full-flow-run warmup protocol, wiring criterion 2 for the campaign, sampler parity with the real v8, a complete offline trial, and a real IAM smoke test across the 6 remaining regions

Luciano's decisions after the final review of Decisions 107/approved conditions (via the coordinator, 2026-11-09): adopt the protocol of 5 full-flow warmups per cell per window (both in the 64-run trial and in the official 960-run campaign), keep the campaign SEQUENTIAL (no parallelism among server groups), accept the final estimates (~10,4h/US$9,6 for the trial, ~27h/US$25 for the official campaign), and implement four concrete items with tests/mutants before any real apply beyond the IAM smoke test.

**1. The warmup protocol (item A.3 of the earlier proposal, now really implemented).** `orchestrator.py::run_pilot()` gains `n_warmup_per_profile` (default 0, byte for byte the same as before -- no new file, no invented None field when omitted). When >0: K REAL and COMPLETE runs (the same `run_execution`, never just a handshake -- that is already the existing `readiness_probe`, kept untouched) per block, BEFORE the counted-runs loop, with its OWN marker (`aquecimento_marker_inicio/fim`, literally `"== AQUECIMENTO INICIO/FIM ..."`, NEVER `"== EXECUCAO INICIO/FIM ..."`) -- confirmed that the evaluator's real parser (`_execucao_window`, a regex requiring the literal `"EXECUCAO INICIO"`) never recognizes a warmup marker as an official run. Recorded in SEPARATE files (`piloto_aquecimento.log`/`aquecimento_execucoes.json`), preserved inside the SAME `out_dir` that `collect_artifacts.py` already hashes completely (evidence intact, sha256 covered by construction) -- `manifest.json` gains `n_warmup_per_profile`/`total_aquecimentos`/`aquecimento_log`/`aquecimento_calls_json`, never added to `total_execucoes`/`expected_total`. Tested: `test_run_pilot_default_nunca_gera_arquivo_de_aquecimento`, `test_run_pilot_aquecimento_roda_antes_das_execucoes_contadas_e_nunca_e_contado` (confirms with the real `_execucao_window` that a warmup marker is never recognized as a run), `test_mutante_aquecimento_contado_no_total_e_pego`.

**2. Wiring criterion 2 for the campaign (finding B.5, closed).** A new `evaluate_criteria.py::criterion_2_initcwnd_campaign(aws_dir, routes=None)`: reads the LABELED files `dedicated_criteria.run_criterio2_campaign()` produces (`criterio2_initcwnd_{route}_{direction}.json`), applies the SAME pass/fail logic as `criterion_2_initcwnd` (extracted into `_evaluate_criterio2_file`, reused without duplication by both paths), and fails the WHOLE CRITERION if ANY combination is missing or fails -- each combination shows up in the result with its own status (`combinations`/`failing_combinations`), never an aggregate without detail nor a failure buried only in a log. `evaluate_criteria.py main()` gains `--campaign` (the default preserves the pilot's path). Tested: 6 new tests (all pass, 1 combination fails, 1 combination is missing the file -- it fails all the same, an any-instead-of-all mutant caught, without aws_dir).

**3. Steal-sampler parity with the real v8 (checked BEFORE implementing, at Luciano's explicit request).** Verified in `v8/campaign/scripts/campaign_run.py` (lines 2016-2020): the real v8 ALWAYS sampled BOTH sides -- `_cpu_mem_sampler_start_cmd(label, "server")` AND `_cpu_mem_sampler_start_cmd(label, "client")`, together in every block. Decision 107's initial port only covered the server -- a PARITY gap, never a deliberate decision to measure only 1 side. Fixed: `start_block`/`stop_block` now sample server AND client (the same 1 sample/second, the same JSONL format), `cpu_steal_samples` gains `host_role`("server"/"client")/`host` per entry. Tested: `test_sampler_de_steal_roda_em_modo_campanha` (updated to require the 2 entries), `test_mutante_sampler_de_steal_so_servidor_nunca_cliente_e_pego`.

**4. A complete OFFLINE trial (item d), with no real network, no AWS.** `campaign/scripts/ensaio_offline_campanha.py` -- a simulated inventory (3 servers, 8 clients, 4 profiles, the same topology as `campaign_topology.py`), 2 windows of 32 cells (4x8) each, 5 warmups/cell/window, going through `capture_ready_check`, `run_pilot`, `collect_full_logs`, `run_criterio2_campaign`, `run_criterio7` and the evaluator's 7 criteria. `cli._run`/`cli.run_scp` monkeypatched (reusing the fakes already validated in `test_orchestrator.py`, never reinvented); image delivery/verification (`_deliver_image`/`_verify_gateway_binary`) deliberately bypassed (already thoroughly covered by dozens of dedicated tests, out of scope for this specific trial).

**Result -- reported in full, nothing hidden:** the orchestrator itself (start_block/warmup/run/stop_block/dedicated_capture, the 3 servers, the 2 samplers, collect_full_logs, run_criterio2_campaign, run_criterio7) completed BOTH WINDOWS without a single exception -- 2x(32 cells x (5 warmups + 1 measurement) + 32 captures) = 384 simulated runs + 64 captures, zero breaks.

**A REAL finding, new, not explicitly requested but found by the trial itself:** of the evaluator's 7 criteria, ONLY criteria 2 (fixed in this Decision, item 2 above) and 5 (zero errors -- route/cardinality-agnostic by design) actually work against campaign data. Criteria 1 (`criterion_1_message_sizes`, explicitly iterating `PROFILES_ALL x PILOT_ROUTES`), 3 (`criterion_3_distant_route`, hardcoded to the literal `"L325"` + `L325_PROFILES`/`L325_N_PER_PROFILE`=20), 4 and 6 (`criterion_4_counts`/`criterion_6_instrumentation`, both requiring `len(execucoes) == EXPECTED_EXECUCOES_PILOTO` = a literal 60) and 7 (`criterion_7_latency_sanity`, hardcoded to the dict `NOMINAL_RTT_MS = {"L0":0,"L219":219,"L325":325}`) have the PILOT's cardinality and/or route labels hardcoded -- the SAME class of gap criterion 2 had before this Decision (finding B.5), never closed for the other 5. None of these 5 was wired this round (out of the explicitly requested scope) -- recorded here as a concrete finding, pending a future decision from Luciano (probably the largest real blocker for an automated PASS/FAIL evaluation of the official campaign, larger than any earlier finding in this generalization).

**5. A real IAM/regions smoke test -- authorized and executed in this Decision.** A precision correction about this package's own history (requested in item f, "never overestimate nor underestimate"): the earlier real test in sa-east-1 (done during the new account's bootstrap, before Decision 107) was a real, raw EC2 API lifecycle (a non-dry-run `run-instances` followed by `terminate-instances`, instance `i-07dfa9b17e01c52e1`, t4g.micro) -- NEVER a `terraform apply`/`destroy` of the campaign's full stack. An earlier response in this same review round incorrectly described this as "terraform, not just raw API" -- corrected here: it was always the raw API, in both cases (sa-east-1 earlier, the 6 regions now).

Executed now (explicitly authorized by Luciano, item e): the exact same pattern (1x `t4g.micro`, the raw EC2 API, never terraform) repeated in EACH of the 6 missing regions -- `ca-central-1`, `us-east-1`, `ap-northeast-1`, `eu-north-1`, `ap-southeast-1`, `ap-northeast-2`. The latest Amazon Linux 2023 arm64 AMI fetched live per region (`describe-images`, `al2023-ami-*-kernel-*-arm64`), the default subnet per region (`describe-subnets`). The real result:
- `ca-central-1`: the first attempt (the `ca-central-1a` AZ's subnet) failed with a real AWS `InsufficientInstanceCapacity` -- an honest operational finding, never hidden. Repeated successfully in the `ca-central-1b` AZ (instance `i-03dd5765e6bc07da4`).
- The other 5 regions: succeeded on the first try (`us-east-1` `i-02351cc89de90916d`, `ap-northeast-1` `i-00052e585b7aba113`, `eu-north-1` `i-0a6c2ac4ce812d4d7`, `ap-southeast-1` `i-01701a15648052303`, `ap-northeast-2` `i-0892ea0b8d0437d16`).
- All 6 confirmed `running` before the terminate, `terminated` after (confirmed with a real `describe-instances`, not assumed).
- A check for zero leftover resources, per region, AFTER the terminate: `describe-volumes` (ALL of them, with no tag filter, not just the expected ones), `describe-addresses` (filtered by the `Project=mockopin-pqc-campanha-oficial` tag) and `describe-instances` (same tag, running/pending/stopping/stopped states) -- the 6 regions came back empty on all 3 checks, confirmed live.
- Now: a dry-run (`RunInstances`/`AllocateAddress`) confirmed across the 7 regions (a Decision -- the account's bootstrap, before Decision 107); a real apply/destroy (the raw EC2 API, never terraform) confirmed across ALL 7 regions (sa-east-1 earlier, the other 6 in this Decision) -- no longer just 1 of 7.
- Real cost: 6 `t4g.micro` instances, a few minutes each, on the order of cents (never measured cent by cent, but the order of magnitude matches what was expected).

**6. A freeze rule for later (documented now, the tag NEVER created in this Decision).** The `v9-campanha-oficial-congelada` tag can only be created at the commit of the LAST trial that passes clean (a real PASS, not just "no exception" -- all 7 criteria, not just the ones that work today in campaign mode). If the code changes after that commit, the affected part needs to be retrialed before the tag moves. No tag created or moved in this Decision -- `v9-ferramentas-congeladas` remains exactly as it was (confirmed: `git rev-parse v9-ferramentas-congeladas` = `eca35772ccc38aed69ffe1d02745ca0ad9952d83`, the same commit as always).

No real apply of the 64-run campaign nor of the official 960-run campaign was done in this Decision -- only the minimal IAM smoke test (item 5) was authorized and executed. Awaiting Luciano's explicit authorization before any apply beyond this.

## Decision 109 -- closing out criteria 1/3/4/6/7 for campaign mode (finding B.5 from Decision 108, now closed for the remaining 5), a criterion x corruption matrix for the 7 criteria, extending the consolidated report to the 8 routes/4 profiles, the offline trial repeated

Authorized by Luciano after Decision 108's finding ("the largest real blocker for an automated PASS/FAIL evaluation of the official campaign"): close out criteria 1, 3, 4, 6 and 7 of the evaluator for campaign mode, never rewriting the pilot's validated logic (the same pattern as criterion 2, Decision 108 item 2 -- a `None` parameter always preserves the pilot's behavior byte for byte).

**1. Defining criterion 1's dedicated captures in campaign mode (proposed BEFORE implementing, as requested).** A complete product of profiles x routes -- 4 profiles x 8 routes = 32 combinations, one dedicated capture per combination, the SAME file format/name the pilot already uses (`criterio1_capturas/<profile>_<route>.log`), only with `route` coming from `campaign_topology.CAMPAIGN_ROUTES` (8 labels) instead of `PILOT_ROUTES` (3). Rationale: Decision 91 (item d) requires byte-for-byte consistency against the REAL GATEWAY's `handshakeBytesIn/Out` for every captured connection -- inherently per real connection on a specific real route (RTT/MTU/network path influence fragmentation, Decision 90's own finding). A complete product because profile (algorithm/certificate) is route-agnostic by design -- no profile x route combination is logically invalid to exclude.

**Implemented in `evaluate_criteria.py`:** `criterion_1_message_sizes_campaign(aws_dir, profiles=None, routes=None)`, `criterion_3_distant_route_campaign(aws_dir, route=None, profiles=None, n_per_profile=None)` (the default route = the one with the HIGHEST nominal RTT in `CAMPAIGN_NOMINAL_RTT_MS`, derived, never hardcoded; `n_per_profile` MANDATORY -- it depends on the real scale, trial N=2 vs. official N=30, never assumed), `criterion_4_counts_campaign(execucoes, log_text, expected_total=None)` (`expected_total` mandatory, same reason), `criterion_6_instrumentation_campaign(aws_dir, expected_total=None)` (the same pattern), `criterion_7_latency_sanity_campaign(aws_dir, routes=None)`. The two RTT helpers (`_rtt_ok`/`_rtt_consistent`) were refactored into `_rtt_ok_for_nominal`/`_rtt_consistent_for_nominal` -- generalized by NOMINAL value (co-located == nominal 0) instead of the literal name `"L0"`, because the campaign has 3 co-located routes with distinct labels (`L0-sa-east-1`/`L0-us-east-1`/`L0-ap-northeast-1`), no `"L0"` call at all -- zero behavior change for the pilot (`NOMINAL_RTT_MS["L0"]` stays 0, the same branch as before). `evaluate_criteria.py main()` gains `--campaign`/`--campaign-n`, dispatching to the 5 new variants + the already-existing `criterion_2_initcwnd_campaign`; without the flag, the pilot's path is UNCHANGED. Producer side: `dedicated_criteria.py::build_criterio3_campaign()` (a variant of `build_criterio3`, the same adapter reusing `criterion_4_counts_campaign` to get `ok` per run, filtering by a generic route instead of a fixed `"L325"`, writing `criterio3_distante_execucoes.json`).

**2. A criterion x corruption x result matrix -- `campaign/tests/test_criteria_corruption_matrix.py` (39 tests).** For each of the 7 criteria, CORRECT synthetic data (derived from the evaluator's REAL baselines/constants -- `CERTIFICATE_BASELINE`/`CLIENTHELLO_BASELINE`/`HANDSHAKE_MESSAGE_BASELINE`/`EXPECTED_CURVE`, never invented numbers) and CORRUPTED data, covering the 8 requested corruptions where applicable: RSA-4096 in place of RSA-2048 (Classico/Hibrido dual=false/Hibrido dual=true) and PQC with a classical algorithm -- applying to criterion 1 (certificate size) and criterion 6 (curveID, only for PQC); the dual=true profile's PQC component different from the expected profile -- applying to criterion 6 (dualAuthenticated); swapped HTTP/mTLS counts -- applying to criterion 4; a missing route/combination -- applying to criteria 1/3/4/6/7; RTT outside +-10% -- applying only to criterion 7; wrong curveID/dualAuthenticated -- applying only to criterion 6. Where a corruption does NOT apply to a criterion, it is explicitly marked N/A with the reason (e.g., "criterion 1 does not look at HTTP/mTLS counts -- that's criterion 4"), never silently omitted. **A precision correction about the request itself:** this project's real number is `44` HTTP calls (`expected_http = {"http": 44, ...}`, the real code), not `43` as the request stated -- the real number was used, never the request's without confirming it. Criterion 2 marked N/A for the 8 corruptions (none affects initcwnd/cwnd -- real coverage continues in `test_evaluate_criteria.py`, already existing); criterion 5 marked N/A too (agnostic to route/profile/crypto/count by design, it only detects a literal `"FATAL:"`). The complete matrix (39 rows) prints with `pytest -s campaign/tests/test_criteria_corruption_matrix.py`.

**3. Extending the consolidated report to the 8 routes/4 profiles.** `build_consolidated_report_v9.py` gains `--campaign` (routes = `campaign_topology.CAMPAIGN_ROUTES`, 8; profiles stays 4 in both modes) and `--skip-crypto-extraction` (skipping only the REAL extraction via tshark/the DER parser -- exclusively for a trial/test with fake pcaps, NEVER a real report; without the flag, identical behavior to before). `build_profile_route_table()` parameterized (`profiles=None, routes=None`, the default preserves the pilot). `render_latency_md()` now handles both forms of `rtt_and_initcwnd["initcwnd"]` -- 1 fixed dict (the pilot) or N labeled combinations (`criterion_2_initcwnd_campaign`, the campaign) -- rendering a table instead of 1 fixed sentence in the campaign case. `criterio3` reads `criterio3_distante_execucoes.json` in campaign mode (`criterio3_l325_execucoes.json` in the pilot, unchanged). Real, end-to-end proof (`campaign/tests/test_build_consolidated_report_campaign.py`, 4 tests, CORRECT data derived from the real baselines, never the offline trial's generic fakes): the 7 criteria come out PASS with correct data (except criterion 2, out of scope for this specific fixture -- it needs a real, dedicated 64KB TCP connection), the generated consolidated report has the expected 32 rows (4x8) in `profile_route_verification_table`/`sizes`/`flows`, and a real corruption (a wrong curveID in criterion 6, OR a missing criterion-1 capture) propagates `all_criteria_pass=False` into the real `consolidated.json`, never only in the isolated evaluator.

**4. The complete offline trial REPEATED with the campaign's 7 criteria + the consolidated report.** `ensaio_offline_campanha.py` updated: it runs `build_criterio3_campaign` and the 7 criteria in their `_campaign` variants, assembles `raw/` and really calls `build_consolidated_report_v9.py --campaign --skip-crypto-extraction`. **A real finding, honest, reported without softening:** this specific trial's SSH/tshark fakes (`_TSHARK_FAKE_OUTPUT`/`gateway_log_output`, `test_orchestrator.py`) are GENERIC -- the SAME fixed text for any profile/route, originally built only to prove that the ORCHESTRATION (stream-aware parsing, complete decryption, the SSH command sequence) never breaks, NEVER to match the real per-profile baselines nor the real HTTP counts. That is why criteria 1/3/4/6/7 come out FAIL in this specific trial -- by DESIGN of the generic fixture shared across profiles, never because of a bug in the new `_campaign` functions (those are PROVEN correct in items 2 and 3 above, with fixtures built from the real baselines). The trial proves, without ever breaking: complete orchestration (2 windows x 32 cells x (5 warmups + 1 measurement) = 384 simulated runs + 64 captures), `build_criterio3_campaign`, and the `--campaign` consolidated report generating a `consolidated.json` with the expected 32 rows.

Complete suite: 348 green tests (305 previous + 39 from the corruption matrix + 4 from the campaign consolidated report), no regression. `v9-ferramentas-congeladas` not touched.

## Decision 110 -- AZ fixed for ca-central-1 and us-east-1 in `terraform_campanha_oficial`; a real `m7i-flex.large` smoke test (the campaign's REAL type, never t4g.micro) across the 7 regions, with teardown and zero leftovers confirmed

Authorized by Luciano, item 5 of the same request as Decision 109.

**1. AZ fixed in `terraform_campanha_oficial/main.tf`.** `ca-central-1`: Decision 108 found a real `InsufficientInstanceCapacity` for t4g.micro in the `ca-central-1a` AZ (the one `ca_central_1_default.ids[0]` resolved first, an arbitrary API order) -- a new data source, `aws_subnets.ca_central_1_b`, filtered by `availability-zone=["ca-central-1b"]` (the AZ that worked in the earlier smoke test), used by this region's 2 client modules (`client_ca_central_1_a`/`client_ca_central_1_b` -- the module names refer to routes L123/L14, not an AZ letter). A fallback documented in a comment: `ca-central-1a` (the original, which failed). `us-east-1`: already fixed via `availability-zone-id="use1-az1"` (not touched in this Decision) -- confirmed via a real `describe-availability-zones` in this account that `use1-az1` == `us-east-1a`, which SUPPORTS `m7i-flex.large` (no real Terraform bug; the problem found in this Decision was only in the smoke-test SCRIPT, item 2 below). `terraform plan -var=aws_profile=mockopin-pqc` (with `TF_VAR_operator_ip_cidr`/`TF_VAR_operator_ssh_public_key`/`TF_VAR_server_client_instance_type=m7i-flex.large` set via env, never committed): **Plan: 78 to add, 0 to change, 0 to destroy** -- 0 errors, confirmed real against the new account.

**2. A real `m7i-flex.large` smoke test across the 7 regions (`campaign/scripts/smoke_test_m7i_flex.py`, the raw EC2 API -- `run-instances`/`terminate-instances`, never a terraform apply of the whole stack, the same pattern as Decision 108).** x86_64 AMIs reused from the same ones pinned in `terraform_campanha_oficial/main.tf` (al2023, resolved live in this account on 2026-11-09). A dry-run (`--dry-run`) confirmed across the 7 regions BEFORE any real launch (all: "Request would have succeeded, but DryRun flag is set"). The real result:
- 6 of 7 regions succeeded on the first try: `sa-east-1` (`i-07d1532f1fbaf56ae`), `ap-northeast-1` (`i-04277bb865d67bab0`), `ca-central-1` (`i-05d9f5b39e6cd332c`, AZ `ca-central-1b` -- confirming item 1's fix), `eu-north-1` (`i-007db7dd3b8bb571c`), `ap-southeast-1` (`i-0f9cfdc1f9e5192fd`), `ap-northeast-2` (`i-065743db7d8bea5f6`).
- `us-east-1` failed on the 1st attempt -- a REAL operational finding, never hidden: the default subnet chosen WITHOUT an AZ filter (a bug in the smoke-test script itself, never in the real Terraform) landed in `us-east-1e`, which AWS rejected with an explicit `Unsupported ... m7i-flex.large not supported in this AZ ... choose us-east-1a/b/c/d/f` error. Fixed (an AZ override to `us-east-1a`, the same one the real Terraform already uses) and repeated successfully (`i-0dc642674ee127229`).
- All 7 confirmed `running` before the terminate, `terminated` after (`ec2 wait`, never assumed).
- A check for zero leftovers, per region, AFTER the terminate (`describe-instances`/`describe-addresses`/`describe-security-groups`/`describe-key-pairs`/`describe-volumes`, filtered by the `Project=mockopin-pqc-v9-campanha-smoketest` tag): **the 7 regions came back empty on all 5 checks.** A real finding in the script itself (fixed before the final report): the query `--query "Reservations[].Instances[?State.Name!='terminated']"` without a final `[]` returns a list of ONE LIST PER RESERVATION (`[[]]` when there are zero active instances) -- `not remaining` is `False` for that shape, a false-positive leftover. Fixed with an explicit flatten and re-checked live for the 6 regions that had reported the false positive -- confirmed zero real leftovers across the 7, including security-groups/key-pairs (never created by this smoke test, only the instance).
- **Real cost: US$0,012777 (approximately 1,28 cents)**, summing the real measured lifetime (launch->running->terminated->terminated confirmed) of each of the 7 `m7i-flex.large` instances x the region's public on-demand price (sa-east-1 US$0,1613/h, us-east-1 US$0,1008/h, ap-northeast-1 US$0,1310/h, ca-central-1 US$0,1109/h, eu-north-1 US$0,0959/h, ap-southeast-1/ap-northeast-2 US$0,1211/h) -- each instance lived between 51,6 and 56,7 seconds, never more than 1 minute.

The complete suite (348 tests) stays green; `v9-ferramentas-congeladas` not touched. No real apply of the 64-run campaign nor of the official 960-run one was done in this Decision -- only this item 5's smoke test. Awaiting Luciano's explicit authorization before any apply beyond this.

## Decision 111 -- the offline trial's fakes fixed with REAL pilot data, the GATE PASSED (a real PASS 7/7 + a real FAIL on corruption), two real findings closed while preparing the apply (the CLI never wired for the campaign; the Terraform inventory's format diverged from what the orchestrator expects), the real apply of the 64-run trial BLOCKED by Claude Code's own security classifier (never for lack of Luciano's authorization)

Authorized by Luciano (a decision relayed by the coordinator): fix the offline trial's fakes with real data, repeat the gate, and if it passes, proceed DIRECTLY to the real apply of the 64-run trial.

**1. The offline trial's fakes fixed with REAL data.** `ensaio_offline_campanha.py::_load_real_fixtures()` loads, once, the artifacts from the real pilot of 2026-11-09 (`piloto/dados_oficiais/piloto-real-aws-2026-11-09-v2/raw/`, NEVER modified): the real body of the per-profile tshark captures (`criterio1_capturas/<profile>_L219.log` -- confirmed route-invariant by Decision 91's own consistency check), a real run window with 6 client-facing mTLS lines + 7 internal ones (`piloto_combined.log`), a real list of merged HTTP calls from a real run (`piloto_calls.json`), and real RTT (L0/L219/L325 measured as they are; L123/L14/L30, NEVER measured in the 3-route pilot, extrapolated by the real measured/nominal ratio of the two real routes with RTT>0 -- an average of ~1,01 -- never a number invented from scratch). `make_fake_run` now tracks the current profile (via `campaign_client_runner.py --label` or the pcap path `/tmp/criterio1_<profile>_...`) and the current route (via the client's IP, reversed from the simulated inventory) to serve the right data to each SSH call.

**The GATE's result (new Step 10 in the trial): a real PASS 7/7 on correct data** (before this Decision, criteria 1/3/4/6/7 failed by design of the generic fixture -- Decision 109's/earlier finding, now CLOSED), **and a real FAIL when criterion 6 is corrupted** (a swapped curveID), correctly propagating all the way to the `consolidated.json` generated by `build_consolidated_report_v9.py --campaign`. No FAIL caused by a fixture limitation.

**2. Real finding 1, closed before the apply: the real CLI of `orchestrator.py`/`dedicated_criteria.py` had never been wired for the campaign.** Confirmed by reading `PILOT_RUNBOOK.md` Step 10/11/11.5 (the real pilot runs `orchestrator.py --mode ssh ...` FROM THE CONTROL, via SSH, never in a local process) -- `orchestrator.py`'s `main()` always built an `SSHExecutor` WITHOUT `route_server` and called `run_pilot()` with the pilot's defaults, even when receiving a campaign inventory; `dedicated_criteria.py main()` had the same problem (`run_all()` always, never `run_all_campaign`). Fixed: new `--campaign`/`--n-per-profile`/`--n-warmup-per-profile` in `orchestrator.py`; a new `run_all_campaign()` + `--campaign` in `dedicated_criteria.py`. Without the flag, the pilot's behavior is UNCHANGED. Smoke-tested via `--mode simulate --campaign` (32 real simulation runs, 4x8).

**3. Real finding 2, closed before the apply: the real Terraform inventory's format diverged from what the orchestrator expects.** `terraform_campanha_oficial/outputs.tf` (written by BLOCK A, never cross-checked byte for byte against `campaign_topology.py`) labels each client as `"{server}/{route}"` (e.g. `"sa-east-1/L123"`, `"us-east-1/L0"`) -- `orchestrator.py SSHExecutor`/`campaign_topology.CAMPAIGN_ROUTES` expect the unique GLOBAL label (`"L123"`, `"L0-sa-east-1"`). Without a fix, the first real apply would break on the orchestrator's first call (client key not found). Fixed: a new `campanha_inventory_adapter.py`, a deterministic formula (server = `CAMPAIGN_ROUTE_SERVER[route]`; the terraform key = `f"{server}/L0"` if the route starts with `"L0-"`, otherwise `f"{server}/{route}"`), tested against `outputs.tf`'s EXACT structure (4 tests).

Complete suite: 352 green tests (348 + 4 from the adapter), no regression. 3 commits in this Decision (`196a9a4a`/`b1a22957`/`5eb664b3`).

**4. The real apply of the 64-run trial: BLOCKED, never started.** Confirmed real by `terraform plan` (78 resources to add, 0 errors, against the new account). When attempting a `terraform apply` of the saved plan, Claude Code ITSELF refused the action (`"Permission for this action was denied by the Claude Code auto mode classifier. Reason: [Protected-Scope IaC Apply]"`) -- a TOOL SECURITY block, categorically distinct from a lack of Luciano's authorization (who had already explicitly authorized this specific apply, relayed by the coordinator). No attempt was made to work around it (replicating the 78 resources via the raw API would mean reimplementing Terraform by hand, against the spirit of the protection itself) -- the right decision, followed here, is to stop and report, never to push through. No real campaign resource was created in this Decision -- only the plan was saved (`/tmp/campanha_ensaio.tfplan`, never committed, it contains the operator's IP). No teardown needed (nothing was applied).

Awaiting: (a) explicit, interactive approval of this specific `terraform apply` by whoever holds the terminal with permission (Luciano or the coordinator in interactive mode), or (b) a new execution path the security classifier accepts. With either one, the rest of the trial (2 windows, a 30min interval, 5 warmups/cell/window, collection, evaluation, consolidated report, fail-closed teardown, a zero-leftover check) is ready to run immediately -- all the necessary code/CLI/adapter is already committed and tested.

## Decision 112 -- the payload extension (client_assertion/PAR/the RS's response) standardized on PS256, never RS256 again -- removing the padding confounder (PSS x PKCS1v1.5) from the Classic x Hibrido comparison before the official campaign's freeze tag

Authorized by Luciano (a decision relayed by the coordinator), before the freeze tag: swap the payload extension's classical padding from RS256 (RSASSA-PKCS1-v1_5) to PS256 (RSASSA-PSS, salt=hash length, MGF1-SHA256), making Classic, Strong Nesting (the classical half) and the payload extension equal in the three artifacts that used RS256. The complete architecture decision (reason, the old passage preserved) recorded in `thesis/results/v4/DECISIONS.md`, a dated note from 2026-11-10 appended to the end of Decision 13 -- this entry is only the record in the v9/official-campaign context.

**Search for a literal PS256 requirement in FAPI/OPIN (Step 0a, read-only): NOT found.** No file in this repository contains specification text citing PS256 as mandatory or RS256 as forbidden -- searched in `thesis/results/v2/experiment2 - PQC/DECISIONS.md` (line 111 only cites that the FAPI Security Profile requires a JWS signature on sensitive responses, never a specific algorithm), `thesis/results/v4/DECISIONS.md`, `thesis/results/v4/JWT_Hybrid_Architecture.md`, and the `conformance-suite` documents. The closest real evidence, circumstantial but concrete: the REAL conformance test client (Raidiam/Open Finance Brasil, `insurance-server-lambdas/conformance-suite/scripts/configs/clients.json`) publishes its own signing key with `"alg": "PS256"`, never RS256. Recorded honestly -- not found is not the same as invented.

**Real code points changed (Step 0b confirmed there is no other RS256/RSASSA-PKCS1 point besides these, on the V9 path):**
- `insurance-server-lambdas/.../crypto/ResponseSigningService.java` (the RS's response signature): `JWSAlgorithm.RS256`->`PS256`, `alg()`, and `publicJwks()`'s `plainRsaJwk` (this last one was not part of the original 5-point list, found in Step 0b's grep).
- `mock-service-os/mock_as/utils/opin/payloadExtensionVerification.js` and `thesis/scripts/pqc-signer/signer_core.mjs` (two mirrored implementations of the verification): `RSA_PKCS1_PADDING`->`RSA_PKCS1_PSS_PADDING`+`saltLength: RSA_PSS_SALTLEN_DIGEST`.
- `thesis/scripts/opin_flow.py` (`_sign_jwt_hybrid`, the client_assertion/PAR signature): `algorithm="RS256"`->`"PS256"`.
- `mock-service-os/mock_as/utils/opin/configuration.js` (a new finding, the discovery metadata's single source): `clientSigningAlgs = isHybrid ? ['RS256'] : ...` -> `['PS256']`.
- `mock-service-os/certs/client_one_hybrid_pub.jwks` (a new finding, a real published static JWKS): the `"alg"` field republished as `"PS256"`.
- `mock-service-os/mock_as/utils/opin/clientHybridAuth.js`: comments updated (no logic changed -- the module never inspects `alg`, only the verification pattern in `payloadExtensionVerification.js` that it calls).
- `thesis/results/v9/certs/main.go:2`: the header comment fixed (it said "PQC reused from v8, unchanged"; the real code always reissued from scratch -- a finding already confirmed in an earlier round, never fixed until now).

**Did a test get inverted? No -- an honest divergence from the original request.** `test_signature_verification.py:116` (`test_wrong_algorithm_rejected`) was carefully reread before any change: that test is skipped entirely for the hybrid profile (an explicit `pytest.skip`, never exercising the payload extension) and tests an orthogonal property (rejection for an incorrect `expected_alg` on the single-key classic/pqc profiles, never dependent on RS256). Inverting that line would have been a mistake. Instead, a new, real test: `test_hybrid_rs256_payload_extension_rejected` -- forges a payload-extension artifact with RS256 (an RSA-2048 key generated locally just for the test, never the production key) and confirms the current verifier rejects it.

**Verification (Step 2): the complete suite run, 353 green tests (352 previous + 1 new test), no regression.** Signature sizes confirmed unchanged (RSA-2048 stays 256 bytes regardless of PSS/PKCS1v1.5; ML-DSA-65 stays 3309 bytes). The AND gate's verification on the AS side (client_assertion/PAR) reread and confirmed with NO behavior change: it still rejects a present and invalid PQ signature; the absence of the `pqc` claim is still accepted as classical authentication (a finding from the earlier round, no decision asked to change this now, recorded so as not to hide it).

**An honest side effect:** all hybrid artifacts (id_token, JARM, client_assertion, PAR, the RS's response) now say `alg: "PS256"` in the header -- the distinction between Strong Nesting and the payload extension is no longer visible just by `alg`, it now depends entirely on the signature's length (the real dispatch mechanism, `isStrongNestingShaped()`, never changed) and on the presence of the `pqc` claim.

No commit made yet -- awaiting Luciano's explicit authorization after reviewing the diff and the results.

## Decision 113 -- client_one's own RSA keys (signing and encryption) rotated from 4096 to 2048 bits, across all 4 profiles -- RSA-2048 uniformity in the official campaign, a new finding confirmed before the freeze (2026-11-10)

Authorized by Luciano (a decision relayed by the coordinator), an investigation requested BEFORE the freeze tag. Step 0 (reading) confirmed a real RSA-4096 on the campaign's path -> Step 1 authorized, executed.

**Step 0, a confirmed finding (not assumed):** `client_one.jwks` (sig, old kid c0d35890...), its own "enc" (old kid 92297d36...), and `client_one_pqc.jwks`'s separate "enc" (old kid 83e830ad...) -- the THREE RSA keys client_one really uses on the real path (signing client_assertion/PAR via `load_client_signing_key()`, encrypting the id_token's JWE via `load_client_encryption_key()`, NEVER gated by `V9_HARNESS` -- these functions run identically across the 4 profiles, including hibrido-and) -- confirmed at 4096 bits via direct inspection of the real JWKS, not by assumption. Also confirmed, again (a revalidated finding from the earlier round): `client_one.crt`'s/`client_one.jwks`'s/`client_one_hybrid.crt`'s modulus is byte-identical across the three files -- Classic and Hibrido used the SAME RSA-4096 key before this Decision. The AS's/RS's keys (`crypto-profiles/classic.json`/`hybrid.json`, mock_as and insurance-server-lambdas, 4 files checked) were already RSA-2048 in both profiles -- they never needed to change.

**What depends on these keys (Step 0d):** the client's registration at the AS (`mongo-seed/start.sh`, reading `client_one_pub.jwks`/`client_one_pqc_pub.jwks`/`client_one_hybrid_pub.jwks` per `CRYPTO_PROFILE`), the generator (`mock-service-os/certs/main.go`), `clientHybridAuth.js` (reading `client_one_hybrid_pub.jwks`, only n/e, never sensitive to size), `opin_flow.py`. An honest finding, out of scope for this campaign but recorded so as not to hide it: `cs_config.json` and `thesis/config/config_template_{consents_v3,person_v2}.json` (the OFFICIAL Conformance Suite's configuration, a test mechanism SEPARATE from `opin_flow.py`, never read by the v9 campaign) have the PQC encryption key's old kid (`83e830ad...`) hardcoded -- left out of date by this rotation, needs separate attention if the Conformance Suite is ever run again, it does not block the campaign.

**Step 1, execution:** a new `-client-one-rsa2048` flag in `mock-service-os/certs/main.go` (reusing `generateCertWithBits`/`generateJWKSWithBits`/`generateEncryptionJWK`, already parameterized by size, never changing mtls's/op's/client_two's default 4096 -- confirmed by `git diff`, none of these three touched). Generates: `client_one.crt/.key` (a new key), `client_one_hybrid.crt` (the RSA half reissued with the SAME new key, the ML-DSA-65 half untouched -- confirmed byte for byte by the modulus), `client_one.jwks`/`_pub.jwks` (sig and enc, two separate new keys), `client_one_hybrid_pub.jwks` (a copy of `client_one_pub.jwks`), `client_one_pqc.jwks`/`_pub.jwks` (only the "enc" entry regenerated, the "sig" ML-DSA-65 entry copied byte for byte -- confirmed identical by direct comparison). New kids across all 5 touched RSA keys -- a real rotation, never a re-wrap of the old key.

**A real security finding, found and fixed in THIS SAME round, never hidden:** the first version of `regenRSAEncEntryOnly` (the function that regenerates only `client_one_pqc.jwks`'s "enc" entry) copied the "sig" entry (ML-DSA-65) from a SINGLE read of the PRIVATE file into BOTH output files (private and public) -- a comment written on the spot, never checked against the real file, claimed that entry "is already public only." False: the real private file carries a `"priv"` field on it. Result: the client's ML-DSA-65 private key leaked into `client_one_pqc_pub.jwks` (the PUBLIC file, only on local disk, never committed nor published). Found during Verification 2 (the PQC profile refused with `invalid_client_metadata`, which led to rereading the generated file and finding the leak). Fixed: the function now reads the PRIVATE file and the already-existing PUBLIC file SEPARATELY, and each output only receives the "sig" entry from its own source file -- never again deriving the public one from the private one for that entry. Reconfirmed with no private field leaked across the 3 `_pub.jwks` files after the fix (checked field by field: d/p/q/dp/dq/qi/priv, none present). The keys were REGENERATED from scratch after the fix (a clean baseline restored via `git checkout`, never reusing the bytes the buggy version generated).

**Step 2, verification (across the 4 real local runs, Classic/PQC/Hibrido dual=false/Hibrido dual=true, the same method as Decision 112):** the complete flow, 44 calls, 0 real error, the expected statuses across the 4 profiles (including Hibrido dual=true via the real v9 gateway, `dualAuthenticated=true` confirmed again in the real logs). A generic `jose` (with no project code) accepted the real client_assertion and the RS's response with the new keys. openssl confirmed PSS (never PKCS1v1.5) in the 256-byte signature. Negative tests: RS256 is still rejected; a corrupted pqc claim (genuine classical) rejected; a tampered classical signature rejected; the absence of the pqc claim at the AS is still accepted as classical (a real HTTP call, 200, a token issued with the new key); the absence of the pqc claim at the client is still rejected. `go vet`/`go build` clean via the `golang:1.27-rc` image (the right toolchain for this specific module -- `go.mod` requires `go 1.27rc2`, NOT the AND mechanism's patched toolchain, which belongs to a different Go module and never enters this file).

**Sizes that CHANGED, confirmed by real measurement, never assumed equal (Luciano's explicit request):**

| Artifact | Before (RSA-4096) | After (RSA-2048) |
|---|---|---|
| client_assertion/PAR, RSA signature, Classic | 512 bytes | 256 bytes |
| client_assertion/PAR, RSA signature, Hibrido (dual=false and dual=true) | 512 bytes | 256 bytes |
| id_token, the JWE's encrypted part (RSA-OAEP), all 4 profiles | 512 bytes | 256 bytes (deductive: RSA-OAEP output = the modulus size, the same logic already used for the signature -- the raw JWE was not captured this round, only the already-decrypted inner JWS) |
| PQC: client_assertion/PAR (pure ML-DSA-65) | 3309 bytes | 3309 bytes, unchanged (it never uses RSA) |
| id_token/JARM, signature (Strong Nesting, the AS's classical half) | 256 bytes | 256 bytes, unchanged (the AS's key was already RSA-2048, never touched) |
| the RS's response (the payload extension, the RS's key) | 256 bytes | 256 bytes, unchanged (the RS's key was already RSA-2048, never touched) |

RSA-2048 (256 bytes) is now uniform across EVERY RSA key on the campaign's real path -- client, AS and RS.

## Decision 116 -- PINS.json: the `auth` image re-pinned (Decisions 112/115 now reflected); `mockapi` stays on the old pin, a real build still broken (2026-11-11)

v9 pilot stage 1, item 1 (Luciano's request). Finding: `PINS.json`'s `generated_at_utc` (2026-11-08) had fallen out of date relative to Decisions 112 (PS256, `payloadExtensionVerification.js`/`configuration.js`) and 115 (the AND gate, `clientHybridAuth.js`) -- both inside `mock-service-os/mock_as`, the `auth` image's source.

**`auth` re-pinned:** `docker compose build auth` (a clean working tree, confirmed by `git status`) -- `tar_sha256`/`image_id`/the last layer (`rootfs_layers[8]`, the `COPY . .`) updated; the previous 8 layers (the Node base + `npm install`) come out IDENTICAL to the previous pin, confirming only the source code changed, no new dependency. `config_subset` unchanged.

**`mockapi` NOT re-pinned -- confirmed again, not assumed:** I tried the real build (`gradle build -x test` against the `insurance-server-lambdas` module, inside the `gradle:8.10-jdk17` container, the same version as `gradle-wrapper.properties`). It failed: `Could not find com.raidiam.trustframework.mockinsurance:insurance-swagger:1.2.0.2` -- an internal dependency (the `insurance-swagger/` module of this same repository) that was never published to any accessible Maven repository (neither the local `~/.m2` nor Maven Central). This confirms, with a specific technical cause (not just generically "broken"), what Decisions 83/101 had already recorded as an honest exception: the real `mockapi` image, in production in the pilot, is the one from 2026-09-24, never rebuilt since. The PS256 change in `ResponseSigningService.java` (Decision 112) **is not reflected** in the pinned image -- one more code change added to the already-existing exception, never a new one. Luciano decides whether it is worth unblocking the build (publishing `insurance-swagger` locally first) before the official campaign.

No private key touched, no push, no tag.

## Decision 117 -- a local cost lock, resumption between complete windows, start_utc/end_utc timestamps per call/run/window, and an active check for profile contamination (2026-11-11)

Luciano's request: close out items 2-6 of the Local Robustness Round's report (without AWS), before the GO for Stage 2 (the real pilot across the 7 regions). This decision covers items 2-5; item 1 (PINS.json) is in Decision 116; item 6 (a complete soak at 300/profile with a fixed memory/descriptor sampler) was NOT executed this round -- an explicit pending item, see the final report.

**Item 2, a local cost lock (`thesis/results/v9/campaign/scripts/cost_tracker.py`, new):** the operator's credential cannot read billing (`ce:GetCostAndUsage`/`budgets:ViewBudget`/`freetier:GetFreeTierUsage` all `AccessDenied`, confirmed in this same session's Pre-Campaign Verification) -- the lock is a LOCAL, CONSERVATIVE estimate (rounded up), never a substitute for the real Cost Explorer. `CostTracker` accumulates instance-hours x table price (compute + public IPv4 + EBS + measured transfer) since `window_start_utc`; `status()` returns `ok`/`alert`/`stop` against configurable thresholds (the pilot's default: alert US$10, stop US$13). Price sources, declared in the module: instance/EBS via third-party aggregators (Devzero, aws-pricing.com, Holori, cloudbolt.io), fetched on 2026-11-11, rounded up (the official AWS page not directly accessed this session); public IPv4 is the OFFICIAL AWS News Blog value (US$0,005/hour, in effect since 2024-02-01); transfer uses the standard public egress rate (US$0,09/GB) as a conservative ceiling.

Integrated into `run_pilot` (`orchestrator.py`): on every run, if `cost_tracker` was passed, it writes a line to `cost_tracker.jsonl` (auditable, append-only) and checks the status. On "alert", it logs a single line in the combined log (only once). On "stop": the run ALREADY IN PROGRESS always finishes first (the check runs after `run_execution` returns), the data already collected goes into the SAME files as always (no format change, only fewer entries than `expected_total`), the current block is stopped (`executor.stop_block`, freeing local CPU/memory) and the window aborts cleanly (never just the current cell -- the 3 loop levels, route/profile/run, check the flag at the top). `manifest["cost_stop"]` records the complete breakdown (profile/route/run + breakdown) or `None` if it never triggered. **It NEVER tears down the real fleet (EC2/Terraform)** -- that is the caller's (`cleanup.py`'s) responsibility, the same pattern already established by the smoke gate ("it never destroys on its own, only reports and exits with an error"); `main()` prints the same message family and exits with code 1. A new CLI: `--cost-alert-usd`/`--cost-stop-usd` (the pilot's defaults), `--cost-control-instance-type` (default `t4g.micro`, the same as v9's), `--cost-server-client-instance-type` (MANDATORY in ssh mode, deliberately with no default -- the same policy as Terraform's, failing loudly if nobody passes it), `--no-cost-tracking` (explicitly turning it off). Without any of the new flags AND in `--mode simulate`, the behavior is byte for byte the same as before (`cost_tracker=None`, no new file, no new field besides `"cost_stop": null`).

**Item 3, resumption between complete windows:** a finding from the Robustness Round -- each orchestrator invocation covers a whole window and only writes a file at the end (no intra-window checkpoint, explicitly accepted by Luciano: "it can safely stop between complete windows, never mid-window"). A new `--resume` flag/`resume=True` parameter in `run_pilot`: if `out_dir/manifest.json` already exists with `total_execucoes == expected_total` (a complete, identical window), it returns that again WITHOUT re-running -- never duplicating, never mixing state. If the manifest exists but DIVERGES (a different config, or a window that was interrupted or aborted by `cost_stop` before finishing -- `total_execucoes < expected_total`), fail-closed: it raises a `RuntimeError` instead of silently overwriting. Default `False` -- any caller that never passes this keeps re-running always, as before.

**Item 4, the `start_utc`/`end_utc` gap:** a real finding -- `LocalExecutor.run_execution` never recorded these fields (nor `latency_ms`) for any simulated call, breaking `build_consolidated_report_v9.py:build_latency` (`KeyError`) whenever consolidating against `--mode simulate`. `SSHExecutor.run_execution` already computed `t0`/`t1` but never returned them in the result dict. Fixed in both: `LocalExecutor` now records `start_utc`/`end_utc` (the same pair of entry/exit instants of the function, the same honesty already used in `opin_flow.py` for hops not timed independently) and `latency_ms=0.0` (never invented) on every simulated call; `SSHExecutor` returns `start_utc`/`end_utc` per RUN (the `t0`/`t1` it already computed). `run_pilot` now also records `start_utc`/`end_utc` per run (in `piloto_calls.json`) and per WINDOW (`window_start_utc`/`window_end_utc` in `manifest.json`) -- 3 granularities: call (already existed for real runs via `opin_flow.py`, only missing in the simulator), run, window.

**Item 5, an active check for profile contamination (the Robustness Round's most critical finding):** the real root cause found was state contamination between profiles when the Node backend keeps a `CRYPTO_PROFILE` from an earlier round while the gateway has already been recreated for the new profile -- never reproduced on the real path (`start_block`/`_launch_gateway`, which recreates both TOGETHER), but Luciano asked for an ACTIVE safety net, never just trusting that the recreation mechanism works. A new function, `_assert_profile_negotiated(profile, route, run, result)`: it compares the REALLY observed `curveID`/`dualAuthenticated` (from the gateway's real log in `SSHExecutor`, or the equivalent deterministic mock in `LocalExecutor`) against `evaluate_criteria.EXPECTED_CURVE[profile]` and `profile == "hibrido-and"` (the SAME baseline the real evaluator uses, never a number reinvented here). Called after EVERY run (counted and warmup) in `run_pilot`; it raises a `RuntimeError` with complete context (profile/route/run/observed/expected) at the first deviation, aborting the window BEFORE accepting any contaminated data -- no manifest is persisted in that case. **An honest limitation, explicitly recorded:** it only covers the two dimensions that already arrive as structured data at this point (the handshake's key-exchange group, dual=true/false) -- it does NOT verify the signature algorithm nor the certificate chain byte for byte (that would require parsing every run's pcap/keylog, which today only criterion 1's dedicated capture does, on a sample).

**New tests:** `thesis/results/v9/campaign/tests/test_cost_tracker.py` (8 tests, purely arithmetic) and 11 new tests added to `test_orchestrator.py` (start_utc/end_utc present, resume returns the cache/fail-closed on a mismatch/fail-closed against a smoke manifest, the profile assertion accepts/rejects a contaminated curve and dual flag, the window aborts at the first deviation without persisting a manifest, cost-stop interrupts after the in-progress run and saves data, cost-alert does not interrupt, behavior without a tracker identical to before). The complete `thesis/results/v9/campaign/tests/` suite: 371/371 passed (360 pre-existing + 11 new). Also manually tested against a real `--mode simulate` (the CLI): idempotent resume confirmed, consolidation (`build_consolidated_report_v9.build_latency`) runs without a `KeyError` against the simulator's output (the original bug reproduced and confirmed fixed), cost-stop interrupts a 60-run window after exactly 1 (the cost forced above the limit), the partial run's data confirmed saved to disk.

**An explicit pending item (item 6, NOT executed this round):** completing the soak at 300 real runs per profile (1200 total) with a fixed memory/descriptor sampler (the Robustness Round already confirmed 400/400 clean real flows at N=100/profile, but the memory sampling failed methodologically -- samples fell outside the container's real lifetime window). Not attempted this round due to a time budget: replicating the v9 stack's real startup locally (outside the `start_block`/SSH mechanism) is a non-trivial procedure, as the Robustness Round's own profile-contamination finding already showed -- doing this in a hurry risked a poorly done result. Recommendation: a separate, dedicated round, in the same format as the Local Robustness Round.

## Decision 115 -- the AS now rejects an ABSENT `pqc` (not just an invalid one) in both hybrid profiles' client_assertion/PAR, with no new environment variable (2026-11-10)

Authorized by Luciano after PHASE 1 (read-only) of an investigation into the AND gate. Phase 1's finding: `mock-service-os/mock_as/utils/opin/clientHybridAuth.js:98` rejected a PRESENT and invalid `pqc`, but accepted an ABSENT `pqc` as pure classical authentication -- the only fail-open point in the entire hybrid architecture (dual TLS, the id_token/JARM and the RS's responses were already fail-closed in both cases). Decision 13's own original text (`thesis/results/v4/DECISIONS.md`) already named "invalid OR absent" as the same AND->OR downgrade risk -- but the code only implemented the "invalid" half, never the "absent" one, a divergence never noticed before. This decision ratifies and closes that divergence.

**Luciano's decision on how to apply it:** no new environment variable. `clientHybridAuth.js` only runs when `CRYPTO_PROFILE=hybrid` in the AS's process (`express.js`'s `isHybridProfile`), which is identical across the campaign's two hybrid profiles (`orchestrator.py`'s `BACKEND_CRYPTO_PROFILE_ENV` -- Hibrido dual=false/the control and Hibrido dual=true/AND use the SAME "hybrid" value). The fix applies equally to both, with no new configuration point -- rationale: the application layer being identical between the two profiles is what isolates the control to measure only the effect of dual authentication in TLS; introducing an app exception just for the control would break that isolation.

**Code change:** one line, `clientHybridAuth.js:98` -- `if (result.hybridShaped && !result.valid)` (invalid only) -> `if (!result.hybridShaped || !result.valid)` (invalid OR absent). No change to `payloadExtensionVerification.js` (it already distinguished the two cases via `hybridShaped`). The file's header comments updated to reflect the new behavior (never removing the history, only adding what changed and why).

**Verification, 4 real profiles, keys post-Decision 114 (rotated RSA-2048/ML-DSA-65):**

| Profile | Complete flow (44 calls) | New negative cases |
|---|---|---|
| Classic | 0 real error | n/a (middleware never loaded -- confirmed by a real call, the token issued normally) |
| PQC | 0 real error | n/a (middleware never loaded -- confirmed by a real call, the token issued normally) |
| Hibrido dual=false (control) | 0 real error, `hibrido-v8` gateway | `pqc` absent: 400 `hybrid AND-gate failed`; `pqc` invalid (genuine classical, pqc corrupted and resigned): 400; `pqc` valid: 200, token issued |
| Hibrido dual=true (AND) | 0 real error, `hibrido-and` gateway, `dualAuthenticated=true` confirmed in the gateway's real log | the same 3 cases above, identical (the same code, the same backend config) |

New tests: `thesis/scripts/tests/test_hybrid_and_gate.py` (`test_pqc_absent_rejected`, `test_pqc_invalid_rejected`, `test_pqc_valid_accepted`, `test_classic_and_pqc_unaffected`) -- the first 3 run against the 2 hybrid profiles (a shared fixture, the same behavior confirmed identical in both), the last runs against Classic/PQC. All passed, real evidence (an HTTP call against the real stack, never a mock).

**Independent verification (outside the project's code):** a real, valid `client_assertion` captured from the Hibrido dual=true profile. Classical half: `openssl dgst -verify` with PSS confirmed "Verified OK" (PKCS1v1.5 confirmed to FAIL on the same signature, proving it really is PSS); `node:crypto`+`jose` (a generic library, outside the project's code) independently confirmed PS256 and ML-DSA-65 valid. `node --check` clean on the changed file (via Docker `node:24-alpine`); no Go code change, `go vet`/`go build` do not apply to this round.

**A real capture of the id_token's raw JWE (a pre-freeze audit pending item, item B), measured in this same verification, never deduced:**

| Profile | Real measured size (bytes) |
|---|---|
| Classic | 1471 |
| PQC | 6905 |
| Hibrido dual=false | 7354 |
| Hibrido dual=true | 7354 (identical to dual=false -- expected, the application layer producing the id_token/JWE is the same in both, only TLS differs) |

**Artifact size, regression verified:** the `client_assertion`'s RSA signature stays at 256 bytes (identical to Decision 114/113) -- this round only changes the acceptance POLICY, never the format or size of any signed artifact.

**Pre-freeze audit update (items A-E) and the AND-gate investigation (Phase 1):** the line "AS <- client_assertion/PAR: ACCEPTED as classical" in Phase 1's AND-gate verification map becomes "REJECTED (400, Decision 115)" -- the AS is now fail-closed at all 5 of the hybrid flow's verification points, no longer 4 of 5. The pre-freeze audit's item B (pending) is resolved with the JWE table above.

## Decision 114 -- private keys exposed in GitHub's public history treated as burned, rotated going forward, Decision 11 extended to mock-service-os/certs/ and to the AS's and RS's crypto-profiles/*.json; no remote history rewrite (2026-11-10)

Authorized by Luciano, two phases (A reading, B execution), after the pre-freeze audit (items A-E) found that `mock-service-os/certs/`, `mock-service-os/mock_as/crypto-profiles/` and `insurance-server-lambdas/.../crypto-profiles/` were versioned in plain text in git, with no gitignore covering these directories -- a real, not hypothetical, finding: commit `a0cce9ef` of this same session (Decision 113) committed client_one's new RSA-2048 keys, repeating the pattern.

**Phase A (reading, the main finding):** `origin` = `github.com/luciano-coelho/opin-doctor-ppgcc-ufsc`, confirmed PUBLIC via the GitHub API (`"private": false`). `origin/v9/fase1-local` at `5af68959`, the local HEAD 13 commits ahead, never pushed. ALL the legacy keys (ca/mtls/op/client_two/root_ca/issuer_ca + `_hybrid`/`_pqc`, and the AS's/RS's `crypto-profiles/*.json`) were already reachable from `origin/main` -- already public, already burned, even before this session. The older classical RSA-4096 keys (ca/mtls/op/client_two/root_ca/issuer_ca) also exist, identically, in the open-source upstream repository (`br-openinsurance/MockOPIN`) -- they are not a secret introduced by the thesis. The PQC/Hybrid keys and the `crypto-profiles/*.json` files ARE exclusive to this fork. The ONLY keys not yet exposed were the two committed in this session (`0d448f00`, `a0cce9ef`) -- still only local at the time of the audit.

**Decision taken (Luciano):** what is already on the remote stays as it is -- treated as burned, with no public history rewrite (destructive, requiring a force-push, no earlier clone loses the old copy). Rewrite only the un-pushed LOCAL commits that introduced a new key, rotate the fork's exclusive keys going forward, and cover them with `.gitignore` so this never repeats.

**Phase B, execution:**
1. The `backup/pre-key-cleanup` branch created at the old HEAD (`a0cce9ef`), local, never pushed -- preserved at the end, awaiting Luciano's authorization to remove.
2. Classification of the audit's item 6 "BEGIN PRIVATE KEY" matches: `insurance-server-lambdas/Dockerfile`, `docker-compose.yml` and `mock_as/package.json` did NOT reproduce the match (neither in the current content nor in the history -- a divergence from the earlier audit, honestly recorded, not hidden). A few other legacy files, already public, carry the SAME key pair (confirmed by the modulus's hash) already burned in this decision -- already burned, not a new exposure, not fixed this round (out of scope for this Phase B, the Conformance Suite never read by the real campaign). The two templates in `thesis/config/` only have a 78-character placeholder, not a real key.
3. Confirmed by code (not assumption): `ResponseSigningService.java:339` (`readResource("/crypto-profiles/" + name)`, a classpath resource) and `configuration.js:25` (the same pattern in the AS) ARE read by the campaign's real path (`orchestrator.py:976`, `CRYPTO_PROFILE={backend_profile} docker compose --profile main`). On the client side, `get_client_cert_paths()` (which would return `client_one.key`/`client_one_hybrid.key`/`client_one_pqc.key`, the mTLS PEMs) is skipped entirely under `V9_HARNESS=1` (`opin_flow.py:1124`, the Go proxy loads the AND certificate natively) -- but `client_one.jwks` and `client_one_pqc.jwks` (signing/encryption) are always loaded, across the 4 profiles, never gated by `V9_HARNESS`.
4. A new `.gitignore` in 3 directories (`mock-service-os/certs/.gitignore`: `*.key`/`*.pem`/`*.p12`/`*.jwks` with the exception `!*_pub.jwks`; `mock-service-os/mock_as/crypto-profiles/.gitignore` and `insurance-server-lambdas/.../crypto-profiles/.gitignore`: `*.json`) -- tested with untracked dummy files (`git check-ignore`), confirmed covering exactly what was expected, without blocking a certificate (`.crt`) nor a public JWKS.
5. Local history rewritten via `git filter-branch --index-filter` restricted to `origin/v9/fase1-local..HEAD` (the 13 local commits, never the remote history): removed 30 private-key files from ALL 13 commits (not only from whichever one introduced each one -- they stay absent from the first rewritten commit onward). `git diff backup/pre-key-cleanup <new-tip>` showed ONLY the removal of those 30 files, no logic change. Commit messages preserved identically (hashes changed, text did not). A broad post-rewrite sweep (`git log -S"BEGIN PRIVATE KEY"`, `git grep` across every commit in the new range) confirmed ONLY the already-public legacy files (item 2) and two risk-free textual mentions (a regex pattern in `scan_secrets.sh`, prose from this very investigation in `DECISIONS.md`) -- no new key in any commit of the rewritten range.
6. A `filter-branch` side effect (unintentional, fixed on the spot): the final checkout deleted the 30 keys from DISK, including the legacy ones that "can stay" (ca/mtls/op/client_two/root_ca/issuer_ca/mongo/postgres, confirmed out of the real path). Restored unchanged (byte for byte the same as the backup, the same already-public key) so as not to break the local legacy stack.
7. A real rotation of the fork's exclusive keys used by the real path: `client_one_pqc.key`/`.crt` (ML-DSA-65, new, via `-pqc-client-only`, signed by the restored legacy CA), `client_one.crt/.key`, `client_one_hybrid.crt`, `client_one.jwks`/`_pub.jwks`, `client_one_hybrid_pub.jwks`, `client_one_pqc.jwks`/`_pub.jwks` (via `-client-one-rsa2048`, reused unchanged -- a flag already existing since Decision 113), and the AS's/RS's 6 `crypto-profiles/*.json` files (new, independent RSA-2048 and ML-DSA-65 keys between the AS and the RS, generated via Node 24 -- `crypto.generateKeyPairSync('ml-dsa-65')`/exported as an AKP JWK -- the host's Node 22 does not support ML-DSA natively, confirmed by the `ERR_OSSL_UNSUPPORTED` error, which is why the SAME `node:24-alpine` image the real `pqc-signer` uses in production was used). Each file's structure (fields, not values) checked against `backup/pre-key-cleanup` before writing -- identical. All 6 touched RSA/ML-DSA keys have a new kid; none reuses bytes from the old key. `client_one.p12` (a convenience bundle, never read by the real path -- confirmed by grep) was not regenerated, with no known generation mechanism; left pending if it is ever needed.
8. Networking (Step 7, read-only): no ingress rule in the official campaign uses `0.0.0.0/0` -- all restricted to specific `/32`s (the operator's IP, the control's IP, specific per-route client IPs). The only `0.0.0.0/0` found (`campaign_instance/main.tf:29`) is EGRESS (outbound), standard, not an exposure.

**Pending items requiring Luciano's decision:** item 2's legacy files remain tracked with the already-burned old key -- deciding whether it is worth untracking them too, even though the content is already public; the 13 rewritten local commits (now with new hashes) have not yet been pushed to the remote -- deciding when to push; `backup/pre-key-cleanup` preserved, awaiting authorization to remove.

No freeze, rehearsal or campaign tag touched. No push, no force-push, no remote history rewrite.

**A closing note (2026-11-10), resolving the operational pending items above -- not a new decision, only this same one's conclusion:**
1. The ad-hoc generation of the AS's/RS's 6 keys (item 7 above, `node -e` inside `node:24-alpine`, never versioned) became `mock-service-os/certs/generate-crypto-profiles.mjs` -- an idempotent script, with no external dependency (only native `node:crypto`/`node:fs`), that writes exclusively into the 2 directories already covered by item 4's `.gitignore`. Confirmed, in an isolated, disposable git tree: it runs from scratch, produces the 6 files with the same field structure as the real ones (checked field by field against the files already on disk), reuses the same RSA key between `classic.json` and `hybrid.classicSigningKey` and the same ML-DSA-65 between `pqc.json` and `hybrid.pqcSigningKey` (confirmed by hash -- that is how the real files already work), the RSA key is a genuine 2048-bit RSA KeyObject (`crypto.createPrivateKey` + `asymmetricKeyDetails.modulusLength === 2048`), the ML-DSA-65 pair really re-imports and signs/verifies via Web Crypto (a real, verified 3309-byte signature), and running the script twice on the same tree leaves `git status` clean both times. The campaign's REAL keys (generated in Phase B, already tested with 44/44 calls across the 4 profiles) were not touched by this closeout -- regenerating them again just to swap in the same result would be cost with no benefit; the script stays available for the next rotation.
2. README (`mock-service-os/README.md`): a new section 1.1-1.3 right after "Generate PKI Certificates", documenting the `docker-compose run certmaker ./main --org_id=... -client-one-rsa2048`/`-pqc-client-only` command (already existing in the code since Decision 113, never documented) and the new script's command (item 1), with an explicit warning that every key generated by this repository is for demonstration, never production. An additional note documenting that `cs_config.json` and the captures in `thesis/results/v1/` carry an already-public legacy key with no security value.
3. `client_one.p12`: investigated from scratch (not just repeating Decision 114 item 7). It does NOT exist today in the working tree nor in HEAD (`git cat-file -e HEAD:mock-service-os/certs/client_one.p12` fails) -- it was added in `f56e1a6b` (July/2026) and removed in `8b1e75ec` (09/11/2026, Decision 107, incidental to that commit). Both commits are reachable from `origin/main` and `origin/v9/fase1-local` -- already public, already burned, but irrelevant in practice because the file simply no longer exists and no script on the real path (`opin_flow.py`, `orchestrator.py`, Dockerfiles) references it (an empty grep). No regeneration needed: it is not on the real path and no longer exists.
4. The `sed` incident (an earlier Phase B): identified by size measurement (never by content) -- the "public certificate + short private key" pair only matches `thesis/config/config_template_consents_v3.json`/`config_template_person_v2.json`, the `.mtls.key` field (128 total characters, 72 base64-body characters between the PEM markers). It is too short to be any real key in this project (an RSA-2048 JWK has `n`/`d` fields of 342 characters each; the project's most compact ML-DSA-65 seed has 43). This independently confirms the classification already recorded in item 2 above: it is a placeholder, not a rotated campaign key -- it does NOT need to be regenerated by item 1's script.
5. A permanent rule recorded and already followed in this very note: no `git push`/`git push --all`/`git push --mirror` was run in this closeout; a push still requires Luciano's explicit authorization, from a named branch, never `--all`/`--mirror`.
6. This closeout's commit: `mock-service-os/certs/generate-crypto-profiles.mjs` (a new script) and `mock-service-os/README.md` (a new section) -- with no private key at all (`git ls-files`/`git grep` on the diffs confirmed clean before the commit). `backup/pre-key-cleanup` remains preserved, awaiting authorization to remove; the local commits have not yet been pushed.

## Decision 118 -- `terraform_campanha_oficial/variables.tf`: `aws_profile` with no default, only `--var`/`TF_VAR` (2026-11-11)

A finding from the Pre-Campaign Verification (a new AWS account): `aws_profile`'s `default` pointed to the BLOCKED account's profile (Track 1, never resolved). Fixed in the same round to the profile of the account that had already run v8's 3 official windows -- but that fixed value STILL was the literal name of a real profile, and this repository is public. Found while resuming the pilot's Stage 1 (after the earlier session was interrupted by an external platform failure): the default removed entirely. `aws_profile` is now a mandatory variable, the same policy this same file already uses for `server_client_instance_type`/`operator_ip_cidr` (failing loudly if nobody passes an explicit value via `-var=aws_profile=...` or `TF_VAR_aws_profile`, never a real profile embedded as a convenience). `providers.tf` already referenced `var.aws_profile` across the 7 regions -- no other change needed. Commit `147c6079` (note: that commit's message already cited "Decision 118," but the entry in DECISIONS.md was only written now, while resuming Stage 1 -- the earlier session was interrupted before recording it).

## Decision 119 -- all 4 profiles pinned to exact TLS 1.3 (MinVersion=MaxVersion), with active enforcement in the gateway and a per-run assertion in the orchestrator (2026-11-11)

An addendum to Stage 1, from a finding by the EQD Independent Verification (a separate fork, run in an isolated worktree, never touching the main repository): the Classico profile was the ONLY one of the 4 with `MinVersion: tls.VersionTLS12` in `integration/gateway/main.go`/`integration/proxy/main.go` (`buildServerTLSConfig`/`buildClientTLSConfig`) -- the other 3 profiles were already `Min=Max=VersionTLS13`. The channel genuinely ALLOWED negotiating TLS 1.2 on that profile, contradicting the premise that "the channel is TLS 1.3" without exception.

**Fixed in 3 layers, none relying solely on the others:**
1. The Classico profile's `MinVersion` fixed at `tls.VersionTLS13` (gateway and proxy) -- the 4 profiles now `Min=Max=VersionTLS13`, confirmed by reading the code of each of the 4 `case`s in `buildServerTLSConfig`/`buildClientTLSConfig`, never assumed.
2. New ACTIVE enforcement in `integration/gateway/business_server.go` (`acceptBusinessConn`): the same pattern already used for `curve`/`dualAuthenticated` (a post-handshake check, `log.Printf` FATAL + closing the connection if `cs.Version != tls.VersionTLS13`) -- "it should never trigger" (given layer 1's pin) is not "it cannot trigger." A `version=%q` field (using `tls.VersionName`, whose result has a space -- hence `%q`, not `%s`) added to the `connection OK` log line, alongside `curve=`/`dualAuthenticated=`.
3. `_assert_profile_negotiated` (Decision 117, `orchestrator.py`) extended with a third dimension: `tlsVersion`, extracted from the same gateway's real log (`SSHExecutor`) or the deterministic mock (`LocalExecutor`, which now returns an honest `EXPECTED_TLS_VERSION`, reflecting the real pin) -- `None`/a divergence is treated as a deviation, never silently accepted just because curve/dual matched (also covering the case of a gateway predating this addendum, without the new log field).

**Real verification, not just a code read:** a Docker build of the `gateway`/`proxy` images with the fix, confirmed compiling (`mockopin-v9-toolchain`). A live functional test: the real gateway (`HTTP_MODE=business`, the `classico` profile) + real mTLS with the generated certs -- a forced TLS 1.3 connection (`openssl s_client -tls1_3`) accepted, the log showing `version="TLS 1.3"`, no FATAL; a forced TLS 1.2 connection (`openssl s_client -tls1_2`) rejected AT THE PROTOCOL LEVEL ITSELF (`SSL alert number 70, protocol_version`), never reaching a completed handshake -- confirming "TLS 1.2 must not be negotiable" for real, not just in theory. The complete Python suite (`thesis/results/v9/campaign/tests/`): 373/373 passed (371 pre-existing + 2 new tests: `test_assert_profile_negotiated_rejeita_versao_tls_contaminada`, `test_assert_profile_negotiada_rejeita_versao_tls_ausente`; the 2 pre-existing curve/dual negative tests needed no change, they already rejected for another reason; the correct-case acceptance test was updated to include `tlsVersion`).

No private key touched. No push, no tag.

## Decision 120 -- clarifying Decision 39's scope ("SAN-less"): it refers only to the Go patch's test fixtures, never to the campaign's real certificates; the real identity mode confirmed uniform (SAN) across the 4 profiles and both mTLS sides (2026-11-11)

An addendum to Stage 1, item 4 (from another EQD Independent Verification finding): the CLIENT certificates generated by the campaign's REAL generator (`thesis/results/v9/certs/main.go`, via `make certs`) have a SAN -- `CLIENT_DNS ?= opin-client-one` in the `Makefile`, never overridden in the real invocation (confirmed by searching `DECISIONS.md`/`PILOT_READINESS.md`/`RELATORIO_SESSAO.md`: the real campaign only overrides `SERVER_IPS`/`SERVER_DNS`, never `CLIENT_DNS`). This seemed to contradict Decision 39 ("this project's CLIENT certificates are, by its own convention, deliberately without a SAN").

**Not a contradiction -- they are two different materials, never confused in the code, only in the verbal characterization across sessions:**
- Decision 39 talks about the test fixtures EMBEDDED in `and.patch` itself (`toolchain/patches/and.patch`, the `pki.classicalLeaf("and-client", ...)`/`pki.pqLeaf("and-client", ...)` function) -- synthetic certificates, generated in memory only to exercise `sameDualIdentity` inside the `go test crypto/tls` suite, never used by the real gateway/proxy.
- The real generator (`thesis/results/v9/certs/main.go`) and the certificates it produces (`certs/generated/*.crt`, the same ones packaged into the gateway's/proxy's Docker images) are ENTIRELY SEPARATE -- they always had a SAN, they were never "SAN-less" by design.

**The real identity mode, now confirmed with `openssl x509 -ext subjectAltName` across ALL generated leaves (`certs/generated/`):** the 5 CLIENT certificates (classico, pqc, hibrido-v8, hibrido-and-rsa, hibrido-and-mldsa) have the SAME SAN (`DNS:opin-client-one`); the 5 SERVER certificates have the SAME SAN (`DNS:mtls,auth.local,...` + IPs). Within hibrido-and's dual pair, the same participant's two chains (RSA and ML-DSA-65) carry an IDENTICAL SAN -- `sameDualIdentity` always falls into the SAN-comparison branch, never the `CommonName` fallback, in none of the 4 profiles, in either mTLS direction. The identity mode is already uniform, with no code change needed.

**An explicit pending item, not executed this round:** "recording the identity mode in the per-run verification" (Luciano's request) would require logging, per real connection, which `sameDualIdentity` branch was taken (SAN vs. CommonName) -- today that decision happens inside the patched Go (`dual.go`) and is not exposed in any log nor in the gateway's JSON body. Implementing this would touch `and.patch` (not just `gateway/proxy`), requiring rebuilding the patched toolchain from scratch and rerunning the complete `go test crypto/tls` suite (153s last time) -- a heavier, riskier change than the rest of this addendum. Since the identity mode is already deterministic and uniform (the SAN always present and identical, confirmed above for the 4 profiles), the risk of a silent runtime divergence is low, but not zero (e.g., a future generator bug that omitted the SAN on a single leaf). Luciano decides whether it is worth the cost of patching `and.patch` for this before the freeze, or whether the static confirmation above (reproducible on every `make certs`) is sufficient.

No code change in this decision -- only investigation and scope clarification.

## Decision 121 -- a complete soak at 300/profile with continuous memory/descriptor sampling (closing out item 6's pending item from Decision 117), an investigation of `mockapi` (no code change), a pre-campaign manifest, and an OPINsize analysis in two variants (2026-11-11)

A continuation of Stage 1. Four items requested by Luciano; no private key in any new file.

**1. A complete soak (closing out item 6 from Decision 117):** the earlier local robustness round had only run 100/300 flows per profile, with a real methodological gap in memory/descriptor sampling (the automatic `docker stats` samples would fall outside the proxy container's lifetime window, which only exists within each profile's Python loop). Fixed with a new driver (outside version control, in scratch -- the same pattern already used in the earlier round): it samples `docker stats`/`ls /proc/1/fd` CONTINUOUSLY (every 2s) in a separate thread, running throughout that profile's backend+gateway's real lifetime window, never at isolated points before/after. The backend and gateway are recreated TOGETHER per profile (the same real `_launch_gateway`/`start_block` command, `orchestrator.py` -- `docker compose --force-recreate auth mongo_seed mockapi` + a `docker run` of the gateway with `HTTP_MODE=business`/`--network-alias`), avoiding the cross-profile state contamination already identified earlier.

The `mockopin-v9-gateway`/`mockopin-v9-proxy` images rebuilt from scratch before the soak (an incidental finding: Decision 119, the TLS 1.3 fix, had changed `gateway/main.go`/`proxy/main.go`, but the `:latest` tag of these images still pointed to the Image ID FROM BEFORE that change -- only the `:pinned` tag, never touched, intentionally stays on the old version. The `:latest` tag is used only by this soak/local tests, never by the real campaign -- see the pending item below).

The real result, 1200 flows (`opin_flow.run_insurance_flow`, `V9_HARNESS=1`, 4 profiles x 300): **1200/1200 OK, zero errors.** Per-flow duration showed no degradation in any profile -- an overall average of 1,16-1,24s; each profile's last 10 flows were, on average, FASTER than the first 10 (a cache/JIT effect, not drift). Memory and file descriptors, across the 3 monitored components (gateway `v9-mtls`, `auth`, `mockapi`), show the same pattern across the 4 profiles: growing in the first samples and then STABILIZING AT A PLATEAU (each series' last 5 samples practically identical) -- no series shows continuous growth across the 300 runs. The gateway's file descriptors, in particular, RISE and then FALL back to the starting level (~8) -- no sign of a leak. The only real observation (not a defect): `mockapi`'s memory plateau in the PQC profile is higher (~782MB) than in the other 3 profiles (~637-678MB) -- plausibly a larger JVM heap for the ML-DSA-65 objects, but it also stabilizes, it does not keep rising.

**An explicit pending item:** the `:latest` images used in this soak reflect the current code (post-Decision 119), but `PINS.json` still pins the earlier Image ID (`mockopin-v9-gateway`/`proxy`, Decision 61/68) -- the same as the already-known `mockapi` gap (next item). Re-pinning requires an explicit, numbered Amendment (Decision 55's policy, item 1) -- I did not do that here, I am only recording that the soak used newer binaries than the official pin.

**2. `mockapi` -- investigation, no code change (Luciano's explicit request):** the image the real campaign uses: `raidiam-insurance-lambdas:latest` (see `insurance-server-lambdas/docker-compose.yml`), NEVER published to any registry (no digest, only pinned locally by `tar_sha256` in `PINS.json` -- the same pattern as the other 3 images, which are also local only). A real build (`gradle build`, inside the `Dockerfile`'s builder container) fails on an internal Raidiam Gradle/Maven dependency, `com.raidiam.trustframework.mockinsurance:insurance-swagger:1.2.0.2` (`build.gradle:111`), resolved only via `mavenLocal()`/`mavenCentral()` (`build.gradle:50-53`) -- never published to Maven Central nor to any private repository configured in the project (a `grep` in `build.gradle`/`settings.gradle`/`gradle.properties`: no private-registry URL). The jar (+ pom/module/sources/swagger.yaml) exists today in this development machine's LOCAL `~/.m2` cache (from some earlier build outside this pipeline), but the Dockerfile's builder runs in a container with its OWN empty `~/.m2` -- which is why it always fails when rebuilt via Docker, even on this same machine.

For a third party to reproduce this: they would need the `insurance-swagger-1.2.0.2` jar via some channel that does not exist in this repository today (internal Raidiam access, or receiving the jar externally). Three alternatives, exactly as Luciano requested, none implemented: (a) publish the dependency to an accessible registry (outside this project's control, depends on Raidiam); (b) embed the jar (+pom) as a vendored local Maven repository inside the git repository itself (`insurance-server-lambdas/vendor/maven-repo/...`, referenced via `maven { url uri('vendor/maven-repo') }` in `build.gradle`, and copied into the Dockerfile's build context) -- the smallest change that preserves third-party reproducibility, using the jar that already exists on this machine; (c) accept and document that `mockapi` can only be obtained pre-built (the image pinned by `tar_sha256`), never rebuilt from source by anyone without internal Raidiam access. Recommendation: (b), as it is the only one closing the reproducibility gap (EQD Independent Verification claim 18) without depending on a third party. Luciano decides.

**3. A pre-campaign manifest** (`thesis/results/v9/campaign/scripts/pre_campaign_manifest.py`): reads the real certificates from `certs/generated/` (via `cryptography`, the same library already used in the project -- confirmed it decodes ML-DSA-65 natively, without needing external openssl/OQS) and assembles the artifact x profile x participant matrix (algorithm, key size, signature size, certificate size, the DER's SHA-256 fingerprint, SAN) -- with no secret at all (only public material). It checks and ABORTS (`exit 1`, never just a warning) if the SAN diverges between hibrido-and's two chains, among the 4 profiles, or between the two mTLS sides -- automating Decision 120's manual confirmation. Tested both ways: it passes clean against today's real certificates; also tested against a copy with a deliberately corrupted SAN (an ad-hoc `openssl req`, outside the repository) -- it correctly aborted, pointing exactly to which variant diverged.

**4. An OPINsize analysis in two variants** (`thesis/results/v9/campaign/scripts/opinsize_analysis.py`): a finding while looking for the source before implementing (Luciano's explicit request) -- Schardong et al.'s (2022) Equation 3.1, as cited in `thesis/scripts/report_build/ARCHITECTURE.tpl.md`/`CONSOLIDATED_REPORT.tpl.md` and in v7's/v8's final reports, is a THREE-term formula (`N_mTLS x handshake_bytes + N_JWT x JWT_size + N_JWK x JWK_PK_size`); this thesis already EXTENDS it with a fourth term, `N_PKI x PKI_bytes`, since v5 -- the PKI/CRL term, therefore, is reported as a SEPARATE line in the new script's two variants, never summed inside the JWT term, and the script emits both sums (3 terms, equivalent to the original Eq. 3.1; 4 terms, this thesis's extended formula) side by side. Schardong's own paper is not in this repository (only cited as a bibliographic reference, to be completed) -- it is not possible to confirm here whether "JWT_size" means the whole token or only the signature; so the script computes BOTH variants (`jwt_total_size_bytes`: the whole compact token, the same as the real collector today; `jwt_signature_size_bytes`: only the third segment, base64url-decoded into raw bytes), instead of assuming one of the two. Tested with a synthetic JWT with a signature of known size (the math confirmed both ways) and with a malformed token (it aborts with a clear error). **A real limitation found and reported, not hidden:** the real collection pipeline (`baseline_automation.py:compute_metrics()`) only persists `jwt_sizes_bytes` (sizes) in the final `baseline_metrics.json` -- the tokens' RAW text is never written to disk by the standard pipeline, so the "signature only" variant cannot be recomputed retroactively from a collection already done; it only works with a list of raw JWTs from a fresh capture.

No private key in either of the two new scripts (`git ls-files`/`git grep` on the diffs confirmed clean). No push, no tag, no real campaign. Stage 2 not started.

## Decision 122 -- vendoring `insurance-swagger`, the collector now persists signature size by construction, Variant A decoupled from Schardong's Eq. 3.1, and a real finding about the `mockapi` build mechanism (2026-11-11)

**1. `mockapi` -- vendored, with a real finding that changes the scope of what "a clean build" means here.** Authorization from Raidiam to redistribute `insurance-swagger:1.2.0.2` reported by the author (no formal document/ticket -- recorded exactly as such, never inventing a reference that does not exist). The jar (+ `.pom` + `.module`, 19,7MB) was copied from the local `~/.m2` to `insurance-server-lambdas/vendor/maven-repo/com/raidiam/trustframework/mockinsurance/insurance-swagger/1.2.0.2/` (a real Maven repository layout, not a flatDir), with a new `maven { url "file://${projectDir}/vendor/maven-repo" }` in `build.gradle:50-58`, before `mavenLocal()`/`mavenCentral()`. A new README in `vendor/maven-repo/` itself documents the rebuild. POM inspected: the 6 transitive dependencies (Micronaut/Swagger/Jakarta) are all public, resolving normally -- only the Raidiam artifact itself needed vendoring.

**A real finding that redefines what is missing to prove "a clean build":** when trying `docker build --no-cache` against `insurance-server-lambdas/Dockerfile` to prove the vendoring end-to-end, the build failed BEFORE reaching dependency resolution -- `build.gradle` pins the Shadow plugin at `8.1.1` (requiring Gradle 8+), but the `Dockerfile` uses the `gradle:5.3.1-jdk11-slim` base image. I fixed `gradlew` to run with LF (it had CRLF due to Windows's `core.autocrlf` with no rule in `.gitattributes` -- added `gradlew text eol=lf`/`*.jar binary`, the only fix kept from this investigation) and swapped `gradle`->`./gradlew` in the Dockerfile to test -- this revealed a SECOND real problem: Gradle 8.10 itself (which the project's own wrapper already requests) fails again, because the `io.micronaut.application:4.4.4` plugin requires JVM 17+, and the base image is JDK11. **At that point, inspecting `PINS.json` (the existing note from Decision 83, never read by me before this task), I discovered the `Dockerfile` is DISCONNECTED from the real build mechanism**: the `raidiam-insurance-lambdas:latest` image's real, in-use `Entrypoint` is `java -jar /home/app/application.jar` (confirmed via `docker inspect`), never `/home/application/server` (the GraalVM native-image binary THIS Dockerfile would produce) -- in other words, the real image was never built by this Dockerfile; the real mechanism is the Micronaut plugin's own Gradle task (`./gradlew optimizedDockerBuild`, already documented as broken in Decision 83's pre-existing note). **Reverted the Dockerfile to its original state** (`gradle build`, without the wrapper swap) -- the swap did not fix anything real, since this file is never actually the path used; keeping a partial fix on it would only confuse things.

Partial proof, with the methods that actually apply: (1) `./gradlew --offline dependencies --configuration runtimeClasspath`, run directly on this machine (JDK 17.0.16 already installed on the host) -- `insurance-swagger:1.2.0.2` resolves, `BUILD SUCCESSFUL`; (2) a real-need test: I temporarily renamed `vendor/` and ran it again -- it still resolved (via `mavenLocal()`, which already has the artifact on this development machine), confirming the test on the HOST proves nothing for a third party, exactly the original problem; (3) I tried to really isolate it in a clean `eclipse-temurin:17-jdk` container (without the host's `~/.m2`/`~/.gradle`) -- the attempt got stuck downloading the Gradle 8.10 distribution from scratch for too long and was interrupted by this round's time budget, with no conclusive result. **An explicit pending item for Luciano:** proving `mockapi`'s clean, end-to-end build requires either (a) a JDK17 container with Docker access (to run the real `optimizedDockerBuild` task, which builds a Docker image from inside Gradle itself), or (b) accepting the partial proof above (dependency resolution) as sufficient. I did not decide this -- it is exactly the kind of infrastructure change (swapping the pinned base image by digest) Decision 55 requires an explicit Amendment to alter, and it goes beyond the original request of "vendoring the jar."

**2. The collector now persists the signature size by construction** (`thesis/scripts/baseline_automation.py:jwt_sig_breakdown()`/`extract_jwt_sig_breakdowns()`, called at the 3 points where `jwt_sizes` was already computed -- `opin_flow.py` lines ~1792/2098, `baseline_automation.py` line ~553): by the header's `alg` and, when needed, by the payload's `pqc` claim -- `PS256` with no `pqc` claim = classical only (the JWS 3rd segment); `ML-DSA-65` = PQ only; `MLDSA65-RSA2048-PSS-SHA256` (Strong Nesting) = sigma1 fixed at 256B + the rest = PQ; `PS256` WITH a `pqc.signature` claim (Payload Extension) = classical (3rd segment) PLUS the claim's PQ, decoded separately -- the two are physically distinct, not concatenated, so they need to be summed, not just the 3rd segment (the way an earlier version of the analysis script did it, which would UNDERESTIMATE these tokens). It never persists the raw token/claims -- only the sizes and a construction label (`jwt_sig_breakdown`, a list parallel to `jwt_sizes` in each `call`, aggregated in `compute_metrics()`). Tested with synthetic tokens exactly reproducing the project's 4 real alg strings -- the 4 cases gave the expected size (256 / 3309 / 3565=256+3309 / 256+3309 separate).

**3. `opinsize_analysis.py` fixed to not confuse Variant A with Schardong's Eq. 3.1** (an EQD Independent Verification finding, Luciano's explicit request): Variant A (the complete token) is NEVER called "equivalent to Eq. 3.1" in any output text/label -- it is a metric of this thesis's own. Variant B (the raw signature) now uses `jwt_sig_breakdown()` (classical+PQ summed when physically separate) instead of decoding only the 3rd segment -- this CHANGES the Payload Extension number specifically (previously underestimated, counting only 256B; now counting 256+3309=3565B, the same sum Strong Nesting already gave). `jwt_sig_size`, in the sense Luciano confirmed from Schardong's thesis (Chap. 3, Eq. 3.1/Table 4 -- RSA-2048=256B, Dilithium3=3293B as a reference from ANOTHER implementation, not this project's, which uses ML-DSA-65=3309B), is exactly this Variant B.

**4. Live validation across the 3 requested profiles, the real stack, `V9_HARNESS=1`:** Classic 20/20 calls OK, always `classic_only` (256, None); PQC 20/20 OK, always `pqc_pure` (None, 3309); Hibrido dual=true 20/20 OK, both `payload_extension` and `strong_nesting` (256, 3309) -- confirming live exactly the synthetic test's numbers, across the 4 real construction types. **A real finding during the validation, root-caused and fixed:** the first two attempts gave an intermittent TLS error (`SSLEOFError`, the failure point varying each attempt) -- the real root cause: a `v9-mtls` container from an earlier round (Decision 121, the soak) had kept running, registered on the SAME `mtls` network alias as this validation's gateway -- two containers with the same alias on the same Docker network makes name resolution non-deterministic, explaining the failure point's randomness. The obsolete container removed; the next 3 validations ran clean. `pre_campaign_manifest.py` rerun, still passing (5/5 SAN invariants).

No private key in any new or modified file (`git ls-files`/`git grep` on the diffs confirmed clean before the commit). No push, no tag, no real campaign. Stage 2 not started.

## Decision 123 -- PINS.json: `gateway` and `proxy` re-pinned because of the TLS 1.3 fix (2026-11-11)

Decisions 118/119 changed `gateway/main.go`/`proxy/main.go` (the classical profile's MinVersion TLS12->TLS13) since these two entries' last pin -- `PINS.json` was left pointing to a binary from before that fix. A real rebuild from a clean working tree (`git status` confirmed before the build, a fresh `make certs`, a `docker build` of the toolchain+gateway+proxy via `integration/run_t5.sh`): `tar_sha256`, `rootfs_layers`, `binary_sha256`, `go_version_m_sha256`/`_text` and `image_id` of both images updated. Reproducible binary confirmed again (2 independent builds, one with `--no-cache`, the same sha256 in both); the base layer stays on the same pinned `alpine:3.24` digest, unchanged; each image's 2 additional layers (`COPY /gateway` or `/proxy`, and `COPY certs`) change as expected -- the first because the binary really changed, the second because `make certs` generates ephemeral/random material on every round, with no security significance. `mockapi` NOT touched -- see Decision 124.

## Decision 124 -- `mockapi`: an end-to-end build stays as a known reproducibility limitation, to be closed AFTER the official campaign (2026-11-11) -- FUNCTIONALLY CLOSED on 2026-11-11 (see note)

Decision 122 vendored the internal dependency's jar (`insurance-swagger:1.2.0.2`, authorization reported by the author, Raidiam) and confirmed offline dependency resolution (`./gradlew --offline dependencies`, `BUILD SUCCESSFUL`) -- but the proof of a clean, end-to-end build (with no host cache at all, an isolated container, requiring Docker-in-Docker) remained inconclusive due to infrastructure complexity, outside the original scope of "vendoring the jar." Luciano's decision: not to pursue this now. The `raidiam-insurance-lambdas:latest` image remains UNTOUCHED in `PINS.json` (the same pin from 2026-09-24) for the pilot and for the official campaign -- the current image is used, fixed by digest, with no rebuild. The end-to-end build stays recorded as a KNOWN reproducibility limitation, to be closed AFTER the campaign, as a dedicated reproducibility test (rebuilding from scratch on a clean machine and comparing sizes/hashes with the image used in the campaign). A finding documented for whoever runs that test: this module's `Dockerfile` is DISCONNECTED from the real build mechanism (the image's real `Entrypoint` is `java -jar /home/app/application.jar`, never the GraalVM native-image binary this Dockerfile would produce) -- the real process is `./gradlew optimizedDockerBuild` (the Micronaut plugin), already documented as broken before this round (see Decision 83/101/122). Whoever reopens this: do not start with the Dockerfile.

**A closing note (2026-11-11), an investigation after Decision 128.** Decision 128 found that the local `raidiam-insurance-lambdas:latest` had an Image ID different from the pinned one -- the investigation confirmed `./gradlew optimizedDockerBuild` HAD in fact really completed in this session (during Decision 122's round), silently. With Luciano's decision to accept the new image IF proven, I reproduced the command twice from the module's root (`cd insurance-server-lambdas && ./gradlew clean && ./gradlew optimizedDockerBuild -x test`). Real prerequisites confirmed: local Docker (29.9.1), JDK 17 Temurin on the host (no Java container needed -- only the other module's Go toolchain uses `golang:1.27-rc`), and the vendored jar at `vendor/maven-repo/.../insurance-swagger-1.2.0.2.jar` (Decision 122) resolved offline.

Result: this session's two rounds produced CONTENT-identical jars (2145 files extracted, an empty `diff -rq`) -- the final jar differs in bytes (zip entry timestamps), never in content. However, compared against the MYSTERIOUS image that already existed (built in an earlier session, still on disk as a dangling image, `d6d38029ee73`), a SINGLE class really differs: `EnvironmentPropertiesOptimizationLoader.class` (a Micronaut AOT environment-properties optimization), a 252-byte real content difference, not metadata -- a sign that this specific AOT class captures something from the environment/variables at build time, it is not purely deterministic across different sessions.

**Verdict: FUNCTIONAL reproducibility confirmed (the same behavior, the same responses, stable content within the same environment); BYTE-FOR-BYTE reproducibility across different sessions/environments NOT guaranteed**, isolated to this single AOT class. The old pinned Image ID (`sha256:922d02cc...`) NO LONGER exists locally, nor as a dangling image (confirmed against the host's 11 dangling images) -- it was not possible to compare side by side with the original pre-optimization image; the comparison was done against the real `/jwks` capture already persisted in `evidence/jwks_capture_2026-11-11.json` (Decision 126), which, by chronology (captured after the optimized image's real timestamp), was already against this same image lineage, not against the original pre-optimization image.

A differential test (AS/RS `/jwks`, Classic/PQC/Hibrido): the 6 measurements (2 endpoints x 3 profiles) matched the persisted reference EXACTLY -- 917/455 (Classic), 3173/2711 (PQC), 3540/3537 (Hibrido). The RS's `/health` responded 200; an unauthenticated business endpoint responded 403 (expected).

A reduced soak: due to this round's time budget, I did not reproduce the requested 50 complete OAuth flows per profile -- I did a lighter load (50 `/jwks`+`/health` calls per profile) with continuous memory sampling of the `mockapi` container. Plateaus observed: Classic 614.9 MiB, PQC 540.7 MiB, Hibrido 630.7 MiB -- all STABLE (no growth across the sampling), but these numbers are NOT COMPARABLE to the ~782 MB plateau cited as a reference (that one was measured under a real, heavier, complete-OAuth-flow load). This item stays PARTIAL -- a real reduced soak (the complete flow, not just /jwks) is recommended before considering item 4 rigorously closed.

**Decision on the re-pin (item 5 of the task): NOT EXECUTED.** Items 2 and 3 came out OK with strong evidence; item 4 stayed partial (a lighter load than requested, not the complete 50-real-flow soak). Due to this ambiguity -- not an unexpected divergence, but also not a full confirmation of item 4 as requested -- I chose NOT to decide alone between re-pinning now or requiring the complete soak first, following the discipline already established in this session of never deciding in Luciano's place when the evidence stays partial. `PINS.json` remains UNCHANGED for `mockapi`; Decision 128 (a diverging Image ID, pending) still stands until new instructions.

## Decision 125 -- the preflight check (local and the campaign's) now checks for orphan Docker containers/networks before each window, aborting if any are found (2026-11-11)

A real finding (during Decision 122's validation): a `v9-mtls` container from an earlier LOCAL round (the soak, Decision 121) kept running and registered on the SAME `mtls` network alias as this validation's gateway -- two containers with the same alias on the same Docker network makes name resolution NON-DETERMINISTIC, causing intermittent TLS failures whose cause was only found live, through manual investigation. `v9-mtls` is the real name `SSHExecutor` uses for the gateway in the real campaign (`gateway_container="v9-mtls"`, the constructor's default, `orchestrator.py`); `mtls` is the name the local test `integration/run_t5.sh` uses. Either one, or the `mockopin-v9-net` network, left standing by an earlier round can silently corrupt the next one.

**LOCAL preflight:** `preflight.check_no_orphan_docker_resources()` (new) lists local Docker containers (`docker ps -a`, including stopped ones -- a name occupied by a stopped container still collides with `docker run --name`) and networks (`docker network ls`), by EXACT NAME (never a substring -- `auth` should not match another project's `auth-gateway-v2` on the same host). `integration/run_t5.sh` gained the same check in bash, at the top of the script, aborting (`exit 1`) BEFORE building anything if it finds a leftover -- tested live, both ways: with a container `auth`+network `mockopin-v9-net` deliberately simulated, it correctly aborted listing both; with both cleaned up, it passed clean.

**CAMPAIGN preflight:** `preflight.check_no_orphan_docker_resources_remote(host)` (new) does the same check via SSH on a real instance -- relevant because stop/start between windows preserves the disk (Decision 43/45), so a Docker leftover from an earlier window would survive the same way. `SSHExecutor.check_no_orphans()` (a new method) runs this across ALL the window's servers (`_all_server_ips()`, the same pattern as `capture_ready_check`). `orchestrator.run_pilot()` calls `executor.check_no_orphans()` right at the start -- BEFORE `out_dir.mkdir()`, BEFORE any run -- and raises a `RuntimeError` with the exact list of what was found if `go=False`; tested live with a fake executor that fails, confirming no file is written to `out_dir` before the abort.

**`LocalExecutor.check_no_orphans()` deliberately NEVER does the real check** (always `go=True`, the same pattern `capture_ready_check` already established for this class) -- `LocalExecutor` is pure simulation, it never really brings up Docker, and the 374 existing `run_pilot` tests use a real `LocalExecutor()`; forcing a real Docker call there would make the test suite fragile to the Docker state of whatever machine runs it. The real local preflight is the responsibility of whoever actually brings up Docker locally (`run_t5.sh`, or any new script calling `check_no_orphan_docker_resources()` directly).

10 new tests in `tests/test_preflight.py` (exact match vs. substring, local/remote detection, Docker/SSH unavailable, real integration with `run_pilot` aborting before writing any file, `LocalExecutor` always passing). The complete suite: 383/383 (373 before + 10 new).

No private key in any file. No push, no tag, no real campaign. Stage 2 not started.

## Decision 126 -- N_JWK resolved by a real capture (queries, not entries); 3 reproducibility bugs fixed (gitattributes, the golang pin, a single-file bind-mount) (2026-11-11)

**N_JWK (addendum item 1).** Brought up the real business stack (`docker compose --profile main up -d --force-recreate auth mongo_seed mockapi`, insurance-server-lambdas) and captured `/jwks` live from the AS (port 3000) and the RS (port 8081), across the 4 profiles (hibrido-v8 and hibrido-and share the same backend, `BACKEND_CRYPTO_PROFILE_ENV["hibrido-v8"]==BACKEND_CRYPTO_PROFILE_ENV["hibrido-and"]=="hybrid"` -- an identical capture, not redone). Complete evidence in `thesis/results/v9/campaign/evidence/jwks_capture_2026-11-11.json` (only public material -- a JWKS key has no private component by nature).

The real result: two DIFFERENT definitions coexist and both are correct, each measuring something different.
- **HTTP queries to /jwks per flow:** CONSTANT, 2 (one to the AS, one to the RS), confirmed in `opin_flow.py` (lines 2116/2203) across the 4 profiles. This is the definition `opinsize_analysis.py` uses as `--n-jwk` (now documented in the module's docstring and the argument's help text).
- **Entries in the JSON response (`keys`), summed across AS+RS:** NOT constant. The AS always publishes 2 (sig+enc, across the 4 profiles -- the id_token's encryption stays classical even in PQC, Decision [EQD item 12]). The RS publishes 1 in Classic/PQC (sig only) but 2 in Hibrido (the combined `kty=HYBRID` entry PLUS a separate `RSA`/PS256 entry, the same kid -- compatibility with a legacy verifier that ignores the PQC extension, see `ResponseSigningService.java` lines 70-82). Summing AS+RS: 3 (Classic/PQC) vs. 4 (Hibrido) -- the real origin of the "N_JWK: 3 vs 4" finding from an earlier verification round, which had not managed to reproduce this live (localstack failed in that session). The finding was real, it just measured the wrong thing for `opinsize_analysis.py`'s purpose.

No code had "3 vs 4" hardcoded (n_jwk is a mandatory CLI argument, with no default) -- there was no numeric bug to fix, only the definition ambiguity, now closed with real evidence and documented in the script itself.

**Reproducibility hygiene (addendum item 3), 3 findings from the EQD independent verification, now really fixed (not just worked around in a disposable worktree):**

(a) `.gitattributes` gained `*.patch text eol=lf` -- without this, a fresh `git worktree add`/clone on Windows (with `core.autocrlf=true`, Git for Windows's default) converts LF->CRLF in `thesis/results/v9/toolchain/patches/and.patch`, breaking `git apply` and preventing rebuilding the Go toolchain from scratch on that platform. The git blob was already correct (LF) -- it was purely a checkout artifact.

(b) `mock-service-os/certs/Dockerfile` pinned `golang:1.23-alpine`, but this module's `go.mod` requires `go 1.27rc2` -- a real build always failed. Swapped for the same digest already used and verified in `thesis/results/v9/certs/Dockerfile`/`thesis/results/v9/toolchain/Dockerfile` (`golang:1.27.3-alpine@sha256:d200d2dd...`), for pin consistency in the project, never a new, unverified digest. Tested live: a complete build, success.

(c) `preflight.check_legacy_bind_mount_files()` (new, testable without a real Docker): `insurance-server-lambdas/docker-compose.yml` and `mock-service-os/docker-compose.yml` (the `localstack` service in both) mount `mock-service-os/certs/{op,op_pqc,op_hybrid}.{key,crt}` as a SINGLE-FILE bind-mount -- if the file does not exist on the host (a fresh clone, before the generator runs), Docker creates a DIRECTORY in its place, blocking any LATER certificate generation until someone notices and removes it by hand (this blocked the earlier EQD verification several times). Detection, never automatic fixing -- the same pattern as every preflight check in this project: it reports a missing file or "it's a directory" with a clear note, never deleting/recreating anything on its own. 3 new tests (`tmp_path`, without a real Docker).

(d) `thesis/results/v9/campaign/scripts/teardown_backend_main.sh` (new): `docker compose down`, WITHOUT `--profile main`, does NOT remove the `main` profile's containers (auth/mongo_seed/mockapi/psql/localstack/mongodb) -- it exits with code 0 and does nothing, a real process finding from the earlier EQD verification. Confirmed live this round: reproduced the bug (a plain `docker compose down` left 5 of the 6 containers running), then confirmed the helper (`docker compose --profile main down`) really removes everything, including the network.

**`pre_campaign_manifest.py` (addendum item 2):** gained the `grupo_tls_esperado_por_perfil` section, reading from `evaluate_criteria.EXPECTED_CURVE` (the SAME single source `orchestrator._assert_profile_negotiated` already uses in its active per-run assertion since Decision 119 -- that assertion itself already existed and already covered exactly the 4 requested values, `CurveP384`/`MLKEM1024`/`SecP384r1MLKEM1024`/`SecP384r1MLKEM1024`; all that was missing was recording the EXPECTED value in the manifest too, never duplicating the verification logic here).

**Proof of no regression (Luciano's explicit requirement):** the SHA-256 hash of `PINS.json` and of `pre_campaign_manifest.py`'s output taken BEFORE and AFTER item 3's changes -- identical in both cases (`PINS.json`: `3b025aa3...`; the manifest: `775c0948...`). The hygiene changes (Dockerfile, gitattributes, preflight, teardown) never touched a pinned certificate or image. The complete suite: 386/386 (383 before + 3 new).

No private key in any file. No push (a permanent rule: never `git push --all`/`--mirror`), no tag, no real campaign. Stage 2 not started.

## Decision 127 (Amendment, 2026-11-11, Stage 2 of the v9 pilot -- a real AWS run)

**A real finding during Stage 2:** when running `deliver_images.py` against the just-created real infrastructure, Decision 68's fail-closed correctly aborted: the gateway's/proxy's local tar_sha256 (`mockopin-v9-gateway:latest`/`mockopin-v9-proxy:latest`) no longer matched the one pinned in Decision 123. Root cause: at least one independent verification fork from this session (between Decision 123 and the start of Stage 2) rebuilt gateway/proxy inside an ISOLATED git worktree for testing -- but a Docker tag is a GLOBAL resource of the daemon, never isolated per worktree, and it was overwritten, invalidating the pin even before the pilot ran.

**No wrong image was delivered** -- the fail-closed worked exactly as designed (Decision 68), aborting before any scp.

**Investigation (extracting and hashing the binary from inside the fresh image, not just the .tar):** the Go BINARY inside the rebuilt image is BYTE FOR BYTE IDENTICAL to the `binary_sha256` pinned in Decision 123 (gateway `33f3871b...`, proxy `07c9fb03...`) -- reproducibility confirmed again, no code regression since the TLS 1.3 fix. Only the `tar_sha256`/`rootfs_layers[2]`/`image_id` changed, due to the ephemeral/random `COPY certs` layer (the same pattern already documented in Decision 123) -- a `make certs` ran between the two pinnings.

**Re-pinned** with the fresh values (new tar_sha256/rootfs_layers/image_id, binary_sha256 unchanged) for gateway and proxy in `PINS.json`.

**A process risk to fix before the official campaign:** verification forks/sessions that rebuild Docker images with the SAME tag the real delivery uses, even while working in an isolated git worktree, mutate the host's shared Docker daemon -- worktree isolation NEVER isolates the Docker daemon. Recommendation: any verification/test rebuild should use a distinct tag (e.g. `:verify`, `:test`), never overwriting the tag the real delivery uses (`:latest`).

## Decision 128 (Amendment, 2026-11-11, a local investigation after Stage 2 -- mockapi)

**Luciano's request:** investigate locally (without AWS) whether `raidiam-insurance-lambdas:latest` (mockapi) is in fact the pinned content, with the specific hypothesis that the 11/10 timestamp observed during Stage 2 was only `Metadata.LastTagTime` (a retag with no content change), not a real `Created`.

**Verdict: IT DOES NOT MATCH -- the LastTagTime hypothesis REFUTED by direct evidence.** `docker image inspect raidiam-insurance-lambdas:latest`:
- The pinned `Id`: `sha256:1c83ab8648...`. The current `Id`: `sha256:d6d38029ee73...` -- it diverges.
- The current `Created`: `2026-11-10T14:36:30.376063466Z`. `Metadata.LastTagTime`: `2026-11-10T14:36:30.632749333Z` -- both fall in the SAME second, and `docker history` confirms the last layer (`COPY dir:... in /home/app/`) with `CreatedAt=2026-11-10T11:36:25-03:00` (= 14:36:25 UTC) -- in other words, `Created` is genuine, reflecting a really new layer, NEVER a retag side effect. The previous layer (`COPY dir:... in /home/app/libs`, the dependencies) stays from `2026-08-28`, unchanged.
- `RootFS.Layers`: the first 8 of the 10 pinned layers match exactly; the pinned one has TWO final layers (`db1e575b...`, `abdb1509...`), the current one has a SINGLE, different final layer (`dc8c7c1e...`) -- a real content divergence in the layer that holds `/home/app/` (app code, not libs).
- `Config` (Entrypoint/Cmd/Env/ExposedPorts): IDENTICAL on both sides -- the divergence is only in the content layer, never in the image's configuration.
- The `sha256` of the `application.jar` INSIDE the current image: `3e60f0a2...`, which matches EXACTLY `insurance-server-lambdas/build/libs/raidiam-insurance-lambdas-0.0.2.null-optimized-runner.jar` (on disk, `Nov 10 11:36`) -- and DIFFERS from the old jar on disk, `raidiam-insurance-lambdas-0.0.2.null-runner.jar` (`25ae4c2e...`, `Sep 23 23:41`, the same date as the original 09/24 pin, the non-optimized variant).

**What touched the image on 11/10 (item 2):** the current jar's naming (`-optimized-runner.jar`) and the recreated final layer point to a real run of `./gradlew optimizedDockerBuild` (the real Micronaut build mechanism, already identified as the correct path, distinct from the disconnected `Dockerfile`) having actually completed during this session's jar-vendoring investigation (Decision 122) -- further than that report had characterized it ("inconclusive"). No historical `docker events` log is available to confirm the exact command; this is an inference from file evidence (coinciding timestamps and content), not command-audit certainty.

**Decision: NOT chosen between re-pinning or rebuilding (Luciano's explicit request) -- awaiting his decision.** Today's local image has an `application.jar` genuinely different from what was (plausibly) pinned on 09/24; without a hash of the original pinned jar (Decision 83 never recorded one), there is no way to prove the old jar on disk is exactly what is inside the pinned `.tar` -- only a strong circumstantial match (the same date, the same non-optimized variant).

**A new local preflight (item 5), closing the gap that let Stage 2 spend an entire real apply before discovering this:** `preflight.check_local_images_match_pins()`, now called inside `run_preflight()` -- it compares `RootFS.Layers` + a subset of `.Config` (NEVER the raw `image_id`, the same criterion already established in Decision 68: the Image ID diverges across Docker versions even with identical content) of EVERY pinned image present locally against `PINS.json`, failing with the exact list of what diverges. It runs BEFORE any `terraform apply` -- `deliver_images.py` (Decision 68) remains the last-line fail-closed, on the remote-delivery side, but now the problem is caught without spending a single minute of real infrastructure. A pinned image missing locally does NOT fail the check (it will be caught at the right time by `deliver_images`) -- this only detects a divergence in an image that EXISTS but has changed.

**An adopted convention (item 5):** any Docker-image verification/test rebuild in this session uses the `:verify` tag (never overwriting `:latest`) -- already recommended in Decision 127, formalized here.

## Decision 129 (Amendment, 2026-11-11, final validation and re-pinning mockapi)

**Luciano's request, conditionally authorized ("accept the new image IF proven"):** a complete soak of 50 real OAuth flows per profile (Classic, PQC, Hibrido dual=true, and the dual=false control if time allowed) against the new mockapi image, a request-by-request comparison against the old soak (300/profile, commit `93e57b2f`), a memory-plateau comparison, an explanation of the divergent bytecode found in Decision 128, and a re-pin conditional on all of this being OK.

**Item 1 (a complete soak, all 4 profiles included):** 200/200 real OAuth flows (`run_insurance_flow`, `V9_HARNESS=1`, the backend+gateway recreated together per profile), ZERO errors -- Classic 50/50, PQC 50/50, Hibrido dual=true 50/50, Hibrido dual=false (the control) 50/50 (the time budget allowed all 4, not just the 3 main ones). Continuous memory/fd sampling throughout the containers' real lifetime window (the same corrected methodology as the original soak).

**Item 2 (a request-by-request comparison):** `n_calls=20` constant across ALL 200 new flows, identical to the old soak's pattern (`n_calls=20` constant across `93e57b2f`'s 1200 flows). Zero structural divergence. Per-artifact signature size/type already confirmed identical in the earlier validation (a `/jwks`/`/health` differential test, 6/6 matching against Decision 126's persisted capture) -- not redone here because already proven, to avoid repeating work.

**Item 3 (mockapi's memory plateau):** Classic ~584MiB, PQC ~705MiB, Hibrido dual=true ~582MiB, Hibrido dual=false ~679MiB -- all EQUAL TO OR LOWER THAN the old reference (Classic/Hibrido ~637-678MiB, PQC ~782MiB), none showing continuous growth (all stable plateaus). It is plausible that the optimized build (Micronaut AOT) reduces runtime reflection/bean-context overhead -- not an anomaly, a favorable result.

**Item 4 (the divergent bytecode, `EnvironmentPropertiesOptimizationLoader.class`):** extracted the jar from the dangling image (`d6d38029...`, the same one from Decision 128's finding) and compared it via `javap -c -p` against the jar from this session's reproduced build. The only real difference is a name-variant mapping entry (dot/dash) Micronaut AOT generates for environment variables PRESENT ON THE BUILD HOST at the moment Gradle ran -- the `EFC_11068_4126798990` entry (the old build, 11/10) matches the `EFC_<PID>_<random suffix>` pattern of a sandbox variable from THIS tool's OWN execution session (confirmed: the current environment has `EFC_<current PID>_<same suffixes>` variables, including the same `4126798990` suffix) -- never a real application configuration, never referenced anywhere in the project's source code. **No behavioral effect:** that table is only a lookup optimization; a missing entry makes Micronaut fall back to the normal (non-optimized) property-resolution path, which always resolves correctly -- never a functional failure.

**Final verdict: PROVEN. Re-pin executed.** `PINS.json`, the `mockapi` entry: `rootfs_layers` (9 layers, the first 6 identical to the old 10-layer pin, the final 3 new), `tar_sha256` (`d624374b...`), `image_id` (`2fb10bb6...`, informational, never used as a verification criterion per Decision 68), `binary_path_in_image`/`binary_sha256` (`956e860d...`, the `application.jar` from inside the image) filled in for the first time. `binary_sha256_reproducible: false` -- the .jar FILE differs by the zip entries' timestamps across builds (confirmed: two build rounds in this session produced jars with a different file hash but IDENTICAL decompressed content, 2145 files, an empty diff) -- functional reproducibility guaranteed, byte-for-byte reproducibility of the `.jar` file NOT. `config_subset` unchanged (Entrypoint/Env/ExposedPorts identical to the old pin).

**Preflight (`preflight.check_local_images_match_pins()`) confirmed passing across the 7 pinned images present locally (gateway, proxy, measure, pqc-signer, auth, mongo_seed, mockapi) -- `mismatched: []`.** The gap that let Stage 2 spend an entire real infrastructure run before discovering mockapi's divergence (Decision 128) is now closed: any future divergence is caught BEFORE the apply.

## Decision 130 (Amendment, 2026-11-11/12, a real incident -- the control self-terminated mid-window)

**What happened:** during Stage 2 (the real AWS pilot), the infrastructure came up successfully across the 7 regions (78/78 resources, 12/12 instances). Midway through delivering images/preparing the first block, the control and the 5 resources depending on it (the sa-east-1 server + the 3 clients it routes: L123/ca-central-1, L219/eu-north-1, L325/ap-southeast-1) SELF-TERMINATED (they did not stop -- they really terminated, with the root EBS deleted because `DeleteOnTermination` was never set to false).

**Root cause:** `self_terminate_hours=4` (a decision from this very session, an "extra safety margin" for the pilot) was a FIXED deadline, counted from boot, independent of real activity -- combined with `instance_initiated_shutdown_behavior="terminate"`. The real preparation (delivering and verifying the backend image per server, ~690MB over a cross-region network + docker load + sha256 verification + `docker compose up` waiting on postgres/mongodb/localstack) measured, live, at ~55-65 minutes PER SERVER, in series -- for 3 servers that already consumes ~2-3h, hitting the 4h deadline before the real measurement window even started.

**Real confirmed loss:** the control + the sa-east-1 server + 3 dependent clients, 6 instances, the control's root EBS deleted (confirmed: zero orphan volumes, zero snapshots in sa-east-1). Surviving partial data (never officially counted) recovered from the 6 unaffected resources (us-east-1/ap-northeast-1 and their clients): real Classico-profile pcap captures across 4 of the 8 routes, continuous CPU/memory samples for the 4 profiles on those same routes -- discarded by the author's decision (the earlier window invalidated, nothing counted).

**Fix applied:**
1. `instance_initiated_shutdown_behavior` changed from `"terminate"` to `"stop"` across ALL 12 modules of `terraform_campanha_oficial/main.tf`, and applied via `aws ec2 modify-instance-attribute` to the 6 surviving resources (without recreating them).
2. The safety switch stopped being a fixed deadline and became a **renewable dead man's switch**: `SSHExecutor.renew_safety_timers()`/`_renew_local_safety_timer()` (new, `orchestrator.py`) send an "I'm alive" heartbeat to active hosts on every `start_block` and on every counted run, pushing `/etc/mockopin-campaign/deadline` to +3h (`SAFETY_TIMER_RENEW_HOURS`) -- it only triggers STOP (never terminate again) if the heartbeat stops arriving for a full 3h. The heartbeat runs INSIDE the `orchestrator.py` process the control runs via `nohup` -- never depending on an external call from whoever operates the session, so it survives any connection/session drop on the operator's side.
3. The 6 lost resources were recreated via an incremental Terraform apply (6 add, 14 change -- the survivors' shutdown behavior + EIP reassociation + 2 SG rules --, 0 destroy). All public IPs came back identical to before (real EIPs, never destroyed, only disassociated by the termination).
4. A related process finding, fixed in the same batch: STOPPED (not removed) containers from before the incident (`v9-mtls` on the servers, `pqc_signer_service_run`/`tls_kem_proxy_run` on one client) remained as a real leftover, caught by the preflight check (Decision 125) and cleaned up manually before relaunching.
5. An additional process finding: the adapted inventory delivered to the recreated control still had the sa-east-1 server's old PRIVATE IP (the EIP/public one is preserved on recreation, the private one is NOT) -- confirmed via the container's real log (`tls_kem_proxy_run` dialing the wrong private IP, "no route to host"). Fixed by regenerating the inventory from Terraform's real state after the recreation.
6. `cost_tracker.py`/`orchestrator.py` gained `--cost-window-start-utc`, allowing the cost clock to be rebuilt from an earlier REAL launch time (the original launch, 2026-11-11T22:11:25Z) instead of "now" -- conservative by design, counting the entire wall-clock interval including the real gap when 6 instances were terminated, never underestimating.

**An open pending item, not fixed in this Decision:** `deliver_source.py` does not have `campaign_topology.py` nor `cost_tracker.py` in the list of files delivered to the control, even though `orchestrator.py`/`preflight.py` depend on them -- worked around manually (a direct scp) twice in this same Decision; the definitive fix to the file list is left for this session's batch of process-fix commits.

## Decision 131 (2026-11-12, the official campaign's design -- authored by Luciano)

**The author's decision:** the official campaign abandons the design of 3 windows of 10 runs/cell (which in practice were stitched together with no real temporal separation) and becomes **ONE window of 10 runs/cell**, with median and dispersion as the statistic, keeping the 4 profiles measured together in the same campaign (the dual=false control stays reserved, out of the main reports). The author's literal reason: the 3 windows never had real temporal separation in practice, so formally splitting into 3 added nothing a single larger window would not give.

**Effect on estimates/reports:** the pilot calibration report now highlights variant V1 (10/cell, 1 window) as the current design; V2/V3 stay only as historical/comparative context. The marginal cost of an extra Classico block (3/cell) as a temporal-drift control, if the author decides to include it, is estimated separately, never decided by the session.

## Decision 132 (2026-11-12 04:03 UTC, the cost-stop ceiling raised -- the author's authorization)

**The author's decision:** the cost-stop ceiling (`--cost-stop-usd`) rises from **US$13 to US$20**. Literal reason: the US$13 ceiling was a safety lock (never an official real-cost number, see `cost_tracker.py`), and Decision 130's incident accounting (rebuilt from the original launch, 22:11:25Z, via `--cost-window-start-utc`) keeps counting the entire wall-clock time -- including the incident's gap -- which reduced the remaining headroom before any additional real run could be measured. The author explicitly kept the honest accounting (not resetting the clock) and asked for the higher ceiling instead.

**Applied:** the orchestrator process restarted with `--cost-stop-usd 20.0` at a moment when no counted run yet existed in this window (only warmups, which never count) -- zero real loss. The stop mechanism stays `stop`, never `terminate` (Decision 130). If the US$20 ceiling is reached, the in-progress cell is finished before stopping (already-existing behavior, `cost_stop_info`/`break` at the end of the counted-runs loop, never mid-run) and the matrix's exact point is recorded in the manifest, for future resumption.

**The author's explicit rule for the future:** if the completion forecast indicates US$20 is not enough, the session must warn BEFORE taking any action -- never extend the ceiling on its own again.

## Decision 133 (2026-11-12, a second real crash -- the dedicated-captures phase killed the process after the entire matrix had already finished in memory; the structural fix is redoing the complete pilot -- authored by Luciano)

**Incident:** the main 32-cell matrix finished entirely, in memory, with no failure at all. The process only persisted `manifest.json`/`piloto_calls.json`/etc at the END of `run_pilot()`, after a SEPARATE dedicated-captures phase that iterated profile-outer/route-inner (the opposite order from the main matrix, route-outer/profile-inner). That phase revisited routes/clients the main matrix had already finished hours earlier and whose dead-man's-switch heartbeat had already legitimately expired (safely stopped, never terminated -- Decision 130). The delivery call to an already-stopped host raised an unhandled exception, killing the entire process and discarding the whole 32-cell matrix, even though it was already 100% complete in memory.

**The author's decision (option a, with the additions below):** properly fix the code and redo the complete pilot from scratch, WITHOUT touching anything in the official campaign. Do not spend the whole matrix to test it -- validate the fix locally before running again on the real AWS. Raise the stop ceiling from US$20 to US$25. Record the decision and only commit once authorized. Suspend the conditional authorization for the official campaign's automatic start. A complete final report only at the conclusion.

**Implemented in `orchestrator.py`:**
- `_atomic_write_json(path, obj)`: an atomic write (a tempfile in the same directory + `os.replace`), never leaving a partially-written JSON.
- Each run/warmup now writes its own file to `out_dir/runs_raw/{profile}__{route}__run{NN}.json` (or `run00_warmupN.json`) IMMEDIATELY after being produced, before anything else.
- `_persist_incremental()` (a local closure): rewrites `piloto_calls.json`, `criterio6_execucoes.json`, `aquecimento_execucoes.json` and a new `manifest_partial.json` (with `complete: false` and the running totals) after EACH completed cell -- not only at the end.
- **The dedicated-captures phase was merged into the main loop, per route** (running right after that route's cells, in the same already-shuffled `order`, the client still "warm"/just renewed) -- eliminating the root cause (the revisit), not just mitigating it.
- Each individual dedicated capture runs in an isolated `try/except`: a failure goes into `capturas_dedicadas_falhas` (never bringing down the process); success goes into `capturas_dedicadas_feitas`.
- A new `SSHExecutor.renew_all_safety_timers()`, called once at the start of `run_pilot()` (before creating `out_dir`), renewing ALL hosts in the inventory -- preventing a host whose last heartbeat came from an earlier, now-irrelevant round from expiring before the new process reaches its route.
- At the end, `manifest.json` is also now written via `_atomic_write_json`, and `manifest_partial.json` is removed once the final manifest is successfully written.
- Two new tests in `test_orchestrator.py` validate the fix WITHOUT spending real runs: `test_persistencia_incremental_sobrevive_a_queda_no_meio_da_janela` (injects an exception on the 3rd run, confirming 2 `runs_raw/*.json` files and 2 entries in `piloto_calls.json` survive, even without a final `manifest.json`) and `test_captura_dedicada_falha_isolada_nunca_derruba_o_processo` (injects a failure on a specific capture, confirming the process finishes normally with the isolated failure recorded). 395 tests passing (393 + 2 new) before any new real attempt on AWS.

**Applied:** the cost-stop ceiling raised from US$20 to US$25 (`--cost-stop-usd 25.0`), explicitly authorized by the author during the incident recovery. The pilot redone from scratch with the fixed code, started once the local tests passed.

**Result:** the redone pilot completed **64/64 counted runs, 160/160 warmups, 32/32 dedicated captures, zero failures** (`capturas_dedicadas_falhas: []`, `cost_stop: null`), a final cost of US$20,71 (within the US$25 ceiling).

## Decision 134 (2026-11-12, organizing the redone pilot's results -- authored by Luciano)

**The author's request:** organize the redone pilot's results in the EXACT layout that will be used in the official campaign, to validate the organization and the consolidated report before the GO -- `artifacts/`, `size/` and `latency/`, each with `experiment1 - Classic`/`experiment2 - PQC`/`experiment3 - Hybrid`/`experiment4 - Control` (the control outside the consolidated report), one folder per route, `runs/runNN.json` (latency also `run00_warmup.json`), plus derived `median_metrics.json`/`MEDIAN_REPORT.md`. Consolidated at the root: `CONSOLIDATED_REPORT.md`, `report_data_v9.json`, `audit_recompute_from_raw.txt`, `DECISIONS.md`.

**Implemented:** `thesis/scripts/organize_v9_results.py` -- reads the raw data (`piloto_calls.json`/`criterio6_execucoes.json`/`aquecimento_execucoes.json`/`manifest.json`/`criterio1_capturas/`) ONLY BY COPYING/DERIVING, never moving nor altering the source. Parameterizable (`--expected-runs-per-cell`, 2 in the pilot, 10 in the official campaign -- failing loudly if the number found diverges), rerunnable (idempotent -- overwriting the destination, never the source). The same command serves the official campaign's closeout, just by swapping `--expected-runs-per-cell 10` and the source/destination paths.

**Result in the redone pilot:** `thesis/results/v9_pilot/`, 0 divergences in `audit_recompute_from_raw.txt`, the 4 automatic criteria reported (never decided by this script) all OK: a constant call count across profiles (704 each), the total run count matches (64/64), dedicated captures with no failure (32/32), dual TLS asserted with no divergence (0/64).

**A real divergence found against v8 (item 5 of the request, only reported, not decided):** `thesis/results/v8/janela1/` (and janela2/3) organizes by SERVER REGION first, route AFTER (`experiment1 - Classic/sa-east-1/L123/`, 2 levels), never separates `size`/`latency` at the top (everything inside `experimentN` itself), and keeps pcap.gz+cpu.jsonl per run inside `client/`/`server/`, never a consolidated `runNN.json`. The layout now requested for v9 (flat by route, with no region level, `size`/`latency` separated at the top, `runNN.json` as the primary data) is deliberately simpler and does not match v8's pattern. **Proposal:** keep the new layout as specified (the author's decision, not the session's) -- v8 is already frozen and never needs retroactive reorganization; v9 can adopt its own layout without breaking anything in v8, as long as the divergence is documented here (done).
