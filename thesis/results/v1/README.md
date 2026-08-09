# v1 — Environment Setup and Classical Baseline (Experiment 1)

## Purpose

This was the first stage of the PQC migration thesis work. Before any
cryptography could be migrated or measured, the MockOPIN ecosystem itself
had to be understood and turned into a working, repeatable test bed. The
goals of this stage were to:

- Study the MockOPIN architecture and the end-to-end flow a real Open
  Insurance Brasil (OPIN) participant goes through (Gateway → Authorization
  Server → Resource Server, consent creation through token issuance) — see
  the root [`README.md`](../../../README.md)'s "Architecture Design" and
  "End-to-End Consent Creation Flow" sections, which this stage relied on
  and validated empirically.
- Get the full local environment (mTLS gateway, Auth Server, Resource
  Server, Conformance Suite) running reliably end-to-end, including running
  it fully offline against the local mock Directory instead of Raidiam's
  real sandbox.
- Build the first data-collection tooling and instrument the environment
  for measurement (mTLS handshake metrics, WAN-latency injection).
- Produce the first classical-cryptography baseline metrics — the numbers
  later reviewed and validated with the advisor, and the reference point
  every subsequent experiment (PQC, hybrid) is compared against.

Everything in this folder is the classical (pre-PQC) baseline, driven
end-to-end by the OpenID Conformance Suite acting as the OPIN client.

## What's in this folder

```
v1/
└── experiment1 - Classic/
    ├── baseline/                  first exploratory run (2026-07-20, no injected
    │                                latency) -- superseded by 0ms below, kept for history
    ├── 0ms/ 14ms/ 30ms/ 140ms/ 225ms/ 320ms/   the six WAN-latency scenarios,
    │                                             each with baseline_metrics.json,
    │                                             BASELINE_REPORT.md, and the raw
    │                                             Conformance Suite export logs
    ├── consolidated.json          the six scenarios' summary metrics side by side
    ├── EXPERIMENT1_REPORT.md      human-readable comparative report across all six
    ├── Relatorio_Experimento1_Final.pdf   thesis report section for this experiment
    ├── logs/                      stdout of every run and retry along the way
    └── scripts/
        └── consolidate_experiment1.py     builds consolidated.json/EXPERIMENT1_REPORT.md
```

## Timeline

**2026-07-20 — First automation and offline Conformance Suite.** Wrote the
first version of `baseline_automation.py`: drives the Conformance Suite's
own HTTP API (plan creation, running the "happy path" modules, handling the
manual OAuth login step, exporting logs) to collect classical-crypto
metrics — payload bytes, per-endpoint latency, JWT sizes. Patched the
Conformance Suite's source so it validates against the local mock
Directory instead of requiring Raidiam's real sandbox (see
[`thesis/patches/README.md`](../../patches/README.md)). Also documented a
real cold-start race condition (localstack's healthcheck passing before
SSM/S3 provisioning actually finishes, causing auth/mtls to fail on a
fresh `make run-with-cs`) and its recovery procedure.

**2026-07-30 — Instrumentation for measurement.** Before the six-scenario
run was possible, the environment needed to actually produce the data
points the thesis needed:
- Enabled TLS on the internal Postgres/MongoDB connections and updated
  every consumer (Resource Server, Auth Server, Conformance Suite,
  mongo-seed) to use it — closer to a real deployment, and needed before
  the gateway's own TLS instrumentation would mean anything.
- Instrumented the Go mTLS gateway (`mock_mtls/main.go`) to log
  per-connection handshake metrics — start/end time, negotiated TLS
  version and cipher suite, client certificate size — joined into the
  access log alongside independently measured OPIN request-processing
  time. Purely observational; no change to the negotiated cipher suites,
  TLS version, certificates, or proxy logic.
- Added `set_latency.sh`, injecting artificial WAN latency (0/14/30/140/
  225/320ms) via `tc netem` on the gateway container's own network
  interface — chosen because all OPIN/auth traffic transits that one
  container, and because the Docker bridge interface itself isn't reachable
  from the host shell on Windows + Docker Desktop. Verified against `ping`
  before trusting it for real data.
