Métricas Experimentais — Resultados Comparativos

Experimento 1 (Clássico) versus Experimento 2 (PQC)

Luciano Figueiredo Coelho   |   PPGCC/LabSEC/UFSC

1. Objetivo

Este documento apresenta os resultados comparativos dos Experimentos 1 e 2 da tese, organizados pelas métricas definidas em conjunto na última reunião de orientação. O Experimento 1 mediu o custo do fluxo de consentimento OPIN com criptografia clássica (PS256/RSA). O Experimento 2 mediu o mesmo fluxo com criptografia pós-quântica pura (ML-DSA-65), substituindo completamente os algoritmos clássicos. A comparação entre os dois experimentos estabelece os dois pontos de referência para o Experimento 3 (híbrido), que é a contribuição central da tese.

Os três blocos abaixo organizam as métricas por dimensão de análise: custo de tráfego em bytes, custo de latência por endpoint e parâmetros da Equação OPINsize. Um quarto bloco apresenta as estimativas para o Experimento 3 com base nos resultados obtidos.

2. Bloco A — Custo de Tráfego

As métricas de tráfego medem o tamanho dos dados que circulam no fluxo de consentimento completo. São os parâmetros que entram diretamente na Equação OPINsize e que determinam o impacto da migração no custo de infraestrutura de nuvem dos participantes do ecossistema.

Este documento apresenta dois números diferentes chamados de "OPINsize", e é importante não confundi-los: o OPINsize analítico (151.120 bytes clássico / 238.838 bytes PQC, crescimento 1,58x, Bloco C) e o OPINsize empírico por participante (~67.604 bytes clássico / ~178.029 bytes PQC, crescimento 2,63x, tabela abaixo). Os dois coexistem porque respondem perguntas diferentes e complementares, não porque um deles esteja errado.

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

Com os parâmetros reais do Experimento 2 (N_mTLS constante de 6 conexões em todos os cenários): OPINsize PQC = 6 × 15.500 + 26 × 5.459 + 2 × 1.952 = 93.000 + 141.934 + 3.904 = 238.838 bytes.

Crescimento analítico: 238.838 / 151.120 = 1,58x. Este é o overhead da migração PQC pura medido pela equação analítica, usando os parâmetros empíricos dos experimentos.

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
| OPINsize total (bytes) | ~67.604 | ~178.029 | 2,63x | O fluxo completo de consentimento OPIN fica 2,63 vezes mais pesado com PQC puro. Este é o custo da substituição completa dos algoritmos clássicos por ML-DSA-65. Estima-se que o Experimento 3 (híbrido) supere este valor — ao rodar PS256 e ML-DSA-65 em paralelo, cada JWT acumularia as duas assinaturas simultaneamente, tornando o fluxo híbrido potencialmente mais pesado que o PQC puro. O experimento confirmará ou corrigirá essa estimativa. |
| Handshake mTLS — P50 (bytes) | 10.381 | 15.500 | +49% | Antes de qualquer troca de dados, os participantes precisam estabelecer uma conexão segura. Esse processo de autenticação custa 49% mais com PQC. A razão é direta: o certificado digital que o cliente apresenta para se identificar cresceu de 1.494 bytes (clássico) para 2.953 bytes (ML-DSA-65), quase dobrando de tamanho, mais o material adicional de chave no handshake. |
| JWT médio (bytes) | 1.385 | 5.459 | 3,94x | Todo token de segurança que circula no fluxo tem três partes: o cabeçalho (identifica o algoritmo), o payload (dados como identificador do consentimento, permissões e validade) e a assinatura digital. Com a migração para ML-DSA-65, apenas a assinatura muda — de 342 bytes (RSA-2048, chaves do Servidor de Autorização e do Servidor de Dados) para 4.412 bytes (ML-DSA-65). O cabeçalho e o payload ficam praticamente iguais. O resultado é que o token completo cresce de 1.385 para 5.459 bytes — 3,94 vezes maior. |
| Bytes do Servidor de Autorização — AS (Authorization Server) | 26.063 | 71.270 | 2,73x | O Servidor de Autorização cresce 2,73x — todos os tokens que ele emite passam a usar ML-DSA-65. O crescimento reflete a migração completa dos tokens de autorização do fluxo para o novo algoritmo. |
| Bytes do Servidor de Dados — RS (Resource Server) | 30.873 | 96.091 | 3,11x | O Servidor de Dados é o participante mais impactado em volume absoluto — cresce 3,11x e acumula +65.218 bytes adicionais. As APIs Consents e Person são chamadas múltiplas vezes no fluxo e todas as respostas passam a ser assinadas com ML-DSA-65, acumulando o overhead a cada chamada. |
| Bytes PKI/CRL | 10.668 | 10.668 | Estável | Os certificados da Autoridade Certificadora não foram migrados para PQC. O valor é praticamente idêntico nos dois experimentos (média 10.668 bytes em ambos), dentro do ruído de medição de ±6 bytes presente igualmente nos dois perfis. Confirma que a variação dos outros participantes é atribuível exclusivamente ao algoritmo criptográfico. |

