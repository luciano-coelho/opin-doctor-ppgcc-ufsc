# ============================================================
# Chaves -- uma aws_key_pair exclusiva da campanha por regiao (7), mais
# a chave do operador so em sa-east-1 (controle). Mesmo padrao do
# piloto (thesis/results/v9/terraform/main.tf), tag Project obrigatoria
# pela politica IAM de menor privilegio.
# ============================================================

resource "tls_private_key" "campaign" {
  algorithm = "ED25519"
}

resource "aws_key_pair" "campaign_sa_east_1" {
  provider   = aws.sa_east_1
  key_name   = "mockopin-pqc-campanha-oficial"
  public_key = tls_private_key.campaign.public_key_openssh
  tags       = { Project = var.project_tag, Role = "campaign-key" }
}
resource "aws_key_pair" "campaign_us_east_1" {
  provider   = aws.us_east_1
  key_name   = "mockopin-pqc-campanha-oficial"
  public_key = tls_private_key.campaign.public_key_openssh
  tags       = { Project = var.project_tag, Role = "campaign-key" }
}
resource "aws_key_pair" "campaign_ap_northeast_1" {
  provider   = aws.ap_northeast_1
  key_name   = "mockopin-pqc-campanha-oficial"
  public_key = tls_private_key.campaign.public_key_openssh
  tags       = { Project = var.project_tag, Role = "campaign-key" }
}
resource "aws_key_pair" "campaign_ca_central_1" {
  provider   = aws.ca_central_1
  key_name   = "mockopin-pqc-campanha-oficial"
  public_key = tls_private_key.campaign.public_key_openssh
  tags       = { Project = var.project_tag, Role = "campaign-key" }
}
resource "aws_key_pair" "campaign_eu_north_1" {
  provider   = aws.eu_north_1
  key_name   = "mockopin-pqc-campanha-oficial"
  public_key = tls_private_key.campaign.public_key_openssh
  tags       = { Project = var.project_tag, Role = "campaign-key" }
}
resource "aws_key_pair" "campaign_ap_southeast_1" {
  provider   = aws.ap_southeast_1
  key_name   = "mockopin-pqc-campanha-oficial"
  public_key = tls_private_key.campaign.public_key_openssh
  tags       = { Project = var.project_tag, Role = "campaign-key" }
}
resource "aws_key_pair" "campaign_ap_northeast_2" {
  provider   = aws.ap_northeast_2
  key_name   = "mockopin-pqc-campanha-oficial"
  public_key = tls_private_key.campaign.public_key_openssh
  tags       = { Project = var.project_tag, Role = "campaign-key" }
}

resource "aws_key_pair" "operator_sa_east_1" {
  provider   = aws.sa_east_1
  key_name   = "mockopin-pqc-campanha-oficial-operator"
  public_key = var.operator_ssh_public_key
  tags       = { Project = var.project_tag, Role = "campaign-key-operator" }
}

# ============================================================
# VPC / sub-rede default, uma por regiao (7). sa-east-1/us-east-1/
# ap-northeast-1 precisam tambem de uma AZ especifica (por AZ ID,
# verificada ao vivo nesta conta nova -- sae1-az1/use1-az1/apne1-az1,
# todas confirmadas disponiveis) compartilhada entre o servidor e o
# cliente L0 co-localizado de cada uma, mesmo padrao da v8 real.
# ============================================================

data "aws_vpc" "sa_east_1" {
  provider = aws.sa_east_1
  default  = true
}
data "aws_vpc" "us_east_1" {
  provider = aws.us_east_1
  default  = true
}
data "aws_vpc" "ap_northeast_1" {
  provider = aws.ap_northeast_1
  default  = true
}
data "aws_vpc" "ca_central_1" {
  provider = aws.ca_central_1
  default  = true
}
data "aws_vpc" "eu_north_1" {
  provider = aws.eu_north_1
  default  = true
}
data "aws_vpc" "ap_southeast_1" {
  provider = aws.ap_southeast_1
  default  = true
}
data "aws_vpc" "ap_northeast_2" {
  provider = aws.ap_northeast_2
  default  = true
}

