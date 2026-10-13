output "campaign_private_key" {
  description = "The campaign-exclusive SSH private key (Decision 49). Sensitive -- never written to a file by Terraform itself; campaign_up.sh reads this via `terraform output -raw campaign_private_key` and copies it to the control instance over SSH, nowhere else."
  value       = tls_private_key.campaign.private_key_openssh
  sensitive   = true
}

output "inventory" {
  description = "Hosts/IPs/roles, for campaign_up.sh to copy onto the control instance as its own inventory file."
  value = {
    control = {
      role       = "control"
      public_ip  = module.control.public_ip
      private_ip = module.control.private_ip
    }
    servers = {
      "sa-east-1"      = { public_ip = module.server_sa_east_1.public_ip, private_ip = module.server_sa_east_1.private_ip }
      "us-east-1"      = { public_ip = module.server_us_east_1.public_ip, private_ip = module.server_us_east_1.private_ip }
      "ap-northeast-1" = { public_ip = module.server_ap_northeast_1.public_ip, private_ip = module.server_ap_northeast_1.private_ip }
    }
    # Decision 53: client keys are qualified by server
    # ("<scenario>@<server>"), not bare scenario names -- L0 now exists
    # once per server, and this avoids any ambiguity about which L0 a
    # given entry is.
    clients = {
      "L0@sa-east-1"           = { region = "sa-east-1", public_ip = module.client_l0.public_ip, private_ip = module.client_l0.private_ip }
      "L123@sa-east-1"         = { region = "ca-central-1", public_ip = module.client_ca_central_1_a.public_ip, private_ip = module.client_ca_central_1_a.private_ip }
      "L219@sa-east-1"         = { region = "eu-north-1", public_ip = module.client_eu_north_1.public_ip, private_ip = module.client_eu_north_1.private_ip }
      "L325@sa-east-1"         = { region = "ap-southeast-1", public_ip = module.client_ap_southeast_1.public_ip, private_ip = module.client_ap_southeast_1.private_ip }
      "L0@us-east-1"           = { region = "us-east-1", public_ip = module.client_l0_us_east_1.public_ip, private_ip = module.client_l0_us_east_1.private_ip }
      "L14@us-east-1"          = { region = "ca-central-1", public_ip = module.client_ca_central_1_b.public_ip, private_ip = module.client_ca_central_1_b.private_ip }
      "L0@ap-northeast-1"      = { region = "ap-northeast-1", public_ip = module.client_l0_ap_northeast_1.public_ip, private_ip = module.client_l0_ap_northeast_1.private_ip }
      "L30@ap-northeast-1"     = { region = "ap-northeast-2", public_ip = module.client_ap_northeast_2.public_ip, private_ip = module.client_ap_northeast_2.private_ip }
    }
  }
}
