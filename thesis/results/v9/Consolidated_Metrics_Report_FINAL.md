# Consolidated Experimental Metrics Report: real multi-region AWS campaign

**Post-quantum migration of the OPIN ecosystem: Classic, pure PQC, Hybrid, and Control -- real network, single window, 320 executions**
Luciano Figueiredo Coelho | PPGCC/LabSEC/UFSC

## 1. Parâmetros da campanha

- **Perfis:** 4 (Classic, PQC, Control, Hybrid) x **8 rotas** reais (3 instalações: `sa-east-1`, `us-east-1`, `ap-northeast-1`).
- **N por célula:** 10 execuções oficiais + 5 aquecimentos descartados (nunca lidos por nenhuma estatística abaixo).
- **Total:** 320/320 execuções oficiais, 160 aquecimentos, 32/32 capturas dedicadas (0 falhas).
- **Janela única:** `2026-11-15T17:37:59.293861+00:00` -> `2026-11-16T00:06:40.838058+00:00`.
- **Seed de randomização:** `20261107` (ordem dos perfis registrada por rota no próprio manifesto -- `route_orders`).
- **cost_stop:** `None` (nunca acionado).

## 2. Resultados de tamanho: a equação OPINsize

Equação desta linha de pesquisa (extensão de Schardong et al., Eq. 3.1, com o termo de PKI):

```
OPINsize = N_mTLS x handshake_bytes + N_JWT x JWT_size + N_JWK x JWK_PK_size + N_PKI x PKI_bytes
```

### 2.1 OPINsize total por perfil (variante assinatura+chave crua) e razão contra Classic

Comparação central desta tese: **Classic / PQC / Hybrid**. O perfil Control é de apoio/diagnóstico -- reportado separadamente logo abaixo, nunca misturado nesta tabela.

| Perfil | OPINsize (bytes) | Razão vs. Classic |
|---|---:|---:|
| Classic | 34.071,88 | 1,00x |
| PQC | 256.429,92 | 7,53x |
| Hybrid | 286.202,08 | 8,40x |

**Hybrid menos PQC: 29.772,16 bytes** (11,61% a mais que PQC puro).

**Perfil Control, separado (não entra na comparação central Classic/PQC/Hybrid acima):**

| Perfil | OPINsize (bytes) | Razão vs. Classic |
|---|---:|---:|
| Control | 242.008,08 | 7,10x |

### 2.2 OPINsize por termo, por perfil, contagens N

| Termo | N por execução | Classic | PQC | Hybrid |
|---|---:|---:|---:|---:|
| mTLS (handshake) | 6 | 18.750 | 129.636 | 144.474 |
| JWT (apenas assinatura) | 28 | 6.655,88 | 86.033,92 | 92.690,08 |
| JWK (chave crua) | 4 | 1.536 | 8.320 | 9.856 |
| PKI (certificados de CA) | 4 | 7.130,00 | 32.440 | 39.182,00 |
| **OPINsize (total)** | 44 chamadas/execução | **34.071,88** | **256.429,92** | **286.202,08** |

**Perfil Control, por termo (separado):**

| Termo | N por execução | Control |
|---|---:|---:|
| mTLS (handshake) | 6 | 101.694 |
| JWT (apenas assinatura) | 28 | 92.690,08 |
| JWK (chave crua) | 4 | 9.856 |
| PKI (certificados de CA) | 4 | 37.768 |
| **OPINsize (total)** | 44 chamadas/execução | **242.008,08** |

**Sobre o rótulo "PKI":** as 4 chamadas deste termo são, confirmado em código (`thesis/scripts/opinsize_v9_oficial.py`, `PKI_ENDPOINTS = {"/root-ca.pem", "/issuer-ca.pem"}`), recuperação dos certificados de CA (raiz + emissora, uma vez por sub-fluxo) -- **nunca** uma lista de revogação (CRL). O campo interno do pipeline se chama `term_pki_crl` por uma convenção de nomenclatura herdada, não porque CRL seja de fato buscada; este relatório usa "PKI (certificados de CA)", que descreve o que a chamada real faz.

**Verificação externa ao pipeline de medição (termo mTLS, não circular):** `evaluate_criteria.expected_handshake_bytes()` deriva o número esperado de bytes de handshake por conexão (entrada+saída) a partir do tamanho DER real dos certificados efetivamente implantados em `certs/generated/` -- uma fonte INDEPENDENTE da captura de tráfego da campanha. Rodado agora, ao vivo, por este script (não copiado de um relatório anterior):

| Perfil | Esperado (DER real dos certificados, bytes/conexão) | Medido (campanha, bytes/conexão) | Bate? |
|---|---:|---:|---|
| Classic | 3.125 | 3.125 | SIM |
| PQC | 21.606 | 21.606 | SIM |
| Hybrid | 24.079 | 24.079 | SIM |

**Perfil Control, separado:** esperado 16.949 bytes/conexão, medido 16.949 bytes/conexão -- bate? SIM.

### 2.3 Status da verificação por termo

| Termo | Fonte da verificação | Resultado |
|---|---|---|
| mTLS | Independente do pipeline de medição (DER real dos certificados implantados, Seção 2.2 acima) | Bate exatamente, 4/4 perfis |
| JWT | Independente do pipeline de medição (tamanho de assinatura por especificação -- RSA-2048/ML-DSA-65, FIPS 204) | Bate (ver Seção 2.4; resíduo fracionário explicado pela aritmetica do pipeline) |
| JWK | Independente do pipeline de medição (tamanho de chave pública por especificação + composição real de cada chamada) | Bate exatamente, 4/4 perfis (ver Seção 2.4) |
| PKI | Independente do pipeline de medição (tamanho real dos arquivos de CA no disco + sobrecarga de framing HTTP, ambos confirmados em código) | Bate exatamente, 4/4 perfis (ver Seção 2.4) |

### 2.4 Verificação por especificação (independente do pipeline), por termo e por perfil

#### 2.4.1 JWT -- bytes de assinatura por especificação

Especificação: assinatura RSA-2048 PS256 = 256B; assinatura ML-DSA-65 pura (FIPS 204) = 3309B; construções duplamente assinadas (Hybrid/Control) somam as duas. Confirmado nos dados reais (2.240 amostras/perfil) que `classical_sig_bytes`/`pq_sig_bytes` são CONSTANTES em todo o conjunto, sem nenhuma variação -- nunca assumido da especificação sem checar.

| Perfil | Construções por execução (contagem real) | Soma esperada/execução (especificação) | Média esperada (c/ arredondamento do pipeline) | Termo esperado | Termo medido | Diferença |
|---|---|---:|---:|---:|---:|---:|
| Classic | classic_only=26, jwe=2 | 6.656 | 237,71 | 6.655,88 | 6.655,88 | 0,00 |
| PQC | jwe=2, pqc_pure=26 | 86.034 | 3.072,64 | 86.033,92 | 86.033,92 | 0,00 |
| Hybrid | jwe=2, payload_extension=24, strong_nesting=2 | 92.690 | 3.310,36 | 92.690,08 | 92.690,08 | 0,00 |

