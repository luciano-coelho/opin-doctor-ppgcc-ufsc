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

variable "az_id" {
  description = "This turn's instruction: pin the AZ by ID (not name -- AZ names map to different physical AZs per AWS account, AZ IDs don't), confirmed via a real describe-instance-type-offerings query to actually offer BOTH flex types before being passed in here."
  type        = string
}
