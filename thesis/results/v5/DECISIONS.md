# Experiment Automation v5 (Median Consolidation) — Architecture Decisions

## 1. Local classical certificate stand-ins for `root-ca.pem`/`issuer-ca.pem` in Classic mode -- closing the last profile's Raidiam dependency

**Context.** Decision 11 in `thesis/results/v4/DECISIONS.md` gave hybrid mode
its own local stand-ins for `root-ca.pem`/`issuer-ca.pem`, closing a symmetry
gap left by `thesis/results/v2/experiment2 - PQC/DECISIONS.md` Decision 12
(which did the same for pqc mode only). Classic mode was the one profile
still hitting the real, external Raidiam sandbox
(`crl.sandbox.pki.opinbrasil.com.br`) for these two files on every run --
a live dependency on a third party the automation below (10-180 sequential
runs) cannot tolerate: any latency spike or outage on that host would
silently pollute every scenario's `PKI/CRL` byte counts and, at worst,
abort a multi-hour batch partway through.

**Implementation**, extending `certs/main.go`'s existing pattern
(`-pqc-name`/`-hybrid-name`) with a new `-classic-name` flag:
`generateClassicCertReuse()` signs an ordinary classical RSA leaf cert (no
PQC material, no dual nested combiner) with the project's local CA
(`ca.crt`/`ca.key`), reusing the RSA keypair that already existed on disk
for each identity (`root_ca.key`/`issuer_ca.key`, generated back in
Decision 11 as the classical half of the hybrid stand-ins) rather than
minting a fresh one -- keeping exactly one RSA keypair per participant
identity shared across all three profiles. Run via the established
`docker run golang:1.27-rc-alpine` toolchain:
`go run . -classic-name root_ca && go run . -classic-name issuer_ca`.
Output: `root_ca.crt`/`issuer_ca.crt`, 5-year validity (`longLivedValidity`).

- `mock_mtls/main.go`: new `case "classic":` branch in `init()`'s
  `CRYPTO_PROFILE` switch, setting `rootCaServeFilePath`/
  `issuerCaServeFilePath` to the new files -- previously classic fell
  through to the package defaults, which pointed at the **pqc** stand-ins
  (`rootCaPqcFilePath`/`issuerCaPqcFilePath`), silently wrong for classic
  even before this decision's real-external dependency was the live
  problem.
- `opin_flow.py`: `fetch_server_keys_and_ca()`'s `ca_host` selector
  simplified from `"directory" if crypto_profile in ("pqc", "hybrid") else
  "crl.sandbox.pki.opinbrasil.com.br"` to an unconditional `"directory"` --
  all three profiles now resolve locally.

**Verified**: `openssl verify -CAfile ca.crt` OK for both new certs.
Fetched live from inside the `mtls` container
(`https://directory/root-ca.pem`/`/issuer-ca.pem`) and confirmed
byte-for-byte the new classical stand-ins, not the pqc ones. DER sizes:
`root_ca.crt` 1515 bytes, `issuer_ca.crt` 1519 bytes -- smaller than both
pqc (2947/2951) and hybrid (6853/6857) stand-ins, as expected for a
pure-RSA leaf cert with no PQC extensions.

## 2. Container reconciliation sequence for `CRYPTO_PROFILE` switching -- two real bugs found only by running the pilot live

**Context.** The pilot's first live run (Classic, 0ms) failed twice, neither
failure caused by this session's own code changes -- both traced to stale
container/database state left over from earlier hybrid-mode testing
earlier in the same session, exposed only because this was the first time
in this session `CRYPTO_PROFILE=classic` was actually re-driven end-to-end
after that hybrid work.

