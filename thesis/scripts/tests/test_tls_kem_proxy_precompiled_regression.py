#!/usr/bin/env python3
"""C.15: regression test for the precompiled-binary tls_kem_proxy path.
Two SEPARATE claims, checked separately (conflating them would be
wrong -- see each function's own docstring):
  (1) "bytes idênticos": the COMPILED BINARY itself is byte-for-byte
      reproducible across two independent `docker build`s (the
      Dockerfile's -trimpath flag's whole point). Checked by
      binary_bytes_reproducible().
  (2) "ClientHello igual (tamanho e SNI)": the ClientHello tls_kem_proxy
      sends UPSTREAM is equal in SIZE and SNI (never full byte content
      -- every ClientHello carries a fresh 32-byte Random field and a
      fresh ephemeral key share, genuine TLS randomness that makes
      literal byte-equality across separate connections impossible by
      design, not a bug this test should chase) between `go run .`
      (the default) and the precompiled binary
      (TLS_KEM_PROXY_USE_PRECOMPILED=1), for all 3 crypto profiles.
      Captured with a plain TCP listener standing in for the upstream
      gateway (ClientHello is the first, unencrypted TLS record -- no
      real mTLS server needed to capture it) on the SAME docker network
      tls_kem_proxy attaches to (insurance-server-lambdas_default).

Requires Docker and the repo's real certs (mock-service-os/certs) --
run directly: `python thesis/scripts/tests/test_tls_kem_proxy_precompiled_regression.py`
"""
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import opin_flow as of

NETWORK = "insurance-server-lambdas_default"
LISTENER_IMAGE = "python:3.12-alpine"
LISTENER_NAME = "mockopin_clienthello_capture"


def _ensure_network():
    r = subprocess.run(["docker", "network", "inspect", NETWORK], capture_output=True)
    if r.returncode != 0:
        subprocess.run(["docker", "network", "create", NETWORK], check=True, capture_output=True)


def _capture_one_clienthello(timeout=30):
    """Starts a throwaway container on NETWORK, aliased "mtls" on that
    network (matching tls_kem_proxy's own default upstream target when
    REMOTE_GATEWAY_HOST is unset), that accepts ONE connection on 443,
    reads up to 8KB (comfortably more than any ClientHello here), and
    prints it hex-encoded to stdout. Returns the raw bytes."""
    subprocess.run(["docker", "rm", "-f", LISTENER_NAME], capture_output=True)
    script = (
        "import socket,sys\n"
        "s=socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
        "s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
        "s.bind(('0.0.0.0', 443)); s.listen(1)\n"
        "conn,_=s.accept()\n"
        "data=conn.recv(8192)\n"
        "sys.stdout.write(data.hex())\n"
        "sys.stdout.flush()\n"
    )
    proc = subprocess.Popen(
        ["docker", "run", "--rm", "-i", "--name", LISTENER_NAME,
         "--network", NETWORK, "--network-alias", "mtls",
         LISTENER_IMAGE, "python3", "-c", script],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return proc


def run_proxy_and_capture(profile, use_precompiled):
    _ensure_network()
    listener_proc = _capture_one_clienthello()
    time.sleep(1.0)  # let the listener bind before the proxy dials it

    import os
    os.environ.pop("REMOTE_GATEWAY_HOST", None)  # use the default "mtls:443" target
    try:
        proxy_proc = of.start_tls_kem_proxy(profile, detached=False, use_precompiled_binary=use_precompiled)
    except RuntimeError:
        # opin_flow.start_tls_kem_proxy()'s own readiness probe is a real
        # end-to-end HTTPS round trip through the proxy to the upstream
        # ("mtls:443") -- it never completes here because our capture
        # listener is a raw TCP sink, not a real TLS server, so the
        # probe's requests.get() keeps hitting an SSL-level error, which
        # (correctly, for ITS purpose) is treated as "not ready yet," not
        # as a usable response. That timeout is expected in this test's
        # setup and is NOT what's being regression-tested here -- the
        # container itself is still up and listening, which is all this
        # test needs. of.TLS_KEM_PROXY_CONTAINER_NAME stays correct in
        # both run modes (set unconditionally before the readiness wait).
        proxy_proc = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", of.TLS_KEM_PROXY_CONTAINER_NAME],
            capture_output=True, text=True,
        )
        if proxy_proc.stdout.strip() != "true":
            raise
        proxy_proc = of.TLS_KEM_PROXY_CONTAINER_NAME  # str sentinel -> stop_tls_kem_proxy()'s docker-stop-by-name path
    try:
        # Trigger the proxy's upstream dial: connecting to it locally is
        # enough -- tls_kem_proxy dials upstream and sends its own
        # ClientHello as soon as a client connects to it, independent of
        # what that client then does.
        with socket.create_connection(("127.0.0.1", of.TLS_KEM_PROXY_PORT), timeout=5):
            time.sleep(2.0)  # give the proxy time to dial upstream and send its ClientHello
        stdout, _ = listener_proc.communicate(timeout=20)
        return bytes.fromhex(stdout.strip())
    finally:
        of.stop_tls_kem_proxy(proxy_proc)
        subprocess.run(["docker", "rm", "-f", LISTENER_NAME], capture_output=True)


