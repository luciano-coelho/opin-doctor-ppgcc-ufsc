# Arquitetura da v7 — Fluxo OPIN com três perfis criptográficos e a equação OPINsize estendida

Este documento descreve, de forma independente, a arquitetura do experimento final (v7): o sistema medido, os três perfis criptográficos, como cada primitiva atua no fluxo, como as métricas são coletadas e a equação de tamanho (OPINsize) com a extensão para certificados de CA. Os resultados numéricos estão em [`CONSOLIDATED_REPORT.md`](CONSOLIDATED_REPORT.md); aqui, os números servem apenas para ilustrar o desenho.

---

## 1. Propósito e escopo

**Pergunta do experimento.** Quanto custa, em bytes trafegados e em tempo de fluxo, migrar o fluxo de consentimento do Open Insurance Brasil (OPIN) de criptografia clássica para pós-quântica (PQC) e para uma combinação híbrida?

**O que a v7 cobre**, num único conjunto de medições:

- **Nível 2 (assinaturas)**: certificados de cliente, tokens (JWT), chaves públicas publicadas (JWKS) e a autenticação do cliente (`client_assertion`).
- **Nível 1 (troca de chave)**: a troca de chave do handshake TLS, a parte exposta ao ataque "colher agora, decifrar depois".

**O que fica fora**: a cifragem dos tokens (JWE com RSA-OAEP), para a qual não existe hoje padrão JOSE/COSE pós-quântico; o registro dinâmico de clientes (SSA/DCR); a trilha de auditoria com hash; a revogação de certificados. A cobertura completa em relação ao documento de arquitetura de segurança (SAD) está em `thesis/docs/Cruzamento_SAD_vs_Experimentos.md`.

**Histórico.** A v7 substitui a v5 (só assinaturas migradas) e a v6 (troca de chave medida isoladamente, com um cliente TLS diferente do da v5). A fusão dos dois níveis num só lote, com um único cliente TLS para os três perfis, é a decisão central da v7 (`DECISIONS.md`, Decision 1 e 2). A extensão da equação de tamanho está na Decision 7.

---

## 2. Visão geral do sistema

```
  máquina do experimento (Docker Desktop, um único host)

  ┌──────────────────────┐   TLS local        ┌──────────────────┐   mTLS real, grupo do perfil
  │ opin_flow.py         │  127.0.0.1:8443    │  tls_kem_proxy   │  (ECDHE | MLKEM1024 | X25519MLKEM768)
  │ (cliente de teste,   │ ─────────────────► │  (cliente TLS    │ ─────────────────────────────┐
  │  Python)             │ ◄───────────────── │   em Go)         │                              │
  └──────┬───────────────┘                    └──────────────────┘                              ▼
         │ assina JWTs PQC                                                     ┌───────────────────────────┐
         ▼                                                                     │ gateway mTLS (mock_mtls)  │
  ┌──────────────────────┐                                                     │  Go, porta 443            │
  │ pqc-signer           │                                                     │  roteia por Host          │
  │ (contêiner efêmero,  │                                                     └───┬────────┬──────────┬───┘
  │  Go, ML-DSA-65)      │                                                         │        │          │
  └──────────────────────┘                                              auth.local  │        │ api.local │ directory
                                                                     ┌─────────────▼┐  ┌────▼───────┐ ┌─▼────────────┐
                                                                     │ AS (auth)    │  │ RS (mockapi)│ │ Diretório/PKI│
                                                                     │ Node.js,     │  │ Java,       │ │ (no gateway) │
                                                                     │ oidc-provider│  │ BouncyCastle│ └──────────────┘
                                                                     └──────┬───────┘  └──────┬──────┘
                                                                            │  matls-api.local │
                                                                            └── auth → RS (interno, sempre clássico)
```

**O que a tabela abaixo mostra.** O diagrama acima é o mapa; a tabela dá, para cada caixa dele, o papel que cumpre no fluxo e a tecnologia em que foi implementada — útil para localizar rapidamente onde procurar código ou logs de um componente específico.

