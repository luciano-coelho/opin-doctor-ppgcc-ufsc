#!/usr/bin/env python3
"""B.14: regression guard for the repo-wide audit this turn did by hand
(grep for set_latency/docker exec/docker logs/127.0.0.1/localhost/fixed
ports, fix every REMOTE_GATEWAY_HOST-unguarded set_latency() call site
in thesis/scripts/*.py -- see DECISIONS.md for the file list). This
test does NOT re-audit everything from scratch (docker exec/docker
logs/127.0.0.1/localhost have many legitimate, intentional local-stack
uses -- LocalExecutor IS the local-stack test, opin_flow.py's own
TLS_KEM_PROXY_PORT local proxy IS always 127.0.0.1 by design, etc. --
an unscoped grep-and-fail on those would be mostly noise). It narrowly
guards the ONE pattern this turn found as a REAL, fixable bug class:
`of.set_latency(...)` (or `self.of.set_latency(...)`) called WITHOUT a
nearby REMOTE_GATEWAY_HOST check in the same file -- that call always
assumes a local gateway container to `docker exec`/tc into, and silently
breaks (or worse, silently no-ops against the wrong target) the moment
REMOTE_GATEWAY_HOST is set. A new call site added later without the
guard is exactly the regression this test exists to catch.

Run directly: `python tests/test_no_local_lab_assumptions.py`.
"""
import re
import sys
from pathlib import Path

REPO_THESIS_SCRIPTS = Path(__file__).resolve().parents[5] / "scripts"
LOOKBACK_LINES = 8

CALL_RE = re.compile(r"\bof\.set_latency\(")


def find_unguarded_call_sites():
    problems = []
    for py_file in sorted(REPO_THESIS_SCRIPTS.glob("*.py")):
        text = py_file.read_text(encoding="utf-8")
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if not CALL_RE.search(line):
                continue
            window = lines[max(0, i - LOOKBACK_LINES):i + 1]
            if not any("REMOTE_GATEWAY_HOST" in w for w in window):
                problems.append(f"{py_file.name}:{i + 1}: {line.strip()}")
    return problems


def run():
    problems = find_unguarded_call_sites()
    if problems:
        print("FAIL: found of.set_latency(...) call site(s) with no REMOTE_GATEWAY_HOST guard "
              f"within {LOOKBACK_LINES} lines above -- these will break (or misbehave) the moment "
              "someone runs that script against a real remote instance:")
        for p in problems:
            print(f"  {p}")
        return False
    print(f"PASS: every of.set_latency(...) call site in {REPO_THESIS_SCRIPTS} is REMOTE_GATEWAY_HOST-guarded.")
    return True


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
