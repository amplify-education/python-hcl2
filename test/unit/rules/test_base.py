# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.const import IS_BLOCK
from hcl2.rules.base import AttributeRule, BodyRule, StartRule, BlockRule
from hcl2.rules.expressions import ExpressionRule, ExprTermRule
from hcl2.rules.literal_rules import IdentifierRule
from hcl2.rules.strings import StringRule, StringPartRule
from hcl2.rules.tokens import (
    NAME,
    EQ,
    LBRACE,
    RBRACE,
    DBLQUOTE,
    STRING_CHARS,
    NL_OR_COMMENT,
)
from hcl2.rules.whitespace import NewLineOrCommentRule
from hcl2.utils import SerializationOptions, SerializationContext


# --- Stubs & helpers ---


class StubExpression(ExpressionRule):
    """Minimal concrete ExpressionRule that serializes to a fixed value."""

    def __init__(self, value):
        self._stub_value = value
        super().__init__([], None)

    def serialize(self, options=SerializationOptions(), context=SerializationContext()):
        return self._stub_value


def _make_identifier(name):
    return IdentifierRule([NAME(name)])


def _make_expr_term(value):
    return ExprTermRule([StubExpression(value)])


def _make_string_rule(text):
    part = StringPartRule([STRING_CHARS(text)])
    return StringRule([DBLQUOTE(), part, DBLQUOTE()])


def _make_nlc(text):
    return NewLineOrCommentRule([NL_OR_COMMENT(text)])


def _make_attribute(name, value):
    return AttributeRule([_make_identifier(name), EQ(), _make_expr_term(value)])


def _make_block(labels, body_children=None):
    """Build a BlockRule with the given labels and body children.

    labels: list of IdentifierRule or StringRule instances
    body_children: list of children for the body, or None for empty body
    """
    body = BodyRule(body_children or [])
    children = list(labels) + [LBRACE(), body, RBRACE()]
    return BlockRule(children)


# --- AttributeRule tests ---


class TestAttributeRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(AttributeRule.lark_name(), "attribute")

    def test_identifier_property(self):
        ident = _make_identifier("name")
        attr = AttributeRule([ident, EQ(), _make_expr_term("value")])
        self.assertIs(attr.identifier, ident)

    def test_expression_property(self):
        expr_term = _make_expr_term("value")
        attr = AttributeRule([_make_identifier("name"), EQ(), expr_term])
        self.assertIs(attr.expression, expr_term)

    def test_serialize(self):
        attr = _make_attribute("name", "value")
        self.assertEqual(attr.serialize(), {"name": "value"})

    def test_serialize_int_value(self):
        attr = _make_attribute("count", 42)
        self.assertEqual(attr.serialize(), {"count": 42})

    def test_serialize_expression_value(self):
        attr = _make_attribute("expr", "${var.x}")
        self.assertEqual(attr.serialize(), {"expr": "${var.x}"})


# --- BodyRule tests ---


class TestBodyRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(BodyRule.lark_name(), "body")

    def test_serialize_empty(self):
        body = BodyRule([])
        self.assertEqual(body.serialize(), {})

    def test_serialize_single_attribute(self):
        body = BodyRule([_make_attribute("name", "value")])
        self.assertEqual(body.serialize(), {"name": "value"})

    def test_serialize_multiple_attributes(self):
        body = BodyRule([_make_attribute("a", 1), _make_attribute("b", 2)])
        self.assertEqual(body.serialize(), {"a": 1, "b": 2})

    def test_serialize_single_block(self):
        block = _make_block([_make_identifier("resource")])
        body = BodyRule([block])
        result = body.serialize()
        self.assertIn("resource", result)
        self.assertIsInstance(result["resource"], list)
        self.assertEqual(len(result["resource"]), 1)
        self.assertTrue(result["resource"][0][IS_BLOCK])

    def test_serialize_multiple_blocks_same_type(self):
        block1 = _make_block(
            [_make_identifier("resource")],
            [_make_attribute("name", "first")],
        )
        block2 = _make_block(
            [_make_identifier("resource")],
            [_make_attribute("name", "second")],
        )
        body = BodyRule([block1, block2])
        result = body.serialize()
        self.assertEqual(len(result["resource"]), 2)
        self.assertEqual(result["resource"][0]["name"], "first")
        self.assertEqual(result["resource"][1]["name"], "second")

    def test_serialize_mixed_attributes_and_blocks(self):
        attr = _make_attribute("version", "1.0")
        block = _make_block([_make_identifier("provider")])
        body = BodyRule([attr, block])
        result = body.serialize()
        self.assertEqual(result["version"], "1.0")
        self.assertIn("provider", result)
        self.assertIsInstance(result["provider"], list)

    def test_serialize_comments_collected(self):
        nlc = _make_nlc("# a comment\n")
        attr = _make_attribute("x", 1)
        body = BodyRule([nlc, attr])
        result = body.serialize(options=SerializationOptions(with_comments=True))
        self.assertIn("__comments__", result)

    def test_serialize_comments_not_collected_without_option(self):
        nlc = _make_nlc("# a comment\n")
        attr = _make_attribute("x", 1)
        body = BodyRule([nlc, attr])
        result = body.serialize(options=SerializationOptions(with_comments=False))
        self.assertNotIn("__comments__", result)

    def test_serialize_bare_newlines_not_collected_as_comments(self):
        nlc = _make_nlc("\n")
        attr = _make_attribute("x", 1)
        body = BodyRule([nlc, attr])
        result = body.serialize(options=SerializationOptions(with_comments=True))
        self.assertNotIn("__comments__", result)

    def test_serialize_skips_newline_children(self):
        nlc = _make_nlc("\n")
        attr = _make_attribute("x", 1)
        body = BodyRule([nlc, attr, nlc])
        result = body.serialize()
        # NLC children should not appear as keys
        keys = [k for k in result.keys() if not k.startswith("__")]
        self.assertEqual(keys, ["x"])