def binary_bytes_reproducible():
    """C.15's OTHER regression claim: the compiled BINARY itself is
    byte-for-byte reproducible across two independent builds (the
    Dockerfile's own -trimpath flag's whole point -- no builder-machine
    absolute paths or other non-determinism baked in). This is checked
    separately from the ClientHello (which can NEVER be byte-identical
    run to run -- see run()'s own docstring) by building the image
    twice under two tags and diffing the extracted binary."""
    tag_a, tag_b = "mockopin/tls_kem_proxy:repro_a", "mockopin/tls_kem_proxy:repro_b"
    src_dir = str(Path(of.TLS_KEM_PROXY_SRC_DIR))
    for tag in (tag_a, tag_b):
        r = subprocess.run(["docker", "build", "--no-cache", "-t", tag, src_dir],
                            capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            raise RuntimeError(f"build {tag} failed:\n{r.stdout}\n{r.stderr}")
    digests = {}
    for tag in (tag_a, tag_b):
        cid = subprocess.run(["docker", "create", tag], capture_output=True, text=True, check=True).stdout.strip()
        try:
            out = Path("/tmp") / f"tls_kem_proxy_{tag.split(':')[-1]}"
            subprocess.run(["docker", "cp", f"{cid}:/usr/local/bin/tls_kem_proxy", str(out)], check=True, capture_output=True)
            digests[tag] = out.read_bytes()
        finally:
            subprocess.run(["docker", "rm", "-f", cid], capture_output=True)
    for tag in (tag_a, tag_b):
        subprocess.run(["docker", "rmi", "-f", tag], capture_output=True)
    same_size = len(digests[tag_a]) == len(digests[tag_b])
    same_bytes = digests[tag_a] == digests[tag_b]
    print(f"  build A: {len(digests[tag_a])} bytes; build B: {len(digests[tag_b])} bytes; "
          f"byte-identical: {same_bytes}")
    return same_bytes and same_size


def run():
    """C.15's TWO separate regression claims, checked separately:
    (1) the compiled binary is byte-for-byte reproducible across two
    independent builds (binary_bytes_reproducible(), above) -- this is
    the only place "bytes idênticos" can mean literal byte equality,
    since the ClientHello itself can NEVER be byte-identical across two
    separate TLS connections: every ClientHello carries a fresh 32-byte
    Random field and, for classic/pqc/hybrid here, a fresh ephemeral
    key share -- genuine, correct TLS randomness, not a bug, and not
    something go-run vs precompiled changes. (2) the ClientHello is
    equal in SIZE and SNI between the two run modes, for all 3 profiles
    -- confirming the precompiled binary negotiates the exact same
    profile/curve as `go run .` does, which IS a meaningful regression
    check and does NOT require byte equality to be meaningful."""
    print("=== binary byte-for-byte reproducibility (two independent builds) ===")
    binary_ok = binary_bytes_reproducible()
    print(f"  {'PASS' if binary_ok else 'FAIL'}")

    results = {"binary_reproducible": binary_ok}
    for profile in ("classic", "pqc", "hybrid"):
        print(f"=== profile={profile}: ClientHello size+SNI, go run vs precompiled ===")
        go_run_hello = run_proxy_and_capture(profile, use_precompiled=False)
        precompiled_hello = run_proxy_and_capture(profile, use_precompiled=True)
        same_size = len(go_run_hello) == len(precompiled_hello)
        sni_go = _extract_sni(go_run_hello)
        sni_pre = _extract_sni(precompiled_hello)
        ok = same_size and sni_go == sni_pre and sni_go is not None
        print(f"  go run:      {len(go_run_hello)} bytes, SNI={sni_go!r}")
        print(f"  precompiled: {len(precompiled_hello)} bytes, SNI={sni_pre!r}")
        print(f"  {'PASS' if ok else 'FAIL'}")
        results[f"clienthello_{profile}"] = ok
    return results


def _extract_sni(client_hello_bytes):
    """Minimal, read-only SNI extraction from a raw ClientHello TLS
    record -- enough to compare "same SNI" across both modes without
    pulling in a full TLS parser. Returns None if not found/parseable
    (never raises -- a parse miss just shows up as a comparison
    mismatch in the caller, which is itself informative)."""
    try:
        data = client_hello_bytes
        idx = data.find(b"\x00\x00")  # extension type 0x0000 = server_name
        while idx != -1:
            # extension_type(2) + extension_length(2) + list_length(2) + entry_type(1) + name_length(2) + name
            if idx + 9 <= len(data) and data[idx + 6] == 0x00:
                name_len = int.from_bytes(data[idx + 7:idx + 9], "big")
                name_start = idx + 9
                if name_start + name_len <= len(data) and 0 < name_len < 256:
                    candidate = data[name_start:name_start + name_len]
                    if candidate.replace(b".", b"").replace(b"-", b"").isalnum():
                        return candidate.decode("ascii", errors="replace")
            idx = data.find(b"\x00\x00", idx + 1)
    except Exception:
        pass
    return None


if __name__ == "__main__":
    results = run()
    print("\n=== SUMMARY ===")
    for k, v in results.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
    sys.exit(0 if all(results.values()) else 1)
