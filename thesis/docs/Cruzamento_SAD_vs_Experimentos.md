# Cruzamento: o que o SAD propõe vs. o que os Experimentos já cobrem

Este documento responde a duas perguntas: (1) os diagramas de fluxo de segurança do SAD
estão corretos, à luz do que aprendemos construindo o sistema de verdade? (2) do que o SAD
propõe, o que os Experimentos 1/2/3 já cobrem, o que ainda falta, e o que é impossível de fazer
agora por alguma limitação técnica real (não por falta de tempo)?

Tudo aqui foi checado direto no código-fonte e nos dados da v5/v7 — não é opinião nem
suposição. Onde alguma coisa não pôde ser confirmada com certeza, isso está marcado
explicitamente. A Parte 2 foi reescrita por completo após uma verificação de cobertura dedicada,
cruzando o SAD, o código de v5/v6/v7, e a pasta `thesis/results/v7/artifacts/` — as Partes 1 e 3
(diagramas do SAD e entendimento teórico) não mudaram desde a versão anterior.

---

## Parte 1 — Os diagramas do SAD estão corretos?

O SAD tem duas figuras centrais: a **Figura 1** (o fluxo de 11 passos do OPIN, com a primitiva
criptográfica de cada um) e a **Figura 2** (a cascata do que acontece se um computador quântico
conseguir quebrar essas primitivas). No geral, as duas estão bem construídas e batem com o que
sabemos hoje. Mas encontrei dois pontos que merecem ajuste.

### 1.1. O rótulo do passo 4a (certificado de transporte, BRCAC) está incompleto

O certificado de transporte (BRCAC) faz duas coisas ao mesmo tempo dentro de um handshake
mTLS: (a) prova quem você é (usando RSA-2048), e (b) ajuda a combinar a chave secreta que vai
criptografar a conversa daquele momento em diante (usando ECDHE). São duas funções
diferentes, com dois tipos de risco diferentes se um computador quântico as quebrar:

- Quebrar o RSA-2048 permite **forjar identidade** — um atacante consegue se passar por
  aquele participante em conexões futuras. Isso é uma quebra de **autenticidade**.
- Quebrar o ECDHE permite **decifrar conversas já gravadas** — um atacante que gravou o
  tráfego de hoje consegue, no futuro, recalcular a chave daquela sessão específica e ler o
  que foi transmitido. Isso é uma quebra de **confidencialidade**.

O próprio texto do SAD (Seção 1.4) explica essa diferença claramente. Mas a Tabela 1 e a
Figura 2 rotulam o passo 4a com uma propriedade comprometida só: *"TLS channel
confidentiality"*. Isso é um problema porque a **lógica da própria Figura 2 depende da quebra de
autenticidade**, não só de confidencialidade: a cascata diz "BRCAC forjado" e depois "SSA
fraudulenta emitida" e "DCR não autorizado aceito" — esses próximos passos só fazem sentido
se o atacante conseguiu **se passar por um participante legítimo**, o que é exatamente o que a
quebra do RSA-2048 permite, não o que a quebra do ECDHE permite. Em outras palavras: o
rótulo da tabela usa a propriedade errada (ou incompleta) para explicar o mecanismo que a
própria figura está descrevendo.

**Correção sugerida**: o passo 4a deveria listar duas propriedades comprometidas, não uma —
"autenticidade da identidade institucional" (via RSA-2048, o que alimenta a cascata) e
"confidencialidade retroativa do canal" (via ECDHE, o vetor HNDL). São coisas diferentes e as
duas merecem aparecer.

### 1.2. Os passos 7/8 (consentimento e token de acesso) estão esquecendo uma dependência real

A Tabela 1 diz que os passos 7 (consentimento, OIDC) e 8 (token de acesso, FAPI) dependem só
de `RSA-PSS · RSA-2048` — ou seja, só de assinatura. Mas conferimos direto no código do
Servidor de Autorização (`mock_as/utils/opin/configuration.js`) que o `id_token` — emitido
exatamente nessa fase do fluxo — é **também criptografado** com RSA-OAEP (o mesmo
algoritmo que o passo 9 usa para os dados). Essa dependência de RSA-OAEP nos passos 7/8
não aparece em lugar nenhum da Tabela 1, que só atribui RSA-OAEP ao passo 9 (troca de dados
via API).

