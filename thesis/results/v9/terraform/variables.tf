variable "aws_profile" {
  type    = string
  default = "mockopin-pqc"
}

variable "operator_ip_cidr" {
  description = <<-EOT
    IP publico do operador como /32, descoberto em tempo de apply
    (ex.: `curl -s https://checkip.amazonaws.com`) e passado via
    TF_VAR_operator_ip_cidr -- variavel de ambiente, nunca arquivo
    versionado. Da SSH so a instancia de controle (Decisao 26 item 3).
  EOT
  type        = string
}

variable "operator_ssh_public_key" {
  description = "Metade publica da chave SSH ja existente do operador -- usada so no key_name da instancia de controle, pra ele alcanca-la direto (Decisao 26 item 3)."
  type        = string
}

# Decisao 25/27: m7i-flex.large confirmado no tfstate real da v8 pros
# papeis servidor/cliente. Mantido SEM default aqui de proposito
# (mesma politica da v8 real, Decisao 52 dela): falha alto se ninguem
# passar um valor explicito, em vez de usar silenciosamente um default
# que pode nao ser mais o certo.
variable "server_client_instance_type" {
  type = string
}

variable "control_instance_type" {
  description = "Free-tier-eligible, pequena -- o controle nunca roda o fluxo medido (Decisao 25 item 2)."
  type        = string
  default     = "t4g.micro"
}

# Decisao 22/23 item 5: autodesligamento de seguranca do PILOTO (nao
# da campanha oficial, que usa 48h) -- N=4h, renovavel pelo
# orquestrador.
variable "self_terminate_hours" {
  type    = number
  default = 4
}
