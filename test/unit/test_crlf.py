# pylint: disable=C0103,C0114,C0115,C0116
r"""Regression tests for GH issue #315: CRLF (\r\n) line endings fail to parse.

`hcl2.lark`'s `%ignore` rule only skipped spaces and tabs, so a bare `\r`
preceding the newline in a CRLF-terminated line had no terminal that could
consume it: `NL_OR_COMMENT` only matches starting from `\n`. The `\r` fell
through to `STRING_CHARS` and the parse failed with `UnexpectedToken`, for
every construct, as soon as a single CRLF line appeared anywhere.

Line endings are handled in three places, so the tests here cross module
boundaries rather than mirroring one: `%ignore` and the heredoc terminals in
`hcl2.lark`, the heredoc patterns in `hcl2/utils.py`, and the trim characters
in `hcl2/rules/strings.py`.
"""

from unittest import TestCase

from hcl2.api import dumps, loads, parses_to_tree, reconstruct, transform
from hcl2.deserializer import DeserializerOptions
from hcl2.utils import SerializationOptions

CR = "\r"


class TestCrlfLineEndings(TestCase):
    """A CRLF source parses to the same dict as its LF equivalent."""

    def test_bare_attribute(self):
        self.assertEqual(loads("a = 1\r\n"), loads("a = 1\n"))

    def test_block(self):
        crlf = loads("locals {\r\n  a = 1\r\n}\r\n")
        lf = loads("locals {\n  a = 1\n}\n")
        self.assertEqual(crlf, lf)

    def test_quoted_string(self):
        crlf = loads('a = "x"\r\n')
        lf = loads('a = "x"\n')
        self.assertEqual(crlf, lf)

    def test_single_crlf_line_amid_lf_lines(self):
        crlf = loads("a = 1\nb = 2\r\nc = 3\n")
        lf = loads("a = 1\nb = 2\nc = 3\n")
        self.assertEqual(crlf, lf)

    def test_tuple_and_object(self):
        crlf = loads("a = [1,\r\n2]\r\nb = {\r\n  x = 1\r\n}\r\n")
        lf = loads("a = [1,\n2]\nb = {\n  x = 1\n}\n")
        self.assertEqual(crlf, lf)

    def test_comments(self):
        for source in ("# hi\r\na = 1\r\n", "// hi\r\na = 1\r\n", "/* hi */\r\na = 1\r\n"):
            with self.subTest(source=source):
                options = SerializationOptions(with_comments=True)
                result = loads(source, serialization_options=options)
                self.assertEqual(result["a"], 1)
                self.assertEqual(result["__comments__"], [{"value": "hi"}])


class TestCrlfDoesNotEatContentCarriageReturns(TestCase):
    r"""Only a `\r` that is insignificant whitespace between tokens is ignored.

    A `\r` inside a terminal's own content belongs to that terminal, which
    matches a longer span from the same position and so wins.
    """

    def test_real_cr_inside_a_quoted_string_survives(self):
        result = loads('a = "x' + CR + 'y"\n')
        self.assertEqual(result, {"a": '"x' + CR + 'y"'})

    def test_string_consisting_only_of_a_cr_survives(self):
        self.assertEqual(loads('a = "' + CR + '"\n'), {"a": '"' + CR + '"'})

    def test_cr_escape_sequence_is_untouched(self):
        r"""`\r` as escape *text* is two ASCII characters, never at risk."""
        self.assertEqual(loads(r'a = "line1\r\nline2"' + "\n"), {"a": r'"line1\r\nline2"'})

    def test_heredoc_body_keeps_its_carriage_returns(self):
        r"""HCL treats `\r` around markers as structure but body text as content."""
        result = loads("a = <<EOF\r\nx\r\ny\r\nEOF\r\n")
        self.assertEqual(result, {"a": '"<<EOF' + CR + "\nx" + CR + "\ny" + CR + '\nEOF"'})


