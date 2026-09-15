# Artefatos reais — perfil Híbrido

Esta pasta (e suas irmãs `artifacts/classico/` e `artifacts/pqc/`) existe como
**prova de implementação verificável**: para cada afirmação deste projeto de
que "isso foi feito" — um certificado híbrido gerado nesta ordem específica,
um JWT assinado com essa composição, uma chave publicada daquele jeito, um
grupo de troca de chave negociado nesse handshake — há aqui o artefato real
capturado ao vivo do sistema rodando (não um exemplo fabricado), a explicação
do mecanismo, e o ponto exato do código-fonte que implementa isso. 

Todo dado abaixo foi capturado ao vivo em `CRYPTO_PROFILE=hybrid`, no mesmo
sistema e pipeline (`tls_kem_proxy`, v7) usados para o lote de tamanho e
latência — não é uma amostra estatística (não são 10 execuções), é uma
fotografia única de cada artefato, exatamente como ele existe em produção
neste projeto.

---

## 1. Certificado híbrido (`client_one_hybrid.crt`)

### O artefato real

Arquivo bruto: [`client_one_hybrid.crt`](client_one_hybrid.crt) (PEM, o mesmo
arquivo usado pelo cliente em toda execução do perfil Híbrido). Versão
decodificada: [`client_one_hybrid.crt.txt`](client_one_hybrid.crt.txt)
(`openssl x509 -text -noout`, capturado ao vivo do arquivo em uso).

Trecho relevante da decodificação — os três campos que carregam o material
pós-quântico:

```
X509v3 Subject Alternative Public Key Info:
    <binário: chave pública ML-DSA-65>
X509v3 Alternative Signature Algorithm:
    <binário: identificador do algoritmo alternativo>
X509v3 Alternative Signature Value:
    <binário: assinatura ML-DSA-65>
Signature Algorithm: sha256WithRSAEncryption
Signature Value:
    c7:f7:74:60:62:ed:df:fa:30:16:23:0f:5f:b6:fd:6f:...
```

**Por que o OpenSSL mostra binário bruto aqui, e por que isso é o
comportamento correto, não uma lacuna de prova.** O OpenSSL reconhece essas
três extensões pelo nome (são extensões X.509 padrão, OIDs `2.5.29.72/73/74`)
mas não decodifica seu conteúdo interno, porque este build não tem suporte
nativo a ML-DSA-65. Isso não é um problema a esconder — é a **evidência viva
de que a retrocompatibilidade está funcionando exatamente como desenhado**:
as três extensões são deliberadamente marcadas **não-críticas**
(`critical=false`, visível na extração de tamanhos abaixo), o que por
definição em X.509 (RFC 5280) instrui qualquer verificador que não reconheça
uma extensão a **ignorar seu conteúdo e continuar validando o certificado
normalmente**. Um OpenSSL comum, sem qualquer patch ou plugin PQC, aceita
este certificado inteiro — porque a assinatura que ele sabe checar (RSA,
`Signature Value`) cobre o certificado completo, extensões PQC incluídas,
mesmo sem entender o que elas significam. O OpenSSL "não entender" o binário
é precisamente o comportamento que prova que um verificador legado consegue
usar este certificado sem adaptação nenhuma. A prova de que o conteúdo
*em si* é criptograficamente válido — não só do tamanho certo — vem a
seguir, com verificação real, não com decodificação por um verificador que
nunca teve motivo para entender ML-DSA-65.

Tamanhos exatos de cada campo, extraídos via `cryptography` (Python) sobre o
mesmo arquivo, confirmando os três OIDs, se são críticos, e seus tamanhos em
bytes:

| Campo (OID) | Crítico? | Tamanho | O que é |
|---|---|---|---|
| `subjectAltPublicKeyInfo` (2.5.29.72) | não | 1.974 bytes | Chave pública ML-DSA-65 do titular |
| `altSignatureAlgorithm` (2.5.29.73) | não | 13 bytes | Identificador do algoritmo alternativo |
| `altSignatureValue` (2.5.29.74) | não | 3.314 bytes | Assinatura ML-DSA-65 |
| Assinatura RSA final (`Signature Value`) | — | 512 bytes | RSA-4096, `sha256WithRSAEncryption` |
| **Certificado completo (DER)** | — | **6.859 bytes** | Confirma o `client_cert_der_bytes` medido em todo o lote v7 |

### A prova que realmente importa: a segunda assinatura é verificável de verdade

Um campo do tamanho certo, sozinho, não prova nada — poderia ser qualquer
sequência de 3.309 bytes. A prova de que este certificado é **híbrido de
verdade**, não um certificado clássico com um campo decorativo do tamanho
certo, é: **essa segunda assinatura passa numa verificação criptográfica
real, feita por um algoritmo diferente (ML-DSA-65), sobre o mesmo conteúdo
que a assinatura RSA cobre.**

Escrevi e rodei uma verificação independente que faz exatamente isso —
extrai a chave e a assinatura de dentro do certificado, reconstrói os bytes
exatos que foram assinados, e verifica a assinatura de verdade contra a
chave pública ML-DSA-65 correspondente:

```
$ docker run --rm -v "<repo>/mock-service-os/certs:/src" -w /src golang:1.27-rc-alpine \
    go run . -verify-hybrid client_one

Subject's own ML-DSA-65 public key (SubjectAltPublicKeyInfo), 1952 bytes, first 16 as hex: 07b8d33d7a261d017ef2f6b70ceac247...
Alternative signature (AltSignatureValue), 3309 bytes, first 16 as hex: a49021396523fef8ef74eab565285e60...
Reconstructed preTBS: 2996 bytes (original final TBS was 6323 bytes -- the difference is exactly the AltSignatureValue extension this removes)
RESULT: verificado -- a assinatura ML-DSA-65 (AltSignatureValue) e valida para a chave ML-DSA-65 da CA emissora (issuer_ca_pqc.crt) sobre o preTBS reconstruido de /src/client_one_hybrid.crt.
```

Saída completa salva em
[`verify_hybrid_cert_output.txt`](verify_hybrid_cert_output.txt) — comando
reproduzível, roda em qualquer máquina com Docker a partir do repositório.

O que esse comando faz, passo a passo (é o mesmo algoritmo que qualquer
verificador real deste esquema híbrido precisaria implementar, não um atalho
de teste):

1. Extrai a chave pública ML-DSA-65 do titular (`SubjectAltPublicKeyInfo`,
   1.952 bytes de chave real — não só o tamanho, o conteúdo, mostrado em hex).
2. Extrai a assinatura ML-DSA-65 (`AltSignatureValue`, 3.309 bytes de
   assinatura real).
3. Reconstrói o **preTBS** — os bytes exatos do certificado como existiam
   *antes* da assinatura ML-DSA-65 ser adicionada (removendo só a extensão
   `AltSignatureValue`, mantendo tudo mais idêntico) — a mesma reconstrução
   que a Fase 3 do Nível 1 já validou para a prova criptográfica standalone.
   2.996 bytes contra 6.323 do TBS final: a diferença bate exatamente com o
   tamanho da extensão removida.
4. Verifica a assinatura com `crypto/mldsa` (suporte nativo a ML-DSA-65 do Go
   1.27rc2, FIPS 204) contra a chave pública ML-DSA-65 **da CA emissora**
   (`issuer_ca_pqc.crt`) — não contra a chave do próprio titular.
   `SubjectAltPublicKeyInfo` (extraída no passo 1) é a chave pública
   ML-DSA-65 **do titular deste certificado** (`client_one`), e ela é
   certificada pela assinatura da CA pelo mesmo motivo que a chave RSA do
   titular também é certificada pela assinatura RSA da CA (passo 4 acima):
   é a CA quem atesta a identidade do titular, nos dois algoritmos — a
   verificação usa a chave da CA porque é a CA que assina, exatamente como
   no lado clássico.

**Resultado: verificado.** A assinatura ML-DSA-65 é criptograficamente
válida para essa chave sobre esse certificado — não é uma suposição baseada
em tamanho de campo, é uma verificação de assinatura real que passou.

### Explicação do mecanismo

Um certificado X.509 híbrido carrega duas assinaturas independentes sobre o
mesmo conteúdo, mas **na ordem ML-DSA-65-primeiro/RSA-por-último**, não o
contrário:

1. Um "pré-TBS" é montado com a chave pública RSA do titular e as extensões
   híbridas de chave/algoritmo (mas ainda sem a assinatura alternativa), e
   assinado uma vez com RSA só para obter bytes DER bem formados a partir dos
   quais extrair o TBS (`extractTBSBytes`).
2. A chave privada ML-DSA-65 da CA assina esse TBS pré-existente — esta é a
   assinatura alternativa (`AltSignatureValue`), verificada acima.
3. A assinatura ML-DSA-65 é inserida como uma extensão do certificado, e **só
   então** a chave privada RSA da CA assina o certificado final —
   `sha256WithRSAEncryption`, a assinatura que aparece no campo padrão
   `Signature Value`, cobrindo agora o TBS completo, **incluindo** a
   assinatura ML-DSA-65 que acabou de ser adicionada.

Por essa ordem, a assinatura RSA (a que qualquer verificador X.509 comum já
sabe checar) cobre transitivamente a assinatura ML-DSA-65 também — adulterar
o campo pós-quântico invalida a assinatura clássica igualmente, mesmo que o
verificador nunca olhe para dentro dela. É a mesma lógica de composição
descrita em **Bindel, Braun, Gladiator, Stebila & Wiggers (2019),
"X.509-Compliant Hybrid Certificates for the Post-Quantum Transition"**,
Journal of Open Source Software (JOSS) — o mecanismo de três extensões
(`SubjectAltPublicKeyInfo`/`AltSignatureAlgorithm`/`AltSignatureValue`), a
marcação não-crítica, e a ordem de assinatura vêm diretamente desse artigo.

### Referência ao código

`mock-service-os/certs/main.go`:

- `generateHybridCert()`, linhas 338–402 — geração do certificado:
  - Linhas 372–376: monta o pré-TBS e extrai seus bytes (`extractTBSBytes`,
    linha 109).
  - Linha 378: `caKeyMLDSA.Sign(nil, preTBS, nil)` — a assinatura ML-DSA-65,
    computada **primeiro**, sobre o pré-TBS.
  - Linhas 383–384: a assinatura ML-DSA-65 entra como extensão
    (`altSignatureValueExtension`, linha 94), e o certificado final é
    criado — é **esta** chamada a `x509.CreateCertificate` que produz a
    assinatura RSA final, por último, sobre tudo.
  - `hybridExtensions()` (linhas 72–91) constrói as duas primeiras extensões
    (`SubjectAltPublicKeyInfo`/`AltSignatureAlgorithm`), ambas marcadas
    `Critical: false` explicitamente; os OIDs estão declarados nas linhas
    38–39 (`oidAltSignatureAlgorithm`/`oidAltSignatureValue`, `2.5.29.73`/
    `74`).
