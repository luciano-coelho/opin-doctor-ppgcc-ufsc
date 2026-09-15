# Artefatos reais — perfil PQC

Prova de implementação verificável para o perfil PQC, no mesmo padrão de
`artifacts/hybrid/` e `artifacts/classico/`: cada artefato vem com a captura
real, a explicação do mecanismo, e o ponto exato do código-fonte. Aqui a
afirmação a provar é dupla: (1) que o material pós-quântico (ML-DSA-65 no
certificado/JWT, MLKEM1024 no handshake) é genuíno e funcional, não apenas
um campo do tamanho certo; e (2) que, onde o desenho é deliberadamente misto
(o certificado, Etapa 3.1 — só a chave do titular migra para PQC, a CA
permanece RSA), essa mistura é exatamente o que foi decidido, não uma PQC
incompleta por acidente — e onde o desenho é puro para o tráfego externo
(o handshake TLS do cliente ao gateway), ele é realmente puro, sem nenhum
componente clássico (X25519 ou qualquer ECDHE) silenciosamente misturado
nesse tráfego especificamente (ver a ressalva sobre o tráfego interno
auth→RS na Seção 4).

Todo dado abaixo foi capturado ao vivo em `CRYPTO_PROFILE=pqc`, no mesmo
pipeline v7 (`tls_kem_proxy`, Decision 1) usado para o lote de tamanho e
latência.

---

## 1. Certificado do titular (`client_one_pqc.crt`) — chave ML-DSA-65, emissor RSA

### O artefato real

Arquivo bruto: [`client_one_pqc.crt`](client_one_pqc.crt). Decodificação
via `openssl x509 -text -noout`:
[`client_one_pqc.crt.txt`](client_one_pqc.crt.txt).

```
Signature Algorithm: sha256WithRSAEncryption
Issuer: CN=ca
Subject: CN=client_one_pqc, ...
Subject Public Key Info:
    Public Key Algorithm: 2.16.840.1.101.3.4.3.18
    Unable to load Public Key
50F50000:error:03000072:digital envelope routines:X509_PUBKEY_get0:decode error:...
...
Signature Algorithm: sha256WithRSAEncryption
```

Duas observações estruturais, ambas intencionais: **a assinatura do
certificado (issuer) é RSA clássica**, não ML-DSA-65 — o certificado é
emitido pela mesma CA `ca.crt`/`ca.key` que assina o certificado do
Clássico (`artifacts/classico/`); e **o OpenSSL reconhece o OID da chave do
titular (`2.16.840.1.101.3.4.3.18`, ML-DSA-65/FIPS 204) mas não consegue
decodificá-la** — exatamente a mesma situação (e o mesmo motivo) já
explicada em `artifacts/hybrid/README.md`, Seção 1: o OpenSSL 3.x deste
ambiente não tem um provider ML-DSA-65 carregado, então ele imprime o OID
corretamente (a estrutura ASN.1 é lida) mas para exatamente aí — não decodifica
o conteúdo da chave, e isso é esperado, não um sinal de que a chave é
inválida ou de tamanho errado.

### A prova que realmente importa: a chave ML-DSA-65 do titular é real e funcional, o issuer é classicamente verificável

Como no certificado híbrido, a limitação do OpenSSL não impede uma prova
criptográfica real — só exige uma ferramenta que entenda ML-DSA-65
nativamente (Go 1.27rc2, `crypto/mldsa`, FIPS 204). A prova aqui é a chave
mais direta possível: **assinar um desafio novo com a chave privada do
titular e verificar contra a chave pública que o próprio certificado
declara** — se isso funciona, a `SubjectPublicKeyInfo` é genuinamente o
outro lado do par de chaves em `client_one_pqc.key`, não um blob do
tamanho certo:

