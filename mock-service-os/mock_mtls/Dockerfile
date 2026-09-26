# Pinned by digest, not a floating "golang:1.27-rc" tag -- confirmed live
# that a rebuild against the floating tag mid-thesis silently shifted
# handshake_bytes for a profile whose curve config didn't change at all.
FROM golang:1.27-rc@sha256:6a284ec7a8c67eff5882aaa53b07a57ee397553f8c85a92e5fc97c517f12201f
# ML-DSA-65 mTLS client cert support (Etapa 3) needs crypto/mldsa +
# crypto/x509/crypto/tls ML-DSA wiring, only in Go 1.27, unreleased as of
# 2026-08 -- see thesis/results/experiment2 - PQC/DECISIONS.md (Decision 2).
# iproute2 (tc/netem) + iputils-ping: used by thesis/scripts/set_latency.sh
# to inject and verify artificial WAN latency for Experiment 1. Not needed
# for normal gateway operation.
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends iproute2 iputils-ping \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# Download Go modules
# COPY certs /app/certs
COPY go.mod ./
COPY go.sum ./
# Copy the entrypoint script into the container
COPY entrypoint.sh ./
# Copy the source code. Note the slash at the end, as explained in
# https://docs.docker.com/reference/dockerfile/#copy
COPY *.go ./
RUN go mod download
RUN CGO_ENABLED=0 GOOS=linux go build -o /mtls_go
# Make the entrypoint script executable
RUN chmod +x ./entrypoint.sh
EXPOSE 443

ENTRYPOINT ["./entrypoint.sh"]
# Run
CMD ["/mtls_go"]