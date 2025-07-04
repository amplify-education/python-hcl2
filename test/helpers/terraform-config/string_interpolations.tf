locals {
  simple_interpolation = "prefix:${var.foo}-suffix"
  embedded_interpolation = "(long substring without interpolation); ${module.special_constants.aws_accounts["aaa-${local.foo}-${local.bar}"]}/us-west-2/key_foo"
  deeply_nested_interpolation = "prefix1-${"prefix2-${"prefix3-$${foo:bar}"}"}"
  escaped_interpolation = "prefix:$${aws:username}-suffix"
  simple_and_escaped = "${"bar"}$${baz:bat}"
  simple_and_escaped_reversed = "$${baz:bat}${"bar"}"
  nested_escaped = "bar-${"$${baz:bat}"}"
}