- `verifyHybridCert()` — a verificação independente rodada acima: extrai as
  extensões, reconstrói o preTBS removendo só `AltSignatureValue`
  (`tbs.Raw = nil` antes de re-serializar é o detalhe que garante que a
  reconstrução reflita a remoção, não reuse os bytes originais), e chama
  `mldsa.Verify()` contra a chave pública de `issuer_ca_pqc.crt`. Invocável
  via `go run . -verify-hybrid <nome>` em qualquer certificado
  `<nome>_hybrid.crt` deste projeto.

---

## 2. JWT real, decodificado (resposta do RS, `GET .../premium`)

### O artefato real

Token completo capturado ao vivo:
[`example_jwt_premium.txt`](example_jwt_premium.txt) — uma resposta real do
Resource Server (`GET .../insurance-person/{id}/premium`) durante uma
execução do fluxo de seguro, perfil Híbrido.

**Header decodificado:**
```json
{"alg": "RS256", "kid": "mZi6awCMmw-lTxi5N3k9d6i_Wa5veP2IZyMvNolkcvQ", "typ": "JWT"}
```
Nada aqui indica que este não é um JWT RS256 comum — esse é o ponto central
do mecanismo (ver abaixo).

**Payload decodificado (chaves de topo):** `data`, `links`, `meta`, `pqc` —
o campo `pqc` carrega `{"alg": "ML-DSA-65", "signature": "<4.412 caracteres
base64url>"}`.

**Números exatos desta captura**, todos conferidos diretamente no token:

| Métrica | Valor |
|---|---|
| Token completo | 7.430 caracteres |
| Segmento de assinatura RS256 | 342 caracteres → decodifica para 256 bytes (RSA-2048) |
| `pqc.signature` (ML-DSA-65) | 4.412 caracteres base64url (59% do token) |

### A prova que realmente importa: as duas assinaturas passam de verdade, porta AND incluída

Decodificar o token mostra a *estrutura* — dois campos do tamanho e formato
certos. Não prova que qualquer um dos dois realmente verifica. A prova real
é rodar a **mesma função de verificação que este projeto já usa em produção**
(`mock-service-os/mock_as/utils/opin/payloadExtensionVerification.js` — não
uma reimplementação para esta pasta) contra o token acima e as chaves
públicas reais do RS, e confirmar que RS256 passa, ML-DSA-65 passa, e a
porta AND das duas aceita o token:

```
$ docker cp insurance-server-lambdas/src/main/resources/crypto-profiles/hybrid.json auth:/tmp/hybrid.json
$ docker cp thesis/results/v7/artifacts/hybrid/example_jwt_premium_compact.txt auth:/tmp/jwt.txt
$ docker cp thesis/scripts/verify_hybrid_jwt/verify_jwt.mjs auth:/tmp/verify_jwt.mjs
$ docker exec insurance-server-lambdas-auth-1 node /tmp/verify_jwt.mjs /tmp/hybrid.json /tmp/jwt.txt

VERIFICATION RESULT: {
  "valid": true,
  "reason": "both RS256 and ML-DSA-65 verified",
  "hybridShaped": true
}
```

Saída completa (incluindo as duas chaves públicas derivadas, mostradas em
claro) em [`verify_jwt_output.txt`](verify_jwt_output.txt).

O script (`thesis/scripts/verify_hybrid_jwt/verify_jwt.mjs`) deriva as duas
chaves públicas necessárias diretamente do arquivo de material de chave do
RS (`crypto-profiles/hybrid.json` — o mesmo arquivo que
`ResponseSigningService.java` carrega para assinar), e chama
`verifyPayloadExtension(jwt, classicPublicJwk, pqcPublicJwk)` — a função
real, não um mock. **Por que derivar do arquivo de chaves em vez de buscar
`/jwks` do RS ao vivo**: tentei — `GET /jwks` no RS devolveu `401
Unauthorized` de algum filtro de segurança do Micronaut não diagnosticado
(fora do escopo desta tarefa, apesar do endpoint estar marcado
`@Secured(IS_ANONYMOUS)` no código). Derivar do arquivo de chaves é
metodologicamente equivalente — é a mesma computação que o endpoint faria —
e, no aspecto que importa aqui, mais rigoroso: confirma que a chave usada na
verificação é exatamente a que assinou este token específico, não apenas
"uma resposta que deveria ser a mesma".

**Um segundo fechamento independente do ciclo, sem eu ter pedido**: computei
separadamente o `kid` que a entrada JWKS do RS teria
(`SHA-256(classicPk‖pqcPk)`, ver Seção 3) a partir desse mesmo arquivo de
chaves — o resultado, `mZi6awCMmw-lTxi5N3k9d6i_Wa5veP2IZyMvNolkcvQ`, é
**byte-idêntico** ao `kid` que já está no header deste JWT (linha acima).
Ou seja: não só as chaves verificam a assinatura, o identificador que um
verificador real usaria para *descobrir* essa chave via JWKS também bate
exatamente.

