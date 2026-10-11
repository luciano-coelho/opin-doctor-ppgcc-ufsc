# Small, dedicated sub-check for Decision 10's candidate regions
# (ap-northeast-2, eu-north-1) -- NOT the full 10-region mesh. sa-east-1
# is included only to serve as the SSH jump host, same role as in
# ../terraform/ (discover_latency_mesh.py hardcodes it as ORIGIN_REGION).
# ap-northeast-1, eu-west-1, eu-central-1 are included because they're the
# proposed partners for the two candidates (Decision 10).
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
  alias   = "ap_northeast_1"
  region  = "ap-northeast-1"
  profile = var.aws_profile
}

provider "aws" {
  alias   = "ap_northeast_2"
  region  = "ap-northeast-2"
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
  alias   = "eu_north_1"
  region  = "eu-north-1"
  profile = var.aws_profile
}
