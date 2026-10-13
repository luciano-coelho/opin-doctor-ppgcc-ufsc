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

  # One rule per allowed /32, not one rule with a list -- Decision 49:
  # "por regras separadas", so each client's access can be revoked
  # individually (by destroying that one rule) without touching the
  # others, and so the plan/diff for adding one more client stays a
  # single-rule change.
  dynamic "ingress" {
    for_each = toset(var.ssh_ingress_cidrs)
    content {
      description = "SSH, scoped to one /32"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  dynamic "ingress" {
    for_each = var.role == "server" ? toset(var.gateway_ingress_cidrs) : toset([])
    content {
      description = "MockOPIN gateway (443), scoped to one client /32"
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

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
}

resource "aws_instance" "this" {
  ami                         = var.ami_id
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [aws_security_group.this.id]
  key_name                    = var.key_name
  associate_public_ip_address = false # Decision 49: Elastic IP only, not an auto-assigned public IP too

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

  user_data = local.self_terminate_user_data != "" ? local.self_terminate_user_data : null

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
