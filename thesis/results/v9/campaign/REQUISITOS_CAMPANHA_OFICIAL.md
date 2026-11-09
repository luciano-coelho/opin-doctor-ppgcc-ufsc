# Requisitos para a campanha oficial (960 execuções, 8 rotas) — documento apenas, nada implementado aqui

Pedido explícito do Luciano, após a Fase B (5ª tentativa real + reanálise offline do critério 2, Decisões 101-104) fechar 7/7 PASS. Este documento **só lista o que falta antes da campanha oficial** — nenhuma linha de código muda por causa dele. Ver `thesis/results/v9/DECISIONS.md` (Decisões 18/58/104) para a origem de cada achado citado.

---

## (a) Cobertura do critério 2 — rota L325 e sentido cliente→servidor

**Estado atual (Decisão 85/102):** `criterio2_probe.py` só roda uma vez, hardcoded em `CRITERIO2_PROBE_ROUTE = "L219"` (`dedicated_criteria.py`). Mede exclusivamente o sentido **servidor→cliente** (o servidor manda ≥64KB pro cliente que conectou).

**O que falta:**
1. **Rota L325 nunca foi exercitada para o critério 2** — nunca ligada, gap pré-existente desde a Decisão 85, nunca notado antes por falta de evidência que o expusesse. L219 (219ms) e L325 (325ms) têm RTTs diferentes o suficiente para o comportamento de `cwnd`/pacing poder divergir (a formação do primeiro flight depende de `rtt_from_handshake_same_connection`, que escala com o RTT real).
2. **Sentido cliente→servidor nunca medido** — os voos do PRÓPRIO cliente durante os handshakes mTLS reais (seu `Certificate`+`CertificateVerify`+`Finished`, que para PQC/Hibrido-AND são maiores que o do servidor em alguns casos) nunca passaram pelo mesmo teste de `initcwnd`. O critério pré-registrado (Decisão 14/24/34) não distingue sentido explicitamente — mas o método dedicado hoje só cobre um dos dois.

**Risco concreto de não corrigir antes da campanha:** o critério 2 oficial continuaria validando só 1 de 3 rotas e 1 de 2 sentidos — uma falha real de `initcwnd` no sentido cliente→servidor, ou especificamente na rota L325, passaria sem nenhuma evidência, exatamente como aconteceu com L0 no critério 1 antes da Decisão 99 corrigi-lo.

---

## (b) Gaps conhecidos do histórico do projeto, com prioridade

### Achado 10 (Decisão 58) — sampler de CPU/steal: **gap aberto, prioridade ALTA, bloqueante antes da campanha oficial**

A v8 real monitorava `cpu_mem_steal` (ruído de vizinhança em nuvem compartilhada — outras VMs no mesmo host físico competindo por CPU) durante toda janela cronometrada, via `_PeriodicSampler`/`_cpu_mem_sampler_start_cmd`/`_steal_pct_from_cpu_jsonl`, usado em `compute_window_health`. **O piloto da v9 (Decisões 90-102) não tem nada equivalente, por desenho explícito** — o piloto testa viabilidade, nunca foi a fonte dos números oficiais da tese.

**Risco concreto:** a campanha oficial (960 execuções, N=30/célula, horas de execução real) **é** a fonte dos números oficiais da tese — sem o sampler de steal, uma célula com ruído de vizinhança alto (comum em instâncias `m7i-flex.large`, que são *flex*, i.e., compartilham capacidade por desenho) ficaria indistinguível de um efeito real do perfil criptográfico. Qualquer diferença entre perfis medida sem esse controle é **não confiável** até o sampler existir — esse é precisamente o tipo de "ruído de medição vs. efeito real" que o relatório final da v8 (`Consolidated_Metrics_Report_FINAL.md`, Seção 8) já trata com cuidado estatístico; a v9 ainda não tem o dado de entrada pra fazer o mesmo.

### Achado 18 (Decisão 58) — sondagem TCP restaurada: **FECHADO, não é mais um gap**

`SSHExecutor._tcp_preflight(route)` já existe e já roda como primeira linha de `start_block`, uma vez por rota, fail-closed. Mencionado aqui só porque foi citado no mesmo achado histórico que o item acima — **nenhuma ação necessária**.

---

## (c) O que o piloto NUNCA exercitou na AWS real — com o risco concreto de cada gap

