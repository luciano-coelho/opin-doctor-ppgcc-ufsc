# Latency Report (hybrid, 14ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **14ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 12.7209s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 13.263860 | 0.973583 | não |
| 2 | 13.240046 | 0.997397 | não |
| 3 | 12.868676 | 1.368766 | não |
| 4 | 14.337731 | 0.100288 | não |
| 5 | 15.305140 | 1.067697 | não |
| 6 | 16.470893 | 2.233451 | não |
| 7 | 11.843072 | 2.394371 | não |
| 8 | 14.137154 | 0.100288 | não |
| 9 | 15.605321 | 1.367878 | não |
| 10 | 17.914788 | 3.677346 | não |

## Valores ordenados (ordem crescente)

11.843072, 12.868676, 13.240046, 13.263860, 14.137154, 14.337731, 15.305140, 15.605321, 16.470893, 17.914788

## Mediana e dispersão

- Mediana: **14.237443s**
- Mínimo: 11.843072s
- Máximo: 17.914788s
- Média: 14.498668s
- Desvio padrão (amostral): 1.838150s
- Spread (min/max): 51.2681%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 51.2681% entre as 10 execuções. **Spread elevado -- investigar antes de aceitar este cenário como concluído.**
