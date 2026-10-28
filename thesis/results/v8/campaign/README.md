# Phase 4 campaign infrastructure (Decision 49)

Prepared, **not applied**. Four commands, run in this order, always with
the author present for `campaign_up.sh` and `campaign_down.sh` (both
touch real AWS resources):

```
cp scripts/campaign.vars.example.sh scripts/campaign.vars.local.sh
# edit campaign.vars.local.sh with your own key paths

scripts/campaign_up.sh   scripts/campaign.vars.local.sh   # terraform apply + key/inventory distribution + connectivity/clock check
scripts/campaign_pull.sh scripts/campaign.vars.local.sh   # idempotent, sha256-verified data pull (run as often as you like during the campaign)
scripts/campaign_down.sh scripts/campaign.vars.local.sh   # refuses to destroy without a verified pull, unless --force
```

`campaign_run.py` is not invoked directly by the operator -- `deliver_source.sh`
installs it on the control instance as a systemd service
(`templates/campaign_run.service`), which starts the orchestrator there,
not here. (Pilot item 1, this turn: this line previously credited
`campaign_up.sh` with this, and no script actually did it at all -- the
unit file didn't exist anywhere in the repository and `campaign_run.py`
was never delivered to control. Found live, trying to start the pilot's
own 60 executions; fixed by extending `deliver_source.sh`, which already
extracts its tarball onto every server/client, to also extract it onto
control itself and install/reload the unit there.)

Window start times (Decision 34/40 -- "spread across the day") default
to now+2h/+10h/+20h if not overridden; set
`MOCKOPIN_WINDOW1_START_UTC`/`_WINDOW2_`/`_WINDOW3_` (ISO-8601 UTC) in
the vars file for explicit times instead.

## Topology (Decision 41)

10 instances: 3 servers (`sa-east-1`, `us-east-1`, `ap-northeast-1`), 6
clients (`sa-east-1` co-located for L0, `ca-central-1` x2 -- one per
server it talks to, `eu-north-1`, `ap-southeast-1`, `ap-northeast-2`),
1 control instance (`sa-east-1`, outside every measured path).

## Light flow check (no DinD/DooD nesting) and the consolidated report (Decision 76)

The heavy local rehearsal (nested Docker, one container per role) was
abandoned (Decision 76, superseding part of Decision 75's own resume
list) -- it does not represent the real target instance and crashed
Docker Desktop once already. The real AWS pilot itself is now the
delivery-and-resume rehearsal; locally, only a **light** check remains
useful: one `amazonlinux:2023` container (the real target's own x86_64
architecture), `--memory=8g --cpus=2` (the campaign's own
`m7i-flex.large` sizing), `install_common_packages.sh` run for real
inside it, then `opin_flow.py`/`campaign_client_runner.py` run for a
COMPLETE flow (not just imported) under that container's real Python
3.9, against the local MockOPIN stack, one profile at a time via
`switch_crypto_profile.py`. No DinD, no nested `dockerd`: the proxy/
signer helper containers are instead rewired, only at the test-driver's
`subprocess.run` layer (never in `opin_flow.py` itself), to join the
check container's own network namespace. See Decision 76 for the exact
mechanism and what it found.

**Consolidated report.** `thesis/results/v8/campaign/scripts/
consolidate_v8.py <v8-latency-root> <output-dir>` reads the real
`v8/latency/experiment{1,2,3} - {Classic,PQC,Hybrid}/{server}/
{scenario}/runs/` tree this campaign produces and writes
`consolidated.json` (source) + `CONSOLIDATED_REPORT.md` (derived), with
the same field structure as v7's own `report_data_v7.json`/
`Consolidated_Metrics_Report_FINAL.md` wherever v8's data supports it,
plus the new metrics (RTT, packet-loss upper bound, RTT jitter,
CPU/steal/memory, a bootstrap CI of the median, a distribution summary
+ Shapiro-Wilk per cell, and Mann-Whitney U between profiles). The last
two need `scipy` installed locally (`pip install scipy`) -- the one
external dependency anywhere in this analysis pipeline, never installed
on any EC2 server/client; without it those two fields report an honest
`"status": "scipy not installed"` instead of failing the whole run.
`thesis/results/v8/METRICS_COVERAGE.md`
is the full map of which v7 metric comes from which v8 file/field, what
is and isn't covered yet, and why -- read it before trusting any
specific row of the generated report. `tests/test_consolidate_v8.py`
runs the generator end to end against real local flow-check data
(`tests/fixtures/light_flow_check_2026-10-21/`); run it with
`python3 -m pytest tests/test_consolidate_v8.py` from this directory.
`tests/test_schardong_coverage.py` covers the mTLS-handshake-fraction/
jitter/distribution-summary/Mann-Whitney additions (Decision 94) the
same way, against the same real fixtures.

