# ============================================================
# Buenos Aires Local Zone client, pinged against sa-east-1
# ============================================================

data "aws_vpc" "us_east_1_default" {
  provider = aws.us_east_1
  default  = true
}

data "aws_internet_gateway" "us_east_1_igw" {
  provider = aws.us_east_1
  filter {
    name   = "attachment.vpc-id"
    values = [data.aws_vpc.us_east_1_default.id]
  }
}

# Local Zone subnets are NOT created automatically the way standard-AZ
# default subnets are -- this has to be explicit. 172.31.128.0/20 is
# unused in this account's default VPC (existing default subnets occupy
# 172.31.{0,16,32,48,64,80}.0/20 -- confirmed via describe-subnets before
# writing this).
resource "aws_subnet" "bue_lz" {
  provider                = aws.us_east_1
  vpc_id                  = data.aws_vpc.us_east_1_default.id
  cidr_block              = "172.31.128.0/20"
  availability_zone       = "us-east-1-bue-1a"
  map_public_ip_on_launch = true

  tags = {
    Name    = "mockopin-pqc-bue-lz-test"
    Project = "mockopin-pqc-aws"
    Role    = "latency-discovery"
  }
}

resource "aws_route_table" "bue_lz" {
  provider = aws.us_east_1
  vpc_id   = data.aws_vpc.us_east_1_default.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = data.aws_internet_gateway.us_east_1_igw.id
  }

  tags = {
    Project = "mockopin-pqc-aws"
    Role    = "latency-discovery"
  }
}

resource "aws_route_table_association" "bue_lz" {
  provider       = aws.us_east_1
  subnet_id      = aws_subnet.bue_lz.id
  route_table_id = aws_route_table.bue_lz.id
}

resource "aws_security_group" "bue_client" {
  provider    = aws.us_east_1
  name_prefix = "mockopin-pqc-bue-lz-"
  description = "mockopin PQC thesis - Buenos Aires Local Zone discovery test (ephemeral)"
  vpc_id      = data.aws_vpc.us_east_1_default.id

  ingress {
    description = "SSH from the sa-east-1-a jump host only -- single entry point, same pattern as every other discovery Terraform (Decision 7)"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["${aws_instance.sa_east_1_a.public_ip}/32"]
  }

  ingress {
    description = "ICMP ping -- same open-ICMP rationale as Decision 10 (bare instance, no service, short-lived)"
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

resource "aws_key_pair" "bue" {
  provider   = aws.us_east_1
  key_name   = "mockopin-pqc-bue-lz-test"
  public_key = var.ssh_public_key
}

# x86_64 (not arm64/t4g) since Local Zones' Graviton support is less
# certain than standard regions' -- confirmed by Decision 10's reasoning
# for t4g in standard regions; not assumed to carry over here.
data "aws_ami" "al2023_x86" {
  provider    = aws.us_east_1
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

resource "aws_instance" "bue_client" {
  provider                    = aws.us_east_1
  ami                         = data.aws_ami.al2023_x86.id
  instance_type               = var.bue_instance_type
  subnet_id                   = aws_subnet.bue_lz.id
  vpc_security_group_ids      = [aws_security_group.bue_client.id]
  key_name                    = aws_key_pair.bue.key_name
  associate_public_ip_address = true # required explicitly here -- Local
  # Zone subnets don't inherit "assign public IP" automatically the way a
  # standard-AZ default subnet does (map_public_ip_on_launch is set on the
  # subnet above too, belt-and-suspenders).

  # gp2, not the newer gp3 default -- not every Local Zone has rolled out
  # gp3 support yet, gp2 is the one volume type universally available
  # everywhere standard regions are. Re-verify once applied whether gp3
  # actually works here; this is the conservative choice, not a confirmed
  # Buenos-Aires-specific requirement.
  #
  # volume_size = 30, not a smaller value -- confirmed live (first apply
  # attempt failed): the AMI's root snapshot is 30GB, and EBS requires the
  # root volume to be >= the snapshot it's created from
  # ("InvalidBlockDeviceMapping: Volume of size 8GB is smaller than
  # snapshot ... expect size >= 30GB"). Not a Local-Zone-specific
  # constraint -- this would fail in any region with this AMI.
  root_block_device {
    volume_type = "gp2"
    volume_size = 30
  }

  tags = {
    Name    = "mockopin-pqc-bue-lz-client"
    Project = "mockopin-pqc-aws"
    Role    = "latency-discovery"
  }
}

# ============================================================
# sa-east-1's 3 availability zones, pinging each other (cross-AZ, the real
# intra-region figure) and reachable from the Buenos Aires client above.
# Plus a 4th instance co-located in the SAME zone as "a", to measure a
# same-AZ pair as the sanity floor alongside the 3 cross-AZ pairs.
# sa-east-1-a doubles as the SSH jump host for b/c/a2 -- same
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
