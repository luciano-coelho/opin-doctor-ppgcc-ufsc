# Light flow check fixtures (2026-10-21)

Real, unmodified `campaign_client_runner.py` JSON output (one full flow per
crypto profile), captured directly against the local MockOPIN stack during
the 2026-10-21 light flow check (`DECISIONS.md`, `METRICS_COVERAGE.md`).
Not synthetic data -- these are `used by test_consolidate_v8.py` to drive
`consolidate_v8.py` end-to-end with real per-call bytes/JWT/JWK data,
reshaped into the campaign's own `runs/run{NN}.json` +
`runs/run{NN}.calls.jsonl` layout.

The ONE field none of these captures can supply -- `gateway_metrics.
handshake_bytes` (mTLS handshake bytes; needs a pcap extractor that does
not exist yet, see METRICS_COVERAGE.md) -- is injected separately by the
test itself, as an explicitly tagged `_FIXTURE` value, never silently
merged into this real data.