**Perfil Control, separado:**

| Perfil | Construções por execução (contagem real) | Soma esperada/execução (especificação) | Média esperada (c/ arredondamento do pipeline) | Termo esperado | Termo medido | Diferença |
|---|---|---:|---:|---:|---:|---:|
| Control | jwe=2, payload_extension=24, strong_nesting=2 | 92.690 | 3.310,36 | 92.690,08 | 92.690,08 | 0,00 |

**Explicação do resíduo fracionário (ex.: 86.033,92 vs. 86.034; 6.655,88 vs. 6.656; 92.690,08 vs. 92.690), confirmada no código, não suposta:** `thesis/scripts/opinsize_v9_oficial.py` calcula `jwt_sig_avg = round(statistics.mean(jwt_sig_sizes_all), 2)` e só depois `term_jwt = round(n_jwt * jwt_sig_avg, 2)` -- a média por token é arredondada a 2 casas decimais ANTES de ser multiplicada por N_JWT=28, o que propaga um resíduo de até ±0,14 byte em relação à soma exata por especificação. A tabela acima reproduz essa MESMA aritmética (coluna "Termo esperado") e bate exatamente com o termo medido nos 4 perfis -- o resíduo não é um erro de medição, é um efeito de arredondamento já presente no próprio pipeline, agora reproduzido e confirmado aqui, não apenas suposto.

**Contribuição dos tokens JWE:** por construção (`_jwt_sig_bytes`, `thesis/scripts/opinsize_v9_oficial.py`), um token `jwe` (criptografado, sem assinatura própria) contribui exatamente **0 bytes** a este termo -- confirmado em código (`classical_sig_bytes`/`pq_sig_bytes` ambos `None`→0 para essa construção) e nos dados reais (2 tokens `jwe` por execução, em todos os 4 perfis, nunca contados aqui).

#### 2.4.2 JWK -- tamanho de chave pública por especificação

Especificação (chave crua, sem envelope): RSA-2048 (módulo) = 256B; ML-DSA-65 (FIPS 204) = 1952B.

| Perfil | Chave por especificação (bytes) | Média real medida (4 chamadas) | Diferença vs. especificação | Composição real confirmada |
|---|---:|---:|---:|---|
| Classic | 256 | 384 | +128 | RSA:256+RSA:256 / RSA:256 / RSA:256+RSA:256 / RSA:256 |
| PQC | 1.952 | 2.080 | +128 | AKP:1952+RSA:256 / AKP:1952 / AKP:1952+RSA:256 / AKP:1952 |
| Hybrid | 2.208 | 2.464 | +256 | HYBRID:2208+RSA:256 / HYBRID:2208+RSA:256 / HYBRID:2208+RSA:256 / HYBRID:2208+RSA:256 |

**Perfil Control, separado:**

| Perfil | Chave por especificação (bytes) | Média real medida (4 chamadas) | Diferença vs. especificação | Composição real confirmada |
|---|---:|---:|---:|---|
| Control | 2.208 | 2.464 | +256 | HYBRID:2208+RSA:256 / HYBRID:2208+RSA:256 / HYBRID:2208+RSA:256 / HYBRID:2208+RSA:256 |

**O que compõe o acréscimo sobre a chave pura, confirmado chamada a chamada (não especulado):** das 4 chamadas reais `/jwks` por execução, **metade (2 de 4)** carrega uma SEGUNDA entrada JWK além da chave de assinatura do próprio perfil -- para Classic/PQC, essa segunda entrada é sempre uma chave RSA-2048 de 256B com `use="enc"` (a chave pública de cifragem do `id_token`, JWE, clássica em todos os perfis por desenho já declarado); as outras 2 de 4 chamadas não carregam nenhuma segunda entrada. Isso dá uma média de +128B/chamada para Classic e PQC -- mas **não é um acréscimo fixo de 128B em cada chamada individual**, é um acréscimo de 256B em exatamente metade das chamadas. Para Hybrid/Control, **todas as 4 chamadas** carregam uma segunda entrada de 256B -- 2 delas a mesma chave `use="enc"` de Classic/PQC, e as outras 2 uma entrada RSA `use="sig"` **duplicada** (o mesmo `kid` da metade clássica da chave composta, republicada separadamente para um consumidor JWKS padrão que faça descoberta por `kid`+`alg` sem suporte à chave híbrida). Por isso Hybrid/Control acrescenta 256B em TODAS as 4 chamadas, não 128B -- a tabela acima confirma isso com a composição real de cada uma das 4 chamadas de uma execução real.

#### 2.4.3 PKI -- tamanho real dos arquivos de CA + sobrecarga de framing HTTP

| Perfil | Arquivo(s) servidos (root / issuer) | PEM real (root+issuer, bytes) | Framing HTTP | Esperado (PEM+framing) | Medido | Diferença |
|---|---|---:|---|---:|---:|---:|
| Classic | root_ca_rsa2048.crt / issuer_ca_rsa2048.crt | 1.679+1.692 | content-length (+97B) | 7.130,00 | 7.130,00 | 0,00 |
| PQC | root_ca_pqc.crt / issuer_ca_pqc.crt | 8.001+8.013 | chunked (+103B) | 32.440,00 | 32.440 | 0,00 |
| Hybrid | root_ca_rsa2048.crt+root_ca_pqc.crt / issuer_ca_rsa2048.crt+issuer_ca_pqc.crt | 9.680+9.705 | chunked (+103B) | 39.182,00 | 39.182,00 | 0,00 |

**Perfil Control, separado:**

| Perfil | Arquivo(s) servidos (root / issuer) | PEM real (root+issuer, bytes) | Framing HTTP | Esperado (PEM+framing) | Medido | Diferença |
|---|---|---:|---|---:|---:|---:|
| Control | root_ca_hybrid.crt / issuer_ca_hybrid.crt | 9.337+9.341 | chunked (+103B) | 37.768,00 | 37.768 | 0,00 |

**Fontes, citadas com file:line (não estimadas):** o arquivo de CA servido por perfil vem de `realCAFilesForProfile` (`thesis/results/v9/integration/gateway/business_server.go:283-294`) -- Hybrid concatena DOIS arquivos por slot (RSA-2048 + ML-DSA-65) num único corpo de resposta, os outros 3 perfis servem um único arquivo. O tamanho PEM real de cada arquivo vem de `certs_manifest.json` (gerado por `cert_manifest.py`, lendo os arquivos reais de `mock-service-os/certs/`). A sobrecarga de enquadramento HTTP (97B content-length, 103B chunked) vem de `headerOverheadByFraming`/`wantFramingByProfile` (`thesis/results/v9/integration/gateway/ca_handler_test.go:142-144` e `:280`) -- Classic usa content-length, os outros 3 perfis usam chunked. **Diferença zero nos 4 perfis** -- esta é a única das três verificações desta seção sem nenhum resíduo de arredondamento, porque a sobrecarga de framing é um inteiro exato, não uma média estatística sobre muitas amostras.