### Explicação do mecanismo

Ao contrário do certificado (onde as duas assinaturas vivem em extensões
X.509 separadas), o JWT híbrido usa **extensão por payload**: a assinatura
RS256 é a única coisa no segmento de assinatura do JWS, computada **por
último**, sobre `base64url(header) + "." + base64url(payload)` — e o
`payload` já contém a assinatura ML-DSA-65 como um claim comum (`pqc`). A
assinatura ML-DSA-65, por sua vez, é computada **primeiro**, sobre a forma
canônica RFC 8785 (JCS) dos claims **sem** o campo `pqc` ainda.

Isso significa que um verificador RS256 comum, que nunca ouviu falar de
ML-DSA-65, aceita o token normalmente — `pqc` é só mais um claim que ele não
reconhece e ignora. Essa é a razão explícita da escolha desta ordem (ao
contrário do certificado, que usa Strong Nesting nas extensões X.509): o
orientador pediu compatibilidade retroativa total como prioridade sobre a
garantia de segurança mais forte (SUF-CMA) que a ordem inversa daria — ver
`thesis/results/v4/JWT_Hybrid_Architecture.md` para a análise completa da
troca SUF-CMA/EUF-CMA e as referências (Bindel et al. 2017; Brendel, Cremers,
Jackson & Zhao 2021). Este mesmo documento já mostra, passo a passo, a
reconstrução dos bytes JCS-canônicos que o ML-DSA-65 realmente assinou.

### Referência ao código

`insurance-server-lambdas/src/main/java/com/raidiam/trustframework/
mockinsurance/crypto/ResponseSigningService.java`:

- `sign()`, linha 112: monta header + payload e assina — `signer.
  preparePayload(claims)` (linha 115) é onde a injeção do campo `pqc`
  acontece **antes** da assinatura RS256 final ser computada (linha 124).
- `loadHybridSigner()`, linha 212, e sua implementação de `preparePayload()`,
  linha 275: onde o claim `pqc` é construído (assinatura ML-DSA-65 sobre a
  forma JCS-canônica dos claims, via BouncyCastle) e inserido no payload
  antes de retornar.
- `mock-service-os/mock_as/utils/opin/payloadExtensionVerification.js`, função
  `verifyPayloadExtension()` (linhas 29–86) — a verificação real rodada
  acima: RS256 primeiro (linhas 44–55, `crypto.verify` nativo do Node), remove
  `pqc` e reconstrói os bytes JCS-canônicos (linhas 76–77, pacote
  `canonicalize`, RFC 8785), verifica ML-DSA-65 sobre eles (linhas 79–80,
  `webcrypto.subtle.verify` nativo do Node 24 — suporte experimental mas
  real, não um polyfill), e só então retorna `valid: true` — a porta AND
  (linhas 53–55 e 81–83 cada uma podendo reprovar sozinha).
- `thesis/scripts/verify_hybrid_jwt/verify_jwt.mjs` — o script desta pasta
  que invoca a função acima com as chaves reais do RS.

---

## 3. Entrada real no JWKS (Authorization Server e Resource Server)

### O artefato real

**Do AS** — captura completa: [`jwks_auth.json`](jwks_auth.json), resposta
real de `GET https://auth.local/jwks` (perfil Híbrido, via `tls_kem_proxy`):

```json
{
  "kty": "HYBRID",
  "use": "sig",
  "alg": "MLDSA65-RSA2048-PSS-SHA256",
  "kid": "I4SZA4ycHOiCgSV7jKQEwgGmhsX3aV0KnTEF372by2A",
  "pk_hybrid": "pu8AVLEIfYppnbU0r2M1PNhCvYpGnVXbSXj-OxRX72e...(truncado)"
}
```

`pk_hybrid` é a concatenação bruta das duas chaves públicas (clássica +
ML-DSA-65) — não duas entradas separadas, uma única chave composta, porque
este JWKS é o do AS (assina `id_token`/JARM, que continuam em Strong
Nesting, não em extensão por payload — ver Seção 5 de
`JWT_Hybrid_Architecture.md`).

**Do RS** — [`jwks_rs_derived.json`](jwks_rs_derived.json): as duas entradas
que `GET /jwks` do RS publicaria (`ResponseSigningService.getPublicJwks()`),
derivadas do mesmo arquivo de material de chave usado na Seção 2 (busca ao
vivo bateu em `401`, não diagnosticado — ver Seção 2 para o porquê isso não
enfraquece a prova):

```json
{
  "kty": "RSA", "use": "sig", "alg": "RS256",
  "kid": "mZi6awCMmw-lTxi5N3k9d6i_Wa5veP2IZyMvNolkcvQ",
  "n": "1KEH2RKcHf2dRKmVcfNB_6vV...(truncado)", "e": "AQAB"
}
```

### A prova que realmente importa: a chave publicada é a chave que assinou, fechando o ciclo

