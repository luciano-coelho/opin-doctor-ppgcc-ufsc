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
  description = "/32s allowed on port 22. For server/client roles, this is the control instance's own EIP /32 only. For the control role, this is the operator's own /32, discovered at apply time and passed in -- never written to a versioned file."
  type        = list(string)
}

variable "gateway_ingress_cidrs" {
  description = "/32s allowed on port 443 (the MockOPIN gateway). Only meaningful for role=\"server\" -- one separate rule per client this server actually serves, created once by Terraform and left in place for the whole campaign (not toggled at runtime)."
  type        = list(string)
  default     = []
}

variable "self_terminate_hours" {
  description = "Safety timer (Decision 49): the instance shuts itself down after this many hours unless the orchestrator renews the deadline. 0 disables the timer entirely -- used for the control instance, which is deliberately exempt."
  type        = number
  default     = 0
}
