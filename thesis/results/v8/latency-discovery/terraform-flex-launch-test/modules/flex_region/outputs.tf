output "public_ips" {
  value = { for t, inst in aws_instance.flex : t => inst.public_ip }
}
