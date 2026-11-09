# Piloto v9 — índice de resultados

Execução autônoma na AWS (Luciano ausente), autorizada por mensagem
explícita. Ver `thesis/results/v9/DECISIONS.md` para a narrativa
completa, decisão por decisão — este índice só orienta onde cada
coisa está.

## Status atual

- **Fase A (ensaio de infraestrutura, `INFRA_REHEARSAL.md`): COMPLETA
  E VERDE.** Passos 0–14 todos passaram numa execução real na AWS
  (segunda tentativa desta retomada).
- **Fase B (piloto real de 60 execuções): COMPLETA DE PONTA A PONTA
  pela SEGUNDA vez (Decisão 101, 5ª tentativa real) — 60/60 execuções,
  12/12 capturas, os 7 critérios avaliados com dados 100% reais.
  Resultado FINAL (após a reanálise offline do critério 2, Decisão
  102): 7/7 PASS — primeira vez na história deste pacote.**
  Resumo da sequência: Decisão 90 parou na prova de captura (classificação
  de mensagens sob rede real). Decisão 91 corrigiu o mecanismo
  (classificação por direção/stream, consistência obrigatória). Decisão
  92 (3ª tentativa): mecanismo provado perfeito nos 4 perfis, mas parou
  de novo em `certificate_bytes` — descompasso de calibração pré-existente
  do `CERTIFICATE_BASELINE` (Decisão 75 já tinha revertido a premissa que
  o motivou, sem reconferir o número). Decisão 93: baseline recalibrado
  por DERIVAÇÃO (fórmula RFC 8446 a partir do DER real), opção 2 do
  Luciano, confirmada nos 5 pontos pedidos. Decisão 94 (4ª tentativa): 4
  achados reais de infraestrutura/lógica nos produtores dos critérios
  2/3/7 (nunca exercitados contra o piloto real antes), todos corrigidos
  ao vivo. Decisão 95 (4ª tentativa, COMPLETA): 4/7 PASS, 3 FAILs
  (critérios 1/2/7) — achados NOVOS de MÉTODO de medição (nunca de
  infraestrutura). Decisões 96-100: Emenda fail-closed de teardown (96),
  Emenda RTT-pcap ao critério 7 (97), Emenda MSS-efetivo ao critério 2
  (98), Emenda robustez-de-captura ao critério 1 com retry (99),
  validação local com tc netem e verdade conhecida (100). Decisão 101
  (5ª tentativa, COMPLETA): os critérios 1 e 7 — alvo direto das
  Emendas 99 e 97 — PASSAM pela primeira vez; só o critério 2 continua
  FAIL, atribuído (ERRADO, corrigido na Decisão 102) a TCP pacing;
  teardown pela PRIMEIRA vez usando o gate fail-closed de verdade
  (`--pull-verified-marker`, nunca `--force`). **Decisão 102: a
  reconstrução do timeline real do pcap (microssegundo a
  microssegundo) provou que NÃO havia pacing nenhum (segmentos do 1º
  voo saem ~1000× mais rápido do que o `pacing_rate` reportado
  exigiria) — a causa real era um bug de contagem (parava no 1º
  pacote de ACK visto, mas o cliente manda vários ACKs em cluster sob
  RTT real). Corrigido (conta por timestamp de envio dentro de 1 RTT
  medido na mesma conexão), validado com verdade conhecida real
  (`ip route ... initcwnd` 4/10/20, com e sem fq pacing real) ANTES de
  tocar o dado real, reanalisado OFFLINE do MESMO pcap preservado
  (nenhuma nova rodada de AWS) — critério 2 PASSA.** Os cinco ensaios
  reais (evidência, nunca critério oficial além do resultado final)
  ficam em `tentativas/`, marcados `conta_como_dado: false`; o
  resultado OFICIAL mais recente fica em `dados_oficiais/piloto-real-
  aws-2026-11-09-v2/` (o resultado anterior, Decisão 95, permanece em
  `piloto-real-aws-2026-11-09/` como histórico, nunca sobrescrito).
- **Fase C (consolidação):** feita (Decisões 101-102) — ver
  `dados_oficiais/piloto-real-aws-2026-11-09-v2/RELATORIO_PILOTO.md`.

## Arquivos neste diretório

