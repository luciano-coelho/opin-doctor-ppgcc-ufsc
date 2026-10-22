# Light flow check fixtures (2026-10-21)

Real, unmodified `campaign_client_runner.py` JSON output (one full flow per
crypto profile), captured directly against the local MockOPIN stack during
the 2026-10-21 light flow check (`DECISIONS.md`, `METRICS_COVERAGE.md`).
Not synthetic data -- these are `used by test_consolidate_v8.py` to drive
`consolidate_v8.py` end-to-end with real per-call bytes/JWT/JWK data,
reshaped into the campaign's own `runs/run{NN}.json` +
`runs/run{NN}.calls.jsonl` layout.

`{profile}_gateway.log` (added 2026-10-22, during the follow-up
investigation into the mTLS handshake bytes term): real `docker logs -t`
output from the local `insurance-server-lambdas-mtls-1` gateway,
captured during an actual `switch_crypto_profile.py` settling sequence
for each profile, then sliced down to exactly one execution's own window
(the last 6 client-facing handshakes + their paired internal AS-to-RS
handshakes, by timestamp) so it matches the shape a real campaign run's
own `_slice_gateway_log_live()` produces. This is what resolved the
earlier (wrong) "needs a pcap extractor" classification -- the gateway
already logs `mtlsHandshakeBytes` per connection
(`mock_mtls/main.go`'s `countingConn`), unchanged since v7. No field in
this fixture set is synthetic; nothing here is tagged `_FIXTURE`.
