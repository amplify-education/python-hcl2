// a comment
provider "aws" {
  region = var.region
}

# another comment
provider "aws" {
  region = (var.backup_region)
  alias  = "backup"
}

/*
one last comment
*/
terraform { required_version = "0.12" }

terraform {
  backend "gcs" {}
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
    null = {
      source = "hashicorp/null"
    }
    template = {
      source = "hashicorp/template"
    }
  }
}