| Componente | Papel | Tecnologia |
|---|---|---|
| **`opin_flow.py`** | Cliente de teste: executa o fluxo OPIN completo e mede o tempo de cada execução | Python |
| **`tls_kem_proxy`** | Cliente TLS em Go que negocia os grupos de troca de chave que o Python não suporta; um por execução | Go (`crypto/tls`) |
| **`pqc-signer`** | Assina os JWTs ML-DSA-65 do lado do cliente; um contêiner efêmero por assinatura | Go (`crypto/mldsa`) |
| **Gateway mTLS** (`mock_mtls`) | Termina o mTLS, valida o certificado do cliente, roteia por `Host` para AS, RS e Diretório e registra métricas por conexão | Go |
| **AS** (`auth`) | Servidor de autorização: consentimento, PAR, tokens, `id_token`, JWKS | Node.js, `oidc-provider` |
| **RS** (`mockapi`) | Servidor de recursos: responde as consultas de seguros com JWT assinado | Java, BouncyCastle |
| **Diretório/PKI** | Serve os certificados de CA (`root-ca.pem`, `issuer-ca.pem`) | Gateway (`directoryHandler`) |

O perfil ativo é escolhido por uma única variável, `CRYPTO_PROFILE` (`classic`, `pqc` ou `hybrid`), lida por todos os componentes; a troca é feita por `switch_crypto_profile.py`, que também espera o ambiente assentar.

**A conexão interna `auth`→RS.** Para exibir o consentimento, o AS consulta o RS pelo mesmo gateway (`matls-api.local`) com um certificado de transporte próprio, fixo e clássico. O cliente HTTPS do Node.js não negocia os grupos pós-quânticos, então essa única conexão é mantida clássica por uma exceção deliberada por SNI no gateway (Seção 5.1). Ela não faz parte do fluxo medido: não entra em N_mTLS nem em nenhuma métrica de tamanho ou de handshake.

---

## 3. O fluxo OPIN medido

Cada execução tem dois sub-fluxos executados em sequência, num total de **28 requisições**:

**O que a tabela abaixo mostra.** Cada linha é um dos dois sub-fluxos do OPIN (obter consentimento para dados de seguros, depois para dados de pessoas); a coluna "Requisições" conta quantas chamadas HTTP/TLS aquele sub-fluxo faz, e "Etapas" lista, na ordem em que acontecem, o que cada uma dessas chamadas é.

| Sub-fluxo | Requisições | Etapas |
|---|---:|---|
| Consentimentos de seguros | 12 | `GET /jwks` · `GET root-ca.pem` · `GET issuer-ca.pem` · `POST /token` (client_credentials) · `POST` consentimento · `GET` consentimento ×3 · `POST /request` (PAR) · [login automatizado] · `POST /token` (authorization_code) · `GET` consentimento ×2 |
| Dados de seguro de pessoas | 16 | as mesmas 8 primeiras etapas de identificação e autorização (1 `GET` de consentimento) · consulta da apólice ×2 · sinistro ×2 · informações da apólice ×2 · prêmio ×2 |

O login é automatizado e usa um pool de conexão separado (como um navegador faria), o que dá **três pools de conexão por sub-fluxo** (AS, RS e login) e, nos dois sub-fluxos, as **6 conexões mTLS** que a equação de tamanho usa como N_mTLS. Cada conexão é reaproveitada (keep-alive) por todas as chamadas do seu pool. O fluxo trafega **26 JWTs**, busca o JWKS do AS **2 vezes** (uma por sub-fluxo) e baixa **4 certificados de CA** (raiz e emissora, em cada sub-fluxo).

---

## 4. Os três perfis criptográficos

### 4.1. Onde cada primitiva atua

**O que a tabela abaixo mostra.** Cada linha é um artefato criptográfico do fluxo (um certificado, um token, uma chave publicada); as três colunas mostram, lado a lado, qual algoritmo ou esquema aquele artefato usa em cada perfil. É a referência central para responder "o que muda, exatamente, quando o perfil muda?" para cada peça do sistema.

