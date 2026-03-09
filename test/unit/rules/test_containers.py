# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.rules.containers import (
    TupleRule,
    ObjectElemKeyRule,
    ObjectElemKeyExpressionRule,
    ObjectElemRule,
    ObjectRule,
)
from hcl2.rules.expressions import ExpressionRule
from hcl2.rules.literal_rules import IdentifierRule, IntLitRule, FloatLitRule
from hcl2.rules.strings import StringRule, StringPartRule
from hcl2.rules.tokens import (
    LSQB,
    RSQB,
    LBRACE,
    RBRACE,
    EQ,
    COLON,
    COMMA,
    NAME,
    DBLQUOTE,
    STRING_CHARS,
    IntLiteral,
    FloatLiteral,
)
from hcl2.rules.whitespace import NewLineOrCommentRule
from hcl2.rules.tokens import NL_OR_COMMENT
from hcl2.utils import SerializationOptions, SerializationContext


# --- Stubs & Helpers ---


class StubExpression(ExpressionRule):
    """Minimal ExpressionRule that serializes to a fixed value."""

    def __init__(self, value):
        self._stub_value = value
        super().__init__([], None)

    def serialize(self, options=SerializationOptions(), context=SerializationContext()):
        return self._stub_value


def _make_nlc(text):
    return NewLineOrCommentRule([NL_OR_COMMENT(text)])


def _make_identifier(name):
    return IdentifierRule([NAME(name)])


def _make_string_rule(text):
    part = StringPartRule([STRING_CHARS(text)])
    return StringRule([DBLQUOTE(), part, DBLQUOTE()])


def _make_object_elem_key(identifier_name):
    return ObjectElemKeyRule([_make_identifier(identifier_name)])


def _make_object_elem(key_name, expr_value, sep=None):
    key = _make_object_elem_key(key_name)
    separator = sep or EQ()
    return ObjectElemRule([key, separator, StubExpression(expr_value)])


# --- TupleRule tests ---


class TestTupleRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(TupleRule.lark_name(), "tuple")

    def test_elements_empty_tuple(self):
        rule = TupleRule([LSQB(), RSQB()])
        self.assertEqual(rule.elements, [])

    def test_elements_single(self):
        expr = StubExpression(1)
        rule = TupleRule([LSQB(), expr, RSQB()])
        self.assertEqual(rule.elements, [expr])

    def test_elements_multiple(self):
        e1 = StubExpression(1)
        e2 = StubExpression(2)
        e3 = StubExpression(3)
        rule = TupleRule([LSQB(), e1, COMMA(), e2, COMMA(), e3, RSQB()])
        self.assertEqual(rule.elements, [e1, e2, e3])

    def test_elements_skips_non_expressions(self):
        e1 = StubExpression(1)
        e2 = StubExpression(2)
        nlc = _make_nlc("\n")
        rule = TupleRule([LSQB(), nlc, e1, COMMA(), nlc, e2, RSQB()])
        self.assertEqual(len(rule.elements), 2)

    def test_serialize_default_returns_list(self):
        rule = TupleRule(
            [LSQB(), StubExpression(1), COMMA(), StubExpression(2), RSQB()]
        )
        result = rule.serialize()
        self.assertEqual(result, [1, 2])

    def test_serialize_empty_returns_empty_list(self):
        rule = TupleRule([LSQB(), RSQB()])
        self.assertEqual(rule.serialize(), [])

    def test_serialize_single_element(self):
        rule = TupleRule([LSQB(), StubExpression(42), RSQB()])
        self.assertEqual(rule.serialize(), [42])

    def test_serialize_wrap_tuples(self):
        rule = TupleRule(
            [LSQB(), StubExpression("a"), COMMA(), StubExpression("b"), RSQB()]
        )
        opts = SerializationOptions(wrap_tuples=True)
        result = rule.serialize(options=opts)
        self.assertEqual(result, "${[a, b]}")

    def test_serialize_wrap_tuples_empty(self):
        rule = TupleRule([LSQB(), RSQB()])
        opts = SerializationOptions(wrap_tuples=True)
        result = rule.serialize(options=opts)
        self.assertEqual(result, "${[]}")

    def test_serialize_inside_dollar_string(self):
        rule = TupleRule([LSQB(), StubExpression("a"), RSQB()])
        ctx = SerializationContext(inside_dollar_string=True)
        result = rule.serialize(context=ctx)
        # Inside dollar string forces string representation
        self.assertEqual(result, "[a]")

    def test_serialize_inside_dollar_string_no_extra_wrap(self):
        rule = TupleRule(
            [LSQB(), StubExpression("a"), COMMA(), StubExpression("b"), RSQB()]
        )
        ctx = SerializationContext(inside_dollar_string=True)
        result = rule.serialize(context=ctx)
        self.assertEqual(result, "[a, b]")

    def test_serialize_wrap_tuples_inside_dollar_string(self):
        rule = TupleRule([LSQB(), StubExpression("x"), RSQB()])
        opts = SerializationOptions(wrap_tuples=True)
        ctx = SerializationContext(inside_dollar_string=True)
        result = rule.serialize(options=opts, context=ctx)
        # Already inside $, so no extra wrapping
        self.assertEqual(result, "[x]")


