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

| Perfil | OPINsize (bytes) | Razão vs. Classic |
|---|---:|---:|
| Classic | 34.071,88 | 1,00x |
| PQC | 256.429,92 | 7,53x |
| Control | 242.008,08 | 7,10x |
| Hybrid | 286.202,08 | 8,40x |

**Hybrid menos PQC: 29.772,16 bytes** (11,61% a mais que PQC puro).

### 2.2 OPINsize por termo, por perfil, contagens N

| Termo | N por execução | Classic | PQC | Control | Hybrid |
|---|---:|---:|---:|---:|---:|
| mTLS (handshake) | 6 | 18.750 | 129.636 | 101.694 | 144.474 |
| JWT (apenas assinatura) | 28 | 6.655,88 | 86.033,92 | 92.690,08 | 92.690,08 |
| JWK (chave crua) | 4 | 1.536 | 8.320 | 9.856 | 9.856 |
| PKI (certificados de CA) | 4 | 7.130,00 | 32.440 | 37.768 | 39.182,00 |
| **OPINsize (total)** | 44 chamadas/execução | **34.071,88** | **256.429,92** | **242.008,08** | **286.202,08** |

**Sobre o rótulo "PKI":** as 4 chamadas deste termo são, confirmado em código (`thesis/scripts/opinsize_v9_oficial.py`, `PKI_ENDPOINTS = {"/root-ca.pem", "/issuer-ca.pem"}`), recuperação dos certificados de CA (raiz + emissora, uma vez por sub-fluxo) -- **nunca** uma lista de revogação (CRL). O campo interno do pipeline se chama `term_pki_crl` por uma convenção de nomenclatura herdada, não porque CRL seja de fato buscada; este relatório usa "PKI (certificados de CA)", que descreve o que a chamada real faz.

**Verificação externa ao pipeline de medição (termo mTLS, não circular):** `evaluate_criteria.expected_handshake_bytes()` deriva o número esperado de bytes de handshake por conexão (entrada+saída) a partir do tamanho DER real dos certificados efetivamente implantados em `certs/generated/` -- uma fonte INDEPENDENTE da captura de tráfego da campanha. Rodado agora, ao vivo, por este script (não copiado de um relatório anterior):

| Perfil | Esperado (DER real dos certificados, bytes/conexão) | Medido (campanha, bytes/conexão) | Bate? |
|---|---:|---:|---|
| Classic | 3.125 | 3.125 | SIM |
| PQC | 21.606 | 21.606 | SIM |
| Control | 16.949 | 16.949 | SIM |
| Hybrid | 24.079 | 24.079 | SIM |

**Status da verificação por termo:**

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
| Control | jwe=2, payload_extension=24, strong_nesting=2 | 92.690 | 3.310,36 | 92.690,08 | 92.690,08 | 0,00 |
| Hybrid | jwe=2, payload_extension=24, strong_nesting=2 | 92.690 | 3.310,36 | 92.690,08 | 92.690,08 | 0,00 |

**Explicação do resíduo fracionário (ex.: 86.033,92 vs. 86.034; 6.655,88 vs. 6.656; 92.690,08 vs. 92.690), confirmada no código, não suposta:** `thesis/scripts/opinsize_v9_oficial.py` calcula `jwt_sig_avg = round(statistics.mean(jwt_sig_sizes_all), 2)` e só depois `term_jwt = round(n_jwt * jwt_sig_avg, 2)` -- a média por token é arredondada a 2 casas decimais ANTES de ser multiplicada por N_JWT=28, o que propaga um resíduo de até ±0,14 byte em relação à soma exata por especificação. A tabela acima reproduz essa MESMA aritmética (coluna "Termo esperado") e bate exatamente com o termo medido nos 4 perfis -- o resíduo não é um erro de medição, é um efeito de arredondamento já presente no próprio pipeline, agora reproduzido e confirmado aqui, não apenas suposto.

**Contribuição dos tokens JWE:** por construção (`_jwt_sig_bytes`, `thesis/scripts/opinsize_v9_oficial.py`), um token `jwe` (criptografado, sem assinatura própria) contribui exatamente **0 bytes** a este termo -- confirmado em código (`classical_sig_bytes`/`pq_sig_bytes` ambos `None`→0 para essa construção) e nos dados reais (2 tokens `jwe` por execução, em todos os 4 perfis, nunca contados aqui).