```
$ docker run --rm -v "<repo>/mock-service-os/certs:/certs" -w /certs golang:1.27-rc-alpine \
    sh -c "go build -o /tmp/certtool . && /tmp/certtool -verify-pqc-cert client_one_pqc"

Subject public key algorithm OID: 2.16.840.1.101.3.4.3.18 (ML-DSA-65, FIPS 204)
SubjectPublicKeyInfo: 1952 bytes, first 16 as hex: 07b8d33d7a261d017ef2f6b70ceac247...
Certificate signature algorithm (issuer signature): SHA256-RSA
Challenge signed with client_one_pqc.key, signature 3309 bytes, first 16 as hex: fc0ab8da913c1c66bc1d712ee3a1b113...
RESULT: verificado -- a assinatura ML-DSA-65 do desafio e valida contra a SubjectPublicKeyInfo de
/certs/client_one_pqc.crt -- o par de chaves ML-DSA-65 do certificado e real e funcional, nao apenas
um campo do tamanho certo. A propria assinatura do certificado (issuer) permanece classica (SHA256-RSA),
por design (Etapa 3.1): so a chave do titular migra para PQC, a CA nao.
```

Saída completa em
[`verify_pqc_cert_output.txt`](verify_pqc_cert_output.txt). 1.952 bytes é
exatamente o tamanho de uma chave pública ML-DSA-65 (FIPS 204, parameter
set 65); 3.309 bytes é exatamente o tamanho de uma assinatura ML-DSA-65 —
ambos batendo com os tamanhos já vistos no certificado híbrido e no JWT da
Seção 2 abaixo, o que por si só é uma checagem cruzada (o mesmo algoritmo
produzindo os mesmos tamanhos em três lugares independentes do sistema).

**A segunda metade da prova** — o issuer signature realmente verifica —
usa a ferramenta clássica de sempre, já que essa assinatura é RSA comum:

```
$ openssl verify -CAfile ca.crt client_one_pqc.crt
client_one_pqc.crt: OK
```

DER completo: **2.953 bytes** (contra 1.494 do Clássico) — a diferença de
1.459 bytes é essencialmente o custo de embutir uma SubjectPublicKeyInfo
ML-DSA-65 (1.952 bytes de chave, mais o `AlgorithmIdentifier`/overhead
ASN.1) no lugar de uma chave RSA-4096 comum, sem nenhuma extensão a mais —
confirma que este certificado não é um híbrido "disfarçado": não tem
`AltSignatureValue` nem `SubjectAltPublicKeyInfo`, só uma SPKI diferente.

### Explicação do mecanismo

Este é o desenho deliberado da Etapa 3.1 (mixing classical issuer +
post-quantum subject key é X.509 ordinário — os dois campos são
independentes): apenas a identidade do titular migra para PQC, a CA
permanece inalterada e classicamente verificável por qualquer software já
existente. Isso é diferente do certificado híbrido (`artifacts/hybrid/`),
que preserva a assinatura RSA original E adiciona uma segunda assinatura
ML-DSA-65 sobre o mesmo certificado — aqui não há segunda assinatura: a
chave do titular simplesmente É ML-DSA-65, ponto, e a CA nunca precisou
aprender a assinar com esse algoritmo para emitir este certificado.

### Referência ao código

`mock-service-os/certs/main.go`:
- `generateClientCertPQC()`, linhas 358–432 — gera a chave ML-DSA-65
  (`mldsa.GenerateKey(mldsa.MLDSA65())`, linha 371) e cria o certificado
  assinando com `caKey` **RSA** (`x509.CreateCertificate(..., key.Public(),
  caKey)`, linha 411–417) — o parâmetro de chave pública é a nova chave
  ML-DSA-65, o parâmetro de chave assinante continua sendo a CA RSA
  existente. O comentário da própria função (linhas 358–361) documenta essa
  escolha explicitamente.
- `verifyPQCCert()`, adicionada para este artefato (mesmo arquivo) — a
  verificação da Seção acima: assina um desafio com a chave privada do
  disco e verifica contra a `SubjectPublicKeyInfo` que `x509.ParseCertificate`
  já decodificou nativamente (o parser do Go 1.27rc2 reconhece o OID
  ML-DSA-65 e retorna `*mldsa.PublicKey` diretamente em `cert.PublicKey`).

---

## 2. JWT real, decodificado (resposta do RS, `GET .../premium`) — ML-DSA-65 puro

### O artefato real

Token completo: [`example_jwt_premium_compact.txt`](example_jwt_premium_compact.txt)
/ [`example_jwt_premium.txt`](example_jwt_premium.txt) (decodificado).

**Header:**
```json
{"alg": "ML-DSA-65", "kid": "5226750c-4adb-4d00-be74-c6a38845622d", "typ": "JWT"}
```

