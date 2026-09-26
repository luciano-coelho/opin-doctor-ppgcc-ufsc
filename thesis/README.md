# Thesis — Post-Quantum Migration of the OPIN Ecosystem

Tooling and data for the doctoral thesis on migrating the Open Insurance
Brasil (OPIN) consent flow from classical to post-quantum (PQC) and hybrid
cryptography, using the local **MockOPIN** environment (this repository) as
the test bed.

**The final, official results are in [`results/v7/`](results/v7/)** —
start with [`results/v7/Consolidated_Metrics_Report_FINAL.md`](results/v7/Consolidated_Metrics_Report_FINAL.md)
for the consolidated numbers, [`results/v7/ARCHITECTURE.md`](results/v7/ARCHITECTURE.md)
for how the measured system works, and [`results/v7/DECISIONS.md`](results/v7/DECISIONS.md)
for the engineering decisions and investigations behind the final setup.
Earlier rounds (`v1`–`v6`) are preserved as historical record — each one
documents, in its own `DECISIONS.md`, what changed and why it was
superseded — but their numbers are not the ones to cite.

## The experiment

Three cryptographic profiles of the same OPIN consent flow are compared:

| Profile | Signatures | TLS key exchange |
|---|---|---|
| Classic | RSA (PS256) | ECDHE, single P-384 curve |
| PQC | Pure ML-DSA-65 (NIST FIPS 204); certificates issued by an RSA CA | Pure ML-KEM-1024 (NIST FIPS 203) |
| Hybrid | RSA + ML-DSA-65 combined (dual-signed certificates, payload-extension JWTs, Strong Nesting on the `id_token`/JARM) | SecP384r1MLKEM1024 (P-384 + ML-KEM-1024) |

Each profile drives the same complete flow (consent, PAR, automated login,
token exchange, resource queries — 28 HTTP calls across two sub-flows) and
is measured for both **size** (bytes of cryptographic material, via the
OPINsize equation extended in this thesis with a fourth, PKI term) and
**latency** (`T_fluxo`, across six emulated WAN-latency scenarios). See
`results/v7/ARCHITECTURE.md` for the full system diagram and measurement
methodology.

## Structure

```
thesis/
├── README.md            this file
├── docs/                 SAD-vs-implementation coverage notes
├── patches/              patched Conformance Suite source files (see patches/README.md
│                          -- needed because that folder is cloned on demand and gitignored)
├── config/               validated Conformance Suite plan configs (used by v1's tooling)
├── scripts/              all automation shared across experiments -- see scripts/README.md
│   ├── opin_flow.py            drives the actual OPIN flow directly (client_credentials,
│   │                            consent, PAR, login, token exchange, resource queries) --
│   │                            used by every experiment from v2 onward
│   ├── switch_crypto_profile.py   switches CRYPTO_PROFILE, rebuilds/restarts the
│   │                                affected containers, and waits for the environment
│   │                                to settle before releasing it for measurement
│   ├── median_automation.py    size-metric batches: N runs per scenario, writes
│   │                            median_metrics.json + MEDIAN_REPORT.md
│   ├── latency_automation.py   latency batches: N runs per scenario, writes
│   │                            median_metrics.json + report.md
│   ├── tls_kem_proxy/           Go TLS client bridging the key-exchange groups
│   │                            (MLKEM1024, SecP384r1MLKEM1024, ...) that the
│   │                            Python/OpenSSL stack driving opin_flow.py can't negotiate
│   ├── pqc-signer/              ML-DSA-65 signer for the client side (Node.js,
│   │                            native node:crypto) -- a persistent HTTP service,
│   │                            reused across every signature in a run
│   ├── verify_kem_export/       standalone Go tool proving a TLS group actually
│   │                            derived a fresh session key (RFC 5705 export),
│   │                            not just that the log says so
│   └── audit_v7_from_raw.py     independent audit: recomputes every reported metric
│                                  straight from the raw run files, no shortcuts
└── results/
    ├── v7/                **final, official** -- size/, latency/, artifacts/ (real
    │                       captured, cryptographically verified artifacts per profile),
    │                       DECISIONS.md, ARCHITECTURE.md, Consolidated_Metrics_Report_FINAL.md
    └── v1 .. v6/          earlier rounds, superseded but preserved as history
                            (each one's own DECISIONS.md explains why it was superseded)
```

## Running the experiment

The automation depends on the full MockOPIN environment running (see the
[repository root README](../README.md) for `make run`/`make run-with-cs`
setup) and needs its own virtual environment — see
[`scripts/README.md`](scripts/README.md) for why and how to create it.

To switch the active cryptographic profile and collect one scenario:

```bash
cd thesis/scripts
python switch_crypto_profile.py pqc            # classic | pqc | hybrid
python median_automation.py 0 --runs 10 --results-version v7/size --experiment-number 2
python latency_automation.py 0 --runs 10 --results-version v7 --experiment-number 2
```

`opin_flow.py` can also be run directly for a single execution
(`CRYPTO_PROFILE=pqc python opin_flow.py 0`), and the `_capture_*.py`
one-shot scripts under `scripts/` regenerate the individual proof artifacts
under `results/v7/artifacts/<profile>/`.

## Metrics collected

- **OPINsize** — the flow's total cryptographic-material size: mTLS
  handshake bytes, JWT sizes, published JWK sizes, and (this thesis's
  extension) CA certificate bytes.
- **Latency per endpoint and `T_fluxo`** — where in the flow the
  post-quantum cost shows up, and how the complete flow behaves across six
  emulated WAN-latency scenarios.
- **Bytes per participant** — AS/RS/Directory egress, for estimating
  cloud-egress cost of the migration.

See `results/v7/ARCHITECTURE.md` (methodology) and
`results/v7/Consolidated_Metrics_Report_FINAL.md` (results) for the full
detail.
