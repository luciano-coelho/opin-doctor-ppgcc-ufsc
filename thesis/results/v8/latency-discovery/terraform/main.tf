# Mesh discovery (Decision 10): all 10 regions measure RTT against each
# other, not just sa-east-1. SSH entry stays single-hop though: only
# sa-east-1 is reachable from the operator's IP; the other 9 accept SSH
# only from sa-east-1's IP, reached via `ssh -J` (ProxyJump) -- same
# minimal-exposure pattern as the original single-origin discovery, just
# extended. ICMP is open (0.0.0.0/0) on all 10 -- see Decision 10 for why
# that's an acceptable tradeoff for this specific, harmless, short-lived
# case (bare AMI, no service, destroyed within ~2h).
module "prober" {
  source = "./modules/prober"
  providers = {
    aws = aws.sa_east_1
  }

  region_label  = "sa-east-1"
  instance_type = var.instance_type
  ssh_cidr      = var.my_ip_cidr
  icmp_cidr     = "0.0.0.0/0"
  public_key    = var.ssh_public_key
}

module "us_east_1" {
  source = "./modules/prober"
  providers = {
    aws = aws.us_east_1
  }

  region_label  = "us-east-1"
  instance_type = var.instance_type
  ssh_cidr      = "${module.prober.public_ip}/32"
  icmp_cidr     = "0.0.0.0/0"
  public_key    = var.ssh_public_key
}

module "us_east_2" {
  source = "./modules/prober"
  providers = {
    aws = aws.us_east_2
  }

  region_label  = "us-east-2"
  instance_type = var.instance_type
  ssh_cidr      = "${module.prober.public_ip}/32"
  icmp_cidr     = "0.0.0.0/0"
  public_key    = var.ssh_public_key
}

module "us_west_2" {
  source = "./modules/prober"
  providers = {
    aws = aws.us_west_2
  }

  region_label  = "us-west-2"
  instance_type = var.instance_type
  ssh_cidr      = "${module.prober.public_ip}/32"
  icmp_cidr     = "0.0.0.0/0"
  public_key    = var.ssh_public_key
}

module "ca_central_1" {
  source = "./modules/prober"
  providers = {
    aws = aws.ca_central_1
  }

  region_label  = "ca-central-1"
  instance_type = var.instance_type
  ssh_cidr      = "${module.prober.public_ip}/32"
  icmp_cidr     = "0.0.0.0/0"
  public_key    = var.ssh_public_key
}

module "eu_west_1" {
  source = "./modules/prober"
  providers = {
    aws = aws.eu_west_1
  }

  region_label  = "eu-west-1"
  instance_type = var.instance_type
  ssh_cidr      = "${module.prober.public_ip}/32"
  icmp_cidr     = "0.0.0.0/0"
  public_key    = var.ssh_public_key
}

module "eu_central_1" {
  source = "./modules/prober"
  providers = {
    aws = aws.eu_central_1
  }

  region_label  = "eu-central-1"
  instance_type = var.instance_type
  ssh_cidr      = "${module.prober.public_ip}/32"
  icmp_cidr     = "0.0.0.0/0"
  public_key    = var.ssh_public_key
}

module "ap_northeast_1" {
  source = "./modules/prober"
  providers = {
    aws = aws.ap_northeast_1
  }

  region_label  = "ap-northeast-1"
  instance_type = var.instance_type
  ssh_cidr      = "${module.prober.public_ip}/32"
  icmp_cidr     = "0.0.0.0/0"
  public_key    = var.ssh_public_key
}

module "ap_southeast_1" {
  source = "./modules/prober"
  providers = {
    aws = aws.ap_southeast_1
  }

  region_label  = "ap-southeast-1"
  instance_type = var.instance_type
  ssh_cidr      = "${module.prober.public_ip}/32"
  icmp_cidr     = "0.0.0.0/0"
  public_key    = var.ssh_public_key
}

module "ap_southeast_2" {
  source = "./modules/prober"
  providers = {
    aws = aws.ap_southeast_2
  }

  region_label  = "ap-southeast-2"
  instance_type = var.instance_type
  ssh_cidr      = "${module.prober.public_ip}/32"
  icmp_cidr     = "0.0.0.0/0"
  public_key    = var.ssh_public_key
}