### 2.5 Invariantes estruturais por termo (Classic < PQC < Hybrid)

| Termo | Classic | PQC | Hybrid | Classic<PQC<Hybrid? |
|---|---:|---:|---:|---|
| mTLS (handshake) | 18.750 | 129.636 | 144.474 | SIM |
| JWT (apenas assinatura) | 6.655,88 | 86.033,92 | 92.690,08 | SIM |
| JWK (chave crua) | 1.536 | 8.320 | 9.856 | SIM |
| PKI (certificados de CA) | 7.130,00 | 32.440 | 39.182,00 | SIM |

**Checagem separada envolvendo Control (Hybrid >= Control, por termo):**

| Termo | Hybrid | Control | Hybrid >= Control? |
|---|---:|---:|---|
| mTLS (handshake) | 144.474 | 101.694 | SIM |
| JWT (apenas assinatura) | 92.690,08 | 92.690,08 | SIM |
| JWK (chave crua) | 9.856 | 9.856 | SIM |
| PKI (certificados de CA) | 39.182,00 | 37.768 | SIM |

**Divergência de bytes de handshake por conexão -- confirmada zero.** `handshake_bytes_alert.json`: 2880 conexões mTLS auditadas, **0 divergentes**.

## 3. Control por termo: onde fica abaixo e onde fica acima do PQC (sem contradição entre texto e tabela)

O total de Control fica abaixo do total de PQC (razões da Seção 2.1), mas isso **não** é verdade termo a termo -- recalculado aqui diretamente dos 4 termos da Seção 2.2, sem copiar nenhum número pronto:

| Termo | Control | PQC | Control − PQC |
|---|---:|---:|---:|
| mTLS (handshake) | 101.694 | 129.636 | -27.942 |
| JWT (apenas assinatura) | 92.690,08 | 86.033,92 | +6.656,16 |
| JWK (chave crua) | 9.856 | 8.320 | +1.536 |
| PKI (certificados de CA) | 37.768 | 32.440 | +5.328 |
| **Total** | **242.008,08** | **256.429,92** | **-14.421,84** |

**Leitura correta, por termo:** Control fica **abaixo** do PQC somente no termo mTLS (cadeia de certificado ainda baseada em RSA no lado do Control contra a cadeia ML-DSA-65 pura do PQC) -- e fica **acima** do PQC nos 3 outros termos (JWT, JWK, PKI), onde ambos usam construção de assinatura equivalente mas Control carrega material adicional que o PQC puro não carrega. O saldo final negativo (Control abaixo do PQC no total) vem inteiramente da economia no termo mTLS, que é grande o suficiente para compensar os 3 acréscimos somados.

## 4. Resultados de latência

### 4.1 T_fluxo por célula (mediana, desvio padrão, mínimo, máximo; n=10 por célula, janela única)

| Instalação | Cenário | Perfil | Mediana | Desvio padrão | Mínimo | Máximo |
|---|---|---|---:|---:|---:|---:|
| sa-east-1 | L0-sa-east-1 | Classic | 2.357,9 ms | 50,96 ms | 2.270,3 ms | 2.439,9 ms |
| sa-east-1 | L0-sa-east-1 | PQC | 2.288,9 ms | 142,19 ms | 1.919,2 ms | 2.425,9 ms |
| sa-east-1 | L0-sa-east-1 | Hybrid | 2.564,6 ms | 83,58 ms | 2.406,0 ms | 2.712,0 ms |
| sa-east-1 | L123 | Classic | 10.879,8 ms | 59,92 ms | 10.811,9 ms | 11.021,8 ms |
| sa-east-1 | L123 | PQC | 11.143,3 ms | 65,40 ms | 11.052,0 ms | 11.253,6 ms |
| sa-east-1 | L123 | Hybrid | 11.349,1 ms | 77,24 ms | 11.255,7 ms | 11.502,8 ms |
| sa-east-1 | L219 | Classic | 17.683,3 ms | 50,11 ms | 17.608,2 ms | 17.776,4 ms |
| sa-east-1 | L219 | PQC | 18.105,6 ms | 46,77 ms | 18.050,1 ms | 18.197,8 ms |
| sa-east-1 | L219 | Hybrid | 18.396,5 ms | 107,86 ms | 18.203,5 ms | 18.483,4 ms |
| sa-east-1 | L325 | Classic | 25.559,2 ms | 178,49 ms | 25.311,2 ms | 25.801,6 ms |
| sa-east-1 | L325 | PQC | 26.136,5 ms | 205,24 ms | 25.934,8 ms | 26.612,2 ms |
| sa-east-1 | L325 | Hybrid | 26.531,6 ms | 305,82 ms | 26.064,8 ms | 27.131,4 ms |
| us-east-1 | L0-us-east-1 | Classic | 3.817,0 ms | 60,52 ms | 3.790,9 ms | 3.935,3 ms |
| us-east-1 | L0-us-east-1 | PQC | 4.040,4 ms | 81,17 ms | 3.943,0 ms | 4.165,9 ms |
| us-east-1 | L0-us-east-1 | Hybrid | 4.208,1 ms | 117,28 ms | 4.044,0 ms | 4.409,6 ms |
| us-east-1 | L14 | Classic | 4.744,6 ms | 48,97 ms | 4.694,9 ms | 4.864,6 ms |
| us-east-1 | L14 | PQC | 5.032,4 ms | 46,92 ms | 4.942,2 ms | 5.085,5 ms |
| us-east-1 | L14 | Hybrid | 5.202,5 ms | 93,31 ms | 5.053,9 ms | 5.363,9 ms |
| ap-northeast-1 | L0-ap-northeast-1 | Classic | 5.786,2 ms | 52,76 ms | 5.688,1 ms | 5.857,5 ms |
| ap-northeast-1 | L0-ap-northeast-1 | PQC | 6.248,6 ms | 82,15 ms | 6.141,1 ms | 6.394,4 ms |
| ap-northeast-1 | L0-ap-northeast-1 | Hybrid | 6.616,3 ms | 155,70 ms | 6.328,1 ms | 6.814,4 ms |
| ap-northeast-1 | L30 | Classic | 8.214,5 ms | 151,14 ms | 8.003,7 ms | 8.518,7 ms |
| ap-northeast-1 | L30 | PQC | 8.769,4 ms | 102,18 ms | 8.540,3 ms | 8.864,0 ms |
| ap-northeast-1 | L30 | Hybrid | 9.028,6 ms | 125,66 ms | 8.859,3 ms | 9.233,5 ms |

