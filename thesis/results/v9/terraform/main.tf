# ============================================================
# Chaves (Decisao 26 item 3, portado da Decisao 49 real da v8)
# ============================================================

resource "tls_private_key" "campaign" {
  algorithm = "ED25519"
}

resource "aws_key_pair" "campaign_sa_east_1" {
  provider   = aws.sa_east_1
  key_name   = "mockopin-pqc-v9-piloto"
  public_key = tls_private_key.campaign.public_key_openssh
}
resource "aws_key_pair" "campaign_eu_north_1" {
  provider   = aws.eu_north_1
  key_name   = "mockopin-pqc-v9-piloto"
  public_key = tls_private_key.campaign.public_key_openssh
}
resource "aws_key_pair" "campaign_ap_southeast_1" {
  provider   = aws.ap_southeast_1
  key_name   = "mockopin-pqc-v9-piloto"
  public_key = tls_private_key.campaign.public_key_openssh
}

# O controle usa a chave JA EXISTENTE do operador (nao a exclusiva da
# campanha) -- mesmo padrao da v8 real, pro operador alcanca-lo direto.
resource "aws_key_pair" "operator_sa_east_1" {
  provider   = aws.sa_east_1
  key_name   = "mockopin-pqc-v9-piloto-operator"
  public_key = var.operator_ssh_public_key
}

# ============================================================
# VPC / subnet / AMI, uma por regiao do piloto
# ============================================================

