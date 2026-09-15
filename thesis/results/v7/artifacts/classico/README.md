# Artefatos reais — perfil Clássico

Esta pasta existe como **prova de implementação verificável**, no mesmo
espírito de `artifacts/hybrid/` e `artifacts/pqc/`: cada afirmação de "isso
foi feito" vem com o artefato real capturado ao vivo, a explicação do
mecanismo, e o ponto exato do código-fonte. Para o Clássico especificamente,
a afirmação que precisa de prova é a **negativa**: nada de material
pós-quântico existe em nenhum dos quatro artefatos — e "nada existe" é
verificado da mesma forma rigorosa que "algo existe" é verificado nos outros
dois perfis, não apenas assumido por omissão.

Todo dado abaixo foi capturado ao vivo em `CRYPTO_PROFILE=classic`, no mesmo
sistema e pipeline (`tls_kem_proxy`, v7 Decision 1 — o Clássico também passa
pelo mesmo cliente Go agora, só pedindo curvas puramente clássicas) usado
para o lote de tamanho e latência.

---

## 1. Certificado clássico (`client_one.crt`)

### O artefato real

Arquivo bruto: [`client_one.crt`](client_one.crt). Versão decodificada:
[`client_one.crt.txt`](client_one.crt.txt) (`openssl x509 -text -noout`).

Bloco de extensões completo — **três extensões, nenhuma delas híbrida**:

```
X509v3 extensions:
    X509v3 Key Usage: critical
        Digital Signature
    X509v3 Extended Key Usage:
        TLS Web Client Authentication
    X509v3 Subject Alternative Name:
        DNS:auth.local, DNS:matls-auth.local, DNS:api.local, DNS:matls-api.local,
        DNS:directory, DNS:directory.local, DNS:keystore, IP Address:127.0.0.1, IP Address:::1
Signature Algorithm: sha256WithRSAEncryption
```

### A prova que realmente importa: confirmar a ausência, e verificar a única assinatura que existe

Dizer "o Clássico não tem extensões híbridas" olhando a decodificação acima
é confiar que eu não pulei nada. A prova real são duas checagens
independentes, ambas rodadas contra o arquivo real:

**1. Ausência confirmada programaticamente, não por inspeção visual** — os
três OIDs híbridos (`2.5.29.72/73/74`, ver `artifacts/hybrid/README.md`,
Seção 1) buscados sobre a lista real de extensões do certificado:

```
$ python -c "
from cryptography import x509
cert = x509.load_pem_x509_certificate(open('client_one.crt','rb').read())
hybrid_oids = {'2.5.29.72','2.5.29.73','2.5.29.74'}
print('Extensoes:', [e.oid.dotted_string for e in cert.extensions])
print('OIDs hibridos encontrados:', [e.oid.dotted_string for e in cert.extensions if e.oid.dotted_string in hybrid_oids])
"
Extensoes: ['2.5.29.15', '2.5.29.37', '2.5.29.17']
OIDs hibridos encontrados: []
```

Três extensões no total (Key Usage, Extended Key Usage, SAN), zero delas
híbrida — confirmado sobre a estrutura real do certificado, não por não
aparecer no trecho que eu escolhi mostrar.

**2. A única assinatura que existe verifica de verdade** — uma cadeia de
confiança X.509 comum, verificada com `openssl verify`, não assumida:

```
$ openssl verify -CAfile ca.crt client_one.crt
client_one.crt: OK
```

Saída completa em
[`verify_classic_cert_output.txt`](verify_classic_cert_output.txt). Ao
contrário do certificado híbrido (Seção 1 de `artifacts/hybrid/`), aqui não
há uma segunda assinatura para reconstruir e verificar separadamente — só
existe a RSA, e ela passa numa verificação de cadeia real e padrão, sem
nenhuma ferramenta especial.

Tamanho do certificado completo (DER): **1.494 bytes** — confirma o
`client_cert_der_bytes` medido em todo o lote v7 para este perfil, e é
2.953/6.859 bytes *menor* que PQC/Híbrido respectivamente, exatamente a
diferença que não ter nenhum material ML-DSA-65 embutido deveria produzir.

