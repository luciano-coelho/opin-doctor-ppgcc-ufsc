# Latency Report (hybrid, 14ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **14ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 24.4913s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 23.991763 | 0.323743 | não |
| 2 | 24.650008 | 0.334502 | não |
| 3 | 23.880847 | 0.434659 | não |
| 4 | 24.844951 | 0.529445 | não |
| 5 | 24.292806 | 0.022700 | não |
| 6 | 24.338205 | 0.022699 | não |
| 7 | 24.787360 | 0.471854 | não |
| 8 | 24.715771 | 0.400265 | não |
| 9 | 24.260973 | 0.054533 | não |
| 10 | 24.092908 | 0.222597 | não |

## Valores ordenados (ordem crescente)

23.880847, 23.991763, 24.092908, 24.260973, 24.292806, 24.338205, 24.650008, 24.715771, 24.787360, 24.844951

## Mediana e dispersão

- Mediana: **24.315506s**
- Mínimo: 23.880847s
- Máximo: 24.844951s
- Média: 24.385559s
- Desvio padrão (amostral): 0.345331s
- Spread (min/max): 4.0371%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 4.0371% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.
