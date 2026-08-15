Métricas Experimentais — Resultados Comparativos

Experimento 1 (Clássico) versus Experimento 2 (PQC)

Luciano Figueiredo Coelho   |   PPGCC/LabSEC/UFSC

1. Objetivo

Este documento apresenta os resultados comparativos dos Experimentos 1 e 2 da tese, organizados pelas métricas definidas em conjunto na última reunião de orientação. O Experimento 1 mediu o custo do fluxo de consentimento OPIN com criptografia clássica (PS256/RSA). O Experimento 2 mediu o mesmo fluxo com criptografia pós-quântica pura (ML-DSA-65), substituindo completamente os algoritmos clássicos. A comparação entre os dois experimentos estabelece os dois pontos de referência para o Experimento 3 (híbrido), que é a contribuição central da tese.

Os três blocos abaixo organizam as métricas por dimensão de análise: custo de tráfego em bytes, custo de latência por endpoint e parâmetros da Equação OPINsize. Um quarto bloco apresenta as estimativas para o Experimento 3 com base nos resultados 
obtidos.

2. Bloco A — Custo de Tráfego

As métricas de tráfego medem o tamanho dos dados que circulam no fluxo de consentimento completo. São os parâmetros que entram diretamente na Equação OPINsize e que determinam o impacto da migração no custo de infraestrutura de nuvem dos participantes do ecossistema.

Este documento apresenta dois números diferentes chamados de "OPINsize", e é importante não confundi-los: o OPINsize analítico (151.120 bytes clássico / 264.374 bytes PQC, crescimento 1,75x, Bloco C) e o OPINsize empírico por participante (~67.604 bytes clássico / ~178.028 bytes PQC, crescimento 2,63x, tabela abaixo). Os dois coexistem porque respondem perguntas diferentes e complementares, não porque um deles esteja errado.

O OPINsize analítico inclui o custo do handshake mTLS, calculado via equação (Equação 3.1 de Schardong et al., 2022). É o número comparável com a literatura e responde à pergunta central da tese: quanto custa um consentimento OPIN completo de ponta a ponta?

O OPINsize empírico por participante mede apenas os bytes que trafegam na camada de aplicação HTTP — depois que o túnel TLS já está estabelecido. É a soma do que cada participante (AS, RS, PKI/CRL, Directory) efetivamente movimentou. Responde à pergunta operacional do orientador: quanto vai para a conta de nuvem de cada participante do ecossistema?

A soma dos participantes fecha com o valor empírico, não com o analítico, porque os participantes só enxergam a camada de aplicação — o handshake mTLS acontece numa camada abaixo, invisível para eles.

3. Bloco B — Custo de Latência

O Bloco A mostrou que o fluxo fica 2,63 vezes mais pesado em bytes com PQC. Mas bytes maiores não significam necessariamente uma aplicação mais lenta — isso depende de quanto tempo o servidor gasta processando cada operação criptográfica.

O Bloco B responde a essa segunda pergunta: além de mais pesado, o fluxo também fica mais lento? E quanto mais lento em cada ponto específico do fluxo?

Para responder com precisão, todas as medições deste bloco foram feitas no cenário de rede zero — todos os serviços rodando na mesma máquina sem atraso artificial de rede. Qualquer diferença de tempo entre os dois experimentos nesse cenário é atribuível exclusivamente ao algoritmo criptográfico, não à velocidade da rede. O P50 foi usado como referência por representar o comportamento mediano do sistema.

A combinação dos dois blocos — mais pesado e mais lento — é o argumento empírico completo de que a migração PQC tem custo real e mensurável em duas dimensões independentes: infraestrutura de rede e capacidade de processamento. Isso é o que fundamenta a proposta do esquema híbrido como solução de transição gradual — permitir que cada participante migre no ritmo que sua infraestrutura comporta.

A latência escala proporcionalmente com a rede em todos os cenários (0ms, 14ms, 30ms, 140ms, 225ms, 320ms) para os dois experimentos — a diferença absoluta de processamento entre clássico e PQC passa a ser estatisticamente indistinguível do ruído de rede em cenários de alta latência, dado o número limitado de amostras por cenário (n=4 para o /token). Em cenários de alta latência (320ms), o overhead computacional do PQC é diluído pela latência de transmissão e torna-se proporcionalmente menor.

4. Bloco C — Parâmetros da Equação OPINsize

A Equação OPINsize desta tese (equivalente à Equação 3.1 de Schardong et al., 2022) calcula o custo total analítico do fluxo como função dos seus parâmetros mensuráveis. A tabela abaixo apresenta os valores empíricos de cada parâmetro nos dois experimentos.