data "aws_subnets" "sa_east_1_az1" {
  provider = aws.sa_east_1
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.sa_east_1.id]
  }
  filter {
    name   = "availability-zone-id"
    values = ["sae1-az1"]
  }
}
data "aws_subnets" "sa_east_1_default" {
  provider = aws.sa_east_1
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.sa_east_1.id]
  }
}
data "aws_subnets" "us_east_1_az1" {
  provider = aws.us_east_1
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.us_east_1.id]
  }
  filter {
    name   = "availability-zone-id"
    values = ["use1-az1"]
  }
}
data "aws_subnets" "ap_northeast_1_az1" {
  provider = aws.ap_northeast_1
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.ap_northeast_1.id]
  }
  filter {
    name   = "availability-zone-id"
    values = ["apne1-az1"]
  }
}
data "aws_subnets" "ca_central_1_default" {
  provider = aws.ca_central_1
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.ca_central_1.id]
  }
}
# AZ fixada por regiao (pedido do Luciano, item 5 -- fechamento dos
# criterios 1/3/4/6/7 pra campanha): o smoke-test real (Decisao 108)
# achou `InsufficientInstanceCapacity` real pra t4g.micro em
# ca-central-1a (a AZ que `ca_central_1_default.ids[0]` resolveria
# primeiro, ordem arbitraria da API) -- resolvido na hora trocando pra
# ca-central-1b, que funcionou. PRIMARIA: ca-central-1b (confirmada
# capaz pelo smoke-test real). FALLBACK documentado: ca-central-1a (a
# original, que falhou para t4g.micro no smoke-test -- se
# ca-central-1b tambem apresentar capacidade insuficiente para
# m7i-flex.large no futuro, a alternativa e usar
# `ca_central_1_default` de novo ou pedir uma 3a AZ). Letra de AZ
# (nao AZ-id) de proposito aqui -- a letra e por-conta, a MESMA conta
# que rodou o smoke-test real, nunca comparada entre contas.
data "aws_subnets" "ca_central_1_b" {
  provider = aws.ca_central_1
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.ca_central_1.id]
  }
  filter {
    name   = "availability-zone"
    values = ["ca-central-1b"]
  }
}
data "aws_subnets" "eu_north_1_default" {
  provider = aws.eu_north_1
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.eu_north_1.id]
  }
}
data "aws_subnets" "ap_southeast_1_default" {
  provider = aws.ap_southeast_1
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.ap_southeast_1.id]
  }
}
data "aws_subnets" "ap_northeast_2_default" {
  provider = aws.ap_northeast_2
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.ap_northeast_2.id]
  }
}

# AMIs PINADAS (nao resolvidas a cada apply, mesma politica do piloto)
# -- resolvidas ao vivo nesta conta nova via describe-images real
# (2026-11-09), al2023-ami-*-kernel-*-{x86_64,arm64}, a mais recente
# disponivel em cada regiao no momento da adaptacao deste Terraform.
# Como toda AMI pinada deste projeto: reconferir antes do apply real,
# nunca assumir que continua a mais recente depois de muito tempo
# parado.
locals {
  pinned_ami_x86_by_region = {
    "sa-east-1"      = "ami-0947d58e57fa20c5f"
    "us-east-1"      = "ami-0cf4b3ccd41c5a321"
    "ap-northeast-1" = "ami-04ff541c93bef7350"
    "ca-central-1"   = "ami-0f39320fcf308a07f"
    "eu-north-1"     = "ami-072b92f3846437950"
    "ap-southeast-1" = "ami-0e5c4d93500d698da"
    "ap-northeast-2" = "ami-0bef747b3acf85e8f"
  }
  pinned_ami_arm64_sa_east_1 = "ami-027c2612cea3ab019"
}

# ============================================================
# Controle -- so em sa-east-1, mesmo padrao do piloto. SSH so do /32
# do operador.
# ============================================================

