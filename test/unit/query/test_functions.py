# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.query.body import DocumentView
from hcl2.query.functions import FunctionCallView
from hcl2.rules.functions import FunctionCallRule
from hcl2.walk import find_first


class TestFunctionCallView(TestCase):
    def test_name(self):
        doc = DocumentView.parse("x = length(var.list)\n")
        node = find_first(doc.raw, FunctionCallRule)
        self.assertIsNotNone(node)
        fv = FunctionCallView(node)
        self.assertEqual(fv.name, "length")

    def test_args(self):
        doc = DocumentView.parse("x = length(var.list)\n")
        node = find_first(doc.raw, FunctionCallRule)
        fv = FunctionCallView(node)
        self.assertEqual(len(fv.args), 1)

    def test_no_args(self):
        doc = DocumentView.parse("x = timestamp()\n")
        node = find_first(doc.raw, FunctionCallRule)
        fv = FunctionCallView(node)
        self.assertEqual(len(fv.args), 0)

    def test_no_ellipsis(self):
        doc = DocumentView.parse("x = length(var.list)\n")
        node = find_first(doc.raw, FunctionCallRule)
        fv = FunctionCallView(node)
        self.assertFalse(fv.has_ellipsis)

    def test_ellipsis(self):
        doc = DocumentView.parse("x = length(var.list...)\n")
        node = find_first(doc.raw, FunctionCallRule)
        fv = FunctionCallView(node)
        self.assertTrue(fv.has_ellipsis)

    def test_multiple_args(self):
        doc = DocumentView.parse('x = coalesce(var.a, var.b, "default")\n')
        node = find_first(doc.raw, FunctionCallRule)
        fv = FunctionCallView(node)
        self.assertEqual(len(fv.args), 3)
