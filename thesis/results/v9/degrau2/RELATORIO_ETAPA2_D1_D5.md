# Degrau 2, Etapa 2 — resultados das 5 hipóteses (D1-D5)

Luciano Figueiredo Coelho | PPGCC/LabSEC/UFSC. **Rascunho para revisão — não considerar final/publicado.** Segue `PLANO_DEGRAU2.md` + Emenda 1 integralmente, sem alterar critérios, testes, sementes ou regras de agregação. Todo número vem de `scripts/etapa2_analise_d1_d5.py`, lendo diretamente `campaign_data/round{1,2}/runs_raw/*.json` e `hardware_probe/probe_overhead_result.json` — nenhum valor digitado à mão. Saída completa (todos os números, inclusive os não citados aqui): `ETAPA2_RESULTADOS.json`.

## Regra das 2 rodadas (aplicada antes de qualquer análise)

Mann-Whitney exato bilateral, Rodada 1 (seed `20261117`) × Rodada 2 (seed `20261118`), por rota × métrica (`t_fluxo_fino_seconds` + 6 componentes de `phase_accounting` = 7 métricas × 4 rotas = 28 testes), Holm sobre os 28. **Nenhuma das 28 comparações teve p ajustado <0,05 — as duas rodadas puderam ser agrupadas em todas as análises abaixo**, sem nenhuma divergência real a reportar.

**Escolha metodológica explícita (não coberta literalmente pelo texto do plano, decidida ANTES de ver os p-valores):** "célula" nesta regra = rota (4, não 12), agrupando os 3 perfis dentro de cada rota (n=45/rodada) — a única leitura consistente com o número fixo "4 células × 7 métricas = 28 testes" já escrito no plano. Isso não afeta nenhum critério de decisão downstream, já que todas as 28 comparações vieram não-significativas.

## D1 — heterogeneidade entre instalações é artefato do orquestrador?

| Par | Mediana A (ms) | Mediana B (ms) | HL diff (ms) | IC95% bootstrap (ms) | Banda ±15% (ms) | Dentro da banda? |
|---|---|---|---|---|---|---|
| sa×us | 1808,4 | 1828,3 | -14,3 | [-37,9; 12,5] | ±271,3 | Sim |
| sa×ap | 1808,4 | 1879,7 | -70,2 | [-96,3; -44,0] | ±271,3 | Sim |
| us×ap | 1828,3 | 1879,7 | -56,6 | [-83,3; -30,8] | ±274,3 | Sim |

**Veredito: SUSTENTADA** (heterogeneidade do T_fluxo PAREDE é majoritariamente artefato de medição) — os 3 ICs caem inteiramente dentro de ±15% da menor mediana do par, exatamente o critério da Emenda 1. Note-se que 2 dos 3 pares são estatisticamente significativos mesmo após Holm (sa×ap e us×ap, p Holm=0,0014) — a diferença é real e detectável, mas pequena em magnitude relativa (≤70ms, dentro da banda de tolerância pré-registrada de ~271-274ms). O terceiro par (sa×us) não é significativo (p Holm=0,321). Esses p-valores são puramente descritivos (convenção geral de testes do plano) — a decisão SUSTENTADA/REFUTADA/PARCIAL de D1 usa exclusivamente o critério de IC-vs-banda da Emenda 1, nunca p-valor. **Achado de processo:** a primeira versão deste script tinha os rótulos SUSTENTADA/REFUTADA invertidos em relação à definição literal da Emenda 1 — corrigido antes deste relatório ser escrito, citado aqui por transparência.

## D2 — overhead (parede−fino) segue a regressão do Item 5b do Degrau 1?

| Rota | Overhead observado (ms) | RTT real (ms) |
|---|---|---|
| L0-sa-east-1 | 456,1 | 2,25 |
| L0-us-east-1 | 2106,4 | 113,40 |
| L0-ap-northeast-1 | 4438,2 | 259,11 |
| L123 | 2290,7 | 124,50 |

Regressão (4 pontos): inclinação = **15,53 ms/ms**, intercepto = **384,67 ms**.

**Veredito: REFUTADA.** Intercepto (384,67ms) está dentro da faixa `[0;1.925]`ms, mas a inclinação (15,53) fica **fora** de `[12,2;15,3]` por uma margem pequena (0,23). Por construção do critério ("REFUTADA caso qualquer um dos dois fique fora"), basta um dos dois falhar. Com apenas 4 pontos, esta é a mesma fragilidade estatística já declarada no pré-registro — a conclusão é sensível a um único ponto.

## D2b — regressão do "SSH puro" vs RTT real (adicional, sem critério SUSTENTADA/REFUTADA)