**Payload (chaves de topo):** `data`, `links`, `meta` — sem nenhum
componente RSA/clássico embutido (nem uma segunda assinatura, nem um claim
extra como o `pqc` do esquema híbrido). Total: 5.559 caracteres; segmento de
assinatura sozinho tem 4.412 caracteres (3.309 bytes decodificados) — o
grosso do tamanho do token é a assinatura ML-DSA-65 em si.

### A prova que realmente importa: a assinatura ML-DSA-65 verifica de verdade, sozinha

```
$ node verify_pqc_jwt.mjs pqc.json example_jwt_premium_compact.txt   # (dentro do container `auth`)

ML-DSA-65 public JWK, derivado de pqc.json via parsing do X.509 SPKI: {"kty":"AKP","alg":"ML-DSA-65",
  "use":"sig","kid":"5226750c-4adb-4d00-be74-c6a38845622d","pub":"nRsKrNTf1cz2CJiG7ZwUiUpu...(truncado)"}
Header: {"alg":"ML-DSA-65","kid":"5226750c-4adb-4d00-be74-c6a38845622d","typ":"JWT"}
Signing input length (bytes): 1146   Signature length (bytes): 3309

VERIFICATION RESULT: {
  "valid": true,
  "reason": "ML-DSA-65 verified",
  "hasClassicComponent": false,
  "payloadTopLevelKeys": ["data", "links", "meta"]
}
```

Saída completa em [`verify_jwt_output.txt`](verify_jwt_output.txt). O
script (`thesis/scripts/verify_hybrid_jwt/verify_pqc_jwt.mjs`, escrito para
este perfil) usa a API nativa `webcrypto.subtle.verify({name:'ML-DSA-65'})`
do Node 24 — a mesma primitiva que
`payloadExtensionVerification.js` usa para a metade PQC do esquema híbrido
(`artifacts/hybrid/README.md`, Seção 2) — sobre a entrada de assinatura
padrão de um JWS (`header_b64 + "." + payload_b64`, 1.146 bytes ASCII neste
token), verificando contra a chave pública derivada diretamente do arquivo
de material de chave do RS (`crypto-profiles/pqc.json`). Ao contrário do
Híbrido, não há aqui nenhum "AND gate" de duas assinaturas: uma única
assinatura ML-DSA-65 cobre o token inteiro, e é exatamente isso que a
verificação confirma (`hasClassicComponent: false`).

### Explicação do mecanismo

`ResponseSigningService.sign()` monta o JWS da forma mais comum possível —
header + payload + `signingInput = headerB64 + "." + payloadB64` — e assina
esse `signingInput` uma única vez com `loadMlDsa65Signer()`. Não há
`preparePayload()` sobrescrito com lógica especial (esse mecanismo existe
só no signer híbrido, para o claim `pqc`): o `default` da interface
devolve os claims inalterados, então este é estruturalmente o JWS mais
simples dos três perfis — só o algoritmo do header muda.

### Referência ao código

`insurance-server-lambdas/.../crypto/ResponseSigningService.java`:
- `sign()`, linhas 112–126 — monta `signingInput` e chama
  `signer.signToBase64Url(signingInput)`.
- `loadMlDsa65Signer()`, linhas 164–197 — carrega `pqc.json`, assina via
  `Signature.getInstance("ML-DSA", "BC")` (BouncyCastle).
- `thesis/scripts/verify_hybrid_jwt/verify_pqc_jwt.mjs` — a verificação
  rodada acima.

---

## 3. Entrada real no JWKS — duas identidades PQC distintas (AS e RS), a mesma que assinou

### O artefato real

**Do AS** — captura completa: [`jwks_auth.json`](jwks_auth.json), resposta
real de `GET https://auth.local/jwks` (perfil PQC, via `tls_kem_proxy`):
entrada `kty: "AKP"`/`alg: "ML-DSA-65"` de assinatura (`kid`
`QiYeUNBZXaKsrgR_...`), mais a entrada `kty: "RSA"`/`RSA-OAEP` de cifragem
(inalterada entre perfis, como já visto em Clássico/Híbrido). Este `kid` é
**diferente** do `kid` do JWT da Seção 2 — esperado: o AS e o RS são dois
serviços com material de chave PQC independente (o AS assina seus próprios
artefatos, como `id_token`; o RS assina as respostas de API que este
documento usa como exemplo). Publicar essa chave aqui não fecha o ciclo do
JWT da Seção 2 — só confirma que o AS também publica sua própria chave
ML-DSA-65 no formato JWKS (`kty: "AKP"`) que a IANA/JOSE registra para
ML-DSA.

