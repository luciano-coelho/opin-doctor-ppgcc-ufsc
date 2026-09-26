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
