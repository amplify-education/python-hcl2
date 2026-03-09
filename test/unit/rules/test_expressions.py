# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.rules.abstract import LarkRule
from hcl2.rules.expressions import (
    ExpressionRule,
    ExprTermRule,
    ConditionalRule,
    BinaryTermRule,
    BinaryOpRule,
    UnaryOpRule,
)
from hcl2.rules.literal_rules import BinaryOperatorRule
from hcl2.rules.tokens import (
    LPAR,
    RPAR,
    QMARK,
    COLON,
    BINARY_OP,
    StringToken,
)
from hcl2.utils import SerializationOptions, SerializationContext


# --- Stubs & helpers ---


class StubExpression(ExpressionRule):
    """Minimal concrete ExpressionRule that serializes to a fixed string."""

    def __init__(self, value, children=None):
        self._stub_value = value
        super().__init__(children or [], None)

    def serialize(self, options=SerializationOptions(), context=SerializationContext()):
        return self._stub_value


class NonExpressionRule(LarkRule):
    """A rule that is NOT an ExpressionRule, for parent-chain tests."""

    @staticmethod
    def lark_name():
        return "non_expression"

    def serialize(self, options=SerializationOptions(), context=SerializationContext()):
        return "non_expr"


def _make_expr_term(value):
    """Build ExprTermRule wrapping a StubExpression (no parens)."""
    return ExprTermRule([StubExpression(value)])


def _make_paren_expr_term(value):
    """Build ExprTermRule wrapping a StubExpression in parentheses."""
    return ExprTermRule([LPAR(), StubExpression(value), RPAR()])


def _make_binary_operator(op_str):
    """Build BinaryOperatorRule for an operator string."""
    return BinaryOperatorRule([BINARY_OP(op_str)])


def _make_binary_term(op_str, rhs_value):
    """Build BinaryTermRule with given operator and RHS value."""
    return BinaryTermRule([_make_binary_operator(op_str), _make_expr_term(rhs_value)])


MINUS_TOKEN = StringToken["MINUS"]  # type: ignore[type-arg,name-defined]
NOT_TOKEN = StringToken["NOT"]  # type: ignore[type-arg,name-defined]


# --- ExprTermRule tests ---


class TestExprTermRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(ExprTermRule.lark_name(), "expr_term")

    def test_construction_without_parens(self):
        stub = StubExpression("a")
        rule = ExprTermRule([stub])
        self.assertFalse(rule.parentheses)

    def test_construction_without_parens_children_structure(self):
        stub = StubExpression("a")
        rule = ExprTermRule([stub])
        # children: [None, None, stub, None, None]
        self.assertEqual(len(rule.children), 5)
        self.assertIsNone(rule.children[0])
        self.assertIsNone(rule.children[1])
        self.assertIs(rule.children[2], stub)
        self.assertIsNone(rule.children[3])
        self.assertIsNone(rule.children[4])

    def test_construction_with_parens(self):
        stub = StubExpression("a")
        rule = ExprTermRule([LPAR(), stub, RPAR()])
        self.assertTrue(rule.parentheses)

    def test_construction_with_parens_children_structure(self):
        stub = StubExpression("a")
        lpar = LPAR()
        rpar = RPAR()
        rule = ExprTermRule([lpar, stub, rpar])
        # children: [LPAR, None, stub, None, RPAR]
        self.assertEqual(len(rule.children), 5)
        self.assertIs(rule.children[0], lpar)
        self.assertIsNone(rule.children[1])
        self.assertIs(rule.children[2], stub)
        self.assertIsNone(rule.children[3])
        self.assertIs(rule.children[4], rpar)

    def test_expression_property(self):
        stub = StubExpression("a")
        rule = ExprTermRule([stub])
        self.assertIs(rule.expression, stub)

    def test_expression_property_with_parens(self):
        stub = StubExpression("a")
        rule = ExprTermRule([LPAR(), stub, RPAR()])
        self.assertIs(rule.expression, stub)

    def test_serialize_no_parens_delegates_to_inner(self):
        rule = _make_expr_term("hello")
        self.assertEqual(rule.serialize(), "hello")

    def test_serialize_no_parens_passes_through_int(self):
        stub = StubExpression(42)
        rule = ExprTermRule([stub])
        self.assertEqual(rule.serialize(), 42)

    def test_serialize_with_parens_wraps_and_dollar(self):
        rule = _make_paren_expr_term("a")
        result = rule.serialize()
        self.assertEqual(result, "${(a)}")

    def test_serialize_with_parens_inside_dollar_string(self):
        rule = _make_paren_expr_term("a")
        ctx = SerializationContext(inside_dollar_string=True)
        result = rule.serialize(context=ctx)
        # Inside dollar string: wraps in () but NOT in ${}
        self.assertEqual(result, "(a)")

    def test_serialize_sets_inside_parentheses_context(self):
        """When parenthesized, inner expression should see inside_parentheses=True."""
        seen_context = {}

        class ContextCapture(ExpressionRule):
            def serialize(
                self, options=SerializationOptions(), context=SerializationContext()
            ):
                seen_context["inside_parentheses"] = context.inside_parentheses
                return "x"

        rule = ExprTermRule([LPAR(), ContextCapture([]), RPAR()])
        rule.serialize()
        self.assertTrue(seen_context["inside_parentheses"])

    def test_serialize_no_parens_preserves_inside_parentheses(self):
        """Without parens, inside_parentheses passes through from caller context."""
        seen_context = {}

        class ContextCapture(ExpressionRule):
            def serialize(
                self, options=SerializationOptions(), context=SerializationContext()
            ):
                seen_context["inside_parentheses"] = context.inside_parentheses
                return "x"

        rule = ExprTermRule([ContextCapture([])])
        rule.serialize(context=SerializationContext(inside_parentheses=False))
        self.assertFalse(seen_context["inside_parentheses"])


