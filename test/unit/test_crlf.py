# pylint: disable=C0103,C0114,C0115,C0116
"""Regression tests for GH issue #315: CRLF (\r\n) line endings fail to parse.

hcl2/hcl2.lark's %ignore rule only skipped spaces and tabs, so a bare '\r'
preceding the newline in a CRLF-terminated line had no terminal that could
consume it: NL_OR_COMMENT only matches starting from '\n', and the ignore
rule didn't cover '\r'. The '\r' fell through to STRING_CHARS and the parse
failed with lark.exceptions.UnexpectedToken, for every construct (bare
attributes, blocks, quoted strings) as soon as a single CRLF line appeared
anywhere in the source.
"""
from unittest import TestCase

from hcl2.api import loads


class TestCrlfLineEndings(TestCase):
    def test_bare_attribute(self):
        self.assertEqual(loads("a = 1\r\n"), loads("a = 1\n"))

    def test_block(self):
        crlf = loads('locals {\r\n  a = 1\r\n}\r\n')
        lf = loads('locals {\n  a = 1\n}\n')
        self.assertEqual(crlf, lf)

    def test_quoted_string(self):
        crlf = loads('a = "x"\r\n')
        lf = loads('a = "x"\n')
        self.assertEqual(crlf, lf)

    def test_single_crlf_line_amid_lf_lines(self):
        crlf = loads("a = 1\nb = 2\r\nc = 3\n")
        lf = loads("a = 1\nb = 2\nc = 3\n")
        self.assertEqual(crlf, lf)

    def test_embedded_cr_inside_string_is_preserved(self):
        # A \r that is part of an in-string escape sequence (not a line
        # ending) must survive untouched -- the fix must not eat CR
        # unconditionally, only when it is insignificant whitespace between
        # tokens.
        result = loads('a = "line1\\r\\nline2"\n')
        self.assertIn("line1", result["a"])
        self.assertIn("\\r\\n", result["a"])
