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

# Item 5 (this turn): enabled by SCENARIO ("{scenario}@{installation}",
# the exact key inventory.json/campaign_run.py already use), not just
# by installation -- a bare installation-level toggle couldn't produce
# a partial topology like "only sa-east-1's L0 and L325" on its own.
# An installation's SERVER (and the control instance's relevance to
# it) is DERIVED from this set (local.enabled_installations below) --
# a server is only created if at least one of its own scenarios is
# enabled. Lets a small test apply (e.g. one installation, two of its
# clients) coexist in state with a later apply that adds the rest,
# without ever recreating what the first apply already created
# (Decision 68's own "nothing recreated" requirement -- every
# resource's identity is independent of which OTHER resources this
# variable currently includes).
variable "enabled_client_scenarios" {
  description = "Which client scenarios (by \"{scenario}@{installation}\" key) this apply creates. Defaults to the full 8-scenario topology (Decision 53)."
  type        = set(string)
  default = [
    "L0@sa-east-1", "L123@sa-east-1", "L219@sa-east-1", "L325@sa-east-1",
    "L0@us-east-1", "L14@us-east-1",
    "L0@ap-northeast-1", "L30@ap-northeast-1",
  ]
  validation {
    condition = alltrue([
      for s in var.enabled_client_scenarios : contains([
        "L0@sa-east-1", "L123@sa-east-1", "L219@sa-east-1", "L325@sa-east-1",
        "L0@us-east-1", "L14@us-east-1",
        "L0@ap-northeast-1", "L30@ap-northeast-1",
      ], s)
    ])
    error_message = "enabled_client_scenarios must be a subset of the 8 real scenario keys (Decision 53)."
  }
}
