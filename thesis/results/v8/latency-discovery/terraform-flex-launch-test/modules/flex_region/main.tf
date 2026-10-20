# One region's worth of the launch test: both flex types, one default
# VPC, one default subnet, SSH-from-operator only, ICMP closed (no ping
# measurement here, this is a CPU/steal test, not a latency one -- no
# reason to open ICMP at all, tighter than Decision 10's precedent).
#
# x86_64, not arm64/t4g -- m7i-flex and c7i-flex are Intel-based families,
# same AMI family/filter already used for the Buenos Aires test's client
# (terraform-bue-lz-test/main.tf) and reused here unchanged.

terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# This turn: pin the AZ by ID, not just "whichever default subnet
# Terraform happens to return first" (the old data.aws_subnets.default
# with no AZ filter) -- a filter on availability-zone-id directly,
# scoped to the default VPC, resolves to exactly the one default
# subnet that actually lives in var.az_id.
data "aws_subnets" "pinned_az" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "availability-zone-id"
    values = [var.az_id]
  }
}

data "aws_ami" "al2023_x86" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-kernel-*-x86_64"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_key_pair" "this" {
  key_name   = "mockopin-pqc-flex-test-${var.region_tag}"
  public_key = var.ssh_public_key
}

resource "aws_security_group" "this" {
  name_prefix = "mockopin-pqc-flex-test-${var.region_tag}-"
  description = "mockopin PQC thesis - flex-instance launch test (ephemeral, Decision 43)"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH from operator only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project = "mockopin-pqc-aws"
    Role    = "flex-launch-test"
  }
}

resource "aws_instance" "flex" {
  for_each                    = toset(var.instance_types)
  ami                         = data.aws_ami.al2023_x86.id
  instance_type               = each.value
  # Real error found by actually applying (not assumed): aws_instance's
  # own `availability_zone` argument takes an AZ NAME ("sa-east-1a"),
  # NOT an AZ ID ("sae1-az1") -- passing var.az_id there failed all 14
  # instances with "InvalidParameterValue: Invalid availability zone".
  # Not needed anyway: subnet_id alone, already filtered to var.az_id
  # via data.aws_subnets.pinned_az's own availability-zone-id filter,
  # fully determines the AZ -- removed rather than reformatted.
  subnet_id                   = data.aws_subnets.pinned_az.ids[0]
  vpc_security_group_ids      = [aws_security_group.this.id]
  key_name                    = aws_key_pair.this.key_name
  associate_public_ip_address = true

  # This turn's safety net: a self-terminating deadline independent of
  # the orchestrating script actually reaching its own `terraform
  # destroy` step -- `shutdown -h +90` (90 minutes from boot) issues a
  # real OS-level shutdown; instance_initiated_shutdown_behavior =
  # "terminate" (below) makes THAT shutdown terminate the instance
  # (the AWS default for an OS-initiated shutdown is merely STOP, which
  # would leave it billed-idle and still holding its EBS volume
  # indefinitely) rather than just stopping it. root_block_device's own
  # delete_on_termination = true (made explicit below, not left as an
  # implicit default) means a termination via EITHER path -- this
  # safety net OR a normal `terraform destroy` -- deletes the volume
  # too, not just the instance.
  user_data                            = "#!/bin/bash\nshutdown -h +90\n"
  instance_initiated_shutdown_behavior = "terminate"

  # 30GB gp3 -- same AMI-snapshot-size floor confirmed live in Decision 23
  # (terraform-bue-lz-test), not a new requirement. delete_on_termination
  # made explicit (this turn) rather than relied on as an implicit
  # default -- see the user_data comment above for why that matters here.
  root_block_device {
    volume_type           = "gp3"
    volume_size           = 30
    delete_on_termination = true
  }

  tags = {
    Name    = "mockopin-pqc-flex-test-${var.region_tag}-${replace(each.value, ".", "-")}"
    Project = "mockopin-pqc-aws"
    Role    = "flex-launch-test"
  }
}