Isso é relevante porque descobrimos, construindo o sistema, que essa criptografia do
`id_token` é **uma das poucas coisas que hoje é literalmente impossível de proteger contra
computador quântico** — não por falta de esforço nosso, mas porque a biblioteca padrão de
JWT/JWE (`jose`) não tem nenhum suporte a ML-KEM, e não existe sequer um rascunho de
padrão (JOSE/COSE) para isso — o rascunho que existia foi retirado do grupo de trabalho do
IETF. Ou seja: essa é uma dependência real, presente, e sem solução no estado da arte atual —
exatamente o tipo de coisa que vale a pena a Tabela 1 deixar explícita, porque é um achado forte
para a tese (mostra uma lacuna que não é do OPIN, é do ecossistema de padrões PQC como um
todo).

**Ressalva**: não confirmei se essa criptografia do `id_token` é uma exigência normativa
obrigatória em todo o OPIN, ou uma configuração específica do jeito que registramos o
`client_one` no mock. Vale checar contra o Manual de Segurança do Open Insurance antes de
decidir se isso vira uma correção universal na Tabela 1, ou uma nota de rodapé específica sobre
o protótipo.

### 1.3. O resto dos diagramas

Os passos 3, 4b, 5, 6, 9, 10, 11, a lista de atores, e a direção geral da cascata na Figura 2 estão
consistentes com o que sabemos na prática, nos pontos em que já tivemos a chance de testar
(3, 4b, 7, 8 parcialmente — via os certificados e tokens híbridos que construímos e medimos).

---

## Parte 2 — O que já está coberto, o que falta, e o que é impossível

**Atualizado para a v7** (thesis/results/v7/, que fundiu Nível 1 + Nível 2 num único lote de
medição unificado, Decision 1/2 de `thesis/results/v7/DECISIONS.md`, e cujos achados de
implementação estão catalogados com prova criptográfica real em
`thesis/results/v7/artifacts/{classico,pqc,hybrid}/README.md`). A versão anterior desta tabela
descrevia a troca de chave TLS (Nível 1) como trabalho futuro — isso mudou: a v7 implementou e
mediu essa migração nos mesmos três perfis já existentes, sem precisar de um quarto perfil
separado como esta mesma seção antes previa. O texto abaixo reflete o estado real depois dessa
verificação de cobertura completa (SAD × implementação × `artifacts/`), passo a passo.

A tabela abaixo cruza os 11 passos do SAD contra o que os Experimentos 1/2/3 (Clássico/PQC/
Híbrido) + a v7 realmente construíram, mediram, e catalogaram como artefato verificável.

