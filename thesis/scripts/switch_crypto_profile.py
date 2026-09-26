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


PSQL_CONTAINER_NAME = "insurance-server-lambdas-psql-1"
PSQL_CHECKPOINT_WARN_SECONDS = 5.0


def _check_psql_checkpoint_health() -> None:
    """
    A manually-triggered `CHECKPOINT` is used as a cheap, direct probe of this host's actual
    disk write/fsync performance for the psql container -- not inferred
    from flow-level symptoms. Confirmed live: a healthy checkpoint here
    (497 buffers, ~3MB dirty) completes in ~1.2s; the same psql container,
    later in the same 13-day-old session, was observed taking 45-56s for
    the same amount of data (`docker logs`, `checkpoint complete: ...
    total=50.936 s` and similar) -- a ~40-50x degradation with no error,
    no crash, and no symptom visible anywhere except unusually slow
    responses on whichever endpoint happened to hit the DB at the wrong
    moment (traced to Clássico's `POST /consents`, the flow's only
    write-heavy call, producing a bimodal T_fluxo that looked at first
    like a crypto-profile effect but wasn't). The degraded window ended
    only because the container was later restarted (root cause not fully
    pinned down -- plausibly WSL2/Docker Desktop VHDX-level I/O
    contention accumulated over a long-lived session, not something this
    script can prevent from recurring). This check exists so a recurrence
    during a multi-day data-collection protocol is caught loudly,
    immediately, before a single execution is measured against a degraded
    database -- not discovered after the fact by a confusing spread number.
    """
    t0 = time.monotonic()
    result = subprocess.run(
        ["docker", "exec", "-e", "PGPASSWORD=test", PSQL_CONTAINER_NAME,
         "psql", "-U", "test", "-d", "mock", "-c", "CHECKPOINT;"],
        capture_output=True, text=True, timeout=90,
    )
    elapsed = time.monotonic() - t0
    if result.returncode != 0:
        raise RuntimeError(f"psql health check: CHECKPOINT failed:\n{result.stdout}\n{result.stderr}")
    print(f"  psql health check: manual CHECKPOINT completed in {elapsed:.2f}s")
    if elapsed > PSQL_CHECKPOINT_WARN_SECONDS:
        raise SystemExit(
            f"psql health check FAILED: CHECKPOINT took {elapsed:.2f}s (threshold {PSQL_CHECKPOINT_WARN_SECONDS}s). "
            f"This host's disk I/O for the psql container is degraded -- the same condition that has previously "
            f"produced Clássico's bimodal POST /consents latency during a pilot run. "
            f"Do NOT proceed with data collection in this state: restart the psql container "
            f"(`docker restart {PSQL_CONTAINER_NAME}`) and re-run this script."
        )


MTLS_READY_TIMEOUT_SECONDS = 30


def _wait_for_mtls_ready(timeout_seconds: int = MTLS_READY_TIMEOUT_SECONDS) -> None:
    """
    Polls the gateway's own log for a readiness signal, not the
    container-state check (`docker inspect ... Status`) this script relied
    on alone before. Root cause, reproduced deliberately: `mock_mtls/main.go`'s `main()` calls
    `loadSsaKey()` -- a blocking `http.Get` to localstack's keystore endpoint
    -- BEFORE it ever calls `net.Listen`/`ListenAndServe` on port 443. Docker
    reports the container "running" as soon as the process starts, which can
    be well before that HTTP call returns and the TLS listener actually
    binds. Reproduced live: 8 consecutive `docker compose up -d
    --force-recreate mtls` cycles, polling `docker logs` for "Listening on
    port 443" -- 7 of 8 took 2.4-2.9s, one took 16.2s. The one production
    incident this fix responds to needed *more* than 30s (tls_kem_proxy's
    own upstream dial saw repeated `remote error: tls: handshake failure`
    for several seconds even after the proxy itself had started) -- worse
    than anything reproduced here, but the same mechanism: whatever made
    that one localstack round trip slow that day, this script's old fixed
    18s sleep (10s + 8s) had no way to detect or wait out.

    Note this does NOT replace start_tls_kem_proxy()'s own readiness check
    (_wait_for_tls_kem_proxy_ready): that one only proves the proxy's local
    listener is bound, not that its upstream dial to the real gateway would
    succeed -- confirmed live to be an insufficient signal on its own (the
    proxy reported itself ready, then failed every dial to mtls for several
    seconds). This function checks the actual dependency directly, before
    the proxy is ever started.

    Checks the gateway's OWN log for "Listening on port 443"
    (mock_mtls/main.go's own line, printed right after net.Listen succeeds)
    rather than attempting a real HTTPS request -- an actual TLS handshake
    is not a profile-agnostic signal here: under pqc/hybrid the gateway's
    CurvePreferences only accepts MLKEM1024/SecP384r1MLKEM1024, which no
    plain Python/OpenSSL client can ever negotiate (the entire reason
    tls_kem_proxy exists). A first version of this check tried
    `requests.get(..., verify=False)` and failed every single time under
    pqc/hybrid with "tls alert handshake failure" -- not a readiness
    problem, an expected, permanent property of those profiles that would
    have made this check useless (or actively wrong) for 2 of 3 profiles.
    Reading the log line sidesteps TLS entirely and checks the exact
    code-level event that actually matters, regardless of profile.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["docker", "logs", "insurance-server-lambdas-mtls-1"],
            capture_output=True, text=True, timeout=10,
        )
        if "Listening on port 443" in (result.stdout + result.stderr):
            return
        time.sleep(0.2)
    raise RuntimeError(
        f"mtls (gateway) did not log \"Listening on port 443\" within {timeout_seconds}s."
    )


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

    _wait_for_mtls_ready()
    print("  mtls health check: gateway logged \"Listening on port 443\"")

    _check_psql_checkpoint_health()

    print(f"  running {SETTLING_WARMUP_RUNS} discarded full-flow executions to settle "
          f"the freshly (re)started containers (Decision 4) ...")
    of.set_latency(0)
    proc = of.start_tls_kem_proxy(profile)  # v7: classic also goes through the proxy now (Decision 1)
    pqc_signer_started = of.start_pqc_signer_service(profile)  # persistent ML-DSA-65 signer
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
        of.stop_pqc_signer_service(pqc_signer_started)
        if proc is not None:
            of.stop_tls_kem_proxy(proc)
    print(f"=== CRYPTO_PROFILE={profile} ready ===")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("classic", "pqc", "hybrid"):
        raise SystemExit(f"Usage: python {Path(__file__).name} classic|pqc|hybrid")
    switch(sys.argv[1])
