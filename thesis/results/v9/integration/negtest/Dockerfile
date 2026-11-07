# v9, Fase 1, T7 follow-up: testes negativos (lacunas b2/b3) contra o
# gateway/proxy reais da v9, nao so a suite de testes Go isolada.
FROM mockopin-v9-toolchain AS goroot

FROM alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a AS build
COPY --from=goroot /go-src /usr/local/go
ENV PATH="/usr/local/go/bin:${PATH}"
WORKDIR /app
COPY go.mod ./
COPY *.go ./
RUN CGO_ENABLED=0 GOOS=linux go build -o /negtest

FROM alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a
COPY --from=build /negtest /negtest
ENTRYPOINT ["/negtest"]
