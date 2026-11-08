# PARADA — Fase A (ensaio de infraestrutura), achado real no Passo 9

**Quando:** execução real desta sessão, Fase A do runbook autorizado
(Decisão 61).
**Estado da conta:** **LIMPA, confirmado.** `cleanup.py --release-eips
--force` rodou com sucesso (`"all_clean": true` nas 3 regiões) e a
verificação final independente (12 chamadas `describe-*`, 4 tipos ×
3 regiões) devolveu listas vazias em todas. Nenhuma instância, EIP,
security group ou key pair resta na conta. Log completo em
`ensaio_infra/logs/cleanup_teardown.log` e
`ensaio_infra/logs/verificacao_final_12_chamadas.log`.

## O que rodou de verdade antes de parar

Apply real (28 recursos, 5 instâncias, 3 regiões), e os Passos 0-8 do
`INFRA_REHEARSAL.md` completaram com sucesso (cada um com pelo menos
uma correção real ao longo do caminho — Decisões 62 a 66, todas
commitadas e empurradas, ver `DECISIONS.md`):
- Passo 3 (chave da campanha): corrigido (CRLF).
- Passo 7 (`deliver_images.py`): corrigido 2x (path do Windows no
  `docker save`; CRLF no `.sha256`/`gateway_binary_info.json`).
- Passo 8 (dependências no controle): corrigido 2x (`redact_aws_
  errors.py` ausente; sintaxe Python 3.10+ incompatível com o Python
  3.9 real do controle).
- Passo 9 (`--exercise-start-stop`): corrigido 1x (`_tcp_preflight`
  reprovava sempre no primeiro bloco) — e então achou o problema
  abaixo, que não é mais um bug simples.

## Por que parou (não é um bug que se corrige e tenta de novo)

**`SSHExecutor._deliver_image` abortou:** o Image ID carregado no
servidor real, depois de um `docker load` bem-sucedido do `.tar` do
gateway (já verificado por sha256 em 2 pontos de transporte — operador
→ controle e controle → host), **não bateu** com o Image ID pinado em
`PINS.json`.

**Investigação (só leitura, nenhuma mudança em `PINS.json` nem
rebuild):**
- O binário `/gateway` dentro do container real, no servidor, tem
  sha256 `a08ba8e3...` — **idêntico** ao `binary_sha256` pinado.
  Conteúdo confirmado correto.
- O tamanho reportado da imagem no servidor (20.1MB) diverge do
  reportado localmente (31.3MB) — não é corrupção; é como cada versão
  do Docker contabiliza o tamanho.
- **Causa raiz real:** a máquina do operador roda Docker **29.9.1**;
  o servidor real (Amazon Linux 2023, pacote `docker` do `dnf`) roda
  Docker **25.0.16**. O mesmo `.tar`, carregado por essas duas versões
  diferentes, produz **dois Image IDs diferentes** — mesmo com
  conteúdo (binário, certificados, camadas) comprovadamente idêntico.

**Por que isso é uma parada, não uma correção:** o mecanismo de
verificação por Image ID (Decisão 55, pré-registrado) foi desenhado e
validado assumindo que `docker load` é determinístico — e é, mas só
**dentro da mesma versão/implementação de Docker**, nunca testado
antes entre versões diferentes (nesta sessão, nem em nenhuma Decisão
anterior). Corrigir isso — seja relaxando a conferência de Image ID,
seja re-pinando por outra via — **altera um critério de verificação
pré-registrado** (regra 6 do prompt que autorizou esta execução: "PARE
e relate"), e há dúvida real sobre se isso muda o que está sendo
medido/garantido (regra 7e). Não decidi isso por conta própria.

**Risco pra campanha oficial futura, não só pro piloto:** qualquer
instância EC2 real provavelmente roda um Docker mais antigo que o do
operador (pacote de distribuição vs. Docker Desktop) — este problema
tende a se repetir em QUALQUER entrega real por Image ID, não é
específico desta instância/região.

## O que decidir

1. **Trocar o que é verificado:** usar o sha256 do BINÁRIO (já
   comprovadamente estável entre versões de Docker — é só o conteúdo
   do arquivo, sem metadado de imagem) como o critério fail-closed
   real, e tratar o Image ID como diagnóstico informativo, não um
   gate. Isso é coerente com o que `proxy`/`pqc-signer`/`measure` TAMBÉM
   precisariam (eles só têm Image ID pinado, sem binário próprio pra
   hashear pra `pqc-signer`/`measure` — precisaria de um mecanismo
   equivalente, ex. hash do `.tar` inteiro, conferido ANTES do load).
2. **Fixar a versão do Docker:** instalar, no controle/host, a MESMA
   versão de Docker do operador (ou vice-versa) antes de qualquer
   entrega — mantém o mecanismo de Image ID como está, mas exige
   trabalho de provisionamento adicional (`install_common_packages.sh`
   fixaria uma versão em vez de `dnf install -y docker`).
3. **Outra via** que eu não enxerguei.

Qualquer uma das três muda o mecanismo de verificação que a Decisão
55 pré-registrou — por isso aguardo sua decisão antes de qualquer
nova tentativa.

## Esforço gasto (contagem pra regra de custo)

Apply real + ~9 passos reais executados + 1 destroy real, todos nas 3
regiões do piloto, janela total estimada em ~25-30 minutos de frota.
Custo estimado: **bem abaixo de US$1** (muito abaixo do teto de US$5).
Nenhuma retentativa "no mesmo problema" passou de 1 (cada achado foi
tratado como um problema novo, corrigido, testado localmente, e só
então re-tentado uma vez — nunca 3 tentativas cegas no mesmo lugar).

## Decisões registradas nesta sessão (ver DECISIONS.md)

61 (Emenda, Image ID do gateway), 62 (CRLF na chave da campanha), 63
(path do Windows no `docker save`), 64 (CRLF no `.sha256`/
`gateway_binary_info.json`), 65 (`redact_aws_errors.py` ausente +
Python 3.9 incompatível), 66 (`_tcp_preflight` logicamente errado pro
primeiro bloco). Todas commitadas e empurradas em `v9/fase1-local`.

Nenhuma Fase B (piloto de 60 execuções) foi tentada — a Fase A não
fechou verde, e o runbook exige fechar a Fase A antes de prosseguir.
