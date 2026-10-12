# ============================================================
# sa-east-1 intra-region AZ-to-AZ RTT test (Decision 30/31) -- no Buenos
# Aires. 4 instances: 3 AZs by AZ ID (the real cross-AZ figure) plus a
# second instance in the SAME zone as the first, as a same-AZ sanity
# floor. sa-east-1-a doubles as the SSH jump host for a2/b/c -- same
# minimal-exposure pattern as every other discovery Terraform in this
# project (Decision 7): only "a" is reachable from the operator; the
# others only from "a"'s own IP, discovered via ProxyCommand the same way
# discover_latency_mesh.py already does for the main 10-region mesh.
# ============================================================

data "aws_vpc" "sa_east_1_default" {
  provider = aws.sa_east_1
  default  = true
}

data "aws_ami" "al2023_arm64_sa" {
  provider    = aws.sa_east_1
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

# Identified by AZ ID (sae1-az1/2/3), not AZ name (sa-east-1a/b/c) -- AZ
# names are account-specific aliases AWS randomizes per account
# specifically so "us-east-1a" doesn't mean the same physical location for
# every customer; AZ IDs are the stable, account-independent identifier
# (confirmed via `aws ec2 describe-availability-zones`, Decision 25).
locals {
  sa_east_1_jump_zone = "sae1-az1" # "a"
  # "a2" shares the SAME zone ID as the jump host -- the same-AZ pair.
  sa_east_1_other_azs = { b = "sae1-az2", c = "sae1-az3", a2 = "sae1-az1" }
}

data "aws_subnets" "sa_east_1_jump" {
  provider = aws.sa_east_1
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.sa_east_1_default.id]
  }
  filter {
    name   = "availability-zone-id"
    values = [local.sa_east_1_jump_zone]
  }
}

data "aws_subnets" "sa_east_1_az" {
  for_each = local.sa_east_1_other_azs
  provider = aws.sa_east_1
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.sa_east_1_default.id]
  }
  filter {
    name   = "availability-zone-id"
    values = [each.value]
  }
}

resource "aws_key_pair" "sa_east_1" {
  provider   = aws.sa_east_1
  key_name   = "mockopin-pqc-sa-az-test"
  public_key = var.ssh_public_key
}

resource "aws_security_group" "sa_east_1_jump" {
  provider    = aws.sa_east_1
  name_prefix = "mockopin-pqc-sa-az-a-"
  description = "mockopin PQC thesis - sa-east-1 intra-region AZ-to-AZ RTT test, jump host (ephemeral)"
  vpc_id      = data.aws_vpc.sa_east_1_default.id

  ingress {
    description = "SSH from operator"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  ingress {
    description = "ICMP ping -- same open-ICMP rationale as Decision 10"
    from_port   = -1
    to_port     = -1
    protocol    = "icmp"
    cidr_blocks = ["0.0.0.0/0"]
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

resource "aws_instance" "sa_east_1_a" {
  provider                    = aws.sa_east_1
  ami                         = data.aws_ami.al2023_arm64_sa.id
  instance_type               = var.sa_east_1_instance_type
  subnet_id                   = data.aws_subnets.sa_east_1_jump.ids[0]
  vpc_security_group_ids      = [aws_security_group.sa_east_1_jump.id]
  key_name                    = aws_key_pair.sa_east_1.key_name
  associate_public_ip_address = true

  tags = {
    Name    = "mockopin-pqc-sa-az-a"
    Project = "mockopin-pqc-aws"
    Role    = "latency-discovery"
  }
}

resource "aws_security_group" "sa_east_1_az" {
  for_each    = local.sa_east_1_other_azs
  provider    = aws.sa_east_1
  name_prefix = "mockopin-pqc-sa-az-${each.key}-"
  description = "mockopin PQC thesis - sa-east-1 intra-region AZ-to-AZ RTT test (ephemeral)"
  vpc_id      = data.aws_vpc.sa_east_1_default.id

  ingress {
    description = "SSH from the sa-east-1-a jump host only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["${aws_instance.sa_east_1_a.public_ip}/32"]
  }

  ingress {
    description = "ICMP ping -- same open-ICMP rationale as Decision 10"
    from_port   = -1
    to_port     = -1
    protocol    = "icmp"
    cidr_blocks = ["0.0.0.0/0"]
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

resource "aws_instance" "sa_east_1_az" {
  for_each                    = local.sa_east_1_other_azs
  provider                    = aws.sa_east_1
  ami                         = data.aws_ami.al2023_arm64_sa.id
  instance_type               = var.sa_east_1_instance_type
  subnet_id                   = data.aws_subnets.sa_east_1_az[each.key].ids[0]
  vpc_security_group_ids      = [aws_security_group.sa_east_1_az[each.key].id]
  key_name                    = aws_key_pair.sa_east_1.key_name
  associate_public_ip_address = true

  tags = {
    Name    = "mockopin-pqc-sa-az-${each.key}"
    Project = "mockopin-pqc-aws"
    Role    = "latency-discovery"
  }
}
