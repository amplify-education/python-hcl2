# pylint: disable=C0103,C0114,C0115,C0116
"""Unit tests for hcl2.postlexer.

Tests parse real HCL2 snippets through the full pipeline to verify that the
postlexer correctly handles newlines before binary operators and QMARK.
"""

from unittest import TestCase

from lark import Token

from hcl2.api import loads
from hcl2.postlexer import OPERATOR_TYPES, PostLexer


class TestMergeNewlinesIntoOperators(TestCase):
    """Test _merge_newlines_into_operators at the token-stream level."""

    def _run(self, tokens):
        """Run the postlexer pass and return a list of tokens."""
        return list(PostLexer()._merge_newlines_into_operators(iter(tokens)))

    def test_no_newlines_passes_through(self):
        tokens = [Token("NAME", "a"), Token("PLUS", "+"), Token("NAME", "b")]
        result = self._run(tokens)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[1].type, "PLUS")
        self.assertEqual(str(result[1]), "+")

    def test_newline_before_operator_is_merged(self):
        tokens = [
            Token("NAME", "a"),
            Token("NL_OR_COMMENT", "\n    "),
            Token("PLUS", "+"),
            Token("NAME", "b"),
        ]
        result = self._run(tokens)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[1].type, "PLUS")
        self.assertEqual(str(result[1]), "\n    +")

    def test_newline_before_non_operator_is_preserved(self):
        tokens = [
            Token("NAME", "a"),
            Token("NL_OR_COMMENT", "\n"),
            Token("NAME", "b"),
        ]
        result = self._run(tokens)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[1].type, "NL_OR_COMMENT")

    def test_consecutive_newlines_first_yielded(self):
        tokens = [
            Token("NL_OR_COMMENT", "\n"),
            Token("NL_OR_COMMENT", "\n    "),
            Token("PLUS", "+"),
        ]
        result = self._run(tokens)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].type, "NL_OR_COMMENT")
        self.assertEqual(str(result[0]), "\n")
        self.assertEqual(result[1].type, "PLUS")
        self.assertEqual(str(result[1]), "\n    +")

    def test_trailing_newline_is_yielded(self):
        tokens = [Token("NAME", "a"), Token("NL_OR_COMMENT", "\n")]
        result = self._run(tokens)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[1].type, "NL_OR_COMMENT")

    def test_all_operator_types_are_merged(self):
        for op_type in sorted(OPERATOR_TYPES):
            with self.subTest(op_type=op_type):
                tokens = [
                    Token("NL_OR_COMMENT", "\n"),
                    Token(op_type, "x"),
                ]
                result = self._run(tokens)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0].type, op_type)
                self.assertTrue(str(result[0]).startswith("\n"))

    def test_minus_not_in_operator_types(self):
        self.assertNotIn("MINUS", OPERATOR_TYPES)


class TestMultilineOperatorParsing(TestCase):
    """Test that HCL2 snippets with multiline operators parse correctly."""

    def test_multiline_ternary(self):
        hcl = 'x = (\n  a\n  ? "yes"\n  : "no"\n)\n'
        result = loads(hcl)
        self.assertEqual(result["x"], '${(a ? "yes" : "no")}')

    def test_multiline_logical_or(self):
        hcl = "x = (\n  a\n  || b\n)\n"
        result = loads(hcl)
        self.assertEqual(result["x"], "${(a || b)}")

    def test_multiline_logical_and(self):
        hcl = "x = (\n  a\n  && b\n)\n"
        result = loads(hcl)
        self.assertEqual(result["x"], "${(a && b)}")

    def test_multiline_equality(self):
        hcl = "x = (\n  a\n  == b\n)\n"
        result = loads(hcl)
        self.assertEqual(result["x"], "${(a == b)}")

    def test_multiline_not_equal(self):
        hcl = "x = (\n  a\n  != b\n)\n"
        result = loads(hcl)
        self.assertEqual(result["x"], "${(a != b)}")

    def test_multiline_comparison(self):
        hcl = "x = (\n  a\n  >= b\n)\n"
        result = loads(hcl)
        self.assertEqual(result["x"], "${(a >= b)}")

    def test_multiline_addition(self):
        hcl = "x = (\n  a\n  + b\n)\n"
        result = loads(hcl)
        self.assertEqual(result["x"], "${(a + b)}")

    def test_multiline_multiplication(self):
        hcl = "x = (\n  a\n  * b\n)\n"
        result = loads(hcl)
        self.assertEqual(result["x"], "${(a * b)}")

    def test_multiline_chained_operators(self):
        hcl = "x = (\n  a\n  && b\n  && c\n)\n"
        result = loads(hcl)
        self.assertEqual(result["x"], "${(a && b && c)}")

    def test_multiline_nested_ternary(self):
        hcl = 'x = (\n  a\n  ? b\n  : c == "d"\n  ? "e"\n  : f\n)\n'
        result = loads(hcl)
        self.assertEqual(result["x"], '${(a ? b : c == "d" ? "e" : f)}')

    def test_minus_on_new_line_is_separate_attribute(self):
        """MINUS is excluded from merging — newline before - starts a new statement."""
        hcl = "a = 1\nb = -2\n"
        result = loads(hcl)
        self.assertEqual(result["a"], 1)
        self.assertIn("b", result)

    def test_single_line_operators_still_work(self):
        hcl = "x = a + b\n"
        result = loads(hcl)
        self.assertEqual(result["x"], "${a + b}")
