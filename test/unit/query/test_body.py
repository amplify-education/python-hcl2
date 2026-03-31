# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.query.body import DocumentView, BodyView


class TestDocumentView(TestCase):
    def test_parse(self):
        doc = DocumentView.parse("x = 1\n")
        self.assertIsInstance(doc, DocumentView)

    def test_body(self):
        doc = DocumentView.parse("x = 1\n")
        body = doc.body
        self.assertIsInstance(body, BodyView)

    def test_blocks(self):
        doc = DocumentView.parse(
            'resource "aws_instance" "main" {\n  ami = "test"\n}\n'
        )
        blocks = doc.blocks("resource")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].block_type, "resource")

    def test_blocks_no_filter(self):
        doc = DocumentView.parse('resource "a" "b" {}\nvariable "c" {}\n')
        blocks = doc.blocks()
        self.assertEqual(len(blocks), 2)

    def test_blocks_with_labels(self):
        doc = DocumentView.parse(
            'resource "aws_instance" "main" {}\nresource "aws_s3_bucket" "data" {}\n'
        )
        blocks = doc.blocks("resource", "aws_instance")
        self.assertEqual(len(blocks), 1)

    def test_attributes(self):
        doc = DocumentView.parse("x = 1\ny = 2\n")
        attrs = doc.attributes()
        self.assertEqual(len(attrs), 2)

    def test_attributes_filtered(self):
        doc = DocumentView.parse("x = 1\ny = 2\n")
        attrs = doc.attributes("x")
        self.assertEqual(len(attrs), 1)

    def test_attribute(self):
        doc = DocumentView.parse("x = 1\ny = 2\n")
        attr = doc.attribute("x")
        self.assertIsNotNone(attr)
        self.assertEqual(attr.name, "x")

    def test_attribute_missing(self):
        doc = DocumentView.parse("x = 1\n")
        attr = doc.attribute("missing")
        self.assertIsNone(attr)

    def test_parse_file(self):
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as tmp:
            tmp.write("x = 1\n")
            tmp.flush()
            try:
                doc = DocumentView.parse_file(tmp.name)
                self.assertIsInstance(doc, DocumentView)
                attr = doc.attribute("x")
                self.assertIsNotNone(attr)
            finally:
                os.unlink(tmp.name)

    def test_blocks_label_too_many(self):
        doc = DocumentView.parse('resource "type" {}\n')
        # Ask for more labels than the block has
        blocks = doc.blocks("resource", "type", "extra")
        self.assertEqual(len(blocks), 0)

    def test_blocks_label_partial_mismatch(self):
        doc = DocumentView.parse('resource "aws_instance" "main" {}\n')
        blocks = doc.blocks("resource", "aws_s3_bucket")
        self.assertEqual(len(blocks), 0)


class TestBodyView(TestCase):
    def test_blocks(self):
        doc = DocumentView.parse('resource "a" "b" {}\n')
        body = doc.body
        blocks = body.blocks()
        self.assertEqual(len(blocks), 1)

    def test_attributes(self):
        doc = DocumentView.parse("x = 1\ny = 2\n")
        body = doc.body
        attrs = body.attributes()
        self.assertEqual(len(attrs), 2)