# --- ConditionalRule tests ---


class TestConditionalRule(TestCase):
    def _make_conditional(self, cond_val="cond", true_val="yes", false_val="no"):
        return ConditionalRule(
            [
                StubExpression(cond_val),
                QMARK(),
                StubExpression(true_val),
                COLON(),
                StubExpression(false_val),
            ]
        )

    def test_lark_name(self):
        self.assertEqual(ConditionalRule.lark_name(), "conditional")

    def test_construction_inserts_optional_slots(self):
        rule = self._make_conditional()
        # Should have 8 children after _insert_optionals at [2, 4, 6]
        self.assertEqual(len(rule.children), 8)

    def test_condition_property(self):
        cond = StubExpression("cond")
        rule = ConditionalRule(
            [cond, QMARK(), StubExpression("t"), COLON(), StubExpression("f")]
        )
        self.assertIs(rule.condition, cond)

    def test_if_true_property(self):
        true_expr = StubExpression("yes")
        rule = ConditionalRule(
            [
                StubExpression("c"),
                QMARK(),
                true_expr,
                COLON(),
                StubExpression("f"),
            ]
        )
        self.assertIs(rule.if_true, true_expr)

    def test_if_false_property(self):
        false_expr = StubExpression("no")
        rule = ConditionalRule(
            [
                StubExpression("c"),
                QMARK(),
                StubExpression("t"),
                COLON(),
                false_expr,
            ]
        )
        self.assertIs(rule.if_false, false_expr)

    def test_serialize_format(self):
        rule = self._make_conditional("a", "b", "c")
        result = rule.serialize()
        self.assertEqual(result, "${a ? b : c}")

    def test_serialize_wraps_in_dollar_string(self):
        rule = self._make_conditional("x", "y", "z")
        result = rule.serialize()
        self.assertTrue(result.startswith("${"))
        self.assertTrue(result.endswith("}"))

    def test_serialize_no_double_wrap_inside_dollar_string(self):
        rule = self._make_conditional("x", "y", "z")
        ctx = SerializationContext(inside_dollar_string=True)
        result = rule.serialize(context=ctx)
        self.assertEqual(result, "x ? y : z")

    def test_serialize_force_parens_no_parent(self):
        """force_operation_parentheses with no parent → no wrapping."""
        rule = self._make_conditional("a", "b", "c")
        opts = SerializationOptions(force_operation_parentheses=True)
        result = rule.serialize(options=opts)
        # No parent, so _wrap_into_parentheses returns unchanged
        self.assertEqual(result, "${a ? b : c}")

    def test_serialize_force_parens_with_expression_parent(self):
        """force_operation_parentheses with ExpressionRule parent → wraps."""
        rule = self._make_conditional("a", "b", "c")
        # Nest inside another expression to set parent
        StubExpression("outer", children=[rule])
        opts = SerializationOptions(force_operation_parentheses=True)
        result = rule.serialize(options=opts)
        self.assertEqual(result, "${(a ? b : c)}")


