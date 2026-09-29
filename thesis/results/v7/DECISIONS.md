# Decisions — v7 (final consolidated round)

## 1. Unification of the 3 profiles under the same Go client/proxy — permanently eliminating the Python-vs-Go confounding variable that dominated the Level 1 (v6) investigation

**Context.** v5 measured Classic, PQC, and Hybrid with the direct Python
client, with no post-quantum key exchange at all (classic ECDHE in all
three profiles). Level 1 (`thesis/results/v6/Level 1/`) migrated the key
exchange for PQC and Hybrid to ML-KEM, but only for those two profiles —
and it was only possible because Python/OpenSSL cannot negotiate ML-KEM
groups, requiring a bridge (`tls_kem_proxy`, Go client) just for PQC/Hybrid,
while Classic stayed on the direct Python path.

This split (Classic in Python, PQC/Hybrid in Go via proxy) introduced
exactly the kind of confounding variable this project tries to eliminate in
every experiment: any difference between Classic and the other two profiles
now carried, embedded within it, a TLS-client implementation effect, not
just the effect of the cryptography itself. The complete history of this
investigation is in `thesis/results/v6/Level 1/DECISIONS.md`:

- **Decision 2**: `handshake_bytes` came out *smaller* with ML-KEM than the
  classic v5 number — the opposite of what was expected. Cause: comparing
  Python/OpenSSL (v5) against Go (v6) does not isolate the ML-KEM effect,
  it is a comparison of different TLS clients. An auxiliary "Go-classic"
  baseline was needed just to have a same-client reference.
- **Decision 3**: a DNS-resolution artifact (`"localhost"` vs
  `"127.0.0.1"`) specific to the proxy process inflated `T_fluxo` by
  ~10-12s, initially misattributed to "proxy architecture overhead."
- **Decision 6**: even after the artifact above was fixed, v6 (with the
  proxy) consistently appeared *faster* than v5 (direct Python) in
  high-latency scenarios — traced to a round-trip efficiency difference
  between the Go and Python TLS clients, confirmed only with a dedicated
  controlled test.
- **Decision 7**: an attempt to close that residual led to an incorrect
  causal attribution (confused with an internal auth→RS call that is
  actually already filtered out by certificate before any official
  statistic) — corrected after a direct audit of the already-committed
  data.

Each of these decisions existed only because **two different TLS clients
(Python and Go) were being compared against each other**, on top of the
cryptography itself. None of them would have been necessary if all profiles
had used the same client from the start.

**Decision.** Starting with v7, **all three profiles — Classic, PQC, and
Hybrid — run through the same `tls_kem_proxy`, varying only the key
exchange group**:

| Profile | Key exchange group | Curve in `tls_kem_proxy` |
|---|---|---|
| Classic | Classic ECDHE (P-521/P-384/P-256) | `-curve classic` |
| PQC | `MLKEM1024` | `-curve mlkem1024` |
| Hybrid | `X25519MLKEM768` | `-curve x25519mlkem768` |