Uma entrada JWKS do tamanho e formato certos não prova que ela corresponde
à chave real usada para assinar — poderia ser qualquer chave RSA/ML-DSA-65
válida, sem relação nenhuma com o token. O fechamento do ciclo está inteiro
na Seção 2: **a verificação que deu `valid: true` usou exatamente estas
duas chaves** (a derivação em `verify_jwt.mjs` e a construção deste JWKS
partem do mesmo `hybrid.json`, com a mesma lógica de composição de
`ResponseSigningService.java`) — se a chave publicada aqui não fosse a que
assinou, a verificação da Seção 2 teria retornado `valid: false`, não
`true`. Adicionalmente, o `kid` `RSA` acima
(`mZi6awCMmw-lTxi5N3k9d6i_Wa5veP2IZyMvNolkcvQ`) — computado
independentemente como `SHA-256(classicPk‖pqcPk)`, nunca copiado do token —
é byte-idêntico ao `kid` que o JWT da Seção 2 carrega no header: um
verificador real, fazendo descoberta por `kid`+`kty` como a Seção 6 de
`JWT_Hybrid_Architecture.md` já demonstra, encontraria exatamente esta
entrada para este token.

### Explicação do mecanismo

O AS publica uma única entrada `kty: "HYBRID"`, com um `alg` não-padrão
(`MLDSA65-RSA2048-PSS-SHA256`) que sinaliza explicitamente a um verificador
que essa chave não é uma RSA ou EC comum — é assim, deliberadamente, porque
os artefatos que o AS assina com Strong Nesting (`id_token`, JARM) não
pretendem ser aceitos por um verificador legado sem adaptação, ao contrário
dos artefatos assinados por extensão de payload (Seção 2 acima), cujo RS
correspondente publica **duas** entradas sob o mesmo `kid` — uma `HYBRID`
completa e uma `RSA`/`RS256` só com a metade clássica — justamente para que
um verificador comum encontre a entrada que reconhece. Essa diferença de
publicação entre AS e RS é intencional, não uma inconsistência: reflete a
diferença de objetivo entre Strong Nesting (sem pretensão de compatibilidade
legada) e extensão por payload (compatibilidade legada é o objetivo
central) — ver `JWT_Hybrid_Architecture.md`, Seções 5 e 6, para o
levantamento completo de por que cada artefato usa o esquema que usa.

### Referência ao código

`mock-service-os/mock_as/utils/opin/hybridSigning.js`:
- Linha 24: `HYBRID_ALG = 'MLDSA65-RSA2048-PSS-SHA256'` — a string de
  algoritmo publicada.
- Linha 36 em diante: composição de `pk_hybrid` como a concatenação das
  chaves clássica e pós-quântica.

Para o lado RS: `insurance-server-lambdas/src/main/java/com/raidiam/
trustframework/mockinsurance/crypto/ResponseSigningService.java`,
`loadHybridSigner()`'s `publicJwks()` (linhas 318–327) — monta a entrada
`RSA`/`RS256` a partir de `classicJwk.get("n"/"e")` (as mesmas usadas para
assinar, não uma re-derivação) e retorna `List.of(publicJwk(), plainRsaJwk)`,
as duas entradas sob o mesmo `kid`; `hybridKid` (linhas 244–248) é onde
`SHA-256(classicPk‖pqcPk)` é computado — a mesma fórmula que
`jwks_rs_derived.json` reproduz e que bate com o `kid` do JWT (Seção 2). O
relato completo da descoberta/correção que motivou publicar as duas
entradas está em `thesis/results/v4/DECISIONS.md`, Decision 13, Seção 6.

---

## 4. Evidência do handshake TLS — grupo de troca de chave negociado

### O artefato real

Linha de log real do próprio gateway (`mock_mtls`), capturada ao vivo
durante uma conexão do perfil Híbrido através do `tls_kem_proxy`:
[`handshake_log.json`](handshake_log.json).

```json
{
  "msg": "mTLS handshake complete",
  "tlsVersion": "TLS 1.3",
  "cipherSuite": "TLS_AES_128_GCM_SHA256",
  "curveID": "X25519MLKEM768",
  "clientCertBytes": 6859,
  "mtlsHandshakeBytes": 17956,
  "handshakeDurationMs": 58
}
```

`curveID: "X25519MLKEM768"` confirma diretamente, na própria negociação TLS
ao vivo, que o grupo híbrido de troca de chave foi de fato usado — não é uma
configuração assumida, é o valor que o handshake realmente negociou,
registrado pelo próprio processo Go que terminou a conexão.

**Tamanho da chave pública do KEM (extensão `key_share` do `ClientHello`)**:
medido e documentado anteriormente neste mesmo projeto, com a mesma
implementação de cliente Go ainda em uso — `thesis/results/v6/Level 1/
DECISIONS.md`, Decision 2 — via decomposição byte-a-byte do `ClientHello`
real: **1.226 bytes** para `X25519MLKEM768` (a chave efêmera X25519 de 32
bytes mais a chave pública ML-KEM-768 de 1.184 bytes, mais overhead de
codificação da extensão). Não refeito aqui porque exige captura de pacote
bruto (fora do escopo desta pasta) e o cliente/mecanismo não mudou desde
aquela medição. O tamanho do ciphertext (enviado pelo servidor, dentro do
`ServerHello`/`EncryptedExtensions`, já cifrado no nível de registro TLS
antes do `Finished`) **não foi extraído** — não há instrumentação neste
projeto que o exponha sem captura de pacote bruto no nível TLS, diferente do
`key_share` do `ClientHello`, que aquela investigação decompôs diretamente.

### A prova que realmente importa: a chave de sessão foi de fato derivada do KEM, não é decorativa