# --- BinaryTermRule tests ---


class TestBinaryTermRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(BinaryTermRule.lark_name(), "binary_term")

    def test_construction_inserts_optional(self):
        rule = _make_binary_term("+", "b")
        # [BinaryOperatorRule, None, ExprTermRule]
        self.assertEqual(len(rule.children), 3)
        self.assertIsNone(rule.children[1])

    def test_binary_operator_property(self):
        op = _make_binary_operator("+")
        rhs = _make_expr_term("b")
        rule = BinaryTermRule([op, rhs])
        self.assertIs(rule.binary_operator, op)

    def test_expr_term_property(self):
        op = _make_binary_operator("+")
        rhs = _make_expr_term("b")
        rule = BinaryTermRule([op, rhs])
        self.assertIs(rule.expr_term, rhs)

    def test_serialize(self):
        rule = _make_binary_term("+", "b")
        result = rule.serialize()
        self.assertEqual(result, "+ b")

    def test_serialize_equals_operator(self):
        rule = _make_binary_term("==", "x")
        self.assertEqual(rule.serialize(), "== x")

    def test_serialize_and_operator(self):
        rule = _make_binary_term("&&", "y")
        self.assertEqual(rule.serialize(), "&& y")


# --- BinaryOpRule tests ---


class TestBinaryOpRule(TestCase):
    def _make_binary_op(self, lhs_val, op_str, rhs_val):
        lhs = _make_expr_term(lhs_val)
        bt = _make_binary_term(op_str, rhs_val)
        return BinaryOpRule([lhs, bt, None])

    def test_lark_name(self):
        self.assertEqual(BinaryOpRule.lark_name(), "binary_op")

    def test_expr_term_property(self):
        lhs = _make_expr_term("a")
        bt = _make_binary_term("+", "b")
        rule = BinaryOpRule([lhs, bt, None])
        self.assertIs(rule.expr_term, lhs)

    def test_binary_term_property(self):
        lhs = _make_expr_term("a")
        bt = _make_binary_term("+", "b")
        rule = BinaryOpRule([lhs, bt, None])
        self.assertIs(rule.binary_term, bt)

    def test_serialize_addition(self):
        rule = self._make_binary_op("a", "+", "b")
        self.assertEqual(rule.serialize(), "${a + b}")

    def test_serialize_equality(self):
        rule = self._make_binary_op("x", "==", "y")
        self.assertEqual(rule.serialize(), "${x == y}")

    def test_serialize_and(self):
        rule = self._make_binary_op("p", "&&", "q")
        self.assertEqual(rule.serialize(), "${p && q}")

    def test_serialize_multiply(self):
        rule = self._make_binary_op("a", "*", "b")
        self.assertEqual(rule.serialize(), "${a * b}")

    def test_serialize_no_double_wrap_inside_dollar_string(self):
        rule = self._make_binary_op("a", "+", "b")
        ctx = SerializationContext(inside_dollar_string=True)
        result = rule.serialize(context=ctx)
        self.assertEqual(result, "a + b")

    def test_serialize_force_parens_no_parent(self):
        """No parent → _wrap_into_parentheses returns unchanged."""
        rule = self._make_binary_op("a", "+", "b")
        opts = SerializationOptions(force_operation_parentheses=True)
        result = rule.serialize(options=opts)
        self.assertEqual(result, "${a + b}")

    def test_serialize_force_parens_with_expression_parent(self):
        """With ExpressionRule parent → wraps in parens."""
        rule = self._make_binary_op("a", "+", "b")
        StubExpression("outer", children=[rule])
        opts = SerializationOptions(force_operation_parentheses=True)
        result = rule.serialize(options=opts)
        self.assertEqual(result, "${(a + b)}")

    def test_serialize_force_parens_inside_dollar_string_with_parent(self):
        """Inside dollar string + parent → parens without extra ${}."""
        rule = self._make_binary_op("a", "+", "b")
        StubExpression("outer", children=[rule])
        opts = SerializationOptions(force_operation_parentheses=True)
        ctx = SerializationContext(inside_dollar_string=True)
        result = rule.serialize(options=opts, context=ctx)
        self.assertEqual(result, "(a + b)")


# --- UnaryOpRule tests ---


