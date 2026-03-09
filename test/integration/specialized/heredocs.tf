locals {
  simple = <<EOF
hello world
EOF

  multiline = <<EOF
line1
line2
line3
EOF

  with_quotes = <<EOF
say "hello"
EOF

  with_backslashes = <<EOF
path\to\file
EOF

  trimmed = <<-EOF
    indented1
    indented2
  EOF

  trimmed_mixed = <<-EOF
    line1
      line2
    line3
  EOF

  json_content = <<EOF
{"key": "value"}
EOF
}