**Perfil Control, por rota (tabela separada):**

| Instalação | Cenário | Mediana | Desvio padrão | Mínimo | Máximo |
|---|---|---:|---:|---:|---:|
| sa-east-1 | L0-sa-east-1 | 2.472,1 ms | 49,94 ms | 2.408,3 ms | 2.550,5 ms |
| sa-east-1 | L123 | 11.263,4 ms | 78,84 ms | 11.145,7 ms | 11.416,7 ms |
| sa-east-1 | L219 | 18.302,0 ms | 117,71 ms | 18.153,5 ms | 18.513,0 ms |
| sa-east-1 | L325 | 26.523,1 ms | 224,60 ms | 26.211,8 ms | 26.878,4 ms |
| us-east-1 | L0-us-east-1 | 4.247,7 ms | 137,51 ms | 4.067,2 ms | 4.529,6 ms |
| us-east-1 | L14 | 5.145,7 ms | 90,21 ms | 5.067,7 ms | 5.316,7 ms |
| ap-northeast-1 | L0-ap-northeast-1 | 6.634,2 ms | 192,58 ms | 6.295,2 ms | 6.786,1 ms |
| ap-northeast-1 | L30 | 9.018,1 ms | 166,88 ms | 8.718,3 ms | 9.270,3 ms |

### 4.2 Ordem das medianas por rota e diferença percentual (PQC vs. Classic, Hybrid vs. PQC)

*Nota de correção: a versão anterior desta tabela incluía Control na coluna "Ordem", misturado com a comparação central -- corrigido aqui para listar somente Classic/PQC/Hybrid, consistente com o restante desta seção (Control nunca fez parte do cálculo de diferença percentual, só da ordem exibida).*

| Rota | Ordem (menor -> maior mediana) | PQC vs. Classic | Hybrid vs. PQC |
|---|---|---:|---:|
| L0-sa-east-1 | PQC < Classic < Hybrid | -2,93% | +12,04% |
| L123 | Classic < PQC < Hybrid | +2,42% | +1,85% |
| L219 | Classic < PQC < Hybrid | +2,39% | +1,61% |
| L325 | Classic < PQC < Hybrid | +2,26% | +1,51% |
| L0-us-east-1 | Classic < PQC < Hybrid | +5,85% | +4,15% |
| L14 | Classic < PQC < Hybrid | +6,07% | +3,38% |
| L0-ap-northeast-1 | Classic < PQC < Hybrid | +7,99% | +5,88% |
| L30 | Classic < PQC < Hybrid | +6,75% | +2,96% |

**Contagens agregadas (8 rotas):** Hybrid > PQC (mediana) em **8/8** rotas; PQC > Classic (mediana) em **7/8** rotas.

### 4.3 Sobreposição de intervalo [mínimo;máximo] por rota (Classic×PQC e PQC×Hybrid)

| Rota | Classic×PQC sobrepõem? | PQC×Hybrid sobrepõem? |
|---|---|---|
| L0-sa-east-1 | SIM | SIM |
| L123 | NÃO | NÃO |
| L219 | NÃO | NÃO |
| L325 | NÃO | SIM |
| L0-us-east-1 | NÃO | SIM |
| L14 | NÃO | SIM |
| L0-ap-northeast-1 | NÃO | SIM |
| L30 | NÃO | SIM |

**Contagens agregadas:** Classic×PQC se sobrepõem em **1/8** rotas; PQC×Hybrid se sobrepõem em **6/8** rotas. Onde os intervalos se sobrepõem, a ordem das medianas naquela rota específica não é lida como robusta somente a partir desta tabela -- ver análise de significância na Seção 5.

### 4.4 Inversão em L0-sa-east-1 (PQC com mediana abaixo de Classic): os 10 valores reais, sem causa atribuída

10 valores reais de T_fluxo (segundos), ordenados, nesta rota:

- **Classic:** 2,270337, 2,320785, 2,327829, 2,341451, 2,353749, 2,362013, 2,362613, 2,401444, 2,425318, 2,439924
- **PQC:** 1,919165, 2,271329, 2,274855, 2,279327, 2,282256, 2,295532, 2,342916, 2,367430, 2,418240, 2,425901

**Mediana PQC com os 10 valores:** 2,288894s. **Mediana PQC excluindo o único valor mais baixo** (1,919165s): 2,295532s -- variação de 6,6ms ao remover esse valor. **Mediana Classic:** 2,357881s. A mediana de PQC permanece abaixo da de Classic mesmo excluindo o valor mais baixo -- a inversão não depende inteiramente de um único valor extremo; os demais 9 valores de PQC, no conjunto, também ficam no mesmo patamar ou abaixo do grosso da distribuição de Classic nesta rota específica.

**Ordem de execução dos blocos de perfil nesta rota** (`manifest.route_orders["L0-sa-east-1"]`): Control -> Classic -> PQC -> Hybrid. PQC roda como o 3º dos 4 blocos nesta rota, depois de Classic -- os dados não mostram, por si só, nenhuma causa específica para a inversão além do que está listado acima; nenhuma causa é proposta além do que os valores e a ordem mostram diretamente.

## 5. Significância estatística dos contrastes entre perfis (análise exploratória)

**Declaração explícita de escopo:** esta é uma análise **EXPLORATÓRIA, não pré-registrada** -- os 16 contrastes principais abaixo (Classic×PQC e PQC×Hybrid, por par adjacente, nas 8 rotas) foram **escolhidos após a descrição dos dados** nas Seções 4.1-4.4 desta mesma versão do relatório, não antes da coleta. Não tem o peso de uma análise confirmatória -- quantifica e testa o que já foi observado descritivamente, não valida uma hipótese fixada de antemão.

### 5.1 Testes por rota -- Classic×PQC e PQC×Hybrid (16 testes principais)

Mann-Whitney U exato, bilateral, n=10 por grupo (medição contínua, sem empates esperados). p-valor ajustado por Holm sobre o conjunto dos 16 testes principais abaixo -- família PRÓPRIA, separada dos 16 testes com Control (Seção 5.2). Hodges-Lehmann: mediana de todas as diferenças pareadas (não a diferença das medianas, reportada em separado); IC 95% via bootstrap, semente fixa, 10.000 reamostragens (ver nota de reprodutibilidade abaixo). Delta de Cliff escolhido como medida de magnitude de efeito (em vez de probabilidade de superioridade bruta) por ser a convenção mais padrão em comparações não-paramétricas de amostras pequenas -- é numericamente equivalente a 2×P(superioridade)-1, então a informação de probabilidade de superioridade continua recuperável a partir dele.

