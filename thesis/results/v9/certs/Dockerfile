# v9, Fase 1, T4+: gera e valida os certificados dos 4 perfis
# (Classico, PQC, Hibrido-v8 em RSA-2048, Hibrido-AND com duas cadeias
# independentes). Mesma versao fixada da T2/T3, go1.27.3. SAN por
# build-arg (default: loopback, para testes locais) -- ver
# DECISIONS.md, Decisao 10/11: na campanha real, estes args recebem os
# enderecos reais da frota, resolvidos no deploy, nunca versionados.
FROM golang:1.27.3-alpine@sha256:d200d2dd76b03a99b52651fd1325aff7dcd35422c35c01bac56571b0507f3deb
WORKDIR /app
COPY go.mod main.go ./
COPY v8_pqc ./v8_pqc
ARG SERVER_DNS="mtls,auth.local,matls-auth.local,api.local,matls-api.local,directory,directory.local,keystore"
ARG SERVER_IPS="127.0.0.1,::1"
ARG CLIENT_DNS="opin-client-one"
RUN go run main.go \
      -server-dns="${SERVER_DNS}" \
      -server-ips="${SERVER_IPS}" \
      -client-dns="${CLIENT_DNS}" \
      > /report.txt 2>&1 \
    || { cat /report.txt; echo "FATAL: certificate generation/validation failed" >&2; exit 1; }
RUN cat /report.txt
