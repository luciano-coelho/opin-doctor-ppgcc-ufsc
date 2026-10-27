#!/usr/bin/env python3
"""Decision 60: thin CLI deployed to each campaign CLIENT instance (or
run locally, pointed at the local stack, for the test below). Runs
EXACTLY ONE timed execution by calling latency_automation.py's own
`run_once_timed_with_retry()` -- the lab's existing, already-correct
T_fluxo measurement (monotonic clock, discarded-sub-attempt time
excluded, whole-run retries redone from scratch) -- never
reimplemented here.

Does NOT manage the TLS proxy / PQC signer service lifecycle -- that is
scoped to the whole profile BLOCK (Decision 56), started once before
round-robin begins and stopped once after, by whatever calls this
script per execution, not by this script itself.

Prints exactly one JSON object to stdout -- the orchestrator (control
instance, or the local test below) captures and parses it. Never writes
files itself; the caller decides where run{NN}.json/calls.jsonl land
(Decision 53's repository-mirroring tree).

Usage:
  CRYPTO_PROFILE=classic REMOTE_GATEWAY_HOST=<host> python campaign_client_runner.py --label run01
"""
import argparse
import json
import os
import sys

import latency_automation as la
import opin_flow as of


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()

    crypto_profile = os.environ.get("CRYPTO_PROFILE", "classic")
    if not of.REMOTE_GATEWAY_HOST:
        sys.exit("REMOTE_GATEWAY_HOST must be set -- this script is for remote/campaign execution only.")

    whole_run_retries = []
    # verification_timings/signing_timings/wait_timings/phase_accounting
    # (T_fluxo full-accounting turn, thesis/results/v8/DECISIONS.md) are
    # now attached by run_once_timed() itself -- the one place every
    # caller goes through -- not wired here separately any more.
    result = la.run_once_timed_with_retry(crypto_profile, args.label, whole_run_retries, return_calls=True)
    result["whole_run_retries"] = whole_run_retries
    result["retried"] = bool(result.get("retries"))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
