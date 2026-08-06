# Thesis — Baseline Automation (PQC Migration)

Tooling and data collected for the doctoral thesis on migrating from classical to post-quantum (PQC) cryptography in the Open Insurance Brasil (OPIN) ecosystem, using the local **MockOPIN** environment as the test bed.

## Structure

Each experiment (classical baseline, PQC, hybrid, ...) owns a self-contained
folder under `results/`, with its own results, run logs, and any
experiment-specific script. Tooling that isn't tied to a particular
cryptography (running the Conformance Suite plans, injecting WAN latency,
patching the suite itself) stays shared at the top level so later
experiments reuse it as-is instead of duplicating it.

```
thesis/
├── README.md                     this file
├── scripts/
│   ├── baseline_automation.py    main automation: creates plans, runs the
│   │                              "happy path" modules, exports logs, and
│   │                              computes the metrics -- reused by every
│   │                              experiment (output folder driven by the
│   │                              latency-scenario CLI arg)
│   ├── check_plan_modules.py     quick diagnostic script — creates a plan
│   │                              and prints the exact module names the
│   │                              Conformance Suite recognizes (useful
│   │                              before adding a new plan to PLANS)
│   └── set_latency.sh            injects/removes tc/netem WAN latency on
│                                   the mTLS gateway container, crypto-agnostic
├── config/
│   ├── config_template_consents_v3.json   validated config for the
│   │                                        "Insurance consents api test V3.0.0" plan
│   └── config_template_person_v2.json     validated config for the
│                                            "person_test-plan_v2.0.0" plan
├── patches/
│   └── ...                                 patched versions of Conformance Suite
│                                            source files (see patches/README.md —
│                                            needed because that folder is cloned
│                                            on demand and gitignored)
└── results/
    └── experiment1 - Classic/    Experiment 1: classical-cryptography baseline
        ├── baseline/                       first exploratory single run (2026-07-20,
        │                                     no injected latency) -- superseded by
        │                                     the 0ms scenario below, kept for history
        ├── 0ms/ 14ms/ 30ms/ 140ms/ 225ms/ 320ms/   the six WAN-latency scenarios
        │                                             (baseline_metrics.json + raw
        │                                             Conformance Suite logs per scenario)
        ├── consolidated.json      the six scenarios' summary metrics side by side
        ├── EXPERIMENT1_REPORT.md  human-readable comparative report
        ├── Relatorio_Experimento1_Final.pdf   thesis report section for this experiment
        ├── logs/
        │   ├── execution_log_20260720.txt     full stdout of the baseline/ run
        │   └── run_*.log, redo_*.log          stdout of each scenario run/retry
        └── scripts/
            └── consolidate_experiment1.py     builds consolidated.json/EXPERIMENT1_REPORT.md
                                                 from the six scenarios above
```

## Infrastructure prerequisites

The automation depends on the full MockOPIN environment running (`make run-with-cs` at the project root), **with patches applied to the Conformance Suite source** (preserved in [`patches/`](patches/README.md) since that folder is cloned on demand and gitignored) — without them the suite tries to validate against Raidiam's real sandbox Directory and fails immediately:

| File (in `insurance-server-lambdas/conformance-suite/src/main/java/net/openid/conformance/opin/testmodule/support/`) | Change |
|---|---|
| `OpinSetDirectoryInfo.java` | uses `directory.discoveryUrl`/`apibase`/`keystore` from the config instead of Raidiam's hardcoded sandbox URLs |
| `CheckOpinDirectoryApiBase.java` | accepts `https://directory/` as a valid URL (in addition to Raidiam's) |
| `CheckOpinDirectoryDiscoveryUrl.java` | accepts `https://directory/.well-known/openid-configuration` as a valid URL |
| `OpinCallDirectoryParticipantsEndpoint.java` | builds the `/participants` URL from `directory.apibase` instead of a hardcoded one |

After changing any of these files you need to rebuild (`make setup-cs` — build phase, ~15-20min) and recreate the container: `docker-compose up -d --force-recreate cs-server`.

**Note on `preflight`:** even with the patches, the `opin-consents_api_preflight_test-module_v3` module always ends with `result=FAILED`. This comes from two conditions built into the suite's own core library (`OpinCheckDirectoryDiscoveryUrl`/`OpinCheckDirectoryApiBase`, shipped inside a dependency `.jar` — not editable) that insist on the real Raidiam Directory. Since they're `continue-on-failure`, the rest of the flow runs normally and the real traffic is captured in the log — only the result label ends up wrong. This is expected and documented in the script itself.

## Configs (`config/`)

Both files **must** use `"alias": "mock"` — the Conformance Suite builds the OAuth `redirect_uri` as `https://.../test/a/{alias}/callback`, and the only `redirect_uri` registered for `client_one` (in `insurance-server-lambdas/software_statement.json`) is `.../test/a/mock/callback`. Any other alias breaks authentication with `redirect_uri did not match any of the client's registered redirect_uris`.

Certificates, JWKS, and CA used in the configs come from `mock-service-os/certs/` (client_one).

## How to run

```bash
cd thesis/scripts
python baseline_automation.py
```

Some modules (the ones that actually create/query a consent) pause at `status=WAITING` waiting for manual login + consent — the script prints the URL to the terminal and keeps polling on its own once it detects the real redirect. Mock user credentials: `usuario1@seguradoramodelo.com.br` / `P@ssword01`.

To investigate a new plan before automating it:

```bash
python check_plan_modules.py
```

## Metrics collected

- **Total bytes exchanged** across the full flow (classical OPINsize) — sum of headers + body for every real HTTP call.
- **Latency per endpoint** — mean, P50, P95, P99, computed from the request/response timestamps in the suite's log.
- **Size of every JWT** found in the payloads (client assertions, request objects, tokens) — the central data point for comparing against PQC signature sizes.
- **Total number of HTTP requests** in the flow.

These metrics make up the classical-cryptography baseline; the next step of the research is to repeat the collection with PQC algorithms enabled and compare.
