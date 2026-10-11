output "prober_public_ip" {
  value = module.prober.public_ip
}

output "candidate_public_ips" {
  value = {
    ap-northeast-1 = module.ap_northeast_1.public_ip
    ap-northeast-2 = module.ap_northeast_2.public_ip
    eu-west-1      = module.eu_west_1.public_ip
    eu-central-1   = module.eu_central_1.public_ip
    eu-north-1     = module.eu_north_1.public_ip
  }
}