class TestCrlfHeredocs(TestCase):
    r"""Heredocs need `\r?` in their own terminals; `%ignore` cannot reach inside.

    HCL's reference scanner handles both `\n` and `\r\n` around heredoc markers,
    so a CRLF heredoc is valid input rather than something to reject.
    """

    def test_heredoc_parses(self):
        result = loads("a = <<EOF\r\nx\r\nEOF\r\n")
        self.assertEqual(result, {"a": '"<<EOF' + CR + "\nx" + CR + '\nEOF"'})

    def test_trimmed_heredoc_parses(self):
        result = loads("a = <<-EOF\r\n  x\r\n  EOF\r\n")
        self.assertEqual(result, {"a": '"<<-EOF' + CR + "\n  x" + CR + '\n  EOF"'})

    def test_heredoc_does_not_swallow_the_following_attribute(self):
        result = loads("a = <<EOF\r\nx\r\nEOF\r\nb = 1\r\n")
        self.assertEqual(result["b"], 1)

    def test_closing_marker_leaves_no_trailing_carriage_return(self):
        r"""`_trim_chars` covers `\r`, so the preserved form ends at the marker."""
        result = loads("a = <<EOF\r\nx\r\nEOF\r\n")
        self.assertTrue(result["a"].endswith('EOF"'), result["a"])

    def test_flattening_a_crlf_heredoc_does_not_raise(self):
        r"""The heredoc patterns in utils.py run on an already-parsed token.

        Every body line keeps its own `\r\n`, the last one included: OpenTofu
        evaluates this source to `"x\r\ny\r\n"`. Both characters are written
        escaped, because this form is quoted-string *source* -- see
        `TestFlattenedCrlfHeredocsStayValidHcl`.
        """
        options = SerializationOptions(preserve_heredocs=False)
        result = loads("a = <<EOF\r\nx\r\ny\r\nEOF\r\n", serialization_options=options)
        self.assertEqual(result, {"a": r'"x\r\ny\r\n"'})

    def test_trimmed_heredoc_flattens(self):
        options = SerializationOptions(preserve_heredocs=False)
        result = loads("a = <<-EOF\r\n  x\r\n  EOF\r\n", serialization_options=options)
        self.assertEqual(result, {"a": r'"x\r\n"'})


class TestCrlfReconstruction(TestCase):
    r"""CRLF input reconstructs as LF, because the `\r` never enters the IR."""

    def test_crlf_normalises_to_lf(self):
        source = "a = 1\r\nb = 2\r\n"
        output = reconstruct(transform(parses_to_tree(source)).to_lark())
        self.assertEqual(output, "a = 1\nb = 2\n")

    def test_lf_is_unchanged(self):
        source = "a = 1\nb = 2\n"
        output = reconstruct(transform(parses_to_tree(source)).to_lark())
        self.assertEqual(output, source)


class TestFlattenedCrlfHeredocsStayValidHcl(TestCase):
    r"""`preserve_heredocs=False` writes a quoted string, which cannot hold a CR.

    The flattened form is source, not a value: it is the string another parser
    -- or this one, on the next pass -- has to read back. A raw carriage return
    inside quotes is not valid there. OpenTofu rejects `"a<CR>b"` with "No
    closing marker was found for the string", while `"a\rb"` evaluates to a
    carriage return, which is what the heredoc body actually held.

    The value form is unaffected: it hands back the body, so its newlines and
    carriage returns stay real characters.
    """

    FLAT = SerializationOptions(preserve_heredocs=False)
    VALUE = SerializationOptions(preserve_heredocs=False, strip_string_quotes=True)

    def test_heredoc_source_form_escapes_carriage_returns(self):
        source = loads("a = <<EOF\r\nx\r\ny\r\nEOF\r\n", serialization_options=self.FLAT)["a"]
        self.assertNotIn(CR, source)
        self.assertEqual(source, r'"x\r\ny\r\n"')

    def test_trim_heredoc_source_form_escapes_carriage_returns(self):
        source = loads("a = <<-EOF\r\n  x\r\n  y\r\nEOF\r\n", serialization_options=self.FLAT)["a"]
        self.assertNotIn(CR, source)
        self.assertEqual(source, r'"x\r\ny\r\n"')

    def test_value_form_keeps_real_carriage_returns(self):
        value = loads("a = <<EOF\r\nx\r\ny\r\nEOF\r\n", serialization_options=self.VALUE)["a"]
        self.assertEqual(value, "x\r\ny\r\n")

    def test_a_lone_cr_inside_a_line_is_escaped_too(self):
        # Not a line ending: a carriage return the body carries mid-line.
        source = loads("a = <<EOF\nx\ry\nEOF\n", serialization_options=self.FLAT)["a"]
        self.assertEqual(source, r'"x\ry\n"')


