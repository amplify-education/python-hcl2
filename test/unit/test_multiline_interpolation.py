# pylint: disable=C0103,C0114,C0115,C0116
r"""A heredoc whose interpolation spans lines is not flattened (GH #347).

`preserve_heredocs=False` returns a heredoc as quoted-string source. That form
cannot hold an interpolation running across lines: the newlines inside `${...}`
are expression source, where OpenTofu rejects an escaped one -- "This character
is not used within the language" -- and a raw one makes the quoted string span
lines, which it rejects as an invalid multi-line string.

Before, it produced the raw-newline version: output neither Terraform nor this
library could read, written with no error. Declining is the only answer that
does not change what the document means. The two alternatives both do:
collapsing the interpolation onto one line silently breaks an expression
holding a `#` comment or a nested heredoc, and raising breaks callers
flattening documents that contain one.

The declined form is the one `preserve_heredocs=True` produces, which reads
back as this heredoc -- so the value survives, in the shape that can carry it.
"""

from unittest import TestCase

from hcl2.api import dumps, loads
from hcl2.utils import SerializationOptions

FLAT = SerializationOptions(preserve_heredocs=False)
VALUE = SerializationOptions(preserve_heredocs=False, strip_string_quotes=True)

MULTI_LINE = "a = <<EOT\n${\n  1 + 2\n}\nEOT\n"
SINGLE_LINE = "a = <<EOT\n${1 + 2}\nEOT\n"


class TestItDeclinesRatherThanCorrupts(TestCase):
    def test_the_heredoc_is_handed_back(self):
        self.assertEqual(loads(MULTI_LINE, serialization_options=FLAT)["a"], '"<<EOT\n${\n  1 + 2\n}\nEOT"')

    def test_the_document_round_trips(self):
        self.assertEqual(dumps(loads(MULTI_LINE, serialization_options=FLAT)), MULTI_LINE)

    def test_the_trim_form_too(self):
        source = "a = <<-EOT\n  ${\n    1 + 2\n  }\n  EOT\n"
        self.assertEqual(dumps(loads(source, serialization_options=FLAT)), source)

    def test_a_directive_spanning_lines_counts(self):
        source = "a = <<EOT\n%{ if\n  true }t%{ endif }\nEOT\n"
        self.assertEqual(dumps(loads(source, serialization_options=FLAT)), source)


class TestEverythingElseStillFlattens(TestCase):
    def test_a_single_line_interpolation(self):
        self.assertEqual(loads(SINGLE_LINE, serialization_options=FLAT)["a"], '"${1 + 2}\\n"')

    def test_a_body_with_no_interpolation(self):
        self.assertEqual(loads("a = <<EOT\nplain\nEOT\n", serialization_options=FLAT)["a"], '"plain\\n"')

    def test_a_newline_outside_the_span_is_not_the_problem(self):
        self.assertEqual(
            loads("a = <<EOT\none\n${x}\ntwo\nEOT\n", serialization_options=FLAT)["a"],
            '"one\\n${x}\\ntwo\\n"',
        )


class TestTheValueFormIsUnaffected(TestCase):
    """`strip_string_quotes` asks for the value, which has no such limit."""

    def test_the_body_comes_back_whole(self):
        self.assertEqual(loads(MULTI_LINE, serialization_options=VALUE)["a"], "${\n  1 + 2\n}\n")


class TestTheTrimMarginIgnoresExpressionSource(TestCase):
    """`<<-` measures its margin on the lines that start with literal text.

    A line that begins inside a `${...}` span is expression source, and its
    indent is part of that expression rather than of the heredoc. OpenTofu
    v1.12.6 evaluates `<<-EOT\\n    a ${\\n  "b"\\n    }\\n    c\\n    EOT` to
    `a b\\nc\\n`: the shallow `  "b"` line does not lower the margin, and the
    literal lines lose all four spaces. Counting it left them two.
    """

    def test_a_shallow_line_inside_a_span_does_not_lower_the_margin(self):
        source = 'x = <<-EOT\n    a ${\n  "b"\n    }\n    c\n    EOT\n'
        self.assertEqual(loads(source, serialization_options=VALUE)["x"], 'a ${\n  "b"\n    }\nc\n')

    def test_a_span_opened_at_the_start_of_a_line_still_measures_it(self):
        # `    ${` starts with literal whitespace, so it counts; `"y"}` does not.
        source = 'x = <<-EOT\n    a ${"x"}\n    ${\n"y"}\n    c\n    EOT\n'
        self.assertEqual(loads(source, serialization_options=VALUE)["x"], 'a ${"x"}\n${\n"y"}\nc\n')

    def test_without_a_span_nothing_changes(self):
        source = "x = <<-EOT\n    a\n  b\n    EOT\n"
        self.assertEqual(loads(source, serialization_options=VALUE)["x"], "  a\nb\n")
