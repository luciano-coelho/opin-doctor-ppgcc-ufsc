# PARADA — pré-voo reprovado, nenhum recurso AWS criado

**Fase:** pré-voo (antes da Fase A — o ensaio de infraestrutura nunca começou)
**Quando:** verificação rodada nesta sessão, antes de qualquer `terraform apply`
**Estado da conta:** inalterado. Nenhum `aws ec2 run-instances`/`terraform apply`/
criação de recurso nenhuma foi tentada. As únicas chamadas feitas à AWS foram
leitura pura: `sts get-caller-identity`, `service-quotas get-service-quota`
(negada) e `ec2 describe-addresses` (0 EIPs alocados nas 3 regiões — nada a
limpar).

## Por que parou

Dois itens do pré-voo reprovaram, cada um por si só já exigindo parar antes
do primeiro `apply` (regras 6 e 7(d) do prompt que autorizou esta execução):

### 1) Image ID local do gateway não bate com `PINS.json` (regra 6)

```
                  Image ID local                                                  Image ID em PINS.json
gateway           sha256:fadd40fc9bf98d018a0cda2c364e1d546ac8b51db80613bac96dee5690bc9d28   sha256:625acc6b8838725265e2f66a52feaa00d87cac513713836d2bb7cc4af816f9ff   DIVERGE
proxy             sha256:d106ee299605d38f073bd24829cef0f5a3d8778879240d369b9ba1c3a9edc163   sha256:d106ee299605d38f073bd24829cef0f5a3d8778879240d369b9ba1c3a9edc163   bate
pqc-signer        sha256:b141cc7831aacdc1369d6a3efefbad55e0c839dac83e25fed1728a6614923b01   sha256:b141cc7831aacdc1369d6a3efefbad55e0c839dac83e25fed1728a6614923b01   bate
measure           sha256:2274de77a3ade4c2cf12b8cfc0e88aceec13ddfb20fe8ccda669798b53d61e6d   sha256:2274de77a3ade4c2cf12b8cfc0e88aceec13ddfb20fe8ccda669798b53d61e6d   bate
```

**Diagnóstico adicional (só leitura — `docker create`+`docker cp`+`sha256sum`
no binário extraído, nenhum rebuild, nenhuma escrita em `PINS.json`):** o
**binário** `/gateway` dentro da imagem local tem sha256
`a08ba8e31c4e6bdc865cd32164413169390eca6766359105d10ed0e7557ff47f` —
**idêntico** ao `binary_sha256` já pinado em `PINS.json`. Ou seja: o conteúdo
é o mesmo; só os metadados da imagem Docker (camadas/timestamp de build)
mudaram desde que o `image_id` foi pinado — exatamente o fenômeno que o
próprio `PINS.json` já documenta (`_reproducibility_note`: "o ID da imagem
Docker não é reproduzível entre builds independentes, mesmo com binário
idêntico"). A imagem local deve ter sido reconstruída (`docker build`) em
algum momento depois da Decisão 55 ter capturado o `image_id` original.

**Por que isso bloqueia, mesmo sendo "só metadado":** corrigir exigiria
reconstruir a imagem pinada (proibido pela regra 6 sem decisão explícita) ou
alterar `PINS.json` (também proibido pela regra 6 e pela própria política
`_policy` do arquivo — exige Emenda numerada). Nenhuma das duas foi feita.

### 2) Quota de vCPU não pôde ser conferida — negação de IAM (regra 7d)

```
aws service-quotas get-service-quota --service-code ec2 --quota-code L-1216C47A
```
reprovou nas 3 regiões (`sa-east-1`/`eu-north-1`/`ap-southeast-1`) com
`AccessDeniedException`: o usuário IAM usado (`mockopin-pqc-experiment`) não
tem a permissão `servicequotas:GetServiceQuota`. Sem essa permissão, não há
como confirmar os limites exigidos pela regra 7(c) (`sa-east-1 >= 8`,
`eu-north-1 >= 2`, `ap-southeast-1 >= 2`) antes do primeiro `apply` — e a
regra 7(d) exige parar nesse caso, sem tentar contornar.

**EIPs livres, única parte do item 7(c) que PÔDE ser conferida:** 0 EIPs
alocados nas 3 regiões (sem concorrência por endereço).

## Pré-voo — resto do checklist (passou)

| Item | Resultado |
|---|---|
| Docker rodando, 4 imagens presentes localmente | OK |
| Profile `mockopin-pqc` configurado e funcional (`sts get-caller-identity`) | OK |
| Chave `~/.ssh/id_ed25519.pub` presente | OK |
| Suíte de testes | **141/141 passando** — saída completa em `pre_voo_testes.log`, nesta mesma pasta |
| Quotas de vCPU (3 regiões) | **FALHOU — IAM nega a leitura (item 2 acima)** |
| Image ID das 4 imagens vs PINS.json | **FALHOU pro gateway (item 1 acima)** — proxy/measure/pqc-signer OK |

## O que decidir

1. **Image ID do gateway**: ou (a) localizar/recuperar a imagem Docker
   original cujo Image ID era `625acc6b8838...` (se ainda existir em algum
   lugar — registry, outro host, backup), ou (b) registrar uma Emenda
   numerada em `DECISIONS.md` re-pinando `PINS.json` com o Image ID atual
   (já que o binário continua idêntico, isso seria uma correção de metadado,
   não de conteúdo — mas ainda assim exige decisão explícita sua, não
   automática).
2. **Permissão de Service Quotas**: ou (a) ampliar a política IAM do usuário
   `mockopin-pqc-experiment` com `servicequotas:GetServiceQuota` (e
   idealmente `servicequotas:ListServiceQuotas`), ou (b) confirmar as quotas
   por outro caminho (ex.: console AWS, ou outro usuário/role com a
   permissão) e me passar os 3 números diretamente.

Nenhuma ação de infraestrutura foi tentada. Nenhum commit, nenhum push.
Aguardando sua decisão sobre os dois itens acima antes de qualquer nova
tentativa.
