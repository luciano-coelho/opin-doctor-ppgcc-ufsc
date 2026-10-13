# Phase 4 campaign infrastructure (Decision 49). PREPARED, NOT APPLIED --
# `terraform plan` only. Apply requires the author present, same standing
# rule as every other apply in this project.
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
