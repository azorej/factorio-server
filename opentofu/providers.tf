terraform {
  required_providers {
    yandex = {
      source = "opentofu/yandex"
      version = "0.114.0"
    }
    tls = {
      source = "opentofu/tls"
      version = "4.0.6"
    }
  }
}

provider "yandex" {
  zone      = var.zone
}