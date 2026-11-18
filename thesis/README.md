# Thesis — Post-Quantum Migration of the OPIN Ecosystem

Tooling and data for the doctoral thesis on migrating the Open Insurance
Brasil (OPIN) consent flow from classical to post-quantum (PQC) and hybrid
cryptography, using the local **MockOPIN** environment (this repository) as
the test bed.

**Three measurement campaigns, all still relevant — see the root
[`README.md`](../README.md#why-three-campaigns-v7-v8-v9) for the full
rationale:**

- **[`results/v7/`](results/v7/)** — the pre-qualification, **simulated**
  WAN-latency (`tc`/`netem`) baseline. Historical, but **not superseded**:
  start with [`results/v7/Consolidated_Metrics_Report_FINAL.md`](results/v7/Consolidated_Metrics_Report_FINAL.md)
  for the numbers and the measured-system architecture (folded into this
  same file since 2026-09-25; the former standalone `ARCHITECTURE.md` no
  longer exists), and [`results/v7/DECISIONS.md`](results/v7/DECISIONS.md)
  for the engineering decisions behind that setup.
- **[`results/v8/`](results/v8/)** — the thesis's first **real**-AWS
  cross-region latency campaign. Additive to v7, not a replacement — see
  `results/v8/README.md`.
- **[`results/v9/`](results/v9/)** — a second, independent real-AWS
  campaign (new AWS account), with a generalized orchestrator, a fourth
  diagnostic **Control** profile, a corrected OPINsize formula, and two
  supplementary post-campaign investigations ("Degrau 1"/"Degrau 2"). This
  is the **most recent and most complete** real-network campaign — see
  `results/v9/README.md` and `results/v9/DECISIONS.md`. The official,
  frozen campaign is identified by tag `v9-campanha-oficial-final`, commit
  `c05dcb364192bc193e99704dea2aae5a33b8ae21` — **any reproducibility check
  must diff against that commit, never against the current branch tip.**

Earlier rounds (`v1`–`v6`) are preserved as historical record — each one
documents, in its own `DECISIONS.md`, what changed and why it was
superseded — but their numbers are not the ones to cite.

## The experiment

Three (v7/v8) or four (v9) cryptographic profiles of the same OPIN consent
flow are compared:

| Profile | X.509 certificate signature | JWT signature | TLS key exchange |
|---|---|---|---|
| Classic | RSA, PKCS1v1.5/SHA-256 (`sha256WithRSAEncryption` — X.509 almost never uses RSA-PSS) | PS256 (RSASSA-PSS) | ECDHE, single P-384 curve |
| PQC | ML-DSA-65 (NIST FIPS 204) end to end — leaf certificate self-signed by an ML-DSA-65 root (no classical signature anywhere in the chain) | ML-DSA-65 | Pure ML-KEM-1024 (NIST FIPS 203) |
| Hybrid | RSA, PKCS1v1.5/SHA-256 — **the same as Classic**. ML-DSA-65 material is present only as three inert, non-critical X.509 extensions the TLS handshake itself never reads (confirmed in `mock_mtls/main.go`) | Dual-signed, at the JWT layer only: `RS256` for client-issued artifacts (payload-extension, the ML-DSA-65 signature rides as an embedded `pqc` claim) and the composite `MLDSA65-RSA2048-PSS-SHA256` for AS-issued artifacts (Strong Nesting) | SecP384r1MLKEM1024 (P-384 + ML-KEM-1024) — the key EXCHANGE is genuinely hybrid; only the certificate's own signature stays classical |
| Control (v9 only) | Same as Hybrid, diagnostic/support profile | Same dual-signature scheme as Hybrid | Same as Hybrid — isolates whether an effect is specific to the *Hybrid design choice* or a general property of running dual signatures |

Each profile drives the same complete flow (consent, PAR, automated login,
token exchange, resource queries — 28 or 44 HTTP calls across two
sub-flows, depending on the campaign) and is measured for both **size**
(bytes of cryptographic material, via the OPINsize equation extended in
this thesis with a fourth, PKI term) and **latency** (`T_fluxo`, across
real or emulated WAN-latency scenarios). See
`results/v7/Consolidated_Metrics_Report_FINAL.md`
for the full system diagram and measurement methodology (v8/v9 reuse the
same measured system, run against real AWS inter-region latency instead of
emulated latency).

## Structure

```
thesis/
├── README.md             this file
├── docs/                  SAD-vs-implementation coverage notes
├── patches/               patched Conformance Suite source files (see patches/README.md
│                           -- needed because that folder is cloned on demand and gitignored)
├── config/                validated Conformance Suite plan configs (used by v1's tooling)
├── scripts/               all automation shared across experiments -- see scripts/README.md
│   ├── opin_flow.py             drives the actual OPIN flow directly (client_credentials,
│   │                             consent, PAR, login, token exchange, resource queries) --
│   │                             used by every experiment from v2 onward
│   ├── switch_crypto_profile.py   switches CRYPTO_PROFILE, rebuilds/restarts the
│   │                                affected containers, and waits for the environment
│   │                                to settle before releasing it for measurement
│   ├── median_automation.py    size-metric batches: N runs per scenario, writes
│   │                             median_metrics.json + MEDIAN_REPORT.md
│   ├── latency_automation.py   latency batches: N runs per scenario, writes
│   │                             median_metrics.json + report.md
│   ├── tls_kem_proxy/           Go TLS client bridging the key-exchange groups
│   │                             (MLKEM1024, SecP384r1MLKEM1024, ...) that the
│   │                             Python/OpenSSL stack driving opin_flow.py can't negotiate
│   ├── pqc-signer/               ML-DSA-65 signer for the client side (Node.js,
│   │                             native node:crypto) -- a persistent HTTP service,
│   │                             reused across every signature in a run
│   ├── verify_kem_export/        standalone Go tool proving a TLS group actually
│   │                             derived a fresh session key (RFC 5705 export),
│   │                             not just that the log says so
│   ├── audit_v7_from_raw.py      independent audit: recomputes every v7 reported
│   │                             metric straight from the raw run files, no shortcuts
│   └── opinsize_v9_oficial.py    v9's OPINsize formula/constants (see results/v9/DECISIONS.md,
│                                  Decisions 216-217, for the id_token correction)
└── results/
    ├── v7/                simulated-latency campaign (size/, latency/, artifacts/ -- real
    │                       captured, cryptographically verified artifacts per profile,
    │                       DECISIONS.md, Consolidated_Metrics_Report_FINAL.md)
    ├── v8/                first real-AWS cross-region latency campaign (additive to v7)
    ├── v9/                second, independent real-AWS campaign -- generalized topology,
    │                       Control profile, corrected OPINsize, Degrau 1/Degrau 2
    │                       supplementary investigations; see results/v9/README.md
    └── v1 .. v6/          earlier rounds, superseded but preserved as history
                            (each one's own DECISIONS.md explains why it was superseded)
```

## Running the experiment

The automation depends on the full MockOPIN environment running (see the
[repository root README](../README.md) for `make run`/`make run-with-cs`
setup) and needs its own virtual environment — see
[`scripts/README.md`](scripts/README.md) for why and how to create it.

To switch the active cryptographic profile and collect one scenario
(v7-style local/simulated-latency run):

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

**v8 and v9 are real-AWS campaigns, not local runs** — reproducing them
means standing up real AWS infrastructure via the Terraform and
orchestration scripts under `results/v8/campaign/` and
`results/v9/campaign/`, which is a different, much more involved process
than the local `v7` loop above. See `results/v8/README.md` and
`results/v9/README.md` for campaign-specific prerequisites, cost, and
step-by-step reproduction instructions, and the
[tag/commit/re-verification note in the root README](../README.md#the-official-v9-campaign-tag-commit-and-re-verification)
before attempting to re-verify any already-collected v9 data.

**Signature verification (v8/v9, "fluxo completo" turn).** `opin_flow.py`
cryptographically verifies every signed artifact it receives (id_token,
JARM, RS-signed responses) in every `CRYPTO_PROFILE` value, through one
uniform mechanism (`verify_jwt()`/`decrypt_and_verify_jwt()`, always
routed through `pqc-signer/`'s own persistent service, classic included,
so a measured timing difference reflects the algorithm, not the
verification architecture) -- `verify_signature=False` no longer appears
anywhere in this file. `pqc-signer/signer_core.mjs` auto-detects hybrid's
two independently-evolved dual-signature schemes (Strong Nesting for
id_token/JARM, payload extension for RS responses) by signature shape.
Mandatory negative tests (tampered signature, wrong key, wrong
algorithm) live in `tests/test_signature_verification.py`, run per
profile: `CRYPTO_PROFILE=<classic|pqc|hybrid> python -m pytest
tests/test_signature_verification.py` (needs the local stack up). Full
detail, the per-artifact/per-profile audit table, and the one documented
exception (id_token's own JWE encryption stays classical in every
profile, a pre-existing, deliberate decision) are in `results/v8/
DECISIONS.md`, Decision 87; v9 corrects a related gap in how the
id_token's *internal* signature bytes were counted in OPINsize — see
`results/v9/DECISIONS.md`, Decisions 216-217.

## Metrics collected

- **OPINsize** — the flow's total cryptographic-material size: mTLS
  handshake bytes, JWT sizes, published JWK sizes, and (this thesis's
  extension) CA certificate bytes.
- **Latency per endpoint and `T_fluxo`** — where in the flow the
  post-quantum cost shows up, and how the complete flow behaves across
  real (v8/v9) or emulated (v7) WAN-latency scenarios.
- **Bytes per participant** — AS/RS/Directory egress, for estimating
  cloud-egress cost of the migration.

See each campaign's own
`Consolidated_Metrics_Report_FINAL.md` (methodology and results) and each campaign's
`DECISIONS.md` (the full methodological trail, including every deviation,
correction, and independent audit) for full detail.
