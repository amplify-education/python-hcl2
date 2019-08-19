variable "region" {
}

variable "account" {
}

locals {
  foo = "${var.account}_bar"
}