Inclinação = **11,77** ms de SSH puro por ms de RTT (vs. `b≈13,17` do Degrau 1 — mesma ordem de grandeza, nunca comparável em nível absoluto). Intercepto = 230,18ms (não previsto por nenhum modelo anterior, conforme já declarado na Emenda 1).

## D3 — ordem Classic/PQC/Hybrid e inversão em L0-sa-east-1 persistem no T_fluxo fino?

| Rota | Ordem observada (fino) | Ordem oficial (parede) | Persiste? |
|---|---|---|---|
| L0-sa-east-1 | Classic < PQC < Hybrid | PQC < Classic < Hybrid | **Não** |
| L0-us-east-1 | Classic < PQC < Hybrid | Classic < PQC < Hybrid | Sim |
| L0-ap-northeast-1 | Classic < PQC < Hybrid | Classic < PQC < Hybrid | Sim |
| L123 | Classic < PQC < Hybrid | Classic < PQC < Hybrid | Sim |

**Veredito: SUSTENTADA** (persiste em 3/4 rotas). **A inversão de L0-sa-east-1 NÃO persiste no T_fluxo fino** — no parede, PQC era mais rápido que Classic nessa instalação (diferença atribuída ao viés de 26-45ms da chave RSA do Classic, Degrau 1); no fino, Classic volta a ser (ligeiramente) mais rápido que PQC, mas a diferença (7,8ms) é pequena e **não significativa** (p Holm=0,546), consistente com a previsão específica da Emenda 1.

**Previsão específica de L0-sa-east-1 (PQC−Classic, mesma convenção da Emenda 1):** observado **+7,8ms**, fora da faixa prevista `[-43;-24]`ms, mas **não-significativo como previsto** (p Holm=0,546 ≥0,05). A não-significância bateu com a previsão; a magnitude e o sinal não (a Emenda 1 previa PQC mais barato que Classic por ~24-43ms; o observado é PQC muito levemente mais caro, 7,8ms, dentro do ruído).

Testes por par (8, Holm): todos os pares Classic×PQC são não-significativos (p Holm entre 0,09 e 0,55); todos os pares PQC×Hybrid são significativos (p Holm <0,012, a maioria <0,0001) — Hybrid é consistentemente mais caro que PQC em todas as 4 rotas.

## D4a — Δ(PQC/Hybrid vs Classic) no T_fluxo fino é dominado por signing+verification?

**Nota metodológica (pós-auditoria):** o plano define a fração como componente ÷ Δ(T_fluxo fino) (escalar). Como Δfino é pequeno em várias células (há cancelamento entre componentes de sinais opostos), essa fração literal produz valores >100% ou com oscilação de sinal — reportados abaixo exatamente como saem, sem arredondar para dentro de `[0%,100%]`.

| Rota | PQC−Classic: sign+verif / http_calls (Δfino, ms) | Hybrid−PQC: sign+verif / http_calls (Δfino, ms) | Confirma (ambos pares)? |
|---|---|---|---|
| L0-sa-east-1 | 332,3% / -300,5% (7,8) | 8,1% / 65,3% (102,6) | Não |
| L0-us-east-1 | 86,0% / 76,2% (27,4) | 6,9% / 39,2% (84,1) | Não |
| L0-ap-northeast-1 | 176,0% / -23,8% (14,9) | 4,7% / 52,8% (157,8) | Não |

**Veredito: REFUTADA** (0/3 rotas confirmam os dois pares — em nenhuma rota o par PQC−Classic simultaneamente atinge sign+verif≥60% E http_calls<20%, por conta do segundo limiar; L0-us-east-1 e L0-ap-northeast-1 atingem facilmente o limiar de signing+verification, mas falham em `http_calls<20%`). **Achado honesto, não forçado na hipótese original:** a instabilidade numérica em si (fracões >100%, sinais trocando) já é um resultado — ela aparece porque Δfino é pequeno e os componentes individuais (signing positivo, http_calls às vezes negativo) quase se cancelam, não porque o cálculo esteja errado. O par Hybrid−PQC nunca é dominado por signing+verification (sempre <9%) — fica concentrado em `http_calls_seconds` (39-65%) e no resíduo (ver `ETAPA2_RESULTADOS.json`), consistente com a leitura do Degrau 1 de que o custo duplo do Hybrid está mais ligado ao handshake/TLS-KEM-proxy e a round-trips adicionais do que à assinatura/verificação em si.

## D4b — o acréscimo de Δfino ao ir de L0-sa-east-1 para L123 é dominado por resíduo+HTTP?

| Par | Incremento total (ms) | residual+http | signing+verif | Confirma? |
|---|---|---|---|---|
| Classic→PQC | 16,7 | 59,5% | 6,6% | Não (por 0,5 ponto percentual) |
| PQC→Hybrid | -30,7 | 78,0% | 5,6% | **Sim** |