| # | Passo do SAD | Nível de urgência (SAD) | Status | Evidência |
|---|---|---|---|---|
| 1 | Onboarding regulatório | — (sem criptografia) | Fora de escopo (não envolve criptografia, é processo administrativo) | — |
| 2 | Registro no Diretório | — (sem criptografia) | Fora de escopo (idem) | — |
| 3 | Emissão de certificado ICP-Brasil | Nível 2 | **Coberto** — certificados híbridos gerados, medidos e com prova criptográfica real catalogada | `certs/main.go`; `artifacts/{classico,pqc,hybrid}/README.md`, Seção 1 |
| 4a | BRCAC (parte RSA/ML-DSA-65 — identidade) | Nível 2 | **Coberto** — mesma cadeia de certificados acima | idem |
| 4a | BRCAC (parte ECDHE/ML-KEM — troca de chave da sessão TLS) | **Nível 1** (o mais urgente) | **Coberto, com ressalva verificada** — desde a v7 (Decision 1), os três perfis negociam via o mesmo cliente Go (`tls_kem_proxy`): PQC usa MLKEM1024 puro, Híbrido usa X25519MLKEM768, medido (`handshake_bytes` salta de 5.119 para 16.605/18.023 bytes) e capturado com prova real (RFC 5705 key export). **Ressalva**: existe uma exceção interna, deliberada e pré-existente (Decision 5, `thesis/results/v5/size/DECISIONS.md`, estendida à troca de chave), que mantém curvas clássicas para exatamente uma conexão de serviço interno (`auth`→RS, SNI `matls-api.local`, cujo cliente Node.js não negocia MLKEM/X25519MLKEM768) — confirmada ao vivo, correspondência 1:1 entre a exceção e cada handshake clássico observado, sem nenhum caso não explicado. Não afeta o tráfego cliente↔gateway medido nem as métricas já reportadas (esse tráfego interno já era excluído delas desde a v6, Decision 7) | `mock_mtls/main.go`, `serverCurvePreferences`/`GetConfigForClient`; `thesis/results/v7/DECISIONS.md`, Decision 6; `artifacts/{pqc,hybrid}/README.md`, Seção 4 |
| 4b | BRSEAL (certificado de assinatura) | Nível 2 | **Coberto** — mesmo mecanismo de certificado híbrido. Nota: neste protótipo, BRCAC e BRSEAL são a mesma identidade (mesma chave RSA/certificado) reaproveitada para transporte mTLS e assinatura — não dois artefatos PKI fisicamente distintos como no OPIN real (confirmado comparando o módulo de `client_one.jwks` com o de `client_one.crt`, byte a byte) | idem passo 3 |
| 5 | SSA (credencial de aplicação emitida pelo Diretório) | Nível 2 | **Não coberto** — o fluxo simulado usa um cliente já pré-cadastrado, nunca busca uma SSA (inalterado desde antes da v7) | `opin_flow.py`: "No SSA fetch in either flow... client_one is a statically pre-registered client" |
| 6 | DCR (registro dinâmico de cliente) | Nível 2 (+ Nível 1 pela parte ECDHE) | **Não coberto** — mesma razão do passo 5; a cobertura de Nível 1 conquistada na v7 não ajuda aqui porque o fluxo de DCR em si nunca é exercitado (inalterado) | idem |
| 7 | Consentimento (OIDC) — assinatura do `id_token` | Nível 2 | **Coberto** — Strong Nesting (Híbrido)/PS256 (Clássico)/ML-DSA-65 (PQC), com `id_token` real capturado, decifrado e com assinatura interna verificada nos três perfis (fechando uma lacuna de catalogação identificada nesta mesma verificação: a assinatura já era medida, mas não havia artefato real até agora) | `artifacts/{classico,pqc,hybrid}/README.md`, Seção 5 |
| 7 | Consentimento (OIDC) — criptografia do `id_token` (RSA-OAEP) | **Nível 1** | **Impossível migrar hoje, confirmado nos três perfis** — sem suporte da biblioteca `jose`, sem padrão JOSE/COSE para ML-KEM; o `id_token` do perfil PQC tem assinatura ML-DSA-65 pura por dentro, mas o JWE que o envolve continua RSA-OAEP igual ao Clássico — evidência direta e concreta desse achado, não apenas teórica | `configuration.js`: comentário explícito no código citando a retirada do rascunho no IETF; `artifacts/pqc/README.md`, Seção 5 |
| 8 | Token de acesso (FAPI) | Nível 2 | **Reclassificado** — o `access_token` em si é **opaco** (`certificateBoundAccessTokens: true`, sem `formats.AccessToken` configurado; confirmado ao vivo: string de 43 caracteres, sem estrutura JWT), não carrega nenhuma assinatura. A afirmação anterior ("assinatura híbrida, medida") descrevia na verdade o `client_assertion` (`private_key_jwt`) que o cliente assina para se autenticar ao pedir o token — esse sim é PS256/ML-DSA-65/payload-extension conforme o perfil, agora capturado e verificado com o AND gate de produção real | `artifacts/{classico,pqc,hybrid}/README.md`, Seção 6 |
| 9 | Troca de dados via API — assinatura das respostas | Nível 2 | **Coberto** — extensão por payload (Clássico/PQC/Híbrido conforme o esquema), com prova criptográfica real e reproduzível nos três perfis | `artifacts/{classico,pqc,hybrid}/README.md`, Seção 2 |
| 9 | Troca de dados via API — confidencialidade via canal (ECDHE/ML-KEM) | **Nível 1** | **Coberto, mesma ressalva do item 4a-ECDHE** — as chamadas de API (`API_CONNECT_HOST`) passam pela mesma troca de chave TLS migrada, medida no mesmo `handshake_bytes` | idem 4a-ECDHE |
| 9 | Troca de dados via API — confidencialidade via payload (RSA-OAEP/JWE) | **Nível 1** | **Não coberto, mesma limitação do item 7-enc** — nenhuma resposta de API é hoje cifrada (apenas assinada); se fosse, esbarraria na mesma ausência de padrão JOSE/COSE para ML-KEM | idem 7-enc |
| 10 | Trilhas de auditoria (SHA-256) | Nível 3 | **Não coberto** — nenhuma migração de hash foi feita neste projeto; reconfirmado nesta verificação (único "audit" no código são anotações `@Audited` do Hibernate/JPA, auditoria de banco, não trilha com hash de integridade) | `insurance-server-lambdas/.../domain/*.java` |
| 11 | Revogação (CRL/OCSP) | Nível 2 | **Não coberto** — não existe verificação de revogação implementada no mock; reconfirmado nesta verificação | Confirmado: as únicas chamadas com "crl" na URL buscam certificado de CA, não lista de revogação |