**Do RS** — [`jwks_rs_derived.json`](jwks_rs_derived.json): a entrada que
`GET /jwks` do RS publicaria, derivada do MESMO arquivo de material de
chave (`pqc.json`) usado para verificar o JWT na Seção 2 (busca ao vivo bateu
em `401`, mesmo motivo não diagnosticado já registrado em
`artifacts/hybrid/README.md`, Seção 2):

```json
{"kty": "AKP", "alg": "ML-DSA-65", "use": "sig", "kid": "5226750c-4adb-4d00-be74-c6a38845622d", "pub": "nRsKrNTf1cz2CJiG7ZwUiUpu...(truncado)"}
```

### A prova que realmente importa: o kid e a chave batem exatamente com o que assinou

Duas checagens diretas, nenhuma delas por inspeção visual:

1. **`kid` idêntico**: `5226750c-4adb-4d00-be74-c6a38845622d` — o mesmo
   valor exato do header do JWT verificado na Seção 2, não uma coincidência
   de formato, um valor UUID literal batendo byte a byte.
2. **`pub` é a mesma chave que verificou**: `jwks_rs_derived.json` e
   `verify_pqc_jwt.mjs` (Seção 2) derivam o campo `pub` do mesmo arquivo
   (`pqc.json`), com o mesmo código de extração
   (`createPublicKey({key: spkiDer, format:'der', type:'spki'})`) — a
   verificação da Seção 2 já retornou `valid: true` usando exatamente esta
   chave; se a chave publicada aqui fosse diferente da que assinou, aquela
   verificação teria falhado, não passado.

Fechar o ciclo aqui é mais direto do que no Híbrido (Seção 3 de
`artifacts/hybrid/`): não há um hash composto (`SHA-256(classicPk‖pqcPk)`)
a recalcular — o `kid` é copiado verbatim de `pqc.json`, e é o mesmo em
ambos os lados (assinatura e publicação) por construção.

### Explicação do mecanismo

`loadMlDsa65Signer()` usa a MESMA variável `kid` (lida uma vez de
`pqc.json`) tanto para assinar (`kid()`, usado no header do JWT) quanto
para publicar (`publicJwk()`, usado no JWKS) — não há dois lugares
independentes que poderiam divergir; é literalmente a mesma referência de
string dentro do mesmo objeto `JwsSigner`.

### Referência ao código

`insurance-server-lambdas/.../crypto/ResponseSigningService.java`:
- Linha 166: `String kid = (String) json.get("kid")` — lido uma vez de
  `pqc.json`.
- Linha 180: `public String kid() { return kid; }` — usado no header do JWT
  (via `sign()`, linha 119).
- Linhas 189–196: `publicJwk()` — usa a MESMA variável `kid` (linha 193) ao
  montar a entrada JWKS.
- `thesis/scripts/verify_hybrid_jwt/derive_pqc_jwks.mjs` — deriva
  `jwks_rs_derived.json` acima.

---

## 4. Evidência do handshake TLS — MLKEM1024 puro no tráfego externo, com uma exceção interna deliberada e documentada

### O artefato real

Linha de log real do gateway, perfil PQC, via `tls_kem_proxy`:
[`handshake_log.json`](handshake_log.json).

```json
{
  "msg": "mTLS handshake complete",
  "tlsVersion": "TLS 1.3",
  "cipherSuite": "TLS_AES_128_GCM_SHA256",
  "curveID": "MLKEM1024",
  "clientCertBytes": 2953,
  "mtlsHandshakeBytes": 16669,
  "handshakeDurationMs": 56
}
```

`clientCertBytes: 2953` bate exatamente com o DER do certificado da Seção 1
(2.953 bytes) — confirma que esta linha de log corresponde à conexão real
que apresentou `client_one_pqc.crt`.

### A prova que realmente importa: confirmar que NENHUM componente clássico entrou no grupo negociado, e que a sessão é fresca

