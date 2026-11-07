output "public_ip" {
  value = aws_eip.this.public_ip
}

output "private_ip" {
  value = aws_instance.this.private_ip
}

output "instance_id" {
  value = aws_instance.this.id
}

output "security_group_id" {
  value = aws_security_group.this.id
}