class TestCrlfSurvivesFlattenAndRestore(TestCase):
    r"""Flattening a CRLF heredoc and writing it back preserves the value.

    The two halves have to be each other's inverse. The flattened form writes
    a carriage return as `\r`, because it is quoted-string source; the writer
    then has to resolve `\r` back into the character, because a heredoc
    interprets no escape at all -- a body holding a backslash and an `r` is
    those two characters, and OpenTofu reads it that way.

    The target value is not this implementation's opinion: OpenTofu evaluates
    a CRLF file containing `<<EOF\r\nx\r\ny\r\nEOF\r\n` to `"x\r\ny\r\n"`,
    checked with `tofu console` against v1.12.5.

    Each half was already covered on its own -- flattening a CRLF heredoc, and
    restoring an LF string -- which is exactly why the combination could break
    without a test noticing.
    """

    FLAT = SerializationOptions(preserve_heredocs=False)
    VALUE = SerializationOptions(preserve_heredocs=False, strip_string_quotes=True)
    HEREDOCS = DeserializerOptions(strings_to_heredocs=True)

    def _restore(self, source: str) -> str:
        flattened = loads(source, serialization_options=self.FLAT)
        return dumps(flattened, deserializer_options=self.HEREDOCS)

    def _round_trip(self, source: str) -> str:
        restored = self._restore(source)
        return loads(restored, serialization_options=self.VALUE)["a"]

    def test_the_value_is_unchanged(self):
        self.assertEqual(self._round_trip("a = <<EOF\r\nx\r\ny\r\nEOF\r\n"), "x\r\ny\r\n")

    def test_the_written_body_holds_real_carriage_returns(self):
        restored = self._restore("a = <<EOF\r\nx\r\ny\r\nEOF\r\n")
        self.assertNotIn("\\r", restored)
        self.assertEqual(restored, "a = <<EOF\nx\r\ny\r\nEOF\n")

    def test_a_trimmed_heredoc_survives_too(self):
        self.assertEqual(self._round_trip("a = <<-EOF\r\n  x\r\n  y\r\nEOF\r\n"), "x\r\ny\r\n")

    def test_a_lone_carriage_return_keeps_the_value_quoted(self):
        r"""A heredoc body cannot hold a `\r` that does not end a line.

        OpenTofu rejects `<<EOF\nx\ry\nEOF` with "No closing marker was
        found for the string", while the quoted `"x\ry\n"` it came from is
        valid and evaluates to that carriage return. Writing the heredoc
        anyway traded a wrong value for an unreadable file; the value stays
        quoted instead, as one that does not end in a newline does.
        """
        source = "a = <<EOF\nx\ry\nEOF\n"
        restored = self._restore(source)
        self.assertEqual(restored, 'a = "x\\ry\\n"\n')
        self.assertEqual(self._round_trip(source), "x\ry\n")

    def test_a_crlf_body_carrying_the_delimiter_gets_another_one(self):
        r"""`EOF\r` ends a heredoc in Terraform, so it counts when choosing.

        The body is split on `\n`, so a CRLF line hands back its own `\r`
        and a marker check that only allowed spaces and tabs never saw it.
        OpenTofu evaluates `<<EOF\nbody\r\nEOF\r\n` to `"body\r\n"` --
        it ends there -- so writing `<<EOF` over a CRLF body containing that
        line produced a file that closed early and no longer parsed.
        """
        # Such a body cannot be written as a heredoc source to read from --
        # this parser ends it at that line too, as Terraform does -- so the
        # value arrives the way it would in practice, from a quoted string.
        quoted = r'"x\r\nEOF\r\ny\r\n"'
        written = dumps({"a": quoted}, deserializer_options=self.HEREDOCS)
        self.assertEqual(written, "a = <<EOF_1\nx\r\nEOF\r\ny\r\nEOF_1\n")
        self.assertEqual(loads(written, serialization_options=self.VALUE)["a"], "x\r\nEOF\r\ny\r\n")
