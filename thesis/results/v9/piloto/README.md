# Piloto v9 — índice de resultados

Execução autônoma na AWS (Luciano ausente), autorizada por mensagem
explícita. Ver `thesis/results/v9/DECISIONS.md` para a narrativa
completa, decisão por decisão — este índice só orienta onde cada
coisa está.

## Status atual

- **Fase A (ensaio de infraestrutura, `INFRA_REHEARSAL.md`): COMPLETA
  E VERDE.** Passos 0–14 todos passaram numa execução real na AWS
  (segunda tentativa desta retomada). Ver `RELATORIO_SESSAO.md`.
- **Fase B (piloto real de 60 execuções): NÃO INICIADA.** Decisão
  deliberada, não um erro — ver `RELATORIO_SESSAO.md`, seção "Fase B"
  e `estado.json`.
- **Fase C (consolidação):** não aplicável ainda (depende da Fase B).

## Arquivos neste diretório

| Arquivo/pasta | Conteúdo |
|---|---|
| `RELATORIO_SESSAO.md` | Relatório final desta sessão — o que rodou, o que foi decidido, custo, itens pendentes do Luciano. **Comece por aqui.** |
| `estado.json` | Estado estruturado (fase atual, tentativas, custo, decisões pendentes) — espelha o relatório, em formato máquina. |
| `PARADA.md` | Relato da PRIMEIRA parada desta rodada (Decisão 67, Passo 9, Image ID entre versões de Docker) — histórico, já superado pela Decisão 68 e pelas retomadas abaixo. |
| `pre_voo_testes.log` | Saída da suíte de testes antes da primeira tentativa desta rodada. |
| `ensaio_infra/` | Logs da PRIMEIRA tentativa real da Fase A (parou no Passo 9, Decisão 67). Ver `ensaio_infra/IDENTIDADE.json`. |
| `ensaio_infra_retomada/` | Logs da retomada da Fase A que fechou COMPLETA E VERDE (Decisões 68–74). Ver `ensaio_infra_retomada/IDENTIDADE.json`. |

## Convenção

Cada subpasta tem um `IDENTIDADE.json` descrevendo o que ela contém,
quando, e quais Decisões numeradas em `DECISIONS.md` ela evidencia.
Nenhum log aqui contém ID de conta AWS, ARN, IP do operador ou
material de chave privada — tudo passado por `redact_aws_errors.py`
e verificação manual antes do commit.
