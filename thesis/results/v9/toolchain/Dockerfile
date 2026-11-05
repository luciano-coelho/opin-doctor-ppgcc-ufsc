# syntax=docker/dockerfile:1
#
# v9, Fase 1, T2+T3: toolchain Go reproduzivel e patch real do AND
# (dupla assinatura TLS, crypto/tls). Compila o Go a partir do
# codigo-fonte oficial, na tag fixada go1.27.3 (commit
# 2aae1000ea1d4b28923b96db28acf4e3b99d6aff, verificado contra
# go.googlesource.com/go nesta sessao), aplica patches/and.patch via
# `git apply` se o arquivo nao estiver vazio, e roda a suite de testes
# do pacote crypto/tls (original + os 18 testes do AND) contra o
# toolchain resultante.
#
# Versao escolhida (decisao desta sessao, ver DECISIONS.md da v9):
# go1.27.3, nao o go1.27rc2 que a v8 usou. Motivos:
#   1. go1.27rc2 e um release candidate, nunca promovido a estavel; a v9
#      comeca um mecanismo novo e mais sensivel (fork do proprio crypto/tls),
#      nao ha razao para construir sobre uma base pre-lancamento quando
#      a final (go1.27.0, 2026-08-19) e os patches seguintes ja existem.
#   2. go1.27.3 (lancado 2026-10-19) inclui uma correcao de seguranca em
#      crypto/x509 que go1.27rc2 nao tem -- relevante aqui porque o
#      mecanismo AND depende diretamente da verificacao de cadeia do
#      crypto/x509 (duas cadeias independentes, EKU, SAN).
#   3. E exatamente a versao que o patch de referencia externo do Luciano
#      (~220 linhas em 6 arquivos + dual.go + 17 testes) ja foi validado
#      contra, fora deste repositorio -- usar a mesma versao aqui elimina
#      qualquer desvio de versao entre essa validacao externa e a
#      reconstrucao feita dentro deste container.
#
# Imagem golang:1.27.3-alpine usada SOMENTE como compilador de bootstrap
# (GOROOT_BOOTSTRAP) -- o codigo-fonte que de fato se torna o toolchain
# desta imagem e clonado fresco de go.googlesource.com/go na tag
# go1.27.3, nao reaproveitado do /usr/local/go/src da imagem bootstrap,
# para que o commit realmente compilado seja verificavel contra a tag
# publica, nao apenas confiado de uma camada Docker de terceiro.

FROM golang:1.27.3-alpine@sha256:d200d2dd76b03a99b52651fd1325aff7dcd35422c35c01bac56571b0507f3deb AS bootstrap

FROM alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a AS builder
RUN apk add --no-cache git bash build-base

COPY --from=bootstrap /usr/local/go /usr/local/go-bootstrap
ENV GOROOT_BOOTSTRAP=/usr/local/go-bootstrap

WORKDIR /go-src
RUN git clone --depth 1 --branch go1.27.3 https://go.googlesource.com/go . \
    && actual_commit="$(git rev-parse HEAD)" \
    && expected_commit="2aae1000ea1d4b28923b96db28acf4e3b99d6aff" \
    && echo "go1.27.3 commit: ${actual_commit}" \
    && if [ "${actual_commit}" != "${expected_commit}" ]; then \
         echo "FATAL: go1.27.3 tag resolved to ${actual_commit}, expected ${expected_commit} (tag mutated or clone tampered with)" >&2; \
         exit 1; \
       fi \
    && echo "${actual_commit}" > /go-src-commit.txt

# patches/and.patch: the real AND mechanism (T3) -- dual.go (304 lines)
# plus changes to 6 existing files (529 lines total outside dual.go and
# the 718-line dual_test.go). Was empty in T2, to prove the
# reproducible build+test pipeline against vanilla go1.27.3 first; this
# same Dockerfile, unchanged below this COPY, applies and tests
# whichever content this file holds.
COPY patches/and.patch /tmp/and.patch
# --directory=src/crypto/tls: the patch's own paths are relative to
# crypto/tls itself (a/common.go, not a/src/crypto/tls/common.go,
# since it was generated from a diff rooted there) -- git apply
# resolves paths against the REPO ROOT regardless of the shell's own
# cwd, not against whatever directory this RUN happens to `cd` into
# first; found live, the hard way, when a first version of this step
# (`cd src && git apply ...`) reported success (exit 0) while silently
# "Skipping" every single file, applying nothing at all. --directory
# is git apply's own supported way to prepend a prefix to every path
# in a patch generated with a different root.
RUN if [ -s /tmp/and.patch ]; then \
      echo "applying patches/and.patch" \
      && git apply --whitespace=nowarn --directory=src/crypto/tls /tmp/and.patch \
      && sha256sum /tmp/and.patch | awk '{print $1}' > /and-patch-sha256.txt; \
    else \
      echo "patches/and.patch is empty -- building vanilla go1.27.3 (T2 baseline, no fork yet)" \
      && echo "(no patch applied)" > /and-patch-sha256.txt; \
    fi

WORKDIR /go-src/src
RUN ./make.bash

ENV GOROOT=/go-src
ENV PATH="/go-src/bin:${PATH}"
RUN go version

# crypto/tls's own test suite, unmodified -- this is T2's actual proof
# that the reproducible toolchain works end to end (clone -> verify
# commit -> optionally patch -> build -> test), before any fork code is
# written. `-count=1` disables the test cache so this always re-runs for
# real. Expected to be green except any test that requires real internet
# access (a known, pre-existing property of this suite, not something
# this build introduces).
WORKDIR /go-src/src/crypto/tls
# set -o pipefail: without it, `go test | tee` always reports tee's own
# exit code (0) regardless of whether go test itself failed -- a failing
# test would silently NOT fail this build step. bash is already
# installed above specifically for this.
RUN bash -o pipefail -c "go test -count=1 -v ./... 2>&1 | tee /crypto_tls_test_output.txt"

WORKDIR /go-src
RUN { \
      echo "{"; \
      echo "  \"go_tag\": \"go1.27.3\","; \
      echo "  \"go_commit\": \"$(cat /go-src-commit.txt)\","; \
      echo "  \"bootstrap_image\": \"golang:1.27.3-alpine@sha256:d200d2dd76b03a99b52651fd1325aff7dcd35422c35c01bac56571b0507f3deb\","; \
      echo "  \"builder_base_image\": \"alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a\","; \
      echo "  \"and_patch_sha256\": \"$(cat /and-patch-sha256.txt)\","; \
      echo "  \"built_at_utc\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\""; \
      echo "}"; \
    } > /build_metadata.json \
    && cat /build_metadata.json

CMD ["sh"]
