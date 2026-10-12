variable "aws_profile" {
  type    = string
  default = "mockopin-pqc"
}

variable "my_ip_cidr" {
  description = "Operator's public IP as a /32 CIDR, allowed to SSH into the sa-east-1-a prober."
  type        = string
}

variable "ssh_public_key" {
  type = string
}

variable "sa_east_1_instance_type" {
  description = "Discovery-standard type, same as every other latency measurement in this project."
  type        = string
  default     = "t4g.micro"
}

variable "bue_instance_type" {
  description = <<-EOT
    PLACEHOLDER -- us-east-1-bue-1a's actual instance-type catalog is
    unknown until the zone is opted into (describe-instance-type-offerings
    returns empty for a non-opted-in zone; confirmed live, see Decision
    17). t3.medium is a reasonable guess (most Local Zones support at
    least the t3/m5/c5 x86 families per AWS's own Local Zone docs) but
    MUST be re-verified once opted in, before this is actually applied.
  EOT
  type        = string
  default     = "t3.medium"
}