### Explicação do mecanismo

O Clássico usa a lógica de certificado mais simples do projeto: uma chave
RSA-4096 do titular, assinada uma única vez pela CA (`sha256WithRSAEncryption`),
sem nenhuma extensão além das três padrão de sempre (Key Usage, Extended Key
Usage, SAN). Não existe "pré-TBS" nem segunda assinatura — o certificado é
criado numa única chamada a `x509.CreateCertificate`, não duas como no
híbrido (Seção 1 de `artifacts/hybrid/README.md`). É o único dos três perfis
cuja lógica de geração nunca precisou mudar desde a v5 — a troca de chave
TLS que a v7 unificou (Decision 1) já era clássica aqui desde sempre.

### Referência ao código

`mock-service-os/certs/main.go`:
- `generateCert()`, linhas 647 em diante — a função que gerou
  `client_one.crt`. Note a ausência estrutural: nenhuma chamada a
  `hybridExtensions()`, nenhum campo `ExtraExtensions` com os OIDs híbridos,
  uma única chamada a `x509.CreateCertificate` (não duas como em
  `generateHybridCert()`, linhas 338–402, comparar diretamente). A ausência
  de material pós-quântico não é uma opção desligada em algum lugar — é
  simplesmente código que `generateCert()` nunca teve.

---

## 2. JWT real, decodificado (resposta do RS, `GET .../premium`)

### O artefato real

Token completo capturado ao vivo:
[`example_jwt_premium.txt`](example_jwt_premium.txt).

**Header decodificado:**
```json
{"alg": "PS256", "kid": "041486ea-f7b8-4b36-9dfb-fadf2966d0e8", "typ": "JWT"}
```

**Payload decodificado (chaves de topo):** `data`, `links`, `meta` — **sem**
`pqc`. Token completo: 1.483 caracteres (contra 7.430 do equivalente
Híbrido — a diferença quase inteira é o `pqc.signature` de 4.412 caracteres
que aqui simplesmente não existe).

### A prova que realmente importa: a assinatura verifica, e o campo `pqc` está genuinamente ausente

```
$ node thesis/scripts/verify_hybrid_jwt/verify_classic_jwt.mjs \
    insurance-server-lambdas/src/main/resources/crypto-profiles/classic.json \
    thesis/results/v7/artifacts/classico/example_jwt_premium_compact.txt

VERIFICATION RESULT: {
  "valid": true,
  "reason": "PS256 verified",
  "hasPqcClaim": false
}
```

Saída completa em [`verify_jwt_output.txt`](verify_jwt_output.txt). O script
(`thesis/scripts/verify_hybrid_jwt/verify_classic_jwt.mjs`, escrito para
este perfil) verifica a assinatura PS256 de verdade (padding RSA-PSS,
`crypto.verify` nativo do Node, contra a chave pública derivada de
`crypto-profiles/classic.json` — o mesmo arquivo que
`ResponseSigningService.java` carrega para assinar) **e** checa
programaticamente que `payload.pqc` não existe (`hasOwnProperty`, não
"não vi no JSON que imprimi") — as duas coisas que precisam ser verdade
para esta ser uma assinatura clássica genuína, não um híbrido com o campo
extra removido manualmente antes de eu olhar.

**Nota sobre a chave**: o `n` desta chave RSA é byte-idêntico ao
`classicSigningKey.n` usado no perfil Híbrido — o projeto reaproveita a
mesma identidade RSA do RS entre os dois perfis (o Híbrido só adiciona
ML-DSA-65 por cima, nunca troca a base clássica). Confirma que "Clássico" e
"a metade clássica do Híbrido" são, deliberadamente, a mesma coisa.

### Explicação do mecanismo

