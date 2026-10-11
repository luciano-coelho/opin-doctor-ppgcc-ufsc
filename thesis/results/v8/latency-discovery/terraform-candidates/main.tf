module "prober" {
  source = "../terraform/modules/prober"
  providers = {
    aws = aws.sa_east_1
  }

  region_label  = "sa-east-1"
  instance_type = var.instance_type
  ssh_cidr      = var.my_ip_cidr
  icmp_cidr     = "0.0.0.0/0"
  public_key    = var.ssh_public_key
}

module "ap_northeast_1" {
  source = "../terraform/modules/prober"
  providers = {
    aws = aws.ap_northeast_1
  }

  region_label  = "ap-northeast-1"
  instance_type = var.instance_type
  ssh_cidr      = "${module.prober.public_ip}/32"
  icmp_cidr     = "0.0.0.0/0"
  public_key    = var.ssh_public_key
}

module "ap_northeast_2" {
  source = "../terraform/modules/prober"
  providers = {
    aws = aws.ap_northeast_2
  }

  region_label  = "ap-northeast-2"
  instance_type = var.instance_type
  ssh_cidr      = "${module.prober.public_ip}/32"
  icmp_cidr     = "0.0.0.0/0"
  public_key    = var.ssh_public_key
}

module "eu_west_1" {
  source = "../terraform/modules/prober"
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
  source = "../terraform/modules/prober"
  providers = {
    aws = aws.eu_central_1
  }

  region_label  = "eu-central-1"
  instance_type = var.instance_type
  ssh_cidr      = "${module.prober.public_ip}/32"
  icmp_cidr     = "0.0.0.0/0"
  public_key    = var.ssh_public_key
}

module "eu_north_1" {
  source = "../terraform/modules/prober"
  providers = {
    aws = aws.eu_north_1
  }

  region_label  = "eu-north-1"
  instance_type = var.instance_type
  ssh_cidr      = "${module.prober.public_ip}/32"
  icmp_cidr     = "0.0.0.0/0"
  public_key    = var.ssh_public_key
}
