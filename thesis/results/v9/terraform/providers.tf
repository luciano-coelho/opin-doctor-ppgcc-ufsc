# v9 piloto (Decisao 26/27/43/45/46). PREPARADO, NAO APLICADO --
# so `terraform validate`/`terraform fmt` nesta sessao. Apply exige o
# autor presente, mesma regra de sempre neste projeto.
#
# 3 regioes apenas (nao as 7 da campanha oficial da v8): sa-east-1
# (servidor + cliente L0 co-localizado + controle), eu-north-1
# (cliente L219), ap-southeast-1 (cliente L325) -- exatamente a
# topologia que a Decisao 26 corrigiu.
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  alias   = "sa_east_1"
  region  = "sa-east-1"
  profile = var.aws_profile
}

provider "aws" {
  alias   = "eu_north_1"
  region  = "eu-north-1"
  profile = var.aws_profile
}

provider "aws" {
  alias   = "ap_southeast_1"
  region  = "ap-southeast-1"
  profile = var.aws_profile
}
