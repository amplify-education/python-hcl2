locals {
  embedded_interpolation = "${module.special_constants.aws_accounts["aaa-${local.foo}-${local.bar}"]}/us-west-2/key_foo"
}
