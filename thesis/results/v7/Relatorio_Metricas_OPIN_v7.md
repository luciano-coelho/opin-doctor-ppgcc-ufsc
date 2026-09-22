# Relatório Consolidado de Métricas Experimentais — v7

**Migração PQC do Ecossistema OPIN — Clássico vs PQC Puro vs Híbrido**
Luciano Figueiredo Coelho | PPGCC/LabSEC/UFSC

> Esta é a atualização, para a v7, de um relatório anterior (`Relatorio_Metricas_OPIN_Luciano_Coelho_FINAL.pdf`, em `thesis/docs/`) que comparava apenas dois experimentos, Clássico e PQC puro, e tratava o perfil híbrido como trabalho futuro ("Experimento 3", Seção 6 daquele documento). A v7 mede os três perfis num único lote, sob a mesma arquitetura de teste, e estende a equação de tamanho com um quarto termo (PKI/CRL). Todo número aqui é o número final da v7 — nenhum valor deste documento vem do relatório anterior, que fica preservado só como registro histórico do que já foi medido antes. Este documento mantém o formato do original (uma tabela larga, uma linha por métrica, com uma coluna de observação que explica o significado e o achado); para a versão organizada por seção, com a metodologia completa e as introduções didáticas de cada tabela, ver [`CONSOLIDATED_REPORT.md`](CONSOLIDATED_REPORT.md) e [`ARCHITECTURE.md`](ARCHITECTURE.md).

## 1. Objetivo e Contexto

Este documento consolida os resultados finais da v7 numa única tabela de referência, organizada por métrica. A v7 mediu o mesmo fluxo de consentimento OPIN sob três perfis criptográficos, executados sob a mesma arquitetura de cliente TLS (eliminando qualquer diferença de ambiente entre eles):

- **Clássico**: PS256/RSA em todos os artefatos de assinatura; troca de chave TLS com curvas elípticas clássicas.
- **PQC puro**: ML-DSA-65 substituindo completamente as assinaturas em todos os componentes sob controle desta tese (Authorization Server, Resource Server, certificado do cliente, certificado do gateway mTLS e a cadeia de certificados CA); troca de chave TLS com ML-KEM-1024 puro.
- **Híbrido**: cada artefato carrega as duas assinaturas (clássica e ML-DSA-65) simultaneamente, com um esquema de combinação escolhido conforme o papel do artefato (Seção 6); troca de chave TLS com o grupo híbrido X25519MLKEM768.

A coluna de observação de cada linha explica o que a métrica significa, referencia as decisões arquiteturais relevantes (documentadas em `DECISIONS.md`) e reporta achados quando existirem. Todos os números têm origem em `thesis/results/v7/report_data_v7.json`, recalculado de forma independente a partir dos arquivos brutos (`thesis/scripts/audit_v7_from_raw.py`) — nenhum deles é uma remedição; são os mesmos 180 execuções (60 por perfil: 6 cenários de latência × 10 execuções) já usadas em `CONSOLIDATED_REPORT.md`.

## 2. Tabela Consolidada de Métricas

