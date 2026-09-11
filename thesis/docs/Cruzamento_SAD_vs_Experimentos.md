# Cruzamento: o que o SAD propõe vs. o que os Experimentos já cobrem

Este documento responde a duas perguntas: (1) os diagramas de fluxo de segurança do SAD
estão corretos, à luz do que aprendemos construindo o sistema de verdade? (2) do que o SAD
propõe, o que os Experimentos 1/2/3 já cobrem, o que ainda falta, e o que é impossível de fazer
agora por alguma limitação técnica real (não por falta de tempo)?

Tudo aqui foi checado direto no código-fonte e nos dados da v5 — não é opinião nem
suposição. Onde alguma coisa não pôde ser confirmada com certeza, isso está marcado
explicitamente.

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

A tabela abaixo cruza os 11 passos do SAD contra o que os Experimentos 1/2/3 (Clássico/PQC/
Híbrido) realmente construíram e mediram.

| # | Passo do SAD | Nível de urgência (SAD) | Status nos Experimentos | Evidência |
|---|---|---|---|---|
| 1 | Onboarding regulatório | — (sem criptografia) | Fora de escopo (não envolve criptografia, é processo administrativo) | — |
| 2 | Registro no Diretório | — (sem criptografia) | Fora de escopo (idem) | — |
| 3 | Emissão de certificado ICP-Brasil | Nível 2 | **Coberto** — certificados híbridos gerados e medidos (Clássico/PQC/Híbrido) | `certs/main.go`, Seção 7 do documento de arquitetura v5 |
| 4a | BRCAC (parte RSA — identidade) | Nível 2 | **Coberto** — mesma cadeia de certificados híbridos acima | idem |
| 4a | BRCAC (parte ECDHE — troca de chave da sessão TLS) | **Nível 1** (o mais urgente) | **Não coberto** — nenhum perfil usa um grupo de troca de chave híbrido; é sempre clássico puro | `mock_mtls/main.go`, `CurvePreferences` só com curvas clássicas (P-521/P-384/P-256) |
| 4b | BRSEAL (certificado de assinatura) | Nível 2 | **Coberto** — mesmo mecanismo de certificado híbrido | idem passo 3 |
| 5 | SSA (credencial de aplicação emitida pelo Diretório) | Nível 2 | **Não coberto** — o fluxo simulado usa um cliente já pré-cadastrado, nunca busca uma SSA | `opin_flow.py`: "No SSA fetch in either flow... client_one is a statically pre-registered client" |
| 6 | DCR (registro dinâmico de cliente) | Nível 2 (+ Nível 1 pela parte ECDHE) | **Não coberto** — mesma razão do passo 5 | idem |
| 7 | Consentimento (OIDC) — assinatura | Nível 2 | **Coberto** — Strong Nesting no `id_token`, medido e verificado | Seção 5.6 do documento de arquitetura v5 |
| 7 | Consentimento (OIDC) — criptografia do `id_token` (RSA-OAEP) | **Nível 1** | **Impossível migrar hoje** — sem suporte da biblioteca `jose`, sem padrão JOSE/COSE para ML-KEM | `configuration.js`: comentário explícito no código citando a retirada do rascunho no IETF |
| 8 | Token de acesso (FAPI) | Nível 2 | **Coberto** — assinatura híbrida, medida | Tabela final v5 |
| 9 | Troca de dados via API — assinatura das respostas | Nível 2 | **Coberto** — extensão por payload / Strong Nesting conforme o artefato | Seção 5 do documento de arquitetura v5 |
| 9 | Troca de dados via API — confidencialidade (RSA-OAEP + ECDHE) | **Nível 1** | **Não coberto** — mesma limitação dos itens acima | idem 4a/7 |
| 10 | Trilhas de auditoria (SHA-256) | Nível 3 | **Não coberto** — nenhuma migração de hash foi feita neste projeto | — |
| 11 | Revogação (CRL/OCSP) | Nível 2 | **Não coberto** — não existe verificação de revogação implementada no mock | Confirmado: as únicas chamadas com "crl" na URL buscam certificado de CA, não lista de revogação |

### Resumo por nível de urgência

- **Nível 1 (o que o próprio SAD chama de mais urgente, por causa do HNDL)**: **quase nada
  coberto**. A troca de chave do TLS (ECDHE) continua 100% clássica em todos os perfis, e a
  criptografia de dados (RSA-OAEP/JWE) também — sendo que essa segunda parte é
  genuinamente impossível de resolver agora, não por escolha nossa.
- **Nível 2 (assinaturas)**: **é onde está praticamente todo o trabalho já feito**. Certificados,
  tokens de acesso, consentimento, id_token — tudo isso foi migrado, medido, e validado nos
  três perfis, com 360 execuções completas (180 de tamanho + 180 de latência).
- **Nível 3 (hash das trilhas de auditoria)**: não tocado.

Isso não é um problema — é uma informação importante para posicionar a tese com precisão: **os
Experimentos 1/2/3 validam, na prática, exatamente a categoria que o SAD chama de Nível 2**, e
ainda não tocam nas categorias 1 e 3. Isso é uma escolha de escopo perfeitamente razoável
(assinatura é o ponto de partida mais natural), mas o texto da tese deveria deixar isso explícito,
em vez de dar a impressão de que "o protótipo valida o framework" de forma genérica.

### O que falta no Nível 1 e no Nível 3 é viável de implementar?

