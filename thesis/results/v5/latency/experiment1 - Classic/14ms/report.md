# Latency Report (classic, 14ms, 10 runs)

Experimento (perfil): **classic**
Latência aplicada (cenário): **14ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 6.0342s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 5.978419 | 0.010587 | não |
| 2 | 6.379523 | 0.411691 | não |
| 3 | 5.179771 | 0.788061 | não |
| 4 | 5.347834 | 0.619998 | não |
| 5 | 5.214561 | 0.753271 | não |
| 6 | 5.228548 | 0.739283 | não |
| 7 | 7.012761 | 1.044930 | não |
| 8 | 5.957244 | 0.010587 | não |
| 9 | 6.124757 | 0.156925 | não |
| 10 | 6.257939 | 0.290108 | não |

## Valores ordenados (ordem crescente)

5.179771, 5.214561, 5.228548, 5.347834, 5.957244, 5.978419, 6.124757, 6.257939, 6.379523, 7.012761

## Mediana e dispersão

- Mediana: **5.967831s**
- Mínimo: 5.179771s
- Máximo: 7.012761s
- Média: 5.868136s
- Desvio padrão (amostral): 0.613766s
- Spread (min/max): 35.3875%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 35.3875% entre as 10 execuções. **Spread elevado -- investigar antes de aceitar este cenário como concluído.**
