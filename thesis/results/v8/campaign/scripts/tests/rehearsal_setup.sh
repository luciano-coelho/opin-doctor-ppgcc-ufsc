#!/usr/bin/env bash
# B.11: sets up the 3-container local rehearsal (control, server, client,
# each running real sshd) that tests/rehearsal_runner.py then drives.
# This is infrastructure for the REHEARSAL only -- it stands in for the
# real campaign's AWS instances with throwaway sshd containers on one
# Docker bridge network, so SSHExecutor's real command strings (A.3's
# shlex-quoting fix, A.6/A.7's tcpdump+interface fix) can be run over a
# REAL SSH connection and checked, not just read.
#
# What this rehearsal covers (confirmed by tests/rehearsal_runner.py):
#   - Every SSH command string SSHExecutor's real methods construct
#     (server_flock_wrap, _ssh_cmd, _tcpdump_start_cmd/_tcpdump_stop_cmd,
#     _iface_detect_sh, _env_prefix) actually parses and runs on a real
#     remote shell -- this is how three real bugs were found this turn
#     (documented in _tcpdump_start_cmd's own docstring): a ~-prefixed
#     path broken by shlex.quote's tilde-expansion defeat, $HOME
#     resolving to root's home across the sudo boundary, and $IFACE
#     unable to cross that same sudo boundary as a variable reference.
#   - A.6's tcpdump PID fix: the captured PID is confirmed to be
#     tcpdump's own (read back via /proc/<pid>/comm), not sudo's/
#     setsid's.
#   - A.7's interface auto-detection runs for real against each
#     container's own /proc/net/route.
#   - A.5's chronyc/ping/cat-/proc-files commands run for real.
#
# What this rehearsal does NOT cover (explicitly, not glossed over):
#   - switch_crypto_profile.py's real settling sequence (container
#     recreation, health checks) -- the rehearsal server only runs a
#     stand-in script that echoes its argv. That protocol is already
#     covered by LocalExecutor's own tests (Decision 62) against the
#     real docker-compose stack.
#   - campaign_client_runner.py's real flow execution -- a stand-in
#     that prints one fixed fake JSON line.
#   - Real AWS conditions: IAM/security-group-gated SSH, real instance
#     boot/cloud-init, real inter-region network latency/packet loss.
#     These 3 containers share one Docker bridge network at ~0ms --
#     this rehearsal validates COMMAND CORRECTNESS, not network realism.
#   - SSHExecutor.live execution itself is still NotImplementedError by
#     design (Decision 60/62) -- rehearsal_runner.py calls the same
#     command-building methods directly and runs the result through
#     its OWN subprocess.run(["ssh", ...]), standing in for the live-
#     execution wiring SSHExecutor itself doesn't have yet.
#
# Usage: bash tests/rehearsal_setup.sh   (idempotent -- removes any
# previous rehearsal containers/network first)
# Then:  docker exec mockopin_rehearsal_control \
#          python3 /repo/thesis/results/v8/campaign/scripts/tests/rehearsal_runner.py
# Teardown: bash tests/rehearsal_teardown.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../../.." && pwd)"
KEYDIR="$(mktemp -d)"

docker rm -f mockopin_rehearsal_server mockopin_rehearsal_client mockopin_rehearsal_control >/dev/null 2>&1 || true
docker network rm mockopin_rehearsal_net >/dev/null 2>&1 || true
docker network create mockopin_rehearsal_net >/dev/null

ssh-keygen -t ed25519 -N "" -f "$KEYDIR/campaign_key" -q
PUBKEY="$(cat "$KEYDIR/campaign_key.pub")"

for name in mockopin_rehearsal_server mockopin_rehearsal_client; do
  docker run -d --name "$name" --network mockopin_rehearsal_net \
    --cap-add=NET_ADMIN --cap-add=NET_RAW \
    -e PUBLIC_KEY="$PUBKEY" -e USER_NAME=ec2-user -e PASSWORD_ACCESS=false -e SUDO_ACCESS=true \
    linuxserver/openssh-server:latest >/dev/null
done
sleep 6

for name in mockopin_rehearsal_server mockopin_rehearsal_client; do
  docker exec "$name" apk add --no-cache python3 tcpdump chrony iputils >/dev/null 2>&1
  # the real campaign's AMI assumes ec2-user's home is /home/ec2-user;
  # this image's own convention is /config -- symlinked so the REAL,
  # unmodified /home/ec2-user/... literal paths campaign_run.py builds
  # work here too, instead of special-casing the test.
  docker exec "$name" sh -c "mkdir -p /home && ln -sfn /config /home/ec2-user"
done

# stand-in remote scripts -- see "what this does NOT cover" above.
docker exec mockopin_rehearsal_server mkdir -p /config/insurance-server-lambdas /config/thesis/scripts
docker exec mockopin_rehearsal_server sh -c "cat > /config/thesis/scripts/switch_crypto_profile.py <<'EOF'
import sys
print('switch_crypto_profile.py stand-in: argv=', sys.argv[1:])
EOF"
docker exec mockopin_rehearsal_client sh -c "cat > /config/campaign_client_runner.py <<'EOF'
import sys, json, os
print(json.dumps({'label': sys.argv[sys.argv.index('--label')+1] if '--label' in sys.argv else None,
                   'crypto_profile': os.environ.get('CRYPTO_PROFILE'),
                   'remote_gateway_host': os.environ.get('REMOTE_GATEWAY_HOST'),
                   'call_count': 5}))
EOF"

docker run -d --name mockopin_rehearsal_control --network mockopin_rehearsal_net \
  -v "$REPO_ROOT/thesis:/repo/thesis" \
  -v "$KEYDIR:/keys:ro" \
  python3:3.12-alpine sleep 3600 >/dev/null 2>&1 || \
docker run -d --name mockopin_rehearsal_control --network mockopin_rehearsal_net \
  -v "$REPO_ROOT/thesis:/repo/thesis" \
  -v "$KEYDIR:/keys:ro" \
  python:3.12-alpine sleep 3600 >/dev/null

docker exec mockopin_rehearsal_control apk add --no-cache openssh-client >/dev/null 2>&1
docker exec mockopin_rehearsal_control mkdir -p /root/.ssh
docker cp "$KEYDIR/campaign_key" mockopin_rehearsal_control:/root/.ssh/campaign_key
docker exec mockopin_rehearsal_control chmod 600 /root/.ssh/campaign_key

echo "Rehearsal ready. Run:"
echo "  docker exec mockopin_rehearsal_control python3 /repo/thesis/results/v8/campaign/scripts/tests/rehearsal_runner.py"
echo "Teardown: bash tests/rehearsal_teardown.sh"
