output "public_ips_by_region" {
  value = {
    "sa-east-1"      = module.sa_east_1.public_ips
    "us-east-1"      = module.us_east_1.public_ips
    "ap-northeast-1" = module.ap_northeast_1.public_ips
    "ca-central-1"   = module.ca_central_1.public_ips
    "eu-north-1"     = module.eu_north_1.public_ips
    "ap-southeast-1" = module.ap_southeast_1.public_ips
    "ap-northeast-2" = module.ap_northeast_2.public_ips
  }
}