Com os parâmetros reais do Experimento 1 (usando a média do handshake P50 de 14ms–320ms = 10.418 bytes e N_mTLS médio de 11 conexões, média dos 6 cenários): OPINsize clássico = 11 × 10.418 + 26 × 1.385 + 2 × 256 = 114.598 + 36.010 + 512 = 151.120 bytes.

Com os parâmetros reais do Experimento 2 (N_mTLS constante de 6 conexões em todos os cenários): OPINsize PQC = 6 × 19.756 + 26 × 5.459 + 2 × 1.952 = 118.536 + 141.934 + 3.904 = 264.374 bytes.

Crescimento analítico: 264.374 / 151.120 = 1,75x. Este é o overhead da migração PQC pura medido pela equação analítica, usando os parâmetros empíricos dos experimentos.

5. Estimativas para o Experimento 3 — Híbrido

O Experimento 3 implementa o esquema híbrido proposto no SAD: PS256 e ML-DSA-65 rodando em paralelo no mesmo fluxo, com os dois algoritmos coexistindo simultaneamente. Este é o cenário de transição real que a tese propõe para o período de migração do ecossistema OPIN.

Nota: os valores do Experimento 3 são estimativas calculadas com base nos resultados dos Experimentos 1 e 2. Os valores reais serão medidos e substituirão estas estimativas após a execução do experimento.

6. Notas Metodológicas

Os Experimentos 1 e 2 foram executados com o mesmo script de automação (opin_flow.py), cobrindo 28 chamadas HTTP nos dois planos de teste (consents_v3 e person_v2) em 6 cenários de latência cada (0ms, 14ms, 30ms, 140ms, 225ms e 320ms via tc/netem no container gateway). Todos os módulos terminaram com resultado PASSED nos 12 cenários.

As métricas de handshake mTLS foram filtradas por client_cert_bytes para isolar o tráfego do script de automação do tráfego interno do Servidor de Autorização, que usa um certificado de transporte separado e sempre clássico.

Os módulos de preflight foram excluídos por sempre terminarem com resultado FAILED devido à dependência do Directory real da Raidiam, indisponível em ambiente local.

O Resource Server (Servidor de Dados) lê CRYPTO_PROFILE apenas no boot — toda troca de perfil entre experimentos exigiu recriar os containers auth, mtls, mongo_seed e mockapi simultaneamente para garantir sincronização completa do ambiente. Isso está documentado em thesis/results/v3/DECISIONS.md.

| Métrica | Clássico (Exp 1) | PQC Puro (Exp 2) | Crescimento | O que isso significa |
|---|---|---|---|---|
| OPINsize total (bytes) | ~67.604 | ~178.028 | 2,63x | O fluxo completo de consentimento OPIN fica 2,63 vezes mais pesado com PQC puro. Este é o custo da substituição completa dos algoritmos clássicos por ML-DSA-65. Estima-se que o Experimento 3 (híbrido) supere este valor — ao rodar PS256 e ML-DSA-65 em paralelo, cada JWT acumularia as duas assinaturas simultaneamente, tornando o fluxo híbrido potencialmente mais pesado que o PQC puro. O experimento confirmará ou corrigirá essa estimativa. |
| Handshake mTLS — P50 (bytes) | 10.381 | 19.756 | +90% | Antes de qualquer troca de dados, os participantes precisam estabelecer uma conexão segura. Esse processo de autenticação custa 90% mais em bytes com PQC — o cliente e o servidor (gateway) apresentam certificados ML-DSA-65, cada um contribuindo com uma assinatura maior que a RSA equivalente. O certificado digital que o cliente apresenta para se identificar cresceu de 1.494 bytes (clássico) para 2.953 bytes (ML-DSA-65). Apesar do handshake maior em bytes, ele fica mais rápido em tempo — ver nota após a tabela de latência por endpoint (Bloco B). |
| JWT médio (bytes) | 1.385 | 5.459 | 3,94x | Todo token de segurança que circula no fluxo tem três partes: o cabeçalho (identifica o algoritmo), o payload (dados como identificador do consentimento, permissões e validade) e a assinatura digital. Com a migração para ML-DSA-65, apenas a assinatura muda — de 342 bytes (RSA-2048, chaves do Servidor de Autorização e do Servidor de Dados) para 4.412 bytes (ML-DSA-65). O cabeçalho e o payload ficam praticamente iguais. O resultado é que o token completo cresce de 1.385 para 5.459 bytes — 3,94 vezes maior. |
| Bytes do Servidor de Autorização — AS (Authorization Server) | 26.063 | 71.270 | 2,73x | O Servidor de Autorização cresce 2,73x — todos os tokens que ele emite passam a usar ML-DSA-65. O crescimento reflete a migração completa dos tokens de autorização do fluxo para o novo algoritmo. |
| Bytes do Servidor de Dados — RS (Resource Server) | 30.873 | 96.091 | 3,11x | O Servidor de Dados é o participante mais impactado em volume absoluto — cresce 3,11x e acumula +65.218 bytes adicionais. As APIs Consents e Person são chamadas múltiplas vezes no fluxo e todas as respostas passam a ser assinadas com ML-DSA-65, acumulando o overhead a cada chamada. |
| Bytes PKI/CRL | 10.668 | 10.668 | Estável | Os certificados da Autoridade Certificadora não foram migrados para PQC. O valor é praticamente idêntico nos dois experimentos (média 10.668 bytes em ambos), dentro do ruído de medição de ±6 bytes presente igualmente nos dois perfis. Confirma que a variação dos outros participantes é atribuível exclusivamente ao algoritmo criptográfico. |

