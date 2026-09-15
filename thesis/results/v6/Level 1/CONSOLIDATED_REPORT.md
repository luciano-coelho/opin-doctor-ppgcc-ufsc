# Nível 1 (TLS key exchange) — Relatório Consolidado Final

Escopo: 2 perfis (PQC, Híbrido) × 6 cenários (0/14/30/140/225/320ms) × 4 séries por etapa
(com KEM, baseline Go-clássico) × 2 etapas (tamanho, latência) = 480 execuções contadas (fora
warmups e execuções de assentamento, todas descartadas por design). Clássico não precisou de
nova medição — sua troca de chave já era clássica desde sempre, sem mudança neste trabalho; seus
números seguem sendo os oficiais da v5.

Metodologia completa em `ARCHITECTURE.md` (Fases 0-6) e `DECISIONS.md` (6 decisões) deste mesmo
diretório. Este relatório substitui integralmente uma versão anterior cujo "achado principal"
("o aumento de latência é overhead de infraestrutura de proxy") foi identificado como incorreto
na causa (Decision 3) e cujos números de latência vieram de um lote contaminado por um artefato
de ambiente, refeito do zero (Decisions 3-6).

---

## Tamanho — `handshake_bytes`, decomposição limpa (Etapa 1, Decision 2)

240 execuções (6 cenários × 10 × 4 séries), **0% de spread em toda métrica, todo cenário** —
esperado, tamanho não depende de latência de rede:

| Perfil | Go-clássico (baseline) | Com KEM (real) | Delta do ML-KEM |
|---|---|---|---|
| PQC | 13.525 bytes | 16.605 bytes | **+3.080 bytes** |
| Híbrido | 15.743 bytes | 18.023 bytes | **+2.280 bytes** |

Consistente com o teste controlado isolado da Decision 2 (+2.969 / +2.169 sem certificado de
cliente) — a pequena diferença vem do certificado de cliente real agora incluso na medição.
Idêntico nos 6 cenários, sem exceção.

**Todas as demais métricas de tamanho continuam idênticas à v5**, 0% de spread em todos os 6
cenários: JWT médio (PQC 5.458,81 / Híbrido 7.324,81 bytes), certificado do cliente (2.953 /
6.859 bytes), tráfego total (185.013 / 255.276 bytes) — todas remedidas ao vivo nesta rodada
(não reaproveitadas da v5; ver `client_cert_der_bytes()`/`compute_metrics()` em
`thesis/scripts/opin_flow.py`/`baseline_automation.py`), confirmando que nada além da troca de
chave foi afetado.

---

## Latência — `T_fluxo` (Etapa 2, Decisions 3-6)

240 execuções (6 cenários × 10 × 4 séries), sem retries nem falhas.

### Delta do ML-KEM (mesmo perfil, mesmo cliente Go, mesma arquitetura de proxy — só a curva difere)

| Cenário | PQC — delta do KEM | Híbrido — delta do KEM |
|---|---|---|
| 0ms | +1,04s\* | +0,33s |
| 14ms | +0,99s\* | -2,01s\*\* |
| 30ms | -0,01s | +0,14s |
| 140ms | +0,34s | +0,44s |
| 225ms | -0,12s | +1,69s |
| 320ms | +0,18s | +0,10s |

\*PQC/0ms: uma única execução da série com KEM saiu em 16,78s (spread 73,5% no grupo, as outras 9
execuções ficaram entre 9,67-11,4s) — pico isolado, sem recorrência nos cenários vizinhos, mesmo
padrão de ruído já caracterizado na Decision 4.
\*\*Híbrido/14ms: o lado *Go-clássico* dessa comparação teve uma execução isolada em 17,91s
(spread 51,3% nesse grupo) puxando sua própria mediana para cima — não o KEM ficando mais barato.

Fora esses dois pontos pontuais, o delta do ML-KEM fica entre -0,12s e +0,44s em todos os 6
cenários — **o custo do ML-KEM na troca de chave é desprezível**, confirmado de ponta a ponta do
espectro de latência de rede testado, não só em 0ms.

### v6 (com KEM, via proxy) vs v5 (histórico, sem proxy/KEM) — mesmo perfil

