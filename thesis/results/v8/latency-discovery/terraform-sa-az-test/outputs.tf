output "sa_east_1_a_public_ip" {
  value = aws_instance.sa_east_1_a.public_ip
}

output "sa_east_1_a_private_ip" {
  value = aws_instance.sa_east_1_a.private_ip
}

output "sa_east_1_other_public_ips" {
  value = { for k, v in aws_instance.sa_east_1_az : k => v.public_ip }
}

output "sa_east_1_other_private_ips" {
  value = { for k, v in aws_instance.sa_east_1_az : k => v.private_ip }
}
