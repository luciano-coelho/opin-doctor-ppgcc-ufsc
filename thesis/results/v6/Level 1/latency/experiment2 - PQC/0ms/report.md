# Latency Report (pqc, 0ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **0ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 12.8899s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 10.152048 | 0.692067 | não |
| 2 | 9.806480 | 1.037635 | não |
| 3 | 9.672633 | 1.171482 | não |
| 4 | 9.864383 | 0.979732 | não |
| 5 | 9.940903 | 0.903212 | não |
| 6 | 11.536182 | 0.692067 | não |
| 7 | 11.912527 | 1.068412 | não |
| 8 | 15.543365 | 4.699250 | não |
| 9 | 16.782979 | 5.938864 | não |
| 10 | 13.628671 | 2.784556 | não |

## Valores ordenados (ordem crescente)

9.672633, 9.806480, 9.864383, 9.940903, 10.152048, 11.536182, 11.912527, 13.628671, 15.543365, 16.782979

## Mediana e dispersão

- Mediana: **10.844115s**
- Mínimo: 9.672633s
- Máximo: 16.782979s
- Média: 11.884017s
- Desvio padrão (amostral): 2.595230s
- Spread (min/max): 73.5099%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 73.5099% entre as 10 execuções. **Spread elevado -- investigar antes de aceitar este cenário como concluído.**
