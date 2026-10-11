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
  alias   = "us_east_2"
  region  = "us-east-2"
  profile = var.aws_profile
}

provider "aws" {
  alias   = "us_west_2"
  region  = "us-west-2"
  profile = var.aws_profile
}

provider "aws" {
  alias   = "ca_central_1"
  region  = "ca-central-1"
  profile = var.aws_profile
}

provider "aws" {
  alias   = "eu_west_1"
  region  = "eu-west-1"
  profile = var.aws_profile
}

provider "aws" {
  alias   = "eu_central_1"
  region  = "eu-central-1"
  profile = var.aws_profile
}

provider "aws" {
  alias   = "ap_northeast_1"
  region  = "ap-northeast-1"
  profile = var.aws_profile
}

provider "aws" {
  alias   = "ap_southeast_1"
  region  = "ap-southeast-1"
  profile = var.aws_profile
}

provider "aws" {
  alias   = "ap_southeast_2"
  region  = "ap-southeast-2"
  profile = var.aws_profile
}
