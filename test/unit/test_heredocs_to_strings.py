# pylint: disable=C0103,C0114,C0115,C0116
r"""`heredocs_to_strings` writes a value, not the heredoc's own text (GH #337).

The option converts a heredoc into a quoted string. It was quoting the
heredoc's *source* -- markers and all -- across as many physical lines as the
original occupied:

    a = "<<EOT
    hello
    EOT"

A quoted template cannot span lines, so OpenTofu rejects that with "Invalid
multi-line string", and reading it back here gave the marker text rather than
the value. Neither a valid file nor the right content.

The flattening the reader already performs is reused rather than written a
second time, so the two cannot drift.
"""

from unittest import TestCase

from hcl2.api import dumps, loads
from hcl2.deserializer import DeserializerOptions

STRINGS = DeserializerOptions(heredocs_to_strings=True)


class TestTheOutputIsAQuotedValue(TestCase):
    def _convert(self, source: str) -> str:
        return dumps(loads(source), deserializer_options=STRINGS)

    def test_a_plain_heredoc(self):
        self.assertEqual(self._convert("a = <<EOT\nhello\nEOT\n"), 'a = "hello"\n')

    def test_a_trimmed_heredoc(self):
        self.assertEqual(self._convert("a = <<-EOT\n  indented\n  EOT\n"), 'a = "indented"\n')

    def test_quotes_in_the_body_are_escaped(self):
        self.assertEqual(self._convert('a = <<EOT\nsay "hi"\nEOT\n'), 'a = "say \\"hi\\""\n')

    def test_the_result_is_one_line(self):
        for source in ("a = <<EOT\nhello\nEOT\n", "a = <<EOT\none\ntwo\nEOT\n"):
            with self.subTest(source=source):
                written = self._convert(source)
                self.assertEqual(written.count("\n"), 1, written)

    def test_the_result_parses_again(self):
        for source in (
            "a = <<EOT\nhello\nEOT\n",
            'a = <<EOT\nsay "hi"\nEOT\n',
            "a = <<EOT\none\ntwo\nEOT\n",
            "a = <<-EOT\n  indented\n  EOT\n",
        ):
            with self.subTest(source=source):
                loads(self._convert(source))

    def test_no_marker_survives_into_the_output(self):
        written = self._convert("a = <<EOT\nhello\nEOT\n")
        self.assertNotIn("EOT", written)
        self.assertNotIn("<<", written)


class TestTheOptionOffIsUnchanged(TestCase):
    def test_a_heredoc_stays_a_heredoc(self):
        source = "a = <<EOT\nhello\nEOT\n"
        self.assertEqual(dumps(loads(source)), source)

    def test_a_plain_string_is_unaffected_either_way(self):
        source = 'a = "hello"\n'
        self.assertEqual(dumps(loads(source), deserializer_options=STRINGS), source)
        self.assertEqual(dumps(loads(source)), source)


class TestAMultiLineInterpolationKeepsTheHeredoc(TestCase):
    """A heredoc whose `${...}` spans lines has no quoted spelling.

    The newlines inside the span are expression source: escaped, OpenTofu
    rejects them as "not used within the language", and raw, they make the
    quoted string span lines. Flattening one raised `UnexpectedToken` out of
    `dumps`. It is written back as the heredoc it was, which is the only answer
    that keeps the file readable and the value unchanged.
    """

    OPTIONS = DeserializerOptions(heredocs_to_strings=True)

    def test_both_forms_are_kept(self):
        for source in (
            "x = <<EOF\na ${\n  b\n} c\nEOF\n",
            "x = <<-EOF\n  a ${\n    b\n  } c\n  EOF\n",
            "x = <<EOF\n%{ if\n  true }y%{ endif }\nEOF\n",
        ):
            with self.subTest(source=source):
                self.assertEqual(dumps(loads(source), deserializer_options=self.OPTIONS), source)

    def test_a_one_line_interpolation_is_still_flattened(self):
        written = dumps(loads("x = <<EOF\na ${b} c\nEOF\n"), deserializer_options=self.OPTIONS)
        self.assertTrue(written.startswith('x = "a ${b} c'), written)

    def test_a_brace_in_a_string_inside_the_span_does_not_end_it(self):
        source = 'x = <<EOF\na ${f("}",\n  b)} c\nEOF\n'
        self.assertEqual(dumps(loads(source), deserializer_options=self.OPTIONS), source)


class TestACommentInsideTheSpanDoesNotEndIt(TestCase):
    """A brace inside a comment in `${...}` is not structural.

    OpenTofu v1.12.6 evaluates each of these to `a 3 b\\n`: the `}` in the
    comment does not close the expression, so the newline after it is still
    expression source and the heredoc has no quoted spelling.
    """

    OPTIONS = DeserializerOptions(heredocs_to_strings=True)

    def test_each_comment_form(self):
        for source in (
            "x = <<EOF\na ${1 /* } */\n+ 2} b\nEOF\n",
            "x = <<EOF\na ${1 # }\n+ 2} b\nEOF\n",
            "x = <<EOF\na ${1 // }\n+ 2} b\nEOF\n",
            "x = <<-EOF\n  a ${1 /* } */\n  + 2} b\n  EOF\n",
        ):
            with self.subTest(source=source):
                self.assertEqual(dumps(loads(source), deserializer_options=self.OPTIONS), source)


class TestAStripMarkerKeepsTheHeredoc(TestCase):
    """`~` strips whitespace up to the line's end in a heredoc, and further in a string.

    A heredoc body is lexed a line at a time, so a `~}` there strips only to
    the end of its own line; in a quoted string the same marker strips across
    the newline and the next line's indent. OpenTofu v1.12.6 evaluates the
    loop below to `items:\\n  - a\\n  - b\\n`, and its flattened form to the
    same list without the indent. No quoted spelling keeps the value, so the
    heredoc stays one.
    """

    OPTIONS = DeserializerOptions(heredocs_to_strings=True)

    def test_each_marker_keeps_the_heredoc(self):
        for source in (
            'x = <<EOF\nitems:\n%{ for s in ["a", "b"] ~}\n  - ${s}\n%{ endfor ~}\nEOF\n',
            "x = <<EOF\na\n${~ b}\nEOF\n",
            "x = <<EOF\na\n%{~ if true }y%{ endif }\nEOF\n",
        ):
            with self.subTest(source=source):
                self.assertEqual(dumps(loads(source), deserializer_options=self.OPTIONS), source)

    def test_a_tilde_in_the_text_is_not_a_marker(self):
        written = dumps(loads("x = <<EOF\na ~ b ${c}\nEOF\n"), deserializer_options=self.OPTIONS)
        self.assertTrue(written.startswith('x = "a ~ b ${c}'), written)
