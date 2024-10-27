# TODO: add remove lock
resource "yandex_compute_disk" "factorio_data" {
  name          = "factorio-data"
  description   = "Persistent disk with Factorio data: saves, configs, etc"
  type          = "network-ssd"
  size          = 10
}

# TODO: we need initialize disk and mount somehow 
# sudo mkfs -t ext4 -L data /dev/disk/by-id/virtio-factorio-data
# sudo mkdir /factorio-data
# echo "LABEL=data /factorio-data ext4 defaults 0 0" | sudo tee -a /etc/fstab
# sudo mount /factorio-data
# sudo mkdir /

# sudo docker cp 183dfb1bfef1:/factorio/ /factorio-data
# sudo mv /factorio-data/factorio/* /factorio-data
# sudo rm -rf /factorio-data/factorio