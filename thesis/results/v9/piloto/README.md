# Piloto v9 — índice de resultados

Execução autônoma na AWS (Luciano ausente), autorizada por mensagem
explícita. Ver `thesis/results/v9/DECISIONS.md` para a narrativa
completa, decisão por decisão — este índice só orienta onde cada
coisa está.

## Status atual

- **Fase A (ensaio de infraestrutura, `INFRA_REHEARSAL.md`): COMPLETA
  E VERDE.** Passos 0–14 todos passaram numa execução real na AWS
  (segunda tentativa desta retomada).
- **Fase B (piloto real de 60 execuções): backend de negócio PROVADO
  (12/12, 0 falhas); mecanismo de medição do critério 1 CORRIGIDO
  (Decisão 91) e PROVADO contra rede real nos 4 perfis (Decisão 92);
  PARADA na calibração de `CERTIFICATE_BASELINE`.** Decisão 90 parou
  na prova de captura (classificação de mensagens sob rede real,
  tocando o critério 1). Decisão 91 corrigiu o mecanismo (classificação
  por direção/stream, consistência obrigatória contra `handshakeBytesIn/
  Out` real) com 13 testes + mutantes, validado localmente (4/4
  perfis). 3ª tentativa real (Decisão 92): a correção funcionou
  PERFEITAMENTE contra rede real nos 4 perfis (6/6 conexões mTLS
  idênticas, consistência fechando exatamente, todas as mensagens
  não-Certificate batendo o baseline oficial) — mas parou de novo em
  `certificate_bytes`, consistentemente +14B/+28B sobre `CERTIFICATE_
  BASELINE` nos 4 perfis: o certificado REALMENTE embutido nas imagens
  pinadas (confirmado por sha256, Decisão 75) nunca bateu com o número
  pré-registrado — um descompasso de calibração pré-existente, só
  agora exposto porque esta é a primeira vez que a prova de captura
  chega inteira a este ponto. 3 decisões pendentes do Luciano (Decisão
  92). Os três ensaios reais (evidência, nunca critério oficial) ficam
  em `tentativas/`, marcados `conta_como_dado: false`.
- **Fase C (consolidação):** não aplicável ainda (depende da Fase B).

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

## Convenção

Cada subpasta tem um `IDENTIDADE.json` descrevendo o que ela contém,
quando, e quais Decisões numeradas em `DECISIONS.md` ela evidencia.
Nenhum log aqui contém ID de conta AWS, ARN, IP do operador ou
material de chave privada — tudo passado por `redact_aws_errors.py`
e verificação manual antes do commit.
