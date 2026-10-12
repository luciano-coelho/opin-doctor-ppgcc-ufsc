# Decision 30/31's Buenos-Aires-free sa-east-1 intra-region AZ-to-AZ RTT
# test. Adapted from terraform-bue-lz-test (kept, not deleted, per
# Decision 31) with the Buenos Aires / us-east-1 half removed entirely --
# only sa-east-1 is needed now.
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
