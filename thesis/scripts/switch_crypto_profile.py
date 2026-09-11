"""
Switches the OPIN stack's CRYPTO_PROFILE and waits out the settling window
before returning -- thesis/results/v6/Level 1/DECISIONS.md, Decision 4.

Context: the Hybrid/0ms pilot's first official 10 runs came back with a
median 2.01s above v5's own historical Hybrid baseline and a 39.7% spread,
including one run at 16.36s. Investigated directly (not accepted as noise):
removing that single outlier barely moved the median (12.744s -> 12.298s),
so it wasn't one bad run distorting an otherwise-clean sample. A controlled
Go-to-Go test (tls_kem_proxy, classical curve, PQC cert vs Hybrid cert,
direct vs via-proxy) showed no measurable cost from the Hybrid cert's larger
size (6,859 vs 2,953 bytes) at either the proxy or the certificate-size
level (~20-24ms fresh-connection cost, same for all four combinations) --
ruling out the two-hop bridge as the cause. Cross-referencing each run's
own timestamp against the CRYPTO_PROFILE switch showed the elevated runs
(1, 2, 4, 5, 6) clustered in the ~2 minutes right after the stack's
`docker compose --force-recreate`, with the later runs (7-10) already
tightening back down. Re-running the same 10-execution measurement on the
same, by-then long-settled stack (no recreate in between) produced a median
of 11.369s (17.9% spread) -- within 0.64s of v5's own historical Hybrid
number (10.7295s), and that remaining 0.64s matches v5's own pre-existing
PQC-vs-Hybrid gap (0.597s, its signature-composition cost), not something
new. Conclusion: the elevated pilot numbers were a one-time settling
artifact of measuring too soon after a fresh container recreation (JIT/
cache/disk warm-up of the freshly (re)started `auth`/`mtls`/`mockapi`
containers), not a per-connection KEM or Hybrid-cert cost.

This script makes the fix procedural rather than something to remember by
hand: every CRYPTO_PROFILE switch, from here on -- pilot or full batch --
goes through this script, which recreates the profile-dependent containers,
waits for them to come up (retrying the known localstack-seeding race and
the psql-dependency race the same way this session's manual switches
needed to), then burns 5 DISCARDED full-flow executions (insurance + person,
0ms, timed and printed but never written as data) before returning control.
5 was picked empirically: the contaminated pilot's own later runs (7-10)
had already tightened by the 7th-8th real execution, so 5 discarded runs
plus whatever warmup the caller's own script performs comfortably covers
the observed settling window without paying much more than ~1 minute per
switch.

Usage:
  python switch_crypto_profile.py classic|pqc|hybrid
"""
import os
import subprocess
import sys
import time
from pathlib import Path

# opin_flow.py computes its routing globals (_USE_TLS_KEM_PROXY,
# AUTH_CONNECT_HOST, etc.) ONCE at import time from os.environ["CRYPTO_PROFILE"]
# -- setting the env var only inside switch()/main() would be too late, since
# the module below would already have imported with whatever CRYPTO_PROFILE
# happened to be ambient in this process's inherited shell environment
# (observed live: the Etapa 1 batch's first switch, to "pqc", ran with no
# CRYPTO_PROFILE set at all, silently defaulted routing to "classic", and its
# 5 settling runs all failed with a direct (non-proxied) TLS handshake error
# on port 443 -- harmless there since size doesn't depend on timing, but this
# would have made every settling warmup for Etapa 2 a silent no-op).
if len(sys.argv) == 2 and sys.argv[1] in ("classic", "pqc", "hybrid"):
    os.environ["CRYPTO_PROFILE"] = sys.argv[1]

import opin_flow as of

COMPOSE_DIR = of.BASE_DIR / "insurance-server-lambdas"
PROFILE_DEPENDENT_SERVICES = ["auth", "mtls", "mongo_seed", "mockapi"]
SETTLING_WARMUP_RUNS = 5


def _compose(*args, env_profile: str) -> subprocess.CompletedProcess:
    import os
    env = dict(os.environ)
    env["CRYPTO_PROFILE"] = env_profile
    return subprocess.run(
        ["docker", "compose", "--profile", "main", *args],
        cwd=str(COMPOSE_DIR), env=env, capture_output=True, text=True, timeout=180,
    )


def _container_status(name: str) -> str:
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Status}}", name],
        capture_output=True, text=True, timeout=15,
    )
    return result.stdout.strip() if result.returncode == 0 else "missing"


def _start_if_exited(name: str) -> None:
    if _container_status(name) == "exited":
        print(f"  [switch_crypto_profile] {name} exited after recreate -- starting it "
              f"(known races: localstack SSM-seed timing for auth/mtls, psql dependency for mockapi)")
        subprocess.run(["docker", "start", name], capture_output=True, text=True, timeout=30)


def switch(profile: str) -> None:
    print(f"=== Switching CRYPTO_PROFILE -> {profile} ===")
    result = _compose(
        "up", "-d", "--force-recreate", *PROFILE_DEPENDENT_SERVICES,
        env_profile=profile,
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker compose up failed:\n{result.stdout}\n{result.stderr}")

    # The force-recreate above returns as soon as containers are *started*,
    # not once auth/mtls/mockapi have finished their own boot-time
    # dependencies (localstack SSM seeding; mockapi's psql connection). Both
    # races were observed live switching profiles for this pilot -- give
    # them a moment to fail, then retry starting only the ones that did.
    time.sleep(10)
    for name in ("insurance-server-lambdas-auth-1", "insurance-server-lambdas-mtls-1",
                 "insurance-server-lambdas-mockapi-1"):
        _start_if_exited(name)
    time.sleep(8)
    for name in ("insurance-server-lambdas-auth-1", "insurance-server-lambdas-mtls-1",
                 "insurance-server-lambdas-mockapi-1"):
        status = _container_status(name)
        if status != "running":
            raise RuntimeError(f"{name} is '{status}' after retry -- switch failed, inspect manually")
    print("  containers up: auth, mtls, mockapi")

    print(f"  running {SETTLING_WARMUP_RUNS} discarded full-flow executions to settle "
          f"the freshly (re)started containers (Decision 4) ...")
    of.set_latency(0)
    proc = of.start_tls_kem_proxy(profile) if profile != "classic" else None
    try:
        for i in range(1, SETTLING_WARMUP_RUNS + 1):
            t0 = time.monotonic()
            try:
                of.run_insurance_flow(profile)
                of.run_person_flow(profile)
            except Exception as e:
                print(f"    settling run {i}/{SETTLING_WARMUP_RUNS}: failed ({type(e).__name__}: {e}) -- "
                      f"discarded regardless, continuing")
                continue
            print(f"    settling run {i}/{SETTLING_WARMUP_RUNS}: {time.monotonic() - t0:.3f}s (discarded)")
    finally:
        if proc is not None:
            of.stop_tls_kem_proxy(proc)
    print(f"=== CRYPTO_PROFILE={profile} ready ===")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("classic", "pqc", "hybrid"):
        raise SystemExit(f"Usage: python {Path(__file__).name} classic|pqc|hybrid")
    switch(sys.argv[1])