#### 2.4.2 JWK -- tamanho de chave pública por especificação

Especificação (chave crua, sem envelope): RSA-2048 (módulo) = 256B; ML-DSA-65 (FIPS 204) = 1952B.

| Perfil | Chave por especificação (bytes) | Média real medida (4 chamadas) | Diferença vs. especificação | Composição real confirmada |
|---|---:|---:|---:|---|
| Classic | 256 | 384 | +128 | RSA:256+RSA:256 / RSA:256 / RSA:256+RSA:256 / RSA:256 |
| PQC | 1.952 | 2.080 | +128 | AKP:1952+RSA:256 / AKP:1952 / AKP:1952+RSA:256 / AKP:1952 |
| Control | 2.208 | 2.464 | +256 | HYBRID:2208+RSA:256 / HYBRID:2208+RSA:256 / HYBRID:2208+RSA:256 / HYBRID:2208+RSA:256 |
| Hybrid | 2.208 | 2.464 | +256 | HYBRID:2208+RSA:256 / HYBRID:2208+RSA:256 / HYBRID:2208+RSA:256 / HYBRID:2208+RSA:256 |

**O que compõe o acréscimo sobre a chave pura, confirmado chamada a chamada (não especulado):** das 4 chamadas reais `/jwks` por execução, **metade (2 de 4)** carrega uma SEGUNDA entrada JWK além da chave de assinatura do próprio perfil -- para Classic/PQC, essa segunda entrada é sempre uma chave RSA-2048 de 256B com `use="enc"` (a chave pública de cifragem do `id_token`, JWE, clássica em todos os perfis por desenho já declarado); as outras 2 de 4 chamadas não carregam nenhuma segunda entrada. Isso dá uma média de +128B/chamada para Classic e PQC -- mas **não é um acréscimo fixo de 128B em cada chamada individual**, é um acréscimo de 256B em exatamente metade das chamadas. Para Hybrid/Control, **todas as 4 chamadas** carregam uma segunda entrada de 256B -- 2 delas a mesma chave `use="enc"` de Classic/PQC, e as outras 2 uma entrada RSA `use="sig"` **duplicada** (o mesmo `kid` da metade clássica da chave composta, republicada separadamente para um consumidor JWKS padrão que faça descoberta por `kid`+`alg` sem suporte à chave híbrida). Por isso Hybrid/Control acrescenta 256B em TODAS as 4 chamadas, não 128B -- a tabela acima confirma isso com a composição real de cada uma das 4 chamadas de uma execução real.

#### 2.4.3 PKI -- tamanho real dos arquivos de CA + sobrecarga de framing HTTP

| Perfil | Arquivo(s) servidos (root / issuer) | PEM real (root+issuer, bytes) | Framing HTTP | Esperado (PEM+framing) | Medido | Diferença |
|---|---|---:|---|---:|---:|---:|
| Classic | root_ca_rsa2048.crt / issuer_ca_rsa2048.crt | 1.679+1.692 | content-length (+97B) | 7.130,00 | 7.130,00 | 0,00 |
| PQC | root_ca_pqc.crt / issuer_ca_pqc.crt | 8.001+8.013 | chunked (+103B) | 32.440,00 | 32.440 | 0,00 |
| Control | root_ca_hybrid.crt / issuer_ca_hybrid.crt | 9.337+9.341 | chunked (+103B) | 37.768,00 | 37.768 | 0,00 |
| Hybrid | root_ca_rsa2048.crt+root_ca_pqc.crt / issuer_ca_rsa2048.crt+issuer_ca_pqc.crt | 9.680+9.705 | chunked (+103B) | 39.182,00 | 39.182,00 | 0,00 |