| Métrica | Clássico | PQC | Híbrido | Observação — significado, decisões e achados |
|---|---:|---:|---:|---|
| **Tráfego — OPINsize** ||||
| OPINsize (bytes) — fórmula estendida (4 termos) | 75.687 | 261.663 | 340.355 | Custo total do fluxo, pela equação desta tese (Seção 3): N_mTLS × handshake_bytes + N_JWT × JWT_size + N_JWK × JWK_PK_size + N_PKI × PKI_bytes. É a métrica de custo de comunicação do fluxo completo. O PQC é **3,46× o Clássico** (+245,72%); o Híbrido é **4,50× o Clássico** (+349,69%) e **1,30× o PQC** (+30,07%). Crescimento tecnicamente plausível e consistente com o aumento esperado no tamanho dos artefatos criptográficos ao adotar primitivas pós-quânticas; o Híbrido soma o custo das duas assinaturas em cada artefato, por isso fica acima do PQC puro em todas as métricas de tamanho. |
| **Handshake mTLS** ||||
| Handshake mTLS — bytes (P50) | 5.119 | 16.605 | 18.023 | Tamanho do handshake mTLS, medido pelo P50 em bytes, sobre 60 execuções por perfil (spread 0,00%, i.e. valor determinístico). O número de handshakes permanece constante em 6 nos três cenários; a variação decorre exclusivamente do tamanho de cada conexão. PQC é 3,24× o Clássico (+224,38%); Híbrido é 3,52× o Clássico (+252,08%) e 1,09× o PQC (+8,54%) — no Híbrido, cliente e gateway apresentam certificados com as duas assinaturas simultâneas, o que soma ao invés de substituir o custo do certificado clássico. |
| **Artefatos Criptográficos** ||||
| JWT médio (bytes) | 1.385,42 | 5.458,81 | 7.324,81 | Tamanho médio dos JWTs (header + payload + assinatura), sobre os 26 tokens do fluxo (constante nos três perfis). PQC é 3,94× o Clássico (+294,02%); Híbrido é 5,29× o Clássico (+428,71%) e 1,34× o PQC (+34,18%) — no Híbrido, o JWT carrega a assinatura RS256/PS256 e a ML-DSA-65 ao mesmo tempo (Strong Nesting ou extensão de payload, conforme o artefato — `ARCHITECTURE.md`, Seção 4.2). |
| Certificado do cliente (bytes DER) | 1.494 | 2.953 | 6.859 | Tamanho do certificado digital do cliente de teste, apresentado na conexão mTLS. PQC é 1,98× o Clássico (+97,66%); Híbrido é 4,59× o Clássico (+359,10%) e 2,32× o PQC (+132,27%) — o certificado híbrido reutiliza a chave RSA do Clássico e acrescenta o material ML-DSA-65 completo (chave pública e assinatura alternativa) em três extensões X.509 não críticas (Bindel et al., 2019), o que explica por que ele é maior que a soma ingênua dos dois certificados isolados não seria. |
| JWK_PK_size — chave pública do AS (bytes) | 256 (RSA-2048) | 1.952 (ML-DSA-65) | 2.208 (composta, `kty: HYBRID`) | Tamanho da chave pública do AS publicada em `/jwks`, para verificação dos tokens. PQC é 7,62× o Clássico (+662,50%); Híbrido é 8,62× o Clássico (+762,50%) e 1,13× o PQC (+13,11%). Como N_JWK permanece constante em 2 nos três cenários, o crescimento decorre exclusivamente do maior tamanho da chave — no Híbrido, uma chave composta que carrega as duas metades. |
| PKI_bytes médio — certificado de CA (bytes, corpo PEM puro) | 2.110 | 4.050 | 9.339 | Tamanho médio dos dois certificados de CA (raiz e emissora) no formato em que trafegam (PEM), sem o enquadramento HTTP. Termo novo desta tese (Seção 3). PQC é 1,92× o Clássico (+91,94%); Híbrido é 4,43× o Clássico (+342,61%) e 2,31× o PQC (+130,59%) — mesmo padrão do certificado de cliente: o Híbrido soma as duas assinaturas na cadeia de CA. |
| **Bytes por Participante** (camada de aplicação HTTP, "enviado" = saída/egress do participante) ||||
| Servidor de Autorização — AS | 14.188 | 29.570 | 31.058 | Volume de saída do AS (consentimento, PAR, tokens, JWKS). PQC é 2,08× o Clássico (+108,42%); Híbrido é 2,19× o Clássico (+118,90%) e 1,05× o PQC (+5,03%) — o AS emite proporcionalmente menos JWTs pesados que o RS, então seu crescimento relativo é mais modesto. Decomposto de "Outros" (que antes somava AS+RS) por uma captura pontual determinística; ver Seção 3.3 de `CONSOLIDATED_REPORT.md` e `DECISIONS.md`, Decision 10. |
| Servidor de Dados — RS | 26.034 | 91.252 | 121.196 | Volume de saída do RS (consultas de seguro, sinistro, apólice, prêmio). PQC é 3,51× o Clássico (+250,51%); Híbrido é 4,66× o Clássico (+365,53%) e 1,33× o PQC (+32,81%) — o maior aumento absoluto entre os participantes (95.162 bytes do Clássico ao Híbrido), pois o RS participa de mais chamadas assinadas ao longo do fluxo do que o AS. De cada 100 bytes que os servidores emitem, o RS responde por 53,1% no Clássico, 66,4% no PQC e 63,8% no Híbrido (`CONSOLIDATED_REPORT.md`, Seção 3.3) — o participante que mais pesa na conta de egress em nuvem. |
| PKI/CRL (certificados CA, resposta HTTP completa) | 8.852 | 16.612 | 37.768 | Volume de saída do Diretório/PKI ao servir os certificados de CA — corpo do certificado + enquadramento HTTP (103 bytes por resposta, idêntico nos três perfis; validado byte a byte contra os arquivos PEM usados no cálculo, `ARCHITECTURE.md` Seção 7.1). PQC é 1,88× o Clássico (+87,66%); Híbrido é 4,27× o Clássico (+326,66%) e 2,27× o PQC (+127,35%). |
| **Latência por Endpoint** (P50, cenário de rede 0ms — algoritmo isolado da rede) ||||
| `/token` (POST) | 21,99 ms | 46,28 ms | 54,08 ms | Latência do endpoint que autentica o cliente via `client_assertion` assinada. PQC +24,29 ms (+110,46%) sobre o Clássico; Híbrido +32,09 ms (+145,93%) sobre o Clássico e +7,80 ms (+16,85%) sobre o PQC — o Híbrido soma o tempo de verificar as duas assinaturas da `client_assertion`. |
| `/consents` (POST) | 29,63 ms | 53,92 ms | 65,15 ms | Criação de consentimento: o RS monta e assina a resposta antes de devolvê-la. PQC +24,29 ms (+81,98%); Híbrido +35,52 ms (+119,88%) sobre o Clássico e +11,23 ms (+20,83%) sobre o PQC. |
| `/consents/{id}` (GET) | 14,11 ms | 27,04 ms | 31,73 ms | Consultas de estado do consentimento (acompanhando a transição até `AUTHORISED`). PQC +12,93 ms (+91,64%); Híbrido +17,62 ms (+124,88%) sobre o Clássico e +4,69 ms (+17,34%) sobre o PQC. |
| `/request` (PAR, POST) | 9,55 ms | 19,27 ms | 21,51 ms | Objeto de autorização por referência, assinado pelo cliente. PQC +9,72 ms (+101,78%); Híbrido +11,96 ms (+125,24%) sobre o Clássico e +2,24 ms (+11,62%) sobre o PQC. |
| APIs de dados pessoais (média de 4 endpoints: dados básicos, sinistro, apólice, prêmio) | 17,41 ms | 33,43 ms | 34,82 ms | Latência média das quatro consultas do fluxo `person`, cada resposta assinada pelo RS. PQC +16,02 ms (+92%) sobre o Clássico; Híbrido +17,42 ms (+100%) sobre o Clássico e +1,39 ms (+4,2%) sobre o PQC. O overhead varia por endpoint (de +9,98 ms em `policy-info` a +22,44 ms em `claim` no PQC), consistente com a ideia de que quanto maior a resposta a assinar, maior o custo de processamento. |
| `/jwks` (GET) | 26,00 ms | 21,05 ms | 27,31 ms | Leitura de chaves públicas — sem operação de assinatura ou verificação no endpoint. As pequenas diferenças (PQC −4,95 ms; Híbrido +1,31 ms sobre o Clássico) não têm direção consistente e ficam no nível do ruído de medição, ao contrário dos endpoints que assinam: confirma que o custo pós-quântico está nas operações de assinatura, não na simples publicação de uma chave maior. |
| PKI/CRL (download de certificado de CA) | 11,81 ms | 10,50 ms | 13,76 ms | Leitura de arquivo estático — mesmo padrão do `/jwks`: sem direção consistente entre Clássico e PQC (−1,31 ms), pequeno aumento no Híbrido (+1,95 ms), ambos dentro do ruído. |
| **Parâmetros Fixos da Equação OPINsize** ||||
| N_mTLS — handshakes distintos | 6 (constante) | 6 (constante) | 6 (constante) | Número de conexões mTLS do fluxo (três pools de conexão por sub-fluxo × 2 sub-fluxos). Constante nos três perfis: o crescimento do custo de comunicação não vem de mais conexões, mas do maior tamanho de cada uma. |
| N_JWT — tokens no fluxo | 26 (constante) | 26 (constante) | 26 (constante) | Número de JWTs trafegados. Constante nos três perfis. |
| N_JWK — chamadas ao `/jwks` | 2 (constante) | 2 (constante) | 2 (constante) | Número de consultas às chaves públicas do AS (uma por sub-fluxo). Constante nos três perfis. |
| N_PKI — buscas de certificado de CA | 4 (constante) | 4 (constante) | 4 (constante) | Termo novo desta tese: número de downloads de certificado de CA (raiz + emissora, uma vez em cada um dos 2 sub-fluxos = 4). Constante nos três perfis; confirmado em código (`opin_flow.py`, `fetch_server_keys_and_ca()`, chamada em `run_insurance_flow` e `run_person_flow`). |