| Endpoint | Clássico P50 (0ms rede) | PQC P50 (0ms rede) | Overhead computacional | O que isso significa |
|---|---|---|---|---|
| /token (POST) | 21,25ms | 66,5ms | +45,25ms (+213%) | O /token é o endpoint onde o cliente prova sua identidade para o servidor. Para fazer isso, ele cria um token especial chamado client assertion. O servidor recebe esse token, verifica a assinatura e, se tudo estiver certo, devolve o token de acesso. Com PS256, criar e verificar essa assinatura leva cerca de 21ms. Com ML-DSA-65, o mesmo processo leva 66ms. A diferença de 45ms é o tempo extra que o algoritmo pós-quântico consome. |
| /open-insurance/consents/v3/consents (POST) | 54,47ms | 126,75ms | +72ms (+133%) | Quando o script cria um consentimento fazendo um POST para /consents, o Servidor de Dados precisa responder confirmando que o consentimento foi criado. Com PQC, essa resposta vem assinada com ML-DSA-65 — o servidor gasta tempo calculando a assinatura, e depois ainda precisa transmitir um JWT maior do que antes. Com PS256 isso leva 54ms. Com ML-DSA-65 leva 127ms. A diferença de 72ms tem duas origens: o tempo de assinar com ML-DSA-65 (mais pesado que PS256) e o tempo de transmitir o JWT de resposta, que agora é quase 4 vezes maior. |
| /open-insurance/consents/v3/consents (GET) | 17,69ms | 39,73ms | +22ms (+125%) | Após criar o consentimento, o script consulta o status dele várias vezes para verificar se está em AWAITING_AUTHORISATION e depois em AUTHORISED. Cada consulta é um GET no mesmo endpoint /consents/{id}. Com PS256 essa consulta leva 17,69ms. Com ML-DSA-65 leva 39,73ms. A lógica do servidor para responder é a mesma da criação — ele busca o consentimento no banco, monta a resposta JSON e assina com ML-DSA-65. O overhead de 22ms vem do mesmo lugar: o tempo de assinar mais o tempo de transmitir um JWT maior. É o mesmo padrão da criação, só que numa operação de leitura em vez de escrita. |
| /open-insurance/insurance-person/v2/... | ~27,40ms | ~46,76ms | +19ms (+71%) | O fluxo person chama quatro APIs de dados pessoais — insurance-person, claim, policy-info e premium — cada uma retornando dados reais de apólice, sinistro e prêmio do segurado. Com PQC, cada resposta é assinada com ML-DSA-65. Com PS256 a média de resposta entre os quatro endpoints é 27,40ms. Com ML-DSA-65 é 46,76ms. O overhead médio entre os quatro endpoints é de 19ms, mas varia significativamente — de +8ms no policy-info até +34ms no insurance-person — refletindo diferenças no tamanho e complexidade de cada payload de resposta. Contrariamente ao que se poderia esperar, o overhead absoluto é menor que o do /consents GET (+22ms) — o custo de assinar com ML-DSA-65 é fixo independentemente do tamanho do payload, e os dados de pessoa, embora maiores em conteúdo de negócio, não geram overhead adicional proporcional no processamento criptográfico. |
| /jwks (GET) | 39,64ms | 49,99ms | +10ms (~26%) no 0ms; convergem a partir de 14ms | O endpoint /jwks é onde o cliente busca a chave pública do servidor para verificar os tokens que recebe. É uma operação simples de leitura — o servidor não faz cálculo criptográfico, só devolve a chave pública armazenada. No cenário de rede zero há uma diferença de 10ms entre os dois experimentos, possivelmente overhead de primeira carga da chave ML-DSA-65 ou ruído estatístico de n=2 amostras. A partir de 14ms de latência injetada, os dois valores convergem e ficam praticamente idênticos — o RTT de rede absorve qualquer diferença de processamento. O que muda entre os experimentos é o tamanho da resposta: a chave pública RSA-2048 tem 256 bytes, enquanto a chave ML-DSA-65 tem 1.952 bytes (valor da especificação FIPS 204 — limitação metodológica: o parser de JWK do pipeline não reconhece o tipo AKP e essa chave não aparece nos resultados medidos diretamente). Como são apenas 2 chamadas no fluxo inteiro, esse crescimento não tem impacto perceptível na latência. |

