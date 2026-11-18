# pylint: disable=C0103,C0114,C0115,C0116
r"""Regression tests for GH issue #316: heredoc bodies are right-stripped of
*all* trailing newlines, tabs and spaces, so distinct sources collapse to
the same flattened value.

Both heredoc rules flattened their body with `rstrip("\n\t ")`, which removes
every trailing character in that set -- not just the single newline separating
the last body line from the closing marker. A trailing blank line, multiple
trailing blank lines, and trailing spaces on the last line all collapsed to
the same value as a plain one-line body.

The blanket rstrip was doing two jobs at once: dropping that separating
newline, and dropping the closing marker line's own indentation. Splitting
them (`_strip_closing_marker_indent`) is what lets body content survive while
the marker line still disappears, and it applies to `<<MARKER` and
`<<-MARKER` alike.

Every body below ends in a newline, because the last content line is
terminated by its own newline just like the others -- see
`test_heredoc_matches_terraform.py`, which checks each case against OpenTofu.

Note: expected values below are built with NL, a literal backslash (chr(92))
followed by "n", rather than hand-written escapes, to avoid any ambiguity
between "a literal backslash followed by n" and "a real newline character".
"""

from unittest import TestCase

from hcl2.api import loads
from hcl2.utils import SerializationOptions

_FLATTEN = SerializationOptions(preserve_heredocs=False)
NL = chr(92) + "n"  # an escaped newline, as it appears in the quoted form


class TestHeredocTrailingWhitespace(TestCase):
    def test_trailing_blank_line_preserved(self):
        src = "a = <<MARKER" + chr(10) + "x" + chr(10) + chr(10) + "MARKER" + chr(10)
        result = loads(src, serialization_options=_FLATTEN)
        expected = '"x' + NL + NL + '"'
        self.assertEqual(result["a"], expected)

    def test_two_trailing_blank_lines_preserved(self):
        src = "a = <<MARKER" + chr(10) + "x" + chr(10) * 3 + "MARKER" + chr(10)
        result = loads(src, serialization_options=_FLATTEN)
        expected = '"x' + NL * 3 + '"'
        self.assertEqual(result["a"], expected)

    def test_trailing_spaces_preserved(self):
        src = "a = <<MARKER" + chr(10) + "x   " + chr(10) + "MARKER" + chr(10)
        result = loads(src, serialization_options=_FLATTEN)
        self.assertEqual(result["a"], '"x   ' + NL + '"')

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

    def test_plain_one_line_heredoc_keeps_its_newline(self):
        # The one content line is terminated by its own newline, so the value
        # is "x\n". Both this library and 7.2.1 used to return "x"; OpenTofu
        # evaluates the same source to "x\n".
        src = "a = <<MARKER" + chr(10) + "x" + chr(10) + "MARKER" + chr(10)
        result = loads(src, serialization_options=_FLATTEN)
        self.assertEqual(result["a"], '"x' + NL + '"')

    def test_interior_blank_line_still_preserved(self):
        src = "a = <<MARKER" + chr(10) + "x" + chr(10) * 2 + "y" + chr(10) + "MARKER" + chr(10)
        result = loads(src, serialization_options=_FLATTEN)
        expected = '"x' + NL + NL + "y" + NL + '"'
        self.assertEqual(result["a"], expected)


class TestHeredocIndentedClosingMarker(TestCase):
    """The closing marker's own indentation is not body content.

    The grammar allows whitespace before the closing marker, and the spec says
    it "may also have an arbitrary number of spaces preceding it on its line".
    That indentation goes; the newline before it stays, being the last content
    line's own terminator.
    """

    def test_space_indented_marker(self):
        src = "a = <<MARKER" + chr(10) + "x" + chr(10) + "   MARKER" + chr(10)
        self.assertEqual(loads(src, serialization_options=_FLATTEN)["a"], '"x' + NL + '"')

    def test_tab_indented_marker(self):
        src = "a = <<MARKER" + chr(10) + "x" + chr(10) + chr(9) + "MARKER" + chr(10)
        self.assertEqual(loads(src, serialization_options=_FLATTEN)["a"], '"x' + NL + '"')

    def test_indented_marker_after_a_blank_line(self):
        src = "a = <<MARKER" + chr(10) + "x" + chr(10) * 2 + "   MARKER" + chr(10)
        self.assertEqual(loads(src, serialization_options=_FLATTEN)["a"], '"x' + NL + NL + '"')

    def test_content_trailing_spaces_survive_an_indented_marker(self):
        """The content line ends with its own newline, so its spaces are safe."""
        src = "a = <<MARKER" + chr(10) + "x   " + chr(10) + "   MARKER" + chr(10)
        self.assertEqual(loads(src, serialization_options=_FLATTEN)["a"], '"x   ' + NL + '"')


class TestTrimmedHeredocTrailingWhitespace(TestCase):
    """`<<-MARKER` loses the same content, and needs the same fix.

    Its `rstrip` removed the marker line's indentation as well as the trailing
    newline, which is why replacing it naively breaks the dedent. Splitting the
    two concerns handles both.
    """

    def test_trailing_blank_line_preserved(self):
        src = "a = <<-MARKER" + chr(10) + "  x" + chr(10) * 2 + "  MARKER" + chr(10)
        self.assertEqual(loads(src, serialization_options=_FLATTEN)["a"], '"x' + NL + NL + '"')

    def test_two_trailing_blank_lines_preserved(self):
        src = "a = <<-MARKER" + chr(10) + "  x" + chr(10) * 3 + "  MARKER" + chr(10)
        expected = '"x' + NL * 3 + '"'
        self.assertEqual(loads(src, serialization_options=_FLATTEN)["a"], expected)

    def test_trailing_spaces_preserved(self):
        src = "a = <<-MARKER" + chr(10) + "  x   " + chr(10) + "  MARKER" + chr(10)
        self.assertEqual(loads(src, serialization_options=_FLATTEN)["a"], '"x   ' + NL + '"')

    def test_dedent_still_applies(self):
        src = "a = <<-MARKER" + chr(10) + "  x" + chr(10) + "  y" + chr(10) + "  MARKER" + chr(10)
        self.assertEqual(loads(src, serialization_options=_FLATTEN)["a"], '"x' + NL + "y" + NL + '"')

    def test_uneven_dedent_keeps_relative_indentation(self):
        src = "a = <<-MARKER" + chr(10) + "  x" + chr(10) + "    y" + chr(10) + "  MARKER" + chr(10)
        expected = '"x' + NL + "  y" + NL + '"'
        self.assertEqual(loads(src, serialization_options=_FLATTEN)["a"], expected)

    def test_blank_line_does_not_cancel_the_dedent(self):
        """A blank line has no leading string to measure, so it must not count."""
        src = "a = <<-MARKER" + chr(10) + "  x" + chr(10) * 2 + "  y" + chr(10) + "  MARKER" + chr(10)
        expected = '"x' + NL + NL + "y" + NL + '"'
        self.assertEqual(loads(src, serialization_options=_FLATTEN)["a"], expected)
