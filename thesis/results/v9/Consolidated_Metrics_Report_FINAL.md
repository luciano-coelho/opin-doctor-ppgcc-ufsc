# Consolidated Experimental Metrics Report: v9, real multi-region AWS campaign (conta nova)

**Post-quantum migration of the OPIN ecosystem: Classic, pure PQC, Hybrid-AND, and Control (Hybrid-v8) -- real network, single window, 320 executions**
Luciano Figueiredo Coelho | PPGCC/LabSEC/UFSC

## 1. Parâmetros da campanha

- **Perfis:** 4 (Classic, PQC, Control, Hybrid) x **8 rotas** reais (3 instalações: `sa-east-1`, `us-east-1`, `ap-northeast-1`).
- **N por célula:** 10 execuções oficiais + 5 aquecimentos descartados (nunca lidos por nenhuma estatística abaixo).
- **Total:** 320/320 execuções oficiais, 160 aquecimentos, 32/32 capturas dedicadas (0 falhas).
- **Janela única (não 3 janelas como em v8):** `2026-11-15T17:37:59.293861+00:00` -> `2026-11-16T00:06:40.838058+00:00`.
- **Seed de randomização:** `20261107` (ordem dos perfis registrada por rota no próprio manifesto -- `route_orders`).
- **cost_stop:** `None` (nunca acionado).

## 2. Resultados de tamanho: a equação OPINsize

Mesma equação desta tese desde v5 (extensão de Schardong et al., Eq. 3.1, com o termo de PKI):

```
OPINsize = N_mTLS x handshake_bytes + N_JWT x JWT_size + N_JWK x JWK_PK_size + N_PKI x PKI_bytes
```

### 2.1 OPINsize total por perfil (variante assinatura+chave crua, Decisão 147) e razão contra Classic

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
| mTLS handshake | 6 | 18.750 | 129.636 | 101.694 | 144.474 |
| JWT (assinatura+chave crua) | 28 | 6.655,88 | 86.033,92 | 92.690,08 | 92.690,08 |
| JWK (chave crua) | 4 | 1.536 | 8.320 | 9.856 | 9.856 |
| PKI/CRL | 4 | 7.130,00 | 32.440 | 37.768 | 39.182,00 |
| **OPINsize (total)** | 44 chamadas/execução | **34.071,88** | **256.429,92** | **242.008,08** | **286.202,08** |

**Comparação contra o gabarito (Decisão 189):** os 4 valores totais acima batem exatamente (0 bytes de diferença) com o gabarito registrado quando este mesmo pipeline de 320 execuções reais foi avaliado por `evaluate_criteria.py`/`opinsize_v9_oficial.py` -- MATCH EXATO, 0 bytes, nos 4 perfis. A auditoria independente do item 4 desta entrega recalcula estes mesmos totais do zero, a partir de `piloto_calls.json`, como segunda confirmação.

### 2.3 Invariantes estruturais por termo (Classic < PQC < Hybrid, Hybrid >= Control)

| Termo | Classic | PQC | Control | Hybrid | Ordem OK? |
|---|---:|---:|---:|---:|---|
| mTLS handshake | 18.750 | 129.636 | 101.694 | 144.474 | SIM |
| JWT (assinatura+chave crua) | 6.655,88 | 86.033,92 | 92.690,08 | 92.690,08 | SIM |
| JWK (chave crua) | 1.536 | 8.320 | 9.856 | 9.856 | SIM |
| PKI/CRL | 7.130,00 | 32.440 | 37.768 | 39.182,00 | SIM |

**Divergência de bytes de handshake por conexão -- confirmada zero.** `handshake_bytes_alert.json`: 2880 conexões mTLS auditadas, **0 divergentes**.

## 3. Resultados de latência

### 3.1 T_fluxo por célula (mediana, desvio padrão, mínimo, máximo; n=10 por célula, janela única)

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

**Ordem observada entre perfis, por rota, e nota sobre sobreposição de intervalos:** com n=10/célula (vs. n=30 em v8), o intervalo [mínimo;máximo] de cada perfil é reportado explicitamente acima em vez de um intervalo de confiança bootstrap -- a amostra é pequena demais para um bootstrap de 8 pontos ser informativo por rota isolada. Comparação feita visualmente, célula a célula, a partir da tabela acima: onde os intervalos [mín;máx] de dois perfis se sobrepõem, a ordem entre eles nesta rota específica não pode ser lida como robusta só a partir desta tabela (nenhum teste de significância foi reaplicado nesta rodada -- fora do escopo desta entrega).

## 4. Critérios técnicos (1-7)

| Critério | Resultado |
|---|---|
| 1 (tamanhos por mensagem (campanha)) | PASS |
| 2 (initcwnd real (campanha)) | PASS |
| 3 (zero erros na rota mais distante (campanha)) | PASS |
| 4 (contagens do fluxo (campanha)) | PASS |
| 5 (zero erros) | PASS |
| 6 (instrumentacao completa + asserções (campanha)) | PASS |
| 7 (sanidade de latencia por rota (campanha)) | **FAIL** |

### 4.1 Critério 7 -- RTT nominal vs. medido, por rota (exceção documentada em L30)

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

