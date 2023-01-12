data "terraform_remote_state" "map" {
  for_each = {
    for s3_bucket_key in data.aws_s3_bucket_objects.remote_state_objects.keys :
    regex(local.remote_state_regex, s3_bucket_key)["account_alias"] => s3_bucket_key
    if length(regexall(local.remote_state_regex, s3_bucket_key)) > 0
  }
  backend = "s3"
}
