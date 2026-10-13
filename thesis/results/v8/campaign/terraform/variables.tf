variable "aws_profile" {
  type    = string
  default = "mockopin-pqc"
}

variable "operator_ip_cidr" {
  description = <<-EOT
    Operator's public IP as a /32, discovered fresh at apply time
    (`curl -s https://checkip.amazonaws.com`) by campaign_up.sh and
    passed in as TF_VAR_operator_ip_cidr -- an environment variable, not
    a file. Grants SSH to the control instance only; never written to
    any versioned file (Decision 49).
  EOT
  type        = string
}

variable "operator_ssh_public_key" {
  description = "The operator's own, already-existing discovery key pair's public half (same one used throughout this project) -- used ONLY for the control instance's key_name, so the operator can reach it directly."
  type        = string
}

variable "server_client_instance_type" {
  description = <<-EOT
    Still open -- Decision 43's launch test hasn't run yet. NO DEFAULT,
    deliberately (Decision 52): an unset variable now fails
    `terraform plan`/`apply` outright instead of silently falling back
    to a placeholder that could get used by accident before the launch
    test actually resolves this.
  EOT
  type        = string
}

variable "control_instance_type" {
  description = "Free-tier-eligible, small -- the control instance never runs the real workload."
  type        = string
  default     = "t4g.micro"
}

variable "self_terminate_hours" {
  description = "Decision 49's safety timer, servers and clients only. Default 48h, renewable by the orchestrator."
  type        = number
  default     = 48
}