| Artefato | Clássico | PQC | Híbrido |
|---|---|---|---|
| **Troca de chave TLS** | ECDHE clássico (P-521, P-384, P-256) | **MLKEM1024** puro | **X25519MLKEM768** |
| **Certificado de cliente** (mTLS) | RSA-4096, assinado por CA RSA | Chave do titular ML-DSA-65; CA continua RSA | RSA-4096 + três extensões X.509 não críticas com o material ML-DSA-65, assinado duas vezes (RSA e ML-DSA-65) |
| **JWT de resposta do RS** | PS256 | ML-DSA-65 | RS256 com extensão de payload (`pqc`) |
| **`id_token` e JARM do AS** | PS256 | ML-DSA-65 | Strong Nesting (σ1‖σ2) |
| **`client_assertion` e objeto PAR** | PS256 | ML-DSA-65 | RS256 com extensão de payload (`pqc`) |
| **Chave pública de assinatura do AS (JWKS)** | RSA (256 bytes) | `kty: AKP`, ML-DSA-65 (1.952 bytes) | `kty: HYBRID`, chave composta (2.208 bytes) |
| **Cifragem do `id_token`** | RSA-OAEP + AES-256-GCM | igual (clássica) | igual (clássica) |
| **Token de acesso** | opaco, ligado ao certificado do cliente | igual | igual |

O token de acesso é uma cadeia opaca, sem assinatura: a assinatura que autentica o cliente nesse passo é a do `client_assertion`.

Tamanhos resultantes por fluxo (idênticos em todos os cenários de latência): certificado de cliente de {{cert_classic}}, {{cert_pqc}} e {{cert_hybrid}} bytes; JWT médio de {{jwtmean_classic}}, {{jwtmean_pqc}} e {{jwtmean_hybrid}} bytes; handshake de {{hs_classic}}, {{hs_pqc}} e {{hs_hybrid}} bytes (Clássico, PQC, Híbrido).

### 4.2. Por que os perfis fazem escolhas diferentes

**PQC — filosofia "só pós-quântico".** Assinatura e troca de chave sem nenhum componente clássico. A única exceção é o certificado de cliente, cuja emissão pela CA continua RSA (a chave do titular é ML-DSA-65, mas a CA não migra): é o desenho deliberado de migrar primeiro a identidade do participante, sem exigir que a CA aprenda a assinar com ML-DSA-65.

**Híbrido — filosofia "porta AND".** Comprometer o resultado exige quebrar os dois algoritmos ao mesmo tempo. Cada artefato usa o esquema de combinação mais adequado ao seu papel:

**O que a tabela abaixo mostra.** O perfil Híbrido não usa um único jeito de combinar clássico e pós-quântico — usa três, cada um escolhido para o tipo de artefato em questão. A tabela lista os três esquemas, onde cada um é aplicado, como funciona por dentro (em que ordem se assina, o que entra em cada assinatura) e a propriedade de segurança que ele garante.

| Esquema | Onde | Como funciona | Propriedade |
|---|---|---|---|
| **Extensões X.509 duplamente assinadas** (Bindel et al., 2019) | Certificados | O ML-DSA-65 assina primeiro, sobre o certificado ainda sem a assinatura alternativa; o RSA assina por último, sobre o certificado completo. As extensões (`SubjectAltPublicKeyInfo`, `AltSignatureAlgorithm`, `AltSignatureValue`) são marcadas como não críticas, então um verificador clássico as ignora | Compatibilidade com verificadores legados |
| **Extensão de payload** | JWT do RS; `client_assertion`; objeto PAR | O ML-DSA-65 assina primeiro, sobre os claims canonicalizados (RFC 8785), e o resultado entra como o claim `pqc`; o RS256 assina por último, cobrindo esse claim. O cabeçalho continua um `RS256` comum | Um verificador RS256 comum aceita o token ignorando `pqc` |
| **Strong Nesting** | `id_token`, JARM | σ1 = PS256(mensagem); σ2 = ML-DSA-65(mensagem ‖ σ1); assinatura = σ1 ‖ σ2 (256 + 3.309 = 3.565 bytes). O cabeçalho continua `PS256` | Não é possível recombinar uma assinatura clássica com outra pós-quântica (propriedade SUF-CMA) |
| **Grupo híbrido de troca de chave** | TLS | `X25519MLKEM768`: a chave da sessão deriva do X25519 e do ML-KEM-768 juntos | Confidencialidade preservada se apenas um dos dois for quebrado |

A extensão de payload abre mão parcialmente da propriedade SUF-CMA do Strong Nesting em troca de compatibilidade com verificadores legados; o raciocínio completo e as referências estão em `thesis/results/v4/JWT_Hybrid_Architecture.md`.

