# pylint: disable=C0103,C0114,C0115,C0116
"""Regression tests for GH issue #316: heredoc bodies are right-stripped of
*all* trailing newlines, tabs and spaces, so distinct sources collapse to
the same flattened value.

HeredocTemplateRule.serialize's preserve_heredocs=False path did
match.group(2).rstrip("\n\t "), which removes every trailing character in
that set -- not just the single newline that separates the last body line
from the closing marker. A trailing blank line, multiple trailing blank
lines, and trailing spaces on the last line all collapsed to the same
value as a plain one-line body.

This is scoped to the plain <<MARKER heredoc only (all of the issue's
reproduction cases use it); the indented <<-MARKER variant has separate,
pre-existing leading-whitespace-trim semantics and its golden tests are
unaffected by this fix.

Note: expected values below are built with BS (a literal backslash
character, via chr(92)) rather than hand-written "\\n" escapes, to avoid
any ambiguity between "a literal backslash followed by n" and "a real
newline character" when this file is read back in by Python.
"""
from unittest import TestCase

from hcl2.api import loads
from hcl2.utils import SerializationOptions

_FLATTEN = SerializationOptions(preserve_heredocs=False)
BS = chr(92)  # a single literal backslash character


class TestHeredocTrailingWhitespace(TestCase):
    def test_trailing_blank_line_preserved(self):
        src = "a = <<MARKER" + chr(10) + "x" + chr(10) + chr(10) + "MARKER" + chr(10)
        result = loads(src, serialization_options=_FLATTEN)
        expected = '"x' + BS + 'n"'
        self.assertEqual(result["a"], expected)

    def test_two_trailing_blank_lines_preserved(self):
        src = "a = <<MARKER" + chr(10) + "x" + chr(10) * 3 + "MARKER" + chr(10)
        result = loads(src, serialization_options=_FLATTEN)
        expected = '"x' + BS + 'n' + BS + 'n"'
        self.assertEqual(result["a"], expected)

    def test_trailing_spaces_preserved(self):
        src = "a = <<MARKER" + chr(10) + "x   " + chr(10) + "MARKER" + chr(10)
        result = loads(src, serialization_options=_FLATTEN)
        self.assertEqual(result["a"], '"x   "')

    def test_three_distinct_sources_no_longer_collapse(self):
        blank_line = loads(
            "a = <<MARKER" + chr(10) + "x" + chr(10) + chr(10) + "MARKER" + chr(10),
            serialization_options=_FLATTEN,
        )["a"]
        two_blank = loads(
            "a = <<MARKER" + chr(10) + "x" + chr(10) * 3 + "MARKER" + chr(10),
            serialization_options=_FLATTEN,
        )["a"]
        trailing_spaces = loads(
            "a = <<MARKER" + chr(10) + "x   " + chr(10) + "MARKER" + chr(10),
            serialization_options=_FLATTEN,
        )["a"]
        values = {blank_line, two_blank, trailing_spaces}
        self.assertEqual(len(values), 3)

    def test_plain_one_line_heredoc_unaffected(self):
        # The single final newline separating content from the marker line
        # is still dropped -- this is the established, non-regressed
        # behavior (Terraform's own one-liner golden semantics).
        src = "a = <<MARKER" + chr(10) + "x" + chr(10) + "MARKER" + chr(10)
        result = loads(src, serialization_options=_FLATTEN)
        self.assertEqual(result["a"], '"x"')

    def test_interior_blank_line_still_preserved(self):
        src = "a = <<MARKER" + chr(10) + "x" + chr(10) * 2 + "y" + chr(10) + "MARKER" + chr(10)
        result = loads(src, serialization_options=_FLATTEN)
        expected = '"x' + BS + 'n' + BS + 'ny"'
        self.assertEqual(result["a"], expected)