*Nota: o menor p bruto matematicamente possível no Mann-Whitney exato bilateral com n=10 por grupo é 2/C(20,10) = 1.08e-05 -- confirmado rodando o próprio teste sobre dois grupos sem nenhuma sobreposição (separação total), não só calculado analiticamente. Por isso nenhuma célula de "p bruto" nas tabelas desta seção mostra "0,0000" (que sugeriria p=0 exato, impossível aqui) -- valores abaixo da resolução de 4 casas decimais aparecem como "<0,0001".*

**Convenção de sinal, válida nas Seções 5.1 e 5.2:** "Dif" = Mediana B − Mediana A; Delta de Cliff positivo significa B sistematicamente maior que A, negativo significa o contrário. Consistente célula a célula com as linhas abaixo (ex.: L0-sa-east-1, PQC vs. Classic -- aqui B=PQC, A=Classic -- tem Dif negativo E Delta de Cliff negativo, ambos concordando que PQC ficou abaixo de Classic nesta rota).

| Rota | Par | Mediana A (referência, ms) | Mediana B (comparado, ms) | Dif (ms) | Dif (%) | p bruto | p Holm (16) | Hodges-Lehmann (ms) | IC 95% bootstrap (ms) | Delta de Cliff | Significante (Holm, α=0,05)? |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| L0-sa-east-1 | PQC vs. Classic | 2.357,9 | 2.288,9 | -69,0 | -2,93% | 0,2176 | 0,2176 | -54,7 | [-105,9;11,9] | -0,340 | NÃO |
| L123 | PQC vs. Classic | 10.879,8 | 11.143,3 | 263,4 | 2,42% | <0,0001 | 0,0002 | 253,9 | [198,3;319,2] | 1,000 | SIM |
| L219 | PQC vs. Classic | 17.683,3 | 18.105,6 | 422,3 | 2,39% | <0,0001 | 0,0002 | 421,4 | [386,3;462,5] | 1,000 | SIM |
| L325 | PQC vs. Classic | 25.559,2 | 26.136,5 | 577,3 | 2,26% | <0,0001 | 0,0002 | 622,3 | [454,9;800,5] | 1,000 | SIM |
| L0-us-east-1 | PQC vs. Classic | 3.817,0 | 4.040,4 | 223,4 | 5,85% | <0,0001 | 0,0002 | 193,9 | [138,8;274,7] | 1,000 | SIM |
| L14 | PQC vs. Classic | 4.744,6 | 5.032,4 | 287,9 | 6,07% | <0,0001 | 0,0002 | 275,0 | [222,7;311,9] | 1,000 | SIM |
| L0-ap-northeast-1 | PQC vs. Classic | 5.786,2 | 6.248,6 | 462,4 | 7,99% | <0,0001 | 0,0002 | 471,5 | [410,8;544,6] | 1,000 | SIM |
| L30 | PQC vs. Classic | 8.214,5 | 8.769,4 | 554,8 | 6,75% | <0,0001 | 0,0002 | 552,6 | [425,2;661,6] | 1,000 | SIM |
| L0-sa-east-1 | Hybrid vs. PQC | 2.288,9 | 2.564,6 | 275,7 | 12,04% | <0,0001 | 0,0003 | 240,0 | [163,8;310,3] | 0,960 | SIM |
| L123 | Hybrid vs. PQC | 11.143,3 | 11.349,1 | 205,9 | 1,85% | <0,0001 | 0,0002 | 204,1 | [146,1;282,0] | 1,000 | SIM |
| L219 | Hybrid vs. PQC | 18.105,6 | 18.396,5 | 290,9 | 1,61% | <0,0001 | 0,0002 | 274,1 | [138,4;340,7] | 1,000 | SIM |
| L325 | Hybrid vs. PQC | 26.136,5 | 26.531,6 | 395,1 | 1,51% | 0,0052 | 0,0104 | 395,4 | [149,4;655,2] | 0,720 | SIM |
| L0-us-east-1 | Hybrid vs. PQC | 4.040,4 | 4.208,1 | 167,7 | 4,15% | 0,0005 | 0,0015 | 174,7 | [81,7;278,1] | 0,860 | SIM |
| L14 | Hybrid vs. PQC | 5.032,4 | 5.202,5 | 170,1 | 3,38% | 0,0001 | 0,0006 | 189,9 | [114,4;255,8] | 0,920 | SIM |
| L0-ap-northeast-1 | Hybrid vs. PQC | 6.248,6 | 6.616,3 | 367,7 | 5,88% | 0,0001 | 0,0006 | 332,5 | [178,3;425,9] | 0,920 | SIM |
| L30 | Hybrid vs. PQC | 8.769,4 | 9.028,6 | 259,2 | 2,96% | <0,0001 | 0,0002 | 298,4 | [181,7;396,6] | 0,980 | SIM |

### 5.2 Contrastes com Control -- Control×Hybrid e Control×PQC (16 testes, FORA DO ESCOPO da tese)

**Fora do escopo central desta tese** -- consistente com a separação de Control das comparações principais (Seção 2). Reportados aqui só por completude metodológica, família de Holm PRÓPRIA (separada dos 16 testes principais da Seção 5.1 -- nunca misturada no mesmo ajuste).