**Fontes, citadas com file:line (não estimadas):** o arquivo de CA servido por perfil vem de `realCAFilesForProfile` (`thesis/results/v9/integration/gateway/business_server.go:283-294`) -- Hybrid concatena DOIS arquivos por slot (RSA-2048 + ML-DSA-65) num único corpo de resposta, os outros 3 perfis servem um único arquivo. O tamanho PEM real de cada arquivo vem de `certs_manifest.json` (gerado por `cert_manifest.py`, lendo os arquivos reais de `mock-service-os/certs/`). A sobrecarga de enquadramento HTTP (97B content-length, 103B chunked) vem de `headerOverheadByFraming`/`wantFramingByProfile` (`thesis/results/v9/integration/gateway/ca_handler_test.go:142-144` e `:280`) -- Classic usa content-length, os outros 3 perfis usam chunked. **Diferença zero nos 4 perfis** -- esta é a única das três verificações desta seção sem nenhum resíduo de arredondamento, porque a sobrecarga de framing é um inteiro exato, não uma média estatística sobre muitas amostras.

### 2.5 Invariantes estruturais por termo (Classic < PQC < Hybrid, Hybrid >= Control)

| Termo | Classic | PQC | Control | Hybrid | Ordem OK? |
|---|---:|---:|---:|---:|---|
| mTLS (handshake) | 18.750 | 129.636 | 101.694 | 144.474 | SIM |
| JWT (apenas assinatura) | 6.655,88 | 86.033,92 | 92.690,08 | 92.690,08 | SIM |
| JWK (chave crua) | 1.536 | 8.320 | 9.856 | 9.856 | SIM |
| PKI (certificados de CA) | 7.130,00 | 32.440 | 37.768 | 39.182,00 | SIM |

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
| sa-east-1 | L0-sa-east-1 | Control | 2.472,1 ms | 49,94 ms | 2.408,3 ms | 2.550,5 ms |
| sa-east-1 | L0-sa-east-1 | Hybrid | 2.564,6 ms | 83,58 ms | 2.406,0 ms | 2.712,0 ms |
| sa-east-1 | L123 | Classic | 10.879,8 ms | 59,92 ms | 10.811,9 ms | 11.021,8 ms |
| sa-east-1 | L123 | PQC | 11.143,3 ms | 65,40 ms | 11.052,0 ms | 11.253,6 ms |
| sa-east-1 | L123 | Control | 11.263,4 ms | 78,84 ms | 11.145,7 ms | 11.416,7 ms |
| sa-east-1 | L123 | Hybrid | 11.349,1 ms | 77,24 ms | 11.255,7 ms | 11.502,8 ms |
| sa-east-1 | L219 | Classic | 17.683,3 ms | 50,11 ms | 17.608,2 ms | 17.776,4 ms |
| sa-east-1 | L219 | PQC | 18.105,6 ms | 46,77 ms | 18.050,1 ms | 18.197,8 ms |
| sa-east-1 | L219 | Control | 18.302,0 ms | 117,71 ms | 18.153,5 ms | 18.513,0 ms |
| sa-east-1 | L219 | Hybrid | 18.396,5 ms | 107,86 ms | 18.203,5 ms | 18.483,4 ms |
| sa-east-1 | L325 | Classic | 25.559,2 ms | 178,49 ms | 25.311,2 ms | 25.801,6 ms |
| sa-east-1 | L325 | PQC | 26.136,5 ms | 205,24 ms | 25.934,8 ms | 26.612,2 ms |
| sa-east-1 | L325 | Control | 26.523,1 ms | 224,60 ms | 26.211,8 ms | 26.878,4 ms |
| sa-east-1 | L325 | Hybrid | 26.531,6 ms | 305,82 ms | 26.064,8 ms | 27.131,4 ms |
| us-east-1 | L0-us-east-1 | Classic | 3.817,0 ms | 60,52 ms | 3.790,9 ms | 3.935,3 ms |
| us-east-1 | L0-us-east-1 | PQC | 4.040,4 ms | 81,17 ms | 3.943,0 ms | 4.165,9 ms |
| us-east-1 | L0-us-east-1 | Control | 4.247,7 ms | 137,51 ms | 4.067,2 ms | 4.529,6 ms |
| us-east-1 | L0-us-east-1 | Hybrid | 4.208,1 ms | 117,28 ms | 4.044,0 ms | 4.409,6 ms |
| us-east-1 | L14 | Classic | 4.744,6 ms | 48,97 ms | 4.694,9 ms | 4.864,6 ms |
| us-east-1 | L14 | PQC | 5.032,4 ms | 46,92 ms | 4.942,2 ms | 5.085,5 ms |
| us-east-1 | L14 | Control | 5.145,7 ms | 90,21 ms | 5.067,7 ms | 5.316,7 ms |
| us-east-1 | L14 | Hybrid | 5.202,5 ms | 93,31 ms | 5.053,9 ms | 5.363,9 ms |
| ap-northeast-1 | L0-ap-northeast-1 | Classic | 5.786,2 ms | 52,76 ms | 5.688,1 ms | 5.857,5 ms |
| ap-northeast-1 | L0-ap-northeast-1 | PQC | 6.248,6 ms | 82,15 ms | 6.141,1 ms | 6.394,4 ms |
| ap-northeast-1 | L0-ap-northeast-1 | Control | 6.634,2 ms | 192,58 ms | 6.295,2 ms | 6.786,1 ms |
| ap-northeast-1 | L0-ap-northeast-1 | Hybrid | 6.616,3 ms | 155,70 ms | 6.328,1 ms | 6.814,4 ms |
| ap-northeast-1 | L30 | Classic | 8.214,5 ms | 151,14 ms | 8.003,7 ms | 8.518,7 ms |
| ap-northeast-1 | L30 | PQC | 8.769,4 ms | 102,18 ms | 8.540,3 ms | 8.864,0 ms |
| ap-northeast-1 | L30 | Control | 9.018,1 ms | 166,88 ms | 8.718,3 ms | 9.270,3 ms |
| ap-northeast-1 | L30 | Hybrid | 9.028,6 ms | 125,66 ms | 8.859,3 ms | 9.233,5 ms |

