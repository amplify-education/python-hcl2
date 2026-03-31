# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.query.body import DocumentView


class TestBlockView(TestCase):
    def test_block_type(self):
        doc = DocumentView.parse('resource "aws_instance" "main" {}\n')
        block = doc.blocks("resource")[0]
        self.assertEqual(block.block_type, "resource")

    def test_labels(self):
        doc = DocumentView.parse('resource "aws_instance" "main" {}\n')
        block = doc.blocks("resource")[0]
        self.assertEqual(block.labels, ["resource", "aws_instance", "main"])

    def test_name_labels(self):
        doc = DocumentView.parse('resource "aws_instance" "main" {}\n')
        block = doc.blocks("resource")[0]
        self.assertEqual(block.name_labels, ["aws_instance", "main"])

    def test_body(self):
        doc = DocumentView.parse('resource "type" "name" {\n  ami = "test"\n}\n')
        block = doc.blocks("resource")[0]
        body = block.body
        self.assertIsNotNone(body)

    def test_nested_attribute(self):
        doc = DocumentView.parse('resource "type" "name" {\n  ami = "test"\n}\n')
        block = doc.blocks("resource")[0]
        attr = block.attribute("ami")
        self.assertIsNotNone(attr)
        self.assertEqual(attr.name, "ami")

    def test_nested_blocks(self):
        hcl = 'resource "type" "name" {\n  provisioner "local-exec" {\n    command = "echo"\n  }\n}\n'
        doc = DocumentView.parse(hcl)
        block = doc.blocks("resource")[0]
        inner = block.blocks("provisioner")
        self.assertEqual(len(inner), 1)

    def test_to_hcl(self):
        doc = DocumentView.parse('resource "type" "name" {\n  ami = "test"\n}\n')
        block = doc.blocks("resource")[0]
        hcl = block.to_hcl()
        self.assertIn("resource", hcl)
        self.assertIn("ami", hcl)

    def test_identifier_label(self):
        doc = DocumentView.parse("locals {\n  x = 1\n}\n")
        block = doc.blocks("locals")[0]
        self.assertEqual(block.block_type, "locals")
        self.assertEqual(block.name_labels, [])

    def test_attributes_list(self):
        doc = DocumentView.parse('resource "type" "name" {\n  a = 1\n  b = 2\n}\n')
        block = doc.blocks("resource")[0]
        attrs = block.attributes()
        self.assertEqual(len(attrs), 2)

    def test_attributes_filtered(self):
        doc = DocumentView.parse('resource "type" "name" {\n  a = 1\n  b = 2\n}\n')
        block = doc.blocks("resource")[0]
        attrs = block.attributes("a")
        self.assertEqual(len(attrs), 1)
        self.assertEqual(attrs[0].name, "a")
