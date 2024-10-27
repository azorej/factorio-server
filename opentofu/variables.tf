variable "factorio_image_tag" {
    type = string
    nullable = false 
}

variable "enable_serial_port" {
    type = bool
    default = false
    nullable = false
}

variable "host_instance_name" {
    type = string
    default = "factorio-server"
    nullable = false
}

variable "username" {
    type = string
    default = "factorio-sre"
    nullable = false
}

variable "zone" {
    type = string
    nullable = false
}