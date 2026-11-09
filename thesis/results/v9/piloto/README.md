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
  funcionando de ponta a ponta (12/12, 0 falhas); mecanismo de
  medição do critério 1 CORRIGIDO (Decisão 91); pronta pra nova
  tentativa real.** Luciano respondeu as 3 lacunas da 1ª rodada
  (Decisões 75–80) e, depois da parada da Decisão 82, respondeu o
  pedido de portar o backend de verdade (Decisões 83–85). 2ª
  tentativa real: 4 achados reais corrigidos ao vivo em sequência
  (Decisões 81/87/88/89) até o backend subir de ponta a ponta — 12/12
  execuções da porta de fumaça, ZERO falhas, primeira vez na história
  deste pacote. Parou (Decisão 90) na prova de mecanismo da captura
  (4/4 perfis reprovados) — achado de classificação de mensagens sob
  rede real, tocando o critério 1 oficial. Luciano respondeu com 3
  instruções: (1) confirmar por dados a causa da fragmentação e a
  hipótese dos "6 grupos" — CONFIRMADO (ver Decisão 91: N_mTLS=6 é um
  invariante já documentado em `opin_flow.py` desde 2026-09-14,
  nunca uma suposição nova; a fragmentação é reordenamento real de
  TCP/TLS sob rede, nunca visto em loopback puro); (2) corrigir
  `_message_sizes_for_profile` com as 6 restrições (a–f) — feito,
  Decisão 91, Emenda de PARSING, nenhum limiar/baseline do critério 1
  tocado; (3) registrar a Emenda com antes/depois — Decisão 91. Os
  dois ensaios reais anteriores (evidência, nunca critério oficial)
  foram para `tentativas/`, marcados `conta_como_dado: false`.
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

## Convenção

Cada subpasta tem um `IDENTIDADE.json` descrevendo o que ela contém,
quando, e quais Decisões numeradas em `DECISIONS.md` ela evidencia.
Nenhum log aqui contém ID de conta AWS, ARN, IP do operador ou
material de chave privada — tudo passado por `redact_aws_errors.py`
e verificação manual antes do commit.
