# Latency Report (pqc, 14ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **14ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 23.1787s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 22.845665 | 0.281855 | não |
| 2 | 24.259412 | 1.131892 | não |
| 3 | 23.636707 | 0.509187 | não |
| 4 | 23.165940 | 0.038419 | não |
| 5 | 22.804971 | 0.322550 | não |
| 6 | 23.956891 | 0.829370 | não |
| 7 | 23.193799 | 0.066278 | não |
| 8 | 22.975091 | 0.152430 | não |
| 9 | 23.089101 | 0.038419 | não |
| 10 | 22.478886 | 0.648635 | não |

## Valores ordenados (ordem crescente)

22.478886, 22.804971, 22.845665, 22.975091, 23.089101, 23.165940, 23.193799, 23.636707, 23.956891, 24.259412

## Mediana e dispersão

- Mediana: **23.127520s**
- Mínimo: 22.478886s
- Máximo: 24.259412s
- Média: 23.240646s
- Desvio padrão (amostral): 0.551273s
- Spread (min/max): 7.9209%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 7.9209% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.
