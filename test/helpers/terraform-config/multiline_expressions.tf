resource "null_resource" "multiline_comment_multiline" {
    triggers = [
        /* "a",
        "b" */
    ]
}

resource "null_resource" "multiline_comment_single_line_before_closing_bracket" {
    triggers = [
        /* "a", "b" */ ]
}

resource "null_resource" "multiline_comment_single_line_between_brackets" {
    triggers = [
        /* "a", "b" */
    ]
}

resource "null_resource" "multiline_comment_single_line_after_opening_bracket" {
    triggers = [ /* "a", "b" */
    ]
}

resource "null_resource" "multiline_comment_multiple_single_element" {
    triggers = [ /* "a",
        "b" */
        2,
        # "c"
    ]
}

variable "some_var2" {
  description = "description"
  type        = string
  default     = cidrsubnets(
    # comment 1
    # comment 2
    "10.0.0.0/24",
    # comment 3
    # comment 4
    2,
    # comment 5
    # comment 6
    2
    # comment 7
    # comment 8
  )
}

variable "some_var2" {
  description = "description"
  default = concat(
    # comment 1
    [{"1": "1"} /* comment 2 */ ],
    # comment 3
    # comment 4
    [{"2": "2"},]
    # comment 5
  )
}
