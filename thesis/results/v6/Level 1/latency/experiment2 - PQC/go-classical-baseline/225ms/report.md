# Latency Report (pqc, 225ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **225ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 45.3603s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 43.848750 | 0.032236 | não |
| 2 | 43.650608 | 0.165906 | não |
| 3 | 43.476822 | 0.339692 | não |
| 4 | 43.784279 | 0.032235 | não |
| 5 | 43.235018 | 0.581497 | não |
| 6 | 43.652011 | 0.164503 | não |
| 7 | 44.510367 | 0.693853 | não |
| 8 | 44.919201 | 1.102687 | não |
| 9 | 47.124096 | 3.307582 | não |
| 10 | 45.951175 | 2.134661 | não |

## Valores ordenados (ordem crescente)

43.235018, 43.476822, 43.650608, 43.652011, 43.784279, 43.848750, 44.510367, 44.919201, 45.951175, 47.124096

## Mediana e dispersão

- Mediana: **43.816514s**
- Mínimo: 43.235018s
- Máximo: 47.124096s
- Média: 44.415233s
- Desvio padrão (amostral): 1.252543s
- Spread (min/max): 8.9952%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 8.9952% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.
