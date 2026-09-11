# Latency Report (hybrid, 320ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **320ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 74.3424s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 73.908313 | 0.013714 | não |
| 2 | 73.765000 | 0.129599 | não |
| 3 | 74.102205 | 0.207605 | não |
| 4 | 73.880886 | 0.013713 | não |
| 5 | 73.249232 | 0.645367 | não |
| 6 | 73.776393 | 0.118206 | não |
| 7 | 74.457189 | 0.562590 | não |
| 8 | 73.540488 | 0.354112 | não |
| 9 | 74.016937 | 0.122338 | não |
| 10 | 75.082358 | 1.187759 | não |

## Valores ordenados (ordem crescente)

73.249232, 73.540488, 73.765000, 73.776393, 73.880886, 73.908313, 74.016937, 74.102205, 74.457189, 75.082358

## Mediana e dispersão

- Mediana: **73.894599s**
- Mínimo: 73.249232s
- Máximo: 75.082358s
- Média: 73.977900s
- Desvio padrão (amostral): 0.504314s
- Spread (min/max): 2.5026%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 2.5026% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.