## 3. Equação do OPINsize

A equação original de tamanho do fluxo (equivalente à Eq. 3.1 de Schardong et al., 2022) soma três termos — o custo do handshake mTLS, dos tokens trafegados e das chaves públicas publicadas. Esta tese a estende com um quarto termo, para os certificados de Autoridade Certificadora que o fluxo baixa e que já eram medidos, mas nunca entravam na soma. A partir daqui, **OPINsize refere-se sempre à fórmula estendida** — a de três termos não volta a aparecer como resultado, só serviu para justificar a extensão (a justificativa completa está em `ARCHITECTURE.md`, Seção 7):

```
OPINsize = N_mTLS × handshake_bytes + N_JWT × JWT_size + N_JWK × JWK_PK_size + N_PKI × PKI_bytes
```

### 3.1 Variáveis da equação

| Variável | Descrição | Clássico | PQC | Híbrido |
|---|---|---:|---:|---:|
| N_mTLS | Número de handshakes mTLS distintos no fluxo | 6 | 6 | 6 |
| handshake_bytes | Tamanho do handshake mTLS (P50) | 5.119 bytes | 16.605 bytes | 18.023 bytes |
| N_JWT | Número de tokens JWT no fluxo | 26 | 26 | 26 |
| JWT_size | Tamanho médio de cada JWT | 1.385,42 bytes | 5.458,81 bytes | 7.324,81 bytes |
| N_JWK | Número de chamadas ao `/jwks` | 2 | 2 | 2 |
| JWK_PK_size | Tamanho da chave pública do AS | 256 bytes | 1.952 bytes | 2.208 bytes |
| N_PKI | Número de buscas de certificado de CA | 4 | 4 | 4 |
| PKI_bytes | Tamanho médio do certificado de CA (PEM) | 2.110 bytes | 4.050 bytes | 9.339 bytes |

