# Mock Service Open Source

This solution provides a complete local instance of Mock mTLS gateway and OpenID Provider, including all components needed to adhere to FAPI standards.

## Prerequisites

To run Mock OS, ensure you have the following tools installed:

- **Docker**
- **Node.js**

### 1. Generate PKI Certificates
To generate the required certificates, run the command below. This step is required only once and will generate a new CA along with the necessary server certificates for the MTLS agent.

```bash
make certs
```

**Aviso:** todas as chaves geradas por este repositório (PKI acima, e as duas
seções seguintes) são chaves de demonstração para uso local, nunca chaves de
produção. Nenhum diretório de chave privada deste repositório é versionado
(`certs/.gitignore`, `mock_as/crypto-profiles/.gitignore`,
`insurance-server-lambdas/.../crypto-profiles/.gitignore`); rode os comandos
abaixo sempre que precisar gerar/rotacionar.

#### 1.1 Rotacionar as chaves do client_one (RSA-2048) e a chave PQC isolada

`client_one` é o único cliente cuja chave de assinatura/cifragem é lida pelo
caminho real da campanha v9 em todos os perfis (sem depender de
`V9_HARNESS`). Para regenerá-la em 2048 bits (em vez do 4096 herdado) sem
tocar em `mtls`/`op`/`client_two`:

```bash
docker-compose run certmaker ./main --org_id="<uuid>" -client-one-rsa2048
```

Para gerar só a chave PQC isolada (`client_one_pqc.crt/.key`, ML-DSA-65),
assinada pela CA já existente em disco:

```bash
docker-compose run certmaker ./main --org_id="<uuid>" -pqc-client-only
```

Veja `certs/main.go` (`flag.Bool`/`flag.String` no `main()`) para as demais
flags de rotação parcial (hybrid, resign-all, etc.) e a Decisão que registrou
cada uma em `thesis/results/v9/DECISIONS.md`.

#### 1.2 Gerar as chaves de assinatura do AS e do RS (classic/hybrid/pqc)

As 6 chaves de assinatura usadas por `mock_as` (Authorization Server) e por
`insurance-server-lambdas` (Resource Server) nos 3 perfis de crypto
(`classic`, `hybrid`, `pqc`) ficam fora da PKI acima — são JWKs/PKCS8
separados, lidos em runtime via `CRYPTO_PROFILE`. Geração requer Node ≥24
(suporte experimental a ML-DSA no Web Crypto; o Node do host, se for mais
antigo, falha com `ERR_OSSL_UNSUPPORTED`), por isso sempre via Docker:

```bash
docker run --rm -v "$(pwd):/work" -w /work node:24-alpine \
  node mock-service-os/certs/generate-crypto-profiles.mjs
```

Escreve `mock_as/crypto-profiles/{classic,hybrid,pqc}.json` e
`insurance-server-lambdas/src/main/resources/crypto-profiles/{classic,hybrid,pqc}.json`
— os 6 arquivos, todos ignorados pelo git. Idempotente: pode rodar de novo a
qualquer momento para rotacionar (gera chaves novas e independentes a cada
execução, nunca reaproveita bytes da chave anterior).

#### 1.3 Material legado sem valor de segurança

`cs_config.json` (raiz do repositório) e as capturas em
`thesis/results/v1/` contêm certificados/chaves de demonstração antigos
(parte herdada do repositório upstream `br-openinsurance/MockOPIN`, parte
gerada por este fork) — já públicos no histórico do git e sem relação com o
caminho real da campanha v9. Os campos `mtls.key`/`mtls2.key` de
`cs_config.json` são chaves RSA-4096 legadas reais, mas sem valor de
segurança (apenas identidade mTLS de teste local, nunca usadas em produção
nem na campanha oficial). Os campos `mtls.key` em
`thesis/config/config_template_*.json` são placeholders curtos (não chaves
funcionais de nenhum algoritmo usado neste projeto) — confirmado por
tamanho: 72 caracteres base64 de corpo, muito abaixo do mínimo de qualquer
chave real aqui (RSA-2048 ≈342, ML-DSA-65 ≈43 só o seed). Nenhum desses
arquivos precisa ser regenerado pelos scripts acima.

### 2. Create local host entries
You need to add api.local and auth.local as aliases to localhost at the hosts file.

```bash
127.0.0.1 api.local
127.0.0.1 auth.local
```

### 3. Start eveything up
To have a fully local instance running you can only spin up all the components using singles containers with the command:
```bash
make run
```

### 4. Start eveything up with lambda context using localstack
To have a fully local instance running with the aws lambda context you need to spin up all the components using singles containers and the api with localstack with the command:

`ps: This will require a powerfull machine to run properly`
```bash
make run-local-localstack
```

# Get a token using the certs

```bash
curl -v \
  --cert ./certs/client_one.crt \
  --key ./certs/client_one.key \
  --cert-type PEM \
  --key-type PEM \
  -u client:1234 \
  -d "grant_type=client_credentials&scope=openid" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  https://auth.local/token -k

  curl -v \
  --cert ./certs/client_one.crt \
  --key ./certs/client_one.key \
  --cert-type PEM \
  --key-type PEM \
  -u client:1234 \
  -d "token=UXc7zN2knByBYD2conPeRgysCRlfL-FbsKmyUoJylnU" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  https://auth.local/token/introspection -k


  curl -v \
  --cert ./certs/client_one.crt \
  --key ./certs/client_one.key \
  --cert-type PEM \
  --key-type PEM \
  -H "Authorization: Bearer UXc7zN2knByBYD2conPeRgysCRlfL-FbsKmyUoJylnU" \
  https://api.local/ -k
  ```
