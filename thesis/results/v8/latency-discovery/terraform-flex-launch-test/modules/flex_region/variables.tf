variable "region_tag" {
  description = "Short tag for this region, used in resource names (e.g. \"sa-east-1\")."
  type        = string
}

variable "my_ip_cidr" {
  type = string
}

variable "ssh_public_key" {
  type = string
}

variable "instance_types" {
  type = list(string)
}
