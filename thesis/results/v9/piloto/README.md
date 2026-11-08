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
  funcionando de ponta a ponta — PARADA na prova de captura.**
  Luciano respondeu as 3 lacunas da 1ª rodada (Decisões 75–80) e,
  depois da parada da Decisão 82, respondeu o pedido de portar o
  backend de verdade (Decisões 83–85: backend auth/mockapi/
  mongo_seed portado, tabela de dependências, validação local em
  ambiente limpo, critérios 2/3/7 ligados ao pipeline). 2ª tentativa
  real: 4 achados reais corrigidos ao vivo em sequência (Decisões
  81/87/88/89 — preflight de captura, identidade de imagem só-por-
  digest, `Env` truncado em PINS.json, bit executável perdido no
  Windows) até o backend subir de ponta a ponta — **12/12 execuções
  da porta de fumaça, ZERO falhas, primeira vez na história deste
  pacote.** Parou (Decisão 90) na prova de mecanismo da captura (4/4
  perfis reprovados) — achado de classificação de mensagens sob rede
  real (nunca exercitado localmente), toca o critério 1 oficial, 3
  decisões pendentes do Luciano. Fleet derrubada, conta confirmada
  limpa.
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
| `ensaio_fase_b_real/` | Logs da primeira tentativa real da Fase B (parou no Passo 10, Decisões 81–82). Ver `ensaio_fase_b_real/IDENTIDADE.json`. |
| `ensaio_fase_b_real_v2/` | Logs da segunda tentativa real da Fase B — backend provado (12/12, 0 falhas), parou na prova de captura (Decisões 81/87/88/89/90). Ver `ensaio_fase_b_real_v2/IDENTIDADE.json`. |

## Convenção

Cada subpasta tem um `IDENTIDADE.json` descrevendo o que ela contém,
quando, e quais Decisões numeradas em `DECISIONS.md` ela evidencia.
Nenhum log aqui contém ID de conta AWS, ARN, IP do operador ou
material de chave privada — tudo passado por `redact_aws_errors.py`
e verificação manual antes do commit.