# --- StartRule tests ---


class TestStartRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(StartRule.lark_name(), "start")

    def test_body_property(self):
        body = BodyRule([])
        start = StartRule([body])
        self.assertIs(start.body, body)

    def test_serialize_delegates_to_body(self):
        attr = _make_attribute("key", "val")
        body = BodyRule([attr])
        start = StartRule([body])
        self.assertEqual(start.serialize(), body.serialize())

    def test_serialize_empty_body(self):
        start = StartRule([BodyRule([])])
        self.assertEqual(start.serialize(), {})


# --- BlockRule tests ---


class TestBlockRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(BlockRule.lark_name(), "block")

    def test_labels_property_single(self):
        ident = _make_identifier("resource")
        block = _make_block([ident])
        self.assertEqual(len(block.labels), 1)
        self.assertIs(block.labels[0], ident)

    def test_labels_property_two(self):
        i1 = _make_identifier("resource")
        i2 = _make_identifier("aws_instance")
        block = _make_block([i1, i2])
        self.assertEqual(len(block.labels), 2)
        self.assertIs(block.labels[0], i1)
        self.assertIs(block.labels[1], i2)

    def test_labels_property_three(self):
        i1 = _make_identifier("resource")
        i2 = _make_identifier("aws_instance")
        s3 = _make_string_rule("example")
        block = _make_block([i1, i2, s3])
        labels = block.labels
        self.assertEqual(len(labels), 3)
        self.assertIs(labels[0], i1)
        self.assertIs(labels[1], i2)
        self.assertIs(labels[2], s3)

    def test_body_property(self):
        body = BodyRule([])
        ident = _make_identifier("resource")
        block = BlockRule([ident, LBRACE(), body, RBRACE()])
        self.assertIs(block.body, body)

    def test_constructor_filters_tokens(self):
        """LBRACE and RBRACE should not appear in labels or body."""
        ident = _make_identifier("resource")
        body = BodyRule([])
        block = BlockRule([ident, LBRACE(), body, RBRACE()])
        # labels should only contain the identifier
        self.assertEqual(len(block.labels), 1)
        self.assertIs(block.labels[0], ident)
        self.assertIs(block.body, body)

    def test_serialize_single_label_empty_body(self):
        block = _make_block([_make_identifier("resource")])
        result = block.serialize()
        self.assertEqual(result, {IS_BLOCK: True})

    def test_serialize_single_label_with_body(self):
        block = _make_block(
            [_make_identifier("resource")],
            [_make_attribute("name", "foo")],
        )
        result = block.serialize()
        self.assertEqual(result, {"name": "foo", IS_BLOCK: True})

    def test_serialize_two_labels(self):
        block = _make_block(
            [_make_identifier("resource"), _make_identifier("aws_instance")],
            [_make_attribute("ami", "abc")],
        )
        result = block.serialize()
        self.assertIn("aws_instance", result)
        inner = result["aws_instance"]
        self.assertEqual(inner, {"ami": "abc", IS_BLOCK: True})

    def test_serialize_three_labels(self):
        block = _make_block(
            [
                _make_identifier("resource"),
                _make_identifier("aws_instance"),
                _make_string_rule("example"),
            ],
            [_make_attribute("ami", "abc")],
        )
        result = block.serialize()
        self.assertIn("aws_instance", result)
        inner = result["aws_instance"]
        self.assertIn('"example"', inner)
        innermost = inner['"example"']
        self.assertEqual(innermost, {"ami": "abc", IS_BLOCK: True})

    def test_serialize_explicit_blocks_false(self):
        block = _make_block(
            [_make_identifier("resource")],
            [_make_attribute("name", "foo")],
        )
        opts = SerializationOptions(explicit_blocks=False)
        result = block.serialize(options=opts)
        self.assertNotIn(IS_BLOCK, result)
        self.assertEqual(result, {"name": "foo"})

    def test_serialize_string_label(self):
        block = _make_block(
            [_make_identifier("resource"), _make_string_rule("my_label")],
            [_make_attribute("x", 1)],
        )
        result = block.serialize()
        # StringRule serializes with quotes
        self.assertIn('"my_label"', result)
