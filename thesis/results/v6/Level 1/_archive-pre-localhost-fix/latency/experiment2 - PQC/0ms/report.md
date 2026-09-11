# Latency Report (pqc, 0ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **0ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 20.2570s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 20.789102 | 0.081694 | não |
| 2 | 25.501261 | 4.793853 | não |
| 3 | 21.113548 | 0.406140 | não |
| 4 | 27.432862 | 6.725454 | não |
| 5 | 20.625713 | 0.081695 | não |
| 6 | 20.877039 | 0.169631 | não |
| 7 | 20.208410 | 0.498998 | não |
| 8 | 20.447521 | 0.259887 | não |
| 9 | 20.320244 | 0.387164 | não |
| 10 | 20.304951 | 0.402457 | não |

## Valores ordenados (ordem crescente)

20.208410, 20.304951, 20.320244, 20.447521, 20.625713, 20.789102, 20.877039, 21.113548, 25.501261, 27.432862

## Mediana e dispersão

- Mediana: **20.707408s**
- Mínimo: 20.208410s
- Máximo: 27.432862s
- Média: 21.762065s
- Desvio padrão (amostral): 2.536954s
- Spread (min/max): 35.7497%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 35.7497% entre as 10 execuções. **Spread elevado -- investigar antes de aceitar este cenário como concluído.**