Um JWT clássico é a coisa mais simples possível: `ResponseSigningService`
monta os claims, nunca chama nada equivalente a `preparePayload()`'s injeção
de `pqc` (essa função é específica do signer híbrido, Seção 2 de
`artifacts/hybrid/README.md`), e assina uma vez com PS256 (RSA-PSS). Não há
canonicalização JCS envolvida — não existe um segundo conteúdo para tornar
reproduzível entre linguagens, porque não existe uma segunda assinatura.

### Referência ao código

`insurance-server-lambdas/src/main/java/com/raidiam/trustframework/
mockinsurance/crypto/ResponseSigningService.java`:
- `loadPs256Signer()`, linhas 140–160 — carrega `classic.json`, assina com
  `RSASSASigner`/`JWSAlgorithm.PS256` (Nimbus). Comparar com
  `loadHybridSigner()` (linha 212): aqui não há `preparePayload()`
  sobrescrito, então o `default` da interface (linha 92, que apenas devolve
  os claims sem tocar) é o que roda — a ausência do campo `pqc` é o
  comportamento padrão da interface, não uma exclusão especial para este
  perfil.
- `thesis/scripts/verify_hybrid_jwt/verify_classic_jwt.mjs` — a verificação
  rodada acima.

---

## 3. Entrada real no JWKS (Authorization Server, `/jwks`)

### O artefato real

Captura completa: [`jwks_auth.json`](jwks_auth.json) — resposta real de
`GET https://auth.local/jwks`, perfil Clássico:

```json
{
  "keys": [
    {"kty": "RSA", "use": "sig", "kid": "xQLs45xYyJr1omHs4qnB2rhes9qNFHIHQ5YPQKVJliM", "alg": "PS256", "e": "AQAB", "n": "pu8AVLEIfYppnbU0r2M1PNhCvYpGnVXbSXj...(truncado)"},
    {"kty": "RSA", "use": "enc", "kid": "AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k", "alg": "RSA-OAEP", "e": "AQAB", "n": "gbulO7BqCAKwVy3ZqrR033OM1Mp...(truncado)"}
  ]
}
```

Duas entradas `kty: "RSA"` comuns — uma de assinatura (PS256), uma de
cifragem (RSA-OAEP, para o JWE do `id_token`). Nenhum `kty: "HYBRID"`,
nenhum campo `pk_hybrid`, nenhum `alg` não-padrão.

### A prova que realmente importa: é um JWKS que qualquer biblioteca JOSE padrão já entende

Ao contrário dos outros dois perfis, aqui não há nada de exótico para
fechar o ciclo com uma verificação especial — **o próprio fato de este JWKS
ter exatamente a forma que `jose`/qualquer biblioteca padrão espera, sem
nenhuma adaptação, é a prova**. O `n` da entrada de assinatura acima é
byte-idêntico ao início do `pk_hybrid` do AS no perfil Híbrido
(`artifacts/hybrid/README.md`, Seção 3) — confirmando que a mesma chave
RSA do AS é reaproveitada entre Clássico e Híbrido, exatamente como no lado
RS (Seção 2 acima).

### Explicação do mecanismo

O AS, em modo clássico, nunca invoca nenhuma lógica de composição híbrida —
publica as duas chaves RSA (assinatura e cifragem) que sempre existiram no
projeto, desde antes de qualquer trabalho pós-quântico começar. Não é um
"híbrido com a metade removida" — é o código original, intocado.

### Referência ao código

O caminho de publicação de JWKS clássico do AS é o mesmo usado desde a v1
deste projeto (antes de qualquer perfil PQC/Híbrido existir) —
`mock-service-os/mock_as/utils/opin/configuration.js` seleciona qual
conjunto de chaves publicar com base em `CRYPTO_PROFILE`; para `"classic"`,
nenhum módulo de `hybridSigning.js`/`payloadExtensionVerification.js` é
sequer importado no caminho de execução.

---

## 4. Evidência do handshake TLS — nenhum grupo de troca de chave pós-quântico

### O artefato real

Linha de log real do gateway, perfil Clássico, via `tls_kem_proxy`:
[`handshake_log.json`](handshake_log.json).

