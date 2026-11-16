# Degrau 2 — inventário reduzido (8 hosts)

Preparado na Etapa 0 (local, sem nenhum comando AWS). **Nenhum IP real, nenhum ID de conta, nenhum conteúdo de chave aparece neste documento** — `host`/`key_path` reais só serão preenchidos na Etapa 1, a partir de `terraform output -json` **escopado/filtrado** (nunca o output completo), sub-etapa própria, com o usuário presente.

## Os 8 hosts (reaproveitados da frota já existente da campanha oficial — nenhuma instância nova)

| Papel | Label | Região | Reaproveita host de |
|---|---|---|---|
| controle | `control` | `sa-east-1` | mesmo host de controle da campanha oficial |
| servidor | `server-sa-east-1` | `sa-east-1` | mesmo servidor da campanha oficial (serve `L0-sa-east-1` **e** `L123` — co-localizado, confirmado no Degrau 1; **não precisa de uma 9ª instância**) |
| cliente | `client-L0-sa-east-1` | `sa-east-1` (colocado) | mesmo cliente L0 da campanha oficial |
| servidor | `server-us-east-1` | `us-east-1` | mesmo servidor da campanha oficial (serve `L0-us-east-1`) |
| cliente | `client-L0-us-east-1` | `us-east-1` (colocado) | mesmo cliente L0 da campanha oficial |
| servidor | `server-ap-northeast-1` | `ap-northeast-1` | mesmo servidor da campanha oficial (serve `L0-ap-northeast-1`) |
| cliente | `client-L0-ap-northeast-1` | `ap-northeast-1` (colocado) | mesmo cliente L0 da campanha oficial |
| cliente | `client-L123` | `ca-central-1` | mesmo cliente de `L123` da campanha oficial |

**Confirmação explícita (já estabelecida no Degrau 1, reconfirmada aqui):** o servidor de `L123` é o mesmo de `sa-east-1` — co-localizado, por desenho da topologia da campanha oficial (`campaign_topology.CAMPAIGN_ROUTE_SERVER["L123"] == "sa-east-1"`). Não é necessária nenhuma 9ª instância/servidor separado para `L123`.

## Células e perfis desta campanha suplementar

- **Células (4):** `L0-sa-east-1`, `L0-us-east-1`, `L0-ap-northeast-1`, `L123`.
- **Perfis (3):** `classico`, `pqc`, `hibrido-and`. **Control (`hibrido-v8`) fora de escopo**, conforme `PLANO_DEGRAU2.md`.
- **Rodadas:** 2, independentes, sementes `20261117` (rodada 1) e `20261118` (rodada 2) — mesmas do pré-registro.
- **N por célula por rodada:** 15 execuções oficiais + 5 aquecimentos descartados (nunca lidos nas análises da Etapa 2).
- **Ordem dos blocos de perfil:** sorteada por rota E por rodada (2 sorteios independentes por rota, 1 por rodada), gravada no manifesto — mesma convenção da campanha oficial (`route_orders`).

## Conta da campanha (confirmada, bate com o pedido)

`4 células × 3 perfis × 15 execuções × 2 rodadas = 360 execuções oficiais` (+ `4 × 3 × 5 × 2 = 120` aquecimentos descartados, não incluídos nos 360).

## Saída pretendida

- **Remoto (no controle):** `~/campaign-data/v9/degrau2/` — mesma estrutura de diretórios da campanha oficial (`raw`/`organized`, manifesto com `route_orders`/sementes/timestamps), adaptada pras 4 células × 3 perfis.
- **Local (cópia, como sempre):** `thesis/results/v9/degrau2/campaign_data/` (ainda não existe — será criado na Etapa 1, ao copiar os dados reais do controle; **não confundir com `thesis/results/v9/degrau2/` em si, que já existe e contém só os artefatos desta Etapa 0** — plano, scripts, este inventário).

## Pendências explícitas para a Etapa 1 (nunca resolvidas nesta Etapa 0)

1. Resolver `host` (IP público) e `key_path` reais dos 8 hosts via `terraform output -json` **escopado** (ex. só os campos `public_ip`/`private_ip` dos 8 labels acima, nunca o output completo) — gravados só num arquivo LOCAL fora do git (mesma convenção de segurança já usada durante toda a campanha oficial), nunca commitados em texto puro.
2. Confirmar que a frota (atualmente parada, confirmado no Degrau 1) está no estado esperado antes de qualquer ação — sub-etapa de leitura, separada, antes de qualquer restart.
3. Rodar `probe_overhead.py` e `collect_cpu_info.py` (ambos escritos nesta Etapa 0) a partir do controle.
4. Só depois disso, rodar a campanha suplementar de 360 execuções em si.

Cada uma dessas 4 pendências é uma sub-etapa SEPARADA, autorizada individualmente pelo usuário, com o usuário presente — nenhuma autorização desta Etapa 0 cobre nenhuma delas.
