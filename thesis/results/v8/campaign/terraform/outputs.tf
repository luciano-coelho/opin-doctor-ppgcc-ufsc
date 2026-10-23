output "campaign_private_key" {
  description = "The campaign-exclusive SSH private key (Decision 49). Sensitive -- never written to a file by Terraform itself; campaign_up.sh reads this via `terraform output -raw campaign_private_key` and copies it to the control instance over SSH, nowhere else."
  value       = tls_private_key.campaign.private_key_openssh
  sensitive   = true
}

output "inventory" {
  description = "Hosts/IPs/roles, for campaign_up.sh to copy onto the control instance as its own inventory file. Item 5 (this turn): every server/client entry is now conditional on var.enabled_client_scenarios -- a disabled installation/scenario is simply ABSENT from this map, not present with a null/placeholder IP, so campaign_run.py's own inventory.json never has to know a disabled entry ever existed."
  value = {
    control = {
      role       = "control"
      public_ip  = module.control.public_ip
      private_ip = module.control.private_ip
    }
    servers = merge(
      local.sa_east_1_enabled ? { "sa-east-1" = { public_ip = module.server_sa_east_1[0].public_ip, private_ip = module.server_sa_east_1[0].private_ip } } : {},
      local.us_east_1_enabled ? { "us-east-1" = { public_ip = module.server_us_east_1[0].public_ip, private_ip = module.server_us_east_1[0].private_ip } } : {},
      local.ap_northeast_1_enabled ? { "ap-northeast-1" = { public_ip = module.server_ap_northeast_1[0].public_ip, private_ip = module.server_ap_northeast_1[0].private_ip } } : {},
    )
    # Decision 53: client keys are qualified by server
    # ("<scenario>@<server>"), not bare scenario names -- L0 now exists
    # once per server, and this avoids any ambiguity about which L0 a
    # given entry is.
    # Pilot item 2 (this turn): `colocated` is an EXPLICIT literal per
    # entry, not derived by comparing `region` against the server's own
    # name -- found live, L0 (every region) genuinely cannot reach the
    # server via its PUBLIC IP at all: same-VPC traffic to another
    # instance's public/Elastic IP routes out through the Internet
    # Gateway and back, which rewrites the SOURCE to the sender's OWN
    # public IP by the time it reaches the destination's security
    # group -- which only ever allowed L0's PRIVATE IP (matching this
    # runbook's own documented intent: "one private -- L0's,
    # co-located"). campaign_run.py now reads this field to choose
    # which of the server's two IPs to hand clients as
    # REMOTE_GATEWAY_HOST.
    clients = merge(
      local.l0_sa_east_1_enabled ? { "L0@sa-east-1" = { region = "sa-east-1", colocated = true, public_ip = module.client_l0[0].public_ip, private_ip = module.client_l0[0].private_ip } } : {},
      local.l123_enabled ? { "L123@sa-east-1" = { region = "ca-central-1", colocated = false, public_ip = module.client_ca_central_1_a[0].public_ip, private_ip = module.client_ca_central_1_a[0].private_ip } } : {},
      local.l219_enabled ? { "L219@sa-east-1" = { region = "eu-north-1", colocated = false, public_ip = module.client_eu_north_1[0].public_ip, private_ip = module.client_eu_north_1[0].private_ip } } : {},
      local.l325_enabled ? { "L325@sa-east-1" = { region = "ap-southeast-1", colocated = false, public_ip = module.client_ap_southeast_1[0].public_ip, private_ip = module.client_ap_southeast_1[0].private_ip } } : {},
      local.l0_us_east_1_enabled ? { "L0@us-east-1" = { region = "us-east-1", colocated = true, public_ip = module.client_l0_us_east_1[0].public_ip, private_ip = module.client_l0_us_east_1[0].private_ip } } : {},
      local.l14_enabled ? { "L14@us-east-1" = { region = "ca-central-1", colocated = false, public_ip = module.client_ca_central_1_b[0].public_ip, private_ip = module.client_ca_central_1_b[0].private_ip } } : {},
      local.l0_ap_northeast_1_enabled ? { "L0@ap-northeast-1" = { region = "ap-northeast-1", colocated = true, public_ip = module.client_l0_ap_northeast_1[0].public_ip, private_ip = module.client_l0_ap_northeast_1[0].private_ip } } : {},
      local.l30_enabled ? { "L30@ap-northeast-1" = { region = "ap-northeast-2", colocated = false, public_ip = module.client_ap_northeast_2[0].public_ip, private_ip = module.client_ap_northeast_2[0].private_ip } } : {},
    )
  }
}