### 3.2 Cálculo do cenário Clássico

```
OPINsize = (6 × 5.119) + (26 × 1.385,42) + (2 × 256) + (4 × 2.110)
6 × 5.119     = 30.714 bytes
26 × 1.385,42 = 36.021 bytes
2 × 256       =    512 bytes
4 × 2.110     =  8.440 bytes
OPINsize = 30.714 + 36.021 + 512 + 8.440 = 75.687 bytes
```

### 3.3 Cálculo do cenário PQC

```
OPINsize = (6 × 16.605) + (26 × 5.458,81) + (2 × 1.952) + (4 × 4.050)
6 × 16.605     =  99.630 bytes
26 × 5.458,81  = 141.929 bytes
2 × 1.952      =   3.904 bytes
4 × 4.050      =  16.200 bytes
OPINsize = 99.630 + 141.929 + 3.904 + 16.200 = 261.663 bytes
```

### 3.4 Cálculo do cenário Híbrido

```
OPINsize = (6 × 18.023) + (26 × 7.324,81) + (2 × 2.208) + (4 × 9.339)
6 × 18.023     = 108.138 bytes
26 × 7.324,81  = 190.445 bytes
2 × 2.208      =   4.416 bytes
4 × 9.339      =  37.356 bytes
OPINsize = 108.138 + 190.445 + 4.416 + 37.356 = 340.355 bytes
```

