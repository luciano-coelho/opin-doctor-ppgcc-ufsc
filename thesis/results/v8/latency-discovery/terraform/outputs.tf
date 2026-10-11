output "prober_public_ip" {
  value = module.prober.public_ip
}

output "candidate_public_ips" {
  value = {
    us-east-1      = module.us_east_1.public_ip
    us-east-2      = module.us_east_2.public_ip
    us-west-2      = module.us_west_2.public_ip
    ca-central-1   = module.ca_central_1.public_ip
    eu-west-1      = module.eu_west_1.public_ip
    eu-central-1   = module.eu_central_1.public_ip
    ap-northeast-1 = module.ap_northeast_1.public_ip
    ap-southeast-1 = module.ap_southeast_1.public_ip
    ap-southeast-2 = module.ap_southeast_2.public_ip
  }
}