| Parâmetro | Clássico (Exp 1) | PQC Puro (Exp 2) | Crescimento | O que isso significa para a equação OPINsize |
|---|---|---|---|---|
| N_mTLS — número de handshakes distintos | ~9 a 16 (média ≈ 11) | 6 (constante em todos os cenários) | Estável | O número de conexões não muda com o algoritmo — só o custo de cada uma. A variação entre cenários no clássico reflete o comportamento de conexão do script Python (reutilização de sessão TLS); no PQC o valor é perfeitamente constante. |
| mTLS_handshake_bytes — tamanho do handshake P50 | 10.381 a 10.511 bytes (média ≈ 10.418 bytes, cenários 14ms–320ms) | 15.500 bytes (todos cenários) | +49% | Parâmetro que cresce com o certificado ML-DSA-65 do cliente. Perfeitamente estável no PQC — evidência de que o tamanho do handshake é determinístico para esse algoritmo. |
| N_JWT — número de tokens no fluxo | 26 | 26 | Estável | O número de tokens não muda com o algoritmo — só o tamanho de cada um. Parâmetro fixo da equação nos dois experimentos. |
| JWT_size — tamanho médio de JWT | 1.385 bytes | 5.459 bytes | 3,94x | Parâmetro mais impactado — dominado pelo crescimento da assinatura. Contribui para o aumento do OPINsize analítico na proporção N_JWT × crescimento. |
| JWK_PK_size — tamanho da chave pública do AS | 256 bytes (RSA-2048) | 1.952 bytes (ML-DSA-65) | 7,63x | A chave pública publicada no JWKS do Servidor de Autorização cresce 7,63 vezes. Reflete o tamanho estruturalmente maior das chaves ML-DSA-65 definido pelo padrão FIPS 204. |
| N_JWK — número de chamadas ao /jwks | 2 | 2 | Estável | O número de consultas ao endpoint de chaves públicas não muda com o algoritmo. |

| Métrica | Clássico (Exp 1) | PQC Puro (Exp 2) | Estimativa Exp 3 (Híbrido) | Justificativa |
|---|---|---|---|---|
| OPINsize total (bytes) | ~67.604 | ~178.029 | Estimado acima de ~178.029 | No híbrido cada JWT carrega PS256 e ML-DSA-65 simultaneamente. O OPINsize deve superar o PQC puro pelo acréscimo das assinaturas PS256 adicionais. |
| JWT médio (bytes) | 1.385 | 5.459 | Estimado acima de 5.459 | Cada JWT carregará duas assinaturas — ML-DSA-65 (~4.412 bytes b64url) e PS256 (~342 bytes b64url, RSA-2048, que representa a maioria dos JWTs do fluxo). O crescimento adicional sobre o PQC puro é da ordem de 342 bytes por JWT. |
| Handshake mTLS P50 (bytes) | 10.381 | 15.500 | Estimado próximo ou acima de 15.500 | O certificado híbrido carregará as duas assinaturas. O handshake deve ser similar ao PQC puro ou ligeiramente maior. |
| Overhead /token (0ms rede) | 21,25ms (ref.) | 66,5ms (+45ms) | Estimado acima de 66,5ms | O servidor precisará verificar duas assinaturas por JWT. O overhead computacional deve ser maior que o PQC puro, que verifica uma assinatura maior, versus o híbrido que verifica duas. |

