# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.rules.expressions import ExpressionRule
from hcl2.rules.for_expressions import (
    ForIntroRule,
    ForCondRule,
    ForTupleExprRule,
    ForObjectExprRule,
)
from hcl2.rules.literal_rules import IdentifierRule
from hcl2.rules.tokens import (
    NAME,
    LSQB,
    RSQB,
    LBRACE,
    RBRACE,
    FOR,
    IN,
    IF,
    COMMA,
    COLON,
    ELLIPSIS,
    FOR_OBJECT_ARROW,
)
from hcl2.utils import SerializationOptions, SerializationContext


# --- Stubs & helpers ---


class StubExpression(ExpressionRule):
    """Minimal concrete ExpressionRule that serializes to a fixed string."""

    def __init__(self, value):
        self._stub_value = value
        self._last_options = None
        super().__init__([], None)

    def serialize(self, options=SerializationOptions(), context=SerializationContext()):
        self._last_options = options
        return self._stub_value


def _make_identifier(name):
    return IdentifierRule([NAME(name)])


def _make_for_intro_single(iter_name, iterable_value):
    """Build ForIntroRule with a single iterator: for iter_name in iterable :"""
    return ForIntroRule(
        [
            FOR(),
            _make_identifier(iter_name),
            IN(),
            StubExpression(iterable_value),
            COLON(),
        ]
    )


def _make_for_intro_dual(iter1_name, iter2_name, iterable_value):
    """Build ForIntroRule with dual iterators: for iter1, iter2 in iterable :"""
    return ForIntroRule(
        [
            FOR(),
            _make_identifier(iter1_name),
            COMMA(),
            _make_identifier(iter2_name),
            IN(),
            StubExpression(iterable_value),
            COLON(),
        ]
    )


def _make_for_cond(value):
    """Build ForCondRule: if <value>"""
    return ForCondRule([IF(), StubExpression(value)])


# --- ForIntroRule tests ---


class TestForIntroRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(ForIntroRule.lark_name(), "for_intro")

    def test_first_iterator_single(self):
        ident = _make_identifier("v")
        rule = ForIntroRule([FOR(), ident, IN(), StubExpression("items"), COLON()])
        self.assertIs(rule.first_iterator, ident)

    def test_first_iterator_dual(self):
        i1 = _make_identifier("k")
        i2 = _make_identifier("v")
        rule = ForIntroRule(
            [FOR(), i1, COMMA(), i2, IN(), StubExpression("items"), COLON()]
        )
        self.assertIs(rule.first_iterator, i1)

    def test_second_iterator_none_when_single(self):
        rule = _make_for_intro_single("v", "items")
        self.assertIsNone(rule.second_iterator)

    def test_second_iterator_present_when_dual(self):
        i2 = _make_identifier("v")
        rule = ForIntroRule(
            [
                FOR(),
                _make_identifier("k"),
                COMMA(),
                i2,
                IN(),
                StubExpression("items"),
                COLON(),
            ]
        )
        self.assertIs(rule.second_iterator, i2)

    def test_iterable_property(self):
        iterable = StubExpression("items")
        rule = ForIntroRule([FOR(), _make_identifier("v"), IN(), iterable, COLON()])
        self.assertIs(rule.iterable, iterable)

    def test_serialize_single_iterator(self):
        rule = _make_for_intro_single("v", "items")
        self.assertEqual(rule.serialize(), "for v in items : ")

    def test_serialize_dual_iterator(self):
        rule = _make_for_intro_dual("k", "v", "items")
        self.assertEqual(rule.serialize(), "for k, v in items : ")

    def test_children_length(self):
        rule = _make_for_intro_single("v", "items")
        self.assertEqual(len(rule.children), 12)


# --- ForCondRule tests ---


class TestForCondRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(ForCondRule.lark_name(), "for_cond")

    def test_condition_expr_property(self):
        cond_expr = StubExpression("cond")
        rule = ForCondRule([IF(), cond_expr])
        self.assertIs(rule.condition_expr, cond_expr)

    def test_serialize(self):
        rule = _make_for_cond("cond")
        self.assertEqual(rule.serialize(), "if cond")

    def test_children_length(self):
        rule = _make_for_cond("cond")
        self.assertEqual(len(rule.children), 3)


# --- ForTupleExprRule tests ---


class TestForTupleExprRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(ForTupleExprRule.lark_name(), "for_tuple_expr")

    def test_for_intro_property(self):
        intro = _make_for_intro_single("v", "items")
        rule = ForTupleExprRule([LSQB(), intro, StubExpression("expr"), RSQB()])
        self.assertIs(rule.for_intro, intro)

    def test_value_expr_property(self):
        value_expr = StubExpression("expr")
        rule = ForTupleExprRule(
            [
                LSQB(),
                _make_for_intro_single("v", "items"),
                value_expr,
                RSQB(),
            ]
        )
        self.assertIs(rule.value_expr, value_expr)

    def test_condition_none(self):
        rule = ForTupleExprRule(
            [
                LSQB(),
                _make_for_intro_single("v", "items"),
                StubExpression("expr"),
                RSQB(),
            ]
        )
        self.assertIsNone(rule.condition)

    def test_condition_present(self):
        cond = _make_for_cond("cond")
        rule = ForTupleExprRule(
            [
                LSQB(),
                _make_for_intro_single("v", "items"),
                StubExpression("expr"),
                cond,
                RSQB(),
            ]
        )
        self.assertIsInstance(rule.condition, ForCondRule)
        self.assertIs(rule.condition, cond)

    def test_serialize_without_condition(self):
        rule = ForTupleExprRule(
            [
                LSQB(),
                _make_for_intro_single("v", "items"),
                StubExpression("expr"),
                RSQB(),
            ]
        )
        self.assertEqual(rule.serialize(), "${[for v in items : expr]}")

    def test_serialize_with_condition(self):
        rule = ForTupleExprRule(
            [
                LSQB(),
                _make_for_intro_single("v", "items"),
                StubExpression("expr"),
                _make_for_cond("cond"),
                RSQB(),
            ]
        )
        self.assertEqual(rule.serialize(), "${[for v in items : expr if cond]}")

    def test_serialize_inside_dollar_string(self):
        rule = ForTupleExprRule(
            [
                LSQB(),
                _make_for_intro_single("v", "items"),
                StubExpression("expr"),
                RSQB(),
            ]
        )
        ctx = SerializationContext(inside_dollar_string=True)
        self.assertEqual(rule.serialize(context=ctx), "[for v in items : expr]")


