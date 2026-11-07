output "campaign_private_key" {
  description = "Chave SSH privada exclusiva do piloto (Decisao 26 item 3). Sensivel -- nunca escrita em arquivo pelo proprio Terraform; o rele da PKI/orquestrador le via `terraform output -raw campaign_private_key` e entrega so pra instancia de controle, por SSH, nunca versionada."
  value       = tls_private_key.campaign.private_key_openssh
  sensitive   = true
}

output "inventory" {
  description = "Hosts/IPs/papeis -- mesmo formato (chaves estaticas, `colocated` explicito) que a Decisao 43/45 confirmou ser a condicao pro SSH sempre discar por IP publico funcionar."
  value = {
    control = {
      role       = "control"
      public_ip  = module.control.public_ip
      private_ip = module.control.private_ip
    }
    server = {
      region     = "sa-east-1"
      public_ip  = module.server_sa_east_1.public_ip
      private_ip = module.server_sa_east_1.private_ip
    }
    clients = {
      "L0" = {
        region     = "sa-east-1", colocated = true
        public_ip  = module.client_l0.public_ip
        private_ip = module.client_l0.private_ip
      }
      "L219" = {
        region     = "eu-north-1", colocated = false
        public_ip  = module.client_eu_north_1.public_ip
        private_ip = module.client_eu_north_1.private_ip
      }
      "L325" = {
        region     = "ap-southeast-1", colocated = false
        public_ip  = module.client_ap_southeast_1.public_ip
        private_ip = module.client_ap_southeast_1.private_ip
      }
    }
  }
}