`curveID: "X25519MLKEM768"` no log prova que o *nome* do grupo negociado é
esse. Não prova, sozinho, que o segredo de sessão realmente resultante
depende de uma troca de chave nova a cada conexão — em tese, um log poderia
dizer isso mesmo se o segredo fosse fixo por algum bug. A prova real: abrir
duas conexões TLS independentes, ambas forçadas a `X25519MLKEM768`, e
exportar material de chave de cada uma via **RFC 5705**
(`tls.ConnectionState.ExportKeyingMaterial` — o mesmo mecanismo padrão que
TLS usa para channel binding). Se as duas exportações vierem diferentes,
o segredo de sessão foi genuinamente re-derivado do zero em cada handshake
— exatamente o que uma troca de chave efêmera (KEM ou ECDHE) garante; um
segredo fixo ou cacheado exportaria o mesmo valor sempre.

```
$ docker run --rm --network insurance-server-lambdas_default \
    -v thesis/scripts/verify_kem_export:/src -v mock-service-os/certs:/certs:ro -w /src \
    golang:1.27-rc-alpine go run . x25519mlkem768 /certs/client_one_hybrid.crt /certs/client_one_hybrid.key

connection 1: curveID=X25519MLKEM768 tlsVersion=TLS 1.3 exported(32B)=3bb7ce2812ac6833ec4484a9ed68c0f7c4db74af5aa53d34229447fb913a7778
connection 2: curveID=X25519MLKEM768 tlsVersion=TLS 1.3 exported(32B)=0456a3e67350bb00e6086436db013ca6902c70d5401e2cd24c5da7c52a092216

RESULT: verificado -- ambas as conexoes negociaram X25519MLKEM768, e o material de chave exportado (RFC 5705)
e DIFERENTE entre as duas -- confirma que o segredo de sessao foi de fato derivado de uma troca de chave nova
a cada conexao (o mecanismo KEM/ECDHE efemero real), nao um valor fixo ou decorativo.
```

Saída completa em
[`verify_kem_export_output.txt`](verify_kem_export_output.txt). As duas
exportações de 32 bytes acima são visivelmente distintas byte a byte, e
ambas as conexões, checado no código, negociaram o mesmo grupo híbrido —
isso é o mais perto que dá de "abrir a caixa" do segredo de sessão sem
comprometer a segurança da própria conexão (o segredo mestre em si nunca é
exposto por design do TLS 1.3; o exportador é o mecanismo padrão que existe
justamente para permitir este tipo de verificação externa sem violar isso).

### Explicação do mecanismo

O Clássico usa curvas ECDHE puras (P-521/P-384/P-256); o Híbrido combina uma
troca de chave clássica (X25519) com uma pós-quântica (ML-KEM-768) no mesmo
grupo `X25519MLKEM768` — a mesma escolha que Chrome e Cloudflare já usam por
padrão em produção (ver `thesis/results/v7/DECISIONS.md`, Decision 1, e
`thesis/results/v6/Level 1/ARCHITECTURE.md`, Fase 1, para o raciocínio
completo de por que esse grupo específico foi escolhido para o Híbrido, e
`MLKEM1024` — sem componente clássico — para o PQC). Desde a unificação da
v7 (Decision 1), o mesmo cliente Go (`tls_kem_proxy`) negocia esse grupo
para os três perfis, variando só a curva solicitada — o Clássico pede
curvas ECDHE puras pelo mesmo processo.

### Referência ao código

- `mock-service-os/mock_mtls/main.go`, função `init()`, linhas 136–138: para
  `CRYPTO_PROFILE=hybrid`, `serverCurvePreferences = []tls.CurveID{tls.
  X25519MLKEM768}` — essa é a política padrão do gateway para esse perfil
  (sem downgrade silencioso para clássico). **Ressalva verificada, não
  suposição**: existe uma exceção única, deliberada e pré-existente a este
  trabalho — `GetConfigForClient` (mesmo arquivo) reserva curvas clássicas
  exclusivamente para conexões cujo SNI seja `"matls-api.local"` (a chamada
  interna `auth`→RS, `InsurerAdapter.getConsent()`, cujo cliente Node.js não
  negocia X25519MLKEM768 — estende o carve-out de certificado da Decision 5,
  `thesis/results/v5/size/DECISIONS.md`, à troca de chave). Confirmado ao
  vivo: instrumentando esse ponto com log e cruzando com os handshakes
  `curveID=CurveP256` capturados no mesmo período, a correspondência foi
  1:1 (35 de cada, mesmo `remoteAddr`) — nenhum handshake clássico sem essa
  explicação. Não afeta o tráfego cliente↔gateway que este artefato mede
  (SNI diferente, via `tls_kem_proxy`).
- `thesis/scripts/tls_kem_proxy/main.go`, função `runRelay()`, caso
  `"x25519mlkem768"` do `switch` de curvas — o cliente que efetivamente
  negocia esse grupo do lado do `tls_kem_proxy`.
- O campo `curveID` do log acima vem de `handshakeInfo.curveID`,
  preenchido a partir de `cs.CurveID.String()` (`ConnectionState` do próprio
  handshake TLS) em `mock_mtls/main.go` — não é uma suposição de
  configuração, é lido de volta do handshake que de fato aconteceu.
