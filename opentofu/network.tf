resource "yandex_vpc_network" "default" {
  name = "default"
}

resource "yandex_vpc_subnet" "default" {
  v4_cidr_blocks = ["10.129.0.0/24"]
  zone           = var.zone
  network_id     = "${yandex_vpc_network.default.id}"
}

resource "yandex_vpc_default_security_group" "group_default" {
  description = "Access to Factorio server."
  network_id  = yandex_vpc_network.default.id

  egress {
    from_port      = 0
    port           = -1
    protocol       = "ANY"
    to_port        = 65535
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description    = "factorio"
    from_port      = -1
    port           = 34197
    protocol       = "UDP"
    to_port        = -1
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description    = "ssh"
    from_port      = -1
    port           = 22
    protocol       = "TCP"
    to_port        = -1
    v4_cidr_blocks = ["0.0.0.0/0"]
  }
}