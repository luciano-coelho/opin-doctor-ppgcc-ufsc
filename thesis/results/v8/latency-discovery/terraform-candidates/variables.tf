variable "aws_profile" {
  description = "AWS CLI profile to use (dedicated IAM user mockopin-pqc-experiment)."
  type        = string
  default     = "mockopin-pqc"
}

variable "instance_type" {
  description = "Free-tier-eligible, disposable instance type used for latency discovery."
  type        = string
  default     = "t4g.micro"
}

variable "my_ip_cidr" {
  description = "Operator's public IP as a /32 CIDR, allowed to SSH into the sa-east-1 prober."
  type        = string
}

variable "ssh_public_key" {
  description = "Contents of the throwaway SSH public key installed on all instances."
  type        = string
}