### Lacunas explícitas, depois desta verificação completa

1. **SAD promete, não implementado**: passos 5 (SSA), 6 (DCR), 10 (trilha de auditoria com
   hash), 11 (revogação CRL/OCSP) — nenhum tocado por v5/v6/v7, sem mudança de status desde
   a versão anterior deste documento.
2. **Genuinamente impossível hoje, não uma lacuna do projeto**: a criptografia (JWE) do
   `id_token`/das respostas de API (passos 7-enc/9-enc) — confirmado nos três perfis, inclusive
   com um `id_token` PQC real cuja assinatura é ML-DSA-65 pura mas cuja cifragem continua
   RSA-OAEP, por ausência de padrão JOSE/COSE pós-quântico.
3. **Estava medido mas sem artefato catalogado — fechado nesta rodada**: o `id_token` (passo
   7) tinha sua assinatura medida em agregado desde a v5, mas nenhuma pasta de artefatos
   continha um exemplo real, decifrado e verificado, até esta verificação — fechado com a Seção
   5 dos três READMEs de `artifacts/`.
4. **Classificação anterior imprecisa — corrigida nesta rodada**: o passo 8 (token de acesso)
   atribuía assinatura híbrida ao `access_token`, que na verdade é opaco; a assinatura real
   pertence ao `client_assertion`, agora capturada e catalogada (Seção 6 dos três READMEs).

### Resumo por nível de urgência

- **Nível 1 (o que o próprio SAD chama de mais urgente, por causa do HNDL)**: **majoritariamente
  coberto desde a v7**, com uma ressalva verificada. A troca de chave TLS (ECDHE→ML-KEM) está
  migrada e medida nos três perfis, para o tráfego cliente↔gateway (que é o que a equação
  OPINsize mede) — a única exceção é uma rota de serviço interno, pré-existente e fora do
  tráfego medido, cuja causa está confirmada e documentada (Decision 6, v7). A criptografia de
  dados/`id_token` (RSA-OAEP/JWE) continua 100% clássica em todos os perfis — confirmado,
  genuinamente impossível de resolver hoje, não por escolha do projeto.
- **Nível 2 (assinaturas)**: continua onde está a maior parte do trabalho, agora com catalogação
  completa. Certificados, `client_assertion`, consentimento/`id_token`, respostas de API — tudo
  migrado, medido, e com prova criptográfica real capturada nos três perfis.
- **Nível 3 (hash das trilhas de auditoria)**: não tocado.

Isso muda a posição da tese em relação à versão anterior deste documento: os Experimentos
1/2/3 + a v7 **não validam mais só o Nível 2** — cobrem a maior parte do Nível 1 também, com
uma exceção pontual, bem compreendida e documentada, e uma segunda parte do Nível 1
(criptografia de payload) que permanece genuinamente fora de alcance do estado da arte atual,
não por limitação deste projeto.

### O trabalho de Nível 1 que restava: como foi resolvido, e o que continua impossível