```json
{
  "msg": "mTLS handshake complete",
  "tlsVersion": "TLS 1.3",
  "cipherSuite": "TLS_AES_128_GCM_SHA256",
  "curveID": "CurveP256",
  "clientCertBytes": 1494,
  "mtlsHandshakeBytes": 5052,
  "handshakeDurationMs": 17
}
```

`curveID: "CurveP256"` — uma curva elíptica clássica pura, sem nenhum
componente KEM. (A preferência do servidor lista P521/P384/P256 nessa
ordem — o cliente Go negociou P256, não necessariamente a primeira da
lista; TLS 1.3 deixa a escolha final depender também da preferência do
cliente, e isso não muda nada do que este artefato precisa provar.)

### A prova que realmente importa: confirmar programaticamente que NENHUM grupo com componente KEM foi negociado, e que a sessão ainda assim é fresca

```
$ docker run --rm --network insurance-server-lambdas_default \
    -v thesis/scripts/verify_kem_export:/src -v mock-service-os/certs:/certs:ro -w /src \
    golang:1.27-rc-alpine go run . classic /certs/client_one.crt /certs/client_one.key

connection 1: curveID=CurveP256 tlsVersion=TLS 1.3 exported(32B)=11f8dee31e3ef962310c1ce7b2947012d13a64a8cc3dd0a4d10515dd2d513134
connection 2: curveID=CurveP256 tlsVersion=TLS 1.3 exported(32B)=6bb68d296426bc17d6a750bd8762a3d299648ed57793c4d2125dfbd9793957df

RESULT: verificado -- ambas as conexoes negociaram CurveP256 (grupo=classic), e o material de chave exportado
(RFC 5705) e DIFERENTE entre as duas -- confirma que o segredo de sessao foi de fato derivado de uma troca de
chave nova a cada conexao, nao um valor fixo ou decorativo.
```

Saída completa em
[`verify_kem_export_output.txt`](verify_kem_export_output.txt). A mesma
ferramenta usada para Híbrido e PQC roda aqui com `-group classic`: ela
checa internamente que o `curveID` negociado está na lista de curvas
clássicas puras (`CurveP256`/`CurveP384`/`CurveP521`) — se qualquer grupo
com "MLKEM" no nome tivesse aparecido, o programa teria terminado em
`RESULT: FAIL`, não com sucesso. A exportação de material de chave (RFC
5705) confirma, como nos outros dois perfis, que o segredo de sessão é
genuinamente novo a cada conexão — aqui, via ECDHE efêmero puro, não KEM.

### Explicação do mecanismo

Antes da v7 (Decision 1), o Clássico nunca passava pelo `tls_kem_proxy` —
conectava direto ao gateway, e `mock_mtls`'s `serverCurvePreferences`
(valor padrão do pacote, nunca sobrescrito para este perfil) já era
puramente clássico. A v7 passou o Clássico pelo mesmo cliente Go que
PQC/Híbrido usam, mas isso não mudou a exigência do lado do servidor —
`CRYPTO_PROFILE=classic` nunca ativa nenhum branch de `init()` que troque
`serverCurvePreferences`, então o servidor continua oferecendo só curvas
clássicas, e o `tls_kem_proxy` (chamado com `-curve classic`, Decision 1 do
v7) pede exatamente isso do lado do cliente.

### Referência ao código

- `mock-service-os/mock_mtls/main.go`, linhas 88–89: `serverCurvePreferences
  = []tls.CurveID{tls.CurveP521, tls.CurveP384, tls.CurveP256}` — o valor
  padrão do pacote, nunca sobrescrito por `init()` para `CRYPTO_PROFILE=
  classic` (comparar com as linhas 114/137, onde `init()` sobrescreve esse
  valor especificamente para `"pqc"`/`"hybrid"`).
- `thesis/scripts/tls_kem_proxy/main.go`, caso `"classic"` do `switch` de
  curvas (ver `thesis/results/v7/DECISIONS.md`, Decision 1, para por que
  esse caso não precisa do truque de SNI que o caso `"classical"` legado
  usa).
