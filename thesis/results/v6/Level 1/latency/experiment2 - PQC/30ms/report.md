# Latency Report (pqc, 30ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **30ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 13.7311s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 13.221073 | 0.037406 | não |
| 2 | 13.038356 | 0.220123 | não |
| 3 | 13.288884 | 0.030405 | não |
| 4 | 13.408170 | 0.149691 | não |
| 5 | 13.982100 | 0.723621 | não |
| 6 | 13.480138 | 0.221659 | não |
| 7 | 13.056604 | 0.201875 | não |
| 8 | 13.406305 | 0.147826 | não |
| 9 | 12.899200 | 0.359279 | não |
| 10 | 13.228074 | 0.030405 | não |

## Valores ordenados (ordem crescente)

12.899200, 13.038356, 13.056604, 13.221073, 13.228074, 13.288884, 13.406305, 13.408170, 13.480138, 13.982100

## Mediana e dispersão

- Mediana: **13.258479s**
- Mínimo: 12.899200s
- Máximo: 13.982100s
- Média: 13.300890s
- Desvio padrão (amostral): 0.301951s
- Spread (min/max): 8.3951%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 8.3951% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.