A avaliação anterior via a troca de chave TLS como "viável, mas cara" — exigindo, na análise de
então, um **quarto perfil separado** ("Híbrido+KEM") para não invalidar a comparação controlada
já escrita, já que trocar a troca de chave de um perfil existente misturaria duas variáveis
(troca de chave *e* assinatura) na mesma medição.

**O que realmente aconteceu na v7 foi diferente e mais simples**: em vez de um quarto perfil, a
v7 (Decision 1) unificou os três perfis existentes sob o mesmo cliente Go (`tls_kem_proxy`),
variando apenas a curva/grupo pedido — Clássico continua puramente ECDHE clássico, PQC passa
a pedir MLKEM1024 puro, Híbrido passa a pedir X25519MLKEM768. Isso preserva exatamente a
comparação controlada que a avaliação anterior queria proteger (cada perfil ainda usa "sua
própria" troca de chave, coerente com sua própria filosofia de assinatura — PQC pura com PQC
pura, híbrida com híbrida), sem precisar de um quarto perfil nem invalidar a v5: a v6 (Nível 1)
mediu esse mesmo aspecto isoladamente antes da fusão, e a v7 então fundiu Nível 1 + Nível 2 no
lote de 360 execuções (180 tamanho + 180 latência) que hoje é a referência.

O impacto na equação OPINsize previsto pela avaliação anterior se confirmou na direção certa,
com a magnitude real medida em vez de estimada: `handshake_bytes` sobe de 5.119 bytes
(Clássico) para 16.605 (PQC) e 18.023 (Híbrido) — bem acima da estimativa de "+2 KB" que a
avaliação anterior calculou a partir dos tamanhos isolados de chave pública/ciphertext do
ML-KEM-768 (a diferença vem de MLKEM1024 ser maior que ML-KEM-768, e de custos de handshake
adicionais como certificados maiores e mais round-trips). `OPINsize`, os totais de tráfego por
participante, e `T_fluxo` mudaram todos na mesma direção prevista, agora com números reais.

**Hash das trilhas de auditoria (SHA-256 → SHA-384): continua nada para migrar.** Reconfirmado
nesta verificação: não existe mecanismo de trilha de auditoria com hash de integridade no
projeto — o único "audit" que aparece são anotações `@Audited` do Hibernate/JPA (auditoria de
banco de dados, não o mecanismo criptográfico que o SAD descreve). Cobrir esse ponto ainda
exigiria primeiro construir a funcionalidade, e só depois decidir sobre o algoritmo de hash — um
passo antes dos outros itens da tabela, não uma simples troca de algoritmo.

---

## Parte 3 — O entendimento do SAD sobre a própria arquitetura, à luz da prática

Além de checar cobertura, vale avaliar se o que o SAD *descreve* sobre como a criptografia
híbrida funciona continua preciso, agora que construímos e medimos o sistema de verdade.

### 3.1. A descrição de "assinatura híbrida" no Capítulo 2 é genérica demais

O SAD (Seção 2.2) descreve assinatura híbrida assim: *"a hybrid signature concatenates the
classical signature... with the post-quantum signature... over the same content"* — ou seja, uma
descrição simples: assina duas vezes e concatena.

Mas construindo o sistema, descobrimos (e documentamos com referências formais) que essa
descrição simples é justamente o esquema **mais fraco** dos que existem — chamado de
concatenação simples, que só garante uma propriedade de segurança mais fraca (EUF-CMA). Por
isso escolhemos deliberadamente um esquema diferente e mais forte para os certificados
(Strong Nesting, onde a segunda assinatura "abraça" a primeira, garantindo uma propriedade
mais forte, SUF-CMA) — e depois, para os JWTs assinados pelo cliente, encontramos um
terceiro esquema ainda diferente (extensão por payload), escolhido deliberadamente para
priorizar compatibilidade com verificadores antigos, aceitando abrir mão de parte dessa
segurança extra de propósito.

Isso não é um erro no SAD — é natural que o Capítulo 2 (fundamentação teórica) seja mais
genérico, porque o desenho formal e detalhado do protocolo híbrido é justamente o objetivo
específico **SO4** do próprio cronograma do SAD, planejado só para 2027. O ponto é que **o
trabalho prático já está à frente dessa parte do SAD** — já temos o desenho formal, testado e
funcionando, pronto para alimentar diretamente essa seção quando ela for escrita.

