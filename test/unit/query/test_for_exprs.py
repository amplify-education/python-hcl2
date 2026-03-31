# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.query.body import DocumentView
from hcl2.query.for_exprs import ForTupleView, ForObjectView
from hcl2.rules.for_expressions import ForTupleExprRule, ForObjectExprRule
from hcl2.walk import find_first


class TestForTupleView(TestCase):
    def test_iterator_name(self):
        doc = DocumentView.parse("x = [for item in var.list : item]\n")
        node = find_first(doc.raw, ForTupleExprRule)
        self.assertIsNotNone(node)
        fv = ForTupleView(node)
        self.assertEqual(fv.iterator_name, "item")

    def test_second_iterator_name_none(self):
        doc = DocumentView.parse("x = [for item in var.list : item]\n")
        node = find_first(doc.raw, ForTupleExprRule)
        fv = ForTupleView(node)
        self.assertIsNone(fv.second_iterator_name)

    def test_second_iterator_name(self):
        doc = DocumentView.parse("x = [for k, v in var.map : v]\n")
        node = find_first(doc.raw, ForTupleExprRule)
        fv = ForTupleView(node)
        self.assertEqual(fv.second_iterator_name, "v")

    def test_iterable(self):
        doc = DocumentView.parse("x = [for item in var.list : item]\n")
        node = find_first(doc.raw, ForTupleExprRule)
        fv = ForTupleView(node)
        self.assertIsNotNone(fv.iterable)

    def test_value_expr(self):
        doc = DocumentView.parse("x = [for item in var.list : item]\n")
        node = find_first(doc.raw, ForTupleExprRule)
        fv = ForTupleView(node)
        self.assertIsNotNone(fv.value_expr)

    def test_no_condition(self):
        doc = DocumentView.parse("x = [for item in var.list : item]\n")
        node = find_first(doc.raw, ForTupleExprRule)
        fv = ForTupleView(node)
        self.assertFalse(fv.has_condition)
        self.assertIsNone(fv.condition)

    def test_with_condition(self):
        doc = DocumentView.parse('x = [for item in var.list : item if item != ""]\n')
        node = find_first(doc.raw, ForTupleExprRule)
        fv = ForTupleView(node)
        self.assertTrue(fv.has_condition)
        self.assertIsNotNone(fv.condition)


class TestForObjectView(TestCase):
    def test_iterator_name(self):
        doc = DocumentView.parse("x = {for k, v in var.map : k => v}\n")
        node = find_first(doc.raw, ForObjectExprRule)
        self.assertIsNotNone(node)
        fv = ForObjectView(node)
        self.assertEqual(fv.iterator_name, "k")

    def test_key_expr(self):
        doc = DocumentView.parse("x = {for k, v in var.map : k => v}\n")
        node = find_first(doc.raw, ForObjectExprRule)
        fv = ForObjectView(node)
        self.assertIsNotNone(fv.key_expr)

    def test_value_expr(self):
        doc = DocumentView.parse("x = {for k, v in var.map : k => v}\n")
        node = find_first(doc.raw, ForObjectExprRule)
        fv = ForObjectView(node)
        self.assertIsNotNone(fv.value_expr)

    def test_no_ellipsis(self):
        doc = DocumentView.parse("x = {for k, v in var.map : k => v}\n")
        node = find_first(doc.raw, ForObjectExprRule)
        fv = ForObjectView(node)
        self.assertFalse(fv.has_ellipsis)

    def test_with_ellipsis(self):
        doc = DocumentView.parse("x = {for k, v in var.map : k => v...}\n")
        node = find_first(doc.raw, ForObjectExprRule)
        fv = ForObjectView(node)
        self.assertTrue(fv.has_ellipsis)

    def test_second_iterator_name(self):
        doc = DocumentView.parse("x = {for k, v in var.map : k => v}\n")
        node = find_first(doc.raw, ForObjectExprRule)
        fv = ForObjectView(node)
        self.assertEqual(fv.second_iterator_name, "v")

    def test_second_iterator_name_none(self):
        doc = DocumentView.parse("x = {for item in var.list : item => item}\n")
        node = find_first(doc.raw, ForObjectExprRule)
        fv = ForObjectView(node)
        self.assertIsNone(fv.second_iterator_name)

    def test_iterable(self):
        doc = DocumentView.parse("x = {for k, v in var.map : k => v}\n")
        node = find_first(doc.raw, ForObjectExprRule)
        fv = ForObjectView(node)
        self.assertIsNotNone(fv.iterable)

    def test_no_condition(self):
        doc = DocumentView.parse("x = {for k, v in var.map : k => v}\n")
        node = find_first(doc.raw, ForObjectExprRule)
        fv = ForObjectView(node)
        self.assertFalse(fv.has_condition)
        self.assertIsNone(fv.condition)

    def test_with_condition(self):
        doc = DocumentView.parse('x = {for k, v in var.map : k => v if k != ""}\n')
        node = find_first(doc.raw, ForObjectExprRule)
        fv = ForObjectView(node)
        self.assertTrue(fv.has_condition)
        self.assertIsNotNone(fv.condition)
