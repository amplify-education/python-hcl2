from unittest import TestCase

from hcl2.rules.literal_rules import (
    TokenRule,
    KeywordRule,
    IdentifierRule,
    IntLitRule,
    FloatLitRule,
    BinaryOperatorRule,
)
from hcl2.rules.tokens import NAME, BINARY_OP, IntLiteral, FloatLiteral


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