## Pcap capture: snaplen 256, handshake measured two ways (Decision 79)

`campaign_run.py`'s own `TCPDUMP_SNAPLEN_BYTES = 256` (raised from 128
on 2026-10-22, DECISIONS.md) -- needed so the ClientHello's own SNI
("mtls") is actually recoverable from the capture; ClientHello's own
SIZE was never affected by snaplen either way. Real measured cost of
this change: +47.6% pcap size per capture; campaign-wide volume
estimate updated to **~32-214MB compressed, both sides** (Decision 57).

The mTLS handshake bytes term (OPINsize's 4th term) is measured TWO
ways, both reported, never silently merged: the gateway's own log
(`term_handshake`, comparable with v7's own historical figures, but
known to include some of the connection's first real request's bytes --
Decision 78) and the client's own pcap (`term_handshake_pcap`, cleaner,
ClientHello through the client's own Finished only). `consolidate_v8.py`'s
`HANDSHAKE_SOURCE` constant picks which one feeds OPINsize's own total
(default: gateway, for v7 comparability) -- `pilot_acceptance.py`'s own
Criterion 11 is what should inform changing it, not either script
deciding on its own.

## Caveats, registered here and in DECISIONS.md Decision 49

- **Terraform state and the campaign's own SSH private key are local
  only** -- the private key exists in Terraform state and briefly in
  memory during `campaign_up.sh`, never in a tracked file. State itself
  is gitignored and checked by `scripts/scan_secrets.sh` (tracked
  content + staged diff + full history, and an explicit
  never-tracked-`.tfstate` check).
- **The control instance has no destructive power** -- no AWS
  credential, no IAM role. It cannot terraform-destroy anything itself;
  only the operator's own machine, running `campaign_down.sh` with the
  real Terraform state, can.
- **Data sits on the control instance's disk until `campaign_pull.sh`
  verifies it locally.** `campaign_down.sh` refuses to destroy without
  that verification (bypassable with `--force`, loudly).
- **The safety timer (servers/clients, not control) is not a teardown.**
  It shuts an instance down past its deadline if the orchestrator stops
  renewing it -- this does not release the instance's Elastic IP and
  does not run any of `campaign_down.sh`'s verification. It exists so a
  crashed orchestrator doesn't leave a billed instance running
  indefinitely, not so the operator can skip `campaign_down.sh`.
- **`rsync` on the OPERATOR's own machine is optional, not required.**
  `deliver_images.sh`'s image transport (operator -> control) prefers
  `rsync --partial` when both the operator's machine AND the control
  instance have it (`have_rsync_locally()` AND `have_rsync_on_control()`,
  pilot item 1 -- the local check was missing before, so a local-only
  gap silently failed instead of falling back). Either side missing it
  falls back to a split-into-100MB-parts + plain `scp` transport instead
  -- each part individually sha256-verified on arrival, AND the
  reassembled whole file sha256-verified again before any `docker load`
  is attempted (glob narrowed to `part.??` so a part's own `.sha256`
  sidecar can never be concatenated into the reassembled tarball by
  accident, pilot item 1 -- found live, corrupting the first real pilot
  transfer, caught by this exact whole-file check before it reached
  `docker load`). `campaign_pull.sh` (operator <- control, the other
  direction) has the same optional-rsync fallback, `scp -r` instead --
  not incremental like rsync, but correctness-equivalent (the sha256
  manifest check is unchanged either way) and small enough data
  volumes not to need incremental transfer in practice. A transport
  failure anywhere in this chain aborts
  loudly (`set -euo pipefail`), never silently ships a partial or
  corrupted image.

`campaign_run.py`'s actual per-execution step
(`run_one_execution()`) is intentionally unimplemented -- it depends on
`opin_flow.py`'s `REMOTE_GATEWAY_HOST` flag (Decision 45, described, not
yet added to that script). Everything around it (window scheduling,
automatic resume, the three pre-block checks) is real and already
runnable.