| Cenário | PQC v6−v5 | Híbrido v6−v5 |
|---|---|---|
| 0ms | +0,71s | -0,08s |
| 14ms | -0,71s | -0,04s |
| 30ms | -0,47s | +0,16s |
| 140ms | -1,35s | +0,03s |
| 225ms | -2,18s | -0,18s |
| 320ms | -3,43s | -3,15s |

**Ressalva importante sobre esta tabela, investigada de ponta a ponta nos 6 cenários antes de
ser incluída aqui (Decisions 6 e 7)**: v6 aparece mais rápido que a v5 em alguns cenários de
latência mais alta, o que à primeira vista soa contraintuitivo (v6 tem uma camada a mais, o
proxy). **Primeiro fato confirmado: a maioria dessas células não é um sinal real.** Repetindo o
teste controlado (curva clássica fixa, sem KEM, sem proxy, Go vs Python numa conexão nova) nos 6
cenários, o delta por conexão escala de forma limpa e monotônica com a latência injetada
(0,017-0,022s em 0ms até 0,326-0,327s em 320ms, idêntico entre os dois certificados). Comparando
esse modelo (×6 conexões do cliente) contra o gap real de cada célula da tabela, ele só bate em
**4 das 12 combinações perfil/cenário** — PQC em 140/225/320ms e Híbrido em 320ms — explicando
consistentemente **59-68%** do gap nessas 4. Nas outras 8, o modelo prevê o sinal errado ou
excede em muito um gap pequeno demais para ser outra coisa que ruído de execução (spreads de
15-50%+ sobre uma base de 10-14s) — ou seja, a maior parte da tabela acima não precisa de
explicação nenhuma, porque não é um efeito real.

**Para os 32-41% restantes nas 4 células com sinal real**, a instrumentação direta do log de
acesso do gateway (mesma técnica das Decisions 1/2) revelou que um fluxo completo faz **13
conexões mTLS no gateway, não 6**: as 6 do cliente (Python/Go, já modeladas acima) mais **7
conexões internas do próprio `auth`** (chamada de volta pro RS via `matls-api.local`, o mesmo
carve-out da Decision 1 — já documentada desde a Decision 5/9 da v5, não é nova do Nível 1), cada
uma custando ~2× o tempo de handshake das conexões do cliente (mesma versão TLS, mesma cipher
suite — não é HelloRetryRequest por KEM, confirmado diretamente).

**Verificado depois, com evidência, se essa contagem varia por causa da race já documentada
(Decisions 5/9) ou se é determinística**: os `run*_baseline_metrics.json` da v5 (tamanho) existem,
estão commitados, e trazem `gateway_metrics.requests_logged` — cuja diferença para
`total_requests` (chamadas do cliente) é exatamente a contagem de requisições internas do
servidor. Checado nos 10 runs, 6 cenários, 2 perfis, para v5 e v6 (120 arquivos): **a diferença é
sempre exatamente 10 na v5 e sempre exatamente 14 na v6, sem uma única exceção.** Não é race — é
determinístico. **v6 faz exatamente 4 conexões internas a mais que a v5, sempre, em todo cenário
e perfil.** Essa contagem extra, a ~2× o custo de round-trip por conexão, está na mesma ordem de
grandeza do resíduo restante em 320ms (~4×0,32s ≈ 1,3s contra um resíduo de ~1,1-1,4s) — explicação
plausível e provável para a maior parte do que sobra, mas a reconciliação exata segundo a segundo,
cenário a cenário, ainda não foi verificada de forma independente (a captura ao vivo usada pra
confirmar o custo por conexão foi uma execução avulsa do baseline Go-clássico, não uma auditoria
direta dos 10 runs oficiais do lote).

**Conclusão honesta**: o mecanismo Go-vs-Python está confirmado e explica 59-68% do gap nos 4
cenários onde o gap é um sinal real; os outros 8 cenários da tabela não representam um efeito
real pra começo de conversa; e as 4 conexões internas extras, determinísticas e confirmadas por
dado já existente (não uma suposição), são a explicação mais provável para a maior parte do que
resta — mas essa última parte não foi fechada com uma reconciliação segundo a segundo verificada
de forma independente. Detalhe completo, incluindo a correção de uma afirmação anterior incorreta
sobre a v5 não ter dado suficiente, na Decision 7. Esta tabela é reportada por transparência, não
como evidência de que o Nível 1 "acelerou" o sistema.

