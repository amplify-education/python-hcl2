block label1 label2 {
  a = 5
  b = 1256.5
  c = 15 + (10 * 12)
  d = (-a)
  e = (a == b ? true : false)
  f = "${"this is a string"}"
  g = 1 == 2
  h = {
    k1           = 5,
    k2           = 10,
    "k3"         = {
      k4 = "a",
    },
    (5 + 5)      = "d",
    k5.attr.attr = "e",
  }
  i = [
    a,
    b,
    "c${aaa}",
    d,
    [
      1,
      2,
      3,
    ],
    f(a),
    provider::func::aa(5),
  ]
  j = func(a, b, c, d ... )
  k = a.b.5
  l = a.*.b
  m = a[*][c].a.*.1
  
  block b1 {
    a = 1
  }
}


block multiline_ternary {
  foo = (bar ? baz(foo) : foo == "bar" ? "baz" : foo)
}


block multiline_binary_ops {
  expr = {
    for k, v in local.map_a :
    k => v
    if lookup(local.map_b[v.id], "enabled", false) || (contains(local.map_c, v.id) && contains(local.map_d, v.id))
  }
}


block {
  route53_forwarding_rule_shares = {
    for forwarding_rule_key in keys(var.route53_resolver_forwarding_rule_shares) :
    "${forwarding_rule_key}" => {
      aws_account_ids = [
        for account_name in var.route53_resolver_forwarding_rule_shares[forwarding_rule_key].aws_account_names :
        module.remote_state_subaccounts.map[account_name].outputs["aws_account_id"]
      ]
    } ... 
    if substr(bucket_name, 0, 1) == "l"
  }
}