### 3.5 Comparação entre os cenários

| Razão | OPINsize |
|---|---:|
| PQC / Clássico | 3,46× (+245,72%) |
| Híbrido / Clássico | 4,50× (+349,69%) |
| Híbrido / PQC | 1,30× (+30,07%) |

Os cálculos mostram que o crescimento do OPINsize não decorre de nenhuma alteração na estrutura do fluxo: N_mTLS, N_JWT, N_JWK e N_PKI são idênticos nos três cenários. O crescimento decorre inteiramente do maior tamanho dos artefatos criptográficos — no Híbrido, porque cada artefato carrega as duas assinaturas ao mesmo tempo, e não apenas a pós-quântica.

O termo de PKI representa 11,15% do OPINsize do Clássico, 6,19% do PQC e 10,98% do Híbrido — no Híbrido, o segundo maior componente da soma, atrás só do termo de JWT. A análise de sensibilidade do termo (formato PEM vs. DER, corpo puro vs. enquadramento HTTP medido) está em `ARCHITECTURE.md`, Seção 7.4; a variação encontrada é de no máximo ±3,1 pontos percentuais sobre o OPINsize total, em qualquer perfil.

## 4. Latência do Fluxo em Cenários de Rede Distintos

Até aqui, este documento mediu o custo do algoritmo criptográfico isolado do efeito da rede: as latências por endpoint da Seção 2 foram medidas no cenário de rede zero, onde cliente e servidor estão na mesma máquina, sem nenhum atraso de transmissão. Essa escolha isola o cenário mais controlado, atribuindo qualquer diferença de tempo exclusivamente ao algoritmo, sem a rede como variável de confusão.

Esta seção responde a uma pergunta complementar: como o fluxo completo de consentimento (as 28 chamadas, nos dois sub-fluxos) se comporta quando a rede real entra em cena? Os seis cenários usados na v7 (0, 14, 30, 140, 225 e 320 ms, simulados via `tc`/`netem` no gateway) reproduzem os valores de latência medidos empiricamente em cinco regiões geográficas da AWS por Schardong et al. (2022) — a mesma metodologia do artigo-base, uma lente granular por componente (Seção 2) e outra agregada por condição de rede (esta seção).

### Latência Total do Fluxo (T_fluxo, mediana de 10 execuções por cenário e por perfil)

