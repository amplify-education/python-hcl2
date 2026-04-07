// top-level standalone comment
resource "aws_instance" "web" {
  ami = "abc-123"

  // standalone comment inside block
  instance_type = "t2.micro"

  # hash standalone comment
  count = 1 + 2
  # absorbed standalone after binary_op

  tags = {
    Name = "web"
    # comment inside object
    Env  = "prod" # inline after value
  }

  /*
  multi-line
  block comment
  */
  enabled = true

  nested {
    // comment inside nested block
    key = "value"
  }
}