# --- ForObjectExprRule tests ---


class TestForObjectExprRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(ForObjectExprRule.lark_name(), "for_object_expr")

    def test_for_intro_property(self):
        intro = _make_for_intro_dual("k", "v", "items")
        rule = ForObjectExprRule(
            [
                LBRACE(),
                intro,
                StubExpression("key"),
                FOR_OBJECT_ARROW(),
                StubExpression("value"),
                RBRACE(),
            ]
        )
        self.assertIs(rule.for_intro, intro)

    def test_key_expr_property(self):
        key_expr = StubExpression("key")
        rule = ForObjectExprRule(
            [
                LBRACE(),
                _make_for_intro_dual("k", "v", "items"),
                key_expr,
                FOR_OBJECT_ARROW(),
                StubExpression("value"),
                RBRACE(),
            ]
        )
        self.assertIs(rule.key_expr, key_expr)

    def test_value_expr_property(self):
        value_expr = StubExpression("value")
        rule = ForObjectExprRule(
            [
                LBRACE(),
                _make_for_intro_dual("k", "v", "items"),
                StubExpression("key"),
                FOR_OBJECT_ARROW(),
                value_expr,
                RBRACE(),
            ]
        )
        self.assertIs(rule.value_expr, value_expr)

    def test_ellipsis_none(self):
        rule = ForObjectExprRule(
            [
                LBRACE(),
                _make_for_intro_dual("k", "v", "items"),
                StubExpression("key"),
                FOR_OBJECT_ARROW(),
                StubExpression("value"),
                RBRACE(),
            ]
        )
        self.assertIsNone(rule.ellipsis)

    def test_ellipsis_present(self):
        ellipsis = ELLIPSIS()
        rule = ForObjectExprRule(
            [
                LBRACE(),
                _make_for_intro_dual("k", "v", "items"),
                StubExpression("key"),
                FOR_OBJECT_ARROW(),
                StubExpression("value"),
                ellipsis,
                RBRACE(),
            ]
        )
        self.assertIs(rule.ellipsis, ellipsis)

    def test_condition_none(self):
        rule = ForObjectExprRule(
            [
                LBRACE(),
                _make_for_intro_dual("k", "v", "items"),
                StubExpression("key"),
                FOR_OBJECT_ARROW(),
                StubExpression("value"),
                RBRACE(),
            ]
        )
        self.assertIsNone(rule.condition)

    def test_condition_present(self):
        cond = _make_for_cond("cond")
        rule = ForObjectExprRule(
            [
                LBRACE(),
                _make_for_intro_dual("k", "v", "items"),
                StubExpression("key"),
                FOR_OBJECT_ARROW(),
                StubExpression("value"),
                cond,
                RBRACE(),
            ]
        )
        self.assertIsInstance(rule.condition, ForCondRule)
        self.assertIs(rule.condition, cond)

    def test_serialize_basic(self):
        rule = ForObjectExprRule(
            [
                LBRACE(),
                _make_for_intro_dual("k", "v", "items"),
                StubExpression("key"),
                FOR_OBJECT_ARROW(),
                StubExpression("value"),
                RBRACE(),
            ]
        )
        self.assertEqual(rule.serialize(), "${{for k, v in items : key => value}}")

    def test_serialize_with_ellipsis(self):
        rule = ForObjectExprRule(
            [
                LBRACE(),
                _make_for_intro_dual("k", "v", "items"),
                StubExpression("key"),
                FOR_OBJECT_ARROW(),
                StubExpression("value"),
                ELLIPSIS(),
                RBRACE(),
            ]
        )
        result = rule.serialize()
        self.assertIn("...", result)
        self.assertEqual(result, "${{for k, v in items : key => value...}}")

    def test_serialize_with_condition(self):
        rule = ForObjectExprRule(
            [
                LBRACE(),
                _make_for_intro_dual("k", "v", "items"),
                StubExpression("key"),
                FOR_OBJECT_ARROW(),
                StubExpression("value"),
                _make_for_cond("cond"),
                RBRACE(),
            ]
        )
        result = rule.serialize()
        self.assertIn("if cond", result)
        self.assertEqual(result, "${{for k, v in items : key => value if cond}}")

    def test_serialize_preserves_caller_options(self):
        value_expr = StubExpression("value")
        rule = ForObjectExprRule(
            [
                LBRACE(),
                _make_for_intro_dual("k", "v", "items"),
                StubExpression("key"),
                FOR_OBJECT_ARROW(),
                value_expr,
                RBRACE(),
            ]
        )
        caller_options = SerializationOptions(
            with_comments=True, preserve_heredocs=False
        )
        rule.serialize(options=caller_options)
        # value_expr should receive options with wrap_objects=True but
        # all other caller settings preserved
        self.assertTrue(value_expr._last_options.wrap_objects)
        self.assertTrue(value_expr._last_options.with_comments)
        self.assertFalse(value_expr._last_options.preserve_heredocs)
