bar = {
  0                                          = 0,
  "foo"                                      = 1,
  baz                                        = 2,
  (var.account)                           = 3,
  (format("key_prefix_%s", local.foo))    = 4,
  "prefix_${var.account}:${var.user}_suffix" = 5,
  1 + 1                                   = "two",
  (2 + 2)                                 = "four",
  format("key_%s", var.name)              = "dynamic",
}