**Veredito: PARCIAL** (1/2 pares confirma). O par PQC→Hybrid confirma claramente a previsão. O par Classic→PQC fica a apenas 0,5 ponto percentual do limiar de 60% (59,5%) — tecnicamente REFUTA esse sub-teste pelo critério exato, mas a direção e a ordem de grandeza batem com a previsão; a fração de signing+verification (6,6%) está bem dentro do limite `<40%` esperado.

## D5 — razão Δresíduo_fino/RTT real em L123 vs L0-sa-east-1

Mediana resíduo fino: L0-sa-east-1 = 1388,7ms; L123 = 3599,6ms. Δ = 2210,9ms. RTT real L123 = 124,50ms. **Razão = 17,76**.

**Veredito: SUSTENTADA** (dentro de `[13,6;26]`) — compatível com a leitura de que o componente de SSH explica o coeficiente `b` do Degrau 1.

## Resumo

| Hipótese | Veredito |
|---|---|
| D1 | SUSTENTADA |
| D2 | REFUTADA (por margem pequena na inclinação) |
| D2b | descritiva (inclinação 11,77 vs b≈13,17) |
| D3 | SUSTENTADA (inversão de L0-sa NÃO persiste no fino) |
| D4a | REFUTADA |
| D4b | PARCIAL |
| D5 | SUSTENTADA |

## Separação pré-registrado × exploratório

Todos os vereditos acima seguem exatamente os critérios/testes/sementes do `PLANO_DEGRAU2.md` + Emenda 1, sem nenhuma alteração após ver os dados. As seguintes observações são **exploratórias** (não fazem parte de nenhum critério pré-registrado, só descrevem o padrão encontrado nos números já calculados): a direção negativa de `http_calls_seconds` em D4a para 2 das 3 rotas L0; a concentração do custo Hybrid−PQC em `http_calls_seconds`+`residual_seconds`; o fato de 2/3 pares de D1 serem estatisticamente significativos apesar de SUSTENTADA.

## Correções feitas após auditoria independente (antes deste relatório ser tratado como final)

Uma auditoria independente (agente separado, nunca leu nenhum arquivo de chave) encontrou e eu corrigi:

1. **[Alta]** D4a/D4b usavam um denominador não-declarado (soma das magnitudes absolutas dos 6 componentes) em vez do denominador literal do plano (o próprio Δfino/incremento). Corrigido — agora usa o denominador literal, com a instabilidade numérica resultante (fracões >100%, sinais trocando quando Δfino é pequeno) reportada explicitamente nas tabelas acima, nunca escondida.
2. **[Média]** D3's previsão de L0-sa-east-1 tinha um erro de sinal (negava PQC−Classic antes de comparar com uma faixa já definida para PQC−Classic). Corrigido — sem efeito no veredito porque a magnitude já ficava fora da faixa nos dois sinais, mas o valor relatado agora é o correto.
3. **[Baixa]** Dois booleanos de D2 (`slope_in_range`/`intercept_in_range`) serializavam como string `"True"`/`"False"` no JSON por um `numpy.bool_` não convertido — corrigido para `bool` nativo; nunca afetou o veredito em si (calculado antes da serialização).
4. **[Baixa, latente]** D4a/D4b nunca checavam a regra das 2 rodadas antes de agrupar — sem efeito real nesta rodada (nenhuma divergência existe), mas adicionada uma guarda que falha alto se isso mudar numa rodada futura, em vez de agrupar silenciosamente.
5. Também adicionados: Holm sobre os 3 p-valores descritivos de D1 (convenção geral do plano, nunca usada na decisão de D1) e uma nota explícita sobre a semente de bootstrap usada quando um par de D1 é agrupado (Rodada 1, `20261117` — o plano não cobre literalmente o caso agrupado).

Nenhuma dessas correções mudou os 6 vereditos finais (D1 SUSTENTADA, D2 REFUTADA, D3 SUSTENTADA, D4a REFUTADA, D4b PARCIAL, D5 SUSTENTADA) — mudaram números de suporte e, em D4a/D4b, a magnitude exata das frações reportadas.

## Achado operacional não relacionado às hipóteses

12/12 capturas dedicadas falharam na Rodada 2 (vs 2/12 na Rodada 1) — mesma categoria de erro já aceita ("decifragem incompleta", nunca "divergência de tamanho"), mas com taxa muito maior, sugerindo causa sistêmica da janela da Rodada 2. Não afeta nenhum número usado nas análises D1-D5 acima (campo ortogonal). Detalhe completo: `DECISIONS.md`, Decisão 214.
