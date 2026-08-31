# pylint: disable=C0103,C0114,C0115,C0116
r"""Flattened heredoc bodies match what Terraform/OpenTofu evaluate.

Every expectation in this file was produced by evaluating the same source with
OpenTofu v1.12.5 (`tofu console`, `jsonencode` of the resulting local), not by
reading the spec. Three things used to differ:

1. The newline before the closing marker was dropped, so `<<EOT\nline\nEOT`
   came back as `"line"` rather than `"line\n"`. The spec ends the template
   where the delimiter "subsequently appears again on a line of its own", so
   every content line, the last one included, is terminated by its own newline.
2. `<<-` measured its indent with `lstrip(" ")`, so a tab-indented heredoc
   measured zero on every line and was not dedented at all. The spec says
   "spaces", but the reference implementation dedents tabs too.
3. A whitespace-only line was excluded from the measurement and then trimmed
   anyway, so a six-space line inside a four-space heredoc came back with two.

None of this was a regression -- 7.2.1 returned the same values -- so these
are new expectations rather than restored ones.
"""

from unittest import TestCase

from hcl2.api import loads
from hcl2.utils import SerializationOptions

_VALUE = SerializationOptions(preserve_heredocs=False, strip_string_quotes=True)

# (source expression, value OpenTofu evaluates it to)
CASES = [
    ("<<EOT\nline\nEOT", "line\n"),
    ("<<EOT\nbody  \n\nEOT", "body  \n\n"),
    ("<<EOT\nx\n   EOT", "x\n"),
    ("<<EOT\nx   \nEOT", "x   \n"),
    ("<<EOT\nx\n\ny\nEOT", "x\n\ny\n"),
    ("<<EOT\nEOT", ""),
    ("<<EOT\n\nEOT", "\n"),
    ("<<EOT\n\n\nEOT", "\n\n"),
    ("<<-EOT\n  a\n    b\n  EOT", "a\n  b\n"),
    ("<<-EOT\n\ta\n\t\tb\n\tEOT", "a\n\tb\n"),
    ("<<-EOT\n    a\n      \n    b\n    EOT", "a\n      \nb\n"),
    ("<<-EOT\n  x\n\n  EOT", "x\n\n"),
    ("<<-EOT\n    a\n  b\n  EOT", "  a\nb\n"),
    ("<<-EOT\nEOT", ""),
    ("<<EOT\r\nx\r\ny\r\nEOT", "x\r\ny\r\n"),
    ("<<-EOT\r\n  x\r\n  EOT", "x\r\n"),
]


class TestHeredocValuesMatchOpenTofu(TestCase):
    maxDiff = None

    def test_every_case(self):
        for source, expected in CASES:
            with self.subTest(source=source):
                self.assertEqual(loads(f"x = {source}\n", serialization_options=_VALUE)["x"], expected)


class TestTrailingNewline(TestCase):
    """The last content line is terminated like every other one."""

    def test_one_line_body_keeps_its_newline(self):
        self.assertEqual(loads("x = <<EOT\nline\nEOT\n", serialization_options=_VALUE)["x"], "line\n")

    def test_the_marker_indent_is_still_not_content(self):
        source = "x = <<EOT\nline\n      EOT\n"
        self.assertEqual(loads(source, serialization_options=_VALUE)["x"], "line\n")

    def test_an_empty_body_stays_empty(self):
        # There is no content line, so there is no newline to keep.
        self.assertEqual(loads("x = <<EOT\nEOT\n", serialization_options=_VALUE)["x"], "")


class TestTrimMeasuresTabs(TestCase):
    """`<<-` dedents tab-indented bodies, as the reference implementation does."""

    def test_tabs_are_dedented(self):
        source = "x = <<-EOT\n\ta\n\t\tb\n\tEOT\n"
        self.assertEqual(loads(source, serialization_options=_VALUE)["x"], "a\n\tb\n")

    def test_spaces_are_unaffected(self):
        source = "x = <<-EOT\n  a\n    b\n  EOT\n"
        self.assertEqual(loads(source, serialization_options=_VALUE)["x"], "a\n  b\n")

    def test_a_mixed_indent_measures_characters(self):
        # One tab and one space are one character each, so the margin is 1.
        source = "x = <<-EOT\n\ta\n b\n EOT\n"
        self.assertEqual(loads(source, serialization_options=_VALUE)["x"], "a\nb\n")


class TestWhitespaceOnlyLines(TestCase):
    """A line that offers no measurement is not trimmed by one either."""

    def test_a_whitespace_line_keeps_its_whitespace(self):
        source = "x = <<-EOT\n    a\n      \n    b\n    EOT\n"
        self.assertEqual(loads(source, serialization_options=_VALUE)["x"], "a\n      \nb\n")

    def test_a_blank_line_does_not_cancel_the_dedent(self):
        source = "x = <<-EOT\n  a\n\n  b\n  EOT\n"
        self.assertEqual(loads(source, serialization_options=_VALUE)["x"], "a\n\nb\n")


class TestQuotedSourceFormAgrees(TestCase):
    """Without `strip_string_quotes` the result is source for the same value."""

    _SOURCE = SerializationOptions(preserve_heredocs=False)

    def test_quoted_form_carries_the_trailing_newline(self):
        result = loads("x = <<EOT\nline\nEOT\n", serialization_options=self._SOURCE)["x"]
        self.assertEqual(result, '"line' + chr(92) + 'n"')

    def test_the_two_forms_describe_the_same_string(self):
        source = "x = <<-EOT\n  a\n    b\n  EOT\n"
        value = loads(source, serialization_options=_VALUE)["x"]
        quoted = loads(source, serialization_options=self._SOURCE)["x"]
        # Re-read the quoted form as HCL and it yields the value back.
        reread = loads(f"x = {quoted}\n", serialization_options=_VALUE)["x"]
        self.assertEqual(reread, value)