### 3.2. A metodologia de validação experimental (Seção 3.4) não bate com o que foi feito

O SAD descreve um plano de validação específico:
- **Ferramentas**: implementações de referência do NIST, integradas com OpenSSL e liboqs.
- **Fluxos a testar**: handshake TLS com ECDHE+ML-KEM, emissão/verificação de JWT e SSA
  com PS256+ML-DSA, e DCR sobre um canal mTLS híbrido.

O que realmente construímos usa outras ferramentas (a biblioteca padrão do Go, `crypto/mldsa`,
e BouncyCastle em Java — nada de OpenSSL/liboqs) e cobre fluxos diferentes: assinatura de
certificados e de JWTs, sim — mas **não** SSA, **não** DCR, e **não** o handshake TLS com
ML-KEM (pelo motivo já explicado na Parte 2).

Por outro lado, as **três dimensões de métrica** que o SAD propõe — latência, tamanho de
artefato, e compatibilidade com verificadores antigos — foram cobertas com muito mais rigor do
que o texto atual do SAD sugere: 180 execuções de latência, 180 de tamanho, e testes de
compatibilidade retroativa (um verificador RS256 genérico aceitando os tokens híbridos sem
nenhuma adaptação). Vale atualizar essa seção do SAD para refletir o que de fato foi validado,
com que ferramentas, e deixar claro que SSA/DCR/TLS+ML-KEM continuam como trabalho futuro
dentro do próprio SO6.

---

## Resumo executivo

1. **Os diagramas do SAD estão majoritariamente corretos**, com dois ajustes pontuais: o
   rótulo do passo 4a deveria separar autenticidade de confidencialidade, e os passos 7/8
   deveriam listar a dependência de RSA-OAEP que hoje só aparece no passo 9.
2. **O trabalho prático (Experimentos 1/2/3 + v7) cobre bem o Nível 2 do próprio framework do
   SAD** (assinaturas — certificados, `client_assertion`, consentimento/`id_token`, respostas de
   API) **e, desde a v7, cobre também a maior parte do Nível 1** (a troca de chave TLS
   ECDHE→ML-KEM está migrada, medida e catalogada com prova real nos três perfis, com uma
   exceção pontual e bem documentada — uma rota de serviço interno pré-existente, fora do
   tráfego medido). A outra metade do Nível 1 (criptografia de dados via JWE/RSA-OAEP) e o
   Nível 3 (hash das trilhas de auditoria) continuam fora de escopo.
3. **Uma parte do Nível 1 é genuinamente impossível de resolver agora** — a criptografia do
   `id_token`/dados via RSA-OAEP não tem alternativa pós-quântica disponível na biblioteca
   usada, porque nem existe ainda um padrão JOSE/COSE para ML-KEM. Confirmado nos três
   perfis, incluindo um `id_token` PQC real cuja assinatura é ML-DSA-65 pura por dentro de uma
   cifragem RSA-OAEP inalterada — evidência concreta, não só teórica. Isso é um achado forte,
   não uma lacuna do projeto.
4. **A descrição teórica de assinatura híbrida no Capítulo 2 do SAD é mais simples do que o que
   foi construído na prática** — o trabalho real já resolveu, testou e documentou formalmente a
   escolha entre os esquemas (Strong Nesting vs. concatenação simples vs. extensão por
   payload), o que está à frente do cronograma do próprio SAD (SO4, planejado para 2027).
5. **A seção de metodologia experimental do SAD (3.4) descreve ferramentas e fluxos diferentes
   dos que foram realmente usados** — vale atualizar para refletir o que já foi validado (e com
   qual rigor) antes da apresentação do SAD.
6. **A classificação do passo 8 (token de acesso) estava imprecisa e foi corrigida**: o
   `access_token` em si é opaco, sem assinatura nenhuma; a assinatura híbrida/PQC real vive no
   `client_assertion` que o cliente usa para se autenticar ao pedir o token — agora capturado e
   verificado nos três perfis (`artifacts/*/README.md`, Seção 6).