module "control" {
  source            = "../terraform/modules/campaign_instance"
  providers         = { aws = aws.sa_east_1 }
  name_tag          = "control"
  role              = "control"
  project_tag       = var.project_tag
  instance_type     = var.control_instance_type
  ami_id            = local.pinned_ami_arm64_sa_east_1
  vpc_id            = data.aws_vpc.sa_east_1.id
  subnet_id         = data.aws_subnets.sa_east_1_default.ids[0]
  key_name          = aws_key_pair.operator_sa_east_1.key_name
  ssh_ingress_cidrs = { "operator" = var.operator_ip_cidr }
  # 48h (Decisao 23 item 5, v9 -- campanha oficial, nao as 4h do
  # piloto), igual aos demais hosts: o controle faz a coleta final
  # DEPOIS dos outros terminarem, entao precisa do MESMO prazo, nunca
  # menor (achado real do Bloco A desta adaptacao: numa tentativa
  # anterior do piloto o controle tinha prazo MENOR que os hosts,
  # invertido do que a coleta final exige).
  self_terminate_hours                 = var.self_terminate_hours
  instance_initiated_shutdown_behavior = "stop"
}

# ============================================================
# Servidores -- 3, um por regiao-base da v8 real (sa-east-1/us-east-1/
# ap-northeast-1). Cada um abre o gateway (443) so pros clientes que
# ele de fato atende.
# ============================================================

module "server_sa_east_1" {
  source            = "../terraform/modules/campaign_instance"
  providers         = { aws = aws.sa_east_1 }
  name_tag          = "server-sa-east-1"
  role              = "server"
  project_tag       = var.project_tag
  instance_type     = var.server_client_instance_type
  ami_id            = local.pinned_ami_x86_by_region["sa-east-1"]
  vpc_id            = data.aws_vpc.sa_east_1.id
  subnet_id         = data.aws_subnets.sa_east_1_az1.ids[0]
  key_name          = aws_key_pair.campaign_sa_east_1.key_name
  ssh_ingress_cidrs = { "control" = "${module.control.public_ip}/32" }
  gateway_ingress_cidrs = {
    "L0"   = "${module.client_l0_sa_east_1.private_ip}/32" # co-localizado
    "L123" = "${module.client_ca_central_1_a.public_ip}/32"
    "L219" = "${module.client_eu_north_1.public_ip}/32"
    "L325" = "${module.client_ap_southeast_1.public_ip}/32"
  }
  self_terminate_hours                 = var.self_terminate_hours
  instance_initiated_shutdown_behavior = "stop"
}

module "server_us_east_1" {
  source            = "../terraform/modules/campaign_instance"
  providers         = { aws = aws.us_east_1 }
  name_tag          = "server-us-east-1"
  role              = "server"
  project_tag       = var.project_tag
  instance_type     = var.server_client_instance_type
  ami_id            = local.pinned_ami_x86_by_region["us-east-1"]
  vpc_id            = data.aws_vpc.us_east_1.id
  subnet_id         = data.aws_subnets.us_east_1_az1.ids[0]
  key_name          = aws_key_pair.campaign_us_east_1.key_name
  ssh_ingress_cidrs = { "control" = "${module.control.public_ip}/32" }
  gateway_ingress_cidrs = {
    "L0"  = "${module.client_l0_us_east_1.private_ip}/32" # co-localizado
    "L14" = "${module.client_ca_central_1_b.public_ip}/32"
  }
  self_terminate_hours                 = var.self_terminate_hours
  instance_initiated_shutdown_behavior = "stop"
}

module "server_ap_northeast_1" {
  source            = "../terraform/modules/campaign_instance"
  providers         = { aws = aws.ap_northeast_1 }
  name_tag          = "server-ap-northeast-1"
  role              = "server"
  project_tag       = var.project_tag
  instance_type     = var.server_client_instance_type
  ami_id            = local.pinned_ami_x86_by_region["ap-northeast-1"]
  vpc_id            = data.aws_vpc.ap_northeast_1.id
  subnet_id         = data.aws_subnets.ap_northeast_1_az1.ids[0]
  key_name          = aws_key_pair.campaign_ap_northeast_1.key_name
  ssh_ingress_cidrs = { "control" = "${module.control.public_ip}/32" }
  gateway_ingress_cidrs = {
    "L0"  = "${module.client_l0_ap_northeast_1.private_ip}/32" # co-localizado
    "L30" = "${module.client_ap_northeast_2.public_ip}/32"
  }
  self_terminate_hours                 = var.self_terminate_hours
  instance_initiated_shutdown_behavior = "stop"
}