# --- ObjectElemKeyRule tests ---


class TestObjectElemKeyRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(ObjectElemKeyRule.lark_name(), "object_elem_key")

    def test_value_property_identifier(self):
        ident = _make_identifier("foo")
        rule = ObjectElemKeyRule([ident])
        self.assertIs(rule.value, ident)

    def test_serialize_identifier(self):
        rule = ObjectElemKeyRule([_make_identifier("my_key")])
        self.assertEqual(rule.serialize(), "my_key")

    def test_serialize_int_lit(self):
        rule = ObjectElemKeyRule([IntLitRule([IntLiteral("5")])])
        self.assertEqual(rule.serialize(), "5")

    def test_serialize_float_lit(self):
        rule = ObjectElemKeyRule([FloatLitRule([FloatLiteral("3.14")])])
        self.assertEqual(rule.serialize(), "3.14")

    def test_serialize_string(self):
        rule = ObjectElemKeyRule([_make_string_rule("k3")])
        self.assertEqual(rule.serialize(), '"k3"')


# --- ObjectElemKeyExpressionRule tests ---


class TestObjectElemKeyExpressionRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(
            ObjectElemKeyExpressionRule.lark_name(), "object_elem_key_expr"
        )

    def test_expression_property(self):
        expr = StubExpression("1 + 1")
        rule = ObjectElemKeyExpressionRule([expr])
        self.assertIs(rule.expression, expr)

    def test_serialize_bare(self):
        rule = ObjectElemKeyExpressionRule([StubExpression("1 + 1")])
        result = rule.serialize()
        self.assertEqual(result, "${1 + 1}")

    def test_serialize_inside_dollar_string(self):
        rule = ObjectElemKeyExpressionRule([StubExpression("1 + 1")])
        ctx = SerializationContext(inside_dollar_string=True)
        result = rule.serialize(context=ctx)
        self.assertEqual(result, "1 + 1")

    def test_serialize_function_call(self):
        rule = ObjectElemKeyExpressionRule([StubExpression('format("k", v)')])
        result = rule.serialize()
        self.assertEqual(result, '${format("k", v)}')


# --- ObjectElemRule tests ---


class TestObjectElemRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(ObjectElemRule.lark_name(), "object_elem")

    def test_key_property(self):
        key = _make_object_elem_key("foo")
        rule = ObjectElemRule([key, EQ(), StubExpression("bar")])
        self.assertIs(rule.key, key)

    def test_expression_property(self):
        expr = StubExpression("bar")
        rule = ObjectElemRule([_make_object_elem_key("foo"), EQ(), expr])
        self.assertIs(rule.expression, expr)

    def test_serialize_with_eq(self):
        rule = _make_object_elem("name", "value")
        self.assertEqual(rule.serialize(), {"name": "value"})

    def test_serialize_with_colon(self):
        rule = ObjectElemRule([_make_object_elem_key("k"), COLON(), StubExpression(42)])
        self.assertEqual(rule.serialize(), {"k": 42})

    def test_serialize_int_value(self):
        rule = _make_object_elem("count", 5)
        self.assertEqual(rule.serialize(), {"count": 5})

    def test_serialize_string_key(self):
        key = ObjectElemKeyRule([_make_string_rule("quoted")])
        rule = ObjectElemRule([key, EQ(), StubExpression("val")])
        self.assertEqual(rule.serialize(), {'"quoted"': "val"})


