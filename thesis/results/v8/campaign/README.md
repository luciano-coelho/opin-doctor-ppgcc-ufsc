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

`campaign_run.py` is not invoked directly by the operator -- `campaign_up.sh`
installs it on the control instance as a systemd service
(`campaign_run.service`, same directory), which starts the orchestrator
there, not here.

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
plus the new metrics (RTT, packet-loss upper bound, CPU/steal/memory,
a bootstrap CI of the median). `thesis/results/v8/METRICS_COVERAGE.md`
is the full map of which v7 metric comes from which v8 file/field, what
is and isn't covered yet, and why -- read it before trusting any
specific row of the generated report. `tests/test_consolidate_v8.py`
runs the generator end to end against real local flow-check data
(`tests/fixtures/light_flow_check_2026-10-21/`); run it with
`python3 -m pytest tests/test_consolidate_v8.py` from this directory.

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

`campaign_run.py`'s actual per-execution step
(`run_one_execution()`) is intentionally unimplemented -- it depends on
`opin_flow.py`'s `REMOTE_GATEWAY_HOST` flag (Decision 45, described, not
yet added to that script). Everything around it (window scheduling,
automatic resume, the three pre-block checks) is real and already
runnable.
