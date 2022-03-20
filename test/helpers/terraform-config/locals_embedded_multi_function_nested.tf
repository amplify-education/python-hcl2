# provided with and without the quotes, to validate the test output.
# both values should evaluate to the same values
locals {
  multi_function          = substr(split("-", "us-west-2")[0], 0, 1)
  multi_function_embedded = substr(split("-", "us-west-2")[0], 0, 1)
}