**Clássico — a linha de base.** Nada muda em relação ao que já era o padrão do sistema.

### 4.3. Prova de implementação

Para cada perfil, `artifacts/` traz uma captura real de cada artefato acima (certificado, JWT do RS, entrada de JWKS, evidência do handshake, `id_token`, `client_assertion`) com uma **verificação criptográfica reproduzível** (por exemplo, a assinatura ML-DSA-65 do certificado híbrido é reconstruída e verificada, e a chave de sessão do handshake é comprovada nova a cada conexão por exportação de material de chave, RFC 5705): [Clássico](artifacts/classico/README.md), [PQC](artifacts/pqc/README.md), [Híbrido](artifacts/hybrid/README.md).

---

## 5. Camada de transporte

Os três perfis foram medidos sob a mesma arquitetura de cliente TLS (`tls_kem_proxy`), eliminando variáveis de confusão entre eles — cada perfil pede exatamente um grupo de troca de chave, sem fallback: se o servidor não o oferecer, a conexão falha de forma visível, em vez de recuar silenciosamente para clássico. Descrição completa, histórico de problemas e referências de código em [`TLS_KEM_Proxy_Architecture.md`](TLS_KEM_Proxy_Architecture.md).

### 5.1. A política do gateway e sua única exceção

O gateway define a lista de grupos aceitos por `CRYPTO_PROFILE`: curvas clássicas no Clássico, somente `MLKEM1024` no PQC, somente `X25519MLKEM768` no Híbrido (com TLS 1.3 obrigatório nos dois últimos). Existe **uma exceção, deliberada e restrita por SNI**: toda conexão cujo `ServerName` seja `matls-api.local` (a chamada interna `auth`→RS) recebe a configuração clássica. Foi confirmado, conexão a conexão, que **todo** handshake clássico observado sob PQC/Híbrido tem esse SNI e que nenhum outro o tem (35 aplicações da exceção, 35 handshakes clássicos, mesmo endereço de origem em cada par; `DECISIONS.md`, Decision 6).

---

## 6. Camada de assinatura

### 6.1. Certificados

`mock-service-os/certs/main.go` gera os certificados de cada perfil. O certificado híbrido reutiliza a chave RSA do Clássico e acrescenta o material ML-DSA-65 em extensões não críticas; a verificação independente reconstrói o conteúdo que o ML-DSA-65 assinou (o certificado sem a extensão de assinatura alternativa) e o confere contra a chave da CA. No gateway, a validação do certificado de cliente híbrido aplica a porta AND (as duas assinaturas devem verificar).

### 6.2. Tokens e chaves publicadas

O RS assina cada resposta conforme o perfil (`ResponseSigningService`); o AS assina `id_token` e JARM (`oidc-provider` com uma chave de assinatura externa no perfil híbrido, para produzir o Strong Nesting sem que a biblioteca reconheça um algoritmo novo); o cliente assina `client_assertion` e objeto PAR (`opin_flow.py`). Os JWKS publicam a chave de cada perfil (no Híbrido, uma entrada composta no AS e, no RS, duas entradas sob o mesmo `kid`: a composta e uma só com a metade clássica, para que um verificador comum encontre a que reconhece).

### 6.3. O limite: a cifragem

O `id_token` é cifrado (JWE, RSA-OAEP com AES-256-GCM) para a chave que o cliente registrou, em **todos** os perfis. Não existe hoje padrão JOSE/COSE para representar uma chave ML-KEM num JWE e a biblioteca usada não o suporta. Um `id_token` do perfil PQC capturado ao vivo mostra o resultado: por dentro, uma assinatura ML-DSA-65 pura verificada; por fora, uma cifragem RSA-OAEP idêntica à do Clássico.

---

## 7. A equação OPINsize: a extensão proposta por esta tese

A equação original de tamanho do fluxo (equivalente à Eq. 3.1 de Schardong et al., 2022) soma três termos — o custo do handshake mTLS, dos tokens trafegados e das chaves públicas publicadas:

```
OPINsize = N_mTLS × handshake_bytes + N_JWT × JWT_size + N_JWK × JWK_PK_size
```

