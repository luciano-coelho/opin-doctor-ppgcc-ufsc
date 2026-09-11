# Latency Report (hybrid, 0ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **0ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 10.9764s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 10.606860 | 0.290264 | não |
| 2 | 11.071974 | 0.755378 | não |
| 3 | 10.748647 | 0.432051 | não |
| 4 | 10.356606 | 0.040010 | não |
| 5 | 10.276586 | 0.040010 | não |
| 6 | 9.990589 | 0.326007 | não |
| 7 | 10.489996 | 0.173400 | não |
| 8 | 10.153020 | 0.163576 | não |
| 9 | 10.136106 | 0.180490 | não |
| 10 | 10.231114 | 0.085482 | não |

## Valores ordenados (ordem crescente)

9.990589, 10.136106, 10.153020, 10.231114, 10.276586, 10.356606, 10.489996, 10.606860, 10.748647, 11.071974

## Mediana e dispersão

- Mediana: **10.316596s**
- Mínimo: 9.990589s
- Máximo: 11.071974s
- Média: 10.406150s
- Desvio padrão (amostral): 0.327873s
- Spread (min/max): 10.8240%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 10.8240% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.
