variable "aws_profile" {
  type    = string
  default = "mockopin-pqc"
}

variable "my_ip_cidr" {
  description = "Operator's public IP as a /32 CIDR, allowed to SSH into every instance directly -- no jump host needed here, every instance is independent and short-lived (a few minutes)."
  type        = string
}

variable "ssh_public_key" {
  type = string
}

variable "flex_instance_types" {
  description = "Decision 32/43: both confirmed free-tier-eligible on this account."
  type        = list(string)
  default     = ["m7i-flex.large", "c7i-flex.large"]
}
