# Latency Report (hybrid, 225ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **225ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 47.1611s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 46.560879 | 0.144269 | não |
| 2 | 46.771201 | 0.354591 | não |
| 3 | 47.877645 | 1.461035 | não |
| 4 | 46.128636 | 0.287974 | não |
| 5 | 46.297667 | 0.118944 | não |
| 6 | 45.769027 | 0.647583 | não |
| 7 | 45.982958 | 0.433652 | não |
| 8 | 46.535554 | 0.118944 | não |
| 9 | 47.278607 | 0.861997 | não |
| 10 | 45.476259 | 0.940351 | não |

## Valores ordenados (ordem crescente)

45.476259, 45.769027, 45.982958, 46.128636, 46.297667, 46.535554, 46.560879, 46.771201, 47.278607, 47.877645

## Mediana e dispersão

- Mediana: **46.416610s**
- Mínimo: 45.476259s
- Máximo: 47.877645s
- Média: 46.467843s
- Desvio padrão (amostral): 0.714987s
- Spread (min/max): 5.2805%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 5.2805% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.
