# Tabela Comparativa Final — Clássico | PQC | Híbrido (v5)

Este arquivo consolida a tabela comparativa dos três perfis (Clássico, PQC puro, Híbrido)
contra os dados definitivos da v5 — mediana de 10 execuções por cenário, 180 execuções
totais (3 perfis × 6 cenários × 10), 0% de spread em toda métrica de tamanho em todo
cenário. Fonte: `thesis/results/v5/experiment{1,2,3} - {Classic,PQC,Hybrid}/*/median_metrics.json`
e `CONSOLIDATED_REPORT.md`. Nenhum valor deste arquivo foi reaproveitado de `v3`/`v4` —
todos foram recalculados ou remedidos a partir da v5 (ver Decision 6 em `DECISIONS.md`
para o único valor que precisou de uma correção de pipeline antes de poder ser medido).

Todas as métricas de tamanho são idênticas nos 6 cenários de latência (0/14/30/140/225/320ms)
dentro de cada perfil — tamanho de payload não depende de latência de rede, só o tempo de
resposta depende (ver Decision 12 em `thesis/results/v4/DECISIONS.md`). Os valores abaixo
valem para qualquer um dos 6 cenários.

---

## Metodologia de Agregação

Cada valor deste documento passa por até duas camadas de agregação estatística, aplicadas
por processos distintos do código (`baseline_automation.py` para a camada intra-execução,
`median_automation.py` para a camada entre execuções) — nem sempre pelo mesmo processo nas
duas camadas, e nem sempre por ambas. Esta seção documenta exatamente qual processo se aplica
a cada métrica, em cada camada, para eliminar qualquer ambiguidade sobre "mediana de quê".

**Camada 1 — intra-execução**: dentro de uma única execução do fluxo (28 chamadas HTTP),
algumas métricas resultam de uma agregação sobre múltiplas amostras coletadas naquela mesma
execução (ex.: ~6 conexões físicas mTLS, 26 JWTs). Outras não têm essa camada — são um total
já fechado por execução, ou uma constante que nunca variou.

**Camada 2 — entre execuções**: `median_automation.py` roda o fluxo 10 vezes por cenário e
calcula a **mediana** dos 10 valores já produzidos pela Camada 1 (ou, quando não há Camada 1,
a mediana dos 10 valores brutos por execução) — nunca agrupa as amostras individuais de
múltiplas execuções num único cálculo. Ver `thesis/results/v5/DECISIONS.md` e
`median_automation.py::summarize()`/`NAMED_SCALAR_METRICS`.

| Métrica | Camada 1 (intra-execução) | Camada 2 (entre execuções) | N final na mediana |
|---|---|---|---|
| mTLS_handshake_bytes (P50) | **Mediana** de ~6 amostras de bytes por conexão física (dedup por `remoteIP:port`, outliers >3× a mediana removidos iterativamente — `filter_handshake_outliers`) | **Mediana** dos 10 P50s já calculados | 10 números (cada um já uma mediana de ~6) |
| JWT médio | **Média** (não mediana) dos 26 tamanhos de JWT capturados na execução | **Mediana** das 10 médias já calculadas | 10 números (cada um já uma média de 26) |
| total_bytes_exchanged | **Soma** de `request_bytes+response_bytes` das 28 chamadas da execução (não é uma estatística de tendência central, é um total) | **Mediana** das 10 somas | 10 números (cada um já uma soma de 28) |
| bytes_by_participant (Client/AS/RS/PKI-CRL, sent/received) | **Soma** por participante/direção, sobre as chamadas roteadas a ele naquela execução | **Mediana** das 10 somas, separadamente por participante×direção | 10 números por célula da tabela |
| Certificado do cliente (bytes DER) | Nenhuma — propriedade estática do arquivo de certificado (`client_cert_der_bytes(profile)`), idêntica em toda chamada | Mediana de 10 valores idênticos (trivial) | 10 números, todos iguais — não é uma agregação real, é uma constante reconfirmada 10× |
| JWK_PK_size | **Nenhuma camada do pipeline de 180 execuções** | **Nenhuma** — não passa por `median_automation.py` de forma alguma | 0 — valor obtido fora do lote, por verificação ao vivo/estática (Decision 6), não por mediana de execuções |

