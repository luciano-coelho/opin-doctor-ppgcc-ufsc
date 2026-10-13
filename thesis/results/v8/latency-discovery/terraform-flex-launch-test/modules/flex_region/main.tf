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
  subnet_id                   = data.aws_subnets.default.ids[0]
  vpc_security_group_ids      = [aws_security_group.this.id]
  key_name                    = aws_key_pair.this.key_name
  associate_public_ip_address = true

  # 30GB gp3 -- same AMI-snapshot-size floor confirmed live in Decision 23
  # (terraform-bue-lz-test), not a new requirement.
  root_block_device {
    volume_type = "gp3"
    volume_size = 30
  }

  tags = {
    Name    = "mockopin-pqc-flex-test-${var.region_tag}-${replace(each.value, ".", "-")}"
    Project = "mockopin-pqc-aws"
    Role    = "flex-launch-test"
  }
}
