# Decision 17's proposed Buenos Aires Local Zone test. NOT APPLIED --
# plan-only until the author opts into the us-east-1-bue-1 zone group
# (admin action, outside this restricted profile's reach -- see
# DECISIONS.md, Decision 21) and gives the go-ahead.
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Local Zones are organized under their parent region's API even though
# they're physically remote from it -- Buenos Aires is a zone of us-east-1.
provider "aws" {
  alias   = "us_east_1"
  region  = "us-east-1"
  profile = var.aws_profile
}

provider "aws" {
  alias   = "sa_east_1"
  region  = "sa-east-1"
  profile = var.aws_profile
}