**Assimetria a não presumir por engano — JWT médio.** Ao contrário de `mTLS_handshake_bytes`,
a Camada 1 do JWT médio é uma **média**, não uma mediana: `jwt_size_avg_bytes` é
`statistics.mean()` sobre os 26 tamanhos de JWT de uma execução. Só a Camada 2 (entre as 10
execuções) usa mediana. As duas métricas passam por "duas camadas de agregação", mas com
processos estatísticos diferentes em cada uma — nem toda métrica é "mediana de mediana".

**JWK_PK_size não é uma estatística do lote de 180 execuções.** É uma constante
criptográfica — o tamanho fixo, em bytes, da chave pública ML-DSA-65 (1.952) ou da
concatenação RSA+ML-DSA-65 (2.208) — confirmada por decodificação direta do material de
chave (ao vivo via `/jwks`, ou estaticamente via `crypto-profiles/{pqc,hybrid}.json`), não
calculada a partir de amostras coletadas nas execuções (Decision 6). Diferente de toda outra
linha desta tabela, nenhuma das 180 execuções contribui matematicamente para este número —
elas apenas confirmam, indiretamente, que a chave publicada em `/jwks` não mudou de tamanho
durante o lote (o que de fato não mudaria, já que a chave é fixa por perfil).

---

## Tráfego — OPINsize

**Fórmula validada**: `OPINsize = N_mTLS × handshake_bytes(P50) + N_JWT × JWT_médio + N_JWK × JWK_PK_size`

| Métrica | Clássico | PQC | Híbrido | Observação |
|---|---|---|---|---|
| OPINsize (bytes) | 95.242,92 | 264.369,06 | 350.141,06 | Cálculo: 6×9.785,0 + 26×1.385,42 + 2×256 (Clássico); 6×19.756,0 + 26×5.458,81 + 2×1.952 (PQC); 6×25.880,0 + 26×7.324,81 + 2×2.208 (Híbrido). No híbrido, o custo total do fluxo é 350.141,06 bytes — 32,44% acima do PQC puro e 3,68× acima do clássico. Os três termos da equação crescem simultaneamente no híbrido: o handshake carrega a estrutura RSA completa mais as três extensões pós-quânticas; cada um dos 26 JWTs carrega assinatura composta (σ1‖σ2, Strong Nesting, para os artefatos emitidos pelo AS) ou a extensão de payload `pqc` (para os assinados pelo cliente, Decision 13); e a chave pública publicada é a concatenação de ambas as chaves. A equação em si não tem termo de PKI/CRL — a correção do certificado local do Clássico (Decision 1) não afeta este valor diretamente. |

## Handshake mTLS

| Métrica | Clássico | PQC | Híbrido | Observação |
|---|---|---|---|---|
| mTLS_handshake_bytes — P50 | 9.785,0 | 19.756,0 | 25.880,0 | No híbrido, o handshake é 2,64× o clássico e 1,31× o PQC. Estável (0% de spread) nos 6 cenários e nas 10 execuções de cada cenário — o certificado apresentado no handshake (`mtls_hybrid.crt`) carrega tanto a assinatura RSA quanto as três extensões X.509 não-críticas com o material ML-DSA-65 completo (dual nested combiner, Bindel et al. 2019), aumentando o tamanho do `Certificate` da negociação TLS além do que qualquer um dos dois esquemas isolados exigiria. |

## Artefatos Criptográficos

