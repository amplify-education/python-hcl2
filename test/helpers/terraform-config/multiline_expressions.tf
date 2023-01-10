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
