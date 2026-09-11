# Decisions — Nível 1 (TLS key exchange coverage)

## 1. The gateway's shared `tls.Config` broke `auth`'s own internal RS-fetch call -- fixed by extending Decision 5's existing carve-out to the key-exchange dimension, not by discovering a new race

**Context.** After wiring `mock_mtls`'s `CurvePreferences`/`MinVersion` to vary
by `CRYPTO_PROFILE` (pqc -> `MLKEM1024`, hybrid -> `X25519MLKEM768`, see
`thesis/results/v6/Level 1/ARCHITECTURE.md`, Fase 2), the first full
end-to-end flow test (pqc, via `tls_kem_proxy`) failed reproducibly (3/3
attempts, not occasionally) at `InsurerAdapter.getConsent()`:

```
InvalidGrant: invalid_grant
    at InsurerAdapter.getConsent (adapter.js:53:13)
```

This is the exact same function and error shape as Decision 5
(`thesis/results/v5/size/DECISIONS.md`) and its recurrence, Decision 9
(`thesis/results/v5/latency/DECISIONS.md`) -- both a rare, timing-dependent
race between `auth` and `mock_mtls`'s reentrant introspection call. Given the
superficial match, the first hypothesis was "the proxy's added latency made
the same rare race more likely." **Investigated before assuming this, per
standing instruction, using the same log instrumentation as the original
Decision 5 investigation** (`docker compose logs auth`/`mtls`, explicit UTC
offsets, cross-referenced timestamps) -- and the cause turned out to be
categorically different, not the same race at higher frequency:

- `mtls`'s own log showed, at the exact same instant as a successful call
  through the proxy: `"http: TLS handshake error from 172.20.0.7:...: tls:
  no key exchanges supported by both client and server"`.
- `auth`'s log for the same request: `"error fetching the consent ... -
  Error: write EPROTO ...SSL routines:ssl3_read_bytes:ssl/tls alert
  handshake failure... SSL alert number 40"`.

