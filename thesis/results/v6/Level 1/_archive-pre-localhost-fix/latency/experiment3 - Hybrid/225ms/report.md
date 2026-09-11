# Latency Report (hybrid, 225ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **225ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 58.5388s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 58.968267 | 0.309054 | não |
| 2 | 58.300627 | 0.976694 | não |
| 3 | 58.639568 | 0.637753 | não |
| 4 | 59.460794 | 0.183473 | não |
| 5 | 59.346369 | 0.069048 | não |
| 6 | 58.455143 | 0.822178 | não |
| 7 | 59.291812 | 0.014491 | não |
| 8 | 59.262830 | 0.014491 | não |
| 9 | 59.385998 | 0.108677 | não |
| 10 | 60.028836 | 0.751515 | não |

## Valores ordenados (ordem crescente)

58.300627, 58.455143, 58.639568, 58.968267, 59.262830, 59.291812, 59.346369, 59.385998, 59.460794, 60.028836

## Mediana e dispersão

- Mediana: **59.277321s**
- Mínimo: 58.300627s
- Máximo: 60.028836s
- Média: 59.114024s
- Desvio padrão (amostral): 0.525032s
- Spread (min/max): 2.9643%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 2.9643% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.
