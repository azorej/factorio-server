resource "tls_private_key" "ssh_key" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

locals {
  ssh_private_key = tls_private_key.ssh_key.private_key_pem
  ssh_public_key = tls_private_key.ssh_key.public_key_openssh
}
