output "campaign_private_key" {
  description = "Chave SSH privada exclusiva da campanha oficial. Sensivel -- nunca escrita em arquivo pelo proprio Terraform."
  value       = tls_private_key.campaign.private_key_openssh
  sensitive   = true
}

# Formato ESTENDIDO em relacao ao inventory.json do piloto (thesis/
# results/v9/terraform/outputs.tf) -- la existe UM servidor so; aqui
# existem 3, cada um com seu proprio subconjunto de rotas. ACHADO
# REGISTRADO NO RELATORIO DESTA ADAPTACAO (nao resolvido aqui, fora do
# escopo de "so o Terraform"): orchestrator.py's SSHExecutor assume UM
# unico servidor (_server_ip(), _server_gateway_ip(route) sem indexar
# por qual servidor) -- vai precisar de adaptacao propria antes de
# conseguir orquestrar esta topologia de 3 servidores, independente
# deste Terraform ja estar pronto.
output "inventory" {
  description = "Hosts/IPs/papeis dos 12 recursos -- 1 controle + 3 servidores + 8 clientes, cada cliente marcado com QUAL servidor ele atende."
  value = {
    control = {
      role       = "control"
      public_ip  = module.control.public_ip
      private_ip = module.control.private_ip
    }
    servers = {
      "sa-east-1" = {
        region     = "sa-east-1"
        public_ip  = module.server_sa_east_1.public_ip
        private_ip = module.server_sa_east_1.private_ip
        routes     = ["L0", "L123", "L219", "L325"]
      }
      "us-east-1" = {
        region     = "us-east-1"
        public_ip  = module.server_us_east_1.public_ip
        private_ip = module.server_us_east_1.private_ip
        routes     = ["L0", "L14"]
      }
      "ap-northeast-1" = {
        region     = "ap-northeast-1"
        public_ip  = module.server_ap_northeast_1.public_ip
        private_ip = module.server_ap_northeast_1.private_ip
        routes     = ["L0", "L30"]
      }
    }
    clients = {
      "sa-east-1/L0" = {
        server = "sa-east-1", colocated = true
        public_ip  = module.client_l0_sa_east_1.public_ip
        private_ip = module.client_l0_sa_east_1.private_ip
      }
      "sa-east-1/L123" = {
        server = "sa-east-1", colocated = false, region = "ca-central-1"
        public_ip  = module.client_ca_central_1_a.public_ip
        private_ip = module.client_ca_central_1_a.private_ip
      }
      "sa-east-1/L219" = {
        server = "sa-east-1", colocated = false, region = "eu-north-1"
        public_ip  = module.client_eu_north_1.public_ip
        private_ip = module.client_eu_north_1.private_ip
      }
      "sa-east-1/L325" = {
        server = "sa-east-1", colocated = false, region = "ap-southeast-1"
        public_ip  = module.client_ap_southeast_1.public_ip
        private_ip = module.client_ap_southeast_1.private_ip
      }
      "us-east-1/L0" = {
        server = "us-east-1", colocated = true
        public_ip  = module.client_l0_us_east_1.public_ip
        private_ip = module.client_l0_us_east_1.private_ip
      }
      "us-east-1/L14" = {
        server = "us-east-1", colocated = false, region = "ca-central-1"
        public_ip  = module.client_ca_central_1_b.public_ip
        private_ip = module.client_ca_central_1_b.private_ip
      }
      "ap-northeast-1/L0" = {
        server = "ap-northeast-1", colocated = true
        public_ip  = module.client_l0_ap_northeast_1.public_ip
        private_ip = module.client_l0_ap_northeast_1.private_ip
      }
      "ap-northeast-1/L30" = {
        server = "ap-northeast-1", colocated = false, region = "ap-northeast-2"
        public_ip  = module.client_ap_northeast_2.public_ip
        private_ip = module.client_ap_northeast_2.private_ip
      }
    }
  }
}
