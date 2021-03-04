variable "region" {
}

variable "account" {
}

locals {
  foo = "${var.account}_bar"
  bar = {
    baz : 1
  }
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
  }
  has_valid_forwarding_rules_template_inputs = (
    length(keys(var.forwarding_rules_template.copy_resolver_rules)) > 0 &&
    length(var.forwarding_rules_template.replace_with_target_ips) > 0 &&
    length(var.forwarding_rules_template.exclude_cidrs) > 0
  )
}
