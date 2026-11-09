# Campanha oficial (8 rotas, 3 servidores, 7 regioes) -- conta AWS NOVA,
# separada da conta do piloto. NUNCA aplicado automaticamente (Luciano
# precisa autorizar o primeiro apply explicitamente, mesma regra padrao
# deste projeto inteiro). Topologia confirmada identica a campanha real
# da v8 (thesis/results/v8/campaign/terraform/{providers,main}.tf) --
# mesmas 7 regioes, mesmos papeis de cliente por regiao.
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
  alias   = "us_east_1"
  region  = "us-east-1"
  profile = var.aws_profile
}

provider "aws" {
  alias   = "ap_northeast_1"
  region  = "ap-northeast-1"
  profile = var.aws_profile
}

provider "aws" {
  alias   = "ca_central_1"
  region  = "ca-central-1"
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

provider "aws" {
  alias   = "ap_northeast_2"
  region  = "ap-northeast-2"
  profile = var.aws_profile
}
