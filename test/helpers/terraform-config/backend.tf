provider "aws" {
  region = var.region
}

provider "aws" {
  region = (var.backup_region)
  alias  = "backup"
}

terraform { required_version = "0.12"}

terraform {
  backend "gcs" {}
}
