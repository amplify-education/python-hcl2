locals {
  function_test          = "${var.basename}-${var.forwarder_function_name}_${md5("${var.vpc_id}${data.aws_region.current.name}")}"
}