# ============================================================
# Clientes -- 8 no total (3 L0 co-localizados + 5 cross-region), mesma
# atribuicao de regiao/papel da campanha real da v8 (confirmado nos
# modulos reais dela: client_l0, client_ca_central_1_a/b, client_eu_
# north_1, client_ap_southeast_1, client_ap_northeast_2, client_l0_us_
# east_1, client_l0_ap_northeast_1). SSH so do EIP do controle.
# ============================================================

module "client_l0_sa_east_1" {
  source                               = "../terraform/modules/campaign_instance"
  providers                            = { aws = aws.sa_east_1 }
  name_tag                             = "client-l0-sa-east-1"
  role                                 = "client"
  project_tag       = var.project_tag
  instance_type                        = var.server_client_instance_type
  ami_id                                = local.pinned_ami_x86_by_region["sa-east-1"]
  vpc_id                                = data.aws_vpc.sa_east_1.id
  subnet_id                             = data.aws_subnets.sa_east_1_az1.ids[0] # mesma AZ ID do servidor
  key_name                              = aws_key_pair.campaign_sa_east_1.key_name
  ssh_ingress_cidrs                     = { "control" = "${module.control.public_ip}/32" }
  self_terminate_hours                  = var.self_terminate_hours
  instance_initiated_shutdown_behavior  = "stop"
}

module "client_l0_us_east_1" {
  source                               = "../terraform/modules/campaign_instance"
  providers                            = { aws = aws.us_east_1 }
  name_tag                             = "client-l0-us-east-1"
  role                                 = "client"
  project_tag       = var.project_tag
  instance_type                        = var.server_client_instance_type
  ami_id                                = local.pinned_ami_x86_by_region["us-east-1"]
  vpc_id                                = data.aws_vpc.us_east_1.id
  subnet_id                             = data.aws_subnets.us_east_1_az1.ids[0] # mesma AZ ID do servidor
  key_name                              = aws_key_pair.campaign_us_east_1.key_name
  ssh_ingress_cidrs                     = { "control" = "${module.control.public_ip}/32" }
  self_terminate_hours                  = var.self_terminate_hours
  instance_initiated_shutdown_behavior  = "stop"
}

module "client_l0_ap_northeast_1" {
  source                               = "../terraform/modules/campaign_instance"
  providers                            = { aws = aws.ap_northeast_1 }
  name_tag                             = "client-l0-ap-northeast-1"
  role                                 = "client"
  project_tag       = var.project_tag
  instance_type                        = var.server_client_instance_type
  ami_id                                = local.pinned_ami_x86_by_region["ap-northeast-1"]
  vpc_id                                = data.aws_vpc.ap_northeast_1.id
  subnet_id                             = data.aws_subnets.ap_northeast_1_az1.ids[0] # mesma AZ ID do servidor
  key_name                              = aws_key_pair.campaign_ap_northeast_1.key_name
  ssh_ingress_cidrs                     = { "control" = "${module.control.public_ip}/32" }
  self_terminate_hours                  = var.self_terminate_hours
  instance_initiated_shutdown_behavior  = "stop"
}

module "client_ca_central_1_a" {
  source                               = "../terraform/modules/campaign_instance"
  providers                            = { aws = aws.ca_central_1 }
  name_tag                             = "client-l123-ca-central-1"
  role                                 = "client"
  project_tag       = var.project_tag
  instance_type                        = var.server_client_instance_type
  ami_id                                = local.pinned_ami_x86_by_region["ca-central-1"]
  vpc_id                                = data.aws_vpc.ca_central_1.id
  subnet_id                             = data.aws_subnets.ca_central_1_b.ids[0]
  key_name                              = aws_key_pair.campaign_ca_central_1.key_name
  ssh_ingress_cidrs                     = { "control" = "${module.control.public_ip}/32" }
  # Generalizacao N-servidores (Decisao 107, gap fechado: direcao
  # cliente->servidor do criterio 2) -- o servidor que esta rota
  # atende (sa-east-1) precisa alcancar a porta 9876 deste cliente.
  criterio2_reverse_ingress_cidrs       = { "server" = "${module.server_sa_east_1.public_ip}/32" }
  self_terminate_hours                  = var.self_terminate_hours
  instance_initiated_shutdown_behavior  = "stop"
}

