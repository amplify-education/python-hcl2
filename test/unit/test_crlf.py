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

from hcl2.api import loads, parses_to_tree, reconstruct, transform
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
        """The heredoc patterns in utils.py run on an already-parsed token.

        Every body line keeps its own `\\r\\n`, the last one included: OpenTofu
        evaluates this source to `"x\\r\\ny\\r\\n"`.
        """
        options = SerializationOptions(preserve_heredocs=False)
        result = loads("a = <<EOF\r\nx\r\ny\r\nEOF\r\n", serialization_options=options)
        self.assertEqual(result, {"a": '"x' + CR + "\\ny" + CR + '\\n"'})

    def test_trimmed_heredoc_flattens(self):
        options = SerializationOptions(preserve_heredocs=False)
        result = loads("a = <<-EOF\r\n  x\r\n  EOF\r\n", serialization_options=options)
        self.assertEqual(result, {"a": '"x' + CR + '\\n"'})


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
