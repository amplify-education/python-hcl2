# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.query.body import DocumentView
from hcl2.utils import SerializationOptions


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


class TestAttributeViewAdjacentComments(TestCase):
    """Tests for adjacent comment merging in AttributeView.to_dict()."""

    _OPTS = SerializationOptions(with_comments=True)

    def test_adjacent_comment(self):
        doc = DocumentView.parse("# about x\nx = 1\n")
        attr = doc.body.attributes("x")[0]
        result = attr.to_dict(options=self._OPTS)
        self.assertEqual(result["__comments__"], [{"value": "about x"}])

    def test_no_comments_without_option(self):
        doc = DocumentView.parse("# about x\nx = 1\n")
        attr = doc.body.attributes("x")[0]
        result = attr.to_dict()
        self.assertNotIn("__comments__", result)

    def test_no_adjacent_comments(self):
        doc = DocumentView.parse("x = 1\n")
        attr = doc.body.attributes("x")[0]
        result = attr.to_dict(options=self._OPTS)
        self.assertNotIn("__comments__", result)
