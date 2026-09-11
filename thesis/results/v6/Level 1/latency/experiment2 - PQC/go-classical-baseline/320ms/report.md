# Latency Report (pqc, 320ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **320ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 59.1872s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 60.098389 | 1.311833 | não |
| 2 | 58.842878 | 0.056322 | não |
| 3 | 58.529362 | 0.257194 | não |
| 4 | 58.836522 | 0.049966 | não |
| 5 | 64.420355 | 5.633799 | não |
| 6 | 58.736589 | 0.049967 | não |
| 7 | 58.526830 | 0.259726 | não |
| 8 | 59.220688 | 0.434132 | não |
| 9 | 58.465956 | 0.320600 | não |
| 10 | 58.631649 | 0.154907 | não |

## Valores ordenados (ordem crescente)

58.465956, 58.526830, 58.529362, 58.631649, 58.736589, 58.836522, 58.842878, 59.220688, 60.098389, 64.420355

## Mediana e dispersão

- Mediana: **58.786556s**
- Mínimo: 58.465956s
- Máximo: 64.420355s
- Média: 59.430922s
- Desvio padrão (amostral): 1.818594s
- Spread (min/max): 10.1844%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 10.1844% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.
