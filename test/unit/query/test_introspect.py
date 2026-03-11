# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.query.body import DocumentView
from hcl2.query.introspect import build_schema, describe_results


class TestDescribeResults(TestCase):
    def test_describe_block(self):
        doc = DocumentView.parse('resource "aws_instance" "main" {}\n')
        blocks = doc.blocks("resource")
        result = describe_results(blocks)
        self.assertIn("results", result)
        self.assertEqual(len(result["results"]), 1)
        desc = result["results"][0]
        self.assertEqual(desc["type"], "BlockView")
        self.assertIn("properties", desc)
        self.assertIn("methods", desc)
        self.assertIn("block_type", desc["summary"])

    def test_describe_attribute(self):
        doc = DocumentView.parse("x = 1\n")
        attrs = doc.attributes("x")
        result = describe_results(attrs)
        desc = result["results"][0]
        self.assertEqual(desc["type"], "AttributeView")
        self.assertIn("name", desc["summary"])

    def test_describe_primitive(self):
        result = describe_results([42])
        desc = result["results"][0]
        self.assertEqual(desc["type"], "int")
        self.assertIn("42", desc["value"])


class TestBuildSchema(TestCase):
    def test_schema_has_views(self):
        schema = build_schema()
        self.assertIn("views", schema)
        self.assertIn("DocumentView", schema["views"])
        self.assertIn("BlockView", schema["views"])
        self.assertIn("AttributeView", schema["views"])
        self.assertIn("NodeView", schema["views"])

    def test_schema_has_eval_namespace(self):
        schema = build_schema()
        self.assertIn("eval_namespace", schema)
        self.assertIn("builtins", schema["eval_namespace"])
        self.assertIn("variables", schema["eval_namespace"])
        self.assertIn("len", schema["eval_namespace"]["builtins"])

    def test_schema_view_has_properties(self):
        schema = build_schema()
        doc_schema = schema["views"]["DocumentView"]
        self.assertIn("properties", doc_schema)
        self.assertIn("body", doc_schema["properties"])

    def test_schema_view_has_methods(self):
        schema = build_schema()
        doc_schema = schema["views"]["DocumentView"]
        self.assertIn("methods", doc_schema)

    def test_schema_view_wraps(self):
        schema = build_schema()
        block_schema = schema["views"]["BlockView"]
        self.assertEqual(block_schema["wraps"], "BlockRule")

    def test_schema_nodeview_no_wraps(self):
        schema = build_schema()
        nv_schema = schema["views"]["NodeView"]
        self.assertNotIn("wraps", nv_schema)

    def test_describe_body_view_no_summary(self):
        doc = DocumentView.parse("x = 1\n")
        result = describe_results([doc.body])
        desc = result["results"][0]
        self.assertEqual(desc["type"], "BodyView")
        self.assertNotIn("summary", desc)

    def test_describe_document_view(self):
        doc = DocumentView.parse("x = 1\n")
        result = describe_results([doc])
        desc = result["results"][0]
        self.assertEqual(desc["type"], "DocumentView")

    def test_schema_static_methods(self):
        schema = build_schema()
        doc_schema = schema["views"]["DocumentView"]
        # DocumentView has parse and parse_file static methods
        self.assertIn("static_methods", doc_schema)