| Rota | Par | Mediana A (referência, ms) | Mediana B (comparado, ms) | Dif (ms) | Dif (%) | p bruto | p Holm (16) | Hodges-Lehmann (ms) | IC 95% bootstrap (ms) | Delta de Cliff | Significante (Holm, α=0,05)? |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| L0-sa-east-1 | Control vs. Hybrid | 2.564,6 | 2.472,1 | -92,5 | -3,61% | 0,0185 | 0,1483 | -78,0 | [-141,4;-19,2] | -0,620 | NÃO |
| L123 | Control vs. Hybrid | 11.349,1 | 11.263,4 | -85,7 | -0,76% | 0,0288 | 0,2016 | -78,5 | [-143,4;-11,5] | -0,580 | NÃO |
| L219 | Control vs. Hybrid | 18.396,5 | 18.302,0 | -94,5 | -0,51% | 0,5787 | 1,0000 | -32,8 | [-158,1;51,0] | -0,160 | NÃO |
| L325 | Control vs. Hybrid | 26.531,6 | 26.523,1 | -8,5 | -0,03% | 0,9705 | 1,0000 | 7,1 | [-290,2;254,0] | 0,020 | NÃO |
| L0-us-east-1 | Control vs. Hybrid | 4.208,1 | 4.247,7 | 39,5 | 0,94% | 0,9705 | 1,0000 | -6,2 | [-105,9;119,9] | -0,020 | NÃO |
| L14 | Control vs. Hybrid | 5.202,5 | 5.145,7 | -56,9 | -1,09% | 0,2799 | 1,0000 | -48,9 | [-126,5;43,9] | -0,300 | NÃO |
| L0-ap-northeast-1 | Control vs. Hybrid | 6.616,3 | 6.634,2 | 17,9 | 0,27% | 0,9118 | 1,0000 | 8,7 | [-182,4;137,3] | 0,040 | NÃO |
| L30 | Control vs. Hybrid | 9.028,6 | 9.018,1 | -10,4 | -0,12% | 0,6842 | 1,0000 | -18,0 | [-159,8;100,1] | -0,120 | NÃO |
| L0-sa-east-1 | Control vs. PQC | 2.288,9 | 2.472,1 | 183,2 | 8,00% | <0,0001 | 0,0007 | 158,9 | [101,8;224,0] | 0,960 | SIM |
| L123 | Control vs. PQC | 11.143,3 | 11.263,4 | 120,2 | 1,08% | 0,0007 | 0,0094 | 126,7 | [58,1;196,1] | 0,840 | SIM |
| L219 | Control vs. PQC | 18.105,6 | 18.302,0 | 196,4 | 1,08% | <0,0001 | 0,0007 | 194,0 | [116,6;313,9] | 0,960 | SIM |
| L325 | Control vs. PQC | 26.136,5 | 26.523,1 | 386,6 | 1,48% | 0,0015 | 0,0150 | 372,3 | [195,8;583,8] | 0,800 | SIM |
| L0-us-east-1 | Control vs. PQC | 4.040,4 | 4.247,7 | 207,2 | 5,13% | 0,0021 | 0,0188 | 175,9 | [93,1;291,9] | 0,780 | SIM |
| L14 | Control vs. PQC | 5.032,4 | 5.145,7 | 113,2 | 2,25% | 0,0001 | 0,0018 | 125,6 | [65,2;218,9] | 0,920 | SIM |
| L0-ap-northeast-1 | Control vs. PQC | 6.248,6 | 6.634,2 | 385,6 | 6,17% | 0,0007 | 0,0094 | 350,1 | [117,4;468,8] | 0,840 | SIM |
| L30 | Control vs. PQC | 8.769,4 | 9.018,1 | 248,8 | 2,84% | 0,0007 | 0,0094 | 259,7 | [146,1;406,2] | 0,840 | SIM |

### 5.3 Teste agregado entre rotas

**Teste do sinal bilateral exato** (contagem de rotas, entre as 8, onde a mediana do 2º perfil supera a do 1º):

| Comparação | Rotas onde supera | p-valor (sinal, exato) |
|---|---:|---:|
| PQC > Classic | 7/8 | 0,0703 |
| Hybrid > PQC | 8/8 | 0,0078 |

**Wilcoxon signed-rank sobre as 8 diferenças percentuais de mediana por rota** (não um teste por execução individual -- um valor por rota, 8 no total):

| Comparação | p-valor (Wilcoxon signed-rank) |
|---|---:|
| PQC vs. Classic (8 diferenças %) | 0,0547 |
| Hybrid vs. PQC (8 diferenças %) | 0,0078 |

### 5.4 Leitura factual (sem afirmar robustez onde o teste não sustenta)

**PQC vs. Classic:** significativo após Holm (α=0,05) em **7/8** rotas; não significativo nas outras 1/8. **Hybrid vs. PQC:** significativo após Holm em **8/8** rotas; não significativo nas outras 0/8.

**Inversão em L0-sa-east-1 (Seção 4.4, PQC com mediana abaixo de Classic):** pelo teste de Mann-Whitney exato com correção de Holm sobre os 16 testes principais, essa diferença **NÃO é** estatisticamente significativa (p bruto=0,2176, p Holm=0,2176, delta de Cliff=-0,340). Nenhuma afirmação de robustez é feita para nenhum contraste cujo p-valor ajustado por Holm não exclua a hipótese nula a α=0,05 -- as células marcadas "NÃO" nas tabelas acima permanecem lidas como não-significativas, não como "quase significativas" ou similar.

**Leitura dos testes agregados (Seção 5.3), sem arredondar a interpretação:** para PQC vs. Classic, **NENHUM** dos dois testes agregados atinge α=0,05 -- teste do sinal p=0,0703, Wilcoxon signed-rank p=0,0547 (ambos acima de 0,05). Para Hybrid vs. PQC, os dois atingem α=0,05 -- sinal p=0,0078, Wilcoxon p=0,0078.

**As 8 rotas NÃO são estatisticamente independentes entre si** -- compartilham apenas 3 instalações físicas (`sa-east-1`, `us-east-1`, `ap-northeast-1`), cada uma hospedando várias rotas simultaneamente (ex.: `L0-sa-east-1`, `L123`, `L219` e `L325` rodam todas a partir do mesmo servidor físico em `sa-east-1`). Por isso, os testes agregados entre rotas desta seção (teste do sinal, Wilcoxon) são **apenas INDICATIVOS** -- não constituem uma inferência formal válida sob a suposição de independência que esses testes exigem. Os 32 testes por rota (Seções 5.1/5.2) não dependem dessa suposição entre rotas (cada um compara só as 10 execuções de um perfil contra as 10 de outro, dentro da MESMA rota) -- a ressalva de independência se aplica apenas aos agregados desta seção, não aos testes por rota.

**Ressalva metodológica sobre T_fluxo (adicionada após investigação exploratória "Degrau 1" -- ver `thesis/results/v9/analise_origem/RELATORIO_ORIGEM.md`):** o campo "T_fluxo" usado nesta seção mede o tempo de execução ponta-a-ponta observado pelo processo orquestrador (via SSH, do host de controle até o host cliente), não apenas as chamadas HTTP entre cliente e servidor. A sobrecarga de SSH e o cold-start do processo cliente são comuns a todos os perfis (não introduzem viés entre perfis). Também inclui um custo de preparação de chave de assinatura RSA (~27ms, medido localmente para o tamanho de chave RSA-2048 real da campanha, Decisão 113) que depende do perfil: pago por Classic, Hybrid e Control, não pago por PQC, a cada execução -- este custo específico está presente nas diferenças PQC vs. Classic e Hybrid vs. PQC reportadas nesta seção e na Seção 4.2, mas sua magnitude é pequena em relação a todas as diferenças já reportadas (a menor delas, 167,7ms, é ~6x maior que o viés) -- uma estimativa de sensibilidade (Degrau 1, Item 8) confirma que nenhuma das 16 comparações publicadas troca de sinal ao remover este viés específico.

### 5.5 Ressalva de desenho (deriva de rede dentro do bloco sequencial de cada rota)

