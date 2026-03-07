# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.rules.tokens import NAME, NL_OR_COMMENT
from hcl2.rules.whitespace import NewLineOrCommentRule, InlineCommentMixIn
from hcl2.utils import SerializationOptions, SerializationContext


# --- Concrete stub for testing InlineCommentMixIn ---


class ConcreteInlineComment(InlineCommentMixIn):
    @staticmethod
    def lark_name() -> str:
        return "test_inline"

    def serialize(self, options=SerializationOptions(), context=SerializationContext()):
        return "test"


def _make_nlc(text):
    """Helper: build NewLineOrCommentRule from a string."""
    return NewLineOrCommentRule([NL_OR_COMMENT(text)])


# --- Tests ---


class TestNewLineOrCommentRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(NewLineOrCommentRule.lark_name(), "new_line_or_comment")

    def test_serialize_newline(self):
        rule = _make_nlc("\n")
        self.assertEqual(rule.serialize(), "\n")

    def test_serialize_line_comment(self):
        rule = _make_nlc("// this is a comment\n")
        self.assertEqual(rule.serialize(), "// this is a comment\n")

    def test_serialize_hash_comment(self):
        rule = _make_nlc("# hash comment\n")
        self.assertEqual(rule.serialize(), "# hash comment\n")

    def test_to_list_bare_newline_returns_none(self):
        rule = _make_nlc("\n")
        self.assertIsNone(rule.to_list())

    def test_to_list_line_comment(self):
        rule = _make_nlc("// my comment\n")
        result = rule.to_list()
        self.assertEqual(result, ["my comment"])

    def test_to_list_hash_comment(self):
        rule = _make_nlc("# my comment\n")
        result = rule.to_list()
        self.assertEqual(result, ["my comment"])

    def test_to_list_block_comment(self):
        rule = _make_nlc("/* block comment */\n")
        result = rule.to_list()
        self.assertEqual(result, ["block comment"])

    def test_to_list_multiple_comments(self):
        rule = _make_nlc("// first\n// second\n")
        result = rule.to_list()
        self.assertIn("first", result)
        self.assertIn("second", result)

    def test_token_property(self):
        token = NL_OR_COMMENT("\n")
        rule = NewLineOrCommentRule([token])
        self.assertIs(rule.token, token)


class TestInlineCommentMixIn(TestCase):
    def test_insert_optionals_inserts_none_where_no_comment(self):

        token = NAME("x")
        children = [token, NAME("y")]
        mixin = ConcreteInlineComment.__new__(ConcreteInlineComment)
        mixin._insert_optionals(children, [1])
        # Should have inserted None at index 1, pushing NAME("y") to index 2
        self.assertIsNone(children[1])
        self.assertEqual(len(children), 3)

    def test_insert_optionals_leaves_comment_in_place(self):
        comment = _make_nlc("// comment\n")

        children = [NAME("x"), comment]
        mixin = ConcreteInlineComment.__new__(ConcreteInlineComment)
        mixin._insert_optionals(children, [1])
        # Should NOT insert None since index 1 is already a NewLineOrCommentRule
        self.assertIs(children[1], comment)
        self.assertEqual(len(children), 2)

    def test_insert_optionals_handles_index_error(self):
        children = [_make_nlc("\n")]
        mixin = ConcreteInlineComment.__new__(ConcreteInlineComment)
        mixin._insert_optionals(children, [3])
        # Should insert None at index 3
        self.assertEqual(len(children), 2)
        self.assertIsNone(children[1])

    def test_inline_comments_collects_from_children(self):
        comment = _make_nlc("// hello\n")

        rule = ConcreteInlineComment([NAME("x"), comment])
        result = rule.inline_comments()
        self.assertEqual(result, ["hello"])

    def test_inline_comments_skips_bare_newlines(self):
        newline = _make_nlc("\n")

        rule = ConcreteInlineComment([NAME("x"), newline])
        result = rule.inline_comments()
        self.assertEqual(result, [])

    def test_inline_comments_recursive(self):
        comment = _make_nlc("// inner\n")
        inner = ConcreteInlineComment([comment])
        outer = ConcreteInlineComment([inner])
        result = outer.inline_comments()
        self.assertEqual(result, ["inner"])

    def test_inline_comments_empty(self):

        rule = ConcreteInlineComment([NAME("x")])
        result = rule.inline_comments()
        self.assertEqual(result, [])
