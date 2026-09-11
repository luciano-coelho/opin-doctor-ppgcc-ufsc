# Latency Report (pqc, 320ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **320ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 64.3243s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 59.703856 | 0.738661 | não |
| 2 | 58.727058 | 0.238137 | não |
| 3 | 58.688897 | 0.276298 | não |
| 4 | 58.690353 | 0.274842 | não |
| 5 | 58.938425 | 0.026770 | não |
| 6 | 58.359166 | 0.606029 | não |
| 7 | 59.416828 | 0.451633 | não |
| 8 | 59.002898 | 0.037703 | não |
| 9 | 58.991964 | 0.026770 | não |
| 10 | 59.010884 | 0.045689 | não |

## Valores ordenados (ordem crescente)

58.359166, 58.688897, 58.690353, 58.727058, 58.938425, 58.991964, 59.002898, 59.010884, 59.416828, 59.703856

## Mediana e dispersão

- Mediana: **58.965195s**
- Mínimo: 58.359166s
- Máximo: 59.703856s
- Média: 58.953033s
- Desvio padrão (amostral): 0.384262s
- Spread (min/max): 2.3042%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 2.3042% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.