Dentro de cada rota, os 4 blocos de perfil rodam **sequencialmente** (ordem sorteada por rota, semente `20261107`, já documentada na Seção 1 -- `route_orders`) -- então deriva de rede ao longo do tempo (ex.: variação de condições de rede entre o início e o fim da janela daquela rota específica) pode contribuir para parte das diferenças observadas entre perfis DENTRO da mesma rota. A aleatorização da ordem ENTRE rotas (cada rota tem uma ordem potencialmente diferente, Seção 1) reduz, mas **não elimina**, esse efeito -- não há controle por bloco dentro de uma única rota (os 4 perfis não rodam entrelaçados/alternados dentro da mesma rota, rodam em 4 blocos consecutivos).

**Ordem real dos blocos de perfil, por rota** (`manifest.route_orders`, dado bruto, sem interpretação adicional):

| Rota | Ordem dos blocos (1º -> 2º -> 3º -> 4º) |
|---|---|
| L0-sa-east-1 | Control -> Classic -> PQC -> Hybrid |
| L123 | Classic -> Hybrid -> Control -> PQC |
| L219 | Hybrid -> Control -> Classic -> PQC |
| L325 | PQC -> Hybrid -> Classic -> Control |
| L0-us-east-1 | Control -> Classic -> Hybrid -> PQC |
| L14 | Hybrid -> PQC -> Classic -> Control |
| L0-ap-northeast-1 | Hybrid -> Classic -> Control -> PQC |
| L30 | PQC -> Classic -> Hybrid -> Control |

**Nota de reprodutibilidade do bootstrap:** semente fixa `20261116`, 10.000 reamostragens, `numpy.random.default_rng` -- nunca semente de sistema/relógio. Rodar este mesmo script novamente reproduz exatamente os mesmos intervalos de confiança.

## 6. Critérios técnicos (1-7)

| Critério | Resultado |
|---|---|
| 1 (tamanhos por mensagem (campanha)) | PASS |
| 2 (initcwnd real (campanha)) | PASS |
| 3 (zero erros na rota mais distante (campanha)) | PASS |
| 4 (contagens do fluxo (campanha)) | PASS |
| 5 (zero erros) | PASS |
| 6 (instrumentacao completa + asserções (campanha)) | PASS |
| 7 (sanidade de latencia por rota (campanha)) | **FAIL** |

### 6.1 Critério 7 -- RTT nominal vs. medido, por rota (exceção documentada em L30)

| Rota | RTT nominal (ms) | RTT medido, probe (ms) | RTT medido, pcap (ms) | Dentro de ±10%? |
|---|---:|---:|---:|---|
| L0-sa-east-1 | 0 | 0,160 | 0,129 | SIM |
| L123 | 123 | 122,618 | 122,642 | SIM |
| L219 | 219 | 220,175 | 220,151 | SIM |
| L325 | 325 | 333,501 | 323,406 | SIM |
| L0-us-east-1 | 0 | 0,264 | 0,287 | SIM |
| L14 | 14 | 15,076 | 14,759 | SIM |
| L0-ap-northeast-1 | 0 | 0,144 | 0,105 | SIM |
| L30 | 30 | 34,079 | 33,423 | **NÃO -- exceção documentada** |

*Rotas `L0-*` são co-localizadas (RTT nominal cadastrado como 0); o avaliador real aplica a essas rotas uma checagem de tolerância diferente da percentual ±10% usada nas demais, nunca uma divisão por zero -- "SIM" ali reflete o resultado real de `evaluate_criteria.py`, não um cálculo percentual sobre um nominal de 0.*

**Decisão sobre L30 (não corrigida, não recalibrada):** aceita como exceção documentada. O RTT real de `L30` mede ~33,4-34,1ms (canal probe e canal pcap concordam entre si) contra 30ms nominais cadastrados no baseline de topologia -- 11-14% fora da tolerância de ±10% que o critério exige. O baseline de medição não foi alterado. A comparação entre perfis (Classic/PQC/Control/Hybrid, Seção 4) ocorre sempre DENTRO da mesma rota -- cada perfil roda sob o mesmo RTT real em L30, então esta exceção não compromete nenhuma comparação entre perfis, apenas o critério de sanidade absoluta desta rota específica contra seu valor nominal cadastrado.

### 6.2 Retries de transporte: 0 (zero)

`retries_report.json`: `total_retries=0`, `por_celula={}` -- nenhuma das 320 execuções oficiais precisou de retry de transporte HTTP/mTLS.

## 7. Canal interno AS<->RS (permanece clássico em todos os 4 perfis)

**Mecanismo, confirmado por código (não assumido):** `thesis/results/v9/integration/gateway/business_server.go:246-250` -- `attachInternalCallerCarveOut` monta um `cfg.GetConfigForClient` cuja única condição é `hello.ServerName == internalCallerSNI` (`"matls-api.local"`, linha 164); quando verdadeira, retorna sempre o MESMO `internalCfg`, cujo `CurvePreferences = []tls.CurveID{tls.CurveP521, tls.CurveP384, tls.CurveP256}` (linha 242) é um valor fixo, sem nenhum `if`/`switch` sobre `profile` dentro do próprio closure. `business_server.go:104` confirma o mesmo do lado do enforcement em runtime: só aplica a curva ESPERADA DO PERFIL a conexões que NÃO sejam a chamada interna -- por construção, válido para os 4 perfis.

**Evidência real desta campanha (320 execuções), fonte completa (não apenas o último bloco de perfil):** `piloto_combined.log` é um log continuamente anexado durante toda a janela (sobrevive ao reinício de container entre blocos de perfil, ao contrário de `full_container_logs`) -- **2.240 conexões reais** com `sni="matls-api.local"`, **100% com curve=CurveP256**, no conjunto central Classic/PQC/Hybrid: Classic=560, Hybrid=560, PQC=560. **Perfil Control, separado:** 560 conexões, mesma curva, mesmo resultado (100% conforme).

**Evidência corroborante de um piloto real anterior (18 execuções, MESMO código e MESMAS imagens Docker desta campanha, rodado antes dela na mesma conta/infraestrutura):** **126 conexões reais** com `sni="matls-api.local"`, **100% com curve=CurveP256**, no mesmo conjunto central Classic/PQC/Hybrid: Classic=42, Hybrid=42, PQC=21. **Perfil Control, separado:** 21 conexões, mesma curva. Duas coletas reais independentes, mesmo mecanismo de código, mesmo resultado -- 0 violações em qualquer das duas.

## 8. Custo (estimativa por fórmula -- NUNCA o valor real cobrado)

Fórmula de `cost_tracker.CostTracker` (frota real: 12 instâncias -- 1 `t4g.micro` + 11 `m7i-flex.large`, 12 EIPs), `window_start_utc` derivado da primeira linha real de `cost_tracker.jsonl` (`2026-11-15T04:17:09Z`). **Todo valor abaixo é uma ESTIMATIVA POR FÓRMULA, nunca "custo final" nem um valor de fato cobrado -- o valor real e definitivo é o que aparece no AWS Billing/Cost Explorer da conta, nunca esta fórmula local.**

