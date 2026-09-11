# Latency Report (hybrid, 14ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **14ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 24.6598s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 23.989446 | 0.346945 | não |
| 2 | 25.868256 | 1.531865 | não |
| 3 | 24.285359 | 0.051032 | não |
| 4 | 24.387424 | 0.051033 | não |
| 5 | 24.459765 | 0.123374 | não |
| 6 | 24.445809 | 0.109418 | não |
| 7 | 24.394058 | 0.057667 | não |
| 8 | 24.262019 | 0.074372 | não |
| 9 | 24.283752 | 0.052639 | não |
| 10 | 24.051205 | 0.285186 | não |

## Valores ordenados (ordem crescente)

23.989446, 24.051205, 24.262019, 24.283752, 24.285359, 24.387424, 24.394058, 24.445809, 24.459765, 25.868256

## Mediana e dispersão

- Mediana: **24.336391s**
- Mínimo: 23.989446s
- Máximo: 25.868256s
- Média: 24.442709s
- Desvio padrão (amostral): 0.524860s
- Spread (min/max): 7.8318%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 7.8318% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.
