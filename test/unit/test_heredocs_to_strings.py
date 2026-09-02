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
