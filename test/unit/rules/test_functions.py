# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.rules.expressions import ExpressionRule
from hcl2.rules.functions import (
    ArgumentsRule,
    FunctionCallRule,
)
from hcl2.rules.literal_rules import IdentifierRule
from hcl2.rules.tokens import NAME, COMMA, ELLIPSIS, LPAR, RPAR, StringToken
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


def _make_arguments(values, ellipsis=False):
    """Build an ArgumentsRule from a list of stub values.

    values: list of serialization values for StubExpression args
    ellipsis: if True, append an ELLIPSIS token
    """
    children = []
    for i, val in enumerate(values):
        if i > 0:
            children.append(COMMA())
        children.append(StubExpression(val))
    if ellipsis:
        children.append(ELLIPSIS())
    return ArgumentsRule(children)


def _make_function_call(func_names, arg_values=None, ellipsis=False):
    """Build a FunctionCallRule.

    func_names: list of identifier name strings (e.g. ["func"] or ["ns", "mod", "func"])
    arg_values: optional list of stub values for arguments
    ellipsis: if True, pass ellipsis to arguments
    """
    children = [_make_identifier(name) for name in func_names]
    children.append(LPAR())
    if arg_values is not None:
        children.append(_make_arguments(arg_values, ellipsis))
    children.append(RPAR())
    return FunctionCallRule(children)


# --- ArgumentsRule tests ---


class TestArgumentsRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(ArgumentsRule.lark_name(), "arguments")

    def test_has_ellipsis_false(self):
        rule = _make_arguments(["a"])
        self.assertFalse(rule.has_ellipsis)

    def test_has_ellipsis_true(self):
        rule = _make_arguments(["a", "b"], ellipsis=True)
        self.assertTrue(rule.has_ellipsis)

    def test_arguments_single(self):
        rule = _make_arguments(["a"])
        self.assertEqual(len(rule.arguments), 1)

    def test_arguments_multiple(self):
        rule = _make_arguments(["a", "b", "c"])
        self.assertEqual(len(rule.arguments), 3)

    def test_serialize_single_arg(self):
        rule = _make_arguments(["a"])
        self.assertEqual(rule.serialize(), "a")

    def test_serialize_with_ellipsis(self):
        rule = _make_arguments(["a", "b"], ellipsis=True)
        self.assertEqual(rule.serialize(), "a, b ...")


# --- FunctionCallRule tests ---


class TestFunctionCallRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(FunctionCallRule.lark_name(), "function_call")

    def test_identifiers_single(self):
        rule = _make_function_call(["func"])
        self.assertEqual(len(rule.identifiers), 1)

    def test_identifiers_multiple(self):
        rule = _make_function_call(["ns", "mod", "func"])
        self.assertEqual(len(rule.identifiers), 3)

    def test_arguments_property_present(self):
        rule = _make_function_call(["func"], ["a"])
        self.assertIsInstance(rule.arguments, ArgumentsRule)

    def test_arguments_property_none(self):
        rule = _make_function_call(["func"])
        self.assertIsNone(rule.arguments)

    def test_serialize_simple_no_args(self):
        rule = _make_function_call(["func"])
        self.assertEqual(rule.serialize(), "${func()}")

    def test_serialize_simple_with_args(self):
        rule = _make_function_call(["func"], ["a", "b"])
        self.assertEqual(rule.serialize(), "${func(a, b)}")

    def test_serialize_inside_dollar_string(self):
        rule = _make_function_call(["func"], ["a"])
        ctx = SerializationContext(inside_dollar_string=True)
        self.assertEqual(rule.serialize(context=ctx), "func(a)")

    def test_arguments_with_colons_tokens(self):
        """FunctionCallRule with COLONS tokens (provider syntax) should still find arguments."""
        COLONS = StringToken["COLONS"]
        children = [
            _make_identifier("provider"),
            COLONS("::"),
            _make_identifier("func"),
            COLONS("::"),
            _make_identifier("aa"),
            LPAR(),
            _make_arguments([5]),
            RPAR(),
        ]
        rule = FunctionCallRule(children)
        self.assertIsNotNone(rule.arguments)
        self.assertEqual(rule.serialize(), "${provider::func::aa(5)}")
