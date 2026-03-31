# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.query._base import NodeView, view_for
from hcl2.rules.base import AttributeRule, BodyRule, StartRule
from hcl2.rules.expressions import ExpressionRule, ExprTermRule
from hcl2.rules.literal_rules import IdentifierRule
from hcl2.rules.tokens import NAME, EQ
from hcl2.utils import SerializationContext, SerializationOptions

# Ensure views are registered
import hcl2.query  # noqa: F401,E402  pylint: disable=unused-import


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


def _make_attribute(name, value):
    return AttributeRule([_make_identifier(name), EQ(), _make_expr_term(value)])


class TestViewFor(TestCase):
    def test_attribute_dispatches(self):
        attr = _make_attribute("x", 1)
        view = view_for(attr)
        self.assertEqual(type(view).__name__, "AttributeView")

    def test_body_dispatches(self):
        body = BodyRule([])
        view = view_for(body)
        self.assertEqual(type(view).__name__, "BodyView")

    def test_start_dispatches(self):
        body = BodyRule([])
        start = StartRule([body])
        view = view_for(start)
        self.assertEqual(type(view).__name__, "DocumentView")

    def test_fallback_to_nodeview(self):
        expr = StubExpression("val")
        view = view_for(expr)
        self.assertIsInstance(view, NodeView)


class TestNodeView(TestCase):
    def test_raw(self):
        attr = _make_attribute("x", 1)
        view = NodeView(attr)
        self.assertIs(view.raw, attr)

    def test_parent_view(self):
        attr = _make_attribute("x", 1)
        BodyRule([attr])  # sets parent on attr
        view = view_for(attr)
        parent = view.parent_view
        self.assertIsNotNone(parent)
        self.assertEqual(type(parent).__name__, "BodyView")

    def test_parent_view_none_for_root(self):
        body = BodyRule([])
        start = StartRule([body])
        view = view_for(start)
        self.assertIsNone(view.parent_view)

    def test_to_dict(self):
        attr = _make_attribute("x", 1)
        view = view_for(attr)
        result = view.to_dict()
        self.assertEqual(result, {"x": 1})

    def test_to_hcl(self):
        # Use a real parsed tree to avoid lark_name issues with stubs
        from hcl2.query.body import DocumentView

        doc = DocumentView.parse("x = 1\n")
        attr_view = doc.attribute("x")
        hcl = attr_view.to_hcl()
        self.assertIn("x", hcl)
        self.assertIn("1", hcl)

    def test_find_all(self):
        attr1 = _make_attribute("x", 1)
        attr2 = _make_attribute("y", 2)
        body = BodyRule([attr1, attr2])
        start = StartRule([body])
        view = view_for(start)
        found = view.find_all(AttributeRule)
        self.assertEqual(len(found), 2)

    def test_walk_semantic(self):
        attr = _make_attribute("x", 1)
        body = BodyRule([attr])
        start = StartRule([body])
        view = view_for(start)
        nodes = view.walk_semantic()
        self.assertTrue(len(nodes) > 0)

    def test_repr(self):
        attr = _make_attribute("x", 1)
        view = view_for(attr)
        r = repr(view)
        self.assertIn("AttributeView", r)

    def test_find_by_predicate(self):
        from hcl2.query.body import DocumentView

        doc = DocumentView.parse("x = 1\ny = 2\n")
        found = doc.find_by_predicate(lambda n: hasattr(n, "name") and n.name == "x")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].name, "x")

    def test_find_by_predicate_no_match(self):
        from hcl2.query.body import DocumentView

        doc = DocumentView.parse("x = 1\n")
        found = doc.find_by_predicate(lambda n: False)
        self.assertEqual(len(found), 0)

    def test_walk_rules(self):
        from hcl2.query.body import DocumentView

        doc = DocumentView.parse("x = 1\n")
        rules = doc.walk_rules()
        self.assertTrue(len(rules) > 0)

    def test_to_dict_with_options(self):
        from hcl2.query.body import DocumentView

        doc = DocumentView.parse("x = 1\n")
        attr = doc.attribute("x")
        opts = SerializationOptions(with_meta=False)
        result = attr.to_dict(options=opts)
        self.assertEqual(result, {"x": 1})

    def test_view_for_mro_fallback(self):
        # ExprTermRule is not directly registered but its parent ExpressionRule
        # is also not registered — should fall back to NodeView
        expr = StubExpression("val")
        view = view_for(expr)
        self.assertIsInstance(view, NodeView)
        self.assertEqual(type(view), NodeView)
