"""
Fase 4 calibration (thesis/results/v6/Level 1/ARCHITECTURE.md): measures
tls_kem_proxy's own added overhead in isolation, BEFORE any pilot run --
per the user's explicit instruction not to wait for a full 10-run pilot to
find out whether "negligible" is actually true.

Starts tls_kem_proxy in -stub mode (answers every request immediately,
never dials the gateway at all -- see tls_kem_proxy/main.go's runStub()),
then fires a batch of requests at it over one reused requests.Session
(matching how opin_flow.py already reuses a Session per connection pool,
not a fresh connection per call) and reports round-trip statistics. This
number is the Python<->proxy floor; the real relay's total T_fluxo also
includes the proxy<->gateway mTLS hop on top of it, which this script does
not touch.

Usage:
  python calibrate_tls_kem_proxy_stub.py [--requests N] [--port PORT]
"""
import argparse
import statistics
import subprocess
import time
from pathlib import Path

import requests

THESIS_DIR = Path(__file__).resolve().parent.parent
PROXY_SRC_DIR = THESIS_DIR / "scripts" / "tls_kem_proxy"
CONTAINER_NAME = "tls_kem_proxy_stub_calibration"


def start_stub(port: int) -> subprocess.Popen:
    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True, text=True)
    proc = subprocess.Popen(
        [
            "docker", "run", "--rm", "-i",
            "--name", CONTAINER_NAME,
            "-p", f"127.0.0.1:{port}:{port}",
            "-v", f"{PROXY_SRC_DIR}:/src",
            "-w", "/src",
            # Pinned by digest, not the floating "golang:1.27-rc-alpine"
            # tag -- see opin_flow.py's TLS_KEM_PROXY_GO_IMAGE for why.
            "golang:1.27-rc-alpine@sha256:c5aca77a4d16cb6688dbf3ccade67eff6f05ee208bc854d060e6947f5c27e23c",
            "go", "run", ".", "-stub", "-listen", f":{port}",
        ],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    # A bare TCP connect is not a sufficient readiness probe here: Docker
    # Desktop's published-port proxy binds the host port as soon as the
    # container starts, before `go run` has finished compiling and the Go
    # process itself has called ListenAndServe -- a connection can succeed
    # at the Docker layer and still be closed immediately with no HTTP
    # response, exactly the "RemoteDisconnected" symptom this replaces.
    # An actual HTTP request only succeeds once the real listener is up.
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"stub proxy exited early:\n{proc.stdout.read() if proc.stdout else ''}")
        try:
            requests.get(f"https://127.0.0.1:{port}/", timeout=1, verify=False)
            return proc
        except requests.exceptions.RequestException:
            time.sleep(0.3)
    raise RuntimeError(f"stub proxy did not answer HTTP on port {port} within 30s")


def stop_stub(proc: subprocess.Popen) -> None:
    subprocess.run(["docker", "stop", CONTAINER_NAME], capture_output=True, text=True, timeout=30)
    proc.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=int, default=200, help="number of requests to measure (default 200)")
    parser.add_argument("--port", type=int, default=8443)
    args = parser.parse_args()

    print(f"Starting tls_kem_proxy in -stub mode on port {args.port}...")
    proc = start_stub(args.port)
    try:
        session = requests.Session()  # one reused connection, matching opin_flow.py's own pattern
        # "127.0.0.1", not "localhost": see thesis/results/v6/Level 1/
        # DECISIONS.md, Decision 3 -- resolving "localhost" on this machine
        # costs ~2s per FRESH connection (IPv6-then-IPv4 happy-eyeballs
        # fallback). Irrelevant to what this script measures (one warmup
        # connection, then 200 samples reused on it), but kept consistent
        # with opin_flow.py's own fix now that its cause is known.
        url = f"https://127.0.0.1:{args.port}/"

        # Warmup: first request on a fresh connection pays TCP setup + TLS
        # handshake (now real, since the local hop also speaks TLS -- see
        # tls_kem_proxy/main.go's module docstring for why) + Go module
        # compile-cache effects; excluded from the measured sample for the
        # same reason median_automation.py discards a warmup run.
        session.get(url, timeout=5, verify=False)

        samples_ms = []
        for _ in range(args.requests):
            start = time.monotonic()
            resp = session.get(url, timeout=5, verify=False)
            elapsed_ms = (time.monotonic() - start) * 1000
            resp.raise_for_status()
            samples_ms.append(elapsed_ms)

        samples_ms.sort()
        print(f"\ntls_kem_proxy stub-mode round-trip, {args.requests} requests, one reused connection:")
        print(f"  median: {statistics.median(samples_ms):.3f} ms")
        print(f"  mean:   {statistics.mean(samples_ms):.3f} ms")
        print(f"  stdev:  {statistics.stdev(samples_ms):.3f} ms")
        print(f"  min:    {samples_ms[0]:.3f} ms")
        print(f"  max:    {samples_ms[-1]:.3f} ms")
        print(f"  p95:    {samples_ms[int(0.95 * len(samples_ms))]:.3f} ms")
    finally:
        stop_stub(proc)


if __name__ == "__main__":
    main()