- `thesis/scripts/verify_kem_export/main.go` — a mesma ferramenta das
  Seções 4 de `artifacts/hybrid/` e `artifacts/pqc/`, aqui invocada com
  `classic`.

---

## 5. `id_token` real, decodificado — assinatura migrada, criptografia da própria mensagem ainda clássica por limitação real

### O artefato real

Capturado ao vivo do campo `id_token` de uma resposta real `POST /token`
(fluxo completo, perfil Clássico): [`id_token_raw.txt`](id_token_raw.txt).

Ao contrário dos artefatos das Seções 1–4 (todos JWS de 3 segmentos), este
é um **JWE de 5 segmentos** — o `id_token` não é apenas assinado, é também
**cifrado**:

```
$ node decrypt_and_verify_id_token.mjs classic id_token_raw.txt   # (dentro do container `auth`)

id_token: 1812 chars, 5 segments (JWE compact serialization)
JWE protected header: {"alg":"RSA-OAEP","enc":"A256GCM","cty":"JWT","kid":"92297d36-...","iss":"https://auth.local","aud":"client_one"}
Decrypted inner JWS: 678 chars, 3 segments
Inner JWS header: {"alg":"PS256","kid":"xQLs45xYyJr1omHs4qnB2rhes9qNFHIHQ5YPQKVJliM"}
Inner JWS payload (decoded, complete): {
  "sub": "usuario1@seguradoramodelo.com.br",
  "acr": "urn:brasil:openinsurance:loa3",
  "nonce": "CTtar5YUNixk",
  "aud": "client_one",
  "exp": 1789354423,
  "iat": 1789350823,
  "iss": "https://auth.local"
}
Inner JWS signature length (bytes): 256
VERIFICATION RESULT: {"valid": true, "reason": "PS256 verified"}
```

Saída completa em
[`verify_id_token_output.txt`](verify_id_token_output.txt).

### A prova que realmente importa: a assinatura interna verifica de verdade; a cifra externa é RSA-OAEP clássico, e é preciso dizer isso sem meio-termo

**Duas camadas, duas provas diferentes.** A camada de dentro (a assinatura)
é verificada de verdade: decifrado o JWE, a assinatura PS256 sobre
`header.payload` confirma válida contra a chave pública do AS
(`client_one.jwks`'s par correspondente à chave privada de decifragem —
o AS assina com sua própria chave de assinatura, PS256/RSA, e cifra para a
chave pública de cifragem que o CLIENTE registrou). Essa camada está
migrada e medida exatamente como os demais artefatos desta pasta.

A camada de fora (a cifragem, `alg: "RSA-OAEP"`) é **classica em todos os
três perfis, sem exceção** — inclusive no PQC (Seção 5 do README daquele
perfil). Isso não é uma lacuna deste protótipo: não existe hoje nenhum
padrão JOSE/COSE para cifragem pós-quântica (o rascunho que existia foi
retirado do grupo de trabalho do IETF) — `thesis/docs/
Cruzamento_SAD_vs_Experimentos.md` documenta esse achado com mais detalhe.
Capturar esse artefato aqui, no Clássico, serve de baseline honesto: aqui a
cifra clássica é exatamente o que se espera (nada mudou), e é o mesmo
mecanismo que aparece, sem alternativa disponível, nos outros dois perfis.

### Explicação do mecanismo

O `id_token` é construído e assinado inteiramente dentro do código interno
do `oidc-provider` (`lib/models/id_token.js`), depois imediatamente cifrado
(RSA-OAEP + AES-256-GCM, JWE compacto) antes de a resposta HTTP sair do
processo — não há nenhum gancho entre a assinatura e a cifragem no
`oidc-provider` 9.5.1. A cifragem é sempre **para a chave pública de
cifragem que o cliente registrou** (aqui, `client_one.jwks`'s entrada
`use: "enc"`), não para uma chave do próprio AS — é assim que a
confidencialidade do `id_token` funciona no OIDC: o AS cifra para quem vai
ler (o cliente), não para si mesmo.

### Referência ao código