| # | Não exercitado | Risco concreto (não "não testado" genérico) |
|---|---|---|
| 1 | **Múltiplas janelas de tempo (settling/drift)** | A v8 real usa 3 janelas (w01/w02/w03) e já encontrou 10/72 células com tendência de queda estatisticamente significativa mesmo após K=5 execuções de aquecimento (Mann-Kendall, `Consolidated_Metrics_Report_FINAL.md` Seção 8). O piloto rodou **uma única janela, sem aquecimento formal, N=5/célula** — se a campanha oficial também tiver drift de settling (ex.: cache de conexão TLS session resumption, buffers do kernel se ajustando, cache de DNS), **isso nunca seria detectado** com o desenho atual, e os N=30 execuções de cada célula poderiam estar misturando um efeito transiente de "aquecimento" com o efeito real do perfil. |
| 2 | **Retomada após interrupção** | Nenhum checkpoint/resume existe em `orchestrator.py run_pilot` — é um laço `for route: for profile: for run` em memória, que só escreve os 3 arquivos finais (`manifest.json`/`piloto_combined.log`/`piloto_calls.json`) no FIM de tudo (confirmado por leitura direta do código, Decisão 102). **Se a campanha oficial de 960 execuções cair no meio (conexão SSH, auto-desligamento de segurança, falha de instância) depois de, digamos, 700 execuções reais, as 700 são PERDIDAS — nada é salvo incrementalmente.** Isso já quase aconteceu nesta própria rodada (Passo 10, Decisão 101, SSH caiu durante a porta de fumaça) — só não causou perda porque era a porta de fumaça (12 execuções), não a campanha real. |
| 3 | **Rotas/regiões além das 3 pilotadas** | O piloto usou sa-east-1 (L0/L219/L325, controle+servidor+1 cliente). **A campanha oficial precisa de 8 rotas reais** (Decisão 21: `sa-east-1` L0/L123/L219/L325, `us-east-1` L0/L14, `ap-northeast-1` L0/L30) — **`us-east-1` e `ap-northeast-1` nunca foram tocadas por esta rodada em NENHUM momento.** Risco concreto: qualquer problema específico de região (cota de EC2 diferente, AMI não disponível, latência SSH controle→cliente mais alta, política de IAM regional, Security Group com comportamento distinto) só apareceria na hora da campanha oficial, sem nenhum ensaio prévio nessas 2 regiões. |
| 4 | **Escala real N=30** | O piloto usa N=5/perfil/rota (60 execuções totais). A campanha oficial usa N=30/perfil/rota (960 execuções totais) — **16x mais execuções**. Riscos concretos nunca exercitados nessa escala: (i) tamanho acumulado de `piloto_calls.json` — já chegou a **10,9MB com só 60 execuções reais** (Decisão 101) — a 960 execuções, por extrapolação linear, isso seria **~175MB**, um único arquivo JSON que o `consolidate_v9_pilot.py`/`evaluate_criteria.py` precisam carregar inteiro na memória; (ii) throttling de SSH já observado uma vez nesta própria rodada **depois de só 60 execuções** (Decisão 94, "throttling transitório do servidor logo após o Passo 11") — a 960 execuções, sem nenhuma mitigação testada em escala real além do retry simples já aplicado, o risco de throttling recorrente é desconhecido; (iii) espaço em disco das 12→96 capturas dedicadas (4 perfis × 8 rotas, com até 3 tentativas cada pela Decisão 99) nunca foi projetado nem testado. |
| 5 | **Estabilidade de horas** | O piloto completo (Passo 0 a Passo 15) durou pouco mais de 4,5h nesta rodada, com a fase de medição real (Passo 11) levando ~1h03min para 60 execuções+12 capturas. A campanha oficial, com 960 execuções (16x) e 96 capturas dedicadas (8x), projetada linearmente, duraria **ordens de grandeza mais tempo** (ver seção de custo/duração abaixo) — **nunca se testou se a fleet, os containers, ou as sessões SSH permanecem saudáveis por esse tempo.** Riscos concretos: rotação de log não configurada em lugar nenhum (os containers do backend — `auth`/`mongo_seed`/`mockapi` — podem acumular logs sem limite, Decisão 96 já mostrou `mockapi-1` sozinho gerando 363KB de log em UMA execução do piloto); timers do `systemd` de autodesligamento de segurança (Decisão 101/102, `safety_timer.sh.tftpl`) precisariam ser estendidos múltiplas vezes manualmente, como aconteceu nesta própria rodada — sem automação, isso é um risco operacional real de a fleet cair no meio de uma campanha de muitas horas sem ninguém monitorando. |

---

## Resumo executivo (para referência rápida, não substitui a leitura das 5 linhas acima)

