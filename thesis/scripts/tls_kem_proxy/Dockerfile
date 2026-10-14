# Decision 66: tls_kem_proxy as a precompiled binary, specified here --
# NOT wired into opin_flow.py's live `docker run ... go run .` path this
# session (that stays today's lab behavior, unchanged, Decision 45's
# original proposal). This Dockerfile is what Decision 50's
# deliver_images.sh would eventually build/deliver, once that wiring
# happens.
#
# Multi-stage: the builder stage compiles the binary ONCE; the runtime
# stage copies only the binary, never the Go toolchain or source --
# no module download at runtime (there are none to download anyway:
# go.mod declares no external requires, confirmed by reading it, only
# the standard library's own crypto/tls -- but the pattern holds even
# if that ever changes, since `go build` resolves/vendors everything
# at BUILD time, not when the container starts).

# syntax=docker/dockerfile:1
FROM golang:1.27-rc-alpine@sha256:c5aca77a4d16cb6688dbf3ccade67eff6f05ee208bc854d060e6947f5c27e23c AS builder
WORKDIR /src
COPY go.mod main.go ./
# CGO_ENABLED=0: a static binary, no libc dependency on the runtime
# image -- lets the runtime stage be `scratch` or `alpine` without
# worrying about glibc/musl mismatches. -trimpath: no builder-machine
# absolute paths baked into the binary (reproducibility, not a security
# requirement here, but costs nothing).
RUN CGO_ENABLED=0 go build -trimpath -o /tls_kem_proxy .

FROM alpine:3.20
# Non-root, minimal -- this binary never needs root (the campaign's own
# servers do, for tc/netem, but this proxy is client-side only and
# never touches networking config, only dials outbound).
RUN adduser -D -u 10001 proxyuser
COPY --from=builder /tls_kem_proxy /usr/local/bin/tls_kem_proxy
USER proxyuser
ENTRYPOINT ["/usr/local/bin/tls_kem_proxy"]
