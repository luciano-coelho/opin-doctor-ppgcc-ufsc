terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}

resource "aws_security_group" "this" {
  name_prefix = "mockopin-pqc-campaign-${var.name_tag}-"
  description = "mockopin PQC thesis - Phase 4 campaign (Decision 49), role=${var.role}"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project = "mockopin-pqc-aws"
    Role    = "campaign-${var.role}"
  }
}

# One rule per allowed /32, as separate resources -- Decision 49's own
# "por regras separadas" intent (each client's access revocable
# individually, one-rule diffs), AND fixes two real, related provider/
# Terraform errors found on the pilot's own first real apply
# (DECISIONS.md):
#
# 1. The ORIGINAL design used `dynamic "ingress"` blocks INLINE on
#    aws_security_group.this, for_each over `toset(var.gateway_ingress_
#    cidrs)` -- a LIST where every element is independently unknown on a
#    first/fresh apply (each is another module's own not-yet-created
#    public_ip/private_ip). Terraform can't tell at plan time whether two
#    unknown values will turn out equal (toset() would then collapse
#    them), so it planned a conservatively SMALLER ingress array; once
#    apply resolved both to real, DISTINCT IPs, the actual array was
#    LARGER than planned, and the AWS provider rejected the mismatch
#    outright ("Provider produced inconsistent final plan ... ingress:
#    length changed from 2 to 3") -- confirmed live, creating the
#    pilot's own server security group.
#
# 2. Moving to separate TOP-LEVEL resources with `for_each =
#    toset(a_list_of_unknowns)` does NOT fix this on its own -- it trades
#    the provider-level error for a Terraform-level one ("Invalid
#    for_each argument ... known only after apply"), because a `for_each`
#    over a SET needs every member known at plan time (the value IS the
#    key). Confirmed live running this turn's own full-campaign plan
#    (fresh install_east/ap_northeast servers, no state yet): both
#    ssh_ingress_cidrs (control's own not-yet-created public_ip) and
#    gateway_ingress_cidrs hit this. Terraform's own error message names
#    the fix directly: "use a map value where the keys are defined
#    statically ... and only the values contain apply-time results" --
#    so both variables are MAPS with fixed, literal string keys (e.g.
#    "control", "L0", "L325") decided purely by which scenario is
#    enabled (a plan-time-known boolean), never by a module output's own
#    value. Only each entry's VALUE (the real CIDR) stays unknown until
#    apply -- which `for_each` over a map tolerates fine, same reasoning
#    as point 1 above: an unknown VALUE never changes which resource
#    INSTANCES (keyed by the static map keys) exist.
resource "aws_vpc_security_group_ingress_rule" "ssh" {
  for_each          = var.ssh_ingress_cidrs
  security_group_id = aws_security_group.this.id
  description       = "SSH, scoped to one /32"
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
  cidr_ipv4         = each.value
  tags = {
    Project = "mockopin-pqc-aws"
    Role    = "campaign-${var.role}"
  }
}

resource "aws_vpc_security_group_ingress_rule" "gateway" {
  for_each          = var.role == "server" ? var.gateway_ingress_cidrs : {}
  security_group_id = aws_security_group.this.id
  description       = "MockOPIN gateway (443), scoped to one client /32"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = each.value
  tags = {
    Project = "mockopin-pqc-aws"
    Role    = "campaign-${var.role}"
  }
}

locals {
  # Renewable safety timer -- Decision 49. A systemd timer checks a
  # deadline file every 5 minutes; past it, the instance shuts itself
  # down. The orchestrator (or a human) renews by overwriting the
  # deadline file. This is a safety net, not a teardown substitute: it
  # does not release the Elastic IP and does not replace
  # campaign_down.sh's own verified teardown (documented explicitly in
  # Decision 49).
  self_terminate_user_data = var.self_terminate_hours > 0 ? templatefile(
    "${path.module}/templates/safety_timer.sh.tftpl",
    { self_terminate_hours = var.self_terminate_hours }
  ) : ""

  # Decision 71 + this turn's own software-inventory audit: docker,
  # rsync, chrony, tcpdump, ping, ss, flock -- on EVERY instance
  # (server, client, AND control -- not role-gated, see
  # install_common_packages.sh's own comment for why). None of these
  # ship on the Amazon Linux 2023 MINIMAL base AMI by default
  # (confirmed empirically, this turn, for all seven in a real
  # amazonlinux:2023 container: only python3 and curl are present out
  # of the box). Without `docker`, NOTHING in this project's own SSH
  # commands would have worked on a real instance at all -- none of
  # them prefix `docker` with `sudo` (campaign_run.py's tcpdump start
  # is the only thing that does, and that's tcpdump, not docker), so
  # `ec2-user` must be in the `docker` group on every instance that
  # runs one.
  install_common_packages_user_data = file("${path.module}/templates/install_common_packages.sh")

  user_data_parts    = compact([local.self_terminate_user_data, local.install_common_packages_user_data])
  combined_user_data = length(local.user_data_parts) > 0 ? join("\n", local.user_data_parts) : ""
}

resource "aws_instance" "this" {
  ami                         = var.ami_id
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [aws_security_group.this.id]
  key_name                    = var.key_name
  associate_public_ip_address = false # Decision 49: Elastic IP only, not an auto-assigned public IP too

  # Found live on the pilot's own first real apply (DECISIONS.md): every
  # region here uses the account's DEFAULT VPC's default subnet, and
  # confirmed directly (`aws ec2 describe-subnets`) that
  # MapPublicIpOnLaunch=true on it -- AWS launches the instance with an
  # auto-assigned public IP regardless of this attribute's own requested
  # `false`, so Terraform's own post-apply refresh reads back `true` and
  # wants to REPLACE the instance on every subsequent plan to "fix" an
  # attribute AWS was never going to honor in the first place. Harmless
  # in practice: associating the Elastic IP (aws_eip, this module)
  # immediately supersedes whatever auto-assigned address the instance
  # launched with as its actual public IP -- confirmed live, every
  # pilot instance's own observed PublicIpAddress already equals its
  # Elastic IP, not a leftover ephemeral one. Ignored rather than set to
  # `true`: setting it to `true` would be fine ONLY as long as every
  # future subnet used here also defaults to MapPublicIpOnLaunch=true,
  # which isn't guaranteed if this module is ever pointed at a
  # non-default VPC -- ignoring the drift (not fighting a value AWS
  # overrides anyway) is the one choice that is correct and reproducible
  # regardless of the subnet's own setting.
  lifecycle {
    ignore_changes = [associate_public_ip_address]
  }

  # IMDSv2 mandatory (Decision 49) -- no AWS credential and no IAM role
  # are attached anywhere on this project's instances (no
  # iam_instance_profile below, intentionally), so IMDSv2 isn't gating
  # credential theft here specifically, but it's the documented AWS
  # baseline hardening and costs nothing to apply uniformly.
  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = 30
  }

  user_data = local.combined_user_data != "" ? local.combined_user_data : null

  tags = {
    Name    = "mockopin-pqc-campaign-${var.name_tag}"
    Project = "mockopin-pqc-aws"
    Role    = "campaign-${var.role}"
  }
}

resource "aws_eip" "this" {
  instance = aws_instance.this.id
  domain   = "vpc"

  tags = {
    Name    = "mockopin-pqc-campaign-${var.name_tag}"
    Project = "mockopin-pqc-aws"
    Role    = "campaign-${var.role}"
  }
}
