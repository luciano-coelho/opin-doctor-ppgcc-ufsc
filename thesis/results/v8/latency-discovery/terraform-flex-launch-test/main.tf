# 7 regions (3 server + 4 client, Decision 41's final topology) x 2 flex
# instance types = 14 instances. Terraform can't select a provider alias
# dynamically via for_each/count, so each region gets its own module call
# with a static `providers` map -- the module itself (modules/flex_region)
# is identical for all 7, only the provider and the region_tag differ.

module "sa_east_1" {
  source = "./modules/flex_region"
  providers = {
    aws = aws.sa_east_1
  }
  region_tag     = "sa-east-1"
  my_ip_cidr     = var.my_ip_cidr
  ssh_public_key = var.ssh_public_key
  instance_types = var.flex_instance_types
}

module "us_east_1" {
  source = "./modules/flex_region"
  providers = {
    aws = aws.us_east_1
  }
  region_tag     = "us-east-1"
  my_ip_cidr     = var.my_ip_cidr
  ssh_public_key = var.ssh_public_key
  instance_types = var.flex_instance_types
}

module "ap_northeast_1" {
  source = "./modules/flex_region"
  providers = {
    aws = aws.ap_northeast_1
  }
  region_tag     = "ap-northeast-1"
  my_ip_cidr     = var.my_ip_cidr
  ssh_public_key = var.ssh_public_key
  instance_types = var.flex_instance_types
}

module "ca_central_1" {
  source = "./modules/flex_region"
  providers = {
    aws = aws.ca_central_1
  }
  region_tag     = "ca-central-1"
  my_ip_cidr     = var.my_ip_cidr
  ssh_public_key = var.ssh_public_key
  instance_types = var.flex_instance_types
}

module "eu_north_1" {
  source = "./modules/flex_region"
  providers = {
    aws = aws.eu_north_1
  }
  region_tag     = "eu-north-1"
  my_ip_cidr     = var.my_ip_cidr
  ssh_public_key = var.ssh_public_key
  instance_types = var.flex_instance_types
}

module "ap_southeast_1" {
  source = "./modules/flex_region"
  providers = {
    aws = aws.ap_southeast_1
  }
  region_tag     = "ap-southeast-1"
  my_ip_cidr     = var.my_ip_cidr
  ssh_public_key = var.ssh_public_key
  instance_types = var.flex_instance_types
}

module "ap_northeast_2" {
  source = "./modules/flex_region"
  providers = {
    aws = aws.ap_northeast_2
  }
  region_tag     = "ap-northeast-2"
  my_ip_cidr     = var.my_ip_cidr
  ssh_public_key = var.ssh_public_key
  instance_types = var.flex_instance_types
}