### 4.2 Ordem das medianas por rota e diferença percentual (PQC vs. Classic, Hybrid vs. PQC)

| Rota | Ordem (menor -> maior mediana) | PQC vs. Classic | Hybrid vs. PQC |
|---|---|---:|---:|
| L0-sa-east-1 | PQC < Classic < Control < Hybrid | -2,93% | +12,04% |
| L123 | Classic < PQC < Control < Hybrid | +2,42% | +1,85% |
| L219 | Classic < PQC < Control < Hybrid | +2,39% | +1,61% |
| L325 | Classic < PQC < Control < Hybrid | +2,26% | +1,51% |
| L0-us-east-1 | Classic < PQC < Hybrid < Control | +5,85% | +4,15% |
| L14 | Classic < PQC < Control < Hybrid | +6,07% | +3,38% |
| L0-ap-northeast-1 | Classic < PQC < Hybrid < Control | +7,99% | +5,88% |
| L30 | Classic < PQC < Control < Hybrid | +6,75% | +2,96% |

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

**Contagens agregadas:** Classic×PQC se sobrepõem em **1/8** rotas; PQC×Hybrid se sobrepõem em **6/8** rotas. Onde os intervalos se sobrepõem, a ordem das medianas naquela rota específica não é lida como robusta somente a partir desta tabela -- nenhum teste de significância foi reaplicado nesta rodada (fora do escopo desta entrega).

### 4.4 Inversão em L0-sa-east-1 (PQC com mediana abaixo de Classic): os 10 valores reais, sem causa atribuída

10 valores reais de T_fluxo (segundos), ordenados, nesta rota:

- **Classic:** 2,270337, 2,320785, 2,327829, 2,341451, 2,353749, 2,362013, 2,362613, 2,401444, 2,425318, 2,439924
- **PQC:** 1,919165, 2,271329, 2,274855, 2,279327, 2,282256, 2,295532, 2,342916, 2,367430, 2,418240, 2,425901

**Mediana PQC com os 10 valores:** 2,288894s. **Mediana PQC excluindo o único valor mais baixo** (1,919165s): 2,295532s -- variação de 6,6ms ao remover esse valor. **Mediana Classic:** 2,357881s. A mediana de PQC permanece abaixo da de Classic mesmo excluindo o valor mais baixo -- a inversão não depende inteiramente de um único valor extremo; os demais 9 valores de PQC, no conjunto, também ficam no mesmo patamar ou abaixo do grosso da distribuição de Classic nesta rota específica.

