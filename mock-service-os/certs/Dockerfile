# Step 1: Build Stage.
# Higiene de reprodutibilidade (Etapa 1, adendo): go.mod deste modulo exige
# go 1.27rc2 -- golang:1.23-alpine (pin anterior) sempre falhava o build real.
# Mesmo digest ja usado e verificado em thesis/results/v9/certs/Dockerfile e
# thesis/results/v9/toolchain/Dockerfile, por coerencia de pin no projeto.
FROM golang:1.27.3-alpine@sha256:d200d2dd76b03a99b52651fd1325aff7dcd35422c35c01bac56571b0507f3deb AS builder

ENV GO111MODULE=on
ENV CGO_ENABLED=0
ENV GOOS=linux
ENV GOARCH=amd64

WORKDIR /app

COPY . .

RUN go mod download

RUN go build -o main .

# Step 2: Run Stage.
FROM alpine:latest

WORKDIR /

COPY --from=builder /app/main /

CMD ["./main"]