# --- ObjectRule tests ---


class TestObjectRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(ObjectRule.lark_name(), "object")

    def test_elements_empty(self):
        rule = ObjectRule([LBRACE(), RBRACE()])
        self.assertEqual(rule.elements, [])

    def test_elements_single(self):
        elem = _make_object_elem("k", "v")
        rule = ObjectRule([LBRACE(), elem, RBRACE()])
        self.assertEqual(rule.elements, [elem])

    def test_elements_multiple(self):
        e1 = _make_object_elem("a", 1)
        e2 = _make_object_elem("b", 2)
        rule = ObjectRule([LBRACE(), e1, e2, RBRACE()])
        self.assertEqual(rule.elements, [e1, e2])

    def test_elements_skips_non_elem(self):
        e1 = _make_object_elem("a", 1)
        nlc = _make_nlc("\n")
        rule = ObjectRule([LBRACE(), nlc, e1, nlc, RBRACE()])
        self.assertEqual(rule.elements, [e1])

    def test_serialize_default_returns_dict(self):
        rule = ObjectRule(
            [
                LBRACE(),
                _make_object_elem("k1", "v1"),
                _make_object_elem("k2", "v2"),
                RBRACE(),
            ]
        )
        result = rule.serialize()
        self.assertEqual(result, {"k1": "v1", "k2": "v2"})

    def test_serialize_empty_returns_empty_dict(self):
        rule = ObjectRule([LBRACE(), RBRACE()])
        self.assertEqual(rule.serialize(), {})

    def test_serialize_single_element(self):
        rule = ObjectRule([LBRACE(), _make_object_elem("x", 42), RBRACE()])
        self.assertEqual(rule.serialize(), {"x": 42})

    def test_serialize_wrap_objects(self):
        rule = ObjectRule(
            [
                LBRACE(),
                _make_object_elem("k1", "v1"),
                _make_object_elem("k2", "v2"),
                RBRACE(),
            ]
        )
        opts = SerializationOptions(wrap_objects=True)
        result = rule.serialize(options=opts)
        # Result is "{k1 = v1, k2 = v2}" wrapped in ${}, giving ${{...}}
        self.assertEqual(result, "${{k1 = v1, k2 = v2}}")

    def test_serialize_wrap_objects_empty(self):
        rule = ObjectRule([LBRACE(), RBRACE()])
        opts = SerializationOptions(wrap_objects=True)
        result = rule.serialize(options=opts)
        self.assertEqual(result, "${{}}")

    def test_serialize_inside_dollar_string(self):
        rule = ObjectRule(
            [
                LBRACE(),
                _make_object_elem("k", "v"),
                RBRACE(),
            ]
        )
        ctx = SerializationContext(inside_dollar_string=True)
        result = rule.serialize(context=ctx)
        # Inside dollar string forces string representation
        self.assertEqual(result, "{k = v}")

    def test_serialize_inside_dollar_string_no_extra_wrap(self):
        rule = ObjectRule(
            [
                LBRACE(),
                _make_object_elem("a", 1),
                _make_object_elem("b", 2),
                RBRACE(),
            ]
        )
        ctx = SerializationContext(inside_dollar_string=True)
        result = rule.serialize(context=ctx)
        self.assertEqual(result, "{a = 1, b = 2}")

    def test_serialize_wrap_objects_inside_dollar_string(self):
        rule = ObjectRule(
            [
                LBRACE(),
                _make_object_elem("k", "v"),
                RBRACE(),
            ]
        )
        opts = SerializationOptions(wrap_objects=True)
        ctx = SerializationContext(inside_dollar_string=True)
        result = rule.serialize(options=opts, context=ctx)
        self.assertEqual(result, "{k = v}")