- `mock-service-os/mock_as/utils/opin/configuration.js`, linha 330:
  `idTokenEncryptionAlgValues: ['RSA-OAEP']` — o único algoritmo de
  cifragem de `id_token` habilitado, em qualquer perfil.
- `mock-service-os/mock_as/mongo-seed/init_clients.json`: registro do
  cliente com `id_token_encrypted_response_alg: "RSA-OAEP"`.
- `mock-service-os/certs/client_one.jwks`: par de chaves RSA-OAEP do
  cliente (`use: "enc"`) usado para decifrar acima.
- `thesis/scripts/verify_hybrid_jwt/decrypt_and_verify_id_token.mjs` — a
  verificação rodada acima.

---

## 6. `client_assertion` real — a assinatura que de fato autentica o cliente (não o access_token)

### Por que este artefato existe

`thesis/docs/Cruzamento_SAD_vs_Experimentos.md` originalmente classificava
o passo 8 do SAD ("Token de acesso") como coberto por "assinatura híbrida,
medida" — impreciso: o `access_token` capturado ao vivo é uma string opaca
de 43 caracteres (`certificateBoundAccessTokens: true`, sem
`formats.AccessToken` configurado — o padrão do `oidc-provider`), **sem
nenhuma assinatura**. A assinatura real que autentica o cliente nesse passo
é o `client_assertion` (`private_key_jwt`) — o JWT que o próprio cliente
assina para se autenticar em `POST /token`. Este artefato fecha essa lacuna
de catalogação para o perfil Clássico.

### O artefato real

Capturado ao vivo do corpo de uma requisição real `POST /token` (perfil
Clássico): [`client_assertion_raw.txt`](client_assertion_raw.txt).

```
$ node verify_client_assertion.mjs classic client_assertion_raw.txt   # (dentro do container `auth`)

Header: {"alg":"PS256","kid":"c0d35890-1f2a-4ed5-bf9f-856d10ccd093","typ":"JWT"}
Payload (decoded, complete): {
  "sub": "client_one",
  "aud": "https://matls-auth.local/token",
  "iss": "client_one",
  "exp": 1789352024,
  "iat": 1789351964,
  "jti": "LduoZgIao5GTDrGr90owD6r1"
}
Signature length (bytes): 512
VERIFICATION RESULT: {"valid": true, "reason": "PS256 verified"}
```

Saída completa em
[`verify_client_assertion_output.txt`](verify_client_assertion_output.txt).
512 bytes de assinatura confirma a chave RSA-4096 do próprio `client_one`
(não uma RSA-2048 comum) — a mesma chave já usada para o certificado mTLS
(Seção 1) e o JWKS (Seção 3), reaproveitada aqui para assinatura de
artefatos que o cliente emite.

### A prova que realmente importa

Verificação PS256 real contra a chave pública publicada em
`client_one_pub.jwks` (o mesmo par de chaves do certificado da Seção 1) —
`valid: true`. Nada de exótico aqui: é o mecanismo `private_key_jwt` padrão
do OIDC/FAPI, sem nenhuma camada extra — o ponto deste artefato é
justamente contrastar com o Híbrido (Seção 6 daquele README), onde a mesma
posição estrutural carrega uma assinatura payload-extension real.

### Explicação do mecanismo

`opin_flow.py`'s `make_client_assertion()` monta os claims padrão de um
`private_key_jwt` (RFC 7523) e assina via `sign_jwt()`, que para `alg ==
"PS256"` delega diretamente a `pyjwt.encode()` — sem nenhuma lógica
adicional, o caminho mais simples dos três perfis.

### Referência ao código

- `thesis/scripts/opin_flow.py`, `make_client_assertion()` (linha 629) e
  `sign_jwt()` (linha 578), branch `alg == "PS256"` (linha 579-580).
- `mock-service-os/certs/client_one_pub.jwks` — chave pública usada na
  verificação.
- `thesis/scripts/verify_hybrid_jwt/verify_client_assertion.mjs` — a
  verificação rodada acima.