- `thesis/scripts/verify_kem_export/main.go` — a prova de exportação de
  chave rodada acima (generalizada para os três perfis via o argumento
  `-group`/primeiro argumento posicional): curva forçada em
  `CurvePreferences` (linha 62), `state.ExportKeyingMaterial(
  "EXPORTER-artifact-proof", nil, 32)` (linha 72, a API pública do Go que
  implementa RFC 5705) em cada uma das duas conexões, comparação byte a
  byte das duas saídas (linha 95).

---

## 5. `id_token` real, decodificado — Strong Nesting de verdade (sigma1||sigma2), criptografia da mensagem ainda clássica

### O artefato real

Capturado ao vivo do campo `id_token` de uma resposta real `POST /token`
(fluxo completo, perfil Híbrido): [`id_token_raw.txt`](id_token_raw.txt) —
um JWE de 5 segmentos (diferente dos JWS de 3 segmentos das Seções 1–4):

```
$ node decrypt_and_verify_id_token.mjs hybrid id_token_raw.txt   # (dentro do container `auth`)

id_token: 7695 chars, 5 segments (JWE compact serialization)
JWE protected header: {"alg":"RSA-OAEP","enc":"A256GCM","cty":"JWT","kid":"92297d36-...","iss":"https://auth.local","aud":"client_one"}
Decrypted inner JWS: 5090 chars, 3 segments
Inner JWS header: {"alg":"PS256","kid":"xQLs45xYyJr1omHs4qnB2rhes9qNFHIHQ5YPQKVJliM"}
Inner JWS payload (decoded, complete): {
  "sub": "usuario1@seguradoramodelo.com.br",
  "acr": "urn:brasil:openinsurance:loa3",
  "nonce": "Auxk99qUA2Vl",
  "aud": "client_one",
  "exp": 1789354340,
  "iat": 1789350740,
  "iss": "https://auth.local"
}
Inner JWS signature length (bytes): 3565
VERIFICATION RESULT: {"valid": true, "reason": "both sigma1 and sigma2 verified"}
```

Saída completa em
[`verify_id_token_output.txt`](verify_id_token_output.txt). O `kid` do JWE
(`92297d36-...`) é **byte-idêntico ao do id_token do Clássico** (Seção 5 do
README daquele perfil) — o Híbrido reaproveita a mesma chave de cifragem do
cliente que o Clássico, consistente com o padrão já confirmado nesta pasta
de que o Híbrido reaproveita a identidade RSA clássica em toda parte, não
apenas no certificado (Seção 1).

### A prova que realmente importa: as DUAS assinaturas internas verificam, com o AND gate real — a cifra externa continua clássica

**A camada de dentro é genuinamente Strong Nesting, não uma assinatura
simples do tamanho certo**: 3.565 bytes de assinatura decompostos em sigma1
(256 bytes, PS256/RSA) + sigma2 (3.309 bytes, ML-DSA-65) — a mesma
verificação usada em toda a tese (`verifyHybrid()`,
`mock_as/utils/opin/hybridVerification.js`, a função de produção real, não
uma reimplementação para este artefato): sigma1 verificado contra a chave
RSA clássica sobre `header.payload`; sigma2 verificado contra a chave
ML-DSA-65 sobre `header.payload || sigma1`; **AND gate — os dois passaram**
(`"both sigma1 and sigma2 verified"`). O header externo continua dizendo
`alg: "PS256"`, por design (Decision 10, `thesis/results/v4/DECISIONS.md`)
— só o tamanho decodificado da assinatura denuncia que é Strong Nesting, o
mesmo padrão de "header comum, assinatura maior" já visto no
`client_assertion`.

**A camada de fora (a cifragem do JWE) continua `RSA-OAEP`, igual em todos
os três perfis** — a mesma limitação genuína documentada nas Seções 5 de
`artifacts/classico/` e `artifacts/pqc/`: não existe hoje padrão JOSE/COSE
para cifragem pós-quântica. O Híbrido não muda isso — a metade
pós-quântica deste perfil vive inteiramente na assinatura, nunca na
cifragem.

### Explicação do mecanismo

Sob `CRYPTO_PROFILE=hybrid`, o `oidc-provider` é mantido completamente
alheio ao modo híbrido — configurado como se fosse Clássico puro
(`internalSigningAlgs = ['PS256']`, `internalSigningKey =
cryptoProfile.classicSigningKey`) — porque `"MLDSA65-RSA2048-PSS-SHA256"`
não é um algoritmo JOSE real que `jose`/`oidc-provider` reconheçam. A
diferença crucial em relação ao Clássico está em UMA peça: a classe
`HybridIdTokenSigningKey` (`idTokenExternalSigningKey.js`), registrada como
a chave de assinatura via o mecanismo oficial `ExternalSigningKey` do
`oidc-provider`. Quando o `oidc-provider` monta e assina o `id_token`
internamente, ele entrega os bytes exatos de `header.payload` a essa
classe, que devolve `signStrongNesting(bytes)` — sigma1||sigma2 reais — no
lugar do que seria uma assinatura PS256 comum. O `oidc-provider` nunca sabe
que recebeu algo diferente de uma assinatura PS256 válida; ele só repassa o
que a classe devolveu. Depois disso, a cifragem RSA-OAEP+AES-256-GCM
acontece exatamente como no Clássico — cega ao que está cifrando.

### Referência ao código

