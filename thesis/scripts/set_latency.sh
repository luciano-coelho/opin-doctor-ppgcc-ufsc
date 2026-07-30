#!/bin/bash
# Injects (or removes) artificial network latency on the mTLS gateway
# container's egress interface, to simulate the WAN RTT scenarios used in
# Experiment 1 (classical vs. PQC baseline comparison at increasing
# latency). Uses tc/netem inside the container itself (see the mtls
# service's `cap_add: NET_ADMIN` in docker-compose.yml and the
# iproute2/iputils-ping packages baked into mock-service-os/mock_mtls/Dockerfile).
#
# Why the gateway and not the host's docker bridge interface: on Windows
# with Docker Desktop, the bridge interface lives inside the Docker Desktop
# / WSL2 VM, not in a namespace reachable from a normal host shell. Applying
# netem on the target container's own eth0 works the same everywhere
# (Linux, macOS, Windows+Docker Desktop) since it only requires `docker exec`
# and NET_ADMIN on that one container -- no host-level network access needed.
# All Open Insurance / auth traffic transits through this single container
# (see README's End-to-End Consent Creation Flow), so this is the one place
# that captures round-trip latency for the whole OPIN flow.
#
# Usage:
#   ./set_latency.sh <ms>     supported: 0 14 30 140 225 320
#   ./set_latency.sh reset    alias for 0 -- removes any configured latency

set -euo pipefail

CONTAINER="insurance-server-lambdas-mtls-1"
IFACE="eth0"
ALLOWED_MS=(0 14 30 140 225 320)

usage() {
    echo "Usage: $0 <${ALLOWED_MS[*]// /|}|reset>" >&2
    exit 1
}

[ $# -eq 1 ] || usage
ARG="$1"
[ "$ARG" = "reset" ] && ARG="0"

valid=0
for v in "${ALLOWED_MS[@]}"; do
    [ "$ARG" = "$v" ] && valid=1
done
[ "$valid" -eq 1 ] || usage

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
    echo "Error: container $CONTAINER is not running." >&2
    exit 1
fi

# Always clear first -- "tc qdisc add" fails if a qdisc is already attached,
# and "tc qdisc del" on a clean interface is a harmless no-op (ignored below).
docker exec "$CONTAINER" tc qdisc del dev "$IFACE" root >/dev/null 2>&1 || true

if [ "$ARG" = "0" ]; then
    echo "Latency reset on $CONTAINER ($IFACE)."
else
    docker exec "$CONTAINER" tc qdisc add dev "$IFACE" root netem delay "${ARG}ms"
    echo "Latency set to ${ARG}ms on $CONTAINER ($IFACE)."
fi

echo "Current qdisc: $(docker exec "$CONTAINER" tc qdisc show dev "$IFACE")"