```
$ docker run --rm --network insurance-server-lambdas_default \
    -v thesis/scripts/verify_kem_export:/src -v mock-service-os/certs:/certs:ro -w /src \
    golang:1.27-rc-alpine go run . mlkem1024 /certs/client_one_pqc.crt /certs/client_one_pqc.key

connection 1: curveID=MLKEM1024 tlsVersion=TLS 1.3 exported(32B)=d2d7b3bd7714b426b128d2c0500ae2b1b965f4e3387dd84234cdf7228a6ed529
connection 2: curveID=MLKEM1024 tlsVersion=TLS 1.3 exported(32B)=a1101913ec7b0234d386503186a9bd68a73c612803ad236743cfdfc4e654dc16

RESULT: verificado -- ambas as conexoes negociaram MLKEM1024 (grupo=mlkem1024), e o material de chave
exportado (RFC 5705) e DIFERENTE entre as duas -- confirma que o segredo de sessao foi de fato derivado
de uma troca de chave nova a cada conexao, nao um valor fixo ou decorativo.
```

Saída completa em
[`verify_kem_export_output.txt`](verify_kem_export_output.txt). A mesma
ferramenta usada em Híbrido e Clássico roda aqui com o argumento
`mlkem1024`: ela exige que o `curveID` negociado seja EXATAMENTE
`"MLKEM1024"` nas duas conexões — se o handshake tivesse negociado
`X25519MLKEM768` (o grupo híbrido clássico+PQC do perfil Híbrido) ou
qualquer curva puramente clássica, o programa teria terminado em `RESULT:
FAIL`, não com sucesso. `MLKEM1024`, ao contrário de `X25519MLKEM768`, não
tem NENHUM componente ECDHE misturado no próprio nome do grupo (RFC 9880) —
não é um "híbrido com metade PQC", é o KEM puro. A exportação de material de
chave (RFC 5705) confirma adicionalmente que o segredo de sessão é
genuinamente novo a cada conexão, via KEM efêmero, não um valor fixo.

### Explicação do mecanismo

`CRYPTO_PROFILE=pqc` faz `mock_mtls`'s `init()` sobrescrever
`serverCurvePreferences` para conter apenas `tls.MLKEM1024` — nenhuma curva
clássica aparece na lista padrão de preferências do servidor. O
`tls_kem_proxy` (Decision 1 do v7) pede exatamente esse grupo do lado do
cliente via `-curve mlkem1024`, usando o suporte nativo do Go 1.27rc2 a
MLKEM1024 (que a stack TLS/OpenSSL do Python, usada pelo resto de
`opin_flow.py`, ainda não negocia — daí o proxy existir).

**Ressalva verificada, não uma suposição**: essa restrição não é absoluta
para 100% do tráfego que toca este gateway — existe uma exceção interna,
deliberada e pré-existente a este trabalho, para exatamente uma chamada:
`GetConfigForClient` (`mock_mtls/main.go`) intercepta o `ClientHelloInfo` de
toda conexão e, quando `hello.ServerName == "matls-api.local"`, devolve um
`tls.Config` separado com `CurvePreferences` fixado em curvas clássicas —
essa é a rota que `auth`'s `InsurerAdapter.getConsent()` usa para checar o
consentimento junto ao RS (Node não negocia MLKEM1024/X25519MLKEM768),
estendendo o mesmo carve-out de certificado clássico já registrado na
Decision 5 (`thesis/results/v5/size/DECISIONS.md`) para a dimensão de troca
de chave também. **Confirmado ao vivo**, não suposto: instrumentei
`GetConfigForClient` com um log (`slog.Info`, printando `hello.ServerName` +
`remoteAddr`) e cruzei, conexão por conexão, contra as linhas `"mTLS
handshake complete"` do mesmo período — **as 35 aplicações do carve-out e
os 35 handshakes `curveID=CurveP256` capturados coincidem 1:1, mesmo
`remoteAddr`, sem nenhum handshake clássico sobrando sem explicação**. Ou
seja: sob `CRYPTO_PROFILE=pqc`/`hybrid`, a ÚNICA fonte de troca de chave
clássica neste gateway é essa rota interna, especificamente amarrada a esse
SNI — não uma falha de aplicação da política, e não algo que afete o
tráfego cliente↔gateway que este artefato mede (SNI diferente,
`AUTH_CONNECT_HOST`/`API_CONNECT_HOST` via `tls_kem_proxy`, nunca
`matls-api.local` diretamente).

