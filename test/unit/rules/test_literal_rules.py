# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.rules.literal_rules import (
    KeywordRule,
    IdentifierRule,
    IntLitRule,
    FloatLitRule,
    BinaryOperatorRule,
)
from hcl2.rules.tokens import NAME, BINARY_OP, IntLiteral, FloatLiteral
from hcl2.utils import SerializationContext, SerializationOptions


class TestKeywordRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(KeywordRule.lark_name(), "keyword")

    def test_token_property(self):
        token = NAME("true")
        rule = KeywordRule([token])
        self.assertIs(rule.token, token)

    def test_serialize(self):
        rule = KeywordRule([NAME("true")])
        self.assertEqual(rule.serialize(), "true")


class TestIdentifierRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(IdentifierRule.lark_name(), "identifier")

    def test_serialize(self):
        rule = IdentifierRule([NAME("my_var")])
        self.assertEqual(rule.serialize(), "my_var")

    def test_token_property(self):
        token = NAME("foo")
        rule = IdentifierRule([token])
        self.assertIs(rule.token, token)


class TestIntLitRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(IntLitRule.lark_name(), "int_lit")

    def test_serialize_returns_int(self):
        rule = IntLitRule([IntLiteral("42")])
        result = rule.serialize()
        self.assertEqual(result, 42)
        self.assertIsInstance(result, int)


class TestFloatLitRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(FloatLitRule.lark_name(), "float_lit")

    def test_serialize_returns_float(self):
        rule = FloatLitRule([FloatLiteral("3.14")])
        result = rule.serialize()
        self.assertAlmostEqual(result, 3.14)
        self.assertIsInstance(result, float)

    def test_serialize_scientific_notation_as_dollar_string(self):
        """Scientific notation is preserved as ${...} to survive dict round-trip."""
        rule = FloatLitRule([FloatLiteral("1.23e5")])
        self.assertEqual(rule.serialize(), "${1.23e5}")

    def test_serialize_scientific_negative_exponent(self):
        rule = FloatLitRule([FloatLiteral("9.87e-3")])
        self.assertEqual(rule.serialize(), "${9.87e-3}")

    def test_serialize_scientific_inside_dollar_string(self):
        """Inside a dollar string context, return raw value without wrapping."""
        rule = FloatLitRule([FloatLiteral("1.23e5")])
        ctx = SerializationContext(inside_dollar_string=True)
        self.assertEqual(rule.serialize(context=ctx), "1.23e5")

    def test_serialize_regular_float_not_wrapped(self):
        """Non-scientific floats should remain plain Python floats."""
        rule = FloatLitRule([FloatLiteral("123.456")])
        result = rule.serialize()
        self.assertEqual(result, 123.456)
        self.assertIsInstance(result, float)

    def test_serialize_scientific_disabled(self):
        """With preserve_scientific_notation=False, returns plain float."""
        rule = FloatLitRule([FloatLiteral("1.23e5")])
        opts = SerializationOptions(preserve_scientific_notation=False)
        result = rule.serialize(options=opts)
        self.assertEqual(result, 123000.0)
        self.assertIsInstance(result, float)


class TestBinaryOperatorRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(BinaryOperatorRule.lark_name(), "binary_operator")

    def test_serialize_plus(self):
        rule = BinaryOperatorRule([BINARY_OP("+")])
        self.assertEqual(rule.serialize(), "+")

    def test_serialize_equals(self):
        rule = BinaryOperatorRule([BINARY_OP("==")])
        self.assertEqual(rule.serialize(), "==")

    def test_serialize_and(self):
        rule = BinaryOperatorRule([BINARY_OP("&&")])
        self.assertEqual(rule.serialize(), "&&")

    def test_serialize_or(self):
        rule = BinaryOperatorRule([BINARY_OP("||")])
        self.assertEqual(rule.serialize(), "||")

    def test_serialize_gt(self):
        rule = BinaryOperatorRule([BINARY_OP(">")])
        self.assertEqual(rule.serialize(), ">")

    def test_serialize_multiply(self):
        rule = BinaryOperatorRule([BINARY_OP("*")])
        self.assertEqual(rule.serialize(), "*")

    def test_token_property(self):
        token = BINARY_OP("+")
        rule = BinaryOperatorRule([token])
        self.assertIs(rule.token, token)