| Métrica | Clássico | PQC | Híbrido | Observação |
|---|---|---|---|---|
| JWT médio (bytes) | 1.385,42 | 5.458,81 | 7.324,81 | No híbrido, a média é 34,18% acima do PQC puro e 5,29× o clássico. Todos os 26 JWTs do fluxo carregam material híbrido — os emitidos pelo AS (id_token, JARM, tokens de acesso/consentimento) usam Strong Nesting (σ1‖σ2, uma assinatura RSA completa seguida de uma ML-DSA-65 completa); os assinados pelo cliente (client assertion, PAR request object) usam a extensão de payload `pqc` sobre um JWT RS256 comum (Decision 13, `thesis/results/v4/DECISIONS.md`) — mais pesada que uma assinatura ML-DSA-65 isolada em ambos os casos, por carregarem as duas assinaturas simultaneamente em vez de uma só. |
| Certificado do cliente (bytes DER) | 1.494 | 2.953 | 6.859 | No híbrido, o certificado é 4,59× o clássico e 2,32× o PQC — carrega simultaneamente a estrutura RSA original mais as três extensões X.509 não-críticas com o material pós-quântico completo (mesma arquitetura do certificado de handshake acima, já que é o mesmo mecanismo de dual nested combiner aplicado à identidade do cliente). Valor remedido diretamente do campo `client_cert_der_bytes` dos dados brutos da v5 (idêntico, 0% de spread, nas 180 execuções) — não herdado de v3/v4. Coincide com o número já reportado antes por ser uma constante estrutural do certificado (mesmo par de chaves, mesma extensão X.509, não sujeito a ruído de medição), não por reaproveitamento. |
| JWK_PK_size — chave pública de assinatura do AS | 256 (RSA-2048) | 1.952 (ML-DSA-65) | 2.208 (256+1.952) | No híbrido, a chave publicada em `/jwks` é a concatenação byte a byte das duas chaves públicas sob um único `kid` (`kty: "HYBRID"`, campo `pk_hybrid`) — 2.208 bytes, 8,63× o clássico. Este valor não estava disponível nos dados brutos da v5 até esta rodada: `extract_jwk_sizes()` só reconhecia `kty` RSA/EC e descartava silenciosamente as chaves `AKP` (PQC) e `HYBRID`, corrigido e remedido ao vivo contra o mesmo material de chave usado em todo o lote de 180 execuções (Decision 6). |

## Bytes por Participante

| Métrica | Clássico | PQC | Híbrido | Observação |
|---|---|---|---|---|
| Servidor de Autorização — AS (sent+received) | 26.063 | 71.270 | 90.433 | No híbrido, o AS movimenta 90.433 bytes — 26,89% acima do PQC puro. Todo token emitido pelo AS (id_token, JARM, tokens de acesso) carrega Strong Nesting completo; a diferença sobre o PQC puro reflete o custo de anexar uma assinatura RSA inteira a cada artefato que já carregava ML-DSA-65 sozinho. |
| Servidor de Dados — RS (sent+received) | 30.873 | 96.091 | 126.035 | No híbrido, o RS movimenta 126.035 bytes — 31,16% acima do PQC puro, mesma causa do AS: toda resposta assinada pelo RS (recursos protegidos) carrega a assinatura composta completa, não apenas a metade pós-quântica. |
| PKI/CRL (sent+received) | 9.516 | 17.276 | 38.432 | No híbrido, o PKI/CRL é 4,04× o clássico e 2,22× o PQC — `root-ca.pem`/`issuer-ca.pem` híbridos carregam o mesmo dual nested combiner dos certificados de handshake/cliente acima (RSA completo + três extensões ML-DSA-65), o maior dos três perfis por representar dois arquivos (root+issuer), cada um com a estrutura híbrida completa. O valor do Clássico (9.516) é menor que o historicamente reportado (10.664, usando o sandbox real da Raidiam) — efeito esperado da Decision 1 (v5): o Clássico agora usa `root_ca.crt`/`issuer_ca.crt` locais (1.515/1.519 bytes DER), menores que os certificados reais externos que eram buscados antes. |
| Client — tráfego total do fluxo | 66.452 | 184.637 | 254.900 | Igual ao `total_bytes_exchanged` do cenário — soma de tudo que o cliente enviou e recebeu nas 28 chamadas HTTP do fluxo. No híbrido, 38,05% acima do PQC puro e 3,84× o clássico, refletindo o acúmulo de todos os itens acima (handshakes maiores, JWTs maiores, PKI/CRL maior). Idêntico (0% de spread) nas 10 execuções de cada um dos 6 cenários de latência. |

## Parâmetros Fixos da Equação

Confirmados a partir dos dados brutos da v5 (`jwt_count`, `gateway_metrics.handshake_bytes.count`
em `runs/run01_baseline_metrics.json` de cada perfil) antes de assumir os valores já esperados.

| Métrica | Clássico | PQC | Híbrido |
|---|---|---|---|
| N_mTLS | 6 | 6 | 6 |
| N_JWT | 26 | 26 | 26 |
| N_JWK | 2 | 2 | 2 |

---