### Referência ao código

- `mock-service-os/mock_mtls/main.go`, linha ~114: `init()` sobrescrevendo
  `serverCurvePreferences` para `[]tls.CurveID{tls.MLKEM1024}` sob
  `CRYPTO_PROFILE=pqc`.
- `thesis/scripts/opin_flow.py`: `TLS_KEM_PROXY_CURVE_BY_PROFILE = {"pqc":
  "mlkem1024", ...}` — mapeia o perfil ao argumento `-curve` do proxy.
- `thesis/scripts/tls_kem_proxy/main.go`, caso `"mlkem1024"` do `switch` de
  curvas.
- `thesis/scripts/verify_kem_export/main.go` — a ferramenta usada acima,
  aqui invocada com `mlkem1024`.
- `mock-service-os/mock_mtls/main.go`, `GetConfigForClient` — a exceção
  interna por SNI documentada na ressalva acima, com o comentário do código
  atualizado para deixá-la explícita ao lado da política "no silent
  fallback" que ela recorta.

---

## 5. `id_token` real, decodificado — assinatura ML-DSA-65 pura, criptografia da mensagem ainda clássica, confirmado impossível de migrar hoje

### O artefato real

Capturado ao vivo do campo `id_token` de uma resposta real `POST /token`
(fluxo completo, perfil PQC): [`id_token_raw.txt`](id_token_raw.txt) — um
JWE de 5 segmentos, não um JWS de 3 (diferente dos artefatos das Seções
1–4):

```
$ node decrypt_and_verify_id_token.mjs pqc id_token_raw.txt   # (dentro do container `auth`)

id_token: 7246 chars, 5 segments (JWE compact serialization)
JWE protected header: {"alg":"RSA-OAEP","enc":"A256GCM","cty":"JWT","kid":"83e830ad-...","iss":"https://auth.local","aud":"client_one"}
Decrypted inner JWS: 4753 chars, 3 segments
Inner JWS header: {"alg":"ML-DSA-65","kid":"QiYeUNBZXaKsrgR_BfvZfQJHxyPo9mez54AgoBeB9VU"}
Inner JWS payload (decoded, complete): {
  "sub": "usuario1@seguradoramodelo.com.br",
  "acr": "urn:brasil:openinsurance:loa3",
  "nonce": "Vq3qV-2HxtFs",
  "aud": "client_one",
  "exp": 1789354547,
  "iat": 1789350947,
  "iss": "https://auth.local"
}
Inner JWS signature length (bytes): 3309
VERIFICATION RESULT: {"valid": true, "reason": "ML-DSA-65 verified"}
```

Saída completa em
[`verify_id_token_output.txt`](verify_id_token_output.txt).

### A prova que realmente importa: a assinatura interna é genuinamente ML-DSA-65 pura; a cifra externa continua RSA-OAEP, e nenhum dos dois fatos deve ser suavizado

**A parte que migrou, migrou de verdade**: a assinatura interna do
`id_token`, uma vez decifrado o JWE, é ML-DSA-65 puro (3.309 bytes,
verificado por `webcrypto.subtle.verify`) — sem nenhum componente RSA
misturado, exatamente como o JWT da Seção 2 e o certificado da Seção 1
deste mesmo perfil.

**A parte que não migrou, e não pode migrar hoje, é a cifragem do JWE**:
`alg: "RSA-OAEP"` — a mesma que aparece em Clássico e Híbrido, sem exceção.
Isso não é uma lacuna deste protótipo especificamente sob PQC — é um
limite real do estado da arte: não existe hoje nenhum padrão JOSE/COSE para
cifragem pós-quântica (ML-KEM) de tokens; o rascunho que existia foi
retirado do grupo de trabalho do IETF, e bibliotecas como `jose` não têm
suporte algum a isso. **Esta é a evidência mais direta e concreta desse
achado em toda a pasta `artifacts/`**: um `id_token` genuinamente PQC do
pescoço para baixo (assinatura), ainda inteiramente clássico na camada que
o envolve (cifragem) — não por escolha de design deste projeto, mas porque
não há alternativa disponível para escolher. Ver
`thesis/docs/Cruzamento_SAD_vs_Experimentos.md` para o levantamento
completo desse ponto contra o SAD.

### Explicação do mecanismo

