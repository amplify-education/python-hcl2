resource "aws_s3_bucket" "name" {
  bucket = "name"
  acl    = "log-delivery-write"

  lifecycle_rule {
    id      = "to_glacier"
    prefix  = ""
    enabled = true

    expiration {
      days = 365
    }

    transition = {
      days          = 30,
      storage_class = "GLACIER",
    }
  }

  versioning {
    enabled = true
  }
}

module "bucket_name" {
  source = "s3_bucket_name"

  name    = "audit"
  account = var.account
  region  = var.region

  providers = {
    aws.ue1 = aws
    aws.uw2.attribute = aws.backup
  }
}
