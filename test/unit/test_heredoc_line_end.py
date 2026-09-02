# pylint: disable=C0103,C0114,C0115,C0116
r"""A heredoc ends its own line, wherever it is written (GH #338).

A heredoc ends at its closing marker, on a line of its own, so whatever comes
next has to start the following line. Inside a list or an object that is the
separator, and `EOF,` closes nothing: the file this library had just written
did not parse, here or in Terraform.

A top-level attribute survived only because the newline after it comes from
the document rather than from the heredoc.

The distinction the fix turns on: `HEREDOC_TEMPLATE` matches through the
newline after the marker, so a token that came from the parser already ends
the line. One built by the deserializer does not, and that is the only case
that needs help -- which is why reconstructing a parsed document is byte for
byte what it was.

Checked against OpenTofu v1.12.5: the emitted list reads back as
`["line1\n", "p"]`.
"""

from unittest import TestCase

from hcl2.api import dumps, loads
from hcl2.deserializer import DeserializerOptions
from hcl2.utils import SerializationOptions

HEREDOCS = DeserializerOptions(strings_to_heredocs=True)
FLAT = SerializationOptions(preserve_heredocs=False)


class TestAHeredocInAContainer(TestCase):
    def _restore(self, source: str) -> str:
        return dumps(loads(source, serialization_options=FLAT), deserializer_options=HEREDOCS)

    def test_in_a_list(self):
        written = self._restore('a = [<<EOT\nline1\nEOT\n, "p"]\n')
        self.assertNotIn("EOF,", written)
        loads(written)

    def test_in_an_object(self):
        written = self._restore("a = { k = <<EOT\nline1\nEOT\n }\n")
        self.assertNotIn("EOF,", written)
        loads(written)

    def test_as_the_only_element(self):
        written = self._restore("a = [<<EOT\nline1\nEOT\n]\n")
        loads(written)

    def test_two_of_them(self):
        written = self._restore("a = [<<EOT\none\nEOT\n, <<EOT\ntwo\nEOT\n]\n")
        loads(written)

    def test_the_values_survive(self):
        source = 'a = [<<EOT\nline1\nEOT\n, "p"]\n'
        restored = self._restore(source)
        self.assertEqual(
            loads(restored, serialization_options=FLAT), loads(source, serialization_options=FLAT)
        )

    def test_a_top_level_attribute_still_works(self):
        written = self._restore("a = <<EOT\nline1\nEOT\n")
        self.assertEqual(written, "a = <<EOF\nline1\nEOF\n")


class TestReconstructionIsUnchanged(TestCase):
    """A parsed heredoc carries its own newline, so nothing is added to it."""

    def test_a_document_round_trips_byte_for_byte(self):
        for source in (
            "locals {\n  a = <<EOT\n  x\n  EOT\n}\n",
            "a = <<EOT\nx\nEOT\n",
            "a = <<-EOT\n  x\n  EOT\n",
            'locals {\n  a = <<EOT\n  x\n  EOT\n  b = "y"\n}\n',
        ):
            with self.subTest(source=source):
                self.assertEqual(dumps(loads(source)), source)