**Bug 1 -- `auth` container running with a stale `CRYPTO_PROFILE`.**
`docker-compose --profile main up -d --build --force-recreate mtls` (to
pick up Decision 1's `mock_mtls/main.go` change) also force-recreated
`localstack` as a dependency, but left `auth`/`mockapi` untouched. The
first flow attempt failed at `POST /token` with `invalid_client: client
authentication failed, detail=alg mismatch`. Root cause, confirmed by
`docker exec auth sh -c 'echo $CRYPTO_PROFILE'`: the running `auth`
container still had `CRYPTO_PROFILE=hybrid` baked into its process
environment from its last recreation (a prior hybrid-mode session), which
makes `mock_as/utils/opin/configuration.js` compute
`clientSigningAlgs = ['RS256']` instead of classic's `['PS256']` --
`docker-compose restart auth` does **not** re-read `CRYPTO_PROFILE` (or any
`environment:` value), only `up`/`up --force-recreate` does. Confirmed via
the boot log line (`Crypto profile: hybrid ...`) not changing after a
plain `restart`, then changing correctly
(`Crypto profile: classic (signingAlgs: PS256)`) only after
`CRYPTO_PROFILE=classic docker-compose --profile main up -d
--force-recreate auth mockapi` -- `mockapi` recreated in the same command
per the existing `docker-compose.yml` comment (`ResponseSigningService`
reads `CRYPTO_PROFILE` once at JVM boot too, must be recreated alongside
`auth` on every profile switch, never separately).

**Bug 2 -- Mongo's `client_one` registration itself stale.** Recreating
`auth` alone did not fully fix it: the same `alg mismatch` persisted one
more round. `mongosh` inspection of the live `openid-server.client`
collection (TLS required for this project's Mongo, `--tls --tlsCAFile
/certs-src/ca.crt` inside the `mongodb` container) confirmed `client_one`'s
registered JWKS still carried whatever `alg` value `mongo-seed/start.sh`'s
last invocation had written -- and `mongo_seed` is a one-shot init
container, not something `docker-compose up` reruns on its own. Fixed by
explicitly rerunning it: `CRYPTO_PROFILE=classic docker-compose --profile
main run --rm mongo_seed` (drops and reimports the `client` collection
fresh; harmless `E11000 duplicate key` messages on `accounts`/`credentials`
are pre-existing account data the seed script intentionally does not
re-drop).

**The reconciliation sequence this establishes, needed on every profile
switch for the automation in Decision 3 below:**
```
CRYPTO_PROFILE=<profile> docker-compose --profile main up -d --force-recreate mtls auth mockapi
CRYPTO_PROFILE=<profile> docker-compose --profile main run --rm mongo_seed
```
(`mtls` only needs `--build` when its own Go source changed, as in
Decision 1 above; a pure profile switch with no code change only needs
`--force-recreate`.) Neither bug is specific to Classic mode or to this
session's own changes -- both are pre-existing gaps in the
environment-recreation protocol first noted in earlier decisions
(`localstack`-vs-`mtls`/`auth` startup race), now extended to cover
`CRYPTO_PROFILE` itself, not just service startup ordering.

**Verified**: after both fixes, a full live run (both `run_insurance_flow`/
`run_person_flow`, 28 HTTP calls) completed with zero errors under
`CRYPTO_PROFILE=classic`.

## 3. Median automation for size metrics across N runs, and the pilot's result

**Context.** The prior size-metric investigation (this session, undocumented
until now) found no existing cross-run aggregation for size metrics
anywhere in the pipeline -- `jwt_size_avg_bytes` and
`gateway_metrics.handshake_bytes` are within-run means/percentiles only;
Decision 12 in `thesis/results/v4/DECISIONS.md` added a 5-run median for
total-flow **latency** alone, computed manually. `thesis/scripts/
median_automation.py` is the size-metric equivalent, automated: drives
`opin_flow.py`'s own `run_insurance_flow`/`run_person_flow` N times in a
single process (importing `opin_flow.py` as a module, reusing its tested
flow logic verbatim rather than reimplementing it), keeps every run's full
`baseline_metrics.json`-shaped dict under `runs/run{NN}_baseline_metrics.json`
for audit, and computes median/min/max/%-spread across the N runs for
exactly the metrics named in scope: `jwt_size_avg_bytes`,
`gateway_metrics.handshake_bytes.p50_bytes`, `bytes_by_participant` (per
participant, sent/received -- this is where `PKI/CRL` lives),
`total_bytes_exchanged`, and the client certificate's own DER byte size.
Everything else in a run's metrics (per-endpoint latency, handshake
duration, raw `jwt_sizes_bytes`/`jwk_sizes` lists) is preserved per-run but
deliberately **not** aggregated -- out of this decision's scope, matching
the size-metric investigation's own boundary.

Output layout mirrors v3/v4's existing per-scenario convention
(`thesis/results/v5/experiment<N> - <Profile>/<latency>ms/`), adding one new
`runs/` subfolder for the raw per-run captures a single-run methodology
never needed: `median_metrics.json` (medians + min/max/spread, machine-
readable) and `MEDIAN_REPORT.md` (the same, human-readable, plus a
`>5%` spread flag section) sit alongside `runs/`.

**Pilot result (Classic, 0ms, 10 runs, ~4s apart, 51s total)**: every named
metric came back at **exactly 0.0% spread** -- `jwt_size_avg_bytes`
1385.42, `total_bytes_exchanged` 66452, `handshake_bytes.p50_bytes` 9785.0,
`client_cert_der_bytes` 1494, and every `bytes_by_participant` entry
(Client/AS/RS/PKI-CRL, sent+received), all identical across all 10 runs.
Expected, not a red flag: at 0ms injected latency there is no network
jitter to perturb payload *sizes* (only *latency* varies run to run at
0ms -- Decision 12's own reason for needing a median there in the first
place); the flow's byte counts are otherwise fully deterministic. The
higher-latency scenarios (225ms/320ms) are where real size variation is
expected to first appear, specifically from the PAR `request_uri`
expiration retry (see the PAR retry fix, committed separately) adding one
extra `POST /request` call on the rare run where it fires -- that is the
mechanism this automation's `>5%` flag exists to catch.
