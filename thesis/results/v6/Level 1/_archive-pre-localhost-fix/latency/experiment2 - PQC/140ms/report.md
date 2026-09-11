# Latency Report (pqc, 140ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **140ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 43.1666s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 43.128825 | 0.156564 | não |
| 2 | 42.321341 | 0.650920 | não |
| 3 | 43.566404 | 0.594143 | não |
| 4 | 43.081169 | 0.108908 | não |
| 5 | 42.649444 | 0.322817 | não |
| 6 | 42.842028 | 0.130233 | não |
| 7 | 43.058476 | 0.086215 | não |
| 8 | 42.767249 | 0.205012 | não |
| 9 | 42.886045 | 0.086216 | não |
| 10 | 43.841227 | 0.868966 | não |

## Valores ordenados (ordem crescente)

42.321341, 42.649444, 42.767249, 42.842028, 42.886045, 43.058476, 43.081169, 43.128825, 43.566404, 43.841227

## Mediana e dispersão

- Mediana: **42.972261s**
- Mínimo: 42.321341s
- Máximo: 43.841227s
- Média: 43.014221s
- Desvio padrão (amostral): 0.438259s
- Spread (min/max): 3.5913%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 3.5913% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.
