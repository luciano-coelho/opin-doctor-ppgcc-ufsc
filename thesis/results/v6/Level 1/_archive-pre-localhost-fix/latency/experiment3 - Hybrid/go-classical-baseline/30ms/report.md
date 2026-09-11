# Latency Report (hybrid, 30ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **30ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 26.7255s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 26.574507 | 0.166487 | não |
| 2 | 26.791623 | 0.050629 | não |
| 3 | 26.565977 | 0.175017 | não |
| 4 | 26.690366 | 0.050628 | não |
| 5 | 26.593246 | 0.147748 | não |
| 6 | 26.896019 | 0.155024 | não |
| 7 | 26.825723 | 0.084729 | não |
| 8 | 26.405837 | 0.335158 | não |
| 9 | 26.847859 | 0.106865 | não |
| 10 | 28.657738 | 1.916743 | não |

## Valores ordenados (ordem crescente)

26.405837, 26.565977, 26.574507, 26.593246, 26.690366, 26.791623, 26.825723, 26.847859, 26.896019, 28.657738

## Mediana e dispersão

- Mediana: **26.740994s**
- Mínimo: 26.405837s
- Máximo: 28.657738s
- Média: 26.884889s
- Desvio padrão (amostral): 0.641796s
- Spread (min/max): 8.5280%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 8.5280% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.
