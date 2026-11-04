# v9 Fase 1, T2: toolchain Go reproduzivel

Build local, em container, do Go a partir do codigo-fonte oficial, numa
tag fixada, para servir de base ao fork de `crypto/tls` que o Hibrido-AND
(D2/D3) exige. Nada de AWS aqui; nada e publicado fora deste repositorio.

## Versao escolhida: go1.27.3

A v8 usou `go1.27rc2` (release candidate). Para a v9, a versao final
escolhida e **go1.27.3** (lancado 2026-10-19), nao a rc2 nem a 1.27.0
simples, pelos tres motivos registrados no cabecalho do `Dockerfile` e
na Decisao correspondente de `DECISIONS.md`:

1. rc2 nunca foi promovida a estavel; a v9 comeca um mecanismo mais
   sensivel (fork do proprio `crypto/tls`), sem motivo para partir de
   uma base pre-lancamento.
2. go1.27.3 inclui uma correcao de seguranca em `crypto/x509` que a rc2
   nao tem, e o mecanismo AND depende diretamente da verificacao de
   cadeia desse pacote (duas cadeias independentes).
3. E a mesma versao contra a qual o patch de referencia externo do
   Luciano (fora deste repositorio) ja foi validado -- usar a mesma aqui
   elimina qualquer desvio de versao entre essa validacao e a
   reconstrucao feita dentro deste container.

Commit da tag `go1.27.3`, verificado nesta sessao contra
`go.googlesource.com/go`: `2aae1000ea1d4b28923b96db28acf4e3b99d6aff`. O
`Dockerfile` falha o build se o clone resolver para um commit diferente.

## O que o Dockerfile faz

1. Usa `golang:1.27.3-alpine` (pinado por digest) **somente** como
   compilador de bootstrap (`GOROOT_BOOTSTRAP`).
2. Clona `go.googlesource.com/go` fresco, na tag `go1.27.3`, e confirma o
   commit contra o valor acima.
3. Aplica `patches/and.patch` via `git apply`, se o arquivo nao estiver
   vazio. Nesta etapa (T2) o arquivo esta vazio de proposito -- o
   objetivo aqui e provar que o pipeline de build+teste funciona ponta a
   ponta ANTES de qualquer codigo do fork existir. A T3 substitui esse
   arquivo pelo patch real (~220 linhas em 6 arquivos + `dual.go`) e usa
   este mesmo Dockerfile, sem alteracao, para aplica-lo e testa-lo.
4. Roda `./make.bash` para construir o toolchain a partir da fonte
   (patcheada ou nao).
5. Roda a suite de testes do pacote `crypto/tls`, sem modificacao
   (`go test -count=1 -v ./...` dentro de `src/crypto/tls`), contra o
   toolchain recem-construido.
6. Escreve `/build_metadata.json` dentro da imagem com a versao do Go, o
   commit, os dois digests de imagem base, e o SHA-256 do patch aplicado
   (ou a marca explicita de que nenhum foi aplicado).

## Como rodar

```
cd thesis/results/v9/toolchain
docker build -t mockopin-v9-toolchain .
docker run --rm mockopin-v9-toolchain cat /crypto_tls_test_output.txt
docker run --rm mockopin-v9-toolchain cat /build_metadata.json
```

## Resultado esperado (T2, patch vazio)

A suite de `crypto/tls` deve passar integralmente, com excecao de
qualquer teste que dependa de acesso real a internet (propriedade
preexistente dessa suite, nao algo introduzido por este build). O
resultado real desta rodada esta registrado na Decisao de T2 em
`DECISIONS.md` da v9, junto com a contagem exata de PASS/FAIL/SKIP.

## O que a T3 muda aqui

Nada neste `Dockerfile`. A T3 escreve o patch real em
`patches/and.patch`, relança o mesmo build, e os 17 testes obrigatorios
do mecanismo AND (especificados no pedido original da v9) rodam contra
o toolchain patcheado resultante -- ainda dentro deste mesmo container,
ainda sem AWS.