| Cenário | Clássico | PQC | Híbrido | Δ PQC−Clássico | Δ Híbrido−Clássico | Δ Híbrido−PQC |
|---|---:|---:|---:|---:|---:|---:|
| 0 ms | 2.891,26 ms | 9.586,39 ms | 10.269,73 ms | +6.695,14 ms (+231,56%) | +7.378,47 ms (+255,20%) | +683,34 ms (+7,13%) |
| 14 ms | 4.693,21 ms | 11.152,92 ms | 12.275,20 ms | +6.459,71 ms (+137,64%) | +7.581,99 ms (+161,55%) | +1.122,28 ms (+10,06%) |
| 30 ms | 7.176,65 ms | 13.345,81 ms | 14.492,22 ms | +6.169,17 ms (+85,96%) | +7.315,57 ms (+101,94%) | +1.146,40 ms (+8,59%) |
| 140 ms | 24.859,26 ms | 30.107,49 ms | 32.358,19 ms | +5.248,23 ms (+21,11%) | +7.498,93 ms (+30,17%) | +2.250,70 ms (+7,48%) |
| 225 ms | 38.481,78 ms | 44.327,57 ms | 46.416,61 ms | +5.845,79 ms (+15,19%) | +7.934,83 ms (+20,62%) | +2.089,04 ms (+4,71%) |
| 320 ms | 53.669,58 ms | 59.569,22 ms | 61.437,57 ms | +5.899,64 ms (+10,99%) | +7.767,99 ms (+14,47%) | +1.868,35 ms (+3,14%) |

Ao contrário do relatório anterior (Clássico vs PQC, pré-v7), em que a diferença entre os cenários oscilava de direção a partir de 14 ms de latência injetada, a v7 encontra a ordem **Clássico < PQC < Híbrido se mantém em todos os 6 cenários de rede**, sem exceção — confirmado por um teste de Mann-Whitney U exato, unicaudal (todas as combinações C(20,10)): a hipótese "PQC é mais lento que o Clássico" tem p ≈ 5,41×10⁻⁶ nos 6 cenários (as faixas min–max de Clássico e PQC nunca se sobrepõem); a hipótese "Híbrido é mais lento que o PQC" tem p entre 1,08×10⁻⁵ e 3,42×10⁻³, dependendo do cenário — estatisticamente significativa mesmo nos casos em que as faixas min–max se sobrepõem entre si.

O que muda com a rede é a **magnitude relativa** do overhead, não a sua direção: em rede zero, o PQC é 3,32× mais lento que o Clássico; em 320 ms, é apenas 1,11× mais lento. Isso é esperado — com 28 chamadas HTTP compondo o fluxo completo, cada uma sofrendo o mesmo atraso de rede, o tempo total passa a ser dominado pelo número de idas e voltas na rede (round trips), não pelo custo computacional de cada assinatura individual. O overhead do algoritmo pós-quântico, da ordem de dezenas de milissegundos por operação (Seção 2), torna-se proporcionalmente menor diante de uma latência de rede que, sozinha, já adiciona segundos ao tempo total do fluxo — mas ele nunca desaparece nem se inverte: mesmo em 320 ms, a ordem Clássico < PQC < Híbrido continua estatisticamente confirmada. Essa é uma leitura mais forte do que a do relatório anterior, que havia relatado a perda de um padrão claro em cenários de rede mais realistas; com os três perfis medidos sob a mesma arquitetura de teste e o teste de hipótese formal, a v7 mostra que a ordem se mantém — só o tamanho relativo da diferença encolhe.

## 5. Consolidação Arquitetural do Perfil Híbrido

O relatório anterior (pré-v7) tratava o perfil híbrido como trabalho futuro ("Experimento 3"), descrevendo a base arquitetural herdada dos Experimentos 1 e 2 e a mudança de lógica de assinatura necessária. Esse trabalho foi concluído na v7. Um resumo do que foi implementado, para fechar essa lacuna:

