output "ssh_private_key" {
  value = local.ssh_private_key
  sensitive=true
}

output "ssh_public_key" {
  value = local.ssh_public_key
  sensitive=true
}