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

    def test_a_trimmed_heredoc_in_an_object(self):
        # The deserializer names this token `HEREDOC_TRIM_TEMPLATE` while the
        # grammar calls it `HEREDOC_TEMPLATE_TRIM`; both have to count.
        written = dumps({"x": {"j": '"<<-EOT\n  bar\n  EOT"'}})
        self.assertNotIn("EOT,", written)
        loads(written)

    def test_a_trimmed_heredoc_in_a_list(self):
        written = dumps({"x": ['"<<-EOT\n  bar\n  EOT"', '"p"']})
        self.assertNotIn("EOT,", written)
        loads(written)

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


class TestAHeredocInsideAnExpressionStaysAHeredoc(TestCase):
    """A heredoc written as an argument is expression source, and stays one.

    It used to come back quoted, markers and all -- `${upper("<<EOF\\nfoo\\nEOF")}`
    -- which `dumps` writes as a multi-line quoted string: OpenTofu v1.12.6
    rejects that with "Invalid multi-line string", and it is a different value
    besides. Handing the heredoc back as written needs it to keep the newline
    after its closing marker, so the `)` that follows starts the next line;
    that is the same rule the rest of this module is about.
    """

    CASES = (
        ("x = upper(<<EOF\nfoo\nEOF\n)\n", "${upper(<<EOF\nfoo\nEOF\n)}"),
        ("x = trimspace(<<EOF\nEOF\n)\n", "${trimspace(<<EOF\nEOF\n)}"),
        ("x = upper(<<-E\n  a\n  E\n)\n", "${upper(<<-E\n  a\n  E\n)}"),
        ('x = join(<<A\nx\nA\n, ["y"])\n', '${join(<<A\nx\nA\n, ["y"])}'),
    )

    def test_the_serialized_form_is_the_heredoc(self):
        for source, expected in self.CASES:
            with self.subTest(source=source):
                self.assertEqual(loads(source)["x"], expected)

    def test_the_value_form_is_the_same_source(self):
        # Inside an expression the text is source either way.
        value = SerializationOptions(strip_string_quotes=True)
        for source, expected in self.CASES:
            with self.subTest(source=source):
                self.assertEqual(loads(source, serialization_options=value)["x"], expected)

    def test_the_round_trip_reads_back_the_same(self):
        # `dumps` lays a tuple out one element per line, so compare what the
        # written file reads back as rather than its bytes.
        for source, _ in self.CASES:
            with self.subTest(source=source):
                self.assertEqual(loads(dumps(loads(source))), loads(source))

    def test_a_lone_argument_is_written_back_byte_for_byte(self):
        for source, _ in self.CASES[:3]:
            with self.subTest(source=source):
                self.assertEqual(dumps(loads(source)), source)

    def test_a_heredoc_that_is_the_whole_value_is_unchanged(self):
        self.assertEqual(loads("x = <<EOF\nfoo\nEOF\n")["x"], '"<<EOF\nfoo\nEOF"')


class TestAHeredocTokenHasOneShape(TestCase):
    """A heredoc built from a dict is the same token a parsed one is.

    The deserializer used to build its own terminal name for `<<-` and drop
    the newline after the closing marker, so everything downstream needed a
    case for each shape -- and the ones that lacked it put a separator on the
    marker's line. Now both carry the grammar's name and end their line.
    """

    def test_a_built_trimmed_token_is_the_parsed_class(self):
        from hcl2.api import from_dict, parses  # pylint: disable=import-outside-toplevel
        from hcl2.rules.tokens import HEREDOC_TRIM_TEMPLATE  # pylint: disable=import-outside-toplevel
        from hcl2.walk import walk  # pylint: disable=import-outside-toplevel

        def heredoc_token(tree):
            return next(n for n in walk(tree) if isinstance(n, HEREDOC_TRIM_TEMPLATE))

        built = heredoc_token(from_dict({"a": '"<<-E\n  x\n  E"'}))
        parsed = heredoc_token(parses("a = <<-E\n  x\n  E\n"))
        self.assertIs(type(built), type(parsed))
        self.assertTrue(str(built.value).endswith("\n"))


class TestAHeredocInAnObjectEndsTheItem(TestCase):
    """In an object the line break separates items; a comma there is rejected.

    OpenTofu v1.12.6 rejects `{\\n  a = <<EOF\\nfoo\\nEOF\\n,\\n  b = 1\\n}` with
    "Invalid expression", and accepts it without the comma. A tuple takes the
    comma, so only objects drop it.
    """

    def test_an_object_attribute(self):
        written = dumps(loads("x = {\n  a = <<EOF\nfoo\nEOF\n  b = 1\n}\n"))
        self.assertEqual(written, "x = {\n  a = <<EOF\nfoo\nEOF\n  b = 1,\n}\n")

    def test_strings_to_heredocs_in_an_object(self):
        written = dumps({"x": {"a": '"foo\\n"', "b": 1}}, deserializer_options=HEREDOCS)
        self.assertEqual(written, "x = {\n  a = <<EOF\nfoo\nEOF\n  b = 1,\n}\n")

    def test_the_inline_form_inside_a_call(self):
        loaded = loads("x = merge({\n  a = <<EOF\nfoo\nEOF\n  b = 1\n}, {})\n")
        self.assertEqual(loaded["x"], "${merge({a = <<EOF\nfoo\nEOF\nb = 1}, {})}")
        self.assertEqual(dumps(loaded), "x = merge({\n  a = <<EOF\nfoo\nEOF\n  b = 1\n}, {})\n")

    def test_wrapped_objects_and_tuples_built_from_a_dict(self):
        from hcl2.api import from_dict, serialize  # pylint: disable=import-outside-toplevel

        objects = serialize(
            from_dict({"x": {"k": '"<<EOF\nbar\nEOF"', "j": 1}}),
            serialization_options=SerializationOptions(wrap_objects=True),
        )
        self.assertEqual(objects["x"], "${{k = <<EOF\nbar\nEOF\nj = 1}}")
        tuples = serialize(
            from_dict({"x": ['"<<EOF\nfoo\nEOF"', '"b"']}),
            serialization_options=SerializationOptions(wrap_tuples=True),
        )
        self.assertEqual(tuples["x"], '${[<<EOF\nfoo\nEOF\n, "b"]}')
        value = SerializationOptions(strip_string_quotes=True, preserve_heredocs=False)
        self.assertEqual(loads(dumps(objects), serialization_options=value)["x"], {"k": "bar\n", "j": 1})
        self.assertEqual(loads(dumps(tuples), serialization_options=value)["x"], ["foo\n", "b"])