Esta tese a estende com um quarto termo, para os certificados de Autoridade Certificadora que o fluxo baixa e que já eram medidos, mas nunca entravam na soma. A partir daqui, **OPINsize refere-se sempre à fórmula estendida** — a de três termos não volta a aparecer como resultado, só serviu para justificar a extensão:

```
OPINsize = N_mTLS × handshake_bytes + N_JWT × JWT_size + N_JWK × JWK_PK_size + N_PKI × PKI_bytes
```

com N_mTLS = {{n_mtls}}, N_JWT = {{n_jwt}}, N_JWK = {{n_jwk}} e N_PKI = {{n_pki}} ({{n_root}} da raiz + {{n_issuer}} da emissora). `PKI_bytes` é o tamanho médio, em bytes, dos dois certificados de CA servidos, **no formato em que trafegam (PEM)**; como raiz e emissora têm tamanhos ligeiramente diferentes, N_PKI × PKI_bytes é a soma exata das {{n_pki}} transferências. Cada termo é um tamanho de material criptográfico, não de tráfego HTTP — o tamanho do JWT é o comprimento do token, o da chave é o tamanho da chave, sem cabeçalhos. Com N_PKI = 0 a equação se reduz à original, o que preserva a comparabilidade com a literatura.

### 7.1. Por que o termo de PKI é necessário

O fluxo baixa dois certificados de CA (`root-ca.pem`, `issuer-ca.pem`) no início de cada sub-fluxo, {{n_pki}} transferências por execução completa. Esses certificados **não são handshake** (trafegam por HTTP, fora da negociação TLS), **não são JWT** e **não são chave de JWKS**; nenhum dos três termos originais os inclui, embora o custo já fosse medido — os arquivos brutos o registram sob o participante "PKI/CRL". Não há dupla contagem com o handshake: os certificados que trafegam **dentro** dele (servidor e cliente) são contados no termo de handshake; os de CA baixados por HTTP são transferências distintas.

**Origem dos dados, sem nova medição.** Os tamanhos dos certificados vêm dos arquivos PEM que o gateway serve (`mock-service-os/certs/`) e foram validados contra o volume de resposta HTTP já registrado nos dados brutos: o volume medido menos o corpo dos {{n_pki}} certificados dá um enquadramento HTTP de exatamente {{frame_each}} bytes por resposta, idêntico nos três perfis, o que só ocorre se o corpo servido for o arquivo usado no cálculo.

**O que a tabela abaixo mostra.** Para cada perfil, o tamanho em bytes do certificado raiz e do certificado da emissora (no formato PEM, como trafegam), e a soma dos {{n_pki}} downloads que compõem o termo de PKI da equação — a base numérica de tudo que a Seção 7.2 discute.

{{table:pki_detail}}

### 7.2. Por que isso importa especificamente no cenário híbrido

No Híbrido, cada certificado de CA carrega, além da estrutura RSA, o material ML-DSA-65 completo (chave pública e assinatura alternativa) nas três extensões: cada um ocupa cerca de {{root_hybrid}} bytes em PEM, contra {{root_classic}} no Clássico e {{root_pqc}} no PQC. Em termos absolutos:

- O termo de PKI do Híbrido é de **{{t_pki_hybrid}} bytes** — **{{hyb_pki_over_jwk}} o termo de chave pública JWK** ({{t_jwk_hybrid}} bytes) e equivalente a {{hyb_pki_over_hs}} do termo de handshake ({{t_hs_hybrid}} bytes): maior que um dos outros três termos da própria equação.
- É **{{pki_ratio_hybrid_classic}} o termo de PKI do Clássico** e {{pki_ratio_hybrid_pqc}} o do PQC: o crescimento do material de CA é a parcela do custo mais sensível ao esquema de combinação escolhido, porque o Híbrido é o único perfil cujos certificados de CA carregam as duas assinaturas.
- O termo de PKI não altera a ordem dos perfis nem o peso dominante dos JWTs ({{t_jwt_hybrid}} bytes no Híbrido) — sua participação no OPINsize de cada perfil está na Seção 7.3.

### 7.3. Impacto numérico