O Nível 1 não é uma coisa só — tem duas partes com viabilidades bem diferentes. E o Nível 3, ao
ser investigado, revelou que nem existe ainda o que migrar.

**Troca de chave TLS (ECDHE → ML-KEM híbrido): viável.** Diferente da criptografia do
`id_token` (que é genuinamente impossível hoje), essa parte não esbarra em nenhum padrão em
falta. O Go, desde a versão 1.23, já suporta nativamente um grupo de troca de chave híbrido para
TLS 1.3 (`X25519MLKEM768`) na própria biblioteca padrão — nada de biblioteca externa, nada de
rascunho de padrão pendente. Hoje o `mock_mtls/main.go` só configura curvas clássicas
(`CurvePreferences: []tls.CurveID{tls.CurveP521, tls.CurveP384, tls.CurveP256}`). Trocar isso por
um grupo híbrido é uma mudança de configuração, não uma barreira de padrão em aberto.

Mas viável não quer dizer barato de encaixar na v5 que já existe. A métrica
`mTLS_handshake_bytes` é um dos três termos da própria equação OPINsize
(`OPINsize = N_mTLS × handshake_bytes + N_JWT × JWT_médio + N_JWK × JWK_PK_size`).
Trocar a troca de chave clássica (ECDHE, ~32-66 bytes de chave efêmera) por uma híbrida com
ML-KEM-768 adiciona ao handshake uma chave pública de **1.184 bytes** e um ciphertext de
**1.088 bytes** — mais de 2 KB extras por handshake, repetidos a cada um dos 6 handshakes do
fluxo (`N_mTLS = 6`). Isso cascateia para quase toda métrica já reportada e aprovada na v5:
`mTLS_handshake_bytes` muda diretamente; `OPINsize` muda, porque handshake é um dos três
termos da fórmula; os totais de tráfego do AS, do RS e do cliente mudam, porque são soma de
tudo que trafegou, handshake incluso; e `T_fluxo` (latência) muda também, porque mais bytes
trafegando em cada um dos 6 handshakes tem custo de transmissão, especialmente nos cenários
de latência mais alta.

O motivo é metodológico: a v5 atual foi desenhada como uma comparação limpa, em que os três
perfis (Clássico/PQC/Híbrido) usam **a mesma troca de chave clássica**, variando só a
assinatura — isso é o que isola exatamente a variável que os experimentos se propõem a medir
(Nível 2). Adicionar ML-KEM só ao perfil Híbrido faria esse perfil deixar de ser "mesma troca de
chave, assinatura diferente" e virar "troca de chave *e* assinatura diferentes ao mesmo tempo",
quebrando a comparação controlada já escrita, aprovada e sabatinada. Isso não invalida os
dados atuais — eles continuam corretos como medição do esquema híbrido *de assinatura*, que é
exatamente o que Nível 2 significa. Mas cobrir Nível 1 de forma limpa exige um **quarto perfil
separado** ("Híbrido+KEM", por exemplo), com seu próprio lote completo de execuções, do
mesmo jeito rigoroso que os três perfis atuais — não dá para só trocar a configuração do perfil
Híbrido existente sem invalidar a tabela e o relatório de latência já escritos.

**Hash das trilhas de auditoria (SHA-256 → SHA-384): nada para migrar ainda.** Ao procurar por
algum mecanismo de trilha de auditoria (log imutável com hash de integridade, que é o que o
passo 10 do SAD descreve) em todo o projeto, o único "audit" que aparece no código são
anotações `@Audited` do Hibernate/JPA nas entidades do seguro
(`insurance-server-lambdas/.../domain/*.java`) — isso é auditoria de banco de dados (quem criou
ou alterou um registro e quando), não o mecanismo de integridade criptográfica que o SAD está
descrevendo. SHA-256 hoje só aparece como parte interna do PS256 (a assinatura RSA-PSS usa
SHA-256 como função de hash), não como um mecanismo separado de proteção de log.

Ou seja: esse item não é "impossível de migrar" — é que **a funcionalidade em si ainda não
existe** no protótipo. Cobrir esse ponto exigiria primeiro construir um mecanismo de trilha de
auditoria com hash, e só depois decidir sobre migrar esse hash para SHA-384. É um passo antes
dos outros itens da tabela, não uma simples troca de algoritmo.

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
2. **O trabalho prático (Experimentos 1/2/3) cobre bem o Nível 2 do próprio framework do SAD**
   (assinaturas — certificados, tokens, consentimento) e **ainda não toca o Nível 1** (troca de
   chave TLS e criptografia de dados) **nem o Nível 3** (hash das trilhas de auditoria).
3. **Uma parte do Nível 1 é genuinamente impossível de resolver agora** — a criptografia do
   `id_token`/dados via RSA-OAEP não tem alternativa pós-quântica disponível na biblioteca
   usada, porque nem existe ainda um padrão JOSE/COSE para ML-KEM. Isso é um achado forte,
   não uma lacuna do projeto.
4. **A descrição teórica de assinatura híbrida no Capítulo 2 do SAD é mais simples do que o que
   foi construído na prática** — o trabalho real já resolveu, testou e documentou formalmente a
   escolha entre os esquemas (Strong Nesting vs. concatenação simples vs. extensão por
   payload), o que está à frente do cronograma do próprio SAD (SO4, planejado para 2027).
5. **A seção de metodologia experimental do SAD (3.4) descreve ferramentas e fluxos diferentes
   dos que foram realmente usados** — vale atualizar para refletir o que já foi validado (e com
   qual rigor) antes da apresentação do SAD.