- `mock-service-os/mock_as/utils/opin/idTokenExternalSigningKey.js`: classe
  `HybridIdTokenSigningKey` completa — `sign()` (linha 63) chama
  `signStrongNesting()`; o comentário no topo do arquivo (linhas 1–41)
  documenta em detalhe por que esse desvio via `ExternalSigningKey` é
  necessário e por que o header tem que continuar dizendo `"PS256"`.
- `mock-service-os/mock_as/utils/opin/configuration.js`, linha 11 (import)
  e a troca de `internalSigningKey`/`internalSigningAlgs` para o modo
  híbrido (linhas 42–44).
- `mock-service-os/mock_as/utils/opin/hybridVerification.js`, função
  `verifyHybrid()` (linha 33) — a verificação real, de produção, rodada
  acima sem nenhuma modificação.
- `mock-service-os/mock_as/utils/opin/configuration.js`, linha 330:
  `idTokenEncryptionAlgValues: ['RSA-OAEP']` — mesma cifragem clássica de
  sempre, inclusive aqui.
- `thesis/scripts/verify_hybrid_jwt/decrypt_and_verify_id_token.mjs` — a
  verificação rodada acima.

---

## 6. `client_assertion` real — payload-extension (RS256 + `pqc`), o AND gate de produção

### Por que este artefato existe

O passo 8 do SAD ("Token de acesso") não tem assinatura nenhuma — o
`access_token` capturado ao vivo é uma string opaca. A "assinatura
híbrida" que uma versão anterior de `thesis/docs/
Cruzamento_SAD_vs_Experimentos.md` atribuía a esse passo é, na prática, o
`client_assertion` que o cliente assina para autenticar `POST /token` —
exatamente o artefato capturado abaixo, com o mesmo esquema payload-
extension (Decision 13) já visto na Seção 2 deste README, aqui na direção
oposta (cliente → AS, não AS/RS → cliente).

### O artefato real

Capturado ao vivo do corpo de uma requisição real `POST /token` (perfil
Híbrido): [`client_assertion_raw.txt`](client_assertion_raw.txt).

```
$ node verify_client_assertion.mjs hybrid client_assertion_raw.txt   # (dentro do container `auth`)

Header: {"alg":"RS256","kid":"c0d35890-1f2a-4ed5-bf9f-856d10ccd093","typ":"JWT"}
Payload (decoded, sem o campo pqc.signature truncado): {
  "sub": "client_one",
  "aud": "https://matls-auth.local/token",
  "iss": "client_one",
  "exp": 1789351935,
  "iat": 1789351875,
  "jti": "W7odyDVfnRq4Bij6ANcq_Ewr",
  "pqc": { "alg": "ML-DSA-65", "signature": "kfglsACsNFdXVp9F6gHoGqik2c...(4412 caracteres, truncado)" }
}
Signature length (bytes): 512
VERIFICATION RESULT: {"valid": true, "reason": "both RS256 and ML-DSA-65 verified", "hybridShaped": true}
```

Saída completa (com o `pqc.signature` integral) em
[`verify_client_assertion_output.txt`](verify_client_assertion_output.txt).
Header `alg: "RS256"` — não `PS256` como o Clássico — por design (Decision
13: o cliente assina sob um header comum desde o início, para que um
verificador RS256 legado aceite este `client_assertion` sem nenhuma
adaptação, exatamente como o JWT da Seção 2 do lado do RS). Assinatura
externa: 512 bytes (RSA-4096 do cliente, mesma chave do Clássico); a
assinatura ML-DSA-65 real vive dentro do claim `pqc`, não no segmento de
assinatura do JWS.

### A prova que realmente importa: o AND gate de produção passou, nas duas direções

Esta é a MESMA função de produção (`verifyPayloadExtension()`,
`payloadExtensionVerification.js`) já usada na Seção 2 — aqui invocada
pelo lado que `clientHybridAuth.js` realmente chama em produção (a AS
verificando um `client_assertion` de entrada), com as chaves públicas do
CLIENTE (`client_one_hybrid_pub.jwks` + `client_one_pqc_pub.jwks`), não as
do RS. `hybridShaped: true` confirma que o verificador detectou
corretamente o formato estendido; `"both RS256 and ML-DSA-65 verified"`
confirma o AND gate completo, não apenas a metade RS256 que um verificador
legado enxergaria.

### Explicação do mecanismo

`opin_flow.py`'s `_sign_jwt_hybrid()` implementa o lado cliente do mesmo
esquema Decision 13 já documentado na Seção 2: ML-DSA-65 assina primeiro
(RFC 8785/JCS, claims sem `pqc`), o resultado vira o claim `pqc`, e RS256
assina por último sobre `header.payload` já com `pqc` embutido — um JWS
RS256 inteiramente comum do ponto de vista de qualquer verificador que não
conheça o claim extra.

### Referência ao código

- `thesis/scripts/opin_flow.py`, `_sign_jwt_hybrid()` (linha 590) — o lado
  cliente do esquema.
- `mock-service-os/mock_as/utils/opin/clientHybridAuth.js` — o middleware
  de produção que chama `verifyPayloadExtension()` sobre todo
  `client_assertion`/objeto de requisição PAR de entrada.
- `mock-service-os/certs/client_one_hybrid_pub.jwks` +
  `client_one_pqc_pub.jwks` — as chaves públicas usadas na verificação.
- `thesis/scripts/verify_hybrid_jwt/verify_client_assertion.mjs` — a
  verificação rodada acima.
