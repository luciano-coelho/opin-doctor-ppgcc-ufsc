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

## T3, concluida e revisada: patch real aplicado e testado

`patches/and.patch` contem o mecanismo AND real: `dual.go` (321
linhas) + mudancas em 6 arquivos existentes (`common.go`, `conn.go`,
`handshake_client.go`, `handshake_client_tls13.go`,
`handshake_messages.go`, `handshake_server_tls13.go`, 543 linhas no
total fora de `dual.go`/testes, mais um registro de 5 linhas em
`tls_test.go`) + `dual_test.go` (879 linhas, 23 testes). SHA-256 do
patch: `093338402cce147920a4f63d2a2b8947f0fc8f275bae36f33a0dd8badeaad572`.

**Bug real encontrado e corrigido no proprio Dockerfile, antes do
primeiro resultado:** a primeira versao deste passo fazia `cd src &&
git apply ... && cd ..`, e reportava sucesso (exit 0) enquanto
"Skipava" (`Skipped patch`) todo arquivo do patch, sem aplicar nada --
`git apply` resolve os caminhos do patch contra a RAIZ do repositorio
git, nao contra o diretorio corrente do shell. Corrigido com
`git apply --directory=src/crypto/tls`. **Endurecido depois**: o passo
agora conta quantos arquivos o proprio `and.patch` toca (via
`grep -c '^diff --git'`) e falha o build explicitamente (`exit 1`) se
`git status` nao mostrar exatamente esse numero de arquivos alterados
em `src/crypto/tls` -- confirmado em um container de diagnostico
isolado que, reintroduzindo deliberadamente o bug antigo, a checagem
agora detecta a divergencia (9 esperados vs. 0 reais) em vez de deixar
passar.

**Resultado real, suite completa de `crypto/tls` (original + os 23
testes do AND), contra o toolchain go1.27.3 reconstruido a partir do
patch real, via o pipeline completo (clone -> verifica commit ->
`git apply` endurecido -> `make.bash` -> teste):** `ok crypto/tls
69.728s` -- **237 PASS, 0 FAIL, 0 SKIP** no nivel dos testes
nomeados (214 da suite original, inalterados, + 23 do AND). Contando
tambem as subcelulas internas de `TestBogoSuite` (a suite de
conformidade da BoringSSL, embutida e offline): 2.991 PASS, 0 FAIL,
2.278 SKIP -- os skips sao todos internos a essa matriz de
conformidade (decisoes proprias do BoGo sobre quais casos aplicam a
esta build), nao relacionados a rede; `TestVerifyHostname`,
`TestRealResumption` e o proprio `TestBogoSuite` (nivel superior)
passam, confirmando rede real disponivel no container. Medicao de
tamanho de fio (`TestDualWireSizeMeasurement`): mensagem Certificate
classica-so 814 B vs. dual (classica+ML-DSA-65) 6.355 B (+680,7%);
campo de assinatura do CertificateVerify classico-so 256 B vs. dual
3.567 B (+1.293,4%); cadeia PQ isolada 5.533 B.

Detalhe completo, incluindo o teste do impostor lado a lado (par
estrito/nao-estrito), a decisao sobre retomada de sessao e
HelloRetryRequest, a tabela por arquivo, e a decisao sobre o tamanho
do patch (543 linhas fora de `dual.go`/testes, acima do ~400 esperado,
seguido como esta por decisao do Luciano): Decisoes 6 e 7 em
`DECISIONS.md` da v9.