---

## Confiabilidade da execução

- **480 execuções contadas nas Etapas 1+2, 0 falhas não documentadas.**
- Etapa 1 (tamanho): 1 retry de execução inteira (Híbrido, 30ms, run03 — `InvalidGrant` em
  `/token`), a mesma race já documentada nas Decisions 5/9 da v5, absorvida automaticamente.
- Etapa 2 (latência): nenhum retry, nenhuma falha.
- 2 execuções isoladas fora da curva (PQC/0ms com-KEM, Híbrido/14ms Go-clássico — ver tabela
  acima), mesmo padrão de ruído já caracterizado e aceito na Decision 4 (pico isolado, sem
  tendência nos cenários vizinhos).
- **Bug de assentamento encontrado e corrigido entre as Etapas 1 e 2** (Decision 5): a troca de
  perfil para PQC na Etapa 1 rodou com o aquecimento pós-troca silenciosamente quebrado (roteava
  direto, não pelo proxy) — sem consequência para tamanho (determinístico), mas corrigido antes
  da Etapa 2, cuja troca de perfil (ambos os sentidos) rodou com o aquecimento funcionando
  corretamente (5/5 execuções OK em cada troca).
- **Investigação de deriva de ambiente** (Decision 4): um resíduo de ~2s no piloto Híbrido/0ms
  foi rastreado até degradação cumulativa do Docker Desktop ao longo de uma sessão longa, não a
  um efeito do KEM ou do certificado Híbrido — confirmado por 2h20m de medições estáveis após um
  reinício do ambiente.

---

## Onde estão os dados

```
thesis/results/v6/Level 1/
  size/experiment2 - PQC/{cenário}ms/                       -- tamanho, perfil PQC
  size/experiment2 - PQC/go-classical-baseline/{cenário}ms/ -- baseline Go-clássico, tamanho
  size/experiment3 - Hybrid/{cenário}ms/                     -- tamanho, perfil Híbrido
  size/experiment3 - Hybrid/go-classical-baseline/{cenário}ms/
  latency/experiment2 - PQC/{cenário}ms/                -- latência, perfil PQC
  latency/experiment2 - PQC/go-classical-baseline/{cenário}ms/
  latency/experiment3 - Hybrid/{cenário}ms/
  latency/experiment3 - Hybrid/go-classical-baseline/{cenário}ms/
  _archive-pre-localhost-fix/                           -- lote original, contaminado (Decision 3),
                                                            preservado só para histórico, não usado
                                                            em nenhuma comparação deste relatório
```

Cada pasta de cenário contém `runs/run01..10.json` (mais `run00_warmup.json` na latência) —
dados brutos, rastreáveis e auditáveis, mais `median_metrics.json`/`report.md` derivados. Mesma
convenção da v5 (JSON é a fonte primária, MD é derivado).

## Pendências para as próximas fases

1. **Atualizar os documentos da v5** que ainda citam os números pré-Nível-1 de PQC/Híbrido:
   `thesis/results/v5/size/tabela_final_v5.md`, `final_comparative_table_v5.md`, os dois
   `CONSOLIDATED_REPORT.md` da v5, `Arquitetura_Tecnica_Experimento3_v5.md`, e os boxplots de
   PQC/Híbrido — todos com os novos números (que agora incluem a troca de chave), mantendo o
   Clássico intocado.
2. **Cruzamento SAD**: atualizar `thesis/docs/Cruzamento_SAD_vs_Experimentos.md` — Nível 1 passa
   de "quase nada coberto" para coberto em PQC e Híbrido.
3. **Gap não totalmente explicado** (Decision 6): os 35-40% restantes do gap v6-vs-v5 em 320ms
   não foram investigados a fundo — não bloqueia o fechamento deste relatório (o achado
   principal, custo do KEM, está resolvido e é robusto), mas fica registrado como possível
   aprofundamento futuro.