**Ordem de execução dos blocos de perfil nesta rota** (`manifest.route_orders["L0-sa-east-1"]`): Control -> Classic -> PQC -> Hybrid. PQC roda como o 3º dos 4 blocos nesta rota, depois de Classic -- os dados não mostram, por si só, nenhuma causa específica para a inversão além do que está listado acima; nenhuma causa é proposta além do que os valores e a ordem mostram diretamente.

## 5. Critérios técnicos (1-7)

| Critério | Resultado |
|---|---|
| 1 (tamanhos por mensagem (campanha)) | PASS |
| 2 (initcwnd real (campanha)) | PASS |
| 3 (zero erros na rota mais distante (campanha)) | PASS |
| 4 (contagens do fluxo (campanha)) | PASS |
| 5 (zero erros) | PASS |
| 6 (instrumentacao completa + asserções (campanha)) | PASS |
| 7 (sanidade de latencia por rota (campanha)) | **FAIL** |

### 5.1 Critério 7 -- RTT nominal vs. medido, por rota (exceção documentada em L30)

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

### 5.2 Retries de transporte: 0 (zero)

`retries_report.json`: `total_retries=0`, `por_celula={}` -- nenhuma das 320 execuções oficiais precisou de retry de transporte HTTP/mTLS.

## 6. Canal interno AS<->RS (permanece clássico em todos os 4 perfis)

**Mecanismo, confirmado por código (não assumido):** `thesis/results/v9/integration/gateway/business_server.go:246-250` -- `attachInternalCallerCarveOut` monta um `cfg.GetConfigForClient` cuja única condição é `hello.ServerName == internalCallerSNI` (`"matls-api.local"`, linha 164); quando verdadeira, retorna sempre o MESMO `internalCfg`, cujo `CurvePreferences = []tls.CurveID{tls.CurveP521, tls.CurveP384, tls.CurveP256}` (linha 242) é um valor fixo, sem nenhum `if`/`switch` sobre `profile` dentro do próprio closure. `business_server.go:104` confirma o mesmo do lado do enforcement em runtime: só aplica a curva ESPERADA DO PERFIL a conexões que NÃO sejam a chamada interna -- por construção, válido para os 4 perfis.

**Evidência real desta campanha (320 execuções), fonte completa (não apenas o último bloco de perfil):** `piloto_combined.log` é um log continuamente anexado durante toda a janela (sobrevive ao reinício de container entre blocos de perfil, ao contrário de `full_container_logs`) -- **2.240 conexões reais** com `sni="matls-api.local"`, **100% com curve=CurveP256**, nos 4 perfis: Classic=560, Hybrid=560, Control=560, PQC=560.

**Evidência corroborante de um piloto real anterior (18 execuções, MESMO código e MESMAS imagens Docker desta campanha, rodado antes dela na mesma conta/infraestrutura):** **126 conexões reais** com `sni="matls-api.local"`, **100% com curve=CurveP256**, também nos 4 perfis: Classic=42, Hybrid=42, Control=21, PQC=21. Duas coletas reais independentes, mesmo mecanismo de código, mesmo resultado -- 0 violações em qualquer das duas.

## 7. Custo e duração (sem teardown -- nenhum valor aqui é "final")

Fórmula real (`cost_tracker.CostTracker`), frota real (12 instâncias: 1 `t4g.micro` + 11 `m7i-flex.large`, 12 EIPs), `window_start_utc` derivado da primeira linha real de `cost_tracker.jsonl` (`2026-11-15T04:17:09Z`). **Nenhuma leitura abaixo é chamada de "custo final" -- isso só se aplica depois do teardown da frota, que ainda não aconteceu.**

| Momento | Timestamp (UTC) | Custo acumulado até este momento |
|---|---|---:|
| última leitura automática registrada (cost_tracker.jsonl) | 2026-11-15T23:36:12Z | US\$27,69 |
| fim da janela oficial (manifest.window_end_utc) | 2026-11-16T00:06:40Z | US\$28,42 |
| fim da coleta dos critérios dedicados (último evento real nos logs do gateway) | 2026-11-16T00:22:57Z | US\$28,81 |
| agora (momento em que este relatório foi gerado) | 2026-11-16T03:25:14Z | US\$33,16 |

