# Secoes (d)(e)(f) -- Fluxos, tabela perfil x rota, criterios

## (d) Contagens de fluxo / DualAuthenticated / CurveID por perfil x rota
| Perfil/Rota | http | jwts | jwks | ca | mtls | OK? | curveID | dualAuthenticated |
|---|---|---|---|---|---|---|---|---|
| classico/L0 | 44 | 28 | 4 | 4 | 6 | True | CurveP384 | False |
| classico/L219 | 44 | 28 | 4 | 4 | 6 | True | CurveP384 | False |
| classico/L325 | 44 | 28 | 4 | 4 | 6 | True | CurveP384 | False |
| hibrido-and/L0 | 44 | 28 | 4 | 4 | 6 | True | SecP384r1MLKEM1024 | True |
| hibrido-and/L219 | 44 | 28 | 4 | 4 | 6 | True | SecP384r1MLKEM1024 | True |
| hibrido-and/L325 | 44 | 28 | 4 | 4 | 6 | True | SecP384r1MLKEM1024 | True |
| hibrido-v8/L0 | 44 | 28 | 4 | 4 | 6 | True | SecP384r1MLKEM1024 | False |
| hibrido-v8/L219 | 44 | 28 | 4 | 4 | 6 | True | SecP384r1MLKEM1024 | False |
| hibrido-v8/L325 | 44 | 28 | 4 | 4 | 6 | True | SecP384r1MLKEM1024 | False |
| pqc/L0 | 44 | 28 | 4 | 4 | 6 | True | MLKEM1024 | False |
| pqc/L219 | 44 | 28 | 4 | 4 | 6 | True | MLKEM1024 | False |
| pqc/L325 | 44 | 28 | 4 | 4 | 6 | True | MLKEM1024 | False |

L325 (rota mais distante): 20 execucoes, 0 erro(s) encontrado(s).

## (e) Tabela perfil x rota (verificacao real)
| Perfil | Rota | Tamanhos (crit.1) | Fluxo/contagens (crit.4/6) | Latencia T_fluxo |
|---|---|---|---|---|
| classico | L0 | verificado | verificado | verificado |
| classico | L219 | verificado | verificado | verificado |
| classico | L325 | verificado | verificado | verificado |
| pqc | L0 | verificado | verificado | verificado |
| pqc | L219 | verificado | verificado | verificado |
| pqc | L325 | verificado | verificado | verificado |
| hibrido-v8 | L0 | verificado | verificado | verificado |
| hibrido-v8 | L219 | verificado | verificado | verificado |
| hibrido-v8 | L325 | verificado | verificado | verificado |
| hibrido-and | L0 | verificado | verificado | verificado |
| hibrido-and | L219 | verificado | verificado | verificado |
| hibrido-and | L325 | verificado | verificado | verificado |

## (f) Resultado dos 7 criterios pre-registrados + desvios consolidados
| # | Nome | Resultado |
|---|---|---|
| 1 | tamanhos por mensagem | PASS |
| 2 | initcwnd real | PASS |
| 3 | zero erros na rota mais distante | PASS |
| 4 | contagens do fluxo | PASS |
| 5 | zero erros | PASS |
| 6 | instrumentacao completa + asserções | PASS |
| 7 | sanidade de latencia por rota | PASS |

**Resultado geral: PASS (7/7)**

Lista consolidada de desvios/ajustes de metodo (ver DECISIONS.md para o texto completo de cada decisao -- Decisao 104 e a Emenda formal ao pre-registro):
| Decisao | O que mudou | Desvio FORMAL do pre-registro? |
|---|---|---|
| 61 | Re-pin de Image ID do gateway apos imagem original deixar de existir localmente (binario/certs idênticos, prova de conteúdo) | Não -- mecanismo de verificação de proveniência, nunca o que é medido |
| 75 | Organização final de piloto/dados_oficiais/ no padrão v8 (fonte json + relatório md) | Não -- forma de apresentação |
| 91 | Ajustes de robustez na coleta remota (nohup/disown em passos SSH longos) | Não -- mecanismo de execução |
| 93 | Emenda MSS-efetivo ao critério 2 (passa a exigir concordância pcap vs ss -ti) | SIM -- muda a definição pré-registrada do critério |
| 97 | Emenda RTT-pcap ao critério 7 (RTT medido via SYN-ACK/ACK do mesmo handshake, não só via probe) | Não -- mecanismo de medição, o limiar pré-registrado não muda |
| 98 | Emenda robustez-de-captura ao critério 1, com retry em decifragem incompleta | SIM -- muda o procedimento de aceitação de captura pré-registrado |
| 99 | Fail-closed de teardown novo | Não -- mecanismo operacional |
| 102 | Emenda robustez-de-janela ao critério 2 (bug de contagem por ACK corrigido para contagem por timestamp de envio dentro de 1 RTT) | Não -- correção de um bug de mecanismo, nunca do que é medido |
