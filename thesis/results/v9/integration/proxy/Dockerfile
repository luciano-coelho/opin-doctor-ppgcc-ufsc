# v9, Fase 1, T5: client (fork of tls_kem_proxy) built against the
# patched go1.27.3 toolchain (AND dual-certificate mechanism). See
# gateway/Dockerfile's own comment -- same toolchain image, same
# certs-via-COPY policy, no bind mounts.
FROM mockopin-v9-toolchain AS goroot

FROM alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a AS build
COPY --from=goroot /go-src /usr/local/go
ENV PATH="/usr/local/go/bin:${PATH}"
WORKDIR /app
COPY go.mod ./
COPY *.go ./
# Decisao 55, item 1: -trimpath + GOARCH explicito -- ver mesmo
# comentario em gateway/Dockerfile.
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -o /proxy

FROM alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a
COPY --from=build /proxy /proxy
COPY certs /certs
ENTRYPOINT ["/proxy"]
