variable "region" {
}

variable "account" {
}

locals {
  foo = "${var.account}_bar"
  bar = {
    baz : 1
    (var.account) : 2
    (format("key_prefix_%s", local.foo)) : 3
    "prefix_${var.account}:${var.user}_suffix" : "interpolation",
    "${var.start}-mid-${var.end}" : 4
    "a:b" : 5
    123 : 6
    (var.x + 1) : 7
  }
  tuple       = [local.foo]
  empty_tuple = []
}

variable "azs" {
  default = {
    us-west-1      = "us-west-1c,us-west-1b"
    us-west-2      = "us-west-2c,us-west-2b,us-west-2a"
    us-east-1      = "us-east-1c,us-east-1b,us-east-1a"
    eu-central-1   = "eu-central-1a,eu-central-1b,eu-central-1c"
    sa-east-1      = "sa-east-1a,sa-east-1c"
    ap-northeast-1 = "ap-northeast-1a,ap-northeast-1c,ap-northeast-1d"
    ap-southeast-1 = "ap-southeast-1a,ap-southeast-1b,ap-southeast-1c"
    ap-southeast-2 = "ap-southeast-2a,ap-southeast-2b,ap-southeast-2c"
  }
}

variable "options" {
  type = string
  default = {
  }
}

variable "var_with_validation" {
  type = list(object({
    id = string
    nested = list(
      object({
        id   = string
        type = string
      })
    )
  }))
  validation {
    condition     = !contains([for v in flatten(var.var_with_validation[*].id) : can(regex("^(A|B)$", v))], false)
    error_message = "The property `id` must be one of value [A, B]."
  }
  validation {
    condition     = !contains([for v in flatten(var.var_with_validation[*].nested[*].type) : can(regex("^(A|B)$", v))], false)
    error_message = "The property `nested.type` must be one of value [A, B]."
  }
}

locals {
  route53_forwarding_rule_shares = {
    for forwarding_rule_key in keys(var.route53_resolver_forwarding_rule_shares) :
    "${forwarding_rule_key}" => {
      aws_account_ids = [
        for account_name in var.route53_resolver_forwarding_rule_shares[
          forwarding_rule_key
        ].aws_account_names :
        module.remote_state_subaccounts.map[account_name].outputs["aws_account_id"]
      ]
    }
    ...
  }
  has_valid_forwarding_rules_template_inputs = (
    length(keys(var.forwarding_rules_template.copy_resolver_rules)) > 0
    && length(var.forwarding_rules_template.replace_with_target_ips) > 0 &&
    length(var.forwarding_rules_template.exclude_cidrs) > 0
  )

  for_whitespace = { for i in [1, 2, 3] :
    i =>
    i...
  }
}

locals {
  nested_data = [
    {
      id = 1,
      nested = [
        {
          id = "a"
          again = [
            { id = "a1" },
            { id = "b1" }
          ]
        },
        { id = "c" }
      ]
    },
    {
      id = 1
      nested = [
        {
          id = "a"
          again = [
            { id = "a2" },
            { id = "b2" }
          ]
        },
        {
          id = "b"
          again = [
            { id = "a" },
            { id = "b" }
          ]
        }
      ]
    }
  ]

  ids_level_1 = distinct(local.nested_data[*].id)
  ids_level_2 = flatten(local.nested_data[*].nested[*].id)
  ids_level_3 = flatten(local.nested_data[*].nested[*].again[*][0].foo.bar[0])
  bindings_by_role = distinct(flatten([
    for name in local.real_entities
    : [
      for role, members in var.bindings
      : { name = name, role = role, members = members }
    ]
  ]))
}
