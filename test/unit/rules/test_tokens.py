# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.rules.tokens import (
    StringToken,
    StaticStringToken,
    IntLiteral,
    FloatLiteral,
    NAME,
    LPAR,
    RPAR,
    QMARK,
    COLON,
    EQ,
    DOT,
    COMMA,
    LBRACE,
    RBRACE,
    LSQB,
    RSQB,
)


class TestStringToken(TestCase):
    def test_class_getitem_creates_subclass(self):
        cls = StringToken["MY_TOKEN"]
        self.assertTrue(issubclass(cls, StringToken))

    def test_class_getitem_caching(self):
        cls1 = StringToken["CACHED"]
        cls2 = StringToken["CACHED"]
        self.assertIs(cls1, cls2)

    def test_different_names_different_classes(self):
        cls1 = StringToken["AAA"]
        cls2 = StringToken["BBB"]
        self.assertIsNot(cls1, cls2)

    def test_lark_name_returns_subscript(self):
        cls = StringToken["FOO_BAR"]
        instance = cls("value")
        self.assertEqual(instance.lark_name(), "FOO_BAR")

    def test_serialize_returns_str(self):
        instance = NAME("my_var")
        self.assertEqual(instance.serialize(), "my_var")

    def test_serialize_numeric_value(self):
        instance = NAME(42)
        self.assertEqual(instance.serialize(), "42")

    def test_type_error_on_non_str_subscript(self):
        with self.assertRaises(TypeError):
            StringToken[42]  # pylint: disable=pointless-statement


class TestStaticStringToken(TestCase):
    def test_class_getitem_with_tuple(self):
        cls = StaticStringToken[("TEST_STATIC", "test_val")]
        self.assertTrue(issubclass(cls, StaticStringToken))

    def test_init_uses_default_value(self):
        instance = LPAR()
        self.assertEqual(instance.value, "(")

    def test_lark_name(self):
        instance = LPAR()
        self.assertEqual(instance.lark_name(), "LPAR")

    def test_serialize(self):
        instance = LPAR()
        self.assertEqual(instance.serialize(), "(")

    def test_classes_by_value_registry(self):
        self.assertIn("(", StaticStringToken.classes_by_value)
        self.assertIs(StaticStringToken.classes_by_value["("], type(LPAR()))


class TestTokenConstants(TestCase):
    def test_lpar(self):
        t = LPAR()
        self.assertEqual(t.lark_name(), "LPAR")
        self.assertEqual(t.serialize(), "(")

    def test_rpar(self):
        t = RPAR()
        self.assertEqual(t.lark_name(), "RPAR")
        self.assertEqual(t.serialize(), ")")

    def test_qmark(self):
        t = QMARK()
        self.assertEqual(t.lark_name(), "QMARK")
        self.assertEqual(t.serialize(), "?")

    def test_colon(self):
        t = COLON()
        self.assertEqual(t.lark_name(), "COLON")
        self.assertEqual(t.serialize(), ":")

    def test_eq(self):
        t = EQ()
        self.assertEqual(t.lark_name(), "EQ")
        self.assertEqual(t.serialize(), "=")

    def test_dot(self):
        t = DOT()
        self.assertEqual(t.lark_name(), "DOT")
        self.assertEqual(t.serialize(), ".")

    def test_comma(self):
        t = COMMA()
        self.assertEqual(t.lark_name(), "COMMA")
        self.assertEqual(t.serialize(), ",")

    def test_lbrace(self):
        t = LBRACE()
        self.assertEqual(t.lark_name(), "LBRACE")
        self.assertEqual(t.serialize(), "{")

    def test_rbrace(self):
        t = RBRACE()
        self.assertEqual(t.lark_name(), "RBRACE")
        self.assertEqual(t.serialize(), "}")

    def test_lsqb(self):
        t = LSQB()
        self.assertEqual(t.lark_name(), "LSQB")
        self.assertEqual(t.serialize(), "[")

    def test_rsqb(self):
        t = RSQB()
        self.assertEqual(t.lark_name(), "RSQB")
        self.assertEqual(t.serialize(), "]")


class TestIntLiteral(TestCase):
    def test_lark_name(self):
        self.assertEqual(IntLiteral.lark_name(), "INT_LITERAL")

    def test_serialize_converts_to_int(self):
        token = IntLiteral("42")
        result = token.serialize()
        self.assertEqual(result, 42)
        self.assertIsInstance(result, int)

    def test_serialize_already_int(self):
        token = IntLiteral(7)
        self.assertEqual(token.serialize(), 7)


class TestFloatLiteral(TestCase):
    def test_lark_name(self):
        self.assertEqual(FloatLiteral.lark_name(), "FLOAT_LITERAL")

    def test_serialize_converts_to_float(self):
        token = FloatLiteral("3.14")
        result = token.serialize()
        self.assertAlmostEqual(result, 3.14)
        self.assertIsInstance(result, float)

    def test_serialize_already_float(self):
        token = FloatLiteral(2.5)
        self.assertEqual(token.serialize(), 2.5)
