# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.query.body import DocumentView
from hcl2.query.containers import ObjectView, TupleView
from hcl2.rules.containers import ObjectRule, TupleRule
from hcl2.walk import find_first


class TestTupleView(TestCase):
    def test_elements(self):
        doc = DocumentView.parse("x = [1, 2, 3]\n")
        attr = doc.attribute("x")
        tuple_node = find_first(attr.raw, TupleRule)
        self.assertIsNotNone(tuple_node)
        tv = TupleView(tuple_node)
        self.assertEqual(len(tv), 3)

    def test_getitem(self):
        doc = DocumentView.parse("x = [1, 2, 3]\n")
        attr = doc.attribute("x")
        tuple_node = find_first(attr.raw, TupleRule)
        tv = TupleView(tuple_node)
        elem = tv[0]
        self.assertIsNotNone(elem)

    def test_elements_property(self):
        doc = DocumentView.parse("x = [1, 2, 3]\n")
        attr = doc.attribute("x")
        tuple_node = find_first(attr.raw, TupleRule)
        tv = TupleView(tuple_node)
        elems = tv.elements
        self.assertEqual(len(elems), 3)


class TestObjectView(TestCase):
    def test_entries(self):
        doc = DocumentView.parse("x = {\n  a = 1\n  b = 2\n}\n")
        attr = doc.attribute("x")
        obj_node = find_first(attr.raw, ObjectRule)
        self.assertIsNotNone(obj_node)
        ov = ObjectView(obj_node)
        entries = ov.entries
        self.assertEqual(len(entries), 2)

    def test_keys(self):
        doc = DocumentView.parse("x = {\n  a = 1\n  b = 2\n}\n")
        attr = doc.attribute("x")
        obj_node = find_first(attr.raw, ObjectRule)
        ov = ObjectView(obj_node)
        self.assertEqual(ov.keys, ["a", "b"])

    def test_get(self):
        doc = DocumentView.parse("x = {\n  a = 1\n  b = 2\n}\n")
        attr = doc.attribute("x")
        obj_node = find_first(attr.raw, ObjectRule)
        ov = ObjectView(obj_node)
        val = ov.get("a")
        self.assertIsNotNone(val)

    def test_get_missing(self):
        doc = DocumentView.parse("x = {\n  a = 1\n}\n")
        attr = doc.attribute("x")
        obj_node = find_first(attr.raw, ObjectRule)
        ov = ObjectView(obj_node)
        val = ov.get("missing")
        self.assertIsNone(val)
