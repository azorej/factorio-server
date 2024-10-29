resource "yandex_iam_service_account" "monitor" {
  name      = "factorio-monitor"
}

data "yandex_compute_image" "container-optimized-image" {
  family = "container-optimized-image"
}

resource "yandex_compute_instance" "server" {
  hostname                  = "factorio"
  allow_stopping_for_update = true
  metadata = {
    "docker-container-declaration" = <<-EOT
            spec:
                containers:
                - image: factoriotools/factorio:${var.factorio_image_tag}
                  securityContext:
                    privileged: false
                  stdin: false
                  tty: false
                  volumeMounts:
                    - mountPath: /factorio
                      name: factorio-data
                restartPolicy: Always
                volumes:
                  - name: factorio-data
                    hostPath:
                      path: /factorio-data
        EOT
    "serial-port-enable"           = var.enable_serial_port ? "1" : "0"
    "ssh-keys"                     = "${var.username}:${local.ssh_public_key}"
    "user-data"                    = <<-EOT
            #cloud-config
            ssh_pwauth: no
            users:
            - name: ${var.username}
              sudo: ALL=(ALL) NOPASSWD:ALL
              shell: /bin/bash
              ssh_authorized_keys:
              - ${local.ssh_public_key}
        EOT
  }
  name               = var.host_instance_name
  platform_id        = "standard-v1"  # https://yandex.cloud/en/docs/compute/concepts/vm-platforms
  service_account_id = yandex_iam_service_account.monitor.id
  zone               = var.zone

  boot_disk {
    initialize_params {
      image_id = data.yandex_compute_image.container-optimized-image.id
    }
  }

  secondary_disk {
    disk_id = yandex_compute_disk.factorio_data.id
    auto_delete = false
    device_name = "factorio-data"
    mode = "READ_WRITE"
  }

  network_interface {
    nat            = true
    subnet_id      = yandex_vpc_subnet.default.id
  }

  resources {
    cores         = 2
    gpus          = 0
    memory        = 8
  }

  scheduling_policy {
    preemptible = false
  }

  lifecycle {
    ignore_changes = [
      boot_disk,
    ]
  }

}