| Item | Prioridade | Bloqueante antes da campanha oficial? |
|---|---|---|
| (a) Critério 2: L325 + sentido cliente→servidor | Média — afeta só 1 dos 7 critérios | Recomendável, não necessariamente bloqueante |
| (b) Achado 10, sampler de CPU/steal | **ALTA** | **Sim, pelo próprio registro da Decisão 58** — sem ele, as diferenças entre perfis medidas pela campanha oficial não são estatisticamente confiáveis |
| (c.1) Múltiplas janelas/drift | Média-Alta | Afeta a validade estatística dos N=30, não a execução em si |
| (c.2) Retomada após interrupção | **ALTA** | Risco operacional direto de perder trabalho de muitas horas |
| (c.3) Rotas `us-east-1`/`ap-northeast-1` nunca tocadas | **ALTA** | Risco operacional de a campanha falhar numa região nunca ensaiada |
| (c.4) Escala N=30/960 execuções | Média-Alta | Riscos de throttling/memória/disco conhecidos em escala menor, nunca projetados pra escala real |
| (c.5) Estabilidade de horas | Média | Risco operacional, mitigável com monitoramento manual como nesta rodada |

Nenhuma decisão de escopo é tomada aqui — isso cabe ao Luciano.

---

## Parâmetros adicionais da campanha oficial, definidos por Luciano em 2026-11-09 (pós-piloto)

Estes parâmetros são **só para a campanha oficial e o ensaio multi-região reduzido futuros** — nunca retroativos aos dados já coletados/preservados desta rodada (`piloto-real-aws-2026-11-09-v2`), que continuam intocados. Nenhum deles foi exercitado nesta rodada, então são registrados aqui como requisitos/parâmetros declarados para o próximo ciclo, não como uma Emenda ao pré-registro do piloto já fechado (Decisão 104):

1. **Conta AWS nova, orçamento US$100.** A campanha oficial e o ensaio multi-região reduzido rodarão numa conta AWS separada da usada nas 5 tentativas do piloto — nada é reaproveitado da conta antiga (chaves SSH, EIPs, security groups, estado do Terraform); só código e as imagens Docker já verificadas por conteúdo (Decisões 61/68/101/103) atravessam para a conta nova.
2. **Janelas oficiais, no máximo 30 minutos de intervalo entre uma e a próxima** — bem mais apertado que os ~2,78h de `setup_overhead` observados nesta rodada entre os Passos 0-10. Nunca foi exercitado: este piloto rodou numa única janela corrida, sem qualquer intervalo planejado entre sub-blocos.
3. **Estrutura da campanha oficial:** 4 perfis × 8 rotas × N=30 = 960 execuções, divididas em **3 janelas de N=10** (não 1 de N=30 nem 30 de N=1), mantendo **Hibrido-v8 como perfil de controle**.
4. **Ensaio multi-região reduzido, redefinido:** 4 perfis × 8 rotas × N=2 = 64 execuções, na conta nova, com a MESMA disciplina de ritmo/janela da campanha oficial (item 2), com o objetivo explícito de **zero intervenção manual necessária durante a campanha oficial real** — ou seja, este ensaio deve expor antecipadamente qualquer problema que exigiria uma correção ao vivo.

**Risco concreto de nenhum destes 4 parâmetros ter sido exercitado ainda:** a conta nova significa que absolutamente nada de operacional (cotas de EC2, permissões IAM, VPC/subnets, AMI disponível na região, comportamento de Security Group) foi testado nela — todo o histórico de "já funcionou uma vez" desta rodada (Decisões 61-104) vale só para a conta antiga. A disciplina de 30 minutos entre janelas é mais apertada que QUALQUER intervalo real já observado neste projeto (o próprio `setup_overhead` de 2,78h já excede isso sozinho) — se a entrega de imagens/verificação de proveniência entre janelas não couber em 30 min, a campanha oficial pode não conseguir cumprir sua própria disciplina de janela.

---

## Estimativa de custo/duração — 4 cenários, com a aritmética (nunca um número solto)

**Taxas reais, derivadas diretamente dos dados desta Fase B (Decisões 101/102), nunca estimativas de catálogo isoladas:**
- `avg_s_por_execucao` = 3309,2s / 60 execuções reais = **55,15s/execução** (pooled L0+L219+L325)
- `avg_s_por_captura` = 651s / 12 capturas reais (incluindo retries da Emenda 99) = **54,23s/captura**
- `setup_overhead` (Passos 0-10: apply→smoke gate) = observado **~2,78h** nesta rodada (fixo, não escala com N — mas ESCALA com número de instâncias/imagens a entregar, ver ressalva abaixo)
- `collect_teardown` (Passos 12-15) = observado **~0,75h**
- Taxa de custo: `(n_flex × $0,0958 + $0,0084 + n_eips × $0,005)` USD/h, onde `n_flex` = servidor + clientes (1 por rota), `n_eips` = `n_flex` + controle

