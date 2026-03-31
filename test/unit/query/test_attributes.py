# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.query.body import DocumentView


class TestAttributeView(TestCase):
    def test_name(self):
        doc = DocumentView.parse("x = 1\n")
        attr = doc.attribute("x")
        self.assertEqual(attr.name, "x")

    def test_value_int(self):
        doc = DocumentView.parse("x = 42\n")
        attr = doc.attribute("x")
        self.assertEqual(attr.value, 42)

    def test_value_string(self):
        doc = DocumentView.parse('x = "hello"\n')
        attr = doc.attribute("x")
        self.assertEqual(attr.value, '"hello"')

    def test_value_node(self):
        doc = DocumentView.parse("x = 42\n")
        attr = doc.attribute("x")
        vn = attr.value_node
        self.assertIsNotNone(vn)

    def test_to_hcl(self):
        doc = DocumentView.parse("x = 42\n")
        attr = doc.attribute("x")
        hcl = attr.to_hcl()
        self.assertIn("x", hcl)
        self.assertIn("42", hcl)

    def test_to_dict(self):
        doc = DocumentView.parse("x = 42\n")
        attr = doc.attribute("x")
        result = attr.to_dict()
        self.assertEqual(result, {"x": 42})
