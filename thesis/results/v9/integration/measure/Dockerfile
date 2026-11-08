# v9, Fase 1, T6: gateway+proxy+bench rodando dentro do MESMO conteiner
# (keylog/pcap compartilhados via filesystem local, nunca entre
# containers -- ver measure.sh). Build context = thesis/results/v9/
# integration/ (o diretorio pai deste Dockerfile), nao measure/ --
# precisa copiar gateway/, proxy/ e bench/ tambem. Builda contra o
# toolchain Go corrigido (mesma imagem mockopin-v9-toolchain que
# gateway/Dockerfile e proxy/Dockerfile usam).
FROM mockopin-v9-toolchain AS goroot

FROM alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a AS build
COPY --from=goroot /go-src /usr/local/go
ENV PATH="/usr/local/go/bin:${PATH}"
WORKDIR /src
COPY gateway ./gateway
COPY proxy ./proxy
COPY bench ./bench
# Decisao 55, item 1: -trimpath + GOARCH explicito -- ver mesmo
# comentario em gateway/Dockerfile.
RUN cd gateway && CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -o /out/gateway .
RUN cd proxy && CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -o /out/proxy .
RUN cd bench && CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -o /out/bench .

FROM alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a
RUN apk add --no-cache tcpdump tshark bash gawk
COPY --from=build /out/gateway /out/proxy /out/bench /usr/local/bin/
COPY measure/measure.sh /usr/local/bin/measure.sh
RUN chmod +x /usr/local/bin/measure.sh
COPY measure/certs /certs
ENTRYPOINT ["/usr/local/bin/measure.sh"]
