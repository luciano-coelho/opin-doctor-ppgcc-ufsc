# Flex launch test — raw results

## O que é este arquivo

`flex_launch_test_results.json` é a saída bruta, sem edição, do teste de
lançamento real (Decision 43) que comparou `m7i-flex.large` e
`c7i-flex.large` nas 7 regiões do piloto/campanha (3 de servidor:
`sa-east-1`, `us-east-1`, `ap-northeast-1`; 4 de cliente: `ca-central-1`,
`eu-north-1`, `ap-southeast-1`, `ap-northeast-2`) — 14 instâncias reais,
lançadas, medidas e destruídas na mesma sessão.

## Por que foi guardado

Esta é a evidência primária por trás da escolha de tipo de instância
registrada em `DECISIONS.md`. Os números no corpo da decisão (tabela,
vereditos, maior queda/maior aumento de vazão) são todos derivados
diretamente deste arquivo — ele existe para que essa derivação seja
auditável depois, não só confiada à prosa da decisão.

## Como ler cada entrada de `results`

Cada um dos 14 objetos tem:

- `region`, `instance_type` — qual par (região, tipo) este resultado descreve.
- `load_command_exact` — o comando exato da carga sintética, **idêntico em
  todas as 14 instâncias**: `stress-ng --cpu 2 --timeout 20s --metrics-brief`
  (carga nas 2 vCPUs — ambos os tipos têm exatamente 2 vCPUs, confirmado
  via `describe-instance-types` antes do teste).
- `environment.ami_id` — o ID da AMI real que a instância reportou (via
  IMDSv2, consultado de dentro da própria instância, não assumido do
  Terraform).
- `environment.availability_zone_id` — a zona por ID (`sae1-az1` etc.),
  mesma convenção fixada no `terraform-flex-launch-test`.
- `environment.kernel` — `uname -r` real da instância.
- `environment.stress_ng_version` — `stress-ng --version` real da
  instância (a ferramenta vem do repositório padrão do Amazon Linux 2023,
  instalada via `dnf install -y stress-ng` no início do teste).
- `phase_a_attempts` — lista de tentativas da medição inicial (cada uma
  com até 3 `bursts`); mais de uma tentativa significa que a dispersão
  `(máx−mín)/mediana` da tentativa anterior passou de 5% (critério de
  "medição inconclusiva", teto de 2 repetições por instância — nenhuma das
  14 chegou a esgotar o teto).
- `phase_b_bursts` — a medição final, depois de pelo menos 10 minutos de
  espera real desde o fim da fase inicial.
- Cada `burst` (em `phase_a_attempts[].bursts` e `phase_b_bursts`) tem
  `utc_start`/`utc_end` (horário UTC real de início/fim daquela medição),
  `steal_pct`/`cpu_busy_pct` (delta real de `/proc/stat` entre o início e
  o fim do burst), `throughput_bogo_ops_per_sec` (vazão real reportada
  pelo próprio `stress-ng`), e a saída bruta do `stress-ng` para
  conferência manual.
- `max_steal_pct` — o maior steal% entre TODAS as medições (fase inicial
  + final) daquela instância — o critério de reprovação por steal usa
  este valor.
- `median_throughput_phase_a`/`median_throughput_phase_b` — mediana de
  pelo menos 3 medições de cada fase.
- `throughput_drop_pct` — `(mediana_inicial − mediana_final) / mediana_inicial × 100`.
  **Convenção de sinal: positivo é queda real de vazão; negativo é
  AUMENTO de vazão** (a mediana final saiu maior que a inicial — comum em
  cargas curtas de CPU, não indica problema). Não inverter ao ler.
- `verdict` — `PASS`, `FAIL (steal)`, `FAIL (throughput drop)`, ou
  `INCONCLUSIVE (...)`, calculado com os limiares fixados ANTES do teste
  (steal > 5% em qualquer medição; queda de vazão > 10%; dispersão
  inicial > 5% é inconclusiva, teto de 2 repetições).

## Sem segredos nem identificadores de conta

Este arquivo foi varrido antes de ser salvo: nenhum IP (operador ou das
instâncias), nenhum ID de conta AWS, nenhuma credencial. Os únicos
identificadores presentes são IDs de recursos já públicos por natureza
(AMI IDs, que são IDs de imagens públicas da Amazon) e IDs de zona de
disponibilidade (não são segredo, aparecem em qualquer `describe-*`
read-only).
