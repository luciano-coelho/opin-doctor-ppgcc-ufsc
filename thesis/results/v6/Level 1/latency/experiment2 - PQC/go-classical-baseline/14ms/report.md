# Latency Report (pqc, 14ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **14ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 11.6188s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 11.005062 | 0.076707 | não |
| 2 | 11.084252 | 0.002483 | não |
| 3 | 10.892855 | 0.188914 | não |
| 4 | 11.127224 | 0.045455 | não |
| 5 | 11.079286 | 0.002483 | não |
| 6 | 10.569481 | 0.512288 | não |
| 7 | 11.453004 | 0.371235 | não |
| 8 | 11.167620 | 0.085851 | não |
| 9 | 11.124637 | 0.042868 | não |
| 10 | 11.007435 | 0.074334 | não |

## Valores ordenados (ordem crescente)

10.569481, 10.892855, 11.005062, 11.007435, 11.079286, 11.084252, 11.124637, 11.127224, 11.167620, 11.453004

## Mediana e dispersão

- Mediana: **11.081769s**
- Mínimo: 10.569481s
- Máximo: 11.453004s
- Média: 11.051086s
- Desvio padrão (amostral): 0.223414s
- Spread (min/max): 8.3592%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 8.3592% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.