data "aws_vpc" "sa_east_1" {
  provider = aws.sa_east_1
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

# sa-east-1 precisa de UMA AZ especifica (por AZ ID, igual a Decisao
# 41/53 da v8) compartilhada pelo servidor e pelo cliente L0
# co-localizado -- o controle usa o default generico (AZ nao importa
# pra ele).
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

# AMIs PINADOS, nao resolvidos a cada apply -- mesmo motivo e MESMOS
# IDs reais ja usados e versionados pela v8 (`v8/campaign/terraform/
# main.tf`, resolvidos uma vez via describe-images real em
# 2026-10-20): evita que uma campanha/piloto atravesse builds AL2023
# diferentes silenciosamente. IDs de AMI nao sao segredo de conta --
# sao identificadores publicos da Amazon, iguais para qualquer conta
# na mesma regiao.
locals {
  pinned_ami_x86_by_region = {
    "sa-east-1"      = "ami-0c7fb00ead73effc8" # al2023-ami-minimal-2023.12.20261016.0-kernel-6.12-x86_64
    "eu-north-1"     = "ami-0048d119f137c7738" # al2023-ami-minimal-2023.12.20261016.0-kernel-6.12-x86_64
    "ap-southeast-1" = "ami-012634091f2034c69" # al2023-ami-minimal-2023.12.20261016.0-kernel-6.12-x86_64
  }
  pinned_ami_arm64_sa_east_1 = "ami-0518be3fcd9e81858" # al2023-ami-minimal-2023.12.20261016.0-kernel-6.12-arm64
}

# ============================================================
# Controle -- sem credencial/role AWS, fora do autodesligamento, SSH
# so do /32 do operador (Decisao 26 item 3).
# ============================================================

module "control" {
  source            = "./modules/campaign_instance"
  providers         = { aws = aws.sa_east_1 }
  name_tag          = "control"
  role              = "control"
  instance_type     = var.control_instance_type
  ami_id            = local.pinned_ami_arm64_sa_east_1
  vpc_id            = data.aws_vpc.sa_east_1.id
  subnet_id         = data.aws_subnets.sa_east_1_default.ids[0]
  key_name          = aws_key_pair.operator_sa_east_1.key_name
  ssh_ingress_cidrs = { "operator" = var.operator_ip_cidr }
  # Decisao 50: NAO mais isento -- rede de seguranca de ULTIMO
  # RECURSO, 5h (acima de qualquer piloto real, ~2h) com terminate,
  # pro risco residual que a Decisao 49 item 4 registrou (controle
  # era o UNICO recurso sem nenhum autodesligamento). NUNCA substitui
  # o destroy final nem a liberacao de EIP do cleanup.py -- so impede
  # o controle (e o EIP dele) de rodar indefinidamente numa sessao
  # abandonada sem ninguem rodar cleanup.py.
  self_terminate_hours                 = 5
  instance_initiated_shutdown_behavior = "terminate"
}

# ============================================================
# Clientes -- SSH so do EIP do controle (Decisao 43/45: confirmado
# contra o incidente 83 real da v8 que isso funciona por construcao,
# contanto que SEMPRE se disque o alvo pelo IP publico -- nunca o
# privado, pra SSH especificamente).
# ============================================================

module "client_l0" {
  source                               = "./modules/campaign_instance"
  providers                            = { aws = aws.sa_east_1 }
  name_tag                             = "client-l0"
  role                                 = "client"
  instance_type                        = var.server_client_instance_type
  ami_id                               = local.pinned_ami_x86_by_region["sa-east-1"]
  vpc_id                               = data.aws_vpc.sa_east_1.id
  subnet_id                            = data.aws_subnets.sa_east_1_az1.ids[0] # mesma AZ ID do servidor
  key_name                             = aws_key_pair.campaign_sa_east_1.key_name
  ssh_ingress_cidrs                    = { "control" = "${module.control.public_ip}/32" }
  self_terminate_hours                 = var.self_terminate_hours
  instance_initiated_shutdown_behavior = "terminate" # Decisao 23 item 5
}

module "client_eu_north_1" {
  source                               = "./modules/campaign_instance"
  providers                            = { aws = aws.eu_north_1 }
  name_tag                             = "client-l219"
  role                                 = "client"
  instance_type                        = var.server_client_instance_type
  ami_id                               = local.pinned_ami_x86_by_region["eu-north-1"]
  vpc_id                               = data.aws_vpc.eu_north_1.id
  subnet_id                            = data.aws_subnets.eu_north_1_default.ids[0]
  key_name                             = aws_key_pair.campaign_eu_north_1.key_name
  ssh_ingress_cidrs                    = { "control" = "${module.control.public_ip}/32" }
  self_terminate_hours                 = var.self_terminate_hours
  instance_initiated_shutdown_behavior = "terminate"
}

module "client_ap_southeast_1" {
  source                               = "./modules/campaign_instance"
  providers                            = { aws = aws.ap_southeast_1 }
  name_tag                             = "client-l325"
  role                                 = "client"
  instance_type                        = var.server_client_instance_type
  ami_id                               = local.pinned_ami_x86_by_region["ap-southeast-1"]
  vpc_id                               = data.aws_vpc.ap_southeast_1.id
  subnet_id                            = data.aws_subnets.ap_southeast_1_default.ids[0]
  key_name                             = aws_key_pair.campaign_ap_southeast_1.key_name
  ssh_ingress_cidrs                    = { "control" = "${module.control.public_ip}/32" }
  self_terminate_hours                 = var.self_terminate_hours
  instance_initiated_shutdown_behavior = "terminate"
}

# ============================================================
# Servidor -- gateway (443) aberto so pros 3 clientes do piloto, um
# por rota; L0 pelo IP PRIVADO (co-localizado), L219/L325 pelo IP
# PUBLICO (regioes diferentes, sem peering -- Decisao 27 item 1).
# ============================================================

module "server_sa_east_1" {
  source            = "./modules/campaign_instance"
  providers         = { aws = aws.sa_east_1 }
  name_tag          = "server"
  role              = "server"
  instance_type     = var.server_client_instance_type
  ami_id            = local.pinned_ami_x86_by_region["sa-east-1"]
  vpc_id            = data.aws_vpc.sa_east_1.id
  subnet_id         = data.aws_subnets.sa_east_1_az1.ids[0] # mesma AZ ID do cliente L0
  key_name          = aws_key_pair.campaign_sa_east_1.key_name
  ssh_ingress_cidrs = { "control" = "${module.control.public_ip}/32" }
  gateway_ingress_cidrs = {
    "L0"   = "${module.client_l0.private_ip}/32"            # co-localizado, Decisao 27 item 1
    "L219" = "${module.client_eu_north_1.public_ip}/32"     # cross-region
    "L325" = "${module.client_ap_southeast_1.public_ip}/32" # cross-region
  }
  self_terminate_hours                 = var.self_terminate_hours
  instance_initiated_shutdown_behavior = "terminate"
}
