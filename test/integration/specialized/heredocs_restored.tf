locals {
  simple           = "hello world"
  multiline        = <<EOF
line1
line2
line3
EOF
  with_quotes      = "say \"hello\""
  with_backslashes = "path\\to\\file"
  trimmed          = <<EOF
indented1
indented2
EOF
  trimmed_mixed    = <<EOF
line1
  line2
line3
EOF
  json_content     = "{\"key\": \"value\"}"
}
