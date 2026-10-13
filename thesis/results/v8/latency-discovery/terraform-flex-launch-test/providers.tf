# Decision 43's launch test: m7i-flex.large and c7i-flex.large, briefly,
# in every server region and every client region of the final campaign
# topology (Decision 41). PREPARED, NOT APPLIED -- `terraform plan` only,
# per the author's instruction. Apply requires the author present, same
# standing rule as every other apply in this project.
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
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