- Found and fixed a real bug while running the suite manually: the AS's
  error handler crashed trying to render a missing view, turning an
  already-consumed `request_uri` (from a stray browser reload during manual
  login) into an opaque 500 instead of a clear error — this had been
  causing intermittent `INTERRUPTED`/`SessionNotFound` failures during
  testing. Fixed, and the "open the login link exactly once" protocol this
  uncovered is still the one used for every manual login in this thesis
  (documented in every automation script's printed instructions since).

**2026-07-31 — First full six-scenario run.** Ran the classical baseline
across all six WAN-latency scenarios. `opin-consent-api-status-test-v3`
passed reproducibly in all 6; `person_api_core_test-module_v2.0.0` failed
identically in all 6 on a pre-existing mock-data schema issue (the mock
person data's `address` field doesn't validate against either of the
schemas the module expects) — a mock-data limitation unrelated to
cryptography or latency, documented rather than "fixed" since it didn't
block the module this thesis's metrics are built on. Added an iterative,
median-based outlier filter for mTLS handshake samples: keep-alive
connections replay the same cached handshake value for every request they
serve, and without filtering, a handful of genuinely slow connections
produced duplicate-value clusters that defeated a plain P99-based
threshold in samples this small. Added `consolidate_experiment1.py`,
producing the side-by-side `consolidated.json`/`EXPERIMENT1_REPORT.md`
(OPINsize, handshake vs. OPIN-processing time split, bytes by participant,
per-endpoint P50/P95/P99) with a methodological-notes section covering all
of the above, plus the 320ms scenario needing several retries (attributed
at the time to accumulated browser session state across many manual
logins in one sitting, not a deterministic bug).

**2026-08-03 — Clean rerun with handshake wire-byte instrumentation.**
Added `mtlsHandshakeBytes` to the gateway's instrumentation: a
`countingConn` wrapper tallying raw TCP bytes read and written during the
handshake itself (`ClientHello`..`Finished`), independent of TLS record
parsing — the metric expected to move the most once PQC is introduced
(larger KEM public keys/ciphertexts and signatures), unlike
`clientCertBytes`, which only ever covers one certificate. Fixed a
`cs-server` container-restart bug along the way (a `keytool -importcert`
that failed non-zero, and therefore never executed, on any restart that
reused the same filesystem layer). Reran all six scenarios end-to-end after
a mid-session machine reboot recovery; `opin-consent-api-status-test-v3`
passed reproducibly in all 6 with no retries needed this time. Handshake
size came out flat (~11.3–11.5KB mean) across every latency scenario, as
expected for a classical baseline where network latency doesn't change
what's cryptographically negotiated — this flat line is the reference
point the PQC experiments' handshake-size growth is measured against.

**Later — reorganized into this `v1/` folder.** As the thesis moved into
the PQC work (Experiment 2) and needed a completely separate measurement
strategy (see [`thesis/results/v2/experiment2 - PQC/DECISIONS.md`](../v2/experiment2%20-%20PQC/DECISIONS.md)),
the results tree was reorganized into versioned top-level folders so each
stage's data stays self-contained. This folder (`v1`) is the archived,
untouched output of everything described above.

## Known limitations (carried forward, not fixed)

- **Preflight modules always fail.** `opin-consents_api_preflight_test-module_v3`
  (for both plans) depends on Raidiam's real Directory and can't succeed in
  a fully local environment. The traffic is real, but the module result is
  `FAILED` in every scenario, by design of this test environment.
- **`person_api_core_test-module_v2.0.0` fails on a mock-data schema
  issue**, not on anything cryptography- or latency-related (see
  2026-07-31 above). `opin-consent-api-status-test-v3` — the module this
  thesis's core metrics are built on — passed in every scenario of every
  run in this stage.

## Relationship to later stages

The environment, gateway instrumentation, and `baseline_metrics.json`/
`BASELINE_REPORT.md` schema established here are the foundation every later
experiment reuses as-is (`baseline_automation.py`'s helper functions are
imported directly by `thesis/scripts/opin_flow.py`, the PQC-era
measurement tool, rather than reimplemented). Experiment 2 (PQC) discovered
that the Conformance Suite itself cannot act as an mTLS client once a
post-quantum certificate is involved — a structural limitation in the
suite's own compiled code, unrelated to anything built in this stage — and
had to replace the Conformance Suite with a direct Python client
(`opin_flow.py`) for all PQC-onward measurement. See
`thesis/results/v2/experiment2 - PQC/DECISIONS.md` (Decisions 6–8) for the
full investigation.