Assim como no Clássico, o `oidc-provider` monta e assina o `id_token`
internamente e o cifra (RSA-OAEP + AES-256-GCM) antes de a resposta sair do
processo. Sob `CRYPTO_PROFILE=pqc`, `internalSigningAlgs`/
`internalSigningKey` apontam para a chave ML-DSA-65 do perfil
(`pqc.json`'s `signingKey`, `kty: "AKP"`) — e, diferente do Híbrido (Seção
5 do README daquele perfil), **não precisa de nenhum mecanismo de
`ExternalSigningKey`**: o `jose`/`oidc-provider` deste ambiente já
reconhece `"ML-DSA-65"` como um algoritmo de assinatura válido nativamente
(o mesmo suporte nativo do Node 24 já usado nas Seções 2 desta pasta e da
pasta `hybrid/`) — só a combinação de DOIS algoritmos num único `alg`
string (o caso do Híbrido) exige o desvio.

A chave pública de cifragem usada aqui é a que `client_one_pqc.jwks`
registra (`kid` diferente do Clássico/Híbrido — cada perfil tem sua própria
chave de cifragem registrada para o cliente, confirmado comparando os
`kid`s dos três `id_token`s capturados nesta pasta).

### Referência ao código

- `mock-service-os/mock_as/utils/opin/configuration.js`, linha 43:
  `internalSigningAlgs = isHybrid ? ['PS256'] : cryptoProfile.signingAlgs`
  — para `pqc`, resolve para `['ML-DSA-65']`, lido de `pqc.json`.
- `mock-service-os/mock_as/utils/opin/configuration.js`, linha 330:
  `idTokenEncryptionAlgValues: ['RSA-OAEP']` — mesma cifragem clássica,
  qualquer perfil.
- `mock-service-os/certs/client_one_pqc.jwks`: par de chaves RSA-OAEP do
  cliente para este perfil (`use: "enc"`).
- `thesis/scripts/verify_hybrid_jwt/decrypt_and_verify_id_token.mjs` — a
  verificação rodada acima.

---

## 6. `client_assertion` real — ML-DSA-65 puro autenticando o cliente

### Por que este artefato existe

O passo 8 do SAD ("Token de acesso") não é assinado — o `access_token`
capturado ao vivo é uma string opaca, sem estrutura JWT
(`certificateBoundAccessTokens: true`, sem `formats.AccessToken`
configurado). A assinatura ML-DSA-65 real que autentica o cliente PQC ao
pedir um token vive no `client_assertion`, não no `access_token` em si —
ver `thesis/docs/Cruzamento_SAD_vs_Experimentos.md` para a correção
completa dessa classificação.

### O artefato real

Capturado ao vivo do corpo de uma requisição real `POST /token` (perfil
PQC): [`client_assertion_raw.txt`](client_assertion_raw.txt).

```
$ node verify_client_assertion.mjs pqc client_assertion_raw.txt   # (dentro do container `auth`)

Header: {"kid":"fbHr8nZT_Z048MGn6p25MDa8YVLmp-teybDNaQK-ADI","alg":"ML-DSA-65"}
Payload (decoded, complete): {
  "sub": "client_one",
  "aud": "https://matls-auth.local/token",
  "iss": "client_one",
  "exp": 1789351810,
  "iat": 1789351750,
  "jti": "Sf-H8rQ8kWgZ973VkKZuIUq9"
}
Signature length (bytes): 3309
VERIFICATION RESULT: {"valid": true, "reason": "ML-DSA-65 verified"}
```

Saída completa em
[`verify_client_assertion_output.txt`](verify_client_assertion_output.txt).
Assinatura ML-DSA-65 pura (3.309 bytes, mesmo tamanho já visto nas Seções 2
e 5 deste perfil), sem componente RSA — o cliente PQC autentica com o
mesmo algoritmo que assina tudo o mais nesse perfil.

### A prova que realmente importa

Verificação ML-DSA-65 real (`webcrypto.subtle.verify`) contra a chave
pública publicada em `client_one_pqc_pub.jwks` — `valid: true`. Mesma
estrutura do `client_assertion` do Clássico (Seção 6 daquele README), só o
algoritmo muda — o `_run_pqc_signer()` docker helper assina exatamente como
assina qualquer outro payload PQC neste projeto (Seção 2).

### Explicação do mecanismo