| Arquivo/pasta | Conteúdo |
|---|---|
| `RELATORIO_SESSAO.md` | Relatório da Fase A — o que rodou, custo, itens já resolvidos. |
| `estado.json` | Estado estruturado (fase atual, tentativas, custo, decisões pendentes) — espelha os relatórios, em formato máquina. |
| `PARADA.md` | Relato da PRIMEIRA parada desta rodada (Decisão 67, Passo 9 da Fase A, Image ID entre versões de Docker) — histórico, já superado. |
| `pre_voo_testes.log` | Saída da suíte de testes antes da primeira tentativa desta rodada. |
| `ensaio_infra/` | Logs da PRIMEIRA tentativa real da Fase A (parou no Passo 9, Decisão 67). Ver `ensaio_infra/IDENTIDADE.json`. |
| `ensaio_infra_retomada/` | Logs da retomada da Fase A que fechou COMPLETA E VERDE (Decisões 68–74). Ver `ensaio_infra_retomada/IDENTIDADE.json`. |
| `dados_oficiais/validacao-local-fase-b/` | Caminho de dados completo (run_pilot→coleta→avaliação→consolidação) provado localmente antes da Fase B real (Decisão 79) — critérios 1/4/5/6 PASS reais, 2/3/7 sem evidência (gap conhecido). |
| `tentativas/ensaio_fase_b_real/` | Logs da primeira tentativa real da Fase B (parou no Passo 10, Decisões 81–82) — `conta_como_dado: false`. Ver `tentativas/ensaio_fase_b_real/IDENTIDADE.json`. |
| `tentativas/ensaio_fase_b_real_v2/` | Logs da segunda tentativa real da Fase B — backend provado (12/12, 0 falhas), parou na prova de captura (Decisões 81/87/88/89/90) — `conta_como_dado: false`, nunca um dos 7 critérios oficiais. Ver `tentativas/ensaio_fase_b_real_v2/IDENTIDADE.json`. |
| `dados_oficiais/validacao-local-decisao-91/` | Validação local REAL (6 conexões mTLS reais, fluxo de negócio completo) do mecanismo corrigido pela Decisão 91, antes de qualquer tentativa real na AWS. Ver `dados_oficiais/validacao-local-decisao-91/IDENTIDADE.json`. |
| `tentativas/ensaio_fase_b_real_v3/` | Logs da terceira tentativa real da Fase B — mecanismo da Decisão 91 provado perfeito contra rede real nos 4 perfis, parou em `certificate_bytes`/`CERTIFICATE_BASELINE` (Decisão 92) — `conta_como_dado: false`. Ver `tentativas/ensaio_fase_b_real_v3/IDENTIDADE.json`. |
| `dados_oficiais/piloto-real-aws-2026-11-09/` | Resultado da 4ª tentativa (Decisão 95) — 60/60 execuções, 12/12 capturas, 4/7 PASS, 3/7 FAIL (achados novos de método, nunca de infraestrutura) — **histórico, superado pela 5ª tentativa**, nunca sobrescrito. `RELATORIO_PILOTO.md` + `criteria_evaluation.json` + `raw/` (19 arquivos coletados). |
| `tentativas/investigacao_passo10_2026-11-09/` | Investigação ao vivo (Decisão 101, achado 2) confirmando que o Passo 10 da 5ª tentativa estava genuinamente progredindo (nunca travado) antes de uma queda de conexão SSH — `conta_como_dado: false`. |
| `dados_oficiais/piloto-real-aws-2026-11-09-v2/` | **Resultado OFICIAL mais recente da Fase B** (Decisões 101-102, 5ª tentativa + reanálise offline do critério 2) — 60/60 execuções, 12/12 capturas, **os 7 critérios reais, 7/7 PASS** — primeira vez na história deste pacote. `RELATORIO_PILOTO.md` + `criteria_evaluation.json` + `raw/` (93 arquivos coletados, incluindo pcaps/keylogs brutos de toda tentativa de captura; `raw/criterio2_initcwnd_original_bug_decisao_95_101.json` preserva o valor original com o bug de contagem, nunca apagado). |
| `campaign/tc_netem_ground_truth/evidencia_initcwnd/` | Validação local com verdade conhecida (Decisão 102) do método corrigido do critério 2 — `ip route ... initcwnd` real 4/10/20, com e sem fq pacing real, contra o `criterio2_probe.py` real. |

## Convenção

Cada subpasta tem um `IDENTIDADE.json` descrevendo o que ela contém,
quando, e quais Decisões numeradas em `DECISIONS.md` ela evidencia.
Nenhum log aqui contém ID de conta AWS, ARN, IP do operador ou
material de chave privada — tudo passado por `redact_aws_errors.py`
e verificação manual antes do commit.