class TestUnaryOpRule(TestCase):
    def _make_unary(self, op_str, operand_val):
        token_cls = MINUS_TOKEN if op_str == "-" else NOT_TOKEN
        token = token_cls(op_str)
        expr_term = _make_expr_term(operand_val)
        return UnaryOpRule([token, expr_term])

    def test_lark_name(self):
        self.assertEqual(UnaryOpRule.lark_name(), "unary_op")

    def test_operator_property_minus(self):
        rule = self._make_unary("-", "x")
        self.assertEqual(rule.operator, "-")

    def test_operator_property_not(self):
        rule = self._make_unary("!", "x")
        self.assertEqual(rule.operator, "!")

    def test_expr_term_property(self):
        expr_term = _make_expr_term("x")
        token = MINUS_TOKEN("-")
        rule = UnaryOpRule([token, expr_term])
        self.assertIs(rule.expr_term, expr_term)

    def test_serialize_minus(self):
        rule = self._make_unary("-", "a")
        self.assertEqual(rule.serialize(), "${-a}")

    def test_serialize_not(self):
        rule = self._make_unary("!", "flag")
        self.assertEqual(rule.serialize(), "${!flag}")

    def test_serialize_no_double_wrap_inside_dollar_string(self):
        rule = self._make_unary("-", "x")
        ctx = SerializationContext(inside_dollar_string=True)
        result = rule.serialize(context=ctx)
        self.assertEqual(result, "-x")

    def test_serialize_force_parens_no_parent(self):
        rule = self._make_unary("-", "x")
        opts = SerializationOptions(force_operation_parentheses=True)
        result = rule.serialize(options=opts)
        self.assertEqual(result, "${-x}")

    def test_serialize_force_parens_with_expression_parent(self):
        rule = self._make_unary("-", "x")
        StubExpression("outer", children=[rule])
        opts = SerializationOptions(force_operation_parentheses=True)
        result = rule.serialize(options=opts)
        self.assertEqual(result, "${(-x)}")


# --- ExpressionRule._wrap_into_parentheses tests ---


class TestWrapIntoParenthesesMethod(TestCase):
    def test_returns_unchanged_when_inside_parentheses(self):
        expr = StubExpression("test")
        ctx = SerializationContext(inside_parentheses=True)
        result = expr._wrap_into_parentheses("${x}", context=ctx)
        self.assertEqual(result, "${x}")

    def test_returns_unchanged_when_no_parent(self):
        expr = StubExpression("test")
        result = expr._wrap_into_parentheses("${x}")
        self.assertEqual(result, "${x}")

    def test_returns_unchanged_when_parent_not_expression(self):
        expr = StubExpression("test")
        NonExpressionRule([expr])
        result = expr._wrap_into_parentheses("${x}")
        self.assertEqual(result, "${x}")

    def test_wraps_when_parent_is_expression(self):
        expr = StubExpression("test")
        StubExpression("outer", children=[expr])
        result = expr._wrap_into_parentheses("${x}")
        self.assertEqual(result, "${(x)}")

    def test_wraps_plain_string_when_parent_is_expression(self):
        expr = StubExpression("test")
        StubExpression("outer", children=[expr])
        result = expr._wrap_into_parentheses("a + b")
        self.assertEqual(result, "(a + b)")

    def test_expr_term_parent_with_expression_grandparent(self):
        """Parent is ExprTermRule, grandparent is ExpressionRule → wraps."""
        inner = StubExpression("test")
        expr_term = ExprTermRule([inner])
        # inner is now at expr_term._children[2], parent=expr_term
        StubExpression("grandparent", children=[expr_term])
        # expr_term.parent = grandparent (ExpressionRule)
        result = inner._wrap_into_parentheses("${x}")
        self.assertEqual(result, "${(x)}")

    def test_expr_term_parent_with_non_expression_grandparent(self):
        """Parent is ExprTermRule, grandparent is NOT ExpressionRule → no wrap."""
        inner = StubExpression("test")
        expr_term = ExprTermRule([inner])
        NonExpressionRule([expr_term])
        result = inner._wrap_into_parentheses("${x}")
        self.assertEqual(result, "${x}")

    def test_expr_term_parent_with_no_grandparent(self):
        """Parent is ExprTermRule with no parent → no wrap."""
        inner = StubExpression("test")
        ExprTermRule([inner])
        result = inner._wrap_into_parentheses("${x}")
        self.assertEqual(result, "${x}")
