# thesis/scripts/

Tooling shared across every experiment in this thesis. Two generations of
tools live here side by side: the Conformance-Suite-driven tools built for
`v1` (still valid, since `v1`'s classical data was collected with them),
and the direct-client tools built for `v2`/`v3` once the Conformance Suite
was found unable to drive PQC traffic (see
[`thesis/results/v2/experiment2 - PQC/DECISIONS.md`](../results/v2/experiment2%20-%20PQC/DECISIONS.md),
Decisions 6–7). Nothing here is tied to one specific experiment's crypto
profile — that's the point of keeping it at this shared level instead of
inside a `results/vN/` folder.

## Virtual environment

`opin_flow.py`'s `pqc` runs need a dependency the machine's global Python
doesn't have reliable support for otherwise, so a dedicated venv lives at
`thesis/scripts/.venv/` (gitignored — recreate it with the commands below,
don't commit it).

**Why:** presenting the ML-DSA-65 client certificate (`client_one_pqc.crt`)
requires an OpenSSL build with ML-DSA support (3.5+). The system/Python-
bundled OpenSSL this was developed against is 3.0.x, which doesn't have it
— `requests` fails with `SSL: EE_KEY_TOO_SMALL` trying to load that
certificate through Python's stdlib `ssl` module. The `cryptography`
package bundles its own, newer OpenSSL independently of the system one;
`pyOpenSSL` + urllib3's `pyopenssl` contrib module route `requests`' TLS
through that bundled copy instead. `opin_flow.py` activates this itself at
import time (see the top of the file) — it only needs `pyOpenSSL` to
actually be installed in whichever `python` runs it. `classic` runs work
fine without any of this; it only matters once `CRYPTO_PROFILE=pqc`.

**This is a project-local venv, not a global install**, specifically so it
doesn't touch (or get affected by) whatever else is installed on the
machine's global Python — installing `pyOpenSSL` globally once pulled in a
`cryptography` upgrade that broke an unrelated tool (`mlflow`) on the
machine this was developed on.

```
cd thesis/scripts
python -m venv .venv
.venv\Scripts\activate          # Windows; source .venv/bin/activate on Linux/macOS
pip install -r requirements.txt
```

Every command below assumes this venv is active (`python` resolving to
`thesis/scripts/.venv/Scripts/python.exe`, not the system Python).

## Scripts

### `opin_flow.py` — the current traffic generator (v2/v3-onward)

Drives the OPIN consent flow directly against the Authorization Server and
Resource Server — no Conformance Suite involved. Replicates the exact call
sequence the Conformance Suite's own modules made in `v1`
(`opin-consent-api-status-test-v3` and `person_api_core_test-module_v2.0.0`),
validated call-for-call against `v1`'s raw exported logs. See its own
module docstring for the full call breakdown, and
[`thesis/results/v3/README.md`](../results/v3/README.md) for how it came
to be built and the bugs found along the way.

```
CRYPTO_PROFILE=classic|pqc EXPERIMENT_NUMBER=1|2|3 RESULTS_VERSION=v3 \
  python opin_flow.py <latency_ms>
```

- `CRYPTO_PROFILE` picks `client_one`'s mTLS certificate (classical or
  ML-DSA-65) — must match whatever the AS/RS containers were started with.
- `EXPERIMENT_NUMBER`/`RESULTS_VERSION` pick the output folder:
  `thesis/results/{RESULTS_VERSION}/experiment{EXPERIMENT_NUMBER}*/{latency_ms}ms/`
  (the folder must already exist).
- `<latency_ms>` must be one of `0 14 30 140 225 320` — it also triggers
  the WAN-latency injection itself (see `set_latency.sh` below; this script
  does **not** shell out to it, it reimplements the same `docker exec
  tc qdisc` calls directly, since which `bash` ends up on `PATH` turned out
  to be environment-dependent on Windows).
- Pauses twice (once per flow) for a **real, manual browser login** —
  prints the URL, waits for ENTER. Protocol: open the link once, don't
  reload, leave the consent screen's selections at their default, confirm.
- Imports and reuses `baseline_automation.py`'s metrics/report machinery
  (see below) rather than reimplementing it, so both tools produce
  identically-shaped `baseline_metrics.json`/`BASELINE_REPORT.md`.

### `baseline_automation.py` — the original traffic generator (v1) and shared metrics engine

Two roles in one file:

1. **Conformance-Suite driver** (`v1`'s own tool, still runnable as-is):
   drives the suite's HTTP API — creates a plan, runs its "happy path"
   modules, handles the manual OAuth interaction, exports the raw logs —
   for the two plans this thesis uses (`Insurance consents api test
   V3.0.0`, `person_test-plan_v2.0.0`). Requires the full MockOPIN
   environment *with* the Conformance Suite running (`make run-with-cs`)
   and the patches in [`thesis/patches/`](../patches/README.md) applied.
   ```
   python baseline_automation.py <latency_ms>
   ```
   Unlike `opin_flow.py`, this script does **not** inject latency itself —
   run `set_latency.sh` first (see below).

2. **Shared metrics engine**, imported by `opin_flow.py` rather than
   duplicated: byte/JWT/JWK extraction (`header_bytes`, `extract_jwts`,
   `extract_jwk_sizes`, `classify_participant`), gateway log parsing
   (`collect_gateway_metrics`), statistics (`percentile`, `latency_stats`,
   `size_stats`, `filter_handshake_outliers`,
   `dedupe_handshake_samples_by_connection`), and report generation
   (`compute_metrics`, `write_report_md`). `parse_calls()` (turning a raw
   Conformance Suite export into the same `calls` shape `opin_flow.py`
   builds directly) is the one piece that's CS-specific and not reused.

   `dedupe_handshake_samples_by_connection()` is the newer of the two: it
   samples one handshake value per physical TCP connection rather than per
   HTTP request, which mattered once `opin_flow.py` started reusing
   connections (see `thesis/results/v3/README.md` for the concrete before/
   after numbers) — it has no effect on `v1`'s own already-archived data,
   since the Conformance Suite rarely reused a connection in the first
   place.

### `consolidate_experiment.py` — builds the side-by-side report across all six scenarios

Reads the six per-scenario `baseline_metrics.json` files for one
experiment and combines them into `consolidated.json` (machine-readable,
six scenarios side by side) and `EXPERIMENT{N}_REPORT.md`
(human-readable: OPINsize, handshake vs. OPIN-processing split,
handshake wire-size, bytes by participant, per-endpoint P50/P95/P99).

```
RESULTS_VERSION=v3 EXPERIMENT_NUMBER=1 python consolidate_experiment.py
```

Generalizes `v1`'s original, folder-specific
[`consolidate_experiment1.py`](../results/v1/experiment1%20-%20Classic/scripts/README.md)
— same output shape, but driven by env vars instead of being hardcoded to
one path, so every experiment reuses this one script instead of each
getting its own copy.

### `set_latency.sh` — WAN latency injection (crypto-agnostic)

Injects or removes artificial latency (`0 14 30 140 225 320` ms) via
`tc netem` on the mTLS gateway container's own network interface — chosen
because all OPIN/auth traffic transits that one container, and because the
Docker bridge interface itself isn't reachable from the host shell on
Windows + Docker Desktop.

```
./set_latency.sh <ms>       # or: ./set_latency.sh reset
```

Used as a **separate, manual pre-step** before `baseline_automation.py`
runs. `opin_flow.py` does not call this script — it reimplements the same
`tc qdisc` logic internally (its own `set_latency()` function) and runs it
automatically at the start of every scenario, so nothing extra needs to be
run before it.

### `check_plan_modules.py` — one-off diagnostic

Creates a Conformance Suite plan from `config_template_consents_v3.json`
and prints every module name and variant the suite recognizes for it.
Not part of any regular workflow — useful only when adding a new plan to
`baseline_automation.py`'s `PLANS` list, to get the exact module name
right before wiring up a real run.

## Which tool should I use?

| | `baseline_automation.py` | `opin_flow.py` |
|---|---|---|
| Traffic driver | Conformance Suite | Direct HTTP client |
| Works with `CRYPTO_PROFILE=pqc` | No (see Decisions 6–7) | Yes |
| Latency injection | Manual (`set_latency.sh` first) | Automatic |
| Used for | `v1` only (classical, archived) | `v2`/`v3` onward, every experiment |

For any new experiment (Experiment 2 PQC, Experiment 3 hybrid, ...), use
`opin_flow.py` + `consolidate_experiment.py`. `baseline_automation.py`
stays here because `opin_flow.py` imports its metrics engine, and because
`v1`'s results should stay reproducible from the tool that actually
produced them.