**A frota foi parada via `StopInstances` ("User initiated") antes de `2026-11-16T04:26:00Z`** -- confirmado por `describe-instances` nas 7 regiões (estado `stopped` nas 12 instâncias, nunca `terminated`). **O horário exato de cada parada não pôde ser determinado por API:** `cloudtrail:LookupEvents` e `cloudwatch:GetMetricStatistics` retornaram `AccessDeniedException` (a mesma política de privilégio mínimo já documentada nunca incluiu permissão de trilha/billing/métricas) -- reconfirmado agora, de novo, lendo o campo BRUTO `StateTransitionReason` diretamente nas 12 instâncias (7 regiões): o valor é, literalmente e sem exceção, a string `"User initiated"` -- sem parênteses, sem data, sem hora embutida -- nas 12. `describe-instances` não traz timestamp de transição de estado em nenhum campo. Usado aqui o limite superior conservador já confirmado -- se a parada real ocorreu antes disso (certo que ocorreu), usar este instante como corte superestima levemente o tempo de compute cobrado, nunca subestima.

**`cost_tracker.py` não modela parada de instância** -- foi desenhado assumindo a frota continuamente ligada desde `window_start_utc`; sem o ajuste abaixo, a fórmula pura continuaria contando custo de compute que já não está mais sendo cobrado desde a parada, superestimando o valor real a partir desse instante.

| Momento | Timestamp (UTC) | Estimativa por fórmula acumulada |
|---|---|---:|
| última leitura automática registrada (cost_tracker.jsonl) -- fórmula contínua, frota ainda ligada | 2026-11-15T23:36:12Z | US\$27,69 |
| fim da janela oficial (manifest.window_end_utc) -- fórmula contínua, frota ainda ligada | 2026-11-16T00:06:40Z | US\$28,42 |
| fim da coleta dos critérios dedicados (último evento real nos logs do gateway) -- fórmula contínua, frota ainda ligada | 2026-11-16T00:22:57Z | US\$28,81 |
| agora (momento em que este relatório foi gerado) -- fórmula EM DUAS FASES: contínua até a frota parar, só EBS+EIP depois | 2026-11-16T16:26:31Z | US\$35,85 |

**Taxa real da frota PARADA, reconfirmada aqui** (mesmas constantes de `cost_tracker.py`, 12 volumes gp3 de 30GB cada + 12 EIPs ainda associados, 0 compute): EBS US\$1,04/dia + EIP US\$1,44/dia = **US\$2,48/dia** (US\$0,1034/h). Aplicada por 12,01h desde a parada até a leitura "agora" acima.

- **cost_stop:** nunca acionado (`None`); teto desta fase: aviso US\$70 / parada US\$90 -- ambos já sem sentido prático agora que a frota está parada (não é mais a formula contínua que se aplica).
- **Integridade dos dados brutos:** 720/720 arquivos copiados do controle, verificados por sha256 local, 0 divergências.

## 9. Transparência e limites de escopo

- **Arquivos catalisadores RSA-4096 da CA do perfil Controle não foram migrados** -- o perfil Controle reutiliza a raiz/emissora RSA clássica para sua cadeia de certificados, por desenho.
- **O total de Controle fica abaixo do total de PQC, mas não termo a termo** -- ver a reconciliação completa na Seção 3: Controle fica abaixo do PQC somente no termo mTLS, e acima nos outros 3 termos.
- **Exceção do critério 7 em L30**, documentada e aceita sem recalibração do baseline (Seção 6.1).
- **Conexões internas AS->RS ficam fora da equação OPINsize** -- o termo mede apenas o que atravessa o canal client-facing (gateway mTLS); o canal interno permanece clássico e não migrado, por desenho (Seção 7).
- **Ressalva de reprodutibilidade:** pacotes do sistema operacional (AMI e `dnf`) instalados no momento do provisionamento desta campanha não têm suas versões exatas re-fixadas por nenhum manifesto além do que o documento de fatos dos hosts (auditoria somente-leitura, entregue separadamente) registrou -- uma reconstrução futura a partir de uma AMI mais nova pode obter versões de pacote diferentes das observadas aqui, sem que isso indique nenhuma mudança no código/binários desta tese (esses seguem pinados, verificados conforme a Seção 10).

## 10. Reprodutibilidade

**Integridade das imagens Docker, por imagem, com a garantia real de cada uma (não uma frase genérica):**

- **`gateway` e `proxy`:** binários **bit a bit idênticos** ao pin registrado -- sha256 do binário compilado confere exatamente contra o valor pinado, sem nenhuma tolerância.
- **`measure`:** equivalência, **não** bit a bit -- os binários `gateway`/`proxy` embutidos dentro da imagem são idênticos ao pin, as camadas estáveis da imagem (posições 0 e 4 do `rootfs_layers`) e o `config_subset` são idênticos; as camadas voláteis (posições 1, 2 e 3) variam de build para build por um timestamp que o BuildKit embute, não por diferença de conteúdo -- documentado desde a Decisão 159.
- **`auth`, `mongo_seed`, `mockapi`:** identidade por `rootfs_layers`+`config_subset`, reconstrução **equivalente**, não bit a bit -- as causas reais, já identificadas, de não-determinismo byte a byte entre builds/sistemas operacionais diferentes são: normalização de fim de linha (CRLF/LF), material de chave efêmera gerado pelo próprio AS a cada execução (nunca persistido, sempre de tamanho/tipo fixo), e resolução de dependências opcionais específicas de plataforma do `npm` (variantes de pacote por sistema operacional de build, nunca uma dependência de runtime real).
- **Gate de entrega (todas as imagens):** verificado por conteúdo (`rootfs_layers`, `config_subset`, `binary_sha256` dos binários embutidos), nunca por `tar_sha256` -- dois `docker save` do EXATO mesmo conteúdo geram arquivos `.tar` com hashes SHA-256 diferentes entre si (instabilidade do próprio formato tar/metadados de empacotamento, não do conteúdo), então comparar por `tar_sha256` produziria falsos negativos.

- Todo número deste documento foi lido ou computado por `thesis/results/v9/campaign/scripts/generate_final_report_oficial_conta_nova.py`, a partir de `thesis/results/v9/campaign_oficial_conta_nova_raw/`, `thesis/results/v9/campaign_oficial_conta_nova_organized/`, e de uma verificação externa ao pipeline rodada ao vivo (`evaluate_criteria.expected_handshake_bytes`, Seção 2.2) -- nenhum valor foi digitado manualmente.
- Este relatório foi auditado de forma independente (agente separado, sem acesso ao texto deste documento como fonte, apenas aos dados organizados/manifesto) antes de sua entrega final -- tabela de conferência na Decisão correspondente em `DECISIONS.md`.

