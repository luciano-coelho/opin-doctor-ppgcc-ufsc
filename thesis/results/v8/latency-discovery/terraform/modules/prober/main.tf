data "aws_ami" "al2023_arm64" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-kernel-*-arm64"]
  }
  filter {
    name   = "architecture"
    values = ["arm64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
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
  # Prefer the "a" AZ: newer AZs in some regions (observed: us-east-1e)
  # don't support every instance type/generation, including t4g.micro.
  filter {
    name   = "availability-zone"
    values = ["${var.region_label}a"]
  }
}

# Fallback for the rare region where the "a" AZ has no default subnet.
data "aws_subnets" "default_any_az" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

locals {
  subnet_id = length(data.aws_subnets.default.ids) > 0 ? data.aws_subnets.default.ids[0] : data.aws_subnets.default_any_az.ids[0]
}

resource "aws_security_group" "this" {
  name_prefix = "mockopin-pqc-discovery-"
  description = "mockopin PQC thesis - latency discovery (ephemeral, destroyed within minutes)"
  vpc_id      = data.aws_vpc.default.id

  dynamic "ingress" {
    for_each = var.ssh_cidr == null ? [] : [var.ssh_cidr]
    content {
      description = "SSH from operator"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  dynamic "ingress" {
    for_each = var.icmp_cidr == null ? [] : [var.icmp_cidr]
    content {
      description = "ICMP ping -- mesh discovery, see DECISIONS.md Decision 10 for why this is open"
      from_port   = -1
      to_port     = -1
      protocol    = "icmp"
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
    Role    = "latency-discovery"
  }
}

resource "aws_key_pair" "this" {
  count      = var.public_key != null ? 1 : 0
  key_name   = "mockopin-pqc-discovery"
  public_key = var.public_key
}

resource "aws_instance" "this" {
  ami                         = data.aws_ami.al2023_arm64.id
  instance_type               = var.instance_type
  subnet_id                   = local.subnet_id
  vpc_security_group_ids      = [aws_security_group.this.id]
  key_name                    = var.public_key != null ? aws_key_pair.this[0].key_name : null
  associate_public_ip_address = true

  tags = {
    Name    = "mockopin-pqc-discovery-${var.region_label}"
    Project = "mockopin-pqc-aws"
    Role    = "latency-discovery"
  }
}

output "public_ip" {
  value = aws_instance.this.public_ip
}