| Endpoint | Clássico P50 (0ms rede) | PQC P50 (0ms rede) | Overhead computacional | O que isso significa |
|---|---|---|---|---|
| /token (POST) | 21,25ms | 68,54ms | +47,29ms (+223%) | O /token é o endpoint onde o cliente prova sua identidade para o servidor. Para fazer isso, ele cria um token especial chamado client assertion. O servidor recebe esse token, verifica a assinatura e, se tudo estiver certo, devolve o token de acesso. Com PS256, criar e verificar essa assinatura leva cerca de 21ms. Com ML-DSA-65, o mesmo processo leva 69ms. A diferença de 47ms é o tempo extra que o algoritmo pós-quântico consome. |
| /open-insurance/consents/v3/consents (POST) | 54,47ms | 141,43ms | +86,96ms (+160%) | Quando o script cria um consentimento fazendo um POST para /consents, o Servidor de Dados precisa responder confirmando que o consentimento foi criado. Com PQC, essa resposta vem assinada com ML-DSA-65 — o servidor gasta tempo calculando a assinatura, e depois ainda precisa transmitir um JWT maior do que antes. Com PS256 isso leva 54ms. Com ML-DSA-65 leva 141ms. **Nota de fragilidade estatística:** este endpoint tem apenas n=2 amostras por cenário (uma chamada por fluxo), então o P50 é sensível a jitter pontual de infraestrutura — o valor oscilou bastante entre reruns do mesmo cenário 0ms nesta sessão (chegou a 65,86ms e a 1.557ms em medições anteriores, antes deste valor definitivo). |
| /open-insurance/consents/v3/consents (GET) | 17,69ms | 35,10ms | +17,41ms (+98%) | Após criar o consentimento, o script consulta o status dele várias vezes para verificar se está em AWAITING_AUTHORISATION e depois em AUTHORISED. Cada consulta é um GET no mesmo endpoint /consents/{id}. Com PS256 essa consulta leva 17,69ms. Com ML-DSA-65 leva 35,10ms. **Nota de fragilidade estatística:** este agregado tem apenas 6 amostras no total (5 de um consentimento + 1 de outro), dominado por poucas chamadas de rede; o valor já oscilou entre 16,24ms e 39,73ms em medições anteriores do mesmo cenário 0ms nesta sessão, inclusive invertendo de sinal (PQC mais rápido que clássico) numa delas. Este é o valor da rodada definitiva, com ambiente completamente recriado. |
| /open-insurance/insurance-person/v2/... | ~27,40ms | ~45,65ms | +18,25ms (+67%) | O fluxo person chama quatro APIs de dados pessoais — insurance-person, claim, policy-info e premium — cada uma retornando dados reais de apólice, sinistro e prêmio do segurado. Com PQC, cada resposta é assinada com ML-DSA-65. Com PS256 a média de resposta entre os quatro endpoints é 27,40ms. Com ML-DSA-65 é 45,65ms. O overhead médio entre os quatro endpoints é de ~18ms, mas varia — de +13,64ms no policy-info até +26,61ms no insurance-person — refletindo diferenças no tamanho e complexidade de cada payload de resposta, além de ruído estatístico (n=2 por endpoint). |
| /jwks (GET) | 39,64ms | 46,07ms | +6,43ms (+16%) | O endpoint /jwks é onde o cliente busca a chave pública do servidor para verificar os tokens que recebe. É uma operação simples de leitura — o servidor não faz cálculo criptográfico, só devolve a chave pública armazenada. **Nota de fragilidade estatística:** apenas n=2 amostras no fluxo inteiro — o valor já oscilou entre 30,78ms e 49,99ms em medições anteriores do mesmo cenário 0ms nesta sessão, inclusive invertendo de sinal numa delas (PQC mais rápido que clássico). O que não muda entre reruns é o tamanho da resposta: a chave pública RSA-2048 tem 256 bytes, enquanto a chave ML-DSA-65 tem 1.952 bytes (valor da especificação FIPS 204 — limitação metodológica: o parser de JWK do pipeline não reconhece o tipo AKP e essa chave não aparece nos resultados medidos diretamente). |

