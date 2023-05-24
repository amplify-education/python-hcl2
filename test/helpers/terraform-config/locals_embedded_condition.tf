locals {
  terraform = {
    channels = local.running_in_ci ? local.ci_channels : local.local_channels
    authentication = []
  }
}
