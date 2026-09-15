# Latency Report (classic, 225ms, 10 runs)

Experimento (perfil): **classic**
Latência aplicada (cenário): **225ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 39.0923s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 38.368775 | 0.113003 | não |
| 2 | 38.481430 | 0.000348 | não |
| 3 | 38.485698 | 0.003920 | não |
| 4 | 38.455619 | 0.026159 | não |
| 5 | 38.440863 | 0.040915 | não |
| 6 | 38.414288 | 0.067490 | não |
| 7 | 38.482126 | 0.000348 | não |
| 8 | 38.490076 | 0.008298 | não |
| 9 | 38.512521 | 0.030743 | não |
| 10 | 38.542924 | 0.061146 | não |

## Valores ordenados (ordem crescente)

38.368775, 38.414288, 38.440863, 38.455619, 38.481430, 38.482126, 38.485698, 38.490076, 38.512521, 38.542924

## Mediana e dispersão

- Mediana: **38.481778s**
- Mínimo: 38.368775s
- Máximo: 38.542924s
- Média: 38.467432s
- Desvio padrão (amostral): 0.049881s
- Spread (min/max): 0.4539%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 0.4539% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.
