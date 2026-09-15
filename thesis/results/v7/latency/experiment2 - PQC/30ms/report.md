# Latency Report (pqc, 30ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **30ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 13.2478s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 14.436291 | 1.090477 | não |
| 2 | 12.947549 | 0.398265 | não |
| 3 | 12.883945 | 0.461869 | não |
| 4 | 12.912497 | 0.433317 | não |
| 5 | 12.952632 | 0.393182 | não |
| 6 | 12.932884 | 0.412930 | não |
| 7 | 13.754654 | 0.408840 | não |
| 8 | 15.571856 | 2.226042 | não |
| 9 | 14.115930 | 0.770116 | não |
| 10 | 13.738996 | 0.393182 | não |

## Valores ordenados (ordem crescente)

12.883945, 12.912497, 12.932884, 12.947549, 12.952632, 13.738996, 13.754654, 14.115930, 14.436291, 15.571856

## Mediana e dispersão

- Mediana: **13.345814s**
- Mínimo: 12.883945s
- Máximo: 15.571856s
- Média: 13.624723s
- Desvio padrão (amostral): 0.892321s
- Spread (min/max): 20.8625%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 20.8625% entre as 10 execuções. **Spread elevado -- investigar antes de aceitar este cenário como concluído.**
