# scripts/ (v1-specific)

## `consolidate_experiment1.py`

Reads the six per-scenario `baseline_metrics.json` files in
`../{0,14,30,140,225,320}ms/` and builds `../consolidated.json` and
`../EXPERIMENT1_REPORT.md` — the six WAN-latency scenarios' metrics side
by side (OPINsize, mTLS handshake vs. OPIN-processing time, handshake
wire-size, bytes by participant, per-endpoint P50/P95/P99).

This is the original version of this tool, hardcoded to this exact folder.
It has been superseded by
[`thesis/scripts/consolidate_experiment.py`](../../../../scripts/README.md),
which does the same thing for any experiment/results-version via env vars
instead of a hardcoded path. Kept here, unmodified, so `v1`'s own results
stay reproducible from the exact script that produced them — not reused
for anything past `v1`.
