# Latency Report (hybrid, 140ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **140ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 33.2032s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 32.571674 | 0.116755 | não |
| 2 | 32.860389 | 0.405470 | não |
| 3 | 32.892451 | 0.437532 | não |
| 4 | 32.091460 | 0.363459 | não |
| 5 | 33.151824 | 0.696905 | não |
| 6 | 32.703569 | 0.248650 | não |
| 7 | 31.800380 | 0.654539 | não |
| 8 | 32.338164 | 0.116755 | não |
| 9 | 31.957242 | 0.497677 | não |
| 10 | 31.864068 | 0.590851 | não |

## Valores ordenados (ordem crescente)

31.800380, 31.864068, 31.957242, 32.091460, 32.338164, 32.571674, 32.703569, 32.860389, 32.892451, 33.151824

## Mediana e dispersão

- Mediana: **32.454919s**
- Mínimo: 31.800380s
- Máximo: 33.151824s
- Média: 32.423122s
- Desvio padrão (amostral): 0.480487s
- Spread (min/max): 4.2498%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 4.2498% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.