# Instancia SEPARADA da anterior -- mesma regiao (ca-central-1), mas
# atende um servidor DIFERENTE (us-east-1, rota L14), nunca a mesma
# maquina que o client_ca_central_1_a (L123, vs sa-east-1). Confirmado
# contra os 2 modulos reais e distintos da v8 (client_ca_central_1_a/b).
module "client_ca_central_1_b" {
  source                               = "../terraform/modules/campaign_instance"
  providers                            = { aws = aws.ca_central_1 }
  name_tag                             = "client-l14-ca-central-1"
  role                                 = "client"
  project_tag       = var.project_tag
  instance_type                        = var.server_client_instance_type
  ami_id                                = local.pinned_ami_x86_by_region["ca-central-1"]
  vpc_id                                = data.aws_vpc.ca_central_1.id
  subnet_id                             = data.aws_subnets.ca_central_1_b.ids[0]
  key_name                              = aws_key_pair.campaign_ca_central_1.key_name
  ssh_ingress_cidrs                     = { "control" = "${module.control.public_ip}/32" }
  criterio2_reverse_ingress_cidrs       = { "server" = "${module.server_us_east_1.public_ip}/32" }
  self_terminate_hours                  = var.self_terminate_hours
  instance_initiated_shutdown_behavior  = "stop"
}

module "client_eu_north_1" {
  source                               = "../terraform/modules/campaign_instance"
  providers                            = { aws = aws.eu_north_1 }
  name_tag                             = "client-l219-eu-north-1"
  role                                 = "client"
  project_tag       = var.project_tag
  instance_type                        = var.server_client_instance_type
  ami_id                                = local.pinned_ami_x86_by_region["eu-north-1"]
  vpc_id                                = data.aws_vpc.eu_north_1.id
  subnet_id                             = data.aws_subnets.eu_north_1_default.ids[0]
  key_name                              = aws_key_pair.campaign_eu_north_1.key_name
  ssh_ingress_cidrs                     = { "control" = "${module.control.public_ip}/32" }
  criterio2_reverse_ingress_cidrs       = { "server" = "${module.server_sa_east_1.public_ip}/32" }
  self_terminate_hours                  = var.self_terminate_hours
  instance_initiated_shutdown_behavior  = "stop"
}

module "client_ap_southeast_1" {
  source                               = "../terraform/modules/campaign_instance"
  providers                            = { aws = aws.ap_southeast_1 }
  name_tag                             = "client-l325-ap-southeast-1"
  role                                 = "client"
  project_tag       = var.project_tag
  instance_type                        = var.server_client_instance_type
  ami_id                                = local.pinned_ami_x86_by_region["ap-southeast-1"]
  vpc_id                                = data.aws_vpc.ap_southeast_1.id
  subnet_id                             = data.aws_subnets.ap_southeast_1_default.ids[0]
  key_name                              = aws_key_pair.campaign_ap_southeast_1.key_name
  ssh_ingress_cidrs                     = { "control" = "${module.control.public_ip}/32" }
  criterio2_reverse_ingress_cidrs       = { "server" = "${module.server_sa_east_1.public_ip}/32" }
  self_terminate_hours                  = var.self_terminate_hours
  instance_initiated_shutdown_behavior  = "stop"
}

module "client_ap_northeast_2" {
  source                               = "../terraform/modules/campaign_instance"
  providers                            = { aws = aws.ap_northeast_2 }
  name_tag                             = "client-l30-ap-northeast-2"
  role                                 = "client"
  project_tag       = var.project_tag
  instance_type                        = var.server_client_instance_type
  ami_id                                = local.pinned_ami_x86_by_region["ap-northeast-2"]
  vpc_id                                = data.aws_vpc.ap_northeast_2.id
  subnet_id                             = data.aws_subnets.ap_northeast_2_default.ids[0]
  key_name                              = aws_key_pair.campaign_ap_northeast_2.key_name
  ssh_ingress_cidrs                     = { "control" = "${module.control.public_ip}/32" }
  criterio2_reverse_ingress_cidrs       = { "server" = "${module.server_ap_northeast_1.public_ip}/32" }
  self_terminate_hours                  = var.self_terminate_hours
  instance_initiated_shutdown_behavior  = "stop"
}
