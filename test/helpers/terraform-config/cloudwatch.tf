resource "aws_cloudwatch_event_rule" "aws_cloudwatch_event_rule" {
  name          = "name"
  event_pattern = <<EOF_CONFIG
    {
      "foo": "bar"
    }
      EOF_CONFIG
}

resource "aws_cloudwatch_event_rule" "aws_cloudwatch_event_rule2" {
  name          = "name"
  event_pattern = <<-EOF_CONFIG
    {
      "foo": "bar"
    }
    EOF_CONFIG
}

resource "aws_cloudwatch_event_rule" "aws_cloudwatch_event_rule2" {
  name          = "name"
  event_pattern = jsonencode(var.cloudwatch_pattern_deploytool)
}
