# Latency Report (pqc, 225ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **225ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 44.9000s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 43.588028 | 0.106939 | não |
| 2 | 43.632521 | 0.062446 | não |
| 3 | 44.034290 | 0.339323 | não |
| 4 | 43.757413 | 0.062446 | não |
| 5 | 43.426204 | 0.268763 | não |
| 6 | 43.954968 | 0.260001 | não |
| 7 | 43.302200 | 0.392767 | não |
| 8 | 43.329099 | 0.365868 | não |
| 9 | 47.229766 | 3.534799 | não |
| 10 | 51.107624 | 7.412657 | não |

## Valores ordenados (ordem crescente)

43.302200, 43.329099, 43.426204, 43.588028, 43.632521, 43.757413, 43.954968, 44.034290, 47.229766, 51.107624

## Mediana e dispersão

- Mediana: **43.694967s**
- Mínimo: 43.302200s
- Máximo: 51.107624s
- Média: 44.736211s
- Desvio padrão (amostral): 2.520201s
- Spread (min/max): 18.0255%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 18.0255% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.