**O que a tabela abaixo mostra.** Cada linha é um termo da equação estendida; as colunas de perfil dão o valor de N (quantas vezes o termo ocorre no fluxo) e o resultado em bytes de cada termo, por perfil. A linha **OPINsize** é a soma dos quatro termos — o resultado final da equação — e a linha seguinte mostra que fração desse total o termo de PKI (o novo, desta tese) representa.

{{table:opin}}

**Como ler a tabela de razões abaixo.** Cada linha divide o OPINsize de um perfil pelo de outro, para responder diretamente "quantas vezes maior/mais pesado é X em relação a Y" — o mesmo tipo de razão usado nas tabelas de tamanho de `CONSOLIDATED_REPORT.md`, Seção 3.1.

{{table:opin_ratios}}

- O termo de PKI representa {{share_classic}} do OPINsize do Clássico, {{share_pqc}} do PQC e {{share_hybrid}} do Híbrido — no Híbrido, o segundo maior componente da soma, atrás só do termo de JWT.
- Pelo OPINsize, o Híbrido é {{opin1_ratio_hybrid_pqc}} o PQC e {{opin1_ratio_hybrid_classic}} o Clássico; o PQC é {{opin1_ratio_pqc_classic}} o Clássico.
- O PQC tem a menor participação relativa do termo de PKI porque, neste protótipo, seus certificados de CA têm chave de titular ML-DSA-65 mas continuam assinados por uma CA RSA (desenho deliberado da Etapa 3.1); no Híbrido, os certificados de CA carregam as duas assinaturas.

### 7.4. Sensibilidade e limites do termo

- **Formato do certificado.** O PEM (base64 com quebras de linha) ocupa cerca de 36–39% mais que o DER; PEM é o formato que efetivamente trafega. Em DER, o termo seria (a tabela abaixo recalcula o OPINsize com o termo de PKI em DER, e mostra a variação percentual em relação ao OPINsize oficial em PEM):

{{table:sens_der}}

- **Enquadramento HTTP.** Usando diretamente o volume de resposta medido (corpo + {{frame_each}} bytes por certificado), o OPINsize muda em menos de 1 ponto percentual — a tabela abaixo é a mesma comparação, agora com o termo de PKI medido pelo tráfego HTTP real em vez do tamanho do arquivo PEM:

{{table:sens}}

- **N_PKI é uma propriedade do fluxo implementado.** O cliente de teste baixa os certificados de CA no início de cada sub-fluxo, sem cache; um cliente real com cache pagaria menos. A fórmula mantém N_PKI explícito para permitir outros valores, do mesmo modo que N_JWK.
- **Escopo.** O OPINsize modela o custo dos artefatos criptográficos; não inclui cabeçalhos HTTP, sobrecarga de TLS/TCP/IP nem o tráfego de aplicação total (`total_bytes_exchanged`), que é outra métrica.

---

## 8. Como as métricas são coletadas

**O que a tabela abaixo mostra.** Para cada métrica usada nos resultados, de onde exatamente o valor sai (qual componente a registra) e o mecanismo de medição — útil para auditar a origem de qualquer número deste relatório ou de `CONSOLIDATED_REPORT.md`.

| Métrica | Onde é medida | Como |
|---|---|---|
| `handshake_bytes` | Gateway | Um contador na conexão TCP bruta (abaixo do TLS) soma os bytes lidos e escritos; o valor é lido quando o servidor começa a ler a primeira requisição, isto é, logo após o handshake terminar |
| Grupo de troca de chave negociado | Gateway | Registrado do estado da conexão TLS (`curveID`), não da configuração |
| `client_cert_der_bytes` | Cliente | Tamanho DER do certificado apresentado |
| JWT e chave JWK | Cliente | Extraídos das respostas e requisições (comprimento do token; tamanho da chave pública de cada entrada do JWKS) |
| Bytes por participante | Cliente | Cabeçalhos + corpo de cada requisição e resposta, atribuídos a Cliente, "Outros" (AS + RS) ou PKI/CRL |
| `T_fluxo` | Cliente | Relógio monotônico, do início ao fim do fluxo completo; tentativas descartadas por falhas conhecidas não contam |

O gateway registra todas as conexões que vê, inclusive a interna `auth`→RS; por isso as estatísticas do gateway são filtradas pelo tamanho do certificado de cliente do perfil ativo, que identifica com segurança as conexões do cliente de teste.

