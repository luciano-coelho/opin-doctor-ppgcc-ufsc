variable "region_label" {
  description = "Human-readable AWS region this prober instance lives in (e.g. \"us-east-1\")."
  type        = string
}

variable "instance_type" {
  type = string
}

variable "ssh_cidr" {
  description = "CIDR allowed to SSH in (/32 of the operator's IP). Null = no SSH ingress rule."
  type        = string
  default     = null
}

variable "icmp_cidr" {
  description = "CIDR allowed to ping in (/32 of the sa-east-1 prober's public IP). Null = no ICMP ingress rule."
  type        = string
  default     = null
}

variable "public_key" {
  description = "SSH public key to install on this instance. Null = no key pair (instance not SSH-reachable)."
  type        = string
  default     = null
}
