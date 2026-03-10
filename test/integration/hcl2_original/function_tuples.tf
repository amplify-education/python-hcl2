resource "octopusdeploy_process_templated_step" "step" {
  parameters = {
    "Octopus.Action.Aws.IamCapabilities" = jsonencode([
      "CAPABILITY_AUTO_EXPAND",
      "CAPABILITY_IAM",
      "CAPABILITY_NAMED_IAM",
    ])
  }
}

variable "list" {
  default = toset([
    "a",
    "b",
    "c",
  ])
}
