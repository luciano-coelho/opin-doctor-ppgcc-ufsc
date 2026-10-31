# Item 3 (Luciano, 2026-10-31) -- matriz promessa-evidência

**Nota importante**: o parecer técnico (`thesis/docs/Parecer técnico —
Relatório de métricas da migração pós-quântica do OPIN.pdf`, Manuel
Matos, 2026-09-28) avalia uma versão ANTERIOR/menor do relatório (7
páginas) -- não a v8 atual. `PILOT_RUNBOOK.md` não foi lido linha a
linha por escopo de tempo (nada encontrado que contradiga o que segue,
mas não auditado). Nenhum "plano de trabalho" separado encontrado em
`thesis/docs/` além do próprio parecer.

**Texto exato dos itens do parecer** (seção 4.6 sem sub-letras no PDF
-- mapeado pela ordem dos 6 bullets: a=Unidades de medida, b=Algoritmo
RSA, c=Conformidade do perfil Clássico, d=Parâmetros, e=Modelo de
certificado híbrido, f=Ambiente):

| # | Texto do parecer | Fonte/Evidência v8 | Status |
|---|---|---|---|
| **4.2** | "O modelo de latência não corresponde às 28 chamadas... o esperado estaria na ordem de 40... os tempos absolutos... não servem de referência." | `DECISIONS.md` Decisions 110-115: k-model real (T_fluxo=T0+k·RTT), k≈56 (44 chamadas + 2×6 conexões), medido com RTT real de pcap, IC bootstrap, testado 3 janelas + combinado. Decision 112: handshake-em-viagens ≈12, confirma sem round-trips extras por certs maiores. | **FEITO** |
| **4.3** | "A comparação PQC×Híbrido é assimétrica... certificados do titular e das CAs têm chave ML-DSA-65 mas continuam assinados com RSA." | mTLS: cadeia PQC corrigida pós-v7 (commit `478bda5`) -- ML-DSA-65 ponta a ponta, **reconfirmado agora ao vivo** (item 1 desta auditoria: `root_ca_pqc.crt`/`issuer_ca_pqc.crt` = ML-DSA-65). Directory/PKI mock: também ML-DSA-65, confirmado agora (item 1). | **FEITO** (ambas as partes resolvidas nesta auditoria) |
| **4.4** | "Transporte e front-channel ficaram fora do alcance do ambiente" -- banda/janela TCP, cliente real com JARM/limite de URL. | MTU real: `DECISIONS.md:6731-6749` -- campanha real tem MTU de 1500B de verdade (rede AWS real, não loopback Docker). Front-channel com navegador/app real: nenhuma evidência. | **PARCIAL**: banda/MTU real = FEITO (via condição real, não teste deliberado); navegador/app real = **NÃO FEITO** |
| **4.6a** (unidades de medida) | JWT base64url vs. chave AS em bytes brutos -- "a regra deve ser única." | `METRICS_COVERAGE.md` não documenta uma regra única declarada. | **NÃO FEITO** |
| **4.6c** (conformidade do perfil Clássico) | "A equivalência entre o perfil Clássico e o perfil de segurança vigente do OPIN deveria ser documentada, não presumida." | Nenhuma referência normativa ao perfil de segurança oficial do OPIN encontrada. | **NÃO FEITO** |
| **4.6e** (modelo de certificado híbrido) | Extensões não críticas vs. assinaturas compostas (IETF) -- "produziriam tamanhos distintos." | `DECISIONS.md:7944-7950` documenta o mecanismo usado (Strong Nesting/payload-extension); alternativa não testada. | **LIMITAÇÃO DECLARADA** |
| **Rec. 1** | Adicionar perfil "KEM híbrido + assinaturas clássicas". | Só 3 perfis existem (classic/pqc/hybrid). | **NÃO FEITO** |
| **Rec. 2** | Simetrizar PQC×Híbrido (CA em ML-DSA-65 no PQC). | Ver 4.3 -- **resolvido nesta auditoria**. | **FEITO** |
| **Rec. 3** | Decompor tempo cliente/servidores/handshakes/esperas; comparar a referências otimizadas. | `METRICS_COVERAGE.md`: phase accounting completo (signing/setup/wait/verification), residual caiu de ~75% para 14-24%. Comparação com implementações otimizadas: `DECISIONS.md:8616`. | **FEITO** |
| **Rec. 4** | Explicar contagem de idas e voltas; restringir atraso emulado ao trecho cliente-gateway. | v8 não usa atraso emulado -- rede AWS real (2ª parte fica moot). 1ª parte: ver 4.2. | **FEITO** |
| **Rec. 5** | Repetir medição com banda/MTU realistas. | MTU real de 1500B em toda a campanha v8 (condição real, não sweep deliberado). | **FEITO** (parcial) |
| **Rec. 6** | Testar front-channel com navegador/app real. | Nenhuma evidência. | **NÃO FEITO** |
| **Rec. 7** | Reformular "custo fixo por fluxo"; listar specs que mudariam. | Decisions 113-115 já reportam variação real entre janelas, mas texto de conclusão final ainda não reescrito. | **NÃO FEITO** |
| **Rec. 8** | Uniformizar unidade de medida e algoritmo RSA; justificar ML-KEM-1024/P-384. | RSA não uniformizado (PS256 vs RS256 conforme artefato, documentado). Parâmetros: `tls_kem_proxy/main.go:176-187` já justifica SecP384r1MLKEM1024. | **LIMITAÇÃO DECLARADA** |
| Schardong 2022 (orientador) | Métricas no mínimo iguais às do artigo. | `METRICS_COVERAGE.md`: T_fluxo baixa/alta latência, fração handshake mTLS, RTT jitter -- cobertos e checados (Decision 94). | **FEITO** |
| Estatística de distribuição | Não só mediana. | Shapiro-Wilk, bootstrap CI, Mann-Whitney, teste do sinal -- implementados e usados (Decisions 110-115). | **FEITO** |
| Aviso ao fim (limitações) | Seção/aviso final de limitações no relatório. | Nenhum `CONSOLIDATED_REPORT*.md`/`global_v2/*` tem seção "Limitações" consolidada. | **NÃO FEITO** |

## Lista NÃO FEITO -- nenhum depende da frota

Todos os itens NÃO FEITO abaixo são análise/redação sobre dados já
coletados, ou exigiriam infraestrutura nova fora do escopo de 60 min
(4º perfil, navegador real) -- **nenhum foi executado contra a frota
porque nenhum precisa dela**. Aguardando decisão do Luciano:
- 4.6a (unidade de medida única para JWT/chaves)
- 4.6c (conformidade do perfil Clássico documentada contra a norma OPIN)
- Rec. 1 (4º perfil -- fora de escopo de 60min)
- Rec. 6 (teste de navegador/app real -- fora de escopo)
- Rec. 7 (reformular texto de conclusões sobre custo fixo)
- Aviso ao fim (seção de limitações consolidada no relatório final)

(A pendência de Diretório/PKI que esta lista continha foi resolvida
dentro do item 1 desta própria auditoria -- ver `item1_layer_matrix.md`.)
