from unittest import TestCase

from lark import Token, Tree
from lark.tree import Meta

from hcl2.rules.abstract import LarkElement, LarkToken, LarkRule
from hcl2.utils import SerializationOptions, SerializationContext


# --- Concrete stubs for testing ABCs ---


class ConcreteToken(LarkToken):
    @staticmethod
    def lark_name() -> str:
        return "TEST_TOKEN"

    @property
    def serialize_conversion(self):
        return str


class IntToken(LarkToken):
    @staticmethod
    def lark_name() -> str:
        return "INT_TOKEN"

    @property
    def serialize_conversion(self):
        return int


class ConcreteRule(LarkRule):
    @staticmethod
    def lark_name() -> str:
        return "test_rule"

    def serialize(self, options=SerializationOptions(), context=SerializationContext()):
        return "test"


# --- Tests ---


class TestLarkToken(TestCase):
    def test_init_stores_value(self):
        token = ConcreteToken("hello")
        self.assertEqual(token.value, "hello")

    def test_value_property(self):
        token = ConcreteToken(42)
        self.assertEqual(token.value, 42)

    def test_set_value(self):
        token = ConcreteToken("old")
        token.set_value("new")
        self.assertEqual(token.value, "new")

    def test_str(self):
        token = ConcreteToken("hello")
        self.assertEqual(str(token), "hello")

    def test_str_numeric(self):
        token = ConcreteToken(42)
        self.assertEqual(str(token), "42")

    def test_repr(self):
        token = ConcreteToken("hello")
        self.assertEqual(repr(token), "<LarkToken instance: TEST_TOKEN hello>")

    def test_to_lark_returns_token(self):
        token = ConcreteToken("val")
        lark_token = token.to_lark()
        self.assertIsInstance(lark_token, Token)
        self.assertEqual(lark_token.type, "TEST_TOKEN")
        self.assertEqual(lark_token, "val")

    def test_serialize_uses_conversion(self):
        token = ConcreteToken("hello")
        self.assertEqual(token.serialize(), "hello")

    def test_serialize_int_conversion(self):
        token = IntToken("42")
        result = token.serialize()
        self.assertEqual(result, 42)
        self.assertIsInstance(result, int)

    def test_lark_name(self):
        self.assertEqual(ConcreteToken.lark_name(), "TEST_TOKEN")


class TestLarkRule(TestCase):
    def test_init_sets_children(self):
        t1 = ConcreteToken("a")
        t2 = ConcreteToken("b")
        rule = ConcreteRule([t1, t2])
        self.assertEqual(rule.children, [t1, t2])

    def test_init_sets_parent_and_index(self):
        t1 = ConcreteToken("a")
        t2 = ConcreteToken("b")
        rule = ConcreteRule([t1, t2])
        self.assertIs(t1._parent, rule)
        self.assertIs(t2._parent, rule)
        self.assertEqual(t1._index, 0)
        self.assertEqual(t2._index, 1)

    def test_init_skips_none_children_for_parent_index(self):
        t1 = ConcreteToken("a")
        rule = ConcreteRule([None, t1, None])
        self.assertIs(t1._parent, rule)
        self.assertEqual(t1._index, 1)

    def test_init_with_meta(self):
        meta = Meta()
        rule = ConcreteRule([], meta)
        self.assertIs(rule._meta, meta)

    def test_init_without_meta(self):
        rule = ConcreteRule([])
        self.assertIsNotNone(rule._meta)

    def test_parent_property(self):
        child_rule = ConcreteRule([])
        parent_rule = ConcreteRule([child_rule])
        self.assertIs(child_rule.parent, parent_rule)

    def test_index_property(self):
        child_rule = ConcreteRule([])
        ConcreteRule([child_rule])
        self.assertEqual(child_rule.index, 0)

    def test_children_property(self):
        t = ConcreteToken("x")
        rule = ConcreteRule([t])
        self.assertEqual(rule.children, [t])

    def test_to_lark_builds_tree(self):
        t1 = ConcreteToken("a")
        t2 = ConcreteToken("b")
        rule = ConcreteRule([t1, t2])
        tree = rule.to_lark()
        self.assertIsInstance(tree, Tree)
        self.assertEqual(tree.data, "test_rule")
        self.assertEqual(len(tree.children), 2)

    def test_to_lark_skips_none_children(self):
        t1 = ConcreteToken("a")
        rule = ConcreteRule([None, t1, None])
        tree = rule.to_lark()
        self.assertEqual(len(tree.children), 1)
        self.assertEqual(tree.children[0], "a")

    def test_repr(self):
        rule = ConcreteRule([])
        self.assertEqual(repr(rule), "<LarkRule: ConcreteRule>")

    def test_nested_rules(self):
        inner = ConcreteRule([ConcreteToken("x")])
        outer = ConcreteRule([inner])
        self.assertIs(inner.parent, outer)
        tree = outer.to_lark()
        self.assertEqual(tree.data, "test_rule")
        self.assertEqual(len(tree.children), 1)
        self.assertIsInstance(tree.children[0], Tree)


class TestLarkElement(TestCase):
    def test_set_index(self):
        token = ConcreteToken("x")
        token.set_index(5)
        self.assertEqual(token._index, 5)

    def test_set_parent(self):
        token = ConcreteToken("x")
        parent = ConcreteRule([])
        token.set_parent(parent)
        self.assertIs(token._parent, parent)