Classic never needed any SNI trick (the carve-out from v6's Decision 1,
`matls-api.local` → classic curves): `CRYPTO_PROFILE=classic` itself already
leaves `mock_mtls`'s `serverCurvePreferences` at its default value, which
already is that same classic list (`mock-service-os/mock_mtls/main.go`, a
package-level variable not touched by `init()` for the `classic` case). All
that was needed was to add the `"classic"` value to `tls_kem_proxy`'s curve
`switch` (`thesis/scripts/tls_kem_proxy/main.go`) — without forcing SNI,
unlike the pre-existing `"classical"` value (which forces
`matls-api.local` and continues to exist only for possible diagnostic
reruns of v6's now-obsolete "Go-classic" baseline).

**Practical consequence**: with all three profiles on the same client,
**v6's auxiliary "Go-classic" baseline is no longer needed** — there is no
longer any client-implementation effect to isolate, so any difference
between profiles in v7 is, by construction, purely the effect of the
cryptography (signing + key exchange) being measured. This simplifies v7 to
3 profiles × 6 scenarios × 10 runs (size and latency, separately) — without
the fourth "baseline" series that Level 1 required.

**Code changes.**
- `thesis/scripts/tls_kem_proxy/main.go`: new `"classic"` value in the
  curve `switch` (in `runRelay`), classic `CurvePreferences` without
  forcing SNI — distinct from the pre-existing `"classical"`.
- `thesis/scripts/opin_flow.py`: `_USE_TLS_KEM_PROXY` now includes
  `"classic"`; `TLS_KEM_PROXY_CURVE_BY_PROFILE` gains the entry
  `"classic": "classic"`. `AUTH_CONNECT_HOST`/`API_CONNECT_HOST`/
  `DIRECTORY_CONNECT_HOST` now point to the proxy for Classic as well
  (previously they went directly to the gateway).
- `thesis/scripts/switch_crypto_profile.py`: removed the exception that
  skipped the proxy for `"classic"`.
- `thesis/scripts/median_automation.py`/`latency_automation.py`: no logic
  change needed — they already called `start_tls_kem_proxy()`
  unconditionally, relying on the function's own `None` return for
  unrecognized profiles; `"classic"` is now recognized.

**What this does not change**: each profile's signing scheme remains
exactly the same as v5/v4 (pure RSA in Classic, pure ML-DSA-65 in PQC,
RSA+ML-DSA-65 in Hybrid, payload-extension for client JWTs) — only the TLS
key-exchange layer and the client executing it changed. See Decision 2 for
the full scope (merging Level 1 + Level 2 into a single measurement batch).

## 2. Scope: Level 1 (key exchange) and Level 2 (signing) measured together, no longer in separate batches

**Decision.** Each profile now runs at once with its final signing
architecture (identical to v5/v4) *and* its corresponding key exchange
(identical to v6's Level 1, now also for Classic, which was already
correct). There is no longer a "signing-only" v5 and a "key-exchange-only"
v6 as separate rounds — v7 is the single, final picture of both levels
together, superseding both.

## 3. Collection protocol — same rigor already validated in v5 and Level 1 (v6)

- 6 latency scenarios (0/14/30/140/225/320ms) × 10 runs × 3 profiles, for
  size and for latency, in this order (full size batch, sanity check,
  approval; then latency).
- `runs/run01..10.json` (plus `run00_warmup.json` for latency) as the
  primary source; `median_metrics.json`/`report.md` (or
  `MEDIAN_REPORT.md`) as the derived artifact — same convention as v5.
- Monotonic clock for `T_fluxo`, no outlier removal, retries counted only
  from the successful attempt onward, settling time after every
  `CRYPTO_PROFILE` switch (`switch_crypto_profile.py`, v6 Decision 4/5),
  anomaly checkpoints before accepting any scenario as closed.
- Structure: `thesis/results/v7/size/experiment{1,2,3} -
  {Classic,PQC,Hybrid}/{scenario}ms/` and `.../latency/...`, mirroring v5.
- `thesis/results/v7/artifacts/`: a non-statistical capture (1 sample, not
  10) per profile of the real cryptographic artifacts in use —
  certificate, decoded real JWT, real JWKS entry, evidence of the key
  exchange group negotiated during the handshake. Details and schedule in
  the corresponding phase; does not block the size/latency batch.

## 4. Classic's `total_bytes_exchanged` rises by +376 bytes in v7 relative to v5 — main cause confirmed, small residual left unresolved

**Context.** During the sanity check of the size stage, v7's Classic
showed `total_bytes_exchanged` = 66,828 against v5's 66,452 (+376 bytes),
even though `handshake_bytes` had dropped by 4,666 bytes (9,785 → 5,119)
in the same profile -- explicitly asked whether the total includes the
handshake (it does not) and, if not, where the +376 comes from.

**Confirmed, not assumed.** `total_bytes_exchanged` (`baseline_automation.
py:643-644,706`) is `sum(req_bytes + resp_bytes for c in all_calls)` --
application-layer traffic (HTTP headers + body) measured client-side, which
never touches `gateway_metrics`/`handshake_bytes`. The two metrics are
independent by design; there is no reason for them to move together.

**Main cause, confirmed via `git log -S` and live measurement.** All the
`host_header=` logic in `opin_flow.py` (the parameter in `do_call()` and
`simulate_login()`'s `session.headers["Host"] = AUTH_HOST`) was introduced
in commit `e88e373` -- the same commit from Level 1 (v6) that created
`tls_kem_proxy`. This makes sense: the proxy tunnels raw bytes, it does not
route by Host, so the client needs to declare the Host explicitly for HTTP
routing to keep working through it -- necessary all along for PQC/Hybrid
(v6), and now, with v7's unification (Decision 1), also for Classic, which
never needed this while connecting directly to the gateway. Measured live
(instrumenting `header_bytes()` across a full Classic flow, 28 calls): the
`Host:` headers add up to exactly **520 bytes**, none of which existed
before that commit -- confirmed via `git log -S` that none of those lines
predate Level 1.

**Residual left unresolved, reported with this precision.** 520 bytes of
new `Host:` headers exceeds the 376 observed -- leaving **~144 bytes
(≈5 bytes/call)** that would need to have dropped elsewhere to compensate
exactly. A `requests` version difference was ruled out (2.34.2 pinned in
`requirements.txt`, same venv all along in this project). Not investigated
further -- **explicit user decision**: the residual is ~0.2% of Classic's
total traffic, too small to compromise any conclusion of the thesis,
categorically different from Level 1's latency gap (v6 Decision 6/7), which
was a large fraction of a number underpinning a central finding. Recorded
as confirmed-on-the-main-cause, unresolved-on-the-residual, without
rounding up to 100% or reopening an investigation the user themself judged
unnecessary.

## 5. PQC/Hybrid reproducibility broken on this machine by an external environment change — fixed by removing a local certificate presentation that never had any real effect

**Context.** While building `thesis/results/v7/artifacts/pqc/`, a
standalone capture script (`thesis/scripts/_capture_pqc_artifacts.py`)
failed to run the real PQC flow: `ssl.SSLError: [SSL: EE_KEY_TOO_SMALL]`,
when trying to load `client_one_pqc.crt/.key` for the local HTTPS
connection (`127.0.0.1:8443`, the `tls_kem_proxy` listener). The initial
hypothesis -- that this was specific to the diagnostic script -- was
tested directly at the user's request, and refuted: `median_automation.
run_once("pqc", 0)`, calling `opin_flow.run_insurance_flow()`/
`run_person_flow()` **with no modification whatsoever** (the exact code
path that produced v7's PQC size/latency batch, committed on 2026-09-12),
failed on this machine now with the same error, at the same call
(`do_call()` → `session.request(cert=cert, ...)` → `urllib3` →
`ssl.SSLContext.load_cert_chain()`).

**Root cause, confirmed.** `do_call()` receives `cert` from
`get_client_cert_paths(crypto_profile)`, computed once at the top of
`run_insurance_flow()`/`run_person_flow()` and used, without distinction,
both for the real leg (Go→gateway, inside `tls_kem_proxy`, started by
`start_tls_kem_proxy()`) and for the local leg (Python→`tls_kem_proxy`, via
`requests`). The local leg **never needed any certificate at all**:
`tls_kem_proxy`'s local listener (`thesis/scripts/tls_kem_proxy/main.go`,
`generateLocalListenerCert()`) builds its `tls.Config` without setting
`ClientAuth` -- Go's default is `tls.NoClientCert`, confirmed by reading the
code, not assumed -- so any certificate Python presented there was always
discarded without verification. This never caused a problem for
Classic/Hybrid because `client_one.crt`/`client_one_hybrid.key` are
ordinary RSA keys, which OpenSSL has always been able to load regardless of
whether they were actually needed. For PQC, `client_one_pqc.key` is a
native ML-DSA-65 key (PKCS8) that this host's default OpenSSL 3.0 cannot
parse -- tested in isolation, with no network activity involved
(`ssl.SSLContext.load_cert_chain()` alone already fails with the same
error).

**Why this broke now and not on 2026-09-12.** The `client_one_pqc.crt`/`.key`
files in the repository did not change (confirmed via `git status` and
timestamps -- Aug 8/Aug 22, well before v7). The same code, with no edits,
produced a batch of 180 successful PQC runs a day ago and fails now. The
most likely cause is an external OpenSSL/Windows update between the two
dates, outside this project's control -- not determined with more precision
than that (not investigated beyond what was needed to confirm this is not a
problem with this code or with the committed certificates).

**Fix applied.** New function `get_local_leg_cert_paths()` in
`opin_flow.py`, used only in the two `cert` assignments inside
`run_insurance_flow()`/`run_person_flow()` (not in
`start_tls_kem_proxy()`, which still uses the real
`get_client_cert_paths()` for the leg that matters): for `pqc`/`hybrid`, it
returns `None` -- no certificate is presented on the local leg anymore, for
either profile. `classic` was not changed (it was never broken, and the
scope of this fix is the two affected profiles).

**Why the fix is safe.** It removes something purely cosmetic: a
certificate presentation that the local listener never inspected, never
used to decide anything, and whose absence changes nothing about which
identity reaches the real gateway -- that continues to be defined entirely
by the Go→gateway connection inside `tls_kem_proxy`, established with the
real certificate (`get_client_cert_paths()`, unchanged) before any HTTP
call happens. It does not alter `client_cert_der_bytes()` (which reads the
file from disk directly, never touched this leg), does not alter any
handshake/byte metric already collected (all of them come from
`mock_mtls`'s `countingConn`/gateway log, on the real-connection side,
never the Python↔proxy side), and does not change the behavior of any
profile that already worked (`classic` untouched; `hybrid` merely stops
doing something that never had any effect).

**Scope of the fix -- does not invalidate or require redoing anything
already committed.** v7's PQC/Hybrid size/latency batch (2026-09-12) was
already successfully collected on this same machine, before the external
environment change that broke reproducibility -- that data remains valid
and was not re-collected. This fix exists solely so that a future new PQC
collection on this machine (for example, to reproduce the thesis results
for a defense or audit) will work again. Confirmed live, after the fix:
`median_automation.run_once("pqc", 0)` -- the same official code, now
without the cosmetic presentation -- completed a real 28-call PQC flow
successfully.

**Separate note, not investigated, out of scope**: `git status` also showed
`thesis/results/v6/Level 1/size/experiment2 - PQC/320ms/` with
`median_metrics.json`/3 `runs/*.json` files modified since 2026-09-11
(before any work in this v7 session), reducing `run_count` from 10 to 3 in
that scenario. Not investigated or fixed -- explicit user decision: v6
ceases to be an official source once v7 is consolidated (the same
historical status as v1-v4), not worth the time to investigate data that
will already be discontinued.

## 6. Reconfirmation of the SNI exception (`GetConfigForClient`): 1:1 correspondence -- no security flaw, policy and documentation corrected

**Context.** During SAD coverage verification, a `curveID` count in the
gateway log under `CRYPTO_PROFILE=hybrid` showed `CurveP256` handshakes
coexisting with `X25519MLKEM768`, even though the code states the profile's
group list has no classic fallback ("must fail visibly, not silently
downgrade"). Investigated as a possible real security flaw before drawing
any conclusion.

**Direct evidence.** `GetConfigForClient` (`mock_mtls/main.go`) already
contained the SNI exception inherited from Level 1's (v6) Decision 1:
`hello.ServerName == "matls-api.local"` returns a configuration with
classic `CurvePreferences`. Instrumented with a permanent log (`sni`,
`remoteAddr`) and cross-checked, connection by connection, against the
`mTLS handshake complete` lines: **35 applications of the exception, 35
`CurveP256` handshakes (filtering by `"msg":"mTLS handshake complete"`,
without counting the `access log` lines that repeat the field), same
`remoteAddr` values, no unexplained classic handshake.** Every source
address was the `auth` container, the request `Host` was
`matls-api.local`, and the path was the consent lookup
(`InsurerAdapter.getConsent()`). An initial reading of 70 handshakes was a
counting error: `curveID` also appears in the `access log` lines, which
duplicate the field.

**Conclusion.** This is the deliberate, already-documented mechanism
(extending v5's Decision 5 to the key exchange), not a flaw. The code's
comment was incomplete, not wrong in intent.

**Corrections.** (1) The `serverCurvePreferences` comment now states the
SNI exception and the 1:1 evidence. (2) Section 4 of the `artifacts/pqc/`
and `artifacts/hybrid/` READMEs no longer states "no classic component" in
absolute terms and now qualifies it: this holds for external
client↔gateway traffic; the internal `auth`→RS connection remains classic
by design. (3) Permanent logging in `GetConfigForClient` so the mechanism
is auditable.

**Why this changes no data.** The internal connection was already excluded
from all metrics (`compute_metrics()` filters by `clientCertBytes`; v6
Decision 7).

## 7. OPINsize equation extended with a PKI/CRL term

**Decision.** The flow's size equation now has four terms: `OPINsize =
N_mTLS × handshake_bytes + N_JWT × JWT_size + N_JWK × JWK_PK_size + N_PKI ×
PKI_bytes`. The new term covers the CA certificates (`root-ca.pem`,
`issuer-ca.pem`) that the flow downloads over HTTP and that were already
being measured (the "PKI/CRL" participant), but never entered the sum --
v5's own final table noted that "the equation has no PKI/CRL term." With
N_PKI = 0 the equation reduces to the original one.

**Definitions.** N_PKI = 4 (2 fetches of each certificate: one per
sub-flow; read from `latency_per_endpoint`, identical across all three
profiles). `PKI_bytes` = average size of the two certificates served, in
PEM (the format transmitted on the wire), so that N_PKI × PKI_bytes is the
exact sum of the 4 transfers. PEM was chosen over the measured HTTP
response volume because the other terms (JWT, JWK) are sizes of
cryptographic material without HTTP headers; PEM is the equivalent for
certificates.

**Validation without new measurement.** The sizes come from the served
files (`mock-service-os/certs/`; the gateway serves the PEM files
unmodified). Cross-checked against the already-measured HTTP response
volume: measured − body = 412 bytes in all three profiles (4 responses ×
103 bytes of framing, an identical, whole-number value across all of them),
which is only possible if the served body is the file actually used.
Sensitivity analysis (DER instead of PEM; measured HTTP volume instead of
PEM) is in `ARCHITECTURE.md`, Section 7.6.

**Impact** (full values in `CONSOLIDATED_REPORT.md`, Section 3.2): Classic
67,247 → 75,687 (+12.55%); PQC 245,463 → 261,663 (+6.60%); Hybrid 302,999 →
340,355 (+12.33%). Hybrid's PKI term (37,356 bytes) is 8.5× the JWK term
the original equation already summed. Also: N_JWT × JWT_size is now
computed as the exact sum of the 26 token lengths (v5's convention used the
average rounded to 2 decimal places, which differs by less than 0.1 byte).

**Stated limitation.** N_PKI and N_JWK are properties of the flow as
implemented (no caching in the test client), not protocol constants.

**Tools.** `thesis/scripts/compute_v7_report_data.py` (derives the numbers
from the raw `runs/`) and `thesis/results/v7/report_data_v7.json`.

## 8. Per-participant decomposition: what v7's raw data does and does not allow

**Finding.** `compute_metrics()` (`baseline_automation.py`) assigns each
call to a participant based on the URL's host (`classify_participant`,
`PARTICIPANT_HOSTS`). In v7, every call from all three profiles goes
through the local proxy (`127.0.0.1:8443`, Decision 1), so no AS/RS/
Directory host is recognized and AS and RS collapse into a single "Other"
participant (only the CA certificates escape this, since they are
classified by path suffix). Confirmed across the 180 size files: the set of
participants is always `{Client, Other, PKI/CRL}`. In v5, Classic and
PQC/Hybrid connected directly and kept AS and RS separate; that resolution
was lost with the unification.

**Additionally**, the gateway counts bytes read and written per connection
separately (`countingConn`), but only records the sum (`mtlsHandshakeBytes`),
so handshake bytes have no direction in the existing data.

**Decision.** Record both gaps as limitations (`CONSOLIDATED_REPORT.md`,
Section 3.3), without fixing or re-collecting in this consolidation
(explicit instruction: no re-measurement). What is available: Client ×
aggregated servers × Directory/PKI-CRL, sent × received, at the
application layer. Obtaining AS separate from RS would require classifying
by the `Host` header (the `host_header` parameter already exists in
`do_call()`) and one instrumented run per profile (the sizes are
deterministic: 0% spread across 180 runs); obtaining the handshake's
direction would require adding `bytesRead`/`bytesWritten` to the gateway's
log line and one run per profile. Pending the author's decision.

## 9. Consolidation: independent audit and correction of a normative reference

- **Audit.** All size and latency metrics were recomputed from the raw
  `runs/` (`thesis/scripts/audit_v7_from_raw.py`, output in
  `audit_recompute_from_raw.txt`): 36 scenarios/profiles, 0 real
  discrepancies. The one alert was a display-rounding artifact at the
  sixth decimal place in the Hybrid/30ms report (the median of two 6-digit
  values falls on the seventh digit).
- **Reference corrected.** The PQC artifacts cited "RFC 9880" for the pure
  `MLKEM1024` group; the reference did not hold up under verification: the
  group is defined in the Internet-Draft `draft-ietf-tls-mlkem` (IETF TLS
  WG), not yet published as an RFC. Corrected in `artifacts/pqc/README.md`
  and `verify_kem_export_output.txt`.

## 10. Closing Decision 8: AS/RS decomposition via a one-off deterministic capture -- not a new statistical sample

**Context.** Decision 8 recorded that `bytes_by_participant` collapses AS
and RS into a single "Other" participant, because `classify_participant()`
classifies by the URL actually called, and in v7 that URL is always
`127.0.0.1:8443` (the proxy). Explicitly asked whether this gap could be
closed by reprocessing already-existing data, without repeating any of the
180 official runs.

**Exhaustive verification, before any new capture.** Two sources of
information already existed, neither sufficient on its own:

1. **`do_call()` (`opin_flow.py`)**: each call carries `endpoint` (the
   URL's path, immune to the proxy's rewriting -- only the host changes)
   and the request/response bytes, but `compute_metrics()` consumes this
   in-memory list and writes out only the aggregates
   (`bytes_by_participant`, with no endpoint identity;
   `latency_per_endpoint`, with endpoint identity but no bytes). Confirmed
   by recursively scanning an entire `run01_baseline_metrics.json` for any
   structure combining `endpoint` and bytes: none exists.
2. **Gateway access log** (`collect_gateway_metrics()`): has the real
   `host` (it survives the proxy's raw tunnel) and the path, but only
   records bytes at the handshake level, never per application request.

**Confirmed conclusion, not assumed**: the 180 raw files already written do
not contain enough data for this separation through pure reprocessing --
the information existed in memory during collection and was discarded
before ever touching disk.

**A one-off capture authorized -- 3 runs, not 180, same category as
`artifacts/`.** `thesis/scripts/capture_participant_decomposition.py`
runs one full flow per profile, with `do_call()` instrumented to record
`host_header` (the value `opin_flow.py` already uses to route each call --
`AUTH_HOST`/`AUTH_MTLS_HOST_HEADER` for the AS, `API_HOST` for the RS,
`DIRECTORY_HOST` for PKI/CRL -- never seen by the proxy, which only
shuffles the physical address) alongside each call's bytes.

**Why one run per profile is sufficient -- and why this is not a new
statistical sample.** This v7's own sanity check (Section 7 of
`CONSOLIDATED_REPORT.md`) already proved 0.00% spread on every size metric,
across each profile's 60 runs (6 scenarios × 10). This means the flow's 28
calls always produce exactly the same bytes, in the same order, for the
same endpoint -- not a random variable with a mean, but a constant of the
implemented flow. The one-off capture does not measure a new sample of that
constant; it **reveals a decomposition of a value already known in
aggregate**. That is why this capture does not appear under
`thesis/results/v7/size/`, has no `runs/run01..10`, and should not be
confused with a re-measurement: it is reprocessing, materialized through a
single run, because the missing information (each call's logical
destination) does not exist in any file already written, but the value it
reveals was already implicit in the 180 files.

**Validation -- exact reconciliation with the already-committed data,
across all three profiles:**

| Profile | AS (sent/received) | RS (sent/received) | AS+RS sent | AS+RS received | Already-committed "Other" (sent/received) |
|---|---|---|---|---|---|
| Classic | 14,188 / 11,911 | 26,034 / 5,111 | 40,222 | 17,022 | 40,222 / 17,022 |
| PQC | 29,570 / 41,736 | 91,252 / 5,111 | 120,822 | 46,847 | 120,822 / 46,847 |
| Hybrid | 31,058 / 59,411 | 121,196 / 5,111 | 152,254 | 64,522 | 152,254 / 64,522 |

Identical, byte for byte, across all three profiles -- and the capture's
PKI/CRL figures (`sent_bytes`/`received_bytes`) also match the
already-committed values exactly in all three cases.
`thesis/scripts/compute_v7_report_data.py` refuses to run (assert) if any
of these equalities fails.

**A real environment issue found along the way, fixed before accepting the
capture.** The first attempt (Classic) produced PKI/CRL
`received_bytes = 772`, not the already-committed 732 -- a real
discrepancy, investigated before being accepted. Cause: the script ran
with the host's global Python (`requests==2.32.3`), not the project's
`.venv` (`thesis/scripts/.venv`, `requests==2.34.2`, the version already
pinned in `requirements.txt` and used by the official collection).
Different `requests`/`urllib3` versions produce HTTP headers of slightly
different sizes. Redone with `thesis/scripts/.venv/Scripts/python.exe`, the
number matched exactly. Same category of finding as Decision 5
(environment drift outside this project's control) -- recorded here so a
future capture does not repeat the same mistake.

**Also discovered, at no additional cost**: between this session's pause
and its resumption, the `psql` container (a dependency of the RS) had gone
down (stopped for 7 days) and the RS (`mockapi`) was exiting with a
connection error -- restarted before any capture; no data depended on this.

**Result**: `thesis/results/v7/participant_decomposition_capture_{classic,pqc,hybrid}.json`
(the raw capture, 28 lines per profile) and a new field in
`report_data_v7.json`, `participants_decomposed` (AS, RS, PKI/CRL, Client).
`CONSOLIDATED_REPORT.md` (Section 3.3) and `ARCHITECTURE.md` (Section 8)
updated with the decomposed table; the limitation recorded in Decision 8 is
now closed for the AS/RS part -- decomposing the handshake by direction
remains open, with no equivalent solution available in the existing data.

---

## 11. A real signed artifact (JARM) missing from N_JWT and from every byte total -- found via external review, fixed at the source, corrected analytically in the existing dataset

**Context.** An independent technical review of the consolidated report raised two questions this project could not answer from the published numbers alone: (1) why the login/consent interaction, on a flow the report describes as 28 HTTP requests over 6 reused connections, implies far more round trips than that when back-calculated from the measured latency deltas; (2) whether the reported byte totals reflect the flow's true application-layer traffic. Investigated directly against the code, not just the numbers, both led to the same root cause.

**Root cause, confirmed live.** `simulate_login()` (the code that drives the automated login/consent interaction, standing in for a browser) makes its own real HTTP requests with `allow_redirects=True`, entirely outside `do_call()` -- the function every other tracked call in this project goes through. Instrumenting a live run and counting every request `requests` actually makes (including every redirect hop, via response hooks) found **at least 40 real HTTP requests per flow, not 28** -- and at least 75,943 bytes of real traffic (headers + body, measured with the exact same formula `do_call()` uses) that never entered `total_bytes_exchanged` or `bytes_by_participant`, confirmed identical across all three profiles for the login/consent HTML pages themselves (they don't depend on the crypto scheme).

**But one of those untracked responses is not profile-independent.** The final "resume" redirect of the `POST /confirm` chain -- the one immediately before the local callback server -- carries a real, signed **JARM (FAPI Advanced authorization response)** token in the `Location` header's `response=` query parameter, one per sub-flow (2 per complete flow). `extract_jwts()` (`baseline_automation.py`) only ever scanned request/response bodies and the `Authorization` header -- never `Location` -- so this JWT was invisible to it even on calls that *do* go through `do_call()`; combined with `simulate_login()` never calling `do_call()` at all, the JARM was doubly unreachable. Measured live, once per profile (deterministic -- JARM content depends only on the fixed claims and the profile's own signing scheme, the same reason every other size metric in this dataset already shows 0.00% spread), each verified by decoding the token's own `alg` header field:

| Profile | JARM size (bytes) | `alg` |
|---|---:|---|
| Classic | 621 | `PS256` |
| PQC | 4,696 | `ML-DSA-65` |
| Hybrid | 5,061 | `MLDSA65-RSA2048-PSS-SHA256` (Strong Nesting) |

This is exactly the artifact `ARCHITECTURE.md`'s own primitive table already names as migrated ("`id_token` and JARM from the AS," Strong Nesting for Hybrid) -- the report's own narrative already claimed this token exists and is migrated; it was just never actually counted.

**Fixed at the source.** `simulate_login()` now takes a `jarm_calls` list and captures this response via a `hooks={"response": [...]}` callback on the `/confirm` POST, building a call-shaped dict with the same `header_bytes()`/body-length formula `do_call()` itself uses, classified and byte-counted identically to any other tracked call. `wait_for_authorization_code()` threads this through per login attempt, only keeping a successful attempt's capture (a discarded/retried attempt's JARM, like its bytes and time, is thrown away with it) -- `create_and_authorize_consent()` passes its own `calls` list straight through. Verified end-to-end through the unmodified official pipeline (`opin_flow.py`, not a scratch script), fresh single runs, all three profiles: `jwt_count` is now 28 (was 26), `total_requests` is now 30 (28 tracked API calls + the 2 JARM captures), and the new `jwt_sizes_bytes` list visibly includes two values matching each profile's measured JARM size exactly.

**Correction applied to the already-collected v7 dataset, without re-collecting.** The 180 already-committed raw run files predate this fix and have no field to retroactively recover the JARM from -- there is no raw-file-level correction possible. Because the missing quantity is deterministic (confirmed 0% spread on every other size metric already in this dataset, and the JARM's own live measurement was taken from three fresh, isolated single runs, one per profile), a full statistical re-collection is not needed either: `thesis/scripts/apply_jarm_correction.py` adds `N_JWT_correction = 2` and each profile's measured JARM size directly into `report_data_v7.json`'s existing `size`/`opinsize` fields, alongside (not replacing) the original numbers, so the correction's provenance stays traceable.

| | OPINsize (as published) | OPINsize (JARM-corrected) | Δ |
|---|---:|---:|---:|
| Classic | 75,687 | 76,929 | +1,242 (+1.64%) |
| PQC | 261,663 | 271,055 | +9,392 (+3.59%) |
| Hybrid | 340,355 | 350,477 | +10,122 (+2.97%) |

Corrected ratios: PQC/Classic 3.52× (was 3.46×); Hybrid/Classic 4.56× (was 4.50×); Hybrid/PQC 1.29× (was 1.30×, essentially unchanged, since PQC's and Hybrid's JARM sizes are close to each other). `CONSOLIDATED_REPORT.md`/`Consolidated_Metrics_Report_FINAL.md` updated to the corrected numbers as the reported ones, with this decision cited as the source of the correction.

**What remained open here, closed in Decision 12.** The untracked-bytes finding also meant `total_bytes_exchanged` and `bytes_by_participant` (Section 2 of the consolidated report) undercounted the flow's true total by the login/consent HTML traffic -- OPINsize itself was unaffected (none of its four terms are derived from those two fields), but a reader citing "total bytes exchanged" as the flow's full application-layer traffic should not have taken that number as complete. Decision 12 closes this. Separately, the same untracked-request investigation confirmed the round-trip count was undercounted (≥40 real requests, not 28) but did not fully close the gap the external review calculated from latency deltas at higher network-delay scenarios -- the remainder is plausibly connection-establishment RTT overhead (new TCP/TLS handshakes cost more than one round trip each), not investigated further here since it is a latency-methodology question, not a size one.

## 12. `total_bytes_exchanged` and `bytes_by_participant` closed the same way -- the AS, not the RS, is the larger contributor to servers' egress in Classic and PQC

**Context.** Decision 11 fixed `N_JWT`/OPINsize but explicitly left `total_bytes_exchanged` and `bytes_by_participant` undercounted, since neither field is derived from OPINsize's four terms and Decision 11's own fix (`simulate_login()` capturing only the JARM-bearing hop) did not route the *rest* of the login/consent traffic through the same accounting path. This decision closes that second gap.

**Fixed at the source, generalized from Decision 11's hook.** `simulate_login()`'s single-hop `_capture_jarm_hop` callback is replaced with a session-level `_capture_hop`, registered via `session.hooks["response"].append(...)` instead of passed to one call -- `requests` dispatches a session hook for every response the session receives, including every redirect hop `resolve_redirects()` follows internally for each of the three top-level calls (`GET /auth`, `POST /login`, `POST /confirm`), not just the final one. Each response becomes the same call-shaped dict `do_call()` produces (participant via `classify_participant()`, bytes via `header_bytes()`), and the one response still carrying the JARM keeps getting its token extracted exactly as before. `jarm_calls` is renamed `login_calls` throughout (`simulate_login()`, `wait_for_authorization_code()`) to reflect that it now carries all of this traffic, not just the JARM hop. `classify_participant()` on these URLs returns "Other", same as every other AS/RS call `do_call()` already produces under `_USE_TLS_KEM_PROXY` (confirmed: it classifies by the URL actually connected to, which is always the proxy's `127.0.0.1:8443` address regardless of participant -- see Decision 8/10) -- this is consistent with the existing convention, not a new inconsistency.

**Verified end-to-end, correct interpreter.** Ran the fixed pipeline (`thesis/scripts/.venv`'s pinned `requests==2.34.2` -- Decision 10 already found the global interpreter's `requests==2.32.3` produces slightly different header byte counts) as one fresh, isolated run per profile, 0ms scenario:

| Profile | total_requests (old→new) | total_bytes_exchanged (old→new) | Δ |
|---|---:|---:|---:|
| Classic | 28 → 42 | 66,828 → 125,065 | +58,237 (+87.14%) |
| PQC | 28 → 42 | 185,013 → 259,552 | +74,539 (+40.29%) |
| Hybrid | 28 → 42 | 255,276 → 331,219 | +75,943 (+29.75%) |

Hybrid's delta (+75,943 bytes) matches Decision 11's own preliminary scratch measurement exactly -- that earlier "at least 75,943 bytes" figure was apparently taken under `CRYPTO_PROFILE=hybrid`, not profile-independent as loosely stated there; the precise, reproducible, in-pipeline number now supersedes it for all three profiles.

**Correction applied to the already-collected v7 dataset, without re-collecting -- same justification as Decision 11.** `thesis/scripts/apply_login_traffic_correction.py` adds `total_requests_corrected`, `total_bytes_corrected`, and `bytes_by_participant_corrected` into `report_data_v7.json`'s existing `size` fields, alongside the originals. The new traffic is 100% AS-side (every request in `simulate_login()` targets `auth.local` paths; the RS and PKI/CRL are never touched by the login flow), so the entire "Other" bucket's delta is attributed to `participants_decomposed[profile]["AS_corrected"]`, leaving RS and PKI/CRL untouched -- the script asserts `AS_corrected + RS == Other_corrected` exactly for both directions and all three profiles before writing (same reconciliation check Decision 10 used to validate the original decomposition).

**A real narrative correction, not just a number update.** The consolidated report's AS row (Section 2) previously read 14,188 / 29,570 / 31,058 bytes -- the AS's signed artifacts alone -- and its RS row claimed "the RS accounts for 53.1%/66.4%/63.8% of servers' outbound traffic... the participant that weighs most on the cloud egress bill." With the login/consent and JARM traffic correctly counted, the AS row becomes 68,325 / 100,009 / 102,901 bytes, and the RS's share of AS+RS outbound drops to 27.6% (Classic) / 47.7% (PQC) / 54.1% (Hybrid): **the AS is the larger contributor in Classic and PQC**, and the two participants are close to parity in Hybrid. The earlier "RS weighs most" reading was an artifact of the AS's undercount, not a real property of the flow -- `Consolidated_Metrics_Report_FINAL.md`'s AS/RS rows (Section 2) and the "HTTP requests" count (Section 1.1) are updated to say so plainly, citing this decision.

**What remains open.** The round-trip-count gap the external review calculated from latency deltas at higher network-delay scenarios is still only partially closed (42 real requests confirmed, not 28 -- but see Decision 11 on the remaining gap, plausibly TCP/TLS connection-establishment RTT, not investigated further here). The T_fluxo/latency dataset itself still needed a genuine re-collection under the persistent-signer architecture to remove the container-spawn contamination described elsewhere in this project's history -- an analytical correction was not applicable there, since latency (unlike every byte-size metric in this dataset) is not a deterministic quantity. Decision 13 closes this.

---

## 13. Latency dataset re-collected under the persistent-signer architecture -- the container-spawn overhead was masking a much smaller real cost, and inverted a headline conclusion

**Context.** The whole v7 latency dataset (T_fluxo, 10 runs × 6 scenarios × 3 profiles = 180 runs) was collected before the persistent ML-DSA-65 signer replaced the old per-call container-spawn architecture in code. Every PQC/Hybrid signing call in that dataset paid roughly 1.25s of Docker container-startup overhead; at 8 signing calls per flow, this added some 6-10s to every PQC/Hybrid run regardless of network condition -- already known and measured before this session (from now-deleted exploratory work), but never propagated into a re-collection until an external technical review flagged the resulting numbers as implausible on their face.

**Re-collected, not corrected analytically.** Unlike Decisions 11 and 12, this quantity is not deterministic (T_fluxo is wall-clock, subject to real OS/network jitter -- Decision 5's own environment-drift findings already established this), so no single precise measurement can stand in for the original sample the way the JARM/login-traffic bytes did. Ran the full original protocol again -- `thesis/scripts/switch_crypto_profile.py` per profile (including its psql health check and 5 discarded settling runs, Decision 4), then `thesis/scripts/latency_automation.py` per scenario, `thesis/scripts/.venv`'s pinned `requests` version (Decision 10) -- overwriting `thesis/results/v7/latency/experimentN - <Profile>/<ms>ms/` in place. v7 stays the official version; this is a fix to it, using the architecture the project had already committed to, not a new experiment or a new version. Zero whole-run retries across all 198 runs (180 counted + 18 warmups).

**Before/after, T_fluxo median (10 runs), ms:**

| Scenario | Classic (old→new) | PQC (old→new) | Hybrid (old→new) |
|---|---:|---:|---:|
| 0 ms | 2,891.26 → 2,613.98 | 9,586.39 → 2,510.39 | 10,269.73 → 2,777.12 |
| 14 ms | 4,693.21 → 4,992.25 | 11,152.92 → 4,906.41 | 12,275.20 → 5,545.71 |
| 30 ms | 7,176.65 → 7,930.67 | 13,345.81 → 7,847.35 | 14,492.22 → 8,356.60 |
| 140 ms | 24,859.26 → 27,856.77 | 30,107.49 → 28,188.37 | 32,358.19 → 29,195.10 |
| 225 ms | 38,481.78 → 43,384.19 | 44,327.57 → 43,699.64 | 46,416.61 → 45,056.78 |
| 320 ms | 53,669.58 → 60,852.74 | 59,569.22 → 61,123.44 | 61,437.57 → 63,397.11 |

Classic's own numbers moved too (up, by a few percent) -- expected, since Classic already went through the same unified proxy architecture (Decision 1) and shares the general environment-drift sensitivity Decision 5 documented; the point of interest is the PQC/Hybrid columns collapsing from several seconds above Classic to within a few hundred milliseconds of it.

**Statistical re-test, exact one-sided Mann-Whitney U (`thesis/scripts/compute_v7_report_data.py`, unchanged methodology from the original v7 batch):**

| Scenario | p(PQC > Classic) | Significant (α=0.05)? | p(Hybrid > PQC) | Significant? |
|---|---:|:---:|---:|:---:|
| 0 ms | 0.9474 | No | 0.0005 | Yes |
| 14 ms | 0.9624 | No | 5.4e-06 | Yes |
| 30 ms | 0.9927 | No | 5.4e-06 | Yes |
| 140 ms | 0.0116 | Yes | 5.4e-06 | Yes |
| 225 ms | 2.2e-05 | Yes | 5.4e-06 | Yes |
| 320 ms | 0.1965 | No | 5.4e-06 | Yes |

**A headline conclusion is overturned, not just its numbers.** The original report claimed "the order Classic < PQC < Hybrid holds under every condition... the distributions don't overlap." That was true of the contaminated data (a ~6-10s fixed gap swamps everything) and is false of the real one: PQC is statistically indistinguishable from Classic at 0, 14, 30, and 320 ms, and only reliably slower at 140 and 225 ms, by roughly 0.4-1.2%. The Classic/PQC run ranges overlap at every single scenario now. Hybrid vs. PQC is the one comparison that remains robustly significant everywhere (p < 0.001 throughout, ranges stop overlapping from 14 ms on) -- doing two signatures instead of one is a reliable, measurable cost; migrating from classical to a single post-quantum scheme, once the measurement artifact is removed, is not clearly slower at all at low-to-moderate network latency in this environment.

**Why this is a better result for the migration case, not a worse one.** The original dataset's "PQC costs 5-7 fixed seconds" finding, if taken at face value, would have been a serious practical objection to migration. The corrected finding -- a few hundred milliseconds, only sometimes statistically distinguishable from classical RSA, dwarfed by ordinary network latency in any real deployment -- is the more defensible and, for the thesis's own migration argument, the more favorable one. It also means the original number was wrong in a way that happened to overstate the cost being investigated, which is exactly the direction of error most worth catching and disclosing plainly rather than the one most convenient to leave uncorrected.

**Updated:** `report_data_v7.json` (`latency`, `latency_deltas`, `hypothesis` fields, regenerated by `compute_v7_report_data.py` and re-merged with Decisions 11/12's analytical corrections via `apply_jarm_correction.py` and `apply_login_traffic_correction.py`, which touch only the `size`/`opinsize`/`participants_decomposed` fields and are unaffected by this re-collection). `Consolidated_Metrics_Report_FINAL.md` Section 4 rewritten with the corrected table, the Mann-Whitney results, and the superseded-claim disclosure, citing this decision.

**What remains open.** This closes every item raised by the external review and by this project's own prior investigation, up to this point. No further re-collection is planned; a future reviewer questioning a specific number should be pointed at the raw runs under `thesis/results/v7/latency/` and `thesis/results/v7/size/`, both now internally consistent with the architecture actually described in `ARCHITECTURE.md`. (Decision 14, immediately below, revisits one further item -- the PQC profile's certificate chain not being post-quantum end-to-end -- found after this decision was written.)

---

## 14. PQC's certificate chain made genuinely post-quantum end-to-end -- closing item 4.3/Recommendation 2 with real data, not a declaration of partial transition

**Context.** The external review's item 4.3 found the PQC profile "not post-quantum end-to-end": `root_ca_pqc.crt`/`issuer_ca_pqc.crt` (the CA-download simulation artifacts) and `client_one_pqc.crt`/`mtls_pqc.crt`/`op_pqc.crt` (the certificates that actually participate in the live mTLS handshake) all carried an ML-DSA-65 subject key but a classical RSA issuer signature -- a real asymmetry against Hybrid, whose certificates carry a genuine ML-DSA-65 signature from the CA. Recommendation 2 offered two ways to close this: make the comparison symmetric (CA signs in ML-DSA-65), or explicitly declare PQC a partial transition. Chosen here: make it symmetric, with real data, reusing infrastructure this project had already built for Hybrid's own CA-side ML-DSA-65 signing (`issuer_ca_pqc.key`).

**Justification for revising the PQC profile's scope.** This thesis's SAD (Solution Architecture Document) models the migration in three phases: Phase 1 (classical), Phase 2 (Hybrid, the transition profile -- backward compatibility is its entire point), Phase 3 (PQC pure, the ecosystem's final state, once every participant has migrated). By definition, Phase 3 preserves no classical component anywhere. The original v2 decision to leave the PQC profile's CA and live-handshake certificates classically signed predates this phase model and reflected a narrower, "only the subject key moves" scope (Etapa 3.1). This decision revises that scope call in light of the phase model the thesis itself now uses: PQC pure should mean Phase 3, and Hybrid alone should carry the backward-compatibility burden the "partial transition" language would otherwise put on PQC.

**Fixed in two layers (`mock-service-os/certs/main.go`):**

1. `-pqc-ca-fully-post-quantum`: re-issues `root_ca_pqc.crt` self-signed (pure ML-DSA-65) and `issuer_ca_pqc.crt` signed by `root_ca_pqc`'s own key. Both reuse their existing ML-DSA-65 keys unchanged -- only the certificate wrapper (issuer, signature) is new.
2. `-pqc-live-certs-fully-post-quantum`: re-issues `client_one_pqc.crt`, `mtls_pqc.crt`, and `op_pqc.crt` signed directly by `root_ca_pqc`'s key instead of the classical `ca.crt` -- again reusing each cert's existing key. Signed directly by the root, not through `issuer_ca_pqc` as an intermediate, matching the single-level-chain shape every other cert this tool issues already uses (no intermediate bundling needed in the handshake).

**A real bug found and fixed along the way, not glossed over.** The first attempt at both steps used a leaf-shaped template for `root_ca_pqc` (`KeyUsage: DigitalSignature`, no `IsCA`/`BasicConstraintsValid`) -- ostensibly harmless from the tool's own perspective (the tool doesn't verify anything, it only issues certificates), but the live gateway does: switching to the new chain broke the pqc profile's mTLS handshake outright, with `mock_mtls` rejecting `client_one_pqc.crt` (`x509: invalid signature: parent certificate cannot sign this kind of certificate`) and Go's TLS client silently sending no certificate at all in response (logged as `clientCertBytes: 0`, not a connection error -- the failure mode that made this take real investigation to diagnose, not an obvious crash). Root cause: Go's X.509 chain verification requires any certificate acting as a signer, root included, to carry CA authority (`IsCA: true`, `KeyUsage` including `CertSign`). Fixed by giving `root_ca_pqc`'s template proper CA properties, matching `generateCACert()`'s own template for the classical `ca.crt`. `mock_mtls/main.go`'s `caCertPool()` was also extended to trust `root_ca_pqc.crt` under `CRYPTO_PROFILE=pqc` (previously it loaded only the classical `ca.crt`, unconditionally, for every profile) -- without this, the gateway would never have had a chance to verify the new chain regardless of the CA-properties fix. `-resign-all`'s ML-DSA-65 group (`resignMLDSANames`) was also split so a future CA expiry re-issues this same chain, not silently reverts it to the classical CA.

**Verified end-to-end, not just "the tool exits 0."** After both fixes: the real pqc flow (`opin_flow.py`, all sub-flows, all 6 mTLS connections) completes successfully against the new chain, confirmed live via the gateway's own handshake log (`clientCertBytes: 5,879`, matching `client_one_pqc.crt`'s new size exactly, `curveID: MLKEM1024`, no handshake errors). Hybrid's own `-verify-hybrid` check still passes unmodified, since `issuer_ca_pqc.key`'s public component -- the only thing Hybrid's alt-signature mechanism depends on -- never changed.

**Measured live, once per quantity (deterministic, same justification as Decisions 10/11/12):**

| Quantity | Old (RSA-signed chain) | New (fully ML-DSA-65) |
|---|---:|---:|
| `root_ca_pqc.crt` (PEM) | 4,048 bytes | 8,001 bytes |
| `issuer_ca_pqc.crt` (PEM) | 4,052 bytes | 8,013 bytes |
| `handshake_bytes` (P50, 6 connections) | 16,605 bytes | 22,607 bytes |
| `client_cert_der_bytes` | 2,953 bytes | 5,879 bytes |
| HTTP framing per PKI response | 103 bytes | 103 bytes (unchanged) |

`thesis/scripts/apply_pqc_ca_postquantum_correction.py` applies this analytically to `report_data_v7.json`, layered on top of Decisions 11/12's already-corrected fields (`extended_corrected`), the same provenance-preserving pattern as every prior correction in this document.

**A genuinely surprising result: PQC's handshake is now bigger than Hybrid's.** `handshake_bytes` P50: Classic 5,119 / PQC 22,607 / Hybrid 18,023 -- PQC is now the largest of the three, not Hybrid. The reason is structural, not an error: Hybrid's certificate keeps reusing Classic's compact RSA subject key and signature as its primary structure, adding the ML-DSA-65 material only as incremental X.509 extensions; PQC's certificate has no compact structure left to reuse -- both its subject key and its issuer's signature are full ML-DSA-65 -- so it ends up larger even though it is the conceptually "purer" profile. Confirmed live, not assumed: `client_cert_der_bytes` alone already shows the same ordering (PQC 5,879 > nothing to compare within Classic/Hybrid's shared RSA base, but Hybrid's 6,859 stays only 16.7% above PQC's, not the 132% gap the old, classically-signed PQC certificate showed).

**Impact on OPINsize and the ratios this report's central claims rest on:**

| | OPINsize | PQC/Classic | Hybrid/Classic | Hybrid/PQC |
|---|---:|---:|---:|---:|
| Before this decision (Decisions 11/12 only) | 271,055 | 3.52× (+252.34%) | 4.56× (+355.59%) | 1.29× (+29.30%) |
| After this decision | 322,895 | 4.20× (+319.73%) | 4.56× (+355.59%) | **1.09× (+8.54%)** |

The Hybrid/PQC premium falls from +29.30% to +8.54% -- close to, though not identical to, the external review's own rough estimate ("something near 10%"). PQC alone now captures 89.9% of Hybrid's total increase over Classic (up from ~71-90% at earlier stages of this correction chain, depending on which prior fix is used as the baseline). This is the expected direction: once PQC's own certificate chain stops getting an unearned discount from reusing a classical signature, its true byte cost rises to sit much closer to Hybrid's, and Hybrid's marginal premium shrinks to roughly what a second, additive signature scheme should cost -- not a sign that Hybrid was overpriced before, but that PQC was underpriced.

**Updated:** `mock-service-os/certs/main.go` (two new flags, `resignEverything` revised), `mock_mtls/main.go` (`caCertPool()` now profile-aware), `report_data_v7.json` (`pki.pqc`, `size.pqc`, `opinsize.pqc` `_corrected` fields via `apply_pqc_ca_postquantum_correction.py`). `Consolidated_Metrics_Report_FINAL.md` Section 1.2 (profile table and a new paragraph stating PQC is now end-to-end post-quantum, citing the SAD's three-phase model), Section 2 (OPINsize, mTLS handshake, Client certificate, Average PKI_bytes, and Directory/PKI rows), and Section 3 (equation variables, the PQC calculation, and the comparison table/prose) all updated to the corrected numbers, citing this decision.

**What remains open.** None, for item 4.3 specifically -- both halves (CA-download artifacts and live-handshake certificates) are now closed with real, live-measured data, not a declaration of partial transition. The per-endpoint signing/verification latencies in Section 2 (measured before this decision, at the 0 ms scenario) were not re-collected, since they depend on CPU-bound signing time, not certificate chain length or issuer identity -- unaffected by this change and not expected to need revisiting.