**Resolução AS/RS.** O participante de cada chamada é atribuído pelo endereço da URL, e na v7 as chamadas dos três perfis passam pelo proxy local — por isso o AS e o RS apareciam ambos como "Outros" nos dados brutos oficiais. Fechado com uma captura pontual (uma execução por perfil, fora do protocolo estatístico, mesma categoria de `artifacts/`) que usa o cabeçalho `Host` real de cada chamada (nunca reescrito pelo proxy) para reclassificar; válido para as 180 execuções já coletadas porque o tamanho é comprovadamente determinístico (0,00% de spread). Ver `DECISIONS.md`, Decision 10, para a metodologia completa e para um problema de ambiente real encontrado no processo.

**Limitação que permanece.** O gateway registra os bytes do handshake como uma soma de leitura+escrita, sem direção — essa decomposição exigiria instrumentar o gateway e não foi feita (`CONSOLIDATED_REPORT.md`, Seção 3.3).

**Protocolo**: 6 cenários de latência × 10 execuções × 3 perfis, para tamanho e para latência; uma execução de aquecimento descartada por cenário de latência; sem remoção de valores atípicos; aquecimento do ambiente após cada troca de perfil; convenção "JSON é a fonte, Markdown é derivado". As estatísticas foram recalculadas dos arquivos brutos numa auditoria independente antes da consolidação (`CONSOLIDATED_REPORT.md`, Seção 7).

---

## 9. Limites conhecidos da arquitetura

1. A cifragem dos tokens permanece clássica nos três perfis (Seção 6.3).
2. A conexão interna `auth`→RS permanece clássica por desenho (Seção 5.1).
3. PQC usa ML-KEM-1024 (categoria NIST 5) e Híbrido, ML-KEM-768 (categoria 3): o Go só oferece ML-KEM-1024 sem componente clássico.
4. O componente RSA do Híbrido é de 2.048 bits nos JWTs emitidos pelo AS e RS, por continuidade com o que já havia sido medido.
5. O assinador ML-DSA-65 do cliente de teste usa um contêiner efêmero por assinatura, o que tem custo de tempo próprio e afeta o T_fluxo dos perfis PQC e Híbrido (`CONSOLIDATED_REPORT.md`, Seção 6).
6. Ferramentas em versão de pré-lançamento ou experimental (Go 1.27 candidata a lançamento; ML-DSA-65 do WebCrypto do Node 24).
7. Não cobertos: SSA, DCR, trilha de auditoria com hash e revogação (CRL/OCSP).

---

## Referências

- Bindel, N., Herath, U., McKague, M., & Stebila, D. (2017). *Transitioning to a Quantum-Resistant Public Key Infrastructure.* PQCrypto 2017 (origem do Strong Nesting e da propriedade SUF-CMA).
- Bindel, N., Braun, J., Gladiator, L., Stebila, D., & Wiggers, T. (2019). *X.509-Compliant Hybrid Certificates for the Post-Quantum Transition.* Journal of Open Source Software, 4(40), 1606.
- Schardong et al. (2022), Eq. 3.1 (equação de tamanho do fluxo original). *Entrada bibliográfica completa a ser inserida pelo autor.*
- NIST FIPS 203 (ML-KEM) e FIPS 204 (ML-DSA).
- IETF TLS WG: `draft-ietf-tls-mlkem` (ML-KEM puro em TLS 1.3) e `draft-ietf-tls-ecdhe-mlkem` (grupos híbridos ECDHE-MLKEM, incluindo X25519MLKEM768), ainda em elaboração.
- RFC 8446 (TLS 1.3); RFC 5705 (exportadores de material de chave); RFC 8785 (JSON Canonicalization Scheme); RFC 7523 (autenticação de cliente por JWT).
- Documentos do projeto: [`CONSOLIDATED_REPORT.md`](CONSOLIDATED_REPORT.md), [`TLS_KEM_Proxy_Architecture.md`](TLS_KEM_Proxy_Architecture.md), [`DECISIONS.md`](DECISIONS.md), `artifacts/`, `thesis/results/v4/JWT_Hybrid_Architecture.md`, `thesis/docs/Cruzamento_SAD_vs_Experimentos.md`.
