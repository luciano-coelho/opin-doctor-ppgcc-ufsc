variable "aws_profile" {
  description = "Profile AWS local a usar (-var=aws_profile=... ou TF_VAR_aws_profile). Sem default de proposito (mesma politica de server_client_instance_type abaixo): o nome de um profile identifica a conta por tras dele, e este repositorio e publico -- nunca grave aqui o nome real do profile da sua conta."
  type        = string
}

variable "project_tag" {
  description = "Tag Project exigida pela politica IAM de menor privilegio do usuario operador (mockopin-campanha-operador-policy) -- toda chamada de criacao PRECISA levar esta tag, senao a propria IAM recusa (confirmado por teste de fumaca real, ver Decisao da adaptacao deste Terraform)."
  type        = string
  default     = "mockopin-pqc-campanha-oficial"
}

variable "operator_ip_cidr" {
  description = <<-EOT
    IP publico do operador como /32, descoberto em tempo de apply
    (ex.: curl -s https://checkip.amazonaws.com) e passado via
    TF_VAR_operator_ip_cidr -- variavel de ambiente, nunca arquivo
    versionado. Da SSH so a instancia de controle.
  EOT
  type        = string
}

variable "operator_ssh_public_key" {
  description = "Metade publica da chave SSH ja existente do operador -- usada so no key_name da instancia de controle."
  type        = string
}

variable "server_client_instance_type" {
  description = "Sem default de proposito (mesma politica da v8/pilot): falha alto se ninguem passar valor explicito."
  type        = string
}

variable "control_instance_type" {
  description = "Free-tier-eligible, pequena -- o controle nunca roda o fluxo medido."
  type        = string
  default     = "t4g.micro"
}

# Decisao 23 (v9, item 5) ja registrou que a CAMPANHA OFICIAL usa 48h
# (nao as 4h do piloto) -- ver thesis/results/v9/DECISIONS.md. Mantido
# aqui como o default desta configuracao SEPARADA, nunca alterando o
# default do piloto (thesis/results/v9/terraform/variables.tf continua
# em 4h, intocado).
variable "self_terminate_hours" {
  type    = number
  default = 48
}
