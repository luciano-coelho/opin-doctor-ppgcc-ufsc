# Latency Report (hybrid, 140ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **140ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 33.1556s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 32.269760 | 0.596917 | não |
| 2 | 32.251235 | 0.615442 | não |
| 3 | 32.864202 | 0.002475 | não |
| 4 | 36.274152 | 3.407475 | não |
| 5 | 32.869153 | 0.002476 | não |
| 6 | 32.885283 | 0.018606 | não |
| 7 | 34.807035 | 1.940358 | não |
| 8 | 36.244664 | 3.377987 | não |
| 9 | 32.296335 | 0.570342 | não |
| 10 | 32.721739 | 0.144938 | não |

## Valores ordenados (ordem crescente)

32.251235, 32.269760, 32.296335, 32.721739, 32.864202, 32.869153, 32.885283, 34.807035, 36.244664, 36.274152

## Mediana e dispersão

- Mediana: **32.866677s**
- Mínimo: 32.251235s
- Máximo: 36.274152s
- Média: 33.548356s
- Desvio padrão (amostral): 1.606291s
- Spread (min/max): 12.4737%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 12.4737% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.