`sign_jwt()`'s branch `alg == "ML-DSA-65"` (`thesis/scripts/opin_flow.py`)
serializa a chave privada + header + claims e invoca `_run_pqc_signer()` —
o mesmo container Docker efêmero usado para qualquer assinatura ML-DSA-65
do lado do cliente neste projeto.

### Referência ao código

- `thesis/scripts/opin_flow.py`, `sign_jwt()`, branch `alg == "ML-DSA-65"`
  (linhas 581–584); `_run_pqc_signer()` (linha 386).
- `mock-service-os/certs/client_one_pqc_pub.jwks` — chave pública usada na
  verificação.
- `thesis/scripts/verify_hybrid_jwt/verify_client_assertion.mjs` — a
  verificação rodada acima.

---

## Nota metodológica: como este lote foi coletado, e uma ameaça de reprodutibilidade real que isso revelou

Capturar um fluxo PQC real ao vivo expôs um problema que inicialmente
pareceu específico deste script de captura, mas **não era**: a stack TLS do
Python (`opin_flow.py`) tenta carregar localmente o par de chaves de
`client_one_pqc.crt/.key` mesmo na perna Python→`tls_kem_proxy` (que nunca
exige certificado de cliente — ver `tls_kem_proxy/main.go`, o listener
local não define `ClientAuth`), e o OpenSSL 3.0 padrão deste host não
consegue analisar uma chave ML-DSA-65 nativa (`EE_KEY_TOO_SMALL`/
`X509_LIB`, confirmado isoladamente, sem qualquer atividade de rede
envolvida). A perna real que autentica com o gateway (Go→gateway, dentro do
`tls_kem_proxy`) usa o Go 1.27rc2 nativo e funciona sem problema — é só a
perna local, cosmética, que não consegue carregar o arquivo.

**Teste direto confirmou que isso não é uma particularidade do script de
captura**: rodar `median_automation.run_once("pqc", 0)` chamando
`opin_flow.run_insurance_flow()`/`run_person_flow()` **sem nenhuma
modificação** — o mesmo caminho de código exato que gerou os dados PQC já
commitados desta v7 (2026-09-12) — falhou nesta máquina, agora, com o
mesmo `EE_KEY_TOO_SMALL`, na mesma chamada (`do_call()` →
`session.request(cert=cert, ...)`). Ou seja: **o pipeline oficial de
medição também está quebrado nesta máquina no momento em que este artefato
foi escrito**, não só a ferramenta de captura auxiliar. A causa é uma
mudança de ambiente externa (OpenSSL/Windows, não determinada com
precisão) entre 2026-09-12 e 2026-09-13 — os arquivos de certificado/chave
no repositório não mudaram (confirmado via `git status`/timestamps).

Essa falha foi corrigida em `opin_flow.py` (ver Decision 5,
`thesis/results/v7/DECISIONS.md`): a perna local Python→`tls_kem_proxy`
para de apresentar qualquer certificado de cliente sob os perfis `pqc`/
`hybrid`, já que essa apresentação nunca teve efeito real (o listener local
nunca a exige) — é puramente cosmética, e removê-la restaura a
reprodutibilidade sem alterar nenhum dado já medido. Após a correção, o
mesmo teste (`median_automation.run_once("pqc", 0)`, pipeline oficial
inalterado fora dessa remoção) foi re-executado com sucesso.

O script de captura usado para gerar os exemplos deste README
(`thesis/scripts/_capture_pqc_artifacts.py`, descartável) usou, antes da
correção acima existir, um contorno equivalente só para essa mesma perna
cosmética — substituindo o certificado local por `client_one.crt` (RSA,
carregável) depois de o `tls_kem_proxy` já ter sido iniciado com o
certificado PQC real, então a autenticação real contra o gateway usou
`client_one_pqc.crt/.key` sem alteração nenhuma. Com a correção do
`opin_flow.py` já aplicada, esse contorno do script de captura tornou-se
redundante (o próprio `opin_flow.py` já não apresenta certificado ali), mas
foi mantido no arquivo por não ser necessário removê-lo.

O dado já commitado do lote de tamanho/latência (2026-09-12) continua
válido e não foi re-coletado — a correção documentada aqui existe apenas
para garantir que uma nova coleta PQC nesta máquina, no futuro, volte a
funcionar.