`40` is `handshake_failure` -- a deterministic protocol rejection, not the
`EOF` that characterized Decision 5's original timing coincidence (`auth`'s
single Node process still mid-flight on the outer request when the
self-referential introspection call arrived). No timing window is involved
here at all: `auth`'s own internal HTTPS client (`mock-service-os/mock_as/
utils/opin/adapter.js`'s `InsurerAdapter`, via `express.js`'s
`apiUrl.host = apiUrl.host.replace('auth', 'matls-api')`) cannot negotiate
`MLKEM1024`/`X25519MLKEM768` any more than Python could (Fase 0) -- so this
call fails outright, every single time, once the gateway's key exchange
requires either group. 3/3 reproductions, not Decision 5/9's documented
rarity (1 in ~89 token exchanges), confirms this: a rare race and a 100%
deterministic protocol mismatch are not the same phenomenon even though they
surface through the same `InvalidGrant`/`getConsent()` error shape.

**Root cause.** `mock_mtls`'s TLS listener uses one shared `tls.Config` for
every inbound connection, regardless of purpose. Decision 5 already
established that `auth`'s own call to the RS (host `matls-api.local`) uses
"the fixed classical transport certificate ... unrelated to `CRYPTO_PROFILE`"
for its *signature* dimension -- this project already treats that one
specific internal, self-referential call as architecturally exempt from
profile variation. Pinning `CurvePreferences` to the profile's new group
gateway-wide extended that variation to the *key-exchange* dimension without
carrying the same exemption forward, breaking the one caller Decision 5 had
already carved out.

**Options considered** (thesis/results/v6/Level 1/ARCHITECTURE.md has the
full comparison): two separate TLS listeners on different ports (would also
require changing `adapter.js`/`express.js`, i.e. touching the exact code
Decision 5 deliberately left alone); teaching `auth`'s own Node.js TLS
client to negotiate the new groups (out of scope -- this piece of work
measures the external, client-facing key exchange `opin_flow.py` drives,
not a migration of the system's internal service mesh, and is of uncertain
feasibility given Node's TLS stack depends on the same class of OpenSSL
version constraint as Python's); same port, differentiated by SNI via the
gateway's existing `GetConfigForClient` hook.

**Decision: SNI-based differentiation, via the already-existing
`GetConfigForClient` hook.** `mock_mtls/main.go` already registers a
`GetConfigForClient` callback (previously used only to record handshake
start time). Confirmed (`express.js:144-146`) that `auth`'s internal client
always connects to literally `matls-api.local`, and Node's HTTPS client sets
SNI to that same hostname automatically -- no code in `opin_flow.py` or
`tls_kem_proxy` ever targets that hostname (external client-facing calls use
`api.local`; the proxy's own upstream `tls.Dial("tcp", "mtls:443", ...)`
defaults its SNI to `"mtls"`), so there is no overlap risk between the two
signals. The hook now checks `hello.ServerName == "matls-api.local"` and, if
so, returns a config cloned from the profile's own (certificates, cipher
suites, everything else unchanged) but with `CurvePreferences` reset to the
classical set and `MinVersion` back to `tls.VersionTLS12` -- for every other
caller, returns `nil` (no override, exactly as before this decision).

This is not a new isolation mechanism -- it is Decision 5's own "fixed
classical, unrelated to `CRYPTO_PROFILE`" rule, now extended to cover the
dimension this etapa adds, expressed through a hook the gateway already had
rather than new infrastructure.

**Confirmed not a new measurement variable.** This internal connection was
never part of what `opin_flow.py`/`tls_kem_proxy` measure: `N_mTLS = 6` and
`mTLS_handshake_bytes` come entirely from the connections `opin_flow.py`'s
own `requests.Session()` pools open (three pools -- AS, RS, login -- per
sub-flow, two sub-flows), captured by the gateway keyed on that
connection's own `remoteAddr`. `auth`'s self-referential call to the RS is a
separate, backend-only connection on its own `remoteAddr`, never included in
either metric. Keeping it classical changes nothing that is or ever was
reported.

**No changes needed in `auth`/`adapter.js`/`express.js`** -- Node's HTTPS
client already sends the right SNI; it has no idea this distinction exists
on the server side.

## 2. `handshake_bytes` cannot be compared v5-vs-v6 directly -- the TLS client implementation changed, not just the curve. A same-implementation "Go-clássico" baseline was added instead

**Context.** The first pilot's `handshake_bytes` came back *smaller* with
ML-KEM than v5's pre-KEM numbers, in both profiles -- the opposite of the
expected direction:

| Profile | v5 (Python client, no KEM) | v6 pilot (Go client, +KEM) |
|---|---|---|
| PQC | 19,756 bytes | 16,605 bytes |
| Hybrid | 25,880 bytes | 18,023 bytes |

**Investigated before drawing any conclusion, per standing instruction.**
Captured the raw `ClientHello` bytes from both client implementations
(same cert/profile, nothing else changed) and decomposed cipher suites,
extensions, and `key_share` byte-for-byte:

| Client | Total | cipher_suites | extensions | `key_share` |
|---|---|---|---|---|
| Python/OpenSSL (v5, classical) | 517 | 38 (18 suites) | 401 | 42 |
| Go, classical | 301 | 8 (3 suites) | 215 | 75 |
| Go, `MLKEM1024` | 1,800 | 8 (3 suites) | 1,714 | 1,578 |
| Go, `X25519MLKEM768` | 1,448 | 8 (3 suites) | 1,362 | 1,226 |

Go's own `ClientHello` with a KEM group is already *larger* than Python's
classical one (1,448-1,800 vs. 517 bytes) -- the `ClientHello` alone
predicts an *increase*, not the decrease observed. The `ClientHello` was
not the explanation.

**Isolated the real cause with a controlled, same-implementation test.**
Using the exact same Go client (no client cert, for simplicity) against
the real, running gateway, varying *only* the curve via SNI (the Decision 1
carve-out: `matls-api.local` forces classical, any other SNI gets the
profile's group) -- same server certificate both times:

| Profile | Go, classical | Go, +KEM | Delta |
|---|---|---|---|
| PQC | 7,228 bytes | 10,197 bytes (`MLKEM1024`) | **+2,969 bytes** |
| Hybrid | 8,337 bytes | 10,506 bytes (`X25519MLKEM768`) | **+2,169 bytes** |

Confirmed: ML-KEM genuinely *increases* handshake bytes, by a sensible
amount, exactly as expected, once the comparison holds the client
implementation constant. The apparent decrease in the v5-vs-v6 comparison
was entirely an artifact of comparing two different TLS client
implementations (Python/OpenSSL directly, vs. Go's `crypto/tls` via
`tls_kem_proxy`) -- not an effect of ML-KEM itself. Reconfiguring Go's
client to mimic Python's exact `ClientHello` byte-for-byte was considered
and rejected: even matching cipher suite/extension lists would not
guarantee identical behavior at points other than `ClientHello` (buffering,
exact TCP segmentation, how much of the connection's tail end
`countingConn`/`StateActive` captures), so no configuration change can make
this comparison trustworthy at the byte level.

**Decision: `handshake_bytes` gets its own, auxiliary "Go-clássico"
baseline, measured with the same client implementation as the KEM
measurement itself -- it does not replace v5's official Classic numbers
for anything else.** A new tool, `thesis/scripts/go_handshake_probe/`
(a one-shot Go HTTPS client, reusing `tls_kem_proxy`'s exact TLS
configuration shape), makes one real request per run through the
`matls-api.local` SNI carve-out, presenting the profile's real external
client certificate (`client_one_pqc.crt`/`client_one_hybrid.crt`) with
classical-only `CurvePreferences`. This is a synthetic combination that
never occurs in the real system (that certificate normally never travels
over that SNI) -- it exists solely to get a same-cert, same-client,
classical-only reference point. Driven by
`thesis/scripts/go_classical_baseline.py`, which measures only
`mtls_handshake_bytes` (median of 10 runs) -- explicitly **not** a
remeasurement of JWT size, certificate size, or any other size metric,
since none of those depend on which TLS client negotiated the connection.

**Scope of this baseline, stated explicitly:** it is a reference point for
computing the ML-KEM delta in isolation, nothing more. **It does not
replace v5's official Classic profile** (measured end-to-end via Python,
the real client this thesis's automation actually drives) as the source of
truth for any other comparison in the thesis. Every other metric --
JWT size, certificate size, `JWK_PK_size`, bytes per participant, T_fluxo
-- continues to come from the real `opin_flow.py` flow (Python client),
exactly as documented throughout `thesis/results/v5/` and the rest of this
directory. The final Nível 1 comparison table presents `handshake_bytes`
with this baseline named explicitly alongside it, not silently substituted
for v5's Classic number.

**Pilot results (0ms, 10 runs each, 0% spread):**

| | Go-clássico baseline | PQC (Go + `MLKEM1024`) | Hybrid (Go + `X25519MLKEM768`) |
|---|---|---|---|
| `mtls_handshake_bytes` | PQC cert: 13,525 · Hybrid cert: 15,743 | 16,605 | 18,023 |

The two Go-clássico values differ from each other (13,525 vs. 15,743)
because the certificate itself differs by profile (`client_one_pqc.crt`
2,953 bytes vs. `client_one_hybrid.crt` 6,859 bytes) -- exactly as
expected, since only the curve was meant to be isolated per profile, not
the certificate. PQC's own delta (Go-clássico 13,525 -> PQC+KEM 16,605)
is +3,080 bytes; Hybrid's own delta (15,743 -> 18,023) is +2,280 bytes --
both close to, and consistent with, the no-client-cert controlled test
above (+2,969 / +2,169), the small remaining difference plausibly being
TCP-segmentation noise from the extra certificate bytes now in play.

## 3. The full-batch "+10-12s proxy overhead" contradicted the stub calibration (~2ms) by ~1000x -- root cause was `opin_flow.py` resolving the literal string `"localhost"`, not a cost of the two-hop bridge architecture

**Context.** `CONSOLIDATED_REPORT.md`'s first version concluded that the
~10-12s `T_fluxo` gap between the Go-clássico-via-proxy baseline and v5's
Classic profile was "overhead of the test's two-hop bridge architecture,"
explicitly flagging that this contradicted the Fase 4 stub-mode calibration
(~2ms, Python -> proxy -> Python, gateway never touched) by close to 1000x.
**Ordered to investigate before treating this as closed, per standing
instruction, with three named hypotheses to check directly rather than
accept "it's the proxy" on the calibration's word alone.**

**Hypothesis 1: stub mode skips a step (e.g. a full upstream handshake)
that the real path always pays.** True in a structural sense --
`tls_kem_proxy/main.go`'s `runStub()` never calls `tls.Dial` at all, by
design (it exists to isolate the local Python<->proxy hop from the
proxy<->gateway hop, stated in the file's own module docstring) -- but this
does not explain the magnitude. A controlled Go-to-Go test
(`relay_overhead_test`, warm reused connection) measured relay mode's real
added cost, upstream dial included, at **4.50ms** vs. **1.99ms** direct --
the same order of magnitude as the stub's ~2ms, not 1000x more. Ruled out
as the explanation for the gap, though it does mean the stub calibration's
number is a floor for a slightly different thing than "the whole real
path," a distinction worth keeping in mind but not the cause here.

**Hypothesis 2: the overhead is not the proxy itself but something that
only appears in the full flow (fresh connections, unexpected reuse,
synchronization).** **Confirmed as the actual cause.** Phase-level timing
instrumentation of the real Python flow (`fetch_server_keys_and_ca`, 3
calls) showed each FRESH connection costing ~2.03-2.06s while a REUSED
connection on the same session cost ~2-3ms -- already a sharp split
pointing at connection establishment, not steady-state transfer. Testing
connection establishment directly (same target, only the hostname string
varied) isolated the exact mechanism:

| Host used to reach `tls_kem_proxy` | Fresh-connection cost |
|---|---|
| `localhost:8443` | **2.095s** |
| `127.0.0.1:8443` | **0.033s** |

This is a classic IPv6-then-IPv4 "happy eyeballs" fallback on this machine:
Python resolves the literal string `"localhost"` to `::1` first, that
attempt stalls/fails, and only then falls back to `127.0.0.1` -- costing
~2.1s per occurrence. `opin_flow.py`'s `AUTH_CONNECT_HOST`/
`API_CONNECT_HOST`/`DIRECTORY_CONNECT_HOST` all built the proxy target as
`f"localhost:{TLS_KEM_PROXY_PORT}"`. With `N_mTLS = 6` fresh, never-reused
connections per full flow execution, 2.095s x 6 ≈ **12.57s** -- matching the
batch's own "+10.66s (PQC) / +11.98s (Híbrido)" overhead at 0ms almost
exactly. The stub calibration never saw this: it deliberately performs one
warmup request (excluded from measurement, matching the project's existing
"discard warmup" convention) and then measures 200 requests reused on that
same session (`calibrate_tls_kem_proxy_stub.py`, `url =
f"https://localhost:{args.port}/"`, one `requests.Session()` for the whole
run) -- the one connection where the happy-eyeballs stall occurs is exactly
the one sample the calibration throws away, and the 200 measured samples
never re-trigger a new connection at all. The calibration was correct about
what it measured (steady-state reused-connection cost); it was simply never
representative of the real flow's connection pattern (6 fresh connections,
none reused across pools).

**Hypothesis 3: the decomposition against the Go-clássico baseline is
capturing something beyond what it should.** Partially true, but not in a
way that invalidates the KEM-cost conclusion. The Go-clássico latency
baseline reuses the same `start_tls_kem_proxy`/`*_CONNECT_HOST` code path
(curve overridden via `TLS_KEM_PROXY_CURVE_OVERRIDE=classical`), so it paid
the exact same `"localhost"` cost, to the same degree, as the KEM
(PQC/Híbrido) runs it was compared against -- only the curve differs
between the two, which has no bearing on DNS resolution. Because the bug
was present and equal on both sides of that specific subtraction, it
**cancels out**: the `CONSOLIDATED_REPORT.md` "delta do KEM" table (PQC/
Híbrido vs. Go-clássico, values from -0.35s to +1.13s) was not distorted by
it, and its conclusion -- ML-KEM's own cost is negligible relative to
measurement noise -- stands. What *was* wrong is the separate "overhead do
proxy" table (Go-clássico vs. v5's Classic profile, +9.56s to +12.22s
across scenarios): v5's Classic profile never went through `tls_kem_proxy`
or the string `"localhost"` at all, so that side of the comparison is
clean, and the entire gap landed on the contaminated side. The number was
measured correctly; its causal label ("cost of the two-hop bridge
architecture") was not -- it is a specific, fixable test-harness DNS
artifact, not a property of the proxy design.

**Fix.** Changed `f"localhost:{TLS_KEM_PROXY_PORT}"` to
`f"127.0.0.1:{TLS_KEM_PROXY_PORT}"` for all three `*_CONNECT_HOST`
variables in `thesis/scripts/opin_flow.py`. Validated at three levels:

| Measurement | Before | After |
|---|---|---|
| `fetch_server_keys_and_ca` (3 fresh connections) | 4.149s | **0.064s** |
| Insurance sub-flow total | 10.547s | **5.621s** |
| Full flow (insurance + person, 28 calls, Híbrido, 0ms) | ~21-22s (pilot-observed) | **10.635s** |

The post-fix full-flow number (10.635s, real ML-KEM key exchange included)
lands almost exactly on v5's own pre-existing Híbrido `T_fluxo` at 0ms
(**10.7295s**, `thesis/results/v5/latency/CONSOLIDATED_REPORT.md`) --
signature-only, no proxy, no KEM. The gap the batch attributed to "proxy
architecture overhead" is, once the DNS artifact is removed, statistically
indistinguishable from zero.

**Conclusion.** The batch's `handshake_bytes` results (240 runs, Decision 2)
are unaffected -- byte counts do not depend on wall-clock connection time.
**All 240 latency runs (KEM + Go-clássico baseline, both profiles, all 6
scenarios) are contaminated by this artifact and must be re-run** with the
fix in place before `CONSOLIDATED_REPORT.md`'s latency section and its
"proxy overhead" framing can be considered valid.

## 4. A ~2s Hybrid/0ms residual, investigated instead of accepted as noise -- traced to session-level Docker Desktop degradation, not to the KEM or the Hybrid certificate

**Context.** After Decision 3's fix, the restarted Nível 1 pilot's
Híbrido/0ms group came back with a median 2.01s above v5's own historical
Híbrido baseline (10.7295s) and a 39.7% spread, including one run at
16.36s -- while PQC/0ms landed within 0.05s of its own v5 number. **Ordered
to investigate before treating this as noise**, with three named checks.

**Removing the single outlier (run02) did not resolve it.** Median moved
only 12.744s -> 12.298s (spread 39.7% -> 36.9%) -- four other runs
(13.19-16.04s) stayed elevated. Not one bad run distorting an otherwise
clean sample.

**Cert size through the proxy, tested directly, is not the cause.** A
controlled Go-to-Go test (`tls_kem_proxy`, classical curve fixed, PQC cert
2,953 bytes vs Hybrid cert 6,859 bytes, direct vs via-proxy) measured
~20-24ms per fresh connection in all four combinations -- no cost
attributable to the larger Hybrid certificate traversing the two-hop
bridge.

**A first re-test pointed at session settling, but a second one
contradicted that explanation.** Cross-referencing each run's own
timestamp against the `docker compose --force-recreate` that started the
Híbrido group's containers showed the elevated runs clustered in the ~2
minutes right after the switch, with later runs (7-10) already tightening.
A clean re-run of the same 10 executions on the same, by-then long-settled
stack (no recreate in between) gave median 11.369s (17.9% spread) -- 0.64s
above v5's Híbrido number, matching v5's own pre-existing PQC-vs-Híbrido
gap (0.597s, its signature-composition cost) almost exactly. This looked
like a closed explanation ("settle after switching profile") until it was
turned into a permanent, testable protocol (below) and immediately
contradicted itself: a fresh `--force-recreate` plus 5 discarded
full-flow warmups produced a *worse* median (14.789s, 25.4% spread) than
either the original or the settled re-test -- if a settling window after
recreate were the whole story, adding one should never make the number
go up. `docker system df` showed 25.29GB of build cache (12.74GB
reclaimable) accumulated from this session's own many `docker run --rm
... go run .` invocations; pruning it dropped the median to 13.290s, still
well above the 11.369s reference. **Conclusion at this point: something
about this session's own multi-hour, Docker-churn-heavy history was
degrading measurements progressively, and neither a post-switch settling
window nor a cache prune fully reversed it.**

**Resolution: an unrelated, externally-triggered Docker Desktop restart
turned into a clean-environment test.** With the OPIN stack brought back
up exactly once (no further recreates, no prune, no profile switch), the
Go-clássico/Hybrid-cert baseline (0ms, 10 runs) was repeated every ~17
minutes for 8 rounds (~2h20m), hands-off between rounds:

| Round | Time (UTC) | Median | Spread |
|---|---|---|---|
| 1 | 02:14 | 10.896s | 41.0% |
| 2 | 02:34 | 14.675s | 155.1% (one-off; max=28.95s) |
| 3 | 02:53 | 10.762s | 9.6% |
| 4 | 03:13 | 10.994s | 15.1% |
| 5 | 03:32 | 11.045s | 13.6% |
| 6 | 03:51 | 11.796s | 16.4% |
| 7 | 04:10 | 10.555s | 17.0% |
| 8 | 04:29 | 10.575s | 6.3% |

Excluding round 2's isolated spike (no recurrence, no trend before or
after -- round 3 immediately returned to the tightest spread of the whole
series), the seven remaining rounds hold flat between 10.56s and 11.80s
across the full 2h20m window, with the *last* round (10.575s, 2h14m after
the first) lower than the first (10.896s) -- the opposite of a growth
trend. This range brackets v5's own Híbrido number (10.7295s) tightly.
**The degradation was specific to that Docker Desktop session's own
accumulated state (consistent with -- though not proven to be only --
the 25GB+ build cache and hours of container churn observed before the
restart), not an inherent property of long OPIN test sessions, and not
caused by the KEM, the Hybrid certificate, or the two-hop proxy.** The
official Híbrido/0ms KEM pilot was re-run once more on this now-validated
environment: median 10.897s, spread 16.8% -- 0.17s from v5, fully
consistent with the drift measurement's own range.

**Decision:** treat the Docker Desktop restart as having resolved the
issue, confirmed by 2h20m of flat, trend-free measurements immediately
after it. `switch_crypto_profile.py` (Decision 5) keeps its 5-run settling
warmup after every profile switch as a cheap, harmless safeguard, but it
is documented honestly as *not* the mechanism that fixed this -- the fix
was the environment restart. If elevated/noisy medians reappear during
Etapa 1/2, re-run this same drift protocol before trusting the data,
rather than assuming it is a one-time, already-closed issue.

## 5. CRYPTO_PROFILE switches go through `switch_crypto_profile.py` from now on, permanently -- not just for this pilot

**Context.** Decision 4's investigation happened because a profile switch
was done by hand (`docker compose --force-recreate` run directly), with no
consistent settling step and no handling for two known boot-time races
observed live switching profiles during this pilot: `auth`/`mtls`
sometimes exit once right after a fresh recreate (localstack's SSM-seeding
init script hasn't finished writing `/local/op_fapi_client_config/
transport_certificate` yet) and `mockapi` can exit once if `psql` was not
already up (its own dependency isn't gated by compose's own health
ordering here).

**Decision.** `thesis/scripts/switch_crypto_profile.py` is now the only
sanctioned way to switch `CRYPTO_PROFILE`, for the remainder of Nível 1
(Etapas 1 and 2) and any future work that reuses this pipeline. It: (1)
force-recreates the profile-dependent services; (2) detects and retries
the two known exit races above rather than requiring a human to notice and
`docker start` them by hand; (3) burns 5 discarded full-flow executions
before returning, as a defensive settling measure (see Decision 4 for why
this is kept despite not being the actual fix for the one incident
observed). Every scenario in Etapas 1 and 2 that requires a profile
different from the currently running one switches through this script,
not through a raw `docker compose` call.

**Bug found and fixed during Etapa 1's own first use.** `opin_flow.py`
computes its routing globals (`_USE_TLS_KEM_PROXY`, `AUTH_CONNECT_HOST`,
etc.) once, at import time, from `os.environ["CRYPTO_PROFILE"]`.
`switch_crypto_profile.py`'s first version imported `opin_flow` before
setting that variable from its own `sys.argv`, so its settling runs
inherited whatever `CRYPTO_PROFILE` happened to already be in the calling
shell's environment rather than the profile actually being switched to.
Live in Etapa 1's own batch script: the switch to `pqc` (the run's first
profile switch, in a shell with no `CRYPTO_PROFILE` set at all) silently
defaulted routing to classic, so its 5 settling runs all failed with a
direct, non-proxied TLS handshake error on port 443 -- discarded regardless
(by design) and therefore invisible in the batch's own pass/fail output;
the later switch to `hybrid` happened not to hit this (ambient shell state
differed by then) and settled correctly. Fixed by setting
`os.environ["CRYPTO_PROFILE"]` from `sys.argv` *before* the `import
opin_flow` line. Verified after the fix: 5/5 settling runs succeed,
correctly routed through the proxy, immediately after switching to `pqc`.

**Consequence for Etapa 1's validity, stated explicitly.** This bug does
not affect Etapa 1's own data: `handshake_bytes`/JWT size/certificate size
are deterministic given profile+curve+certs and do not depend on wall-clock
settling at all (confirmed by Etapa 1's own 0% spread across all 240 runs,
including the ones collected right after the broken `pqc` switch). But it
means **Etapa 1 ran with the settling protocol silently non-functional for
one of its two profile switches, so it cannot be read as evidence that the
settling protocol works.** Only Etapa 2 (latency), running after this fix,
is a real test of whether `switch_crypto_profile.py`'s settling warmup
does what Decision 4 intends.

## 6. v6 (with the two-hop proxy) came back *faster* than v5 (direct Python) at high-latency scenarios -- investigated instead of left as an unexplained "positive" result

**Context.** Etapa 2's full latency table showed v6's PQC/Híbrido `T_fluxo`
(with KEM, via the proxy) consistently *below* v5's own historical
PQC/Híbrido numbers (no KEM, no proxy, direct Python) at the higher-latency
scenarios, growing with the scenario: roughly flat at 0-30ms (-0.7s to
+0.7s) but reaching -2.18s (PQC) / -0.18s (Híbrido) at 225ms and -3.43s /
-3.15s at 320ms. **Flagged as counter-intuitive before writing it into the
final report as a positive finding**, since v6 has an *extra* hop (the
proxy) that v5 never paid for -- a two-hop architecture reading as faster
than a one-hop one demands an explanation, not just a footnote.

**Isolated the variable directly, holding the curve classical on both
sides so ML-KEM plays no part.** At the 320ms scenario (already injected on
`mtls`'s `eth0` for both tests), timed a single fresh connection + one
`/jwks` request, no proxy involved on either side, same client certificate
(Hybrid, matching the profile the stack was already running under):

| Client | Path | Median (fresh conn) |
|---|---|---|
| Go (`crypto/tls`, the same client `tls_kem_proxy` uses upstream) | direct to `mtls:443` | **1.305-1.310s** (steady state) |
| Python (`urllib3` + the pyOpenSSL injection this project already needs for PQC/Hybrid certs) | direct to `127.0.0.1:443`, same carve-out SNI | **1.648-1.662s** (steady state) |

Go completes the same classical TLS 1.3 handshake + request **~0.34s
faster per fresh connection** than Python's stack, at 320ms of injected
per-packet delay -- with neither the proxy nor ML-KEM involved in either
measurement. Multiplied by `N_mTLS = 6` fresh connections per full flow
execution: 0.34s x 6 ≈ **2.0s**, which accounts for roughly 60-65% of the
observed 3.15-3.43s gap at 320ms. The scenario-by-scenario pattern (near
zero at 0-30ms, growing at 140ms+) is consistent with a per-round-trip
efficiency difference: negligible when few ms are riding on each round
trip, compounding once each round trip is worth hundreds of ms.

**Conclusion, stated at the confidence level the evidence supports.** The
"v6 faster than v5 at high latency" pattern is **not a Nível 1 result** --
it does not reflect anything about ML-KEM, the two-hop proxy, or this
etapa's own methodology. It traces, at least in large part, to v6's mTLS
connections now being driven by Go's `crypto/tls` (via `tls_kem_proxy`,
regardless of curve) instead of Python's `urllib3`/OpenSSL stack that v5
used directly -- and Go's TLS 1.3 implementation appears to need fewer
effective round trips per fresh connection, an advantage that only shows up
once each round trip carries real injected latency. The controlled test
above accounts for roughly 60-65% of the gap at 320ms; the remaining
35-40% was not run down further (plausibly more of the same effect
elsewhere in the flow's other fresh connections, or ordinary run-to-run
noise) and is left honestly unresolved rather than rounded up to "fully
explained." **This finding must be presented in `CONSOLIDATED_REPORT.md`
as a Go-vs-Python client-implementation artifact of this etapa's own
measurement method, explicitly not implied as a Nível 1 performance
benefit of any kind.**