**Nota — handshake mTLS maior em bytes, mas mais rápido em tempo:** o handshake mTLS ficou maior em bytes (+27%, de 15.500 para 19.756 bytes) mas mais rápido em tempo (~18-25ms → 7-9ms) após a migração do certificado do gateway de RSA-4096 para ML-DSA-65. Isso ocorre porque RSA-4096 é ~9,3x mais lento que ML-DSA-65 para a operação de assinatura durante o handshake TLS (CertificateVerify). Tamanho de assinatura e custo computacional de assinar são dimensões independentes — ML-DSA-65 produz assinaturas maiores mas as calcula muito mais rapidamente que RSA-4096.

| Parâmetro | Clássico (Exp 1) | PQC Puro (Exp 2) | Crescimento | O que isso significa para a equação OPINsize |
|---|---|---|---|---|
| N_mTLS — número de handshakes distintos | ~9 a 16 (média ≈ 11) | 6 (constante em todos os cenários) | Estável | O número de conexões não muda com o algoritmo — só o custo de cada uma. A variação entre cenários no clássico reflete o comportamento de conexão do script Python (reutilização de sessão TLS); no PQC o valor é perfeitamente constante. |
| mTLS_handshake_bytes — tamanho do handshake P50 | 10.381 a 10.511 bytes (média ≈ 10.418 bytes, cenários 14ms–320ms) | 19.756 bytes (todos cenários) | +90% | Parâmetro que cresce com os certificados ML-DSA-65 do cliente e do gateway (Experimento 2 completo — ver nota no Bloco B). Perfeitamente estável no PQC — evidência de que o tamanho do handshake é determinístico para esse algoritmo. Maior em bytes, porém mais rápido em tempo: ver nota logo após a tabela de latência por endpoint. |
| N_JWT — número de tokens no fluxo | 26 | 26 | Estável | O número de tokens não muda com o algoritmo — só o tamanho de cada um. Parâmetro fixo da equação nos dois experimentos. |
| JWT_size — tamanho médio de JWT | 1.385 bytes | 5.459 bytes | 3,94x | Parâmetro mais impactado — dominado pelo crescimento da assinatura. Contribui para o aumento do OPINsize analítico na proporção N_JWT × crescimento. |
| JWK_PK_size — tamanho da chave pública do AS | 256 bytes (RSA-2048) | 1.952 bytes (ML-DSA-65) | 7,63x | A chave pública publicada no JWKS do Servidor de Autorização cresce 7,63 vezes. Reflete o tamanho estruturalmente maior das chaves ML-DSA-65 definido pelo padrão FIPS 204. |
| N_JWK — número de chamadas ao /jwks | 2 | 2 | Estável | O número de consultas ao endpoint de chaves públicas não muda com o algoritmo. |

| Métrica | Clássico (Exp 1) | PQC Puro (Exp 2) | Estimativa Exp 3 (Híbrido) | Justificativa |
|---|---|---|---|---|
| OPINsize total (bytes) | ~67.604 | ~178.028 | Estimado acima de ~178.028 | No híbrido cada JWT carrega PS256 e ML-DSA-65 simultaneamente. O OPINsize deve superar o PQC puro pelo acréscimo das assinaturas PS256 adicionais. |
| JWT médio (bytes) | 1.385 | 5.459 | Estimado acima de 5.459 | Cada JWT carregará duas assinaturas — ML-DSA-65 (~4.412 bytes b64url) e PS256 (~342 bytes b64url, RSA-2048, que representa a maioria dos JWTs do fluxo). O crescimento adicional sobre o PQC puro é da ordem de 342 bytes por JWT. |
| Handshake mTLS P50 (bytes) | 10.381 | 19.756 | Estimado próximo ou acima de 19.756 | O certificado híbrido carregará as duas assinaturas. O handshake deve ser similar ao PQC puro ou ligeiramente maior. |
| Overhead /token (0ms rede) | 21,25ms (ref.) | 68,54ms (+47,29ms) | Estimado acima de 68,54ms | O servidor precisará verificar duas assinaturas por JWT. O overhead computacional deve ser maior que o PQC puro, que verifica uma assinatura maior, versus o híbrido que verifica duas. |