| Cenário | Execuções | Capturas | Instâncias (flex/clientes) | Tempo total | Custo total |
|---|---|---|---|---|---|
| **(a) Campanha oficial completa** (8 rotas × 4 perfis × N=30, 3 janelas de N=10, conta nova) | 960 | 32 (4×8) | 9 flex (servidor+8 clientes) | base 2,78+14,71+0,48+0,75=18,72h + 2 intervalos entre as 3 janelas × até 0,5h = **~19,72h** | 0,9206 USD/h × 19,72h = **~US$18,15** |
| **(b) As 3 rotas do piloto, N=30** (4×3×30) | 360 | 12 (4×3) | 4 flex (servidor+3 clientes) | 2,78+5,52+0,18+0,75 = **~9,2h** | 0,4166 USD/h × 9,2h = **~US$3,84** |
| **(c) Ensaio multi-região reduzido** (8 rotas × 4 perfis × N=2, mesma disciplina de janela, conta nova) | 64 | 32 (4×8) | 9 flex (servidor+8 clientes) | base 2,78+0,98+0,48+0,75=4,99h + intervalo(s) de janela (ver nota 4) = **~5,0h a ~5,5h** | 0,9206 USD/h × 5,0–5,5h = **~US$4,60 a US$5,06** |
| **(d) Ensaio curto de janela** (3 rotas × 4 perfis × N=1) | 12 | 12 (4×3) | 4 flex (servidor+3 clientes) | 2,78+0,18+0,18+0,75 = **~3,9h** | 0,4166 USD/h × 3,9h = **~US$1,62** |

**Comparação com o orçamento de US$100 da conta nova (cenários (a) e (c)):**
- (a) campanha oficial: **~US$18,15 computado vs. US$100 de teto** — margem de ~US$81,85 (≈5,5× o custo computado) para absorver o setup do zero da conta nova (IAM, VPC, quotas, retries) e qualquer subestimativa das ressalvas abaixo.
- (c) ensaio multi-região reduzido: **~US$4,60–5,06 computado vs. US$100 de teto** — margem de ~US$95 (≈20×), ou seja, o teto de US$100 não é o fator limitante deste ensaio; o que limita é o tempo real de configuração manual da conta nova, não exercitado/medido aqui.

**Ressalvas explícitas sobre a aritmética acima (nunca escondidas):**
1. `setup_overhead` foi observado com **5 instâncias** (1 servidor + 3 clientes + controle), **na conta antiga já configurada** (VPC/IAM/quotas já existentes de rodadas anteriores). Os cenários (a)/(c) usam **10 instâncias** (8 clientes) **numa conta AWS totalmente nova** (item "Conta AWS nova" acima) — tanto o número maior de hosts quanto a ausência de qualquer configuração prévia de conta provavelmente tornam `setup_overhead` MAIOR que os 2,78h observados, por um fator desconhecido — **não medido, tratado aqui como o mesmo valor por simplicidade, uma subestimativa conhecida e explícita** para (a) e (c).
2. `avg_s_por_execucao`/`avg_s_por_captura` são extrapolações LINEARES de uma amostra de 60 execuções/12 capturas — a seção (c.4) do documento acima já registra que throttling de SSH JÁ apareceu uma vez nesta escala pequena (Decisão 94); em 960 execuções reais, o tempo por execução pode não ser constante.
3. Nenhum destes 4 cenários inclui o sampler de CPU/steal (achado 10, ainda não implementado) nem qualquer uma das lacunas da seção (c) acima — são estimativas de tempo/custo de EXECUÇÃO, não de validade estatística.
4. Para (a), o intervalo entre as 3 janelas (item "Janelas oficiais" acima) foi somado aqui como **2 intervalos × até 30 minutos cada** (o máximo permitido, tratado como teto conservador — pode ser menor na prática). Para (c), a divisão de N=2/célula em janelas não foi especificada por Luciano (a estrutura "3 janelas de N=10" é definida para N=30; não há uma divisão óbvia equivalente para N=2) — por isso o intervalo de (c) é apresentado como uma faixa (0 a 1 intervalo de até 30min, dependendo de o ensaio rodar como 1 passagem única ou como 2 sub-janelas de N=1), não um número único.

Nenhuma recomendação de escopo é feita aqui — os números acima são para o Luciano decidir.