- **cost_stop:** nunca acionado (`None`); teto desta fase: aviso US\$70 / parada US\$90.
- **Integridade dos dados brutos:** 720/720 arquivos copiados do controle, verificados por sha256 local, 0 divergências.

## 8. Transparência e limites de escopo

- **Arquivos catalisadores RSA-4096 da CA do perfil Controle não foram migrados** -- o perfil Controle reutiliza a raiz/emissora RSA clássica para sua cadeia de certificados, por desenho.
- **O total de Controle fica abaixo do total de PQC, mas não termo a termo** -- ver a reconciliação completa na Seção 3: Controle fica abaixo do PQC somente no termo mTLS, e acima nos outros 3 termos.
- **Exceção do critério 7 em L30**, documentada e aceita sem recalibração do baseline (Seção 5.1).
- **Conexões internas AS->RS ficam fora da equação OPINsize** -- o termo mede apenas o que atravessa o canal client-facing (gateway mTLS); o canal interno permanece clássico e não migrado, por desenho (Seção 6).
- **Ressalva de reprodutibilidade:** pacotes do sistema operacional (AMI e `dnf`) instalados no momento do provisionamento desta campanha não têm suas versões exatas re-fixadas por nenhum manifesto além do que o documento de fatos dos hosts (auditoria somente-leitura, entregue separadamente) registrou -- uma reconstrução futura a partir de uma AMI mais nova pode obter versões de pacote diferentes das observadas aqui, sem que isso indique nenhuma mudança no código/binários desta tese (esses seguem pinados, verificados conforme a Seção 9).

## 9. Reprodutibilidade

**Integridade das imagens Docker, por imagem, com a garantia real de cada uma (não uma frase genérica):**

- **`gateway` e `proxy`:** binários **bit a bit idênticos** ao pin registrado -- sha256 do binário compilado confere exatamente contra o valor pinado, sem nenhuma tolerância.
- **`measure`:** equivalência, **não** bit a bit -- os binários `gateway`/`proxy` embutidos dentro da imagem são idênticos ao pin, as camadas estáveis da imagem (posições 0 e 4 do `rootfs_layers`) e o `config_subset` são idênticos; as camadas voláteis (posições 1, 2 e 3) variam de build para build por um timestamp que o BuildKit embute, não por diferença de conteúdo -- documentado desde a Decisão 159.
- **`auth`, `mongo_seed`, `mockapi`:** identidade por `rootfs_layers`+`config_subset`, reconstrução **equivalente**, não bit a bit -- as causas reais, já identificadas, de não-determinismo byte a byte entre builds/sistemas operacionais diferentes são: normalização de fim de linha (CRLF/LF), material de chave efêmera gerado pelo próprio AS a cada execução (nunca persistido, sempre de tamanho/tipo fixo), e resolução de dependências opcionais específicas de plataforma do `npm` (variantes de pacote por sistema operacional de build, nunca uma dependência de runtime real).
- **Gate de entrega (todas as imagens):** verificado por conteúdo (`rootfs_layers`, `config_subset`, `binary_sha256` dos binários embutidos), nunca por `tar_sha256` -- dois `docker save` do EXATO mesmo conteúdo geram arquivos `.tar` com hashes SHA-256 diferentes entre si (instabilidade do próprio formato tar/metadados de empacotamento, não do conteúdo), então comparar por `tar_sha256` produziria falsos negativos.

- Todo número deste documento foi lido ou computado por `thesis/results/v9/campaign/scripts/generate_final_report_oficial_conta_nova.py`, a partir de `thesis/results/v9/campaign_oficial_conta_nova_raw/`, `thesis/results/v9/campaign_oficial_conta_nova_organized/`, e de uma verificação externa ao pipeline rodada ao vivo (`evaluate_criteria.expected_handshake_bytes`, Seção 2.2) -- nenhum valor foi digitado manualmente.
- Este relatório foi auditado de forma independente (agente separado, sem acesso ao texto deste documento como fonte, apenas aos dados organizados/manifesto) antes de sua entrega final -- tabela de conferência na Decisão correspondente em `DECISIONS.md`.