**Decisão do autor sobre L30 (não corrigida, não recalibrada):** aceita como exceção documentada. O RTT real de `L30` (`ap-northeast-1`<->`ap-northeast-2`) mede ~33,4-34,1ms (canal probe e canal pcap concordam entre si) contra 30ms nominais cadastrados em `campaign_topology.CAMPAIGN_NOMINAL_RTT_MS` -- 11-14% fora da tolerância de ±10% que o critério exige. O baseline de medição não foi alterado. A comparação entre perfis (Classic/PQC/Control/Hybrid, Seção 3) ocorre sempre DENTRO da mesma rota -- cada perfil roda sob o mesmo RTT real em L30, então esta exceção não compromete nenhuma comparação entre perfis, apenas o critério de sanidade absoluta desta rota específica contra seu valor nominal cadastrado.

### 4.2 Retries de transporte: 0 (zero)

`retries_report.json`: `total_retries=0`, `por_celula={}` -- nenhuma das 320 execuções oficiais precisou de retry de transporte HTTP/mTLS.

## 5. Canal interno AS<->RS (permanece clássico em todos os 4 perfis)

**Mecanismo, confirmado por código (não assumido):** `thesis/results/v9/integration/gateway/business_server.go:246-250` -- `attachInternalCallerCarveOut` monta um `cfg.GetConfigForClient` cuja única condição é `hello.ServerName == internalCallerSNI` (`"matls-api.local"`, linha 164); quando verdadeira, retorna sempre o MESMO `internalCfg`, cujo `CurvePreferences = []tls.CurveID{tls.CurveP521, tls.CurveP384, tls.CurveP256}` (linha 242) é um valor fixo, sem nenhum `if`/`switch` sobre `profile` dentro do próprio closure -- o parâmetro `profile` recebido por `attachInternalCallerCarveOut` escolhe apenas qual CA confiar, nunca a lista de curvas. `business_server.go:104` confirma a mesma exceção do lado do enforcement em runtime: `if cs.ServerName != internalCallerSNI && cs.CurveID != want` só aplica a curva ESPERADA DO PERFIL a conexões que NÃO sejam a chamada interna -- ou seja, por construção, válido para os 4 perfis, não apenas para o que ficou com evidência de log salva (abaixo).

**Evidência real nos logs desta campanha, com uma ressalva de cobertura:** varredura de `full_container_logs/*_v9-mtls.log` encontrou 21 linhas reais com `sni="matls-api.local"` nos 3 logs de servidor salvos, 100% com `curve=CurveP256` (0 violações). **Ressalva honesta:** esses 3 arquivos de log capturam apenas o ÚLTIMO bloco de perfil em execução no container no momento da coleta pós-janela (o container do gateway é reiniciado a cada troca de perfil) -- as linhas encontradas pertencem exclusivamente ao perfil `hibrido-v8`. Para os outros 3 perfis, a confirmação desta campanha específica fica no mecanismo de código acima (idêntico e sem branch por perfil), não em uma segunda evidência de log direta -- não foi possível recuperar os logs intermediários dos outros 3 blocos de perfil, já sobrescritos antes da coleta.

## 6. Custo, duração e integridade

- **Custo final real** (`cost_tracker.jsonl`, última leitura real antes da coleta de critérios dedicados não reabrir o tracker): **US\$27,69** em 19,32h (12 instâncias) -- muito abaixo do aviso (US\$70) e do teto (US\$90) desta fase.
- **cost_stop:** nunca acionado (`None`).
- **Integridade dos dados brutos:** 720/720 arquivos copiados do controle, verificados por sha256 local, 0 divergências (já confirmado na Decisão 189, não repetido nesta entrega).

## 7. Transparência e limites de escopo

- **Arquivos catalisadores RSA-4096 da CA do perfil Controle não foram migrados** -- o perfil Controle (`hibrido-v8`) reutiliza a raiz/emissora RSA clássica para sua cadeia de certificados, por desenho (não é uma lacuna nova desta campanha).
- **Bytes do perfil Controle ficam abaixo do PQC por desenho**, não por anomalia -- Controle combina assinatura dupla nas mensagens com uma cadeia de certificados ainda RSA, enquanto PQC é ML-DSA-65 puro de ponta a ponta; o termo de PKI de Controle por isso não precisa superar o do PQC puro para a hierarquia de invariantes (Seção 2.3) continuar válida.
- **Exceção do critério 7 em L30**, documentada e aceita sem recalibração do baseline (Seção 4.1).
- **Conexões internas AS->RS ficam fora da equação OPINsize** -- o termo mede apenas o que atravessa o canal client-facing (gateway mTLS); o canal interno permanece clássico e não migrado, por desenho já documentado desde v6 (Seção 5).
- **Ressalva de reprodutibilidade:** pacotes do sistema (AMI/apt) instalados no momento do provisionamento desta campanha não têm suas versões exatas re-fixadas por nenhum manifesto desta entrega além do que o documento de fatos dos hosts (auditoria somente-leitura, entregue separadamente) registrou -- uma reconstrução futura a partir de uma AMI mais nova pode obter versões de pacote diferentes das observadas aqui, sem que isso indique nenhuma mudança no código/binários desta tese (esses seguem pinados em `PINS.json`, verificados byte a byte na entrega desta campanha).

## 8. Reprodutibilidade

- Todo número deste documento foi lido ou computado por `thesis/results/v9/campaign/scripts/generate_final_report_oficial_conta_nova.py`, a partir de `thesis/results/v9/campaign_oficial_conta_nova_raw/` e `thesis/results/v9/campaign_oficial_conta_nova_organized/` -- nenhum valor foi digitado manualmente.
- Este relatório foi auditado de forma independente (agente separado, sem acesso ao texto deste documento como fonte, apenas aos dados organizados/manifesto) antes de sua entrega final -- tabela de conferência na Decisão correspondente em `DECISIONS.md`.

