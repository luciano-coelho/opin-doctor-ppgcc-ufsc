# v9, Fase 1, T4: gera e valida os certificados dos 4 perfis (Classico,
# PQC reaproveitado da v8, Hibrido-v8 em RSA-2048, Hibrido-AND com duas
# cadeias independentes). Mesma versao fixada da T2/T3, go1.27.3.
FROM golang:1.27.3-alpine@sha256:d200d2dd76b03a99b52651fd1325aff7dcd35422c35c01bac56571b0507f3deb
WORKDIR /app
COPY go.mod main.go ./
COPY v8_pqc ./v8_pqc
RUN go run main.go > /report.txt 2>&1 || { cat /report.txt; echo "FATAL: certificate generation/validation failed" >&2; exit 1; }
RUN cat /report.txt
