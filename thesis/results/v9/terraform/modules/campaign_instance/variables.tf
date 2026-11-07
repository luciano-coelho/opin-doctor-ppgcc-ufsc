variable "name_tag" {
  type = string
}

variable "role" {
  description = "\"server\", \"client\", or \"control\" -- only \"server\" opens the gateway port; only \"control\" allows SSH from outside the campaign's own key pair's holders."
  type        = string
  validation {
    condition     = contains(["server", "client", "control"], var.role)
    error_message = "role must be server, client, or control."
  }
}

variable "instance_type" {
  type = string
}

variable "ami_id" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "key_name" {
  description = "The campaign's single, exclusive key pair (Decision 49) -- same name/public key on every instance; the private key never touches user-data or this repository."
  type        = string
}

variable "ssh_ingress_cidrs" {
  description = "/32s allowed on port 22, keyed by a static, literal label (e.g. \"control\", \"operator\") -- NOT by the CIDR value itself, which may be unknown until apply (DECISIONS.md: for_each needs its KEYS known at plan time, not its values). For server/client roles, this is the control instance's own EIP /32 only (key \"control\"). For the control role, this is the operator's own /32, discovered at apply time and passed in -- never written to a versioned file (key \"operator\")."
  type        = map(string)
}

variable "gateway_ingress_cidrs" {
  description = "/32s allowed on port 443 (the MockOPIN gateway), keyed by the scenario's own static label (e.g. \"L0\", \"L325\") -- same static-key/dynamic-value reasoning as ssh_ingress_cidrs. Only meaningful for role=\"server\" -- one separate rule per client this server actually serves, created once by Terraform and left in place for the whole campaign (not toggled at runtime)."
  type        = map(string)
  default     = {}
}

variable "self_terminate_hours" {
  description = "Safety timer (Decision 49): the instance shuts itself down after this many hours unless the orchestrator renews the deadline. 0 disables the timer entirely -- used for the control instance, which is deliberately exempt."
  type        = number
  default     = 0
}

# v9 Decisao 23 item 5/Decisao 46 (portado do modulo real da v8, campo
# novo e aditivo -- v8's own aws_instance never sets this, so null
# here reproduces v8's exact behavior byte for byte; the v9 pilot
# passes "terminate" explicitly, since `shutdown -h now` (the safety
# timer's own command, templates/safety_timer.sh.tftpl, unchanged from
# v8) defaults to AWS's own "stop" otherwise -- Decisao 23 confirmed
# this was v8's real, undocumented default and decided v9 should
# diverge deliberately).
variable "instance_initiated_shutdown_behavior" {
  description = "null reproduces v8's real, unset default (AWS's own \"stop\"). v9's pilot passes \"terminate\" explicitly (Decisao 23 item 5) so the safety timer's `shutdown -h now` destroys the instance instead of merely stopping it -- note this still never releases the instance's own aws_eip (Decisao 43/45): only a real `terraform destroy` does that, regardless of this setting."
  type        = string
  default     = null
  validation {
    condition     = var.instance_initiated_shutdown_behavior == null || contains(["stop", "terminate"], var.instance_initiated_shutdown_behavior)
    error_message = "instance_initiated_shutdown_behavior must be null, \"stop\", or \"terminate\"."
  }
}
