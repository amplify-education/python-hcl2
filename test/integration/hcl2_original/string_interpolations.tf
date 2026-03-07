block label1 label3 {
  simple_interpolation = "prefix:${var}-suffix"
  embedded_interpolation = "(long substring without interpolation); ${"aaa-${local}-${local}"}/us-west-2/key_foo"
  deeply_nested_interpolation = "prefix1-${"prefix2-${"prefix3-$${foo:bar}"}"}"
  escaped_interpolation = "prefix:$${aws:username}-suffix"
  simple_and_escaped = "${"bar"}$${baz:bat}"
  simple_and_escaped_reversed = "$${baz:bat}${"bar"}"
  nested_escaped = "bar-${"$${baz:bat}"}"
}