- **Arquitetura de perfis evoluiu de seleção para combinação.** Em vez de escolher um único algoritmo por variável de configuração, o AS e o RS agora assinam com os dois algoritmos simultaneamente quando `CRYPTO_PROFILE=hybrid`, e o certificado do cliente e do gateway carregam as duas assinaturas ao mesmo tempo.
- **Três esquemas de combinação, um por tipo de artefato**, escolhidos pela propriedade de segurança mais adequada a cada papel: extensões X.509 duplamente assinadas nos certificados (Bindel et al., 2019); extensão de payload no JWT do RS, na `client_assertion` e no objeto PAR (compatibilidade com verificadores legados); Strong Nesting no `id_token` e no JARM do AS (propriedade SUF-CMA, Bindel et al., 2017). O detalhamento de cada esquema, com as referências completas, está em `ARCHITECTURE.md`, Seção 4.2.
- **A troca de chave híbrida** usa o grupo `X25519MLKEM768`: a chave de sessão deriva do X25519 e do ML-KEM-768 juntos, preservando a confidencialidade se apenas um dos dois for quebrado.
- **Nenhuma métrica nova precisou ser criada**: OPINsize, tamanho do handshake mTLS, tamanho médio de JWT, bytes por participante e latência por endpoint — as mesmas métricas definidas nos Experimentos 1 e 2 — foram medidas para o Híbrido com o mesmo pipeline de coleta e análise, e são as que aparecem em todas as tabelas deste documento.

## 6. Proveniência dos números

Todos os valores desta tabela vêm de `thesis/results/v7/report_data_v7.json`, computado por `thesis/scripts/compute_v7_report_data.py` a partir dos arquivos brutos das 180 execuções oficiais (`thesis/results/v7/size/` e `thesis/results/v7/latency/`), e recalculados de forma independente antes da consolidação (`thesis/scripts/audit_v7_from_raw.py`, saída completa em `audit_recompute_from_raw.txt`). Duas exceções, documentadas explicitamente para não gerar confusão futura sobre o que foi ou não remedido:

1. **Bytes por participante (AS/RS decompostos)**: reprocessados a partir de uma captura pontual determinística (uma execução por perfil, fora do protocolo estatístico oficial), que reconcilia exatamente com os totais "Outros" já commitados — não é uma nova amostra estatística (`DECISIONS.md`, Decision 10).
2. **Latência por endpoint (Seção 2)**: reprocessada diretamente dos 10 arquivos brutos oficiais de cada perfil no cenário 0 ms (`thesis/results/v7/size/experiment*/0ms/runs/*.json`, campo `latency_per_endpoint`), agrupando os endpoints com identificador dinâmico (ex.: `/consents/{id}`) pelo padrão da URL; a mediana, entre as 10 execuções, da latência média ponderada de cada grupo de endpoint. Também não é uma nova coleta — é a mesma medição já usada para compor as métricas de tamanho, olhada por um ângulo (endpoint) que nenhum dos dois relatórios principais publica.

Documentos relacionados: [`CONSOLIDATED_REPORT.md`](CONSOLIDATED_REPORT.md) (relatório oficial, organizado por seção, com metodologia completa), [`ARCHITECTURE.md`](ARCHITECTURE.md) (arquitetura do experimento e da equação OPINsize estendida), [`DECISIONS.md`](DECISIONS.md) (decisões arquiteturais e metodológicas, Decisions 1–10), [`TLS_KEM_Proxy_Architecture.md`](TLS_KEM_Proxy_Architecture.md) (o cliente TLS unificado que mediu os três perfis).

## Referências

- Bindel, N., Herath, U., McKague, M., & Stebila, D. (2017). *Transitioning to a Quantum-Resistant Public Key Infrastructure.* PQCrypto 2017.
- Bindel, N., Braun, J., Gladiator, L., Stebila, D., & Wiggers, T. (2019). *X.509-Compliant Hybrid Certificates for the Post-Quantum Transition.* Journal of Open Source Software, 4(40), 1606.
- Schardong et al. (2022), Eq. 3.1 (equação de tamanho do fluxo original). *Entrada bibliográfica completa a ser inserida pelo autor.*
- NIST FIPS 203 (ML-KEM) e FIPS 204 (ML-DSA).
