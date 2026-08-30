# Latency Report (pqc, 14ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **14ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 13.7457s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 13.328915 | 0.546016 | não |
| 2 | 12.537777 | 0.245122 | não |
| 3 | 12.493231 | 0.289668 | não |
| 4 | 12.134393 | 0.648506 | não |
| 5 | 11.843594 | 0.939305 | não |
| 6 | 13.028021 | 0.245122 | não |
| 7 | 13.913525 | 1.130626 | não |
| 8 | 14.426413 | 1.643514 | não |
| 9 | 14.375406 | 1.592507 | não |
| 10 | 12.535008 | 0.247891 | não |

## Valores ordenados (ordem crescente)

11.843594, 12.134393, 12.493231, 12.535008, 12.537777, 13.028021, 13.328915, 13.913525, 14.375406, 14.426413

## Mediana e dispersão

- Mediana: **12.782899s**
- Mínimo: 11.843594s
- Máximo: 14.426413s
- Média: 13.061628s
- Desvio padrão (amostral): 0.919248s
- Spread (min/max): 21.8077%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 21.8077% entre as 10 execuções. **Spread elevado -- investigar antes de aceitar este cenário como concluído.**
