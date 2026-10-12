variable "aws_profile" {
  type    = string
  default = "mockopin-pqc"
}

variable "my_ip_cidr" {
  description = "Operator's public IP as a /32 CIDR, allowed to SSH into the sa-east-1-a jump host."
  type        = string
}

variable "ssh_public_key" {
  type = string
}

variable "sa_east_1_instance_type" {
  description = <<-EOT
    Discovery-standard type, same as every other latency measurement in
    this project. Confirmed free-tier-eligible on this account via
    `describe-instance-types --filters Name=free-tier-eligible,Values=true`
    (Decision 29) -- t4g.micro is in that list.
  EOT
  type        = string
  default     = "t4g.micro"
}
