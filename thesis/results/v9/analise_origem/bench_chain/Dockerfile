# Degrau 1, Etapa 1, item 5 (chain validation) -- mesma toolchain do projeto.
FROM mockopin-v9-toolchain AS goroot

FROM alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a AS build
COPY --from=goroot /go-src /usr/local/go
ENV PATH="/usr/local/go/bin:${PATH}"
WORKDIR /app
COPY go.mod ./
COPY *.go ./
RUN CGO_ENABLED=0 GOOS=linux go build -o /bench-chain

FROM alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a
COPY --from=build /bench-chain /bench-chain
ENTRYPOINT ["/bench-chain"]
