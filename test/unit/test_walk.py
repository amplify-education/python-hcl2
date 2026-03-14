# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.rules.base import AttributeRule, BlockRule, BodyRule, StartRule
from hcl2.rules.expressions import ExpressionRule, ExprTermRule
from hcl2.rules.literal_rules import IdentifierRule
from hcl2.rules.tokens import NAME, EQ, LBRACE, RBRACE, NL_OR_COMMENT
from hcl2.rules.whitespace import NewLineOrCommentRule
from hcl2.utils import SerializationOptions, SerializationContext
from hcl2.walk import (
    ancestors,
    find_all,
    find_by_predicate,
    find_first,
    walk,
    walk_rules,
    walk_semantic,
)


class StubExpression(ExpressionRule):
    def __init__(self, value):
        self._stub_value = value
        super().__init__([], None)

    def serialize(self, options=SerializationOptions(), context=SerializationContext()):
        return self._stub_value


def _make_identifier(name):
    return IdentifierRule([NAME(name)])


def _make_expr_term(value):
    return ExprTermRule([StubExpression(value)])


def _make_nlc(text):
    return NewLineOrCommentRule([NL_OR_COMMENT(text)])


def _make_attribute(name, value):
    return AttributeRule([_make_identifier(name), EQ(), _make_expr_term(value)])


def _make_block(labels, body_children=None):
    body = BodyRule(body_children or [])
    children = list(labels) + [LBRACE(), body, RBRACE()]
    return BlockRule(children)


class TestWalk(TestCase):
    def test_walk_single_node(self):
        attr = _make_attribute("x", 1)
        nodes = list(walk(attr))
        self.assertIn(attr, nodes)
        self.assertTrue(len(nodes) > 1)

    def test_walk_skips_none(self):
        attr = _make_attribute("x", 1)
        nodes = list(walk(attr))
        self.assertTrue(all(n is not None for n in nodes))

    def test_walk_includes_tokens(self):
        from hcl2.rules.abstract import LarkToken

        attr = _make_attribute("x", 1)
        nodes = list(walk(attr))
        has_token = any(isinstance(n, LarkToken) for n in nodes)
        self.assertTrue(has_token)


class TestWalkRules(TestCase):
    def test_only_rules(self):
        from hcl2.rules.abstract import LarkRule, LarkToken

        attr = _make_attribute("x", 1)
        rules = list(walk_rules(attr))
        for r in rules:
            self.assertIsInstance(r, LarkRule)
            self.assertNotIsInstance(r, LarkToken)


class TestWalkSemantic(TestCase):
    def test_no_whitespace(self):
        nlc = _make_nlc("\n")
        body = BodyRule([nlc, _make_attribute("x", 1)])
        rules = list(walk_semantic(body))
        for r in rules:
            self.assertNotIsInstance(r, NewLineOrCommentRule)

    def test_finds_attribute(self):
        body = BodyRule([_make_attribute("x", 1)])
        rules = list(walk_semantic(body))
        self.assertTrue(any(isinstance(r, AttributeRule) for r in rules))


class TestFindAll(TestCase):
    def test_finds_all_attributes(self):
        body = BodyRule([_make_attribute("x", 1), _make_attribute("y", 2)])
        start = StartRule([body])
        attrs = list(find_all(start, AttributeRule))
        self.assertEqual(len(attrs), 2)

    def test_finds_nested(self):
        BodyRule([_make_attribute("inner", 1)])  # unused but creates parent refs
        block = _make_block(
            [_make_identifier("resource")], [_make_attribute("outer", 2)]
        )
        outer_body = BodyRule([block])
        start = StartRule([outer_body])
        attrs = list(find_all(start, AttributeRule))
        self.assertEqual(len(attrs), 1)  # only outer, inner is in block's body

    def test_finds_blocks(self):
        block = _make_block([_make_identifier("resource")])
        body = BodyRule([block])
        start = StartRule([body])
        blocks = list(find_all(start, BlockRule))
        self.assertEqual(len(blocks), 1)


class TestFindFirst(TestCase):
    def test_finds_first(self):
        body = BodyRule([_make_attribute("x", 1), _make_attribute("y", 2)])
        start = StartRule([body])
        attr = find_first(start, AttributeRule)
        self.assertIsNotNone(attr)
        self.assertEqual(attr.identifier.serialize(), "x")

    def test_returns_none(self):
        body = BodyRule([])
        start = StartRule([body])
        result = find_first(start, AttributeRule)
        self.assertIsNone(result)


class TestFindByPredicate(TestCase):
    def test_predicate(self):
        attr1 = _make_attribute("x", 1)
        attr2 = _make_attribute("y", 2)
        body = BodyRule([attr1, attr2])
        found = list(
            find_by_predicate(
                body,
                lambda n: isinstance(n, AttributeRule)
                and n.identifier.serialize() == "x",
            )
        )
        self.assertEqual(len(found), 1)
        self.assertIs(found[0], attr1)


class TestAncestors(TestCase):
    def test_parent_chain(self):
        attr = _make_attribute("x", 1)
        body = BodyRule([attr])
        start = StartRule([body])
        chain = list(ancestors(attr))
        self.assertEqual(chain[0], body)
        self.assertEqual(chain[1], start)

    def test_empty_for_root(self):
        body = BodyRule([])
        start = StartRule([body])
        chain = list(ancestors(start))
        self.assertEqual(len(chain), 0)
